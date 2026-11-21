"""
Verification tests for P3.2: RFC 5545 `.ics` University Timetable & Moodle/Canvas LMS Importer.
"""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from smartschedule.core.config import CORE_DIR
from smartschedule.core.ics_importer import parse_ics_calendar
from smartschedule.api.app import app

SAMPLE_UNIVERSITY_AND_LMS_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//HCMUS//SmartSchedule Test//EN
BEGIN:VEVENT
UID:cs252-lecture@hcmus.edu.vn
SUMMARY:CS252 Computational Thinking
  Lecture (Room E204)
DTSTART:20261102T073000
DTEND:20261102T100000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE
CATEGORIES:LECTURE
END:VEVENT
BEGIN:VEVENT
UID:moodle-lab05@courses.hcmus.edu.vn
SUMMARY:Lab 05 Coding Assignment is due
DTSTART:20261105T150000Z
DTEND:20261105T150000Z
CATEGORIES:MOODLE
END:VEVENT
BEGIN:VEVENT
UID:canvas-midterm@hcmus.edu.vn
SUMMARY:Midterm Exam Preparation Deadline
DTSTART:20261106
END:VEVENT
BEGIN:VEVENT
UID:bad-event@hcmus.edu.vn
SUMMARY:Corrupted Event Without Date
END:VEVENT
END:VCALENDAR
"""


def test_ics_importer_ast_purity_inv1_inv2() -> None:
    """INV-1 & INV-2: smartschedule/core/ics_importer.py must not import api/nlp/solvers/controller."""
    src_path = CORE_DIR / "ics_importer.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    forbidden = (
        "smartschedule.api",
        "smartschedule.nlp",
        "web",
        "fastapi",
        "starlette",
        "httpx",
        "smartschedule.core.solvers",
        "smartschedule.core.controller",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods = [node.module]
        else:
            continue
        for mod in mods:
            for bad in forbidden:
                assert not (mod == bad or mod.startswith(f"{bad}.")), f"Forbidden import: {mod}"


def test_parse_ics_university_timetable_and_moodle_deadlines() -> None:
    res = parse_ics_calendar(SAMPLE_UNIVERSITY_AND_LMS_ICS, tz_offset_hours=7, default_task_duration_min=90)
    assert res["stats"]["total_vevents"] == 4
    assert res["stats"]["fixed_event_count"] == 2
    assert res["stats"]["task_count"] == 2
    assert len(res["warnings"]) == 1

    # Weekly recurring lecture expanded to Monday & Wednesday with unfolded summary
    days = [e["day"] for e in res["fixed_events"]]
    assert days == ["Monday", "Wednesday"]
    assert "Lecture (Room E204)" in res["fixed_events"][0]["title"]
    assert res["fixed_events"][0]["start_time"] == "07:30"
    assert res["fixed_events"][0]["end_time"] == "10:00"
    assert res["fixed_events"][0]["event_type"] == "ACADEMIC_CLASS"

    # Moodle UTC 15:00Z -> +07:00 = 22:00 Thursday, classified as CODING load=3
    t_lab = res["tasks"][0]
    assert t_lab["deadline_day"] == "Thursday"
    assert t_lab["deadline_time"] == "22:00"
    assert t_lab["category"] == "CODING"
    assert t_lab["cognitive_load"] == 3

    # Canvas all-day exam -> Friday 23:45, EXAM_PREP priority=5
    t_exam = res["tasks"][1]
    assert t_exam["deadline_day"] == "Friday"
    assert t_exam["deadline_time"] == "23:45"
    assert t_exam["category"] == "EXAM_PREP"
    assert t_exam["priority"] == 5


def test_api_import_ics_endpoint() -> None:
    client = TestClient(app)
    r_bad = client.post("/api/import/ics", json={"ics_content": ""})
    assert r_bad.status_code == 400

    r_ok = client.post(
        "/api/import/ics",
        json={"ics_content": SAMPLE_UNIVERSITY_AND_LMS_ICS, "tz_offset_hours": 7},
    )
    assert r_ok.status_code == 200
    body = r_ok.json()
    assert body["stats"]["fixed_event_count"] == 2
    assert body["stats"]["task_count"] == 2
