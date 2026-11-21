"""
Solution 3A: Classical Greedy Earliest Deadline First (EDF) + First-Fit Placement.
Default V0 Baseline Engine as specified in Proposal §9.3 and baseline_plan.md §3.3.3A & §3.5.1.
"""

from typing import List, Optional, Tuple

from smartschedule.core.grid_manager import TimeGridManager
from smartschedule.core.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task
from smartschedule.core.solvers.base_solver import BaseScheduler


class GreedyEDFSolver(BaseScheduler):
    """
    Earliest Deadline First (EDF) Solver:
      1. Sort tasks by (has_no_deadline, deadline_slot ASC, -priority DESC, original_order ASC).
      2. Enforce DAG dependency topology & isolate cycles / missing prerequisites (A7) & past-due (A12).
      3. Run shared two-tier greedy pipeline (dead-zone REST, 15m breaks, Circadian/Batching when requested).
    """

    solver_name = "GREEDY_EDF_FIRST_FIT"

    @staticmethod
    def _edf_sort_key(
        idx: int, task: Task, _now_slot: int, week_start_iso: str
    ) -> Tuple[int, int, int, int]:
        d_slot = task.resolve_deadline_slot(week_start_iso=week_start_iso)
        if d_slot is None:
            return (1, 999999, -task.priority, idx)
        return (0, d_slot, -task.priority, idx)

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
            sort_key_fn=self._edf_sort_key,
            primary_code="EARLIEST_FREE_GAP",
            reason_builder_fn=lambda task, rank, total: (
                f"[EDF + First-Fit] Xếp thứ {rank}/{total} "
                f"(Ưu tiên {task.priority}, Hạn: {task.format_deadline_label(profile.planning_week_start)})."
            ),
        )
