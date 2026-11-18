"""Tests for OutputEvaluator Contrast Pairs, G1 supplementary checks, Circular SJL, Shock absorption, & Fox stability."""

from __future__ import annotations

from schedule_testing_system.evaluator import ScheduleEvaluator, build_contrast_pairs
from schedule_testing_system.schemas import EvaluationConfig, VerdictLabel
from schedule_testing_system.sut_adapter import (
    CommitmentsProfile,
    FixedEvent,
    ScheduleBlock,
    ScheduleOutput,
    ScheduleSummary,
    SleepSchedule,
    Task,
    day_time_to_slot,
    preprocess_tasks,
    run_solver_direct,
    slot_to_day_time,
)


def _mk_blk(task: Task, start_slot: int, dur_min: int, state: str = "ACCEPTED", chunk_idx: int = 1, total_chunks: int = 1) -> ScheduleBlock:
    end_slot = start_slot + dur_min // 15
    d_s, ts = slot_to_day_time(start_slot, is_end_time=False)
    _, te = slot_to_day_time(end_slot, is_end_time=True)
    return ScheduleBlock(
        block_id=f"{task.task_id}_P{chunk_idx}",
        task_id=task.task_id,
        title=task.title,
        day=d_s,
        start_time=ts,
        end_time=te,
        start_slot=start_slot,
        end_slot=end_slot,
        duration_min=dur_min,
        priority=task.priority,
        category=task.category,
        cognitive_load=task.cognitive_load,
        deadline_slot=task.resolve_deadline_slot(),
        chunk_index=chunk_idx,
        total_chunks=total_chunks,
        state=state,
    )


def test_contrast_pairs_self_test_passes():
    res = build_contrast_pairs()
    assert res.passed, f"Contrast pairs failed: {[a for a in res.assertions if not a.passed]}"
    assert res.golden_report.verdict == VerdictLabel.HIGH_PRODUCTIVITY
    assert res.feasible_bad_report.verdict == VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY
    assert res.invalid_report.verdict == VerdictLabel.INVALID
    # Full ICEE provenance check across P2.1 / P2.2 / P3.2 culprits
    assert "H1_P1" in res.feasible_bad_report.p2_cognitive_biology.missing_break_block_ids
    assert "H1_P1" in res.feasible_bad_report.p3_sustainable_pacing.overload_heavy_block_ids
    assert any(c.pillar == "P2.2" and "H1_P1" in c.block_ids for c in res.feasible_bad_report.d1_icee_critiques)


def test_g1_supplementary_catches_start_after_before_now_and_pin_loss():
    profile = CommitmentsProfile(
        now="Monday 10:00",
        buffer_mode="HABIT",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
    )
    tasks = [
        Task(task_id="T_SA", title="Delayed Release", duration_min=60, deadline_day="Tuesday", start_after="Monday 14:00"),
        Task(task_id="T_PIN", title="Pinned Anchor", duration_min=60, deadline_day="Tuesday"),
    ]
    prep = preprocess_tasks(profile, tasks)
    t_sa, t_pin = prep[0], prep[1]
    pin_in = [_mk_blk(t_pin, day_time_to_slot("Monday", "16:00"), 60, state="PINNED")]

    # Violate start_after (starts 08:00 < 14:00), violate now_slot (08:00 < 10:00), and move T_PIN to 18:00!
    bad_blocks = [
        _mk_blk(t_sa, day_time_to_slot("Monday", "08:00"), 60),
        _mk_blk(t_pin, day_time_to_slot("Monday", "18:00"), 60, state="ACCEPTED"),
    ]
    out = ScheduleOutput(
        status="SUCCESS",
        solver_used="MANUAL_TEST",
        execution_time_ms=1.0,
        summary=ScheduleSummary(total_tasks_requested=2, tasks_placed=2, tasks_unplaced=0),
        blocks=bad_blocks,
    )
    rep = ScheduleEvaluator.evaluate(profile, tasks, out, input_pinned_blocks=pin_in)
    assert rep.verdict == VerdictLabel.INVALID
    assert rep.gates.g1_start_after_violations == 1
    assert rep.gates.g1_before_now_violations == 1
    assert rep.gates.g1_pin_integrity_violations == 1


def test_p2_3_circular_sjl_handles_midnight_wrap_and_single_group_na():
    # Sleep 02:00-08:00 (midpoint 05:00 = slot 20). Study sessions around midnight 23:30-00:30 wrap smoothly!
    profile = CommitmentsProfile(
        focus_preference="EVENING",
        sleep_schedule=SleepSchedule(daily_start_time="02:00", daily_end_time="08:00"),
        fixed_events=[
            FixedEvent(event_id="C1", title="Evening Lecture", day_of_week="Monday", start_time="23:30", end_time="23:59", category="ACADEMIC_CLASS"),
        ],
    )
    tasks = [
        Task(task_id="NIGHT1", title="Midnight Study", duration_min=45, deadline_day="Wednesday", cognitive_load=3),
    ]
    prep = preprocess_tasks(profile, tasks)
    # Place NIGHT1 on Tuesday 23:45 -> Wednesday 00:30 (across calendar midnight!)
    s0 = day_time_to_slot("Tuesday", "23:45")
    blk = _mk_blk(prep[0], s0, 45)
    out = ScheduleOutput(
        status="SUCCESS",
        solver_used="MIDNIGHT_TEST",
        execution_time_ms=1.0,
        summary=ScheduleSummary(total_tasks_requested=1, tasks_placed=1, tasks_unplaced=0),
        blocks=[blk],
    )
    rep = ScheduleEvaluator.evaluate(profile, tasks, out)
    # Class day Mon 23:45 (~23.75h -> unwrapped ~1125m past 05:00) vs Non-class Tue 23:45-00:30 (~15m later, NOT 1200m!)
    assert rep.p2_cognitive_biology.sjl_minutes is not None
    assert rep.p2_cognitive_biology.sjl_minutes <= 60.0

    # Without any classes -> non_class only -> SJL must return None ("N/A")
    prof_no_class = profile.model_copy(update={"fixed_events": []})
    rep_na = ScheduleEvaluator.evaluate(prof_no_class, tasks, out)
    assert rep_na.p2_cognitive_biology.sjl_minutes is None
    assert rep_na.p2_cognitive_biology.sjl_direction == "N/A"


def test_p4_1_shock_measures_raw_duration_buffer_absorption():
    # Compare COGNITIVE_LOAD buffered (alpha_heavy=1.35 -> 60m raw becomes 90m planned) vs NONE unbuffered (60m packed right before fixed event)
    prof_buf = CommitmentsProfile(
        buffer_mode="COGNITIVE_LOAD",
        sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00"),
        fixed_events=[
            FixedEvent(event_id="HARD_WALL", title="Class", day_of_week="Monday", start_time="10:30", end_time="12:00"),
        ],
    )
    task = Task(task_id="T_SHK", title="Deep Task", duration_min=60, deadline_day="Monday", deadline_time="10:30", priority=5, cognitive_load=3)

    # Scheduled starting at 09:00 -> ends at 10:30 (90m block); raw 60m + 25% = 75m fits inside 90m -> SURVIVES!
    prep_buf = preprocess_tasks(prof_buf, [task])
    out_buf = ScheduleOutput(
        status="SUCCESS",
        solver_used="BUF",
        execution_time_ms=1.0,
        summary=ScheduleSummary(total_tasks_requested=1, tasks_placed=1, tasks_unplaced=0),
        blocks=[_mk_blk(prep_buf[0], day_time_to_slot("Monday", "09:00"), 90)],
    )
    rep_buf = ScheduleEvaluator.evaluate(prof_buf, [task], out_buf)
    assert rep_buf.p4_robustness_stability.true_buffer_task_pct == 100.0
    assert rep_buf.p4_robustness_stability.shock_results[0].survived_priority_pct == 100.0
    assert rep_buf.p4_robustness_stability.shock_results[0].absorbed_by_internal_buffer_count == 1

    # Unbuffered ending right at 10:30 wall (09:30-10:30, 60m) -> +25% hits 10:45 (HARD_WALL & deadline!) -> FAILS!
    prof_nobuf = prof_buf.model_copy(update={"buffer_mode": "HABIT", "estimate_habit": "RARELY"})
    prep_nobuf = preprocess_tasks(prof_nobuf, [task])
    out_nobuf = ScheduleOutput(
        status="SUCCESS",
        solver_used="NOBUF",
        execution_time_ms=1.0,
        summary=ScheduleSummary(total_tasks_requested=1, tasks_placed=1, tasks_unplaced=0),
        blocks=[_mk_blk(prep_nobuf[0], day_time_to_slot("Monday", "09:30"), 60)],
    )
    rep_nobuf = ScheduleEvaluator.evaluate(prof_nobuf, [task], out_nobuf)
    assert rep_nobuf.p4_robustness_stability.true_buffer_task_pct == 0.0
    assert rep_nobuf.p4_robustness_stability.shock_results[0].survived_priority_pct == 0.0


def test_p1_2_justifies_strategic_idling_and_flags_true_procrastination():
    profile = CommitmentsProfile(
        now="Monday 08:00",
        focus_preference="MORNING",  # Morning Peak = 3, Afternoon = 2, Evening = 1
        buffer_mode="HABIT",
        sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00"),
    )
    t_wide = Task(task_id="WIDE", title="Wide Window Essay", duration_min=60, deadline_day="Wednesday", deadline_time="22:00", priority=4, cognitive_load=3)
    prep = preprocess_tasks(profile, [t_wide])

    # Unjustified procrastination: Monday & Tuesday mornings (energy=3) were completely FREE, yet placed at Wednesday 19:00 (energy=1, <10h before Wed 22:00)!
    bad_late = ScheduleOutput(
        status="SUCCESS",
        solver_used="LATE",
        execution_time_ms=1.0,
        summary=ScheduleSummary(total_tasks_requested=1, tasks_placed=1, tasks_unplaced=0),
        blocks=[_mk_blk(prep[0], day_time_to_slot("Wednesday", "19:00"), 60)],
    )
    rep_bad = ScheduleEvaluator.evaluate(profile, [t_wide], bad_late)
    assert rep_bad.p1_value_timeliness.unjustified_last_10h_crowding_pct == 100.0
    assert "WIDE" in rep_bad.p1_value_timeliness.unjustified_last_10h_task_ids

    # Good early start: placed Monday 08:00 (energy=3) -> 0% crowding
    good_early = ScheduleOutput(
        status="SUCCESS",
        solver_used="EARLY",
        execution_time_ms=1.0,
        summary=ScheduleSummary(total_tasks_requested=1, tasks_placed=1, tasks_unplaced=0),
        blocks=[_mk_blk(prep[0], day_time_to_slot("Monday", "08:00"), 60)],
    )
    rep_good = ScheduleEvaluator.evaluate(profile, [t_wide], good_early)
    assert rep_good.p1_value_timeliness.unjustified_last_10h_crowding_pct == 0.0

