"""
Tier 0: Gate Context Evaluation — G1 (Hard Feasibility & Pin Integrity) and G2 (Load Tightness Context).

References:
  - Schaerf (1999) §1.1–1.2 (tr. 1–3), §5.1 (tr. 29)
  - Myers et al. (2006) SPARK feasibility (tr. 5)
  - Gombolay (2017) §3.2.1 bounds (tr. 78–80), §3.4.1 bottlenecks (tr. 96–98), Ch. 5–6 mixed-initiative
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from schedule_testing_system.schemas import GateContextMetrics
from schedule_testing_system.sut_adapter import (
    BaseScheduler,
    CommitmentsProfile,
    ScheduleBlock,
    ScheduleOutput,
    Task,
    TimeGridManager,
    audit_hard_constraint_violations,
    build_base_grid,
    round_up_to_15,
)


def evaluate_gates(
    profile: CommitmentsProfile,
    prepared_tasks: List[Task],
    schedule: ScheduleOutput,
    horizon_slots: int,
    input_pinned_blocks: Optional[List[ScheduleBlock]] = None,
    is_overrun_context: bool = False,
) -> Tuple[GateContextMetrics, TimeGridManager]:
    """
    Evaluate Tier 0 Gates G1 & G2 on defensive copies.
    Returns `(GateContextMetrics, fresh_base_grid)` without mutating inputs.
    """
    week_start_iso = profile.planning_week_start
    now_slot = BaseScheduler.resolve_now_slot(profile)
    base_grid = build_base_grid(profile, horizon_slots)
    blocks = list(schedule.blocks)
    unplaced_ids = {str(u.get("task_id", "")) for u in schedule.unplaced_tasks}
    task_map: Dict[str, Task] = {t.task_id: t for t in prepared_tasks}

    # G1.0: Existing SmartSchedule H1-H5 audit
    h1_h5_count, details = audit_hard_constraint_violations(
        grid_manager=base_grid,
        blocks=blocks,
        tasks=prepared_tasks,
        week_start_iso=week_start_iso,
    )
    violation_details = list(details)

    # G1 Supplementary 1: start_after lower bound (excluding DONE / valid user PINNED)
    start_after_v = 0
    for b in blocks:
        if b.state in ("DONE", "PINNED"):
            continue
        t_obj = task_map.get(b.task_id)
        if t_obj is None:
            continue
        sa_slot = t_obj.resolve_start_after_slot(week_start_iso=week_start_iso)
        if sa_slot is not None and b.start_slot < sa_slot:
            start_after_v += 1
            violation_details.append(
                f"G1_START_AFTER: Block {b.block_id} starts at {b.start_slot} < start_after {sa_slot}."
            )

    # G1 Supplementary 2: now_slot boundary (excluding DONE / PINNED)
    before_now_v = 0
    for b in blocks:
        if b.state in ("DONE", "PINNED"):
            continue
        if b.start_slot < now_slot:
            before_now_v += 1
            violation_details.append(
                f"G1_BEFORE_NOW: Block {b.block_id} starts at {b.start_slot} < now_slot {now_slot}."
            )

    # G1 Supplementary 3 & 4: Splitting rules, chunk ordering, and planned duration completeness
    blocks_by_task: Dict[str, List[ScheduleBlock]] = {}
    for b in blocks:
        blocks_by_task.setdefault(b.task_id, []).append(b)

    splitting_v = 0
    duration_v = 0
    for tid, t_blocks in blocks_by_task.items():
        t_obj = task_map.get(tid)
        if t_obj is None:
            continue

        sorted_tb = sorted(t_blocks, key=lambda x: (x.chunk_index, x.start_slot))
        if not t_obj.is_splittable and len(sorted_tb) > 1 and not is_overrun_context:
            splitting_v += 1
            violation_details.append(
                f"G1_UNSPLITTABLE_SPLIT: Unsplittable task {tid} was split into {len(sorted_tb)} blocks."
            )

        for i in range(len(sorted_tb) - 1):
            cur_b, nxt_b = sorted_tb[i], sorted_tb[i + 1]
            if cur_b.end_slot > nxt_b.start_slot or cur_b.chunk_index >= nxt_b.chunk_index:
                splitting_v += 1
                violation_details.append(
                    f"G1_CHUNK_ORDER: Task {tid} chunk ordering broken between {cur_b.block_id} and {nxt_b.block_id}."
                )

        if t_obj.is_splittable and len(sorted_tb) > 1 and not is_overrun_context:
            max_chunk = max(15, round_up_to_15(t_obj.max_chunk_min or 90))
            expected_chunks = BaseScheduler.split_task_into_chunks(t_obj, week_start_iso=week_start_iso)
            expected_mins = {ch.duration_min for ch in expected_chunks}
            min_chunk = max(15, round_up_to_15(t_obj.min_chunk_min or 45))
            for ch_b in sorted_tb:
                if ch_b.state in ("PINNED", "DONE"):
                    continue
                if ch_b.duration_min > max_chunk:
                    splitting_v += 1
                    violation_details.append(
                        f"G1_CHUNK_MAX: Block {ch_b.block_id} duration {ch_b.duration_min}m > max_chunk {max_chunk}m."
                    )
                elif ch_b.duration_min < min_chunk and ch_b.duration_min not in expected_mins:
                    splitting_v += 1
                    violation_details.append(
                        f"G1_CHUNK_MIN: Block {ch_b.block_id} duration {ch_b.duration_min}m < min_chunk {min_chunk}m."
                    )

        if not is_overrun_context and tid not in unplaced_ids:
            placed_min = sum(b.duration_min for b in sorted_tb)
            planned_min = t_obj.get_planned_duration_min()
            if placed_min != planned_min:
                duration_v += 1
                violation_details.append(
                    f"G1_DURATION_MISMATCH: Task {tid} placed={placed_min}m != planned={planned_min}m."
                )

    # G1 Supplementary 5: Pin Integrity (valid input PINNED blocks must remain at exact slot)
    pin_v = 0
    pin_total_valid = 0
    pin_preserved = 0
    pinned_slots_by_task: Dict[str, int] = {}
    if input_pinned_blocks:
        accepted_pins, pinned_slots_by_task, _, _ = BaseScheduler.prepare_pinned_blocks(
            base_grid.clone(),
            prepared_tasks,
            input_pinned_blocks,
            now_slot,
            week_start_iso,
        )
        pin_total_valid = len(accepted_pins)
        out_block_spans = {
            (b.task_id, b.start_slot, b.end_slot)
            for b in blocks
            if b.state in ("PINNED", "DONE")
        }
        for pb in accepted_pins:
            if (pb.task_id, pb.start_slot, pb.end_slot) in out_block_spans:
                pin_preserved += 1
            else:
                pin_v += 1
                violation_details.append(
                    f"G1_PIN_VIOLATED: Valid PINNED block {pb.block_id} ({pb.start_slot}..{pb.end_slot}) altered or dropped."
                )

    g1_total = h1_h5_count + start_after_v + before_now_v + splitting_v + duration_v + pin_v

    # G2: Structural Load Tightness rho
    past_due = BaseScheduler.detect_past_due_tasks(prepared_tasks, week_start_iso=week_start_iso)
    valid_tasks = [t for t in prepared_tasks if t.task_id not in past_due]

    deadline_tasks: List[Task] = []
    habit_tasks: List[Task] = []
    for t in valid_tasks:
        d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
        if d_slot is not None:
            deadline_tasks.append(t)
        else:
            habit_tasks.append(t)

    # Subtract already-pinned slots before demand check against remaining free slots
    total_planned_slots = sum(t.get_planned_slots() for t in valid_tasks)
    deadline_planned_slots = sum(t.get_planned_slots() for t in deadline_tasks)
    habit_planned_slots = sum(t.get_planned_slots() for t in habit_tasks)

    remaining_total_slots = sum(
        max(0, t.get_planned_slots() - pinned_slots_by_task.get(t.task_id, 0)) for t in valid_tasks
    )
    remaining_deadline_slots = sum(
        max(0, t.get_planned_slots() - pinned_slots_by_task.get(t.task_id, 0)) for t in deadline_tasks
    )

    usable_free_horizon = base_grid.count_free_slots_in_range(start_from=now_slot, up_to=horizon_slots)
    deadline_caps = [
        min(horizon_slots, d_val)
        for t in deadline_tasks
        for d_val in [t.resolve_deadline_slot(week_start_iso=week_start_iso)]
        if d_val is not None
    ]
    max_d_slot = min(horizon_slots, max(deadline_caps)) if deadline_caps else horizon_slots
    usable_free_deadlines = base_grid.count_free_slots_in_range(start_from=now_slot, up_to=max_d_slot)

    eval_end_for_total = max_d_slot if (deadline_tasks and not habit_tasks) else horizon_slots
    usable_free_eval = base_grid.count_free_slots_in_range(start_from=now_slot, up_to=eval_end_for_total)

    rho_total = round(remaining_total_slots / float(max(1, usable_free_eval)), 4) if valid_tasks else 0.0
    rho_deadline = round(remaining_deadline_slots / float(max(1, usable_free_deadlines)), 4) if deadline_tasks else 0.0

    capacity_shortages = BaseScheduler.check_deadline_capacity(
        base_grid.clone(),
        valid_tasks,
        now_slot=now_slot,
        week_start_iso=week_start_iso,
        pinned_slots_by_task=pinned_slots_by_task,
    )
    is_structurally_overloaded = (rho_total > 1.0) or (rho_deadline > 1.0) or (len(capacity_shortages) > 0)

    metrics = GateContextMetrics(
        g1_total_violations=g1_total,
        g1_is_feasible=(g1_total == 0),
        g1_h1_h5_violations=h1_h5_count,
        g1_start_after_violations=start_after_v,
        g1_before_now_violations=before_now_v,
        g1_splitting_order_violations=splitting_v,
        g1_incomplete_duration_violations=duration_v,
        g1_pin_integrity_violations=pin_v,
        g1_pin_total_valid_input=pin_total_valid,
        g1_pin_preserved_count=pin_preserved,
        g1_violation_details=violation_details,
        horizon_slots=horizon_slots,
        now_slot=now_slot,
        total_valid_tasks=len(valid_tasks),
        deadline_tasks_count=len(deadline_tasks),
        habit_tasks_count=len(habit_tasks),
        total_planned_slots=total_planned_slots,
        deadline_planned_slots=deadline_planned_slots,
        habit_planned_slots=habit_planned_slots,
        usable_free_slots_horizon=usable_free_horizon,
        usable_free_slots_before_deadlines=usable_free_deadlines,
        rho_total=rho_total,
        rho_deadline=rho_deadline,
        is_structurally_overloaded=is_structurally_overloaded,
    )
    return metrics, base_grid
