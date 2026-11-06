"""
Automated Unit & FastAPI Verification Tests for Feature 002 (F15):
Smart Overload Triage, Habit-Skipping & Interactive Trade-off Preview Engine.
Author: Hoang Minh Anh (Thinker 2 - Perspective 4: Overload & Alerts / UI-UX Review Flow)

Covers Acceptance Criteria AC1–AC6 & Edge Cases E1–E5 from `specs/002-overload-triage-preview/spec.md`:
  - AC1: `SKIP_HABIT`, `SHORTEN_TASK`, `POSTPONE_LOWEST` generation on Scenario T06 & Minh's Week
  - AC2: What-If Preview (`POST /api/overload/preview`) for `SHORTEN_TASK` and `SKIP_HABIT` on T06
  - AC3: What-If Preview (`ALLOW_SPLIT` and `POSTPONE_LOWEST`) on Fragmentation Failure (T03)
  - AC4: Dependency DAG (`depends_on`) protection against skipping/postponing prerequisites (H3)
  - AC5: Stateless deep-copy immutability (`INV-3`) & Sleep/Commitment lock preservation (`INV-4`)
  - AC6: 3x SHA-256 Determinism & minimal stub payload backward compatibility
"""

from fastapi.testclient import TestClient
import pytest

from src.controller import ScheduleController
from src.models import CommitmentsProfile, FixedEvent, SleepSchedule, Task
from src.overload_triage import OverloadTriageEngine
from web.api import app

client = TestClient(app)


def test_ac1_t06_overload_generates_skip_habit_shorten_and_postpone_options():
    """
    AC1: Scenario T06 (1365m free vs 1470m needed -> 105m shortage) must return
    enriched overload options including 'SKIP_HABIT', 'SHORTEN_TASK', and 'POSTPONE_LOWEST',
    ordered by least academic harm ('SKIP_HABIT' first).
    """
    res_sc = client.get("/api/scenarios/t06")
    assert res_sc.status_code == 200
    sc = res_sc.json()

    res_plan = client.post(
        "/api/plan",
        json={"commitments": sc["commitments"], "tasks": sc["tasks"], "algorithm": "EDF"},
    )
    assert res_plan.status_code == 200
    data = res_plan.json()

    overload = data.get("overload")
    assert overload is not None
    assert overload["error_type"] == "CAPACITY_SHORTAGE"
    assert overload["shortage_minutes"] == 105

    options = overload.get("options", [])
    assert len(options) >= 3
    option_codes = [opt.get("code") for opt in options]
    assert "SKIP_HABIT" in option_codes
    assert "SHORTEN_TASK" in option_codes
    assert "POSTPONE_LOWEST" in option_codes
    assert options[0]["code"] == "SKIP_HABIT"
    assert options[0]["task"] == "T06-EXTRA-3"


def test_ac1_minh_week_with_explicit_habits_prefers_habit_over_academic_tasks():
    """
    AC1 & Edge Case E2: When a week contains explicit HABIT tasks (category='HABIT', no deadline)
    and an academic overload occurs, `SKIP_HABIT` must target the explicit habit task first
    rather than graded academic assignments.
    """
    res_presets = client.get("/api/presets")
    assert res_presets.status_code == 200
    minh = res_presets.json()["presets"]["minh"]

    raw_tasks = minh["tasks"]["tasks"] if isinstance(minh["tasks"], dict) else minh["tasks"]
    tasks = list(raw_tasks)
    # Add an extra heavy Tuesday assignment to trigger a Tuesday capacity shortage
    tasks.append(
        {
            "task_id": "EXTRA_TUE_EXAM",
            "title": "Ôn thi Vấn đáp Cấu trúc Dữ liệu",
            "duration_min": 1500,
            "deadline_day": "Tuesday",
            "deadline_time": "23:59",
            "priority": 5,
            "category": "EXAM",
            "is_splittable": True,
            "min_chunk_min": 45,
        }
    )

    res_plan = client.post(
        "/api/plan",
        json={"commitments": minh["commitments"], "tasks": tasks, "algorithm": "EDF"},
    )
    assert res_plan.status_code == 200
    overload = res_plan.json().get("overload")
    assert overload is not None

    skip_opts = [o for o in overload.get("options", []) if o.get("code") == "SKIP_HABIT"]
    assert len(skip_opts) >= 1
    # Minh's explicit habits are LAUNDRY / GYM (priority 1, category HABIT)
    assert skip_opts[0]["task"] in ("LAUNDRY", "GYM", "TASK-08", "TASK-09")
    assert skip_opts[0]["category"] == "HABIT"


def test_ac2_preview_shorten_task_on_t06_achieves_100_percent_feasibility():
    """
    AC2: Calling POST /api/overload/preview with `SHORTEN_TASK` on Scenario T06
    reduces T06-EXTRA-3 by 105 minutes (510m -> 405m), places 3/3 tasks (100% deadline rate,
    0 hard violations), and marks the newly placed blocks as state='PROPOSED'.
    """
    sc = client.get("/api/scenarios/t06").json()

    res_preview = client.post(
        "/api/overload/preview",
        json={
            "commitments": sc["commitments"],
            "tasks": sc["tasks"],
            "algorithm": "EDF",
            "option_id": "O2",
            "option_code": "SHORTEN_TASK",
            "target_task_id": "T06-EXTRA-3",
        },
    )
    assert res_preview.status_code == 200
    prev = res_preview.json()

    assert prev["status"] == "OK"
    assert prev["preview_mode"] is True
    assert prev["option_code"] == "SHORTEN_TASK"
    assert prev["option_applied"]["old_duration_min"] == 510
    assert prev["option_applied"]["new_duration_min"] == 405
    assert prev["option_applied"]["reduces_min"] == 105

    # Before vs After summary check
    assert prev["before_summary"]["tasks_placed"] == 2
    assert prev["before_summary"]["tasks_unplaced"] == 1
    assert prev["after_summary"]["tasks_placed"] == 3
    assert prev["after_summary"]["tasks_unplaced"] == 0
    assert prev["after_summary"]["deadline_satisfaction_rate"] == 100.0
    assert prev["after_summary"]["hard_constraint_violations"] == 0

    # Proposed blocks check
    proposed_blocks = [b for b in prev["blocks"] if b.get("state") == "PROPOSED"]
    assert len(proposed_blocks) >= 1
    assert any(b["task_id"] == "T06-EXTRA-3" for b in proposed_blocks)


def test_ac2_preview_skip_habit_on_t06_eliminates_overload():
    """
    AC2: Calling POST /api/overload/preview with `SKIP_HABIT` on Scenario T06
    removes/defers T06-EXTRA-3, leaving 2/2 core tasks placed with 100% deadline satisfaction.
    """
    sc = client.get("/api/scenarios/t06").json()

    res_preview = client.post(
        "/api/overload/preview",
        json={
            "commitments": sc["commitments"],
            "tasks": sc["tasks"],
            "algorithm": "EDF",
            "option_id": "O1",
            "option_code": "SKIP_HABIT",
            "target_task_id": "T06-EXTRA-3",
        },
    )
    assert res_preview.status_code == 200
    prev = res_preview.json()

    assert prev["option_code"] == "SKIP_HABIT"
    assert len(prev["resolved_tasks"]) == 2
    assert prev["after_summary"]["tasks_placed"] == 2
    assert prev["after_summary"]["tasks_unplaced"] == 0
    assert prev["after_summary"]["deadline_satisfaction_rate"] == 100.0
    assert prev["after_summary"]["hard_constraint_violations"] == 0
    assert all(b["state"] == "PROPOSED" for b in prev["blocks"])


def test_ac3_preview_allow_split_on_fragmented_unsplittable_task():
    """
    AC3: When an unsplittable 180-minute task faces fragmented 90-minute gaps before its deadline,
    `solve_schedule` reports FRAGMENTATION_FAILURE and suggests `ALLOW_SPLIT`.
    Previewing `ALLOW_SPLIT` splits the task into 90m+90m chunks with state='PROPOSED' and 100% placement.
    """
    sc = client.get("/api/scenarios/t03").json()
    # Keep only the unsplittable 180m task so 270m total free time (three 90m gaps) is available before Mon 21:00
    unsplittable_only = [t for t in sc["tasks"] if t["task_id"] == "T03-UNSPLITTABLE"]

    res_plan = client.post(
        "/api/plan",
        json={"commitments": sc["commitments"], "tasks": unsplittable_only, "algorithm": "EDF"},
    )
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    assert plan_data["status"] == "NO_SCHEDULE_FOUND"
    overload = plan_data["overload"]
    assert overload["error_type"] == "FRAGMENTATION_FAILURE"
    option_codes = {o["code"] for o in overload["options"]}
    assert "ALLOW_SPLIT" in option_codes

    res_preview = client.post(
        "/api/overload/preview",
        json={
            "commitments": sc["commitments"],
            "tasks": unsplittable_only,
            "algorithm": "EDF",
            "option_code": "ALLOW_SPLIT",
            "target_task_id": "T03-UNSPLITTABLE",
        },
    )
    assert res_preview.status_code == 200
    prev = res_preview.json()
    assert prev["after_summary"]["tasks_placed"] == 1
    assert prev["after_summary"]["tasks_unplaced"] == 0
    assert prev["after_summary"]["deadline_satisfaction_rate"] == 100.0
    assert prev["after_summary"]["hard_constraint_violations"] == 0
    assert len(prev["blocks"]) == 2
    assert all(b["state"] == "PROPOSED" for b in prev["blocks"])


def test_ac3_preview_postpone_lowest_on_t03_and_t06():
    """
    AC3: Previewing `POSTPONE_LOWEST` on both T03 and T06 defers the bottleneck task's deadline
    to Sunday 23:59 and resolves the schedule to 100% deadline satisfaction with 0 violations.
    """
    for sc_id, target_id in (("t03", "T03-UNSPLITTABLE"), ("t06", "T06-EXTRA-3")):
        sc = client.get(f"/api/scenarios/{sc_id}").json()
        res_preview = client.post(
            "/api/overload/preview",
            json={
                "commitments": sc["commitments"],
                "tasks": sc["tasks"],
                "algorithm": "EDF",
                "option_code": "POSTPONE_LOWEST",
                "target_task_id": target_id,
            },
        )
        assert res_preview.status_code == 200
        prev = res_preview.json()
        assert prev["after_summary"]["tasks_unplaced"] == 0
        assert prev["after_summary"]["deadline_satisfaction_rate"] == 100.0
        assert prev["after_summary"]["hard_constraint_violations"] == 0


def test_ac4_prerequisite_dag_protection_never_skips_or_postpones_prereq():
    """
    AC4 & Edge Case E3: A low-priority task (priority=1) that is a prerequisite (`depends_on`)
    for a high-priority task (priority=5) must NEVER be recommended for `SKIP_HABIT` or `POSTPONE_LOWEST`.
    """
    profile = CommitmentsProfile(
        student_id="DAG_SAFETY_TEST",
        planning_week_start="2026-11-02T00:00:00+07:00",
        now="2026-11-02T06:30:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    tasks = [
        Task(
            task_id="T_PREREQ_SETUP",
            title="Cài đặt môi trường Lab (P1 nhưng là tiên quyết của Đồ án)",
            duration_min=60,
            deadline_day="Monday",
            deadline_time="12:00",
            priority=1,
            category="HABIT",
        ),
        Task(
            task_id="T_CAPSTONE_CORE",
            title="Đồ án Cốt lõi (Phụ thuộc T_PREREQ_SETUP)",
            duration_min=960,
            deadline_day="Monday",
            deadline_time="23:59",
            priority=5,
            is_splittable=True,
            min_chunk_min=45,
            depends_on=["T_PREREQ_SETUP"],
        ),
        Task(
            task_id="T_INDEPENDENT_OPT",
            title="Đọc báo cáo phụ trợ (P2 không có task phụ thuộc)",
            duration_min=180,
            deadline_day="Monday",
            deadline_time="23:59",
            priority=2,
            is_splittable=True,
            min_chunk_min=45,
        ),
    ]

    protected = OverloadTriageEngine.get_protected_prerequisite_ids(tasks)
    assert "T_PREREQ_SETUP" in protected

    out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    assert out.overload is not None
    for opt in out.overload.options:
        if opt["code"] in ("SKIP_HABIT", "POSTPONE_LOWEST"):
            assert opt["task"] != "T_PREREQ_SETUP", (
                f"Prerequisite task T_PREREQ_SETUP was unsafely suggested for {opt['code']}!"
            )


def test_ac5_statelessness_and_sleep_lock_immutability():
    """
    AC5 (INV-3 & INV-4): Calling `solve_schedule` and `preview_overload_resolution` must
    never mutate caller's `Task` instances in-place, and must preserve exact SLEEP and OCCUPIED slot counts.
    """
    sc = client.get("/api/scenarios/t06").json()
    profile = CommitmentsProfile.model_validate(sc["commitments"])
    caller_tasks = [Task.model_validate(t) for t in sc["tasks"]]
    original_snapshot = [(t.task_id, t.duration_min, t.deadline_day, t.is_splittable) for t in caller_tasks]

    before_out, _ = ScheduleController.solve_schedule(profile, caller_tasks, algorithm="EDF")
    preview_res = ScheduleController.preview_overload_resolution(
        profile=profile,
        tasks=caller_tasks,
        option_code="SHORTEN_TASK",
        target_task_id="T06-EXTRA-3",
        algorithm="EDF",
    )

    # Caller's task objects must remain 100% untouched (INV-3)
    after_snapshot = [(t.task_id, t.duration_min, t.deadline_day, t.is_splittable) for t in caller_tasks]
    assert after_snapshot == original_snapshot
    assert len(caller_tasks) == 3
    assert caller_tasks[2].duration_min == 510

    # SLEEP and OCCUPIED slot counts must remain strictly locked (INV-4)
    after_sched = preview_res["schedule"]
    assert after_sched.summary.sleep_slots == before_out.summary.sleep_slots
    assert after_sched.summary.occupied_slots == before_out.summary.occupied_slots
    assert after_sched.summary.hard_constraint_violations == 0


def test_ac6_determinism_3x_hash_and_fallback_contract():
    """
    AC6 & Edge Case E5:
      1. Running preview 3 times on the same overload option produces identical SHA-256 hashes.
      2. Calling POST /api/overload/preview with minimal `{option_id, schedule}` stub payload succeeds.
    """
    sc = client.get("/api/scenarios/t06").json()
    hashes = []
    for _ in range(3):
        res = client.post(
            "/api/overload/preview",
            json={
                "commitments": sc["commitments"],
                "tasks": sc["tasks"],
                "algorithm": "EDF",
                "option_code": "SHORTEN_TASK",
                "target_task_id": "T06-EXTRA-3",
            },
        )
        assert res.status_code == 200
        hashes.append(res.json()["schedule"]["determinism_hash"])
    assert len(set(hashes)) == 1

    # Minimal stub payload fallback check
    res_stub = client.post(
        "/api/overload/preview",
        json={
            "option_id": "O1",
            "schedule": {
                "blocks": [
                    {"block_id": "B1", "task_id": "T1", "state": "ACCEPTED"},
                ]
            },
        },
    )
    assert res_stub.status_code == 200
    stub_data = res_stub.json()
    assert stub_data["status"] == "OK"
    assert stub_data["preview_mode"] is True
    assert stub_data["blocks"][0]["state"] == "PROPOSED"
