"""Verification tests for v2.1 Human-Centric Evaluation Rules & Procedural Infinite FuzzGenerator."""

from __future__ import annotations

import pytest

from Testing_System.evaluator import ScheduleEvaluator
from Testing_System.generator import FuzzGenerator, GeneratedCaseBundle
from Testing_System.runner import run_fuzz_case, run_single_regime_case
from Testing_System.runner.project_runner import execute_project_direct
from Testing_System.schemas import GeneratedTestMetadata, RegimeName, VerdictLabel
from Testing_System.sut_adapter import (
    BaseScheduler,
    CommitmentsProfile,
    FixedEvent,
    PersonalHabit,
    ScheduleBlock,
    ScheduleOutput,
    ScheduleSummary,
    SleepSchedule,
    Task,
    day_time_to_slot,
    preprocess_tasks,
    slot_to_day_time,
)


def _meals() -> list[FixedEvent]:
    return [
        FixedEvent(event_id="M1", title="Sáng", day_of_week="ALL", start_time="07:00", end_time="07:30", category="MEAL"),
        FixedEvent(event_id="M2", title="Trưa", day_of_week="ALL", start_time="12:00", end_time="12:45", category="MEAL"),
        FixedEvent(event_id="M3", title="Tối", day_of_week="ALL", start_time="18:30", end_time="19:15", category="MEAL"),
    ]


def _blk(
    tid: str,
    day: str,
    st: str,
    en: str,
    prio: int = 4,
    load: int = 2,
    cat: str = "ASSIGNMENT",
    idx: int = 1,
    tot: int = 1,
    dday: str = "Sunday",
) -> ScheduleBlock:
    s0 = day_time_to_slot(day, st, is_end_or_deadline=False)
    s1 = day_time_to_slot(day, en, is_end_or_deadline=True)
    return ScheduleBlock(
        block_id=f"{tid}_P{idx}",
        task_id=tid,
        title=tid,
        day=day,
        start_time=st,
        end_time=en,
        start_slot=s0,
        end_slot=s1,
        duration_min=(s1 - s0) * 15,
        priority=prio,
        category=cat,
        cognitive_load=load,
        deadline_slot=day_time_to_slot(dday, "23:59", is_end_or_deadline=True),
        chunk_index=idx,
        total_chunks=tot,
        state="ACCEPTED",
    )


def _out(blks: list[ScheduleBlock], unplaced: list[dict], req: int) -> ScheduleOutput:
    return ScheduleOutput(
        status="SUCCESS",
        solver_used="ADV_TEST",
        execution_time_ms=5.0,
        blocks=blks,
        unplaced_tasks=unplaced,
        summary=ScheduleSummary(
            total_tasks_requested=req,
            tasks_placed=len({b.task_id for b in blks}),
            tasks_unplaced=len(unplaced),
        ),
    )


def test_v21_eliminates_regime3_paradox_high_always_beats_low():
    for seed in range(1, 6):
        res = run_single_regime_case(RegimeName.CIRCADIAN_SJL_AND_RECOVERY, seed=seed, use_http_e2e=False)
        top1 = res.cross_solver_ranking[0]
        assert top1.verdict == VerdictLabel.HIGH_PRODUCTIVITY, (
            f"seed={seed}: expected HIGH_PRODUCTIVITY at Rank #1, got {top1.solver_name} ({top1.verdict})"
        )
        assert top1.solver_name == "SCORED_GREEDY"


def test_v21_blocks_adversarial_hacks_while_passing_golden_schedule():
    base_prof = CommitmentsProfile(
        student_id="ADV",
        focus_preference="MORNING",
        buffer_mode="COGNITIVE_LOAD",
        horizon_days=7,
        sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00", is_hard_lock=True),
        fixed_events=_meals()
        + [
            FixedEvent(
                event_id="CL",
                title="246",
                day_of_week=["Monday", "Wednesday", "Friday"],
                start_time="08:00",
                end_time="11:30",
                category="ACADEMIC_CLASS",
            )
        ],
        personal_habits=[
            PersonalHabit(
                habit_id="H1",
                name="Gym",
                duration_min=30,
                frequency_per_week=3,
                preferred_window="AFTERNOON",
                cognitive_load=1,
            )
        ],
    )
    prof_no_hab = base_prof.model_copy(update={"personal_habits": []})

    # 1. Hack: Drop 100% HABIT on loose week
    t_hab = [
        Task(task_id="T1", title="T1", duration_min=60, deadline_day="Thursday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM", preferred_window="MORNING"),
        Task(task_id="T2", title="T2", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT", preferred_window="MORNING"),
    ]
    prep_h = preprocess_tasks(base_prof, t_hab)
    unp_h = [{"task_id": t.task_id, "reason": "dropped"} for t in prep_h if t.resolve_deadline_slot() is None]
    rep_drop_hab = ScheduleEvaluator.evaluate(
        base_prof,
        t_hab,
        _out([_blk("T1", "Tuesday", "08:00", "09:30", 5, 3, "EXAM", dday="Thursday"), _blk("T2", "Thursday", "08:00", "09:30", 5, 3, "PROJECT", dday="Friday")], unp_h, 5),
    )
    assert rep_drop_hab.verdict == VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY

    # 2. Hack: 5h nonstop load=2 (300m streak)
    t_stk = [Task(task_id=f"L{i}", title=f"L{i}", duration_min=d, deadline_day="Friday", deadline_time="23:59", priority=4, cognitive_load=2, category="ASSIGNMENT") for i, d in [(1, 75), (2, 75), (3, 75), (4, 25)]]
    rep_stk = ScheduleEvaluator.evaluate(
        prof_no_hab,
        t_stk,
        _out(
            [
                _blk("L1", "Tuesday", "13:00", "14:30", 4, 2, dday="Friday"),
                _blk("L2", "Tuesday", "14:30", "16:00", 4, 2, dday="Friday"),
                _blk("L3", "Tuesday", "16:00", "17:30", 4, 2, dday="Friday"),
                _blk("L4", "Tuesday", "17:30", "18:00", 4, 2, dday="Friday"),
            ],
            [],
            4,
        ),
    )
    assert rep_stk.p2_cognitive_biology.max_multi_block_streak_l2_min == 300
    assert rep_stk.verdict == VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY

    # 3. Hack: MORNING student forced load=3 at night (energy=1)
    t_off = [
        Task(task_id="D1", title="D1", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM"),
        Task(task_id="D2", title="D2", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT"),
    ]
    rep_off = ScheduleEvaluator.evaluate(
        prof_no_hab,
        t_off,
        _out([_blk("D1", "Tuesday", "08:00", "09:30", 5, 3, "EXAM", dday="Friday"), _blk("D2", "Wednesday", "20:00", "21:30", 5, 3, "PROJECT", dday="Friday")], [], 2),
    )
    assert rep_off.p2_cognitive_biology.off_peak_heavy_mismatch_count == 1
    assert rep_off.verdict == VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY

    # 4. Hack: 5 rapid context switches
    t_ctx = [Task(task_id=f"C{i}", title=f"C{i}", duration_min=25, deadline_day="Friday", deadline_time="23:59", priority=3, cognitive_load=1, category=cat) for i, cat in [(1, "EXAM"), (2, "PROJECT"), (3, "ASSIGNMENT"), (4, "DEADLINE"), (5, "EXAM")]]
    rep_ctx = ScheduleEvaluator.evaluate(
        prof_no_hab,
        t_ctx,
        _out(
            [
                _blk("C1", "Tuesday", "08:00", "08:30", 3, 1, "EXAM", dday="Friday"),
                _blk("C2", "Tuesday", "08:45", "09:15", 3, 1, "PROJECT", dday="Friday"),
                _blk("C3", "Tuesday", "09:30", "10:00", 3, 1, "ASSIGNMENT", dday="Friday"),
                _blk("C4", "Tuesday", "10:15", "10:45", 3, 1, "DEADLINE", dday="Friday"),
                _blk("C5", "Tuesday", "11:00", "11:30", 3, 1, "EXAM", dday="Friday"),
            ],
            [],
            5,
        ),
    )
    assert rep_ctx.p3_sustainable_pacing.focus_context_switches == 4

    # 5. Hack: 0m post-class transition before load=3 twice
    prof_cls = prof_no_hab.model_copy(
        update={
            "fixed_events": _meals()
            + [FixedEvent(event_id="C", title="Lớp sáng", day_of_week=["Monday", "Wednesday"], start_time="08:00", end_time="11:30", category="ACADEMIC_CLASS")]
        }
    )
    t_pc = [
        Task(task_id="P1", title="P1", duration_min=20, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM"),
        Task(task_id="P2", title="P2", duration_min=20, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM"),
    ]
    rep_pc = ScheduleEvaluator.evaluate(
        prof_cls,
        t_pc,
        _out([_blk("P1", "Monday", "11:30", "12:00", 5, 3, "EXAM", dday="Friday"), _blk("P2", "Wednesday", "11:30", "12:00", 5, 3, "EXAM", dday="Friday")], [], 2),
    )
    assert rep_pc.p2_cognitive_biology.post_class_buffer_violations == 2
    assert rep_pc.verdict == VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY

    # 6. Golden Human Schedule passes HIGH_PRODUCTIVITY cleanly
    hab_ids = [t.task_id for t in prep_h if t.resolve_deadline_slot() is None]
    rep_gold = ScheduleEvaluator.evaluate(
        base_prof,
        t_hab,
        _out(
            [
                _blk("T1", "Tuesday", "08:30", "10:00", 5, 3, "EXAM", dday="Thursday"),
                _blk("T2", "Thursday", "08:30", "10:00", 5, 3, "PROJECT", dday="Friday"),
                _blk(hab_ids[0], "Monday", "15:00", "15:45", 3, 1, "HABIT", dday="Sunday"),
                _blk(hab_ids[1], "Wednesday", "15:00", "15:45", 3, 1, "HABIT", dday="Sunday"),
                _blk(hab_ids[2], "Friday", "15:00", "15:45", 3, 1, "HABIT", dday="Sunday"),
            ],
            [],
            5,
        ),
    )
    assert rep_gold.verdict == VerdictLabel.HIGH_PRODUCTIVITY


def test_v21_fairness_for_high_school_morning_and_uni_owl_students():
    hs_prof = CommitmentsProfile(
        student_id="HS1",
        focus_preference="MORNING",
        buffer_mode="COGNITIVE_LOAD",
        horizon_days=7,
        sleep_schedule=SleepSchedule(daily_start_time="22:30", daily_end_time="06:00", is_hard_lock=True),
        fixed_events=_meals()
        + [FixedEvent(event_id="HS", title="HS", day_of_week=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], start_time="07:30", end_time="11:30", category="ACADEMIC_CLASS")],
        personal_habits=[PersonalHabit(habit_id="GYM", name="Gym", duration_min=30, frequency_per_week=3, preferred_window="AFTERNOON", cognitive_load=1)],
    )
    hs_tasks = [
        Task(task_id="TOAN", title="Toán", duration_min=60, deadline_day="Thursday", deadline_time="22:00", priority=5, cognitive_load=3, category="EXAM", preferred_window="AFTERNOON"),
        Task(task_id="LY", title="Lý", duration_min=60, deadline_day="Friday", deadline_time="22:00", priority=4, cognitive_load=3, category="ASSIGNMENT", preferred_window="AFTERNOON"),
        Task(task_id="ANH", title="Anh", duration_min=45, deadline_day="Wednesday", deadline_time="22:00", priority=3, cognitive_load=2, category="ASSIGNMENT"),
    ]
    hs_bundle = GeneratedCaseBundle(
        profile=hs_prof,
        tasks=hs_tasks,
        pinned_blocks=[],
        metadata=GeneratedTestMetadata(seed=99, regime=RegimeName.LOOSE_FEASIBLE, chronotype="MORNING", horizon_days=7, planned_demand_slots=0, usable_free_slots=1, tightness_rho=0.0, task_count=3, habit_count=1, pinned_count=0),
    )
    hs_run = execute_project_direct(hs_bundle)
    hs_rep = ScheduleEvaluator.evaluate(hs_prof, hs_tasks, hs_run.solver_outputs["SCORED_GREEDY"])
    assert hs_rep.p2_cognitive_biology.achievable_heavy_peak_match_pct is None
    assert hs_rep.verdict == VerdictLabel.HIGH_PRODUCTIVITY

    owl_prof = CommitmentsProfile(
        student_id="OWL1",
        focus_preference="EVENING",
        buffer_mode="COGNITIVE_LOAD",
        horizon_days=7,
        sleep_schedule=SleepSchedule(daily_start_time="23:45", daily_end_time="07:00", is_hard_lock=True),
        fixed_events=_meals()
        + [
            FixedEvent(event_id="C1", title="246", day_of_week=["Monday", "Wednesday", "Friday"], start_time="08:00", end_time="11:30", category="ACADEMIC_CLASS"),
            FixedEvent(event_id="C2", title="Lab", day_of_week="Monday", start_time="13:30", end_time="16:00", category="ACADEMIC_CLASS"),
        ],
        personal_habits=[PersonalHabit(habit_id="RD", name="Read", duration_min=30, frequency_per_week=3, preferred_window="EVENING", cognitive_load=1)],
    )
    owl_tasks = [
        Task(task_id="P1", title="Code", duration_min=60, deadline_day="Thursday", deadline_time="23:30", priority=5, cognitive_load=3, category="PROJECT", preferred_window="EVENING"),
        Task(task_id="P2", title="Test", duration_min=60, deadline_day="Friday", deadline_time="23:30", priority=4, cognitive_load=3, category="PROJECT", depends_on=["P1"], preferred_window="EVENING"),
        Task(task_id="H1", title="Slide", duration_min=45, deadline_day="Wednesday", deadline_time="23:30", priority=3, cognitive_load=2, category="ASSIGNMENT"),
        Task(task_id="H2", title="Paper", duration_min=45, deadline_day="Saturday", deadline_time="23:30", priority=2, cognitive_load=2, category="ASSIGNMENT"),
    ]
    owl_bundle = GeneratedCaseBundle(
        profile=owl_prof,
        tasks=owl_tasks,
        pinned_blocks=[],
        metadata=GeneratedTestMetadata(seed=98, regime=RegimeName.LOOSE_FEASIBLE, chronotype="EVENING", horizon_days=7, planned_demand_slots=0, usable_free_slots=1, tightness_rho=0.0, task_count=4, habit_count=1, pinned_count=0),
    )
    owl_run = execute_project_direct(owl_bundle)
    rep_sg = ScheduleEvaluator.evaluate(owl_prof, owl_tasks, owl_run.solver_outputs["SCORED_GREEDY"])
    rep_edf = ScheduleEvaluator.evaluate(owl_prof, owl_tasks, owl_run.solver_outputs["EDF"])
    assert rep_sg.verdict == VerdictLabel.HIGH_PRODUCTIVITY
    assert rep_edf.p3_sustainable_pacing.max_daily_total_min > 600
    assert rep_edf.verdict == VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY


def test_fuzz_generator_determinism_diversity_and_e2e_solvers():
    # 1. Seed determinism
    b1 = FuzzGenerator.generate(seed=1007)
    b2 = FuzzGenerator.generate(seed=1007)
    assert b1.profile.model_dump() == b2.profile.model_dump()
    assert [t.model_dump() for t in b1.tasks] == [t.model_dump() for t in b2.tasks]
    assert b1.metadata.model_dump() == b2.metadata.model_dump()

    # 2. Structural diversity across 20 arbitrary seeds & acyclic DAG checks
    signatures = set()
    for seed in range(1001, 1021):
        b = FuzzGenerator.generate(seed=seed)
        assert b.metadata.is_fuzz is True
        prep = preprocess_tasks(b.profile, b.tasks)
        _, bad_deps = BaseScheduler.partition_dependency_order(prep, prep)
        assert not bad_deps
        sig = (
            b.metadata.persona_archetype,
            b.metadata.chronotype,
            b.metadata.horizon_days,
            b.metadata.task_count,
            b.metadata.habit_count,
            round(b.metadata.tightness_rho, 2),
        )
        signatures.add(sig)
    assert len(signatures) >= 18

    # 3. Full 5-solver E2E pass over 10 fuzz seeds across all 3 tiers
    for seed in range(1001, 1011):
        res = run_fuzz_case(seed=seed)
        assert res.all_invariants_passed, (
            f"Fuzz seed={seed} failed: " + "; ".join(f"{c.name}: {c.detail}" for c in res.invariant_checks if not c.passed)
        )


def test_shock_survival_is_strictly_monotonic_across_meal_barrier():
    prof = CommitmentsProfile(
        student_id="MONOTONE",
        focus_preference="BALANCED",
        buffer_mode="HABIT",
        estimate_habit=None,
        horizon_days=7,
        sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00", is_hard_lock=True),
        fixed_events=_meals(),
    )
    t_prev = Task(
        task_id="TPREV",
        title="Push barrier",
        duration_min=150,
        deadline_day="Monday",
        deadline_time="23:59",
        priority=1,
        cognitive_load=2,
        category="ASSIGNMENT",
        is_splittable=False,
        max_chunk_min=180,
        buffer_mode="NONE",
    )
    t_next = Task(
        task_id="TNEXT",
        title="Next after meal edge",
        duration_min=30,
        deadline_day="Monday",
        deadline_time="23:59",
        priority=5,
        cognitive_load=2,
        category="ASSIGNMENT",
        is_splittable=False,
        buffer_mode="NONE",
    )
    sched = _out(
        [
            _blk("TPREV", "Monday", "15:30", "18:00", prio=1, load=2, dday="Monday"),
            _blk("TNEXT", "Monday", "18:00", "18:30", prio=5, load=2, dday="Monday"),
        ],
        [],
        2,
    )
    rep = ScheduleEvaluator.evaluate(prof, [t_prev, t_next], sched)
    shocks = {sr.shock_pct: sr.survived_priority_pct for sr in rep.p4_robustness_stability.shock_results}
    assert rep.p1_value_timeliness.deadline_value_rate_pct >= shocks[25.0] >= shocks[50.0]
    assert shocks[50.0] == 0.0


def test_fuzz_v2_witness_sufficiency_and_14day_tight_density():
    # 1. Plant-a-Witness guarantee on LOOSE & TIGHT + true structural overload on OVERLOAD
    for idx, tier in enumerate(["LOOSE", "TIGHT", "OVERLOAD"] * 5, start=2001):
        b = FuzzGenerator.generate(seed=idx, tier=tier)
        if tier in ("LOOSE", "TIGHT"):
            assert b.metadata.witness_verified is True
            assert b.witness_blocks is not None
            w_blocks = sorted(b.witness_blocks, key=lambda x: (x.start_slot, x.end_slot))
            w_sched = _out(w_blocks, [], len(preprocess_tasks(b.profile, b.tasks)))
            w_rep = ScheduleEvaluator.evaluate(
                b.profile, b.tasks, w_sched, input_pinned_blocks=b.pinned_blocks
            )
            assert w_rep.gates.g1_total_violations == 0
            assert w_rep.p1_value_timeliness.deadline_value_rate_pct == 100.0
            assert not w_rep.gates.is_structurally_overloaded
        else:
            assert b.metadata.witness_verified is False
            assert b.witness_blocks is None
            assert b.metadata.tightness_rho_deadline is not None
            assert b.metadata.tightness_rho_deadline >= 1.22

    # 2. Verify 14-day TIGHT density scaling (collect 6 seeds whose random profile has horizon_days == 14)
    found_14d_tight = 0
    for seed in range(1001, 1100):
        b = FuzzGenerator.generate(seed=seed, tier="TIGHT")
        if b.metadata.horizon_days == 14:
            found_14d_tight += 1
            assert b.metadata.fuzz_tier == "TIGHT"
            assert b.metadata.tightness_rho >= 0.65, f"seed={seed}: rho={b.metadata.tightness_rho} too loose"
            assert b.witness_blocks is not None
            w_rep = ScheduleEvaluator.evaluate(
                b.profile, b.tasks, _out(b.witness_blocks, [], len(preprocess_tasks(b.profile, b.tasks))),
                input_pinned_blocks=b.pinned_blocks,
            )
            assert w_rep.gates.g1_total_violations == 0
            assert w_rep.p1_value_timeliness.deadline_value_rate_pct == 100.0
            if found_14d_tight >= 6:
                break
    assert found_14d_tight == 6


def test_v21_scale_invariant_ctx_and_zero_buffer_controllability():
    # A. Scale-invariant FOCUS-FLOW: 6 switches spread over 10 study days (14d horizon) stays clean,
    # while 4 switches concentrated in a single study day (ctx_limit=4) triggers WARNING.
    prof_14 = CommitmentsProfile(
        student_id="SCALE14",
        focus_preference="MORNING",
        buffer_mode="COGNITIVE_LOAD",
        horizon_days=14,
        sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00", is_hard_lock=True),
        fixed_events=_meals(),
    )
    spread_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    tasks_14 = []
    blks_14 = []
    tid = 1
    for d_name in spread_days:
        for cat in ("EXAM", "PROJECT"):
            tasks_14.append(
                Task(task_id=f"S{tid}", title=f"S{tid}", duration_min=25, deadline_day="Next Sunday", deadline_time="23:59", priority=3, cognitive_load=1, category=cat)
            )
            blks_14.append(_blk(f"S{tid}", d_name, "08:00" if cat == "EXAM" else "08:45", "08:30" if cat == "EXAM" else "09:15", 3, 1, cat, dday="Next Sunday"))
            tid += 1
    for extra_d in ["Sunday", "Next Monday", "Next Tuesday", "Next Wednesday"]:
        tasks_14.append(
            Task(task_id=f"S{tid}", title=f"S{tid}", duration_min=25, deadline_day="Next Sunday", deadline_time="23:59", priority=3, cognitive_load=1, category="ASSIGNMENT")
        )
        blks_14.append(_blk(f"S{tid}", extra_d, "08:00", "08:30", 3, 1, "ASSIGNMENT", dday="Next Sunday"))
        tid += 1

    rep_spread = ScheduleEvaluator.evaluate(prof_14, tasks_14, _out(blks_14, [], len(tasks_14)))
    assert rep_spread.p3_sustainable_pacing.focus_context_switches == 6
    assert not any("FOCUS-FLOW" in w for w in rep_spread.moderate_warnings)
    assert rep_spread.verdict == VerdictLabel.HIGH_PRODUCTIVITY

    # Single-day 4 context switches still warns (ctx_limit = max(4, 1) = 4)
    tasks_1d = [
        Task(task_id=f"D{i}", title=f"D{i}", duration_min=25, deadline_day="Friday", deadline_time="23:59", priority=3, cognitive_load=1, category=cat)
        for i, cat in [(1, "EXAM"), (2, "PROJECT"), (3, "ASSIGNMENT"), (4, "DEADLINE"), (5, "EXAM")]
    ]
    blks_1d = [
        _blk("D1", "Tuesday", "08:00", "08:30", 3, 1, "EXAM", dday="Friday"),
        _blk("D2", "Tuesday", "08:45", "09:15", 3, 1, "PROJECT", dday="Friday"),
        _blk("D3", "Tuesday", "09:30", "10:00", 3, 1, "ASSIGNMENT", dday="Friday"),
        _blk("D4", "Tuesday", "10:15", "10:45", 3, 1, "DEADLINE", dday="Friday"),
        _blk("D5", "Tuesday", "11:00", "11:30", 3, 1, "EXAM", dday="Friday"),
    ]
    rep_1d = ScheduleEvaluator.evaluate(prof_14.model_copy(update={"horizon_days": 7}), tasks_1d, _out(blks_1d, [], 5))
    assert any("FOCUS-FLOW" in w for w in rep_1d.moderate_warnings)

    # B. Zero-buffer input (estimate_habit=RARELY) should NOT warn when Shock@+25% == 100%,
    # only emit INFO; when Shock@+25% drops below 85%, it MUST still flag WARNING.
    prof_nobuf = CommitmentsProfile(
        student_id="NOBUF",
        focus_preference="MORNING",
        buffer_mode="HABIT",
        estimate_habit="RARELY",
        horizon_days=7,
        sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00", is_hard_lock=True),
        fixed_events=_meals(),
    )
    t_b1 = Task(task_id="B1", title="B1", duration_min=60, deadline_day="Friday", priority=5, cognitive_load=2, category="ASSIGNMENT")
    t_b2 = Task(task_id="B2", title="B2", duration_min=60, deadline_day="Friday", priority=1, cognitive_load=2, category="ASSIGNMENT")
    rep_safe = ScheduleEvaluator.evaluate(
        prof_nobuf,
        [t_b1, t_b2],
        _out([_blk("B1", "Monday", "08:00", "09:00", 5, 2, dday="Friday"), _blk("B2", "Tuesday", "08:00", "09:00", 1, 2, dday="Friday")], [], 2),
    )
    assert rep_safe.p4_robustness_stability.true_buffer_task_pct == 0.0
    assert not any("SHOCK-SAFE" in w for w in rep_safe.moderate_warnings)
    assert any(c.severity == "INFO" and c.pillar == "P4.1" for c in rep_safe.d1_icee_critiques)
    assert rep_safe.verdict == VerdictLabel.HIGH_PRODUCTIVITY

    # Place low-prio B2 right before lunch so +25% (75m) collides -> Shock@+25% = 5/6 = 83.33% < 85% -> WARNING
    rep_frag = ScheduleEvaluator.evaluate(
        prof_nobuf,
        [t_b1, t_b2],
        _out([_blk("B1", "Monday", "08:00", "09:00", 5, 2, dday="Friday"), _blk("B2", "Tuesday", "11:00", "12:00", 1, 2, dday="Friday")], [], 2),
    )
    assert any("SHOCK-SAFE" in w for w in rep_frag.moderate_warnings)


def test_fuzz_v2_loose_witness_proves_high_productivity_achievable():
    high_cnt = 0
    for seed in range(3001, 3021):
        b = FuzzGenerator.generate(seed=seed, tier="LOOSE")
        assert b.witness_blocks is not None
        wb = sorted(b.witness_blocks, key=lambda x: (x.start_slot, x.end_slot))
        wr = ScheduleEvaluator.evaluate(
            b.profile,
            b.tasks,
            _out(wb, [], len(preprocess_tasks(b.profile, b.tasks))),
            input_pinned_blocks=b.pinned_blocks,
        )
        assert wr.gates.g1_total_violations == 0
        assert wr.p1_value_timeliness.deadline_value_rate_pct == 100.0
        assert not wr.gates.is_structurally_overloaded
        if wr.verdict == VerdictLabel.HIGH_PRODUCTIVITY:
            high_cnt += 1
    assert high_cnt >= 16, f"Expected >=16/20 LOOSE witnesses to hit HIGH_PRODUCTIVITY, got {high_cnt}/20"
