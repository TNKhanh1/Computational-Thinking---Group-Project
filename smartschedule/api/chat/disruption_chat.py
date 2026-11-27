"""
Conversational Mid-Week Emergency Disruption Handler (`smartschedule.api.chat.disruption_chat` — Pattern P8).

Routes unexpected one-off events (e.g., urgent club meetings, power outages, sudden appointments)
through `LocalRepairEngine.repair_disruption(..., mode="LOCAL_INSERTION")` to preserve >= 90%
schedule stability, performs post-repair circadian trough ergonomics checks (Fix M-8), and logs
disruption windows into workspace state for cross-week chronic zone detection (Fix M-5).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from smartschedule.api.chat.thinking_stage import build_post_actions, build_thinking_summary
from smartschedule.core.controller import ScheduleController
from smartschedule.core.models import (
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    ScheduleBlock,
    ScheduleOutput,
    Task,
)
from smartschedule.core.solvers.local_repair import LocalRepairEngine
from smartschedule.core.storage import load_workspace_state, save_workspace_state
from smartschedule.nlp.clause_condenser import (
    _WEEKDAY_VI_MAP,
    _extract_flexible_duration_min,
    _extract_time_range,
    _parse_clock_token,
    _resolve_day_token,
    _resolve_now_weekday,
)
from smartschedule.nlp.parser_controller import WEEKDAYS, _strip_accents

_RECURRING_EXCLUSION_RE = re.compile(
    r"\b(?:hang\s*ngay|moi\s*ngay|hang\s*tuan|moi\s*tuan|moi\s*thu|moi\s*sang|moi\s*chieu|moi\s*toi|"
    r"lap\s*lai|thoi\s*khoa\s*bieu|co\s*dinh|daily|weekly|every\s*week|every\s*day)\b"
)

_LIFECYCLE_EXCLUSION_RE = re.compile(
    r"^\s*(?:xoa|huy\s+bai|huy\s+cong\s*viec|lam\s*xong|da\s*xong|hoan\s*thanh|doi\s*deadline|gia\s*han)\b"
)

_STRONG_DISRUPTION_RE = re.compile(
    r"\b(?:dot\s*xuat|khan\s*cap|phat\s*sinh|bat\s*ngo|cup\s*dien|mat\s*dien|ket\s*lich|"
    r"ket\s*xe|hong\s*xe|di\s*kham|nhap\s*vien|om\s*dot\s*xuat|sot\s*dot\s*xuat|"
    r"urgent|emergency|unexpected|sudden)\b"
)

_BUSY_INSERTION_RE = re.compile(
    r"\b(?:ban\s+hop|ban\s+viec|ban\s+dot\s*xuat|co\s+lich\s+hop|hop\s+clb|hop\s+nhom\s+gap|"
    r"hop\s+khan|viec\s+rieng\s+gap|viec\s+gia\s*dinh|ket\s+viec)\b"
)

_STUDY_TASK_CUE_RE = re.compile(
    r"\b(?:deadline|han\s*chot|han\s*nop|nop\s*bai|lam\s*bai\s*tap|on\s*thi|viet\s*bao\s*cao)\b"
)

_CANCEL_DRAFT_RE = re.compile(
    r"^\s*(?:huy|huy\s*bo|huy\s*thao\s*tac|thoi|khong\s*can\s*nua|cancel|stop)\s*$"
)


def is_disruption_intent(
    prompt: str,
    mode_hint: str = "AUTO",
    pending_draft: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Return True iff the user turn describes a one-off mid-week disruption / emergency event
    (or continues an active `DISRUPTION_REPAIR` clarification draft), excluding weekly recurring classes.
    """
    if isinstance(pending_draft, dict) and str(pending_draft.get("intent") or "").upper() == "DISRUPTION_REPAIR":
        return True

    hint = str(mode_hint or "AUTO").strip().upper()
    if hint in ("DISRUPTION", "DISRUPTION_REPAIR"):
        return True
    if hint not in ("AUTO", ""):
        return False

    norm = _strip_accents(prompt or "").lower().strip()
    if not norm:
        return False
    if _LIFECYCLE_EXCLUSION_RE.search(norm):
        return False

    has_strong_emergency = bool(_STRONG_DISRUPTION_RE.search(norm))
    if _RECURRING_EXCLUSION_RE.search(norm) and not has_strong_emergency:
        return False
    if _STUDY_TASK_CUE_RE.search(norm) and not has_strong_emergency:
        return False

    if has_strong_emergency:
        return True
    if _BUSY_INSERTION_RE.search(norm):
        return True
    return False


def is_disruption_prompt(prompt: str) -> bool:
    """Backward-compatible single-argument alias for `M4` router integration."""
    return is_disruption_intent(prompt)


def _normalize_midnight_end_bounds(norm_text: str) -> str:
    """
    Normalize Vietnamese midnight end-of-day expressions (`'24h'`, `'24:00'`, `'12h dem'`, `'0h dem'`, `'nua dem'`)
    to `'23:59'` when appearing after `- / den / toi / to` so same-day range parsers never wrap to `00:00` or `12:00`.
    """
    out = re.sub(
        r"(-|–|—|\bden\b|\btoi\b|\bto\b)\s*(?:24\s*(?::\s*00|h|gio)?|(?:12|0)\s*(?::\s*00|h|gio)\s*dem|nua\s*dem)\b",
        r"\1 23:59",
        norm_text,
    )
    return out


def _adjust_pm_from_context(
    s_time: Optional[str],
    e_time: Optional[str],
    norm_text: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Handle Vietnamese leading period-of-day cues such as `'Chiều thứ 4 từ 2h đến 4h'`
    or `'Tối thứ 5 từ 8h đến 12h đêm'` where `'chiều/tối'` precedes the weekday.
    """
    if not s_time or not e_time:
        return s_time, e_time
    has_pm_cue = bool(re.search(r"\b(?:chieu|toi|dem)\b", norm_text))
    has_am_cue = bool(re.search(r"\b(?:sang|am)\b", norm_text))
    if not has_pm_cue or has_am_cue:
        return s_time, e_time

    sh, sm = map(int, s_time.split(":"))
    eh, em = map(int, e_time.split(":"))
    if 1 <= sh <= 11:
        sh += 12
    if 1 <= eh <= 11:
        eh += 12
    elif eh == 12 and em == 0 and sh >= 12:
        eh, em = 23, 59
    if sh <= 23 and eh <= 23 and (eh * 60 + em) > (sh * 60 + sm):
        return f"{sh:02d}:{sm:02d}", f"{eh:02d}:{em:02d}"
    return s_time, e_time


def _resolve_immediate_now_window(norm_text: str, profile: CommitmentsProfile) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Support `'Ngay bây giờ / Bây giờ / Lúc này mình bận họp khẩn 90 phút'` anchored to `profile.now`."""
    if not re.search(r"\b(?:ngay\s+bay\s+gio|bay\s+gio|luc\s+nay|hien\s+tai|right\s+now)\b", norm_text):
        return None, None, None
    dur_min, dur_inferred = _extract_flexible_duration_min(norm_text)
    eff_dur = int(dur_min) if (not dur_inferred and dur_min and dur_min > 0) else 60

    ref = profile.now or profile.planning_week_start or "2026-11-02T08:00:00+07:00"
    try:
        dt = datetime.fromisoformat(str(ref).replace("Z", "+00:00"))
        day_en = WEEKDAYS[dt.weekday()]
        # Align start down to 15-min slot boundary
        start_total = dt.hour * 60 + (dt.minute // 15) * 15
        end_total = min(23 * 60 + 59, start_total + max(15, eff_dur))
        if end_total <= start_total:
            return day_en, None, None
        sh, sm = divmod(start_total, 60)
        eh, em = divmod(end_total, 60)
        return day_en, f"{sh:02d}:{sm:02d}", f"{eh:02d}:{em:02d}"
    except Exception:
        return None, None, None


def _extract_single_start_plus_duration(norm_text: str) -> Tuple[Optional[str], Optional[str]]:
    """Fallback parser for `'lúc 14h30 kéo dài 90 phút'` when an explicit `A - B` range is absent."""
    m = re.search(
        r"\b(?:luc|vao|tu)\s*(\d{1,2})\s*(?::|h|gio)\s*(\d{1,2}|ruoi)?\s*(am|pm)?\s*(sang|trua|chieu|toi|dem)?\b",
        norm_text,
    )
    if not m:
        return None, None
    s_time = _parse_clock_token(m.group(1), m.group(2), m.group(3), m.group(4))
    if not s_time:
        return None, None
    dur_min, dur_inferred = _extract_flexible_duration_min(norm_text)
    if dur_inferred or not dur_min or dur_min <= 0:
        return None, None

    sh, sm = map(int, s_time.split(":"))
    if 1 <= sh <= 11 and re.search(r"\b(?:chieu|toi|dem)\b", norm_text) and not re.search(r"\b(?:sang|am)\b", norm_text):
        sh += 12
        s_time = f"{sh:02d}:{sm:02d}"

    total_end_min = min(23 * 60 + 59, sh * 60 + sm + int(dur_min))
    eh, em = divmod(total_end_min, 60)
    if (eh * 60 + em) <= (sh * 60 + sm):
        return None, None
    return s_time, f"{eh:02d}:{em:02d}"


def _clean_disruption_title(raw_text: str) -> str:
    """
    Dedicated disruption event title extractor that strips temporal anchors (`'Tối thứ 5'`, `'từ 8h đến 12h đêm'`,
    `'ngay bây giờ'`, `'trong 90 phút'`) while preserving the meaningful disruption phrase (`'Họp CLB đột xuất'`,
    `'Cúp điện đột xuất'`, `'Khám bệnh đột xuất'`).
    """
    work = str(raw_text or "").split("\n")[0].strip()
    if not work:
        return "Sự kiện bận đột xuất"

    # Strip explicit time ranges, start clocks, durations, and temporal weekday/period anchors
    strip_patterns = (
        r"\b(?:từ|tu|from)\s+\d{1,2}\s*(?::|h|giờ|gio)?\s*(?:\d{1,2}|rưỡi|ruoi)?\s*(?:am|pm|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\s*(?:-|–|—|đến|den|tới|toi|to)\s*(?:\d{1,2}\s*(?::|h|giờ|gio)?\s*(?:\d{1,2}|rưỡi|ruoi)?\s*(?:am|pm|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?|nửa\s*đêm|nua\s*dem)\b",
        r"\b\d{1,2}\s*(?::|h|giờ|gio)\s*(?:\d{1,2}|rưỡi|ruoi)?\s*(?:am|pm|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\s*(?:-|–|—|đến|den|tới|toi|to)\s*\d{1,2}\s*(?::|h|giờ|gio)?\s*(?:\d{1,2}|rưỡi|ruoi)?\s*(?:am|pm|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\b",
        r"\b(?:lúc|luc|vào|vao)\s*\d{1,2}\s*(?::|h|giờ|gio)\s*(?:\d{1,2}|rưỡi|ruoi)?\s*(?:am|pm|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\b",
        r"\b(?:kéo\s*dài|keo\s*dai|trong(?:\s*vòng|\s*khoảng)?|khoảng|khoang|mất|mat|tầm|tam)?\s*\d+(?:[.,]\d+)?\s*(?:tiếng|tieng|giờ|gio|h|hours?|hrs?|phút|phut|p|mins?|minutes?)(?:\s*(?:rưỡi|ruoi))?\b",
        r"\b(?:buổi\s+|buoi\s+)?(?:sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\s*(?:ngày\s+|ngay\s+)?(?:thứ\s*(?:[2-7]|hai|ba|tư|tu|năm|nam|sáu|sau|bảy|bay)|t[2-7]|chủ\s*nhật|chu\s*nhat|cn|hôm\s*nay|hom\s*nay|ngày\s*mai|ngay\s*mai|mai|ngay\s*kia|ngày\s*kia|monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)\b",
        r"\b(?:ngay\s+bây\s+giờ|ngay\s+bay\s+gio|bây\s+giờ|bay\s+gio|lúc\s+này|luc\s+nay|hiện\s+tại|hien\s+tai)\b",
    )
    for pat in strip_patterns:
        work = re.sub(pat, " ", work, flags=re.IGNORECASE)

    work = re.sub(
        r"^\s*(?:mình|minh|em|tôi|toi)\s+(?:bị\s+|bi\s+|có\s+|co\s+|đang\s+|dang\s+)?",
        "",
        work,
        flags=re.IGNORECASE,
    )
    work = re.sub(
        r"^\s*(?:bị\s+|bi\s+|có\s+|co\s+)?(?:bận\s+|ban\s+|kẹt\s+|ket\s+)(?=(?:họp|hop|việc|viec|lịch|lich|khám|kham|đi|di))",
        "",
        work,
        flags=re.IGNORECASE,
    )
    work = re.sub(r"\s{2,}", " ", work).strip(" ,;:-.")
    norm_c = _strip_accents(work).lower().strip()
    generic_leftovers = {
        "",
        "ban",
        "ket",
        "dot xuat",
        "ban dot xuat",
        "viec dot xuat",
        "ket lich",
        "ket lich dot xuat",
        "ban viec",
        "ban viec dot xuat",
        "sang",
        "trua",
        "chieu",
        "toi",
        "dem",
    }
    if norm_c in generic_leftovers or len(norm_c) < 3:
        return "Sự kiện bận đột xuất"
    return work[0].upper() + work[1:]


def extract_disruption_fields(
    prompt: str,
    profile: CommitmentsProfile,
    pending_draft: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract `(title, day_of_week, start_time, end_time)` merging optional `pending_draft`."""
    draft = dict(pending_draft) if isinstance(pending_draft, dict) else {}
    norm_raw = _strip_accents(prompt or "").lower()
    norm = _normalize_midnight_end_bounds(norm_raw)
    now_day = _resolve_now_weekday(profile)

    now_d, now_s, now_e = _resolve_immediate_now_window(norm, profile)
    day_of_week = _resolve_day_token(prompt, now_day) or now_d or draft.get("day_of_week")

    s_time, e_time = _extract_time_range(norm)
    s_time, e_time = _adjust_pm_from_context(s_time, e_time, norm_raw)
    if not s_time or not e_time:
        fb_s, fb_e = _extract_single_start_plus_duration(norm)
        s_time = s_time or fb_s or now_s or draft.get("start_time")
        e_time = e_time or fb_e or now_e or draft.get("end_time")

    if s_time and e_time:
        sh, sm = map(int, s_time.split(":"))
        eh, em = map(int, e_time.split(":"))
        if (eh * 60 + em) <= (sh * 60 + sm):
            s_time, e_time = None, None

    new_title = _clean_disruption_title(prompt)
    if draft.get("title") and new_title == "Sự kiện bận đột xuất":
        title = str(draft["title"])
    else:
        title = new_title

    missing: List[str] = []
    if not day_of_week:
        missing.append("day_of_week")
    if not s_time or not e_time:
        missing.append("time_range")

    return {
        "title": title,
        "day_of_week": day_of_week,
        "start_time": s_time,
        "end_time": e_time,
        "missing_fields": missing,
    }


def _enrich_schedule_for_chat(profile: CommitmentsProfile, out: ScheduleOutput) -> Dict[str, Any]:
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
    return sched_dict


def _build_p8_thinking_summary(
    *,
    context_note_vi: str,
    chosen_solver: str,
    exec_ms: float,
    peak_match_pct: float,
    tasks_placed: int,
    tasks_total: int,
    stability_pct: float,
) -> Dict[str, Any]:
    pattern_rules = [
        {
            "pattern_id": "P8",
            "pattern_name": "Schedule Whiplash Prevention (Minimum-Perturbation Repair)",
            "causal_link_vi": (
                "Đóng băng toàn bộ các phiên không va chạm để tránh đảo lộn thói quen cả tuần khi phát sinh sự cố"
            ),
            "deterministic_rule": (
                f"LOCAL_INSERTION: freeze PINNED/DONE & non-colliding blocks -> min |Δs| "
                f"(Stability = {stability_pct:.1f}%)"
            ),
        }
    ]
    base_kwargs: Dict[str, Any] = {
        "intent": "DISRUPTION_REPAIR",
        "context_note_vi": context_note_vi,
        "chosen_solver": chosen_solver,
        "escalated_from_greedy": False,
        "exec_ms": exec_ms,
        "peak_match_pct": peak_match_pct,
        "tasks_placed": tasks_placed,
        "tasks_total": tasks_total,
    }
    sig_params = inspect.signature(build_thinking_summary).parameters
    if "repair_stability_pct" in sig_params:
        base_kwargs["repair_stability_pct"] = stability_pct
    if "pattern_rules" in sig_params:
        base_kwargs["pattern_rules"] = pattern_rules

    summary = build_thinking_summary(**base_kwargs)
    if not summary.get("pattern_rules"):
        summary["pattern_rules"] = pattern_rules
    summary["headline_vi"] = (
        f"Đã chèn sự cố & sửa cục bộ LOCAL_INSERTION (Giữ ổn định {stability_pct:.1f}% lịch tuần, {exec_ms:.0f}ms)"
    )
    return summary


def handle_disruption_chat_turn(
    payload_or_prompt: Any = None,
    profile: Optional[CommitmentsProfile] = None,
    tasks_raw: Optional[List[Any]] = None,
    pinned_raw: Optional[List[Any]] = None,
    completed_blocks: Optional[Dict[str, Any]] = None,
    algorithm: str = "SCORED_GREEDY",
    workspace_id: str = "default",
    auto_save: bool = True,
    *,
    prompt: Optional[str] = None,
    current_schedule: Optional[Any] = None,
    pending_draft: Optional[Dict[str, Any]] = None,
    mode_hint: str = "AUTO",
) -> Dict[str, Any]:
    """
    Execute conversational emergency disruption handling (`Pattern P8`).

    Supports BOTH calling conventions seamlessly for zero-conflict Wave 1A/1B integration:
      1) Dict payload: `handle_disruption_chat_turn(payload_dict)` (from `app.py` or `handlers.py`)
      2) Unpacked arguments: `handle_disruption_chat_turn(prompt, profile, tasks_raw, ...)` (like `M3`/`M4`)
    """
    t0 = time.perf_counter()
    saved_state_data: Dict[str, Any] = {}

    if isinstance(payload_or_prompt, dict):
        pl = payload_or_prompt
        workspace_id = str(pl.get("workspace_id") or workspace_id or "default")
        saved_rec = load_workspace_state(workspace_id=workspace_id)
        saved_state_data = (saved_rec.get("state") or {}) if isinstance(saved_rec, dict) else {}

        prompt_text = str(pl.get("prompt") or pl.get("text") or prompt or "").strip()
        mode_hint = str(pl.get("mode_hint") or mode_hint or "AUTO")
        pending_draft = pl.get("pending_draft") if isinstance(pl.get("pending_draft"), dict) else pending_draft
        auto_save = bool(pl.get("auto_save", auto_save))
        algorithm = str(pl.get("algorithm") or saved_state_data.get("activeSolver") or algorithm or "SCORED_GREEDY")

        comm_src = pl.get("commitments") or pl.get("profile") or saved_state_data.get("commitments") or {}
        eff_profile = (
            comm_src
            if isinstance(comm_src, CommitmentsProfile)
            else CommitmentsProfile.model_validate(comm_src)
        )
        eff_tasks_raw = pl.get("tasks") if pl.get("tasks") is not None else (saved_state_data.get("tasks") or [])
        eff_pinned_raw = (
            pl.get("pinned_blocks")
            if pl.get("pinned_blocks") is not None
            else (saved_state_data.get("pinnedBlocks") or [])
        )
        eff_completed = (
            pl.get("completed_blocks")
            if pl.get("completed_blocks") is not None
            else (saved_state_data.get("completedBlocks") or {})
        )
        raw_sched_in = pl.get("schedule") or pl.get("current_schedule") or saved_state_data.get("currentSchedule")
    else:
        prompt_text = str(prompt if prompt is not None else (payload_or_prompt or "")).strip()
        saved_rec = load_workspace_state(workspace_id=workspace_id)
        saved_state_data = (saved_rec.get("state") or {}) if isinstance(saved_rec, dict) else {}
        eff_profile = profile if isinstance(profile, CommitmentsProfile) else CommitmentsProfile.model_validate(profile or {})
        eff_tasks_raw = list(tasks_raw or [])
        eff_pinned_raw = list(pinned_raw or [])
        eff_completed = dict(completed_blocks or {})
        raw_sched_in = current_schedule

    task_models: List[Task] = [
        t if isinstance(t, Task) else Task.model_validate(t) for t in eff_tasks_raw
    ]
    pinned_models: List[ScheduleBlock] = [
        pb if isinstance(pb, ScheduleBlock) else ScheduleBlock.model_validate(pb) for pb in eff_pinned_raw
    ]

    norm_prompt = _strip_accents(prompt_text).lower().strip()
    if pending_draft and _CANCEL_DRAFT_RE.match(norm_prompt):
        exec_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "status": "CANCELLED",
            "intent": "DISRUPTION_REPAIR",
            "finalized": False,
            "finalized_message_vi": "",
            "reply_vi": "Đã hủy thao tác báo lịch bận đột xuất. Lịch trình hiện tại của bạn được giữ nguyên.",
            "thinking_summary": None,
            "pending_draft": None,
            "missing_fields": [],
            "quick_chips": [],
            "mutated_task_id": None,
            "traced_task": None,
            "remaining_estimation": None,
            "edge_case": None,
            "post_actions": build_post_actions(),
            "updated_commitments": eff_profile.model_dump(),
            "updated_tasks": [t.model_dump() for t in task_models],
            "updated_pinned_blocks": [pb.model_dump() for pb in pinned_models],
            "schedule": None,
            "execution_time_ms": exec_ms,
        }

    parsed = extract_disruption_fields(prompt_text, eff_profile, pending_draft=pending_draft)
    missing = parsed["missing_fields"]

    if missing:
        draft_out = {
            "intent": "DISRUPTION_REPAIR",
            "title": parsed["title"],
            "day_of_week": parsed["day_of_week"],
            "start_time": parsed["start_time"],
            "end_time": parsed["end_time"],
        }
        if "day_of_week" in missing and "time_range" in missing:
            ask_vi = (
                f"Mình đã ghi nhận việc phát sinh **\"{parsed['title']}\"**. "
                "Bạn bị bận vào **thứ mấy** và **khung giờ nào** (ví dụ: *Chiều thứ 5 từ 14:00 đến 16:00*) để mình dời nhẹ các phiên học bị trùng nhé?"
            )
            chips = [
                {"label": "Hôm nay 14:00–16:00", "prompt": "Hôm nay từ 14h đến 16h"},
                {"label": "Ngày mai 09:00–11:00", "prompt": "Ngày mai từ 9h đến 11h"},
                {"label": "Hủy báo bận", "prompt": "Hủy thao tác"},
            ]
        elif "day_of_week" in missing:
            ask_vi = (
                f"Sự kiện **\"{parsed['title']}\"** ({parsed['start_time']}–{parsed['end_time']}) diễn ra vào **ngày nào trong tuần** vậy bạn?"
            )
            chips = [
                {"label": "Hôm nay", "prompt": "Hôm nay"},
                {"label": "Ngày mai", "prompt": "Ngày mai"},
                {"label": "Thứ Năm", "prompt": "Thứ 5"},
            ]
        else:
            day_vi = _WEEKDAY_VI_MAP.get(str(parsed["day_of_week"]), str(parsed["day_of_week"]))
            ask_vi = (
                f"Bạn bận **\"{parsed['title']}\"** vào **{day_vi}** trong khung giờ từ mấy giờ đến mấy giờ "
                "để mình giữ nguyên phần lịch còn lại và chỉ xê dịch đúng chỗ bị trùng?"
            )
            chips = [
                {"label": "09:00 – 11:00", "prompt": "Từ 9h đến 11h"},
                {"label": "14:00 – 16:00", "prompt": "Từ 14h đến 16h"},
                {"label": "19:30 – 21:00", "prompt": "Từ 19h30 đến 21h"},
            ]

        exec_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "status": "NEEDS_CLARIFICATION",
            "intent": "DISRUPTION_REPAIR",
            "finalized": False,
            "finalized_message_vi": "",
            "reply_vi": ask_vi,
            "thinking_summary": None,
            "pending_draft": draft_out,
            "missing_fields": missing,
            "quick_chips": chips,
            "mutated_task_id": None,
            "traced_task": None,
            "remaining_estimation": None,
            "edge_case": None,
            "post_actions": [],
            "updated_commitments": eff_profile.model_dump(),
            "updated_tasks": [t.model_dump() for t in task_models],
            "updated_pinned_blocks": [pb.model_dump() for pb in pinned_models],
            "schedule": None,
            "execution_time_ms": exec_ms,
        }

    day_en = str(parsed["day_of_week"])
    start_hhmm = str(parsed["start_time"])
    end_hhmm = str(parsed["end_time"])
    event_title = str(parsed["title"])
    day_vi = _WEEKDAY_VI_MAP.get(day_en, day_en)

    # Resolve baseline schedule before disruption
    base_schedule: Optional[ScheduleOutput] = None
    if isinstance(raw_sched_in, ScheduleOutput):
        base_schedule = raw_sched_in
    elif isinstance(raw_sched_in, dict) and "blocks" in raw_sched_in and "summary" in raw_sched_in:
        try:
            base_schedule = ScheduleOutput.model_validate(raw_sched_in)
        except Exception:
            base_schedule = None

    eff_algo = algorithm if algorithm in ("SCORED_GREEDY", "HYBRID_ALNS", "BACKTRACK") else "SCORED_GREEDY"
    if base_schedule is None:
        base_schedule, _, _ = ScheduleController.solve_adaptive(
            profile=eff_profile,
            tasks=task_models,
            algorithm=eff_algo,
            pinned_blocks=pinned_models,
        )

    disruption_id = f"DISR_{uuid.uuid4().hex[:6].upper()}"
    disruption = DisruptionEvent(
        event_id=disruption_id,
        title=event_title,
        day_of_week=day_en,
        start_time=start_hhmm,
        end_time=end_hhmm,
        now_iso=eff_profile.now,
    )

    expanded_tasks = ScheduleController.expand_personal_habits(eff_profile, task_models)
    buffered_tasks = ScheduleController.apply_estimate_buffer(eff_profile, expanded_tasks)
    rep_out = LocalRepairEngine.repair_disruption(
        profile=eff_profile,
        tasks=buffered_tasks,
        current_schedule=base_schedule,
        disruption=disruption,
        mode="LOCAL_INSERTION",
        algorithm=eff_algo,
    )
    ScheduleController.annotate_estimate_buffer(eff_profile, buffered_tasks, rep_out.schedule)

    updated_profile = eff_profile.model_copy(deep=True)
    already_exists = any(
        str(fe.day_of_week) == day_en and fe.start_time == start_hhmm and fe.end_time == end_hhmm
        for fe in updated_profile.fixed_events
    )
    if not already_exists:
        updated_profile.fixed_events.append(
            FixedEvent(
                event_id=disruption_id,
                title=event_title,
                day_of_week=day_en,
                start_time=start_hhmm,
                end_time=end_hhmm,
                category="DISRUPTION",
            )
        )

    ergo_check = ScheduleController.inspect_repair_ergonomics(updated_profile, rep_out)
    sched_dict = _enrich_schedule_for_chat(updated_profile, rep_out.schedule)
    stability_pct = float(rep_out.stability_score)
    moved_cnt = int(rep_out.moved_blocks_count)

    if rep_out.directly_hit_blocks == 0 and moved_cnt == 0:
        reply_vi = (
            f"Đã ghi nhận lịch bận **\"{event_title}\"** ({day_vi}, `{start_hhmm}–{end_hhmm}`). "
            "Khung giờ này đang trống nên **100% các phiên học khác trong tuần được giữ nguyên vẹn**!"
        )
    else:
        moved_titles = []
        for ch in rep_out.changes:
            if ch.status == "MOVED" and ch.title not in moved_titles:
                moved_titles.append(
                    f"**{ch.title}** (chuyển sang {_WEEKDAY_VI_MAP.get(ch.new_day or '', ch.new_day or '')} `{ch.new_start_time}–{ch.new_end_time}`)"
                )
        moved_detail = ", ".join(moved_titles[:3])
        reply_vi = (
            f"Đã khóa khung bận **\"{event_title}\"** ({day_vi}, `{start_hhmm}–{end_hhmm}`) và sửa lịch cục bộ: "
            f"chỉ dời nhẹ `{moved_cnt}` phiên bị trùng ({moved_detail or 'sang khung trống gần nhất'}), "
            f"**giữ ổn định `{stability_pct:.1f}%`** các buổi học còn lại trong tuần."
        )

    quick_chips_out: List[Dict[str, str]] = []
    if ergo_check["has_ergonomic_degradation"]:
        reply_vi += (
            "\n\n💡 *Lưu ý sức khỏe:* Để hạn chế xáo trộn lịch chung, một phiên học nặng đang tạm dời sang khung giờ năng lượng thấp. "
            "Nếu muốn ưu tiên độ tỉnh táo hơn, bạn có thể chọn tối ưu lại lịch bên dưới."
        )
        quick_chips_out.append(
            {
                "label": "✨ Xếp tối ưu lại theo khung giờ tỉnh táo",
                "prompt": "Tối ưu lại lịch theo khung giờ năng lượng cao",
            }
        )

    now_vn_iso = datetime.now(timezone(timedelta(hours=7))).isoformat()
    disruption_log_entry = {
        "event_id": disruption_id,
        "title": event_title,
        "day_of_week": day_en,
        "start_time": start_hhmm,
        "end_time": end_hhmm,
        "disruption_slot_window": f"{day_en} {start_hhmm}-{end_hhmm}",
        "created_at": now_vn_iso,
    }

    if auto_save:
        prev_logs = list(saved_state_data.get("disruption_logs") or [])
        prev_logs.append(disruption_log_entry)
        next_state = dict(saved_state_data)
        next_state.update(
            {
                "commitments": updated_profile.model_dump(),
                "tasks": [t.model_dump() for t in task_models],
                "pinnedBlocks": [pb.model_dump() for pb in pinned_models],
                "completedBlocks": eff_completed,
                "activeSolver": eff_algo,
                "currentSchedule": sched_dict,
                "disruption_logs": prev_logs[-50:],
            }
        )
        save_workspace_state(next_state, workspace_id=workspace_id)

    exec_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    context_note = (
        f"Phát hiện sự cố đột xuất một lần \"{event_title}\" ({day_vi} {start_hhmm}–{end_hhmm}); "
        f"kích hoạt sửa cục bộ LOCAL_INSERTION thay vì xếp lại từ đầu."
    )
    thinking = _build_p8_thinking_summary(
        context_note_vi=context_note,
        chosen_solver="LOCAL_INSERTION",
        exec_ms=exec_ms,
        peak_match_pct=float(sched_dict["metrics"].get("peak_match_rate_pct", 100.0)),
        tasks_placed=rep_out.schedule.summary.tasks_placed,
        tasks_total=rep_out.schedule.summary.total_tasks_requested,
        stability_pct=stability_pct,
    )

    edge_case_dict = None
    if rep_out.schedule.overload is not None:
        edge_case_dict = {
            "has_edge_case": True,
            "severity": "WARNING",
            "code": "POST_DISRUPTION_OVERLOAD",
            "message_vi": rep_out.schedule.overload.message,
        }

    return {
        "status": "APPLIED",
        "intent": "DISRUPTION_REPAIR",
        "finalized": True,
        "finalized_message_vi": f"Đã chèn sự cố & giữ ổn định {stability_pct:.1f}% lịch tuần.",
        "reply_vi": reply_vi,
        "thinking_summary": thinking,
        "pending_draft": None,
        "missing_fields": [],
        "quick_chips": quick_chips_out,
        "mutated_task_id": None,
        "traced_task": None,
        "remaining_estimation": None,
        "edge_case": edge_case_dict,
        "post_actions": build_post_actions(),
        "updated_commitments": updated_profile.model_dump(),
        "updated_tasks": [t.model_dump() for t in task_models],
        "updated_pinned_blocks": [pb.model_dump() for pb in pinned_models],
        "schedule": sched_dict,
        "repair_summary": {
            "disruption_event": disruption.model_dump(),
            "stability_score": stability_pct,
            "moved_blocks_count": moved_cnt,
            "directly_hit_blocks": rep_out.directly_hit_blocks,
            "changes": [c.model_dump() for c in rep_out.changes],
            "ergonomic_check": ergo_check,
        },
        "execution_time_ms": exec_ms,
    }
