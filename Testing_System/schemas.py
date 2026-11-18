"""
Pure Leaf Schemas (INV-2) for the 3-Tier Productivity Evaluation & 2-Part Test System.

Does NOT import solvers, controller, or FastAPI/web modules so domain evaluation schemas
remain clean, typed, JSON-serializable, and independent.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RegimeName(str, Enum):
    LOOSE_FEASIBLE = "REGIME_1_LOOSE_FEASIBLE"
    TIGHT_DEADLINE_CLUSTER = "REGIME_2_TIGHT_DEADLINE_CLUSTER"
    CIRCADIAN_SJL_AND_RECOVERY = "REGIME_3_CIRCADIAN_SJL_AND_RECOVERY"
    PROCRASTINATION_ONSET_AND_DAG = "REGIME_4_PROCRASTINATION_ONSET_AND_DAG"
    OVERLOAD_INFEASIBLE = "REGIME_5_OVERLOAD_INFEASIBLE"
    DISRUPTION_AND_OVERRUN_SERIES = "REGIME_6_DISRUPTION_AND_OVERRUN_SERIES"


class VerdictLabel(str, Enum):
    HIGH_PRODUCTIVITY = "HIGH_PRODUCTIVITY"
    FEASIBLE_BUT_LOW_PRODUCTIVITY = "FEASIBLE_BUT_LOW_PRODUCTIVITY"
    SUBOPTIMAL_ALGORITHM_FAILURE = "SUBOPTIMAL_ALGORITHM_FAILURE"
    OVERLOAD_TRIAGE = "OVERLOAD_TRIAGE"
    INVALID = "INVALID"


class EvaluationConfig(BaseModel):
    """
    Configurable Project Policy Parameters (explicitly separated from fixed paper facts).

    Paper-derived boundaries used directly in evaluation logic:
      - Albulescu et al. (2022): recovery break > 10 min for cognitively demanding tasks (15m >= 1 slot)
      - Smarr & Schirmer (2018): empirical SJL benchmark > 30 min; circular 24h radians
      - Svartdal et al. / Howell (2018): last-minute compression window < 10h (only when window > 10h)
      - Corne et al. / Schaerf (1999): > 2 heavy sessions/day; reference clustering weights 10:3:1

    Fields below are project-tunable parameters (Daniels & Kouvelis shock levels, verdict policy tolerances,
    and Myers Towel UI rescheduling effort boundaries).
    """

    shock_levels_pct: List[float] = Field(default_factory=lambda: [25.0, 50.0])
    max_icee_critiques: int = Field(default=5, ge=1, le=10)
    near_term_window_slots: int = Field(default=96, ge=4)  # 24h lookahead for Eq 1st / Orig% / Diff%

    # Configurable Verdict Policy tolerances (used only for flagging FEASIBLE_BUT_LOW_PRODUCTIVITY)
    critical_shock25_min_pct: float = Field(default=70.0)
    moderate_shock25_min_pct: float = Field(default=85.0)
    moderate_heavy_peak_min_pct: float = Field(default=50.0)
    critical_heavy_peak_min_pct: float = Field(default=25.0)
    moderate_onset_delay_max_pct: float = Field(default=60.0)
    critical_last10h_crowding_max_pct: float = Field(default=50.0)
    moderate_last10h_crowding_max_pct: float = Field(default=25.0)
    moderate_max_daily_load_std_min: float = Field(default=150.0)

    # Myers Towel UI Rescheduling Effort bands (based on fraction of future blocks disrupted)
    effort_medium_min_diff_ratio: float = Field(default=0.10)
    effort_high_min_diff_ratio: float = Field(default=0.35)


class GateContextMetrics(BaseModel):
    """Tier 0: G1 (Hard Feasibility & Pin Integrity) + G2 (Input Tightness Context)."""

    g1_total_violations: int = 0
    g1_is_feasible: bool = True
    g1_h1_h5_violations: int = 0
    g1_start_after_violations: int = 0
    g1_before_now_violations: int = 0
    g1_splitting_order_violations: int = 0
    g1_incomplete_duration_violations: int = 0
    g1_pin_integrity_violations: int = 0
    g1_pin_total_valid_input: int = 0
    g1_pin_preserved_count: int = 0
    g1_violation_details: List[str] = Field(default_factory=list)

    # G2 Tightness Context
    horizon_slots: int = 672
    now_slot: int = 0
    total_valid_tasks: int = 0
    deadline_tasks_count: int = 0
    habit_tasks_count: int = 0
    total_planned_slots: int = 0
    deadline_planned_slots: int = 0
    habit_planned_slots: int = 0
    usable_free_slots_horizon: int = 0
    usable_free_slots_before_deadlines: int = 0
    rho_total: float = 0.0
    rho_deadline: float = 0.0
    is_structurally_overloaded: bool = False


class Pillar1ValueTimeliness(BaseModel):
    """P1: Effective Value Delivery & Anti-Procrastination Timeliness."""

    # P1.1 Value & Distance to Feasibility
    deadline_value_rate_pct: float = 100.0
    deadline_priority_achieved: int = 0
    deadline_priority_total: int = 0
    missed_deadline_priority: int = 0
    unplaced_deadline_count: int = 0
    unplaced_deadline_min: int = 0
    missed_deadline_task_ids: List[str] = Field(default_factory=list)
    habit_value_rate_pct: Optional[float] = None
    unplaced_habit_count: int = 0
    min_slack_margin_min: Optional[float] = None
    mean_slack_margin_min: Optional[float] = None

    # P1.2 Anti-Procrastination & Onset
    mean_onset_delay_pct: Optional[float] = None
    heavy_onset_delay_pct: Optional[float] = None
    min_preparatory_margin_min: Optional[float] = None
    unjustified_last_10h_crowding_pct: float = 0.0
    unjustified_last_10h_task_ids: List[str] = Field(default_factory=list)
    eligible_wide_window_tasks: int = 0
    justified_deferrals_count: int = 0


class Pillar2CognitiveBiology(BaseModel):
    """P2: Cognitive Power, Recovery Breaks & Biological/Circular Alignment."""

    # P2.1 Circadian Peak & Phase Advance
    has_heavy_tasks: bool = False
    heavy_peak_match_pct: Optional[float] = None
    has_preferred_window_tasks: bool = False
    preferred_window_match_pct: Optional[float] = None
    forced_phase_advance_count: int = 0
    forced_phase_advance_blocks: List[str] = Field(default_factory=list)
    forced_phase_advance_task_ids: List[str] = Field(default_factory=list)
    is_evening_chronotype: bool = False

    # P2.2 Albulescu Recovery (> 10 min)
    heavy_sessions_total: int = 0
    heavy_sessions_with_gt10m_break: int = 0
    heavy_recovery_rate_pct: Optional[float] = None
    missing_break_block_ids: List[str] = Field(default_factory=list)
    max_uninterrupted_work_min: int = 0
    crunch_tier_used: int = 0

    # P2.3 Circular SJL & Phase Dispersion
    sleep_midpoint_slot: int = 12
    sjl_minutes: Optional[float] = None
    sjl_direction: Optional[str] = None  # PHASE_ADVANCE | PHASE_DELAY | ALIGNED | N/A
    sjl_exceeds_30m: Optional[bool] = None
    class_days_count: int = 0
    non_class_days_count: int = 0
    solver_induced_class_day_shift_min: Optional[float] = None
    cross_day_phase_std_min: Optional[float] = None
    pre_bedtime_heavy_count: int = 0
    pre_bedtime_heavy_block_ids: List[str] = Field(default_factory=list)


class Pillar3SustainablePacing(BaseModel):
    """P3: Weekly Spreading, Utilization Adequacy, Clustering & Context Switching."""

    # P3.1 Dispersion & Utilization
    active_days_count: int = 0
    daily_load_minutes: List[int] = Field(default_factory=list)
    daily_load_std_min: float = 0.0
    daily_util_std_pct: float = 0.0
    awake_utilization_pct: float = 0.0

    # P3.2 Clustering & Setup Costs
    heavy_day_overload_days: int = 0
    overload_heavy_block_ids: List[str] = Field(default_factory=list)
    adjacent_heavy_pairs: int = 0
    adjacent_heavy_block_ids: List[str] = Field(default_factory=list)
    meal_boundary_offenses: int = 0
    corne_reference_penalty: int = 0  # 10*overload + 3*adjacent + 1*meal (Corne 10:3:1)
    context_switches: int = 0
    batched_pairs: int = 0


class ShockScenarioMetrics(BaseModel):
    """Simulation results for a single configured duration shock (+s%)."""

    shock_pct: float
    survived_priority_pct: float
    survived_tasks_count: int
    total_deadline_tasks: int
    overflow_blocks_count: int
    absorbed_by_internal_buffer_count: int
    cascade_collisions_count: int
    failed_task_ids: List[str] = Field(default_factory=list)


class PostRepairStabilityMetrics(BaseModel):
    """P4.2 Stability & Near-Term Preservation comparing baseline pi0 vs repaired pi1."""

    now_slot_reference: int = 0
    pi0_future_actions_count: int = 0
    pi1_future_actions_count: int = 0
    symmetric_plan_difference: int = 0  # Fox Def. 2: |pi1 \ pi0| + |pi0 \ pi1|
    eq_1st: Optional[bool] = None
    orig_pct: Optional[float] = None
    diff_pct: Optional[float] = None
    mean_abs_time_shift_min: float = 0.0
    sequence_inversions: int = 0
    moved_blocks_count: int = 0
    unplaced_from_baseline_count: int = 0
    unaffected_stability_pct: float = 100.0
    unnecessary_repair_flag: bool = False
    rescheduling_effort: str = "LOW"  # LOW | MEDIUM | HIGH (Myers Towel UI)


class Pillar4RobustnessStability(BaseModel):
    """P4: Buffer Adequacy, Shock Survival Under Uncertainty & Plan Stability."""

    true_buffer_task_pct: float = 0.0
    buffered_tasks_count: int = 0
    total_tasks_checked: int = 0
    zero_slack_risk_blocks: int = 0
    shock_results: List[ShockScenarioMetrics] = Field(default_factory=list)
    realized_mean_abs_deviation_min: Optional[float] = None
    realized_actual_to_estimate_ratio: Optional[float] = None
    post_repair_stability: Optional[PostRepairStabilityMetrics] = None


class ICEECritique(BaseModel):
    """D1: Actionable, non-noisy explanation item with provenance (Myers ICEE + Gombolay §7.2.1)."""

    severity: str  # CRITICAL | WARNING | INFO
    pillar: str    # G1 | G2 | P1.1 | P1.2 | P2.1 | P2.2 | P2.3 | P3.1 | P3.2 | P4.1 | P4.2
    impact_rank: int
    task_ids: List[str] = Field(default_factory=list)
    block_ids: List[str] = Field(default_factory=list)
    summary_vi: str
    rationale_vi: str
    suggested_action_vi: str
    paper_reference: str


class AuxiliaryDiagnostics(BaseModel):
    """D2 Auxiliary solver diagnostics (kept separate from core productivity verdict)."""

    fragmentation_index_pct: float = 0.0
    execution_time_ms: float = 0.0
    work_rhythm_compliance_pct: float = 100.0
    habit_completion_pct: Optional[float] = None
    existing_deep_peak_match_pct: float = 100.0
    existing_experience_rating: float = 1.0


class EvaluationReport(BaseModel):
    """Complete 3-Tier Evaluation Output (Natural Uncompressed Metric Vectors + Verdict)."""

    solver_used: str
    verdict: VerdictLabel
    verdict_reasons_vi: List[str] = Field(default_factory=list)
    critical_breaches: List[str] = Field(default_factory=list)
    moderate_warnings: List[str] = Field(default_factory=list)
    gates: GateContextMetrics
    p1_value_timeliness: Pillar1ValueTimeliness
    p2_cognitive_biology: Pillar2CognitiveBiology
    p3_sustainable_pacing: Pillar3SustainablePacing
    p4_robustness_stability: Pillar4RobustnessStability
    d1_icee_critiques: List[ICEECritique] = Field(default_factory=list)
    diagnostics: AuxiliaryDiagnostics
    config_used: EvaluationConfig


class CrossSolverEntry(BaseModel):
    """One row of D2 Cross-Solver Comparison ranked by Lexicographic Tuple."""

    solver_name: str
    lexicographic_rank: int
    verdict: VerdictLabel
    g1_violations: int
    p1_value_rate_pct: float
    p4_shock25_survived_pct: float
    p2_heavy_peak_pct: Optional[float]
    p2_recovery_rate_pct: Optional[float]
    p2_forced_phase_advance: int
    p1_unjustified_last10h_pct: float
    p2_sjl_minutes: Optional[float]
    p3_corne_penalty: int
    p3_daily_load_std_min: float
    exec_ms: float


class GeneratedTestMetadata(BaseModel):
    """Reproducible metadata emitted by InputGenerator (Part 1)."""

    seed: int
    regime: RegimeName
    chronotype: str
    horizon_days: int
    has_asymmetric_classes: bool = False
    buffer_mode: str = "HABIT"
    estimate_habit: Optional[str] = None
    planned_demand_slots: int
    usable_free_slots: int
    tightness_rho: float
    tightness_rho_deadline: Optional[float] = None
    task_count: int
    habit_count: int
    pinned_count: int
    notes: str = ""


class InvariantCheckResult(BaseModel):
    name: str
    passed: bool
    detail: str


class RegimeRunResult(BaseModel):
    """Full end-to-end result of Part 1 -> Run Project -> Part 2 for one (regime, seed)."""

    metadata: GeneratedTestMetadata
    execution_mode: str  # DIRECT_CONTROLLER | HTTP_E2E
    solver_reports: Dict[str, EvaluationReport] = Field(default_factory=dict)
    cross_solver_ranking: List[CrossSolverEntry] = Field(default_factory=list)
    repair_evaluations: Dict[str, EvaluationReport] = Field(default_factory=dict)
    invariant_checks: List[InvariantCheckResult] = Field(default_factory=list)
    all_invariants_passed: bool = True


class ContrastPairResult(BaseModel):
    """Validation result of OutputEvaluator self-test (Gombolay §5.3 Contrast Pairs)."""

    passed: bool
    golden_report: EvaluationReport
    feasible_bad_report: EvaluationReport
    invalid_report: EvaluationReport
    assertions: List[InvariantCheckResult] = Field(default_factory=list)

