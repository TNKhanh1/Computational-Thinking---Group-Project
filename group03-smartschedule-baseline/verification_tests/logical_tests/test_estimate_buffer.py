"""
Feature 001 — Estimate Buffer (planning-fallacy correction).
Spec: specs/001-estimate-buffer/spec.md (acceptance criteria AC1–AC7).
Author: Nguyen Trong Tien (Thinker 3 - Abstraction & Algorithmic Design)
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.controller import ScheduleController
from src.estimate_buffer import multiplier_for_habit, normalize_habit, planned_duration_min
from src.models import CommitmentsProfile, SleepSchedule, Task
from web.api import app

client = TestClient(app)
SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "test_scenarios"


def _profile(habit=None):
    return CommitmentsProfile(
        student_id="BUFFER_TEST",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
        estimate_habit=habit,
    )


def _task(task_id, minutes, day="Friday"):
    return Task(task_id=task_id, title=task_id, duration_min=minutes, deadline_day=day, deadline_time="18:00")


# ---------------------------------------------------------------- pure rule (FR2, FR3)
@pytest.mark.parametrize(
    "estimate, habit, expected",
    [
        (60, "OFTEN", 75),      # AC1: the gap-test value
        (90, "OFTEN", 120),     # 112.5 -> nearest 120
        (45, "OFTEN", 60),      # 56.25 -> 60
        (25, "OFTEN", 30),      # 31.25 -> 30 (naive round-up would give 45)
        (15, "OFTEN", 15),      # 18.75 -> 15 (naive round-up would double it to 30)
        (10, "OFTEN", 15),      # small task: grid already rounds to 15, buffer adds nothing
        (5, "OFTEN", 15),
        (120, "SOMETIMES", 135),  # 132 -> 135
        (60, "SOMETIMES", 60),    # 66 -> 60 (buffer absorbed)
        (60, "RARELY", 60),
        (50, None, 60),           # no habit: exact V0 round_up_to_15
    ],
)
def test_planned_duration_rule(estimate, habit, expected):
    assert planned_duration_min(estimate, multiplier_for_habit(habit)) == expected


def test_planned_never_below_unbuffered_v0_value():
    for estimate in range(1, 300):
        for habit in (None, "RARELY", "SOMETIMES", "OFTEN"):
            planned = planned_duration_min(estimate, multiplier_for_habit(habit))
            v0 = -(-estimate // 15) * 15
            assert planned >= v0
            assert planned % 15 == 0
            # Error vs. the exact buffered time is at most half a slot, unless the V0 floor wins.
            if planned > v0:
                assert abs(planned - estimate * multiplier_for_habit(habit)) <= 7.5


def test_habit_normalisation():
    assert normalize_habit("often") == "OFTEN"
    assert normalize_habit("") is None
    assert normalize_habit(None) is None
    with pytest.raises(ValueError):
        normalize_habit("ALWAYS")
    with pytest.raises(ValueError):
        CommitmentsProfile(estimate_habit="ALWAYS")


# ---------------------------------------------------------------- engine (AC1, AC3, AC4, AC5)
def test_ac1_ac4_often_plans_75_minutes_with_reason():
    out, _ = ScheduleController.solve_schedule(_profile("OFTEN"), [_task("ESSAY", 60)], algorithm="EDF")
    block = out.blocks[0]
    assert block.duration_min == 75
    reason = next(r for r in block.reasons if r["code"] == "ESTIMATE_BUFFER")
    assert reason["estimate_min"] == 60 and reason["planned_min"] == 75 and reason["multiplier"] == 1.25


def test_ac3_small_tasks_are_not_padded_further():
    tasks = [_task("EMAIL", 5), _task("SUBMIT", 10), _task("QUIZ", 15)]
    out, _ = ScheduleController.solve_schedule(_profile("OFTEN"), tasks, algorithm="EDF")
    assert len(out.blocks) == 3
    for b in out.blocks:
        assert b.duration_min == 15
        assert all(r.get("code") != "ESTIMATE_BUFFER" for r in b.reasons)


def test_input_tasks_are_not_mutated_and_buffer_is_idempotent():
    profile = _profile("OFTEN")
    original = _task("ESSAY", 60)
    once = ScheduleController.apply_estimate_buffer(profile, [original])
    twice = ScheduleController.apply_estimate_buffer(profile, once)
    assert original.buffer_multiplier == 1.0
    assert once[0].get_planned_duration_min() == twice[0].get_planned_duration_min() == 75


@pytest.mark.parametrize("algorithm", ["EDF", "LST", "WSPT", "BACKTRACK"])
def test_ac5_all_solvers_use_buffer_and_stay_deterministic(algorithm):
    tasks = [_task("A", 60, "Wednesday"), _task("B", 90, "Thursday")]
    res = ScheduleController.verify_determinism(_profile("OFTEN"), tasks, algorithm=algorithm, runs=3)
    assert res["is_deterministic"]
    planned = {b.task_id: sum(x.duration_min for x in res["schedule"].blocks if x.task_id == b.task_id)
               for b in res["schedule"].blocks}
    assert planned == {"A": 75, "B": 120}


def test_overload_numbers_use_buffered_minutes():
    # Monday 06:30-18:00 = 690 free minutes. 8 x 90 = 720 raw (> 690), 8 x 120 = 960 buffered.
    tasks = [_task(f"T{i}", 90, "Monday") for i in range(8)]
    out, _ = ScheduleController.solve_schedule(_profile("OFTEN"), tasks, algorithm="EDF")
    assert out.overload is not None
    assert out.overload.total_planned_work_minutes == 960


# ---------------------------------------------------------------- AC2: V0 behaviour unchanged
@pytest.mark.parametrize("scenario_file", sorted(p.name for p in SCENARIOS_DIR.glob("t*.json")))
def test_ac2_no_habit_keeps_v0_results(scenario_file):
    sc = json.loads((SCENARIOS_DIR / scenario_file).read_text(encoding="utf-8"))
    profile = CommitmentsProfile.model_validate(sc["commitments"])
    tasks = [Task.model_validate(t) for t in sc["tasks"]]
    assert profile.estimate_habit is None
    out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    for b in out.blocks:
        assert all(r.get("code") != "ESTIMATE_BUFFER" for r in b.reasons)
    raw = {t.task_id: -(-t.duration_min // 15) * 15 for t in tasks}
    placed = {}
    for b in out.blocks:
        placed[b.task_id] = placed.get(b.task_id, 0) + b.duration_min
    for task_id, minutes in placed.items():
        assert minutes == raw[task_id]


# ---------------------------------------------------------------- API (AC6, AC7)
def test_ac7_improve_plan_contract_lowercase_habit():
    payload = {
        "now": "2026-11-02T06:00:00+07:00",
        "week_start": "2026-11-02T00:00:00+07:00",
        "algorithm": "EDF",
        "profile": {"sleep": {"start": "23:30", "end": "06:30"}, "estimate_habit": "often"},
        "fixed_events": [],
        "tasks": [{"id": "T1", "title": "Essay", "estimate_min": 60, "due": "2026-11-04T23:59:00+07:00"}],
    }
    res = client.post("/api/plan", json=payload)
    assert res.status_code == 200
    assert res.json()["blocks"][0]["duration_min"] == 75


def test_ac6_overrun_adds_to_raw_estimate_then_rebuffers():
    payload = {
        "commitments": {"planning_week_start": "2026-11-02T00:00:00+07:00", "estimate_habit": "OFTEN"},
        "tasks": [{"task_id": "ESSAY", "title": "Essay", "duration_min": 60, "deadline_day": "Friday"}],
        "task_id": "ESSAY",
        "extra_min": 30,
    }
    res = client.post("/api/progress", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["old_duration_min"] == 75
    assert data["new_estimate_min"] == 90
    assert data["new_duration_min"] == 120


def test_invalid_habit_is_rejected_by_api():
    payload = {"commitments": {"estimate_habit": "ALWAYS"}, "tasks": []}
    assert client.post("/api/plan", json=payload).status_code == 400
