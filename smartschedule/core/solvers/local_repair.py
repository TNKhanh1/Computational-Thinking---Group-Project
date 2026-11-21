"""
Disruption & Rescheduling Engine (Module M4 - baseline_plan.md §5 & Proposal §6.6 Step 4).
Fixes applied:
  - A6 #1: Pin Guard in LOCAL_INSERTION (PINNED / DONE blocks are never silently moved or unfrozen).
  - A6 #2: Step 4 Progressive Unfreezing of lowest-priority future non-pinned tasks one task at a time.
  - A6 #3: Topological _enforce_post_move_dependencies + nearest-slot search + deduplicated RepairChange logs.
  - A6 #4: _repair_ripple_shift enforces now_slot and post-move topological dependency consistency.
  - A6 #5: _build_repair_output generates full OverloadReport enriched with OverloadTriageEngine.
  - A8: Dynamic 1w/2w horizon support.
  - A9: repair_overrun() method handles duration overruns locally without full-week reshuffle.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from smartschedule.core.grid_manager import TimeGridManager
from smartschedule.core.metrics import (
    audit_hard_constraint_violations,
    calculate_deadline_satisfaction_rate,
    calculate_experience_rating,
    calculate_fragmentation_index,
    calculate_schedule_stability,
    compute_determinism_hash,
)
from smartschedule.core.models import (
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    OverloadReport,
    RepairChange,
    RepairOutput,
    ScheduleBlock,
    ScheduleOutput,
    ScheduleSummary,
    Task,
)
from smartschedule.core.overload_triage import OverloadTriageEngine
from smartschedule.core.solvers.base_solver import BaseScheduler
from smartschedule.core.solvers.registry import resolve_solver
from smartschedule.core.utils import (
    MINUTES_PER_SLOT,
    SLOTS_PER_WEEK,
    day_time_to_slot,
    iso_to_slot,
    slot_to_day_time,
    slot_to_iso,
)


class LocalRepairEngine:
    """Handles unexpected events (T04) and task duration overruns (T05) via Local Insertion, Ripple-Shift, or Full Rebuild."""

    @staticmethod
    def resolve_disruption_slots(
        disruption: DisruptionEvent,
        week_start_iso: str = "2026-11-02T00:00:00+07:00",
    ) -> Tuple[int, int, int]:
        """Return (disruption_start_slot, disruption_end_slot, now_slot)."""
        d_start = day_time_to_slot(disruption.day_of_week, disruption.start_time, is_end_or_deadline=False)
        d_end = day_time_to_slot(disruption.day_of_week, disruption.end_time, is_end_or_deadline=True)
        if d_end <= d_start:
            d_end = d_start + 4

        if disruption.now_iso:
            now_slot = iso_to_slot(disruption.now_iso, week_start_iso=week_start_iso, is_end_or_deadline=False)
        elif disruption.now_day and disruption.now_time:
            now_slot = day_time_to_slot(disruption.now_day, disruption.now_time, is_end_or_deadline=False)
        else:
            now_slot = max(0, d_start - 4)

        return d_start, d_end, now_slot

    @classmethod
    def repair_disruption(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_schedule: ScheduleOutput,
        disruption: DisruptionEvent,
        mode: str = "LOCAL_INSERTION",
        algorithm: Optional[str] = None,
    ) -> RepairOutput:
        mode_norm = mode.strip().upper()
        if mode_norm in ("LOCAL", "LOCAL_REPAIR", "LOCAL_INSERTION"):
            return cls._repair_local_insertion(profile, tasks, current_schedule, disruption)
        elif mode_norm in ("RIPPLE", "RIPPLE_SHIFT"):
            return cls._repair_ripple_shift(profile, tasks, current_schedule, disruption)
        return cls._repair_full_rebuild(
            profile,
            tasks,
            current_schedule,
            disruption,
            algorithm=algorithm,
        )

    @staticmethod
    def _record_move_change(
        changes_by_id: Dict[str, RepairChange],
        initial_blocks: Dict[str, ScheduleBlock],
        moved_b: ScheduleBlock,
    ) -> None:
        """Deduplicate RepairChange entries so every moved block shows one net (original -> final) delta."""
        orig = initial_blocks.get(moved_b.block_id)
        if orig is None:
            return
        if (orig.start_slot, orig.end_slot) == (moved_b.start_slot, moved_b.end_slot):
            changes_by_id.pop(moved_b.block_id, None)
            return
        changes_by_id[moved_b.block_id] = RepairChange(
            block_id=moved_b.block_id,
            task_id=moved_b.task_id,
            title=moved_b.title,
            old_day=orig.day,
            old_start_time=orig.start_time,
            old_end_time=orig.end_time,
            old_start_slot=orig.start_slot,
            old_end_slot=orig.end_slot,
            new_day=moved_b.day,
            new_start_time=moved_b.start_time,
            new_end_time=moved_b.end_time,
            new_start_slot=moved_b.start_slot,
            new_end_slot=moved_b.end_slot,
            status="MOVED",
        )

    @staticmethod
    def _record_unplaced_change(
        changes_by_id: Dict[str, RepairChange],
        initial_blocks: Dict[str, ScheduleBlock],
        b: ScheduleBlock,
    ) -> None:
        orig = initial_blocks.get(b.block_id, b)
        changes_by_id[b.block_id] = RepairChange(
            block_id=b.block_id,
            task_id=b.task_id,
            title=b.title,
            old_day=orig.day,
            old_start_time=orig.start_time,
            old_end_time=orig.end_time,
            old_start_slot=orig.start_slot,
            old_end_slot=orig.end_slot,
            status="UNPLACED",
        )

    @staticmethod
    def _find_nearest_valid_slot(
        grid: TimeGridManager,
        block: ScheduleBlock,
        repaired_blocks: List[ScheduleBlock],
        task_map: Dict[str, Task],
        now_slot: int,
    ) -> Optional[int]:
        length_slots = block.end_slot - block.start_slot
        t_obj = task_map.get(block.task_id)

        earliest_start = max(now_slot, 0)
        if t_obj and t_obj.depends_on:
            for pid in t_obj.depends_on:
                prereq_ends = [rb.end_slot for rb in repaired_blocks if rb.task_id == pid]
                if prereq_ends:
                    earliest_start = max(earliest_start, max(prereq_ends))

        earlier_chunks = [
            rb.end_slot
            for rb in repaired_blocks
            if rb.task_id == block.task_id and rb.chunk_index < block.chunk_index
        ]
        eff_deadline = (
            min(block.deadline_slot, grid.total_slots)
            if block.deadline_slot is not None
            else grid.total_slots
        )
        later_chunks = [
            rb.start_slot
            for rb in repaired_blocks
            if rb.task_id == block.task_id and rb.chunk_index > block.chunk_index
        ]

        seq_earliest = max([earliest_start] + earlier_chunks)
        seq_deadline = min([eff_deadline] + later_chunks)

        def _collect_candidates(min_s: int, max_e: int) -> List[int]:
            found: List[int] = []
            for s in range(min_s, max_e - length_slots + 1):
                if grid.can_place_chunk(
                    start_slot=s,
                    length_slots=length_slots,
                    deadline_slot=block.deadline_slot,
                    earliest_start_slot=min_s,
                    max_grid_slot=max_e,
                ):
                    found.append(s)
            return found

        candidates = _collect_candidates(seq_earliest, seq_deadline)
        # Fallback if a frozen sibling chunk blocks sequential ordering (e.g., P1 displaced after frozen P2)
        if not candidates and (seq_earliest != earliest_start or seq_deadline != eff_deadline):
            candidates = _collect_candidates(earliest_start, eff_deadline)

        if not candidates:
            return None
        candidates.sort(key=lambda s: (abs(s - block.start_slot), s))
        return candidates[0]

    @classmethod
    def _try_progressive_unfreeze(
        cls,
        grid: TimeGridManager,
        target_block: ScheduleBlock,
        repaired_blocks: List[ScheduleBlock],
        task_map: Dict[str, Task],
        now_slot: int,
        week_start_iso: str,
        initial_blocks: Dict[str, ScheduleBlock],
        changes_by_id: Dict[str, RepairChange],
        unplaced_tasks: List[Dict[str, Any]],
        event_title: str,
    ) -> Optional[ScheduleBlock]:
        """
        Fix A6 #2 / Proposal §6.6 Step 4:
        When an impacted high-priority block cannot fit, progressively unfreeze future
        non-PINNED/non-DONE blocks of lowest-priority tasks one task at a time,
        place the impacted block, then re-insert the displaced low-priority blocks.
        """
        # Identify candidate victim tasks sorted by ascending priority (strictly or <= target_block.priority)
        victim_scores: Dict[str, Tuple[int, int, int]] = {}
        for rb in repaired_blocks:
            if rb.task_id == target_block.task_id:
                continue
            if rb.state in ("PINNED", "DONE") or rb.start_slot < now_slot:
                continue
            if rb.priority > target_block.priority:
                continue
            d_val = rb.deadline_slot if rb.deadline_slot is not None else 999999
            cur_best = victim_scores.get(rb.task_id)
            score = (rb.priority, -d_val, rb.start_slot)
            if cur_best is None or score < cur_best:
                victim_scores[rb.task_id] = score

        if not victim_scores:
            return None

        ordered_victims = [tid for tid, _ in sorted(victim_scores.items(), key=lambda x: x[1])]

        trial_grid = grid.clone()
        trial_repaired = [rb.model_copy(deep=True) for rb in repaired_blocks]
        evicted_blocks: List[ScheduleBlock] = []
        placed_slot: Optional[int] = None

        for v_tid in ordered_victims:
            # Unfreeze all future non-pinned blocks belonging to victim `v_tid`
            v_blocks = [
                rb for rb in trial_repaired
                if rb.task_id == v_tid and rb.state not in ("PINNED", "DONE") and rb.start_slot >= now_slot
            ]
            if not v_blocks:
                continue
            for vb in v_blocks:
                trial_grid.remove_block(vb.start_slot, vb.end_slot - vb.start_slot)
                trial_repaired.remove(vb)
                evicted_blocks.append(vb)

            cand = cls._find_nearest_valid_slot(trial_grid, target_block, trial_repaired, task_map, now_slot)
            if cand is not None:
                placed_slot = cand
                break

        if placed_slot is None:
            return None

        # Commit target_block into trial_grid
        t_len = target_block.end_slot - target_block.start_slot
        trial_grid.place_block(placed_slot, t_len, target_block.task_id, target_block.title)
        new_day, new_s_str = slot_to_day_time(placed_slot, is_end_time=False)
        _, new_e_str = slot_to_day_time(placed_slot + t_len, is_end_time=True)
        moved_target = target_block.model_copy(deep=True)
        moved_target.day = new_day
        moved_target.start_time = new_s_str
        moved_target.end_time = new_e_str
        moved_target.start_slot = placed_slot
        moved_target.end_slot = placed_slot + t_len
        moved_target.start_iso = slot_to_iso(placed_slot, week_start_iso=week_start_iso)
        moved_target.end_iso = slot_to_iso(placed_slot + t_len, week_start_iso=week_start_iso)
        moved_target.reason = (
            f"[Local Repair + Progressive Unfreeze] Giải phóng tạm block ưu tiên thấp hơn để đặt '{moved_target.title}'."
        )
        moved_target.reasons = [
            {"code": "PROGRESSIVE_UNFREEZE", "event": event_title, "text": moved_target.reason}
        ]
        trial_repaired.append(moved_target)

        # Re-insert evicted lower-priority blocks nearest to their original slots
        for eb in sorted(evicted_blocks, key=lambda b: (-b.priority, b.start_slot)):
            eb_cand = cls._find_nearest_valid_slot(trial_grid, eb, trial_repaired, task_map, now_slot)
            if eb_cand is not None:
                eb_len = eb.end_slot - eb.start_slot
                trial_grid.place_block(eb_cand, eb_len, eb.task_id, eb.title)
                eb_day, eb_s_str = slot_to_day_time(eb_cand, is_end_time=False)
                _, eb_e_str = slot_to_day_time(eb_cand + eb_len, is_end_time=True)
                eb.day = eb_day
                eb.start_time = eb_s_str
                eb.end_time = eb_e_str
                eb.start_slot = eb_cand
                eb.end_slot = eb_cand + eb_len
                eb.start_iso = slot_to_iso(eb_cand, week_start_iso=week_start_iso)
                eb.end_iso = slot_to_iso(eb_cand + eb_len, week_start_iso=week_start_iso)
                eb.reason = f"[Progressive Unfreeze Shift] Nhường chỗ cho block ưu tiên cao hơn '{target_block.title}'."
                trial_repaired.append(eb)
                cls._record_move_change(changes_by_id, initial_blocks, eb)
            else:
                unplaced_tasks.append({
                    "task_id": eb.task_id,
                    "title": eb.title,
                    "duration_min": eb.duration_min,
                    "priority": eb.priority,
                    "deadline": eb.deadline_str,
                    "deadline_slot": eb.deadline_slot,
                    "reason": f"Nhường chỗ cho block ưu tiên cao hơn ({target_block.title}) khi sửa sự kiện '{event_title}'.",
                    "reason_code": "PREEMPTED_BY_HIGHER_PRIORITY",
                })
                cls._record_unplaced_change(changes_by_id, initial_blocks, eb)

        # Copy trial state back to caller references
        grid.grid = trial_grid.grid
        grid.labels = trial_grid.labels
        repaired_blocks[:] = trial_repaired
        cls._record_move_change(changes_by_id, initial_blocks, moved_target)
        return moved_target

    @classmethod
    def _repair_local_insertion(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_schedule: ScheduleOutput,
        disruption: DisruptionEvent,
    ) -> RepairOutput:
        """Proposal §6.6 Step 4 Local Insertion with Pin Guard + Progressive Unfreezing."""
        t0 = time.perf_counter()
        week_start_iso = profile.planning_week_start
        d_start, d_end, now_slot = cls.resolve_disruption_slots(disruption, week_start_iso=week_start_iso)
        horizon_slots = BaseScheduler.resolve_horizon_slots(
            tasks,
            week_start_iso=week_start_iso,
            horizon_days=getattr(profile, "horizon_days", 7),
        )

        updated_profile = profile.model_copy(deep=True)
        updated_profile.fixed_events.append(
            FixedEvent(
                event_id=disruption.event_id,
                title=disruption.title,
                day_of_week=disruption.day_of_week,
                start_time=disruption.start_time,
                end_time=disruption.end_time,
                category="DISRUPTION_EVENT",
            )
        )

        grid = TimeGridManager(total_slots=horizon_slots)
        grid.initialize_from_profile(updated_profile)

        task_map: Dict[str, Task] = {t.task_id: t for t in tasks}
        original_blocks = [b.model_copy(deep=True) for b in current_schedule.blocks]
        initial_blocks: Dict[str, ScheduleBlock] = {b.block_id: b.model_copy(deep=True) for b in original_blocks}

        frozen_blocks: List[ScheduleBlock] = []
        affected_blocks: List[ScheduleBlock] = []
        pin_warnings: List[str] = []
        unplaced_tasks: List[Dict[str, Any]] = [dict(u) for u in current_schedule.unplaced_tasks]
        changes_by_id: Dict[str, RepairChange] = {}

        # Fix A6 #1: Pin Guard separates PINNED / DONE blocks
        for b in original_blocks:
            overlaps = not (b.end_slot <= d_start or b.start_slot >= d_end)
            if b.state in ("PINNED", "DONE"):
                if overlaps:
                    pin_warnings.append(
                        f"Pin Guard Warning: Sự kiện '{disruption.title}' trùng vào block đã khóa {b.state} '{b.block_id}' — cần xác nhận gỡ ghim."
                    )
                    unplaced_tasks.append({
                        "task_id": b.task_id,
                        "title": b.title,
                        "duration_min": b.duration_min,
                        "priority": b.priority,
                        "deadline": b.deadline_str,
                        "deadline_slot": b.deadline_slot,
                        "reason": f"Pin Guard: Sự kiện '{disruption.title}' đè lên block đang giữ trạng thái {b.state}.",
                        "reason_code": "PIN_CONFLICT",
                    })
                    cls._record_unplaced_change(changes_by_id, initial_blocks, b)
                else:
                    frozen_blocks.append(b)
            elif overlaps:
                affected_blocks.append(b)
            else:
                frozen_blocks.append(b)

        for fb in frozen_blocks:
            length_slots = fb.end_slot - fb.start_slot
            if grid.is_range_free(fb.start_slot, length_slots):
                grid.place_block(fb.start_slot, length_slots, fb.task_id, fb.title)

        affected_blocks.sort(
            key=lambda b: (-b.priority, b.deadline_slot if b.deadline_slot is not None else 999999, b.start_slot)
        )

        repaired_blocks: List[ScheduleBlock] = list(frozen_blocks)

        for b in affected_blocks:
            cand = cls._find_nearest_valid_slot(grid, b, repaired_blocks, task_map, now_slot)
            if cand is not None:
                length_slots = b.end_slot - b.start_slot
                new_end = cand + length_slots
                grid.place_block(cand, length_slots, b.task_id, b.title)

                new_day, new_start_str = slot_to_day_time(cand, is_end_time=False)
                _, new_end_str = slot_to_day_time(new_end, is_end_time=True)

                moved_b = b.model_copy(deep=True)
                moved_b.day = new_day
                moved_b.start_time = new_start_str
                moved_b.end_time = new_end_str
                moved_b.start_slot = cand
                moved_b.end_slot = new_end
                moved_b.start_iso = slot_to_iso(cand, week_start_iso=week_start_iso)
                moved_b.end_iso = slot_to_iso(new_end, week_start_iso=week_start_iso)
                moved_b.reason = (
                    f"[Local Repair M4] Dời cục bộ từ {b.day} {b.start_time}–{b.end_time} "
                    f"do trùng sự kiện '{disruption.title}' ({disruption.day_of_week} {disruption.start_time}–{disruption.end_time})."
                )
                moved_b.reasons = [
                    {
                        "code": "MOVED_BY_REPAIR",
                        "event": disruption.title,
                        "text": f"Dời do sự kiện đột xuất '{disruption.title}'",
                    },
                    {
                        "code": "BEFORE_DEADLINE",
                        "due": b.deadline_str,
                        "text": f"Vẫn đảm bảo hoàn thành trước hạn chót ({b.deadline_str})",
                    },
                ]
                repaired_blocks.append(moved_b)
                cls._record_move_change(changes_by_id, initial_blocks, moved_b)
            else:
                # Fix A6 #2: Step 4 Progressive Unfreezing before giving up
                rescued = cls._try_progressive_unfreeze(
                    grid=grid,
                    target_block=b,
                    repaired_blocks=repaired_blocks,
                    task_map=task_map,
                    now_slot=now_slot,
                    week_start_iso=week_start_iso,
                    initial_blocks=initial_blocks,
                    changes_by_id=changes_by_id,
                    unplaced_tasks=unplaced_tasks,
                    event_title=disruption.title,
                )
                if rescued is None:
                    unplaced_tasks.append({
                        "task_id": b.task_id,
                        "title": b.title,
                        "duration_min": b.duration_min,
                        "priority": b.priority,
                        "deadline": b.deadline_str,
                        "deadline_slot": b.deadline_slot,
                        "reason": (
                            f"Bị sự kiện '{disruption.title}' chèn vào và không còn khoảng trống hợp lệ "
                            f"trước hạn chót {b.deadline_str}."
                        ),
                        "reason_code": "CAPACITY_SHORTAGE",
                    })
                    cls._record_unplaced_change(changes_by_id, initial_blocks, b)

        # Fix A6 #3: Topological H5 enforcement + nearest-slot + deduplicated RepairChange
        cls._enforce_post_move_dependencies(
            grid=grid,
            tasks=tasks,
            repaired_blocks=repaired_blocks,
            changes_by_id=changes_by_id,
            initial_blocks=initial_blocks,
            unplaced_tasks=unplaced_tasks,
            now_slot=now_slot,
            week_start_iso=week_start_iso,
        )

        exec_ms = (time.perf_counter() - t0) * 1000.0
        return cls._build_repair_output(
            mode_name="LOCAL_INSERTION",
            profile=updated_profile,
            grid=grid,
            tasks=tasks,
            original_blocks=original_blocks,
            repaired_blocks=repaired_blocks,
            unplaced_tasks=unplaced_tasks,
            changes=list(changes_by_id.values()),
            d_start=d_start,
            d_end=d_end,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
            extra_warnings=pin_warnings,
        )

    @classmethod
    def _enforce_post_move_dependencies(
        cls,
        grid: TimeGridManager,
        tasks: List[Task],
        repaired_blocks: List[ScheduleBlock],
        changes_by_id: Dict[str, RepairChange],
        initial_blocks: Dict[str, ScheduleBlock],
        unplaced_tasks: List[Dict[str, Any]],
        now_slot: int,
        week_start_iso: str,
    ) -> None:
        """
        Fix A6 #3: Iterate tasks in topological order (A -> B -> C), shift dependent blocks
        that start before prerequisite completion using nearest valid slot >= now_slot,
        and record deduplicated RepairChange entries.
        """
        topo_tasks = BaseScheduler.enforce_dependency_order(tasks, tasks)
        for t in topo_tasks:
            if not t.depends_on:
                continue
            prereq_ends = [rb.end_slot for rb in repaired_blocks if rb.task_id in t.depends_on]
            if not prereq_ends:
                continue
            req_start = max(now_slot, max(prereq_ends))
            dep_blocks = sorted(
                [rb for rb in repaired_blocks if rb.task_id == t.task_id],
                key=lambda b: b.chunk_index,
            )
            prev_chunk_end = req_start
            for db in dep_blocks:
                needed_start = max(req_start, prev_chunk_end)
                if db.start_slot < needed_start:
                    length_slots = db.end_slot - db.start_slot
                    grid.remove_block(db.start_slot, length_slots)
                    eff_deadline = (
                        min(db.deadline_slot, grid.total_slots)
                        if db.deadline_slot is not None
                        else grid.total_slots
                    )
                    candidates: List[int] = []
                    for s in range(needed_start, eff_deadline - length_slots + 1):
                        if grid.can_place_chunk(s, length_slots, db.deadline_slot, needed_start, grid.total_slots):
                            candidates.append(s)

                    if candidates:
                        candidates.sort(key=lambda s: (abs(s - db.start_slot), s))
                        chosen_s = candidates[0]
                        grid.place_block(chosen_s, length_slots, db.task_id, db.title)
                        new_day, new_s_str = slot_to_day_time(chosen_s, is_end_time=False)
                        _, new_e_str = slot_to_day_time(chosen_s + length_slots, is_end_time=True)
                        db.day = new_day
                        db.start_time = new_s_str
                        db.end_time = new_e_str
                        db.start_slot = chosen_s
                        db.end_slot = chosen_s + length_slots
                        db.start_iso = slot_to_iso(chosen_s, week_start_iso=week_start_iso)
                        db.end_iso = slot_to_iso(chosen_s + length_slots, week_start_iso=week_start_iso)
                        prev_chunk_end = db.end_slot
                        cls._record_move_change(changes_by_id, initial_blocks, db)
                    else:
                        repaired_blocks.remove(db)
                        unplaced_tasks.append({
                            "task_id": db.task_id,
                            "title": db.title,
                            "duration_min": db.duration_min,
                            "priority": db.priority,
                            "deadline": db.deadline_str,
                            "deadline_slot": db.deadline_slot,
                            "reason": "Không đủ chỗ trống sau khi dời task tiên quyết (H5).",
                            "reason_code": "PREREQUISITE_SHIFT_OVERLOAD",
                        })
                        cls._record_unplaced_change(changes_by_id, initial_blocks, db)
                else:
                    prev_chunk_end = max(prev_chunk_end, db.end_slot)

    @classmethod
    def _repair_full_rebuild(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_schedule: ScheduleOutput,
        disruption: DisruptionEvent,
        algorithm: Optional[str] = None,
    ) -> RepairOutput:
        """Full Regeneration / Global Rebuild respecting the active scheduling algorithm."""
        t0 = time.perf_counter()
        week_start_iso = profile.planning_week_start
        d_start, d_end, _ = cls.resolve_disruption_slots(disruption, week_start_iso=week_start_iso)

        updated_profile = profile.model_copy(deep=True)
        updated_profile.fixed_events.append(
            FixedEvent(
                event_id=disruption.event_id,
                title=disruption.title,
                day_of_week=disruption.day_of_week,
                start_time=disruption.start_time,
                end_time=disruption.end_time,
                category="DISRUPTION_EVENT",
            )
        )
        updated_profile.now = slot_to_iso(d_end, week_start_iso=week_start_iso)

        original_blocks = [b.model_copy(deep=True) for b in current_schedule.blocks]
        pinned_blocks = [
            b for b in original_blocks
            if b.state in ("PINNED", "DONE") and (b.end_slot <= d_start or b.start_slot >= d_end)
        ]

        eff_algo = algorithm or getattr(current_schedule, "solver_used", None) or "EDF"
        solver = resolve_solver(eff_algo)
        rebuilt_output, rebuilt_grid = solver.solve(updated_profile, tasks, pinned_blocks=pinned_blocks)

        rebuilt_map = {(b.task_id, b.chunk_index): b for b in rebuilt_output.blocks}
        changes: List[RepairChange] = []
        for ob in original_blocks:
            rb = rebuilt_map.get((ob.task_id, ob.chunk_index))
            if rb is None:
                changes.append(
                    RepairChange(
                        block_id=ob.block_id,
                        task_id=ob.task_id,
                        title=ob.title,
                        old_day=ob.day,
                        old_start_time=ob.start_time,
                        old_end_time=ob.end_time,
                        old_start_slot=ob.start_slot,
                        old_end_slot=ob.end_slot,
                        status="UNPLACED",
                    )
                )
            elif (rb.start_slot, rb.end_slot) != (ob.start_slot, ob.end_slot):
                changes.append(
                    RepairChange(
                        block_id=ob.block_id,
                        task_id=ob.task_id,
                        title=ob.title,
                        old_day=ob.day,
                        old_start_time=ob.start_time,
                        old_end_time=ob.end_time,
                        old_start_slot=ob.start_slot,
                        old_end_slot=ob.end_slot,
                        new_day=rb.day,
                        new_start_time=rb.start_time,
                        new_end_time=rb.end_time,
                        new_start_slot=rb.start_slot,
                        new_end_slot=rb.end_slot,
                        status="MOVED",
                    )
                )

        exec_ms = (time.perf_counter() - t0) * 1000.0
        return cls._build_repair_output(
            mode_name="FULL_REBUILD",
            profile=updated_profile,
            grid=rebuilt_grid,
            tasks=tasks,
            original_blocks=original_blocks,
            repaired_blocks=rebuilt_output.blocks,
            unplaced_tasks=rebuilt_output.unplaced_tasks,
            changes=changes,
            d_start=d_start,
            d_end=d_end,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
        )

    @classmethod
    def _repair_ripple_shift(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_schedule: ScheduleOutput,
        disruption: DisruptionEvent,
    ) -> RepairOutput:
        """Fix A6 #4: Ripple-Shift enforces now_slot and post-move topological dependency order."""
        t0 = time.perf_counter()
        week_start_iso = profile.planning_week_start
        d_start, d_end, now_slot = cls.resolve_disruption_slots(disruption, week_start_iso=week_start_iso)
        horizon_slots = BaseScheduler.resolve_horizon_slots(
            tasks,
            week_start_iso=week_start_iso,
            horizon_days=getattr(profile, "horizon_days", 7),
        )

        updated_profile = profile.model_copy(deep=True)
        updated_profile.fixed_events.append(
            FixedEvent(
                event_id=disruption.event_id,
                title=disruption.title,
                day_of_week=disruption.day_of_week,
                start_time=disruption.start_time,
                end_time=disruption.end_time,
                category="DISRUPTION_EVENT",
            )
        )

        grid = TimeGridManager(total_slots=horizon_slots)
        grid.initialize_from_profile(updated_profile)

        original_blocks = sorted(
            [b.model_copy(deep=True) for b in current_schedule.blocks],
            key=lambda x: x.start_slot,
        )
        initial_blocks: Dict[str, ScheduleBlock] = {b.block_id: b.model_copy(deep=True) for b in original_blocks}

        repaired_blocks: List[ScheduleBlock] = []
        unplaced_tasks: List[Dict[str, Any]] = [dict(u) for u in current_schedule.unplaced_tasks]
        changes_by_id: Dict[str, RepairChange] = {}

        # Lock non-overlapping PINNED / DONE blocks first
        pinned_ids = set()
        for ob in original_blocks:
            if ob.state in ("PINNED", "DONE") and (ob.end_slot <= d_start or ob.start_slot >= d_end):
                length = ob.end_slot - ob.start_slot
                if grid.is_range_free(ob.start_slot, length):
                    grid.place_block(ob.start_slot, length, ob.task_id, ob.title)
                    repaired_blocks.append(ob)
                    pinned_ids.add(ob.block_id)

        cursor_slot = 0
        for ob in original_blocks:
            if ob.block_id in pinned_ids:
                cursor_slot = max(cursor_slot, ob.end_slot)
                continue
            length_slots = ob.end_slot - ob.start_slot
            if ob.end_slot <= d_start and grid.is_range_free(ob.start_slot, length_slots):
                grid.place_block(ob.start_slot, length_slots, ob.task_id, ob.title)
                repaired_blocks.append(ob)
                cursor_slot = max(cursor_slot, ob.end_slot)
                continue

            search_from = max(ob.start_slot, cursor_slot, now_slot)
            eff_deadline = (
                min(ob.deadline_slot, grid.total_slots)
                if ob.deadline_slot is not None
                else grid.total_slots
            )
            chosen_s = None
            for s in range(search_from, eff_deadline - length_slots + 1):
                if grid.can_place_chunk(s, length_slots, ob.deadline_slot, search_from, grid.total_slots):
                    chosen_s = s
                    break

            if chosen_s is not None:
                grid.place_block(chosen_s, length_slots, ob.task_id, ob.title)
                cursor_slot = chosen_s + length_slots
                if chosen_s != ob.start_slot:
                    new_day, new_s_str = slot_to_day_time(chosen_s, is_end_time=False)
                    _, new_e_str = slot_to_day_time(chosen_s + length_slots, is_end_time=True)
                    moved_b = ob.model_copy(deep=True)
                    moved_b.day = new_day
                    moved_b.start_time = new_s_str
                    moved_b.end_time = new_e_str
                    moved_b.start_slot = chosen_s
                    moved_b.end_slot = chosen_s + length_slots
                    moved_b.start_iso = slot_to_iso(chosen_s, week_start_iso=week_start_iso)
                    moved_b.end_iso = slot_to_iso(chosen_s + length_slots, week_start_iso=week_start_iso)
                    moved_b.reason = f"[Ripple-Shift] Đẩy dây chuyền từ {ob.day} {ob.start_time}."
                    repaired_blocks.append(moved_b)
                    cls._record_move_change(changes_by_id, initial_blocks, moved_b)
                else:
                    repaired_blocks.append(ob)
            else:
                unplaced_tasks.append({
                    "task_id": ob.task_id,
                    "title": ob.title,
                    "duration_min": ob.duration_min,
                    "priority": ob.priority,
                    "deadline": ob.deadline_str,
                    "deadline_slot": ob.deadline_slot,
                    "reason": f"Đẩy dây chuyền vượt quá hạn chót {ob.deadline_str}.",
                })
                cls._record_unplaced_change(changes_by_id, initial_blocks, ob)

        # Enforce H5 post-move dependencies
        cls._enforce_post_move_dependencies(
            grid=grid,
            tasks=tasks,
            repaired_blocks=repaired_blocks,
            changes_by_id=changes_by_id,
            initial_blocks=initial_blocks,
            unplaced_tasks=unplaced_tasks,
            now_slot=now_slot,
            week_start_iso=week_start_iso,
        )

        exec_ms = (time.perf_counter() - t0) * 1000.0
        return cls._build_repair_output(
            mode_name="RIPPLE_SHIFT",
            profile=updated_profile,
            grid=grid,
            tasks=tasks,
            original_blocks=original_blocks,
            repaired_blocks=repaired_blocks,
            unplaced_tasks=unplaced_tasks,
            changes=list(changes_by_id.values()),
            d_start=d_start,
            d_end=d_end,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
        )

    @classmethod
    def repair_overrun(
        cls,
        profile: CommitmentsProfile,
        updated_tasks: List[Task],
        current_schedule: ScheduleOutput,
        target_task_id: str,
        now_slot: Optional[int] = None,
    ) -> RepairOutput:
        """
        Fix A9: Local Repair for Task Overrun (Pattern 8 stability >= 90%).
        Freezes unaffected blocks across the week; extends/re-inserts only `target_task_id`
        and relocates any directly colliding future non-pinned blocks via Local Insertion + Unfreezing.
        """
        t0 = time.perf_counter()
        week_start_iso = profile.planning_week_start
        horizon_slots = BaseScheduler.resolve_horizon_slots(
            updated_tasks,
            week_start_iso=week_start_iso,
            horizon_days=getattr(profile, "horizon_days", 7),
        )
        resolved_now = BaseScheduler.resolve_now_slot(profile) if now_slot is None else now_slot

        grid = TimeGridManager(total_slots=horizon_slots)
        grid.initialize_from_profile(profile)
        grid.mark_dead_zones_as_rest()

        task_map: Dict[str, Task] = {t.task_id: t for t in updated_tasks}
        original_blocks = [b.model_copy(deep=True) for b in current_schedule.blocks]
        initial_blocks: Dict[str, ScheduleBlock] = {b.block_id: b.model_copy(deep=True) for b in original_blocks}

        old_target_blocks = sorted(
            [b for b in original_blocks if b.task_id == target_task_id],
            key=lambda b: b.chunk_index,
        )
        other_blocks = [b.model_copy(deep=True) for b in original_blocks if b.task_id != target_task_id]
        locked_other_blocks = [b for b in other_blocks if b.state in ("PINNED", "DONE")]
        flexible_other_blocks = [b for b in other_blocks if b.state not in ("PINNED", "DONE")]

        target_task = task_map.get(target_task_id)
        if target_task is None:
            for ob in original_blocks:
                grid.place_block(ob.start_slot, ob.end_slot - ob.start_slot, ob.task_id, ob.title)
            exec_ms = (time.perf_counter() - t0) * 1000.0
            return cls._build_repair_output(
                mode_name="LOCAL_INSERTION",
                profile=profile,
                grid=grid,
                tasks=updated_tasks,
                original_blocks=original_blocks,
                repaired_blocks=original_blocks,
                unplaced_tasks=list(current_schedule.unplaced_tasks),
                changes=[],
                d_start=0,
                d_end=0,
                exec_ms=exec_ms,
                week_start_iso=week_start_iso,
            )

        repaired_blocks: List[ScheduleBlock] = []
        # Pin Guard: reserve PINNED/DONE blocks first so overrun extension never overwrites locked blocks
        for lb in sorted(locked_other_blocks, key=lambda b: b.start_slot):
            length = lb.end_slot - lb.start_slot
            if grid.is_range_free(lb.start_slot, length):
                grid.place_block(lb.start_slot, length, lb.task_id, lb.title)
            repaired_blocks.append(lb)

        # Anchor at original first start (or resolved_now if unplaced)
        anchor_start = old_target_blocks[0].start_slot if old_target_blocks else resolved_now
        # Place expanded chunks of `target_task` around locked blocks, evicting only flexible future blocks
        new_chunks = BaseScheduler.split_task_into_chunks(target_task, week_start_iso=week_start_iso)
        desired_slots: List[Tuple[Any, int]] = []
        cursor = anchor_start
        for ch in new_chunks:
            d_cap = min(ch.deadline_slot, grid.total_slots) if ch.deadline_slot is not None else grid.total_slots
            cands = BaseScheduler.find_valid_start_slots(grid, ch.duration_slots, cursor, d_cap)
            if not cands:
                cands = BaseScheduler.find_valid_start_slots(grid, ch.duration_slots, resolved_now, d_cap)
            if cands:
                chosen = cands[0]
                grid.place_block(chosen, ch.duration_slots, ch.task_id, ch.title)
                desired_slots.append((ch, chosen))
                cursor = chosen + ch.duration_slots

        unplaced_tasks: List[Dict[str, Any]] = [
            dict(u) for u in current_schedule.unplaced_tasks if u.get("task_id") != target_task_id
        ]
        changes_by_id: Dict[str, RepairChange] = {}

        new_target_blocks: List[ScheduleBlock] = []
        if len(desired_slots) < len(new_chunks):
            for ch, s_pos in desired_slots:
                grid.remove_block(s_pos, ch.duration_slots)
            unplaced_tasks.append({
                "task_id": target_task.task_id,
                "title": target_task.title,
                "duration_min": target_task.get_planned_duration_min(),
                "priority": target_task.priority,
                "deadline": target_task.format_deadline_label(week_start_iso=week_start_iso),
                "deadline_slot": target_task.resolve_deadline_slot(week_start_iso=week_start_iso),
                "reason": (
                    f"Không đủ khe trống trước hạn chót (sau khi tôn trọng block đã ghim/khóa) "
                    f"để mở rộng '{target_task.title}' lên {target_task.get_planned_duration_min()}p."
                ),
                "reason_code": "OVERRUN_OVERLOAD",
            })
            for ob_old in old_target_blocks:
                cls._record_unplaced_change(changes_by_id, initial_blocks, ob_old)
        else:
            for ch, s_pos in desired_slots:
                new_target_blocks.append(
                    BaseScheduler.build_schedule_block(
                        chunk=ch,
                        start_slot=s_pos,
                        reason_text=f"[Overrun Local Repair] Điều chỉnh thời lượng '{ch.title}' lên {target_task.get_planned_duration_min()}p.",
                        reason_codes=[{"code": "OVERRUN_EXTENSION", "text": "Cập nhật thời lượng thực tế vượt dự kiến"}],
                        week_start_iso=week_start_iso,
                        state="ACCEPTED",
                    )
                )
            repaired_blocks.extend(new_target_blocks)
            for nb in new_target_blocks:
                if nb.block_id in initial_blocks:
                    cls._record_move_change(changes_by_id, initial_blocks, nb)

        # Freeze unaffected non-colliding flexible blocks; collect directly bumped future blocks
        bumped_blocks: List[ScheduleBlock] = []
        for ob in sorted(flexible_other_blocks, key=lambda b: b.start_slot):
            length = ob.end_slot - ob.start_slot
            if grid.is_range_free(ob.start_slot, length):
                grid.place_block(ob.start_slot, length, ob.task_id, ob.title)
                repaired_blocks.append(ob)
            else:
                bumped_blocks.append(ob)

        for bb in sorted(bumped_blocks, key=lambda b: (-b.priority, b.start_slot)):
            cand = cls._find_nearest_valid_slot(grid, bb, repaired_blocks, task_map, resolved_now)
            if cand is not None:
                length = bb.end_slot - bb.start_slot
                grid.place_block(cand, length, bb.task_id, bb.title)
                new_day, new_s_str = slot_to_day_time(cand, is_end_time=False)
                _, new_e_str = slot_to_day_time(cand + length, is_end_time=True)
                moved_b = bb.model_copy(deep=True)
                moved_b.day = new_day
                moved_b.start_time = new_s_str
                moved_b.end_time = new_e_str
                moved_b.start_slot = cand
                moved_b.end_slot = cand + length
                moved_b.start_iso = slot_to_iso(cand, week_start_iso=week_start_iso)
                moved_b.end_iso = slot_to_iso(cand + length, week_start_iso=week_start_iso)
                moved_b.reason = f"[Overrun Shift] Dời cục bộ để nhường thời lượng phát sinh cho '{target_task.title}'."
                repaired_blocks.append(moved_b)
                cls._record_move_change(changes_by_id, initial_blocks, moved_b)
            else:
                rescued = cls._try_progressive_unfreeze(
                    grid=grid,
                    target_block=bb,
                    repaired_blocks=repaired_blocks,
                    task_map=task_map,
                    now_slot=resolved_now,
                    week_start_iso=week_start_iso,
                    initial_blocks=initial_blocks,
                    changes_by_id=changes_by_id,
                    unplaced_tasks=unplaced_tasks,
                    event_title=f"Overrun {target_task.title}",
                )
                if rescued is None:
                    unplaced_tasks.append({
                        "task_id": bb.task_id,
                        "title": bb.title,
                        "duration_min": bb.duration_min,
                        "priority": bb.priority,
                        "deadline": bb.deadline_str,
                        "deadline_slot": bb.deadline_slot,
                        "reason": f"Không còn chỗ trống sau khi '{target_task.title}' kéo dài thêm thời gian.",
                        "reason_code": "OVERRUN_OVERLOAD",
                    })
                    cls._record_unplaced_change(changes_by_id, initial_blocks, bb)

        cls._enforce_post_move_dependencies(
            grid=grid,
            tasks=updated_tasks,
            repaired_blocks=repaired_blocks,
            changes_by_id=changes_by_id,
            initial_blocks=initial_blocks,
            unplaced_tasks=unplaced_tasks,
            now_slot=resolved_now,
            week_start_iso=week_start_iso,
        )

        # Disruption window is the extension range of target_task
        d_start = anchor_start
        d_end = max([b.end_slot for b in new_target_blocks], default=anchor_start)
        exec_ms = (time.perf_counter() - t0) * 1000.0
        return cls._build_repair_output(
            mode_name="LOCAL_INSERTION",
            profile=profile,
            grid=grid,
            tasks=updated_tasks,
            original_blocks=original_blocks,
            repaired_blocks=repaired_blocks,
            unplaced_tasks=unplaced_tasks,
            changes=list(changes_by_id.values()),
            d_start=d_start,
            d_end=d_end,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
        )

    @classmethod
    def _build_repair_output(
        cls,
        mode_name: str,
        profile: CommitmentsProfile,
        grid: TimeGridManager,
        tasks: List[Task],
        original_blocks: List[ScheduleBlock],
        repaired_blocks: List[ScheduleBlock],
        unplaced_tasks: List[Dict[str, Any]],
        changes: List[RepairChange],
        d_start: int,
        d_end: int,
        exec_ms: float,
        week_start_iso: str,
        extra_warnings: Optional[List[str]] = None,
    ) -> RepairOutput:
        stability_pct, total_unaff, unchanged_unaff, directly_hit = calculate_schedule_stability(
            original_blocks=original_blocks,
            repaired_blocks=repaired_blocks,
            disruption_start_slot=d_start,
            disruption_end_slot=d_end,
        )

        unplaced_ids = sorted(set(str(u.get("task_id", "")) for u in unplaced_tasks))
        hard_violations, violation_msgs = audit_hard_constraint_violations(
            grid, repaired_blocks, tasks, week_start_iso=week_start_iso
        )
        deadline_rate = calculate_deadline_satisfaction_rate(
            tasks, repaired_blocks, unplaced_ids, week_start_iso=week_start_iso
        )
        slot_counts = grid.get_slot_counts(up_to=SLOTS_PER_WEEK)
        frag_idx = calculate_fragmentation_index(grid, up_to=SLOTS_PER_WEEK)

        placed_task_ids = set(b.task_id for b in repaired_blocks) - set(unplaced_ids)
        tasks_placed = len(placed_task_ids)
        tasks_unplaced = len(tasks) - tasks_placed

        exp_rating, exp_label = calculate_experience_rating(
            grid_manager=grid,
            blocks=repaired_blocks,
            tasks=tasks,
            profile=profile,
            unplaced_count=tasks_unplaced,
        )

        # Fix A6 #5: Build OverloadReport whenever repair leaves unplaced blocks/tasks
        overload_reports: List[OverloadReport] = []
        if unplaced_tasks or tasks_unplaced > 0:
            overload_reports = BaseScheduler.check_deadline_capacity(
                grid, tasks, now_slot=0, week_start_iso=week_start_iso
            )
            if not overload_reports:
                first_u = unplaced_tasks[0] if unplaced_tasks else {}
                u_tid = str(first_u.get("task_id", "TASK"))
                free_min_total = slot_counts["FREE"] * MINUTES_PER_SLOT
                needed_min = sum(int(u.get("duration_min", 0)) for u in unplaced_tasks)
                overload_reports.append(
                    OverloadReport(
                        error_type="FRAGMENTATION_FAILURE",
                        type="NO_SCHEDULE_FOUND",
                        message=f"Không thể tái sắp xếp toàn bộ công việc sau gián đoạn ({u_tid}).",
                        deadline=str(first_u.get("deadline", "Trong tuần")),
                        deadline_slot=first_u.get("deadline_slot"),
                        total_free_minutes_available=free_min_total,
                        total_planned_work_minutes=needed_min,
                        shortage_minutes=max(0, needed_min - free_min_total),
                        unplaced_tasks=unplaced_ids,
                    )
                )

        ext_alerts = BaseScheduler.compute_early_extension_alerts(
            tasks=tasks,
            unplaced_tasks=unplaced_tasks,
            now_slot=0,
            week_start_iso=week_start_iso,
        )

        summary = ScheduleSummary(
            total_tasks_requested=len(tasks),
            tasks_placed=tasks_placed,
            tasks_unplaced=tasks_unplaced,
            parts_total=len(repaired_blocks) + len(unplaced_tasks),
            parts_placed=len(repaired_blocks),
            parts_unplaced=len(unplaced_tasks),
            hard_constraint_violations=hard_violations,
            deadline_satisfaction_rate=deadline_rate,
            free_slots_remaining=slot_counts["FREE"],
            occupied_slots=slot_counts["OCCUPIED"],
            sleep_slots=slot_counts["SLEEP"],
            block_slots=slot_counts["BLOCK"],
            rest_slots=slot_counts.get("REST", 0),
            fragmentation_index=frag_idx,
            experience_rating=exp_rating,
            experience_label=exp_label,
            early_extension_alerts=ext_alerts,
        )

        sorted_repaired = sorted(repaired_blocks, key=lambda b: (b.start_slot, b.task_id, b.chunk_index))
        det_hash = compute_determinism_hash(sorted_repaired, unplaced_tasks)
        status = "SUCCESS" if tasks_unplaced == 0 else "PARTIAL_OVERLOAD"
        all_warnings = list(grid.sleep_warnings) + list(extra_warnings or []) + violation_msgs

        schedule_out = ScheduleOutput(
            status=status,
            solver_used=f"REPAIR_{mode_name}",
            execution_time_ms=round(exec_ms, 4),
            determinism_hash=det_hash,
            summary=summary,
            blocks=sorted_repaired,
            unplaced_tasks=unplaced_tasks,
            overload_reports=overload_reports,
            overload=overload_reports[0] if overload_reports else None,
            warnings=all_warnings,
            grid_states=list(grid.grid[:grid.total_slots]),
        )
        OverloadTriageEngine.enrich_schedule_overload(schedule_out, profile, tasks)

        moved_count = sum(1 for c in changes if c.status == "MOVED")
        unplaced_count = sum(1 for c in changes if c.status == "UNPLACED")

        return RepairOutput(
            status=status,
            repair_mode=mode_name,
            execution_time_ms=round(exec_ms, 4),
            stability_score=stability_pct,
            total_unaffected_blocks=total_unaff,
            unchanged_unaffected_blocks=unchanged_unaff,
            directly_hit_blocks=directly_hit,
            moved_blocks_count=moved_count,
            unplaced_blocks_count=unplaced_count,
            changes=changes,
            schedule=schedule_out,
        )
