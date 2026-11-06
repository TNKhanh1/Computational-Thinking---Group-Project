"""
Orchestration Layer (controller.py - baseline_plan.md §8).
Coordinates solver selection, determinism verification, comparative algorithm runs,
disruption repair, manual move validation, and task overrun updates.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.grid_manager import TimeGridManager
from src.models import (
    CommitmentsProfile,
    DisruptionEvent,
    RepairOutput,
    ScheduleBlock,
    ScheduleOutput,
    Task,
)
from src.overload_triage import OverloadTriageEngine
from src.solvers.backtracking import BacktrackingSolver
from src.solvers.base_solver import BaseScheduler
from src.solvers.greedy_edf import GreedyEDFSolver
from src.solvers.greedy_lst import GreedyLSTSolver
from src.solvers.greedy_wspt import GreedyWSPTSolver
from src.solvers.local_repair import LocalRepairEngine
from src.utils import SLOTS_PER_WEEK, day_time_to_slot, iso_to_slot, round_up_to_15


class ScheduleController:
    """Central orchestration controller for the SmartSchedule Baseline Engine."""

    SOLVER_REGISTRY = {
        "EDF": GreedyEDFSolver,
        "GREEDY_EDF": GreedyEDFSolver,
        "GREEDY_EDF_FIRST_FIT": GreedyEDFSolver,
        "SCORED_GREEDY": GreedyEDFSolver,  # V0 fallback alias for Improve Plan contract
        "LST": GreedyLSTSolver,
        "LST_BEST_FIT": GreedyLSTSolver,
        "GREEDY_LST": GreedyLSTSolver,
        "GREEDY_LST_BEST_FIT": GreedyLSTSolver,
        "WSPT": GreedyWSPTSolver,
        "GREEDY_WSPT": GreedyWSPTSolver,
        "GREEDY_WSPT_SMITH_RULE": GreedyWSPTSolver,
        "BACKTRACK": BacktrackingSolver,
        "BACKTRACKING": BacktrackingSolver,
        "BACKTRACKING_BRANCH_AND_BOUND": BacktrackingSolver,
    }

    @classmethod
    def get_solver(cls, algorithm: str = "EDF") -> BaseScheduler:
        key = (algorithm or "EDF").strip().upper()
        solver_cls = cls.SOLVER_REGISTRY.get(key, GreedyEDFSolver)
        return solver_cls()

    @classmethod
    def solve_schedule(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        algorithm: str = "EDF",
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        solver = cls.get_solver(algorithm)
        out, grid = solver.solve(profile, tasks, pinned_blocks=pinned_blocks)
        OverloadTriageEngine.enrich_schedule_overload(out, profile, tasks)
        return out, grid

    @classmethod
    def verify_determinism(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        algorithm: str = "EDF",
        runs: int = 3,
    ) -> Dict[str, Any]:
        """
        Run the exact same input `runs` times and verify that every run produces
        the exact same SHA-256 determinism_hash and identical block placements.
        """
        hashes: List[str] = []
        latencies: List[float] = []
        first_output: Optional[ScheduleOutput] = None

        for _ in range(max(2, runs)):
            out, _ = cls.solve_schedule(profile, tasks, algorithm=algorithm)
            hashes.append(out.determinism_hash)
            latencies.append(out.execution_time_ms)
            if first_output is None:
                first_output = out

        is_deterministic = len(set(hashes)) == 1
        return {
            "is_deterministic": is_deterministic,
            "runs": len(hashes),
            "hashes": hashes,
            "unique_hash": hashes[0] if hashes else "",
            "latencies_ms": latencies,
            "avg_latency_ms": round(sum(latencies) / float(len(latencies)), 4) if latencies else 0.0,
            "schedule": first_output,
        }

    @classmethod
    def compare_algorithms(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        algo_left: str = "GREEDY_EDF_FIRST_FIT",
        algo_right: str = "GREEDY_LST_BEST_FIT",
    ) -> Dict[str, Any]:
        """Run two algorithms side-by-side on the exact same inputs for Dual-Algorithm Comparative View."""
        out_left, _ = cls.solve_schedule(profile, tasks, algorithm=algo_left)
        out_right, _ = cls.solve_schedule(profile, tasks, algorithm=algo_right)

        # Compute block position differences
        left_map = {(b.task_id, b.chunk_index): (b.start_slot, b.end_slot) for b in out_left.blocks}
        right_map = {(b.task_id, b.chunk_index): (b.start_slot, b.end_slot) for b in out_right.blocks}
        all_keys = sorted(set(left_map.keys()) | set(right_map.keys()))
        diff_blocks = sum(1 for k in all_keys if left_map.get(k) != right_map.get(k))

        return {
            "left": out_left,
            "right": out_right,
            "comparison": {
                "algo_left": out_left.solver_used,
                "algo_right": out_right.solver_used,
                "different_block_placements": diff_blocks,
                "total_chunks_compared": len(all_keys),
                "left_exec_ms": out_left.execution_time_ms,
                "right_exec_ms": out_right.execution_time_ms,
                "left_deadline_rate": out_left.summary.deadline_satisfaction_rate,
                "right_deadline_rate": out_right.summary.deadline_satisfaction_rate,
                "left_fragmentation": out_left.summary.fragmentation_index,
                "right_fragmentation": out_right.summary.fragmentation_index,
                "left_hard_violations": out_left.summary.hard_constraint_violations,
                "right_hard_violations": out_right.summary.hard_constraint_violations,
            },
        }

    @classmethod
    def compare_repair_modes(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_schedule: ScheduleOutput,
        disruption: DisruptionEvent,
    ) -> Dict[str, Any]:
        """Compare Local Insertion (M4) vs Full Rebuild on the same disruption event (Scenario T04)."""
        local_res = LocalRepairEngine.repair_disruption(
            profile, tasks, current_schedule, disruption, mode="LOCAL_INSERTION"
        )
        rebuild_res = LocalRepairEngine.repair_disruption(
            profile, tasks, current_schedule, disruption, mode="FULL_REBUILD"
        )
        return {
            "local_repair": local_res,
            "full_rebuild": rebuild_res,
            "comparison": {
                "local_stability_pct": local_res.stability_score,
                "rebuild_stability_pct": rebuild_res.stability_score,
                "local_moved_blocks": local_res.moved_blocks_count,
                "rebuild_moved_blocks": rebuild_res.moved_blocks_count,
                "directly_hit_blocks": local_res.directly_hit_blocks,
                "total_unaffected_blocks": local_res.total_unaffected_blocks,
            },
        }

    @classmethod
    def validate_manual_move(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_blocks: List[ScheduleBlock],
        block_id: str,
        new_start_slot: Optional[int] = None,
        new_start_iso: Optional[str] = None,
        new_day: Optional[str] = None,
        new_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate whether moving `block_id` to a new start time obeys Hard Constraints H1-H5."""
        week_start_iso = profile.planning_week_start
        if new_start_slot is None:
            if new_start_iso:
                new_start_slot = iso_to_slot(new_start_iso, week_start_iso=week_start_iso)
            elif new_day and new_time:
                new_start_slot = day_time_to_slot(new_day, new_time)
            else:
                return {"ok": False, "violations": [{"code": "MISSING_TARGET", "message": "Thiếu vị trí đích."}]}

        target_block: Optional[ScheduleBlock] = None
        other_blocks: List[ScheduleBlock] = []
        for b in current_blocks:
            if b.block_id == block_id or (b.task_id == block_id and b.total_chunks == 1):
                target_block = b
            else:
                other_blocks.append(b)

        if target_block is None:
            return {"ok": False, "violations": [{"code": "NOT_FOUND", "message": f"Không tìm thấy block {block_id}."}]}

        grid = TimeGridManager(total_slots=SLOTS_PER_WEEK)
        grid.initialize_from_profile(profile)
        for ob in other_blocks:
            length = ob.end_slot - ob.start_slot
            if grid.is_range_free(ob.start_slot, length):
                grid.place_block(ob.start_slot, length, ob.task_id, ob.title)

        task_map = {t.task_id: t for t in tasks}
        t_obj = task_map.get(target_block.task_id)
        earliest_start = BaseScheduler.resolve_now_slot(profile)
        if t_obj and t_obj.depends_on:
            prereq_ends = [ob.end_slot for ob in other_blocks if ob.task_id in t_obj.depends_on]
            if prereq_ends:
                earliest_start = max(earliest_start, max(prereq_ends))

        length_slots = target_block.end_slot - target_block.start_slot
        violations = grid.explain_violation(
            start_slot=new_start_slot,
            length_slots=length_slots,
            deadline_slot=target_block.deadline_slot,
            earliest_start_slot=earliest_start,
        )
        return {
            "ok": len(violations) == 0,
            "new_start_slot": new_start_slot,
            "new_end_slot": new_start_slot + length_slots,
            "violations": violations,
        }

    @classmethod
    def handle_task_overrun(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        task_id: str,
        extra_minutes: int = 0,
        overrun_pct: float = 0.0,
        algorithm: str = "EDF",
    ) -> Dict[str, Any]:
        """
        Scenario T05 / Use Case UC9: A task takes longer than estimated (e.g. +30% or +extra_minutes).
        Updates the task duration and re-evaluates the schedule to expose ripple shifts or new conflicts.
        """
        before_out, _ = cls.solve_schedule(profile, tasks, algorithm=algorithm)

        updated_tasks: List[Task] = []
        target_old_min = 0
        target_new_min = 0

        for t in tasks:
            t_copy = t.model_copy(deep=True)
            if t_copy.task_id == task_id:
                target_old_min = t_copy.get_planned_duration_min()
                if extra_minutes > 0:
                    raw_new = t_copy.duration_min + extra_minutes
                elif overrun_pct > 0:
                    raw_new = int(round(t_copy.duration_min * (1.0 + overrun_pct / 100.0)))
                else:
                    raw_new = int(round(t_copy.duration_min * 1.30))
                t_copy.duration_min = round_up_to_15(raw_new)
                target_new_min = t_copy.get_planned_duration_min()
            updated_tasks.append(t_copy)

        after_out, _ = cls.solve_schedule(profile, updated_tasks, algorithm=algorithm)

        before_map = {(b.task_id, b.chunk_index): (b.start_slot, b.end_slot) for b in before_out.blocks}
        after_map = {(b.task_id, b.chunk_index): (b.start_slot, b.end_slot) for b in after_out.blocks}
        shifted_blocks = sum(1 for k, v in after_map.items() if k in before_map and before_map[k] != v)

        return {
            "task_id": task_id,
            "old_duration_min": target_old_min,
            "new_duration_min": target_new_min,
            "shifted_blocks_count": shifted_blocks,
            "before_schedule": before_out,
            "after_schedule": after_out,
        }

    @classmethod
    def preview_overload_resolution(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        option_id: Optional[str] = None,
        option_code: Optional[str] = None,
        target_task_id: Optional[str] = None,
        algorithm: str = "EDF",
        current_schedule: Optional[ScheduleOutput] = None,
    ) -> Dict[str, Any]:
        """
        Feature 002 (F15 — Improve Plan §6.7 & §7.2):
        Simulate an overload resolution option (`SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST`)
        on deep-copied tasks (`INV-3` statelessness) and return the proposed schedule with affected/new
        blocks marked `state = "PROPOSED"`.
        """
        if current_schedule is not None:
            before_out = current_schedule.model_copy(deep=True)
            OverloadTriageEngine.enrich_schedule_overload(before_out, profile, tasks)
        else:
            before_out, _ = cls.solve_schedule(profile, tasks, algorithm=algorithm)

        shortage_min = 0
        available_options: List[Dict[str, Any]] = []
        if before_out.overload is not None:
            shortage_min = int(before_out.overload.shortage_minutes or 0)
            available_options = list(before_out.overload.options or [])

        resolved_tasks, applied_change = OverloadTriageEngine.apply_triage_option(
            profile=profile,
            tasks=tasks,
            option_id=option_id,
            option_code=option_code,
            target_task_id=target_task_id,
            shortage_min=shortage_min,
            available_options=available_options,
        )

        after_out, _ = cls.solve_schedule(profile, resolved_tasks, algorithm=algorithm)

        before_map = {
            (b.task_id, b.chunk_index): (b.start_slot, b.end_slot, b.duration_min)
            for b in before_out.blocks
        }
        changed_target_id = str(applied_change.get("task_id", ""))
        proposed_block_ids: List[str] = []

        for b in after_out.blocks:
            key = (b.task_id, b.chunk_index)
            val = (b.start_slot, b.end_slot, b.duration_min)
            if key not in before_map or before_map[key] != val or b.task_id == changed_target_id:
                b.state = "PROPOSED"
                proposed_block_ids.append(b.block_id)

        # If an unplaced task was skipped (`SKIP_HABIT`) and existing blocks stayed in place,
        # mark all blocks in the preview as PROPOSED so the preview grid clearly shows the proposal state.
        if not proposed_block_ids and after_out.blocks:
            for b in after_out.blocks:
                b.state = "PROPOSED"
                proposed_block_ids.append(b.block_id)

        return {
            "status": "OK",
            "preview_mode": True,
            "option_id": applied_change.get("option_id", option_id or "O1"),
            "option_code": applied_change.get("code", option_code or ""),
            "target_task_id": changed_target_id,
            "option_applied": applied_change,
            "resolved_tasks": [t.model_dump() for t in resolved_tasks],
            "before_summary": before_out.summary.model_dump(),
            "after_summary": after_out.summary.model_dump(),
            "blocks": [b.model_dump() for b in after_out.blocks],
            "proposed_block_ids": proposed_block_ids,
            "changes": [applied_change],
            "schedule": after_out,
        }


