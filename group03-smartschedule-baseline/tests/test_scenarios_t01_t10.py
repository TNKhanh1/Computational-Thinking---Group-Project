"""
End-to-End Integration Tests for all 10 Standard Scenarios (T01–T10) and FastAPI Endpoints.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.controller import ScheduleController
from src.models import CommitmentsProfile, Task
from web.api import app

SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "data" / "test_scenarios"
client = TestClient(app)


def _load_scenario(sc_prefix: str):
    matches = list(SCENARIOS_DIR.glob(f"{sc_prefix.lower()}*.json"))
    assert len(matches) == 1, f"Expected 1 file for {sc_prefix}, got {matches}"
    raw = json.loads(matches[0].read_text(encoding="utf-8"))
    comm_dict = dict(raw["commitments"])
    if "now" in raw and raw["now"] and not comm_dict.get("now"):
        comm_dict["now"] = raw["now"]
    profile = CommitmentsProfile.model_validate(comm_dict)
    tasks = [Task.model_validate(t) for t in raw["tasks"]]
    return raw, profile, tasks


def test_t01_normal_feasible():
    _, profile, tasks = _load_scenario("t01")
    out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    assert out.summary.deadline_satisfaction_rate == 100.0
    assert len(out.unplaced_tasks) == 0


def test_t02_tight_cluster():
    _, profile, tasks = _load_scenario("t02")
    out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    assert out.summary.deadline_satisfaction_rate == 100.0


def test_t03_fragmented_slots():
    """
    Verifies T03: T03-SPLITTABLE (180m, splittable) is split into 90m+90m and placed,
    while T03-UNSPLITTABLE (180m, atomic) cannot fit in fragmented 90m gaps and is flagged unplaced.
    """
    _, profile, tasks = _load_scenario("t03")
    out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    placed_ids = {b.task_id for b in out.blocks}
    unplaced_ids = {u["task_id"] for u in out.unplaced_tasks}
    assert "T03-SPLITTABLE" in placed_ids
    assert "T03-UNSPLITTABLE" in unplaced_ids


def test_t06_overload_capacity_exact_shortage():
    """
    Verifies T06 mathematical overload proof from Proposal_Report.pdf §6.7 & baseline_plan.md §6.2.B:
      - Free capacity before Tuesday 23:59 = 1,365 minutes
      - Total planned task duration before Tuesday 23:59 = 1,470 minutes
      - Exact shortage = 105 minutes -> CAPACITY_SHORTAGE
    """
    _, profile, tasks = _load_scenario("t06")
    out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    assert len(out.unplaced_tasks) >= 1
    assert out.overload is not None
    assert out.overload.error_type == "CAPACITY_SHORTAGE"
    assert out.overload.shortage_minutes == 105


def test_t07_incomplete_metadata_normalization():
    """
    Verifies T07: Tasks with missing deadline_day / grade_weight / min_chunk_min are normalized
    cleanly without crashing and scheduled with 0 hard violations.
    """
    _, profile, tasks = _load_scenario("t07")
    out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    assert out.summary.deadline_satisfaction_rate == 100.0
    assert len(out.unplaced_tasks) == 0


def test_t08_t09_t10_edge_cases():
    for prefix in ["t08", "t09", "t10"]:
        _, profile, tasks = _load_scenario(prefix)
        out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
        assert out.summary.hard_constraint_violations == 0
        assert out.summary.deadline_satisfaction_rate == 100.0
        assert len(out.unplaced_tasks) == 0


def test_fastapi_endpoints_e2e():
    # 1. GET /api/presets
    res_p = client.get("/api/presets")
    assert res_p.status_code == 200
    presets = res_p.json()["presets"]
    assert "minh" in presets and "lan" in presets

    # 2. GET /api/scenarios
    res_s = client.get("/api/scenarios")
    assert res_s.status_code == 200
    assert len(res_s.json()["scenarios"]) == 10

    # 3. POST /api/plan
    minh = presets["minh"]
    res_plan = client.post(
        "/api/plan",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "algorithm": "EDF",
        },
    )
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert plan_data["summary"]["hard_constraint_violations"] == 0
    assert plan_data["summary"]["deadline_satisfaction_rate"] == 100.0

    # 4. POST /api/compare
    res_cmp = client.post(
        "/api/compare",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "algo_left": "EDF",
            "algo_right": "LST",
        },
    )
    assert res_cmp.status_code == 200
    assert "left" in res_cmp.json() and "right" in res_cmp.json()

    # 5. POST /api/export/ics
    res_ics = client.post(
        "/api/export/ics",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "schedule": plan_data,
        },
    )
    assert res_ics.status_code == 200
    assert "BEGIN:VCALENDAR" in res_ics.text
