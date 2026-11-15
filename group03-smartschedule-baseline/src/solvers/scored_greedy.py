"""
Pattern 7 + Pattern 3 + Pattern 4 Solver: Exponential Urgency * Importance + Circadian & Category Batching.
Replaces the old EDF alias in SOLVER_REGISTRY['SCORED_GREEDY'] (Presentation2.pdf Slide 8 & 16).
Formula:
  Urgency(t) = exp(-max(0, slack_hours) / gamma) * Importance
  (Overdue / zero-slack tasks capped at OVERDUE_URGENCY_CAP * Importance; Habits use HABIT_BASE_URGENCY).
"""

import math
from typing import List, Optional, Tuple

from src.config import (
    GAMMA_URGENCY_HOURS,
    HABIT_BASE_URGENCY,
    OVERDUE_URGENCY_CAP,
)
from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task, TaskChunk
from src.solvers.base_solver import BaseScheduler
from src.utils import MINUTES_PER_SLOT


class ScoredGreedySolver(BaseScheduler):
    """Hyperbolic Urgency-Importance + Circadian Energy + Category Batching Solver."""

    solver_name = "SCORED_GREEDY"

    @staticmethod
    def should_prefer_energy_placement(profile: CommitmentsProfile, chunk: TaskChunk) -> bool:
        """SCORED_GREEDY always applies Pattern 3 Circadian & Pattern 4 Category Batching."""
        return True

    @staticmethod
    def compute_task_score(task: Task, now_slot: int, week_start_iso: str) -> Tuple[float, Optional[int]]:
        """Compute Pattern 7 Exponential Urgency * Importance priority score."""
        d_slot = task.resolve_deadline_slot(week_start_iso=week_start_iso)
        importance = float(task.priority)
        if d_slot is None:
            return round(HABIT_BASE_URGENCY * importance, 6), None

        planned_min = task.get_planned_duration_min()
        slack_min = (d_slot - now_slot) * MINUTES_PER_SLOT - planned_min
        slack_hours = slack_min / 60.0

        if slack_hours <= 0.0:
            # Overdue or zero slack: elevated capped urgency retaining relative tightness ordering
            urgency = OVERDUE_URGENCY_CAP + min(0.50, abs(slack_hours) * 0.01)
        else:
            urgency = math.exp(-slack_hours / GAMMA_URGENCY_HOURS)

        return round(urgency * importance, 6), d_slot

    @classmethod
    def _scored_sort_key(
        cls, idx: int, task: Task, now_slot: int, week_start_iso: str
    ) -> Tuple[float, int, int, int]:
        score, d_slot = cls.compute_task_score(task, now_slot, week_start_iso)
        return (-score, d_slot if d_slot is not None else 999999, -task.priority, idx)

    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        now_slot = self.resolve_now_slot(profile)
        return self.run_ranked_greedy_pipeline(
            profile=profile,
            tasks=tasks,
            pinned_blocks=pinned_blocks,
            sort_key_fn=self._scored_sort_key,
            primary_code="HYPERBOLIC_URGENCY_SCORE",
            reason_builder_fn=lambda task, rank, total: (
                f"[Scored Greedy] Xếp thứ {rank}/{total} "
                f"(Điểm Urgency×Priority = {self.compute_task_score(task, now_slot, profile.planning_week_start)[0]:.2f})."
            ),
        )

