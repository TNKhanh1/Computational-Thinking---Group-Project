"""
Comprehensive Regression & Sync Verification Tests for Algorithm Fixes A1–A12,
Human Behavioral Patterns 1–8, Hybrid M1 NL Parser, and Experience Rating (1–5).
"""

from fastapi.testclient import TestClient

from src.controller import ScheduleController
from src.grid_manager import TimeGridManager
from src.metrics import calculate_experience_rating
from src.models import (
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    PersonalHabit,
    ScheduleBlock,
    SleepSchedule,
    Task,
)
from src.nl_parser import parse_natural_language_task
from src.solvers.base_solver import BaseScheduler
from web.api import app

client = TestClient(app)


def _base_profile(**kwargs) -> CommitmentsProfile:
    defaults = dict(
        student_id="SYNC_TEST_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        now="2026-11-02T06:30:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    defaults.update(kwargs)
    return CommitmentsProfile(**defaults)


def test_a1_safe_chunk_splitting_respects_90m_max_and_remainder_45_90():
    """Fix A1 & Pattern 2: No chunk may exceed max_chunk_min (90m) — e.g. 105m -> 60m + 45m."""
    t = Task(
        task_id="T105",
        title="Lab 105m",
        duration_min=105,
        deadline_day="Wednesday",
        deadline_time="23:59",
        is_splittable=True,
        min_chunk_min=45,
        max_chunk_min=90,
        cognitive_load=3,
    )
    chunks = BaseScheduler.split_task_into_chunks(t)
    assert [c.duration_min for c in chunks] == [60, 45]
    assert all(45 <= c.duration_min <= 90 for c in chunks)


def test_a2_wspt_handles_zero_deadline_slot_without_false_infinity():
    """Fix A2: WSPT must treat deadline_slot == 0 properly (`if raw_d is not None`), not replace 0 with 999999."""
    p = _base_profile(now="2026-11-02T00:00:00+07:00")
    t0 = Task(
        task_id="T_ZERO_DL",
        title="Due Immediately",
        duration_min=60,
        deadline_day="Monday",
        deadline_time="00:00",
        priority=3,
    )
    t1 = Task(
        task_id="T_LATER",
        title="Due Friday",
        duration_min=60,
        deadline_day="Friday",
        deadline_time="23:59",
        priority=3,
    )
    out, _ = ScheduleController.solve_schedule(p, [t0, t1], algorithm="WSPT")
    placed_ids = {b.task_id for b in out.blocks}
    assert "T_ZERO_DL" not in placed_ids  # Monday 00:00 has 0 slots after 00:00, H4 prevents placing past deadline
    assert "T_LATER" in placed_ids
    assert out.summary.hard_constraint_violations == 0


def test_a3_lst_dynamic_free_slot_slack_respects_depends_on_dag():
    """Fix A3: GreedyLSTSolver uses dynamic free-slot slack and satisfies depends_on H5 cleanly."""
    p = _base_profile()
    tasks = [
        Task(task_id="A", title="Prereq A", duration_min=60, deadline_day="Tuesday", deadline_time="18:00", priority=3),
        Task(task_id="B", title="Child B", duration_min=90, deadline_day="Tuesday", deadline_time="18:00", priority=5, depends_on=["A"]),
    ]
    out, _ = ScheduleController.solve_schedule(p, tasks, algorithm="LST")
    assert out.summary.hard_constraint_violations == 0
    b_a = max(b.end_slot for b in out.blocks if b.task_id == "A")
    b_b = min(b.start_slot for b in out.blocks if b.task_id == "B")
    assert b_b >= b_a


def test_a4_pinned_blocks_capacity_check_no_double_counting_and_h4():
    """Fix A4: Pinned blocks avoid double counting capacity and reject illegal H4 deadline violations."""
    p = _base_profile()
    t = Task(task_id="T_PIN", title="Pinned Task", duration_min=120, deadline_day="Monday", deadline_time="12:00", priority=4, is_splittable=True, min_chunk_min=45)
    valid_pin = ScheduleBlock(
        block_id="T_PIN_P1",
        task_id="T_PIN",
        title="Pinned Task",
        day="Monday",
        start_time="08:00",
        end_time="09:00",
        start_slot=32,
        end_slot=36,
        duration_min=60,
        chunk_index=1,
        total_chunks=2,
        priority=4,
        state="PINNED",
    )
    out, _ = ScheduleController.solve_schedule(p, [t], algorithm="EDF", pinned_blocks=[valid_pin])
    assert out.summary.hard_constraint_violations == 0
    assert out.summary.tasks_placed == 1
    assert len(out.blocks) == 2

    bad_pin = valid_pin.model_copy(
        update={"start_slot": 56, "end_slot": 60, "start_time": "14:00", "end_time": "15:00"}, deep=True
    )
    out_bad, _ = ScheduleController.solve_schedule(p, [t], algorithm="EDF", pinned_blocks=[bad_pin])
    assert out_bad.summary.hard_constraint_violations == 0


def test_a5_backtracking_explores_multiple_candidates():
    """Fix A5: Backtracking samples multiple candidate slots and produces 0 violations with optimal objective."""
    p = _base_profile(focus_preference="EVENING")
    tasks = [
        Task(task_id="T1", title="Deep Essay", duration_min=90, deadline_day="Tuesday", deadline_time="23:59", priority=5, cognitive_load=3),
        Task(task_id="T2", title="Reading", duration_min=45, deadline_day="Tuesday", deadline_time="23:59", priority=2, cognitive_load=1),
    ]
    out, _ = ScheduleController.solve_schedule(p, tasks, algorithm="BACKTRACK")
    assert out.summary.hard_constraint_violations == 0
    assert out.summary.deadline_satisfaction_rate == 100.0


def test_a7_circular_dependency_never_triggers_h5_violation():
    """Fix A7: Circular dependencies (A->B->A) & missing prerequisites produce 0 H5 hard violations."""
    p = _base_profile()
    tasks = [
        Task(task_id="CYC_A", title="Cycle A", duration_min=60, deadline_day="Tuesday", deadline_time="18:00", depends_on=["CYC_B"]),
        Task(task_id="CYC_B", title="Cycle B", duration_min=60, deadline_day="Tuesday", deadline_time="18:00", depends_on=["CYC_A"]),
        Task(task_id="OK_T", title="Normal", duration_min=45, deadline_day="Tuesday", deadline_time="18:00"),
    ]
    out, _ = ScheduleController.solve_schedule(p, tasks, algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    placed = {b.task_id for b in out.blocks}
    assert "OK_T" in placed
    assert "CYC_A" not in placed and "CYC_B" not in placed


def test_a8_a11_sleep_6h_enforcement_and_overnight_fixed_event():
    """Fix A8 & A11 + Pattern 6: Sleep >= 6h enforced even if short sleep specified; overnight FixedEvent supported."""
    p = _base_profile(
        sleep_schedule=SleepSchedule(daily_start_time="01:00", daily_end_time="05:00", is_hard_lock=False),
        fixed_events=[
            FixedEvent(
                event_id="NIGHT_SHIFT",
                title="Ca trực tối",
                day_of_week="Friday",
                start_time="22:00",
                end_time="01:30",
            )
        ],
    )
    grid = TimeGridManager(672)
    grid.initialize_from_profile(p)
    counts = grid.get_slot_counts()
    # >= 6h * 4 slots * 7 days = 168 sleep slots enforced (actually auto-extended by 8 slots/day)
    assert counts["SLEEP"] >= 168
    assert len(grid.sleep_warnings) >= 1
    # Friday 22:00..23:59 (slots 472..480) and Saturday 00:00..01:30 (slots 480..486) blocked
    assert grid.grid[472] != "FREE"
    assert grid.grid[480] != "FREE"


def test_a10_auto_splittable_default_by_duration():
    """Fix A10: Unspecified `is_splittable` defaults to False when <= 45m and True when > 45m."""
    t_short = Task(task_id="TS", title="Quick Note", duration_min=45)
    t_long = Task(task_id="TL", title="Long Project", duration_min=120)
    t_explicit_false = Task(task_id="TEF", title="Single Focus 90m", duration_min=90, is_splittable=False)
    assert t_short.is_splittable is False
    assert t_long.is_splittable is True
    assert t_explicit_false.is_splittable is False


def test_a12_past_due_iso_deadline_rejected_instead_of_clamping_to_zero():
    """Fix A12: Task with ISO `due` strictly before planning_week_start is rejected as DEADLINE_IN_PAST."""
    p = _base_profile(planning_week_start="2026-11-02T00:00:00+07:00")
    t_past = Task(
        task_id="T_PAST",
        title="Expired Homework",
        duration_min=60,
        due="2026-11-01T23:00:00+07:00",
        priority=4,
    )
    out, _ = ScheduleController.solve_schedule(p, [t_past], algorithm="EDF")
    assert out.summary.tasks_placed == 0
    assert len(out.unplaced_tasks) == 1
    assert out.unplaced_tasks[0]["reason_code"] == "DEADLINE_IN_PAST"
    assert out.summary.hard_constraint_violations == 0


def test_pattern_5_dead_zone_rest_classification_and_scored_greedy():
    """Pattern 5 & Pattern 7: Gaps < 30m between classes become REST; SCORED_GREEDY prioritizes urgency*importance."""
    p = _base_profile(
        focus_preference="EVENING",
        fixed_events=[
            FixedEvent(event_id="C1", title="Class 1", day_of_week="Monday", start_time="08:00", end_time="09:45"),
            FixedEvent(event_id="C2", title="Class 2", day_of_week="Monday", start_time="10:00", end_time="12:00"),
        ],
    )
    t = Task(task_id="T_SG", title="Deep Algorithm Proof", duration_min=60, deadline_day="Tuesday", deadline_time="23:59", priority=5, cognitive_load=3)
    out, grid = ScheduleController.solve_schedule(p, [t], algorithm="SCORED_GREEDY")
    assert out.solver_used == "SCORED_GREEDY"
    assert out.summary.hard_constraint_violations == 0
    # 09:45–10:00 on Monday (slot 39) is a 15-min dead-zone between C1 and C2 -> REST:DEAD_ZONE
    assert str(grid.grid[39]).startswith("REST")
    assert out.summary.rest_slots >= 1
    assert out.summary.experience_rating >= 1.0


def test_experience_rating_and_personal_habits_and_early_extension_alert():
    """Slide 11, Slide 6, Slide 14: PersonalHabit expansion, Experience Rating 1–5, Early Extension Alert 24–48h."""
    p_light = _base_profile()
    g_light = TimeGridManager(672)
    g_light.initialize_from_profile(p_light)
    rating_low, lbl_low = calculate_experience_rating(g_light, [], [], p_light, unplaced_count=0, crunch_tier_used=0)

    # Simulate dense busy week with heavy load-3 mismatch & crunch tier
    p_heavy = _base_profile(
        focus_preference="EVENING",
        fixed_events=[
            FixedEvent(event_id="B1", title="Busy Day", day_of_week="ALL", start_time="09:00", end_time="20:00"),
        ],
    )
    g_heavy = TimeGridManager(672)
    g_heavy.initialize_from_profile(p_heavy)
    heavy_blocks = [
        ScheduleBlock(
            block_id=f"H_{i}",
            task_id=f"T_{i}",
            title=f"Heavy {i}",
            day="Monday",
            start_time="06:30",
            end_time="08:30",
            start_slot=26 + i * 96,
            end_slot=34 + i * 96,
            duration_min=120,
            priority=5,
            cognitive_load=3,
        )
        for i in range(5)
    ]
    rating_high, lbl_high = calculate_experience_rating(
        g_heavy, heavy_blocks, [], p_heavy, unplaced_count=3, crunch_tier_used=1
    )
    assert 1.0 <= rating_low < rating_high <= 5.0
    assert "Comfortable" in lbl_low or "Manageable" in lbl_low
    assert any(k in lbl_high for k in ("Moderate", "Stressful", "Exhausting"))

    p = _base_profile(
        now="2026-11-02T08:00:00+07:00",
        personal_habits=[PersonalHabit(habit_id="H_GYM", name="Gym", duration_min=60, frequency_per_week=2)],
        fixed_events=[
            FixedEvent(event_id="BUSY", title="Full Day BootCamp", day_of_week="Monday", start_time="08:00", end_time="23:00"),
            FixedEvent(event_id="BUSY2", title="Full Day BootCamp 2", day_of_week="Tuesday", start_time="06:30", end_time="23:00"),
        ],
    )
    t_alert = Task(
        task_id="DUE_TUE",
        title="Báo cáo sắp hết hạn",
        duration_min=180,
        deadline_day="Tuesday",
        deadline_time="23:59",
        priority=5,
        is_splittable=True,
    )
    out, _ = ScheduleController.solve_schedule(p, [t_alert], algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    assert len(out.summary.early_extension_alerts) >= 1
    assert out.summary.early_extension_alerts[0]["task_id"] == "DUE_TUE"


def test_a6_a9_local_repair_pin_guard_and_overrun_stability():
    """Fix A6 & A9: LocalRepair respects PINNED blocks & preserves >= 90% stability on local overrun."""
    p = _base_profile()
    tasks = [
        Task(task_id="T1", title="Task 1", duration_min=60, deadline_day="Monday", deadline_time="23:59", priority=5),
        Task(task_id="T2", title="Task 2", duration_min=60, deadline_day="Wednesday", deadline_time="23:59", priority=3),
        Task(task_id="T3", title="Task 3", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=3),
        Task(task_id="T4", title="Task 4", duration_min=60, deadline_day="Saturday", deadline_time="23:59", priority=2),
    ]
    init, _ = ScheduleController.solve_schedule(p, tasks, algorithm="EDF")
    res = ScheduleController.handle_task_overrun(
        profile=p, tasks=tasks, task_id="T1", extra_minutes=30, algorithm="EDF"
    )
    assert res["after_schedule"].summary.hard_constraint_violations == 0
    assert res["after_schedule"].summary.deadline_satisfaction_rate == 100.0
    assert res["stability_score"] >= 90.0

    # Fix A6 #1 Pin Guard: directly hit PINNED block emits Pin Guard warning / PIN_CONFLICT rather than silent move,
    # while non-hit PINNED blocks stay untouched at their original slot.
    t2_block = next(b for b in init.blocks if b.task_id == "T2")
    t3_block = next(b for b in init.blocks if b.task_id == "T3")
    pinned_init = init.model_copy(deep=True)
    for b in pinned_init.blocks:
        if b.block_id in (t2_block.block_id, t3_block.block_id):
            b.state = "PINNED"
    dis = DisruptionEvent(
        event_id="DIS_PIN",
        title="Họp đột xuất",
        day_of_week=t2_block.day,
        start_time=t2_block.start_time,
        end_time=t2_block.end_time,
    )
    from src.solvers.local_repair import LocalRepairEngine
    rep = LocalRepairEngine.repair_disruption(p, tasks, pinned_init, dis, mode="LOCAL_INSERTION")
    after_t3 = next((b for b in rep.schedule.blocks if b.block_id == t3_block.block_id), None)
    assert after_t3 is not None and after_t3.start_slot == t3_block.start_slot
    assert any(u.get("reason_code") == "PIN_CONFLICT" and u.get("task_id") == "T2" for u in rep.schedule.unplaced_tasks)
    assert any("Pin Guard" in w or "PINNED" in w for w in rep.schedule.warnings)


def test_hybrid_m1_nl_parser_no_hardcoded_wednesday_and_checkin_endpoint():
    """M1 Hybrid Parser EN/VI + API `/api/tasks/natural-add` & `/api/tasks/complete`."""
    res_vi = parse_natural_language_task("Ôn thi Giải tích 2 tiếng trước 17h thứ 6 #deep", now="2026-11-02T08:00:00+07:00")
    d = res_vi["draft"]
    assert d["deadline_day"] == "Friday"
    assert d["deadline_time"] == "17:00"
    assert d["duration_min"] == 120
    assert d["category"] == "EXAM"
    assert d["cognitive_load"] == 3
    assert d["priority"] == 5

    res_rel = parse_natural_language_task("Đọc tài liệu 45p ngày mai", now="2026-11-02T08:00:00+07:00")
    assert res_rel["draft"]["deadline_day"] == "Tuesday"
    assert res_rel["draft"]["duration_min"] == 45

    api_res = client.post(
        "/api/tasks/natural-add",
        json={"prompt": "Làm lab mạng máy tính 1h30 trước 18:30 thứ 3 #lab"},
    )
    assert api_res.status_code == 200
    assert api_res.json()["draft"]["deadline_day"] == "Tuesday"
    assert api_res.json()["draft"]["deadline_time"] == "18:30"
    assert api_res.json()["draft"]["duration_min"] == 90

    chk_res = client.post(
        "/api/tasks/complete",
        json={"task_id": "T1", "estimated_min": 60, "actual_duration_min": 90, "completed": True},
    )
    assert chk_res.status_code == 200
    assert chk_res.json()["recommended_estimate_habit"] == "OFTEN"


def test_audit_fixes_validate_move_optout_buffer_and_overrun_pin_guard():
    """Verify validate-move `proposed_block`, per-task `NONE` buffer opt-out, SHORTEN_TASK <=90m cohesion, and overrun PIN guard."""
    p = _base_profile(buffer_mode="COGNITIVE_LOAD", alpha_light=1.20, alpha_heavy=1.35)
    t_optout = Task(
        task_id="OPT_RAW",
        title="Task No Buffer",
        duration_min=60,
        deadline_day="Wednesday",
        deadline_time="23:59",
        cognitive_load=3,
        buffer_mode="NONE",
    )
    t_buf = Task(
        task_id="OPT_BUF",
        title="Task With Buffer",
        duration_min=60,
        deadline_day="Wednesday",
        deadline_time="23:59",
        cognitive_load=3,
    )
    out, _ = ScheduleController.solve_schedule(p, [t_optout, t_buf], algorithm="SCORED_GREEDY")
    dur_by_task = {b.task_id: b.duration_min for b in out.blocks}
    assert dur_by_task["OPT_RAW"] == 60
    assert dur_by_task["OPT_BUF"] == 90

    # validate-move returns proposed_block with state='PINNED' and accepts current_blocks
    first_b = out.blocks[0]
    val_res = client.post(
        "/api/validate-move",
        json={
            "commitments": p.model_dump(mode="json"),
            "tasks": [t_optout.model_dump(mode="json"), t_buf.model_dump(mode="json")],
            "current_blocks": [b.model_dump(mode="json") for b in out.blocks],
            "block_id": first_b.block_id,
            "new_day": "Tuesday",
            "new_time": "14:00",
        },
    )
    assert val_res.status_code == 200
    vj = val_res.json()
    assert vj["ok"] is True
    assert vj["proposed_block"] is not None
    assert vj["proposed_block"]["day"] == "Tuesday"
    assert vj["proposed_block"]["start_time"] == "14:00"
    assert vj["proposed_block"]["state"] == "PINNED"

    # SHORTEN_TASK on <= 90m keeps task unshattered (max_chunk_min == 90)
    from src.overload_triage import OverloadTriageEngine
    t180 = Task(task_id="UNSPL", title="Exam", duration_min=180, deadline_day="Monday", is_splittable=False)
    shortened, _ = OverloadTriageEngine.apply_triage_option(
        p, [t180], option_code="SHORTEN_TASK", target_task_id="UNSPL", shortage_min=90
    )
    assert shortened[0].duration_min == 90
    assert shortened[0].max_chunk_min == 90

    # repair_overrun protects PINNED block immediately after overrun task
    from src.solvers.local_repair import LocalRepairEngine
    p_plain = _base_profile()
    ta = Task(task_id="A", title="Overrun A", duration_min=60, deadline_day="Tuesday", deadline_time="23:59", priority=5)
    tb = Task(task_id="B", title="Pinned B", duration_min=60, deadline_day="Tuesday", deadline_time="23:59", priority=3)
    init_s, _ = ScheduleController.solve_schedule(p_plain, [ta, tb], algorithm="EDF")
    b_pin = next(b for b in init_s.blocks if b.task_id == "B").model_copy(deep=True)
    a_blk = next(b for b in init_s.blocks if b.task_id == "A")
    # Pin B right where it stands, then double A so it would overlap B if Pin Guard failed
    for b in init_s.blocks:
        if b.block_id == b_pin.block_id:
            b.state = "PINNED"
    ta_over = ta.model_copy(update={"duration_min": 120}, deep=True)
    rep = LocalRepairEngine.repair_overrun(p_plain, [ta_over, tb], init_s, target_task_id="A")
    b_after = next(b for b in rep.schedule.blocks if b.block_id == b_pin.block_id)
    assert b_after.start_slot == b_pin.start_slot
    assert b_after.end_slot == b_pin.end_slot
    assert rep.schedule.summary.hard_constraint_violations == 0
    assert a_blk.block_id != b_pin.block_id
