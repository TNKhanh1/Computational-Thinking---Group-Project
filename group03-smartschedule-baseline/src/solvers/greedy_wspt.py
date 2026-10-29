"""
Solution 3C: Weighted Shortest Processing Time (WSPT / Smith's Rule) + First-Fit Placement.
Specified in baseline_plan.md §3.3.3C:
  Ratio(t) = Priority(t) / Duration_Min(t)
Prioritizes high-priority quick wins to maximize the number of completed tasks per unit of time.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task
from src.solvers.base_solver import BaseScheduler
from src.utils import SLOTS_PER_WEEK


class GreedyWSPTSolver(BaseScheduler):
    """Weighted Shortest Processing Time (WSPT / Smith's Rule) Solver."""

    solver_name = "GREEDY_WSPT_SMITH_RULE"

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

        def wspt_sort_key(item: Tuple[int, Task]) -> Tuple[float, int, int]:
            idx, t = item
            ratio = float(t.priority) / float(max(15, t.get_planned_duration_min()))
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso) or 999999
            return (-ratio, d_slot, idx)

        sorted_by_wspt = [t for _, t in sorted(indexed_tasks, key=wspt_sort_key)]
        ordered_tasks = self.enforce_dependency_order(tasks, sorted_by_wspt)

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

            ratio = round(float(task.priority) / float(max(15, task.get_planned_duration_min())), 4)
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
                    fail_reason = f"Không còn khoảng trống hợp lệ trước hạn chót {chunk.deadline_str}."
                    break

                chosen_slot = allowed_starts[0]
                grid.place_block(chosen_slot, chunk.duration_slots, chunk.task_id, chunk.title)

                reason_codes: List[Dict[str, Any]] = [
                    {
                        "code": "ORDER",
                        "rank": rank_idx,
                        "of": total_tasks,
                        "text": f"WSPT Ratio = {ratio} (Xếp thứ {rank_idx}/{total_tasks})",
                    },
                    {
                        "code": "EARLIEST_FREE_GAP",
                        "text": "Đặt vào khoảng trống hợp lệ đầu tiên",
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
                    f"[WSPT Smith's Rule] Xếp thứ {rank_idx}/{total_tasks} "
                    f"(Tỷ số Priority/Duration = {ratio})."
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

