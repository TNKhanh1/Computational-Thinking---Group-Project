"""
Solution 3B: Classical Greedy Least Slack Time (LST / Minimum Laxity First) + Best-Fit Placement.
Comparison Engine as specified in baseline_plan.md §3.3.3B & §3.5.2.
Formula:
  Slack(t) = Deadline_t - CurrentTime - Duration_t
Placement:
  Best-Fit chooses the contiguous FREE interval whose usable size is closest to Duration_t,
  preserving large contiguous blocks for longer tasks and minimizing schedule fragmentation.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task
from src.solvers.base_solver import BaseScheduler
from src.utils import MINUTES_PER_SLOT, SLOTS_PER_WEEK


class GreedyLSTSolver(BaseScheduler):
    """
    Least Slack Time (LST) + Best-Fit Placement Solver.
    1. Compute Slack(t) = deadline_slot - now_slot - planned_slots.
    2. Sort tasks by (has_no_deadline, slack ASC, -priority DESC, deadline_slot ASC, original_order ASC).
    3. Place each chunk into the valid FREE interval with minimal excess length (Best-Fit).
    """

    solver_name = "GREEDY_LST_BEST_FIT"

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

        capacity_reports = self.check_deadline_capacity(
            grid, tasks, now_slot=now_slot, week_start_iso=week_start_iso
        )

        indexed_tasks = list(enumerate(tasks))

        def lst_sort_key(item: Tuple[int, Task]) -> Tuple[int, int, int, int, int]:
            idx, t = item
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if d_slot is None:
                return (1, 999999, -t.priority, 999999, idx)
            slack_slots = d_slot - now_slot - t.get_planned_slots()
            return (0, slack_slots, -t.priority, d_slot, idx)

        sorted_by_lst = [t for _, t in sorted(indexed_tasks, key=lst_sort_key)]
        ordered_tasks = self.enforce_dependency_order(tasks, sorted_by_lst)

        orig_order_map = {t.task_id: i for i, t in indexed_tasks}
        total_tasks = len(ordered_tasks)

        task_completion_slot: Dict[str, int] = {}
        failed_task_ids = set()
        unplaced_tasks: List[Dict[str, Any]] = []

        for rank_idx, task in enumerate(ordered_tasks, start=1):
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

            d_slot_task = task.resolve_deadline_slot(week_start_iso=week_start_iso)
            slack_min = (
                (d_slot_task - now_slot - task.get_planned_slots()) * MINUTES_PER_SLOT
                if d_slot_task is not None
                else None
            )

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
                    for pb in placed_blocks:
                        if pb.task_id == chunk.task_id and pb.chunk_index == chunk.chunk_index:
                            current_earliest = max(current_earliest, pb.end_slot)
                    continue

                effective_deadline = (
                    min(chunk.deadline_slot, SLOTS_PER_WEEK)
                    if chunk.deadline_slot is not None
                    else SLOTS_PER_WEEK
                )

                # Best-Fit: scan all contiguous FREE intervals in [current_earliest, effective_deadline)
                free_intervals = grid.get_free_intervals(
                    start_from=current_earliest, up_to=effective_deadline
                )
                valid_intervals: List[Tuple[int, int]] = [
                    (iv_start, iv_len)
                    for iv_start, iv_len in free_intervals
                    if iv_len >= chunk.duration_slots
                ]

                if not valid_intervals:
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

                # Best-Fit selects the interval with minimum (iv_len - duration_slots), tie-breaking by earliest iv_start
                valid_intervals.sort(key=lambda iv: (iv[1] - chunk.duration_slots, iv[0]))
                best_start, best_len = valid_intervals[0]
                allowed_starts = [iv[0] for iv in valid_intervals]

                grid.place_block(best_start, chunk.duration_slots, chunk.task_id, chunk.title)

                slack_label = f"{slack_min}p" if slack_min is not None else "∞"
                reason_codes: List[Dict[str, Any]] = [
                    {
                        "code": "BEST_FIT_GAP",
                        "text": f"Best-Fit: Chọn khoảng trống vừa khít nhất ({best_len * 15}p cho phiên {chunk.duration_min}p)",
                    },
                    {
                        "code": "ORDER",
                        "rank": rank_idx,
                        "of": total_tasks,
                        "text": f"Xếp thứ {rank_idx}/{total_tasks} theo Least Slack Time (Độ trôi tự do = {slack_label})",
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
                    f"[LST + Best-Fit] Xếp thứ {rank_idx}/{total_tasks} (Slack = {slack_label}, Ưu tiên {chunk.priority}). "
                    f"Chọn khoảng rảnh sát nhất ({best_len * 15}p) để tránh làm vỡ khoảng trống lớn."
                )

                block = self.build_schedule_block(
                    chunk=chunk,
                    start_slot=best_start,
                    reason_text=reason_text,
                    reason_codes=reason_codes,
                    week_start_iso=week_start_iso,
                    allowed_starts_slots=allowed_starts,
                )
                task_temp_blocks.append(block)
                current_earliest = best_start + chunk.duration_slots

            if task_failed:
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

