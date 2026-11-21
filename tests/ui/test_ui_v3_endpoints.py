"""
UI v3 Backend Endpoint Verification Tests.
Validates:
  - GET  /api/solvers
  - POST /api/evaluate
  - POST /api/benchmark-all (matching Testing_System ScheduleEvaluator & rank_cross_solver_reports)
  - POST /api/solver-weights (matching src/config.py & solver priority formulas)
  - GET  /api/test-suites/catalog & POST /api/test-suites/load (Presets, T01-T10, Regimes R1-R6)
  - POST /api/import/ics
  - GET  /api/tasks/calibration
"""

from fastapi.testclient import TestClient

from smartschedule.core import config as app_config
from smartschedule.api.app import app

client = TestClient(app)


def test_solvers_catalog():
    res = client.get("/api/solvers")
    assert res.status_code == 200
    keys = [s["key"] for s in res.json()["solvers"]]
    for expected in ("EDF", "WSPT", "LST", "SCORED_GREEDY", "BACKTRACK"):
        assert expected in keys


def test_benchmark_all_and_cache_payload():
    minh = client.get("/api/presets").json()["presets"]["minh"]
    res = client.post(
        "/api/benchmark-all",
        json={"commitments": minh["commitments"], "tasks": minh["tasks"]},
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert len(data["ranking"]) >= 5
    ranks = [r["lexicographic_rank"] for r in data["ranking"]]
    assert ranks == list(range(1, len(ranks) + 1))

    # Every solver in ranking has a cached schedule for 0ms UI switching
    for row in data["ranking"]:
        skey = row["solver_key"]
        assert skey in data["schedules_by_solver"]
        sched = data["schedules_by_solver"][skey]
        assert "blocks" in sched
        assert "evaluation" in sched
        assert sched["evaluation"]["verdict"] == row["verdict"]

    # Glossary & lexicographic appendix present for Dev view
    assert len(data["column_glossary"]) >= 10
    assert len(data["lexicographic_order"]) >= 10
    assert len(data["verdict_definitions"]) == 5


def test_solver_weights_matches_config_constants():
    minh = client.get("/api/presets").json()["presets"]["minh"]
    res = client.post(
        "/api/solver-weights",
        json={"commitments": minh["commitments"], "tasks": minh["tasks"]},
    )
    assert res.status_code == 200, res.text
    data = res.json()

    assert len(data["per_task_weights"]) == len(minh["tasks"])
    first = data["per_task_weights"][0]
    for k in (
        "duration_min",
        "buffer_multiplier",
        "planned_duration_min",
        "planned_slots",
        "priority",
        "urgency_score",
        "smith_ratio",
        "edf_key",
        "descendant_count",
    ):
        assert k in first

    cfg = data["config_constants"]
    assert cfg["ALPHA_LIGHT_DEFAULT"] == app_config.ALPHA_LIGHT_DEFAULT
    assert cfg["ALPHA_HEAVY_DEFAULT"] == app_config.ALPHA_HEAVY_DEFAULT
    assert cfg["GAMMA_URGENCY_HOURS"] == app_config.GAMMA_URGENCY_HOURS
    assert cfg["MANDATORY_REST_SLOTS"] == app_config.MANDATORY_REST_SLOTS
    assert cfg["BACKTRACK_MAX_NODES"] == app_config.BACKTRACK_MAX_NODES
    assert len(data["weights_glossary"]) >= 8


def test_unified_test_suites_catalog_and_load():
    cat = client.get("/api/test-suites/catalog")
    assert cat.status_code == 200
    cdata = cat.json()
    assert len(cdata["presets"]) == 3
    assert len(cdata["scenarios"]) == 10
    assert len(cdata["regimes"]) == 6

    # Load preset
    r_pre = client.post("/api/test-suites/load", json={"source": "preset", "id": "lan"})
    assert r_pre.status_code == 200
    assert len(r_pre.json()["tasks"]) > 0

    # Load scenario
    r_sc = client.post("/api/test-suites/load", json={"source": "scenario", "id": "T06"})
    assert r_sc.status_code == 200
    assert r_sc.json()["id"] == "T06"

    # Load regime from Testing_System InputGenerator
    r_reg = client.post("/api/test-suites/load", json={"source": "regime", "id": "R3", "seed": 42})
    assert r_reg.status_code == 200
    reg_data = r_reg.json()
    assert reg_data["source"] == "regime"
    assert len(reg_data["tasks"]) > 0
    assert reg_data["commitments"]["focus_preference"] in ("EVENING", "MORNING", "AFTERNOON", "BALANCED")


def test_import_ics_and_calibration():
    ics_sample = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Lý thuyết CTDL\r\n"
        "DTSTART:20261102T080000\r\n"
        "DTEND:20261102T103000\r\n"
        "RRULE:FREQ=WEEKLY;BYDAY=MO,WE\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Nộp bài tập Assignment 3\r\n"
        "DTSTART:20261105T235900\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    res = client.post("/api/import/ics", json={"content": ics_sample})
    assert res.status_code == 200
    parsed = res.json()
    assert len(parsed["fixed_events"]) == 1
    assert parsed["fixed_events"][0]["day_of_week"] == ["Monday", "Wednesday"]
    assert len(parsed["tasks"]) == 1
    assert parsed["tasks"][0]["category"] == "ASSIGNMENT"

    cal = client.get("/api/tasks/calibration")
    assert cal.status_code == 200
    assert "sample_count" in cal.json()


def test_overrun_set_target_duration_and_ui_controls():
    from pathlib import Path

    minh = client.get("/api/presets").json()["presets"]["minh"]
    target_task = minh["tasks"][0]

    # Expand task directly via target_duration_min (with 15m round-up: 140 -> 150)
    res_up = client.post(
        "/api/overrun",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "algorithm": "SCORED_GREEDY",
            "task_id": target_task["task_id"],
            "target_duration_min": 140,
        },
    )
    assert res_up.status_code == 200, res_up.text
    up_data = res_up.json()
    assert up_data["new_estimate_min"] == 150
    assert up_data["after_schedule"]["metrics"]["hard_violations"] == 0

    # Shrink task directly via target_duration_min (to 45p)
    res_down = client.post(
        "/api/overrun",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "algorithm": "SCORED_GREEDY",
            "task_id": target_task["task_id"],
            "target_duration_min": 45,
        },
    )
    assert res_down.status_code == 200, res_down.text
    down_data = res_down.json()
    assert down_data["new_estimate_min"] == 45
    assert down_data["after_schedule"]["metrics"]["hard_violations"] == 0

    # Verify UI modal and handler expose custom task duration controls,
    # user-friendly reason humanization, completion cleanup, and no modal Focus Timer clutter
    modals_js = Path("smartschedule/ui/js/modals.js").read_text(encoding="utf-8")
    app_js = Path("smartschedule/ui/app.js").read_text(encoding="utf-8")
    input_js = Path("smartschedule/ui/js/input-drawer.js").read_text(encoding="utf-8")
    list_js = Path("smartschedule/ui/js/render-list.js").read_text(encoding="utf-8")
    assert "inpSetTaskDuration" in modals_js
    assert "btnSetTaskDuration" in modals_js
    assert "_humanizeBlockReason" in modals_js
    assert "secFocusTimer" not in modals_js
    assert "data-list-timer" not in list_js
    assert "handleSetTaskDuration" in app_js
    assert "_completeBlockAndFreeSchedule" in app_js
    assert "USER_LOAD_LABELS" in input_js
