"""
Part 1b: Procedural Infinite Stress / Fuzz Input Generator (`FuzzGenerator v2`).

Generates arbitrary, unbiased, non-templated student profiles, class schedules, habits,
tasks, acyclic dependency DAGs, start_after windows, and optional PINNED blocks across
any integer seed across 3 controllable density tiers (`LOOSE`, `TIGHT`, `OVERLOAD`).

v2 Upgrades:
  1. Scales max tasks and splittable task durations cleanly for 14-day horizons so
     `TIGHT` 14-day cases actually achieve target density rho in [0.65, 0.90].
  2. Uses Plant-a-Witness (Solution-First) generation for `LOOSE`/`TIGHT` cases: carves
     a randomized, solver-unbiased feasible witness schedule directly on `base_grid` and
     derives deadlines, DAG dependencies, `start_after`, and `PINNED` blocks from it,
     guaranteeing sufficient feasibility (`G1=0, P1.1=100%`) without solver bias.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Set, Tuple

from Testing_System.generator.input_generator import GeneratedCaseBundle
from Testing_System.schemas import GeneratedTestMetadata, RegimeName
from Testing_System.sut_adapter import (
    BaseScheduler,
    CommitmentsProfile,
    FixedEvent,
    PersonalHabit,
    SLOTS_PER_DAY,
    ScheduleBlock,
    ScheduleController,
    SleepSchedule,
    Task,
    TimeGridManager,
    build_base_grid,
    day_time_to_slot,
    parse_time_to_slot_offset,
    preprocess_tasks,
    resolve_horizon_slots_safe,
    slot_to_day_time,
)

DAYS_14 = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
    "Next Monday",
    "Next Tuesday",
    "Next Wednesday",
    "Next Thursday",
    "Next Friday",
    "Next Saturday",
    "Next Sunday",
]

ARCHETYPES = (
    "HIGH_SCHOOL_STUDENT",
    "UNI_ASYMMETRIC",
    "UNI_BUSY_WEEK",
    "EXAM_PREP_WEEK",
)

CLASS_CATEGORIES = {"ACADEMIC_CLASS", "CLASS", "LAB", "LECTURE"}
CATEGORIES = ("EXAM", "PROJECT", "ASSIGNMENT", "DEADLINE")
TASK_TITLES_BY_CAT = {
    "EXAM": [
        "Ôn thi Giải tích",
        "Luyện đề Xác suất",
        "Tổng ôn Cấu trúc dữ liệu",
        "Ôn tập Vật lý đại cương",
        "Làm đề thử Tiếng Anh",
        "Ôn kiểm tra Hóa học",
    ],
    "PROJECT": [
        "Cài đặt mô-đun thuật toán",
        "Thiết kế cơ sở dữ liệu",
        "Viết báo cáo thực nghiệm",
        "Xây dựng API backend",
        "Kiểm thử tích hợp hệ thống",
        "Làm slide thuyết trình nhóm",
    ],
    "ASSIGNMENT": [
        "Bài tập Toán rời rạc",
        "Viết bài luận phân tích",
        "Đọc hiểu & tóm tắt paper",
        "Bài tập lập trình tuần",
        "Soạn bài Ngữ văn",
        "Giải bài tập mạch số",
    ],
    "DEADLINE": [
        "Nộp biểu mẫu môn học",
        "Ghi chú tổng hợp tuần",
        "Hoàn thiện quiz nhanh",
        "Cập nhật nhật ký thực hành",
        "Kiểm tra định dạng báo cáo",
        "Tổng hợp tài liệu tham khảo",
    ],
}

HABIT_TEMPLATES = [
    ("Tập thể dục / Chạy bộ", 30, 1),
    ("Ôn từ vựng ngoại ngữ", 30, 1),
    ("Đọc sách chuyên ngành", 45, 2),
    ("Luyện nghe phản xạ", 30, 1),
    ("Ghi chép sổ tay tổng kết", 30, 1),
]


def _slot_str(slot_in_day: int) -> str:
    h, q = divmod(max(0, min(95, slot_in_day)), 4)
    return f"{h:02d}:{q * 15:02d}"


def _window_match_fraction(start_slot: int, length_slots: int, preferred_window: Optional[str]) -> float:
    pref = (preferred_window or "").strip().upper()
    if pref not in ("MORNING", "AFTERNOON", "EVENING"):
        return 1.0
    hits = 0
    for s in range(start_slot, start_slot + max(1, length_slots)):
        tod = s % SLOTS_PER_DAY
        if pref == "MORNING" and 24 <= tod < 48:
            hits += 1
        elif pref == "AFTERNOON" and 48 <= tod < 72:
            hits += 1
        elif pref == "EVENING" and 72 <= tod < 92:
            hits += 1
    return hits / float(max(1, length_slots))


def _chunk_shock25_extra(raw_min: int, total_planned_min: int, chunk_min: int, chunk_slots: int) -> int:
    """Exact mirror of `_simulate_shock_survival` extra slots needed at +25% shock on raw duration."""
    raw_chunk_min = raw_min * (chunk_min / float(max(15, total_planned_min)))
    shocked_slots = max(1, int(math.ceil((raw_chunk_min * 1.25) / 15.0 - 1e-9)))
    return max(0, shocked_slots - chunk_slots)


def _extract_profile_day_context(
    profile: CommitmentsProfile, horizon_slots: int
) -> Tuple[Dict[int, int], Set[int], Set[int], List[Tuple[int, int]]]:
    """Compute baseline class slots/day, all class slots, long class ends (>= 6 slots), and meal spans."""
    grid_helper = TimeGridManager(total_slots=horizon_slots)
    class_slots_per_day: Dict[int, int] = {}
    class_slots: Set[int] = set()
    long_class_ends: Set[int] = set()
    meal_spans: List[Tuple[int, int]] = []

    for ev in profile.fixed_events:
        cat = (ev.category or "").strip().upper()
        if cat not in CLASS_CATEGORIES and cat != "MEAL":
            continue
        start_off = parse_time_to_slot_offset(ev.start_time, is_end_or_deadline=False)
        end_off = parse_time_to_slot_offset(ev.end_time, is_end_or_deadline=True)
        if end_off == start_off:
            continue
        for d_idx in grid_helper._resolve_event_days(ev.day_of_week):
            if d_idx * SLOTS_PER_DAY >= horizon_slots:
                continue
            base = d_idx * SLOTS_PER_DAY
            spans = (
                [(base + start_off, min(horizon_slots, base + end_off))]
                if end_off > start_off
                else [
                    (base + start_off, min(horizon_slots, base + SLOTS_PER_DAY)),
                    ((d_idx + 1) * SLOTS_PER_DAY, min(horizon_slots, (d_idx + 1) * SLOTS_PER_DAY + end_off)),
                ]
            )
            for s0, s1 in spans:
                if s1 <= s0 or s0 >= horizon_slots:
                    continue
                if cat == "MEAL":
                    meal_spans.append((s0, s1))
                    continue
                for s in range(s0, s1):
                    d = s // SLOTS_PER_DAY
                    class_slots_per_day[d] = class_slots_per_day.get(d, 0) + 1
                    class_slots.add(s)
                if s1 - s0 >= 6 and s1 < horizon_slots:
                    long_class_ends.add(s1)

    return class_slots_per_day, class_slots, long_class_ends, meal_spans


def _build_archetype_profile(
    rng: random.Random, seed: int, tier: str
) -> Tuple[CommitmentsProfile, str, bool]:
    """Build a varied student CommitmentsProfile with non-overlapping sleep, meals, and classes."""
    archetype = "EXAM_PREP_WEEK" if (tier == "OVERLOAD" and rng.random() < 0.35) else rng.choice(ARCHETYPES)
    chrono = rng.choice(["MORNING", "AFTERNOON", "EVENING", "BALANCED"])
    h_days = 14 if rng.random() < 0.25 else 7
    buf_mode = rng.choice(["COGNITIVE_LOAD", "HABIT"])
    est_habit = rng.choice(["RARELY", "SOMETIMES", "OFTEN"]) if buf_mode == "HABIT" else None

    if archetype == "HIGH_SCHOOL_STUDENT":
        sleep_st = rng.choice(["22:15", "22:30", "23:00"])
        sleep_en = rng.choice(["05:45", "06:00", "06:15"])
    elif chrono == "EVENING":
        sleep_st = rng.choice(["23:30", "23:45", "00:15"])
        sleep_en = rng.choice(["07:00", "07:30", "08:00"])
    else:
        sleep_st = rng.choice(["22:45", "23:00", "23:30"])
        sleep_en = rng.choice(["06:30", "06:45", "07:00"])

    # Safe meal slots well outside typical sleep [22:15..08:00]: breakfast starts >= wake + 15m
    wake_parts = [int(x) for x in sleep_en.split(":")]
    wake_slot = wake_parts[0] * 4 + wake_parts[1] // 15
    bf_start = max(wake_slot + 1, 28)  # >= 07:00
    lunch_idx = rng.choice([47, 48])   # 11:45 or 12:00
    dinner_idx = rng.choice([73, 74])  # 18:15 or 18:30
    fixed_events: List[FixedEvent] = [
        FixedEvent(
            event_id="FZ_MEAL_B",
            title="Bữa sáng",
            day_of_week="ALL",
            start_time=_slot_str(bf_start),
            end_time=_slot_str(bf_start + 2),
            category="MEAL",
        ),
        FixedEvent(
            event_id="FZ_MEAL_L",
            title="Bữa trưa",
            day_of_week="ALL",
            start_time=_slot_str(lunch_idx),
            end_time=_slot_str(lunch_idx + 3),
            category="MEAL",
        ),
        FixedEvent(
            event_id="FZ_MEAL_D",
            title="Bữa tối",
            day_of_week="ALL",
            start_time=_slot_str(dinner_idx),
            end_time=_slot_str(dinner_idx + 3),
            category="MEAL",
        ),
    ]

    cls_start_min_slot = bf_start + 2
    am_start_str = _slot_str(max(cls_start_min_slot, 30))  # >= 07:30
    am_end_str = _slot_str(lunch_idx)  # ends cleanly before lunch

    has_asym = False
    if archetype == "HIGH_SCHOOL_STUDENT":
        fixed_events.append(
            FixedEvent(
                event_id="FZ_HS_AM",
                title="Học chính khóa",
                day_of_week=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
                start_time=am_start_str,
                end_time=am_end_str,
                category="ACADEMIC_CLASS",
            )
        )
        extra_pm_days = rng.sample(["Monday", "Tuesday", "Thursday", "Friday"], k=rng.randint(1, 2))
        fixed_events.append(
            FixedEvent(
                event_id="FZ_HS_PM",
                title="Học tăng cường chiều",
                day_of_week=extra_pm_days,
                start_time="13:45",
                end_time="16:45",
                category="ACADEMIC_CLASS",
            )
        )
        has_asym = True
    elif archetype == "UNI_ASYMMETRIC":
        has_asym = True
        cls_days_am = rng.sample(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], k=rng.randint(2, 3))
        fixed_events.append(
            FixedEvent(
                event_id="FZ_UNI_AM",
                title="Lý thuyết trên giảng đường",
                day_of_week=cls_days_am,
                start_time=_slot_str(max(cls_start_min_slot, 32)),
                end_time=am_end_str,
                category="ACADEMIC_CLASS",
            )
        )
        cls_days_pm = rng.sample(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], k=rng.randint(1, 2))
        fixed_events.append(
            FixedEvent(
                event_id="FZ_UNI_PM",
                title="Thực hành Lab",
                day_of_week=cls_days_pm,
                start_time="13:30",
                end_time=rng.choice(["15:30", "16:30"]),
                category="ACADEMIC_CLASS",
            )
        )
    elif archetype == "UNI_BUSY_WEEK":
        has_asym = True
        am_days = rng.sample(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"], k=4)
        fixed_events.append(
            FixedEvent(
                event_id="FZ_BUSY_AM",
                title="Ca học sáng",
                day_of_week=am_days,
                start_time=_slot_str(max(cls_start_min_slot, 32)),
                end_time=am_end_str,
                category="ACADEMIC_CLASS",
            )
        )
        pm_days = rng.sample(["Monday", "Tuesday", "Wednesday", "Thursday"], k=rng.randint(2, 3))
        fixed_events.append(
            FixedEvent(
                event_id="FZ_BUSY_PM",
                title="Ca học chiều",
                day_of_week=pm_days,
                start_time="13:30",
                end_time="16:45",
                category="ACADEMIC_CLASS",
            )
        )
    else:  # EXAM_PREP_WEEK
        has_asym = True
        sem_days = rng.sample(["Monday", "Tuesday", "Wednesday", "Thursday"], k=rng.randint(1, 2))
        fixed_events.append(
            FixedEvent(
                event_id="FZ_SEM",
                title="Hướng dẫn đồ án / Phụ đạo",
                day_of_week=sem_days,
                start_time="09:00",
                end_time="11:30",
                category="ACADEMIC_CLASS",
            )
        )

    habit_count = rng.randint(0, 2) if tier != "OVERLOAD" else rng.randint(0, 1)
    habits: List[PersonalHabit] = []
    chosen_h = rng.sample(HABIT_TEMPLATES, k=habit_count)
    for idx, (h_name, h_dur, h_load) in enumerate(chosen_h, start=1):
        habits.append(
            PersonalHabit(
                habit_id=f"FZ_HAB_{idx}",
                name=h_name,
                duration_min=h_dur,
                frequency_per_week=rng.randint(2, 4),
                preferred_window=rng.choice(["MORNING", "AFTERNOON", "EVENING", "ANYTIME"]),
                cognitive_load=h_load,
            )
        )

    now_str = f"Monday {_slot_str(max(wake_slot, 26))}"
    profile = CommitmentsProfile(
        student_id=f"FZ_{archetype[:4]}_{seed}",
        now=now_str,
        focus_preference=chrono,
        buffer_mode=buf_mode,
        estimate_habit=est_habit,
        horizon_days=h_days,
        sleep_schedule=SleepSchedule(daily_start_time=sleep_st, daily_end_time=sleep_en, is_hard_lock=True),
        fixed_events=fixed_events,
        personal_habits=habits,
    )
    return profile, archetype, has_asym


def _compute_rho(
    profile: CommitmentsProfile,
    tasks: List[Task],
    pinned: List[ScheduleBlock],
    require_chunk_fit: bool = True,
) -> Tuple[bool, int, int, float, float, bool]:
    """Compute grid tightness (rho_total, rho_deadline, deadline_capacity_ok) WITHOUT EDF ordering bias."""
    week_start = profile.planning_week_start
    now_slot = BaseScheduler.resolve_now_slot(profile)
    prep = preprocess_tasks(profile, tasks)
    h_slots = resolve_horizon_slots_safe(profile, prep, pinned)
    grid = build_base_grid(profile, h_slots)

    for pb in pinned:
        length = pb.end_slot - pb.start_slot
        if length > 0 and pb.end_slot <= h_slots and grid.is_range_free(pb.start_slot, length):
            grid.place_block(pb.start_slot, length, pb.task_id, pb.title)
        else:
            return False, 0, 1, 9.9, 9.9, False

    if BaseScheduler.detect_past_due_tasks(prep, week_start_iso=week_start):
        return False, 0, 1, 9.9, 9.9, False

    _, bad_deps = BaseScheduler.partition_dependency_order(prep, prep)
    if bad_deps:
        return False, 0, 1, 9.9, 9.9, False

    pinned_slots_map: Dict[str, int] = {}
    for pb in pinned:
        pinned_slots_map[pb.task_id] = pinned_slots_map.get(pb.task_id, 0) + (pb.end_slot - pb.start_slot)

    cap_shortages = BaseScheduler.check_deadline_capacity(
        grid, prep, now_slot=now_slot, week_start_iso=week_start, pinned_slots_by_task=pinned_slots_map
    )

    if require_chunk_fit:
        max_free_len = max((l for _, l in grid.get_free_intervals(now_slot, h_slots)), default=0)
        for t in prep:
            d_slot = t.resolve_deadline_slot(week_start)
            lim = min(h_slots, d_slot) if d_slot is not None else h_slots
            sa = t.resolve_start_after_slot(week_start)
            rd = max(now_slot, sa if sa is not None else 0)
            chunks = BaseScheduler.split_task_into_chunks(t, week_start_iso=week_start)
            need_max = max((c.duration_slots for c in chunks), default=0)
            if pinned_slots_map.get(t.task_id, 0) > 0:
                continue
            if need_max > max_free_len:
                return False, 0, 1, 9.9, 9.9, False
            if not any(l >= need_max for _, l in grid.get_free_intervals(rd, lim)):
                return False, 0, 1, 9.9, 9.9, False

    d_tasks = [t for t in prep if t.resolve_deadline_slot(week_start) is not None]
    d_slots = sum(max(0, t.get_planned_slots() - pinned_slots_map.get(t.task_id, 0)) for t in d_tasks)
    tot_slots = sum(max(0, t.get_planned_slots() - pinned_slots_map.get(t.task_id, 0)) for t in prep)

    d_vals = [d for t in d_tasks for d in [t.resolve_deadline_slot(week_start)] if d is not None]
    max_d = min(h_slots, max(d_vals)) if d_vals else h_slots
    free_d = grid.count_free_slots_in_range(now_slot, max_d)

    has_habit = len(d_tasks) < len(prep)
    eval_end = h_slots if has_habit else max_d
    usable_eval = grid.count_free_slots_in_range(now_slot, eval_end)
    rho_total = round(tot_slots / float(max(1, usable_eval)), 4)
    rho_deadline = round(d_slots / float(max(1, free_d)), 4) if d_tasks else 0.0
    return (not cap_shortages), tot_slots, usable_eval, rho_total, rho_deadline, bool(cap_shortages)


def _sample_interval_positions(rng: random.Random, iv_start: int, iv_len: int, span: int) -> List[int]:
    """Sample diverse start positions inside a free interval (zero EDF/LST bias)."""
    max_off = iv_len - span
    if max_off <= 0:
        return [iv_start]
    offs = {0, max_off}
    for _ in range(min(3, max_off)):
        offs.add(rng.randint(0, max_off))
    return [iv_start + o for o in sorted(offs)]


def _place_habits_on_witness(
    rng: random.Random,
    profile: CommitmentsProfile,
    witness_grid: TimeGridManager,
    now_slot: int,
    h_slots: int,
    class_slots_day: Dict[int, int],
    day_study_slots: Dict[int, int],
    l2_starts: Set[int],
    l2_ends: Set[int],
    shock_guard_slots: Set[int],
    strict_ergonomic: bool = False,
) -> List[ScheduleBlock]:
    """Commit all PersonalHabit occurrences onto `witness_grid`, dropping any habit that cannot fit."""
    week_start = profile.planning_week_start
    kept_habits: List[PersonalHabit] = []
    habit_blocks: List[ScheduleBlock] = []

    for hab in list(profile.personal_habits):
        solo_prof = profile.model_copy(update={"personal_habits": [hab]}, deep=True)
        h_tasks = preprocess_tasks(solo_prof, [])
        trial = witness_grid.clone()
        trial_study = dict(day_study_slots)
        trial_guards = set(shock_guard_slots)
        placed_h: List[ScheduleBlock] = []
        fit_all = True

        for ht in h_tasks:
            need = ht.get_planned_slots()
            shock_extra = _chunk_shock25_extra(ht.duration_min, ht.get_planned_duration_min(), ht.get_planned_duration_min(), need)
            sa = ht.resolve_start_after_slot(week_start)
            ready = max(now_slot, sa if sa is not None else 0)
            cands: List[Tuple[Tuple[int, int, int], int]] = []
            for iv_s, iv_l in trial.get_free_intervals(start_from=ready, up_to=h_slots):
                if iv_l < need:
                    continue
                for s0 in _sample_interval_positions(rng, iv_s, iv_l, need):
                    shock_ok = 0
                    if shock_extra > 0 and (
                        s0 + need + shock_extra > h_slots or not trial.is_range_free(s0 + need, shock_extra)
                    ):
                        shock_ok = 1
                    elif any(s in trial_guards for s in range(s0, min(h_slots, s0 + need + shock_extra))):
                        shock_ok = 1
                    win_ok = 0 if _window_match_fraction(s0, need, ht.preferred_window) >= 0.99 else 1
                    d = s0 // SLOTS_PER_DAY
                    cap_bad = 0 if (class_slots_day.get(d, 0) + trial_study.get(d, 0) + need <= 36) else 1
                    if strict_ergonomic and (cap_bad or shock_ok):
                        continue
                    cands.append(((shock_ok + cap_bad, win_ok, (class_slots_day.get(d, 0) + trial_study.get(d, 0)) // 4), s0))
            if not cands:
                fit_all = False
                break
            best_key = min(k[:2] for k, _ in cands)
            top = [s0 for k, s0 in cands if k[:2] == best_key]
            chosen = rng.choice(top)
            trial.place_block(chosen, need, ht.task_id, ht.title)
            if shock_extra > 0:
                trial_guards.update(range(chosen + need, min(h_slots, chosen + need + shock_extra)))
            d = chosen // SLOTS_PER_DAY
            trial_study[d] = trial_study.get(d, 0) + need
            blk = BaseScheduler.build_schedule_block(
                chunk=BaseScheduler.split_task_into_chunks(ht, week_start_iso=week_start)[0],
                start_slot=chosen,
                reason_text="Fuzz Witness Habit",
                reason_codes=[],
                week_start_iso=week_start,
                state="ACCEPTED",
            )
            placed_h.append(blk)

        if fit_all:
            for blk in placed_h:
                span = blk.end_slot - blk.start_slot
                witness_grid.place_block(blk.start_slot, span, blk.task_id, blk.title)
                if (blk.cognitive_load or 1) >= 2:
                    l2_starts.add(blk.start_slot)
                    l2_ends.add(blk.end_slot)
            day_study_slots.update(trial_study)
            shock_guard_slots.update(trial_guards)
            kept_habits.append(hab)
            habit_blocks.extend(placed_h)

    profile.personal_habits = kept_habits
    return habit_blocks


def _make_candidate_task(
    rng: random.Random,
    idx: int,
    h_days: int,
    tier: str,
    allow_heavy: bool = True,
    forced_splittable_long: bool = False,
    desired_raw_slots: Optional[int] = None,
) -> Task:
    """Create a deadline Task skeleton tuned to horizon & desired chunk density."""
    if desired_raw_slots is not None and desired_raw_slots >= 8:
        cat = rng.choice(["PROJECT", "EXAM", "ASSIGNMENT"]) if allow_heavy else rng.choice(["ASSIGNMENT", "DEADLINE"])
        choices = [m for m in [90, 120, 150, 180, 210, 240] if abs(m // 15 - desired_raw_slots) <= 6]
        dur = rng.choice(choices or [120, 150, 180, 240])
        load = (3 if cat in ("EXAM", "PROJECT") and rng.random() < 0.55 else rng.choice([1, 2])) if allow_heavy else rng.choice([1, 2])
        prio = rng.choice([1, 2, 4, 5]) if tier == "OVERLOAD" else rng.randint(1, 5)
        splittable = True
        max_chunk = rng.choice([60, 75, 90])
    elif forced_splittable_long:
        cat = rng.choice(["PROJECT", "EXAM", "ASSIGNMENT"])
        dur = rng.choice([120, 150, 180, 240] if h_days == 14 else [90, 120, 150, 180])
        load = rng.choice([1, 2]) if not allow_heavy else rng.choice([1, 2, 2, 3])
        prio = rng.randint(1, 5)
        splittable = True
        max_chunk = rng.choice([60, 90])
    else:
        cat = rng.choice(CATEGORIES) if allow_heavy else rng.choice(["ASSIGNMENT", "DEADLINE"])
        if h_days == 14:
            if tier == "LOOSE":
                dur = rng.choice([45, 60, 90, 120, 150, 180])
            elif tier == "TIGHT":
                dur = rng.choice([75, 90, 120, 150, 180, 240])
            else:
                dur = rng.choice([90, 120, 150, 180])
        else:
            if tier == "LOOSE":
                dur = rng.choice([30, 45, 60, 75, 90])
            elif tier == "TIGHT":
                dur = rng.choice([60, 75, 90, 120, 150, 180])
            else:
                dur = rng.choice([90, 120, 150, 180])

        prio = rng.choice([1, 2, 4, 5]) if tier == "OVERLOAD" else rng.randint(1, 5)
        if allow_heavy:
            load = 3 if (cat in ("EXAM", "PROJECT") and rng.random() < 0.65) else rng.choice([1, 2, 3])
        else:
            load = rng.choice([1, 2])
        splittable = (dur >= 120) or (dur >= 90 and rng.random() < 0.75) or (rng.random() < 0.55)
        max_chunk = rng.choice([60, 90]) if splittable else 120

    rhythm = "FLOW" if (load == 3 and rng.random() < 0.5) else ("LIGHT" if load == 1 else "BALANCED")
    end_d_label = DAYS_14[h_days - 1]
    return Task(
        task_id=f"FZ_T{idx}",
        title=rng.choice(TASK_TITLES_BY_CAT[cat]) + f" #{idx}",
        duration_min=dur,
        deadline_day=end_d_label,
        deadline_time="23:59",
        priority=prio,
        cognitive_load=load,
        category=cat,
        preferred_window=rng.choice(["MORNING", "AFTERNOON", "EVENING", "ANYTIME"]),
        work_rhythm=rhythm,
        is_splittable=splittable,
        min_chunk_min=45,
        max_chunk_min=max_chunk,
    )


def _try_carve_task_on_witness(
    rng: random.Random,
    profile: CommitmentsProfile,
    raw_task: Task,
    witness_grid: TimeGridManager,
    now_slot: int,
    h_slots: int,
    rest_slots: Set[int],
    class_slots: Set[int],
    long_class_ends: Set[int],
    meal_spans: List[Tuple[int, int]],
    class_slots_day: Dict[int, int],
    day_study_slots: Dict[int, int],
    day_heavy_count: Dict[int, int],
    day_heavy_spans: Dict[int, List[Tuple[int, int]]],
    l2_starts: Set[int],
    l2_ends: Set[int],
    shock_guard_slots: Set[int],
    strict_ergonomic: bool = False,
    day_block_spans: Optional[Dict[int, List[Tuple[int, int, str, str]]]] = None,
) -> Optional[Tuple[List[ScheduleBlock], int]]:
    """
    Attempt to carve all buffered chunks of `raw_task` onto `witness_grid`.
    When `strict_ergonomic=True` (used for `LOOSE`), enforces biological, break, daily-cap,
    meal-boundary, streak, and +25% shock margins cleanly so the witness demonstrates HIGH_PRODUCTIVITY.
    """
    week_start = profile.planning_week_start
    prep_task = ScheduleController.apply_estimate_buffer(profile, [raw_task])[0]
    total_planned_min = prep_task.get_planned_duration_min()
    chunks = BaseScheduler.split_task_into_chunks(prep_task, week_start_iso=week_start)
    energy_prof = profile.get_energy_profile()
    load = raw_task.cognitive_load or 2

    trial_grid = witness_grid.clone()
    trial_study = dict(day_study_slots)
    trial_heavy = dict(day_heavy_count)
    trial_heavy_spans: Dict[int, List[Tuple[int, int]]] = {d: list(sp) for d, sp in day_heavy_spans.items()}
    trial_l2_starts = set(l2_starts)
    trial_l2_ends = set(l2_ends)
    trial_guards = set(shock_guard_slots)
    trial_day_blocks: Dict[int, List[Tuple[int, int, str, str]]] = (
        {d: list(sp) for d, sp in day_block_spans.items()} if day_block_spans is not None else {}
    )
    placed_blocks: List[ScheduleBlock] = []
    min_start = now_slot
    last_shock_extra = 0

    for c_idx, ch in enumerate(chunks):
        span = ch.duration_slots
        shock25_extra = _chunk_shock25_extra(raw_task.duration_min, total_planned_min, ch.duration_min, span)
        rem_after = sum(rem.duration_slots for rem in chunks[c_idx + 1:])
        search_end = h_slots - rem_after - (shock25_extra if c_idx == len(chunks) - 1 and strict_ergonomic else 0)
        if min_start + span > search_end:
            return None

        candidates: List[Tuple[Tuple[int, int, int, int, int, int, int], int]] = []
        for iv_s, iv_l in trial_grid.get_free_intervals(start_from=min_start, up_to=search_end):
            if iv_l < span:
                continue
            cand_starts = set(_sample_interval_positions(rng, iv_s, iv_l, span))
            if load == 3 and iv_l > span:
                for p_s in range(iv_s, iv_s + iv_l - span + 1):
                    if all(energy_prof.level_for_slot(s) == 3 for s in range(p_s, p_s + span)):
                        cand_starts.add(p_s)
                        break

            for s0 in sorted(cand_starts):
                e0 = s0 + span
                d = s0 // SLOTS_PER_DAY
                rest_bad = 1 if any(s in rest_slots for s in range(s0, e0)) else 0
                after_heavy_blocked = 1 if (
                    load == 3
                    and e0 < h_slots
                    and (trial_grid.grid[e0].startswith(TimeGridManager.STATE_BLOCK) or e0 in class_slots)
                ) else 0
                post_cls_bad = 1 if (load == 3 and s0 in long_class_ends) else 0
                off_peak_bad = 1 if (load == 3 and any(energy_prof.level_for_slot(s) == 1 for s in range(s0, e0))) else 0
                not_peak_bad = 1 if (load == 3 and any(energy_prof.level_for_slot(s) < 3 for s in range(s0, e0))) else 0
                heavy_cap_bad = 1 if (load == 3 and trial_heavy.get(d, 0) >= 2) else 0
                daily_cap_bad = 1 if (class_slots_day.get(d, 0) + trial_study.get(d, 0) + span > 36) else 0
                adj_heavy_bad = 1 if (
                    load == 3 and any(s0 <= he + 1 and hs <= e0 + 1 for hs, he in trial_heavy_spans.get(d, []))
                ) else 0
                streak_l2_bad = 1 if (load >= 2 and (s0 in trial_l2_ends or e0 in trial_l2_starts)) else 0
                meal_l2_bad = 1 if (
                    load >= 2
                    and any((e0 == ms and me in trial_l2_starts) or (s0 == me and ms in trial_l2_ends) for ms, me in meal_spans)
                ) else 0
                shock_bad = 0
                if shock25_extra > 0 and (e0 + shock25_extra > h_slots or not trial_grid.is_range_free(e0, shock25_extra)):
                    shock_bad = 1
                elif any(s in trial_guards for s in range(s0, min(h_slots, e0 + shock25_extra))):
                    shock_bad = 1

                if strict_ergonomic and (
                    off_peak_bad
                    or heavy_cap_bad
                    or daily_cap_bad
                    or rest_bad
                    or post_cls_bad
                    or after_heavy_blocked
                    or adj_heavy_bad
                    or streak_l2_bad
                    or meal_l2_bad
                    or shock_bad
                ):
                    continue

                pref_bad = 1 if (
                    raw_task.preferred_window in ("MORNING", "AFTERNOON", "EVENING")
                    and _window_match_fraction(s0, span, raw_task.preferred_window) < 0.7
                ) else 0
                peak_waste_bad = 1 if (
                    strict_ergonomic
                    and load < 3
                    and any(energy_prof.level_for_slot(s) == 3 for s in range(s0, e0))
                ) else 0
                ctx_bad = 0
                if strict_ergonomic:
                    cat_u = (raw_task.category or "").upper()
                    for bs, be, bcat, btid in trial_day_blocks.get(d, []):
                        if btid != prep_task.task_id and bcat != cat_u:
                            gap_b = s0 - be if s0 >= be else bs - e0
                            if 0 <= gap_b <= 2:
                                ctx_bad = 1
                                break
                day_load_bucket = (class_slots_day.get(d, 0) + trial_study.get(d, 0)) // 4
                score = (
                    off_peak_bad + heavy_cap_bad + shock_bad,
                    rest_bad + post_cls_bad + after_heavy_blocked,
                    daily_cap_bad + adj_heavy_bad + streak_l2_bad + meal_l2_bad,
                    not_peak_bad + ctx_bad,
                    pref_bad,
                    peak_waste_bad,
                    day_load_bucket,
                    d if (strict_ergonomic and load == 3) else 0,
                )
                candidates.append((score, s0))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        best_tier = candidates[0][0][:5] if strict_ergonomic else candidates[0][0][:3]
        top_pool = [s0 for sc, s0 in candidates if sc[: len(best_tier)] == best_tier][:8]
        chosen_s = rng.choice(top_pool)
        chosen_e = chosen_s + span

        trial_grid.place_block(chosen_s, span, prep_task.task_id, prep_task.title)
        d = chosen_s // SLOTS_PER_DAY
        trial_study[d] = trial_study.get(d, 0) + span
        trial_day_blocks.setdefault(d, []).append((chosen_s, chosen_e, (raw_task.category or "").upper(), prep_task.task_id))
        if load == 3:
            trial_heavy[d] = trial_heavy.get(d, 0) + 1
            trial_heavy_spans.setdefault(d, []).append((chosen_s, chosen_e))
        if load >= 2:
            trial_l2_starts.add(chosen_s)
            trial_l2_ends.add(chosen_e)
        if shock25_extra > 0:
            trial_guards.update(range(chosen_e, min(h_slots, chosen_e + shock25_extra)))
        last_shock_extra = shock25_extra

        blk = BaseScheduler.build_schedule_block(
            chunk=ch,
            start_slot=chosen_s,
            reason_text="Fuzz Witness Task",
            reason_codes=[],
            week_start_iso=week_start,
            state="ACCEPTED",
        )
        placed_blocks.append(blk)
        gap_next = max(1 if load == 3 else rng.choice([0, 1, 2]), shock25_extra if strict_ergonomic else 0)
        min_start = chosen_e + gap_next

    # Commit onto live witness state
    for blk in placed_blocks:
        witness_grid.place_block(blk.start_slot, blk.end_slot - blk.start_slot, blk.task_id, blk.title)
        if load == 3:
            if blk.end_slot < h_slots:
                rest_slots.add(blk.end_slot)
            if blk.start_slot > now_slot:
                rest_slots.add(blk.start_slot - 1)
    day_study_slots.update(trial_study)
    day_heavy_count.update(trial_heavy)
    day_heavy_spans.clear()
    day_heavy_spans.update(trial_heavy_spans)
    l2_starts.update(trial_l2_starts)
    l2_ends.update(trial_l2_ends)
    shock_guard_slots.update(trial_guards)
    if day_block_spans is not None:
        day_block_spans.clear()
        day_block_spans.update(trial_day_blocks)
    return placed_blocks, last_shock_extra


def _derive_constraints_from_witness(
    rng: random.Random,
    profile: CommitmentsProfile,
    tasks: List[Task],
    witness_blocks_by_task: Dict[str, List[ScheduleBlock]],
    witness_shock_tail: Dict[str, int],
    habit_blocks: List[ScheduleBlock],
    tier: str,
) -> Tuple[List[Task], List[ScheduleBlock], List[ScheduleBlock]]:
    """Derive guaranteed-feasible deadlines, DAG edges, `start_after`, and 1 PINNED block from witness."""
    week_start = profile.planning_week_start
    now_slot = BaseScheduler.resolve_now_slot(profile)
    h_days = profile.horizon_days
    h_slots = h_days * SLOTS_PER_DAY

    task_span: Dict[str, Tuple[int, int]] = {}
    task_deadlines: Dict[str, int] = {}
    for t in tasks:
        tbs = witness_blocks_by_task[t.task_id]
        first_s = min(b.start_slot for b in tbs)
        last_e = max(b.end_slot for b in tbs)
        task_span[t.task_id] = (first_s, last_e)
        needed_shock_e = min(h_slots, last_e + witness_shock_tail.get(t.task_id, 0))
        req_end = needed_shock_e if tier == "LOOSE" else last_e

        min_d_idx = max(1 if now_slot < 96 else 0, (req_end - 1) // SLOTS_PER_DAY)
        if tier == "LOOSE":
            slack_days = rng.choices([2, 3, 4], weights=[40, 35, 25])[0]
        else:  # TIGHT / OVERLOAD core
            slack_days = rng.choices([0, 1, 2], weights=[40, 45, 15])[0]
        d_idx = min(h_days - 1, min_d_idx + slack_days)
        d_idx = max(1, d_idx) if h_days >= 2 else d_idx
        d_day = DAYS_14[d_idx]

        cand_times = [
            tm
            for tm in ["18:00", "21:00", "22:00", "23:59"]
            if day_time_to_slot(d_day, tm, is_end_or_deadline=True) >= req_end
        ]
        d_time = rng.choice(cand_times) if cand_times else "23:59"
        t.deadline_day = d_day
        t.deadline_time = d_time
        d_slot = day_time_to_slot(d_day, d_time, is_end_or_deadline=True)
        task_deadlines[t.task_id] = d_slot
        d_str = t.format_deadline_label(week_start_iso=week_start)
        witness_blocks_by_task[t.task_id] = [
            b.model_copy(update={"deadline_slot": d_slot, "deadline_str": d_str}) for b in tbs
        ]

        # Optional start_after cleanly <= first_start and >= now_slot
        if first_s >= now_slot + 16 and rng.random() < 0.20:
            raw_sa = rng.randint(now_slot + 4, first_s - 4)
            sa_slot = max(now_slot, (raw_sa // 4) * 4)
            if sa_slot <= first_s:
                d_s, t_s = slot_to_day_time(sa_slot, is_end_time=False)
                t.start_after = f"{d_s} {t_s}"

    # Topological-by-Witness DAG edges: parent.witness_end <= child.witness_start & parent_dl <= child_dl
    by_witness_end = sorted(tasks, key=lambda t: (task_span[t.task_id][1], task_span[t.task_id][0]))
    for i in range(1, len(by_witness_end)):
        if rng.random() < 0.24:
            child = by_witness_end[i]
            child_start, _ = task_span[child.task_id]
            child_dl = task_deadlines[child.task_id]
            parent_cands = [
                by_witness_end[j]
                for j in range(i)
                if task_span[by_witness_end[j].task_id][1] <= child_start
                and task_deadlines[by_witness_end[j].task_id] <= child_dl
            ]
            if parent_cands:
                parent = rng.choice(parent_cands)
                child.depends_on = [parent.task_id]

    # Optional 1 PINNED block upgraded directly from a single-chunk witness task
    pinned: List[ScheduleBlock] = []
    if rng.random() < 0.35:
        pin_cands = [
            t
            for t in tasks
            if not t.is_splittable
            and not t.depends_on
            and t.start_after is None
            and len(witness_blocks_by_task[t.task_id]) == 1
            and (witness_blocks_by_task[t.task_id][0].end_slot - witness_blocks_by_task[t.task_id][0].start_slot) <= 6
            and witness_blocks_by_task[t.task_id][0].start_slot >= now_slot
        ]
        if pin_cands:
            chosen_t = rng.choice(pin_cands)
            wb = witness_blocks_by_task[chosen_t.task_id][0]
            pin_blk = wb.model_copy(update={"block_id": f"{chosen_t.task_id}_PIN1", "state": "PINNED"})
            pinned.append(pin_blk)
            witness_blocks_by_task[chosen_t.task_id] = [pin_blk]

    all_witness = list(habit_blocks)
    for tbs in witness_blocks_by_task.values():
        all_witness.extend(tbs)
    all_witness.sort(key=lambda b: (b.start_slot, b.end_slot))

    shuffled_tasks = list(tasks)
    rng.shuffle(shuffled_tasks)
    return shuffled_tasks, pinned, all_witness


class FuzzGenerator:
    """Procedural infinite random test generator parameterized by any integer seed."""

    @staticmethod
    def generate(seed: int, tier: Optional[str] = None) -> GeneratedCaseBundle:
        rng = random.Random(seed)
        eff_tier = (tier or rng.choices(["LOOSE", "TIGHT", "OVERLOAD"], weights=[45, 35, 20])[0]).upper()
        if eff_tier not in ("LOOSE", "TIGHT", "OVERLOAD"):
            raise ValueError(f"Unsupported fuzz tier: {tier}")

        profile, archetype, has_asym = _build_archetype_profile(rng, seed, eff_tier)
        now_slot = BaseScheduler.resolve_now_slot(profile)
        h_days = profile.horizon_days
        h_slots = h_days * SLOTS_PER_DAY
        is_overload = (eff_tier == "OVERLOAD")

        witness_grid = build_base_grid(profile, h_slots)
        usable_free_init = witness_grid.count_free_slots_in_range(start_from=now_slot, up_to=h_slots)
        class_slots_day, class_slots, long_class_ends, meal_spans = _extract_profile_day_context(profile, h_slots)

        day_study_slots: Dict[int, int] = {}
        day_heavy_count: Dict[int, int] = {}
        day_heavy_spans: Dict[int, List[Tuple[int, int]]] = {}
        day_block_spans: Dict[int, List[Tuple[int, int, str, str]]] = {}
        rest_slots: Set[int] = set()
        l2_starts: Set[int] = set()
        l2_ends: Set[int] = set()
        shock_guard_slots: Set[int] = set()

        habit_blocks = _place_habits_on_witness(
            rng,
            profile,
            witness_grid,
            now_slot,
            h_slots,
            class_slots_day,
            day_study_slots,
            l2_starts,
            l2_ends,
            shock_guard_slots,
            strict_ergonomic=(eff_tier == "LOOSE"),
        )
        for hb in habit_blocks:
            day_block_spans.setdefault(hb.start_slot // SLOTS_PER_DAY, []).append(
                (hb.start_slot, hb.end_slot, (hb.category or "HABIT").upper(), hb.task_id)
            )
        placed_slots = sum(b.end_slot - b.start_slot for b in habit_blocks)

        if eff_tier == "LOOSE":
            target_min, target_max = 0.25, 0.56
            rho_goal = rng.uniform(0.28, 0.48)
        elif eff_tier == "TIGHT":
            target_min, target_max = 0.65, 0.90
            rho_goal = rng.uniform(0.68, 0.85)
        else:
            target_min, target_max = 1.22, 1.55
            rho_goal = rng.uniform(0.68, 0.80)

        max_tasks = (
            min(34, max(22, round(usable_free_init / 18.0)))
            if h_days == 14
            else min(24, max(16, round(usable_free_init / 13.0)))
        )
        goal_slots = int(round(rho_goal * usable_free_init))
        ceiling_slots = int(0.88 * usable_free_init) if is_overload else int(target_max * usable_free_init)
        max_heavy_chunks = (
            min(int(1.2 * h_days), 8 if h_days == 7 else 14)
            if eff_tier == "LOOSE"
            else int(1.6 * h_days)
        )

        tasks: List[Task] = []
        witness_by_task: Dict[str, List[ScheduleBlock]] = {}
        witness_shock_tail: Dict[str, int] = {}
        idx_counter = 1
        heavy_chunks_placed = 0

        # Phase 1: Carve feasible witness core up to rho_goal / max_tasks
        for attempt in range(max_tasks * 4):
            if len(tasks) >= max_tasks:
                break
            if placed_slots >= goal_slots and len(tasks) >= (5 if eff_tier == "LOOSE" else 7):
                break
            rem_tasks = max(1, max_tasks - len(tasks))
            rem_slots_need = max(0, goal_slots - placed_slots)
            avg_need_planned = rem_slots_need / float(rem_tasks)
            desired_raw = int(round(avg_need_planned / 1.15)) if (eff_tier in ("TIGHT", "OVERLOAD") and avg_need_planned >= 7.0) else None
            need_long = (eff_tier in ("TIGHT", "OVERLOAD") and (h_days == 14 or attempt % 2 == 0) and avg_need_planned >= 6.0)
            cand = _make_candidate_task(
                rng,
                idx_counter,
                h_days,
                "TIGHT" if is_overload else eff_tier,
                allow_heavy=(heavy_chunks_placed < max_heavy_chunks),
                forced_splittable_long=need_long,
                desired_raw_slots=desired_raw,
            )
            idx_counter += 1
            cand_prep = ScheduleController.apply_estimate_buffer(profile, [cand])[0]
            need_slots = cand_prep.get_planned_slots()
            if placed_slots + need_slots > ceiling_slots:
                continue

            carved = _try_carve_task_on_witness(
                rng,
                profile,
                cand,
                witness_grid,
                now_slot,
                h_slots,
                rest_slots,
                class_slots,
                long_class_ends,
                meal_spans,
                class_slots_day,
                day_study_slots,
                day_heavy_count,
                day_heavy_spans,
                l2_starts,
                l2_ends,
                shock_guard_slots,
                strict_ergonomic=(eff_tier == "LOOSE"),
                day_block_spans=day_block_spans,
            )
            if carved is not None:
                c_blocks, tail_sh = carved
                tasks.append(cand)
                witness_by_task[cand.task_id] = c_blocks
                witness_shock_tail[cand.task_id] = tail_sh
                placed_slots += sum(b.end_slot - b.start_slot for b in c_blocks)
                if cand.cognitive_load == 3:
                    heavy_chunks_placed += len(c_blocks)

        # Fallback only if LOOSE ultra-strict ergonomic pass fell short of floor (rare extreme class schedules)
        if eff_tier == "LOOSE":
            for _ in range(15):
                _, _, _, rt_l, _, _ = _compute_rho(profile, tasks, [], require_chunk_fit=False)
                if rt_l >= 0.22 and len(tasks) >= 5:
                    break
                cand = _make_candidate_task(rng, idx_counter, h_days, "LOOSE", allow_heavy=False)
                idx_counter += 1
                cand_prep = ScheduleController.apply_estimate_buffer(profile, [cand])[0]
                if placed_slots + cand_prep.get_planned_slots() > ceiling_slots:
                    continue
                carved = _try_carve_task_on_witness(
                    rng,
                    profile,
                    cand,
                    witness_grid,
                    now_slot,
                    h_slots,
                    rest_slots,
                    class_slots,
                    long_class_ends,
                    meal_spans,
                    class_slots_day,
                    day_study_slots,
                    day_heavy_count,
                    day_heavy_spans,
                    l2_starts,
                    l2_ends,
                    shock_guard_slots,
                    strict_ergonomic=False,
                )
                if carved is not None:
                    c_blocks, tail_sh = carved
                    tasks.append(cand)
                    witness_by_task[cand.task_id] = c_blocks
                    witness_shock_tail[cand.task_id] = tail_sh
                    placed_slots += sum(b.end_slot - b.start_slot for b in c_blocks)

        # Phase 2: Tight dense top-up using splittable L1/L2 tasks if below target_min
        if not is_overload and eff_tier == "TIGHT":
            for _ in range(30):
                _, _, _, rt, _, _ = _compute_rho(profile, tasks, [], require_chunk_fit=False)
                if rt >= target_min or len(tasks) >= max_tasks + 8:
                    break
                cand = _make_candidate_task(
                    rng,
                    idx_counter,
                    h_days,
                    eff_tier,
                    allow_heavy=False,
                    forced_splittable_long=True,
                    desired_raw_slots=12 if h_days == 14 else 10,
                )
                idx_counter += 1
                cand_prep = ScheduleController.apply_estimate_buffer(profile, [cand])[0]
                if placed_slots + cand_prep.get_planned_slots() > int(target_max * usable_free_init):
                    continue
                carved = _try_carve_task_on_witness(
                    rng,
                    profile,
                    cand,
                    witness_grid,
                    now_slot,
                    h_slots,
                    rest_slots,
                    class_slots,
                    long_class_ends,
                    meal_spans,
                    class_slots_day,
                    day_study_slots,
                    day_heavy_count,
                    day_heavy_spans,
                    l2_starts,
                    l2_ends,
                    shock_guard_slots,
                    strict_ergonomic=False,
                )
                if carved is not None:
                    c_blocks, tail_sh = carved
                    tasks.append(cand)
                    witness_by_task[cand.task_id] = c_blocks
                    witness_shock_tail[cand.task_id] = tail_sh
                    placed_slots += sum(b.end_slot - b.start_slot for b in c_blocks)

        # Phase 3: Derive constraints cleanly from witness
        tasks, pinned, all_witness = _derive_constraints_from_witness(
            rng, profile, tasks, witness_by_task, witness_shock_tail, habit_blocks, eff_tier
        )

        # Phase 4: For OVERLOAD, keep feasible base tasks and add tight early-deadline tasks until overload proven
        final_witness: Optional[List[ScheduleBlock]] = all_witness
        witness_verified = True
        if is_overload:
            final_witness = None
            witness_verified = False
            pinned = []
            max_ov_day = min(6, h_days - 1) if h_days == 14 else min(3, h_days - 1)
            for _ in range(60):
                _, demand_now, _, _, rho_dl, has_shortage = _compute_rho(profile, tasks, [], require_chunk_fit=False)
                if rho_dl >= target_min and has_shortage:
                    break
                ov_t = _make_candidate_task(
                    rng,
                    idx_counter,
                    h_days,
                    "OVERLOAD",
                    allow_heavy=True,
                    forced_splittable_long=True,
                    desired_raw_slots=12,
                )
                idx_counter += 1
                forced_d = rng.randint(1, max_ov_day)
                ov_t.deadline_day = DAYS_14[forced_d]
                ov_t.deadline_time = rng.choice(["18:00", "21:00", "23:59"])
                tasks.append(ov_t)
            rng.shuffle(tasks)

        _, demand, usable_free, rho_tot, rho_dl, _ = _compute_rho(
            profile, tasks, pinned, require_chunk_fit=False
        )
        reported_tier = eff_tier
        if eff_tier == "TIGHT" and rho_tot < 0.60:
            reported_tier = "LOOSE"

        regime_map = {
            "LOOSE": RegimeName.LOOSE_FEASIBLE,
            "TIGHT": RegimeName.TIGHT_DEADLINE_CLUSTER,
            "OVERLOAD": RegimeName.OVERLOAD_INFEASIBLE,
        }
        meta = GeneratedTestMetadata(
            seed=seed,
            regime=regime_map[reported_tier],
            chronotype=profile.focus_preference or "BALANCED",
            horizon_days=h_days,
            has_asymmetric_classes=has_asym,
            buffer_mode=profile.buffer_mode,
            estimate_habit=profile.estimate_habit,
            planned_demand_slots=demand,
            usable_free_slots=usable_free,
            tightness_rho=rho_tot,
            tightness_rho_deadline=rho_dl,
            task_count=len(tasks),
            habit_count=len(profile.personal_habits),
            pinned_count=len(pinned),
            notes=f"Infinite Procedural Fuzz v2 [{reported_tier} | {archetype}] seed={seed}.",
            is_fuzz=True,
            fuzz_tier=reported_tier,
            persona_archetype=archetype,
            witness_verified=witness_verified,
        )
        return GeneratedCaseBundle(
            profile=profile,
            tasks=tasks,
            pinned_blocks=pinned,
            metadata=meta,
            witness_blocks=final_witness,
        )
