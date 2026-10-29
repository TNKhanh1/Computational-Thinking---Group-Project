"""
Schedule Exporter Module (baseline_plan.md §7.6 item 9 & §8).
Exports schedules to:
  1. JSON (standardized schedule_output.json & overload_report.json)
  2. CSV (spreadsheet-ready tabular schedule)
  3. ICS (RFC 5545 iCalendar format for Google Calendar / Apple Calendar / Outlook)
"""

import csv
from datetime import datetime, timedelta, timezone
import io
import json
from typing import Optional

from src.models import CommitmentsProfile, ScheduleOutput
from src.utils import SLOTS_PER_DAY, parse_day_to_index, parse_iso_datetime, parse_time_to_slot_offset


def export_to_json(schedule: ScheduleOutput, indent: int = 2) -> str:
    """Serialize ScheduleOutput to formatted JSON string."""
    return json.dumps(schedule.model_dump(), ensure_ascii=False, indent=indent)


def export_to_csv(schedule: ScheduleOutput) -> str:
    """Serialize placed schedule blocks into a UTF-8 CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "block_id",
        "task_id",
        "title",
        "day",
        "start_time",
        "end_time",
        "start_slot",
        "end_slot",
        "duration_min",
        "priority",
        "deadline",
        "chunk_index",
        "total_chunks",
        "state",
        "reason",
    ])
    for b in schedule.blocks:
        writer.writerow([
            b.block_id,
            b.task_id,
            b.title,
            b.day,
            b.start_time,
            b.end_time,
            b.start_slot,
            b.end_slot,
            b.duration_min,
            b.priority,
            b.deadline_str,
            b.chunk_index,
            b.total_chunks,
            b.state,
            b.reason,
        ])
    return output.getvalue()


def _format_ics_dt(dt: datetime) -> str:
    """Format datetime as YYYYMMDDTHHMMSS in local time."""
    return dt.strftime("%Y%m%dT%H%M%S")


def export_to_ics(
    schedule: ScheduleOutput,
    profile: Optional[CommitmentsProfile] = None,
) -> str:
    """
    Generate an RFC 5545 iCalendar (.ics) file string containing placed task blocks
    (and optionally fixed commitment events from profile).
    """
    week_start_str = profile.planning_week_start if profile else "2026-11-02T00:00:00+07:00"
    ws_dt = parse_iso_datetime(week_start_str)
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//FIT-HCMUS Group 03//SmartSchedule Baseline V0//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:SmartSchedule Weekly Plan",
        "X-WR-TIMEZONE:Asia/Ho_Chi_Minh",
    ]

    # 1. Export placed task blocks
    for b in schedule.blocks:
        start_dt = ws_dt + timedelta(minutes=b.start_slot * 15)
        end_dt = ws_dt + timedelta(minutes=b.end_slot * 15)
        uid = f"smartschedule-{b.block_id}-{start_dt.strftime('%Y%m%d%H%M')}@fithcmus.edu.vn"
        part_tag = f" ({b.chunk_index}/{b.total_chunks})" if b.total_chunks > 1 else ""
        summary = f"[{b.task_id}] {b.title}{part_tag}"
        desc = (
            f"Priority: {b.priority}/5 | Deadline: {b.deadline_str}\\n"
            f"Solver: {schedule.solver_used}\\n"
            f"Reason: {b.reason}"
        )
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;TZID=Asia/Ho_Chi_Minh:{_format_ics_dt(start_dt)}",
            f"DTEND;TZID=Asia/Ho_Chi_Minh:{_format_ics_dt(end_dt)}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{desc}",
            "CATEGORIES:STUDY_TASK",
            "END:VEVENT",
        ])

    # 2. Export fixed events if profile is provided
    if profile:
        for ev in profile.fixed_events:
            days = ev.day_of_week if isinstance(ev.day_of_week, list) else [ev.day_of_week]
            expanded_days = []
            for d in days:
                if str(d).strip().upper() == "ALL":
                    expanded_days = list(range(7))
                    break
                try:
                    expanded_days.append(parse_day_to_index(str(d)))
                except ValueError:
                    pass
            s_off = parse_time_to_slot_offset(ev.start_time, is_end_or_deadline=False)
            e_off = parse_time_to_slot_offset(ev.end_time, is_end_or_deadline=True)
            for d_idx in expanded_days:
                if d_idx >= 7:
                    continue
                s_slot = d_idx * SLOTS_PER_DAY + s_off
                e_slot = d_idx * SLOTS_PER_DAY + e_off
                s_dt = ws_dt + timedelta(minutes=s_slot * 15)
                e_dt = ws_dt + timedelta(minutes=e_slot * 15)
                uid = f"smartschedule-fixed-{ev.event_id}-d{d_idx}@fithcmus.edu.vn"
                lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{now_stamp}",
                    f"DTSTART;TZID=Asia/Ho_Chi_Minh:{_format_ics_dt(s_dt)}",
                    f"DTEND;TZID=Asia/Ho_Chi_Minh:{_format_ics_dt(e_dt)}",
                    f"SUMMARY:[FIXED] {ev.title}",
                    f"DESCRIPTION:Category: {ev.category}",
                    f"CATEGORIES:{ev.category}",
                    "END:VEVENT",
                ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
