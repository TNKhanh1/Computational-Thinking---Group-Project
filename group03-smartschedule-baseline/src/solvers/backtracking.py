"""
Solution 2: Backtracking with Branch-and-Bound Pruning (Ground-Truth / Quality Optimizer).
Fixes applied:
  - A4: Unified pinned_blocks validation, non-double-counting capacity, chunk ordering bounds.
  - A5: Multi-point interval sampling (start, peak-energy transition, midpoint, right-edge) up to 12 candidates/task
        and objective optimization across placements within bounded node/time budget (< 2s).
  - A7/A12/A8: Isolated cycle/missing-prereq/past-due tasks; dynamic 1w/2w grid horizon.
  - Pattern 2/3/4/5 + Tier 1 Sprint fallback ('Cut breaks').
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    BACKTRACK_MAX_CANDIDATES_PER_TASK,
    BACKTRACK_MAX_NODES,
    MANDATORY_REST_SLOTS,
    MIN_DEEP_WORK_BREAK_TRIGGER_MIN,
)
from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task, TaskChunk
from src.solvers.base_solver import BaseScheduler
from src.utils import MINUTES_PER_SLOT


class BacktrackingSolver(BaseScheduler):
    """Branch-and-Bound Backtracking Solver with Circadian & Context-Batching Multi-Criteria Pruning."""

    solver_name = "BACKTRACKING_BRANCH_AND_BOUND"

    def __init__(self, chunk_strategy: str = "UNIFORM", max_nodes: int = BACKTRACK_MAX_NODES):
        super().__init__(chunk_strategy=chunk_strategy)
        self.max_nodes = max_nodes
        self.nodes_explored = 0

    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        t0 = time.perf_counter()
        self.nodes_explored = 0
        week_start_iso = profile.planning_week_start
        now_slot = self.resolve_now_slot(profile)
        horizon_slots = self.resolve_horizon_slots(tasks, week_start_iso=week_start_iso)

        base_grid = TimeGridManager(total_slots=horizon_slots)
        base_grid.initialize_from_profile(profile)

        accepted_pinned, pinned_slots_by_task, pinned_chunk_map, base_warnings = (
            self.prepare_pinned_blocks(base_grid, tasks, pinned_blocks, now_slot, week_start_iso)
        )
        past_due_map = self.detect_past_due_tasks(tasks, week_start_iso=week_start_iso)

        active_capacity_tasks = [t for t in tasks if t.task_id not in past_due_map]
        capacity_reports = self.check_deadline_capacity(
            base_grid,
            active_capacity_tasks,
            now_slot=now_slot,
            week_start_iso=week_start_iso,
            pinned_slots_by_task=pinned_slots_by_task,
        )

        indexed_tasks = list(enumerate(tasks))
        orig_order_map = {t.task_id: i for i, t in indexed_tasks}

        def mrv_sort_key(item: Tuple[int, Task]) -> Tuple[int, int, int, int, int]:
            idx, t = item
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if d_slot is None:
                return (1, 999999, -t.priority, -t.get_planned_slots(), idx)
            return (0, d_slot, -t.priority, -t.get_planned_slots(), idx)

        sorted_tasks = [t for _, t in sorted(indexed_tasks, key=mrv_sort_key)]
        ordered_valid, invalid_dep_reasons = self.partition_dependency_order(tasks, sorted_tasks)

        invalid_ids = set(invalid_dep_reasons.keys()) | set(past_due_map.keys())
        base_unplaced: List[Dict[str, Any]] = []
        for t in tasks:
            if t.task_id in invalid_dep_reasons:
                r_code = invalid_dep_reasons[t.task_id]
                msg = (
                    "Phát hiện phụ thuộc vòng lặp (Circular Dependency) — cô lập để giữ C_hard = 0."
                    if r_code == "CIRCULAR_DEPENDENCY"
                    else "Thiếu công việc tiên quyết không tồn tại trong danh sách."
                )
                base_unplaced.append({
                    "task_id": t.task_id,
                    "title": t.title,
                    "duration_min": t.get_planned_duration_min(),
                    "priority": t.priority,
                    "deadline": t.format_deadline_label(week_start_iso=week_start_iso),
                    "deadline_slot": t.resolve_deadline_slot(week_start_iso=week_start_iso),
                    "reason": msg,
                    "reason_code": r_code,
                })
            elif t.task_id in past_due_map:
                base_unplaced.append({
                    "task_id": t.task_id,
                    "title": t.title,
                    "duration_min": t.get_planned_duration_min(),
                    "priority": t.priority,
                    "deadline": t.due or t.format_deadline_label(week_start_iso=week_start_iso),
                    "deadline_slot": None,
                    "reason": "Hạn chót nằm trong quá khứ trước tuần lập lịch.",
                    "reason_code": "DEADLINE_IN_PAST",
                })

        ordered_tasks = [t for t in ordered_valid if t.task_id not in invalid_ids]
        num_tasks = len(ordered_tasks)
        task_chunks_map: Dict[str, List[TaskChunk]] = {
            t.task_id: self.split_task_into_chunks(
                t, original_order=orig_order_map.get(t.task_id, 0), week_start_iso=week_start_iso
            )
            for t in ordered_tasks
        }
        task_map: Dict[str, Task] = {t.task_id: t for t in ordered_tasks}

        # Precompute total free slots needed per task excluding already-pinned chunks
        task_needed_slots: Dict[str, int] = {}
        for t in ordered_tasks:
            task_needed_slots[t.task_id] = sum(
                c.duration_slots
                for c in task_chunks_map[t.task_id]
                if (c.task_id, c.chunk_index) not in pinned_chunk_map
            )

        suffix_priority = [0] * (num_tasks + 1)
        for i in range(num_tasks - 1, -1, -1):
            suffix_priority[i] = suffix_priority[i + 1] + ordered_tasks[i].priority

        def sample_interval_starts(
            grid: TimeGridManager,
            chunk: TaskChunk,
            iv_start: int,
            eff_len: int,
        ) -> List[int]:
            """A5: Diverse start points inside wide free gaps (left edge, energy transitions, midpoint, right edge)."""
            max_start = iv_start + eff_len - chunk.duration_slots
            if max_start < iv_start:
                return []
            pts = [iv_start]
            if max_start > iv_start:
                prev_lvl = grid.get_slot_energy_level(iv_start)
                # Sample at 1-hour (4 slots) or energy boundary transitions
                for s in range(iv_start + 1, max_start + 1):
                    lvl = grid.get_slot_energy_level(s)
                    if lvl != prev_lvl:
                        pts.append(s)
                        prev_lvl = lvl
                mid = iv_start + (max_start - iv_start) // 2
                if mid not in pts:
                    pts.append(mid)
                if max_start not in pts:
                    pts.append(max_start)

            # Rank candidate start positions by Circadian & early bias when preference/load set
            if self.should_prefer_energy_placement(profile, chunk):
                pts = sorted(
                    set(pts),
                    key=lambda s: (-self.score_candidate_slot(grid, chunk, s, profile, accepted_pinned)[0], s),
                )
            else:
                pts = list(dict.fromkeys(pts))
            return pts[:4]

        def run_search(allow_breaks: bool):
            search_grid = base_grid.clone()
            if allow_breaks:
                search_grid.mark_dead_zones_as_rest()

            # Score: (placed_count, placed_priority, round(soft_energy_score, 3), -sum_end_slots)
            best_score: Tuple[int, int, float, int] = (-1, -1, -999999.0, -999999999)
            best_placements: Dict[str, List[Tuple[TaskChunk, int, int]]] = {}

            def generate_candidates(
                g: TimeGridManager,
                chunks: List[TaskChunk],
                earliest_start: int,
            ) -> List[List[Tuple[int, int]]]:
                """Return candidate sequences of (start_slot, reserved_break_slots) for chunks."""
                results: List[List[Tuple[int, int]]] = []
                max_cand = BACKTRACK_MAX_CANDIDATES_PER_TASK

                # Precompute chunk upper bounds around any pinned later chunks (Fix A4 #3)
                d_cap = min(chunks[0].deadline_slot, g.total_slots) if chunks[0].deadline_slot is not None else g.total_slots
                max_ends = [d_cap] * len(chunks)
                for i in range(len(chunks) - 1, -1, -1):
                    slots_after = 0
                    for j in range(i + 1, len(chunks)):
                        pb = pinned_chunk_map.get((chunks[j].task_id, chunks[j].chunk_index))
                        if pb is not None:
                            max_ends[i] = min(d_cap, pb.start_slot - slots_after)
                            break
                        slots_after += chunks[j].duration_slots

                def rec(c_idx: int, cur_earliest: int, seq: List[Tuple[int, int]]) -> None:
                    if len(results) >= max_cand:
                        return
                    if c_idx == len(chunks):
                        results.append(list(seq))
                        return
                    ch = chunks[c_idx]
                    pb = pinned_chunk_map.get((ch.task_id, ch.chunk_index))
                    if pb is not None:
                        if pb.start_slot < cur_earliest or pb.end_slot > max_ends[c_idx]:
                            return
                        rec(c_idx + 1, max(cur_earliest, pb.end_slot), seq + [(pb.start_slot, 0)])
                        return

                    bound_end = max_ends[c_idx]
                    intervals = g.get_free_intervals(start_from=cur_earliest, up_to=bound_end)
                    trial_starts: List[int] = []
                    for iv_s, iv_l in intervals:
                        if iv_l >= ch.duration_slots:
                            trial_starts.extend(sample_interval_starts(g, ch, iv_s, iv_l))

                    if self.should_prefer_energy_placement(profile, ch):
                        trial_starts.sort(
                            key=lambda s: (-self.score_candidate_slot(g, ch, s, profile, accepted_pinned)[0], s)
                        )
                    else:
                        trial_starts = sorted(set(trial_starts))

                    is_deep = ch.duration_min >= MIN_DEEP_WORK_BREAK_TRIGGER_MIN or (
                        ch.cognitive_load is not None and ch.cognitive_load >= 3
                    )

                    for cand_s in trial_starts[:max_cand]:
                        if not g.can_place_chunk(cand_s, ch.duration_slots, bound_end, cur_earliest, g.total_slots):
                            continue
                        g.place_block(cand_s, ch.duration_slots, ch.task_id, ch.title)
                        end_s = cand_s + ch.duration_slots
                        rest_res = g.reserve_rest_break(end_s, MANDATORY_REST_SLOTS, task_id=ch.task_id) if (allow_breaks and is_deep) else 0
                        rec(c_idx + 1, end_s + rest_res, seq + [(cand_s, rest_res)])
                        g.remove_block(cand_s, ch.duration_slots)
                        if rest_res > 0:
                            for rs in range(end_s, min(g.total_slots, end_s + rest_res)):
                                if g.grid[rs].startswith(f"{g.STATE_REST}:BREAK:{ch.task_id}"):
                                    g.grid[rs] = g.STATE_FREE
                                    g.labels[rs] = ""
                        if len(results) >= max_cand:
                            return

                rec(0, earliest_start, [])
                return results

            def dfs(
                t_idx: int,
                g: TimeGridManager,
                cur_place: Dict[str, List[Tuple[TaskChunk, int, int]]],
                placed_cnt: int,
                placed_prio: int,
                soft_score: float,
                sum_ends: int,
                free_left: int,
            ) -> None:
                nonlocal best_score, best_placements
                self.nodes_explored += 1
                if self.nodes_explored > self.max_nodes or (time.perf_counter() - t0) > 1.75:
                    return

                if t_idx == num_tasks:
                    cur_s = (placed_cnt, placed_prio, round(soft_score, 3), -sum_ends)
                    if cur_s > best_score:
                        best_score = cur_s
                        best_placements = {k: list(v) for k, v in cur_place.items()}
                    return

                rem = num_tasks - t_idx
                if (placed_cnt + rem, placed_prio + suffix_priority[t_idx]) < (best_score[0], best_score[1]):
                    return
                if best_score[0] == num_tasks and (placed_cnt + rem) < num_tasks:
                    return

                t_obj = ordered_tasks[t_idx]
                chunks = task_chunks_map[t_obj.task_id]
                need = task_needed_slots[t_obj.task_id]

                prereq_ok = True
                earliest = now_slot
                for pid in t_obj.depends_on:
                    if pid not in cur_place:
                        prereq_ok = False
                        break
                    p_end = max(s + c.duration_slots for c, s, _ in cur_place[pid])
                    earliest = max(earliest, p_end)

                if prereq_ok and need <= free_left:
                    cands = generate_candidates(g, chunks, earliest)
                    for seq in cands:
                        pairs: List[Tuple[TaskChunk, int, int]] = []
                        cand_soft = 0.0
                        for c_obj, (s_pos, rest_res) in zip(chunks, seq):
                            if (c_obj.task_id, c_obj.chunk_index) not in pinned_chunk_map:
                                g.place_block(s_pos, c_obj.duration_slots, c_obj.task_id, c_obj.title)
                                if rest_res > 0:
                                    g.reserve_rest_break(s_pos + c_obj.duration_slots, rest_res, task_id=c_obj.task_id)
                            cand_soft += self.score_candidate_slot(g, c_obj, s_pos, profile, accepted_pinned)[0]
                            pairs.append((c_obj, s_pos, rest_res))

                        cur_place[t_obj.task_id] = pairs
                        end_sum = sum(s_p + c_o.duration_slots for c_o, s_p, _ in pairs)
                        used_rest = sum(rr for _, _, rr in pairs)

                        dfs(
                            t_idx + 1,
                            g,
                            cur_place,
                            placed_cnt + 1,
                            placed_prio + t_obj.priority,
                            soft_score + cand_soft,
                            sum_ends + end_sum,
                            free_left - need - used_rest,
                        )

                        del cur_place[t_obj.task_id]
                        for c_o, s_p, rr in pairs:
                            if (c_o.task_id, c_o.chunk_index) not in pinned_chunk_map:
                                g.remove_block(s_p, c_o.duration_slots)
                                if rr > 0:
                                    end_p = s_p + c_o.duration_slots
                                    for rs in range(end_p, min(g.total_slots, end_p + rr)):
                                        if g.grid[rs].startswith(f"{g.STATE_REST}:BREAK:{c_o.task_id}"):
                                            g.grid[rs] = g.STATE_FREE
                                            g.labels[rs] = ""

                        if self.nodes_explored > self.max_nodes or (time.perf_counter() - t0) > 1.75:
                            return

                # Skip branch allowed when we haven't exhausted optimal complete coverage
                if best_score[0] < num_tasks:
                    dfs(
                        t_idx + 1,
                        g,
                        cur_place,
                        placed_cnt,
                        placed_prio,
                        soft_score,
                        sum_ends,
                        free_left,
                    )

            init_free = search_grid.count_free_slots_in_range(start_from=now_slot, up_to=search_grid.total_slots)
            dfs(0, search_grid, {}, 0, 0, 0.0, 0, init_free)
            return best_score, best_placements

        best_score, best_placements = run_search(allow_breaks=True)
        crunch_used = 0
        tier_warnings: List[str] = []

        if best_score[0] < num_tasks:
            sp_score, sp_placements = run_search(allow_breaks=False)
            if sp_score[0] > best_score[0]:
                best_score, best_placements = sp_score, sp_placements
                crunch_used = 1
                tier_warnings.append(
                    "Tier 1 Sprint Mode (Cut breaks): Tạm bỏ nghỉ 15p để tối ưu hóa số task hoàn thành đúng hạn."
                )

        # Reconstruct final deterministic grid
        final_grid = base_grid.clone()
        if crunch_used == 0:
            final_grid.mark_dead_zones_as_rest()

        final_blocks: List[ScheduleBlock] = [pb.model_copy(deep=True) for pb in accepted_pinned]
        energy_prof = profile.get_energy_profile()
        unplaced_tasks: List[Dict[str, Any]] = list(base_unplaced)

        for rank_idx, task in enumerate(ordered_tasks, start=1):
            if task.task_id in best_placements:
                for ch, start_slot, rest_res in best_placements[task.task_id]:
                    if (ch.task_id, ch.chunk_index) in pinned_chunk_map:
                        continue
                    final_grid.place_block(start_slot, ch.duration_slots, ch.task_id, ch.title)
                    actual_rest = 0
                    if crunch_used == 0 and rest_res > 0:
                        actual_rest = final_grid.reserve_rest_break(
                            start_slot + ch.duration_slots, rest_res, task_id=ch.task_id
                        )
                    avg_energy = sum(
                        energy_prof.level_for_slot(s) for s in range(start_slot, start_slot + ch.duration_slots)
                    ) / float(max(1, ch.duration_slots))
                    r_text, r_codes = self.build_chunk_reasons(
                        task=task,
                        chunk=ch,
                        start_slot=start_slot,
                        avg_energy=avg_energy,
                        primary_code="BACKTRACKING_OPTIMAL",
                        primary_text=(
                            f"[Backtracking Branch-and-Bound] Nghiệm tối ưu ({self.nodes_explored} nút duyệt, Ưu tiên {ch.priority})."
                        ),
                        has_prereq=bool(task.depends_on),
                        rest_reserved=actual_rest,
                        profile=profile,
                        placed_blocks=final_blocks,
                        crunch_tier_used=crunch_used,
                    )
                    final_blocks.append(
                        self.build_schedule_block(
                            chunk=ch,
                            start_slot=start_slot,
                            reason_text=r_text,
                            reason_codes=r_codes,
                            week_start_iso=week_start_iso,
                        )
                    )
            else:
                # Release any orphan PINNED chunk if full task was dropped in optimal solution
                for pb in accepted_pinned:
                    if pb.task_id == task.task_id and pb.state != "DONE":
                        final_grid.remove_block(pb.start_slot, pb.end_slot - pb.start_slot)
                unplaced_tasks.append({
                    "task_id": task.task_id,
                    "title": task.title,
                    "duration_min": task.get_planned_duration_min(),
                    "priority": task.priority,
                    "deadline": task.format_deadline_label(week_start_iso=week_start_iso),
                    "deadline_slot": task.resolve_deadline_slot(week_start_iso=week_start_iso),
                    "reason": (
                        f"Branch-and-Bound ({self.nodes_explored} nút): Không thể xếp đồng thời trước hạn chót."
                    ),
                    "reason_code": "CAPACITY_SHORTAGE" if capacity_reports else "FRAGMENTATION",
                })

        exec_ms = (time.perf_counter() - t0) * 1000.0
        return self.finalize_output(
            grid_manager=final_grid,
            tasks=tasks,
            blocks=final_blocks,
            unplaced_tasks=unplaced_tasks,
            capacity_reports=capacity_reports,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
            warnings=base_warnings + tier_warnings,
            profile=profile,
            now_slot=now_slot,
            crunch_tier_used=crunch_used,
        ), final_grid
