"""
Algorithm 2 (V1 Upgraded): Energy-Blind Weighted Shortest Processing Time (WSPT / Smith's Rule).

Strictly Energy-Blind (Q10 invariant: never reads circadian energy_profile so
MORNING == EVENING bit-for-bit). Upgrades:
  - Strict two-tier priority: deadline-bearing tasks ordered in topological order by
    Smith ratio `(priority + 1) / duration_slots`, strictly ahead of non-deadline habits.
  - Energy-Blind Ergonomic State: respects daily L3/total caps, L2 streaks, recovery gaps,
    post-class buffers, meal boundaries, +25% shock survival, SJL, and TStd.
  - Pass B Feasibility-First Rescue + Overload Priority Knapsack to maximize deadline
    priority coverage (`P1.1`) without touching energy profiles.
"""

import time
from typing import List, Optional, Tuple

from smartschedule.core.grid_manager import TimeGridManager
from smartschedule.core.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task, TaskChunk
from smartschedule.core.solvers.base_solver import BaseScheduler
from smartschedule.core.solvers.ergonomic_engine import (
    ScheduleState,
    build_constructive_solution,
    build_feasibility_first_fit_state,
    evaluate_state_lex_key,
    materialize_schedule_output,
    order_key_edf_ergonomic,
    order_key_overload_knapsack,
    order_key_priority_first,
    order_key_wspt_value,
    polish_schedule_deterministic,
    prepare_solver_context,
)


class GreedyWSPTSolver(BaseScheduler):
    """Upgraded Energy-Blind Smith Rule Scheduler with Feasibility-First & Overload Rescue."""

    solver_name = "GREEDY_WSPT_SMITH_RULE"

    @staticmethod
    def should_prefer_energy_placement(profile: CommitmentsProfile, chunk: TaskChunk) -> bool:
        """Strict Q10 Energy-Blind guarantee: WSPT never adapts to circadian energy curves."""
        return False

    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        t0 = time.perf_counter()

        (
            ctx,
            locked_grid,
            pinned_units,
            accepted_pinned,
            blocked_map,
            capacity_reports,
            pin_warnings,
        ) = prepare_solver_context(
            solver=self,
            profile=profile,
            tasks=tasks,
            pinned_blocks=pinned_blocks,
            energy_aware=False,  # Strict Q10 Energy-Blind guarantee
        )

        # Primary candidate: authentic Smith Rule (use overload knapsack immediately if rho_deadline > 1.0)
        if ctx.rho_deadline > 1.0:
            best_state = build_constructive_solution(
                ctx=ctx,
                pinned_units=pinned_units,
                order_key_fn=order_key_overload_knapsack,
                strategy_mode="TIGHT_PACK",
                enable_rescue=True,
                overload_pack=True,
                time_budget_sec=0.14,
                start_ts=t0,
            )
            best_key = evaluate_state_lex_key(best_state)
            c_prio = build_constructive_solution(
                ctx=ctx,
                pinned_units=pinned_units,
                order_key_fn=order_key_priority_first,
                strategy_mode="TIGHT_PACK",
                enable_rescue=True,
                overload_pack=True,
                time_budget_sec=0.16,
                start_ts=t0,
            )
            if evaluate_state_lex_key(c_prio) < best_key:
                best_state = c_prio
                best_key = evaluate_state_lex_key(c_prio)
        else:
            best_state = build_constructive_solution(
                ctx=ctx,
                pinned_units=pinned_units,
                order_key_fn=order_key_wspt_value,
                strategy_mode="ANTI_CRAM",
                enable_rescue=True,
                overload_pack=False,
                time_budget_sec=0.14,
                start_ts=t0,
            )
            best_key = evaluate_state_lex_key(best_state)

            if best_key[0] > 0 or ctx.rho_deadline > 0.92:
                for key_fn, mode, ov_pack in (
                    (order_key_edf_ergonomic, "TIGHT_PACK", False),
                    (order_key_overload_knapsack, "TIGHT_PACK", True),
                    (order_key_priority_first, "TIGHT_PACK", True),
                ):
                    if time.perf_counter() - t0 > 0.16:
                        break
                    cand = build_constructive_solution(
                        ctx=ctx,
                        pinned_units=pinned_units,
                        order_key_fn=key_fn,
                        strategy_mode=mode,
                        enable_rescue=True,
                        overload_pack=ov_pack,
                        time_budget_sec=0.16,
                        start_ts=t0,
                    )
                    c_key = evaluate_state_lex_key(cand)
                    if c_key < best_key:
                        best_state = cand
                        best_key = c_key

        if best_key[0] > 0 and ctx.rho_deadline <= 1.05:
            ff_state = build_feasibility_first_fit_state(ctx, pinned_units)
            if evaluate_state_lex_key(ff_state) < best_key:
                best_state = ff_state

        best_state = polish_schedule_deterministic(
            best_state, max_passes=1, time_budget_sec=0.18, start_ts=t0
        )

        exec_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        return materialize_schedule_output(
            solver=self,
            ctx=ctx,
            state=best_state,
            locked_grid=locked_grid,
            profile=profile,
            tasks=tasks,
            accepted_pinned=accepted_pinned,
            blocked_map=blocked_map,
            capacity_reports=capacity_reports,
            pin_warnings=pin_warnings,
            exec_ms=exec_ms,
            algo_tag="GREEDY_WSPT",
        )
