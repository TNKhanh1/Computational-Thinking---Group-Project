"""
Week navigation regression: moving the planning week past all absolute (`due`) deadlines must be
reported as "already past due", not as a scheduling failure / overload.

The calendar view splits `unplaced_tasks` by `reason_code` (PAST_DUE / DEADLINE_IN_PAST); this test
locks that backend contract and the UI wiring.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from smartschedule.api.app import app

_DAY_TO_DATE = {"Monday": 2, "Tuesday": 3, "Wednesday": 4, "Thursday": 5, "Friday": 6, "Saturday": 7, "Sunday": 8}


def _minh_with_absolute_dues(client: TestClient):
    minh = client.get("/api/presets").json()["presets"]["minh"]
    tasks = []
    for t in minh["tasks"]:
        t = dict(t)
        if t.get("deadline_day") in _DAY_TO_DATE:
            t["due"] = f"2026-11-{_DAY_TO_DATE[t['deadline_day']]:02d}T{t.get('deadline_time') or '23:59'}:00+07:00"
        tasks.append(t)
    return minh["commitments"], tasks


def test_tasks_due_before_planning_week_are_flagged_past_due() -> None:
    client = TestClient(app)
    commitments, tasks = _minh_with_absolute_dues(client)
    deadline_ids = {t["task_id"] for t in tasks if t.get("due")}

    same_week = client.post("/api/plan", json={"commitments": commitments, "tasks": tasks, "algorithm": "SCORED_GREEDY"}).json()
    assert not any(u.get("reason_code") == "PAST_DUE" for u in same_week["unplaced_tasks"])

    later = dict(commitments, planning_week_start="2026-11-30T00:00:00+07:00", now="2026-11-30T08:00:00+07:00")
    shifted = client.post("/api/plan", json={"commitments": later, "tasks": tasks, "algorithm": "SCORED_GREEDY"}).json()
    past_due = {u["task_id"] for u in shifted["unplaced_tasks"] if u.get("reason_code") == "PAST_DUE"}
    assert past_due == deadline_ids
    # The independent checker agrees there is nothing due in that week (no overload).
    assert shifted["health_v21"]["gates"]["rho_deadline"] == 0.0


def test_week_buttons_are_view_only_and_clear_all_is_wired() -> None:
    """‹ › must not re-plan (no shiftWeek) — re-planning another week is an explicit banner action."""
    client = TestClient(app)
    js = client.get("/app.js").text
    assert 'getElementById("btnWeekPrev").addEventListener("click", () => shiftWeek' not in js
    assert 'getElementById("btnWeekNext").addEventListener("click", () => shiftWeek' not in js
    assert "setViewWeek(" in js and "viewWeekOffset" in js
    cal = client.get("/js/render-calendar.js").text
    assert "btnPlanViewedWeek" in cal and "btnBackToPlanWeek" in cal and "out-of-plan" in cal
    html = client.get("/").text
    assert 'id="btnClearAllSchedule"' in html and 'id="clearAllModal"' in html and 'id="chkClearIncludeFixed"' in html
    assert "async function clearAllSchedule(" in js


def test_calendar_separates_past_due_from_genuine_unplaced() -> None:
    client = TestClient(app)
    js = client.get("/js/render-calendar.js").text
    assert "PAST_DUE" in js and "past-due-strip" in js and "btnJumpToDueWeek" in js
    assert "genuineUnplaced" in js
    assert "onShiftWeek" in client.get("/app.js").text
