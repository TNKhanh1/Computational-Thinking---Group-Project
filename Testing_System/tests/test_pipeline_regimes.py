"""End-to-End 2-Part Pipeline Tests across all 6 Regimes (Direct Controller & Isolated HTTP E2E)."""

from __future__ import annotations

import pytest

from Testing_System.runner import run_single_regime_case
from Testing_System.schemas import RegimeName


@pytest.mark.parametrize("regime", list(RegimeName))
def test_all_regimes_pass_direct_controller(regime: RegimeName):
    res = run_single_regime_case(regime=regime, seed=42, use_http_e2e=False)
    assert res.all_invariants_passed, (
        f"{regime.value} failed invariants: "
        + "; ".join(f"{c.name}: {c.detail}" for c in res.invariant_checks if not c.passed)
    )


@pytest.mark.parametrize(
    "regime",
    [
        RegimeName.LOOSE_FEASIBLE,
        RegimeName.CIRCADIAN_SJL_AND_RECOVERY,
        RegimeName.OVERLOAD_INFEASIBLE,
        RegimeName.DISRUPTION_AND_OVERRUN_SERIES,
    ],
)
def test_http_e2e_pipeline_isolated_db(tmp_path, regime: RegimeName):
    isolated_db = tmp_path / "e2e_test.db"
    res = run_single_regime_case(
        regime=regime,
        seed=42,
        use_http_e2e=True,
        db_path=str(isolated_db),
    )
    assert res.execution_mode == "HTTP_E2E"
    assert res.all_invariants_passed, (
        f"HTTP E2E {regime.value} failed invariants: "
        + "; ".join(f"{c.name}: {c.detail}" for c in res.invariant_checks if not c.passed)
    )
    if regime == RegimeName.DISRUPTION_AND_OVERRUN_SERIES:
        ov_rep = res.repair_evaluations.get("OVERRUN_LVL_B::HTTP_PROGRESS")
        assert ov_rep is not None
        assert ov_rep.p4_robustness_stability.realized_actual_to_estimate_ratio is not None

