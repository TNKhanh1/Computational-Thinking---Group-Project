"""
Part 1: Reproducible Seeded Input Generator (`InputGenerator`).

Generates schema-valid SmartSchedule test inputs across 6 controlled Regimes
matching `Testing_Plan/Testing_Plan.md`:
  - Strict acyclic `depends_on` DAG + `start_after`
  - Chronotypes (`MORNING`/`Lark`, `BALANCED`/`Finch`, `EVENING`/`Owl`)
  - Asymmetric vs uniform `ACADEMIC_CLASS`, 3 daily `MEAL` events, locked `SleepSchedule`
  - Diversity of `priority`, `cognitive_load`, `work_rhythm`, `preferred_window`, `PersonalHabit`, `pinned_blocks`
  - Real-grid feasibility validation for Regimes 1–4 computed AFTER `expand_personal_habits -> apply_estimate_buffer`
"""

from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any, Dict, List, Optional, Tuple

from Testing_System.schemas import GeneratedTestMetadata, RegimeName
from Testing_System.sut_adapter import (
    BaseScheduler,
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    PersonalHabit,
    SLOTS_PER_DAY,
    ScheduleBlock,
    SleepSchedule,
    Task,
    TimeGridManager,
    build_base_grid,
    day_time_to_slot,
    preprocess_tasks,
    resolve_horizon_slots_safe,
    slot_to_day_time,
)

WEEKDAYS_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@dataclass
class Regime6PerturbationSuite:
    """Fox et al. (2006 §5.1) increasing-severity perturbations for Regime 6."""

    level_a_single_disruption: DisruptionEvent
    level_b_overrun_task_id: str
    level_b_overrun_pct: float
    level_c_compound_disruption: DisruptionEvent


@dataclass
class GeneratedCaseBundle:
    """Complete immutable Part-1 input bundle ready for Run Project & OutputEvaluator."""

    profile: CommitmentsProfile
    tasks: List[Task]
    pinned_blocks: List[ScheduleBlock]
    metadata: GeneratedTestMetadata
    regime6_suite: Optional[Regime6PerturbationSuite] = None


def _build_meals() -> List[FixedEvent]:
    """3 daily fixed MEAL commitments to enable Corne/Laporte meal-boundary checks."""
    return [
        FixedEvent(
            event_id="MEAL_BREAKFAST",
            title="Bữa sáng",
            day_of_week="ALL",
            start_time="07:15",
            end_time="07:45",
            category="MEAL",
        ),
        FixedEvent(
            event_id="MEAL_LUNCH",
            title="Bữa trưa",
            day_of_week="ALL",
            start_time="12:00",
            end_time="12:45",
            category="MEAL",
        ),
        FixedEvent(
            event_id="MEAL_DINNER",
            title="Bữa tối",
            day_of_week="ALL",
            start_time="18:30",
            end_time="19:15",
            category="MEAL",
        ),
    ]


def _build_classes(asymmetric: bool, rng: random.Random) -> List[FixedEvent]:
    """Build non-overlapping academic classes (avoiding meal windows)."""
    if asymmetric:
        # University pattern: classes Mon/Wed/Fri mornings; free Tue/Thu/weekend for SJL measurement
        events = [
            FixedEvent(
                event_id="CLASS_MWF_AM",
                title="Ca học sáng T2-T4-T6",
                day_of_week=["Monday", "Wednesday", "Friday"],
                start_time="08:00",
                end_time="11:30",
                category="ACADEMIC_CLASS",
            ),
            FixedEvent(
                event_id="CLASS_MON_PM",
                title="Thực hành T2",
                day_of_week="Monday",
                start_time="13:30",
                end_time="15:30",
                category="ACADEMIC_CLASS",
            ),
        ]
        if rng.random() < 0.5:
            events.append(
                FixedEvent(
                    event_id="CLASS_WED_PM",
                    title="Seminar T4",
                    day_of_week="Wednesday",
                    start_time="14:00",
                    end_time="16:00",
                    category="ACADEMIC_CLASS",
                )
            )
        return events

    return [
        FixedEvent(
            event_id="CLASS_DAILY_AM",
            title="Lớp cố định T2–T6",
            day_of_week=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            start_time="09:00",
            end_time="11:00",
            category="ACADEMIC_CLASS",
        )
    ]


def _verify_grid_feasibility(
    profile: CommitmentsProfile,
    raw_tasks: List[Task],
    pinned_blocks: List[ScheduleBlock],
) -> Tuple[bool, int, int, float]:
    """
    Validate true grid feasibility AFTER `expand_personal_habits -> apply_estimate_buffer`.
    Returns `(is_feasible, demand_slots, usable_free_slots, rho)`.
    """
    week_start = profile.planning_week_start
    now_slot = BaseScheduler.resolve_now_slot(profile)
    prepared = preprocess_tasks(profile, raw_tasks)
    horizon_slots = resolve_horizon_slots_safe(profile, prepared, pinned_blocks)
    grid = build_base_grid(profile, horizon_slots)

    # Place valid pins first on local grid copy
    _, pinned_slots_map, _, _ = BaseScheduler.prepare_pinned_blocks(
        grid,
        prepared,
        pinned_blocks,
        now_slot,
        week_start,
    )

    past_due = BaseScheduler.detect_past_due_tasks(prepared, week_start_iso=week_start)
    if past_due:
        return False, 0, 0, 0.0

    cap_reports = BaseScheduler.check_deadline_capacity(
        grid,
        prepared,
        now_slot=now_slot,
        week_start_iso=week_start,
        pinned_slots_by_task=pinned_slots_map,
    )
    if cap_reports:
        return False, 0, 0, 1.5

    # Check chronological release/dependency/contiguous-chunk bounds per task on simulated grid
    sim_grid = grid.clone()
    sim_grid.mark_dead_zones_as_rest()
    task_map = {t.task_id: t for t in prepared}
    # Quick topological check
    ordered_tasks, bad_deps = BaseScheduler.partition_dependency_order(prepared, prepared)
    if bad_deps:
        return False, 0, 0, 0.0

    # Sort deadlines ascending to check real interval fit greedily on the pre-buffered grid
    ordered_by_deadline = sorted(
        ordered_tasks,
        key=lambda t: (
            t.resolve_deadline_slot(week_start) if t.resolve_deadline_slot(week_start) is not None else 999999,
            -t.priority,
        ),
    )
    task_ends: Dict[str, int] = {}
    for t in ordered_by_deadline:
        sa = t.resolve_start_after_slot(week_start)
        ready = max(now_slot, sa if sa is not None else 0)
        for pid in t.depends_on:
            if pid not in task_ends:
                return False, 0, 0, 0.0
            ready = max(ready, task_ends[pid])
        d_slot = t.resolve_deadline_slot(week_start)
        limit = min(horizon_slots, d_slot) if d_slot is not None else horizon_slots
        if ready >= limit:
            return False, 0, 0, 0.0
        chunks = BaseScheduler.split_task_into_chunks(t, week_start_iso=week_start)
        cur = ready
        for ch in chunks:
            if (t.task_id, ch.chunk_index) in {(p.task_id, p.chunk_index) for p in pinned_blocks}:
                continue
            free_ivs = [
                (s, l)
                for s, l in sim_grid.get_free_intervals(start_from=cur, up_to=limit)
                if l >= ch.duration_slots
            ]
            if not free_ivs:
                return False, 0, 0, 0.0
            chosen = free_ivs[0][0]
            sim_grid.place_block(chosen, ch.duration_slots, t.task_id, t.title)
            cur = chosen + ch.duration_slots
            if ch.duration_min >= 90 or ch.cognitive_load == 3:
                sim_grid.reserve_rest_break(cur, 1, task_id=t.task_id)
        task_ends[t.task_id] = cur

    # Compute exact G2 tightness metrics
    demand_slots = sum(
        max(0, t.get_planned_slots() - pinned_slots_map.get(t.task_id, 0)) for t in prepared
    )
    has_habit = any(t.resolve_deadline_slot(week_start) is None for t in prepared)
    if has_habit:
        eval_end = horizon_slots
    else:
        d_vals = [
            d_val for t in prepared for d_val in [t.resolve_deadline_slot(week_start)] if d_val is not None
        ]
        eval_end = min(horizon_slots, max(d_vals)) if d_vals else horizon_slots
    usable_free = grid.count_free_slots_in_range(start_from=now_slot, up_to=eval_end)
    rho = round(demand_slots / float(max(1, usable_free)), 4)
    return True, demand_slots, usable_free, rho


class InputGenerator:
    """Seeded synthetic benchmark input generator across 6 controlled Regimes."""

    @staticmethod
    def generate(regime: RegimeName, seed: int = 42, horizon_days: Optional[int] = None) -> GeneratedCaseBundle:
        rng = random.Random(seed)
        if regime == RegimeName.LOOSE_FEASIBLE:
            return InputGenerator._gen_regime1_loose(rng, seed, horizon_days)
        if regime == RegimeName.TIGHT_DEADLINE_CLUSTER:
            return InputGenerator._gen_regime2_tight_cluster(rng, seed, horizon_days)
        if regime == RegimeName.CIRCADIAN_SJL_AND_RECOVERY:
            return InputGenerator._gen_regime3_circadian_sjl(rng, seed, horizon_days)
        if regime == RegimeName.PROCRASTINATION_ONSET_AND_DAG:
            return InputGenerator._gen_regime4_procrastination_dag(rng, seed, horizon_days)
        if regime == RegimeName.OVERLOAD_INFEASIBLE:
            return InputGenerator._gen_regime5_overload(rng, seed, horizon_days)
        if regime == RegimeName.DISRUPTION_AND_OVERRUN_SERIES:
            return InputGenerator._gen_regime6_disruption_series(rng, seed, horizon_days)
        raise ValueError(f"Unsupported regime: {regime}")

    @staticmethod
    def _gen_regime1_loose(
        rng: random.Random, seed: int, horizon_days_override: Optional[int]
    ) -> GeneratedCaseBundle:
        chrono = rng.choice(["EVENING", "MORNING", "BALANCED"])
        h_days = horizon_days_override or (14 if seed % 4 == 1 else 7)
        profile = CommitmentsProfile(
            student_id=f"R1_STU_{seed}",
            focus_preference=chrono,
            buffer_mode="COGNITIVE_LOAD",
            horizon_days=h_days,
            sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00", is_hard_lock=True),
            fixed_events=_build_meals() + _build_classes(asymmetric=True, rng=rng),
            personal_habits=[
                PersonalHabit(
                    habit_id="HAB_REVIEW",
                    name="Ôn từ vựng ngắn",
                    duration_min=30,
                    frequency_per_week=2,
                    preferred_window="EVENING" if chrono == "EVENING" else "AFTERNOON",
                    cognitive_load=1,
                )
            ],
        )

        # Target rho in ~[0.35, 0.55] with rich mix of priority, load, category, and preferred_window
        # Note: BALANCED profile also peaks in MORNING (3, 2, 2, 1), so align heavy preferred_window with Peak!
        pref_heavy = "EVENING" if chrono == "EVENING" else "MORNING"
        d_end_label = "Next Wednesday" if h_days == 14 else "Sunday"
        candidates: List[Task] = [
            Task(task_id="R1_T1", title="Phân tích thuật toán đồ thị", duration_min=60, deadline_day="Thursday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT", preferred_window=pref_heavy, work_rhythm="FLOW"),
            Task(task_id="R1_T2", title="Ôn tập chuyên đề tối ưu", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM", preferred_window=pref_heavy, work_rhythm="FLOW"),
            Task(task_id="R1_T3", title="Lập báo cáo thực nghiệm", duration_min=60, deadline_day=d_end_label, deadline_time="23:59", priority=4, cognitive_load=3, category="PROJECT", preferred_window=pref_heavy, work_rhythm="BALANCED"),
            Task(task_id="R1_T4", title="Bài tập đọc hiểu tài liệu", duration_min=45, deadline_day="Wednesday", deadline_time="23:59", priority=3, cognitive_load=2, category="ASSIGNMENT", preferred_window="AFTERNOON", work_rhythm="BALANCED"),
            Task(task_id="R1_T5", title="Ghi chú tổng hợp tuần", duration_min=30, deadline_day="Friday", deadline_time="23:59", priority=2, cognitive_load=1, category="DEADLINE", work_rhythm="LIGHT"),
            Task(task_id="R1_T6", title="Kiểm tra nhanh công thức", duration_min=30, deadline_day="Saturday", deadline_time="23:59", priority=1, cognitive_load=1, category="ASSIGNMENT", work_rhythm="LIGHT"),
            Task(task_id="R1_T7", title="Thiết kế mô-đun mở rộng", duration_min=60, deadline_day=d_end_label, deadline_time="23:59", priority=4, cognitive_load=3, category="PROJECT", preferred_window=pref_heavy, is_splittable=True, depends_on=["R1_T1"]),
        ]
        # Top up deterministically up to ~0.36..0.52 tightness while remaining comfortably loose & feasible
        topup_days = ["Thursday", "Friday", "Saturday", "Sunday"]
        if h_days == 14:
            topup_days.extend(["Next Tuesday", "Next Wednesday", "Next Thursday", "Next Friday", "Next Saturday"])
        ok, demand, free_slots, rho = _verify_grid_feasibility(profile, candidates, [])
        for idx_top in range(1, 35):
            if rho >= 0.36:
                break
            load_pick = 3 if idx_top % 3 == 1 else (2 if idx_top % 3 == 2 else 1)
            pref_pick = pref_heavy if load_pick == 3 else ("AFTERNOON" if load_pick == 2 else "ANYTIME")
            cand = Task(
                task_id=f"R1_FILL_{idx_top}",
                title=f"Module tự học #{idx_top}",
                duration_min=60 if load_pick >= 2 else 45,
                deadline_day=topup_days[(idx_top - 1) % len(topup_days)],
                deadline_time="23:59",
                priority=4 if load_pick == 3 else (3 if load_pick == 2 else 2),
                cognitive_load=load_pick,
                category="PROJECT" if load_pick == 3 else ("ASSIGNMENT" if load_pick == 2 else "DEADLINE"),
                preferred_window=pref_pick,
                is_splittable=False,
            )
            ok_t, d_t, f_t, rho_t = _verify_grid_feasibility(profile, candidates + [cand], [])
            if ok_t and rho_t <= 0.54:
                candidates.append(cand)
                ok, demand, free_slots, rho = ok_t, d_t, f_t, rho_t

        if not ok:
            while candidates and not ok:
                candidates.pop()
                ok, demand, free_slots, rho = _verify_grid_feasibility(profile, candidates, [])

        meta = GeneratedTestMetadata(
            seed=seed,
            regime=RegimeName.LOOSE_FEASIBLE,
            chronotype=chrono,
            horizon_days=h_days,
            has_asymmetric_classes=True,
            buffer_mode=profile.buffer_mode,
            planned_demand_slots=demand,
            usable_free_slots=free_slots,
            tightness_rho=rho,
            task_count=len(candidates),
            habit_count=len(profile.personal_habits),
            pinned_count=0,
            notes="Loose feasible benchmark isolating soft quality & circadian gaps beyond % scheduled.",
        )
        return GeneratedCaseBundle(profile=profile, tasks=candidates, pinned_blocks=[], metadata=meta)

    @staticmethod
    def _gen_regime2_tight_cluster(
        rng: random.Random, seed: int, horizon_days_override: Optional[int]
    ) -> GeneratedCaseBundle:
        chrono = rng.choice(["BALANCED", "EVENING", "MORNING"])
        h_days = horizon_days_override or 7
        profile = CommitmentsProfile(
            student_id=f"R2_STU_{seed}",
            focus_preference=chrono,
            buffer_mode="HABIT",
            estimate_habit="RARELY",  # Low/zero internal buffer to stress-test Zero-Slack & Shock@+25%
            horizon_days=h_days,
            sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00", is_hard_lock=True),
            fixed_events=_build_meals() + [
                FixedEvent(event_id="R2_CLS1", title="Lớp sáng T2-T3-T4", day_of_week=["Monday", "Tuesday", "Wednesday"], start_time="08:00", end_time="11:30", category="ACADEMIC_CLASS"),
                FixedEvent(event_id="R2_CLS2", title="Lab chiều T2-T4", day_of_week=["Monday", "Wednesday"], start_time="13:30", end_time="17:00", category="ACADEMIC_CLASS"),
            ],
        )

        # Pack heavy + clustered deadlines on Tuesday–Thursday
        tasks = [
            Task(task_id="R2_EX1", title="Ôn thi giữa kỳ Cấu trúc dữ liệu", duration_min=120, deadline_day="Wednesday", deadline_time="22:00", priority=5, cognitive_load=3, category="EXAM", is_splittable=True, max_chunk_min=60),
            Task(task_id="R2_PRJ1", title="Đồ án nhóm phần lõi", duration_min=120, deadline_day="Wednesday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT", is_splittable=True, max_chunk_min=60),
            Task(task_id="R2_HW1", title="Bài tập rời rạc", duration_min=90, deadline_day="Tuesday", deadline_time="23:00", priority=4, cognitive_load=3, category="ASSIGNMENT", is_splittable=False),
            Task(task_id="R2_HW2", title="Viết tóm tắt đọc hiểu", duration_min=60, deadline_day="Wednesday", deadline_time="23:59", priority=2, cognitive_load=2, category="DEADLINE", is_splittable=False),
            Task(task_id="R2_L1", title="Nộp biểu mẫu môn học", duration_min=45, deadline_day="Thursday", deadline_time="18:00", priority=1, cognitive_load=1, category="DEADLINE", is_splittable=False),
            Task(task_id="R2_EX2", title="Luyện đề Xác suất", duration_min=90, deadline_day="Thursday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM", is_splittable=False),
            Task(task_id="R2_PRJ2", title="Viết tài liệu kiểm thử", duration_min=90, deadline_day="Friday", deadline_time="23:59", priority=4, cognitive_load=2, category="PROJECT", is_splittable=True, max_chunk_min=60),
            Task(task_id="R2_PRJ3", title="Tổng hợp kết quả tuần", duration_min=90, deadline_day="Friday", deadline_time="23:59", priority=3, cognitive_load=3, category="ASSIGNMENT", is_splittable=False),
        ]
        # Top up deterministic tasks targeting tight rho ~ [0.78, 0.94] across Mon..Fri cluster
        extra_pool = [
            Task(
                task_id=f"R2_EXT_{i}",
                title=f"Bài luyện bổ sung #{i}",
                duration_min=60 if i % 2 == 1 else 45,
                deadline_day="Friday" if i % 3 != 0 else "Thursday",
                deadline_time="23:59",
                priority=rng.choice([2, 3, 4]),
                cognitive_load=rng.choice([2, 3]),
                category=rng.choice(["EXAM", "ASSIGNMENT", "DEADLINE"]),
            )
            for i in range(1, 35)
        ]
        ok, demand, free_slots, rho = _verify_grid_feasibility(profile, tasks, [])
        for cand in extra_pool:
            if rho >= 0.82:
                break
            trial = tasks + [cand]
            ok_t, d_t, f_t, rho_t = _verify_grid_feasibility(profile, trial, [])
            if ok_t and rho_t <= 0.94:
                tasks = trial
                demand, free_slots, rho = d_t, f_t, rho_t

        meta = GeneratedTestMetadata(
            seed=seed,
            regime=RegimeName.TIGHT_DEADLINE_CLUSTER,
            chronotype=chrono,
            horizon_days=h_days,
            has_asymmetric_classes=True,
            buffer_mode=profile.buffer_mode,
            estimate_habit=profile.estimate_habit,
            planned_demand_slots=demand,
            usable_free_slots=free_slots,
            tightness_rho=rho,
            task_count=len(tasks),
            habit_count=0,
            pinned_count=0,
            notes="Tight deadline cluster stressing P1.1 priority preservation, P3.2 Corne clustering, and P4.1 shock vulnerability.",
        )
        return GeneratedCaseBundle(profile=profile, tasks=tasks, pinned_blocks=[], metadata=meta)

    @staticmethod
    def _gen_regime3_circadian_sjl(
        rng: random.Random, seed: int, horizon_days_override: Optional[int]
    ) -> GeneratedCaseBundle:
        # Primarily Owl (EVENING) so EDF morning scan collides with low morning energy (Forced Phase Advance),
        # plus asymmetric MWF morning classes to test circular SJL.
        chrono = "EVENING" if seed % 5 != 0 else "MORNING"
        h_days = horizon_days_override or 7
        profile = CommitmentsProfile(
            student_id=f"R3_STU_{seed}",
            focus_preference=chrono,
            buffer_mode="COGNITIVE_LOAD",
            horizon_days=h_days,
            sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30", is_hard_lock=True),
            fixed_events=_build_meals() + _build_classes(asymmetric=True, rng=rng),
        )

        # Place heavy load=3 tasks starting early Mon morning so EDF tends to schedule Tue morning [06:30-12:00]
        # while SCORED_GREEDY chooses EVENING peak windows, plus light tasks to fill remaining slots.
        tasks = [
            Task(task_id="R3_DEEP1", title="Giải bài tập Giải tích nâng cao", duration_min=60, deadline_day="Thursday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM", preferred_window="EVENING" if chrono == "EVENING" else "MORNING"),
            Task(task_id="R3_DEEP2", title="Xây dựng bộ giải tối ưu", duration_min=60, deadline_day="Thursday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT", preferred_window="EVENING" if chrono == "EVENING" else "MORNING"),
            Task(task_id="R3_DEEP3", title="Đọc và phản biện paper", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=4, cognitive_load=3, category="ASSIGNMENT", preferred_window="EVENING" if chrono == "EVENING" else "MORNING"),
            Task(task_id="R3_DEEP4", title="Phân tích dữ liệu thực nghiệm", duration_min=60, deadline_day="Saturday", deadline_time="23:59", priority=4, cognitive_load=3, category="PROJECT"),
            Task(task_id="R3_L1", title="Chuẩn bị tài liệu đọc nhẹ", duration_min=45, deadline_day="Wednesday", deadline_time="23:59", priority=2, cognitive_load=1, category="DEADLINE"),
            Task(task_id="R3_L2", title="Kiểm tra định dạng báo cáo", duration_min=45, deadline_day="Friday", deadline_time="23:59", priority=1, cognitive_load=1, category="DEADLINE"),
        ]
        ok, demand, free_slots, rho = _verify_grid_feasibility(profile, tasks, [])
        if not ok:
            while tasks and not ok:
                tasks.pop()
                ok, demand, free_slots, rho = _verify_grid_feasibility(profile, tasks, [])

        meta = GeneratedTestMetadata(
            seed=seed,
            regime=RegimeName.CIRCADIAN_SJL_AND_RECOVERY,
            chronotype=chrono,
            horizon_days=h_days,
            has_asymmetric_classes=True,
            buffer_mode=profile.buffer_mode,
            planned_demand_slots=demand,
            usable_free_slots=free_slots,
            tightness_rho=rho,
            task_count=len(tasks),
            habit_count=0,
            pinned_count=0,
            notes="Tests Owl forced morning phase advance (06:00-12:00), circular SJL on asymmetric classes, and >10m cognitive breaks.",
        )
        return GeneratedCaseBundle(profile=profile, tasks=tasks, pinned_blocks=[], metadata=meta)

    @staticmethod
    def _gen_regime4_procrastination_dag(
        rng: random.Random, seed: int, horizon_days_override: Optional[int]
    ) -> GeneratedCaseBundle:
        chrono = "EVENING"
        h_days = horizon_days_override or 7
        profile = CommitmentsProfile(
            student_id=f"R4_STU_{seed}",
            now="Monday 08:00",
            focus_preference=chrono,
            buffer_mode="COGNITIVE_LOAD",
            horizon_days=h_days,
            sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30", is_hard_lock=True),
            fixed_events=_build_meals() + _build_classes(asymmetric=False, rng=rng),
        )

        # Chain 1: PREP -> BUILD -> REVIEW (preparatory behavior Studies 3a-3b)
        # Chain 2: Wide-window urgent vs strategic-idling tasks on Mon/Tue so delaying for Peak or urgent prereq is justified
        tasks = [
            Task(task_id="R4_URGENT_TUE", title="Bài nộp gấp Thứ Ba", duration_min=90, deadline_day="Tuesday", deadline_time="22:00", priority=5, cognitive_load=3, category="EXAM"),
            Task(task_id="R4_PREP", title="Bước 1: Đọc đề và thu thập dữ liệu", duration_min=45, deadline_day="Friday", deadline_time="23:59", priority=4, cognitive_load=2, category="PROJECT", start_after="Monday 08:00"),
            Task(task_id="R4_BUILD", title="Bước 2: Cài đặt mô hình chính", duration_min=60, deadline_day="Saturday", deadline_time="23:59", priority=4, cognitive_load=3, category="PROJECT", depends_on=["R4_PREP"], preferred_window="EVENING"),
            Task(task_id="R4_FINAL", title="Bước 3: Viết báo cáo & kiểm tra", duration_min=60, deadline_day="Sunday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT", depends_on=["R4_BUILD"], preferred_window="EVENING"),
            Task(task_id="R4_LATE_RELEASE", title="Nhiệm vụ chỉ mở sau Thứ Tư trưa", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=3, cognitive_load=2, category="ASSIGNMENT", start_after="Wednesday 13:00"),
        ]
        ok, demand, free_slots, rho = _verify_grid_feasibility(profile, tasks, [])
        assert ok, f"Regime 4 seed={seed} failed grid feasibility verification"

        meta = GeneratedTestMetadata(
            seed=seed,
            regime=RegimeName.PROCRASTINATION_ONSET_AND_DAG,
            chronotype=chrono,
            horizon_days=h_days,
            has_asymmetric_classes=False,
            buffer_mode=profile.buffer_mode,
            planned_demand_slots=demand,
            usable_free_slots=free_slots,
            tightness_rho=rho,
            task_count=len(tasks),
            habit_count=0,
            pinned_count=0,
            notes="DAG precedence chain + start_after + wide >10h windows + strategic idling branch for P1.2.",
        )
        return GeneratedCaseBundle(profile=profile, tasks=tasks, pinned_blocks=[], metadata=meta)

    @staticmethod
    def _gen_regime5_overload(
        rng: random.Random, seed: int, horizon_days_override: Optional[int]
    ) -> GeneratedCaseBundle:
        chrono = rng.choice(["BALANCED", "MORNING", "EVENING"])
        h_days = horizon_days_override or 7
        profile = CommitmentsProfile(
            student_id=f"R5_STU_{seed}",
            focus_preference=chrono,
            buffer_mode="COGNITIVE_LOAD",
            horizon_days=h_days,
            sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00", is_hard_lock=True),
            fixed_events=_build_meals() + [
                FixedEvent(event_id="R5_CLS_ALL", title="Học toàn ngày T2-T4", day_of_week=["Monday", "Tuesday", "Wednesday", "Thursday"], start_time="08:00", end_time="17:00", category="ACADEMIC_CLASS"),
            ],
            personal_habits=[
                PersonalHabit(habit_id="R5_HAB", name="Đọc sách", duration_min=45, frequency_per_week=2, cognitive_load=1),
            ],
        )

        # Low-priority filler due EARLIER (Wednesday 23:59) vs High-priority critical exams due Thursday 23:59:
        # Tests EDF's classic blind-urgency weakness vs priority-preserving SCORED_GREEDY / WSPT.
        tasks = [
            Task(task_id="R5_CRIT1", title="Đồ án tối quan trọng", duration_min=150, deadline_day="Thursday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT", is_splittable=True, max_chunk_min=90),
            Task(task_id="R5_CRIT2", title="Thi giữa kỳ bắt buộc", duration_min=120, deadline_day="Thursday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM", is_splittable=True, max_chunk_min=90),
            Task(task_id="R5_MED1", title="Bài tập lớn số 2", duration_min=120, deadline_day="Thursday", deadline_time="23:59", priority=4, cognitive_load=2, category="ASSIGNMENT", is_splittable=True, max_chunk_min=90),
            Task(task_id="R5_LOW1", title="Việc phụ lặt vặt 1", duration_min=150, deadline_day="Wednesday", deadline_time="23:59", priority=1, cognitive_load=1, category="DEADLINE", is_splittable=True, max_chunk_min=90),
            Task(task_id="R5_LOW2", title="Việc phụ lặt vặt 2", duration_min=150, deadline_day="Wednesday", deadline_time="23:59", priority=1, cognitive_load=1, category="DEADLINE", is_splittable=True, max_chunk_min=90),
            Task(task_id="R5_LOW3", title="Việc phụ lặt vặt 3", duration_min=150, deadline_day="Wednesday", deadline_time="23:59", priority=1, cognitive_load=1, category="DEADLINE", is_splittable=True, max_chunk_min=90),
        ]
        # Bump optional tasks until structural overload rho_deadline in [1.18, 1.50]
        prepared = preprocess_tasks(profile, tasks)
        h_slots = resolve_horizon_slots_safe(profile, prepared, [])
        grid = build_base_grid(profile, h_slots)
        deadline_vals = [d for t in prepared for d in [t.resolve_deadline_slot()] if d is not None]
        max_d = max(deadline_vals) if deadline_vals else h_slots
        free_d = grid.count_free_slots_in_range(start_from=0, up_to=max_d)
        d_slots = sum(t.get_planned_slots() for t in prepared if t.resolve_deadline_slot() is not None)
        rho_deadline = round(d_slots / float(max(1, free_d)), 4)
        extra_i = 1
        while rho_deadline < 1.25 and extra_i <= 6:
            tasks.append(
                Task(
                    task_id=f"R5_EXTRA_{extra_i}",
                    title=f"Việc quá tải #{extra_i}",
                    duration_min=120,
                    deadline_day="Thursday",
                    deadline_time="23:59",
                    priority=2,
                    cognitive_load=2,
                    category="ASSIGNMENT",
                    is_splittable=True,
                    max_chunk_min=90,
                )
            )
            prepared = preprocess_tasks(profile, tasks)
            d_slots = sum(t.get_planned_slots() for t in prepared if t.resolve_deadline_slot() is not None)
            rho_deadline = round(d_slots / float(max(1, free_d)), 4)
            extra_i += 1

        total_planned = sum(t.get_planned_slots() for t in prepared)
        usable_horizon = grid.count_free_slots_in_range(0, h_slots)
        rho_total = round(total_planned / float(max(1, usable_horizon)), 4)

        meta = GeneratedTestMetadata(
            seed=seed,
            regime=RegimeName.OVERLOAD_INFEASIBLE,
            chronotype=chrono,
            horizon_days=h_days,
            has_asymmetric_classes=False,
            buffer_mode=profile.buffer_mode,
            planned_demand_slots=total_planned,
            usable_free_slots=usable_horizon,
            tightness_rho=rho_total,
            tightness_rho_deadline=rho_deadline,
            task_count=len(tasks),
            habit_count=len(profile.personal_habits),
            pinned_count=0,
            notes=f"Structural overload before Thursday deadline (rho_deadline={rho_deadline}) testing OVERLOAD_TRIAGE & G2.",
        )
        return GeneratedCaseBundle(profile=profile, tasks=tasks, pinned_blocks=[], metadata=meta)

    @staticmethod
    def _gen_regime6_disruption_series(
        rng: random.Random, seed: int, horizon_days_override: Optional[int]
    ) -> GeneratedCaseBundle:
        h_days = horizon_days_override or 7
        profile = CommitmentsProfile(
            student_id=f"R6_STU_{seed}",
            now="Monday 07:00",
            focus_preference="BALANCED",
            buffer_mode="COGNITIVE_LOAD",
            horizon_days=h_days,
            sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00", is_hard_lock=True),
            fixed_events=_build_meals() + _build_classes(asymmetric=True, rng=rng),
        )
        tasks = [
            Task(task_id="R6_ANCHOR", title="Buổi thực hành tự chọn (Cố định ghim)", duration_min=45, deadline_day="Saturday", deadline_time="23:59", priority=4, cognitive_load=2, category="PROJECT"),
            Task(task_id="R6_PREP", title="Chuẩn bị dữ liệu đầu vào", duration_min=60, deadline_day="Thursday", deadline_time="23:59", priority=5, cognitive_load=3, category="PROJECT"),
            Task(task_id="R6_MAIN", title="Huấn luyện & đánh giá mô hình", duration_min=60, deadline_day="Friday", deadline_time="23:59", priority=5, cognitive_load=3, category="EXAM", depends_on=["R6_PREP"]),
            Task(task_id="R6_FOLLOWUP", title="Tổng hợp kết quả sau đánh giá", duration_min=45, deadline_day="Saturday", deadline_time="23:59", priority=4, cognitive_load=2, category="ASSIGNMENT", depends_on=["R6_MAIN"]),
            Task(task_id="R6_SIDE1", title="Bài tập tự học T2", duration_min=60, deadline_day="Thursday", deadline_time="23:59", priority=3, cognitive_load=2, category="ASSIGNMENT"),
            Task(task_id="R6_SIDE2", title="Tổng kết tuần", duration_min=45, deadline_day="Sunday", deadline_time="23:59", priority=2, cognitive_load=1, category="DEADLINE"),
        ]

        # Pin R6_ANCHOR cleanly on Thursday afternoon 14:00-15:00 (after planned buffer 45*1.2=60m -> 4 slots)
        pin_start = day_time_to_slot("Thursday", "14:00", is_end_or_deadline=False)
        pin_end = pin_start + 4
        d_s, t_st = slot_to_day_time(pin_start, is_end_time=False)
        _, t_en = slot_to_day_time(pin_end, is_end_time=True)
        pinned_anchor = ScheduleBlock(
            block_id="R6_ANCHOR_P1",
            task_id="R6_ANCHOR",
            title="Buổi thực hành tự chọn (Cố định ghim)",
            day=d_s,
            start_time=t_st,
            end_time=t_en,
            start_slot=pin_start,
            end_slot=pin_end,
            duration_min=60,
            priority=4,
            category="PROJECT",
            cognitive_load=2,
            deadline_slot=day_time_to_slot("Saturday", "23:59", is_end_or_deadline=True),
            chunk_index=1,
            total_chunks=1,
            state="PINNED",
        )

        ok, demand, free_slots, rho = _verify_grid_feasibility(profile, tasks, [pinned_anchor])
        assert ok, f"Regime 6 seed={seed} failed grid feasibility"

        # Perturbation series: placed on Tuesday (early free window where solvers place R6_PREP / R6_SIDE1!)
        # Level A: Tuesday 14:00-16:00 sudden meeting; Level C: Wednesday 13:00-16:00 longer interruption hitting mid-week
        suite = Regime6PerturbationSuite(
            level_a_single_disruption=DisruptionEvent(
                event_id="DISR_LVL_A",
                title="Họp đột xuất 2h chiều Thứ Ba",
                day_of_week="Tuesday",
                start_time="14:00",
                end_time="16:00",
                now_day="Tuesday",
                now_time="13:00",
            ),
            level_b_overrun_task_id="R6_PREP",
            level_b_overrun_pct=50.0,
            level_c_compound_disruption=DisruptionEvent(
                event_id="DISR_LVL_C",
                title="Sự cố hệ thống kéo dài chiều Thứ Tư",
                day_of_week="Wednesday",
                start_time="13:00",
                end_time="16:30",
                now_day="Wednesday",
                now_time="12:30",
            ),
        )

        meta = GeneratedTestMetadata(
            seed=seed,
            regime=RegimeName.DISRUPTION_AND_OVERRUN_SERIES,
            chronotype="BALANCED",
            horizon_days=h_days,
            has_asymmetric_classes=True,
            buffer_mode=profile.buffer_mode,
            planned_demand_slots=demand,
            usable_free_slots=free_slots,
            tightness_rho=rho,
            task_count=len(tasks),
            habit_count=0,
            pinned_count=1,
            notes="Increasing disruption + +50% overrun series with valid Thursday PINNED block for P4.2 Fox/Vieira stability checks.",
        )
        return GeneratedCaseBundle(
            profile=profile,
            tasks=tasks,
            pinned_blocks=[pinned_anchor],
            metadata=meta,
            regime6_suite=suite,
        )
