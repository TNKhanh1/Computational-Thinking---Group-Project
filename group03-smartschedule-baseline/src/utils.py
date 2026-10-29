"""
Time & Slot Conversion Utilities for the 672-slot (15-minute) Discrete Time Grid.
Supports both Baseline Schema (weekday + HH:MM) and Improve Plan Schema (ISO-8601 with +07:00 offset),
including 2-week horizon (slots 0..1343) for cross-week deadlines (Scenario T10).
"""

from datetime import datetime, timedelta, timezone
import math
from typing import Optional, Tuple

MINUTES_PER_SLOT: int = 15
SLOTS_PER_HOUR: int = 4
SLOTS_PER_DAY: int = 96
DAYS_PER_WEEK: int = 7
SLOTS_PER_WEEK: int = 672
MAX_HORIZON_SLOTS: int = 1344  # 2 weeks for T10 cross-week horizon

DAYS_OF_WEEK = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

DAYS_OF_WEEK_VI = {
    "Monday": "Thứ Hai",
    "Tuesday": "Thứ Ba",
    "Wednesday": "Thứ Tư",
    "Thursday": "Thứ Năm",
    "Friday": "Thứ Sáu",
    "Saturday": "Thứ Bảy",
    "Sunday": "Chủ Nhật",
    "Next Monday": "Thứ Hai (Tuần sau)",
    "Next Tuesday": "Thứ Ba (Tuần sau)",
    "Next Wednesday": "Thứ Tư (Tuần sau)",
    "Next Thursday": "Thứ Năm (Tuần sau)",
    "Next Friday": "Thứ Sáu (Tuần sau)",
    "Next Saturday": "Thứ Bảy (Tuần sau)",
    "Next Sunday": "Chủ Nhật (Tuần sau)",
}

DAY_ALIASES = {
    "monday": 0, "mon": 0, "mo": 0, "t2": 0, "thu 2": 0, "thứ 2": 0, "thứ hai": 0,
    "tuesday": 1, "tue": 1, "tu": 1, "t3": 1, "thu 3": 1, "thứ 3": 1, "thứ ba": 1,
    "wednesday": 2, "wed": 2, "we": 2, "t4": 2, "thu 4": 2, "thứ 4": 2, "thứ tư": 2,
    "thursday": 3, "thu": 3, "th": 3, "t5": 3, "thu 5": 3, "thứ 5": 3, "thứ năm": 3,
    "friday": 4, "fri": 4, "fr": 4, "t6": 4, "thu 6": 4, "thứ 6": 4, "thứ sáu": 4,
    "saturday": 5, "sat": 5, "sa": 5, "t7": 5, "thu 7": 5, "thứ 7": 5, "thứ bảy": 5,
    "sunday": 6, "sun": 6, "su": 6, "cn": 6, "chu nhat": 6, "chủ nhật": 6,
    "next monday": 7, "next_monday": 7, "next mon": 7,
    "next tuesday": 8, "next_tuesday": 8, "next tue": 8,
    "next wednesday": 9, "next_wednesday": 9, "next wed": 9,
    "next thursday": 10, "next_thursday": 10, "next thu": 10,
    "next friday": 11, "next_friday": 11, "next fri": 11,
    "next saturday": 12, "next_saturday": 12, "next sat": 12,
    "next sunday": 13, "next_sunday": 13, "next sun": 13,
}

VN_TZ = timezone(timedelta(hours=7))


def round_up_to_15(minutes: int) -> int:
    """Round a positive duration in minutes up to the nearest multiple of 15 minutes."""
    if minutes <= 0:
        return 0
    return int(math.ceil(minutes / float(MINUTES_PER_SLOT)) * MINUTES_PER_SLOT)


def minutes_to_slots(minutes: int) -> int:
    """Convert duration in minutes to number of 15-minute slots (rounded up)."""
    if minutes <= 0:
        return 0
    return int(math.ceil(minutes / float(MINUTES_PER_SLOT)))


def parse_day_to_index(day_str: str) -> int:
    """
    Convert a weekday name or alias to day index (0=Monday .. 6=Sunday, 7=Next Monday .. 13=Next Sunday).
    Raises ValueError if unrecognized.
    """
    if not day_str:
        raise ValueError("Empty day string provided.")
    cleaned = day_str.strip().lower()
    if cleaned in DAY_ALIASES:
        return DAY_ALIASES[cleaned]
    raise ValueError(f"Unrecognized day_of_week: '{day_str}'")


def parse_time_to_slot_offset(time_str: str, is_end_or_deadline: bool = False) -> int:
    """
    Convert 'HH:MM' string into a slot offset within a day (0..96).
    Note: '23:59' or '24:00' when used as an end time or deadline is treated as end-of-day (slot 96).
    """
    if not time_str:
        raise ValueError("Empty time string provided.")
    cleaned = time_str.strip()
    if cleaned in ("24:00", "23:59", "23:59:59"):
        return SLOTS_PER_DAY if is_end_or_deadline else SLOTS_PER_DAY - 1

    parts = cleaned.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid time format '{time_str}', expected HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour == 24 and minute == 0:
        return SLOTS_PER_DAY
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Time out of range: '{time_str}'")

    total_minutes = hour * 60 + minute
    if is_end_or_deadline and minute == 59:
        total_minutes += 1
    return total_minutes // MINUTES_PER_SLOT


def day_time_to_slot(day_str: str, time_str: str, is_end_or_deadline: bool = False) -> int:
    """
    Formula from baseline_plan.md §2:
    Slot Index = day * 96 + hour * 4 + floor(minute / 15)
    """
    day_idx = parse_day_to_index(day_str)
    slot_offset = parse_time_to_slot_offset(time_str, is_end_or_deadline=is_end_or_deadline)
    return day_idx * SLOTS_PER_DAY + slot_offset


def parse_iso_datetime(iso_str: str) -> datetime:
    """Parse an ISO-8601 datetime string; attach UTC+7 if naive."""
    dt = datetime.fromisoformat(iso_str.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=VN_TZ)
    else:
        dt = dt.astimezone(VN_TZ)
    return dt


def iso_to_slot(iso_str: str, week_start_iso: str = "2026-11-02T00:00:00+07:00", is_end_or_deadline: bool = False) -> int:
    """
    Convert an ISO-8601 datetime to a slot index relative to week_start_iso.
    Supports 2-week horizon (slots 0..1344).
    """
    dt = parse_iso_datetime(iso_str)
    ws = parse_iso_datetime(week_start_iso)
    delta_seconds = (dt - ws).total_seconds()
    delta_minutes = delta_seconds / 60.0
    if is_end_or_deadline and dt.minute == 59:
        delta_minutes += 1.0
    slot = int(math.floor(delta_minutes / MINUTES_PER_SLOT))
    return max(0, min(MAX_HORIZON_SLOTS, slot))


def slot_to_day_time(slot_idx: int, is_end_time: bool = False) -> Tuple[str, str]:
    """
    Convert a slot index back to (day_name, 'HH:MM').
    Handles end-of-day boundary cleanly (e.g., slot 96 as end_time of Monday -> ('Monday', '24:00')).
    """
    if is_end_time and slot_idx > 0 and slot_idx % SLOTS_PER_DAY == 0:
        day_idx = (slot_idx // SLOTS_PER_DAY) - 1
        time_str = "24:00"
    else:
        day_idx = slot_idx // SLOTS_PER_DAY
        rem_slots = slot_idx % SLOTS_PER_DAY
        total_min = rem_slots * MINUTES_PER_SLOT
        hour = total_min // 60
        minute = total_min % 60
        time_str = f"{hour:02d}:{minute:02d}"

    if 0 <= day_idx < DAYS_PER_WEEK:
        day_name = DAYS_OF_WEEK[day_idx]
    elif DAYS_PER_WEEK <= day_idx < 2 * DAYS_PER_WEEK:
        day_name = f"Next {DAYS_OF_WEEK[day_idx - DAYS_PER_WEEK]}"
    else:
        day_name = f"Day+{day_idx}"
    return day_name, time_str


def slot_to_iso(slot_idx: int, week_start_iso: str = "2026-11-02T00:00:00+07:00") -> str:
    """Convert a slot index to an ISO-8601 timestamp with +07:00 offset."""
    ws = parse_iso_datetime(week_start_iso)
    dt = ws + timedelta(minutes=slot_idx * MINUTES_PER_SLOT)
    return dt.isoformat()


def format_slot_range(start_slot: int, end_slot: int) -> str:
    """Format a [start_slot, end_slot) range into human-readable 'Day HH:MM–HH:MM'."""
    day_name, start_str = slot_to_day_time(start_slot, is_end_time=False)
    _, end_str = slot_to_day_time(end_slot, is_end_time=True)
    return f"{day_name} {start_str}–{end_str}"

