"""
Layer 4 Web API Helper: Real-Time `Testing_System v2.1` 4-Pillar Productivity & ICEE Evaluator.

Preserves INV-1..INV-6:
  - Only imported by Layer 4 (`web/api.py`).
  - Never imported by `src/solvers/*`, `src/models.py`, or `Testing_System/*`.
  - Gracefully returns `{"available": False}` if `Testing_System` is not co-located.
"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

_BASELINE_ROOT = str(Path(__file__).resolve().parents[1])
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
for _p in (_REPO_ROOT, _BASELINE_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from Testing_System.evaluator.schedule_evaluator import ScheduleEvaluator as _ScheduleEvaluator

    _EVAL_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ScheduleEvaluator = None
    _EVAL_AVAILABLE = False

from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task  # noqa: E402

VERDICT_META_VI: Dict[str, Tuple[str, str]] = {
    "HIGH_PRODUCTIVITY": ("Chuẩn Năng Suất Cao", "emerald"),
    "FEASIBLE_BUT_LOW_PRODUCTIVITY": ("Khả Thi — Cần Tối Ưu Nhịp Học", "amber"),
    "OVERLOAD_TRIAGE": ("Tuần Quá Tải — Cần Phân Loại Ưu Tiên", "indigo"),
    "SUBOPTIMAL_ALGORITHM_FAILURE": ("Chưa Tối Ưu Hạn Chót", "rose"),
    "INVALID": ("Vi Phạm Ràng Buộc Cứng", "rose"),
}


def evaluate_schedule_v21(
    profile: CommitmentsProfile,
    raw_tasks: List[Task],
    schedule: ScheduleOutput,
    pinned_blocks: Optional[List[ScheduleBlock]] = None,
    baseline_schedule: Optional[ScheduleOutput] = None,
    disruption_span: Optional[Tuple[int, int]] = None,
    repair_now_slot: Optional[int] = None,
    is_overrun_context: bool = False,
) -> Dict[str, Any]:
    """Run stateless Checking Engine v2.1 (`G1/G2` + `P1–P4` + Top-5 `ICEE`) for Web UI telemetry."""
    if not _EVAL_AVAILABLE or _ScheduleEvaluator is None:
        return {"available": False, "reason": "Testing_System evaluator not co-located."}

    try:
        report = _ScheduleEvaluator.evaluate(
            profile=profile.model_copy(deep=True),
            tasks=[t.model_copy(deep=True) for t in raw_tasks],
            schedule=schedule.model_copy(deep=True),
            input_pinned_blocks=[b.model_copy(deep=True) for b in pinned_blocks] if pinned_blocks else None,
            baseline_schedule=baseline_schedule.model_copy(deep=True) if baseline_schedule else None,
            disruption_span=disruption_span,
            repair_now_slot=repair_now_slot,
            is_overrun_context=is_overrun_context,
        )
    except Exception as exc:  # pragma: no cover
        return {"available": False, "reason": str(exc)}

    v_key = report.verdict.value
    label_vi, tone = VERDICT_META_VI.get(v_key, (v_key, "slate"))

    p1 = report.p1_value_timeliness
    p2 = report.p2_cognitive_biology
    p3 = report.p3_sustainable_pacing
    p4 = report.p4_robustness_stability
    gates = report.gates

    shock_25 = 100.0
    shock_50 = 100.0
    for sr in p4.shock_results:
        if abs(sr.shock_pct - 25.0) < 1e-6:
            shock_25 = float(sr.survived_priority_pct)
        elif abs(sr.shock_pct - 50.0) < 1e-6:
            shock_50 = float(sr.survived_priority_pct)

    return {
        "available": True,
        "verdict": v_key,
        "verdict_label_vi": label_vi,
        "verdict_tone": tone,
        "critical_count": len(report.critical_breaches),
        "warning_count": len(report.moderate_warnings),
        "critical_breaches": list(report.critical_breaches),
        "moderate_warnings": list(report.moderate_warnings),
        "verdict_reasons_vi": list(report.verdict_reasons_vi),
        "exec_ms": report.diagnostics.execution_time_ms,
        "gates": {
            "g1_total_violations": gates.g1_total_violations,
            "g1_is_feasible": gates.g1_is_feasible,
            "rho_total": gates.rho_total,
            "rho_deadline": gates.rho_deadline,
            "is_structurally_overloaded": gates.is_structurally_overloaded,
        },
        "pillars": {
            "p1": {
                "deadline_value_rate_pct": p1.deadline_value_rate_pct,
                "unjustified_last_10h_crowding_pct": p1.unjustified_last_10h_crowding_pct,
                "habit_value_rate_pct": p1.habit_value_rate_pct,
                "unplaced_deadline_count": p1.unplaced_deadline_count,
            },
            "p2": {
                "achievable_heavy_peak_match_pct": p2.achievable_heavy_peak_match_pct,
                "heavy_peak_match_pct": p2.heavy_peak_match_pct,
                "off_peak_heavy_mismatch_count": p2.off_peak_heavy_mismatch_count,
                "heavy_recovery_rate_pct": p2.heavy_recovery_rate_pct,
                "max_multi_block_streak_l2_min": p2.max_multi_block_streak_l2_min,
                "post_class_buffer_violations": p2.post_class_buffer_violations,
                "sjl_minutes": p2.sjl_minutes,
                "sjl_direction": p2.sjl_direction,
                "sjl_neutral_unpaired": p2.sjl_neutral_unpaired,
            },
            "p3": {
                "max_daily_total_min": p3.max_daily_total_min,
                "total_daily_load_std_min": p3.total_daily_load_std_min,
                "effective_daily_std_limit_min": p3.effective_daily_std_limit_min,
                "heavy_day_overload_days": p3.heavy_day_overload_days,
                "adjacent_heavy_pairs": p3.adjacent_heavy_pairs,
                "meal_boundary_offenses_l2": p3.meal_boundary_offenses_l2,
                "focus_context_switches": p3.focus_context_switches,
                "corne_lexicographic_vector": list(p3.corne_lexicographic_vector),
            },
            "p4": {
                "true_buffer_task_pct": p4.true_buffer_task_pct,
                "shock_25_pct": shock_25,
                "shock_50_pct": shock_50,
                "zero_slack_risk_blocks": p4.zero_slack_risk_blocks,
                "post_repair_stability": (
                    p4.post_repair_stability.model_dump() if p4.post_repair_stability else None
                ),
            },
        },
        "top_critiques": [c.model_dump() for c in report.d1_icee_critiques],
    }


__all__ = ["VERDICT_META_VI", "evaluate_schedule_v21"]
