"""
Logical Test: Undefined Behaviors & Boundary Warning Traps
Author: Nguyen Nguyen Gia Bao (Builder 3 - Edge Cases §8 & System Architecture)
Validates:
  - Guarding against undefined state transitions and illegal parameters
  - Emitting warnings and exceptions on invalid time boundaries
  - Zero/negative durations, invalid hours (e.g., '25:99'), out-of-bounds slot indexes
  - Graceful degradation on completely empty or zero-task inputs
"""

import warnings
from pydantic import ValidationError
import pytest

from src.controller import ScheduleController
from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, SleepSchedule, Task
from src.utils import (
    MAX_HORIZON_SLOTS,
    SLOTS_PER_WEEK,
    day_time_to_slot,
    parse_day_to_index,
    parse_time_to_slot_offset,
    round_up_to_15,
)


def test_undefined_time_strings_raise_clean_value_error():
    """Attempting to parse impossible time strings must raise ValueError."""
    with pytest.raises(ValueError):
        parse_time_to_slot_offset("25:00")

    with pytest.raises(ValueError):
        parse_time_to_slot_offset("12:75")

    with pytest.raises(ValueError):
        parse_time_to_slot_offset("")

    with pytest.raises(ValueError):
        parse_day_to_index("Someday")


def test_out_of_bounds_slot_queries_are_safely_rejected():
    """GridManager must trap slot coordinates outside [0, total_slots) with clean error or false."""
    gm = TimeGridManager(total_slots=SLOTS_PER_WEEK)

    assert gm.is_range_free(-1, 4) is False
    assert gm.is_range_free(670, 5) is False

    violations = gm.explain_violation(-4, 4)
    assert any("OUT_OF_BOUNDS" in v["code"] for v in violations)


def test_empty_input_graceful_handling():
    """Passing zero tasks and no commitments must yield a valid, empty schedule with 0 errors."""
    profile = CommitmentsProfile(
        student_id="STUDENT_EMPTY",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )

    out, _ = ScheduleController.solve_schedule(profile, tasks=[], algorithm="EDF")
    assert out.summary.total_tasks_requested == 0
    assert out.summary.tasks_placed == 0
    assert out.summary.hard_constraint_violations == 0
    assert out.summary.deadline_satisfaction_rate == 100.0
    assert len(out.blocks) == 0


def test_invalid_task_parameters_validation_trap():
    """Task model must reject negative duration or priority outside 1..5."""
    with pytest.raises(ValidationError):
        Task(task_id="BAD_DUR", title="Negative duration", duration_min=-15)

    with pytest.raises(ValidationError):
        Task(task_id="PRIO_TOO_HIGH", title="Too High Priority", duration_min=60, priority=10)

    with pytest.raises(ValidationError):
        Task(task_id="PRIO_ZERO", title="Zero Priority", duration_min=60, priority=0)

