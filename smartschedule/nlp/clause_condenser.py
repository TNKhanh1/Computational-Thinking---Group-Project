"""
Deterministic Clause & Cross-Day Window Condenser (Layer 4 NLP — Layer A & C).

Handles:
  - Cross-day start-to-deadline bounds ("từ 19h tối thứ 3, đến 21h tối thứ 5")
  - Same-day start-end ranges ("18:00 - 19:00", "từ 14h đến 16h30")
  - Recurring weekday lists ("thứ 2, 4, 6", "hằng ngày")
  - Flexible duration & continuity extraction ("cần hoàn thành trong tổng thời gian 2 tiếng liên tục" -> 120m)
  - Clause-level Vietnamese subject title condensation ("Làm bài tập môn Computational Thinking..." -> "Làm bài tập Computational Thinking")
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from smartschedule.core.models import CommitmentsProfile
from smartschedule.nlp.parser_controller import OfflineNLParser, WEEKDAYS, _strip_accents

_OFFLINE_NL = OfflineNLParser()

_WEEKDAY_VI_MAP: Dict[str, str] = {
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
    """Detect a start-anchor + end-deadline window spanning days."""
    day_expr = r"(?:ngay\s+)?(?:thu\s*(?:[2-7]|hai|ba|tu|nam|sau|bay)|t[2-7]|chu\s*nhat|cn|hom\s*nay|ngay\s*mai|mai|monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    time_expr = r"(\d{1,2})\s*(?::|h|gio)\s*(\d{1,2}|ruoi)?\s*(am|pm)?\s*(sang|trua|chieu|toi|dem)?"

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
    """Extract explicit same-day `(start_time, end_time)` pairs."""
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


def _extract_flexible_duration_min(norm_text: str) -> Tuple[Optional[int], bool]:
    """Extract explicit task duration including phrasing with 'tổng thời gian' / 'thời lượng'."""
    dur_val, dur_inferred = _OFFLINE_NL.extract_duration_min(norm_text)
    if not dur_inferred and dur_val is not None:
        return dur_val, False

    m = re.search(
        r"\b(?:trong(?:\s+vong|\s+khoang)?\s+)?"
        r"(?:tong\s+)?(?:thoi\s*gian(?:\s+la)?\s+|thoi\s*luong\s+|khoang\s+|tam\s+|mat\s+|keo\s*dai\s+)"
        r"(\d+(?:[.,]\d+)?)\s*(tieng|gio|h|hours?|hrs?|phut|p|m|mins?|minutes?)\b",
        norm_text,
    )
    if m:
        raw_num = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        mins = int(round(raw_num * 60)) if unit.startswith(("t", "g", "h")) else int(round(raw_num))
        if mins >= 15:
            return mins, False
    return dur_val, dur_inferred


def _is_temporal_or_constraint_clause(clause_norm: str) -> bool:
    """Identify secondary comma-clauses describing time windows, duration bounds, or pacing constraints."""
    c = clause_norm.strip(" ,;:-.")
    if not c:
        return True
    has_day_or_clock = bool(
        re.search(
            r"\b(?:\d{1,2}\s*(?::|h|gio)|thu\s*(?:[2-7]|hai|ba|tu|nam|sau|bay)|t[2-7]|chu\s*nhat|cn|hom\s*nay|ngay\s*mai|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            c,
        )
    )
    if re.match(r"^(?:tu|from|toi|den|truoc|to|until|deadline|han\s*chot|han\s*nop|vao|luc)\b", c) and (
        has_day_or_clock or re.search(r"\b(?:sang|trua|chieu|toi|dem)\b", c)
    ):
        return True
    if re.search(
        r"\b(?:tong\s*thoi\s*gian|thoi\s*luong|thuc\s*hien\s+trong|hoan\s*thanh\s+trong|lam\s+trong|keo\s*dai(?:\s+trong)?|trong\s+khoang)\b",
        c,
    ) and re.search(r"\b\d+(?:[.,]\d+)?\s*(?:tieng|gio|h|phut|p|m|mins?|hours?)\b", c):
        return True
    if re.match(
        r"^(?:trong(?:\s+vong|\s+khoang)?\s+)?\d+(?:[.,]\d+)?\s*(?:tieng|gio|h|phut|p|m|mins?|hours?)(?:\s+(?:lien\s*tuc|lien\s*mach))?$",
        c,
    ):
        return True
    if re.match(
        r"^(?:lam\s+)?(?:lien\s*tuc|lien\s*mach|lien\s*1\s*mach|khong\s*(?:the\s*)?chia\s*nho|hang\s*ngay|moi\s*ngay|hang\s*tuan)$",
        c,
    ):
        return True
    if re.match(r"^[2-7]$", c):
        return True
    return False


def _clean_conversational_title(raw_text: str) -> str:
    """Clause-level subject title condenser preserving clean Vietnamese/English task names."""
    first_line = str(raw_text or "").split("\n")[0].strip()
    if not first_line:
        return ""

    raw_clauses = [c.strip() for c in re.split(r"[,;]+", first_line) if c.strip()]
    kept_clauses: List[str] = []
    for cl in raw_clauses:
        cl_norm = _strip_accents(cl).lower().strip()
        if len(raw_clauses) > 1 and _is_temporal_or_constraint_clause(cl_norm):
            continue
        kept_clauses.append(cl)

    work = ", ".join(kept_clauses) if kept_clauses else first_line

    clause_patterns = (
        r"(?:,\s*)?\b(?:từ|tu|from)\s+(?:(?!(?:tới|đến|trước|\bto\b|\buntil\b))[^;\n]){1,55}?\b(?:tới|toi|đến|den|trước|truoc|to|until)\s+[^,\n]+",
        r"(?:,\s*)?\b(?:cần\s*|can\s*|phải\s*|phai\s*)?(?:thực\s*hiện|thuc\s*hien|làm|lam|hoàn\s*thành|hoan\s*thanh|học|hoc|kéo\s*dài|keo\s*dai)?\s*(?:trong(?:\s*vòng|\s*khoảng|\s*tổng\s*thời\s*gian|\s*thời\s*gian)?|tổng\s*thời\s*gian|tong\s*thoi\s*gian|thời\s*gian|thoi\s*gian|thời\s*lượng|thoi\s*luong|khoảng|khoang|mất|mat|tầm|tam)\s+\d+(?:[.,]\d+)?\s*(?:tiếng|tieng|giờ|gio|h|phút|phut|p|m|mins?|hours?)(?:\s+(?:liên\s*tục|lien\s*tuc|liền\s*mạch|lien\s*mach|liền|lien|không\s*chia\s*nhỏ|khong\s*chia\s*nho))?\b",
        r"(?:,\s*)?\b(?:làm\s+|lam\s+)?(?:liên\s*tục|lien\s*tuc|liền\s*mạch|lien\s*mach|liền\s*1\s*mạch|lien\s*1\s*mach|không\s*thể\s*chia\s*nhỏ|khong\s*the\s*chia\s*nho|không\s*chia\s*nhỏ|khong\s*chia\s*nho)\b",
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

    cleaned = re.sub(
        r"(?:,\s*)?\b(?:cần\s*hoàn\s*thành|can\s*hoan\s*thanh|hoàn\s*thành|hoan\s*thanh|cần\s*thực\s*hiện|can\s*thuc\s*hien|thực\s*hiện|thuc\s*hien|cần\s*làm|can\s*lam|trong\s+tổng\s+thời\s+gian|tong\s+thoi\s+gian|liên\s*tục|lien\s*tuc|trong|từ|tu|tới|toi|đến|den)\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b((?:làm|lam)\s+(?:bài|bai)\s+(?:tập|tap)|(?:bài|bai)\s+(?:tập|tap)|(?:ôn|on)\s+(?:thi|tập|tap)|(?:đồ|do)\s+(?:án|an)|(?:báo|bao)\s+(?:cáo|cao)|(?:thực|thuc)\s+(?:hành|hanh)|học|hoc|lab)\s+(?:môn\s+học|mon\s+hoc|môn|mon|học\s+phần|hoc\s+phan|bộ\s+môn|bo\s+mon)\s+(?=\S)",
        r"\1 ",
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
