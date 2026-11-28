"""
Comprehensive Verification Suite for M5 (`v1.0-alpha/m5-cross-week-adaptation-and-repair`):
  - Group A: `CrossWeekPreferenceAdapter` (Pattern P13), Empirical Bayes Shrinkage,
             No Double-Shrinkage (Fix M-2), No Double-Buffering (`M4` Invariant #1),
             Per-Task Alpha Preservation in `ScheduleController` (Fix M-1),
             Revealed Chronotype & Guardrails (Fix M-6), Pydantic Pacing Bounds (Fix M-4),
             and Day-Specific `ADVISORY_BUFFER` without 7-day `hourly_levels` corruption (Fix M-3).
  - Group B: `disruption_chat.py` (Pattern P8 `LOCAL_INSERTION` >= 90% stability),
             Recurring vs Emergency intent filtering, Multi-turn clarification, Dual calling convention,
             and Post-repair ergonomic trough warning (Fix M-8).
  - Group C: 6 FastAPI Endpoints (`init-real-week`, `tasks/delete` with DAG orphan cleanup,
             `fixed-events/upsert`, `fixed-events/delete`, `adapt-next-week` LoA-4 SQLite bridge,
             and `simulation/multi-week` 3x SHA-256 determinism, < 500ms SLA, & W1->W4 convergence).
  - Group D: Layer-1 AST Purity & `INV-1..5` Guardrails.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import types

from fastapi.testclient import TestClient
import pytest

from smartschedule.api.app import app
from smartschedule.api.chat.disruption_chat import (
    extract_disruption_fields,
    handle_disruption_chat_turn,
    is_disruption_intent,
    is_disruption_prompt,
)
from smartschedule.core.config import CORE_DIR, PRESETS_DIR
from smartschedule.core.controller import ScheduleController
from smartschedule.core.cross_week_adapter import adapt_preferences_for_next_week
from smartschedule.core.models import CommitmentsProfile, FixedEvent, SleepSchedule, Task


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_file = tmp_path / "m5_isolated_test.sqlite3"
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(db_file))
    return db_file


@pytest.fixture()
def monday_profile() -> CommitmentsProfile:
    ref = datetime(2026, 11, 23, 8, 0, tzinfo=timezone(timedelta(hours=7)))
    return ScheduleController.build_empty_current_week_profile(
        student_id="TEST_M5_STUDENT",
        daily_start_time="23:30",
        daily_end_time="06:30",
        focus_preference="MORNING",
        estimate_habit="SOMETIMES",
        reference_dt=ref,
    )


# ===========================================================================
# GROUP A: CrossWeekPreferenceAdapter & M4 Mathematical Invariants
# ===========================================================================

def test_cold_start_zero_logs_preserves_priors(monday_profile: CommitmentsProfile):
    tasks = [
        Task(task_id="T1", title="Coding Lab", duration_min=60, category="CODING", cognitive_load=3, deadline_day="Friday"),
        Task(task_id="T2", title="Reading", duration_min=45, category="READING", cognitive_load=1, deadline_day="Saturday"),
    ]
    res = adapt_preferences_for_next_week(monday_profile, tasks, timeline_logs=[], kappa=3.0)

    assert res["category_alphas"]["CODING"]["alpha_light"] == pytest.approx(1.20)
    assert res["category_alphas"]["CODING"]["alpha_heavy"] == pytest.approx(1.35)
    assert res["preference_shifts"] == []
    assert res["adapted_profile"].focus_preference == "MORNING"


def test_single_extreme_outlier_clipped_and_shrunk_safely(monday_profile: CommitmentsProfile):
    tasks = [
        Task(task_id="T1", title="Hard Code", duration_min=60, category="CODING", cognitive_load=3, deadline_day="Friday")
    ]
    # A/E = 300 / 60 = 5.0 -> clipped to 2.50 -> (1/4)*2.50 + (3/4)*1.35 = 1.6375 -> clamped to 1.60!
    logs = [{"category": "CODING", "estimated_duration_min": 60, "actual_duration_min": 300, "cognitive_load": 3}]
    res = adapt_preferences_for_next_week(monday_profile, tasks, timeline_logs=logs, kappa=3.0)

    coding_alpha = res["category_alphas"]["CODING"]
    assert coding_alpha["ewma_ratio"] == pytest.approx(2.50)
    assert coding_alpha["alpha_heavy"] == pytest.approx(1.60)
    assert 1.00 <= coding_alpha["alpha_light"] <= 1.60


def test_no_double_shrinkage_sensitivity_at_small_sample(monday_profile: CommitmentsProfile):
    tasks = [
        Task(task_id="T_LIGHT", title="Quiz", duration_min=60, category="ASSIGNMENT", cognitive_load=1, deadline_day="Friday")
    ]
    # r_1 = 91.2 / 60 = 1.52 -> exact 1-step Bayes shrinkage: 0.25 * 1.52 + 0.75 * 1.20 = 1.28
    logs = [{"category": "ASSIGNMENT", "estimated_duration_min": 60, "actual_duration_min": 91.2, "cognitive_load": 1}]
    res = adapt_preferences_for_next_week(monday_profile, tasks, timeline_logs=logs, kappa=3.0)

    assert res["category_alphas"]["ASSIGNMENT"]["alpha_light"] == pytest.approx(1.28, abs=1e-3)


def test_multi_category_differentiation_and_no_double_buffering(monday_profile: CommitmentsProfile):
    raw_tasks = [
        Task(task_id="T_CODE", title="Code", duration_min=90, category="CODING", cognitive_load=3, deadline_day="Friday"),
        Task(task_id="T_READ", title="Read", duration_min=90, category="READING", cognitive_load=2, deadline_day="Friday"),
        Task(task_id="T_NONE", title="Locked", duration_min=60, category="CODING", cognitive_load=3, buffer_mode="NONE", deadline_day="Friday"),
    ]
    logs = [
        {"category": "CODING", "estimated_duration_min": 60, "actual_duration_min": 93, "cognitive_load": 3},
        {"category": "CODING", "estimated_duration_min": 60, "actual_duration_min": 96, "cognitive_load": 3},
        {"category": "CODING", "estimated_duration_min": 60, "actual_duration_min": 90, "cognitive_load": 3},
        {"category": "READING", "estimated_duration_min": 60, "actual_duration_min": 60, "cognitive_load": 2},
        {"category": "READING", "estimated_duration_min": 60, "actual_duration_min": 61, "cognitive_load": 2},
        {"category": "READING", "estimated_duration_min": 60, "actual_duration_min": 60, "cognitive_load": 2},
    ]

    pass1 = adapt_preferences_for_next_week(monday_profile, raw_tasks, timeline_logs=logs, kappa=3.0)
    t_code_1, t_read_1, t_none_1 = pass1["adapted_tasks"]

    assert t_code_1.duration_min == 90
    assert t_read_1.duration_min == 90
    assert t_code_1.alpha_heavy > 1.40
    assert t_read_1.alpha_light < 1.15
    assert t_none_1.buffer_mode == "NONE" and t_none_1.buffer_multiplier == 1.0

    # Re-applying on already-adapted tasks MUST NOT double-buffer duration_min or planned_duration_min!
    pass2 = adapt_preferences_for_next_week(pass1["adapted_profile"], pass1["adapted_tasks"], timeline_logs=logs, kappa=3.0)
    t_code_2 = pass2["adapted_tasks"][0]
    assert t_code_2.duration_min == 90
    assert t_code_2.get_planned_duration_min() == t_code_1.get_planned_duration_min()


def test_controller_preserves_per_category_task_alphas_during_solve(monday_profile: CommitmentsProfile):
    tasks = [
        Task(task_id="C1", title="Coding", duration_min=100, category="CODING", cognitive_load=3, deadline_day="Friday"),
        Task(task_id="R1", title="Reading", duration_min=100, category="READING", cognitive_load=3, deadline_day="Saturday"),
    ]
    logs = (
        [{"category": "CODING", "estimated_duration_min": 60, "actual_duration_min": 96, "cognitive_load": 3}] * 4
        + [{"category": "READING", "estimated_duration_min": 60, "actual_duration_min": 60, "cognitive_load": 3}] * 4
    )
    res = adapt_preferences_for_next_week(monday_profile, tasks, timeline_logs=logs, kappa=3.0)

    out, _ = ScheduleController.solve_schedule(res["adapted_profile"], res["adapted_tasks"], algorithm="SCORED_GREEDY")
    c_total = sum(b.duration_min for b in out.blocks if b.task_id == "C1")
    r_total = sum(b.duration_min for b in out.blocks if b.task_id == "R1")

    assert c_total == 150
    assert r_total == 120
    c_blocks = [b for b in out.blocks if b.task_id == "C1"]
    assert any(any(r.get("code") == "ESTIMATE_BUFFER" for r in b.reasons) for b in c_blocks)


def test_revealed_chronotype_shift_lark_to_owl_and_guardrail(monday_profile: CommitmentsProfile):
    tasks = [
        Task(task_id="DEEP_FREE", title="Deep Unpinned", duration_min=60, cognitive_load=3, deadline_day="Friday"),
        Task(
            task_id="DEEP_LOCKED",
            title="Deep Afternoon Locked",
            duration_min=60,
            cognitive_load=3,
            preferred_window="AFTERNOON",
            deadline_day="Friday",
        ),
    ]
    owl_logs = [
        {"window": "MORNING", "estimated_duration_min": 60, "actual_duration_min": 0, "adhered": False},
        {"window": "MORNING", "estimated_duration_min": 60, "actual_duration_min": 0, "adhered": False},
        {"window": "MORNING", "estimated_duration_min": 60, "actual_duration_min": 90, "adhered": True},
        {"window": "EVENING", "estimated_duration_min": 60, "actual_duration_min": 55, "adhered": True},
        {"window": "EVENING", "estimated_duration_min": 60, "actual_duration_min": 60, "adhered": True},
        {"window": "EVENING", "estimated_duration_min": 60, "actual_duration_min": 58, "adhered": True},
    ]
    res = adapt_preferences_for_next_week(monday_profile, tasks, timeline_logs=owl_logs)

    assert res["adapted_profile"].focus_preference == "EVENING"
    assert res["adapted_profile"].get_energy_profile().level_for_hour(20) == 3
    assert res["adapted_tasks"][0].preferred_window == "EVENING"
    assert res["adapted_tasks"][1].preferred_window == "AFTERNOON"

    # Guardrail: when stated MORNING also has strong adherence, do not flip chronotype
    strong_morning_logs = [
        {"window": "MORNING", "estimated_duration_min": 60, "actual_duration_min": 60, "adhered": True},
        {"window": "MORNING", "estimated_duration_min": 60, "actual_duration_min": 58, "adhered": True},
        {"window": "EVENING", "estimated_duration_min": 60, "actual_duration_min": 55, "adhered": True},
        {"window": "EVENING", "estimated_duration_min": 60, "actual_duration_min": 55, "adhered": True},
    ]
    res_guard = adapt_preferences_for_next_week(monday_profile, tasks, timeline_logs=strong_morning_logs)
    assert res_guard["adapted_profile"].focus_preference == "MORNING"


def test_pacing_adjustment_enforces_explicit_chunk_bounds_in_pydantic(monday_profile: CommitmentsProfile):
    tasks = [
        Task(
            task_id="FLOW_HEAVY",
            title="Long Research Synthesis",
            duration_min=120,
            category="PROJECT",
            cognitive_load=3,
            work_rhythm="FLOW",
            deadline_day="Saturday",
        )
    ]
    fatigue_logs = [
        {"category": "PROJECT", "estimated_duration_min": 90, "planned_duration_min": 90, "actual_duration_min": 120, "fatigue_after": 0.78},
        {"category": "PROJECT", "estimated_duration_min": 90, "planned_duration_min": 90, "actual_duration_min": 115, "fatigue_after": 0.82},
    ]
    res = adapt_preferences_for_next_week(monday_profile, tasks, timeline_logs=fatigue_logs)
    t_adapted = res["adapted_tasks"][0]

    assert res["pacing_adjusted"] is True
    assert t_adapted.min_chunk_min == 45
    assert t_adapted.max_chunk_min == 75
    assert t_adapted.is_splittable is True

    out, _ = ScheduleController.solve_schedule(res["adapted_profile"], res["adapted_tasks"], algorithm="SCORED_GREEDY")
    placed = [b for b in out.blocks if b.task_id == "FLOW_HEAVY"]
    assert len(placed) >= 2
    assert all(b.duration_min <= 75 for b in placed)


def test_chronic_disruption_zone_adds_single_day_advisory_buffer_without_corrupting_other_days(
    monday_profile: CommitmentsProfile,
):
    profile_evening = monday_profile.model_copy(update={"focus_preference": "EVENING"}, deep=True)
    tasks = [
        Task(task_id="T_THU", title="Evening Study", duration_min=60, cognitive_load=3, deadline_day="Saturday")
    ]
    logs = [
        {"disruption_slot_window": "Thursday 19:30-21:00"},
        {"disruption_slot_window": "Thursday 19:30-21:00"},
    ]
    res = adapt_preferences_for_next_week(profile_evening, tasks, timeline_logs=logs)

    assert len(res["chronic_disruption_zones"]) == 1
    zone = res["chronic_disruption_zones"][0]
    assert zone["day_of_week"] == "Thursday"
    assert zone["action"] == "ADVISORY_BUFFER_ADDED"

    adv_events = [fe for fe in res["adapted_profile"].fixed_events if fe.category == "ADVISORY_BUFFER"]
    assert len(adv_events) == 1
    assert adv_events[0].day_of_week == "Thursday"
    # Evening energy at 20:00 on non-disrupted days MUST remain Peak (3), never degraded globally!
    assert res["adapted_profile"].get_energy_profile().level_for_hour(20) == 3


# ===========================================================================
# GROUP B: Conversational Disruption Repair (`disruption_chat.py` — Pattern P8)
# ===========================================================================

def test_disruption_intent_filtering_vs_recurring_and_tasks():
    assert is_disruption_intent("Chiều thứ 4 từ 14h đến 16h họp CLB đột xuất") is True
    assert is_disruption_prompt("Tối mai 19h30 - 21h cúp điện đột xuất") is True
    assert is_disruption_intent("Sáng thứ 5 từ 9h đến 10h30 bận họp nhóm gấp") is True

    assert is_disruption_intent("Thêm lịch học cố định mỗi thứ 4 từ 8h đến 10h") is False
    assert is_disruption_intent("Mỗi ngày từ 12h đến 13h ăn trưa") is False
    assert is_disruption_intent("Làm bài tập Giải tích 2 tiếng trước thứ 6") is False
    assert is_disruption_intent("Xóa bài tập Giải tích") is False


def test_disruption_chat_missing_time_requests_clarification_then_applies(isolated_db: Path):
    comm = json.loads((PRESETS_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    tasks = json.loads((PRESETS_DIR / "sample_week_tasks.json").read_text(encoding="utf-8"))

    turn1 = handle_disruption_chat_turn(
        {
            "prompt": "Chiều thứ Tư mình bận họp CLB đột xuất",
            "commitments": comm,
            "tasks": tasks,
            "auto_save": False,
        }
    )
    assert turn1["status"] == "NEEDS_CLARIFICATION"
    assert "time_range" in turn1["missing_fields"]
    assert turn1["pending_draft"]["day_of_week"] == "Wednesday"
    assert len(turn1["quick_chips"]) >= 2

    turn2 = handle_disruption_chat_turn(
        {
            "prompt": "Từ 2h đến 4h chiều",
            "commitments": comm,
            "tasks": tasks,
            "pending_draft": turn1["pending_draft"],
            "auto_save": False,
        }
    )
    assert turn2["status"] == "APPLIED"
    assert turn2["repair_summary"]["disruption_event"]["start_time"] == "14:00"
    assert turn2["repair_summary"]["disruption_event"]["end_time"] == "16:00"


def test_disruption_chat_local_insertion_high_stability_and_p8_trace(isolated_db: Path):
    comm = json.loads((PRESETS_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    tasks = json.loads((PRESETS_DIR / "sample_week_tasks.json").read_text(encoding="utf-8"))

    res = handle_disruption_chat_turn(
        {
            "prompt": "Thứ Hai từ 08:00 đến 09:30 họp khẩn cấp",
            "commitments": comm,
            "tasks": tasks,
            "workspace_id": "ws_p8_test",
            "auto_save": True,
        }
    )
    assert res["status"] == "APPLIED"
    assert res["intent"] == "DISRUPTION_REPAIR"
    assert res["repair_summary"]["stability_score"] >= 90.0
    assert any(r["pattern_id"] == "P8" for r in res["thinking_summary"]["pattern_rules"])
    assert any(fe["category"] == "DISRUPTION" for fe in res["updated_commitments"]["fixed_events"])


def test_disruption_chat_dual_calling_convention_for_m4_compatibility(
    isolated_db: Path, monday_profile: CommitmentsProfile
):
    tasks_raw = [{"task_id": "T1", "title": "Study Math", "duration_min": 60, "deadline_day": "Friday"}]
    res_unpacked = handle_disruption_chat_turn(
        "Thứ Ba từ 09:00 đến 10:30 bận khám bệnh đột xuất",
        monday_profile,
        tasks_raw,
        [],
        {},
        "SCORED_GREEDY",
        "ws_m4_compat",
        False,
    )
    assert res_unpacked["status"] == "APPLIED"
    assert res_unpacked["repair_summary"]["disruption_event"]["day_of_week"] == "Tuesday"


# ===========================================================================
# GROUP C: FastAPI Endpoints, Real SQLite Bridge & Multi-Week Simulation
# ===========================================================================

def test_api_init_real_week_computes_monday_and_rejects_unsafe_sleep(isolated_db: Path):
    preset_before = (PRESETS_DIR / "sample_week_commitments.json").read_text(encoding="utf-8")
    client = TestClient(app)

    resp = client.post(
        "/api/workspace/init-real-week",
        json={
            "workspace_id": "ws_real_init",
            "daily_start_time": "23:00",
            "daily_end_time": "06:30",
            "focus_preference": "EVENING",
            "estimate_habit": "OFTEN",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    ws_dt = datetime.fromisoformat(body["commitments"]["planning_week_start"])
    assert ws_dt.weekday() == 0
    assert body["tasks"] == []
    assert body["commitments"]["focus_preference"] == "EVENING"

    # Reject < 6h sleep (Pattern P6 invariant)
    bad_resp = client.post(
        "/api/workspace/init-real-week",
        json={"workspace_id": "ws_bad_sleep", "sleep_start": "02:00", "sleep_end": "05:00"},
    )
    assert bad_resp.status_code == 400
    assert (PRESETS_DIR / "sample_week_commitments.json").read_text(encoding="utf-8") == preset_before


def test_api_delete_task_cleans_dangling_dag_dependencies_and_pins(
    isolated_db: Path, monday_profile: CommitmentsProfile
):
    client = TestClient(app)
    tasks = [
        {"task_id": "PREREQ_A", "title": "Design Spec", "duration_min": 60, "deadline_day": "Thursday"},
        {
            "task_id": "CHILD_B",
            "title": "Implement Code",
            "duration_min": 60,
            "deadline_day": "Friday",
            "depends_on": ["PREREQ_A"],
        },
    ]
    pinned = [
        {
            "block_id": "PIN_A",
            "task_id": "PREREQ_A",
            "title": "Design Spec",
            "day": "Tuesday",
            "start_time": "08:00",
            "end_time": "09:00",
            "start_slot": 96 + 32,
            "end_slot": 96 + 36,
            "duration_min": 60,
            "state": "PINNED",
        }
    ]

    resp = client.post(
        "/api/tasks/delete",
        json={
            "workspace_id": "ws_del_test",
            "commitments": monday_profile.model_dump(),
            "tasks": tasks,
            "pinned_blocks": pinned,
            "task_id": "PREREQ_A",
            "save": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted_task_id"] == "PREREQ_A"
    assert len(data["updated_tasks"]) == 1
    assert data["updated_tasks"][0]["task_id"] == "CHILD_B"
    assert data["updated_tasks"][0]["depends_on"] == []
    assert data["updated_pinned_blocks"] == []
    assert data["schedule"]["summary"]["tasks_placed"] == 1


def test_api_fixed_events_upsert_and_delete_roundtrip(
    isolated_db: Path, monday_profile: CommitmentsProfile
):
    client = TestClient(app)
    r_add = client.post(
        "/api/fixed-events/upsert",
        json={
            "workspace_id": "ws_fe_test",
            "commitments": monday_profile.model_dump(),
            "tasks": [],
            "event": {
                "event_id": "CLUB_1",
                "title": "Sinh hoạt CLB",
                "day_of_week": "Wednesday",
                "start_time": "18:00",
                "end_time": "19:30",
                "category": "MEETING",
            },
            "save": True,
        },
    )
    assert r_add.status_code == 200
    assert len(r_add.json()["updated_commitments"]["fixed_events"]) == 1

    # Updating same event_id replaces in place without duplicating
    r_upd = client.post(
        "/api/fixed-events/upsert",
        json={
            "workspace_id": "ws_fe_test",
            "event": {
                "event_id": "CLUB_1",
                "title": "Sinh hoạt CLB (Đổi giờ)",
                "day_of_week": "Wednesday",
                "start_time": "19:00",
                "end_time": "20:30",
                "category": "MEETING",
            },
        },
    )
    assert r_upd.status_code == 200
    fe_list = r_upd.json()["updated_commitments"]["fixed_events"]
    assert len(fe_list) == 1 and fe_list[0]["start_time"] == "19:00"

    r_del = client.post(
        "/api/fixed-events/delete",
        json={"workspace_id": "ws_fe_test", "event_id": "CLUB_1"},
    )
    assert r_del.status_code == 200
    assert r_del.json()["updated_commitments"]["fixed_events"] == []


def test_api_adapt_next_week_from_real_sqlite_logs_loa4_preview_and_apply(
    isolated_db: Path, monday_profile: CommitmentsProfile
):
    client = TestClient(app)
    ws_id = "ws_real_adapt"
    next_tasks = [
        {"task_id": "NEXT_C1", "title": "Backend Lab", "duration_min": 90, "category": "CODING", "cognitive_load": 3, "deadline_day": "Friday"}
    ]
    client.put(
        "/api/state",
        json={"workspace_id": ws_id, "state": {"commitments": monday_profile.model_dump(), "tasks": next_tasks}},
    )

    # Log 3 real completions with ~1.58x overrun in CODING
    for act in (95, 92, 98):
        rc = client.post(
            "/api/tasks/complete",
            json={
                "workspace_id": ws_id,
                "task_id": "OLD_C",
                "category": "CODING",
                "estimated_duration_min": 60,
                "actual_duration_min": act,
                "completed": True,
            },
        )
        assert rc.status_code == 200

    # Preview mode (default apply=False — LoA-4 safety!)
    preview = client.post(
        "/api/workspace/adapt-next-week",
        json={"workspace_id": ws_id, "next_week_tasks": next_tasks, "apply": False},
    )
    assert preview.status_code == 200
    p_body = preview.json()
    assert p_body["applied"] is False
    assert p_body["category_alphas"]["CODING"]["alpha_heavy"] > 1.42

    saved_before = client.get("/api/state", params={"workspace_id": ws_id}).json()
    assert saved_before["state"]["tasks"][0].get("alpha_heavy", 1.35) == pytest.approx(1.35)

    # Explicit opt-in apply=True persists adapted parameters
    applied = client.post(
        "/api/workspace/adapt-next-week",
        json={"workspace_id": ws_id, "next_week_tasks": next_tasks, "apply": True},
    )
    assert applied.status_code == 200 and applied.json()["applied"] is True
    saved_after = client.get("/api/state", params={"workspace_id": ws_id}).json()
    assert saved_after["state"]["tasks"][0]["alpha_heavy"] > 1.42


def test_api_multi_week_simulation_determinism_convergence_and_sla(isolated_db: Path):
    client = TestClient(app)
    runs = [
        client.post("/api/simulation/multi-week", json={"weeks": 4, "n_students": 1, "seed": 42}).json()
        for _ in range(3)
    ]

    # Single student (default n=1): determinism + interactive SLA only.
    assert runs[0]["determinism_hash"] == runs[1]["determinism_hash"] == runs[2]["determinism_hash"]
    assert runs[0]["execution_time_ms"] < 1000.0

    # Convergence is a population claim. With one student a week has only 6-9 blocks, so one
    # block flips adherence by 11-17 points, and W4 lands in the learning transient (focus moved
    # to EVENING in W3, chronic Thursday zone needs 2 collisions -> learned only after W4).
    # Seed sweep 40..49 on the real InSilicoStudentSimulator: n=1 converges 1/5, n=10 converges 9/10.
    cohort = client.post("/api/simulation/multi-week", json={"weeks": 4, "n_students": 10, "seed": 42}).json()
    assert cohort["simulator_backend"] == "InSilicoStudentSimulator"
    assert cohort["converged"] is True
    w1 = cohort["weeks_summary"][0]
    w4 = cohort["weeks_summary"][-1]
    assert w4["adherence_pct"] > w1["adherence_pct"]
    assert w4["on_time_value_pct"] > w1["on_time_value_pct"]
    assert w4["learned_focus"] == "EVENING"

    # Also verify multi-student cohort aggregation mode + chat disruption E2E route
    cohort = client.post("/api/simulation/multi-week", json={"weeks": 4, "n_students": 4, "seed": 101}).json()
    assert len(cohort["weeks_summary"]) == 4
    assert cohort["weeks_summary"][-1]["on_time_value_pct"] > cohort["weeks_summary"][0]["on_time_value_pct"]

    chat_disr = client.post(
        "/api/chat/turn",
        json={
            "workspace_id": "ws_chat_e2e_disr",
            "prompt": "Thứ Năm từ 19:30 đến 21:00 họp CLB đột xuất",
            "auto_save": False,
        },
    )
    assert chat_disr.status_code == 200
    assert chat_disr.json()["intent"] == "DISRUPTION_REPAIR"


# ===========================================================================
# GROUP D: Architectural Layer Purity (`INV-1`..`INV-5`)
# ===========================================================================

def test_m5_core_modules_strict_layer_purity():
    forbidden_prefixes = (
        "smartschedule.api",
        "smartschedule.nlp",
        "smartschedule.core.storage",
        "fastapi",
        "spacy",
        "transformers",
        "docling",
        "google",
    )
    for filename in ("cross_week_adapter.py", "controller.py"):
        py_path = CORE_DIR / filename
        tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)

        for mod in imported:
            assert not mod.startswith(forbidden_prefixes), (
                f"Layer purity violation in {filename}: forbidden import '{mod}'"
            )
    # Specifically ensure cross_week_adapter never imports solvers either
    adapter_tree = ast.parse((CORE_DIR / "cross_week_adapter.py").read_text(encoding="utf-8"))
    adapter_imps = {
        node.module
        for node in ast.walk(adapter_tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(m.startswith("smartschedule.core.solvers") for m in adapter_imps)


# ===========================================================================
# GROUP E: Red-Team Adversarial & Integration Edge Cases (Passes 1–3)
# ===========================================================================

def test_nan_inf_bool_garbage_logs_ignored_safely(monday_profile: CommitmentsProfile):
    tasks = [
        Task(task_id="T1", title="Code", duration_min=60, category="CODING", cognitive_load=3, deadline_day="Friday")
    ]
    corrupt_logs = [
        {"category": "CODING", "estimated_duration_min": float("nan"), "actual_duration_min": 60, "fatigue_after": float("nan")},
        {"category": "CODING", "estimated_duration_min": 60, "actual_duration_min": float("inf"), "fatigue_after": float("inf")},
        {"category": "CODING", "estimated_duration_min": True, "actual_duration_min": 120},
        {"category": "CODING", "estimated_duration_min": -30, "actual_duration_min": 60},
    ]
    res = adapt_preferences_for_next_week(
        monday_profile,
        tasks,
        timeline_logs=corrupt_logs,
        kappa=float("nan"),
        lambda_ewma=float("inf"),
    )
    assert res["category_alphas"]["CODING"]["sample_count"] == 0
    assert res["category_alphas"]["CODING"]["alpha_light"] == pytest.approx(1.20)
    assert res["category_alphas"]["CODING"]["alpha_heavy"] == pytest.approx(1.35)


def test_disruption_vietnamese_midnight_now_and_clean_titles():
    ref = datetime(2026, 11, 25, 14, 17, tzinfo=timezone(timedelta(hours=7)))  # Wednesday 14:17
    prof = ScheduleController.build_empty_current_week_profile(reference_dt=ref)

    f_midnight = extract_disruption_fields("Tối thứ 5 từ 8h đến 12h đêm bận việc đột xuất", prof)
    assert f_midnight["day_of_week"] == "Thursday"
    assert f_midnight["start_time"] == "20:00"
    assert f_midnight["end_time"] == "23:59"

    f_24h = extract_disruption_fields("Tối thứ 5 từ 20h đến 24h cúp điện đột xuất", prof)
    assert f_24h["day_of_week"] == "Thursday"
    assert f_24h["start_time"] == "20:00"
    assert f_24h["end_time"] == "23:59"
    assert "cúp điện" in f_24h["title"].lower()

    f_now = extract_disruption_fields("Ngay bây giờ mình bận họp khẩn cấp 90 phút", prof)
    assert f_now["day_of_week"] == "Wednesday"
    assert f_now["start_time"] == "14:15"
    assert f_now["end_time"] == "15:45"
    assert "họp khẩn cấp" in f_now["title"].lower()

    f_zero = extract_disruption_fields("Chiều thứ 4 từ 14h đến 14h họp đột xuất", prof)
    assert "time_range" in f_zero["missing_fields"]


def test_advisory_buffer_trims_partial_class_overlap_and_is_idempotent(monday_profile: CommitmentsProfile):
    prof = monday_profile.model_copy(deep=True)
    prof.fixed_events.append(
        FixedEvent(
            event_id="CLS_TTH",
            title="Evening Seminar",
            day_of_week=["Tuesday", "Thursday"],
            start_time="19:00",
            end_time="20:15",
            category="ACADEMIC_CLASS",
        )
    )
    tasks = [Task(task_id="T1", title="Study", duration_min=60, deadline_day="Saturday")]
    logs = [
        {"disruption_slot_window": "Thursday 19:30-21:00"},
        {"disruption_slot_window": "Thursday 19:30-21:00"},
    ]
    r1 = adapt_preferences_for_next_week(prof, tasks, timeline_logs=logs)
    r2 = adapt_preferences_for_next_week(r1["adapted_profile"], tasks, timeline_logs=logs + logs)

    adv_events = [fe for fe in r2["adapted_profile"].fixed_events if fe.category == "ADVISORY_BUFFER"]
    assert len(adv_events) == 1
    assert adv_events[0].day_of_week == "Thursday"
    assert adv_events[0].start_time == "20:15"
    assert adv_events[0].end_time == "21:00"


def test_overloaded_schedule_and_disruption_edge_case_no_crash(
    isolated_db: Path, monday_profile: CommitmentsProfile
):
    heavy_tasks = [
        Task(
            task_id=f"HV_{i}",
            title=f"Heavy Task {i}",
            duration_min=240,
            priority=5,
            cognitive_load=3,
            deadline_day="Monday",
            deadline_time="20:00",
        ).model_dump()
        for i in range(5)
    ]
    res = handle_disruption_chat_turn(
        {
            "prompt": "Thứ Hai từ 09:00 đến 11:00 họp khẩn cấp",
            "commitments": monday_profile.model_dump(),
            "tasks": heavy_tasks,
            "auto_save": False,
        }
    )
    assert res["status"] == "APPLIED"
    assert res["edge_case"] is not None
    assert res["edge_case"]["code"] == "POST_DISRUPTION_OVERLOAD"


def test_adapt_next_week_advance_week_shifts_iso_deadlines(
    isolated_db: Path, monday_profile: CommitmentsProfile
):
    client = TestClient(app)
    iso_task = {
        "task_id": "T_ISO_DUE",
        "title": "Chat-Created ISO Task",
        "duration_min": 60,
        "category": "CODING",
        "cognitive_load": 3,
        "due": "2026-11-27T23:59:00+07:00",
        "start_after": "2026-11-24T09:00:00+07:00",
    }
    resp = client.post(
        "/api/workspace/adapt-next-week",
        json={
            "workspace_id": "ws_iso_shift",
            "commitments": monday_profile.model_dump(),
            "next_week_tasks": [iso_task],
            "timeline_logs": [],
            "advance_week": True,
            "apply": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["schedule"]["summary"]["tasks_placed"] == 1
    assert body["adapted_tasks"][0]["due"].startswith("2026-12-04")


def test_delete_task_cleans_completed_blocks_in_workspace(
    isolated_db: Path, monday_profile: CommitmentsProfile
):
    client = TestClient(app)
    ws_id = "ws_del_completed"
    tasks = [
        {"task_id": "DEL_ME", "title": "Old", "duration_min": 60, "deadline_day": "Thursday"},
        {"task_id": "KEEP_ME", "title": "Keep", "duration_min": 60, "deadline_day": "Friday"},
    ]
    client.put(
        "/api/state",
        json={
            "workspace_id": ws_id,
            "state": {
                "commitments": monday_profile.model_dump(),
                "tasks": tasks,
                "completedBlocks": {
                    "DEL_ME_P1": {"actual_min": 60},
                    "KEEP_ME_P1": {"actual_min": 45},
                },
            },
        },
    )
    r_del = client.post("/api/tasks/delete", json={"workspace_id": ws_id, "task_id": "DEL_ME"})
    assert r_del.status_code == 200
    st = client.get("/api/state", params={"workspace_id": ws_id}).json()["state"]
    assert "DEL_ME_P1" not in st["completedBlocks"]
    assert "KEEP_ME_P1" in st["completedBlocks"]


def test_multi_week_simulation_dynamic_m7_simulator_hookup(
    isolated_db: Path, monkeypatch: pytest.MonkeyPatch
):
    mock_mod = types.ModuleType("smartschedule.core.student_simulator")

    class MockM7InSilicoSimulator:
        def __init__(self, student_id: str, seed: int = 42, latent_profile=None):
            self.student_id = student_id
            self.seed = seed

        def simulate_week_execution(self, profile, tasks, schedule):
            is_eve = profile.focus_preference == "EVENING"
            return [
                {
                    "task_id": b.task_id,
                    "block_id": b.block_id,
                    "category": b.category,
                    "cognitive_load": b.cognitive_load or 3,
                    "day": b.day,
                    "window": "EVENING" if int(b.start_time[:2]) >= 18 else "MORNING",
                    "estimated_duration_min": 60,
                    "planned_duration_min": b.duration_min,
                    "actual_duration_min": 85 if (is_eve or int(b.start_time[:2]) >= 18) else 0,
                    "adhered": bool(is_eve or int(b.start_time[:2]) >= 18),
                    "overrun_min": 0 if b.duration_min >= 85 else 25,
                    "fatigue_after": 0.40,
                    "disruption_slot_window": "Thursday 19:30-21:00",
                }
                for b in schedule.blocks
            ]

    mock_mod.InSilicoStudentSimulator = MockM7InSilicoSimulator
    monkeypatch.setitem(sys.modules, "smartschedule.core.student_simulator", mock_mod)

    client = TestClient(app)
    resp = client.post("/api/simulation/multi-week", json={"weeks": 4, "n_students": 1, "seed": 42})
    assert resp.status_code == 200
    body = resp.json()
    assert body["simulator_backend"] == "InSilicoStudentSimulator"
    assert body["converged"] is True
    assert body["weeks_summary"][-1]["on_time_value_pct"] > body["weeks_summary"][0]["on_time_value_pct"]



# ===========================================================================
# GROUP F: M4 verification regressions (B4, B5, B8 — M4_Verification_Notes.md)
# ===========================================================================

def test_b5_delete_and_cancel_phrases_never_become_disruptions():
    for prompt in (
        "Hủy lịch họp CLB thứ 5",
        "Mình muốn hủy lịch họp CLB thứ 5",
        "Thứ 5 hủy lịch họp CLB nhé",
        "Xóa giúp mình lịch họp nhóm",
        "Bỏ lịch họp nhóm tối thứ 6",
    ):
        assert is_disruption_intent(prompt) is False, prompt
    # "Huy" is also a given name; a strong emergency cue still wins over a cancelled study session.
    assert is_disruption_intent("Huy rủ mình họp khẩn 19h-21h tối nay") is True
    assert is_disruption_intent("Bận đột xuất họp CLB, hủy buổi tự học tối nay 19h-21h") is True


def test_b8_same_day_period_resolves_to_today_and_title_is_clean():
    ref = datetime(2026, 11, 26, 15, 0, tzinfo=timezone(timedelta(hours=7)))  # Thursday 15:00
    prof = ScheduleController.build_empty_current_week_profile(reference_dt=ref)

    f_tonight = extract_disruption_fields("Tối nay mình bận đột xuất họp nhóm 19h-21h", prof)
    assert f_tonight["missing_fields"] == []
    assert f_tonight["day_of_week"] == "Thursday"
    assert (f_tonight["start_time"], f_tonight["end_time"]) == ("19:00", "21:00")
    assert f_tonight["title"] == "Họp nhóm đột xuất"

    f_afternoon = extract_disruption_fields("Chiều nay cúp điện đột xuất 16h-18h", prof)
    assert f_afternoon["day_of_week"] == "Thursday"
    assert "tối nay" not in f_afternoon["title"].lower() and "chiều nay" not in f_afternoon["title"].lower()

    # An explicit weekday still wins over the same-day anchor.
    assert extract_disruption_fields("Họp CLB đột xuất tối mai 19h-21h", prof)["day_of_week"] == "Friday"


def test_b4_one_off_disruption_is_not_carried_into_next_week(monday_profile: CommitmentsProfile):
    profile = monday_profile.model_copy(update={"focus_preference": "EVENING"}, deep=True)
    profile.fixed_events.extend(
        [
            FixedEvent(event_id="CLASS_1", title="Giải tích", day_of_week="Tuesday", start_time="07:30", end_time="09:30"),
            FixedEvent(
                event_id="DISR_ONE",
                title="Họp CLB đột xuất",
                day_of_week="Thursday",
                start_time="19:30",
                end_time="21:00",
                category="DISRUPTION",
            ),
        ]
    )
    tasks = [Task(task_id="T_THU", title="Evening Study", duration_min=60, cognitive_load=3, deadline_day="Saturday")]

    # One occurrence only: the event belongs to this week and must vanish next week.
    res_once = adapt_preferences_for_next_week(profile, tasks, timeline_logs=[{"disruption_slot_window": "Thursday 19:30-21:00"}])
    cats_once = [fe.category for fe in res_once["adapted_profile"].fixed_events]
    assert "DISRUPTION" not in cats_once
    assert any(fe.event_id == "CLASS_1" for fe in res_once["adapted_profile"].fixed_events)
    assert res_once["chronic_disruption_zones"] == []

    # Two occurrences (from logs): chronic zone is still learned, and the advisory buffer is no longer
    # blocked by the stale one-off DISRUPTION event sitting on the same slots.
    logs_twice = [{"disruption_slot_window": "Thursday 19:30-21:00"}] * 2
    res_twice = adapt_preferences_for_next_week(profile, tasks, timeline_logs=logs_twice)
    assert "DISRUPTION" not in [fe.category for fe in res_twice["adapted_profile"].fixed_events]
    assert [z["action"] for z in res_twice["chronic_disruption_zones"]] == ["ADVISORY_BUFFER_ADDED"]
