"""
Tier 1: The 4 Core Productivity Pillars (P1..P4) grounded strictly in the 8 full-text papers.

Implements:
  - P1: Effective Value Delivery & Anti-Procrastination Onset Timeliness
        (Vieira / Shafaei & Brunn / Portougal & Robb; Schaerf; Svartdal et al.; Gombolay strategic idling)
  - P2: Cognitive Power, Recovery Breaks (>10 min) & Circular Social Jetlag
        (Schaerf / Junginger / De Werra; Smarr & Schirmer; Albulescu et al.; Svartdal / Kroese)
  - P3: Sustainable Pacing, Weekly Dispersion, Clustering & Context-Switching
        (Schaerf / Colorni / Corne / Carter / Laporte; Vieira; Gombolay Ch. 6)
  - P4: Buffer Adequacy, Simulated Duration-Shock Survival (+25%/+50% on raw duration) & Plan Stability
        (Vieira / Mehta & Uzsoy / Daniels & Kouvelis / O'Donovan / Cowling / Wu / Bean; Fox et al.; Myers)
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Dict, List, Optional, Set, Tuple

from schedule_testing_system.schemas import (
    EvaluationConfig,
    GateContextMetrics,
    Pillar1ValueTimeliness,
    Pillar2CognitiveBiology,
    Pillar3SustainablePacing,
    Pillar4RobustnessStability,
    PostRepairStabilityMetrics,
    ShockScenarioMetrics,
)
from schedule_testing_system.sut_adapter import (
    BaseScheduler,
    CircadianEnergyProfile,
    CommitmentsProfile,
    MINUTES_PER_SLOT,
    SLOTS_PER_DAY,
    ScheduleBlock,
    ScheduleOutput,
    Task,
    TimeGridManager,
    build_base_grid,
    calculate_schedule_stability,
    parse_day_to_index,
    parse_time_to_slot_offset,
)

CLASS_CATEGORIES = {"ACADEMIC_CLASS", "CLASS", "LAB", "LECTURE"}


def _deadline_or_horizon(task: Task, week_start_iso: str, horizon_slots: int) -> int:
    raw = task.resolve_deadline_slot(week_start_iso=week_start_iso)
    return min(horizon_slots, raw if raw is not None else horizon_slots)


def _effective_load(block: ScheduleBlock, task_map: Dict[str, Task]) -> Optional[int]:
    if block.cognitive_load is not None:
        return block.cognitive_load
    t = task_map.get(block.task_id)
    return t.cognitive_load if t else None


def _effective_rhythm(block: ScheduleBlock, task_map: Dict[str, Task]) -> Optional[str]:
    t = task_map.get(block.task_id)
    return t.work_rhythm if t else None


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


def _avg_energy_over_span(energy_prof: CircadianEnergyProfile, start_slot: int, length_slots: int) -> float:
    span = max(1, length_slots)
    return sum(energy_prof.level_for_slot(s) for s in range(start_slot, start_slot + span)) / float(span)


def _build_schedule_grid(base_grid: TimeGridManager, blocks: List[ScheduleBlock]) -> TimeGridManager:
    """Reconstruct schedule occupancy safely on a defensive clone of base_grid."""
    g = base_grid.clone()
    for b in blocks:
        length = b.end_slot - b.start_slot
        if length > 0 and b.start_slot >= 0 and b.end_slot <= g.total_slots and g.is_range_free(b.start_slot, length):
            g.place_block(b.start_slot, length, b.task_id, b.title)
    return g


def _grid_with_block_freed(
    base_grid: TimeGridManager,
    all_blocks: List[ScheduleBlock],
    target_block: ScheduleBlock,
) -> TimeGridManager:
    """Clone base_grid and place every block EXCEPT `target_block` to inspect counterfactual availability."""
    g = base_grid.clone()
    for b in all_blocks:
        if b.block_id == target_block.block_id and b.start_slot == target_block.start_slot:
            continue
        length = b.end_slot - b.start_slot
        if length > 0 and b.start_slot >= 0 and b.end_slot <= g.total_slots and g.is_range_free(b.start_slot, length):
            g.place_block(b.start_slot, length, b.task_id, b.title)
    return g


def _resolve_fixed_event_ranges(
    profile: CommitmentsProfile,
    horizon_slots: int,
    categories: Optional[Set[str]] = None,
) -> List[Tuple[int, int, str]]:
    """Expand FixedEvent definitions into concrete [start_slot, end_slot, category_upper) instances reusing TimeGridManager."""
    grid_helper = TimeGridManager(total_slots=horizon_slots)
    instances: List[Tuple[int, int, str]] = []
    for ev in profile.fixed_events:
        cat = (ev.category or "").strip().upper()
        if categories is not None and cat not in categories:
            continue
        start_off = parse_time_to_slot_offset(ev.start_time, is_end_or_deadline=False)
        end_off = parse_time_to_slot_offset(ev.end_time, is_end_or_deadline=True)
        if end_off == start_off:
            continue

        day_indices = grid_helper._resolve_event_days(ev.day_of_week)
        for d_idx in sorted(set(day_indices)):
            if d_idx * SLOTS_PER_DAY >= horizon_slots:
                continue
            base = d_idx * SLOTS_PER_DAY
            if end_off > start_off:
                s0, s1 = base + start_off, min(horizon_slots, base + end_off)
                if s1 > s0:
                    instances.append((s0, s1, cat))
            else:
                if base + start_off < horizon_slots:
                    instances.append((base + start_off, min(horizon_slots, base + SLOTS_PER_DAY), cat))
                nxt_base = (d_idx + 1) * SLOTS_PER_DAY
                if nxt_base < horizon_slots:
                    instances.append((nxt_base, min(horizon_slots, nxt_base + end_off), cat))
    return instances


def evaluate_p1(
    profile: CommitmentsProfile,
    prepared_tasks: List[Task],
    schedule: ScheduleOutput,
    gates: GateContextMetrics,
    base_grid: TimeGridManager,
) -> Pillar1ValueTimeliness:
    """Compute P1.1 Value Delivery & P1.2 Anti-Procrastination / Onset Timeliness."""
    week_start_iso = profile.planning_week_start
    now_slot = gates.now_slot
    horizon_slots = gates.horizon_slots
    energy_prof = profile.get_energy_profile()
    blocks = list(schedule.blocks)
    unplaced_ids = {str(u.get("task_id", "")) for u in schedule.unplaced_tasks}
    task_map: Dict[str, Task] = {t.task_id: t for t in prepared_tasks}
    past_due_ids = BaseScheduler.detect_past_due_tasks(prepared_tasks, week_start_iso=week_start_iso)

    blocks_by_task: Dict[str, List[ScheduleBlock]] = {}
    for b in blocks:
        blocks_by_task.setdefault(b.task_id, []).append(b)

    deadline_tasks: List[Task] = []
    habit_tasks: List[Task] = []
    for t in prepared_tasks:
        if t.task_id in past_due_ids:
            continue
        if t.resolve_deadline_slot(week_start_iso=week_start_iso) is not None:
            deadline_tasks.append(t)
        else:
            habit_tasks.append(t)

    ok_deadline_tasks: List[Task] = []
    missed_deadline_tasks: List[Task] = []
    slack_margins_min: List[float] = []
    task_first_start: Dict[str, int] = {}
    task_last_end: Dict[str, int] = {}

    for t in prepared_tasks:
        tb = blocks_by_task.get(t.task_id, [])
        if tb:
            task_first_start[t.task_id] = min(b.start_slot for b in tb)
            task_last_end[t.task_id] = max(b.end_slot for b in tb)

    for t in deadline_tasks:
        tb = blocks_by_task.get(t.task_id, [])
        raw_d = t.resolve_deadline_slot(week_start_iso=week_start_iso)
        d_slot = min(horizon_slots, raw_d if raw_d is not None else horizon_slots)
        placed_min = sum(b.duration_min for b in tb)
        if (
            t.task_id not in unplaced_ids
            and tb
            and placed_min >= t.get_planned_duration_min()
            and max(b.end_slot for b in tb) <= d_slot
        ):
            ok_deadline_tasks.append(t)
            slack_margins_min.append(float((d_slot - max(b.end_slot for b in tb)) * MINUTES_PER_SLOT))
        else:
            missed_deadline_tasks.append(t)

    prio_achieved = sum(t.priority for t in ok_deadline_tasks)
    prio_total = sum(t.priority for t in deadline_tasks)
    missed_prio = sum(t.priority for t in missed_deadline_tasks)
    value_rate_pct = round(100.0 * prio_achieved / float(prio_total), 2) if prio_total > 0 else 100.0
    unplaced_d_min = sum(t.get_planned_duration_min() for t in missed_deadline_tasks)

    habit_ok = 0
    for h in habit_tasks:
        tb = blocks_by_task.get(h.task_id, [])
        if h.task_id not in unplaced_ids and tb and sum(b.duration_min for b in tb) >= h.get_planned_duration_min():
            habit_ok += 1
    habit_rate = round(100.0 * habit_ok / float(len(habit_tasks)), 2) if habit_tasks else None

    # P1.2: Onset Delay, Preparatory Margins, and Unjustified <10h Crowding
    onset_rates: List[float] = []
    heavy_onset_rates: List[float] = []
    prep_margins: List[float] = []
    wide_window_min = 0
    unjustified_last10h_min = 0
    unjustified_ids: List[str] = []
    justified_deferrals = 0

    for t in ok_deadline_tasks:
        d_slot = _deadline_or_horizon(t, week_start_iso, horizon_slots)
        sa_slot = t.resolve_start_after_slot(week_start_iso=week_start_iso)
        ready_slot = max(now_slot, sa_slot if sa_slot is not None else 0)
        for pid in t.depends_on:
            if pid in task_last_end:
                ready_slot = max(ready_slot, task_last_end[pid])
                prep_margins.append(float((d_slot - task_last_end[pid]) * MINUTES_PER_SLOT))

        window_slots = d_slot - ready_slot
        first_start = task_first_start.get(t.task_id)
        if window_slots > 0 and first_start is not None:
            delay_rate = max(0.0, (first_start - ready_slot) / float(window_slots)) * 100.0
            onset_rates.append(delay_rate)
            if t.cognitive_load == 3:
                heavy_onset_rates.append(delay_rate)

        # Howell (2006) < 10h check ONLY when available ready->deadline window > 10h (> 40 slots)
        if window_slots > 40:
            tb = sorted(blocks_by_task.get(t.task_id, []), key=lambda x: x.start_slot)
            wide_window_min += sum(b.duration_min for b in tb)
            last_10h_start = max(ready_slot, d_slot - 40)
            prev_end_cursor = ready_slot
            for b in tb:
                b_len = b.end_slot - b.start_slot
                overlap_start = max(b.start_slot, last_10h_start)
                overlap_slots = max(0, b.end_slot - overlap_start)
                earliest_b_ready = max(ready_slot, prev_end_cursor)
                prev_end_cursor = b.end_slot

                if overlap_slots == 0 or b.state in ("PINNED", "DONE"):
                    continue
                if earliest_b_ready + b_len > last_10h_start:
                    continue

                # Check counterfactual grid whether an earlier slot existed with >= energy and >= window match
                cf_grid = _grid_with_block_freed(base_grid, blocks, b)
                placed_energy = _avg_energy_over_span(energy_prof, b.start_slot, b_len)
                placed_win = _window_match_fraction(b.start_slot, b_len, t.preferred_window)

                found_unjustified_earlier = False
                for iv_start, iv_len in cf_grid.get_free_intervals(start_from=earliest_b_ready, up_to=last_10h_start):
                    if iv_len < b_len:
                        continue
                    for cand_s in range(iv_start, iv_start + iv_len - b_len + 1):
                        if cand_s >= last_10h_start:
                            break
                        cand_energy = _avg_energy_over_span(energy_prof, cand_s, b_len)
                        cand_win = _window_match_fraction(cand_s, b_len, t.preferred_window)
                        if cand_energy + 1e-9 >= placed_energy and cand_win + 1e-9 >= placed_win:
                            found_unjustified_earlier = True
                            break
                    if found_unjustified_earlier:
                        break

                if found_unjustified_earlier:
                    unjustified_last10h_min += overlap_slots * MINUTES_PER_SLOT
                    if t.task_id not in unjustified_ids:
                        unjustified_ids.append(t.task_id)
                else:
                    justified_deferrals += 1

    eligible_wide = sum(
        1
        for t in ok_deadline_tasks
        if (
            _deadline_or_horizon(t, week_start_iso, horizon_slots)
            - max(
                now_slot,
                t.resolve_start_after_slot(week_start_iso=week_start_iso) if t.resolve_start_after_slot(week_start_iso=week_start_iso) is not None else 0,
                max((task_last_end.get(p, 0) for p in t.depends_on), default=0),
            )
        )
        > 40
    )

    crowding_pct = (
        round(100.0 * unjustified_last10h_min / float(wide_window_min), 2) if wide_window_min > 0 else 0.0
    )

    return Pillar1ValueTimeliness(
        deadline_value_rate_pct=value_rate_pct,
        deadline_priority_achieved=prio_achieved,
        deadline_priority_total=prio_total,
        missed_deadline_priority=missed_prio,
        unplaced_deadline_count=len(missed_deadline_tasks),
        unplaced_deadline_min=unplaced_d_min,
        missed_deadline_task_ids=[t.task_id for t in missed_deadline_tasks],
        habit_value_rate_pct=habit_rate,
        unplaced_habit_count=len(habit_tasks) - habit_ok,
        min_slack_margin_min=min(slack_margins_min) if slack_margins_min else None,
        mean_slack_margin_min=round(sum(slack_margins_min) / float(len(slack_margins_min)), 2)
        if slack_margins_min
        else None,
        mean_onset_delay_pct=round(sum(onset_rates) / float(len(onset_rates)), 2) if onset_rates else None,
        heavy_onset_delay_pct=round(sum(heavy_onset_rates) / float(len(heavy_onset_rates)), 2)
        if heavy_onset_rates
        else None,
        min_preparatory_margin_min=min(prep_margins) if prep_margins else None,
        unjustified_last_10h_crowding_pct=crowding_pct,
        unjustified_last_10h_task_ids=unjustified_ids,
        eligible_wide_window_tasks=eligible_wide,
        justified_deferrals_count=justified_deferrals,
    )


def _compute_sleep_midpoint_slot(profile: CommitmentsProfile) -> Tuple[int, int]:
    """Return `(sleep_start_slot_in_day, sleep_midpoint_slot_in_day)` from sleep_schedule."""
    sleep = profile.sleep_schedule
    s_start = parse_time_to_slot_offset(sleep.daily_start_time, is_end_or_deadline=False)
    s_end = parse_time_to_slot_offset(sleep.daily_end_time, is_end_or_deadline=True)
    if s_start == s_end:
        return s_start, (s_start + 12) % SLOTS_PER_DAY
    if s_start > s_end:
        mid = ((s_start + s_end + SLOTS_PER_DAY) // 2) % SLOTS_PER_DAY
    else:
        mid = ((s_start + s_end) // 2) % SLOTS_PER_DAY
    return s_start, mid


def evaluate_p2(
    profile: CommitmentsProfile,
    prepared_tasks: List[Task],
    schedule: ScheduleOutput,
    gates: GateContextMetrics,
    base_grid: TimeGridManager,
) -> Pillar2CognitiveBiology:
    """Compute P2.1 Circadian Alignment, P2.2 Recovery (>10m), P2.3 Circular SJL & Phase Stability."""
    week_start_iso = profile.planning_week_start
    now_slot = gates.now_slot
    horizon_slots = gates.horizon_slots
    energy_prof = profile.get_energy_profile()
    blocks = sorted(schedule.blocks, key=lambda b: (b.start_slot, b.end_slot))
    task_map: Dict[str, Task] = {t.task_id: t for t in prepared_tasks}
    task_last_end: Dict[str, int] = {}
    for b in blocks:
        task_last_end[b.task_id] = max(task_last_end.get(b.task_id, 0), b.end_slot)

    # P2.1: Heavy peak alignment strictly for load == 3 + Preferred window + Forced Phase Advance
    heavy_slots = 0
    heavy_peak_slots = 0
    pref_slots = 0
    pref_matched_slots = 0

    is_evening_chrono = (
        str(profile.focus_preference or "").strip().upper() == "EVENING"
        or (energy_prof.evening_level > energy_prof.morning_level and energy_prof.morning_level == 1)
    )
    forced_advance_blocks: List[str] = []
    forced_advance_task_ids: List[str] = []

    for b in blocks:
        span = max(1, b.end_slot - b.start_slot)
        load = _effective_load(b, task_map)
        t_obj = task_map.get(b.task_id)

        if load == 3:
            heavy_slots += span
            for s in range(b.start_slot, b.end_slot):
                if energy_prof.level_for_slot(s) == 3:
                    heavy_peak_slots += 1

            # Check forced phase advance (Evening chronotype placed in MORNING [24,48) with energy==1)
            if is_evening_chrono and b.state not in ("PINNED", "DONE"):
                overlaps_morning_low = any(
                    24 <= (s % SLOTS_PER_DAY) < 48 and energy_prof.level_for_slot(s) == 1
                    for s in range(b.start_slot, b.end_slot)
                )
                if overlaps_morning_low and t_obj is not None:
                    d_slot = t_obj.resolve_deadline_slot(week_start_iso=week_start_iso)
                    limit_slot = min(horizon_slots, d_slot) if d_slot is not None else horizon_slots
                    sa_slot = t_obj.resolve_start_after_slot(week_start_iso=week_start_iso)
                    ready_slot = max(now_slot, sa_slot if sa_slot is not None else 0)
                    for pid in t_obj.depends_on:
                        if pid in task_last_end:
                            ready_slot = max(ready_slot, task_last_end[pid])

                    cf_grid = _grid_with_block_freed(base_grid, blocks, b)
                    has_better_later_window = False
                    for iv_start, iv_len in cf_grid.get_free_intervals(start_from=ready_slot, up_to=limit_slot):
                        if iv_len < span:
                            continue
                        for cand_s in range(iv_start, iv_start + iv_len - span + 1):
                            if any(energy_prof.level_for_slot(cs) >= 2 for cs in range(cand_s, cand_s + span)):
                                if _avg_energy_over_span(energy_prof, cand_s, span) >= 2.0:
                                    has_better_later_window = True
                                    break
                        if has_better_later_window:
                            break
                    if has_better_later_window:
                        forced_advance_blocks.append(b.block_id)
                        if b.task_id not in forced_advance_task_ids:
                            forced_advance_task_ids.append(b.task_id)

        if t_obj and t_obj.preferred_window in ("MORNING", "AFTERNOON", "EVENING"):
            pref_slots += span
            pref_matched_slots += int(round(_window_match_fraction(b.start_slot, span, t_obj.preferred_window) * span))

    heavy_peak_pct = round(100.0 * heavy_peak_slots / float(heavy_slots), 2) if heavy_slots > 0 else None
    pref_pct = round(100.0 * pref_matched_slots / float(pref_slots), 2) if pref_slots > 0 else None

    # P2.2: Albulescu > 10 min (>= 1 slot) decoupling break after heavy/FLOW/>=90m sessions
    occupied_study_slots: Set[int] = set()
    for b in blocks:
        for s in range(b.start_slot, b.end_slot):
            occupied_study_slots.add(s)

    heavy_sessions_total = 0
    heavy_sessions_recovered = 0
    missing_break_block_ids: List[str] = []
    for b in blocks:
        load = _effective_load(b, task_map)
        rhythm = _effective_rhythm(b, task_map)
        is_heavy_session = (load == 3) or (rhythm == "FLOW") or (b.duration_min >= 90)
        if not is_heavy_session:
            continue
        heavy_sessions_total += 1
        if b.end_slot >= horizon_slots or (b.end_slot not in occupied_study_slots):
            heavy_sessions_recovered += 1
        else:
            missing_break_block_ids.append(b.block_id)

    # Max uninterrupted contiguous study streak (0-gap blocks merged)
    max_streak_slots = 0
    cur_streak = 0
    prev_end = -1
    for b in blocks:
        span = max(1, b.end_slot - b.start_slot)
        if b.start_slot == prev_end:
            cur_streak += span
        else:
            cur_streak = span
        prev_end = b.end_slot
        max_streak_slots = max(max_streak_slots, cur_streak)

    recovery_rate_pct = (
        round(100.0 * heavy_sessions_recovered / float(heavy_sessions_total), 2)
        if heavy_sessions_total > 0
        else None
    )

    # P2.3: Circular Social Jetlag with Biological Day boundary & Pre-Bedtime Heavy Count
    sleep_start_tod, sleep_mid_slot = _compute_sleep_midpoint_slot(profile)
    class_instances = _resolve_fixed_event_ranges(profile, horizon_slots, categories=CLASS_CATEGORIES)

    bio_day_class_mins: Dict[int, List[int]] = {}
    bio_day_all_mins: Dict[int, List[int]] = {}
    bio_days_with_class: Set[int] = set()

    for cs, ce, _ in class_instances:
        for s in range(cs, ce):
            d_bio = (s - sleep_mid_slot) // SLOTS_PER_DAY
            m_unwrapped = (((s % SLOTS_PER_DAY) - sleep_mid_slot) % SLOTS_PER_DAY) * MINUTES_PER_SLOT
            bio_day_class_mins.setdefault(d_bio, []).append(m_unwrapped)
            bio_day_all_mins.setdefault(d_bio, []).append(m_unwrapped)
            bio_days_with_class.add(d_bio)

    for b in blocks:
        for s in range(b.start_slot, b.end_slot):
            d_bio = (s - sleep_mid_slot) // SLOTS_PER_DAY
            m_unwrapped = (((s % SLOTS_PER_DAY) - sleep_mid_slot) % SLOTS_PER_DAY) * MINUTES_PER_SLOT
            bio_day_all_mins.setdefault(d_bio, []).append(m_unwrapped)

    class_day_medians: List[float] = []
    non_class_day_medians: List[float] = []
    all_day_medians: List[float] = []
    class_day_solver_shifts: List[float] = []

    for d_bio, mins in sorted(bio_day_all_mins.items()):
        med_all = float(statistics.median(mins))
        all_day_medians.append(med_all)
        if d_bio in bio_days_with_class:
            class_day_medians.append(med_all)
            cls_mins = bio_day_class_mins.get(d_bio, [])
            if cls_mins and len(mins) > len(cls_mins):
                med_cls = float(statistics.median(cls_mins))
                class_day_solver_shifts.append(abs(med_all - med_cls))
        else:
            non_class_day_medians.append(med_all)

    sjl_minutes: Optional[float] = None
    sjl_direction = "N/A"
    sjl_exceeds_30m: Optional[bool] = None
    if class_day_medians and non_class_day_medians:
        med_cls_group = float(statistics.median(class_day_medians))
        med_non_group = float(statistics.median(non_class_day_medians))
        phi_cls = 2.0 * math.pi * (med_cls_group / 1440.0)
        phi_non = 2.0 * math.pi * (med_non_group / 1440.0)
        delta_rad = math.atan2(math.sin(phi_non - phi_cls), math.cos(phi_non - phi_cls))
        sjl_minutes = round(abs(delta_rad) / (2.0 * math.pi) * 1440.0, 2)
        if abs(delta_rad) < 1e-9:
            sjl_direction = "ALIGNED"
        elif delta_rad > 0:
            sjl_direction = "PHASE_DELAY"
        else:
            sjl_direction = "PHASE_ADVANCE"
        sjl_exceeds_30m = sjl_minutes > 30.0

    cross_day_std = round(statistics.pstdev(all_day_medians), 2) if len(all_day_medians) >= 2 else 0.0
    solver_shift = (
        round(sum(class_day_solver_shifts) / float(len(class_day_solver_shifts)), 2)
        if class_day_solver_shifts
        else None
    )

    pre_bedtime_heavy_block_ids: List[str] = []
    for b in blocks:
        if _effective_load(b, task_map) == 3:
            end_tod = b.end_slot % SLOTS_PER_DAY
            slots_before_sleep = (sleep_start_tod - end_tod) % SLOTS_PER_DAY
            if 0 <= slots_before_sleep <= 4:  # <= 60 min before daily sleep start
                pre_bedtime_heavy_block_ids.append(b.block_id)

    return Pillar2CognitiveBiology(
        has_heavy_tasks=(heavy_slots > 0),
        heavy_peak_match_pct=heavy_peak_pct,
        has_preferred_window_tasks=(pref_slots > 0),
        preferred_window_match_pct=pref_pct,
        forced_phase_advance_count=len(forced_advance_blocks),
        forced_phase_advance_blocks=forced_advance_blocks,
        forced_phase_advance_task_ids=forced_advance_task_ids,
        is_evening_chronotype=is_evening_chrono,
        heavy_sessions_total=heavy_sessions_total,
        heavy_sessions_with_gt10m_break=heavy_sessions_recovered,
        heavy_recovery_rate_pct=recovery_rate_pct,
        missing_break_block_ids=missing_break_block_ids,
        max_uninterrupted_work_min=max_streak_slots * MINUTES_PER_SLOT,
        crunch_tier_used=schedule.summary.crunch_tier_used,
        sleep_midpoint_slot=sleep_mid_slot,
        sjl_minutes=sjl_minutes,
        sjl_direction=sjl_direction,
        sjl_exceeds_30m=sjl_exceeds_30m,
        class_days_count=len(class_day_medians),
        non_class_days_count=len(non_class_day_medians),
        solver_induced_class_day_shift_min=solver_shift,
        cross_day_phase_std_min=cross_day_std,
        pre_bedtime_heavy_count=len(pre_bedtime_heavy_block_ids),
        pre_bedtime_heavy_block_ids=pre_bedtime_heavy_block_ids,
    )


def evaluate_p3(
    profile: CommitmentsProfile,
    prepared_tasks: List[Task],
    schedule: ScheduleOutput,
    gates: GateContextMetrics,
    base_grid: TimeGridManager,
) -> Pillar3SustainablePacing:
    """Compute P3.1 Weekly Load Dispersion / Utilization & P3.2 Corne/Carter/Laporte Clustering & Context Switches."""
    now_slot = gates.now_slot
    horizon_slots = gates.horizon_slots
    week_start_iso = profile.planning_week_start
    blocks = sorted(schedule.blocks, key=lambda b: (b.start_slot, b.end_slot))
    task_map: Dict[str, Task] = {t.task_id: t for t in prepared_tasks}

    # Narrow active days D_active up to max deadline if all tasks are DEADLINE-only
    has_habit = gates.habit_tasks_count > 0
    if not has_habit and gates.deadline_tasks_count > 0:
        max_d_slot = max(
            _deadline_or_horizon(t, week_start_iso, horizon_slots)
            for t in prepared_tasks
            if t.resolve_deadline_slot(week_start_iso=week_start_iso) is not None
        )
        active_end_slot = max(now_slot + 1, min(horizon_slots, max_d_slot))
    else:
        active_end_slot = horizon_slots

    start_day = now_slot // SLOTS_PER_DAY
    end_day = max(start_day, (active_end_slot - 1) // SLOTS_PER_DAY)

    daily_load_mins: List[int] = []
    daily_util_pcts: List[float] = []
    for d in range(start_day, end_day + 1):
        d_s = max(now_slot, d * SLOTS_PER_DAY)
        d_e = min(active_end_slot, (d + 1) * SLOTS_PER_DAY)
        if d_e <= d_s:
            continue
        free_slots_day = base_grid.count_free_slots_in_range(start_from=d_s, up_to=d_e)
        if free_slots_day <= 0:
            continue
        l_slots = 0
        for b in blocks:
            ov_s = max(d_s, b.start_slot)
            ov_e = min(d_e, b.end_slot)
            if ov_e > ov_s:
                l_slots += ov_e - ov_s
        l_min = l_slots * MINUTES_PER_SLOT
        daily_load_mins.append(l_min)
        daily_util_pcts.append(100.0 * l_min / float(max(15, free_slots_day * MINUTES_PER_SLOT)))

    daily_std = round(statistics.pstdev(daily_load_mins), 2) if len(daily_load_mins) >= 2 else 0.0
    daily_util_std = round(statistics.pstdev(daily_util_pcts), 2) if len(daily_util_pcts) >= 2 else 0.0

    # Awake utilization over [now_slot, horizon_slots)
    awake_slots = 0
    busy_slots = 0
    occ_blocks = {s for b in blocks for s in range(max(now_slot, b.start_slot), min(horizon_slots, b.end_slot))}
    for s in range(now_slot, horizon_slots):
        locked = base_grid._locked_mask[s]
        if locked != TimeGridManager.STATE_SLEEP:
            awake_slots += 1
            if locked.startswith(TimeGridManager.STATE_OCCUPIED) or s in occ_blocks:
                busy_slots += 1
    awake_util_pct = round(100.0 * busy_slots / float(max(1, awake_slots)), 2)

    # P3.2: Corne et al. (1993) >2 heavy/day (10), adjacent heavy (3), meal-boundary (1), context switches
    heavy_by_day: Dict[int, List[ScheduleBlock]] = {}
    for b in blocks:
        if _effective_load(b, task_map) == 3:
            heavy_by_day.setdefault(b.start_slot // SLOTS_PER_DAY, []).append(b)

    heavy_overload_days = 0
    overload_heavy_block_ids: List[str] = []
    for blist in heavy_by_day.values():
        if len(blist) > 2:
            heavy_overload_days += 1
            for b in blist:
                if b.block_id not in overload_heavy_block_ids:
                    overload_heavy_block_ids.append(b.block_id)

    adjacent_heavy_pairs = 0
    adjacent_heavy_block_ids: List[str] = []
    for blist in heavy_by_day.values():
        blist_sorted = sorted(blist, key=lambda x: x.start_slot)
        for i in range(len(blist_sorted) - 1):
            if blist_sorted[i + 1].start_slot - blist_sorted[i].end_slot <= 1:
                adjacent_heavy_pairs += 1
                for bid in (blist_sorted[i].block_id, blist_sorted[i + 1].block_id):
                    if bid not in adjacent_heavy_block_ids:
                        adjacent_heavy_block_ids.append(bid)

    # Meal-boundary offenses: BLOCK ends exactly at meal_start AND BLOCK starts exactly at meal_end
    block_ends = {b.end_slot for b in blocks}
    block_starts = {b.start_slot for b in blocks}
    meal_events = _resolve_fixed_event_ranges(profile, horizon_slots, categories={"MEAL"})
    meal_offenses = sum(1 for ms, me, _ in meal_events if ms in block_ends and me in block_starts)

    context_switches = 0
    batched_pairs = 0
    for idx in range(1, len(blocks)):
        prev_b = blocks[idx - 1]
        cur_b = blocks[idx]
        same_day = (prev_b.start_slot // SLOTS_PER_DAY) == (cur_b.start_slot // SLOTS_PER_DAY)
        gap = cur_b.start_slot - prev_b.end_slot
        if same_day and 0 <= gap <= 2:
            if (prev_b.category or "").upper() == (cur_b.category or "").upper():
                batched_pairs += 1
            else:
                context_switches += 1

    corne_penalty = 10 * heavy_overload_days + 3 * adjacent_heavy_pairs + 1 * meal_offenses

    return Pillar3SustainablePacing(
        active_days_count=len(daily_load_mins),
        daily_load_minutes=daily_load_mins,
        daily_load_std_min=daily_std,
        daily_util_std_pct=daily_util_std,
        awake_utilization_pct=awake_util_pct,
        heavy_day_overload_days=heavy_overload_days,
        overload_heavy_block_ids=overload_heavy_block_ids,
        adjacent_heavy_pairs=adjacent_heavy_pairs,
        adjacent_heavy_block_ids=adjacent_heavy_block_ids,
        meal_boundary_offenses=meal_offenses,
        corne_reference_penalty=corne_penalty,
        context_switches=context_switches,
        batched_pairs=batched_pairs,
    )


def _simulate_shock_survival(
    profile: CommitmentsProfile,
    raw_tasks: List[Task],
    prepared_tasks: List[Task],
    schedule: ScheduleOutput,
    base_grid: TimeGridManager,
    shock_pct: float,
) -> ShockScenarioMetrics:
    """
    Simulate duration overrun shock (+s%) on RAW `Task.duration_min`, preserving scheduled start_slots
    unless pushed forward sequentially by a preceding colliding block (domino cascade).
    """
    week_start_iso = profile.planning_week_start
    horizon_slots = base_grid.total_slots
    raw_map: Dict[str, Task] = {t.task_id: t for t in raw_tasks}
    prep_map: Dict[str, Task] = {t.task_id: t for t in prepared_tasks}
    unplaced_ids = {str(u.get("task_id", "")) for u in schedule.unplaced_tasks}
    blocks = sorted(schedule.blocks, key=lambda b: (b.start_slot, b.end_slot))

    overflow_blocks = 0
    absorbed_by_buffer = 0
    cascade_collisions = 0
    failed_task_ids: Set[str] = set()

    task_actual_ends: Dict[str, int] = {}
    prev_actual_end = -1
    factor = 1.0 + (shock_pct / 100.0)

    for b in blocks:
        t_raw = raw_map.get(b.task_id)
        t_prep = prep_map.get(b.task_id)
        planned_slots = max(1, b.end_slot - b.start_slot)

        if t_raw is not None and t_prep is not None:
            total_planned_min = max(MINUTES_PER_SLOT, t_prep.get_planned_duration_min())
            raw_chunk_min = t_raw.duration_min * (b.duration_min / float(total_planned_min))
            raw_base_slots = max(1, int(math.ceil(raw_chunk_min / float(MINUTES_PER_SLOT) - 1e-9)))
            shocked_slots = max(raw_base_slots, int(math.ceil((raw_chunk_min * factor) / float(MINUTES_PER_SLOT) - 1e-9)))
        else:
            raw_base_slots = planned_slots
            shocked_slots = max(planned_slots, int(math.ceil((b.duration_min * factor) / float(MINUTES_PER_SLOT) - 1e-9)))

        if shocked_slots > planned_slots:
            overflow_blocks += 1
        elif shocked_slots > raw_base_slots and shocked_slots <= planned_slots:
            absorbed_by_buffer += 1

        eff_start = b.start_slot
        if prev_actual_end > b.start_slot:
            cascade_collisions += 1
            eff_start = prev_actual_end
        eff_end = eff_start + shocked_slots

        # Check dependency delay if prerequisite finished after eff_start or already failed
        if t_prep and t_prep.depends_on:
            for pid in t_prep.depends_on:
                if pid in failed_task_ids or task_actual_ends.get(pid, 0) > eff_start:
                    cascade_collisions += 1
                    failed_task_ids.add(b.task_id)

        # Check SLEEP / OCCUPIED / horizon collision
        if eff_end > horizon_slots:
            cascade_collisions += 1
            failed_task_ids.add(b.task_id)
        else:
            for s in range(eff_start, eff_end):
                locked = base_grid._locked_mask[s]
                if locked == TimeGridManager.STATE_SLEEP or locked.startswith(TimeGridManager.STATE_OCCUPIED):
                    cascade_collisions += 1
                    failed_task_ids.add(b.task_id)
                    break

        d_slot = b.deadline_slot
        if d_slot is None and t_prep is not None:
            d_slot = t_prep.resolve_deadline_slot(week_start_iso=week_start_iso)
        if d_slot is not None and eff_end > d_slot:
            failed_task_ids.add(b.task_id)

        task_actual_ends[b.task_id] = max(task_actual_ends.get(b.task_id, 0), eff_end)
        prev_actual_end = eff_end

    # Compute survived deadline priority %
    past_due_ids = BaseScheduler.detect_past_due_tasks(prepared_tasks, week_start_iso=week_start_iso)
    deadline_tasks = [
        t
        for t in prepared_tasks
        if t.task_id not in past_due_ids and t.resolve_deadline_slot(week_start_iso=week_start_iso) is not None
    ]
    blocks_by_task: Dict[str, List[ScheduleBlock]] = {}
    for b in blocks:
        blocks_by_task.setdefault(b.task_id, []).append(b)

    total_prio = sum(t.priority for t in deadline_tasks)
    survived_prio = 0
    survived_count = 0
    failed_list: List[str] = []

    for t in deadline_tasks:
        tb = blocks_by_task.get(t.task_id, [])
        d_slot = _deadline_or_horizon(t, week_start_iso, horizon_slots)
        initially_ok = (
            t.task_id not in unplaced_ids
            and bool(tb)
            and sum(b.duration_min for b in tb) >= t.get_planned_duration_min()
            and max(b.end_slot for b in tb) <= d_slot
        )
        if initially_ok and t.task_id not in failed_task_ids:
            survived_prio += t.priority
            survived_count += 1
        else:
            failed_list.append(t.task_id)

    survived_pct = round(100.0 * survived_prio / float(total_prio), 2) if total_prio > 0 else 100.0
    return ShockScenarioMetrics(
        shock_pct=shock_pct,
        survived_priority_pct=survived_pct,
        survived_tasks_count=survived_count,
        total_deadline_tasks=len(deadline_tasks),
        overflow_blocks_count=overflow_blocks,
        absorbed_by_internal_buffer_count=absorbed_by_buffer,
        cascade_collisions_count=cascade_collisions,
        failed_task_ids=failed_list,
    )


def _evaluate_post_repair_stability(
    baseline_schedule: ScheduleOutput,
    repaired_schedule: ScheduleOutput,
    now_slot_ref: int,
    config: EvaluationConfig,
    disruption_span: Optional[Tuple[int, int]] = None,
) -> PostRepairStabilityMetrics:
    """
    Compute P4.2 stability on unexecuted plan actions (end_slot > now_slot_ref) using Fox et al. (2006)
    Def. 2 Symmetric Difference, §5.2 Eq 1st / Orig% / Diff%, and Vieira / Myers metrics.
    """
    pi0_blocks = sorted(
        [b for b in baseline_schedule.blocks if b.end_slot > now_slot_ref],
        key=lambda b: (b.start_slot, b.task_id, b.chunk_index),
    )
    pi1_blocks = sorted(
        [b for b in repaired_schedule.blocks if b.end_slot > now_slot_ref],
        key=lambda b: (b.start_slot, b.task_id, b.chunk_index),
    )

    def _to_action(b: ScheduleBlock) -> Tuple[str, int, int, int]:
        return (b.task_id, b.chunk_index, b.start_slot, b.end_slot)

    set0 = {_to_action(b) for b in pi0_blocks}
    set1 = {_to_action(b) for b in pi1_blocks}
    sym_diff = len(set1 ^ set0)  # Fox Def. 2: |pi1 \ pi0| + |pi0 \ pi1|

    # Near-term window: within configured horizon (24h = 96 slots), fallback to first 5 unexecuted blocks
    win_end = now_slot_ref + config.near_term_window_slots
    near0_blocks = [b for b in pi0_blocks if b.start_slot < win_end]
    near1_blocks = [b for b in pi1_blocks if b.start_slot < win_end]
    if len(near0_blocks) < 2 and len(pi0_blocks) > 0:
        near0_blocks = pi0_blocks[:5]
    if len(near1_blocks) < 2 and len(pi1_blocks) > 0:
        near1_blocks = pi1_blocks[:5]

    near0_set = {_to_action(b) for b in near0_blocks}
    near1_set = {_to_action(b) for b in near1_blocks}

    eq_1st: Optional[bool] = None
    if pi0_blocks and pi1_blocks:
        eq_1st = _to_action(pi0_blocks[0]) == _to_action(pi1_blocks[0])
    elif not pi0_blocks and not pi1_blocks:
        eq_1st = True
    else:
        eq_1st = False

    orig_pct = round(100.0 * len(near1_set & near0_set) / float(len(near1_set)), 2) if near1_set else None
    diff_pct = round(100.0 * len(near0_set - near1_set) / float(len(near0_set)), 2) if near0_set else None

    # Mean abs shift, moved count, sequence inversions over matched unexecuted (task_id, chunk_index)
    map0 = {(b.task_id, b.chunk_index): b for b in pi0_blocks}
    map1 = {(b.task_id, b.chunk_index): b for b in pi1_blocks}
    common_keys = sorted(set(map0.keys()) & set(map1.keys()))

    shifts_min: List[float] = []
    moved_count = 0
    for k in common_keys:
        b0, b1 = map0[k], map1[k]
        if (b0.start_slot, b0.end_slot) != (b1.start_slot, b1.end_slot):
            moved_count += 1
        shifts_min.append(abs(b1.start_slot - b0.start_slot) * float(MINUTES_PER_SLOT))

    mean_shift = round(sum(shifts_min) / float(len(shifts_min)), 2) if shifts_min else 0.0
    unplaced_from_base = len(set(map0.keys()) - set(map1.keys()))

    inversions = 0
    for i in range(len(common_keys)):
        for j in range(i + 1, len(common_keys)):
            ki, kj = common_keys[i], common_keys[j]
            s0_i, s0_j = map0[ki].start_slot, map0[kj].start_slot
            s1_i, s1_j = map1[ki].start_slot, map1[kj].start_slot
            if (s0_i < s0_j and s1_i > s1_j) or (s0_i > s0_j and s1_i < s1_j):
                inversions += 1

    d_s, d_e = disruption_span if disruption_span is not None else (-1, -1)
    stab_pct, _, _, directly_hit = calculate_schedule_stability(
        baseline_schedule.blocks,
        repaired_schedule.blocks,
        disruption_start_slot=d_s,
        disruption_end_slot=d_e,
    )
    unnecessary_flag = (disruption_span is not None) and (directly_hit == 0) and (sym_diff > 0)

    denom = max(1, len(pi0_blocks))
    disruption_ratio = (moved_count + unplaced_from_base) / float(denom)
    if disruption_ratio >= config.effort_high_min_diff_ratio:
        effort = "HIGH"
    elif disruption_ratio >= config.effort_medium_min_diff_ratio or moved_count > 0:
        effort = "MEDIUM"
    else:
        effort = "LOW"

    return PostRepairStabilityMetrics(
        now_slot_reference=now_slot_ref,
        pi0_future_actions_count=len(pi0_blocks),
        pi1_future_actions_count=len(pi1_blocks),
        symmetric_plan_difference=sym_diff,
        eq_1st=eq_1st,
        orig_pct=orig_pct,
        diff_pct=diff_pct,
        mean_abs_time_shift_min=mean_shift,
        sequence_inversions=inversions,
        moved_blocks_count=moved_count,
        unplaced_from_baseline_count=unplaced_from_base,
        unaffected_stability_pct=stab_pct,
        unnecessary_repair_flag=unnecessary_flag,
        rescheduling_effort=effort,
    )


def evaluate_p4(
    profile: CommitmentsProfile,
    raw_tasks: List[Task],
    prepared_tasks: List[Task],
    schedule: ScheduleOutput,
    gates: GateContextMetrics,
    base_grid: TimeGridManager,
    config: EvaluationConfig,
    baseline_schedule: Optional[ScheduleOutput] = None,
    disruption_span: Optional[Tuple[int, int]] = None,
    repair_now_slot: Optional[int] = None,
    completion_logs: Optional[List[Dict[str, Any]]] = None,
) -> Pillar4RobustnessStability:
    """Compute P4.1 Buffer Adequacy, Shock Survival (+25%/+50% on raw duration), Realized Deviation, & P4.2 Stability."""
    from schedule_testing_system.sut_adapter import round_up_to_15

    raw_map: Dict[str, Task] = {t.task_id: t for t in raw_tasks}
    horizon_slots = gates.horizon_slots
    blocks = sorted(schedule.blocks, key=lambda b: (b.start_slot, b.end_slot))

    # Map expanded habits so raw estimate lookup works cleanly
    buffered_count = 0
    for t_prep in prepared_tasks:
        t_raw = raw_map.get(t_prep.task_id)
        base_raw_min = t_raw.duration_min if t_raw is not None else t_prep.duration_min
        if t_prep.get_planned_duration_min() > round_up_to_15(base_raw_min):
            buffered_count += 1

    true_buffer_pct = round(100.0 * buffered_count / float(len(prepared_tasks)), 2) if prepared_tasks else 0.0

    # Zero-slack risk blocks: 0 free/rest slots immediately after b.end_slot
    occ_block_starts = {b.start_slot for b in blocks}
    zero_slack = 0
    for b in blocks:
        if b.end_slot >= horizon_slots:
            zero_slack += 1
            continue
        locked = base_grid._locked_mask[b.end_slot]
        is_at_deadline = b.deadline_slot is not None and b.end_slot >= b.deadline_slot
        if (
            locked == TimeGridManager.STATE_SLEEP
            or locked.startswith(TimeGridManager.STATE_OCCUPIED)
            or b.end_slot in occ_block_starts
            or is_at_deadline
        ):
            zero_slack += 1

    # Simulate configured duration shocks (+25%, +50%)
    raw_full = list(raw_tasks)
    known_raw_ids = {t.task_id for t in raw_full}
    for tp in prepared_tasks:
        if tp.task_id not in known_raw_ids:
            raw_full.append(tp)

    shock_results = [
        _simulate_shock_survival(profile, raw_full, prepared_tasks, schedule, base_grid, pct)
        for pct in config.shock_levels_pct
    ]

    # Realized vs Planned deviation (O'Donovan)
    prep_map = {t.task_id: t for t in prepared_tasks}
    realized_diffs: List[float] = []
    realized_ratios: List[float] = []
    for t in raw_tasks:
        if t.actual_duration_min is not None:
            t_p = prep_map.get(t.task_id, t)
            realized_diffs.append(float(abs(t.actual_duration_min - t_p.get_planned_duration_min())))
            realized_ratios.append(t.actual_duration_min / float(max(1, t.duration_min)))
    if completion_logs:
        for log in completion_logs:
            est = float(log.get("estimated_duration_min") or 0)
            act = float(log.get("actual_duration_min") or 0)
            if est > 0 and act > 0:
                tid = str(log.get("task_id") or "")
                planned = float(prep_map[tid].get_planned_duration_min()) if tid in prep_map else est
                realized_diffs.append(abs(act - planned))
                realized_ratios.append(act / est)

    post_repair: Optional[PostRepairStabilityMetrics] = None
    if baseline_schedule is not None:
        now_ref = repair_now_slot if repair_now_slot is not None else gates.now_slot
        post_repair = _evaluate_post_repair_stability(
            baseline_schedule=baseline_schedule,
            repaired_schedule=schedule,
            now_slot_ref=now_ref,
            config=config,
            disruption_span=disruption_span,
        )

    return Pillar4RobustnessStability(
        true_buffer_task_pct=true_buffer_pct,
        buffered_tasks_count=buffered_count,
        total_tasks_checked=len(prepared_tasks),
        zero_slack_risk_blocks=zero_slack,
        shock_results=shock_results,
        realized_mean_abs_deviation_min=round(sum(realized_diffs) / float(len(realized_diffs)), 2)
        if realized_diffs
        else None,
        realized_actual_to_estimate_ratio=round(sum(realized_ratios) / float(len(realized_ratios)), 3)
        if realized_ratios
        else None,
        post_repair_stability=post_repair,
    )
