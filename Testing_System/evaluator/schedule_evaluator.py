"""
Part 2 Coordinator (`ScheduleEvaluator` / `OutputEvaluator`) + Contrast Pairs Self-Test.

Complies strictly with Architectural Invariants INV-1..INV-6:
  - Pure domain logic (zero FastAPI/Web imports).
  - Stateless evaluation on defensive deep copies (zero mutation of input profiles/tasks/schedules).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from Testing_System.evaluator.gates import evaluate_gates
from Testing_System.evaluator.pillars import (
    evaluate_p1,
    evaluate_p2,
    evaluate_p3,
    evaluate_p4,
)
from Testing_System.evaluator.verdict_and_icee import (
    build_auxiliary_diagnostics,
    evaluate_verdict_and_critiques,
    rank_cross_solver_reports,
)
from Testing_System.schemas import (
    ContrastPairResult,
    CrossSolverEntry,
    EvaluationConfig,
    EvaluationReport,
    InvariantCheckResult,
    VerdictLabel,
)
from Testing_System.sut_adapter import (
    CommitmentsProfile,
    ScheduleBlock,
    ScheduleController,
    ScheduleOutput,
    ScheduleSummary,
    SleepSchedule,
    Task,
    FixedEvent,
    preprocess_tasks,
    resolve_horizon_slots_safe,
    slot_to_day_time,
)


class ScheduleEvaluator:
    """Stateless 3-Tier Output Evaluator (INV-1, INV-3, INV-4, INV-6)."""

    @staticmethod
    def evaluate(
        profile: CommitmentsProfile,
        tasks: List[Task],
        schedule: ScheduleOutput,
        config: Optional[EvaluationConfig] = None,
        input_pinned_blocks: Optional[List[ScheduleBlock]] = None,
        baseline_schedule: Optional[ScheduleOutput] = None,
        disruption_span: Optional[Tuple[int, int]] = None,
        repair_now_slot: Optional[int] = None,
        is_overrun_context: bool = False,
        completion_logs: Optional[List[Dict[str, Any]]] = None,
    ) -> EvaluationReport:
        """Run full Tier 0 -> Tier 1 -> Tier 2 evaluation on defensive deep copies."""
        cfg = (config or EvaluationConfig()).model_copy(deep=True)
        prof_copy = profile.model_copy(deep=True)
        raw_task_copies = [t.model_copy(deep=True) for t in tasks]
        sched_copy = schedule.model_copy(deep=True)
        pin_copies = [b.model_copy(deep=True) for b in input_pinned_blocks] if input_pinned_blocks else None
        base_sched_copy = baseline_schedule.model_copy(deep=True) if baseline_schedule else None

        # Mandatory preprocessing matching controller flow before calling get_planned_duration_min()
        prepared_tasks = preprocess_tasks(prof_copy, raw_task_copies)
        horizon_slots = resolve_horizon_slots_safe(prof_copy, prepared_tasks, sched_copy.blocks)

        gates, base_grid = evaluate_gates(
            profile=prof_copy,
            prepared_tasks=prepared_tasks,
            schedule=sched_copy,
            horizon_slots=horizon_slots,
            input_pinned_blocks=pin_copies,
            is_overrun_context=is_overrun_context,
        )

        p1 = evaluate_p1(prof_copy, prepared_tasks, sched_copy, gates, base_grid)
        p2 = evaluate_p2(prof_copy, prepared_tasks, sched_copy, gates, base_grid)
        p3 = evaluate_p3(prof_copy, prepared_tasks, sched_copy, gates, base_grid)
        p4 = evaluate_p4(
            profile=prof_copy,
            raw_tasks=raw_task_copies,
            prepared_tasks=prepared_tasks,
            schedule=sched_copy,
            gates=gates,
            base_grid=base_grid,
            config=cfg,
            baseline_schedule=base_sched_copy,
            disruption_span=disruption_span,
            repair_now_slot=repair_now_slot,
            completion_logs=completion_logs,
        )

        verdict, reasons_vi, crit_breaches, mod_warnings, critiques = evaluate_verdict_and_critiques(
            gates=gates, p1=p1, p2=p2, p3=p3, p4=p4, config=cfg
        )

        insights = ScheduleController.compute_schedule_insights(prof_copy, sched_copy)
        diagnostics = build_auxiliary_diagnostics(base_grid, sched_copy.blocks, prepared_tasks, sched_copy, p1, insights)

        return EvaluationReport(
            solver_used=sched_copy.solver_used,
            verdict=verdict,
            verdict_reasons_vi=reasons_vi,
            critical_breaches=crit_breaches,
            moderate_warnings=mod_warnings,
            gates=gates,
            p1_value_timeliness=p1,
            p2_cognitive_biology=p2,
            p3_sustainable_pacing=p3,
            p4_robustness_stability=p4,
            d1_icee_critiques=critiques,
            diagnostics=diagnostics,
            config_used=cfg,
        )

    @staticmethod
    def compare_solvers(reports: Dict[str, EvaluationReport]) -> List[CrossSolverEntry]:
        return rank_cross_solver_reports(reports)


def _make_block(task: Task, planned_min: int, start_slot: int, chunk_idx: int = 1, total_chunks: int = 1) -> ScheduleBlock:
    dur_slots = planned_min // 15
    end_slot = start_slot + dur_slots
    day_s, t_start = slot_to_day_time(start_slot, is_end_time=False)
    _, t_end = slot_to_day_time(end_slot, is_end_time=True)
    return ScheduleBlock(
        block_id=f"{task.task_id}_P{chunk_idx}",
        task_id=task.task_id,
        title=task.title,
        day=day_s,
        start_time=t_start,
        end_time=t_end,
        start_slot=start_slot,
        end_slot=end_slot,
        duration_min=planned_min,
        priority=task.priority,
        category=task.category,
        cognitive_load=task.cognitive_load,
        deadline_slot=task.resolve_deadline_slot(),
        chunk_index=chunk_idx,
        total_chunks=total_chunks,
        state="ACCEPTED",
    )


def _make_summary(tasks_count: int, placed_count: int) -> ScheduleSummary:
    return ScheduleSummary(total_tasks_requested=tasks_count, tasks_placed=placed_count, tasks_unplaced=0)


def build_contrast_pairs(config: Optional[EvaluationConfig] = None) -> ContrastPairResult:
    """
    Self-test suite for OutputEvaluator inspired by Gombolay (2017 §5.3 tr. 131):
      Constructs Golden High-Productivity, Feasible-But-Low-Productivity, and Infeasible schedules
      on identical input and verifies exact 3-way discrimination + accurate ICEE provenance.
    """
    profile = CommitmentsProfile(
        student_id="CONTRAST_OWL_STUDENT",
        focus_preference="EVENING",  # Morning 06-12 = 1 (Low), Afternoon 12-18 = 2, Evening 18-24 = 3 (Peak)
        buffer_mode="COGNITIVE_LOAD",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30", is_hard_lock=True),
        fixed_events=[
            FixedEvent(event_id="MEAL_L", title="Lunch", day_of_week="ALL", start_time="12:00", end_time="12:45", category="MEAL"),
            FixedEvent(event_id="CLS_M", title="Lecture Mon", day_of_week="Monday", start_time="09:00", end_time="11:00", category="ACADEMIC_CLASS"),
        ],
    )
    tasks = [
        Task(task_id="H1", title="Deep Algorithm Design", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT"),
        Task(task_id="H2", title="Heavy Proof Writing", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM"),
        Task(task_id="H3", title="Research Paper Synthesis", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=4, cognitive_load=3, category="ASSIGNMENT"),
        Task(task_id="L1", title="Quick Reading Quiz", duration_min=45, deadline_day="Friday", deadline_time="23:59", priority=2, cognitive_load=1, category="DEADLINE"),
    ]
    # Note: with COGNITIVE_LOAD buffer, raw 60m load=3 -> planned 90m (6 slots); raw 45m load=1 -> planned 60m (4 slots).
    prepared = preprocess_tasks(profile, tasks)
    prep_map = {t.task_id: t for t in prepared}

    # 1. Golden Schedule: All load=3 placed in EVENING Peak 19:00-22:00 across Tue/Wed/Thu (<=1 heavy/day), >=15m gap, spread evenly
    golden_blocks = [
        _make_block(prep_map["H1"], 90, 1 * 96 + 76),  # Tue 19:00-20:30 (EVENING energy=3)
        _make_block(prep_map["H2"], 90, 2 * 96 + 76),  # Wed 19:00-20:30 (EVENING energy=3)
        _make_block(prep_map["H3"], 90, 3 * 96 + 76),  # Thu 19:00-20:30 (EVENING energy=3)
        _make_block(prep_map["L1"], 60, 0 * 96 + 56),  # Mon 14:00-15:00 (Light afternoon)
    ]
    golden_out = ScheduleOutput(
        status="SUCCESS",
        solver_used="GOLDEN_CONTRAST",
        execution_time_ms=1.0,
        summary=_make_summary(4, 4),
        blocks=golden_blocks,
    )

    # 2. Feasible-But-Low-Productivity Trap Schedule (G1=0, P1.1=100%, ZERO unplaced):
    # All 3 heavy blocks stuffed on Friday (Corne >2/day!), starting morning 07:00 (forced phase advance on Owl!),
    # back-to-back with ZERO recovery break (Albulescu violation!), and finishing right inside <10h before Friday 23:59,
    # PLUS evaluated against unbuffered execution risk if using tight packing -> L1 right before midnight.
    bad_blocks = [
        _make_block(prep_map["H1"], 90, 4 * 96 + 28),  # Fri 07:00-08:30 (Morning energy=1, 0 gap to H2!)
        _make_block(prep_map["H2"], 90, 4 * 96 + 34),  # Fri 08:30-10:00 (Morning energy=1, 0 break, 0 gap to H3!)
        _make_block(prep_map["H3"], 90, 4 * 96 + 40),  # Fri 10:00-11:30 (Morning energy=1, 3 heavy/Fri!)
        _make_block(prep_map["L1"], 60, 4 * 96 + 88),  # Fri 22:00-23:00 (inside <10h near deadline)
    ]
    bad_out = ScheduleOutput(
        status="SUCCESS",
        solver_used="FEASIBLE_BAD_CONTRAST",
        execution_time_ms=1.0,
        summary=_make_summary(4, 4),
        blocks=bad_blocks,
    )

    # 3. Invalid Schedule: H1 overlaps SLEEP (Mon 02:00-03:30)
    invalid_blocks = [
        _make_block(prep_map["H1"], 90, 8),  # Mon 02:00-03:30 -> overlaps SLEEP
        _make_block(prep_map["H2"], 90, 2 * 96 + 76),
        _make_block(prep_map["H3"], 90, 3 * 96 + 76),
        _make_block(prep_map["L1"], 60, 0 * 96 + 56),
    ]
    invalid_out = ScheduleOutput(
        status="SUCCESS",
        solver_used="INVALID_CONTRAST",
        execution_time_ms=1.0,
        summary=_make_summary(4, 4),
        blocks=invalid_blocks,
    )

    golden_rep = ScheduleEvaluator.evaluate(profile, tasks, golden_out, config=config)
    bad_rep = ScheduleEvaluator.evaluate(profile, tasks, bad_out, config=config)
    invalid_rep = ScheduleEvaluator.evaluate(profile, tasks, invalid_out, config=config)

    checks = [
        InvariantCheckResult(
            name="Contrast: Golden verdict is HIGH_PRODUCTIVITY",
            passed=(golden_rep.verdict == VerdictLabel.HIGH_PRODUCTIVITY),
            detail=f"got {golden_rep.verdict.value} (reasons={golden_rep.verdict_reasons_vi})",
        ),
        InvariantCheckResult(
            name="Contrast: Feasible-Bad verdict is FEASIBLE_BUT_LOW_PRODUCTIVITY",
            passed=(bad_rep.verdict == VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY),
            detail=f"got {bad_rep.verdict.value} (breaches={bad_rep.critical_breaches})",
        ),
        InvariantCheckResult(
            name="Contrast: Invalid verdict is INVALID",
            passed=(invalid_rep.verdict == VerdictLabel.INVALID),
            detail=f"got {invalid_rep.verdict.value} (g1={invalid_rep.gates.g1_total_violations})",
        ),
        InvariantCheckResult(
            name="Contrast: Golden beats Feasible-Bad on P2 HeavyPeak & Recovery & ForcedAdvance & P3 Corne",
            passed=(
                (golden_rep.p2_cognitive_biology.heavy_peak_match_pct if golden_rep.p2_cognitive_biology.heavy_peak_match_pct is not None else -1.0)
                > (bad_rep.p2_cognitive_biology.heavy_peak_match_pct if bad_rep.p2_cognitive_biology.heavy_peak_match_pct is not None else 101.0)
                and (golden_rep.p2_cognitive_biology.heavy_recovery_rate_pct if golden_rep.p2_cognitive_biology.heavy_recovery_rate_pct is not None else -1.0)
                > (bad_rep.p2_cognitive_biology.heavy_recovery_rate_pct if bad_rep.p2_cognitive_biology.heavy_recovery_rate_pct is not None else 101.0)
                and golden_rep.p2_cognitive_biology.forced_phase_advance_count
                < bad_rep.p2_cognitive_biology.forced_phase_advance_count
                and golden_rep.p3_sustainable_pacing.corne_lexicographic_vector
                < bad_rep.p3_sustainable_pacing.corne_lexicographic_vector
            ),
            detail=(
                f"Golden peak={golden_rep.p2_cognitive_biology.heavy_peak_match_pct} rec={golden_rep.p2_cognitive_biology.heavy_recovery_rate_pct} adv={golden_rep.p2_cognitive_biology.forced_phase_advance_count} corne={golden_rep.p3_sustainable_pacing.corne_lexicographic_vector}; "
                f"Bad peak={bad_rep.p2_cognitive_biology.heavy_peak_match_pct} rec={bad_rep.p2_cognitive_biology.heavy_recovery_rate_pct} adv={bad_rep.p2_cognitive_biology.forced_phase_advance_count} corne={bad_rep.p3_sustainable_pacing.corne_lexicographic_vector}"
            ),
        ),
        InvariantCheckResult(
            name="Contrast: ICEE critiques pinpoint exact culprit blocks",
            passed=(len(bad_rep.d1_icee_critiques) >= 2 and any("H1_P1" in c.block_ids for c in bad_rep.d1_icee_critiques)),
            detail=f"critiques={[ (c.pillar, c.block_ids) for c in bad_rep.d1_icee_critiques ]}",
        ),
    ]
    return ContrastPairResult(
        passed=all(c.passed for c in checks),
        golden_report=golden_rep,
        feasible_bad_report=bad_rep,
        invalid_report=invalid_rep,
        assertions=checks,
    )
