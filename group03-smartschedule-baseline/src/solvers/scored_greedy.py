"""
Algorithm 4 (V3 Upgraded Production Default): Circadian-Aware Ergonomic Portfolio Greedy + Polish.

Combines a fast deterministic 3-strategy constructive portfolio (`EFF_EDF_ERGONOMIC`,
`HEAVY_PEAK_FIRST`, `DAG_SLACK_URGENCY`) backed by:
  - Peak Energy reservation protecting energy==3 slots for cognitive_load==3 work
  - Daily heavy cap (<=2), daily total study+class cap (<=540m soft / <=600m hard)
  - Load >= 2 streak guard (<=120m soft / <=180m hard) & >=30m separation between L3 blocks
  - Post-class 15m recovery buffer, Meal-L2 sandwich guard, and mandatory Tier-0 rest breaks
  - Explicit +25% shock survival headroom, SJL phase alignment, and daily load TStd balancing
  - G1-legal adaptive splitting + Pass B Feasibility-First Rescue (Kempe ejection)
  - Overload Priority-Density Knapsack & 3-pass deterministic polish (`<= 250 ms` UI target)
"""

import math
import time
from typing import List, Optional, Tuple

from src.config import (
    GAMMA_URGENCY_HOURS,
    HABIT_BASE_URGENCY,
    OVERDUE_URGENCY_CAP,
)
from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task, TaskChunk
from src.solvers.base_solver import BaseScheduler
from src.solvers.ergonomic_engine import (
    ScheduleState,
    build_constructive_solution,
    build_feasibility_first_fit_state,
    evaluate_state_lex_key,
    is_perfect_ergonomic_key,
    materialize_schedule_output,
    order_key_dag_slack_urgency,
    order_key_edf_ergonomic,
    order_key_heavy_peak_first,
    order_key_overload_knapsack,
    order_key_priority_first,
    order_key_wspt_value,
    polish_schedule_deterministic,
    prepare_solver_context,
)
from src.utils import MINUTES_PER_SLOT


class ScoredGreedySolver(BaseScheduler):
    """Upgraded Circadian-Aware Ergonomic Portfolio Greedy Scheduler."""

    solver_name = "SCORED_GREEDY"

    @staticmethod
    def should_prefer_energy_placement(profile: CommitmentsProfile, chunk: TaskChunk) -> bool:
        """SCORED_GREEDY always applies Pattern 3 Circadian & Pattern 4 Category Batching."""
        return True

    @staticmethod
    def compute_task_score(
        task: Task,
        now_slot: int,
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
    ) -> Tuple[float, Optional[int]]:
        """Compute Pattern 7 Exponential Urgency * Importance priority score."""
        d_slot = task.resolve_deadline_slot(week_start_iso=week_start_iso)
        importance = float(task.priority)
        if d_slot is None:
            return round(HABIT_BASE_URGENCY * importance, 6), None

        planned_min = task.get_planned_duration_min()
        slack_min = (d_slot - now_slot) * MINUTES_PER_SLOT - planned_min
        slack_hours = slack_min / 60.0

        if slack_hours <= 0.0:
            urgency = OVERDUE_URGENCY_CAP + min(0.50, abs(slack_hours) * 0.01)
        else:
            urgency = math.exp(-slack_hours / GAMMA_URGENCY_HOURS)

        return round(urgency * importance, 6), d_slot

    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        t0 = time.perf_counter()
        budget_sec = 0.42

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
            energy_aware=True,
        )

        # Deterministic constructive portfolio (prioritize overload knapsack immediately if rho_deadline > 1.0)
        candidates: List[ScheduleState] = []
        if ctx.rho_deadline > 1.0:
            strategies = [
                (order_key_overload_knapsack, "OVERLOAD_PACK", True),
                (order_key_priority_first, "OVERLOAD_PACK", True),
                (order_key_wspt_value, "OVERLOAD_PACK", True),
                (order_key_edf_ergonomic, "ERGONOMIC", False),
            ]
        else:
            strategies = [
                (order_key_edf_ergonomic, "ERGONOMIC", False),
                (order_key_heavy_peak_first, "ERGONOMIC", False),
                (order_key_dag_slack_urgency, "ANTI_CRAM", False),
            ]
        for key_fn, mode, ov_pack in strategies:
            if time.perf_counter() - t0 > budget_sec * 0.78 and candidates:
                break
            st = build_constructive_solution(
                ctx=ctx,
                pinned_units=pinned_units,
                order_key_fn=key_fn,
                strategy_mode=mode,
                enable_rescue=True,
                overload_pack=ov_pack,
                time_budget_sec=budget_sec * 0.78,
                start_ts=t0,
            )
            candidates.append(st)
            if is_perfect_ergonomic_key(evaluate_state_lex_key(st)):
                break

        best_state = min(candidates, key=evaluate_state_lex_key)
        best_key = evaluate_state_lex_key(best_state)

        # Extra overload / tie-break check if deadlines remain unplaced on borderline feasible (rho <= 1.0)
        if ctx.rho_deadline <= 1.0 and (best_key[0] > 0 or ctx.rho_deadline > 0.92):
            for key_fn, mode, ov_pack in (
                (order_key_wspt_value, "ANTI_CRAM", False),
                (order_key_overload_knapsack, "TIGHT_PACK", True),
            ):
                if time.perf_counter() - t0 > budget_sec * 0.85:
                    break
                cand = build_constructive_solution(
                    ctx=ctx,
                    pinned_units=pinned_units,
                    order_key_fn=key_fn,
                    strategy_mode=mode,
                    enable_rescue=True,
                    overload_pack=ov_pack,
                    time_budget_sec=budget_sec * 0.85,
                    start_ts=t0,
                )
                c_key = evaluate_state_lex_key(cand)
                if c_key < best_key:
                    best_state = cand
                    best_key = c_key
        elif ctx.rho_total > 0.85 or best_key[3] > 0 or best_key[5] > 0:
            if time.perf_counter() - t0 <= budget_sec * 0.78:
                st_wspt = build_constructive_solution(
                    ctx=ctx,
                    pinned_units=pinned_units,
                    order_key_fn=order_key_wspt_value,
                    strategy_mode="ANTI_CRAM",
                    enable_rescue=True,
                    overload_pack=False,
                    time_budget_sec=budget_sec * 0.78,
                    start_ts=t0,
                )
                if evaluate_state_lex_key(st_wspt) < best_key:
                    best_state = st_wspt
                    best_key = evaluate_state_lex_key(best_state)

        # Ultra-fast EDF Feasibility Floor whenever any deadline remains unplaced on feasible rho
        if best_key[0] > 0 and ctx.rho_deadline <= 1.05:
            ff_state = build_feasibility_first_fit_state(ctx, pinned_units)
            ff_key = evaluate_state_lex_key(ff_state)
            if ff_key < best_key:
                best_state = ff_state
                best_key = ff_key

        best_state = polish_schedule_deterministic(
            best_state,
            max_passes=3,
            time_budget_sec=budget_sec,
            start_ts=t0,
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
            algo_tag="SCORED_GREEDY",
        )
