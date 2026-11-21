"""
RFC 5545 `.ics` Importer for University Timetables & Moodle/Canvas LMS Feeds (P3.2).

Pure standard-library parser (zero external dependencies, INV-1/INV-2 compliant).
Converts VEVENT blocks into LoA Level 4 preview drafts:
  - Timed / weekly recurring class events -> SmartSchedule `FixedEvent` dicts
  - Moodle / Canvas LMS deadline events   -> SmartSchedule `Task` dicts
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

BYDAY_TO_WEEKDAY = {
    "MO": "Monday",
    "TU": "Tuesday",
    "WE": "Wednesday",
    "TH": "Thursday",
    "FR": "Friday",
    "SA": "Saturday",
    "SU": "Sunday",
}

_DEADLINE_RE = re.compile(
    r"\b(due|deadline|assignment|quiz|homework|submission|closes|exam|midterm|final|lab\s+\d+|"
    r"nộp|hạn|bài\s+tập|kiểm\s+tra|thi\s+cuối\s+kỳ|thi\s+giữa\s+kỳ)\b",
    re.IGNORECASE,
)
_EXAM_RE = re.compile(r"\b(exam|midterm|final|quiz|kiểm\s+tra|thi)\b", re.IGNORECASE)
_CODING_RE = re.compile(r"\b(code|coding|lab|project|git|repo|program|lập\s+trình|đồ\s+án)\b", re.IGNORECASE)
_MEAL_RE = re.compile(r"\b(lunch|dinner|breakfast|meal|ăn\s+trưa|ăn\s+tối|ăn\s+sáng)\b", re.IGNORECASE)
_WORK_RE = re.compile(r"\b(shift|part-time|work|ca\s+làm|đi\s+làm|intern)\b", re.IGNORECASE)


def _unfold_ics_lines(ics_text: str) -> List[str]:
    """Unfold RFC 5545 folded lines (CRLF/LF followed by single space or tab)."""
    normalized = ics_text.replace("\r\n", "\n").replace("\r", "\n")
    unfolded: List[str] = []
    for raw_line in normalized.split("\n"):
        if raw_line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw_line[1:]
        else:
            unfolded.append(raw_line)
    return unfolded


def _unescape_ics_text(text: str) -> str:
    return (
        text.replace("\\n", " ")
        .replace("\\N", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _parse_ics_datetime(
    raw_value: str,
    tz_offset_hours: int = 7,
) -> Tuple[Optional[datetime], bool]:
    """
    Parse RFC 5545 DTSTART/DTEND value into timezone-aware local datetime.
    Returns `(dt, is_all_day)`.
    """
    val = (raw_value or "").strip()
    local_tz = timezone(timedelta(hours=tz_offset_hours))
    if not val:
        return None, False

    # All-day date: YYYYMMDD
    if re.fullmatch(r"\d{8}", val):
        try:
            dt = datetime.strptime(val, "%Y%m%d").replace(hour=23, minute=45, tzinfo=local_tz)
            return dt, True
        except ValueError:
            return None, False

    # UTC timestamp: YYYYMMDDTHHMMSSZ
    if re.fullmatch(r"\d{8}T\d{6}Z", val):
        try:
            utc_dt = datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            return utc_dt.astimezone(local_tz), False
        except ValueError:
            return None, False

    # Floating / TZID local timestamp: YYYYMMDDTHHMMSS
    if re.fullmatch(r"\d{8}T\d{6}", val):
        try:
            dt = datetime.strptime(val, "%Y%m%dT%H%M%S").replace(tzinfo=local_tz)
            return dt, False
        except ValueError:
            return None, False

    return None, False


def _extract_bydays(rrule: str) -> List[str]:
    if not rrule:
        return []
    m = re.search(r"BYDAY=([A-Z,]+)", rrule.upper())
    if not m:
        return []
    days: List[str] = []
    for token in m.group(1).split(","):
        code = token.strip()[-2:]
        if code in BYDAY_TO_WEEKDAY and BYDAY_TO_WEEKDAY[code] not in days:
            days.append(BYDAY_TO_WEEKDAY[code])
    return days


def _round_hhmm_15(dt: datetime) -> str:
    total_min = dt.hour * 60 + dt.minute
    rounded = min(23 * 60 + 45, max(0, ((total_min + 7) // 15) * 15))
    return f"{rounded // 60:02d}:{rounded % 60:02d}"


def _classify_fixed_event_type(summary: str, categories: str) -> str:
    combined = f"{summary} {categories}"
    if _MEAL_RE.search(combined):
        return "MEAL"
    if _WORK_RE.search(combined):
        return "WORK_SHIFT"
    return "ACADEMIC_CLASS"


def _infer_task_metadata(summary: str, categories: str) -> Tuple[str, int, int]:
    """Return `(category, cognitive_load, priority)` inferred from LMS event text."""
    combined = f"{summary} {categories}"
    if _EXAM_RE.search(combined):
        return "EXAM_PREP", 3, 5
    if _CODING_RE.search(combined):
        return "CODING", 3, 4
    return "ASSIGNMENT", 2, 4


def parse_ics_calendar(
    ics_text: str,
    tz_offset_hours: int = 7,
    default_task_duration_min: int = 90,
) -> Dict[str, Any]:
    """
    Parse raw `.ics` content into LoA Level 4 preview drafts of `FixedEvent` and `Task`.
    """
    if not ics_text or "BEGIN:VEVENT" not in ics_text:
        return {
            "fixed_events": [],
            "tasks": [],
            "warnings": ["No VEVENT entries found in provided .ics content."],
            "stats": {"total_vevents": 0, "fixed_event_count": 0, "task_count": 0},
        }

    lines = _unfold_ics_lines(ics_text)
    vevents: List[Dict[str, str]] = []
    current: Optional[Dict[str, str]] = None

    for line in lines:
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            current = {}
            continue
        if stripped == "END:VEVENT":
            if current is not None:
                vevents.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        prop_part, value = line.split(":", 1)
        prop_name = prop_part.split(";", 1)[0].strip().upper()
        current[prop_name] = value.strip()

    fixed_events: List[Dict[str, Any]] = []
    tasks: List[Dict[str, Any]] = []
    warnings: List[str] = []

    dur_default = max(15, ((int(default_task_duration_min) + 14) // 15) * 15)

    for idx, ev in enumerate(vevents, start=1):
        summary = _unescape_ics_text(ev.get("SUMMARY") or f"Imported Event {idx}")
        categories = _unescape_ics_text(ev.get("CATEGORIES") or "")
        rrule = ev.get("RRULE") or ""

        dt_start, is_all_day = _parse_ics_datetime(ev.get("DTSTART") or "", tz_offset_hours=tz_offset_hours)
        dt_end, _ = _parse_ics_datetime(ev.get("DTEND") or "", tz_offset_hours=tz_offset_hours)

        if dt_start is None:
            warnings.append(f"Skipped VEVENT #{idx} ('{summary}'): missing or invalid DTSTART.")
            continue

        duration_min = 0
        if dt_end is not None and dt_end > dt_start:
            duration_min = int((dt_end - dt_start).total_seconds() // 60)

        has_weekly_rrule = "FREQ=WEEKLY" in rrule.upper()
        looks_like_deadline = (
            is_all_day
            or dt_end is None
            or duration_min < 15
            or (not has_weekly_rrule and bool(_DEADLINE_RE.search(f"{summary} {categories}")))
        )

        if looks_like_deadline:
            dl_dt = dt_end if (dt_end is not None and dt_end >= dt_start and not is_all_day) else dt_start
            day_name = WEEKDAY_NAMES[dl_dt.weekday()]
            dl_time = "23:45" if is_all_day else _round_hhmm_15(dl_dt)
            cat, load, prio = _infer_task_metadata(summary, categories)
            tasks.append(
                {
                    "task_id": f"ICS-T{len(tasks) + 1:02d}",
                    "title": summary,
                    "category": cat,
                    "duration_min": dur_default,
                    "deadline_day": day_name,
                    "deadline_time": dl_time,
                    "deadline_iso": dl_dt.isoformat(),
                    "priority": prio,
                    "cognitive_load": load,
                    "is_splittable": dur_default > 90,
                    "min_chunk_min": 45,
                    "max_chunk_min": 90,
                    "source": "ICS_LMS_IMPORT",
                }
            )
            continue

        # Otherwise classify as timed FixedEvent (expand weekly BYDAY if present)
        start_hhmm = _round_hhmm_15(dt_start)
        end_hhmm = _round_hhmm_15(dt_end) if dt_end is not None else _round_hhmm_15(dt_start + timedelta(minutes=60))
        if start_hhmm == end_hhmm:
            end_hhmm = _round_hhmm_15(dt_start + timedelta(minutes=max(30, duration_min)))

        event_type = _classify_fixed_event_type(summary, categories)
        target_days = _extract_bydays(rrule) if has_weekly_rrule else [WEEKDAY_NAMES[dt_start.weekday()]]
        if not target_days:
            target_days = [WEEKDAY_NAMES[dt_start.weekday()]]

        for d_name in target_days:
            fixed_events.append(
                {
                    "event_id": f"ICS-E{len(fixed_events) + 1:02d}",
                    "title": summary,
                    "event_type": event_type,
                    "day": d_name,
                    "start_time": start_hhmm,
                    "end_time": end_hhmm,
                    "source": "ICS_TIMETABLE_IMPORT",
                }
            )

    return {
        "fixed_events": fixed_events,
        "tasks": tasks,
        "warnings": warnings,
        "stats": {
            "total_vevents": len(vevents),
            "fixed_event_count": len(fixed_events),
            "task_count": len(tasks),
        },
    }
