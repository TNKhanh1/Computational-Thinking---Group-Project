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

from src.config import (
    CATEGORY_BATCH_BONUS,
    CONTEXT_SWITCH_PENALTY,
    EARLY_EXTENSION_ALERT_MAX_HOURS,
    MANDATORY_REST_SLOTS,
    MIN_DEEP_WORK_BREAK_TRIGGER_MIN,
)
from src.estimate_buffer import buffer_reason
from src.grid_manager import TimeGridManager
from src.metrics import (
    audit_hard_constraint_violations,
    calculate_deadline_satisfaction_rate,
    calculate_experience_rating,
    calculate_fragmentation_index,
    compute_determinism_hash,
)
from src.models import (
    CircadianEnergyProfile,
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
    def resolve_horizon_slots(
        tasks: List[Task],
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
    ) -> int:
        """A8: Automatically expand grid horizon to 2 weeks (1344 slots) for cross-week deadlines."""
        for t in tasks:
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if d_slot is not None and d_slot > SLOTS_PER_WEEK:
                return MAX_HORIZON_SLOTS
        return SLOTS_PER_WEEK

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
            Use the smallest number of parts k >= ceil(duration / max_chunk) so NO part ever exceeds max_chunk_min (Fix A1).
        """
        planned_min = task.get_planned_duration_min()
        deadline_slot = task.resolve_deadline_slot(week_start_iso=week_start_iso)
        deadline_str = task.format_deadline_label(week_start_iso=week_start_iso)
        max_chunk = max(MINUTES_PER_SLOT, round_up_to_15(task.max_chunk_min or 90))
        min_chunk = max(MINUTES_PER_SLOT, round_up_to_15(task.min_chunk_min or 45))

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
                    cognitive_load=task.cognitive_load,
                    category=task.category,
                )
            ]

        total_slots = minutes_to_slots(planned_min)
        max_slots_per_part = minutes_to_slots(max_chunk)
        min_slots_per_part = minutes_to_slots(min_chunk)

        # Fix A1: Guarantee every chunk stays <= max_slots_per_part even when total_slots // num_parts < min_slots
        effective_min_slots = min(min_slots_per_part, max_slots_per_part)
        num_parts = int(math.ceil(total_slots / float(max_slots_per_part)))
        while num_parts > 1 and (total_slots // num_parts) < effective_min_slots:
            next_parts = num_parts - 1
            next_max_chunk = (total_slots + next_parts - 1) // next_parts
            if next_max_chunk > max_slots_per_part:
                break
            num_parts = next_parts

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
                    cognitive_load=task.cognitive_load,
                    category=task.category,
                )
            )
        return chunks

    @staticmethod
    def partition_dependency_order(
        tasks: List[Task], sorted_tasks: List[Task]
    ) -> Tuple[List[Task], Dict[str, str]]:
        """
        Fix A7: Detect cycles (CIRCULAR_DEPENDENCY) and missing prerequisite IDs (MISSING_PREREQUISITE)
        while preserving topological order for all valid DAG tasks.
        Propagates invalidity downstream so dependent tasks never cause H5 violations.
        Returns (valid_ordered_tasks, invalid_reasons_by_task_id).
        """
        task_map = {t.task_id: t for t in tasks}
        rank_map = {t.task_id: i for i, t in enumerate(sorted_tasks)}

        # status: 0=unvisited, 1=visiting, 2=valid, 3=invalid
        state: Dict[str, int] = {}
        invalid_reasons: Dict[str, str] = {}
        ordered: List[Task] = []
        active_stack: List[str] = []

        def dfs(tid: str) -> str:
            st = state.get(tid, 0)
            if st == 2:
                return "VALID"
            if st == 3:
                return invalid_reasons[tid]
            if tid not in task_map:
                return "MISSING_PREREQUISITE"
            if st == 1:
                # Cycle hit: mark every node in the cycle path on stack
                if tid in active_stack:
                    cycle_start = active_stack.index(tid)
                    for cyc_tid in active_stack[cycle_start:]:
                        state[cyc_tid] = 3
                        invalid_reasons[cyc_tid] = "CIRCULAR_DEPENDENCY"
                return "CIRCULAR_DEPENDENCY"

            state[tid] = 1
            active_stack.append(tid)
            t_obj = task_map[tid]
            prereqs = sorted(t_obj.depends_on, key=lambda pid: rank_map.get(pid, 999999))
            bad_reason: Optional[str] = None
            for pid in prereqs:
                if pid not in task_map:
                    bad_reason = "MISSING_PREREQUISITE"
                    break
                res = dfs(pid)
                if res != "VALID":
                    bad_reason = res if bad_reason is None else bad_reason
                    # Do not break immediately so cycle members finish marking if needed
            active_stack.pop()

            if state.get(tid) == 3:
                return invalid_reasons[tid]
            if bad_reason is not None:
                state[tid] = 3
                invalid_reasons[tid] = bad_reason
                return bad_reason

            state[tid] = 2
            ordered.append(t_obj)
            return "VALID"

        for t in sorted_tasks:
            dfs(t.task_id)

        return ordered, invalid_reasons

    @staticmethod
    def enforce_dependency_order(tasks: List[Task], sorted_tasks: List[Task]) -> List[Task]:
        """
        Backward-compatible topological adjustment returning valid ordered tasks followed by
        any cycle tasks (kept for direct unit tests in test_circular_dependencies.py).
        Solvers use `partition_dependency_order()` directly to isolate invalid tasks cleanly.
        """
        ordered, invalid_reasons = BaseScheduler.partition_dependency_order(tasks, sorted_tasks)
        ordered_ids = {t.task_id for t in ordered}
        for t in sorted_tasks:
            if t.task_id in invalid_reasons and t.task_id not in ordered_ids:
                ordered.append(t)
                ordered_ids.add(t.task_id)
        return ordered

    @staticmethod
    def detect_past_due_tasks(
        tasks: List[Task],
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
    ) -> Dict[str, str]:
        """Fix A12: Detect ISO deadlines strictly before week_start_iso instead of clamping to Mon 00:00."""
        past_due: Dict[str, str] = {}
        for t in tasks:
            _, is_past_due, _ = t.resolve_deadline_status(week_start_iso=week_start_iso)
            if is_past_due:
                past_due[t.task_id] = "DEADLINE_IN_PAST"
        return past_due

    @staticmethod
    def check_deadline_capacity(
        grid_manager: TimeGridManager,
        tasks: List[Task],
        now_slot: int = 0,
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
        pinned_slots_by_task: Optional[Dict[str, int]] = None,
    ) -> List[OverloadReport]:
        """
        Mathematical Capacity Check (Proposal §6.5 & baseline_plan.md §6.2.B):
        For each distinct deadline D, check if remaining planned work due <= D exceeds free time in [now_slot, D).
        Fix A4: Deduct already-PINNED slots from task work demand so capacity is never double-counted.
        """
        pinned_lookup = pinned_slots_by_task or {}
        reports: List[OverloadReport] = []
        tasks_with_deadline: List[Tuple[int, Task]] = []
        for t in tasks:
            d_slot, is_past_due, _ = t.resolve_deadline_status(week_start_iso=week_start_iso)
            if d_slot is not None and not is_past_due:
                effective_d = min(d_slot, grid_manager.total_slots)
                tasks_with_deadline.append((effective_d, t))

        if not tasks_with_deadline:
            return reports

        distinct_deadlines = sorted(set(d for d, _ in tasks_with_deadline))
        for d_slot in distinct_deadlines:
            due_by_d = [t for d, t in tasks_with_deadline if d <= d_slot]
            work_min = sum(
                max(0, t.get_planned_duration_min() - pinned_lookup.get(t.task_id, 0) * MINUTES_PER_SLOT)
                for t in due_by_d
            )
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
            category=chunk.category,
            cognitive_load=chunk.cognitive_load,
            deadline_str=chunk.deadline_str,
            deadline_slot=chunk.deadline_slot,
            chunk_index=chunk.chunk_index,
            total_chunks=chunk.total_chunks,
            state=state,
            reason=reason_text,
            reasons=reason_codes,
            allowed_starts=allowed_iso,
        )

    @staticmethod
    def prepare_pinned_blocks(
        grid: TimeGridManager,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]],
        now_slot: int,
        week_start_iso: str,
    ) -> Tuple[List[ScheduleBlock], Dict[str, int], Dict[Tuple[str, int], ScheduleBlock], List[str]]:
        """
        Fix A4: Validate and lock valid PINNED/DONE blocks onto grid once before solving.
        Enforces H1/H2/H3 free range check and H4 deadline bound.
        Returns (accepted_pinned_blocks, pinned_slots_by_task, pinned_chunk_map, warnings).
        """
        accepted: List[ScheduleBlock] = []
        pinned_slots_by_task: Dict[str, int] = {}
        pinned_chunk_map: Dict[Tuple[str, int], ScheduleBlock] = {}
        warnings: List[str] = []
        if not pinned_blocks:
            return accepted, pinned_slots_by_task, pinned_chunk_map, warnings

        task_map = {t.task_id: t for t in tasks}
        for pb in pinned_blocks:
            dur = pb.end_slot - pb.start_slot
            if dur <= 0 or pb.start_slot < 0 or pb.end_slot > grid.total_slots:
                warnings.append(f"Skipped invalid pinned block {pb.block_id}: out of grid bounds.")
                continue
            if not grid.is_range_free(pb.start_slot, dur):
                warnings.append(f"Skipped pinned block {pb.block_id}: overlaps SLEEP/OCCUPIED/other PINNED block.")
                continue
            t_obj = task_map.get(pb.task_id)
            if t_obj is not None:
                d_slot = t_obj.resolve_deadline_slot(week_start_iso=week_start_iso)
                if d_slot is not None and pb.end_slot > d_slot:
                    warnings.append(
                        f"Skipped pinned block {pb.block_id}: violates deadline constraint H4 (end_slot={pb.end_slot} > {d_slot})."
                    )
                    continue
            if now_slot > 0 and pb.end_slot <= now_slot and pb.state != "DONE":
                warnings.append(f"Pinned block {pb.block_id} ends before `now` (slot {now_slot}); kept as locked.")

            grid.place_block(pb.start_slot, dur, pb.task_id, pb.title)
            pb_copy = pb.model_copy(deep=True)
            if pb_copy.state not in ("PINNED", "DONE"):
                pb_copy.state = "PINNED"
            accepted.append(pb_copy)
            pinned_slots_by_task[pb.task_id] = pinned_slots_by_task.get(pb.task_id, 0) + dur
            pinned_chunk_map[(pb.task_id, pb.chunk_index)] = pb_copy

        return accepted, pinned_slots_by_task, pinned_chunk_map, warnings

    @staticmethod
    def score_candidate_slot(
        grid: TimeGridManager,
        chunk: TaskChunk,
        start_slot: int,
        profile: CommitmentsProfile,
        placed_blocks: List[ScheduleBlock],
    ) -> Tuple[float, float]:
        """
        Compute Pattern 3 (Circadian Energy) + Pattern 4 (Category Batching / Context Switching) score
        for placing `chunk` at `start_slot`.
        Returns (total_score, avg_energy_level).
        """
        energy_prof: CircadianEnergyProfile = profile.get_energy_profile()
        total_energy = 0.0
        for s in range(start_slot, start_slot + chunk.duration_slots):
            total_energy += energy_prof.level_for_slot(s)
        avg_energy = total_energy / float(max(1, chunk.duration_slots))

        # Pattern 3: Energy matching by cognitive_load (or general peak alignment when preference set)
        load = chunk.cognitive_load
        if load is not None and load >= 3:
            # Deep work strongly prefers Level 3 Peak; penalize Level 1 Low energy
            energy_score = (avg_energy - 1.5) * 4.0
        elif load is not None and load <= 1:
            # Light work slightly prefers Low/Medium slots so Peak stays open for deep work
            energy_score = (3.5 - avg_energy) * 1.2
        else:
            energy_score = (avg_energy - 1.0) * 1.0

        # Pattern 4: Category Batching bonus vs Context Switching penalty with immediate neighbours
        end_slot = start_slot + chunk.duration_slots
        batch_score = 0.0
        cat_upper = (chunk.category or "").upper()
        for prev_b in placed_blocks:
            # Immediate neighbour or separated only by a 15-min recovery break
            gap_before = start_slot - prev_b.end_slot
            gap_after = prev_b.start_slot - end_slot
            if gap_before in (0, 1) or gap_after in (0, 1):
                if (prev_b.category or "").upper() == cat_upper:
                    batch_score += CATEGORY_BATCH_BONUS
                else:
                    batch_score -= CONTEXT_SWITCH_PENALTY

        # Small chronological preference so earliest slot still wins ties deterministically
        early_bias = -0.002 * start_slot
        return (energy_score + batch_score + early_bias), avg_energy

    @staticmethod
    def should_prefer_energy_placement(profile: CommitmentsProfile, chunk: TaskChunk) -> bool:
        """
        Use Circadian & Batching candidate ranking whenever explicit focus_preference,
        energy_profile, or chunk.cognitive_load is specified. Keeps V0 first-fit untouched otherwise.
        """
        return bool(
            profile.focus_preference is not None
            or profile.energy_profile is not None
            or (chunk.cognitive_load is not None)
        )

    @staticmethod
    def find_valid_start_slots(
        grid: TimeGridManager,
        duration_slots: int,
        earliest_start: int,
        max_end_slot: int,
    ) -> List[int]:
        """Find all contiguous valid start slots inside [earliest_start, max_end_slot - duration_slots]."""
        limit = min(grid.total_slots, max_end_slot)
        last_start = limit - duration_slots
        if last_start < earliest_start:
            return []
        valid: List[int] = []
        run_len = 0
        for s in range(max(0, earliest_start), limit):
            if grid.grid[s] == grid.STATE_FREE:
                run_len += 1
                if run_len >= duration_slots:
                    valid.append(s - duration_slots + 1)
            else:
                run_len = 0
        return valid

    @staticmethod
    def build_chunk_reasons(
        task: Task,
        chunk: TaskChunk,
        start_slot: int,
        avg_energy: float,
        primary_code: str,
        primary_text: str,
        has_prereq: bool,
        rest_reserved: int,
        profile: CommitmentsProfile,
        placed_blocks: List[ScheduleBlock],
        crunch_tier_used: int = 0,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Build structured Explainability reasons[] matching Improve Plan & Presentation2 patterns."""
        codes: List[Dict[str, Any]] = []
        if chunk.deadline_slot is not None:
            codes.append({
                "code": "BEFORE_DEADLINE",
                "due": chunk.deadline_str,
                "text": f"Hoàn thành trước hạn chót ({chunk.deadline_str}).",
            })
        codes.append({
            "code": primary_code,
            "priority": task.priority,
            "deadline": chunk.deadline_str,
            "text": primary_text,
        })

        energy_prof = profile.get_energy_profile()
        load = chunk.cognitive_load
        pref_label = energy_prof.focus_preference
        if load is not None and load >= 3 and avg_energy < 1.8:
            codes.append({
                "code": "ENERGY_FALLBACK",
                "energy_level": round(avg_energy, 2),
                "focus_preference": pref_label,
                "text": f"Xếp vào khung năng lượng thấp hơn ({avg_energy:.1f}/3) để đảm bảo kịp hạn ({pref_label}).",
            })
        else:
            codes.append({
                "code": "ENERGY_MATCH",
                "energy_level": round(avg_energy, 2),
                "focus_preference": pref_label,
                "text": f"Khớp nhịp sinh học ({pref_label}, mức năng lượng {avg_energy:.1f}/3).",
            })

        if has_prereq:
            codes.append({
                "code": "AFTER_PREREQ",
                "depends_on": list(task.depends_on),
                "text": f"Xếp sau khi hoàn thành tiên quyết {', '.join(task.depends_on)}.",
            })

        planned = task.get_planned_duration_min()
        if task.buffer_multiplier > 1.0 and planned > round_up_to_15(task.duration_min):
            codes.append(
                buffer_reason(task.duration_min, planned, task.buffer_multiplier, profile.estimate_habit)
            )
        elif profile.buffer_mode == "COGNITIVE_LOAD" and planned > round_up_to_15(task.duration_min):
            codes.append({
                "code": "ESTIMATE_BUFFER",
                "estimate_min": task.duration_min,
                "planned_min": planned,
                "text": f"Dự phòng tải nhận thức α: {task.duration_min}p → {planned}p.",
            })

        if rest_reserved > 0:
            codes.append({
                "code": "BREAK_AFTER",
                "rest_min": rest_reserved * MINUTES_PER_SLOT,
                "text": f"Tự động chèn {rest_reserved * MINUTES_PER_SLOT} phút nghỉ phục hồi sau phiên dài.",
            })

        cat_upper = (chunk.category or "").upper()
        end_slot = start_slot + chunk.duration_slots
        batched = any(
            (b.category or "").upper() == cat_upper and ((start_slot - b.end_slot) in (0, 1) or (b.start_slot - end_slot) in (0, 1))
            for b in placed_blocks
            if b.task_id != chunk.task_id
        )
        if batched:
            codes.append({
                "code": "BATCHED_CATEGORY",
                "category": chunk.category,
                "text": f"Gom nhóm liền kề với công việc cùng loại ({chunk.category}) để giảm chuyển đổi ngữ cảnh.",
            })

        if crunch_tier_used > 0:
            codes.append({
                "code": "CRUNCH_RELAXED",
                "tier": crunch_tier_used,
                "text": "Chế độ Sprint (Tier 1): nới nghỉ giữa giờ để ưu tiên kịp hạn.",
            })

        return primary_text, codes

    def place_task_with_constraints(
        self,
        task: Task,
        grid: TimeGridManager,
        profile: CommitmentsProfile,
        now_slot: int,
        task_end_slots: Dict[str, int],
        pinned_chunk_map: Dict[Tuple[str, int], ScheduleBlock],
        placed_blocks: List[ScheduleBlock],
        week_start_iso: str,
        primary_code: str,
        primary_text: str,
        allow_breaks: bool = True,
        crunch_tier_used: int = 0,
        order_index: int = 0,
        best_fit: bool = False,
    ) -> Tuple[bool, List[ScheduleBlock], Optional[Dict[str, Any]], List[str]]:
        """
        Shared deterministic atomic placement helper (Fixes A1, A2, A4, Pattern 2, Pattern 3, Pattern 4).
        Places all unpinned chunks of `task` in strictly increasing chunk order around any pinned chunks,
        reserves mandatory 15m recovery breaks after deep-work chunks, and atomically rolls back if incomplete.
        Returns (success, newly_added_blocks, unplaced_entry_or_none, warnings).
        """
        chunks = self.split_task_into_chunks(task, original_order=order_index, week_start_iso=week_start_iso)
        task_warnings: List[str] = []

        # H5 Prerequisite check: if any prerequisite is missing from placed tasks, fail fast
        prereq_end = now_slot
        for pid in task.depends_on:
            if pid not in task_end_slots:
                return False, [], {
                    "task_id": task.task_id,
                    "title": task.title,
                    "duration_min": task.get_planned_duration_min(),
                    "deadline": task.format_deadline_label(week_start_iso=week_start_iso),
                    "deadline_slot": task.resolve_deadline_slot(week_start_iso=week_start_iso),
                    "reason": f"Công việc tiên quyết '{pid}' chưa được xếp lịch trước.",
                    "reason_code": "PREREQUISITE_UNPLACED",
                }, task_warnings
            prereq_end = max(prereq_end, task_end_slots[pid])

        # Compute unpinned-chunk bounds respecting pinned chunks (Fix A4 #3)
        raw_d_slot = task.resolve_deadline_slot(week_start_iso=week_start_iso)
        horizon_limit = min(raw_d_slot, grid.total_slots) if raw_d_slot is not None else grid.total_slots

        chunk_max_ends: List[int] = [horizon_limit] * len(chunks)
        for i in range(len(chunks) - 1, -1, -1):
            c_i = chunks[i]
            pinned_next = None
            slots_between = 0
            for j in range(i + 1, len(chunks)):
                pb_j = pinned_chunk_map.get((task.task_id, chunks[j].chunk_index))
                if pb_j is not None:
                    pinned_next = pb_j
                    break
                slots_between += chunks[j].duration_slots
            if pinned_next is not None:
                chunk_max_ends[i] = min(horizon_limit, pinned_next.start_slot - slots_between)

        placed_temp: List[Tuple[int, int, ScheduleBlock]] = []  # (start_slot, rest_slots_reserved, block)
        current_min_start = prereq_end
        failed_reason: Optional[str] = None
        fail_code = "FRAGMENTATION"
        existing_pinned_for_task: List[ScheduleBlock] = []

        for idx, ch in enumerate(chunks):
            pb = pinned_chunk_map.get((task.task_id, ch.chunk_index))
            if pb is not None:
                # Validate chunk order against prev chunk
                if pb.start_slot < current_min_start:
                    failed_reason = f"Block ghim {pb.block_id} vi phạm thứ tự sau phần trước hoặc tiên quyết."
                    fail_code = "PIN_ORDER_CONFLICT"
                    break
                existing_pinned_for_task.append(pb)
                current_min_start = pb.end_slot
                continue

            max_end = chunk_max_ends[idx]
            candidates = self.find_valid_start_slots(grid, ch.duration_slots, current_min_start, max_end)
            if not candidates:
                avail_slots = grid.count_free_slots_in_range(start_from=current_min_start, up_to=max_end)
                if avail_slots < ch.duration_slots:
                    failed_reason = (
                        f"Không đủ thời gian trống trước hạn ({avail_slots * MINUTES_PER_SLOT}p < {ch.duration_min}p)."
                    )
                    fail_code = "CAPACITY_SHORTAGE"
                else:
                    failed_reason = (
                        f"Thời gian rảnh bị phân mảnh, không đủ đoạn liên tục {ch.duration_min}p cho phần {ch.chunk_index}/{ch.total_chunks}."
                    )
                    fail_code = "FRAGMENTATION"
                break

            energy_prof = profile.get_energy_profile()
            if best_fit:
                free_ivs = grid.get_free_intervals(start_from=current_min_start, up_to=max_end)
                valid_ivs = [(ivs, ivl) for ivs, ivl in free_ivs if ivl >= ch.duration_slots]
                if not valid_ivs:
                    chosen_start = candidates[0]
                    avg_energy = energy_prof.level_for_slot(chosen_start)
                elif self.should_prefer_energy_placement(profile, ch):
                    iv_for_start: Dict[int, int] = {}
                    for ivs, ivl in valid_ivs:
                        for pos in range(ivs, ivs + ivl - ch.duration_slots + 1):
                            iv_for_start[pos] = ivl
                    scored = [
                        (
                            self.score_candidate_slot(grid, ch, s, profile, placed_blocks)[0]
                            - 0.15 * (iv_for_start.get(s, ch.duration_slots) - ch.duration_slots),
                            self.score_candidate_slot(grid, ch, s, profile, placed_blocks)[1],
                            s,
                        )
                        for s in candidates
                    ]
                    scored.sort(key=lambda item: (-item[0], item[2]))
                    chosen_start = scored[0][2]
                    avg_energy = scored[0][1]
                else:
                    valid_ivs.sort(key=lambda iv: (iv[1] - ch.duration_slots, iv[0]))
                    chosen_start = valid_ivs[0][0]
                    avg_energy = sum(
                        energy_prof.level_for_slot(s) for s in range(chosen_start, chosen_start + ch.duration_slots)
                    ) / float(max(1, ch.duration_slots))
            elif self.should_prefer_energy_placement(profile, ch):
                scored = [
                    (self.score_candidate_slot(grid, ch, s, profile, placed_blocks), s)
                    for s in candidates
                ]
                scored.sort(key=lambda item: (-item[0][0], item[1]))
                chosen_start = scored[0][1]
                avg_energy = scored[0][0][1]
            else:
                chosen_start = candidates[0]
                avg_energy = sum(
                    energy_prof.level_for_slot(s) for s in range(chosen_start, chosen_start + ch.duration_slots)
                ) / float(max(1, ch.duration_slots))

            grid.place_block(chosen_start, ch.duration_slots, ch.task_id, ch.title)
            end_slot = chosen_start + ch.duration_slots

            rest_reserved = 0
            is_deep = ch.duration_min >= MIN_DEEP_WORK_BREAK_TRIGGER_MIN or (
                ch.cognitive_load is not None and ch.cognitive_load >= 3
            )
            if allow_breaks and is_deep:
                rest_reserved = grid.reserve_rest_break(end_slot, MANDATORY_REST_SLOTS, task_id=ch.task_id)

            r_text, r_codes = self.build_chunk_reasons(
                task=task,
                chunk=ch,
                start_slot=chosen_start,
                avg_energy=avg_energy,
                primary_code=primary_code,
                primary_text=primary_text,
                has_prereq=bool(task.depends_on),
                rest_reserved=rest_reserved,
                profile=profile,
                placed_blocks=placed_blocks,
                crunch_tier_used=crunch_tier_used,
            )

            block = self.build_schedule_block(
                chunk=ch,
                start_slot=chosen_start,
                reason_text=r_text,
                reason_codes=r_codes,
                week_start_iso=week_start_iso,
                allowed_starts_slots=candidates,
                state="ACCEPTED",
            )
            placed_temp.append((chosen_start, rest_reserved, block))
            # Next chunk of the same task starts after end_slot + any mandatory break reserved
            current_min_start = end_slot + rest_reserved

        if failed_reason is not None:
            # Atomic rollback of temp blocks AND any rest breaks they created
            for start_s, rest_res, tb in placed_temp:
                grid.remove_block(start_s, tb.end_slot - start_s)
                if rest_res > 0:
                    for rs in range(tb.end_slot, min(grid.total_slots, tb.end_slot + rest_res)):
                        if grid.grid[rs].startswith(f"{grid.STATE_REST}:BREAK:{task.task_id}"):
                            grid.grid[rs] = grid.STATE_FREE
                            grid.labels[rs] = ""
            # Fix A4 #2: Do not leave non-DONE orphaned pinned chunks stranded on grid
            for pb in list(pinned_chunk_map.values()):
                if pb.task_id == task.task_id and pb.state != "DONE":
                    grid.remove_block(pb.start_slot, pb.end_slot - pb.start_slot)
                    task_warnings.append(
                        f"Released incomplete PINNED block {pb.block_id} because remaining chunks of '{task.task_id}' could not be placed."
                    )

            return False, [], {
                "task_id": task.task_id,
                "title": task.title,
                "duration_min": task.get_planned_duration_min(),
                "deadline": task.format_deadline_label(week_start_iso=week_start_iso),
                "deadline_slot": raw_d_slot,
                "reason": failed_reason,
                "reason_code": fail_code,
            }, task_warnings

        new_blocks = [tb for _, _, tb in placed_temp]
        all_task_blocks = existing_pinned_for_task + new_blocks
        if all_task_blocks:
            task_end_slots[task.task_id] = max(b.end_slot for b in all_task_blocks)
        return True, new_blocks, None, task_warnings

    @staticmethod
    def compute_early_extension_alerts(
        tasks: List[Task],
        unplaced_tasks: List[Dict[str, Any]],
        now_slot: int,
        week_start_iso: str,
    ) -> List[Dict[str, Any]]:
        """
        Presentation2 Slide 16 Step 5: Emit Early Extension Alerts when an unplaced / at-risk task's
        deadline falls within the 0–48h early warning horizon so the student can negotiate early.
        """
        unplaced_ids = {str(u.get("task_id", "")) for u in unplaced_tasks}
        alerts: List[Dict[str, Any]] = []
        for t in tasks:
            if t.task_id not in unplaced_ids:
                continue
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if d_slot is None:
                continue
            hours_remaining = ((d_slot - now_slot) * MINUTES_PER_SLOT) / 60.0
            if 0.0 < hours_remaining <= EARLY_EXTENSION_ALERT_MAX_HOURS:
                alerts.append({
                    "task_id": t.task_id,
                    "title": t.title,
                    "hours_remaining": round(hours_remaining, 1),
                    "deadline": t.format_deadline_label(week_start_iso=week_start_iso),
                    "recommendation": (
                        f"Early Extension Alert: Còn {hours_remaining:.1f}h tới hạn '{t.title}' — "
                        "nên chủ động xin gia hạn sớm (24–48h trước deadline) hoặc cắt giảm phạm vi."
                    ),
                })
        return alerts

    def run_ranked_greedy_pipeline(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        pinned_blocks: Optional[List[ScheduleBlock]],
        sort_key_fn: Any,
        primary_code: str,
        reason_builder_fn: Any,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        """
        Shared deterministic greedy scheduling pipeline used across EDF, WSPT, and SCORED_GREEDY.
        Handles:
          - Dynamic 1w/2w horizon (A8) & mandatory >=6h sleep / fixed events (A11, Pattern 6)
          - Validated pinned blocks without double-counting capacity (A4)
          - Cycle / Missing-prereq isolation (A7) & Past-due detection (A12)
          - Tier 0 (Pattern 5 dead-zones + Pattern 2 15m rest breaks) & Tier 1 Sprint fallback ('Cut breaks')
        """
        t0 = time.perf_counter()
        week_start_iso = profile.planning_week_start
        now_slot = self.resolve_now_slot(profile)
        horizon_slots = self.resolve_horizon_slots(tasks, week_start_iso=week_start_iso)

        grid = TimeGridManager(total_slots=horizon_slots)
        grid.initialize_from_profile(profile)

        accepted_pinned, pinned_slots_by_task, pinned_chunk_map, base_warnings = (
            self.prepare_pinned_blocks(grid, tasks, pinned_blocks, now_slot, week_start_iso)
        )
        past_due_map = self.detect_past_due_tasks(tasks, week_start_iso=week_start_iso)

        active_capacity_tasks = [t for t in tasks if t.task_id not in past_due_map]
        capacity_reports = self.check_deadline_capacity(
            grid,
            active_capacity_tasks,
            now_slot=now_slot,
            week_start_iso=week_start_iso,
            pinned_slots_by_task=pinned_slots_by_task,
        )

        indexed_tasks = list(enumerate(tasks))
        sorted_tasks = [t for _, t in sorted(indexed_tasks, key=lambda item: sort_key_fn(item[0], item[1], now_slot, week_start_iso))]
        ordered_valid, invalid_dep_reasons = self.partition_dependency_order(tasks, sorted_tasks)

        orig_order_map = {t.task_id: i for i, t in indexed_tasks}
        schedulable_tasks: List[Task] = []
        base_unplaced: List[Dict[str, Any]] = []
        invalid_ids = set(invalid_dep_reasons.keys()) | set(past_due_map.keys())

        for t in tasks:
            if t.task_id in invalid_dep_reasons:
                r_code = invalid_dep_reasons[t.task_id]
                msg = (
                    "Phát hiện phụ thuộc vòng lặp (Circular Dependency) — cô lập để giữ C_hard = 0."
                    if r_code == "CIRCULAR_DEPENDENCY"
                    else "Thiếu công việc tiên quyết không tồn tại trong danh sách (Missing Prerequisite)."
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
                    "reason": "Hạn chót (due) nằm trong quá khứ trước tuần lập lịch (DEADLINE_IN_PAST).",
                    "reason_code": "DEADLINE_IN_PAST",
                })

        for t in ordered_valid:
            if t.task_id not in invalid_ids:
                schedulable_tasks.append(t)

        # Pinned end slots baseline (if entire task was already pinned)
        base_pinned_end_slots: Dict[str, int] = {}
        chunks_count_map = {
            t.task_id: len(self.split_task_into_chunks(t, orig_order_map.get(t.task_id, 0), week_start_iso))
            for t in schedulable_tasks
        }
        pinned_counts: Dict[str, int] = {}
        for pb in accepted_pinned:
            pinned_counts[pb.task_id] = pinned_counts.get(pb.task_id, 0) + 1
            base_pinned_end_slots[pb.task_id] = max(base_pinned_end_slots.get(pb.task_id, 0), pb.end_slot)
        # Only pre-seed task completion slot if all chunks are pinned
        completed_pin_end_slots = {
            tid: end_s
            for tid, end_s in base_pinned_end_slots.items()
            if pinned_counts.get(tid, 0) >= chunks_count_map.get(tid, 999)
        }

        def execute_pass(allow_breaks: bool, crunch_tier: int) -> Tuple[TimeGridManager, List[ScheduleBlock], List[Dict[str, Any]], List[str]]:
            pass_grid = grid.clone()
            if allow_breaks:
                pass_grid.mark_dead_zones_as_rest()

            placed: List[ScheduleBlock] = [pb.model_copy(deep=True) for pb in accepted_pinned]
            task_ends = dict(completed_pin_end_slots)
            unplaced: List[Dict[str, Any]] = []
            pass_warnings: List[str] = []
            failed_ids = set(invalid_ids)
            total_sched = len(schedulable_tasks)

            for rank_idx, task in enumerate(schedulable_tasks, start=1):
                failed_prereqs = [p for p in task.depends_on if p in failed_ids]
                if failed_prereqs:
                    failed_ids.add(task.task_id)
                    unplaced.append({
                        "task_id": task.task_id,
                        "title": task.title,
                        "duration_min": task.get_planned_duration_min(),
                        "priority": task.priority,
                        "deadline": task.format_deadline_label(week_start_iso=week_start_iso),
                        "deadline_slot": task.resolve_deadline_slot(week_start_iso=week_start_iso),
                        "reason": f"Công việc tiên quyết ({', '.join(failed_prereqs)}) chưa thể xếp lịch.",
                        "reason_code": "PREREQUISITE_UNPLACED",
                    })
                    continue

                p_text = reason_builder_fn(task, rank_idx, total_sched)
                ok, new_blocks, err_entry, t_warns = self.place_task_with_constraints(
                    task=task,
                    grid=pass_grid,
                    profile=profile,
                    now_slot=now_slot,
                    task_end_slots=task_ends,
                    pinned_chunk_map=pinned_chunk_map,
                    placed_blocks=placed,
                    week_start_iso=week_start_iso,
                    primary_code=primary_code,
                    primary_text=p_text,
                    allow_breaks=allow_breaks,
                    crunch_tier_used=crunch_tier,
                    order_index=orig_order_map.get(task.task_id, 0),
                )
                pass_warnings.extend(t_warns)
                if ok:
                    placed.extend(new_blocks)
                else:
                    failed_ids.add(task.task_id)
                    if err_entry is not None:
                        err_entry["priority"] = task.priority
                        unplaced.append(err_entry)

            return pass_grid, placed, unplaced, pass_warnings

        final_grid, final_blocks, tier_unplaced, tier_warnings = execute_pass(allow_breaks=True, crunch_tier=0)
        crunch_used = 0

        # Step 5 Tier 1 Sprint ('Cut breaks'): retry without REST breaks only if it rescues unplaced task(s)
        if tier_unplaced:
            sprint_grid, sprint_blocks, sprint_unplaced, sprint_warnings = execute_pass(allow_breaks=False, crunch_tier=1)
            if len(sprint_unplaced) < len(tier_unplaced):
                final_grid, final_blocks, tier_unplaced, tier_warnings = (
                    sprint_grid,
                    sprint_blocks,
                    sprint_unplaced,
                    sprint_warnings + [
                        "Tier 1 Sprint Mode (Cut breaks): Tạm bỏ nghỉ 15p giữa phiên và sử dụng khoảng trống nhỏ để ưu tiên kịp hạn."
                    ],
                )
                crunch_used = 1

        all_unplaced = base_unplaced + tier_unplaced
        all_warnings = base_warnings + tier_warnings
        exec_ms = (time.perf_counter() - t0) * 1000.0
        output = self.finalize_output(
            grid_manager=final_grid,
            tasks=tasks,
            blocks=final_blocks,
            unplaced_tasks=all_unplaced,
            capacity_reports=capacity_reports,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
            warnings=all_warnings,
            profile=profile,
            now_slot=now_slot,
            crunch_tier_used=crunch_used,
        )
        return output, final_grid

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
        profile: Optional[CommitmentsProfile] = None,
        now_slot: int = 0,
        crunch_tier_used: int = 0,
    ) -> ScheduleOutput:
        """Assemble the standardized ScheduleOutput with verified metrics and overload reports."""
        overload_reports = list(capacity_reports)
        unplaced_task_ids = sorted(set(str(u["task_id"]) for u in unplaced_tasks))
        unplaced_set = set(unplaced_task_ids)

        # Ensure blocks never retain released pinned chunks of failed tasks
        clean_blocks = [b for b in blocks if b.task_id not in unplaced_set or b.state == "DONE"]

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
            for rep in overload_reports:
                merged = list(dict.fromkeys(rep.unplaced_tasks + unplaced_task_ids))
                rep.unplaced_tasks = merged

        hard_violations, violation_msgs = audit_hard_constraint_violations(
            grid_manager, clean_blocks, tasks, week_start_iso=week_start_iso
        )
        deadline_rate = calculate_deadline_satisfaction_rate(
            tasks, clean_blocks, unplaced_task_ids, week_start_iso=week_start_iso
        )
        slot_counts = grid_manager.get_slot_counts(up_to=SLOTS_PER_WEEK)
        frag_index = calculate_fragmentation_index(grid_manager, up_to=SLOTS_PER_WEEK)

        placed_task_ids = set(b.task_id for b in clean_blocks) - set(unplaced_task_ids)
        tasks_placed_count = len(placed_task_ids)
        tasks_unplaced_count = len(tasks) - tasks_placed_count

        if tasks_unplaced_count == 0 and not overload_reports:
            status = "SUCCESS"
        elif any(r.error_type == "CAPACITY_SHORTAGE" for r in overload_reports):
            status = "INFEASIBLE_CAPACITY"
        else:
            status = "NO_SCHEDULE_FOUND"

        exp_rating, exp_label = calculate_experience_rating(
            grid_manager=grid_manager,
            blocks=clean_blocks,
            tasks=tasks,
            profile=profile,
            unplaced_count=tasks_unplaced_count,
            crunch_tier_used=crunch_tier_used,
        )
        ext_alerts = self.compute_early_extension_alerts(
            tasks=tasks,
            unplaced_tasks=unplaced_tasks,
            now_slot=now_slot,
            week_start_iso=week_start_iso,
        )

        summary = ScheduleSummary(
            total_tasks_requested=len(tasks),
            tasks_placed=tasks_placed_count,
            tasks_unplaced=tasks_unplaced_count,
            parts_total=len(clean_blocks) + len(unplaced_tasks),
            parts_placed=len(clean_blocks),
            parts_unplaced=len(unplaced_tasks),
            hard_constraint_violations=hard_violations,
            deadline_satisfaction_rate=deadline_rate,
            free_slots_remaining=slot_counts["FREE"],
            occupied_slots=slot_counts["OCCUPIED"],
            sleep_slots=slot_counts["SLEEP"],
            block_slots=slot_counts["BLOCK"],
            rest_slots=slot_counts.get("REST", 0),
            fragmentation_index=frag_index,
            experience_rating=exp_rating,
            experience_label=exp_label,
            crunch_tier_used=crunch_tier_used,
            early_extension_alerts=ext_alerts,
        )

        det_hash = compute_determinism_hash(clean_blocks, unplaced_tasks)
        all_warnings = list(grid_manager.sleep_warnings) + list(warnings or []) + violation_msgs
        for al in ext_alerts:
            all_warnings.append(al["recommendation"])

        return ScheduleOutput(
            status=status,
            solver_used=self.solver_name,
            execution_time_ms=round(exec_ms, 4),
            determinism_hash=det_hash,
            summary=summary,
            blocks=sorted(clean_blocks, key=lambda b: (b.start_slot, b.task_id, b.chunk_index)),
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

