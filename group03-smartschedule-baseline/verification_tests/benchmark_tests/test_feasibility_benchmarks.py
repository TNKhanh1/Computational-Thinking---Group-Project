"""
Scheduling Feasibility Benchmark Suite: Response Retrieval & Solvability Evaluation.
Author: Nguyen Nguyen Gia Bao (Builder 3 - Edge Cases §8 & Architecture §7)

Evaluates whether problem instances are mathematically POSSIBLE (feasible) or IMPOSSIBLE (infeasible).
The test retrieves the solver/API response and rigorously verifies the classification:
  - If mathematically feasible: Must return 100% placement, 0 hard violations, 0 unplaced tasks.
  - If mathematically impossible (capacity shortage): Must detect overload, compute exact shortage, and flag unplaced.
  - If mathematically impossible (fragmentation barrier): Must identify atomic task in unplaced without violating constraints.
  - If the solver returns the incorrect classification or violates constraints, the test FAILS.
"""

from pathlib import Path
import pytest

from src.controller import ScheduleController
from src.models import CommitmentsProfile, FixedEvent, SleepSchedule, Task

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _make_profile(fixed_events=None):
    return CommitmentsProfile(
        student_id="EVAL_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=fixed_events or [],
    )


def test_response_retrieval_tight_feasible_single_gap():
    """
    FEASIBILITY BENCHMARK (POSSIBLE - Exact Tight Fit):
    On Monday, student has class 06:30–13:00 and 15:00–23:30.
    The ONLY available free window on Monday is 13:00–15:00 (exactly 120 minutes).
    Task: 120 minutes, due Monday 15:00.
    Evaluation: Mathematically 100% possible (0 slack).
    Failure Rule: If task is unplaced or placed outside [13:00, 15:00], test FAILS.
    """
    classes = [
        FixedEvent(event_id="C_EARLY", title="Morning Lecture", day_of_week="Monday", start_time="06:30", end_time="13:00"),
        FixedEvent(event_id="C_LATE", title="Evening Lab", day_of_week="Monday", start_time="15:00", end_time="23:30"),
    ]
    profile = _make_profile(fixed_events=classes)
    task = Task(
        task_id="T_TIGHT",
        title="Tight Gap Project",
        duration_min=120,
        deadline_day="Monday",
        deadline_time="15:00",
        is_splittable=True,
    )

    out, _ = ScheduleController.solve_schedule(profile, [task], algorithm="EDF")

    # Response Retrieval Verification
    assert out.summary.hard_constraint_violations == 0, "Hard constraint violation detected on feasible input"
    assert out.summary.tasks_placed == 1, "Failed to place task in provably feasible 120m gap"
    assert len(out.unplaced_tasks) == 0, f"Incorrect response: reported unplaced tasks: {out.unplaced_tasks}"

    # Verify placed slots are strictly inside the 13:00-15:00 gap on Monday
    for b in out.blocks:
        assert b.day == "Monday"
        assert b.start_time >= "13:00"
        assert b.end_time <= "15:00"


def test_response_retrieval_impossible_capacity_exhaustion():
    """
    FEASIBILITY BENCHMARK (IMPOSSIBLE - Capacity Shortage):
    On Monday, student sleeps 00:00–06:30, has class 06:30–11:00.
    Available free time before 12:00 deadline = 60 minutes (11:00–12:00).
    Two tasks require 60m + 60m = 120m before 12:00.
    Mathematical Proof: Shortage = 120 - 60 = 60 minutes.
    Failure Rule: If solver reports 100% deadline satisfaction or misses the overload diagnosis, test FAILS.
    """
    classes = [
        FixedEvent(event_id="C_MON", title="Morning Class", day_of_week="Monday", start_time="06:30", end_time="11:00")
    ]
    profile = _make_profile(fixed_events=classes)
    task_a = Task(task_id="T_A", title="Task A", duration_min=60, deadline_day="Monday", deadline_time="12:00", priority=5)
    task_b = Task(task_id="T_B", title="Task B", duration_min=60, deadline_day="Monday", deadline_time="12:00", priority=3)

    out, _ = ScheduleController.solve_schedule(profile, [task_a, task_b], algorithm="EDF")

    # Response Retrieval Verification: Must identify impossibility
    assert out.summary.hard_constraint_violations == 0
    assert len(out.unplaced_tasks) >= 1, "Incorrect response: solver claimed impossible schedule was 100% placed!"

    # Verify Overload Report accuracy
    assert out.overload is not None, "Incorrect response: missing OverloadReport on capacity exhaustion"
    assert out.overload.error_type == "CAPACITY_SHORTAGE"
    assert out.overload.shortage_minutes == 60, f"Expected 60m shortage, retrieved: {out.overload.shortage_minutes}"


def test_response_retrieval_impossible_fragmentation_barrier():
    """
    FEASIBILITY BENCHMARK (IMPOSSIBLE - Fragmentation Failure):
    On Monday before 14:30 deadline, free time is split into two disjoint 90m gaps:
      - 10:30–12:00 (90 min free)
      - 13:00–14:30 (90 min free)
    Total free time = 180 min.
    Task: 150 min, atomic (is_splittable = False), due Monday 14:30.
    Mathematical Proof: Total free (180m) > task duration (150m), but largest gap (90m) < task duration (150m).
    Failure Rule: If solver places the atomic task (causing class overlap) or fails to flag it unplaced, test FAILS.
    """
    classes = [
        FixedEvent(event_id="B1", title="Early Block", day_of_week="Monday", start_time="06:30", end_time="10:30"),
        FixedEvent(event_id="B2", title="Mid Class", day_of_week="Monday", start_time="12:00", end_time="13:00"),
    ]
    profile = _make_profile(fixed_events=classes)
    atomic_task = Task(
        task_id="T_ATOMIC_150",
        title="Unsplittable Lab Exam",
        duration_min=150,
        deadline_day="Monday",
        deadline_time="14:30",
        is_splittable=False,
    )

    out, _ = ScheduleController.solve_schedule(profile, [atomic_task], algorithm="EDF")

    # Response Retrieval Verification
    assert out.summary.hard_constraint_violations == 0, "Atomic task must never overlap classes to force placement"
    unplaced_ids = {u["task_id"] for u in out.unplaced_tasks}
    assert "T_ATOMIC_150" in unplaced_ids, "Incorrect response: unsplittable task exceeding gap size was not flagged unplaced"


def test_response_retrieval_prerequisite_chain_feasibility():
    """
    FEASIBILITY BENCHMARK (POSSIBLE - Sequential Dependency Chain):
    Prerequisite chain: Architecture (60m) -> Implementation (90m) -> Testing (45m).
    All due Thursday 22:00. Sufficient free time available.
    Evaluation: Feasible.
    Failure Rule: If dependency order is inverted (e.g. Test starts before Arch ends), test FAILS.
    """
    profile = _make_profile()
    arch = Task(task_id="CHAIN_1_ARCH", title="Architecture Spec", duration_min=60, deadline_day="Thursday", deadline_time="22:00", priority=4)
    impl = Task(task_id="CHAIN_2_IMPL", title="Implementation", duration_min=90, deadline_day="Thursday", deadline_time="22:00", priority=4, depends_on=["CHAIN_1_ARCH"])
    test_task = Task(task_id="CHAIN_3_TEST", title="Unit Testing", duration_min=45, deadline_day="Thursday", deadline_time="22:00", priority=4, depends_on=["CHAIN_2_IMPL"])

    out, _ = ScheduleController.solve_schedule(profile, [arch, impl, test_task], algorithm="EDF")

    # Response Retrieval Verification
    assert out.summary.hard_constraint_violations == 0
    assert out.summary.tasks_placed == 3
    assert len(out.unplaced_tasks) == 0

    blocks_arch = [b for b in out.blocks if b.task_id == "CHAIN_1_ARCH"]
    blocks_impl = [b for b in out.blocks if b.task_id == "CHAIN_2_IMPL"]
    blocks_test = [b for b in out.blocks if b.task_id == "CHAIN_3_TEST"]

    assert max(b.end_slot for b in blocks_arch) <= min(b.start_slot for b in blocks_impl), "Implementation started before Architecture finished"
    assert max(b.end_slot for b in blocks_impl) <= min(b.start_slot for b in blocks_test), "Testing started before Implementation finished"


def test_response_retrieval_zero_free_window_impossible():
    """
    FEASIBILITY BENCHMARK (IMPOSSIBLE - Deadlocked Zero Free Window):
    Task due Monday 06:00. Sleep is locked 23:30–06:30.
    Available free time before 06:00 = 0 minutes.
    Evaluation: Impossible.
    Failure Rule: If solver places task inside sleep window, test FAILS (H2 violation).
    """
    profile = _make_profile()
    deadlocked_task = Task(
        task_id="T_SLEEP_LOCKED",
        title="Impossible Midnight Task",
        duration_min=45,
        deadline_day="Monday",
        deadline_time="06:00",
    )

    out, _ = ScheduleController.solve_schedule(profile, [deadlocked_task], algorithm="EDF")

    # Response Retrieval Verification
    assert out.summary.hard_constraint_violations == 0, "Solver must NEVER violate sleep to satisfy deadline"
    assert len(out.unplaced_tasks) == 1, "Task must be classified as unplaced when free window is 0"
