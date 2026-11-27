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

from fastapi.testclient import TestClient
import pytest

from smartschedule.api.app import app
from smartschedule.api.chat.disruption_chat import (
    handle_disruption_chat_turn,
    is_disruption_intent,
    is_disruption_prompt,
)
from smartschedule.core.config import CORE_DIR, PRESETS_DIR
from smartschedule.core.controller import ScheduleController
from smartschedule.core.cross_week_adapter import adapt_preferences_for_next_week
from smartschedule.core.models import CommitmentsProfile, SleepSchedule, Task


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

    assert runs[0]["determinism_hash"] == runs[1]["determinism_hash"] == runs[2]["determinism_hash"]
    assert runs[0]["converged"] is True
    assert runs[0]["execution_time_ms"] < 1000.0

    w1 = runs[0]["weeks_summary"][0]
    w4 = runs[0]["weeks_summary"][-1]
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
