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
      - Albulescu et al. (2022): micro-breaks <= 10 min showed no performance effect after cognitive tasks
        (d=-.09, p=.541); authors suggest > 10 min -> SmartSchedule grid: >= 1 free slot (15 min)
      - Smarr & Schirmer (2018): SJL = circular median phase(class days) - phase(non-class days);
        empirical benchmark "60% of students > 30 min"
      - Svartdal et al. (2018) Table 2 / Howell (2006): most submissions < 10 h before deadline
      - Corne et al. (1993) in Schaerf (1999) §4.2 tr. 25: penalties in DESCENDING order of weight
        (>2 per day > consecutive > around lunch) -> compared lexicographically, no numeric weights

    Fields below are project-tunable parameters (shock levels, verdict policy tolerances, ICEE budget,
    Fox "initial actions" window and Myers Towel UI effort bands) — none of these numbers come from a paper.
    """

    shock_levels_pct: List[float] = Field(default_factory=lambda: [25.0, 50.0])
    max_icee_critiques: int = Field(default=5, ge=1, le=10)
    # Project mapping of Fox et al. (2006) §5.2 "initial actions" for a single-agent calendar:
    # blocks of the unexecuted plan whose start falls within this many slots after now_slot (default 24h).
    near_term_window_slots: int = Field(default=96, ge=4)

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

    # v2.1 Human-Centric Calibration Parameters (Pre-Deployment Verified)
    max_exec_ms_sla: float = Field(default=1000.0)
    moderate_multi_block_streak_min: int = Field(default=120)
    critical_multi_block_streak_min: int = Field(default=180)
    post_class_min_class_slots: int = Field(default=6)
    critical_post_class_violations_min: int = Field(default=2)
    moderate_max_daily_total_min: int = Field(default=540)
    critical_max_daily_total_min: int = Field(default=600)
    moderate_context_switches_max: int = Field(default=4)
    habit_check_max_rho: float = Field(default=0.85)
    critical_habit_rate_min_pct: float = Field(default=50.0)
    moderate_habit_rate_min_pct: float = Field(default=80.0)
    moderate_preferred_window_min_pct: float = Field(default=50.0)
    moderate_sjl_advance_max_min: float = Field(default=60.0)
    moderate_sjl_delay_max_min: float = Field(default=180.0)
    total_daily_std_min_floor: float = Field(default=180.0)
    total_daily_std_class_margin: float = Field(default=45.0)


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

    # P2.3 Circular SJL (Smarr & Schirmer 2018) computed on study-block activity (LMS-login analogue)
    sjl_minutes: Optional[float] = None          # |SJL|
    sjl_signed_minutes: Optional[float] = None   # phase(class days) - phase(non-class days); < 0 = advance on class days
    sjl_direction: Optional[str] = None  # PHASE_ADVANCE | PHASE_DELAY | ALIGNED | N/A (direction on class days)
    sjl_exceeds_30m: Optional[bool] = None
    class_days_count: int = 0
    non_class_days_count: int = 0
    # Diagnostic only (Smarr & Schirmer discuss schedule instability -> internal desynchrony as a hypothesis)
    cross_day_phase_std_min: Optional[float] = None

    # v2.1 Human-Centric P2 Extensions
    achievable_heavy_peak_match_pct: Optional[float] = None
    off_peak_heavy_mismatch_count: int = 0
    off_peak_heavy_mismatch_blocks: List[str] = Field(default_factory=list)
    off_peak_heavy_mismatch_task_ids: List[str] = Field(default_factory=list)
    max_multi_block_streak_l2_min: int = 0
    post_class_buffer_violations: int = 0
    post_class_violation_block_ids: List[str] = Field(default_factory=list)
    sjl_neutral_unpaired: bool = False


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
    # Corne et al. (1993): [>2 heavy/day days, consecutive heavy pairs, around-meal offenses] compared lexicographically
    corne_lexicographic_vector: List[int] = Field(default_factory=lambda: [0, 0, 0])
    context_switches: int = 0
    batched_pairs: int = 0

    # v2.1 Human-Centric P3 Extensions
    meal_boundary_offenses_l2: int = 0
    total_daily_load_minutes: List[int] = Field(default_factory=list)
    max_daily_total_min: int = 0
    total_daily_load_std_min: float = 0.0
    base_class_daily_std_min: float = 0.0
    effective_daily_std_limit_min: float = 180.0
    focus_context_switches: int = 0


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
    mean_abs_time_shift_min: float = 0.0  # Cowling & Johansson: mean |Δstart| & |Δcompletion|
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
    p3_corne_vector: List[int]
    p3_daily_load_std_min: float
    exec_ms: float

    # v2.1 Human-Centric Cross-Solver Fields
    v2_achievable_peak_pct: Optional[float] = None
    v2_off_peak_mismatch: int = 0
    v2_max_streak_l2_min: int = 0
    v2_post_class_violations: int = 0
    v2_max_daily_total_min: int = 0
    v2_total_daily_std_min: float = 0.0
    v2_meal_l2_offenses: int = 0
    v2_context_switches: int = 0
    v2_habit_rate_pct: Optional[float] = None
    v2_preferred_window_pct: Optional[float] = None
    v2_sjl_effective_min: Optional[float] = None
    v2_sla_exceeded: bool = False


class GeneratedTestMetadata(BaseModel):
    """Reproducible metadata emitted by InputGenerator / FuzzGenerator (Part 1)."""

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
    is_fuzz: bool = False
    fuzz_tier: Optional[str] = None
    persona_archetype: Optional[str] = None
    witness_verified: bool = False


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

