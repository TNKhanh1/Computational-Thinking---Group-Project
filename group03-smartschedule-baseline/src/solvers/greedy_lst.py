"""
Solution 3B: Dynamic Least Slack Time (LST / Minimum Laxity First) + Best-Fit Placement.
Upgraded (Fix A3):
  - Respects DAG prerequisite chains in effective earliest start time.
  - Dynamically re-evaluates actual FREE slots inside [effective_earliest, deadline) after each placement.
  - Shares A1/A4/A7/A8/A12/Pattern-2/Pattern-3/Pattern-4/Pattern-5 + Tier-1 Sprint safeguards.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task
from src.solvers.base_solver import BaseScheduler


class GreedyLSTSolver(BaseScheduler):
    """Dynamic Least Slack Time (LST) + Best-Fit Placement Solver."""

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

        # Isolate invalid cycles / missing prerequisites before dynamic selection
        indexed_tasks = list(enumerate(tasks))
        orig_order_map = {t.task_id: i for i, t in indexed_tasks}

        def static_tie_key(item: Tuple[int, Task]) -> Tuple[int, int, int, int]:
            idx, t = item
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if d_slot is None:
                return (1, 999999, -t.priority, idx)
            return (0, d_slot - now_slot - t.get_planned_slots(), -t.priority, idx)

        static_sorted = [t for _, t in sorted(indexed_tasks, key=static_tie_key)]
        ordered_valid, invalid_dep_reasons = self.partition_dependency_order(tasks, static_sorted)

        invalid_ids = set(invalid_dep_reasons.keys()) | set(past_due_map.keys())
        base_unplaced: List[Dict[str, Any]] = []
        for t in tasks:
            if t.task_id in invalid_dep_reasons:
                r_code = invalid_dep_reasons[t.task_id]
                msg = (
                    "Phát hiện phụ thuộc vòng lặp (Circular Dependency) — cô lập để giữ C_hard = 0."
                    if r_code == "CIRCULAR_DEPENDENCY"
                    else "Thiếu công việc tiên quyết không tồn tại trong danh sách."
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
                    "reason": "Hạn chót nằm trong quá khứ trước tuần lập lịch.",
                    "reason_code": "DEADLINE_IN_PAST",
                })

        schedulable_tasks = [t for t in ordered_valid if t.task_id not in invalid_ids]

        chunks_count_map = {
            t.task_id: len(self.split_task_into_chunks(t, orig_order_map.get(t.task_id, 0), week_start_iso))
            for t in schedulable_tasks
        }
        base_pinned_end: Dict[str, int] = {}
        pinned_counts: Dict[str, int] = {}
        for pb in accepted_pinned:
            pinned_counts[pb.task_id] = pinned_counts.get(pb.task_id, 0) + 1
            base_pinned_end[pb.task_id] = max(base_pinned_end.get(pb.task_id, 0), pb.end_slot)
        completed_pin_ends = {
            tid: end_s
            for tid, end_s in base_pinned_end.items()
            if pinned_counts.get(tid, 0) >= chunks_count_map.get(tid, 999)
        }

        def execute_dynamic_lst(allow_breaks: bool, crunch_tier: int):
            pass_grid = grid.clone()
            if allow_breaks:
                pass_grid.mark_dead_zones_as_rest()

            placed: List[ScheduleBlock] = [pb.model_copy(deep=True) for pb in accepted_pinned]
            task_ends = dict(completed_pin_ends)
            unplaced: List[Dict[str, Any]] = []
            pass_warnings: List[str] = []
            failed_ids = set(invalid_ids)
            remaining = list(schedulable_tasks)
            total_sched = len(schedulable_tasks)
            rank_counter = 0

            while remaining:
                # Propagate failed prerequisites immediately
                blocked = [t for t in remaining if any(p in failed_ids for p in t.depends_on)]
                if blocked:
                    for bt in blocked:
                        failed_ids.add(bt.task_id)
                        remaining.remove(bt)
                        unplaced.append({
                            "task_id": bt.task_id,
                            "title": bt.title,
                            "duration_min": bt.get_planned_duration_min(),
                            "priority": bt.priority,
                            "deadline": bt.format_deadline_label(week_start_iso=week_start_iso),
                            "deadline_slot": bt.resolve_deadline_slot(week_start_iso=week_start_iso),
                            "reason": "Công việc tiên quyết chưa thể xếp lịch.",
                            "reason_code": "PREREQUISITE_UNPLACED",
                        })
                    continue

                ready = [t for t in remaining if all(p in task_ends for p in t.depends_on)]
                if not ready:
                    break

                def dynamic_slack_key(t: Task) -> Tuple[int, int, int, int, int]:
                    d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
                    if d_slot is None:
                        return (1, 999999, -t.priority, 999999, orig_order_map.get(t.task_id, 0))
                    eff_earliest = max([now_slot] + [task_ends[p] for p in t.depends_on if p in task_ends])
                    eff_d = min(d_slot, pass_grid.total_slots)
                    free_avail = pass_grid.count_free_slots_in_range(start_from=eff_earliest, up_to=eff_d)
                    needed = max(0, t.get_planned_slots() - pinned_slots_by_task.get(t.task_id, 0))
                    dyn_slack = free_avail - needed
                    return (0, dyn_slack, -t.priority, d_slot, orig_order_map.get(t.task_id, 0))

                chosen_task = min(ready, key=dynamic_slack_key)
                remaining.remove(chosen_task)
                rank_counter += 1

                p_key = dynamic_slack_key(chosen_task)
                slack_min_label = f"{p_key[1] * 15}p" if p_key[0] == 0 else "∞"
                p_text = (
                    f"[Dynamic LST + Best-Fit] Xếp thứ {rank_counter}/{total_sched} "
                    f"(Slack thực = {slack_min_label}, Ưu tiên {chosen_task.priority})."
                )

                ok, new_blocks, err_entry, t_warns = self.place_task_with_constraints(
                    task=chosen_task,
                    grid=pass_grid,
                    profile=profile,
                    now_slot=now_slot,
                    task_end_slots=task_ends,
                    pinned_chunk_map=pinned_chunk_map,
                    placed_blocks=placed,
                    week_start_iso=week_start_iso,
                    primary_code="BEST_FIT_GAP",
                    primary_text=p_text,
                    allow_breaks=allow_breaks,
                    crunch_tier_used=crunch_tier,
                    order_index=orig_order_map.get(chosen_task.task_id, 0),
                    best_fit=True,
                )
                pass_warnings.extend(t_warns)
                if ok:
                    placed.extend(new_blocks)
                else:
                    failed_ids.add(chosen_task.task_id)
                    if err_entry is not None:
                        err_entry["priority"] = chosen_task.priority
                        unplaced.append(err_entry)

            return pass_grid, placed, unplaced, pass_warnings

        final_grid, final_blocks, tier_unplaced, tier_warnings = execute_dynamic_lst(allow_breaks=True, crunch_tier=0)
        crunch_used = 0
        if tier_unplaced:
            sp_grid, sp_blocks, sp_unplaced, sp_warnings = execute_dynamic_lst(allow_breaks=False, crunch_tier=1)
            if len(sp_unplaced) < len(tier_unplaced):
                final_grid, final_blocks, tier_unplaced, tier_warnings = (
                    sp_grid,
                    sp_blocks,
                    sp_unplaced,
                    sp_warnings + [
                        "Tier 1 Sprint Mode (Cut breaks): Tạm bỏ nghỉ 15p để giải phóng khoảng trống kịp hạn."
                    ],
                )
                crunch_used = 1

        exec_ms = (time.perf_counter() - t0) * 1000.0
        return self.finalize_output(
            grid_manager=final_grid,
            tasks=tasks,
            blocks=final_blocks,
            unplaced_tasks=base_unplaced + tier_unplaced,
            capacity_reports=capacity_reports,
            exec_ms=exec_ms,
            week_start_iso=week_start_iso,
            warnings=base_warnings + tier_warnings,
            profile=profile,
            now_slot=now_slot,
            crunch_tier_used=crunch_used,
        ), final_grid
