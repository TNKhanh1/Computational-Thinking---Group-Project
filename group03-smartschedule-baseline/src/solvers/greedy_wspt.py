"""
Solution 3C: Weighted Shortest Processing Time (WSPT / Smith's Rule) Solver.
Specified in baseline_plan.md §3.3.3C: Ratio(t) = Priority(t) / Duration_Min(t).
"""

from typing import List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task
from src.solvers.base_solver import BaseScheduler
from src.utils import MINUTES_PER_SLOT


class GreedyWSPTSolver(BaseScheduler):
    """
    Weighted Shortest Processing Time (WSPT / Smith's Rule) Solver.
    Fixes A2: Distinguishes d_slot == 0 (Mon 00:00) from None, attaches AFTER_PREREQ and structured reasons.
    """

    solver_name = "GREEDY_WSPT_SMITH_RULE"

    @staticmethod
    def _wspt_sort_key(
        idx: int, task: Task, _now_slot: int, week_start_iso: str
    ) -> Tuple[float, int, int]:
        ratio = float(task.priority) / float(max(MINUTES_PER_SLOT, task.get_planned_duration_min()))
        raw_d = task.resolve_deadline_slot(week_start_iso=week_start_iso)
        d_slot = raw_d if raw_d is not None else 999999
        return (-ratio, d_slot, idx)

    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        return self.run_ranked_greedy_pipeline(
            profile=profile,
            tasks=tasks,
            pinned_blocks=pinned_blocks,
            sort_key_fn=self._wspt_sort_key,
            primary_code="EARLIEST_FREE_GAP",
            reason_builder_fn=lambda task, rank, total: (
                f"[WSPT Smith's Rule] Xếp thứ {rank}/{total} "
                f"(Tỷ số Priority/Duration = {round(float(task.priority) / float(max(15, task.get_planned_duration_min())), 4)})."
            ),
        )
