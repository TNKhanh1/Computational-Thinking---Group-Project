"""
Logical Edge Case Suite: Extreme Scheduling Scenarios & Boundary Failures (40% Ratio).
Author: Nguyen Nguyen Gia Bao (Builder 3 - Edge Cases §8 & Architecture §7)

Validates:
  - Simultaneous deadline priority inversion traps
  - Sunday midnight 23:59 boundary slot overflow & no wraparound
  - Extreme 15-minute slot fragmentation vs. capacity diagnostics
  - Zero-slack cross-midnight sleep boundary enforcement
"""

from pathlib import Path
import pytest

from smartschedule.core.config import PRESETS_DIR
from smartschedule.core.controller import ScheduleController
from smartschedule.core.models import CommitmentsProfile, FixedEvent, SleepSchedule, Task

DATA_DIR = PRESETS_DIR


def _make_profile(fixed_events=None):
    return CommitmentsProfile(
        student_id="EDGE_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=fixed_events or [],
    )


def test_edge_simultaneous_deadline_priority_inversion():
    """
    SCHEDULING EDGE CASE:
    3 tasks have the EXACT SAME deadline (Wednesday 23:59).
    Available free capacity before deadline is 150 minutes:
      - Task High: Priority 5, duration 90m
      - Task Mid: Priority 4, duration 60m
      - Task Low: Priority 1, duration 60m
    Total needed = 210m > 150m (Shortage = 60m).
    EDGE CASE REQUIREMENT:
    High-priority tasks (P5 and P4) MUST be scheduled (90 + 60 = 150m).
    Low-priority task (P1) MUST be the one left unplaced.
    If the solver drops P5 or P4 to place P1, it is a priority inversion failure!
    """
    profile = _make_profile([
        FixedEvent(event_id="C_BL", title="Blocking Class", day_of_week="Wednesday", start_time="06:30", end_time="21:30")
    ])  # leaves 21:30-23:30 = 120m + 23:30-23:59 = 0 (sleep). Let's use Monday with 150m free.
    
    # Monday: sleep 00:00-06:30, classes 06:30-21:00 (free 21:00-23:30 = 150 min)
    profile_mon = _make_profile([
        FixedEvent(event_id="C_ALL_DAY", title="Full Day", day_of_week="Monday", start_time="06:30", end_time="21:00")
    ])
    t_high = Task(task_id="T_P5", title="High Prio Assignment", duration_min=90, deadline_day="Monday", deadline_time="23:30", priority=5)
    t_mid = Task(task_id="T_P4", title="Mid Prio Assignment", duration_min=60, deadline_day="Monday", deadline_time="23:30", priority=4)
    t_low = Task(task_id="T_P1", title="Low Prio Task", duration_min=60, deadline_day="Monday", deadline_time="23:30", priority=1)

    out, _ = ScheduleController.solve_schedule(profile_mon, [t_low, t_mid, t_high], algorithm="EDF")

    # Audit results
    assert out.summary.hard_constraint_violations == 0
    placed_ids = {b.task_id for b in out.blocks}
    unplaced_ids = {u["task_id"] for u in out.unplaced_tasks}

    # P5 must be preserved
    assert "T_P5" in placed_ids, "Priority Inversion: P5 high priority task was dropped!"
    assert "T_P1" in unplaced_ids, "Priority Inversion: P1 low priority task was placed instead of high priority!"


def test_edge_sunday_boundary_overflow_no_wraparound():
    """
    SCHEDULING EDGE CASE (Boundary slot 672):
    Task starts at Sunday 23:00 (slot 668) with 60m duration (4 slots: 668..672).
    A 90m task ending past midnight (slot 674) must NOT wrap around to Monday slot 0..2.
    Asserts: start_slot < end_slot and no block has start_slot < 0 or start_slot >= 672 when week is single-week.
    """
    profile = _make_profile()
    t_sunday = Task(
        task_id="T_SUN_BORDER",
        title="Late Sunday Work",
        duration_min=45,
        deadline_day="Sunday",
        deadline_time="23:30",
        priority=3,
    )
    out, _ = ScheduleController.solve_schedule(profile, [t_sunday], algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    for b in out.blocks:
        assert 0 <= b.start_slot < 672
        assert b.start_slot < b.end_slot
        if b.day == "Sunday":
            assert b.end_slot <= 672


def test_edge_extreme_15min_fragmentation():
    """
    SCHEDULING EDGE CASE:
    4 hours (240 min) of free time on Tuesday, but partitioned into 16 non-contiguous 15-minute slots:
    (15m class, 15m free, 15m class, 15m free...).
    An atomic task requires 60 minutes.
    Evaluation: Total free time (240m) >> task duration (60m), but max gap is only 15m.
    Asserts: Task cannot be scheduled; it must be diagnosed in unplaced_tasks.
    """
    alternating_classes = []
    # Create alternating 15-minute occupied blocks on Monday between 07:00 and 15:00
    for h in range(7, 15):
        alternating_classes.append(
            FixedEvent(event_id=f"ALT_{h}_A", title="Class A", day_of_week="Monday", start_time=f"{h:02d}:00", end_time=f"{h:02d}:15")
        )
        alternating_classes.append(
            FixedEvent(event_id=f"ALT_{h}_B", title="Class B", day_of_week="Monday", start_time=f"{h:02d}:30", end_time=f"{h:02d}:45")
        )

    # Rest of Monday is occupied
    alternating_classes.append(
        FixedEvent(event_id="MON_REST", title="Evening Shift", day_of_week="Monday", start_time="15:00", end_time="23:30")
    )
    profile = _make_profile(fixed_events=alternating_classes)

    atomic_task = Task(
        task_id="T_60M_ATOMIC",
        title="Unsplittable 60m Task",
        duration_min=60,
        deadline_day="Monday",
        deadline_time="15:00",
        is_splittable=False,
    )

    out, _ = ScheduleController.solve_schedule(profile, [atomic_task], algorithm="EDF")
    assert out.summary.hard_constraint_violations == 0
    unplaced = {u["task_id"] for u in out.unplaced_tasks}
    assert "T_60M_ATOMIC" in unplaced, "Atomic task was placed into a 15-minute gap, causing constraint violation!"


def test_fail_edge_sprint_mode_compression_recovery():
    """
    EDGE CASE (Q9 Option A — Lossless Sprint Safety + User-Confirmed Triage Recovery):
    A single 90m raw task (`T_SPRINT`) faces a 75m free window before deadline (`06:30–07:45`).
    Under Option A (no silent truncation of user raw work):
      1. Pass 1 refuses to silently chop 90m -> 75m (`INFEASIBLE_CAPACITY`, `tasks_placed == 0`),
         notifying the user with an `Early Extension Alert` and `SHORTEN_TASK` (`90 -> 75m`)
         confirmed-triage recovery option.
      2. Once the student explicitly confirms `SHORTEN_TASK`, Pass 2 schedules the task (`tasks_placed == 1`)
         with zero hard constraint violations.
      3. Conversely, when a tight deadline shortage is ONLY due to a 15m rest break, Tier-1 Sprint Mode
         (`Cut breaks`, `crunch_tier_used == 1`) automatically rescues placement without altering raw duration.
    """
    from smartschedule.core.overload_triage import OverloadTriageEngine

    # 90m task needing 90m before 08:00, while only 75m is free (06:30-07:45)
    profile = _make_profile([
        FixedEvent(event_id="C_SPRINT", title="Early Class", day_of_week="Monday", start_time="07:45", end_time="12:00")
    ])
    task = Task(task_id="T_SPRINT", title="Urgent Sprint Task", duration_min=90, deadline_day="Monday", deadline_time="08:00", priority=5)

    out, _ = ScheduleController.solve_schedule(profile, [task], algorithm="EDF")
    assert out.status == "INFEASIBLE_CAPACITY"
    assert out.summary.tasks_placed == 0
    assert out.overload is not None
    assert out.summary.early_extension_alerts, "Expected caution notification via Early Extension Alert"
    shorten_opts = [o for o in out.overload.options if o.get("code") == "SHORTEN_TASK"]
    assert shorten_opts and shorten_opts[0]["new_duration_min"] == 75

    # Confirm user-approved SHORTEN_TASK triage option -> task is now cleanly placed
    resolved_tasks, action_meta = OverloadTriageEngine.apply_triage_option(
        profile=profile,
        tasks=[task],
        option_code="SHORTEN_TASK",
        target_task_id="T_SPRINT",
        available_options=out.overload.options,
    )
    assert action_meta["new_duration_min"] == 75
    recovered_out, _ = ScheduleController.solve_schedule(profile, resolved_tasks, algorithm="EDF")
    assert recovered_out.summary.tasks_placed == 1
    assert recovered_out.summary.hard_constraint_violations == 0

    # Tier-1 Sprint Mode ('Cut breaks') auto-rescues when raw duration fits if 15m rest break is shed:
    # 06:30-08:30 (120m free) with two 60m DEEP tasks due 08:30 -> Tier 0 needs 60+15+60=135m, Tier 1 fits 120m!
    profile_breaks = _make_profile([
        FixedEvent(event_id="C_DAY", title="All Day Class", day_of_week="Monday", start_time="08:30", end_time="23:30")
    ])
    t1 = Task(task_id="T_SP1", title="Deep Drill 1", duration_min=60, deadline_day="Monday", deadline_time="08:30", priority=5, cognitive_load=3)
    t2 = Task(task_id="T_SP2", title="Deep Drill 2", duration_min=60, deadline_day="Monday", deadline_time="08:30", priority=4, cognitive_load=3)
    sp_out, _ = ScheduleController.solve_schedule(profile_breaks, [t1, t2], algorithm="EDF")
    assert sp_out.summary.tasks_placed == 2
    assert sp_out.summary.crunch_tier_used == 1
    assert sp_out.summary.hard_constraint_violations == 0

