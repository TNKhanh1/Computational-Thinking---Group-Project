"""Tests for Part 1 InputGenerator: determinism, acyclic DAGs, post-buffer feasibility, & Regime targets."""

from __future__ import annotations

import pytest

from Testing_System.generator import InputGenerator
from Testing_System.schemas import RegimeName
from Testing_System.sut_adapter import BaseScheduler, build_base_grid, preprocess_tasks, resolve_horizon_slots_safe


@pytest.mark.parametrize("regime", list(RegimeName))
def test_input_generator_deterministic_and_acyclic(regime: RegimeName):
    b1 = InputGenerator.generate(regime=regime, seed=42)
    b2 = InputGenerator.generate(regime=regime, seed=42)

    assert b1.profile.model_dump() == b2.profile.model_dump()
    assert [t.model_dump() for t in b1.tasks] == [t.model_dump() for t in b2.tasks]
    assert b1.metadata.model_dump() == b2.metadata.model_dump()

    prepared = preprocess_tasks(b1.profile, b1.tasks)
    _, bad_deps = BaseScheduler.partition_dependency_order(prepared, prepared)
    assert not bad_deps, f"Unexpected cyclic/missing deps in {regime}: {bad_deps}"


@pytest.mark.parametrize(
    "regime,min_rho,max_rho",
    [
        (RegimeName.LOOSE_FEASIBLE, 0.25, 0.60),
        (RegimeName.TIGHT_DEADLINE_CLUSTER, 0.70, 0.96),
        (RegimeName.CIRCADIAN_SJL_AND_RECOVERY, 0.05, 0.95),
        (RegimeName.PROCRASTINATION_ONSET_AND_DAG, 0.05, 0.80),
    ],
)
def test_feasible_regimes_verified_after_buffer(regime: RegimeName, min_rho: float, max_rho: float):
    bundle = InputGenerator.generate(regime=regime, seed=42)
    assert min_rho <= bundle.metadata.tightness_rho <= max_rho, f"{regime} rho={bundle.metadata.tightness_rho}"

    prepared = preprocess_tasks(bundle.profile, bundle.tasks)
    h_slots = resolve_horizon_slots_safe(bundle.profile, prepared, bundle.pinned_blocks)
    grid = build_base_grid(bundle.profile, h_slots)
    cap_reports = BaseScheduler.check_deadline_capacity(
        grid,
        prepared,
        now_slot=BaseScheduler.resolve_now_slot(bundle.profile),
        week_start_iso=bundle.profile.planning_week_start,
    )
    assert not cap_reports, f"Capacity shortage in feasible {regime}: {cap_reports}"


def test_regime5_is_genuinely_overloaded():
    bundle = InputGenerator.generate(regime=RegimeName.OVERLOAD_INFEASIBLE, seed=42)
    rho_d = bundle.metadata.tightness_rho_deadline or bundle.metadata.tightness_rho
    assert rho_d > 1.15, f"Expected deadline overload > 1.15, got {rho_d}"
    prepared = preprocess_tasks(bundle.profile, bundle.tasks)
    h_slots = resolve_horizon_slots_safe(bundle.profile, prepared)
    grid = build_base_grid(bundle.profile, h_slots)
    shortages = BaseScheduler.check_deadline_capacity(grid, prepared, now_slot=0)
    assert len(shortages) >= 1


def test_two_week_horizon_generation_supported():
    # seed % 4 == 1 triggers 14-day horizon in Regime 1
    bundle = InputGenerator.generate(regime=RegimeName.LOOSE_FEASIBLE, seed=41)
    assert bundle.metadata.horizon_days == 14
    prepared = preprocess_tasks(bundle.profile, bundle.tasks)
    assert resolve_horizon_slots_safe(bundle.profile, prepared) == 1344

