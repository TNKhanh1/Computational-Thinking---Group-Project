"""
Abstract Base Scheduler & Task Splitting / Capacity Verification Logic.
Implements:
  - Task Splitting Strategies (baseline_plan.md §4 & Proposal §6.4):
      1. Atomic (Unsplittable)
      2. Uniform Fixed-Size Chunking (45–90 min multiples of 15 min)
  - Mathematical Capacity Check (baseline_plan.md §6.2.B & Proposal §6.5):
      Distinguishes CAPACITY_SHORTAGE ("Not enough time" - mathematical proof of infeasibility)
      from FRAGMENTATION_FAILURE ("No schedule found" - free time exists but no contiguous gap fits).
"""

from abc import ABC, abstractmethod
import math
import time
from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.metrics import (
    audit_hard_constraint_violations,
    calculate_deadline_satisfaction_rate,
    calculate_fragmentation_index,
    compute_determinism_hash,
)
from src.models import (
    CommitmentsProfile,
    OverloadReport,
    ScheduleBlock,
    ScheduleOutput,
    ScheduleSummary,
    Task,
    TaskChunk,
)
from src.utils import (
    MAX_HORIZON_SLOTS,
    MINUTES_PER_SLOT,
    SLOTS_PER_WEEK,
    day_time_to_slot,
    iso_to_slot,
    minutes_to_slots,
    round_up_to_15,
    slot_to_day_time,
    slot_to_iso,
)


class BaseScheduler(ABC):
    """Abstract base class for all Baseline V0 scheduling algorithms (Strategy Pattern)."""

    solver_name: str = "BASE_SCHEDULER"

    def __init__(self, chunk_strategy: str = "UNIFORM"):
        self.chunk_strategy = chunk_strategy.upper()

    @staticmethod
    def resolve_now_slot(profile: CommitmentsProfile) -> int:
        """Resolve explicit `now` from CommitmentsProfile into a slot index (defaults to 0 = Mon 00:00)."""
        if not profile.now:
            return 0
        now_str = profile.now.strip()
        if "T" in now_str or "-" in now_str:
            return iso_to_slot(now_str, week_start_iso=profile.planning_week_start, is_end_or_deadline=False)
        parts = now_str.split()
        if len(parts) >= 2:
            return day_time_to_slot(parts[0], parts[1], is_end_or_deadline=False)
        return 0

    @staticmethod
    def split_task_into_chunks(
        task: Task,
        original_order: int = 0,
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
    ) -> List[TaskChunk]:
        """
        Split a Task into one or more TaskChunks according to baseline_plan.md §4 & Proposal §6.4:
          - If is_splittable == False or planned_duration <= max_chunk_min (90m): single atomic chunk.
          - If is_splittable == True and planned_duration > max_chunk_min:
            Use the smallest number of parts k = ceil(duration / max_chunk) that keeps every part
            <= max_chunk_min (90m) and >= min_chunk_min (45m), as equal as possible, in multiples of 15 min.
        """
        planned_min = task.get_planned_duration_min()
        deadline_slot = task.resolve_deadline_slot(week_start_iso=week_start_iso)
        deadline_str = task.format_deadline_label(week_start_iso=week_start_iso)
        max_chunk = max(15, round_up_to_15(task.max_chunk_min or 90))
        min_chunk = max(15, round_up_to_15(task.min_chunk_min or 45))

        if not task.is_splittable or planned_min <= max_chunk:
            return [
                TaskChunk(
                    chunk_id=f"{task.task_id}_P1",
                    task_id=task.task_id,
                    title=task.title,
                    chunk_index=1,
                    total_chunks=1,
                    duration_min=planned_min,
                    duration_slots=minutes_to_slots(planned_min),
                    deadline_slot=deadline_slot,
                    deadline_str=deadline_str,
                    priority=task.priority,
                    depends_on=list(task.depends_on),
                    original_order=original_order,
                    is_splittable=task.is_splittable,
                    min_chunk_min=min_chunk,
                )
            ]

        total_slots = minutes_to_slots(planned_min)
        max_slots_per_part = minutes_to_slots(max_chunk)
        min_slots_per_part = minutes_to_slots(min_chunk)

        num_parts = int(math.ceil(total_slots / float(max_slots_per_part)))
        while num_parts > 1 and (total_slots // num_parts) < min_slots_per_part:
            num_parts -= 1

        base_slots = total_slots // num_parts
        remainder_slots = total_slots % num_parts

        chunks: List[TaskChunk] = []
        for idx in range(num_parts):
            c_slots = base_slots + (1 if idx < remainder_slots else 0)
            c_min = c_slots * MINUTES_PER_SLOT
            chunks.append(
                TaskChunk(
                    chunk_id=f"{task.task_id}_P{idx + 1}",
                    task_id=task.task_id,
                    title=task.title,
                    chunk_index=idx + 1,
                    total_chunks=num_parts,
                    duration_min=c_min,
                    duration_slots=c_slots,
                    deadline_slot=deadline_slot,
                    deadline_str=deadline_str,
                    priority=task.priority,
                    depends_on=list(task.depends_on),
                    original_order=original_order,
                    is_splittable=task.is_splittable,
                    min_chunk_min=min_chunk,
                )
            )
        return chunks

    @staticmethod
    def enforce_dependency_order(tasks: List[Task], sorted_tasks: List[Task]) -> List[Task]:
        """
        Topological adjustment: preserve the solver's priority/deadline ordering as closely as possible
        while guaranteeing that every prerequisite in `depends_on` appears before its dependent task.
        """
        task_map = {t.task_id: t for t in tasks}
        rank_map = {t.task_id: i for i, t in enumerate(sorted_tasks)}
        visited = set()
        visiting = set()
        ordered: List[Task] = []

        def visit(tid: str) -> None:
            if tid in visited or tid not in task_map:
                return
            if tid in visiting:
                # Cycle detected: break cycle deterministically
                return
            visiting.add(tid)
            t_obj = task_map[tid]
            # Visit prerequisites sorted by their rank
            prereqs = sorted(t_obj.depends_on, key=lambda pid: rank_map.get(pid, 999999))
            for pid in prereqs:
                visit(pid)
            visiting.remove(tid)
            visited.add(tid)
            ordered.append(t_obj)

        for t in sorted_tasks:
            visit(t.task_id)

        return ordered

    @staticmethod
    def check_deadline_capacity(
        grid_manager: TimeGridManager,
        tasks: List[Task],
        now_slot: int = 0,
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
    ) -> List[OverloadReport]:
        """
        Mathematical Capacity Check (Proposal §6.5 & baseline_plan.md §6.2.B):
        For each distinct deadline D, check if sum(planned_work due <= D) > free_time_available in [now_slot, D).
        If true, this is a mathematical proof of CAPACITY_SHORTAGE ("Not enough time").
        """
        reports: List[OverloadReport] = []
        tasks_with_deadline: List[Tuple[int, Task]] = []
        for t in tasks:
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if d_slot is not None:
                # Clamp effective check boundary to grid size
                effective_d = min(d_slot, grid_manager.total_slots)
                tasks_with_deadline.append((effective_d, t))

        if not tasks_with_deadline:
            return reports

        distinct_deadlines = sorted(set(d for d, _ in tasks_with_deadline))
        for d_slot in distinct_deadlines:
            due_by_d = [t for d, t in tasks_with_deadline if d <= d_slot]
            work_min = sum(t.get_planned_duration_min() for t in due_by_d)
            free_slots = grid_manager.count_free_slots_in_range(start_from=now_slot, up_to=d_slot)
            free_min = free_slots * MINUTES_PER_SLOT

            if work_min > free_min:
                shortage = work_min - free_min
                day_name, time_str = slot_to_day_time(d_slot, is_end_time=True)
                d_label = f"{day_name} {time_str}"
                low_prio_tasks = sorted(due_by_d, key=lambda x: (x.priority, -x.get_planned_duration_min()))
                lowest_id = low_prio_tasks[0].task_id if low_prio_tasks else "TASK"

                reports.append(
                    OverloadReport(
                        error_type="CAPACITY_SHORTAGE",
                        type="NOT_ENOUGH_TIME",
                        message=f"Không đủ thời gian trước hạn chót {d_label} (Thiếu {shortage} phút).",
                        deadline=d_label,
                        deadline_slot=d_slot,
                        total_free_minutes_available=free_min,
                        total_planned_work_minutes=work_min,
                        shortage_minutes=shortage,
                        unplaced_tasks=[t.task_id for t in due_by_d],
                        suggested_actions=[
                            f"Dời hạn chót hoặc giảm thời lượng của task ưu tiên thấp nhất ({lowest_id})",
                            "Cho phép chia nhỏ task (Bật cờ is_splittable = True)",
                            "Xin gia hạn sớm (Early Extension Alert) trước 24–48 giờ",
                        ],
                        options=[
                            {
                                "id": "O1",
                                "code": "POSTPONE_LOWEST",
                                "task": lowest_id,
                                "frees_min": low_prio_tasks[0].get_planned_duration_min() if low_prio_tasks else 0,
                                "label": f"Hoãn hoặc dời hạn chót task '{lowest_id}'",
                            },
                            {
                                "id": "O2",
                                "code": "SHORTEN_TASK",
                                "task": lowest_id,
                                "frees_min": min(shortage, 60),
                                "label": f"Rút gọn phạm vi làm việc tối thiểu (Minimum Viable Deliverable)",
                            },
                        ],
                    )
                )
        return reports

    @staticmethod
    def build_schedule_block(
        chunk: TaskChunk,
        start_slot: int,
        reason_text: str,
        reason_codes: List[Dict[str, Any]],
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
        allowed_starts_slots: Optional[List[int]] = None,
        state: str = "ACCEPTED",
    ) -> ScheduleBlock:
        end_slot = start_slot + chunk.duration_slots
        day_name, start_str = slot_to_day_time(start_slot, is_end_time=False)
        _, end_str = slot_to_day_time(end_slot, is_end_time=True)
        start_iso = slot_to_iso(start_slot, week_start_iso=week_start_iso)
        end_iso = slot_to_iso(end_slot, week_start_iso=week_start_iso)

        allowed_iso: List[str] = []
        if allowed_starts_slots:
            for s in allowed_starts_slots[:12]:
                allowed_iso.append(slot_to_iso(s, week_start_iso=week_start_iso))

        return ScheduleBlock(
            block_id=f"{chunk.task_id}_P{chunk.chunk_index}",
            task_id=chunk.task_id,
            title=chunk.title,
            day=day_name,
            start_time=start_str,
            end_time=end_str,
            start_iso=start_iso,
            end_iso=end_iso,
            start_slot=start_slot,
            end_slot=end_slot,
            duration_min=chunk.duration_min,
            priority=chunk.priority,
            deadline_str=chunk.deadline_str,
            deadline_slot=chunk.deadline_slot,
            chunk_index=chunk.chunk_index,
            total_chunks=chunk.total_chunks,
            state=state,
            reason=reason_text,
            reasons=reason_codes,
            allowed_starts=allowed_iso,
        )

    def finalize_output(
        self,
        grid_manager: TimeGridManager,
        tasks: List[Task],
        blocks: List[ScheduleBlock],
        unplaced_tasks: List[Dict[str, Any]],
        capacity_reports: List[OverloadReport],
        exec_ms: float,
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
        warnings: Optional[List[str]] = None,
    ) -> ScheduleOutput:
        """Assemble the standardized ScheduleOutput with verified metrics and overload reports."""
        overload_reports = list(capacity_reports)
        unplaced_task_ids = sorted(set(str(u["task_id"]) for u in unplaced_tasks))

        # Check if there are unplaced tasks NOT explained by a capacity shortage -> Fragmentation Failure
        if unplaced_tasks and not overload_reports:
            first_u = unplaced_tasks[0]
            u_tid = first_u.get("task_id", "UNKNOWN")
            u_reason = first_u.get(
                "reason",
                "Tổng thời gian rảnh vẫn đủ nhưng bị phân mảnh nhỏ hơn thời lượng yêu cầu của task.",
            )
            free_counts = grid_manager.get_slot_counts(up_to=SLOTS_PER_WEEK)
            free_min_total = free_counts["FREE"] * MINUTES_PER_SLOT
            needed_min = sum(int(u.get("duration_min", 0)) for u in unplaced_tasks)
            overload_reports.append(
                OverloadReport(
                    error_type="FRAGMENTATION_FAILURE",
                    type="NO_SCHEDULE_FOUND",
                    message=f"Không tìm thấy khoảng trống liên tục đủ dài cho task ({u_tid}). {u_reason}",
                    deadline=str(first_u.get("deadline", "Trong tuần")),
                    deadline_slot=first_u.get("deadline_slot"),
                    total_free_minutes_available=free_min_total,
                    total_planned_work_minutes=needed_min,
                    shortage_minutes=0,
                    unplaced_tasks=unplaced_task_ids,
                    suggested_actions=[
                        f"Bật cờ cho phép chia nhỏ task (is_splittable = True) cho '{u_tid}'",
                        "Giảm kích thước mảnh tối thiểu (min_chunk_min)",
                        "Dời một sự kiện cố định để gộp các khoảng trống ngắn thành khoảng dài",
                    ],
                    options=[
                        {
                            "id": "O1",
                            "code": "ALLOW_SPLIT",
                            "task": u_tid,
                            "frees_min": 0,
                            "label": f"Cho phép cắt nhỏ task '{u_tid}' thành các phiên 45–90 phút",
                        }
                    ],
                )
            )
        elif unplaced_tasks and overload_reports:
            # Make sure all actually unplaced task IDs are listed in the capacity report
            for rep in overload_reports:
                merged = list(dict.fromkeys(rep.unplaced_tasks + unplaced_task_ids))
                rep.unplaced_tasks = merged

        hard_violations, violation_msgs = audit_hard_constraint_violations(
            grid_manager, blocks, tasks, week_start_iso=week_start_iso
        )
        deadline_rate = calculate_deadline_satisfaction_rate(
            tasks, blocks, unplaced_task_ids, week_start_iso=week_start_iso
        )
        slot_counts = grid_manager.get_slot_counts(up_to=SLOTS_PER_WEEK)
        frag_index = calculate_fragmentation_index(grid_manager, up_to=SLOTS_PER_WEEK)

        placed_task_ids = set(b.task_id for b in blocks) - set(unplaced_task_ids)
        tasks_placed_count = len(placed_task_ids)
        tasks_unplaced_count = len(tasks) - tasks_placed_count

        if tasks_unplaced_count == 0 and not overload_reports:
            status = "SUCCESS"
        elif any(r.error_type == "CAPACITY_SHORTAGE" for r in overload_reports):
            status = "INFEASIBLE_CAPACITY"
        else:
            status = "NO_SCHEDULE_FOUND"

        summary = ScheduleSummary(
            total_tasks_requested=len(tasks),
            tasks_placed=tasks_placed_count,
            tasks_unplaced=tasks_unplaced_count,
            parts_total=len(blocks) + len(unplaced_tasks),
            parts_placed=len(blocks),
            parts_unplaced=len(unplaced_tasks),
            hard_constraint_violations=hard_violations,
            deadline_satisfaction_rate=deadline_rate,
            free_slots_remaining=slot_counts["FREE"],
            occupied_slots=slot_counts["OCCUPIED"],
            sleep_slots=slot_counts["SLEEP"],
            block_slots=slot_counts["BLOCK"],
            fragmentation_index=frag_index,
        )

        det_hash = compute_determinism_hash(blocks, unplaced_tasks)
        all_warnings = list(warnings or []) + violation_msgs

        return ScheduleOutput(
            status=status,
            solver_used=self.solver_name,
            execution_time_ms=round(exec_ms, 4),
            determinism_hash=det_hash,
            summary=summary,
            blocks=sorted(blocks, key=lambda b: (b.start_slot, b.task_id, b.chunk_index)),
            unplaced_tasks=unplaced_tasks,
            overload_reports=overload_reports,
            overload=overload_reports[0] if overload_reports else None,
            warnings=all_warnings,
            grid_states=list(grid_manager.grid[:SLOTS_PER_WEEK]),
        )

    @abstractmethod
    def solve(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        """Run the scheduling algorithm and return (ScheduleOutput, final TimeGridManager)."""
        raise NotImplementedError

