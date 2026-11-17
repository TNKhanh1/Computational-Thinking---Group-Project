"""Verification tests for Milestone 2 (Production Readiness A.0–A.3 + B Cleanup)."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.controller import ScheduleController
from src.models import CommitmentsProfile, PersonalHabit, SleepSchedule, Task
from src.nl_parser import OfflineNLParser
from web.api import app


def _clean_profile(**overrides) -> CommitmentsProfile:
    base = {
        "student_id": "M2_TEST",
        "planning_week_start": "2026-11-02T00:00:00+07:00",
        "sleep_schedule": SleepSchedule(daily_start_time="23:30", daily_end_time="06:30", is_hard_lock=True),
        "fixed_events": [],
        "buffer_mode": "COGNITIVE_LOAD",
    }
    base.update(overrides)
    return CommitmentsProfile.model_validate(base)


def test_sqlite_workspace_state_and_completions_roundtrip(tmp_path, monkeypatch):
    """A.1: SQLite GET/PUT/DELETE /api/state and /api/tasks/complete persistence across requests."""
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "m2_test.db"))
    client = TestClient(app)

    r_empty = client.get("/api/state")
    assert r_empty.status_code == 200
    assert r_empty.json()["exists"] is False

    payload = {
        "workspace_id": "default",
        "state": {
            "version": 2,
            "commitments": _clean_profile(horizon_days=14).model_dump(),
            "tasks": [{"task_id": "T1", "title": "Lab Mạng", "duration_min": 60, "deadline_day": "Wednesday"}],
            "algorithm": "SCORED_GREEDY",
            "pinned_blocks": [],
            "done_blocks": ["T1_P1"],
            "actual_durations": [["T1_P1", 75]],
        },
    }
    r_put = client.put("/api/state", json=payload)
    assert r_put.status_code == 200
    assert r_put.json()["status"] == "saved"

    r_get = client.get("/api/state")
    assert r_get.status_code == 200
    body = r_get.json()
    assert body["exists"] is True
    assert body["state"]["commitments"]["horizon_days"] == 14
    assert body["state"]["tasks"][0]["task_id"] == "T1"
    assert body["state"]["done_blocks"] == ["T1_P1"]

    r_comp = client.post(
        "/api/tasks/complete",
        json={"task_id": "T1", "category": "LAB", "estimated_min": 60, "actual_duration_min": 90, "completed": True},
    )
    assert r_comp.status_code == 200
    assert "completion_log" in r_comp.json()
    assert r_comp.json()["completion_log"]["actual_duration_min"] == 90

    r_logs = client.get("/api/tasks/completions")
    assert r_logs.status_code == 200
    assert len(r_logs.json()["completions"]) == 1
    assert r_logs.json()["completions"][0]["task_id"] == "T1"

    r_del = client.delete("/api/state")
    assert r_del.status_code == 200
    assert r_del.json()["removed"] is True
    assert client.get("/api/state").json()["exists"] is False


def test_horizon_days_14_and_cross_week_grid_states():
    """A.2: CommitmentsProfile.horizon_days=14 expands grid_states to 1344 slots while 7 keeps 672."""
    p7 = _clean_profile(horizon_days=7)
    p14 = _clean_profile(horizon_days=14)
    t_w1 = Task(task_id="W1", title="Week 1 Task", duration_min=60, deadline_day="Tuesday", priority=4)
    t_w2 = Task(
        task_id="W2",
        title="Week 2 Project",
        duration_min=60,
        deadline_day="Next Friday",
        start_after="Next Tuesday 08:00",
        priority=3,
    )

    out7, _ = ScheduleController.solve_schedule(p7, [t_w1], algorithm="SCORED_GREEDY")
    assert len(out7.grid_states) == 672
    assert out7.summary.hard_constraint_violations == 0

    out14, _ = ScheduleController.solve_schedule(p14, [t_w1, t_w2], algorithm="SCORED_GREEDY")
    assert len(out14.grid_states) == 1344
    assert out14.summary.hard_constraint_violations == 0
    w2_blk = next(b for b in out14.blocks if b.task_id == "W2")
    assert w2_blk.start_slot >= 7 * 96 + 96 + 32


def test_task_start_after_and_work_rhythm_bounds():
    """A.3: Task.start_after lower bound holds in greedy & backtracking; work_rhythm sets chunk bounds cleanly."""
    p = _clean_profile()
    # Thursday 09:00 = 3 * 96 + 36 = 324
    t_rel = Task(
        task_id="REL1",
        title="Released Thursday",
        duration_min=60,
        start_after="Thursday 09:00",
        deadline_day="Saturday",
        priority=5,
    )
    for algo in ("SCORED_GREEDY", "BACKTRACKING_BRANCH_AND_BOUND"):
        out, _ = ScheduleController.solve_schedule(p, [t_rel], algorithm=algo)
        assert out.summary.hard_constraint_violations == 0
        blk = next(b for b in out.blocks if b.task_id == "REL1")
        assert blk.start_slot >= 3 * 96 + 36

    t_flow = Task(task_id="FL1", title="Deep Focus", duration_min=105, deadline_day="Wednesday", work_rhythm="FLOW")
    assert t_flow.min_chunk_min == 60
    assert t_flow.max_chunk_min == 120
    out_flow, _ = ScheduleController.solve_schedule(p, [t_flow], algorithm="SCORED_GREEDY")
    flow_blocks = [b for b in out_flow.blocks if b.task_id == "FL1"]
    assert len(flow_blocks) == 1

    t_light = Task(task_id="LG1", title="Flashcards", duration_min=60, deadline_day="Wednesday", work_rhythm="LIGHT")
    assert t_light.min_chunk_min == 30
    assert t_light.max_chunk_min == 45
    assert t_light.is_splittable is True


def test_personal_habit_preferred_window_and_day_spreading():
    """A.3 (Q7.3 = A3): PersonalHabit spreads occurrences across days and honors preferred_window."""
    p = _clean_profile(
        personal_habits=[
            PersonalHabit(
                habit_id="H_RUN",
                name="Chạy bộ",
                preferred_window="EVENING",
                frequency_per_week=3,
                duration_min=45,
            )
        ]
    )
    out, _ = ScheduleController.solve_schedule(p, [], algorithm="SCORED_GREEDY")
    assert out.summary.hard_constraint_violations == 0
    habit_blocks = [b for b in out.blocks if b.task_id.startswith("H_RUN")]
    assert len(habit_blocks) == 3
    assert len({b.day for b in habit_blocks}) == 3
    for b in habit_blocks:
        slot_in_day = b.start_slot % 96
        assert 72 <= slot_in_day < 92


def test_offline_nl_parser_clock_tokens_do_not_misparse_duration():
    """A.3: Clock tokens like 19h30 and 14h00 - 16h00 do not corrupt duration_min."""
    parser = OfflineNLParser()

    r1 = parser.parse("Làm lab mạng 19h30 khoảng 90p", now_day="Monday", existing_count=0)
    assert r1["draft"]["duration_min"] == 90

    r2 = parser.parse("Học nhóm 14h00 - 16h00", now_day="Monday", existing_count=0)
    assert r2["draft"]["duration_min"] not in (840, 960, 1170)

    r3 = parser.parse("Học nhóm 14h00 - 16h00 khoảng 90p", now_day="Monday", existing_count=0)
    assert r3["draft"]["duration_min"] == 90

    r4 = parser.parse("Học Toán 1h30 trước 18:30", now_day="Monday", existing_count=0)
    assert r4["draft"]["duration_min"] == 90


def test_ui_progressive_disclosure_and_student_crud_contracts():
    """A.0–A.3 & B: UI serves Progressive Disclosure, persistence, week nav, Student edit/habit CRUD, COGNITIVE_LOAD."""
    client = TestClient(app)
    html = client.get("/").text
    js = client.get("/app.js").text

    for html_token in (
        "st-lab-only-modal",
        "stTaskAdvDetails",
        "stInpPriorityCore",
        "stInpStartAfter",
        "stInpWorkRhythm",
        "btnStWeekPrev",
        "btnStWeekNext",
        "btnStJumpRealtime",
        "stHorizonDaysSelect",
        "stSetHabitsList",
        "stHabitNewName",
        "stHabitNewWindow",
        "stHabitNewFreq",
        "stHabitNewDur",
        "btnSaveStTask",
    ):
        assert html_token in html

    for js_token in (
        "/api/state",
        "restorePersistedWorkspace",
        "syncTaskModalModeVisibility",
        "shiftStudentCalendarWeek",
        "changeStudentHorizonDays",
        "jumpToCurrentWeek",
        "editStudentTask",
        "addStudentPersonalHabit",
        "removeStudentPersonalHabit",
        "COGNITIVE_LOAD",
    ):
        assert js_token in js

    # Ensure analyzeQuickAddHybrid is no longer hardcoded to engine: "offline"
    qa_idx = js.index("async function analyzeQuickAddHybrid()")
    qa_slice = js[qa_idx : qa_idx + 800]
    assert 'engine: "offline"' not in qa_slice


def test_plan_and_compare_scientific_insights_and_block_diffs():
    """Step 1 UI Redesign Backend Telemetry: energy_level, peak match, context switches, verdict & block_diffs."""
    client = TestClient(app)
    minh = client.get("/api/presets").json()["presets"]["minh"]

    plan_res = client.post(
        "/api/plan",
        json={
            "commitments": minh["commitments"],
            "tasks": minh["tasks"],
            "algorithm": "SCORED_GREEDY",
        },
    )
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    m = plan_data["metrics"]
    for key in (
        "peak_match_rate_pct",
        "deep_peak_match_pct",
        "avg_energy_level",
        "context_switches",
        "batched_pairs",
    ):
        assert key in m
    assert len(plan_data["blocks"]) > 0
    assert all(isinstance(b.get("energy_level"), (int, float)) for b in plan_data["blocks"])

    # Compare baseline Energy-Blind EDF vs Adaptive SCORED_GREEDY on Minh preset & T01 scenario
    t01 = client.get("/api/scenarios/T01").json()
    for dataset in (minh, t01):
        cmp_res = client.post(
            "/api/compare",
            json={
                "commitments": dataset["commitments"],
                "tasks": dataset["tasks"],
                "algo_left": "GREEDY_EDF_FIRST_FIT",
                "algo_right": "SCORED_GREEDY",
            },
        )
        assert cmp_res.status_code == 200
        cmp_data = cmp_res.json()["comparison"]
        assert cmp_data["verdict_winner"] == "RIGHT"
        assert cmp_data["right_deep_peak_match_pct"] > cmp_data["left_deep_peak_match_pct"]
        assert cmp_data["different_block_placements"] > 0
        assert len(cmp_data["verdict_highlights"]) >= 1
        diffs = cmp_data["block_diffs"]
        assert len(diffs) >= 2
        assert any(d["changed"] for d in diffs)
        assert all("left_energy" in d and "right_energy" in d for d in diffs)


def test_redesigned_temporal_student_and_lab_ui_contracts():
    """Steps 2–3 UI Redesign: DD/MM/YYYY temporal engine, clean Student actions/habits, Lab 3-tab analytics."""
    client = TestClient(app)
    html = client.get("/").text
    js = client.get("/app.js").text

    for html_token in (
        "temporalContextBanner",
        "topWeekRangePill",
        "inpWeekStartDate",
        "studentToolsMenu",
        "stDayTemporal_0",
        "stDayDate_0",
        "stSubHabitsPane",
        "stMainHabitsList",
        "btnLabTabSingle",
        "btnLabTabCompare",
        "btnLabTabResilience",
        "kpiPeakMatch",
        "kpiExperienceVal",
        "labFixedInspectorPanel",
        "compareVerdictBanner",
        "compareDiffTableBody",
        "compareFullGridsDetails",
        "determinismLedgerBody",
        "stCalendarScrollContainer",
        "stCalendarHorizontalSlider",
        "stObservedRangeLabel",
        "stObservedDaysStrip",
        "stExtraWeek2Columns",
        "observedRangeCalendarPopover",
        "calPopoverGrid",
        "labGridScrollContainer",
        "labGridHorizontalSlider",
    ):
        assert html_token in html

    for forbidden in ("stNlCiteInput", "Ưu tiên Solver", 'id="inpTaskId"'):
        assert forbidden not in html

    for js_token in (
        "formatDateDDMMYYYY",
        "getBlockTemporalState",
        "resolveDeadlineDisplay",
        "rebaseScheduleToCurrentWeek",
        "loadPresetIntoCurrentWeek",
        "runComparisonPreset",
        "renderLastComparisonDiffTable",
        "runAllSolversDeterminismLedger",
        "switchStudentTasksSubtab",
        "addStudentHabitFromMainTab",
        "toggleObservedRangeCalendar",
        "renderObservedRangeCalendar",
        "updateObservedViewportRange",
        "onStHorizontalSliderInput",
        "onLabHorizontalSliderInput",
        "scrollToCalendarDay",
    ):
        assert js_token in js
