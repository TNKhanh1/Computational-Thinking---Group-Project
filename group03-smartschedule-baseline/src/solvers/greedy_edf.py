"""
Solution 3A: Classical Greedy Earliest Deadline First (EDF) + First-Fit Placement.
Default V0 Baseline B Engine as specified in Proposal §9.3 and baseline_plan.md §3.3.3A & §3.5.1.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task, TaskChunk
from src.solvers.base_solver import BaseScheduler
from src.utils import SLOTS_PER_WEEK, slot_to_iso


class GreedyEDFSolver(BaseScheduler):
    """
    Earliest Deadline First (EDF) + First-Fit Placement Solver.
    1. Lock SLEEP and OCCUPIED slots.
    2. Sort tasks by:
         (has_no_deadline, deadline_slot ASC, -priority DESC, original_order ASC)
       then enforce prerequisite topological order (depends_on).
    3. Split splittable tasks into uniform chunks (45–90 min).
    4. For each chunk, scan from max(now_slot, prereq_end, prev_chunk_end) and place into the
       FIRST contiguous FREE slot range that finishes on or before the deadline (First-Fit).
    """

    solver_name = "GREEDY_EDF_FIRST_FIT"

    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        t0 = time.perf_counter()
        week_start_iso = profile.planning_week_start
        now_slot = self.resolve_now_slot(profile)

        grid = TimeGridManager(total_slots=SLOTS_PER_WEEK)
        grid.initialize_from_profile(profile)

        # Lock any pinned blocks first
        placed_blocks: List[ScheduleBlock] = []
        pinned_task_chunks = set()
        if pinned_blocks:
            for pb in pinned_blocks:
                length_slots = pb.end_slot - pb.start_slot
                if grid.is_range_free(pb.start_slot, length_slots):
                    grid.place_block(pb.start_slot, length_slots, pb.task_id, pb.title)
                    pb_copy = pb.model_copy(deep=True)
                    pb_copy.state = "PINNED"
                    placed_blocks.append(pb_copy)
                    pinned_task_chunks.add((pb.task_id, pb.chunk_index))

        # Step 1: Mathematical capacity check before placement
        capacity_reports = self.check_deadline_capacity(
            grid, tasks, now_slot=now_slot, week_start_iso=week_start_iso
        )

        # Step 2: Sort tasks by EDF rule (Deadline ASC -> Priority DESC -> FIFO Order ASC)
        indexed_tasks = list(enumerate(tasks))

        def edf_sort_key(item: Tuple[int, Task]) -> Tuple[int, int, int, int]:
            idx, t = item
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if d_slot is None:
                return (1, 999999, -t.priority, idx)
            return (0, d_slot, -t.priority, idx)

        sorted_by_edf = [t for _, t in sorted(indexed_tasks, key=edf_sort_key)]
        ordered_tasks = self.enforce_dependency_order(tasks, sorted_by_edf)

        orig_order_map = {t.task_id: i for i, t in indexed_tasks}
        total_tasks = len(ordered_tasks)

        # Track completion end_slot of each task for H5 depends_on checks
        task_completion_slot: Dict[str, int] = {}
        failed_task_ids = set()
        unplaced_tasks: List[Dict[str, Any]] = []

        # Step 3: First-Fit placement per task & chunk
        for rank_idx, task in enumerate(ordered_tasks, start=1):
            # Check if any prerequisite failed
            missing_prereqs = [p for p in task.depends_on if p in failed_task_ids]
            if missing_prereqs:
                failed_task_ids.add(task.task_id)
                unplaced_tasks.append({
                    "task_id": task.task_id,
                    "title": task.title,
                    "duration_min": task.get_planned_duration_min(),
                    "priority": task.priority,
                    "deadline": task.format_deadline_label(week_start_iso=week_start_iso),
                    "deadline_slot": task.resolve_deadline_slot(week_start_iso=week_start_iso),
                    "reason": f"Task phụ thuộc ({', '.join(missing_prereqs)}) chưa thể xếp lịch.",
                })
                continue

            prereq_end_slot = now_slot
            for pid in task.depends_on:
                if pid in task_completion_slot:
                    prereq_end_slot = max(prereq_end_slot, task_completion_slot[pid])

            chunks = self.split_task_into_chunks(
                task,
                original_order=orig_order_map.get(task.task_id, 0),
                week_start_iso=week_start_iso,
            )

            task_temp_blocks: List[ScheduleBlock] = []
            current_earliest = prereq_end_slot
            task_failed = False
            fail_reason = ""

            for chunk in chunks:
                if (chunk.task_id, chunk.chunk_index) in pinned_task_chunks:
                    # Already placed via pinned_blocks
                    for pb in placed_blocks:
                        if pb.task_id == chunk.task_id and pb.chunk_index == chunk.chunk_index:
                            current_earliest = max(current_earliest, pb.end_slot)
                    continue

                # Effective deadline on the 672-slot weekly grid:
                # For T10 (deadline in next week, i.e. > 672), any slot inside 0..672 is before the deadline.
                effective_deadline = (
                    min(chunk.deadline_slot, SLOTS_PER_WEEK)
                    if chunk.deadline_slot is not None
                    else SLOTS_PER_WEEK
                )

                # Collect allowed start positions for First-Fit
                allowed_starts: List[int] = []
                max_start = effective_deadline - chunk.duration_slots
                for s in range(current_earliest, max_start + 1):
                    if grid.can_place_chunk(
                        start_slot=s,
                        length_slots=chunk.duration_slots,
                        deadline_slot=chunk.deadline_slot,
                        earliest_start_slot=current_earliest,
                        max_grid_slot=SLOTS_PER_WEEK,
                    ):
                        allowed_starts.append(s)

                if not allowed_starts:
                    task_failed = True
                    free_before = grid.count_free_slots_in_range(
                        start_from=current_earliest, up_to=effective_deadline
                    )
                    if free_before < chunk.duration_slots:
                        fail_reason = (
                            f"Thiếu thời gian rảnh trước hạn chót {chunk.deadline_str} "
                            f"(Cần {chunk.duration_min}p, chỉ còn {free_before * 15}p rảnh)."
                        )
                    else:
                        fail_reason = (
                            f"Không có khoảng trống liên tục dài {chunk.duration_min} phút "
                            f"trước hạn chót {chunk.deadline_str} (Lỗi phân mảnh chỗ trống)."
                        )
                    break

                # First-Fit chooses the earliest valid slot
                chosen_slot = allowed_starts[0]
                grid.place_block(chosen_slot, chunk.duration_slots, chunk.task_id, chunk.title)

                reason_codes: List[Dict[str, Any]] = [
                    {
                        "code": "EARLIEST_FREE_GAP",
                        "text": "Đặt vào khoảng trống hợp lệ đầu tiên (First-Fit)",
                    },
                    {
                        "code": "ORDER",
                        "rank": rank_idx,
                        "of": total_tasks,
                        "text": f"Xếp thứ {rank_idx}/{total_tasks} theo luật Earliest Deadline First (EDF)",
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
                if chunk.depends_on:
                    reason_codes.append({
                        "code": "AFTER_PREREQ",
                        "task": ", ".join(chunk.depends_on),
                        "text": f"Bắt đầu sau khi hoàn thành {', '.join(chunk.depends_on)}",
                    })

                reason_text = (
                    f"[EDF + First-Fit] Xếp thứ {rank_idx}/{total_tasks} (Ưu tiên {chunk.priority}, "
                    f"Hạn: {chunk.deadline_str}). Đặt tại khoảng trống hợp lệ sớm nhất."
                )

                block = self.build_schedule_block(
                    chunk=chunk,
                    start_slot=chosen_slot,
                    reason_text=reason_text,
                    reason_codes=reason_codes,
                    week_start_iso=week_start_iso,
                    allowed_starts_slots=allowed_starts,
                )
                task_temp_blocks.append(block)
                current_earliest = chosen_slot + chunk.duration_slots

            if task_failed:
                # Roll back any partial chunks of this failed task so the schedule never has half-placed tasks
                for tb in task_temp_blocks:
                    grid.remove_block(tb.start_slot, tb.end_slot - tb.start_slot)
                failed_task_ids.add(task.task_id)
                unplaced_tasks.append({
                    "task_id": task.task_id,
                    "title": task.title,
                    "duration_min": task.get_planned_duration_min(),
                    "priority": task.priority,
                    "deadline": task.format_deadline_label(week_start_iso=week_start_iso),
                    "deadline_slot": task.resolve_deadline_slot(week_start_iso=week_start_iso),
                    "reason": fail_reason,
                })
            else:
                placed_blocks.extend(task_temp_blocks)
                if task_temp_blocks:
                    task_completion_slot[task.task_id] = max(b.end_slot for b in task_temp_blocks)
                else:
                    task_completion_slot[task.task_id] = current_earliest

        exec_ms = (time.perf_counter() - t0) * 1000.0
        output = self.finalize_output(
            grid_manager=grid,
            tasks=tasks,
            blocks=placed_blocks,
            unplaced_tasks=unplaced_tasks,
            capacity_reports=capacity_reports,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
        )
        return output, grid

