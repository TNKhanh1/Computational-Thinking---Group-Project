"""
Algorithm 5 (V3 Upgraded): Live-State Ergonomic Branch-and-Bound Backtracking Solver.

Fixes baseline DFS blindness (which only checked against pinned blocks and produced 96+
daily-cap critical violations) by:
  1. Warm-starting an exact feasible ergonomic incumbent (Portfolio + Overload Knapsack).
  2. Exploring DFS branches directly over live `ScheduleState` (full incremental tracking
     of daily L3/total caps, L2 streaks, post-class buffers, meal boundaries, Peak energy,
     and +25% shock headroom).
  3. Pruning dominated branches cleanly under deterministic `BACKTRACK_MAX_NODES` +
     `0.45s` safety cap, followed by deterministic polish.
"""

import time
from typing import List, Optional, Tuple

from smartschedule.core.config import BACKTRACK_MAX_CANDIDATES_PER_TASK, BACKTRACK_MAX_NODES
from smartschedule.core.grid_manager import TimeGridManager
from smartschedule.core.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task, TaskChunk
from smartschedule.core.solvers.base_solver import BaseScheduler
from smartschedule.core.solvers.ergonomic_engine import (
    ScheduleState,
    UnitPlacement,
    _task_temporal_window,
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
    score_candidate_unit,
)
from smartschedule.core.utils import SLOTS_PER_DAY


def _top_k_single_candidates(
    state: ScheduleState,
    task: Task,
    chunk: TaskChunk,
    earliest: int,
    latest: int,
    max_cands: int,
) -> List[Tuple[Tuple[int, float], UnitPlacement]]:
    """Collect diverse best-scoring slot candidates across distinct days/times."""
    ctx = state.ctx
    tid = task.task_id
    dur = chunk.duration_slots
    ld = ctx.task_load[tid]
    max_st = latest - dur
    if earliest > max_st:
        return []

    scored: List[Tuple[Tuple[int, float], int]] = []
    for s in range(earliest, max_st + 1):
        if not ctx.is_free_base[s] or state.slot_owner[s]:
            continue
        if not state.is_span_available(s, s + dur):
            continue
        flags, cost = score_candidate_unit(state, task, chunk, s, strategy_mode="ERGONOMIC")
        scored.append(((flags, cost), s))

    scored.sort(key=lambda x: (x[0], x[1]))
    chosen: List[Tuple[Tuple[int, float], UnitPlacement]] = []
    seen_buckets: set = set()
    for sc, s in scored:
        bucket = (s // SLOTS_PER_DAY, (s % SLOTS_PER_DAY) // 16)
        if bucket not in seen_buckets:
            seen_buckets.add(bucket)
            chosen.append(
                (
                    sc,
                    UnitPlacement(
                        task_id=tid,
                        chunk_index=chunk.chunk_index,
                        total_chunks=chunk.total_chunks,
                        start_slot=s,
                        end_slot=s + dur,
                        duration_slots=dur,
                        cognitive_load=ld,
                        priority=task.priority,
                        category=task.category,
                        preferred_window=task.preferred_window,
                        deadline_slot=ctx.raw_deadline[tid],
                    ),
                )
            )
            if len(chosen) >= max_cands:
                break
    return chosen


class BacktrackingSolver(BaseScheduler):
    """Upgraded Live-State Ergonomic Branch-and-Bound Solver."""

    solver_name = "BACKTRACKING_BRANCH_AND_BOUND"

    @staticmethod
    def should_prefer_energy_placement(profile: CommitmentsProfile, chunk: TaskChunk) -> bool:
        """Backtracking Branch-and-Bound always optimizes circadian peak placement."""
        return True

    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        t0 = time.perf_counter()
        budget_sec = 0.52

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

        # Warm-start strong feasible incumbent immediately (keep N>25 fast <= 450ms)
        if ctx.rho_deadline > 1.0:
            seeds = [
                build_constructive_solution(
                    ctx, pinned_units, order_key_overload_knapsack, "OVERLOAD_PACK",
                    enable_rescue=True, overload_pack=True, time_budget_sec=budget_sec * 0.45, start_ts=t0
                ),
            ]
            if (time.perf_counter() - t0) < budget_sec * 0.45:
                seeds.append(
                    build_constructive_solution(
                        ctx, pinned_units, order_key_priority_first, "OVERLOAD_PACK",
                        enable_rescue=True, overload_pack=True, time_budget_sec=budget_sec * 0.45, start_ts=t0
                    )
                )
            if len(ctx.tasks_by_id) <= 25 and (time.perf_counter() - t0) < budget_sec * 0.45:
                seeds.append(
                    build_constructive_solution(
                        ctx, pinned_units, order_key_wspt_value, "OVERLOAD_PACK",
                        enable_rescue=True, overload_pack=True, time_budget_sec=budget_sec * 0.45, start_ts=t0
                    )
                )
        elif len(ctx.tasks_by_id) > 25:
            seeds = [
                build_constructive_solution(
                    ctx, pinned_units, order_key_edf_ergonomic, "ERGONOMIC",
                    enable_rescue=True, time_budget_sec=budget_sec * 0.55, start_ts=t0
                )
            ]
        else:
            s0 = build_constructive_solution(
                ctx, pinned_units, order_key_edf_ergonomic, "ERGONOMIC",
                enable_rescue=True, time_budget_sec=budget_sec * 0.55, start_ts=t0
            )
            seeds = [s0]
            if not is_perfect_ergonomic_key(evaluate_state_lex_key(s0)):
                seeds.append(
                    build_constructive_solution(
                        ctx, pinned_units, order_key_dag_slack_urgency, "ANTI_CRAM",
                        enable_rescue=True, time_budget_sec=budget_sec * 0.55, start_ts=t0
                    )
                )
                if (time.perf_counter() - t0) < budget_sec * 0.45:
                    seeds.append(
                        build_constructive_solution(
                            ctx, pinned_units, order_key_heavy_peak_first, "ERGONOMIC",
                            enable_rescue=True, time_budget_sec=budget_sec * 0.55, start_ts=t0
                        )
                    )
        best_state = min(seeds, key=evaluate_state_lex_key).clone()
        best_key = evaluate_state_lex_key(best_state)

        if ctx.rho_deadline <= 1.0 and (best_key[0] > 0 or ctx.rho_deadline > 0.92) and (time.perf_counter() - t0) < budget_sec * 0.55:
            ov_seed = build_constructive_solution(
                ctx,
                pinned_units,
                order_key_overload_knapsack,
                "TIGHT_PACK",
                enable_rescue=True,
                overload_pack=True,
                time_budget_sec=budget_sec * 0.55,
                start_ts=t0,
            )
            ov_key = evaluate_state_lex_key(ov_seed)
            if ov_key < best_key:
                best_state = ov_seed.clone()
                best_key = ov_key

        if best_key[0] > 0 and ctx.rho_deadline <= 1.05:
            ff_state = build_feasibility_first_fit_state(ctx, pinned_units)
            ff_key = evaluate_state_lex_key(ff_state)
            if ff_key < best_key:
                best_state = ff_state
                best_key = ff_key

        # Collect non-pinned single-chunk tasks to refine via bounded live-state DFS
        search_tids = [
            tid
            for tid in ctx.topo_order
            if tid not in ctx.pinned_chunk_indices_by_task
            and len(ctx.default_chunks_by_task[tid]) == 1
        ]

        # Run Live-State Branch-and-Bound only on tractable 7-day subproblems (SLA safety)
        if 1 <= len(search_tids) <= 16 and ctx.horizon_slots <= 700 and not (
            best_key[0] == 0 and best_key[3] == 0 and best_key[5] == 0 and best_key[7] <= -99.9 and best_key[13] <= -99.9
        ):
            base_state = ScheduleState(ctx, pinned_units=pinned_units)
            search_set = set(search_tids)
            for tid, units in best_state.units_by_task.items():
                if tid not in search_set:
                    for u in units:
                        if not u.is_pinned:
                            base_state.add_unit(u)

            rem = list(search_tids)
            final_vars: List[str] = []
            placed_v: set = set(ctx.tasks_by_id.keys()) - search_set
            while rem:
                avail_v = [tid for tid in rem if all(p in placed_v for p in ctx.preds_map[tid])]
                if not avail_v:
                    final_vars.extend(rem)
                    break
                nxt = min(
                    avail_v,
                    key=lambda tid: (
                        0 if ctx.task_is_deadline[tid] else 1,
                        ctx.eff_deadline[tid] if ctx.eff_deadline[tid] is not None else 999999,
                        -ctx.task_load[tid],
                        -ctx.tasks_by_id[tid].priority,
                        tid,
                    ),
                )
                final_vars.append(nxt)
                placed_v.add(nxt)
                rem.remove(nxt)

            nodes = 0
            n_vars = len(final_vars)
            max_branch = min(5, max(2, BACKTRACK_MAX_CANDIDATES_PER_TASK // 3))

            def _dfs(idx: int, cur_state: ScheduleState, skipped_dl_count: int, skipped_dl_prio: int) -> None:
                nonlocal nodes, best_state, best_key
                nodes += 1
                if nodes >= BACKTRACK_MAX_NODES or (time.perf_counter() - t0) > budget_sec * 0.80:
                    return
                if best_key[0] == 0 and skipped_dl_count > 0:
                    return
                if skipped_dl_prio > best_key[2]:
                    return

                if idx >= n_vars:
                    cand_key = evaluate_state_lex_key(cur_state)
                    if cand_key < best_key:
                        best_state = cur_state.clone()
                        best_key = cand_key
                    return

                tid = final_vars[idx]
                t = ctx.tasks_by_id[tid]
                if any(not cur_state.is_task_fully_placed(p) for p in ctx.preds_map[tid]):
                    add_c = 1 if ctx.task_is_deadline[tid] else 0
                    add_p = t.priority if ctx.task_is_deadline[tid] else 0
                    _dfs(idx + 1, cur_state, skipped_dl_count + add_c, skipped_dl_prio + add_p)
                    return

                earliest, latest = _task_temporal_window(cur_state, tid)
                ch = ctx.default_chunks_by_task[tid][0]
                cands = _top_k_single_candidates(cur_state, t, ch, earliest, latest, max_cands=max_branch)

                explored = 0
                for (flags, _cost), unit in cands:
                    if best_key[0] == 0 and best_key[3] == 0 and flags >= 35:
                        continue
                    cur_state.add_unit(unit)
                    _dfs(idx + 1, cur_state, skipped_dl_count, skipped_dl_prio)
                    cur_state.remove_task(tid)
                    explored += 1
                    if nodes >= BACKTRACK_MAX_NODES or (time.perf_counter() - t0) > budget_sec * 0.80:
                        return

                if explored == 0 or not ctx.task_is_deadline[tid] or best_key[0] > 0:
                    add_c = 1 if ctx.task_is_deadline[tid] else 0
                    add_p = t.priority if ctx.task_is_deadline[tid] else 0
                    if (best_key[0] > 0 or add_c == 0) and (skipped_dl_prio + add_p <= best_key[2] or not ctx.task_is_deadline[tid]):
                        _dfs(idx + 1, cur_state, skipped_dl_count + add_c, skipped_dl_prio + add_p)

            _dfs(0, base_state, 0, 0)

        best_state = polish_schedule_deterministic(
            best_state,
            max_passes=2,
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
            algo_tag="BACKTRACKING_B_AND_B",
        )
