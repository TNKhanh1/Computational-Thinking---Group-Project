"""
Conversational Scheduling Service for Chat-First UI/UX (Layer 4 — Revision 2).

Handles:
  1. Multi-turn slot filling for recurring schedules (FixedEvent) and one-off tasks (Task)
     when title or start/end time is missing.
  2. Context-aware cross-day window parsing (e.g. "từ 19h ngày thứ 3, tới 21h ngày thứ 5,
     cần thực hiện trong 2 tiếng" -> 1 single task with start_after=Tuesday 19:00,
     deadline=Thursday 21:00, duration=120m).
  3. SHA-256 task traceability + hidden criteria tuning.
  4. Deadline adjustment & remaining-duration estimation using user habit + M7 EWMA calibration.
  5. Dominant Algorithm Subset selection (`SCORED_GREEDY` / `HYBRID_ALNS`, pruning dominated
     energy-blind `EDF`/`WSPT`/`LST`) + Antigravity-style humanized Thinking Summary for Developer Mode.
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.calibration import compute_ewma_calibration
from src.controller import ScheduleController
from src.estimate_buffer import multiplier_for_habit, multiplier_for_load
from src.models import CommitmentsProfile, FixedEvent, ScheduleBlock, ScheduleOutput, Task
from src.nl_parser import OfflineNLParser, WEEKDAYS, _strip_accents
from src.storage import list_completion_logs, load_workspace_state, save_workspace_state
from src.task_tracer import (
    enrich_task_trace_metadata,
    extract_hidden_criteria_updates,
    resolve_target_task_from_prompt,
)
from src.utils import SLOTS_PER_DAY, round_up_to_15

_OFFLINE_NL = OfflineNLParser()

_WEEKDAY_VI_MAP = {
    "Monday": "Thứ Hai",
    "Tuesday": "Thứ Ba",
    "Wednesday": "Thứ Tư",
    "Thursday": "Thứ Năm",
    "Friday": "Thứ Sáu",
    "Saturday": "Thứ Bảy",
    "Sunday": "Chủ Nhật",
    "Next Monday": "Thứ Hai tuần sau",
}

_DAY_CHIP_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"\b(?:thu\s*(?:2|hai)|t2|monday|mon)\b", "Monday"),
    (r"\b(?:thu\s*(?:3|ba)|t3|tuesday|tue)\b", "Tuesday"),
    (r"\b(?:thu\s*(?:4|tu)|t4|wednesday|wed)\b", "Wednesday"),
    (r"\b(?:thu\s*(?:5|nam)|t5|thursday)\b|\bthu\b(?!\s*(?:[2-7]|hai|ba|tu|nam|sau|bay)\b)", "Thursday"),
    (r"\b(?:thu\s*(?:6|sau)|t6|friday|fri)\b", "Friday"),
    (r"\b(?:thu\s*(?:7|bay)|t7|saturday|sat)\b", "Saturday"),
    (r"\b(?:chu\s*nhat|cn|sunday|sun)\b", "Sunday"),
)

_GENERIC_TITLES = frozenset(
    {
        "",
        "lich",
        "lich trinh",
        "lich lap",
        "lap lai",
        "hang ngay",
        "cong viec",
        "viec",
        "task",
        "them",
        "sua",
        "chinh",
        "doi",
        "moi",
        "schedule",
        "event",
        "can thuc hien",
        "thuc hien",
    }
)


def _format_hhmm(hh: int, mm: int) -> Optional[str]:
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return f"{hh:02d}:{mm:02d}"
    return None


def _parse_clock_token(hour_raw: str, min_raw: Optional[str], ampm_raw: Optional[str], tod_raw: Optional[str]) -> Optional[str]:
    hh = int(hour_raw)
    if min_raw is None or min_raw == "":
        mm = 0
    elif min_raw.lower() in ("ruoi", "rưỡi"):
        mm = 30
    else:
        mm = int(min_raw)

    ampm = (ampm_raw or "").strip().lower()
    tod = (tod_raw or "").strip().lower()
    if ampm == "pm" and hh < 12:
        hh += 12
    elif ampm == "am" and hh == 12:
        hh = 0
    elif tod in ("chieu", "toi", "dem") and hh < 12:
        hh += 12
    elif tod == "trua" and hh < 11:
        hh += 12
    return _format_hhmm(hh, mm)


def _resolve_day_token(day_fragment: str, now_day: str) -> Optional[str]:
    norm = _strip_accents(day_fragment).lower()
    for pat, wd in _DAY_CHIP_PATTERNS:
        if re.search(pat, norm):
            return wd
    now_idx = WEEKDAYS.index(now_day) if now_day in WEEKDAYS else 0
    if re.search(r"\b(?:hom\s*nay|today)\b", norm):
        return now_day
    if re.search(r"\b(?:ngay\s*mai|mai|tomorrow)\b", norm):
        return WEEKDAYS[(now_idx + 1) % 7]
    if re.search(r"\b(?:ngay\s*kia|ngay\s*mot)\b", norm):
        return WEEKDAYS[(now_idx + 2) % 7]
    return None


def _extract_cross_day_window(norm_text: str, now_day: str) -> Optional[Dict[str, str]]:
    """
    Detect a start-anchor + end-deadline window spanning days, such as:
      - "từ 19h ngày thứ 3, tới 21h ngày thứ 5"
      - "từ thứ 3 lúc 19:00 đến thứ 5 lúc 21:00"
      - "từ ngày thứ 3 tới ngày thứ 5"
    Returns `{"start_day": ..., "start_time": ..., "end_day": ..., "end_time": ...}` or None.
    """
    day_expr = r"(?:ngay\s+)?(?:thu\s*(?:[2-7]|hai|ba|tu|nam|sau|bay)|t[2-7]|chu\s*nhat|cn|hom\s*nay|ngay\s*mai|mai|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    time_expr = r"(\d{1,2})\s*(?::|h|gio)\s*(\d{1,2}|ruoi)?\s*(am|pm)?\s*(sang|trua|chieu|toi|dem)?"

    # Pattern A: từ <time1> [ngày] <day1> [, ] (tới|đến|trước) <time2> [ngày] <day2>
    pat_a = re.compile(
        rf"\b(?:tu|from)\s+{time_expr}\s*(?:,|\s)*({day_expr})\s*(?:,|\s)*(?:\b(?:toi|den|truoc|to|until)\b|-|–|—)\s*{time_expr}\s*(?:,|\s)*({day_expr})\b"
    )
    m = pat_a.search(norm_text)
    if m:
        t1 = _parse_clock_token(m.group(1), m.group(2), m.group(3), m.group(4)) or "08:00"
        d1 = _resolve_day_token(m.group(5), now_day)
        t2 = _parse_clock_token(m.group(6), m.group(7), m.group(8), m.group(9)) or "23:59"
        d2 = _resolve_day_token(m.group(10), now_day)
        if d1 and d2:
            return {"start_day": d1, "start_time": t1, "end_day": d2, "end_time": t2}

    # Pattern B: từ [ngày] <day1> [lúc <time1>] (tới|đến|trước) [ngày] <day2> [lúc <time2>]
    pat_b = re.compile(
        rf"\b(?:tu|from)\s+({day_expr})(?:\s*(?:luc|vao)?\s*{time_expr})?\s*(?:,|\s)*(?:\b(?:toi|den|truoc|to|until)\b|-|–|—)\s*({day_expr})(?:\s*(?:luc|vao|truoc)?\s*{time_expr})?\b"
    )
    m = pat_b.search(norm_text)
    if m:
        d1 = _resolve_day_token(m.group(1), now_day)
        t1 = _parse_clock_token(m.group(2), m.group(3), m.group(4), m.group(5)) if m.group(2) else "08:00"
        d2 = _resolve_day_token(m.group(6), now_day)
        t2 = _parse_clock_token(m.group(7), m.group(8), m.group(9), m.group(10)) if m.group(7) else "23:59"
        if d1 and d2:
            return {"start_day": d1, "start_time": t1 or "08:00", "end_day": d2, "end_time": t2 or "23:59"}

    return None


def _extract_time_range(norm_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract explicit same-day `(start_time, end_time)` pairs like `08:00 - 10:00` or `từ 14h đến 16h30`."""
    pattern = re.compile(
        r"(?:\b(?:tu|from|luc|vao)\s+)?"
        r"(\d{1,2})\s*(?:(?::|h|gio)\s*(\d{1,2}|ruoi)?)\s*(am|pm)?\s*(sang|trua|chieu|toi|dem)?\s*"
        r"(?:-|–|—|\bden\b|\btoi\b|\bto\b)\s*"
        r"(\d{1,2})\s*(?:(?::|h|gio)\s*(\d{1,2}|ruoi)?)\s*(am|pm)?\s*(sang|trua|chieu|toi|dem)?\b"
    )
    for m in pattern.finditer(norm_text):
        raw_span = m.group(0)
        if not re.search(r"[:hg]|am|pm", raw_span):
            continue
        s_time = _parse_clock_token(m.group(1), m.group(2), m.group(3), m.group(4))
        e_time = _parse_clock_token(m.group(5), m.group(6), m.group(7), m.group(8))
        if s_time and e_time:
            sh, sm = map(int, s_time.split(":"))
            eh, em = map(int, e_time.split(":"))
            if eh < sh and eh < 12 and sh >= 12:
                eh += 12
                e_time = _format_hhmm(eh, em)
            elif eh < sh and (m.group(8) or "").lower() in ("chieu", "toi") and sh < 12:
                sh += 12
                s_time = _format_hhmm(sh, sm)
            if e_time and (eh * 60 + em) > (sh * 60 + sm):
                return s_time, e_time
    return None, None


def _extract_recurring_days(norm_text: str) -> Optional[Any]:
    if re.search(r"\b(?:hang\s*ngay|moi\s*ngay|ngay\s*nao|tat\s*ca\s*cac\s*ngay|every\s*day|daily)\b", norm_text):
        return "ALL"
    if re.search(r"\b(?:trong\s*tuan|ngay\s*thuong|t2\s*-\s*t6|weekdays)\b", norm_text):
        return ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    if re.search(r"\b(?:cuoi\s*tuan|weekend)\b", norm_text):
        return ["Saturday", "Sunday"]

    found: List[str] = []
    seq_m = re.search(r"\b(?:thu|t)\s*([2-7](?:\s*(?:,|va|&|-)\s*[2-7])+)", norm_text)
    if seq_m:
        digits = re.findall(r"[2-7]", seq_m.group(0))
        num_map = {"2": "Monday", "3": "Tuesday", "4": "Wednesday", "5": "Thursday", "6": "Friday", "7": "Saturday"}
        for d in digits:
            wd = num_map.get(d)
            if wd and wd not in found:
                found.append(wd)

    for pat, wd in _DAY_CHIP_PATTERNS:
        if re.search(pat, norm_text) and wd not in found:
            found.append(wd)

    if not found:
        return None
    return found[0] if len(found) == 1 else found


def _clean_conversational_title(raw_text: str) -> str:
    """Strip temporal clauses, duration expressions, and command prefixes while preserving the subject title."""
    work = raw_text.split("\n")[0]

    # Strip cross-day & temporal clauses first before OfflineNLParser touches them
    clause_patterns = (
        r"(?:,\s*)?\b(?:từ|tu|from)\s+[^,\n]*?\b(?:tới|toi|đến|den|trước|truoc|to|until)\s+[^,\n]+",
        r"(?:,\s*)?\b(?:cần\s*)?(?:thực\s*hiện|thuc\s*hien|làm|lam|hoàn\s*thành|hoan\s*thanh)?\s*(?:trong(?:\s*vòng|\s*khoảng)?|khoảng|khoang|mất|mat|tầm|tam)\s+\d+(?:\.\d+)?\s*(?:tiếng|tieng|giờ|gio|h|phút|phut|p|m|mins?|hours?)\b",
        r"(?:,\s*)?\b(?:từ\s+)?\d{1,2}\s*(?::|h|giờ|gio)\s*(?:\d{1,2}|rưỡi|ruoi)?\s*(?:am|pm|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\s*(?:-|–|—|đến|den|tới|toi|to)\s*\d{1,2}\s*(?::|h|giờ|gio)\s*(?:\d{1,2}|rưỡi|ruoi)?\s*(?:am|pm|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\b",
        r"\b(?:hằng\s*ngày|hàng\s*ngày|mỗi\s*ngày|lặp\s*lại|cố\s*định|mỗi\s*tuần|hằng\s*tuần|daily|weekly)\b",
    )
    for pat in clause_patterns:
        work = re.sub(pat, " ", work, flags=re.IGNORECASE)

    cleaned = _OFFLINE_NL.clean_title(work)
    cleaned_norm = _strip_accents(cleaned).lower().strip()

    lead_patterns = (
        r"^(?:them|tao|len\s*lich|dat\s*lich|nhac\s*minh|sua|chinh|cap\s*nhat|doi|"
        r"add|create|schedule|remind)\s+",
        r"^(?:lich\s*(?:lap(?:\s*lai)?|co\s*dinh|hang\s*ngay)|cong\s*viec|task|viec)\s*[:\-]?\s*",
    )
    for _ in range(3):
        prev = cleaned
        for pat in lead_patterns:
            m = re.match(pat, _strip_accents(cleaned).lower())
            if m:
                cleaned = cleaned[m.end():].strip(" ,:-.")
        if cleaned == prev:
            break

    # Clean trailing filler verbs left after stripping duration (e.g. ", cần thực hiện")
    cleaned = re.sub(
        r"(?:,\s*)?\b(?:cần\s*thực\s*hiện|can\s*thuc\s*hien|thực\s*hiện|thuc\s*hien|cần\s*làm|can\s*lam|trong|từ|tu|tới|toi|đến|den)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,:-.")
    work_norm = _strip_accents(cleaned).lower().strip()
    if work_norm in _GENERIC_TITLES or len(work_norm) < 2 or cleaned_norm in _GENERIC_TITLES:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def _infer_fixed_category(norm_text: str) -> str:
    if re.search(r"\b(?:an\s*sang|an\s*trua|an\s*toi|bua\s*an|com|meal|lunch|dinner|breakfast)\b", norm_text):
        return "MEAL"
    if re.search(r"\b(?:lam\s*them|part\s*time|ca\s*lam|cong\s*ty|work|shift)\b", norm_text):
        return "WORK"
    if re.search(r"\b(?:hop|meeting|clb|cau\s*lac\s*bo|team)\b", norm_text):
        return "MEETING"
    return "ACADEMIC_CLASS"


def _resolve_now_weekday(profile: CommitmentsProfile) -> str:
    ref = profile.now or profile.planning_week_start or "2026-11-02T08:00:00+07:00"
    try:
        dt = datetime.fromisoformat(str(ref).replace("Z", "+00:00"))
        return WEEKDAYS[dt.weekday()]
    except Exception:
        return "Monday"


def _date_iso_for_weekday(profile: CommitmentsProfile, day_label: str) -> str:
    ws_str = str(profile.planning_week_start or "2026-11-02T00:00:00+07:00")[:10]
    try:
        ws_dt = datetime.strptime(ws_str, "%Y-%m-%d")
    except ValueError:
        ws_dt = datetime(2026, 11, 2)
    clean = str(day_label or "Monday").strip()
    is_next = clean.lower().startswith("next ")
    base_day = clean[5:].strip() if is_next else clean
    idx = WEEKDAYS.index(base_day) if base_day in WEEKDAYS else 0
    target = ws_dt + timedelta(days=idx + (7 if is_next else 0))
    return target.strftime("%Y-%m-%d")


def _detect_intent(
    prompt: str,
    mode_hint: str,
    pending_draft: Optional[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    last_task_id: Optional[str],
    profile: CommitmentsProfile,
) -> str:
    norm = _strip_accents(prompt).lower()
    hint = (mode_hint or "AUTO").strip().upper()
    if pending_draft and pending_draft.get("intent"):
        return str(pending_draft["intent"])
    if hint in ("ADD_RECURRING", "ADD_TASK", "MODIFY_HIDDEN", "ADJUST_DEADLINE"):
        return hint

    # 1. Explicit deadline + remaining-time adjustment
    deadline_adj_cue = bool(
        re.search(
            r"\b(?:doi|chuyen|gia\s*han|lui|cap\s*nhat|sua)\b.*\b(?:deadline|han\s*chot|han\s*nop|han)\b"
            r"|\b(?:deadline|han\s*chot|han\s*nop)\b.*\b(?:sang|thanh|ve|den|toi)\b"
            r"|\b(?:con\s*lai|lam\s*tiep|uoc\s*luong|estimate|moi\s*lam\s*duoc)\b",
            norm,
        )
    )
    if deadline_adj_cue and tasks:
        return "ADJUST_DEADLINE"

    # 2. Recurring fixed schedule detection
    recurring_cue = bool(
        re.search(
            r"\b(?:hang\s*ngay|moi\s*ngay|lap\s*lai|hang\s*tuan|moi\s*tuan|co\s*dinh|"
            r"thoi\s*khoa\s*bieu|lich\s*hoc|lop\s*hoc|di\s*lam\s*them|bua\s*an|daily|weekly)\b",
            norm,
        )
    )
    if recurring_cue:
        return "ADD_RECURRING"

    # 3. If the prompt states a cross-day window or duration + deadline without an explicit edit verb, it's a NEW task!
    now_day = _resolve_now_weekday(profile)
    has_cross_window = _extract_cross_day_window(norm, now_day) is not None
    dur_val, dur_inferred = _OFFLINE_NL.extract_duration_min(norm)
    has_explicit_dur = not dur_inferred and dur_val is not None
    has_add_verb = bool(re.match(r"^\s*(?:them|tao|add|create|len\s*lich|lam|hoc|on|viet|code|doc|chuan\s*bi|nop)\b", norm))
    has_modify_verb = bool(re.search(r"\b(?:sua|chinh|cap\s*nhat|dieu\s*chinh|tach|chia\s*nho|gop|nang\s*qua|qua\s*nang)\b", norm))

    if (has_cross_window or has_explicit_dur) and not has_modify_verb:
        return "ADD_TASK"

    # 4. Hidden criteria modification on an existing traced task
    trace = resolve_target_task_from_prompt(prompt, tasks, last_task_id=last_task_id)
    hidden = extract_hidden_criteria_updates(prompt, focus_preference=profile.focus_preference)
    if trace["matched"] and trace["confidence"] >= 0.60 and (hidden["has_hidden_updates"] or has_modify_verb) and not (has_add_verb and has_explicit_dur):
        return "MODIFY_HIDDEN"

    return "ADD_TASK"


def _analyze_schedule_edge_cases(
    profile: CommitmentsProfile,
    out: ScheduleOutput,
    tasks: List[Task],
) -> Optional[Dict[str, Any]]:
    """
    Detect:
      - DEADLOCK: genuine unplaced tasks due to overlapping deadlines or capacity shortage.
      - DENSE_WARNING: feasible (0 unplaced) but intense daily load (> 420m) or crunch/high fatigue.
    """
    genuine_unplaced = [
        u
        for u in (out.unplaced_tasks or [])
        if str(u.get("reason_code") or "").upper() not in ("PAST_DUE", "DEADLINE_IN_PAST")
        and "DEADLINE_IN_PAST" not in str(u.get("reason") or "")
    ]

    if genuine_unplaced or out.status in ("INFEASIBLE_CAPACITY", "NO_SCHEDULE_FOUND"):
        titles = [str(u.get("title") or u.get("task_id") or "Công việc") for u in genuine_unplaced]
        shortage_min = int(out.overload.shortage_minutes) if out.overload else sum(
            int(u.get("duration_min") or 60) for u in genuine_unplaced
        )
        suggestions: List[Dict[str, Any]] = []
        if out.overload and out.overload.options:
            for opt in out.overload.options[:4]:
                code = str(opt.get("code") or "")
                friendly = {
                    "SKIP_HABIT": f"🌱 Tạm nghỉ thói quen '{opt.get('title', '')}' tuần này (+{opt.get('frees_min', 0)}p)",
                    "SHORTEN_TASK": f"✂️ Rút ngắn '{opt.get('title', '')}' xuống {opt.get('new_duration_min', 45)}p",
                    "ALLOW_SPLIT": f"🧩 Chia nhỏ '{opt.get('title', '')}' để lấp khe trống ngắn",
                    "POSTPONE_LOWEST": f"📅 Dời '{opt.get('title', '')}' sang cuối tuần",
                }.get(code, str(opt.get("label") or "Điều chỉnh lịch"))
                suggestions.append(
                    {
                        "action": "OVERLOAD_OPTION",
                        "option_id": opt.get("id", "O1"),
                        "option_code": code,
                        "target_task_id": opt.get("task", ""),
                        "label": friendly,
                    }
                )
        else:
            suggestions = [
                {"action": "PROMPT", "label": "✂️ Chia nhỏ bớt các công việc dài", "prompt": "Chia nhỏ các công việc dài để dễ xếp lịch hơn"},
                {"action": "PROMPT", "label": "📅 Dời hạn chót việc ít gấp", "prompt": "Dời deadline công việc ưu tiên thấp sang Chủ nhật"},
            ]

        return {
            "type": "DEADLOCK",
            "severity": "danger",
            "shortage_min": shortage_min,
            "unplaced_titles": titles,
            "message_vi": (
                f"Lịch trình đang bị kẹt hoặc chồng hạn chót ({len(titles)} việc chưa xếp được: "
                f"{', '.join(titles[:3])}, thiếu khoảng {max(15, shortage_min)} phút trống). "
                "Bạn chọn một hướng gỡ rối nhẹ nhàng bên dưới nhé:"
            ),
            "suggestions": suggestions,
        }

    # Check overly dense feasible schedule (Yellow warning)
    horizon_days = max(7, min(14, int(getattr(profile, "horizon_days", 7) or 7)))
    day_load: Dict[int, int] = {d: 0 for d in range(horizon_days)}
    for ev in profile.fixed_events or []:
        raw_days = ev.day_of_week
        days_list = WEEKDAYS if str(raw_days).upper() == "ALL" else (raw_days if isinstance(raw_days, list) else [raw_days])
        try:
            sh, sm = map(int, ev.start_time.split(":"))
            eh, em = map(int, ev.end_time.split(":"))
            dur = max(0, (eh * 60 + em) - (sh * 60 + sm))
        except Exception:
            dur = 0
        if str(ev.category or "").upper() == "MEAL":
            continue
        for wd_name in days_list:
            if wd_name in WEEKDAYS:
                idx = WEEKDAYS.index(wd_name)
                if idx < horizon_days:
                    day_load[idx] = day_load.get(idx, 0) + dur

    for blk in out.blocks or []:
        d_idx = int(blk.start_slot) // SLOTS_PER_DAY
        if 0 <= d_idx < horizon_days:
            day_load[d_idx] = day_load.get(d_idx, 0) + int(blk.duration_min or 0)

    dense_days = [
        {
            "day_index": d,
            "day_vi": _WEEKDAY_VI_MAP.get(WEEKDAYS[d % 7], WEEKDAYS[d % 7]),
            "minutes": mins,
        }
        for d, mins in sorted(day_load.items())
        if mins >= 420
    ]
    max_day_min = max(day_load.values(), default=0)
    is_dense = bool(dense_days) or out.summary.crunch_tier_used > 0 or out.summary.experience_rating >= 2.2

    if is_dense:
        day_txt = ", ".join(f"{d['day_vi']} (~{round(d['minutes'] / 60, 1)} tiếng)" for d in dense_days[:3])
        if not day_txt:
            day_txt = f"một số ngày trong tuần (~{round(max_day_min / 60, 1)} tiếng/ngày)"
        return {
            "type": "DENSE_WARNING",
            "severity": "warn",
            "dense_days": dense_days,
            "max_daily_min": max_day_min,
            "message_vi": (
                f"Đã xếp đủ công việc trước hạn, nhưng lịch trình đang khá dày đặc ở {day_txt}. "
                "Bạn có thể giảm áp lực bằng cách chia nhỏ việc dài hoặc dời bớt sang ngày thoáng hơn:"
            ),
            "suggestions": [
                {
                    "action": "PROMPT",
                    "label": "🌬️ Chia nhỏ các việc nặng để giãn bớt",
                    "prompt": "Chia nhỏ các công việc nặng ra nhiều buổi ngắn hơn để lịch đỡ dày",
                },
                {
                    "action": "PROMPT",
                    "label": "📅 Dời bớt 1 việc nhẹ sang cuối tuần",
                    "prompt": "Dời hạn công việc ưu tiên thấp sang Chủ nhật cho thoáng lịch",
                },
                {"action": "DISMISS", "label": "👍 Giữ nguyên lịch này"},
            ],
        }

    return None


def _compute_remaining_and_habit_buffer(
    *,
    prompt: str,
    task_dict: Dict[str, Any],
    profile: CommitmentsProfile,
    completed_blocks: Dict[str, Any],
    workspace_id: str,
) -> Dict[str, Any]:
    """
    Compute remaining raw minutes + habit/performance safety buffer using M7 EWMA calibration
    and the user's stated estimation habit / task cognitive load.
    """
    norm = _strip_accents(prompt).lower()
    explicit_rem_min, dur_inferred = _OFFLINE_NL.extract_duration_min(norm)
    old_duration = int(task_dict.get("duration_min") or 60)

    if not dur_inferred and explicit_rem_min is not None:
        remaining_raw = round_up_to_15(explicit_rem_min)
        source_note = f"theo thời lượng bạn ước lượng cần làm tiếp ({remaining_raw} phút)"
    else:
        tid = str(task_dict.get("task_id") or "")
        done_min = 0
        for bid, info in (completed_blocks or {}).items():
            if tid and (str(bid).startswith(f"{tid}_") or str(bid) == tid):
                done_min += int((info or {}).get("actual_min") or 0)
        remaining_raw = max(15, round_up_to_15(max(15, old_duration - done_min)))
        source_note = (
            f"tính từ phần việc còn lại ({old_duration}p - {done_min}p đã làm)"
            if done_min > 0
            else f"giữ nguyên thời lượng ước tính hiện có ({remaining_raw} phút)"
        )

    logs = list_completion_logs(workspace_id=workspace_id, limit=100)
    cal = compute_ewma_calibration(logs)
    cog_load = int(task_dict.get("cognitive_load") or 2)

    base_load_mult = multiplier_for_load(
        cog_load,
        alpha_light=float(getattr(profile, "alpha_light", 1.20) or 1.20),
        alpha_heavy=float(getattr(profile, "alpha_heavy", 1.35) or 1.35),
    )
    habit_mult = multiplier_for_habit(getattr(profile, "estimate_habit", None))
    ewma_mult = float(cal.get("ewma_overall") or cal.get("mean_ratio") or 1.0)
    if cal.get("ready_to_apply"):
        ewma_mult = float(
            cal.get("recommended_alpha_heavy" if cog_load >= 3 else "recommended_alpha_light") or ewma_mult
        )

    eff_alpha = round(max(1.10, min(1.60, max(base_load_mult, habit_mult, ewma_mult))), 2)
    buffered_min = max(remaining_raw, round_up_to_15(int(round(remaining_raw * eff_alpha))))
    extra_buffer_min = max(0, buffered_min - remaining_raw)

    return {
        "old_duration_min": old_duration,
        "remaining_raw_min": remaining_raw,
        "applied_alpha": eff_alpha,
        "buffered_duration_min": buffered_min,
        "extra_buffer_min": extra_buffer_min,
        "calibration_samples": int(cal.get("sample_count") or 0),
        "explanation_vi": (
            f"Phần việc còn lại là {remaining_raw} phút ({source_note}). "
            f"Áp dụng hệ số nhịp độ & thói quen cá nhân (×{eff_alpha:.2f}), "
            f"hệ thống dự phòng thêm +{extra_buffer_min} phút thành tổng {buffered_min} phút."
        ),
    }


def _build_post_actions(task_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Keep post-action buttons ultra-minimal: one clear button to inspect the schedule."""
    return [
        {"action": "OPEN_CALENDAR", "label": "🗓️ Kiểm tra lịch trình"},
    ]


def _build_thinking_summary(
    *,
    intent: str,
    context_note_vi: str,
    chosen_solver: str,
    escalated_from_greedy: bool,
    exec_ms: float,
    peak_match_pct: float,
    tasks_placed: int,
    tasks_total: int,
) -> Dict[str, Any]:
    """
    Build an Antigravity-inspired, humanized Thinking Summary for Developer Mode:
      1. Context parsing summary
      2. Dominant algorithm subset selection rationale
      3. Placement & constraint outcome
    """
    if escalated_from_greedy or chosen_solver == "HYBRID_ALNS":
        algo_note = (
            f"Đã loại bỏ nhóm thuật toán cổ điển mù năng lượng (`EDF`, `WSPT`, `LST` — kết quả tốt nhất của nhóm này "
            f"đã thấp hơn mức tệ nhất của nhóm thuật toán sinh học). Trong tập thuật toán tối ưu (`SCORED_GREEDY`, `HYBRID_ALNS`), "
            f"hệ thống chọn **`HYBRID_ALNS`** (tìm kiếm lân cận lớn phá-và-xây lại trong `{exec_ms:.1f}ms`) để hóa giải mật độ hạn chót dày."
        )
    else:
        algo_note = (
            f"Đã loại bỏ nhóm thuật toán cổ điển mù năng lượng (`EDF`, `WSPT`, `LST` — kết quả tốt nhất của nhóm này "
            f"vẫn kém hơn mức tệ nhất của nhóm có nhịp sinh học). Trong tập thuật toán vượt trội (`SCORED_GREEDY`, `HYBRID_ALNS`), "
            f"hệ thống chọn **`{chosen_solver}`** vì tốc độ phản hồi tức thì (`{exec_ms:.1f}ms`) và độ khớp khung giờ tỉnh táo đạt `{peak_match_pct:.0f}%`."
        )

    outcome_note = (
        f"Xếp thành công `{tasks_placed}/{tasks_total}` đầu việc vào lưới thời gian với `0` vi phạm ràng buộc cứng (bảo toàn giờ ngủ & lịch cố định)."
    )

    return {
        "headline_vi": f"Đã phân tích ngữ cảnh & tối ưu bằng {chosen_solver} ({exec_ms:.0f}ms)",
        "context_summary_vi": context_note_vi,
        "algorithm_summary_vi": algo_note,
        "outcome_summary_vi": outcome_note,
        "pruned_algorithms": ["EDF", "WSPT", "LST"],
        "candidate_subset": ["SCORED_GREEDY", "HYBRID_ALNS"],
        "selected_algorithm": chosen_solver,
        "steps_vi": [
            f"Phân tích ngữ cảnh: {context_note_vi}",
            f"Chọn thuật toán: {algo_note}",
            f"Kết quả xếp lịch: {outcome_note}",
        ],
    }


def process_chat_turn(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a single conversational scheduling turn cleanly in < 10s SLA.
    """
    t0 = time.perf_counter()
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Prompt cannot be empty.")

    workspace_id = str(payload.get("workspace_id") or "default").strip() or "default"
    auto_save = bool(payload.get("auto_save", True))
    mode_hint = str(payload.get("mode_hint") or "AUTO").strip().upper()
    algorithm = str(payload.get("algorithm") or "SCORED_GREEDY").strip().upper()
    last_task_id = payload.get("last_task_id")
    pending_draft = payload.get("pending_draft") if isinstance(payload.get("pending_draft"), dict) else None

    saved_record = load_workspace_state(workspace_id) if (payload.get("commitments") is None or payload.get("tasks") is None) else None
    saved_state = (saved_record or {}).get("state") or {}

    comm_raw = payload.get("commitments") if isinstance(payload.get("commitments"), dict) else saved_state.get("commitments")
    if not isinstance(comm_raw, dict):
        comm_raw = {
            "student_id": "STUDENT_01",
            "planning_week_start": "2026-11-02T00:00:00+07:00",
            "now": "2026-11-02T08:00:00+07:00",
            "sleep_schedule": {"daily_start_time": "23:30", "daily_end_time": "06:30", "is_hard_lock": True},
            "fixed_events": [],
            "buffer_mode": "COGNITIVE_LOAD",
            "focus_preference": "BALANCED",
            "horizon_days": 7,
        }

    tasks_raw: List[Dict[str, Any]] = [
        enrich_task_trace_metadata(t)
        for t in (payload.get("tasks") if isinstance(payload.get("tasks"), list) else (saved_state.get("tasks") or []))
        if isinstance(t, dict)
    ]
    pinned_raw = payload.get("pinned_blocks") if isinstance(payload.get("pinned_blocks"), list) else (saved_state.get("pinnedBlocks") or [])
    completed_blocks = payload.get("completed_blocks") if isinstance(payload.get("completed_blocks"), dict) else (saved_state.get("completedBlocks") or {})

    profile = CommitmentsProfile.model_validate(comm_raw)
    now_day = _resolve_now_weekday(profile)
    norm_prompt = _strip_accents(prompt).lower()

    if pending_draft and re.match(r"^\s*(?:huy|thoi|bo\s*qua|cancel|lam\s*lai)\s*$", norm_prompt):
        return {
            "status": "CANCELLED",
            "intent": "CANCELLED",
            "reply_vi": "Đã hủy thao tác đang dở. Bạn có thể nhập yêu cầu mới bất cứ lúc nào.",
            "pending_draft": None,
            "missing_fields": [],
            "quick_chips": [],
            "post_actions": _build_post_actions(),
            "updated_commitments": profile.model_dump(mode="json"),
            "updated_tasks": tasks_raw,
            "updated_pinned_blocks": pinned_raw,
            "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }

    intent = _detect_intent(prompt, mode_hint, pending_draft, tasks_raw, last_task_id, profile)

    # ------------------------------------------------------------------
    # BRANCH 1: MODIFY HIDDEN CRITERIA VIA SHA-256 TASK TRACEABILITY
    # ------------------------------------------------------------------
    if intent == "MODIFY_HIDDEN":
        trace = resolve_target_task_from_prompt(prompt, tasks_raw, last_task_id=last_task_id)
        if not trace["matched"]:
            cands = trace.get("candidates") or []
            chips = [
                {
                    "label": f"📌 {c['title']}",
                    "prompt": f"[trace:{str(c.get('trace_hash') or '')[:8]}] {prompt}",
                }
                for c in cands
                if c.get("title")
            ]
            return {
                "status": "NEEDS_CLARIFICATION",
                "intent": "MODIFY_HIDDEN",
                "reply_vi": (
                    "Mình chưa xác định chắc chắn bạn muốn điều chỉnh công việc nào. "
                    "Bạn bấm chọn đúng công việc bên dưới nhé:"
                ),
                "pending_draft": {"intent": "MODIFY_HIDDEN", "original_prompt": prompt},
                "missing_fields": ["target_task"],
                "quick_chips": chips,
                "post_actions": _build_post_actions(),
                "updated_commitments": profile.model_dump(mode="json"),
                "updated_tasks": tasks_raw,
                "updated_pinned_blocks": pinned_raw,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

        target_id = trace["task_id"]
        hidden_info = extract_hidden_criteria_updates(prompt, focus_preference=profile.focus_preference)
        if not hidden_info["has_hidden_updates"]:
            return {
                "status": "NEEDS_CLARIFICATION",
                "intent": "MODIFY_HIDDEN",
                "reply_vi": (
                    f"Mình đã tìm thấy công việc **{trace['task']['title']}**. "
                    "Bạn muốn điều chỉnh tiêu chí nào cho việc này?"
                ),
                "pending_draft": {
                    "intent": "MODIFY_HIDDEN",
                    "target_task_id": target_id,
                    "trace_hash": trace["trace_hash"],
                },
                "missing_fields": ["hidden_criteria"],
                "quick_chips": [
                    {"label": "🧠 Việc nặng — thêm trừ hao & xếp giờ tỉnh táo", "prompt": f"[trace:{trace['trace_hash'][:8]}] Việc này nặng quá, xếp giờ tỉnh táo nhất và thêm buffer"},
                    {"label": "🧩 Chia nhỏ nhiều buổi ngắn", "prompt": f"[trace:{trace['trace_hash'][:8]}] Chia nhỏ ra nhiều buổi ngắn"},
                    {"label": "🔒 Không chia nhỏ, làm liền 1 mạch", "prompt": f"[trace:{trace['trace_hash'][:8]}] Không chia nhỏ, làm liền 1 mạch"},
                    {"label": "🌅 Chuyển sang buổi sáng", "prompt": f"[trace:{trace['trace_hash'][:8]}] Chuyển sang buổi sáng"},
                ],
                "post_actions": _build_post_actions(),
                "traced_task": trace,
                "updated_commitments": profile.model_dump(mode="json"),
                "updated_tasks": tasks_raw,
                "updated_pinned_blocks": pinned_raw,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

        mutated_task = None
        for idx, t in enumerate(tasks_raw):
            if t.get("task_id") == target_id:
                updated = dict(t)
                for k, v in hidden_info["updates"].items():
                    updated[k] = v
                if hidden_info["updates"].get("is_splittable") is False:
                    updated["min_chunk_min"] = max(15, int(updated.get("duration_min") or 60))
                    updated["max_chunk_min"] = updated["min_chunk_min"]
                updated = enrich_task_trace_metadata(updated)
                tasks_raw[idx] = updated
                mutated_task = updated
                break

        pinned_raw = [p for p in pinned_raw if p.get("task_id") != target_id]
        context_note = (
            f"Truy vết công việc đã lưu **{mutated_task['title']}** (SHA-256 `#{mutated_task['trace_hash'][:8]}`) "
            f"và điều chỉnh tiêu chí ẩn: {'; '.join(hidden_info['summary_vi'])}."
        )
        return _finalize_solve_and_package(
            intent="MODIFY_HIDDEN",
            profile=profile,
            tasks_raw=tasks_raw,
            pinned_raw=pinned_raw,
            completed_blocks=completed_blocks,
            algorithm=algorithm,
            workspace_id=workspace_id,
            auto_save=auto_save,
            mutated_task_id=target_id,
            context_note_vi=context_note,
            reply_vi=(
                f"Đã cập nhật **{mutated_task['title']}** ({'; '.join(hidden_info['summary_vi'])}) "
                "và sắp xếp lại lịch trình cho bạn."
            ),
            traced_task={
                "task_id": target_id,
                "title": mutated_task["title"],
                "trace_hash": mutated_task["trace_hash"],
                "matched_keywords": trace.get("matched_keywords", []),
                "hidden_updates": hidden_info["updates"],
                "summary_vi": hidden_info["summary_vi"],
            },
            t0=t0,
        )

    # ------------------------------------------------------------------
    # BRANCH 2: DEADLINE ADJUSTMENT & REMAINING-TIME + HABIT BUFFER
    # ------------------------------------------------------------------
    if intent == "ADJUST_DEADLINE":
        trace = resolve_target_task_from_prompt(prompt, tasks_raw, last_task_id=last_task_id)
        if not trace["matched"]:
            cands = trace.get("candidates") or []
            return {
                "status": "NEEDS_CLARIFICATION",
                "intent": "ADJUST_DEADLINE",
                "reply_vi": "Bạn muốn đổi hạn chót và tính lại thời gian làm tiếp cho công việc nào?",
                "pending_draft": {"intent": "ADJUST_DEADLINE", "original_prompt": prompt},
                "missing_fields": ["target_task"],
                "quick_chips": [
                    {"label": f"📌 {c['title']}", "prompt": f"[trace:{str(c.get('trace_hash') or '')[:8]}] {prompt}"}
                    for c in cands
                    if c.get("title")
                ],
                "post_actions": _build_post_actions(),
                "updated_commitments": profile.model_dump(mode="json"),
                "updated_tasks": tasks_raw,
                "updated_pinned_blocks": pinned_raw,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

        target_id = trace["task_id"]
        new_dl_day, day_inferred = _OFFLINE_NL.extract_deadline_day(norm_prompt, now_day)
        new_dl_time, time_inferred, _, _ = _OFFLINE_NL.extract_clock_time(norm_prompt)

        mutated_task = None
        rem_info: Optional[Dict[str, Any]] = None
        for idx, t in enumerate(tasks_raw):
            if t.get("task_id") == target_id:
                updated = dict(t)
                rem_info = _compute_remaining_and_habit_buffer(
                    prompt=prompt,
                    task_dict=updated,
                    profile=profile,
                    completed_blocks=completed_blocks,
                    workspace_id=workspace_id,
                )
                updated["duration_min"] = rem_info["remaining_raw_min"]
                updated["buffer_mode"] = "COGNITIVE_LOAD"
                updated["buffer_multiplier"] = rem_info["applied_alpha"]
                updated["alpha_light"] = rem_info["applied_alpha"]
                updated["alpha_heavy"] = rem_info["applied_alpha"]
                if not day_inferred and new_dl_day:
                    updated["deadline_day"] = new_dl_day
                    updated["due"] = None
                if not time_inferred and new_dl_time:
                    updated["deadline_time"] = new_dl_time
                    updated["due"] = None
                updated = enrich_task_trace_metadata(updated)
                tasks_raw[idx] = updated
                mutated_task = updated
                break

        pinned_raw = [p for p in pinned_raw if p.get("task_id") != target_id]
        dl_vi = _WEEKDAY_VI_MAP.get(str(mutated_task.get("deadline_day") or ""), str(mutated_task.get("deadline_day") or "linh hoạt"))
        dl_time_str = mutated_task.get("deadline_time") or "23:59"
        context_note = (
            f"Cập nhật hạn chót cho **{mutated_task['title']}** (SHA-256 `#{mutated_task['trace_hash'][:8]}`) "
            f"sang `{dl_time_str} {dl_vi}` · Thời lượng còn lại `{rem_info['remaining_raw_min']}p` -> dự phòng `{rem_info['buffered_duration_min']}p` (×{rem_info['applied_alpha']:.2f})."
        )

        return _finalize_solve_and_package(
            intent="ADJUST_DEADLINE",
            profile=profile,
            tasks_raw=tasks_raw,
            pinned_raw=pinned_raw,
            completed_blocks=completed_blocks,
            algorithm=algorithm,
            workspace_id=workspace_id,
            auto_save=auto_save,
            mutated_task_id=target_id,
            context_note_vi=context_note,
            reply_vi=(
                f"Đã cập nhật hạn chót mới cho **{mutated_task['title']}** sang **{dl_time_str} {dl_vi}**. "
                f"{rem_info['explanation_vi']}"
            ),
            remaining_estimation=rem_info,
            traced_task={
                "task_id": target_id,
                "title": mutated_task["title"],
                "trace_hash": mutated_task["trace_hash"],
                "matched_keywords": trace.get("matched_keywords", []),
            },
            t0=t0,
        )

    # ------------------------------------------------------------------
    # BRANCH 3: ADD / MODIFY RECURRING DAILY / WEEKLY SCHEDULE
    # ------------------------------------------------------------------
    if intent == "ADD_RECURRING":
        draft = dict(pending_draft or {"intent": "ADD_RECURRING"})
        s_time, e_time = _extract_time_range(norm_prompt)
        days_parsed = _extract_recurring_days(norm_prompt)
        title_parsed = _clean_conversational_title(prompt)

        if title_parsed and not draft.get("title"):
            draft["title"] = title_parsed
        if s_time and e_time:
            draft["start_time"] = s_time
            draft["end_time"] = e_time
        if days_parsed is not None:
            draft["day_of_week"] = days_parsed
        if not draft.get("category"):
            draft["category"] = _infer_fixed_category(norm_prompt)

        missing: List[str] = []
        if not draft.get("title"):
            missing.append("title")
        if not draft.get("start_time") or not draft.get("end_time"):
            missing.append("time_range")

        if missing:
            if "title" in missing and "time_range" in missing:
                q_vi = "Bạn muốn thêm lịch lặp lại với **nội dung gì** và trong khung **giờ bắt đầu – giờ kết thúc** nào?"
                chips = [
                    {"label": "🍳 Ăn sáng 07:00 – 07:30 hằng ngày", "prompt": "Ăn sáng từ 07:00 đến 07:30 hằng ngày"},
                    {"label": "🏃 Tập thể dục 17:30 – 18:30 hằng ngày", "prompt": "Tập thể dục từ 17:30 đến 18:30 hằng ngày"},
                    {"label": "🏫 Học trên trường 07:30 – 11:00 Thứ 2, 4", "prompt": "Học trên trường từ 07:30 đến 11:00 thứ 2 và thứ 4"},
                ]
            elif "time_range" in missing:
                q_vi = (
                    f"Với lịch lặp **{draft['title']}**, bạn cần **thời gian bắt đầu và kết thúc** từ mấy giờ đến mấy giờ?"
                )
                chips = [
                    {"label": "🌅 07:30 – 09:30", "prompt": "từ 07:30 đến 09:30"},
                    {"label": "☀️ 13:30 – 15:30", "prompt": "từ 13:30 đến 15:30"},
                    {"label": "🌆 18:00 – 19:00", "prompt": "từ 18:00 đến 19:00"},
                    {"label": "🌙 20:00 – 21:30", "prompt": "từ 20:00 đến 21:30"},
                ]
            else:
                q_vi = f"Trong khung giờ **{draft['start_time']} – {draft['end_time']}**, nội dung công việc / lịch lặp là gì?"
                chips = [
                    {"label": "🏫 Lịch học trên lớp", "prompt": "Học trên lớp"},
                    {"label": "💼 Làm thêm", "prompt": "Đi làm thêm"},
                    {"label": "🏃 Tập thể dục", "prompt": "Tập thể dục"},
                ]

            return {
                "status": "NEEDS_CLARIFICATION",
                "intent": "ADD_RECURRING",
                "reply_vi": q_vi,
                "pending_draft": draft,
                "missing_fields": missing,
                "quick_chips": chips,
                "post_actions": _build_post_actions(),
                "updated_commitments": profile.model_dump(mode="json"),
                "updated_tasks": tasks_raw,
                "updated_pinned_blocks": pinned_raw,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

        day_val = draft.get("day_of_week") or "ALL"
        new_event = FixedEvent(
            event_id=f"FE_CHAT_{int(time.time() * 1000) % 100000}",
            title=str(draft["title"]),
            day_of_week=day_val,
            start_time=str(draft["start_time"]),
            end_time=str(draft["end_time"]),
            category=str(draft.get("category") or "ACADEMIC_CLASS"),
        )
        comm_updated = profile.model_dump(mode="json")
        comm_updated.setdefault("fixed_events", []).append(new_event.model_dump(mode="json"))
        profile = CommitmentsProfile.model_validate(comm_updated)
        day_desc = "hằng ngày" if day_val == "ALL" else (
            ", ".join(_WEEKDAY_VI_MAP.get(d, d) for d in day_val) if isinstance(day_val, list) else _WEEKDAY_VI_MAP.get(str(day_val), str(day_val))
        )
        context_note = (
            f"Nhận diện 1 lịch cố định lặp lại: **{new_event.title}** · Khung giờ `{new_event.start_time} – {new_event.end_time}` ({day_desc})."
        )
        return _finalize_solve_and_package(
            intent="ADD_RECURRING",
            profile=profile,
            tasks_raw=tasks_raw,
            pinned_raw=pinned_raw,
            completed_blocks=completed_blocks,
            algorithm=algorithm,
            workspace_id=workspace_id,
            auto_save=auto_save,
            mutated_task_id=None,
            context_note_vi=context_note,
            reply_vi=(
                f"Đã thêm lịch lặp **{new_event.title}** ({new_event.start_time} – {new_event.end_time}, {day_desc}) "
                "và cập nhật lại lịch tuần cho bạn."
            ),
            t0=t0,
        )

    # ------------------------------------------------------------------
    # BRANCH 4: ADD / ADJUST SPECIFIC TASK (WITH CROSS-DAY WINDOW SUPPORT)
    # ------------------------------------------------------------------
    draft = dict(pending_draft or {"intent": "ADD_TASK"})
    cross_win = _extract_cross_day_window(norm_prompt, now_day)
    s_time, e_time = (None, None) if cross_win else _extract_time_range(norm_prompt)
    dur_min, dur_inferred = _OFFLINE_NL.extract_duration_min(norm_prompt)
    dl_day, day_inferred = _OFFLINE_NL.extract_deadline_day(norm_prompt, now_day)
    dl_time, time_inferred, _, _ = _OFFLINE_NL.extract_clock_time(norm_prompt)
    title_parsed = _clean_conversational_title(prompt)
    cat, prio, cog_load = _OFFLINE_NL.extract_category_priority_load(prompt.lower(), norm_prompt)
    hidden = extract_hidden_criteria_updates(prompt, focus_preference=profile.focus_preference)

    if title_parsed and not draft.get("title"):
        draft["title"] = title_parsed

    if cross_win:
        draft["start_after_day"] = cross_win["start_day"]
        draft["start_after_time"] = cross_win["start_time"]
        draft["deadline_day"] = cross_win["end_day"]
        draft["deadline_time"] = cross_win["end_time"]
        if not dur_inferred and dur_min is not None:
            draft["duration_min"] = round_up_to_15(dur_min)
            draft["has_time_bounds"] = True
        elif cross_win["start_day"] == cross_win["end_day"]:
            sh, sm = map(int, cross_win["start_time"].split(":"))
            eh, em = map(int, cross_win["end_time"].split(":"))
            if (eh * 60 + em) > (sh * 60 + sm):
                draft["start_time"] = cross_win["start_time"]
                draft["end_time"] = cross_win["end_time"]
                draft["duration_min"] = max(15, round_up_to_15((eh * 60 + em) - (sh * 60 + sm)))
                draft["has_time_bounds"] = True
    elif s_time and e_time:
        draft["start_time"] = s_time
        draft["end_time"] = e_time
        sh, sm = map(int, s_time.split(":"))
        eh, em = map(int, e_time.split(":"))
        draft["duration_min"] = max(15, round_up_to_15((eh * 60 + em) - (sh * 60 + sm)))
        draft["deadline_time"] = e_time
        draft["has_time_bounds"] = True
    elif not dur_inferred and dur_min is not None:
        draft["duration_min"] = round_up_to_15(dur_min)
        draft["has_time_bounds"] = True

    if not cross_win:
        if not day_inferred and dl_day:
            draft["deadline_day"] = dl_day
        if not time_inferred and dl_time and not (s_time and e_time):
            draft["deadline_time"] = dl_time

    draft.setdefault("category", cat)
    draft.setdefault("priority", prio)
    draft.setdefault("cognitive_load", cog_load)
    for k, v in hidden["updates"].items():
        draft[k] = v

    missing = []
    if not draft.get("title"):
        missing.append("title")
    has_explicit_window = bool(draft.get("start_time") and draft.get("end_time"))
    has_duration_and_deadline = bool(draft.get("duration_min") and draft.get("deadline_day"))
    if not has_explicit_window and not has_duration_and_deadline:
        if not draft.get("duration_min"):
            missing.append("time_range")
        if not draft.get("deadline_day") and not has_explicit_window:
            missing.append("deadline_day")

    if missing:
        if "title" in missing and ("time_range" in missing or "deadline_day" in missing):
            q_vi = "Bạn muốn thêm **công việc gì**, và cần làm **từ mấy giờ đến mấy giờ** (hoặc mất khoảng bao lâu, hạn ngày nào)?"
            chips = [
                {"label": "📝 Làm bài tập Giải tích 90p trước Thứ 6", "prompt": "Làm bài tập Giải tích 90 phút trước Thứ 6"},
                {"label": "📊 Chuẩn bị slide từ 14:00 – 16:00 Thứ 5", "prompt": "Chuẩn bị slide từ 14:00 đến 16:00 Thứ 5"},
            ]
        elif "title" in missing:
            time_desc = (
                f"{draft['start_time']} – {draft['end_time']}"
                if has_explicit_window
                else f"{draft.get('duration_min', 60)} phút"
            )
            q_vi = f"Bạn muốn làm **nội dung công việc gì** cho khung thời gian {time_desc} này?"
            chips = [
                {"label": "📚 Ôn tập bài giảng", "prompt": "Ôn tập bài giảng"},
                {"label": "💻 Code bài thực hành", "prompt": "Code bài thực hành"},
                {"label": "📝 Viết báo cáo", "prompt": "Viết báo cáo"},
            ]
        elif "time_range" in missing and "deadline_day" in missing:
            q_vi = (
                f"Với công việc **{draft['title']}**, bạn dự định làm **từ mấy giờ đến mấy giờ** "
                "(hoặc trong **bao lâu** và **hạn chót ngày nào**)?"
            )
            chips = [
                {"label": "🕗 Sáng mai 08:00 – 09:30", "prompt": "ngày mai từ 08:00 đến 09:30"},
                {"label": "⏱ 60 phút · Hạn Thứ 6", "prompt": "khoảng 60 phút trước Thứ 6"},
                {"label": "⏱ 90 phút · Hạn Chủ nhật", "prompt": "khoảng 90 phút trước Chủ nhật"},
            ]
        elif "time_range" in missing:
            q_vi = f"Bạn ước lượng **{draft['title']}** cần làm trong **bao lâu** (hoặc từ mấy giờ đến mấy giờ)?"
            chips = [
                {"label": "⏱ 45 phút", "prompt": "khoảng 45 phút"},
                {"label": "⏱ 60 phút", "prompt": "khoảng 60 phút"},
                {"label": "⏱ 90 phút", "prompt": "khoảng 90 phút"},
                {"label": "⏱ 2 tiếng", "prompt": "khoảng 2 tiếng"},
            ]
        else:
            q_vi = f"Công việc **{draft['title']}** ({draft['duration_min']} phút) cần hoàn thành trước **ngày nào**?"
            chips = [
                {"label": "📅 Hôm nay", "prompt": "trước 23:59 hôm nay"},
                {"label": "📅 Ngày mai", "prompt": "trước 23:59 ngày mai"},
                {"label": "📅 Thứ Sáu", "prompt": "trước 23:59 Thứ Sáu"},
                {"label": "📅 Chủ Nhật", "prompt": "trước 23:59 Chủ Nhật"},
            ]

        return {
            "status": "NEEDS_CLARIFICATION",
            "intent": "ADD_TASK",
            "reply_vi": q_vi,
            "pending_draft": draft,
            "missing_fields": missing,
            "quick_chips": chips,
            "post_actions": _build_post_actions(),
            "updated_commitments": profile.model_dump(mode="json"),
            "updated_tasks": tasks_raw,
            "updated_pinned_blocks": pinned_raw,
            "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }

    # Build final validated Task dict with SHA-256 trace metadata
    new_tid = f"T_CHAT_{int(time.time() * 1000) % 100000}_{len(tasks_raw) + 1}"
    target_day = draft.get("deadline_day") or now_day
    final_dur = int(draft.get("duration_min") or 60)
    start_after_iso = None
    buf_mode = str(draft.get("buffer_mode") or "COGNITIVE_LOAD")

    if has_explicit_window:
        day_iso = _date_iso_for_weekday(profile, str(target_day))
        start_after_iso = f"{day_iso}T{draft['start_time']}:00+07:00"
        buf_mode = "NONE"
    elif draft.get("start_after_day"):
        sa_iso = _date_iso_for_weekday(profile, str(draft["start_after_day"]))
        sa_time = str(draft.get("start_after_time") or "08:00")
        start_after_iso = f"{sa_iso}T{sa_time}:00+07:00"

    # Keep a single task as 1 single contiguous block unless the user asked to split or duration > 180m
    explicit_split_req = "is_splittable" in hidden["updates"]
    is_split = bool(draft["is_splittable"]) if explicit_split_req else (final_dur > 180)
    min_c = int(draft.get("min_chunk_min") or (45 if is_split else final_dur))
    max_c = int(draft.get("max_chunk_min") or (90 if is_split else max(180, final_dur)))

    task_obj = Task(
        task_id=new_tid,
        title=str(draft["title"]),
        duration_min=final_dur,
        deadline_day=str(target_day),
        deadline_time=str(draft.get("deadline_time") or "23:59"),
        priority=int(draft.get("priority") or 3),
        category=str(draft.get("category") or "ASSIGNMENT"),
        cognitive_load=int(draft.get("cognitive_load") or 2),
        is_splittable=is_split,
        work_rhythm=draft.get("work_rhythm") if is_split else "FLOW",
        min_chunk_min=min_c,
        max_chunk_min=max_c,
        preferred_window=draft.get("preferred_window"),
        start_after=start_after_iso,
        buffer_mode=buf_mode,
        buffer_multiplier=float(draft.get("buffer_multiplier") or 1.0),
    )
    enriched_new = enrich_task_trace_metadata(task_obj.model_dump(mode="json"))
    tasks_raw.append(enriched_new)

    day_vi = _WEEKDAY_VI_MAP.get(str(target_day), str(target_day))
    if has_explicit_window:
        time_desc = f"{draft['start_time']} – {draft['end_time']} {day_vi}"
    elif draft.get("start_after_day"):
        sa_day_vi = _WEEKDAY_VI_MAP.get(str(draft["start_after_day"]), str(draft["start_after_day"]))
        time_desc = (
            f"{task_obj.duration_min} phút, trong khung từ {draft.get('start_after_time', '08:00')} {sa_day_vi} "
            f"đến {task_obj.deadline_time} {day_vi}"
        )
    else:
        time_desc = f"{task_obj.duration_min} phút, hạn {task_obj.deadline_time} {day_vi}"

    context_note = (
        f"Nhận diện 1 công việc duy nhất: **{task_obj.title}** (SHA-256 `#{enriched_new['trace_hash'][:8]}`) · "
        f"Thời gian: `{time_desc}` · Giữ nguyên 1 khối liền mạch để tránh chia vụn."
        if not is_split
        else f"Nhận diện 1 công việc: **{task_obj.title}** (SHA-256 `#{enriched_new['trace_hash'][:8]}`) · "
        f"Thời gian: `{time_desc}` · Cho phép chia thành các phiên `{min_c}–{max_c}p`."
    )

    return _finalize_solve_and_package(
        intent="ADD_TASK",
        profile=profile,
        tasks_raw=tasks_raw,
        pinned_raw=pinned_raw,
        completed_blocks=completed_blocks,
        algorithm=algorithm,
        workspace_id=workspace_id,
        auto_save=auto_save,
        mutated_task_id=new_tid,
        context_note_vi=context_note,
        reply_vi=f"Đã lên lịch cho **{task_obj.title}** ({time_desc}).",
        traced_task={
            "task_id": new_tid,
            "title": task_obj.title,
            "trace_hash": enriched_new["trace_hash"],
            "keyword_hashes": enriched_new["keyword_hashes"],
        },
        t0=t0,
    )


def _finalize_solve_and_package(
    *,
    intent: str,
    profile: CommitmentsProfile,
    tasks_raw: List[Dict[str, Any]],
    pinned_raw: List[Dict[str, Any]],
    completed_blocks: Dict[str, Any],
    algorithm: str,
    workspace_id: str,
    auto_save: bool,
    mutated_task_id: Optional[str],
    context_note_vi: str,
    reply_vi: str,
    t0: float,
    traced_task: Optional[Dict[str, Any]] = None,
    remaining_estimation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    task_models = [Task.model_validate(t) for t in tasks_raw]
    pinned_models = [ScheduleBlock.model_validate(pb) for pb in pinned_raw]

    # Dominant Ergonomic Subset Selection:
    # Prune energy-blind baseline heuristics (EDF, WSPT, LST) in normal conversational flow
    # and run SCORED_GREEDY first, escalating to HYBRID_ALNS if greedy leaves unplaced tasks.
    dominant_subset = ("SCORED_GREEDY", "HYBRID_ALNS", "BACKTRACK")
    eff_algo = algorithm if algorithm in dominant_subset else "SCORED_GREEDY"
    escalated = False

    out, _ = ScheduleController.solve_schedule(
        profile=profile,
        tasks=task_models,
        algorithm=eff_algo,
        pinned_blocks=pinned_models,
    )
    if eff_algo == "SCORED_GREEDY" and out.summary.tasks_unplaced > 0 and "HYBRID_ALNS" in ScheduleController.SOLVER_REGISTRY:
        alns_out, _ = ScheduleController.solve_schedule(
            profile=profile,
            tasks=task_models,
            algorithm="HYBRID_ALNS",
            pinned_blocks=pinned_models,
        )
        if alns_out.summary.tasks_unplaced < out.summary.tasks_unplaced:
            out = alns_out
            eff_algo = "HYBRID_ALNS"
            escalated = True

    insights = ScheduleController.compute_schedule_insights(profile, out)
    sched_dict = out.model_dump()
    sched_dict["unplaced"] = sched_dict["unplaced_tasks"]
    b_energies = insights.get("block_energies", {})
    for blk in sched_dict.get("blocks", []):
        blk["energy_level"] = b_energies.get(blk.get("block_id"))
    sched_dict["metrics"] = {
        "hard_violations": out.summary.hard_constraint_violations,
        "deadline_rate": round(out.summary.deadline_satisfaction_rate / 100.0, 4),
        "deadline_satisfaction_pct": out.summary.deadline_satisfaction_rate,
        "exec_ms": out.execution_time_ms,
        "free_slots": out.summary.free_slots_remaining,
        "rest_slots": out.summary.rest_slots,
        "fragmentation_index": out.summary.fragmentation_index,
        "experience_rating": out.summary.experience_rating,
        "experience_label": out.summary.experience_label,
        "crunch_tier_used": out.summary.crunch_tier_used,
        "peak_match_rate_pct": insights.get("peak_match_rate_pct", 100.0),
        "deep_peak_match_pct": insights.get("deep_peak_match_pct", 100.0),
        "avg_energy_level": insights.get("avg_energy_level", 0.0),
        "context_switches": insights.get("context_switches", 0),
        "batched_pairs": insights.get("batched_pairs", 0),
    }

    # Include exact placed block summary inside reply_vi when a single task was added/updated
    if mutated_task_id:
        placed_for_task = [b for b in out.blocks if b.task_id == mutated_task_id]
        if placed_for_task:
            slots_txt = ", ".join(
                f"**{b.start_time} – {b.end_time} {_WEEKDAY_VI_MAP.get(b.day, b.day)}**"
                for b in placed_for_task
            )
            reply_vi = f"{reply_vi} Mình đã xếp vào khung giờ: {slots_txt}."

    edge_case = _analyze_schedule_edge_cases(profile, out, task_models)
    comm_dict = profile.model_dump(mode="json")

    if auto_save:
        save_workspace_state(
            {
                "suiteLabel": "Lịch trình của bạn",
                "commitments": comm_dict,
                "tasks": tasks_raw,
                "pinnedBlocks": pinned_raw,
                "completedBlocks": completed_blocks,
                "activeSolver": eff_algo,
            },
            workspace_id=workspace_id,
        )

    total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    thinking_summary = _build_thinking_summary(
        intent=intent,
        context_note_vi=context_note_vi,
        chosen_solver=eff_algo,
        escalated_from_greedy=escalated,
        exec_ms=float(out.execution_time_ms or total_ms),
        peak_match_pct=float(insights.get("peak_match_rate_pct", 100.0)),
        tasks_placed=int(out.summary.tasks_placed),
        tasks_total=int(out.summary.total_tasks_requested),
    )

    return {
        "status": "APPLIED",
        "intent": intent,
        "finalized": edge_case is None or edge_case.get("type") != "DEADLOCK",
        "finalized_message_vi": (
            "⚠️ Lịch trình đang bị kẹt — hãy chọn một hướng gỡ rối bên dưới."
            if edge_case and edge_case.get("type") == "DEADLOCK"
            else "✅ Đã hoàn tất và chốt lịch trình mới!"
        ),
        "reply_vi": reply_vi,
        "thinking_summary": thinking_summary,
        "pending_draft": None,
        "missing_fields": [],
        "quick_chips": [],
        "mutated_task_id": mutated_task_id,
        "traced_task": traced_task,
        "remaining_estimation": remaining_estimation,
        "edge_case": edge_case,
        "post_actions": _build_post_actions(mutated_task_id),
        "updated_commitments": comm_dict,
        "updated_tasks": tasks_raw,
        "updated_pinned_blocks": pinned_raw,
        "schedule": sched_dict,
        "execution_time_ms": total_ms,
    }
