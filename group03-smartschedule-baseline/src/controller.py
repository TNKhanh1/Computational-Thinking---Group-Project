"""
Schedule Controller & Orchestration Engine (Pure Domain Service).
Routes solve requests across EDF, LST, WSPT, SCORED_GREEDY (Pattern 3+4+7), Backtracking,
Local Repair (M4), Estimate Buffer (Feature 001 + Presentation2 COGNITIVE_LOAD), and Overload Triage (Feature 002).
"""

from typing import Any, Dict, List, Optional, Tuple, Type

from src.estimate_buffer import buffer_reason, multiplier_for_habit, multiplier_for_load
from src.grid_manager import TimeGridManager
from src.models import (
    CommitmentsProfile,
    DisruptionEvent,
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
from src.solvers.scored_greedy import ScoredGreedySolver
from src.utils import SLOTS_PER_WEEK, day_time_to_slot, iso_to_slot, round_up_to_15, slot_to_day_time, slot_to_iso


class ScheduleController:
    """Central domain facade used by both CLI benchmarks and FastAPI endpoints."""

    SOLVER_REGISTRY: Dict[str, Type[BaseScheduler]] = {
        "EDF": GreedyEDFSolver,
        "GREEDY_EDF": GreedyEDFSolver,
        "GREEDY_EDF_FIRST_FIT": GreedyEDFSolver,
        "SCORED_GREEDY": ScoredGreedySolver,
        "URGENCY": ScoredGreedySolver,
        "LST": GreedyLSTSolver,
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
    def expand_personal_habits(cls, profile: CommitmentsProfile, tasks: List[Task]) -> List[Task]:
        """
        Presentation2.pdf Slide 6: Convert structured PersonalHabit tuples
        (Name, PreferredWindow, Frequency, Duration) into flexible HABIT tasks if not already included.
        """
        habits = getattr(profile, "personal_habits", None) or []
        if not habits:
            return list(tasks)

        existing_ids = {t.task_id for t in tasks}
        expanded: List[Task] = list(tasks)
        for h in habits:
            # Spread habit occurrences cleanly across non-deadline flexible HABIT tasks
            for occ in range(1, h.frequency_per_week + 1):
                tid = f"{h.habit_id}_{occ}" if h.frequency_per_week > 1 else h.habit_id
                if tid in existing_ids:
                    continue
                existing_ids.add(tid)
                expanded.append(
                    Task(
                        task_id=tid,
                        title=f"{h.name} (#{occ})" if h.frequency_per_week > 1 else h.name,
                        duration_min=h.duration_min,
                        deadline_day=None,
                        priority=1,
                        category=h.category or "HABIT",
                        is_splittable=False,
                        cognitive_load=h.cognitive_load,
                    )
                )
        return expanded

    @classmethod
    def solve_schedule(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        algorithm: str = "EDF",
        pinned_blocks: Optional[List[ScheduleBlock]] = None,
    ) -> Tuple[ScheduleOutput, TimeGridManager]:
        solver = cls.get_solver(algorithm)
        all_tasks = cls.expand_personal_habits(profile, tasks)
        buffered_tasks = cls.apply_estimate_buffer(profile, all_tasks)
        out, grid = solver.solve(profile, buffered_tasks, pinned_blocks=pinned_blocks)
        cls.annotate_estimate_buffer(profile, buffered_tasks, out)
        OverloadTriageEngine.enrich_schedule_overload(out, profile, buffered_tasks)
        return out, grid

    # ------------------------------------------------------------------
    # Pattern 1 / Feature 001 — Estimate buffer (HABIT + COGNITIVE_LOAD)
    # ------------------------------------------------------------------
    @classmethod
    def apply_estimate_buffer(cls, profile: CommitmentsProfile, tasks: List[Task]) -> List[Task]:
        """
        Return copies of `tasks` with duration buffer settings derived from `profile`:
          * buffer_mode == 'COGNITIVE_LOAD': sets α_light (1.20) / α_heavy (1.35) + RoundUp_15.
          * buffer_mode == 'HABIT' (default): Feature 001 (`RARELY` / `SOMETIMES` / `OFTEN`), V0 unchanged if None.
        """
        buf_mode = getattr(profile, "buffer_mode", "HABIT")
        if buf_mode == "COGNITIVE_LOAD":
            a_light = getattr(profile, "alpha_light", 1.20)
            a_heavy = getattr(profile, "alpha_heavy", 1.35)
            out_tasks: List[Task] = []
            for t in tasks:
                if str(getattr(t, "buffer_mode", "HABIT")).strip().upper() == "NONE":
                    out_tasks.append(t.model_copy(update={"buffer_mode": "NONE", "buffer_multiplier": 1.0}, deep=True))
                else:
                    out_tasks.append(
                        t.model_copy(
                            update={
                                "buffer_mode": "COGNITIVE_LOAD",
                                "alpha_light": a_light,
                                "alpha_heavy": a_heavy,
                                "buffer_multiplier": multiplier_for_load(t.cognitive_load, a_light, a_heavy),
                            },
                            deep=True,
                        )
                    )
            return out_tasks

        habit = getattr(profile, "estimate_habit", None)
        if not habit:
            return list(tasks)
        multiplier = multiplier_for_habit(habit)
        out_tasks = []
        for t in tasks:
            if str(getattr(t, "buffer_mode", "HABIT")).strip().upper() == "NONE":
                out_tasks.append(t.model_copy(update={"buffer_mode": "NONE", "buffer_multiplier": 1.0}, deep=True))
            else:
                out_tasks.append(t.model_copy(update={"buffer_mode": "HABIT", "buffer_multiplier": multiplier}, deep=True))
        return out_tasks

    @classmethod
    def annotate_estimate_buffer(
        cls, profile: CommitmentsProfile, buffered_tasks: List[Task], out: ScheduleOutput
    ) -> None:
        """Attach an ESTIMATE_BUFFER reason to every block whose planned time was increased."""
        habit = getattr(profile, "estimate_habit", None)
        buf_mode = getattr(profile, "buffer_mode", "HABIT")
        if not habit and buf_mode != "COGNITIVE_LOAD":
            return
        task_map = {t.task_id: t for t in buffered_tasks}
        for block in out.blocks:
            task = task_map.get(block.task_id)
            if task is None or task.buffer_multiplier <= 1.0:
                continue
            planned = task.get_planned_duration_min()
            if planned <= round_up_to_15(task.duration_min):
                continue
            if any(r.get("code") == "ESTIMATE_BUFFER" for r in block.reasons):
                continue
            block.reasons.append(buffer_reason(task.duration_min, planned, task.buffer_multiplier, habit))

    @classmethod
    def verify_determinism(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        algorithm: str = "EDF",
        runs: int = 3,
    ) -> Dict[str, Any]:
        hashes: List[str] = []
        latencies: List[float] = []
        first_output: Optional[ScheduleOutput] = None

        for _ in range(max(2, runs)):
            out, _ = cls.solve_schedule(profile, tasks, algorithm=algorithm)
            hashes.append(out.determinism_hash)
            latencies.append(out.execution_time_ms)
            if first_output is None:
                first_output = out

        return {
            "is_deterministic": len(set(hashes)) == 1,
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
        out_left, _ = cls.solve_schedule(profile, tasks, algorithm=algo_left)
        out_right, _ = cls.solve_schedule(profile, tasks, algorithm=algo_right)

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
                "left_experience_rating": out_left.summary.experience_rating,
                "right_experience_rating": out_right.summary.experience_rating,
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
        tasks = cls.apply_estimate_buffer(profile, tasks)
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

        horizon = BaseScheduler.resolve_horizon_slots(tasks, week_start_iso=week_start_iso)
        grid = TimeGridManager(total_slots=horizon)
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
        new_end_slot = new_start_slot + length_slots
        proposed_block: Optional[Dict[str, Any]] = None
        if len(violations) == 0:
            p_day, p_start_str = slot_to_day_time(new_start_slot, is_end_time=False)
            _, p_end_str = slot_to_day_time(new_end_slot, is_end_time=True)
            moved_copy = target_block.model_copy(
                update={
                    "day": p_day,
                    "start_time": p_start_str,
                    "end_time": p_end_str,
                    "start_slot": new_start_slot,
                    "end_slot": new_end_slot,
                    "start_iso": slot_to_iso(new_start_slot, week_start_iso=week_start_iso),
                    "end_iso": slot_to_iso(new_end_slot, week_start_iso=week_start_iso),
                    "state": "PINNED",
                },
                deep=True,
            )
            proposed_block = moved_copy.model_dump(mode="json")

        return {
            "ok": len(violations) == 0,
            "new_start_slot": new_start_slot,
            "new_end_slot": new_end_slot,
            "violations": violations,
            "proposed_block": proposed_block,
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
        Fix A9 (Scenario T05 / Use Case UC9):
        1. Re-compute buffered estimate after adding overrun to raw estimate (Feature 001 FR7).
        2. Repair the schedule locally using LocalRepairEngine.repair_overrun() instead of Full Rebuild
           so unaffected blocks keep high stability (>= 90% Pattern 8).
        """
        buffered_tasks = cls.apply_estimate_buffer(profile, tasks)
        before_out, _ = cls.solve_schedule(profile, buffered_tasks, algorithm=algorithm)

        updated_raw_tasks: List[Task] = []
        target_old_min = 0
        target_new_estimate = 0

        for t in buffered_tasks:
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
                target_new_estimate = t_copy.duration_min
            updated_raw_tasks.append(t_copy)

        updated_buffered = cls.apply_estimate_buffer(profile, updated_raw_tasks)
        target_new_min = next(
            (t.get_planned_duration_min() for t in updated_buffered if t.task_id == task_id),
            target_new_estimate,
        )

        repair_res = LocalRepairEngine.repair_overrun(
            profile=profile,
            updated_tasks=updated_buffered,
            current_schedule=before_out,
            target_task_id=task_id,
        )
        after_out = repair_res.schedule
        cls.annotate_estimate_buffer(profile, updated_buffered, after_out)

        before_map = {(b.task_id, b.chunk_index): (b.start_slot, b.end_slot) for b in before_out.blocks}
        after_map = {(b.task_id, b.chunk_index): (b.start_slot, b.end_slot) for b in after_out.blocks}
        shifted_blocks = sum(1 for k, v in after_map.items() if k in before_map and before_map[k] != v)

        return {
            "task_id": task_id,
            "old_duration_min": target_old_min,
            "new_duration_min": target_new_min,
            "new_estimate_min": target_new_estimate,
            "shifted_blocks_count": shifted_blocks,
            "stability_score": repair_res.stability_score,
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
        """Feature 002 (F15): Simulate an overload resolution option in memory and return PROPOSED blocks."""
        expanded_tasks = cls.expand_personal_habits(profile, tasks)
        if current_schedule is not None:
            before_out = current_schedule.model_copy(deep=True)
            OverloadTriageEngine.enrich_schedule_overload(before_out, profile, expanded_tasks)
        else:
            before_out, _ = cls.solve_schedule(profile, expanded_tasks, algorithm=algorithm)

        shortage_min = 0
        available_options: List[Dict[str, Any]] = []
        if before_out.overload is not None:
            shortage_min = int(before_out.overload.shortage_minutes or 0)
            available_options = list(before_out.overload.options or [])

        resolved_tasks, applied_change = OverloadTriageEngine.apply_triage_option(
            profile=profile,
            tasks=expanded_tasks,
            option_id=option_id,
            option_code=option_code,
            target_task_id=target_task_id,
            shortage_min=shortage_min,
            available_options=available_options,
        )

        # Avoid duplicate habit expansion inside solve_schedule when habits were already expanded cleanly
        preview_profile = profile.model_copy(update={"personal_habits": []}, deep=True)
        after_out, _ = cls.solve_schedule(preview_profile, resolved_tasks, algorithm=algorithm)

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
