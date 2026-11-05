"""
Logical Test: Dynamic Test Case Generation & Fuzzing
Author: Nguyen Nguyen Gia Bao (Builder 3 - Edge Cases & Testing)
Validates:
  - Automated generation of randomized task sets to stress-test solver logic
  - Cross-algorithm test generation matrix (EDF, LST, WSPT)
  - Time string fuzzing: Ensure parser either outputs valid slot or raises ValueError
  - Invariant: All dynamically generated schedules must satisfy C_hard == 0
"""

import random
from typing import List
import pytest

from src.controller import ScheduleController
from src.models import CommitmentsProfile, SleepSchedule, Task
from src.utils import DAYS_OF_WEEK, day_time_to_slot, minutes_to_slots, round_up_to_15


def _generate_synthetic_tasks(n: int, seed: int = 42) -> List[Task]:
    """Generates `n` valid synthetic tasks with random parameters."""
    rng = random.Random(seed)
    durations = [30, 45, 60, 75, 90, 120, 150]
    deadlines = [
        ("Monday", "18:00"),
        ("Tuesday", "23:59"),
        ("Wednesday", "12:00"),
        ("Thursday", "20:00"),
        ("Friday", "23:59"),
        ("Saturday", "17:00"),
        ("Sunday", "23:59"),
    ]

    tasks = []
    for i in range(1, n + 1):
        d_day, d_time = rng.choice(deadlines)
        dur = rng.choice(durations)
        splittable = dur > 90 or rng.random() > 0.5
        tasks.append(
            Task(
                task_id=f"GEN_{i:02d}",
                title=f"Synthetic Task {i}",
                duration_min=dur,
                deadline_day=d_day,
                deadline_time=d_time,
                priority=rng.randint(1, 5),
                is_splittable=splittable,
                min_chunk_min=45,
                max_chunk_min=90,
            )
        )
    return tasks


@pytest.mark.parametrize("algo", ["EDF", "LST", "WSPT"])
def test_generated_task_set_solver_matrix(algo: str):
    """
    Test Generator Matrix:
    Evaluates generated workload across multiple solver strategies.
    Every algorithm must maintain C_hard == 0 on the generated workload.
    """
    profile = CommitmentsProfile(
        student_id="GEN_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    synthetic_tasks = _generate_synthetic_tasks(n=10, seed=123)

    output, _ = ScheduleController.solve_schedule(profile, synthetic_tasks, algorithm=algo)

    assert output.summary.hard_constraint_violations == 0
    assert output.execution_time_ms < 500.0


def test_fuzzing_time_conversions():
    """Fuzzing generator: Feeds boundary time strings into day_time_to_slot."""
    valid_hours = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
    valid_hours.append("23:59")
    valid_hours.append("24:00")

    for day in DAYS_OF_WEEK:
        for t_str in random.sample(valid_hours, 10):
            slot = day_time_to_slot(day, t_str, is_end_or_deadline=(t_str in ("23:59", "24:00")))
            assert 0 <= slot <= 672, f"Slot out of bounds for {day} {t_str}: {slot}"


