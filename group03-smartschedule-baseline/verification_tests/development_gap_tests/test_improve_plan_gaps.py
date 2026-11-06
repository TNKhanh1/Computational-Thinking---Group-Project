"""
Development Gap Tests: Intentional Failing Tests Tracking Improve Plan Target Features.
Author: Nguyen Nguyen Gia Bao (Builder 3 - Edge Cases §8 & Architecture §7)

PURPOSE:
These tests define the TARGET BEHAVIORS from `Improve_Plan/improve_plan.md`
that the current Baseline (V0) cannot yet fulfill.
They INTENTIONALLY FAIL against V0 to expose the development backlog for our team.
When teammates implement these features in upcoming weeks, these tests will turn green.
"""

from fastapi.testclient import TestClient
import pytest

from src.controller import ScheduleController
from src.models import CommitmentsProfile, SleepSchedule, Task
from web.api import app

client = TestClient(app)


def test_fail_circadian_energy_matching():
    """
    TARGET: Improve Plan §3.3 & §7.3, Proposal Pillar 2 (Pattern Recognition).
    A student with focus_preference='EVENING' (18:00–21:00) adding a DEEP focus task
    MUST have that task placed during evening focus hours (>= 18:00).

    WHY V0 CURRENTLY FAILS:
    V0 Greedy EDF is energy-blind and places tasks into the earliest free slot (Monday 06:30).
    """
    profile = CommitmentsProfile(
        student_id="LAN_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    deep_task = Task(
        task_id="T_DEEP_ESSAY",
        title="Essay: Deep Research",
        duration_min=90,
        deadline_day="Wednesday",
        deadline_time="23:59",
        priority=4,
    )

    out, _ = ScheduleController.solve_schedule(profile, [deep_task], algorithm="EDF")
    assert len(out.blocks) >= 1
    placed_block = out.blocks[0]

    start_hour = int(placed_block.start_time.split(":")[0])
    assert start_hour >= 18, (
        f"[IMPROVE PLAN GAP: §3.3] Circadian rhythm matching is not implemented in V0. "
        f"Deep task was placed at {placed_block.day} {placed_block.start_time} instead of evening focus hours (>= 18:00)."
    )


def test_fail_rest_break_insertion_after_deep_work():
    """
    TARGET: Improve Plan Decision D2 & Table §3.3.
    After a 90-minute Deep focus task, a 15-minute rest break (1 slot) MUST be reserved
    before the next task starts to prevent cognitive fatigue.

    WHY V0 CURRENTLY FAILS:
    V0 packs tasks contiguously back-to-back with 0 gap.
    """
    profile = CommitmentsProfile(
        student_id="REST_TEST",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    task1 = Task(task_id="T1_DEEP", title="Deep Coding Session", duration_min=90, deadline_day="Monday", deadline_time="18:00", priority=5)
    task2 = Task(task_id="T2_FOLLOWUP", title="Follow-up Quiz", duration_min=45, deadline_day="Monday", deadline_time="18:00", priority=4)

    out, _ = ScheduleController.solve_schedule(profile, [task1, task2], algorithm="EDF")
    assert len(out.blocks) == 2

    b1 = [b for b in out.blocks if b.task_id == "T1_DEEP"][0]
    b2 = [b for b in out.blocks if b.task_id == "T2_FOLLOWUP"][0]

    gap_slots = b2.start_slot - b1.end_slot
    assert gap_slots >= 1, (
        f"[IMPROVE PLAN GAP: Decision D2] 15-minute rest break after Deep work is not implemented in V0. "
        f"Gap between tasks is {gap_slots * 15} min instead of >= 15 min."
    )


def test_fail_planning_fallacy_buffer_multiplier():
    """
    TARGET: Improve Plan §6.2 (Planned duration buffer) & Proposal Pillar 2 Part B.
    When a student has estimate_habit='OFTEN', an estimation buffer (1.25x) MUST be applied,
    so an estimate of 60m is scheduled as 75m (5 slots).

    WHY V0 CURRENTLY FAILS:
    V0 maintains raw duration (T_planned = T_estimate = 60 min).
    """
    profile = CommitmentsProfile(
        student_id="BUFFER_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
        # Feature 001 (spec clarification C2): the docstring's precondition estimate_habit='OFTEN'
        # was missing from the input. The default stays "no buffer" so T01–T10 keep V0 results.
        estimate_habit="OFTEN",
    )
    task = Task(task_id="T_ESSAY_BUFFER", title="Writing Assignment", duration_min=60, deadline_day="Tuesday", deadline_time="18:00")

    out, _ = ScheduleController.solve_schedule(profile, [task], algorithm="EDF")
    assert len(out.blocks) >= 1
    placed = out.blocks[0]

    assert placed.duration_min == 75, (
        f"[IMPROVE PLAN GAP: Feature F06] Behavioral planning buffer is not implemented in V0. "
        f"Expected buffered duration of 75 min, but V0 scheduled raw {placed.duration_min} min."
    )


def test_fail_why_popover_structured_reason_codes():
    """
    TARGET: Improve Plan §7.3 Table (Why Here? Popover reason codes).
    Each scheduled block MUST return a structured `reasons[]` array containing
    reasons such as 'ENERGY_MATCH' and 'BREAK_AFTER'.

    WHY V0 CURRENTLY FAILS:
    V0 only produces basic 'BEFORE_DEADLINE' and 'EARLIEST_FREE_GAP', missing 'ENERGY_MATCH'.
    """
    profile = CommitmentsProfile(
        student_id="REASON_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    task = Task(task_id="T_WHY", title="Math Review", duration_min=60, deadline_day="Monday", deadline_time="18:00", priority=4)

    out, _ = ScheduleController.solve_schedule(profile, [task], algorithm="EDF")
    assert len(out.blocks) >= 1
    b = out.blocks[0]

    reason_codes = {r.get("code") for r in b.reasons}
    assert "ENERGY_MATCH" in reason_codes, (
        f"[IMPROVE PLAN GAP: Table §7.3] Structured reason code 'ENERGY_MATCH' is missing. "
        f"Current reason codes returned: {reason_codes}."
    )


def test_fail_overload_habit_skipping_recommendation():
    """
    TARGET: Improve Plan Feature F15 & Table §7.3 (Overload resolution options).
    When the week is overloaded, the engine MUST suggest skipping flexible habits
    ('SKIP_HABIT') to preserve academic assignments.

    WHY V0 CURRENTLY FAILS:
    V0 does not distinguish habits from assignments and only suggests dropping lowest priority.
    """
    res_sc = client.get("/api/scenarios/t06")
    assert res_sc.status_code == 200
    sc_data = res_sc.json()

    res_plan = client.post(
        "/api/plan",
        json={"commitments": sc_data["commitments"], "tasks": sc_data["tasks"], "algorithm": "EDF"},
    )
    assert res_plan.status_code == 200
    overload = res_plan.json().get("overload")
    assert overload is not None

    option_codes = {opt.get("code") for opt in overload.get("options", [])}
    assert "SKIP_HABIT" in option_codes, (
        f"[IMPROVE PLAN GAP: Feature F15] Overload resolution failed to suggest 'SKIP_HABIT'. "
        f"Available options returned: {option_codes}."
    )
