"""
Verification tests for P2.1 (Extreme Tight-Load Alpha >= 1.70 Over-Buffering Cliff)
and P2.2 (M7 Completion Telemetry Calibration & EWMA Personal Alpha API).
"""

from __future__ import annotations

import ast
from pathlib import Path

from fastapi.testclient import TestClient

from tools.benchmarks.benchmark_alpha_grid import run_extreme_tight_stress
from smartschedule.core.calibration import compute_ewma_calibration, format_pilot_markdown_report
from smartschedule.core.config import ALPHA_GRID_MAX, ALPHA_GRID_MIN, ALPHA_HEAVY_DEFAULT, ALPHA_LIGHT_DEFAULT, CORE_DIR
from smartschedule.api.app import app


def test_calibration_ast_purity_inv1_inv2() -> None:
    """INV-1 & INV-2: smartschedule/core/calibration.py must be a pure leaf module."""
    src_path = CORE_DIR / "calibration.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    forbidden_prefixes = (
        "smartschedule.api",
        "smartschedule.nlp",
        "web",
        "fastapi",
        "starlette",
        "httpx",
        "smartschedule.core.solvers",
        "smartschedule.core.controller",
    )

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for mod in imported:
        for bad in forbidden_prefixes:
            assert not (mod == bad or mod.startswith(f"{bad}.")), (
                f"INV-1/INV-2 violation: calibration.py imported forbidden module '{mod}'"
            )


def test_ewma_calibration_min_samples_gating_and_clipping() -> None:
    """Verify min_samples LoA-4 gate, outlier clipping, safe clamping [1.00, 1.60], and heavy >= light."""
    few_logs = [
        {"id": 1, "category": "READING", "estimated_duration_min": 60, "actual_duration_min": 75, "completed_at": "2026-11-18T10:00:00Z"},
        {"id": 2, "category": "CODING", "estimated_duration_min": 60, "actual_duration_min": 90, "completed_at": "2026-11-18T12:00:00Z"},
    ]
    gated = compute_ewma_calibration(few_logs, min_samples=5)
    assert gated["ready_to_apply"] is False
    assert gated["sample_count"] == 2
    assert gated["recommended_alpha_light"] == ALPHA_LIGHT_DEFAULT
    assert gated["recommended_alpha_heavy"] == ALPHA_HEAVY_DEFAULT

    # Feed 6 logs (including an extreme 10x outlier that must be clipped to 2.5 and clamped <= 1.60)
    many_logs = [
        {"id": 1, "category": "READING", "estimated_duration_min": 60, "actual_duration_min": 66, "completed_at": "2026-11-18T08:00:00Z"},
        {"id": 2, "category": "WRITING", "estimated_duration_min": 60, "actual_duration_min": 72, "completed_at": "2026-11-18T10:00:00Z"},
        {"id": 3, "category": "READING", "estimated_duration_min": 60, "actual_duration_min": 69, "completed_at": "2026-11-18T12:00:00Z"},
        {"id": 4, "category": "CODING", "estimated_duration_min": 60, "actual_duration_min": 96, "completed_at": "2026-11-18T14:00:00Z"},
        {"id": 5, "category": "EXAM_PREP", "estimated_duration_min": 60, "actual_duration_min": 600, "completed_at": "2026-11-18T16:00:00Z"},
        {"id": 6, "category": "PROJECT", "estimated_duration_min": 60, "actual_duration_min": 102, "completed_at": "2026-11-18T18:00:00Z"},
    ]
    cal = compute_ewma_calibration(many_logs, lambda_ewma=0.25, min_samples=5)
    assert cal["ready_to_apply"] is True
    assert cal["sample_count"] == 6
    assert cal["light_sample_count"] == 3
    assert cal["heavy_sample_count"] == 3
    assert ALPHA_GRID_MIN <= cal["recommended_alpha_light"] <= ALPHA_GRID_MAX
    assert ALPHA_GRID_MIN <= cal["recommended_alpha_heavy"] <= ALPHA_GRID_MAX
    assert cal["recommended_alpha_heavy"] >= cal["recommended_alpha_light"]
    assert "CODING" in cal["by_category"]
    assert "READING" in cal["by_category"]

    md = format_pilot_markdown_report(cal, workspace_id="pilot_user")
    assert "pilot_user" in md
    assert "| `CODING` |" in md


def test_api_tasks_calibration_end_to_end_isolated_db(tmp_path, monkeypatch) -> None:
    """Verify POST /api/tasks/complete feeds GET /api/tasks/calibration on an isolated SQLite DB."""
    db_file = tmp_path / "test_p2_calibration.db"
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(db_file))
    client = TestClient(app)

    ws = "pilot_test_ws"
    # Before logging: not ready
    r0 = client.get(f"/api/tasks/calibration?workspace_id={ws}&min_samples=5")
    assert r0.status_code == 200
    d0 = r0.json()
    assert d0["workspace_id"] == ws
    assert d0["calibration"]["ready_to_apply"] is False
    assert d0["calibration"]["sample_count"] == 0

    # Log 5 realistic sessions (2 light, 3 heavy)
    sessions = [
        {"task_id": "T1", "category": "READING", "estimated_duration_min": 60, "actual_duration_min": 65},
        {"task_id": "T2", "category": "WRITING", "estimated_duration_min": 60, "actual_duration_min": 70},
        {"task_id": "T3", "category": "CODING", "estimated_duration_min": 90, "actual_duration_min": 120},
        {"task_id": "T4", "category": "EXAM_PREP", "estimated_duration_min": 90, "actual_duration_min": 125},
        {"task_id": "T5", "category": "LAB", "estimated_duration_min": 60, "actual_duration_min": 85},
    ]
    for s in sessions:
        res = client.post("/api/tasks/complete", json={**s, "workspace_id": ws})
        assert res.status_code == 200

    r1 = client.get(f"/api/tasks/calibration?workspace_id={ws}&min_samples=5&include_markdown=true")
    assert r1.status_code == 200
    d1 = r1.json()
    cal = d1["calibration"]
    assert cal["ready_to_apply"] is True
    assert cal["sample_count"] == 5
    assert cal["recommended_alpha_heavy"] >= cal["recommended_alpha_light"]
    assert "markdown" in d1 and "M7 Empirical Alpha Calibration Summary" in d1["markdown"]


def test_extreme_tight_alpha_over_buffering_cliff() -> None:
    """Verify P2.1: alpha 1.20/1.35 stays feasible on tight load while alpha >= 1.70 triggers cliff."""
    ext = run_extreme_tight_stress(algorithm="SCORED_GREEDY", alphas=[1.00, 1.20, 1.35, 1.70, 1.90, 2.00])
    assert ext["baseline_alpha_1_00_dl_rate"] == 100.0
    assert ext["recommended_asym_default"]["avg_deadline_rate"] == 100.0
    assert ext["recommended_asym_default"]["over_buffer_infeasible_rate_pct"] == 0.0
    assert ext["over_buffering_cliff_detected"] is True
    assert ext["max_cliff_dl_drop_pct"] > 0.0
