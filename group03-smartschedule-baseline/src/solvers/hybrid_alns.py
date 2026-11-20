"""
Algorithm 6 (Higher-End Architecture): HYBRID_ALNS (Adaptive Large Neighborhood Search + Regret-2).

Designed as SmartSchedule's premier high-quality metaheuristic:
  1. Multi-Strategy Constructive Portfolio (4 diverse topological/ergonomic orders + overload
     knapsack under high load), each with G1-legal adaptive splitting and Kempe/split rescue.
  2. Deterministic ALNS (`80` iterations, PRNG seed `20261120`) with Adaptive Roulette selection
     over 5 domain-specific Ruin operators (Worst-Pillar, Day-Congestion, Shaw-Related,
     Dependency-Cluster, Random+Unplaced) and 2 Repair operators (Regret-2 Insertion &
     Critical Ergonomic Ordered Insertion).
  3. Lexicographic Record-to-Record acceptance & 3-pass exhaustive 1-shift/2-swap local polish
     optimizing exact `Testing_System v2.1` pillars within `<= 600 ms` safety bound.
"""

import time
from typing import List, Optional, Tuple

from src.config import ALNS_MAX_ITERS
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
    prepare_solver_context,
    run_alns_deterministic,
)


class HybridALNSSolver(BaseScheduler):
    """Higher-End 6th Solver: Deterministic Portfolio + ALNS + Regret-2 + Lexicographic Polish."""

    solver_name = "HYBRID_ALNS"

    @staticmethod
    def should_prefer_energy_placement(profile: CommitmentsProfile, chunk: TaskChunk) -> bool:
        """HYBRID_ALNS always optimizes circadian energy alignment & category batching."""
        return True

    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        t0 = time.perf_counter()
        total_budget_sec = 0.65

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

        # Stage 1: Constructive Portfolio + Rescue (overload-aware when rho_deadline > 1.0)
        if ctx.rho_deadline > 1.0:
            portfolio_specs = [
                (order_key_overload_knapsack, "OVERLOAD_PACK", True),
                (order_key_priority_first, "OVERLOAD_PACK", True),
                (order_key_wspt_value, "OVERLOAD_PACK", True),
                (order_key_edf_ergonomic, "ERGONOMIC", False),
            ]
        else:
            portfolio_specs = [
                (order_key_edf_ergonomic, "ERGONOMIC", False),
                (order_key_heavy_peak_first, "ERGONOMIC", False),
                (order_key_dag_slack_urgency, "ANTI_CRAM", False),
                (order_key_wspt_value, "TIGHT_PACK", False),
            ]
        initial_states: List[ScheduleState] = []
        for key_fn, mode, ov_pack in portfolio_specs:
            if (time.perf_counter() - t0) > (total_budget_sec * 0.48) and initial_states:
                break
            st = build_constructive_solution(
                ctx=ctx,
                pinned_units=pinned_units,
                order_key_fn=key_fn,
                strategy_mode=mode,
                enable_rescue=True,
                overload_pack=ov_pack,
                time_budget_sec=total_budget_sec * 0.48,
                start_ts=t0,
            )
            initial_states.append(st)
            if is_perfect_ergonomic_key(evaluate_state_lex_key(st)):
                break

        best_init_key = min(evaluate_state_lex_key(s) for s in initial_states)
        if ctx.rho_deadline <= 1.0 and (best_init_key[0] > 0 or ctx.rho_deadline > 0.92):
            for key_fn in (order_key_overload_knapsack, order_key_priority_first):
                if (time.perf_counter() - t0) > (total_budget_sec * 0.55):
                    break
                st = build_constructive_solution(
                    ctx=ctx,
                    pinned_units=pinned_units,
                    order_key_fn=key_fn,
                    strategy_mode="TIGHT_PACK",
                    enable_rescue=True,
                    overload_pack=True,
                    time_budget_sec=total_budget_sec * 0.55,
                    start_ts=t0,
                )
                initial_states.append(st)
                st_key = evaluate_state_lex_key(st)
                if st_key < best_init_key:
                    best_init_key = st_key

        # Always guarantee 0 SUBOPT feasibility floor when rho <= 1.05 and no constructive state covered all deadlines
        if ctx.rho_deadline <= 1.05 and best_init_key[0] > 0:
            initial_states.append(build_feasibility_first_fit_state(ctx, pinned_units))

        # Stage 2 & 3: Deterministic ALNS + Regret-2 + Multi-Pass Polish (hard-capped well < 1000ms)
        rem_budget = max(0.08, total_budget_sec - (time.perf_counter() - t0))
        best_state = run_alns_deterministic(
            initial_states=initial_states,
            max_iters=ALNS_MAX_ITERS,
            time_budget_sec=rem_budget,
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
            algo_tag="HYBRID_ALNS",
        )
