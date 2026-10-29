"""
Disruption & Rescheduling Engine (Module M4 - baseline_plan.md §5 & Proposal §6.3 Step 4).
Implements all three rescheduling mechanisms for comparative benchmarking:
  1. FULL_REBUILD (Global Regeneration): Clears all unstarted future blocks and re-runs the solver.
  2. RIPPLE_SHIFT (Push Delay): Pushes collided blocks forward in a chain while skipping SLEEP/OCCUPIED.
  3. LOCAL_INSERTION (Greedy Local Repair): Freezes 100% of unaffected blocks; moves ONLY blocks
     directly hit by the disruption to the nearest valid FREE slot (achieving >= 90% Schedule Stability).
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.metrics import (
    audit_hard_constraint_violations,
    calculate_deadline_satisfaction_rate,
    calculate_fragmentation_index,
    calculate_schedule_stability,
    compute_determinism_hash,
)
from src.models import (
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    RepairChange,
    RepairOutput,
    ScheduleBlock,
    ScheduleOutput,
    ScheduleSummary,
    Task,
)
from src.solvers.base_solver import BaseScheduler
from src.solvers.greedy_edf import GreedyEDFSolver
from src.utils import (
    MINUTES_PER_SLOT,
    SLOTS_PER_WEEK,
    day_time_to_slot,
    iso_to_slot,
    minutes_to_slots,
    slot_to_day_time,
    slot_to_iso,
)


class LocalRepairEngine:
    """Handles unexpected events (T04) and task duration overruns (T05) via Local Insertion or Full Rebuild."""

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
            # Default notification time: morning of the disruption day or d_start
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
    ) -> RepairOutput:
        """
        Execute schedule repair upon an unexpected disruption event.
        mode: 'LOCAL_INSERTION' (or 'LOCAL') | 'FULL_REBUILD' (or 'REBUILD') | 'RIPPLE_SHIFT'
        """
        mode_norm = mode.strip().upper()
        if mode_norm in ("LOCAL", "LOCAL_REPAIR", "LOCAL_INSERTION"):
            return cls._repair_local_insertion(profile, tasks, current_schedule, disruption)
        elif mode_norm in ("RIPPLE", "RIPPLE_SHIFT"):
            return cls._repair_ripple_shift(profile, tasks, current_schedule, disruption)
        else:
            return cls._repair_full_rebuild(profile, tasks, current_schedule, disruption)

    @classmethod
    def _repair_local_insertion(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_schedule: ScheduleOutput,
        disruption: DisruptionEvent,
    ) -> RepairOutput:
        """
        Solution 3 (Proposal §6.3 Step 4 & baseline_plan.md §5):
        1. Freeze all blocks NOT overlapping the new disruption event.
        2. Mark disruption slots as OCCUPIED.
        3. Relocate ONLY the overlapped blocks (and any dependent blocks that now violate H5)
           to the FREE run nearest to their old start time, not earlier than `now_slot`.
        """
        t0 = time.perf_counter()
        week_start_iso = profile.planning_week_start
        d_start, d_end, now_slot = cls.resolve_disruption_slots(disruption, week_start_iso=week_start_iso)

        # Build updated profile with the disruption event locked as a fixed commitment
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

        grid = TimeGridManager(total_slots=SLOTS_PER_WEEK)
        grid.initialize_from_profile(updated_profile)

        task_map: Dict[str, Task] = {t.task_id: t for t in tasks}
        original_blocks = [b.model_copy(deep=True) for b in current_schedule.blocks]

        # Separate unaffected vs directly hit blocks
        frozen_blocks: List[ScheduleBlock] = []
        affected_blocks: List[ScheduleBlock] = []

        for b in original_blocks:
            overlaps = not (b.end_slot <= d_start or b.start_slot >= d_end)
            if overlaps:
                affected_blocks.append(b)
            else:
                frozen_blocks.append(b)

        # Lock all frozen blocks onto the grid
        for fb in frozen_blocks:
            length_slots = fb.end_slot - fb.start_slot
            if grid.is_range_free(fb.start_slot, length_slots):
                grid.place_block(fb.start_slot, length_slots, fb.task_id, fb.title)

        # Sort affected blocks: higher priority first, earlier deadline first, earlier old start first
        affected_blocks.sort(
            key=lambda b: (-b.priority, b.deadline_slot if b.deadline_slot is not None else 999999, b.start_slot)
        )

        repaired_blocks: List[ScheduleBlock] = list(frozen_blocks)
        unplaced_tasks: List[Dict[str, Any]] = list(current_schedule.unplaced_tasks)
        changes: List[RepairChange] = []

        for b in affected_blocks:
            length_slots = b.end_slot - b.start_slot
            t_obj = task_map.get(b.task_id)

            # Determine earliest valid start slot respecting `now_slot`, prerequisites (`depends_on`), and earlier chunks of same task
            earliest_start = max(now_slot, 0)
            if t_obj and t_obj.depends_on:
                for pid in t_obj.depends_on:
                    prereq_ends = [
                        rb.end_slot for rb in repaired_blocks if rb.task_id == pid
                    ]
                    if prereq_ends:
                        earliest_start = max(earliest_start, max(prereq_ends))

            same_task_earlier_ends = [
                rb.end_slot
                for rb in repaired_blocks
                if rb.task_id == b.task_id and rb.chunk_index < b.chunk_index
            ]
            if same_task_earlier_ends:
                earliest_start = max(earliest_start, max(same_task_earlier_ends))

            # Also check if a later chunk or dependent task is frozen; if we can fit before it, great;
            # otherwise we just respect the task's own deadline_slot.
            eff_deadline = min(b.deadline_slot, SLOTS_PER_WEEK) if b.deadline_slot is not None else SLOTS_PER_WEEK

            # Find all valid start positions in [earliest_start, eff_deadline - length_slots]
            candidates: List[int] = []
            for s in range(earliest_start, eff_deadline - length_slots + 1):
                if grid.can_place_chunk(
                    start_slot=s,
                    length_slots=length_slots,
                    deadline_slot=b.deadline_slot,
                    earliest_start_slot=earliest_start,
                    max_grid_slot=SLOTS_PER_WEEK,
                ):
                    candidates.append(s)

            if candidates:
                # Choose the slot nearest to old start_slot; tie-break by earlier slot
                candidates.sort(key=lambda s: (abs(s - b.start_slot), s))
                new_start = candidates[0]
                new_end = new_start + length_slots
                grid.place_block(new_start, length_slots, b.task_id, b.title)

                new_day, new_start_str = slot_to_day_time(new_start, is_end_time=False)
                _, new_end_str = slot_to_day_time(new_end, is_end_time=True)

                moved_b = b.model_copy(deep=True)
                moved_b.day = new_day
                moved_b.start_time = new_start_str
                moved_b.end_time = new_end_str
                moved_b.start_slot = new_start
                moved_b.end_slot = new_end
                moved_b.start_iso = slot_to_iso(new_start, week_start_iso=week_start_iso)
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

                changes.append(
                    RepairChange(
                        block_id=b.block_id,
                        task_id=b.task_id,
                        title=b.title,
                        old_day=b.day,
                        old_start_time=b.start_time,
                        old_end_time=b.end_time,
                        old_start_slot=b.start_slot,
                        old_end_slot=b.end_slot,
                        new_day=new_day,
                        new_start_time=new_start_str,
                        new_end_time=new_end_str,
                        new_start_slot=new_start,
                        new_end_slot=new_end,
                        status="MOVED",
                    )
                )
            else:
                # Could not relocate locally without violating hard constraints -> mark unplaced
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
                })
                changes.append(
                    RepairChange(
                        block_id=b.block_id,
                        task_id=b.task_id,
                        title=b.title,
                        old_day=b.day,
                        old_start_time=b.start_time,
                        old_end_time=b.end_time,
                        old_start_slot=b.start_slot,
                        old_end_slot=b.end_slot,
                        status="UNPLACED",
                    )
                )

        # Ensure H5 dependent tasks in frozen_blocks still start after relocated prerequisites;
        # if a prerequisite moved after a frozen dependent block, relocate that dependent block too!
        cls._enforce_post_move_dependencies(
            grid, tasks, repaired_blocks, changes, unplaced_tasks, now_slot, week_start_iso
        )

        exec_ms = (time.perf_counter() - t0) * 1000.0
        return cls._build_repair_output(
            mode_name="LOCAL_INSERTION",
            grid=grid,
            tasks=tasks,
            original_blocks=original_blocks,
            repaired_blocks=repaired_blocks,
            unplaced_tasks=unplaced_tasks,
            changes=changes,
            d_start=d_start,
            d_end=d_end,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
        )

    @classmethod
    def _enforce_post_move_dependencies(
        cls,
        grid: TimeGridManager,
        tasks: List[Task],
        repaired_blocks: List[ScheduleBlock],
        changes: List[RepairChange],
        unplaced_tasks: List[Dict[str, Any]],
        now_slot: int,
        week_start_iso: str,
    ) -> None:
        """If moving an affected block caused it to finish after a dependent task starts, shift the dependent block."""
        task_map = {t.task_id: t for t in tasks}
        for t in tasks:
            if not t.depends_on:
                continue
            prereq_ends = [
                rb.end_slot for rb in repaired_blocks if rb.task_id in t.depends_on
            ]
            if not prereq_ends:
                continue
            req_start = max(prereq_ends)
            dep_blocks = [rb for rb in repaired_blocks if rb.task_id == t.task_id]
            for db in dep_blocks:
                if db.start_slot < req_start:
                    # Must relocate db to start >= req_start
                    length_slots = db.end_slot - db.start_slot
                    grid.remove_block(db.start_slot, length_slots)
                    eff_deadline = (
                        min(db.deadline_slot, SLOTS_PER_WEEK)
                        if db.deadline_slot is not None
                        else SLOTS_PER_WEEK
                    )
                    chosen_s = None
                    for s in range(max(now_slot, req_start), eff_deadline - length_slots + 1):
                        if grid.can_place_chunk(s, length_slots, db.deadline_slot, req_start, SLOTS_PER_WEEK):
                            chosen_s = s
                            break
                    old_day, old_start_str, old_end_str = db.day, db.start_time, db.end_time
                    old_s, old_e = db.start_slot, db.end_slot
                    if chosen_s is not None:
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
                        changes.append(
                            RepairChange(
                                block_id=db.block_id,
                                task_id=db.task_id,
                                title=db.title,
                                old_day=old_day,
                                old_start_time=old_start_str,
                                old_end_time=old_end_str,
                                old_start_slot=old_s,
                                old_end_slot=old_e,
                                new_day=new_day,
                                new_start_time=new_s_str,
                                new_end_time=new_e_str,
                                new_start_slot=chosen_s,
                                new_end_slot=chosen_s + length_slots,
                                status="MOVED",
                            )
                        )
                    else:
                        repaired_blocks.remove(db)
                        unplaced_tasks.append({
                            "task_id": db.task_id,
                            "title": db.title,
                            "duration_min": db.duration_min,
                            "priority": db.priority,
                            "deadline": db.deadline_str,
                            "deadline_slot": db.deadline_slot,
                            "reason": "Không đủ chỗ trống sau khi dời task phụ thuộc.",
                        })

    @classmethod
    def _repair_full_rebuild(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_schedule: ScheduleOutput,
        disruption: DisruptionEvent,
    ) -> RepairOutput:
        """
        Solution 1 (baseline_plan.md §5): Full Regeneration / Global Rebuild.
        Adds the disruption event and re-runs the solver from `now_slot` for all non-pinned tasks.
        """
        t0 = time.perf_counter()
        week_start_iso = profile.planning_week_start
        d_start, d_end, now_slot = cls.resolve_disruption_slots(disruption, week_start_iso=week_start_iso)

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
        # In Full Rebuild (baseline_plan.md §5.1), when an event disrupts the schedule,
        # the global rebuild re-runs from the disruption end (or `now_slot`), causing downstream shifts.
        updated_profile.now = slot_to_iso(d_end, week_start_iso=week_start_iso)

        original_blocks = [b.model_copy(deep=True) for b in current_schedule.blocks]
        pinned_blocks = [
            b for b in original_blocks if b.state == "PINNED" and (b.end_slot <= d_start or b.start_slot >= d_end)
        ]

        solver = GreedyEDFSolver()
        rebuilt_output, rebuilt_grid = solver.solve(updated_profile, tasks, pinned_blocks=pinned_blocks)

        # Compute diff changes between original_blocks and rebuilt_output.blocks
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
        """
        Solution 2 (baseline_plan.md §5.2): Ripple-Shift / Push Delay.
        Preserves the exact sequence of scheduled blocks from `d_start` onward by pushing them
        sequentially into available free slots after `d_end`.
        """
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

        grid = TimeGridManager(total_slots=SLOTS_PER_WEEK)
        grid.initialize_from_profile(updated_profile)

        original_blocks = sorted(
            [b.model_copy(deep=True) for b in current_schedule.blocks],
            key=lambda x: x.start_slot,
        )

        repaired_blocks: List[ScheduleBlock] = []
        unplaced_tasks: List[Dict[str, Any]] = list(current_schedule.unplaced_tasks)
        changes: List[RepairChange] = []

        cursor_slot = 0
        for ob in original_blocks:
            length_slots = ob.end_slot - ob.start_slot
            if ob.end_slot <= d_start and grid.is_range_free(ob.start_slot, length_slots):
                grid.place_block(ob.start_slot, length_slots, ob.task_id, ob.title)
                repaired_blocks.append(ob)
                cursor_slot = max(cursor_slot, ob.end_slot)
                continue

            # Must place at or after max(ob.start_slot, cursor_slot)
            search_from = max(ob.start_slot, cursor_slot)
            eff_deadline = (
                min(ob.deadline_slot, SLOTS_PER_WEEK)
                if ob.deadline_slot is not None
                else SLOTS_PER_WEEK
            )
            chosen_s = None
            for s in range(search_from, eff_deadline - length_slots + 1):
                if grid.can_place_chunk(s, length_slots, ob.deadline_slot, search_from, SLOTS_PER_WEEK):
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
                            new_day=new_day,
                            new_start_time=new_s_str,
                            new_end_time=new_e_str,
                            new_start_slot=chosen_s,
                            new_end_slot=chosen_s + length_slots,
                            status="MOVED",
                        )
                    )
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

        exec_ms = (time.perf_counter() - t0) * 1000.0
        return cls._build_repair_output(
            mode_name="RIPPLE_SHIFT",
            grid=grid,
            tasks=tasks,
            original_blocks=original_blocks,
            repaired_blocks=repaired_blocks,
            unplaced_tasks=unplaced_tasks,
            changes=changes,
            d_start=d_start,
            d_end=d_end,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
        )

    @classmethod
    def _build_repair_output(
        cls,
        mode_name: str,
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
            fragmentation_index=frag_idx,
        )

        sorted_repaired = sorted(repaired_blocks, key=lambda b: (b.start_slot, b.task_id, b.chunk_index))
        det_hash = compute_determinism_hash(sorted_repaired, unplaced_tasks)
        status = "SUCCESS" if tasks_unplaced == 0 else "PARTIAL_OVERLOAD"

        schedule_out = ScheduleOutput(
            status=status,
            solver_used=f"REPAIR_{mode_name}",
            execution_time_ms=round(exec_ms, 4),
            determinism_hash=det_hash,
            summary=summary,
            blocks=sorted_repaired,
            unplaced_tasks=unplaced_tasks,
            overload_reports=[],
            overload=None,
            warnings=violation_msgs,
            grid_states=list(grid.grid[:SLOTS_PER_WEEK]),
        )

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

