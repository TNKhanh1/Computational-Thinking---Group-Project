"""
UI Test: Backend API Endpoints & Workbench Delivery
Author: Nguyen Nguyen Gia Bao (Builder 3 - System Architecture & Testing)
Validates:
  - Static Web delivery (/ and /app.js)
  - Presets & Scenario endpoints
  - Drag-and-drop manual move validator (/api/validate-move)
  - Export endpoints (.ics, .csv, .json)
"""

from fastapi.testclient import TestClient
from web.api import app

client = TestClient(app)


def test_ui_static_workbench_delivery():
    """Verify that root UI workbench loads with status 200."""
    res_index = client.get("/")
    assert res_index.status_code == 200
    assert "SmartSchedule" in res_index.text

    res_js = client.get("/app.js")
    assert res_js.status_code == 200


def test_ui_presets_delivery():
    """Verify built-in presets (Minh, Lan, Empty) load properly."""
    res = client.get("/api/presets")
    assert res.status_code == 200
    presets = res.json().get("presets", {})
    assert "minh" in presets
    assert "lan" in presets
    assert "empty" in presets


def test_ui_scenario_catalog():
    """Verify all 10 standard evaluation scenarios are listed and fetchable."""
    res = client.get("/api/scenarios")
    assert res.status_code == 200
    scenarios = res.json().get("scenarios", [])
    assert len(scenarios) == 10

    # Test single scenario fetch
    res_t01 = client.get("/api/scenarios/t01")
    assert res_t01.status_code == 200
    assert res_t01.json()["scenario_id"] == "T01"


def test_ui_validate_move_api():
    """Verify that the frontend live drag-and-drop validator endpoint functions properly."""
    res_presets = client.get("/api/presets")
    minh = res_presets.json()["presets"]["minh"]

    # Plan schedule first
    res_plan = client.post(
        "/api/plan",
        json={"commitments": minh["commitments"], "tasks": minh["tasks"], "algorithm": "EDF"},
    )
    assert res_plan.status_code == 200
    first_block = res_plan.json()["blocks"][0]

    # Validate move to illegal sleep slot (Monday 01:00)
    res_val = client.post(
        "/api/validate-move",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "current_blocks": res_plan.json()["blocks"],
            "block_id": first_block["block_id"],
            "new_day": "Monday",
            "new_time": "01:00",
        },
    )
    assert res_val.status_code == 200
    val_data = res_val.json()
    assert val_data["ok"] is False
    assert len(val_data["violations"]) >= 1


def test_ui_export_endpoints():
    """Verify export formats (ICS, CSV, JSON)."""
    res_presets = client.get("/api/presets")
    minh = res_presets.json()["presets"]["minh"]

    res_plan = client.post(
        "/api/plan",
        json={"commitments": minh["commitments"], "tasks": minh["tasks"], "algorithm": "EDF"},
    )
    plan_data = res_plan.json()

    # Export ICS
    res_ics = client.post(
        "/api/export/ics",
        json={"commitments": minh["commitments"], "tasks": minh["tasks"], "schedule": plan_data},
    )
    assert res_ics.status_code == 200
    assert "BEGIN:VCALENDAR" in res_ics.text

    # Export CSV
    res_csv = client.post(
        "/api/export/csv",
        json={"commitments": minh["commitments"], "tasks": minh["tasks"], "schedule": plan_data},
    )
    assert res_csv.status_code == 200
    assert "block_id,task_id" in res_csv.text

