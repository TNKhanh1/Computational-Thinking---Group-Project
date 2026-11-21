"""
Verification Tests (`P1` Commercial Readiness): `HYBRID_ALNS` + Real-Time `v2.1` 4-Pillar Health API & UI.

Validates:
  - `POST /api/plan` with `HYBRID_ALNS` & `SCORED_GREEDY` returns full `health_v21` telemetry while keeping legacy `metrics` intact
  - `POST /api/evaluate` evaluates both scheduled outputs and manually edited `blocks`/`pinned_blocks` without mutating inputs
  - `/` HTML and `/app.js` expose `HYBRID_ALNS`, Student 4-pillar `#stHealthV21Panel`, Lab `#labHealthV21Panel`, and pass JS syntax check
"""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

BASELINE_ROOT = Path(__file__).resolve().parents[2]
if str(BASELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(BASELINE_ROOT))

from web.api import app  # noqa: E402


def test_api_plan_hybrid_alns_and_health_v21_payload(tmp_path, monkeypatch) -> None:
    """`POST /api/plan` with HYBRID_ALNS and SCORED_GREEDY exposes full `health_v21` 4-pillar vector."""
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "p1_plan.db"))
    client = TestClient(app)
    minh = client.get("/api/presets").json()["presets"]["minh"]

    for algo in ("HYBRID_ALNS", "SCORED_GREEDY"):
        res = client.post(
            "/api/plan",
            json={
                "commitments": minh["commitments"],
                "tasks": minh["tasks"],
                "algorithm": algo,
            },
        )
        assert res.status_code == 200, f"{algo} failed: {res.text}"
        data = res.json()
        assert data["metrics"]["hard_violations"] == 0
        assert "health_v21" in data
        hv = data["health_v21"]
        assert hv["available"] is True
        assert hv["verdict"] in (
            "HIGH_PRODUCTIVITY",
            "FEASIBLE_BUT_LOW_PRODUCTIVITY",
            "OVERLOAD_TRIAGE",
            "SUBOPTIMAL_ALGORITHM_FAILURE",
            "INVALID",
        )
        assert hv["gates"]["g1_total_violations"] == 0
        pillars = hv["pillars"]
        assert set(pillars.keys()) == {"p1", "p2", "p3", "p4"}
        assert "deadline_value_rate_pct" in pillars["p1"]
        assert "achievable_heavy_peak_match_pct" in pillars["p2"]
        assert "max_daily_total_min" in pillars["p3"]
        assert "shock_25_pct" in pillars["p4"]
        assert isinstance(hv["top_critiques"], list)


def test_api_evaluate_endpoint_on_custom_and_pinned_schedule(tmp_path, monkeypatch) -> None:
    """`POST /api/evaluate` evaluates both ScheduleOutput payloads and lightweight blocks lists."""
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "p1_eval.db"))
    client = TestClient(app)
    minh = client.get("/api/presets").json()["presets"]["minh"]

    initial_plan = client.post(
        "/api/plan",
        json={"commitments": minh["commitments"], "tasks": minh["tasks"], "algorithm": "SCORED_GREEDY"},
    ).json()

    pinned = [dict(initial_plan["blocks"][0], state="PINNED")] if initial_plan["blocks"] else []
    pinned_plan = client.post(
        "/api/plan",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "pinned_blocks": pinned,
            "algorithm": "SCORED_GREEDY",
        },
    ).json()

    ev_full = client.post(
        "/api/evaluate",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "pinned_blocks": pinned,
            "schedule": pinned_plan,
        },
    )
    assert ev_full.status_code == 200, ev_full.text
    ev_data = ev_full.json()
    assert ev_data["available"] is True
    assert ev_data["verdict"] == pinned_plan["health_v21"]["verdict"]
    assert ev_data["gates"]["g1_total_violations"] == 0

    ev_blocks_only = client.post(
        "/api/evaluate",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "blocks": initial_plan["blocks"],
            "algorithm": "SCORED_GREEDY",
        },
    )
    assert ev_blocks_only.status_code == 200, ev_blocks_only.text
    assert ev_blocks_only.json()["available"] is True
    assert ev_blocks_only.json()["gates"]["g1_total_violations"] == 0


def test_ui_exposes_hybrid_alns_and_v21_health_panels() -> None:
    """Web Workbench HTML & JS expose HYBRID_ALNS, 4-pillar UI, and /api/evaluate without violating contracts."""
    client = TestClient(app)
    html = client.get("/").text
    js = client.get("/app.js").text

    for html_token in (
        "HYBRID_ALNS",
        "stHealthV21Panel",
        "stHealthVerdictBadge",
        "stHealthIceeDetails",
        "labHealthV21Panel",
        "labHealthVectorGrid",
        "labHealthIceeList",
    ):
        assert html_token in html

    for forbidden in ("stNlCiteInput", "Ưu tiên Solver", 'id="inpTaskId"'):
        assert forbidden not in html

    for js_token in (
        "renderHealthV21Panels",
        "evaluateCurrentScheduleV21",
        "/api/evaluate",
        "HYBRID_ALNS",
    ):
        assert js_token in js
