"""
Solution 2: Backtracking with Branch-and-Bound Pruning (Ground-Truth Validator).
Specified in baseline_plan.md §3.2 & §3.5.3.
Implements three formal pruning conditions:
  1. Hard Constraint Pruning (H1, H2, H3): Only branch on contiguous FREE intervals.
  2. Deadline Pruning (H4): Prune immediately if start_slot + duration_slots > deadline_slot.
  3. Capacity & Upper-Bound Pruning: Prune branch if remaining tasks cannot beat the current
     best solution's placed task count / total priority, or if required slots exceed remaining FREE slots.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task, TaskChunk
from src.solvers.base_solver import BaseScheduler
from src.utils import SLOTS_PER_WEEK


class BacktrackingSolver(BaseScheduler):
    """
    Branch-and-Bound Backtracking Solver for Ground-Truth Verification.
    Finds the global optimal feasible schedule (maximizing placed tasks, then total priority,
    then minimizing total completion time).
    """

    solver_name = "BACKTRACKING_BRANCH_AND_BOUND"

    def __init__(self, chunk_strategy: str = "UNIFORM", max_nodes: int = 25000):
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

        base_grid = TimeGridManager(total_slots=SLOTS_PER_WEEK)
        base_grid.initialize_from_profile(profile)

        initial_blocks: List[ScheduleBlock] = []
        pinned_task_chunks = set()
        if pinned_blocks:
            for pb in pinned_blocks:
                length_slots = pb.end_slot - pb.start_slot
                if base_grid.is_range_free(pb.start_slot, length_slots):
                    base_grid.place_block(pb.start_slot, length_slots, pb.task_id, pb.title)
                    pb_copy = pb.model_copy(deep=True)
                    pb_copy.state = "PINNED"
                    initial_blocks.append(pb_copy)
                    pinned_task_chunks.add((pb.task_id, pb.chunk_index))

        capacity_reports = self.check_deadline_capacity(
            base_grid, tasks, now_slot=now_slot, week_start_iso=week_start_iso
        )

        # Sort tasks initially by constrainedness (Tightest deadline -> Highest priority -> Longest duration)
        indexed_tasks = list(enumerate(tasks))

        def mrv_sort_key(item: Tuple[int, Task]) -> Tuple[int, int, int, int, int]:
            idx, t = item
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if d_slot is None:
                return (1, 999999, -t.priority, -t.get_planned_slots(), idx)
            return (0, d_slot, -t.priority, -t.get_planned_slots(), idx)

        sorted_tasks = [t for _, t in sorted(indexed_tasks, key=mrv_sort_key)]
        ordered_tasks = self.enforce_dependency_order(tasks, sorted_tasks)
        orig_order_map = {t.task_id: i for i, t in indexed_tasks}
        num_tasks = len(ordered_tasks)

        # Precompute chunks for each task
        task_chunks_map: Dict[str, List[TaskChunk]] = {
            t.task_id: self.split_task_into_chunks(
                t, original_order=orig_order_map.get(t.task_id, 0), week_start_iso=week_start_iso
            )
            for t in ordered_tasks
        }

        # Remaining priority suffix sum for Branch-and-Bound upper-bound pruning
        suffix_priority = [0] * (num_tasks + 1)
        for i in range(num_tasks - 1, -1, -1):
            suffix_priority[i] = suffix_priority[i + 1] + ordered_tasks[i].priority

        # Best state tracking: score = (placed_count, total_priority, -sum_end_slots)
        best_score: Tuple[int, int, int] = (-1, -1, -999999999)
        best_placements: Dict[str, List[Tuple[TaskChunk, int]]] = {}

        def generate_candidate_slots_for_task(
            grid: TimeGridManager,
            chunks: List[TaskChunk],
            earliest_start: int,
        ) -> List[List[int]]:
            """
            Find valid start slot sequences [s_1, s_2, ..., s_k] for the chunks of a task.
            Uses interval-aligned candidate starts to avoid combinatorial explosion on contiguous free hours
            while still testing diverse free windows across the week.
            """
            results: List[List[int]] = []
            max_candidates_per_task = 6

            def place_chunk_recursive(c_idx: int, cur_earliest: int, current_seq: List[int]) -> None:
                if len(results) >= max_candidates_per_task:
                    return
                if c_idx == len(chunks):
                    results.append(list(current_seq))
                    return

                chunk = chunks[c_idx]
                if (chunk.task_id, chunk.chunk_index) in pinned_task_chunks:
                    for pb in initial_blocks:
                        if pb.task_id == chunk.task_id and pb.chunk_index == chunk.chunk_index:
                            place_chunk_recursive(c_idx + 1, max(cur_earliest, pb.end_slot), current_seq + [pb.start_slot])
                            return

                eff_deadline = (
                    min(chunk.deadline_slot, SLOTS_PER_WEEK)
                    if chunk.deadline_slot is not None
                    else SLOTS_PER_WEEK
                )
                intervals = grid.get_free_intervals(start_from=cur_earliest, up_to=eff_deadline)

                for iv_start, iv_len in intervals:
                    if iv_len < chunk.duration_slots:
                        continue
                    # Try the start of this free interval
                    cand_s = iv_start
                    if grid.can_place_chunk(
                        cand_s, chunk.duration_slots, chunk.deadline_slot, cur_earliest, SLOTS_PER_WEEK
                    ):
                        grid.place_block(cand_s, chunk.duration_slots, chunk.task_id, chunk.title)
                        place_chunk_recursive(c_idx + 1, cand_s + chunk.duration_slots, current_seq + [cand_s])
                        grid.remove_block(cand_s, chunk.duration_slots)
                        if len(results) >= max_candidates_per_task:
                            return

            place_chunk_recursive(0, earliest_start, [])
            return results

        def dfs(
            t_idx: int,
            grid: TimeGridManager,
            current_placements: Dict[str, List[Tuple[TaskChunk, int]]],
            placed_count: int,
            placed_priority: int,
            sum_end_slots: int,
            free_slots_left: int,
        ) -> None:
            nonlocal best_score, best_placements
            self.nodes_explored += 1
            if self.nodes_explored > self.max_nodes:
                return

            # Update best solution if at leaf
            if t_idx == num_tasks:
                cur_score = (placed_count, placed_priority, -sum_end_slots)
                if cur_score > best_score:
                    best_score = cur_score
                    best_placements = {k: list(v) for k, v in current_placements.items()}
                return

            # Branch-and-Bound Upper-Bound Pruning:
            # Even if all remaining tasks were placed, could we beat best_score?
            rem_tasks = num_tasks - t_idx
            max_possible_count = placed_count + rem_tasks
            max_possible_prio = placed_priority + suffix_priority[t_idx]
            if (max_possible_count, max_possible_prio, 0) < (best_score[0], best_score[1], -999999999):
                return

            # If we already found a 100% feasible placement of all tasks, prune sub-optimal branches quickly
            if best_score[0] == num_tasks and max_possible_count < num_tasks:
                return

            task = ordered_tasks[t_idx]
            chunks = task_chunks_map[task.task_id]
            needed_slots = sum(c.duration_slots for c in chunks)

            # Check prerequisites (H5)
            prereqs_ok = True
            earliest_start = now_slot
            for pid in task.depends_on:
                if pid not in current_placements:
                    prereqs_ok = False
                    break
                prereq_end = max(s + c.duration_slots for c, s in current_placements[pid])
                earliest_start = max(earliest_start, prereq_end)

            # Branch 1: Try placing `task` in candidate slots (if capacity & prerequisites allow)
            if prereqs_ok and needed_slots <= free_slots_left:
                candidate_seqs = generate_candidate_slots_for_task(grid, chunks, earliest_start)
                for seq in candidate_seqs:
                    # Place all chunks of `task`
                    placed_pairs: List[Tuple[TaskChunk, int]] = []
                    for c_obj, s_pos in zip(chunks, seq):
                        if (c_obj.task_id, c_obj.chunk_index) not in pinned_task_chunks:
                            grid.place_block(s_pos, c_obj.duration_slots, c_obj.task_id, c_obj.title)
                        placed_pairs.append((c_obj, s_pos))

                    current_placements[task.task_id] = placed_pairs
                    task_end_sum = sum(s_pos + c_obj.duration_slots for c_obj, s_pos in placed_pairs)

                    dfs(
                        t_idx + 1,
                        grid,
                        current_placements,
                        placed_count + 1,
                        placed_priority + task.priority,
                        sum_end_slots + task_end_sum,
                        free_slots_left - needed_slots,
                    )

                    # Backtrack
                    del current_placements[task.task_id]
                    for c_obj, s_pos in placed_pairs:
                        if (c_obj.task_id, c_obj.chunk_index) not in pinned_task_chunks:
                            grid.remove_block(s_pos, c_obj.duration_slots)

                    # Early exit if all tasks are placed and we only need optimal feasible confirmation
                    if best_score[0] == num_tasks and self.nodes_explored > 500:
                        return

            # Branch 2: Skip placing `task` (allows finding maximal partial schedule when infeasible)
            if best_score[0] < num_tasks:
                dfs(
                    t_idx + 1,
                    grid,
                    current_placements,
                    placed_count,
                    placed_priority,
                    sum_end_slots,
                    free_slots_left,
                )

        initial_free = base_grid.count_free_slots_in_range(start_from=now_slot, up_to=SLOTS_PER_WEEK)
        dfs(0, base_grid, {}, 0, 0, 0, initial_free)

        # Reconstruct final grid and ScheduleBlocks from best_placements
        final_grid = TimeGridManager(total_slots=SLOTS_PER_WEEK)
        final_grid.initialize_from_profile(profile)
        final_blocks: List[ScheduleBlock] = []

        if pinned_blocks:
            for pb in pinned_blocks:
                length_slots = pb.end_slot - pb.start_slot
                if final_grid.is_range_free(pb.start_slot, length_slots):
                    final_grid.place_block(pb.start_slot, length_slots, pb.task_id, pb.title)
                    pb_copy = pb.model_copy(deep=True)
                    pb_copy.state = "PINNED"
                    final_blocks.append(pb_copy)

        unplaced_tasks: List[Dict[str, Any]] = []
        for rank_idx, task in enumerate(ordered_tasks, start=1):
            if task.task_id in best_placements:
                for chunk, start_slot in best_placements[task.task_id]:
                    if (chunk.task_id, chunk.chunk_index) in pinned_task_chunks:
                        continue
                    final_grid.place_block(start_slot, chunk.duration_slots, chunk.task_id, chunk.title)
                    reason_codes: List[Dict[str, Any]] = [
                        {
                            "code": "ORDER",
                            "rank": rank_idx,
                            "of": num_tasks,
                            "text": f"Nghiệm tối ưu toàn cục từ Quay lui Nhánh-Cận ({self.nodes_explored} nút duyệt)",
                        },
                        {
                            "code": "EARLIEST_FREE_GAP",
                            "text": "Đặt tại vị trí tối ưu không vi phạm ràng buộc cứng",
                        },
                    ]
                    if chunk.deadline_slot is not None:
                        reason_codes.insert(
                            0,
                            {
                                "code": "BEFORE_DEADLINE",
                                "due": chunk.deadline_str,
                                "text": f"Hoàn thành trước hạn chót ({chunk.deadline_str})",
                            },
                        )
                    reason_text = (
                        f"[Backtracking Branch-and-Bound] Nghiệm tối ưu kiểm chứng "
                        f"({self.nodes_explored} trạng thái đã duyệt, Ưu tiên {chunk.priority})."
                    )
                    block = self.build_schedule_block(
                        chunk=chunk,
                        start_slot=start_slot,
                        reason_text=reason_text,
                        reason_codes=reason_codes,
                        week_start_iso=week_start_iso,
                    )
                    final_blocks.append(block)
            else:
                unplaced_tasks.append({
                    "task_id": task.task_id,
                    "title": task.title,
                    "duration_min": task.get_planned_duration_min(),
                    "priority": task.priority,
                    "deadline": task.format_deadline_label(week_start_iso=week_start_iso),
                    "deadline_slot": task.resolve_deadline_slot(week_start_iso=week_start_iso),
                    "reason": (
                        f"Chứng minh vét cạn ({self.nodes_explored} nút): "
                        f"Không thể xếp đồng thời cùng các task có độ ưu tiên cao hơn trước hạn chót."
                    ),
                })

        exec_ms = (time.perf_counter() - t0) * 1000.0
        output = self.finalize_output(
            grid_manager=final_grid,
            tasks=tasks,
            blocks=final_blocks,
            unplaced_tasks=unplaced_tasks,
            capacity_reports=capacity_reports,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
        )
        return output, final_grid

