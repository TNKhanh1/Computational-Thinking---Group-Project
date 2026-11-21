"""
Schedule Controller & Orchestration Engine (Pure Domain Service).
Routes solve requests across EDF, LST, WSPT, SCORED_GREEDY (Pattern 3+4+7), Backtracking,
Local Repair (M4), Estimate Buffer (Feature 001 + Presentation2 COGNITIVE_LOAD), and Overload Triage (Feature 002).
"""

from typing import Any, Dict, List, Optional, Tuple, Type

from smartschedule.core.estimate_buffer import buffer_reason, multiplier_for_habit, multiplier_for_load
from smartschedule.core.grid_manager import TimeGridManager
from smartschedule.core.models import (
    CommitmentsProfile,
    DisruptionEvent,
    ScheduleBlock,
    ScheduleOutput,
    Task,
)
from smartschedule.core.overload_triage import OverloadTriageEngine
from smartschedule.core.solvers.base_solver import BaseScheduler
from smartschedule.core.solvers.local_repair import LocalRepairEngine
from smartschedule.core.solvers.registry import SOLVER_REGISTRY, resolve_solver
from smartschedule.core.utils import SLOTS_PER_WEEK, day_time_to_slot, iso_to_slot, round_up_to_15, slot_to_day_time, slot_to_iso


class ScheduleController:
    """Central domain facade used by both CLI benchmarks and FastAPI endpoints."""

    SOLVER_REGISTRY: Dict[str, Type[BaseScheduler]] = SOLVER_REGISTRY

    @classmethod
    def get_solver(cls, algorithm: str = "EDF") -> BaseScheduler:
        key = (algorithm or "EDF").strip().upper()
        if cls.SOLVER_REGISTRY is not SOLVER_REGISTRY:
            solver_cls = cls.SOLVER_REGISTRY.get(key)
            if solver_cls is not None:
                return solver_cls()
        return resolve_solver(key)

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
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        now_slot = BaseScheduler.resolve_now_slot(profile)
        now_day = min(6, max(0, now_slot // 96))
        span_days = max(1, 7 - now_day)

        for h in habits:
            # Spread habit occurrences cleanly across remaining days and honor preferred_window (Q7.3 = A3)
            freq = max(1, int(h.frequency_per_week))
            pref_win = (h.preferred_window or "ANYTIME").strip().upper()
            for occ in range(1, freq + 1):
                tid = f"{h.habit_id}_{occ}" if freq > 1 else h.habit_id
                if tid in existing_ids:
                    continue
                existing_ids.add(tid)
                day_offset = ((occ - 1) * span_days) // freq
                target_day_idx = min(6, now_day + day_offset)
                start_after_str = f"{day_names[target_day_idx]} 00:00" if target_day_idx > now_day else None
                expanded.append(
                    Task(
                        task_id=tid,
                        title=f"{h.name} (#{occ})" if freq > 1 else h.name,
                        duration_min=h.duration_min,
                        deadline_day=None,
                        priority=1,
                        category=h.category or "HABIT",
                        is_splittable=False,
                        cognitive_load=h.cognitive_load,
                        start_after=start_after_str,
                        preferred_window=pref_win,
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
    def compute_schedule_insights(
        cls,
        profile: CommitmentsProfile,
        out: ScheduleOutput,
    ) -> Dict[str, Any]:
        """Compute Circadian energy alignment and category-batching insights for UI/Lab telemetry."""
        energy_prof = profile.get_energy_profile()
        sorted_blocks = sorted(out.blocks, key=lambda b: (b.start_slot, b.end_slot))
        block_energies: Dict[str, float] = {}

        total_energy_sum = 0.0
        peak_matched = 0
        deep_total = 0
        deep_peak_matched = 0

        for b in sorted_blocks:
            span = max(1, b.end_slot - b.start_slot)
            avg_e = sum(energy_prof.level_for_slot(s) for s in range(b.start_slot, b.end_slot)) / float(span)
            avg_e_round = round(avg_e, 2)
            block_energies[b.block_id] = avg_e_round
            total_energy_sum += avg_e
            if avg_e >= 2.5:
                peak_matched += 1
            load = b.cognitive_load if b.cognitive_load is not None else 2
            if load >= 2:
                deep_total += 1
                if avg_e >= 2.5:
                    deep_peak_matched += 1

        context_switches = 0
        batched_pairs = 0
        for idx in range(1, len(sorted_blocks)):
            prev_b = sorted_blocks[idx - 1]
            cur_b = sorted_blocks[idx]
            same_day = (prev_b.start_slot // 96) == (cur_b.start_slot // 96)
            gap = cur_b.start_slot - prev_b.end_slot
            if same_day and 0 <= gap <= 2:
                if (prev_b.category or "").upper() == (cur_b.category or "").upper():
                    batched_pairs += 1
                else:
                    context_switches += 1

        total_blocks = len(sorted_blocks)
        peak_rate = round(100.0 * peak_matched / total_blocks, 1) if total_blocks > 0 else 100.0
        deep_rate = round(100.0 * deep_peak_matched / deep_total, 1) if deep_total > 0 else peak_rate
        avg_lvl = round(total_energy_sum / total_blocks, 2) if total_blocks > 0 else 0.0

        return {
            "block_energies": block_energies,
            "peak_match_rate_pct": peak_rate,
            "deep_peak_match_pct": deep_rate,
            "avg_energy_level": avg_lvl,
            "context_switches": context_switches,
            "batched_pairs": batched_pairs,
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

        ins_left = cls.compute_schedule_insights(profile, out_left)
        ins_right = cls.compute_schedule_insights(profile, out_right)

        left_blk_map = {(b.task_id, b.chunk_index): b for b in out_left.blocks}
        right_blk_map = {(b.task_id, b.chunk_index): b for b in out_right.blocks}
        all_keys = sorted(set(left_blk_map.keys()) | set(right_blk_map.keys()))

        block_diffs: List[Dict[str, Any]] = []
        diff_blocks = 0
        for k in all_keys:
            lb = left_blk_map.get(k)
            rb = right_blk_map.get(k)
            l_span = (lb.start_slot, lb.end_slot) if lb else None
            r_span = (rb.start_slot, rb.end_slot) if rb else None
            changed = l_span != r_span
            if changed:
                diff_blocks += 1
            ref = lb or rb
            block_diffs.append(
                {
                    "task_id": k[0],
                    "chunk_index": k[1],
                    "total_chunks": ref.total_chunks if ref else 1,
                    "title": ref.title if ref else k[0],
                    "category": ref.category if ref else "DEADLINE",
                    "cognitive_load": ref.cognitive_load if ref else 2,
                    "priority": ref.priority if ref else 3,
                    "changed": changed,
                    "left_slot": lb.start_slot if lb else None,
                    "left_day": lb.day if lb else None,
                    "left_time": f"{lb.start_time}–{lb.end_time}" if lb else "UNPLACED",
                    "left_start_iso": lb.start_iso if lb else None,
                    "left_energy": ins_left["block_energies"].get(lb.block_id) if lb else None,
                    "left_reasons": [r.get("code") for r in (lb.reasons or []) if isinstance(r, dict) and r.get("code")] if lb else [],
                    "right_slot": rb.start_slot if rb else None,
                    "right_day": rb.day if rb else None,
                    "right_time": f"{rb.start_time}–{rb.end_time}" if rb else "UNPLACED",
                    "right_start_iso": rb.start_iso if rb else None,
                    "right_energy": ins_right["block_energies"].get(rb.block_id) if rb else None,
                    "right_reasons": [r.get("code") for r in (rb.reasons or []) if isinstance(r, dict) and r.get("code")] if rb else [],
                    "delta_slots": (rb.start_slot - lb.start_slot) if (lb and rb) else None,
                }
            )

        highlights: List[str] = []
        if out_right.summary.deadline_satisfaction_rate != out_left.summary.deadline_satisfaction_rate:
            dl_d = out_right.summary.deadline_satisfaction_rate - out_left.summary.deadline_satisfaction_rate
            highlights.append(
                f"Đạt hạn chót: {out_right.solver_used} {'+' if dl_d > 0 else ''}{dl_d:.1f}% "
                f"({out_left.summary.deadline_satisfaction_rate:.1f}% → {out_right.summary.deadline_satisfaction_rate:.1f}%)."
            )
        if ins_right["deep_peak_match_pct"] != ins_left["deep_peak_match_pct"]:
            pk_d = ins_right["deep_peak_match_pct"] - ins_left["deep_peak_match_pct"]
            highlights.append(
                f"Khớp khung giờ đỉnh Circadian (Load≥2): {out_right.solver_used} {'+' if pk_d > 0 else ''}{pk_d:.1f}% "
                f"({ins_left['deep_peak_match_pct']:.1f}% → {ins_right['deep_peak_match_pct']:.1f}%)."
            )
        if ins_right["context_switches"] != ins_left["context_switches"]:
            sw_d = ins_right["context_switches"] - ins_left["context_switches"]
            verb = "giảm" if sw_d < 0 else "tăng"
            highlights.append(
                f"Chuyển ngữ cảnh (Context Switches): {out_right.solver_used} {verb} {abs(sw_d)} lần "
                f"({ins_left['context_switches']} → {ins_right['context_switches']})."
            )
        if round(out_right.summary.experience_rating, 2) != round(out_left.summary.experience_rating, 2):
            exp_d = out_right.summary.experience_rating - out_left.summary.experience_rating
            highlights.append(
                f"Chỉ số trải nghiệm / độ mỏi (1=Thoải mái): {out_left.summary.experience_rating:.2f} → {out_right.summary.experience_rating:.2f} "
                f"({'nhẹ nhàng hơn' if exp_d < 0 else 'căng hơn'})."
            )
        if not highlights:
            highlights.append(
                f"Hai thuật toán cho kết quả tương đồng về chỉ số chính ({diff_blocks}/{len(all_keys)} phiên khác vị trí)."
            )

        def _side_quality_score(out_obj: ScheduleOutput, ins_obj: Dict[str, Any]) -> float:
            return (
                out_obj.summary.deadline_satisfaction_rate * 10.0
                - out_obj.summary.hard_constraint_violations * 500.0
                + ins_obj["deep_peak_match_pct"] * 0.5
                - ins_obj["context_switches"] * 2.0
                - out_obj.summary.experience_rating * 10.0
            )

        left_q = _side_quality_score(out_left, ins_left)
        right_q = _side_quality_score(out_right, ins_right)
        if right_q - left_q >= 1.0:
            verdict_winner = "RIGHT"
        elif left_q - right_q >= 1.0:
            verdict_winner = "LEFT"
        else:
            verdict_winner = "TIE"

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
                "left_peak_match_pct": ins_left["peak_match_rate_pct"],
                "right_peak_match_pct": ins_right["peak_match_rate_pct"],
                "left_deep_peak_match_pct": ins_left["deep_peak_match_pct"],
                "right_deep_peak_match_pct": ins_right["deep_peak_match_pct"],
                "left_avg_energy": ins_left["avg_energy_level"],
                "right_avg_energy": ins_right["avg_energy_level"],
                "left_context_switches": ins_left["context_switches"],
                "right_context_switches": ins_right["context_switches"],
                "left_batched_pairs": ins_left["batched_pairs"],
                "right_batched_pairs": ins_right["batched_pairs"],
                "left_rest_slots": out_left.summary.rest_slots,
                "right_rest_slots": out_right.summary.rest_slots,
                "left_placed_tasks": out_left.summary.tasks_placed,
                "right_placed_tasks": out_right.summary.tasks_placed,
                "total_tasks": out_left.summary.total_tasks_requested,
                "verdict_winner": verdict_winner,
                "verdict_highlights": highlights,
                "block_diffs": block_diffs,
            },
        }

    @classmethod
    def compare_repair_modes(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        current_schedule: ScheduleOutput,
        disruption: DisruptionEvent,
        algorithm: Optional[str] = None,
    ) -> Dict[str, Any]:
        tasks = cls.apply_estimate_buffer(profile, tasks)
        eff_algo = algorithm or getattr(current_schedule, "solver_used", None) or "EDF"
        local_res = LocalRepairEngine.repair_disruption(
            profile, tasks, current_schedule, disruption, mode="LOCAL_INSERTION", algorithm=eff_algo
        )
        rebuild_res = LocalRepairEngine.repair_disruption(
            profile, tasks, current_schedule, disruption, mode="FULL_REBUILD", algorithm=eff_algo
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

        horizon = BaseScheduler.resolve_horizon_slots(
            tasks,
            week_start_iso=week_start_iso,
            horizon_days=getattr(profile, "horizon_days", 7),
        )
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
