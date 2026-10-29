"""
Quantitative Benchmark Metrics & Determinism Verification (baseline_plan.md §9.1).
Computes:
  1. Hard Constraint Violations (C_hard): Overlaps with SLEEP, OCCUPIED, other BLOCKs, Deadline misses, Dependency violations.
  2. Deadline Satisfaction Rate (R_deadline): % of tasks with deadlines completely placed on or before deadline.
  3. Execution Latency (T_exec): Measured in milliseconds using time.perf_counter().
  4. Schedule Stability (S_stability): % of unaffected blocks that remain at the exact same slot after a disruption.
  5. Fragmentation Index: % of remaining FREE slots stranded in short gaps (< 30 min / 2 slots).
  6. Determinism Hash: SHA-256 fingerprint of the output schedule to prove Pure Determinism.
"""

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.models import ScheduleBlock, Task
from src.utils import SLOTS_PER_WEEK


def audit_hard_constraint_violations(
    grid_manager: TimeGridManager,
    blocks: List[ScheduleBlock],
    tasks: List[Task],
    week_start_iso: str = "2026-11-02T00:00:00+07:00",
) -> Tuple[int, List[str]]:
    """
    Audit a generated schedule against all Hard Constraints H1-H5:
      - H1: Overlap with fixed commitment (OCCUPIED)
      - H2: Overlap with protected sleep (SLEEP)
      - H3: Two task blocks overlapping the same slot
      - H4: A block ending after its task deadline
      - H5: A task starting before a prerequisite task in `depends_on` finishes
    Returns (violation_count, details_list).
    """
    violations: List[str] = []
    violation_count = 0

    task_map: Dict[str, Task] = {t.task_id: t for t in tasks}
    slot_owner: Dict[int, str] = {}

    # Check H1, H2, H3, H4 per block
    for b in blocks:
        for s in range(b.start_slot, b.end_slot):
            if s < 0 or s >= grid_manager.total_slots:
                violation_count += 1
                violations.append(f"Out of bounds slot {s} in block {b.block_id}")
                continue

            locked_state = grid_manager._locked_mask[s]
            if locked_state == TimeGridManager.STATE_SLEEP:
                violation_count += 1
                violations.append(f"H2 Violation: Block {b.block_id} overlaps SLEEP at slot {s}")
            elif locked_state.startswith(TimeGridManager.STATE_OCCUPIED):
                violation_count += 1
                violations.append(f"H1 Violation: Block {b.block_id} overlaps {locked_state} at slot {s}")

            if s in slot_owner:
                violation_count += 1
                violations.append(f"H3 Violation: Block {b.block_id} overlaps block {slot_owner[s]} at slot {s}")
            else:
                slot_owner[s] = b.block_id

        # Check H4 deadline
        t_obj = task_map.get(b.task_id)
        d_slot = b.deadline_slot
        if d_slot is None and t_obj is not None:
            d_slot = t_obj.resolve_deadline_slot(week_start_iso=week_start_iso)
        if d_slot is not None and b.end_slot > d_slot:
            violation_count += 1
            violations.append(
                f"H4 Violation: Block {b.block_id} ends at slot {b.end_slot} after deadline slot {d_slot}"
            )

    # Check H5 dependency order
    task_blocks: Dict[str, List[ScheduleBlock]] = {}
    for b in blocks:
        task_blocks.setdefault(b.task_id, []).append(b)

    for t in tasks:
        if not t.depends_on or t.task_id not in task_blocks:
            continue
        earliest_start = min(b.start_slot for b in task_blocks[t.task_id])
        for prereq_id in t.depends_on:
            if prereq_id not in task_blocks:
                violation_count += 1
                violations.append(
                    f"H5 Violation: Task {t.task_id} scheduled even though prerequisite {prereq_id} is unplaced"
                )
            else:
                prereq_end = max(b.end_slot for b in task_blocks[prereq_id])
                if earliest_start < prereq_end:
                    violation_count += 1
                    violations.append(
                        f"H5 Violation: Task {t.task_id} starts at slot {earliest_start} before prerequisite {prereq_id} ends at {prereq_end}"
                    )

    return violation_count, violations


def calculate_deadline_satisfaction_rate(
    tasks: List[Task],
    blocks: List[ScheduleBlock],
    unplaced_task_ids: List[str],
    week_start_iso: str = "2026-11-02T00:00:00+07:00",
) -> float:
    """
    Formula from baseline_plan.md §9.1:
    R_deadline = (Tasks completed on or before deadline / Total tasks with deadline) * 100%
    """
    if not tasks:
        return 100.0

    unplaced_set = set(unplaced_task_ids)
    blocks_by_task: Dict[str, List[ScheduleBlock]] = {}
    for b in blocks:
        blocks_by_task.setdefault(b.task_id, []).append(b)

    deadline_tasks = [
        t for t in tasks if t.resolve_deadline_slot(week_start_iso=week_start_iso) is not None
    ]
    target_pool = deadline_tasks if deadline_tasks else tasks

    satisfied = 0
    for t in target_pool:
        if t.task_id in unplaced_set:
            continue
        t_blocks = blocks_by_task.get(t.task_id, [])
        if not t_blocks:
            continue
        placed_min = sum(b.duration_min for b in t_blocks)
        if placed_min < t.get_planned_duration_min():
            continue
        d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
        if d_slot is not None:
            max_end = max(b.end_slot for b in t_blocks)
            if max_end > d_slot:
                continue
        satisfied += 1

    return round((satisfied / float(len(target_pool))) * 100.0, 2)


def calculate_schedule_stability(
    original_blocks: List[ScheduleBlock],
    repaired_blocks: List[ScheduleBlock],
    disruption_start_slot: int,
    disruption_end_slot: int,
) -> Tuple[float, int, int, int]:
    """
    Formula from Proposal §2.7, §9.5 and baseline_plan.md §9.1:
    S_stability = (Unchanged Unaffected Blocks / Total Previously Scheduled Unaffected Blocks) * 100%
    Unaffected blocks are those that do NOT directly overlap [disruption_start_slot, disruption_end_slot).
    Returns: (stability_pct, total_unaffected, unchanged_unaffected, directly_hit)
    """
    unaffected_originals: List[ScheduleBlock] = []
    directly_hit = 0

    for b in original_blocks:
        overlaps = not (b.end_slot <= disruption_start_slot or b.start_slot >= disruption_end_slot)
        if overlaps:
            directly_hit += 1
        else:
            unaffected_originals.append(b)

    total_unaffected = len(unaffected_originals)
    if total_unaffected == 0:
        return 100.0, 0, 0, directly_hit

    repaired_lookup = {
        (rb.task_id, rb.chunk_index): (rb.start_slot, rb.end_slot) for rb in repaired_blocks
    }

    unchanged = 0
    for b in unaffected_originals:
        key = (b.task_id, b.chunk_index)
        if key in repaired_lookup and repaired_lookup[key] == (b.start_slot, b.end_slot):
            unchanged += 1

    stability_pct = round((unchanged / float(total_unaffected)) * 100.0, 2)
    return stability_pct, total_unaffected, unchanged, directly_hit


def calculate_fragmentation_index(grid_manager: TimeGridManager, up_to: int = SLOTS_PER_WEEK) -> float:
    """
    Compute percentage of remaining FREE slots that are isolated in short gaps (< 30 min = 1 slot).
    Lower fragmentation means free time stays in larger, more usable contiguous blocks.
    """
    intervals = grid_manager.get_free_intervals(start_from=0, up_to=up_to)
    total_free = sum(length for _, length in intervals)
    if total_free == 0:
        return 0.0
    short_gap_slots = sum(length for _, length in intervals if length < 2)
    return round((short_gap_slots / float(total_free)) * 100.0, 2)


def compute_determinism_hash(blocks: List[ScheduleBlock], unplaced_tasks: List[Dict[str, Any]]) -> str:
    """Compute a deterministic SHA-256 hex digest of the placement result."""
    canonical = {
        "blocks": [
            {
                "task_id": b.task_id,
                "chunk_index": b.chunk_index,
                "start_slot": b.start_slot,
                "end_slot": b.end_slot,
            }
            for b in sorted(blocks, key=lambda x: (x.start_slot, x.task_id, x.chunk_index))
        ],
        "unplaced": sorted(str(u.get("task_id", "")) for u in unplaced_tasks),
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

