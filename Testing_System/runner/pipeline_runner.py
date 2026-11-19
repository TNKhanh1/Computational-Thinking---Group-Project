"""
Part 1 -> Run Project -> Part 2 Complete Pipeline Runner & Vietnamese Diagnostic Reporter.

Enforces Regime 1–6 Invariants (`Plan §4.3`) across all 5 solvers (plus Regime 6 repairs/overrun)
and formats both structured JSON reports and concise 4-block Vietnamese summary tables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from Testing_System.evaluator import ScheduleEvaluator, build_contrast_pairs
from Testing_System.generator import FuzzGenerator, GeneratedCaseBundle, InputGenerator
from Testing_System.runner.project_runner import (
    ProjectRunBundle,
    execute_project_direct,
    execute_project_http_e2e,
)
from Testing_System.schemas import (
    CrossSolverEntry,
    EvaluationConfig,
    EvaluationReport,
    InvariantCheckResult,
    RegimeName,
    RegimeRunResult,
    VerdictLabel,
)
from Testing_System.sut_adapter import FIVE_SOLVERS, ScheduleOutput, ScheduleSummary, preprocess_tasks


def _check_regime_invariants(
    bundle: GeneratedCaseBundle,
    run_bundle: ProjectRunBundle,
    solver_reports: Dict[str, EvaluationReport],
    repair_reports: Dict[str, EvaluationReport],
) -> List[InvariantCheckResult]:
    """Verify exact Regime PASS/FAIL invariants specified in `Testing_Plan/Testing_Plan.md §4.3`."""
    checks: List[InvariantCheckResult] = []
    regime = bundle.metadata.regime

    # Universal Invariant across ALL Regimes: every solver must have G1 == 0 and preserve valid PINNED blocks
    bad_g1 = [
        f"{name} (g1={rep.gates.g1_total_violations}, pins={rep.gates.g1_pin_integrity_violations})"
        for name, rep in solver_reports.items()
        if rep.gates.g1_total_violations > 0
    ]
    checks.append(
        InvariantCheckResult(
            name="Universal: All solvers satisfy G1 == 0 & PINNED integrity",
            passed=(len(bad_g1) == 0),
            detail="OK" if not bad_g1 else f"Failed: {bad_g1}",
        )
    )

    edf_rep = solver_reports.get("EDF")
    scored_rep = solver_reports.get("SCORED_GREEDY")
    bt_rep = solver_reports.get("BACKTRACK")

    if regime == RegimeName.LOOSE_FEASIBLE:
        unplaced_any = [
            f"{n}:{r.p1_value_timeliness.deadline_value_rate_pct}%"
            for n, r in solver_reports.items()
            if r.p1_value_timeliness.deadline_value_rate_pct < 100.0
        ]
        checks.append(
            InvariantCheckResult(
                name="Regime 1: All solvers achieve P1.1 == 100% under loose load",
                passed=(len(unplaced_any) == 0),
                detail="All 100%" if not unplaced_any else f"Drops: {unplaced_any}",
            )
        )
        if edf_rep and scored_rep:
            edf_peak = edf_rep.p2_cognitive_biology.heavy_peak_match_pct if edf_rep.p2_cognitive_biology.heavy_peak_match_pct is not None else 0.0
            sc_peak = scored_rep.p2_cognitive_biology.heavy_peak_match_pct if scored_rep.p2_cognitive_biology.heavy_peak_match_pct is not None else 0.0
            edf_win = edf_rep.p2_cognitive_biology.preferred_window_match_pct if edf_rep.p2_cognitive_biology.preferred_window_match_pct is not None else 0.0
            sc_win = scored_rep.p2_cognitive_biology.preferred_window_match_pct if scored_rep.p2_cognitive_biology.preferred_window_match_pct is not None else 0.0
            bt_peak = (bt_rep.p2_cognitive_biology.heavy_peak_match_pct if bt_rep.p2_cognitive_biology.heavy_peak_match_pct is not None else 0.0) if bt_rep else sc_peak
            bt_win = (bt_rep.p2_cognitive_biology.preferred_window_match_pct if bt_rep.p2_cognitive_biology.preferred_window_match_pct is not None else 0.0) if bt_rep else sc_win
            better_or_tied_at_100 = (
                (sc_peak > edf_peak or sc_win > edf_win)
                or (sc_peak >= edf_peak and sc_win >= edf_win and sc_peak >= 90.0)
            )
            checks.append(
                InvariantCheckResult(
                    name="Regime 1: SCORED_GREEDY/BACKTRACK beat or match peak/window vs Energy-Blind EDF",
                    passed=(better_or_tied_at_100 and (bt_peak >= edf_peak or bt_win >= edf_win)),
                    detail=(
                        f"EDF(peak={edf_peak}%, win={edf_win}%) vs "
                        f"SCORED_GREEDY(peak={sc_peak}%, win={sc_win}%) vs "
                        f"BACKTRACK(peak={bt_peak}%, win={bt_win}%)"
                    ),
                )
            )

    elif regime == RegimeName.TIGHT_DEADLINE_CLUSTER:
        # (a) Schaerf §5.1: drops must be judged against input tightness. The generator certifies the input
        #     as feasible (rho < 1, no capacity shortage), so G2 must NOT flag overload and every solver that
        #     still drops deadline work must be labelled SUBOPTIMAL_ALGORITHM_FAILURE (never OVERLOAD_TRIAGE).
        mislabelled = [
            f"{n}(overloaded={r.gates.is_structurally_overloaded}, verdict={r.verdict.value})"
            for n, r in solver_reports.items()
            if r.gates.is_structurally_overloaded
            or (r.p1_value_timeliness.unplaced_deadline_count > 0 and r.verdict != VerdictLabel.SUBOPTIMAL_ALGORITHM_FAILURE)
        ]
        drops = [
            f"{n}={r.p1_value_timeliness.deadline_value_rate_pct}%"
            for n, r in solver_reports.items()
            if r.p1_value_timeliness.deadline_value_rate_pct < 100.0
        ]
        checks.append(
            InvariantCheckResult(
                name="Regime 2: Feasible tight input -> G2 not overloaded & any drop labelled SUBOPTIMAL_ALGORITHM_FAILURE",
                passed=not mislabelled,
                detail=(f"Mislabelled: {mislabelled}" if mislabelled else "OK")
                + (f" | solver drops (finding, not harness failure): {drops}" if drops else " | no drops"),
            )
        )
        # (b) Daniels & Kouvelis worst-case view: survival must be monotone non-increasing in shock size
        #     (P1.1 >= Shock@+25% >= Shock@+50%), otherwise the shock simulation itself is broken.
        non_monotone = []
        for n, r in solver_reports.items():
            seq = [r.p1_value_timeliness.deadline_value_rate_pct] + [
                sr.survived_priority_pct
                for sr in sorted(r.p4_robustness_stability.shock_results, key=lambda x: x.shock_pct)
            ]
            if any(seq[i + 1] > seq[i] + 1e-9 for i in range(len(seq) - 1)):
                non_monotone.append(f"{n}:{seq}")
        checks.append(
            InvariantCheckResult(
                name="Regime 2: Shock survival monotone (P1.1 >= Shock@+25% >= Shock@+50%) for every solver",
                passed=not non_monotone,
                detail="OK" if not non_monotone else f"Non-monotone: {non_monotone}",
            )
        )

    elif regime == RegimeName.CIRCADIAN_SJL_AND_RECOVERY:
        if edf_rep and scored_rep:
            edf_adv = edf_rep.p2_cognitive_biology.forced_phase_advance_count
            sc_adv = scored_rep.p2_cognitive_biology.forced_phase_advance_count
            edf_pk = edf_rep.p2_cognitive_biology.heavy_peak_match_pct if edf_rep.p2_cognitive_biology.heavy_peak_match_pct is not None else 0.0
            sc_pk = scored_rep.p2_cognitive_biology.heavy_peak_match_pct if scored_rep.p2_cognitive_biology.heavy_peak_match_pct is not None else 0.0
            checks.append(
                InvariantCheckResult(
                    name="Regime 3: SCORED_GREEDY avoids/reduces forced Owl phase advance & lifts HeavyPeak vs EDF",
                    passed=(sc_adv <= edf_adv and sc_pk >= edf_pk and (sc_adv < edf_adv or sc_pk > edf_pk or not scored_rep.p2_cognitive_biology.is_evening_chronotype)),
                    detail=f"EDF(forced_adv={edf_adv}, peak={edf_pk}%) vs SCORED_GREEDY(forced_adv={sc_adv}, peak={sc_pk}%)",
                )
            )
            sjl_ok = (
                scored_rep.p2_cognitive_biology.sjl_minutes is not None
                and scored_rep.p2_cognitive_biology.class_days_count > 0
                and scored_rep.p2_cognitive_biology.non_class_days_count > 0
                and scored_rep.p2_cognitive_biology.heavy_recovery_rate_pct is not None
            )
            checks.append(
                InvariantCheckResult(
                    name="Regime 3: Circular SJL & >10m Cognitive Recovery metrics populated cleanly",
                    passed=sjl_ok,
                    detail=(
                        f"SJL={scored_rep.p2_cognitive_biology.sjl_minutes}m ({scored_rep.p2_cognitive_biology.sjl_direction}), "
                        f"recovery={scored_rep.p2_cognitive_biology.heavy_recovery_rate_pct}%"
                    ),
                )
            )

    elif regime == RegimeName.PROCRASTINATION_ONSET_AND_DAG:
        # Justified strategic idling / start_after / circadian deferral must not trigger unjustified <10h false positives on SCORED_GREEDY
        if scored_rep:
            checks.append(
                InvariantCheckResult(
                    name="Regime 4: Justified DAG / start_after / circadian deferrals not penalized as unjustified <10h crowding",
                    passed=(
                        scored_rep.p1_value_timeliness.min_preparatory_margin_min is not None
                        and scored_rep.p1_value_timeliness.deadline_value_rate_pct == 100.0
                        and scored_rep.p1_value_timeliness.unjustified_last_10h_crowding_pct == 0.0
                    ),
                    detail=(
                        f"unjustified_10h={scored_rep.p1_value_timeliness.unjustified_last_10h_crowding_pct}%, "
                        f"prep_margin={scored_rep.p1_value_timeliness.min_preparatory_margin_min}m, "
                        f"justified_deferrals={scored_rep.p1_value_timeliness.justified_deferrals_count}"
                    ),
                )
            )

    elif regime == RegimeName.OVERLOAD_INFEASIBLE:
        overload_ok = all(
            r.gates.is_structurally_overloaded and r.verdict == VerdictLabel.OVERLOAD_TRIAGE
            for r in solver_reports.values()
        )
        checks.append(
            InvariantCheckResult(
                name="Regime 5: G2 detects rho > 1 overload & assigns OVERLOAD_TRIAGE verdict",
                passed=overload_ok,
                detail="; ".join(
                    f"{n}: rho_d={r.gates.rho_deadline}, verdict={r.verdict.value}, val={r.p1_value_timeliness.deadline_value_rate_pct}%"
                    for n, r in solver_reports.items()
                ),
            )
        )
        # Verify priority-aware greedy solvers retain >= deadline value than pure EDF under mixed-deadline overload
        prio_check_solvers = [r for n, r in solver_reports.items() if n in ("SCORED_GREEDY", "WSPT")]
        retained_ok = all(
            r.p1_value_timeliness.deadline_value_rate_pct >= (edf_rep.p1_value_timeliness.deadline_value_rate_pct if edf_rep else 0.0)
            for r in prio_check_solvers
        )
        checks.append(
            InvariantCheckResult(
                name="Regime 5: Priority-aware solvers (SCORED_GREEDY/WSPT) retain >= deadline value than blind EDF under overload",
                passed=retained_ok,
                detail=", ".join(
                    f"{n}={r.p1_value_timeliness.deadline_value_rate_pct}%" for n, r in solver_reports.items()
                ),
            )
        )

    elif regime == RegimeName.DISRUPTION_AND_OVERRUN_SERIES:
        # Compare Level A LOCAL_INSERTION vs FULL_REBUILD + Verify PINNED survival & zero G1 violations across all repairs
        bad_rep_g1 = [
            f"{k} (g1={rep.gates.g1_total_violations}, pins={rep.gates.g1_pin_integrity_violations})"
            for k, rep in repair_reports.items()
            if rep.gates.g1_total_violations > 0
        ]
        checks.append(
            InvariantCheckResult(
                name="Regime 6: All repair & overrun schedules preserve G1 == 0 & 100% valid PINNED blocks",
                passed=(len(bad_rep_g1) == 0 and len(repair_reports) > 0),
                detail="OK" if not bad_rep_g1 else f"Failed repairs: {bad_rep_g1}",
            )
        )
        # Fox et al. (2006): repair should give at least the stability of replanning on every variant
        # (weak dominance per level). On the compound Level C (several disruptions, Fox §5.1 increasing
        # perturbation), repair must be STRICTLY more stable in D(pi0, pi1).
        for level in ("A", "C"):
            loc = repair_reports.get(f"DISRUPTION_LVL_{level}::LOCAL_INSERTION")
            reb = repair_reports.get(f"DISRUPTION_LVL_{level}::FULL_REBUILD")
            if not (
                loc and reb
                and loc.p4_robustness_stability.post_repair_stability
                and reb.p4_robustness_stability.post_repair_stability
            ):
                continue
            s_loc = loc.p4_robustness_stability.post_repair_stability
            s_reb = reb.p4_robustness_stability.post_repair_stability
            d_ok = (
                s_loc.symmetric_plan_difference < s_reb.symmetric_plan_difference
                if level == "C"
                else s_loc.symmetric_plan_difference <= s_reb.symmetric_plan_difference
            )
            orig_better_or_eq = (s_loc.orig_pct if s_loc.orig_pct is not None else 100.0) >= (
                s_reb.orig_pct if s_reb.orig_pct is not None else 0.0
            )
            diff_lower_or_eq = (s_loc.diff_pct if s_loc.diff_pct is not None else 0.0) <= (
                s_reb.diff_pct if s_reb.diff_pct is not None else 100.0
            )
            eq1_preserved = (s_loc.eq_1st is True) or (s_reb.eq_1st is False)
            dt_lower_or_eq = s_loc.mean_abs_time_shift_min <= s_reb.mean_abs_time_shift_min + 1e-6
            inv_lower_or_eq = s_loc.sequence_inversions <= s_reb.sequence_inversions
            strict_note = " (D strictly smaller required)" if level == "C" else ""
            checks.append(
                InvariantCheckResult(
                    name=f"Regime 6 Level {level}: LOCAL_INSERTION vs FULL_REBUILD on Fox D, Orig%, Diff%, Eq1st, Δt, inversions{strict_note}",
                    passed=(d_ok and orig_better_or_eq and diff_lower_or_eq and eq1_preserved and dt_lower_or_eq and inv_lower_or_eq),
                    detail=(
                        f"LOCAL(D={s_loc.symmetric_plan_difference}, Eq1st={s_loc.eq_1st}, Orig={s_loc.orig_pct}%, Diff={s_loc.diff_pct}%, dt={s_loc.mean_abs_time_shift_min}m, inv={s_loc.sequence_inversions}) vs "
                        f"REBUILD(D={s_reb.symmetric_plan_difference}, Eq1st={s_reb.eq_1st}, Orig={s_reb.orig_pct}%, Diff={s_reb.diff_pct}%, dt={s_reb.mean_abs_time_shift_min}m, inv={s_reb.sequence_inversions})"
                    ),
                )
            )

    return checks


def run_single_regime_case(
    regime: RegimeName,
    seed: int = 42,
    use_http_e2e: bool = False,
    config: Optional[EvaluationConfig] = None,
    solvers: Optional[Tuple[str, ...]] = None,
    db_path: Optional[str] = None,
) -> RegimeRunResult:
    """Execute complete Gen Input -> Run Project -> Evaluate Output pipeline for 1 (regime, seed)."""
    cfg = config or EvaluationConfig()
    bundle = InputGenerator.generate(regime=regime, seed=seed)

    eff_solvers = solvers or (
        ("EDF", "SCORED_GREEDY", "BACKTRACK") if use_http_e2e else FIVE_SOLVERS
    )
    if use_http_e2e:
        run_bundle = execute_project_http_e2e(bundle, solvers=eff_solvers, db_path=db_path)
    else:
        run_bundle = execute_project_direct(bundle, solvers=eff_solvers)

    solver_reports: Dict[str, EvaluationReport] = {}
    for name, out in run_bundle.solver_outputs.items():
        solver_reports[name] = ScheduleEvaluator.evaluate(
            profile=bundle.profile,
            tasks=bundle.tasks,
            schedule=out,
            config=cfg,
            input_pinned_blocks=bundle.pinned_blocks,
        )

    ranking = ScheduleEvaluator.compare_solvers(solver_reports, config=cfg)

    repair_reports: Dict[str, EvaluationReport] = {}
    for r_key, rec in run_bundle.repair_records.items():
        # Filter valid pins not directly overwritten by disruption window
        valid_pins_after_disr = [
            pb
            for pb in bundle.pinned_blocks
            if rec.disruption_span[0] < 0
            or pb.end_slot <= rec.disruption_span[0]
            or pb.start_slot >= rec.disruption_span[1]
        ]
        repair_reports[r_key] = ScheduleEvaluator.evaluate(
            profile=rec.disruption_profile,
            tasks=bundle.tasks,
            schedule=rec.repaired_schedule,
            config=cfg,
            input_pinned_blocks=valid_pins_after_disr if rec.check_pinned_blocks else None,
            baseline_schedule=rec.baseline_schedule,
            disruption_span=rec.disruption_span if rec.disruption_span[0] >= 0 else None,
            repair_now_slot=rec.repair_now_slot,
            is_overrun_context=rec.is_overrun_context,
            completion_logs=rec.completion_logs or None,
        )

    invariants = _check_regime_invariants(bundle, run_bundle, solver_reports, repair_reports)
    return RegimeRunResult(
        metadata=bundle.metadata,
        execution_mode=run_bundle.execution_mode,
        solver_reports=solver_reports,
        cross_solver_ranking=ranking,
        repair_evaluations=repair_reports,
        invariant_checks=invariants,
        all_invariants_passed=all(c.passed for c in invariants),
    )


def _check_fuzz_invariants(
    bundle: GeneratedCaseBundle,
    solver_reports: Dict[str, EvaluationReport],
    config: Optional[EvaluationConfig] = None,
) -> List[InvariantCheckResult]:
    checks: List[InvariantCheckResult] = []
    if bundle.witness_blocks is not None:
        w_blocks = sorted(bundle.witness_blocks, key=lambda b: (b.start_slot, b.end_slot))
        w_sched = ScheduleOutput(
            status="SUCCESS",
            solver_used="WITNESS_ORACLE",
            execution_time_ms=0.0,
            blocks=w_blocks,
            unplaced_tasks=[],
            summary=ScheduleSummary(
                total_tasks_requested=len(preprocess_tasks(bundle.profile, bundle.tasks)),
                tasks_placed=len({b.task_id for b in w_blocks}),
                tasks_unplaced=0,
            ),
        )
        w_rep = ScheduleEvaluator.evaluate(
            profile=bundle.profile,
            tasks=bundle.tasks,
            schedule=w_sched,
            config=config,
            input_pinned_blocks=bundle.pinned_blocks,
        )
        checks.append(
            InvariantCheckResult(
                name="Fuzz Witness: Planted solution proves G1 == 0, P1.1 == 100%, not overloaded",
                passed=(
                    w_rep.gates.g1_total_violations == 0
                    and w_rep.p1_value_timeliness.deadline_value_rate_pct == 100.0
                    and not w_rep.gates.is_structurally_overloaded
                ),
                detail=(
                    f"G1={w_rep.gates.g1_total_violations}, "
                    f"P1.1={w_rep.p1_value_timeliness.deadline_value_rate_pct}%, "
                    f"witness_verdict={w_rep.verdict.value}"
                ),
            )
        )

    bad_g1 = [
        f"{name} (g1={rep.gates.g1_total_violations}, pins={rep.gates.g1_pin_integrity_violations})"
        for name, rep in solver_reports.items()
        if rep.gates.g1_total_violations > 0
    ]
    checks.append(
        InvariantCheckResult(
            name="Universal: All solvers satisfy G1 == 0 & PINNED integrity",
            passed=(len(bad_g1) == 0),
            detail="OK" if not bad_g1 else f"Failed: {bad_g1}",
        )
    )

    non_monotone = []
    for n, r in solver_reports.items():
        seq = [r.p1_value_timeliness.deadline_value_rate_pct] + [
            sr.survived_priority_pct
            for sr in sorted(r.p4_robustness_stability.shock_results, key=lambda x: x.shock_pct)
        ]
        if any(seq[i + 1] > seq[i] + 1e-9 for i in range(len(seq) - 1)):
            non_monotone.append(f"{n}:{seq}")
    checks.append(
        InvariantCheckResult(
            name="Fuzz: Shock survival monotone (P1.1 >= Shock@+25% >= Shock@+50%) for every solver",
            passed=not non_monotone,
            detail="OK" if not non_monotone else f"Non-monotone: {non_monotone}",
        )
    )

    if bundle.metadata.fuzz_tier == "OVERLOAD":
        ov_ok = all(
            r.gates.is_structurally_overloaded and r.verdict == VerdictLabel.OVERLOAD_TRIAGE
            for r in solver_reports.values()
        )
        checks.append(
            InvariantCheckResult(
                name="Fuzz Overload: G2 detects overload & assigns OVERLOAD_TRIAGE",
                passed=ov_ok,
                detail=", ".join(f"{n}={r.verdict.value}" for n, r in solver_reports.items()),
            )
        )
    return checks


def run_fuzz_case(
    seed: int,
    tier: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
    solvers: Optional[Tuple[str, ...]] = None,
) -> RegimeRunResult:
    """Execute Gen Random Fuzz Input -> Run 5 Solvers -> Evaluate v2.1 Output for one fuzz seed."""
    cfg = config or EvaluationConfig()
    bundle = FuzzGenerator.generate(seed=seed, tier=tier)
    eff_solvers = solvers or FIVE_SOLVERS
    run_bundle = execute_project_direct(bundle, solvers=eff_solvers)

    solver_reports: Dict[str, EvaluationReport] = {
        name: ScheduleEvaluator.evaluate(
            profile=bundle.profile,
            tasks=bundle.tasks,
            schedule=out,
            config=cfg,
            input_pinned_blocks=bundle.pinned_blocks,
        )
        for name, out in run_bundle.solver_outputs.items()
    }
    ranking = ScheduleEvaluator.compare_solvers(solver_reports, config=cfg)
    invariants = _check_fuzz_invariants(bundle, solver_reports, config=cfg)
    return RegimeRunResult(
        metadata=bundle.metadata,
        execution_mode=run_bundle.execution_mode,
        solver_reports=solver_reports,
        cross_solver_ranking=ranking,
        repair_evaluations={},
        invariant_checks=invariants,
        all_invariants_passed=all(c.passed for c in invariants),
    )


def run_fuzz_benchmark(
    seeds: List[int],
    tier: Optional[str] = None,
    output_json_path: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
) -> Dict[str, Any]:
    """Run procedural random fuzz suite over all supplied seeds and optionally export JSON."""
    runs = [run_fuzz_case(seed=s, tier=tier, config=config) for s in seeds]
    payload = {
        "overall_passed": all(r.all_invariants_passed for r in runs),
        "fuzz_runs": [r.model_dump(mode="json") for r in runs],
    }
    if output_json_path:
        out_p = Path(output_json_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def format_vietnamese_summary(res: RegimeRunResult) -> str:
    """Format 4-block human-readable Vietnamese v2.1 diagnostic report."""
    m = res.metadata
    rho_d_str = f" | ρ_deadline={m.tightness_rho_deadline}" if m.tightness_rho_deadline is not None else ""
    kind_hdr = (
        f"FUZZ[{m.fuzz_tier} | {m.persona_archetype}]"
        if m.is_fuzz
        else m.regime.value
    )
    lines: List[str] = [
        f"=== BÁO CÁO ĐÁNH GIÁ (v2.1): {kind_hdr} (seed={m.seed}, mode={res.execution_mode}) ===",
        f"[1] Bối cảnh Input: Chronotype={m.chronotype} | Horizon={m.horizon_days} ngày | Buffer={m.buffer_mode} | Tải ρ={m.tightness_rho} ({m.planned_demand_slots}/{m.usable_free_slots} slots){rho_d_str}",
        "",
        "[2 & 3] Bảng Đối Chiếu v2.1 (Cổng 0 + Thứ tự Từ Điển 10 Cấp):",
        f"{'Rank':<4} {'Solver':<14} {'Verdict':<29} {'G1':<3} {'P1.1%':<6} {'Shk25':<6} {'Rec/Stk/PCl':<12} {'OffP/APk%':<10} {'<10h':<6} {'Crn/MaxD':<11} {'Ctx':<4} {'Hab/Prf':<10} {'SJL/TStd':<11} {'ms':<6}",
    ]
    for row in res.cross_solver_ranking:
        rc = f"{row.p2_recovery_rate_pct:.0f}" if row.p2_recovery_rate_pct is not None else "-"
        rec_grp = f"{rc}/{row.v2_max_streak_l2_min}/{row.v2_post_class_violations}"
        apk = f"{row.v2_achievable_peak_pct:.0f}" if row.v2_achievable_peak_pct is not None else "N/A"
        bio_grp = f"{row.v2_off_peak_mismatch}/{apk}"
        corne = "/".join(str(x) for x in row.p3_corne_vector)
        cap_grp = f"{corne}/{row.v2_max_daily_total_min}m"
        hab_s = f"{row.v2_habit_rate_pct:.0f}" if row.v2_habit_rate_pct is not None else "-"
        prf_s = f"{row.v2_preferred_window_pct:.0f}" if row.v2_preferred_window_pct is not None else "-"
        pref_grp = f"{hab_s}/{prf_s}"
        sjl_s = f"{row.v2_sjl_effective_min:.0f}" if row.v2_sjl_effective_min is not None else "-"
        pace_grp = f"{sjl_s}/{row.v2_total_daily_std_min:.0f}"
        lines.append(
            f"#{row.lexicographic_rank:<3} {row.solver_name:<14} {row.verdict.value:<29} {row.g1_violations:<3} "
            f"{row.p1_value_rate_pct:<6.1f} {row.p4_shock25_survived_pct:<6.1f} {rec_grp:<12} {bio_grp:<10} "
            f"{row.p1_unjustified_last10h_pct:<6.1f} {cap_grp:<11} {row.v2_context_switches:<4} {pref_grp:<10} {pace_grp:<11} {row.exec_ms:<6.1f}"
        )

    if res.repair_evaluations:
        lines.append("")
        lines.append("[3b] Đánh giá Ổn định Sau Sửa Lịch / Tràn Giờ (P4.2):")
        for label, r_rep in res.repair_evaluations.items():
            st = r_rep.p4_robustness_stability.post_repair_stability
            if st:
                lines.append(
                    f"  • {label}: G1={r_rep.gates.g1_total_violations}, D(π₀,π₁)={st.symmetric_plan_difference}, "
                    f"Eq1st={st.eq_1st}, Orig={st.orig_pct}%, Diff={st.diff_pct}%, Δt={st.mean_abs_time_shift_min}m, "
                    f"Inv={st.sequence_inversions}, Effort={st.rescheduling_effort}"
                )

    lines.append("")
    top_solver = res.cross_solver_ranking[0].solver_name if res.cross_solver_ranking else "SCORED_GREEDY"
    top_rep = res.solver_reports.get(top_solver)
    lines.append(f"[4] Top Cảnh Báo ICEE cho phương án #1 ({top_solver}):")
    if top_rep and top_rep.d1_icee_critiques:
        for idx, c in enumerate(top_rep.d1_icee_critiques, start=1):
            lines.append(f"  {idx}. [{c.severity}][{c.pillar}] {c.summary_vi} → {c.suggested_action_vi} ({c.paper_reference})")
    else:
        lines.append("  • Không phát hiện cảnh báo suy giảm năng suất nghiêm trọng nào.")

    lines.append("")
    lines.append(f"[Invariants]: {'PASS' if res.all_invariants_passed else 'FAIL'}")
    for inv in res.invariant_checks:
        mark = "PASS" if inv.passed else "FAIL"
        lines.append(f"  - [{mark}] {inv.name} :: {inv.detail}")

    return "\n".join(lines)


def run_full_benchmark_suite(
    seeds: Optional[List[int]] = None,
    use_http_e2e: bool = False,
    output_json_path: Optional[str] = None,
    config: Optional[EvaluationConfig] = None,
) -> Dict[str, Any]:
    """Run Contrast Pairs self-test + all 6 Regimes across configured seeds and optionally export JSON."""
    seed_list = seeds or [42, 101]
    contrast = build_contrast_pairs(config=config)

    regime_results: List[RegimeRunResult] = []
    for reg in RegimeName:
        for s in seed_list:
            regime_results.append(
                run_single_regime_case(regime=reg, seed=s, use_http_e2e=use_http_e2e, config=config)
            )

    all_passed = contrast.passed and all(r.all_invariants_passed for r in regime_results)
    payload = {
        "overall_passed": all_passed,
        "contrast_pairs": contrast.model_dump(mode="json"),
        "regime_runs": [r.model_dump(mode="json") for r in regime_results],
    }

    if output_json_path:
        out_p = Path(output_json_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return payload
