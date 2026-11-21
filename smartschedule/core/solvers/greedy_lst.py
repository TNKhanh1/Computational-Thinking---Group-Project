"""
Algorithm 3 (V1 Upgraded): Energy-Blind Dynamic Least Slack Time (LST).

Strictly Energy-Blind (Q10 invariant: never reads circadian energy_profile so
MORNING == EVENING bit-for-bit). Upgrades over baseline LST:
  - Uses forward `eff_earliest = max(now_slot, start_after, pred_end)` and backward
    DAG-propagated `eff_deadline` when measuring true dynamic slack at every step.
  - Energy-Blind Ergonomic Early-Best-Fit respecting daily caps, recovery, L2 streaks,
    post-class buffers, meal boundaries, +25% shock survival, SJL, and TStd.
  - Priority-weighted overload knapsack rescue (`P1.1`) when `rho_deadline > 0.92` or
    deadlines collide under overload.
"""

import time
from typing import List, Optional, Set, Tuple

from smartschedule.core.grid_manager import TimeGridManager
from smartschedule.core.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task, TaskChunk
from smartschedule.core.solvers.base_solver import BaseScheduler
from smartschedule.core.solvers.ergonomic_engine import (
    ErgonomicContext,
    ScheduleState,
    _find_best_chunks_assignment,
    _kempe_eject_rescue,
    _rescue_unplaced_deadlines,
    build_constructive_solution,
    build_feasibility_first_fit_state,
    evaluate_state_lex_key,
    materialize_schedule_output,
    order_key_dag_slack_urgency,
    order_key_overload_knapsack,
    polish_schedule_deterministic,
    prepare_solver_context,
)


def _dynamic_lst_construct(
    ctx: ErgonomicContext,
    pinned_units: List,
    deadline_ts: Optional[float] = None,
) -> ScheduleState:
    """True stepwise Dynamic Least-Slack construction in Energy-Blind Ergonomic State."""
    state = ScheduleState(ctx, pinned_units=pinned_units)
    dl_ids = [tid for tid in ctx.topo_order if ctx.task_is_deadline[tid]]
    habit_ids = [tid for tid in ctx.topo_order if not ctx.task_is_deadline[tid]]

    pending: Set[str] = {tid for tid in dl_ids if not state.is_task_fully_placed(tid)}
    unplaced_dl: List[str] = []

    while pending:
        ready = [
            tid
            for tid in sorted(pending)
            if all(state.is_task_fully_placed(p) for p in ctx.preds_map[tid])
        ]
        if not ready:
            break

        def _slack_key(tid: str) -> Tuple[int, int, int, int, str]:
            est = ctx.raw_earliest[tid]
            for p in ctx.preds_map[tid]:
                pe = state.task_max_end_slot(p)
                if pe is not None and pe > est:
                    est = pe
            eff_dl = ctx.eff_deadline[tid]
            need = ctx.task_planned_slots[tid]
            dyn_slack = (eff_dl - est - need) if eff_dl is not None else 999999
            return (
                dyn_slack,
                -ctx.tasks_by_id[tid].priority,
                eff_dl if eff_dl is not None else 999999,
                -ctx.descendant_count[tid],
                tid,
            )

        best_tid = min(ready, key=_slack_key)
        pending.remove(best_tid)
        t = ctx.tasks_by_id[best_tid]
        opts = ctx.split_options_by_task[best_tid]
        assigned = _find_best_chunks_assignment(
            state, t, opts[:1], strategy_mode="ANTI_CRAM", strict_crit_zero=True
        )
        if assigned is not None:
            for u in assigned:
                state.add_unit(u)
        else:
            unplaced_dl.append(best_tid)

    if unplaced_dl and (deadline_ts is None or time.perf_counter() < deadline_ts):
        unplaced_dl = _rescue_unplaced_deadlines(state, unplaced_dl, strategy_mode="ANTI_CRAM")
    if unplaced_dl and (deadline_ts is None or time.perf_counter() < deadline_ts):
        still_unplaced: List[str] = []
        for tid in unplaced_dl:
            if deadline_ts is not None and time.perf_counter() >= deadline_ts:
                still_unplaced.append(tid)
                continue
            t = ctx.tasks_by_id[tid]
            assigned = _find_best_chunks_assignment(
                state, t, ctx.split_options_by_task[tid][:2], strategy_mode="TIGHT_PACK", strict_crit_zero=False
            )
            if assigned is not None:
                for u in assigned:
                    state.add_unit(u)
            else:
                still_unplaced.append(tid)
        unplaced_dl = still_unplaced
    if unplaced_dl and ctx.rho_deadline <= 1.0 and len(ctx.tasks_by_id) <= 28 and (deadline_ts is None or time.perf_counter() < deadline_ts):
        _kempe_eject_rescue(state, unplaced_dl)

    for tid in habit_ids:
        if state.is_task_fully_placed(tid):
            continue
        t = ctx.tasks_by_id[tid]
        assigned = _find_best_chunks_assignment(
            state, t, ctx.split_options_by_task[tid][:1], strategy_mode="ERGONOMIC", strict_crit_zero=True
        )
        if assigned is None and (deadline_ts is None or time.perf_counter() < deadline_ts):
            assigned = _find_best_chunks_assignment(
                state, t, ctx.split_options_by_task[tid][:1], strategy_mode="ERGONOMIC", strict_crit_zero=False
            )
        if assigned is not None:
            cand = state.clone()
            for u in assigned:
                cand.add_unit(u)
            if evaluate_state_lex_key(cand)[:4] <= evaluate_state_lex_key(state)[:4] or ctx.rho_total <= 0.85:
                state = cand

    return state


class GreedyLSTSolver(BaseScheduler):
    """Upgraded Energy-Blind Dynamic Least-Slack Scheduler."""

    solver_name = "GREEDY_LST_BEST_FIT"

    @staticmethod
    def should_prefer_energy_placement(profile: CommitmentsProfile, chunk: TaskChunk) -> bool:
        """Strict Q10 Energy-Blind guarantee: LST never adapts to circadian energy curves."""
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

        if ctx.rho_deadline > 1.0:
            best_state = build_constructive_solution(
                ctx=ctx,
                pinned_units=pinned_units,
                order_key_fn=order_key_overload_knapsack,
                strategy_mode="TIGHT_PACK",
                enable_rescue=True,
                overload_pack=True,
                time_budget_sec=0.15,
                start_ts=t0,
            )
            best_key = evaluate_state_lex_key(best_state)
        else:
            best_state = _dynamic_lst_construct(ctx, pinned_units, deadline_ts=t0 + 0.16)
            best_key = evaluate_state_lex_key(best_state)

            if best_key[0] > 0 or ctx.rho_deadline > 0.92:
                for key_fn, mode, ov_pack in (
                    (order_key_dag_slack_urgency, "TIGHT_PACK", False),
                    (order_key_overload_knapsack, "TIGHT_PACK", True),
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
            algo_tag="GREEDY_LST",
        )
