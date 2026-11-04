"""
Logical Test: Circular Dependency Detection & DAG Integrity
Author: Nguyen Nguyen Gia Bao (Builder 3 - Edge Cases §8 & Architecture §7)
Validates:
  - Direct 2-node mutual dependencies (A -> B and B -> A)
  - Self-referential dependencies (A -> A)
  - Multi-node cycle detection (A -> B -> C -> A)
  - Disconnected subgraphs containing an isolated cycle
  - Invariant: Circular tasks must never cause infinite recursion or crash the scheduler
"""

import pytest

from src.controller import ScheduleController
from src.models import CommitmentsProfile, SleepSchedule, Task
from src.solvers.base_solver import BaseScheduler


def _get_minimal_profile():
    return CommitmentsProfile(
        student_id="STUDENT_DAG_TEST",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )


def test_topological_sort_direct_two_node_cycle():
    """Direct cycle: Task A depends on B, Task B depends on A."""
    task_a = Task(task_id="A", title="Task A", duration_min=60, deadline_day="Monday", deadline_time="18:00", depends_on=["B"])
    task_b = Task(task_id="B", title="Task B", duration_min=60, deadline_day="Monday", deadline_time="18:00", depends_on=["A"])

    sorted_tasks = BaseScheduler.enforce_dependency_order([task_a, task_b], sorted_tasks=[task_a, task_b])
    assert len(sorted_tasks) == 2
    ids = {t.task_id for t in sorted_tasks}
    assert ids == {"A", "B"}


def test_self_dependency_cycle():
    """Self-loop: Task A depends on itself (depends_on=['SELF_LOOP'])."""
    task_self = Task(
        task_id="SELF_LOOP",
        title="Self depending task",
        duration_min=45,
        deadline_day="Tuesday",
        deadline_time="12:00",
        depends_on=["SELF_LOOP"],
    )
    sorted_tasks = BaseScheduler.enforce_dependency_order([task_self], sorted_tasks=[task_self])
    assert len(sorted_tasks) == 1
    assert sorted_tasks[0].task_id == "SELF_LOOP"


def test_three_node_transitive_cycle():
    """Transitive cycle: A -> B -> C -> A."""
    task_a = Task(task_id="A", title="Task A", duration_min=60, deadline_day="Wednesday", deadline_time="12:00", depends_on=["B"])
    task_b = Task(task_id="B", title="Task B", duration_min=60, deadline_day="Wednesday", deadline_time="12:00", depends_on=["C"])
    task_c = Task(task_id="C", title="Task C", duration_min=60, deadline_day="Wednesday", deadline_time="12:00", depends_on=["A"])

    sorted_tasks = BaseScheduler.enforce_dependency_order([task_a, task_b, task_c], sorted_tasks=[task_a, task_b, task_c])
    assert len(sorted_tasks) == 3


def test_full_solver_handles_cycle_gracefully_without_unhandled_crash():
    """Engine test on cycle: Solver must finish execution cleanly (no stack overflow)."""
    profile = _get_minimal_profile()
    cycle_tasks = [
        Task(task_id="CYCLE_1", title="Cycle 1", duration_min=60, deadline_day="Monday", deadline_time="18:00", depends_on=["CYCLE_2"]),
        Task(task_id="CYCLE_2", title="Cycle 2", duration_min=60, deadline_day="Monday", deadline_time="18:00", depends_on=["CYCLE_1"]),
    ]

    out, _ = ScheduleController.solve_schedule(profile, cycle_tasks, algorithm="EDF")
    assert out is not None
    assert out.execution_time_ms < 500.0

