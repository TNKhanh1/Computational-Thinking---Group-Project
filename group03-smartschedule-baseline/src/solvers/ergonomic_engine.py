"""
Shared Ergonomic Scheduling Engine (`ergonomic_engine.py`) for SmartSchedule Solvers.

Provides deterministic, stateless, O(1)-prefix-assisted scheduling primitives used across
the solver portfolio:
- ErgonomicContext: Precomputes grid geometry (FREE/SLEEP/OCCUPIED/MEAL/CLASS),
  energy prefix sums, Peak reservation demand, Social Jetlag anchor midpoints, and
  backward/forward DAG effective bounds.
- ScheduleState: Incremental mutable schedule representation tracking per-day counts,
  load==3 caps, total study+class load, load>=2 streaks, post-class buffers, meal-L2
  sandwiches, recovery coverage, +25% shock survival, context switches, and TStd.
- evaluate_state_lex_key: Fast exact lexicographic objective aligned with the v2.1
  ergonomic verdict hierarchy (G1/CRIT -> WARN -> tie-breakers).
- Constructive strategies + G1-legal adaptive chunk splitting + Feasibility-First Rescue
  (Pass B Kempe/split ejection) + deterministic Local Polish & Hybrid ALNS (Regret-2).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
import random
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from src.config import (
    ALNS_MAX_ITERS,
    ALNS_POLISH_MAX_PASSES,
    ALNS_TIME_BUDGET_SEC,
    ERGONOMIC_CRAM_WINDOW_SLOTS,
    ERGONOMIC_DAILY_HEAVY_CAP,
    ERGONOMIC_DAILY_STD_BASE_TOL_MIN,
    ERGONOMIC_DAILY_STD_FLOOR_MIN,
    ERGONOMIC_DAILY_TOTAL_HARD_SLOTS,
    ERGONOMIC_DAILY_TOTAL_SOFT_SLOTS,
    ERGONOMIC_HEAVY_MIN_GAP_SLOTS,
    ERGONOMIC_L2_STREAK_HARD_SLOTS,
    ERGONOMIC_L2_STREAK_SOFT_SLOTS,
    GREEDY_POLISH_MAX_PASSES,
    GREEDY_TIME_BUDGET_SEC,
    MANDATORY_REST_SLOTS,
    MIN_DEEP_WORK_BREAK_TRIGGER_MIN,
)
from src.grid_manager import TimeGridManager
from src.models import (
    WORK_RHYTHM_BOUNDS,
    CircadianEnergyProfile,
    CommitmentsProfile,
    ScheduleBlock,
    Task,
    TaskChunk,
)
from src.utils import MINUTES_PER_SLOT, SLOTS_PER_DAY, parse_time_to_slot_offset


WINDOW_RANGES: Dict[str, Tuple[int, int]] = {
    "MORNING": (24, 48),     # 06:00 - 12:00
    "AFTERNOON": (48, 72),   # 12:00 - 18:00
    "EVENING": (72, 92),     # 18:00 - 23:00 (matches Testing_System & M2 habit window)
    "NIGHT": (0, 24),        # 00:00 - 06:00
}

_TWO_PI_OVER_DAY: float = (2.0 * math.pi) / float(SLOTS_PER_DAY)
_SIN_TOD: Tuple[float, ...] = tuple(math.sin(t * _TWO_PI_OVER_DAY) for t in range(SLOTS_PER_DAY))
_COS_TOD: Tuple[float, ...] = tuple(math.cos(t * _TWO_PI_OVER_DAY) for t in range(SLOTS_PER_DAY))


def circular_midpoint_slots(active_slots: Iterable[int]) -> Optional[float]:
    """Compute circular mean in [0, SLOTS_PER_DAY) slots using unit circle projection."""
    sin_sum = 0.0
    cos_sum = 0.0
    count = 0
    for s in active_slots:
        tod = s % SLOTS_PER_DAY
        sin_sum += _SIN_TOD[tod]
        cos_sum += _COS_TOD[tod]
        count += 1
    if count == 0 or (abs(sin_sum) < 1e-9 and abs(cos_sum) < 1e-9):
        return None
    angle = math.atan2(sin_sum, cos_sum)
    if angle < 0.0:
        angle += 2.0 * math.pi
    return (angle / (2.0 * math.pi)) * float(SLOTS_PER_DAY)


def _circ_tod_from_sincos(sin_v: float, cos_v: float) -> Optional[float]:
    if abs(sin_v) < 1e-9 and abs(cos_v) < 1e-9:
        return None
    ang = math.atan2(sin_v, cos_v)
    if ang < 0.0:
        ang += 2.0 * math.pi
    return (ang / (2.0 * math.pi)) * float(SLOTS_PER_DAY)


def _circular_median_tod_min(hist: Sequence[int]) -> Optional[float]:
    """Compute Smarr & Schirmer circular median in minutes [0, 1440)."""
    nonzero = [(i, c) for i, c in enumerate(hist) if c > 0]
    if not nonzero:
        return None
    half = SLOTS_PER_DAY // 2
    best_t = 0
    best_dist = 10**12
    for cand in range(SLOTS_PER_DAY):
        d = 0
        for idx, cnt in nonzero:
            diff = abs(cand - idx)
            if diff > half:
                diff = SLOTS_PER_DAY - diff
            d += cnt * diff
        if d < best_dist:
            best_dist = d
            best_t = cand
    return float(best_t * MINUTES_PER_SLOT)


def circular_signed_diff_slots(phi_a: float, phi_b: float) -> float:
    """Signed circular delta (phi_a - phi_b) in [-48, +48] slots."""
    raw = (phi_a - phi_b) % float(SLOTS_PER_DAY)
    if raw > SLOTS_PER_DAY / 2.0:
        raw -= float(SLOTS_PER_DAY)
    return raw


def _window_match_fraction(start_slot: int, dur_slots: int, pref: Optional[str]) -> float:
    """Exact fraction of slots falling inside preferred_window (MORNING/AFTERNOON/EVENING)."""
    p = (pref or "").strip().upper()
    if p not in ("MORNING", "AFTERNOON", "EVENING"):
        return 1.0
    bounds = WINDOW_RANGES[p]
    hits = 0
    span = max(1, dur_slots)
    for s in range(start_slot, start_slot + span):
        tod = s % SLOTS_PER_DAY
        if bounds[0] <= tod < bounds[1]:
            hits += 1
    return hits / float(span)


def _effective_chunk_bounds_slots(task: Task) -> Tuple[int, int]:
    """Return G1-legal (min_chunk_slots, max_chunk_slots) strictly honoring Task bounds."""
    lo_m = int(task.min_chunk_min or 45)
    hi_m = max(lo_m, int(task.max_chunk_min or 90))
    return max(1, lo_m // MINUTES_PER_SLOT), max(1, hi_m // MINUTES_PER_SLOT)


def _effective_load(task: Task) -> int:
    if task.cognitive_load is not None:
        return max(1, min(3, int(task.cognitive_load)))
    if task.priority >= 5:
        return 3
    if task.priority >= 3:
        return 2
    return 1


def _is_habit_task(task: Task, deadline_slot: Optional[int]) -> bool:
    cat = (task.category or "").strip().upper()
    return deadline_slot is None or cat in ("HABIT", "PERSONAL_HABIT", "CHORE", "CHORES")


def _shock25_extra_slots(dur_slots: int) -> int:
    return int(math.ceil(dur_slots * 0.25))


def _make_chunks_from_durations(
    task: Task,
    durations_slots: Sequence[int],
    week_start_iso: str,
    original_order: int = 0,
    min_chunk_min_override: Optional[int] = None,
) -> List[TaskChunk]:
    lo_s, _ = _effective_chunk_bounds_slots(task)
    min_c_min = min_chunk_min_override if min_chunk_min_override is not None else lo_s * MINUTES_PER_SLOT
    dl_slot = task.resolve_deadline_slot(week_start_iso=week_start_iso)
    dl_label = task.format_deadline_label(week_start_iso=week_start_iso)
    total = len(durations_slots)
    out: List[TaskChunk] = []
    for idx, d_slots in enumerate(durations_slots, start=1):
        out.append(
            TaskChunk(
                chunk_id=f"{task.task_id}_C{idx}",
                task_id=task.task_id,
                title=task.title,
                chunk_index=idx,
                total_chunks=total,
                duration_min=d_slots * MINUTES_PER_SLOT,
                duration_slots=d_slots,
                deadline_slot=dl_slot,
                deadline_str=dl_label,
                priority=task.priority,
                depends_on=list(task.depends_on),
                original_order=original_order,
                is_splittable=task.is_splittable,
                min_chunk_min=min_c_min,
                cognitive_load=task.cognitive_load,
                category=task.category,
                preferred_window=task.preferred_window,
            )
        )
    return out


def generate_legal_split_options(
    task: Task,
    default_chunks: List[TaskChunk],
    week_start_iso: str,
    original_order: int = 0,
    max_variants: int = 3,
) -> List[List[TaskChunk]]:
    """
    Generate G1-legal adaptive chunkings for `task`, always keeping `default_chunks` first.
    Every chunk in any alternate multi-chunk split stays strictly inside [lo_s, hi_s].
    """
    variants: List[List[TaskChunk]] = [default_chunks]
    if not task.is_splittable:
        return variants

    total_slots = sum(c.duration_slots for c in default_chunks)
    lo_s, hi_s = _effective_chunk_bounds_slots(task)
    default_durs = tuple(c.duration_slots for c in default_chunks)
    if total_slots < 2 * lo_s:
        return variants

    seen: Set[Tuple[int, ...]] = {default_durs}
    candidates: List[Tuple[int, ...]] = []

    min_k = max(2, math.ceil(total_slots / float(hi_s)))
    max_k = min(total_slots // lo_s, 6)
    for k in range(min_k, max_k + 1):
        base, rem = divmod(total_slots, k)
        if base < lo_s or (base + (1 if rem > 0 else 0)) > hi_s:
            continue
        # Balanced descending (larger chunks first) and balanced ascending
        desc = tuple(base + (1 if i < rem else 0) for i in range(k))
        asc = tuple(reversed(desc))
        for tup in (desc, asc):
            if tup not in seen and all(lo_s <= x <= hi_s for x in tup):
                seen.add(tup)
                candidates.append(tup)
        # Try shifting 1..2 slots to expose smaller chunks that fit tight gaps cleanly
        if k == 2 and lo_s <= total_slots - hi_s <= hi_s:
            t_max_first = (hi_s, total_slots - hi_s)
            t_min_first = (total_slots - hi_s, hi_s)
            for tup in (t_max_first, t_min_first):
                if tup not in seen and all(lo_s <= x <= hi_s for x in tup):
                    seen.add(tup)
                    candidates.append(tup)
        if len(candidates) >= max_variants - 1:
            break

    min_c_min = default_chunks[0].min_chunk_min if default_chunks else lo_s * MINUTES_PER_SLOT
    for durs in candidates[: max_variants - 1]:
        variants.append(
            _make_chunks_from_durations(
                task,
                durs,
                week_start_iso=week_start_iso,
                original_order=original_order,
                min_chunk_min_override=min_c_min,
            )
        )
    return variants


@dataclass(frozen=True)
class UnitPlacement:
    task_id: str
    chunk_index: int
    total_chunks: int
    start_slot: int
    end_slot: int
    duration_slots: int
    cognitive_load: int
    priority: int
    category: str
    preferred_window: Optional[str]
    deadline_slot: Optional[int]
    is_pinned: bool = False


@dataclass
class ErgonomicContext:
    """Immutable precomputed grid/task/circadian metadata for fast O(1) evaluation."""

    horizon_slots: int
    num_days: int
    now_slot: int
    week_start_iso: str
    energy_aware: bool
    locked_mask: List[str]
    is_free_base: List[bool]
    is_sleep: List[bool]
    is_occupied: List[bool]
    is_meal: List[bool]
    energy_levels: List[int]
    pref_free: List[int]
    pref_peak: List[int]
    pref_low: List[int]
    pref_energy2p: List[int]
    pref_energy_sum: List[int]
    pref_tod_sin: List[float]
    pref_tod_cos: List[float]
    after_long_class: List[bool]
    meal_left_edge_to_id: Dict[int, int]
    meal_right_edge_to_id: Dict[int, int]
    meal_id_to_span: List[Tuple[int, int]]
    base_class_slots_per_day: List[int]
    total_base_class_slots: int
    base_class_std_min: float
    class_days: Set[int]
    is_class_day: List[bool]
    free_days_in_scope: Set[int]
    rho_total: float
    rho_deadline: float
    total_peak_demand_l3_slots: int
    tasks_by_id: Dict[str, Task]
    default_chunks_by_task: Dict[str, List[TaskChunk]]
    split_options_by_task: Dict[str, List[List[TaskChunk]]]
    pinned_chunk_indices_by_task: Dict[str, Set[int]]
    pinned_end_by_task: Dict[str, int]
    raw_deadline: Dict[str, Optional[int]]
    eff_deadline: Dict[str, Optional[int]]
    raw_earliest: Dict[str, int]
    eff_earliest: Dict[str, int]
    preds_map: Dict[str, List[str]]
    succs_map: Dict[str, List[str]]
    topo_order: List[str]
    descendant_count: Dict[str, int]
    task_planned_slots: Dict[str, int]
    task_load: Dict[str, int]
    task_is_habit: Dict[str, bool]
    task_is_deadline: Dict[str, bool]
    crunch_tier_used: int = 0
    # Whether grid has free Peak (>=2 energy) span per chunk length (for CRIT check accuracy)
    has_non_low_energy_span_cache: Dict[int, bool] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        base_grid: TimeGridManager,
        profile: CommitmentsProfile,
        schedulable_tasks: List[Task],
        pinned_blocks: List[ScheduleBlock],
        now_slot: int,
        horizon_slots: int,
        week_start_iso: str,
        energy_aware: bool,
        solver_split_fn: Any,
    ) -> "ErgonomicContext":
        H = horizon_slots
        num_days = max(1, (H + SLOTS_PER_DAY - 1) // SLOTS_PER_DAY)
        locked_mask = list(base_grid._locked_mask[:H])
        is_free_base = [st == TimeGridManager.STATE_FREE for st in locked_mask]
        is_sleep = [st == TimeGridManager.STATE_SLEEP for st in locked_mask]
        is_occupied = [st.startswith(TimeGridManager.STATE_OCCUPIED) for st in locked_mask]

        # Extract MEAL vs >=6-slot Class spans directly from profile.fixed_events
        is_meal = [False] * H
        is_class = [False] * H
        after_long_class = [False] * H
        meal_intervals: List[Tuple[int, int]] = []
        class_slots_per_day = [0] * num_days

        anchor_slots: List[int] = []
        has_sleep = any(is_sleep)
        has_fixed_non_sleep = any(is_occupied)

        for d_idx in range(min(len(is_sleep), H)):
            if is_sleep[d_idx]:
                # Wake/sleep anchor complement doesn't go directly; collect active commitments/meals
                pass

        for ev in profile.fixed_events:
            cat = (ev.category or "").strip().upper()
            days = base_grid._resolve_event_days(ev.day_of_week)
            try:
                st_off = parse_time_to_slot_offset(ev.start_time, is_end_or_deadline=False)
                en_off = parse_time_to_slot_offset(ev.end_time, is_end_or_deadline=True)
            except Exception:
                continue
            for d in days:
                if d < 0 or d >= num_days:
                    continue
                if en_off <= st_off:
                    # Cross-midnight fixed event capped cleanly within horizon
                    abs_st = d * SLOTS_PER_DAY + st_off
                    abs_en = min(H, (d + 1) * SLOTS_PER_DAY + en_off)
                else:
                    abs_st = d * SLOTS_PER_DAY + st_off
                    abs_en = min(H, d * SLOTS_PER_DAY + en_off)
                abs_st = max(0, abs_st)
                if abs_en <= abs_st:
                    continue
                dur = abs_en - abs_st
                if "MEAL" in cat:
                    meal_intervals.append((abs_st, abs_en))
                    for s in range(abs_st, abs_en):
                        is_meal[s] = True
                        anchor_slots.append(s)
                else:
                    for s in range(abs_st, abs_en):
                        is_class[s] = True
                        anchor_slots.append(s)
                        class_slots_per_day[s // SLOTS_PER_DAY] += 1
                    if dur >= 6 and abs_en < H:
                        after_long_class[abs_en] = True

        # Fallback: mark any remaining OCCUPIED slots (not flagged meal) into class_slots if needed
        for s in range(H):
            if is_occupied[s] and not is_meal[s] and not is_class[s]:
                is_class[s] = True
                anchor_slots.append(s)
                class_slots_per_day[s // SLOTS_PER_DAY] += 1

        # Build merged contiguous MEAL spans -> left/right boundary indices
        meal_intervals.sort()
        merged_meals: List[Tuple[int, int]] = []
        for ms, me in meal_intervals:
            if merged_meals and ms <= merged_meals[-1][1]:
                merged_meals[-1] = (merged_meals[-1][0], max(merged_meals[-1][1], me))
            else:
                merged_meals.append((ms, me))
        meal_left_edge_to_id: Dict[int, int] = {}
        meal_right_edge_to_id: Dict[int, int] = {}
        for mid, (ms, me) in enumerate(merged_meals):
            meal_left_edge_to_id[ms] = mid
            meal_right_edge_to_id[me] = mid

        # Energy array & prefix sums
        if energy_aware:
            energy_prof = profile.get_energy_profile()
            energy_levels = [energy_prof.level_for_slot(s) for s in range(H)]
        else:
            energy_levels = [2] * H

        pref_free = [0] * (H + 1)
        pref_peak = [0] * (H + 1)
        pref_low = [0] * (H + 1)
        pref_energy2p = [0] * (H + 1)
        pref_energy_sum = [0] * (H + 1)
        pref_tod_sin = [0.0] * (H + 1)
        pref_tod_cos = [0.0] * (H + 1)
        total_free_slots = 0
        for s in range(H):
            f = 1 if is_free_base[s] else 0
            e = energy_levels[s]
            tod = s % SLOTS_PER_DAY
            pref_free[s + 1] = pref_free[s] + f
            pref_peak[s + 1] = pref_peak[s] + (1 if (f and e == 3) else 0)
            pref_low[s + 1] = pref_low[s] + (1 if e == 1 else 0)
            pref_energy2p[s + 1] = pref_energy2p[s] + (1 if (f and e >= 2) else 0)
            pref_energy_sum[s + 1] = pref_energy_sum[s] + e
            pref_tod_sin[s + 1] = pref_tod_sin[s] + _SIN_TOD[tod]
            pref_tod_cos[s + 1] = pref_tod_cos[s] + _COS_TOD[tod]
            if s >= now_slot and f:
                total_free_slots += 1

        # Base class STD in minutes & class_days SJL indicators
        total_base_class_slots = sum(class_slots_per_day)
        mean_c = total_base_class_slots / float(num_days)
        var_c = sum(((c - mean_c) * MINUTES_PER_SLOT) ** 2 for c in class_slots_per_day) / float(num_days)
        base_class_std_min = math.sqrt(var_c)
        class_days = {d for d, cnt in enumerate(class_slots_per_day) if cnt > 0}
        is_class_day = [d in class_days for d in range(num_days)]

        # Build task metadata & DAG
        tasks_by_id: Dict[str, Task] = {}
        default_chunks_by_task: Dict[str, List[TaskChunk]] = {}
        split_options_by_task: Dict[str, List[List[TaskChunk]]] = {}
        raw_deadline: Dict[str, Optional[int]] = {}
        raw_earliest: Dict[str, int] = {}
        task_planned_slots: Dict[str, int] = {}
        task_load: Dict[str, int] = {}
        task_is_habit: Dict[str, bool] = {}
        task_is_deadline: Dict[str, bool] = {}
        preds_map: Dict[str, List[str]] = {}
        succs_map: Dict[str, List[str]] = {}

        # Pinned slot map & partial-chunk tracking
        pinned_by_task: Dict[str, int] = {}
        pinned_chunk_indices_by_task: Dict[str, Set[int]] = {}
        pinned_end_by_task: Dict[str, int] = {}
        for pb in pinned_blocks:
            tid = pb.task_id
            pinned_by_task[tid] = pinned_by_task.get(tid, 0) + (pb.end_slot - pb.start_slot)
            pinned_chunk_indices_by_task.setdefault(tid, set()).add(pb.chunk_index)
            if pb.end_slot > pinned_end_by_task.get(tid, 0):
                pinned_end_by_task[tid] = pb.end_slot

        total_demand_slots = 0
        total_peak_demand_l3_slots = 0

        for idx, t in enumerate(schedulable_tasks):
            tid = t.task_id
            tasks_by_id[tid] = t
            dl = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            raw_deadline[tid] = dl
            sa = t.resolve_start_after_slot(week_start_iso=week_start_iso)
            raw_earliest[tid] = max(now_slot, sa if sa is not None else 0)
            p_slots = t.get_planned_slots()
            task_planned_slots[tid] = p_slots
            ld = _effective_load(t)
            task_load[tid] = ld
            hb = _is_habit_task(t, dl)
            task_is_habit[tid] = hb
            task_is_deadline[tid] = dl is not None

            def_chunks = solver_split_fn(t, original_order=idx, week_start_iso=week_start_iso)
            default_chunks_by_task[tid] = def_chunks
            if tid in pinned_by_task:
                split_options_by_task[tid] = [def_chunks]
            else:
                split_options_by_task[tid] = generate_legal_split_options(
                    t, def_chunks, week_start_iso=week_start_iso, original_order=idx
                )

            rem = max(0, p_slots - pinned_by_task.get(tid, 0))
            total_demand_slots += rem
            if ld == 3:
                total_peak_demand_l3_slots += rem

            preds_map[tid] = []
            succs_map[tid] = []

        valid_ids = set(tasks_by_id.keys())
        in_degree: Dict[str, int] = {tid: 0 for tid in valid_ids}
        for t in schedulable_tasks:
            for dep in t.depends_on:
                if dep in valid_ids and dep != t.task_id and dep not in preds_map[t.task_id]:
                    preds_map[t.task_id].append(dep)
                    succs_map[dep].append(t.task_id)
                    in_degree[t.task_id] += 1

        # Deterministic topological sort
        q = deque(sorted([tid for tid, deg in in_degree.items() if deg == 0]))
        topo_order: List[str] = []
        while q:
            u = q.popleft()
            topo_order.append(u)
            for v in sorted(succs_map[u]):
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    q.append(v)
        # Safety fallback if any leftover (cycle already filtered before ErgonomicContext)
        for tid in sorted(valid_ids):
            if tid not in topo_order:
                topo_order.append(tid)

        # Forward effective earliest & backward effective deadline propagation
        eff_earliest: Dict[str, int] = dict(raw_earliest)
        for u in topo_order:
            u_dur = task_planned_slots[u]
            for v in succs_map[u]:
                cand = eff_earliest[u] + u_dur
                if cand > eff_earliest[v]:
                    eff_earliest[v] = cand

        eff_deadline: Dict[str, Optional[int]] = dict(raw_deadline)
        for v in reversed(topo_order):
            v_dl = eff_deadline[v]
            if v_dl is None:
                continue
            v_dur = task_planned_slots[v]
            needed_pred_end = v_dl - v_dur
            for u in preds_map[v]:
                cur = eff_deadline[u]
                if cur is None or needed_pred_end < cur:
                    eff_deadline[u] = needed_pred_end

        # Transitive descendant count for critical-chain weighting
        desc_sets: Dict[str, Set[str]] = {tid: set() for tid in valid_ids}
        for v in reversed(topo_order):
            for u in preds_map[v]:
                desc_sets[u].add(v)
                desc_sets[u].update(desc_sets[v])
        descendant_count = {tid: len(s) for tid, s in desc_sets.items()}

        dl_demand_slots = sum(
            max(0, task_planned_slots[tid] - pinned_by_task.get(tid, 0))
            for tid, is_dl in task_is_deadline.items()
            if is_dl
        )
        max_dl_slot = max(
            (dl for dl in raw_deadline.values() if dl is not None),
            default=H,
        )
        free_before_dl = max(1, pref_free[min(H, max_dl_slot)] - pref_free[now_slot])
        rho_total = float(total_demand_slots) / float(max(1, total_free_slots))
        rho_deadline = float(dl_demand_slots) / float(free_before_dl)

        start_d = now_slot // SLOTS_PER_DAY
        max_d_day = max(start_d, (min(H, max_dl_slot) - 1) // SLOTS_PER_DAY)
        free_days_in_scope = {
            d
            for d in range(start_d, max_d_day + 1)
            if (pref_free[min(H, (d + 1) * SLOTS_PER_DAY)] - pref_free[max(now_slot, d * SLOTS_PER_DAY)]) >= 4
        }

        ctx = cls(
            horizon_slots=H,
            num_days=num_days,
            now_slot=now_slot,
            week_start_iso=week_start_iso,
            energy_aware=energy_aware,
            locked_mask=locked_mask,
            is_free_base=is_free_base,
            is_sleep=is_sleep,
            is_occupied=is_occupied,
            is_meal=is_meal,
            energy_levels=energy_levels,
            pref_free=pref_free,
            pref_peak=pref_peak,
            pref_low=pref_low,
            pref_energy2p=pref_energy2p,
            pref_energy_sum=pref_energy_sum,
            pref_tod_sin=pref_tod_sin,
            pref_tod_cos=pref_tod_cos,
            after_long_class=after_long_class,
            meal_left_edge_to_id=meal_left_edge_to_id,
            meal_right_edge_to_id=meal_right_edge_to_id,
            meal_id_to_span=merged_meals,
            base_class_slots_per_day=class_slots_per_day,
            total_base_class_slots=total_base_class_slots,
            base_class_std_min=base_class_std_min,
            class_days=class_days,
            is_class_day=is_class_day,
            free_days_in_scope=free_days_in_scope,
            rho_total=rho_total,
            rho_deadline=rho_deadline,
            total_peak_demand_l3_slots=total_peak_demand_l3_slots,
            tasks_by_id=tasks_by_id,
            default_chunks_by_task=default_chunks_by_task,
            split_options_by_task=split_options_by_task,
            pinned_chunk_indices_by_task=pinned_chunk_indices_by_task,
            pinned_end_by_task=pinned_end_by_task,
            raw_deadline=raw_deadline,
            eff_deadline=eff_deadline,
            raw_earliest=raw_earliest,
            eff_earliest=eff_earliest,
            preds_map=preds_map,
            succs_map=succs_map,
            topo_order=topo_order,
            descendant_count=descendant_count,
            task_planned_slots=task_planned_slots,
            task_load=task_load,
            task_is_habit=task_is_habit,
            task_is_deadline=task_is_deadline,
        )
        return ctx

    def is_span_base_free(self, start_slot: int, end_slot: int) -> bool:
        if start_slot < 0 or end_slot > self.horizon_slots or start_slot >= end_slot:
            return False
        dur = end_slot - start_slot
        return (self.pref_free[end_slot] - self.pref_free[start_slot]) == dur

    def span_energy_sum(self, start_slot: int, end_slot: int) -> int:
        return self.pref_energy_sum[end_slot] - self.pref_energy_sum[start_slot]

    def has_non_low_energy_span(self, dur_slots: int) -> bool:
        """True iff there exists at least one locked-free span of `dur_slots` with avg_energy >= 2.0."""
        cached = self.has_non_low_energy_span_cache.get(dur_slots)
        if cached is not None:
            return cached
        ok = False
        limit = self.horizon_slots - dur_slots + 1
        req_e = 2 * dur_slots
        for s in range(self.now_slot, limit):
            e = s + dur_slots
            if (self.pref_free[e] - self.pref_free[s]) == dur_slots and (
                self.pref_energy_sum[e] - self.pref_energy_sum[s]
            ) >= req_e:
                ok = True
                break
        self.has_non_low_energy_span_cache[dur_slots] = ok
        return ok


class ScheduleState:
    """Mutable incremental schedule state supporting fast placement/removal and exact evaluation."""

    def __init__(self, ctx: ErgonomicContext, pinned_units: Optional[List[UnitPlacement]] = None) -> None:
        self.ctx = ctx
        H = ctx.horizon_slots
        # Index of placement tag: "" if unused, or task_id if occupied by a study/pinned unit
        self.slot_owner: List[str] = [""] * H
        self.units_by_task: Dict[str, List[UnitPlacement]] = {}
        self.day_study_slots: List[int] = [0] * ctx.num_days
        self.day_l3_count: List[int] = [0] * ctx.num_days
        self.day_units: List[List[UnitPlacement]] = [[] for _ in range(ctx.num_days)]
        self.peak_used_by_non_l3: int = 0
        self.peak_free_now: int = ctx.pref_peak[H] - ctx.pref_peak[ctx.now_slot]
        self.placed_l3_slots_count: int = 0
        self.total_study_slots: int = 0
        self.cls_sin: float = 0.0
        self.cls_cos: float = 0.0
        self.cls_cnt: int = 0
        self.non_sin: float = 0.0
        self.non_cos: float = 0.0
        self.non_cnt: int = 0
        self.crunch_tier_used: int = 0

        if pinned_units:
            for u in pinned_units:
                self.add_unit(u)

    def clone(self) -> "ScheduleState":
        st = ScheduleState.__new__(ScheduleState)
        st.ctx = self.ctx
        st.slot_owner = list(self.slot_owner)
        st.units_by_task = {k: list(v) for k, v in self.units_by_task.items()}
        st.day_study_slots = list(self.day_study_slots)
        st.day_l3_count = list(self.day_l3_count)
        st.day_units = [list(lst) for lst in self.day_units]
        st.peak_used_by_non_l3 = self.peak_used_by_non_l3
        st.peak_free_now = self.peak_free_now
        st.placed_l3_slots_count = self.placed_l3_slots_count
        st.total_study_slots = self.total_study_slots
        st.cls_sin = self.cls_sin
        st.cls_cos = self.cls_cos
        st.cls_cnt = self.cls_cnt
        st.non_sin = self.non_sin
        st.non_cos = self.non_cos
        st.non_cnt = self.non_cnt
        st.crunch_tier_used = self.crunch_tier_used
        return st

    def is_span_available(self, start_slot: int, end_slot: int) -> bool:
        if not self.ctx.is_span_base_free(start_slot, end_slot):
            return False
        owners = self.slot_owner
        for s in range(start_slot, end_slot):
            if owners[s]:
                return False
        return True

    def add_unit(self, unit: UnitPlacement) -> None:
        owners = self.slot_owner
        tid = unit.task_id
        for s in range(unit.start_slot, unit.end_slot):
            owners[s] = tid
        self.units_by_task.setdefault(tid, []).append(unit)
        self.units_by_task[tid].sort(key=lambda u: u.start_slot)

        d = unit.start_slot // SLOTS_PER_DAY
        if 0 <= d < self.ctx.num_days:
            self.day_units[d].append(unit)
            self.day_units[d].sort(key=lambda u: u.start_slot)

        self.total_study_slots += unit.duration_slots
        if unit.cognitive_load == 3:
            self.placed_l3_slots_count += unit.duration_slots
            if 0 <= d < self.ctx.num_days:
                self.day_l3_count[d] += 1

        # Distribute study slots + O(1) circadian SJL sin/cos sums across days
        e_lvls = self.ctx.energy_levels
        is_cday = self.ctx.is_class_day
        n_days = self.ctx.num_days
        for s in range(unit.start_slot, unit.end_slot):
            sd, tod = divmod(s, SLOTS_PER_DAY)
            if 0 <= sd < n_days:
                self.day_study_slots[sd] += 1
                if is_cday[sd]:
                    self.cls_sin += _SIN_TOD[tod]
                    self.cls_cos += _COS_TOD[tod]
                    self.cls_cnt += 1
                else:
                    self.non_sin += _SIN_TOD[tod]
                    self.non_cos += _COS_TOD[tod]
                    self.non_cnt += 1
            if e_lvls[s] == 3 and not unit.is_pinned:
                self.peak_free_now -= 1
                if unit.cognitive_load < 3:
                    self.peak_used_by_non_l3 += 1

    def remove_task(self, task_id: str) -> List[UnitPlacement]:
        units = self.units_by_task.pop(task_id, [])
        if not units:
            return []
        kept: List[UnitPlacement] = []
        removed: List[UnitPlacement] = []
        owners = self.slot_owner
        e_lvls = self.ctx.energy_levels
        is_cday = self.ctx.is_class_day
        n_days = self.ctx.num_days
        for u in units:
            if u.is_pinned:
                kept.append(u)
                continue
            removed.append(u)
            self.total_study_slots -= u.duration_slots
            if u.cognitive_load == 3:
                self.placed_l3_slots_count -= u.duration_slots
            for s in range(u.start_slot, u.end_slot):
                if owners[s] == task_id:
                    owners[s] = ""
                sd, tod = divmod(s, SLOTS_PER_DAY)
                if 0 <= sd < n_days:
                    self.day_study_slots[sd] -= 1
                    if is_cday[sd]:
                        self.cls_sin -= _SIN_TOD[tod]
                        self.cls_cos -= _COS_TOD[tod]
                        self.cls_cnt -= 1
                    else:
                        self.non_sin -= _SIN_TOD[tod]
                        self.non_cos -= _COS_TOD[tod]
                        self.non_cnt -= 1
                if e_lvls[s] == 3:
                    self.peak_free_now += 1
                    if u.cognitive_load < 3:
                        self.peak_used_by_non_l3 -= 1
            d = u.start_slot // SLOTS_PER_DAY
            if 0 <= d < n_days:
                if u.cognitive_load == 3:
                    self.day_l3_count[d] -= 1
                self.day_units[d] = [x for x in self.day_units[d] if not (x.task_id == task_id and x.start_slot == u.start_slot)]
        if kept:
            self.units_by_task[task_id] = kept
        return removed

    def has_task_placed(self, task_id: str) -> bool:
        return bool(self.units_by_task.get(task_id))

    def is_task_fully_placed(self, task_id: str) -> bool:
        units = self.units_by_task.get(task_id)
        if not units:
            return False
        need = self.ctx.task_planned_slots.get(task_id, 0)
        return sum(u.duration_slots for u in units) >= need

    def task_max_end_slot(self, task_id: str) -> Optional[int]:
        units = self.units_by_task.get(task_id)
        if not units:
            return None
        return max(u.end_slot for u in units)

    def all_units(self) -> List[UnitPlacement]:
        out: List[UnitPlacement] = []
        for units in self.units_by_task.values():
            out.extend(units)
        out.sort(key=lambda u: (u.start_slot, u.task_id))
        return out

    def is_recovery_slot(self, slot_idx: int) -> bool:
        """Exact mirror of Testing_System._is_recovery_slot: H, SLEEP, MEAL, or empty FREE."""
        ctx = self.ctx
        if slot_idx >= ctx.horizon_slots:
            return True
        if ctx.is_sleep[slot_idx] or ctx.is_meal[slot_idx]:
            return True
        if ctx.is_occupied[slot_idx]:
            return False
        if self.slot_owner[slot_idx]:
            return False
        return True

    def placed_l3_slots(self) -> int:
        return self.placed_l3_slots_count


def score_candidate_unit(
    state: ScheduleState,
    task: Task,
    chunk: TaskChunk,
    start_slot: int,
    strategy_mode: str = "ERGONOMIC",
) -> Tuple[int, float]:
    """
    Score placing `chunk` at `start_slot` inside `state`.
    Returns `(crit_warn_flags, continuous_cost)` where lower is strictly better!
    When `state.ctx.energy_aware` is False, NO energy profile attribute is ever read (Q10).
    """
    ctx = state.ctx
    dur = chunk.duration_slots
    end_slot = start_slot + dur
    ld = ctx.task_load[task.task_id]
    dl = ctx.eff_deadline[task.task_id]
    raw_dl = ctx.raw_deadline[task.task_id]
    day = start_slot // SLOTS_PER_DAY
    is_l3 = ld == 3
    is_l2p = ld >= 2

    crit_pen = 0
    warn_pen = 0
    cost = 0.0

    # 1. Circadian Energy & Off-Peak Mismatch (O(1) via prefix sums, skipped in chronological OVERLOAD_PACK)
    if ctx.energy_aware and strategy_mode != "OVERLOAD_PACK":
        esum = ctx.pref_energy_sum[end_slot] - ctx.pref_energy_sum[start_slot]
        avg_e = esum / float(dur)
        has_low_slot = (ctx.pref_low[end_slot] - ctx.pref_low[start_slot]) > 0
        peak_cnt = ctx.pref_peak[end_slot] - ctx.pref_peak[start_slot]
        if is_l3:
            if has_low_slot and ctx.has_non_low_energy_span(dur):
                crit_pen += 50  # CRIT: off_peak_heavy_mismatch_count
            elif avg_e < 2.0:
                warn_pen += 10
            # Reward Peak energy==3 strongly (> SJL/onset) so L3 prioritizes Peak slots first (#5 before #10)
            cost -= 20.0 * avg_e + 24.0 * (peak_cnt / float(dur))
        else:
            # Peak reservation: protect energy==3 slots if unplaced L3 tasks still need Peak
            rem_l3_demand = max(0, ctx.total_peak_demand_l3_slots - state.placed_l3_slots_count)
            if peak_cnt > 0:
                peak_margin = state.peak_free_now - peak_cnt - rem_l3_demand
                if peak_margin < 0:
                    cost += 28.0 * float(peak_cnt)
                elif rem_l3_demand > 0:
                    cost += 7.0 * float(peak_cnt)
            if ld == 2:
                cost -= 1.2 * avg_e
            else:
                cost += 0.6 * avg_e

    # 2. Recovery immediately after chunk (mandatory for L3 / dur>=90m when tier==0)
    if state.crunch_tier_used == 0 and (is_l3 or chunk.duration_min >= MIN_DEEP_WORK_BREAK_TRIGGER_MIN):
        if not state.is_recovery_slot(end_slot):
            if is_l3:
                crit_pen += 60  # heavy_recovery_rate_pct < 100% -> CRIT!
            else:
                cost += 12.0
    # Also ensure any immediately preceding L3 block ending at `start_slot` isn't stripped of recovery!
    if start_slot > 0 and state.slot_owner[start_slot - 1]:
        prev_tid = state.slot_owner[start_slot - 1]
        if prev_tid != task.task_id and ctx.task_load.get(prev_tid, 1) == 3:
            crit_pen += 60
        elif prev_tid == task.task_id and is_l3:
            crit_pen += 60

    # 3. Post-class buffer violation (L3 starting immediately after >=6-slot class)
    if is_l3 and ctx.after_long_class[start_slot]:
        warn_pen += 12  # 1 WARN, 2 CRIT

    # 4. Daily Heavy Cap (load==3 blocks <= 2 per day)
    if is_l3:
        if state.day_l3_count[day] >= ERGONOMIC_DAILY_HEAVY_CAP:
            crit_pen += 55

    # 5. Daily Total Cap (study + class <= 36 WARN, <= 40 CRIT)
    cur_tot = state.day_study_slots[day] + ctx.base_class_slots_per_day[day]
    new_tot = cur_tot + dur
    if new_tot > ERGONOMIC_DAILY_TOTAL_HARD_SLOTS:
        crit_pen += 45 + (new_tot - ERGONOMIC_DAILY_TOTAL_HARD_SLOTS) * 4
    elif new_tot > ERGONOMIC_DAILY_TOTAL_SOFT_SLOTS:
        warn_pen += 8 + (new_tot - ERGONOMIC_DAILY_TOTAL_SOFT_SLOTS)

    # 6. Load >= 2 contiguous streak & Adjacent Heavy Pairs (L3-L3 gap <= 1) & Context Switches
    day_u = state.day_units[day] if 0 <= day < ctx.num_days else []
    left_l2 = 0
    right_l2 = 0
    prev_end_gap: Optional[int] = None
    next_start_gap: Optional[int] = None
    left_unit: Optional[UnitPlacement] = None
    right_unit: Optional[UnitPlacement] = None

    for u in day_u:
        if u.end_slot <= start_slot:
            left_unit = u
            prev_end_gap = start_slot - u.end_slot
        elif u.start_slot >= end_slot:
            right_unit = u
            next_start_gap = u.start_slot - end_slot
            break

    if is_l2p:
        # Compute contiguous load>=2 chain length crossing this insertion
        chain_slots = dur
        # Check left contiguous load>=2 blocks in day_units
        cur_s = start_slot
        for u in reversed(day_u):
            if u.end_slot == cur_s and u.cognitive_load >= 2:
                chain_slots += u.duration_slots
                cur_s = u.start_slot
            elif u.end_slot <= cur_s:
                break
        cur_e = end_slot
        for u in day_u:
            if u.start_slot == cur_e and u.cognitive_load >= 2:
                chain_slots += u.duration_slots
                cur_e = u.end_slot
            elif u.start_slot >= cur_e:
                break
        if chain_slots > ERGONOMIC_L2_STREAK_HARD_SLOTS:
            crit_pen += 50
        elif chain_slots > ERGONOMIC_L2_STREAK_SOFT_SLOTS:
            warn_pen += 10

    if is_l3:
        for u in day_u:
            if u.cognitive_load == 3:
                gap = min(
                    abs(start_slot - u.end_slot) if start_slot >= u.end_slot else 999,
                    abs(u.start_slot - end_slot) if u.start_slot >= end_slot else 999,
                )
                if gap < ERGONOMIC_HEAVY_MIN_GAP_SLOTS:
                    warn_pen += 10

    # Meal boundary sandwich check for load >= 2 (O(1) via meal_id_to_span)
    if is_l2p:
        if end_slot in ctx.meal_left_edge_to_id:
            mid = ctx.meal_left_edge_to_id[end_slot]
            _ms, me = ctx.meal_id_to_span[mid]
            owner = state.slot_owner[me] if me < ctx.horizon_slots else ""
            if owner and ctx.task_load.get(owner, 1) >= 2:
                warn_pen += 8
        if start_slot in ctx.meal_right_edge_to_id:
            mid = ctx.meal_right_edge_to_id[start_slot]
            ms, _me = ctx.meal_id_to_span[mid]
            owner = state.slot_owner[ms - 1] if ms > 0 else ""
            if owner and ctx.task_load.get(owner, 1) >= 2:
                warn_pen += 8

    # Context switch check (same_day, 0 <= gap <= 2, diff category, diff task_id)
    if left_unit is not None and prev_end_gap is not None and prev_end_gap <= 2:
        if left_unit.task_id != task.task_id and left_unit.category != task.category:
            cost += 5.5
    if right_unit is not None and next_start_gap is not None and next_start_gap <= 2:
        if right_unit.task_id != task.task_id and right_unit.category != task.category:
            cost += 5.5
    if left_unit is not None and left_unit.category == task.category and prev_end_gap is not None and prev_end_gap <= 4:
        cost -= 2.5  # Category batch bonus

    # 7. +25% Shock Headroom Check (crucial for shock25_pct >= 85% / 100%)
    shock_extra = _shock25_extra_slots(dur)
    shock_limit = min(ctx.horizon_slots, end_slot + shock_extra)
    if end_slot + shock_extra > ctx.horizon_slots:
        cost += 18.0
    else:
        for s in range(end_slot, shock_limit):
            if not ctx.is_free_base[s]:
                cost += 16.0  # Direct collision with SLEEP or OCCUPIED under +25% shock!
                break
            if state.slot_owner[s]:
                cost += 6.0   # Would cascade into next study block
                break
    # Also avoid placing immediately inside an existing block's +25% shock tail!
    if left_unit is not None and prev_end_gap is not None:
        left_shock = _shock25_extra_slots(left_unit.duration_slots)
        if prev_end_gap < left_shock:
            cost += 5.5

    # 8. Preferred Window & Habits + Habit Day Spreading
    pref = task.preferred_window
    if pref and pref.strip().upper() not in ("", "ANYTIME", "NONE"):
        w_frac = _window_match_fraction(start_slot, dur, pref)
        if ctx.task_is_habit[task.task_id]:
            cost += -12.0 * w_frac + 30.0 * (1.0 - w_frac)
        else:
            cost += -3.0 * w_frac + 6.0 * (1.0 - w_frac)

    if ctx.task_is_habit[task.task_id]:
        task_base_id = task.task_id.rsplit("_", 1)[0]
        for u in day_u:
            if u.task_id != task.task_id and (
                ctx.tasks_by_id[u.task_id].title == task.title
                or u.task_id.rsplit("_", 1)[0] == task_base_id
            ):
                cost += 25.0  # Spread repeating habits across distinct days
                break

    # 9. Anti-cramming (<10h before deadline) & Heavy onset delay (>35% of window guard)
    if raw_dl is not None:
        if start_slot >= raw_dl - ERGONOMIC_CRAM_WINDOW_SLOTS:
            frac = 1.0 - max(0.0, float(raw_dl - start_slot)) / float(ERGONOMIC_CRAM_WINDOW_SLOTS)
            cost += 10.0 + 18.0 * frac
        span_avail = max(1, raw_dl - ctx.raw_earliest[task.task_id])
        pos_frac = float(start_slot - ctx.raw_earliest[task.task_id]) / float(span_avail)
        if is_l3:
            if pos_frac > 0.55:
                cost += 22.0 + 45.0 * (pos_frac - 0.55)
            elif pos_frac > 0.40:
                cost += 14.0 * (pos_frac - 0.40)
        cost += 1.8 * pos_frac
    else:
        cost += 0.05 * day

    # 10. Daily TStd Load Balancing (O(1) using incremental total_study_slots)
    avg_tot = float(ctx.total_base_class_slots + state.total_study_slots + dur) / float(ctx.num_days)
    cost += 0.9 * max(0.0, float(new_tot) - avg_tot)
    cost += 0.35 * float(state.day_study_slots[day])

    # 11. Exact Smarr & Schirmer SJL guard (O(1) via pref_tod_sin/cos)
    cand_cday = ctx.is_class_day[day] if 0 <= day < ctx.num_days else False
    phi_cls: Optional[float] = None
    phi_non: Optional[float] = None
    pair_needed = False
    if cand_cday and state.non_cnt > 0:
        d_sin = ctx.pref_tod_sin[end_slot] - ctx.pref_tod_sin[start_slot]
        d_cos = ctx.pref_tod_cos[end_slot] - ctx.pref_tod_cos[start_slot]
        phi_cls = _circ_tod_from_sincos(state.cls_sin + d_sin, state.cls_cos + d_cos)
        phi_non = _circ_tod_from_sincos(state.non_sin, state.non_cos)
        pair_needed = ld == 1 and state.cls_cnt == 0 and strategy_mode in ("ERGONOMIC", "ANTI_CRAM")
    elif (not cand_cday) and state.cls_cnt > 0:
        d_sin = ctx.pref_tod_sin[end_slot] - ctx.pref_tod_sin[start_slot]
        d_cos = ctx.pref_tod_cos[end_slot] - ctx.pref_tod_cos[start_slot]
        phi_cls = _circ_tod_from_sincos(state.cls_sin, state.cls_cos)
        phi_non = _circ_tod_from_sincos(state.non_sin + d_sin, state.non_cos + d_cos)
    if phi_cls is not None and phi_non is not None:
        delta_min = circular_signed_diff_slots(phi_cls, phi_non) * MINUTES_PER_SLOT
        if pair_needed:
            cost -= 22.0
            if delta_min < -60.0:
                cost += 30.0
            elif delta_min > 180.0:
                cost += 12.0 + 0.02 * abs(delta_min)
            else:
                cost += 0.02 * abs(delta_min)
        elif delta_min < -60.0 or delta_min > 180.0:
            cost += 30.0
        elif delta_min < -45.0 or delta_min > 160.0:
            cost += 14.0

    if strategy_mode == "ANTI_CRAM":
        cost += 0.08 * start_slot
    elif strategy_mode in ("TIGHT_PACK", "OVERLOAD_PACK"):
        cost += 0.12 * start_slot

    flags = crit_pen + warn_pen
    return flags, cost


def _simulate_shock25_rate(state: ScheduleState) -> float:
    """Exact replica of Testing_System _simulate_shock_survival(..., +25%)."""
    ctx = state.ctx
    units = state.all_units()
    if not units:
        return 100.0
    placed_tids = {u.task_id for u in units}
    failed_tids: Set[str] = set()
    cur_end = -1
    for u in units:
        eff_start = u.start_slot if cur_end <= u.start_slot else cur_end
        shock_slots = u.duration_slots + _shock25_extra_slots(u.duration_slots)
        eff_end = eff_start + shock_slots
        if eff_end > ctx.horizon_slots:
            failed_tids.add(u.task_id)
        else:
            for s in range(eff_start, eff_end):
                if not ctx.is_free_base[s]:
                    failed_tids.add(u.task_id)
                    break
        cur_end = eff_end
    total = len(placed_tids)
    if total == 0:
        return 100.0
    return 100.0 * float(total - len(failed_tids)) / float(total)


def evaluate_state_lex_key(state: ScheduleState) -> Tuple[Any, ...]:
    """
    Fast exact 10-level bucketed lexicographic evaluation aligned with Testing_System v2.1.
    Smaller tuple is STRICTLY BETTER!
    """
    ctx = state.ctx
    units = state.all_units()

    unplaced_dl = 0
    missed_dl_priority = 0
    habit_total_slots = 0
    habit_placed_slots = 0
    pref_eligible = 0
    pref_matched_frac = 0.0
    total_placed_slots = 0

    for tid, t in ctx.tasks_by_id.items():
        if ctx.task_is_habit[tid]:
            habit_total_slots += ctx.task_planned_slots[tid]
        t_units = state.units_by_task.get(tid)
        if t_units and state.is_task_fully_placed(tid):
            p_slots = sum(u.duration_slots for u in t_units)
            total_placed_slots += p_slots
            if ctx.task_is_habit[tid]:
                habit_placed_slots += p_slots
            if t.preferred_window and t.preferred_window.strip().upper() not in ("", "ANYTIME", "NONE"):
                pref_eligible += 1
                f_sum = sum(_window_match_fraction(u.start_slot, u.duration_slots, t.preferred_window) for u in t_units)
                pref_matched_frac += f_sum / float(len(t_units))
        else:
            if ctx.task_is_deadline[tid]:
                unplaced_dl += 1
                missed_dl_priority += t.priority

    crit_count = 0
    warn_count = 0
    if state.crunch_tier_used > 0:
        warn_count += 1

    off_peak_heavy_mismatch = 0
    l3_slots_total = 0
    l3_weighted_e = 0.0
    l3_total_blocks = 0
    l3_recovered_blocks = 0
    post_class_viol = 0
    adj_heavy_pairs = 0
    max_streak_l2_slots = 0
    meal_left_l2: Set[int] = set()
    meal_right_l2: Set[int] = set()
    ctx_switches = 0
    dl_total_blocks = 0
    dl_cram_blocks = 0
    task_first_start: Dict[str, int] = {}
    task_last_end: Dict[str, int] = {}

    class_hist = [0] * SLOTS_PER_DAY
    non_class_hist = [0] * SLOTS_PER_DAY
    days_active: Set[int] = set()

    prev_u: Optional[UnitPlacement] = None
    cur_l2_chain = 0

    for u in units:
        tid_u = u.task_id
        if tid_u not in task_first_start or u.start_slot < task_first_start[tid_u]:
            task_first_start[tid_u] = u.start_slot
        if tid_u not in task_last_end or u.end_slot > task_last_end[tid_u]:
            task_last_end[tid_u] = u.end_slot
        d = u.start_slot // SLOTS_PER_DAY
        is_l3 = u.cognitive_load == 3
        is_l2p = u.cognitive_load >= 2
        dur = u.duration_slots
        for s in range(u.start_slot, u.end_slot):
            sd, tod = divmod(s, SLOTS_PER_DAY)
            days_active.add(sd)
            if sd in ctx.class_days:
                class_hist[tod] += 1
            else:
                non_class_hist[tod] += 1

        if is_l3:
            l3_total_blocks += 1
            l3_slots_total += dur
            if ctx.energy_aware:
                esum = ctx.pref_energy_sum[u.end_slot] - ctx.pref_energy_sum[u.start_slot]
                l3_weighted_e += esum
                if (ctx.pref_low[u.end_slot] - ctx.pref_low[u.start_slot]) > 0 and ctx.has_non_low_energy_span(dur):
                    off_peak_heavy_mismatch += 1
            if state.crunch_tier_used == 0 and state.is_recovery_slot(u.end_slot):
                l3_recovered_blocks += 1
            if ctx.after_long_class[u.start_slot]:
                post_class_viol += 1

        if u.deadline_slot is not None:
            dl_total_blocks += 1
            if u.start_slot >= u.deadline_slot - ERGONOMIC_CRAM_WINDOW_SLOTS:
                if u.start_slot > ctx.raw_earliest[u.task_id] + 4:
                    dl_cram_blocks += 1

        if is_l2p:
            if u.end_slot in ctx.meal_left_edge_to_id:
                meal_left_l2.add(ctx.meal_left_edge_to_id[u.end_slot])
            if u.start_slot in ctx.meal_right_edge_to_id:
                meal_right_l2.add(ctx.meal_right_edge_to_id[u.start_slot])

        same_day = prev_u is not None and (prev_u.start_slot // SLOTS_PER_DAY) == d
        gap = (u.start_slot - prev_u.end_slot) if prev_u is not None else 999
        if is_l2p and prev_u is not None and gap == 0 and prev_u.cognitive_load >= 2:
            cur_l2_chain += dur
        elif is_l2p:
            cur_l2_chain = dur
        else:
            cur_l2_chain = 0
        if prev_u is not None and gap == 0 and prev_u.cognitive_load >= 2 and is_l2p:
            if cur_l2_chain > max_streak_l2_slots:
                max_streak_l2_slots = cur_l2_chain

        if prev_u is not None and is_l3 and prev_u.cognitive_load == 3 and gap < ERGONOMIC_HEAVY_MIN_GAP_SLOTS:
            adj_heavy_pairs += 1

        if same_day and 0 <= gap <= 2 and prev_u is not None:
            if prev_u.task_id != u.task_id and prev_u.category != u.category:
                ctx_switches += 1

        prev_u = u

    if ctx.energy_aware and l3_slots_total > 0:
        apk_pct = 100.0 * (l3_weighted_e / float(l3_slots_total) - 1.0) / 2.0
        if off_peak_heavy_mismatch >= 1 or apk_pct < 25.0:
            crit_count += 1
        elif apk_pct < 50.0:
            warn_count += 1
    else:
        apk_pct = 100.0

    rec_pct = 100.0 * float(l3_recovered_blocks) / float(l3_total_blocks) if l3_total_blocks > 0 else 100.0
    if state.crunch_tier_used == 0 and l3_total_blocks > 0 and l3_recovered_blocks < l3_total_blocks:
        crit_count += 1

    if max_streak_l2_slots > ERGONOMIC_L2_STREAK_HARD_SLOTS:
        crit_count += 1
    elif max_streak_l2_slots > ERGONOMIC_L2_STREAK_SOFT_SLOTS:
        warn_count += 1

    if post_class_viol >= 2:
        crit_count += 1
    elif post_class_viol == 1:
        warn_count += 1

    heavy_overload_days = sum(1 for c in state.day_l3_count if c > ERGONOMIC_DAILY_HEAVY_CAP)
    if heavy_overload_days >= 1:
        crit_count += 1

    max_day_tot = max(
        (state.day_study_slots[d] + ctx.base_class_slots_per_day[d] for d in range(ctx.num_days)),
        default=0,
    )
    max_day_tot_min = max_day_tot * MINUTES_PER_SLOT
    if max_day_tot > ERGONOMIC_DAILY_TOTAL_HARD_SLOTS:
        crit_count += 1
    elif max_day_tot > ERGONOMIC_DAILY_TOTAL_SOFT_SLOTS:
        warn_count += 1

    if adj_heavy_pairs >= 1:
        warn_count += 1

    meal_l2_offenses = len(meal_left_l2.intersection(meal_right_l2))
    if meal_l2_offenses >= 1:
        warn_count += 1

    shock25_pct = _simulate_shock25_rate(state)
    if shock25_pct < 70.0:
        crit_count += 1
    elif shock25_pct < 85.0:
        warn_count += 1

    study_days = sum(1 for x in state.day_study_slots if x > 0)
    if ctx_switches >= max(4, study_days):
        warn_count += 1

    habit_pct = (100.0 * habit_placed_slots / float(habit_total_slots)) if habit_total_slots > 0 else 100.0
    pref_pct = (100.0 * pref_matched_frac / float(pref_eligible)) if pref_eligible > 0 else 100.0
    if ctx.rho_total <= 0.85:
        if habit_pct < 50.0:
            crit_count += 1
        elif habit_pct < 80.0 or pref_pct < 50.0:
            warn_count += 1

    cram_pct = (100.0 * dl_cram_blocks / float(dl_total_blocks)) if dl_total_blocks > 0 else 0.0
    if cram_pct > 50.0:
        crit_count += 1
    elif cram_pct > 25.0:
        warn_count += 1

    # Exact P1.2 mean heavy_onset_delay_pct matching pillars.py
    heavy_onset_rates: List[float] = []
    for tid, units_t in state.units_by_task.items():
        if ctx.task_load.get(tid, 2) == 3 and ctx.task_is_deadline.get(tid, False) and units_t:
            dl_t = ctx.raw_deadline.get(tid) or ctx.horizon_slots
            ready_t = max(
                [ctx.raw_earliest[tid]] + [task_last_end[p] for p in ctx.preds_map[tid] if p in task_last_end]
            )
            win_t = dl_t - ready_t
            if win_t > 0 and tid in task_first_start:
                heavy_onset_rates.append(max(0.0, (task_first_start[tid] - ready_t) / float(win_t)) * 100.0)
    onset_pct = (sum(heavy_onset_rates) / float(len(heavy_onset_rates))) if heavy_onset_rates else 0.0
    if onset_pct > 60.0:
        warn_count += 1

    # Exact Smarr & Schirmer circular SJL between class days & non-class days
    sjl_signed_min: Optional[float] = None
    if (days_active & ctx.class_days) and (days_active - ctx.class_days):
        phi_cls = _circular_median_tod_min(class_hist)
        phi_non = _circular_median_tod_min(non_class_hist)
        if phi_cls is not None and phi_non is not None:
            raw_d = (phi_cls - phi_non) % 1440.0
            if raw_d > 720.0:
                raw_d -= 1440.0
            sjl_signed_min = raw_d
            if sjl_signed_min < -60.0 or sjl_signed_min > 180.0:
                warn_count += 1
    sjl_neutral_unpaired = (
        sjl_signed_min is None
        and bool(ctx.free_days_in_scope & ctx.class_days)
        and bool(ctx.free_days_in_scope - ctx.class_days)
        and len(units) >= 3
    )
    sjl_eff = 90.0 if sjl_neutral_unpaired else (abs(sjl_signed_min) if sjl_signed_min is not None else 0.0)

    eval_days = (max(ctx.free_days_in_scope) + 1) if ctx.free_days_in_scope else ctx.num_days
    eval_days = max(1, min(ctx.num_days, eval_days))
    tot_per_day = [
        (state.day_study_slots[d] + ctx.base_class_slots_per_day[d]) * MINUTES_PER_SLOT
        for d in range(eval_days)
    ]
    mean_tot = sum(tot_per_day) / float(eval_days)
    tstd_min = math.sqrt(sum((x - mean_tot) ** 2 for x in tot_per_day) / float(eval_days))
    tstd_thresh = max(ERGONOMIC_DAILY_STD_FLOOR_MIN, ctx.base_class_std_min + ERGONOMIC_DAILY_STD_BASE_TOL_MIN)
    if tstd_min > tstd_thresh:
        warn_count += 1

    if unplaced_dl > 0:
        verdict_bucket = 2
    elif crit_count == 0 and warn_count <= 1:
        verdict_bucket = 0
    else:
        verdict_bucket = 1

    max_streak_l2_min = max_streak_l2_slots * MINUTES_PER_SLOT
    return (
        0 if unplaced_dl == 0 else 1,
        verdict_bucket,
        missed_dl_priority,
        crit_count,
        max(0, warn_count - 1),
        warn_count + (2 if sjl_neutral_unpaired else 0),
        -int(shock25_pct // 5) * 5,
        round(-shock25_pct, 2),
        -int(rec_pct // 5) * 5,
        max(0, max_streak_l2_min - 90) // 30,
        post_class_viol,
        off_peak_heavy_mismatch,
        -int(apk_pct // 10) * 10,
        round(-apk_pct, 2),
        int(cram_pct // 5) * 5,
        round(cram_pct, 2),
        heavy_overload_days,
        max(0, max_day_tot_min - 540) // 30,
        adj_heavy_pairs,
        meal_l2_offenses,
        ctx_switches,
        -int(habit_pct // 10) * 10,
        -int(pref_pct // 10) * 10,
        int(sjl_eff // 30) * 30,
        int(tstd_min // 30) * 30,
        round(tstd_min, 2),
        -total_placed_slots,
    )


def is_perfect_ergonomic_key(key: Tuple[Any, ...]) -> bool:
    """Return True when state meets strict zero-defect, zero-warn, full shock/peak & paired-SJL quality."""
    return (
        key[0] == 0
        and key[3] == 0
        and key[5] == 0
        and key[7] <= -99.9
        and key[13] <= -99.9
        and key[23] <= 90
    )


def _find_best_chunks_assignment(
    state: ScheduleState,
    task: Task,
    chunk_options: List[List[TaskChunk]],
    strategy_mode: str = "ERGONOMIC",
    strict_crit_zero: bool = True,
) -> Optional[List[UnitPlacement]]:
    """
    Search valid non-overlapping sequential placements across all chunking variants of `task`.
    Enforces DAG predecessor end_slot, partial-pinned end_slot, start_after, and deadline_slot.
    """
    ctx = state.ctx
    tid = task.task_id
    pred_end = ctx.raw_earliest[tid]
    for p in ctx.preds_map[tid]:
        if not state.is_task_fully_placed(p):
            return None  # Prerequisite not placed -> cannot place successor!
        pend = state.task_max_end_slot(p)
        if pend is not None and pend > pred_end:
            pred_end = pend

    pinned_idxs = ctx.pinned_chunk_indices_by_task.get(tid)
    if pinned_idxs:
        # Honor partial pinned chunk end_slot & only schedule missing default chunks
        p_end = ctx.pinned_end_by_task.get(tid, 0)
        if p_end > pred_end:
            pred_end = p_end
        filtered_opts = [
            [c for c in ctx.default_chunks_by_task[tid] if c.chunk_index not in pinned_idxs]
        ]
        if not filtered_opts[0]:
            return []
        chunk_options = filtered_opts

    dl = ctx.raw_deadline[tid]
    upper_end = dl if dl is not None else ctx.horizon_slots
    upper_end = min(upper_end, ctx.horizon_slots)

    total_need = sum(c.duration_slots for c in chunk_options[0])
    if pred_end + total_need > upper_end:
        return None

    best_score: Optional[Tuple[int, float]] = None
    best_units: Optional[List[UnitPlacement]] = None
    ld = ctx.task_load[tid]

    for chunks in chunk_options:
        k = len(chunks)
        if k == 1:
            ch = chunks[0]
            dur = ch.duration_slots
            max_st = upper_end - dur
            if pred_end > max_st:
                continue
            for s in range(pred_end, max_st + 1):
                if not ctx.is_free_base[s] or state.slot_owner[s]:
                    continue
                if not state.is_span_available(s, s + dur):
                    continue
                flags, cost = score_candidate_unit(state, task, ch, s, strategy_mode=strategy_mode)
                if strict_crit_zero and flags >= 35:
                    continue
                cand_score = (flags, cost)
                if best_score is None or cand_score < best_score:
                    best_score = cand_score
                    best_units = [
                        UnitPlacement(
                            task_id=tid,
                            chunk_index=ch.chunk_index,
                            total_chunks=ch.total_chunks,
                            start_slot=s,
                            end_slot=s + dur,
                            duration_slots=dur,
                            cognitive_load=ld,
                            priority=task.priority,
                            category=task.category,
                            preferred_window=task.preferred_window,
                            deadline_slot=ctx.raw_deadline[tid],
                        )
                    ]
        else:
            # Multi-chunk DP / greedy chain over top candidate starts per chunk
            seq_assign = _place_multichunk_chain(
                state, task, chunks, pred_end, upper_end, strategy_mode, strict_crit_zero
            )
            if seq_assign is not None:
                c_score, c_units = seq_assign
                if best_score is None or c_score < best_score:
                    best_score = c_score
                    best_units = c_units

        # Short-circuit if default chunking already achieved crisp zero-flag placement
        if best_score is not None and best_score[0] == 0 and best_score[1] < 6.0 and chunks is chunk_options[0]:
            break

    return best_units


def _place_multichunk_chain(
    state: ScheduleState,
    task: Task,
    chunks: List[TaskChunk],
    earliest_slot: int,
    upper_end: int,
    strategy_mode: str,
    strict_crit_zero: bool,
) -> Optional[Tuple[Tuple[int, float], List[UnitPlacement]]]:
    """Place a multi-chunk splittable task deterministically respecting intra-task gaps & daily L3 caps."""
    ctx = state.ctx
    tid = task.task_id
    ld = ctx.task_load[tid]
    k = len(chunks)
    min_gap = 2 if (ld == 3 and strict_crit_zero) else (1 if ld >= 2 or state.crunch_tier_used == 0 else 0)

    # Compute remaining suffixes for tight upper bounds
    rem_dur = [0] * (k + 1)
    for i in range(k - 1, -1, -1):
        rem_dur[i] = rem_dur[i + 1] + chunks[i].duration_slots

    temp = state.clone()
    chosen: List[UnitPlacement] = []
    tot_flags = 0
    tot_cost = 0.0
    cur_earliest = earliest_slot

    for idx, ch in enumerate(chunks):
        dur = ch.duration_slots
        max_st = upper_end - rem_dur[idx] - (min_gap * (k - 1 - idx) if min_gap > 0 else 0)
        if max_st < cur_earliest:
            # Retry without mandatory intra-task gap if tight!
            max_st = upper_end - rem_dur[idx]
        if max_st < cur_earliest:
            return None

        best_c_score: Optional[Tuple[int, float]] = None
        best_s: Optional[int] = None
        last_day = chosen[-1].start_slot // SLOTS_PER_DAY if chosen else -1

        for s in range(cur_earliest, max_st + 1):
            if not ctx.is_free_base[s] or temp.slot_owner[s]:
                continue
            e = s + dur
            if not temp.is_span_available(s, e):
                continue
            flags, cost = score_candidate_unit(temp, task, ch, s, strategy_mode=strategy_mode)
            if strict_crit_zero and flags >= 35:
                continue
            # Spread chunks across different days when possible (boosts TStd + avoids L3 daily cap!)
            if (s // SLOTS_PER_DAY) != last_day:
                cost -= 2.5
            else:
                cost += 1.5
            c_sc = (flags, cost)
            if best_c_score is None or c_sc < best_c_score:
                best_c_score = c_sc
                best_s = s

        if best_s is None or best_c_score is None:
            return None

        tot_flags += best_c_score[0]
        tot_cost += best_c_score[1]
        unit = UnitPlacement(
            task_id=tid,
            chunk_index=ch.chunk_index,
            total_chunks=ch.total_chunks,
            start_slot=best_s,
            end_slot=best_s + dur,
            duration_slots=dur,
            cognitive_load=ld,
            priority=task.priority,
            category=task.category,
            preferred_window=task.preferred_window,
            deadline_slot=ctx.raw_deadline[tid],
        )
        temp.add_unit(unit)
        chosen.append(unit)
        cur_earliest = best_s + dur + min_gap

    return (tot_flags, tot_cost), chosen


def _topological_ordered_ids(
    ctx: ErgonomicContext,
    key_fn: Any,
) -> List[str]:
    """Deterministic priority-queue topological sort using `key_fn(tid)`."""
    import heapq

    in_deg = {tid: 0 for tid in ctx.tasks_by_id}
    for tid in ctx.tasks_by_id:
        in_deg[tid] = len(ctx.preds_map[tid])

    heap: List[Tuple[Any, str]] = []
    for tid, deg in in_deg.items():
        if deg == 0:
            heapq.heappush(heap, (key_fn(tid), tid))

    order: List[str] = []
    while heap:
        _, u = heapq.heappop(heap)
        order.append(u)
        for v in ctx.succs_map[u]:
            in_deg[v] -= 1
            if in_deg[v] == 0:
                heapq.heappush(heap, (key_fn(v), v))
    return order


def order_key_edf_ergonomic(ctx: ErgonomicContext, tid: str) -> Tuple[Any, ...]:
    t = ctx.tasks_by_id[tid]
    dl = ctx.eff_deadline[tid]
    return (
        0 if dl is not None else 1,
        dl if dl is not None else 999999,
        -ctx.task_load[tid],
        -t.priority,
        -ctx.descendant_count[tid],
        ctx.task_planned_slots[tid],
        tid,
    )


def order_key_heavy_peak_first(ctx: ErgonomicContext, tid: str) -> Tuple[Any, ...]:
    t = ctx.tasks_by_id[tid]
    dl = ctx.eff_deadline[tid]
    return (
        0 if dl is not None else 1,
        -ctx.task_load[tid],
        dl if dl is not None else 999999,
        -t.priority,
        -ctx.descendant_count[tid],
        tid,
    )


def order_key_dag_slack_urgency(ctx: ErgonomicContext, tid: str) -> Tuple[Any, ...]:
    t = ctx.tasks_by_id[tid]
    dl = ctx.eff_deadline[tid]
    slack = (dl - ctx.eff_earliest[tid] - ctx.task_planned_slots[tid]) if dl is not None else 999999
    return (
        0 if dl is not None else 1,
        slack,
        dl if dl is not None else 999999,
        -t.priority,
        -ctx.task_load[tid],
        tid,
    )


def order_key_wspt_value(ctx: ErgonomicContext, tid: str) -> Tuple[Any, ...]:
    t = ctx.tasks_by_id[tid]
    dl = ctx.eff_deadline[tid]
    dur = max(1, ctx.task_planned_slots[tid])
    ratio = -float(t.priority + 1) / float(dur)
    return (
        0 if dl is not None else 1,
        round(ratio, 6),
        dl if dl is not None else 999999,
        -t.priority,
        dur,
        tid,
    )


def order_key_overload_knapsack(ctx: ErgonomicContext, tid: str) -> Tuple[Any, ...]:
    t = ctx.tasks_by_id[tid]
    dl = ctx.eff_deadline[tid]
    dur = max(1, ctx.task_planned_slots[tid])
    return (
        0 if dl is not None else 1,
        round(-float(t.priority) / float(dur), 6),
        -t.priority,
        dl if dl is not None else 999999,
        tid,
    )


def order_key_priority_first(ctx: ErgonomicContext, tid: str) -> Tuple[Any, ...]:
    t = ctx.tasks_by_id[tid]
    dl = ctx.eff_deadline[tid]
    dur = ctx.task_planned_slots[tid]
    return (
        0 if dl is not None else 1,
        -t.priority,
        dur,
        dl if dl is not None else 999999,
        tid,
    )


def _overload_priority_swap(state: ScheduleState, deadline_ts: Optional[float] = None) -> None:
    """Under overload, eject placed lower-priority deadline tasks when doing so admits higher-priority unplaced ones."""
    ctx = state.ctx
    unplaced_dl = sorted(
        [
            tid
            for tid in ctx.topo_order
            if ctx.task_is_deadline[tid]
            and not state.is_task_fully_placed(tid)
            and all(state.is_task_fully_placed(p) for p in ctx.preds_map[tid])
        ],
        key=lambda tid: (-ctx.tasks_by_id[tid].priority, ctx.task_planned_slots[tid], tid),
    )
    for tid in unplaced_dl:
        if deadline_ts is not None and time.perf_counter() > deadline_ts:
            break
        t = ctx.tasks_by_id[tid]
        dl = ctx.raw_deadline[tid]
        earliest = max([ctx.raw_earliest[tid]] + [state.task_max_end_slot(p) or 0 for p in ctx.preds_map[tid]])
        end_bound = min(dl if dl is not None else ctx.horizon_slots, ctx.horizon_slots)
        if earliest + ctx.task_planned_slots[tid] > end_bound:
            continue

        # Lower-priority placed candidates overlapping target window (skip pinned & preds)
        cand_victims = []
        for vid, units in state.units_by_task.items():
            if any(u.is_pinned for u in units) or vid == tid or vid in ctx.preds_map[tid]:
                continue
            vt = ctx.tasks_by_id[vid]
            if not ctx.task_is_deadline[vid] or vt.priority < t.priority:
                if any(u.end_slot > earliest and u.start_slot < end_bound for u in units):
                    cand_victims.append(vid)
        cand_victims.sort(
            key=lambda vid: (0 if not ctx.task_is_deadline[vid] else 1, ctx.tasks_by_id[vid].priority, -ctx.task_planned_slots[vid], vid)
        )

        # Single victim swap
        swapped = False
        cur_key = evaluate_state_lex_key(state)
        for vid in cand_victims[:12]:
            trial = state.clone()
            deps = [vid] + [s for s in ctx.succs_map[vid] if trial.has_task_placed(s)]
            lost_prio = sum(ctx.tasks_by_id[x].priority for x in deps if ctx.task_is_deadline[x])
            if lost_prio >= t.priority:
                continue
            for d_id in reversed(deps):
                trial.remove_task(d_id)
            t_units = _find_best_chunks_assignment(
                trial, t, ctx.split_options_by_task[tid], strategy_mode="TIGHT_PACK", strict_crit_zero=False
            )
            if t_units is None:
                continue
            for u in t_units:
                trial.add_unit(u)
            if evaluate_state_lex_key(trial) < cur_key:
                for old_tid in list(state.units_by_task.keys()):
                    state.remove_task(old_tid)
                for u_new in trial.all_units():
                    if not u_new.is_pinned:
                        state.add_unit(u_new)
                swapped = True
                break

        # Pair victim swap if single didn't fit
        if not swapped and len(cand_victims) >= 2:
            top_v = cand_victims[:8]
            for i in range(len(top_v)):
                if swapped:
                    break
                for j in range(i + 1, len(top_v)):
                    v1, v2 = top_v[i], top_v[j]
                    trial = state.clone()
                    deps_set: Set[str] = {v1, v2}
                    for s in ctx.succs_map[v1] + ctx.succs_map[v2]:
                        if trial.has_task_placed(s):
                            deps_set.add(s)
                    lost_prio = sum(ctx.tasks_by_id[x].priority for x in deps_set if ctx.task_is_deadline[x])
                    if lost_prio >= t.priority:
                        continue
                    for d_id in reversed([x for x in ctx.topo_order if x in deps_set]):
                        trial.remove_task(d_id)
                    t_units = _find_best_chunks_assignment(
                        trial, t, ctx.split_options_by_task[tid], strategy_mode="TIGHT_PACK", strict_crit_zero=False
                    )
                    if t_units is None:
                        continue
                    for u in t_units:
                        trial.add_unit(u)
                    if evaluate_state_lex_key(trial) < cur_key:
                        for old_tid in list(state.units_by_task.keys()):
                            state.remove_task(old_tid)
                        for u_new in trial.all_units():
                            if not u_new.is_pinned:
                                state.add_unit(u_new)
                        swapped = True
                        break


def build_constructive_solution(
    ctx: ErgonomicContext,
    pinned_units: List[UnitPlacement],
    order_key_fn: Any,
    strategy_mode: str = "ERGONOMIC",
    enable_rescue: bool = True,
    overload_pack: bool = False,
    time_budget_sec: Optional[float] = None,
    start_ts: Optional[float] = None,
) -> ScheduleState:
    """
    Two-pass constructive builder:
      Pass A: Tier-0 ergonomic placement respecting daily/recovery/streak/peak guards
              (or priority-maximizing direct placement when `overload_pack=True`).
      Pass B: Feasibility-First Rescue for unplaced deadline tasks + optional overload priority swaps.
    """
    state = ScheduleState(ctx, pinned_units=pinned_units)
    order = _topological_ordered_ids(ctx, key_fn=lambda tid: order_key_fn(ctx, tid))

    deadline_ids = [tid for tid in order if ctx.task_is_deadline[tid]]
    habit_ids = [tid for tid in order if not ctx.task_is_deadline[tid]]

    unplaced_dl: List[str] = []
    t0 = start_ts if start_ts is not None else time.perf_counter()

    # Pass A1: Deadline tasks using primary split only (always completes Pass A1 cleanly without aborting mid-task)
    for tid in deadline_ids:
        if state.is_task_fully_placed(tid):
            continue
        t = ctx.tasks_by_id[tid]
        opts = ctx.split_options_by_task[tid]
        assigned = _find_best_chunks_assignment(
            state, t, opts[:1], strategy_mode=strategy_mode, strict_crit_zero=not overload_pack
        )
        if assigned is not None:
            for u in assigned:
                state.add_unit(u)
        else:
            unplaced_dl.append(tid)

    # Pass A2 & Pass B rescues for unplaced deadline tasks
    # Use outer safety cap on feasible workloads so tight budgets never abort rescue on 14-day instances;
    # under large overload (>25 tasks, rho_dl > 1), bound rescue strictly by time_budget_sec.
    outer_cap = max(time_budget_sec, 0.72) if time_budget_sec is not None else None
    is_large_overload = overload_pack and ctx.rho_deadline > 1.0
    if is_large_overload:
        rescue_dl_ts = (t0 + time_budget_sec) if time_budget_sec is not None else None
        run_a2 = enable_rescue and bool(unplaced_dl) and len(ctx.tasks_by_id) <= 25 and (
            rescue_dl_ts is None or time.perf_counter() < rescue_dl_ts
        )
    else:
        rescue_dl_ts = (t0 + outer_cap) if outer_cap is not None else None
        run_a2 = enable_rescue and bool(unplaced_dl) and (
            rescue_dl_ts is None or time.perf_counter() < rescue_dl_ts
        )
    if run_a2:
        unplaced_dl = _rescue_unplaced_deadlines(
            state, unplaced_dl, strategy_mode=strategy_mode, deadline_ts=rescue_dl_ts
        )
    if enable_rescue and unplaced_dl and (rescue_dl_ts is None or time.perf_counter() < rescue_dl_ts):
        still_unplaced: List[str] = []
        for idx, tid in enumerate(unplaced_dl):
            if rescue_dl_ts is not None and time.perf_counter() > rescue_dl_ts:
                still_unplaced.extend(unplaced_dl[idx:])
                break
            if state.is_task_fully_placed(tid):
                continue
            t = ctx.tasks_by_id[tid]
            assigned = _find_best_chunks_assignment(
                state,
                t,
                ctx.split_options_by_task[tid],
                strategy_mode="TIGHT_PACK",
                strict_crit_zero=False,
            )
            if assigned is not None:
                for u in assigned:
                    state.add_unit(u)
            else:
                still_unplaced.append(tid)
        unplaced_dl = still_unplaced

    # Skip slow Kempe combinatorial pair-ejection when structurally overloaded or large/time-capped
    if (
        enable_rescue
        and unplaced_dl
        and ctx.rho_deadline <= 1.0
        and len(ctx.tasks_by_id) <= 30
        and (time_budget_sec is None or (time.perf_counter() - t0) < time_budget_sec * 0.85)
    ):
        unplaced_dl = _kempe_eject_rescue(state, unplaced_dl)

    if overload_pack and unplaced_dl and (time_budget_sec is None or (time.perf_counter() - t0) < time_budget_sec):
        dl_ts = (t0 + time_budget_sec) if time_budget_sec is not None else None
        _overload_priority_swap(state, deadline_ts=dl_ts)
        _overload_priority_swap(state, deadline_ts=dl_ts)

    # Pass C: Habits / non-deadline tasks in remaining ergonomic capacity
    for tid in habit_ids:
        if state.is_task_fully_placed(tid):
            continue
        t = ctx.tasks_by_id[tid]
        opts = ctx.split_options_by_task[tid]
        assigned = _find_best_chunks_assignment(
            state, t, opts[:1], strategy_mode=strategy_mode, strict_crit_zero=True
        )
        if assigned is None:
            assigned = _find_best_chunks_assignment(
                state, t, opts[:2], strategy_mode=strategy_mode, strict_crit_zero=False
            )
        if assigned is not None:
            cand_state = state.clone()
            for u in assigned:
                cand_state.add_unit(u)
            if evaluate_state_lex_key(cand_state)[:4] <= evaluate_state_lex_key(state)[:4] or ctx.rho_total <= 0.85:
                state = cand_state

    return state


def build_feasibility_first_fit_state(
    ctx: ErgonomicContext,
    pinned_units: List[UnitPlacement],
) -> ScheduleState:
    """
    Ultra-fast chronological First-Fit EDF feasibility floor (`min_gap=0` across multi-chunks).
    Guarantees <= EDF suboptimal rate whenever deadlines are tightly packable (~10 ms).
    """
    state = ScheduleState(ctx, pinned_units=pinned_units)
    order = _topological_ordered_ids(
        ctx,
        key_fn=lambda tid: (
            0 if ctx.task_is_deadline[tid] else 1,
            ctx.raw_deadline[tid] if ctx.raw_deadline[tid] is not None else 999999,
            ctx.eff_deadline[tid] if ctx.eff_deadline[tid] is not None else 999999,
            -ctx.tasks_by_id[tid].priority,
            tid,
        ),
    )
    for tid in order:
        if state.is_task_fully_placed(tid):
            continue
        if any(not state.is_task_fully_placed(p) for p in ctx.preds_map[tid]):
            continue
        t = ctx.tasks_by_id[tid]
        ld = ctx.task_load[tid]
        dl = ctx.raw_deadline[tid]
        upper_end = min(dl if dl is not None else ctx.horizon_slots, ctx.horizon_slots)
        earliest = max(
            [ctx.raw_earliest[tid]] + [state.task_max_end_slot(p) or 0 for p in ctx.preds_map[tid]]
        )
        pinned_idxs = ctx.pinned_chunk_indices_by_task.get(tid)
        if pinned_idxs:
            p_end = ctx.pinned_end_by_task.get(tid, 0)
            if p_end > earliest:
                earliest = p_end
            opts = [[c for c in ctx.default_chunks_by_task[tid] if c.chunk_index not in pinned_idxs]]
        else:
            opts = ctx.split_options_by_task[tid]

        for chunks in opts:
            if not chunks:
                continue
            cur = earliest
            temp_units: List[UnitPlacement] = []
            ok = True
            for ch in chunks:
                dur = ch.duration_slots
                max_st = upper_end - dur
                placed_s: Optional[int] = None
                for s in range(cur, max_st + 1):
                    if not ctx.is_free_base[s] or state.slot_owner[s]:
                        continue
                    if state.is_span_available(s, s + dur):
                        placed_s = s
                        break
                if placed_s is None:
                    ok = False
                    break
                temp_units.append(
                    UnitPlacement(
                        task_id=tid,
                        chunk_index=ch.chunk_index,
                        total_chunks=ch.total_chunks,
                        start_slot=placed_s,
                        end_slot=placed_s + dur,
                        duration_slots=dur,
                        cognitive_load=ld,
                        priority=t.priority,
                        category=t.category,
                        preferred_window=t.preferred_window,
                        deadline_slot=dl,
                    )
                )
                cur = placed_s + dur
            if ok:
                for u in temp_units:
                    state.add_unit(u)
                break
    return state


def _rescue_unplaced_deadlines(
    state: ScheduleState,
    unplaced_dl: List[str],
    strategy_mode: str,
    deadline_ts: Optional[float] = None,
) -> List[str]:
    """Try adaptive split + local shift rescue on currently unplaced deadline tasks."""
    ctx = state.ctx
    # Sort tightly by earliest effective deadline first
    queue = sorted(unplaced_dl, key=lambda tid: (ctx.eff_deadline[tid] or 999999, -ctx.tasks_by_id[tid].priority, tid))
    remaining: List[str] = []
    for idx, tid in enumerate(queue):
        if deadline_ts is not None and time.perf_counter() > deadline_ts:
            remaining.extend(queue[idx:])
            break
        if state.has_task_placed(tid):
            continue
        t = ctx.tasks_by_id[tid]
        # First retry strict with all split options reversed/expanded
        opts = ctx.split_options_by_task[tid]
        assigned = _find_best_chunks_assignment(
            state, t, opts, strategy_mode="ANTI_CRAM", strict_crit_zero=True
        )
        if assigned is None:
            assigned = _find_best_chunks_assignment(
                state, t, opts, strategy_mode="TIGHT_PACK", strict_crit_zero=False
            )
        if assigned is not None:
            for u in assigned:
                state.add_unit(u)
        else:
            remaining.append(tid)
    return remaining


def _kempe_eject_rescue(state: ScheduleState, unplaced_dl: List[str]) -> List[str]:
    """
    Kempe 1-eject / 2-eject rescue: Temporarily eject placed blocks whose deadline is
    later (or non-deadline / lower priority), insert `target`, then re-insert ejected blocks!
    Also supports shifting a blocking task earlier/later to open a contiguous hole.
    """
    ctx = state.ctx
    remaining: List[str] = []
    queue = sorted(unplaced_dl, key=lambda tid: (ctx.eff_deadline[tid] or 999999, -ctx.tasks_by_id[tid].priority, tid))

    for tid in queue:
        if state.has_task_placed(tid):
            continue
        t = ctx.tasks_by_id[tid]
        # Ensure all predecessors are already placed
        if any(not state.has_task_placed(p) for p in ctx.preds_map[tid]):
            remaining.append(tid)
            continue

        dl = ctx.raw_deadline[tid]
        earliest = max([ctx.raw_earliest[tid]] + [state.task_max_end_slot(p) or 0 for p in ctx.preds_map[tid]])
        end_bound = min(dl if dl is not None else ctx.horizon_slots, ctx.horizon_slots)
        need_slots = ctx.task_planned_slots[tid]
        if earliest + need_slots > end_bound:
            remaining.append(tid)
            continue

        # Collect candidate blocking tasks overlapping [earliest, end_bound)
        blockers: Set[str] = set()
        for b_tid, units in state.units_by_task.items():
            if any(u.is_pinned for u in units):
                continue
            if b_tid == tid or b_tid in ctx.preds_map[tid]:
                continue
            # Also skip if tid is a predecessor of b_tid unless we re-insert b_tid after tid
            for u in units:
                if u.end_slot > earliest and u.start_slot < end_bound:
                    blockers.add(b_tid)
                    break

        # Order blockers: non-deadline first, then slackiest / later deadline / lower priority
        ordered_blockers = sorted(
            blockers,
            key=lambda bid: (
                0 if not ctx.task_is_deadline[bid] else 1,
                -(ctx.eff_deadline[bid] or 999999),
                ctx.tasks_by_id[bid].priority,
                bid,
            ),
        )

        rescued = False
        # 1. Single blocker ejection
        for bid in ordered_blockers[:16]:
            trial = state.clone()
            # Also detach any dependents of bid if needed
            deps_to_reinsert = [bid] + [s for s in ctx.succs_map[bid] if trial.has_task_placed(s)]
            for d_id in reversed(deps_to_reinsert):
                trial.remove_task(d_id)

            target_units = _find_best_chunks_assignment(
                trial, t, ctx.split_options_by_task[tid], strategy_mode="TIGHT_PACK", strict_crit_zero=False
            )
            if target_units is None:
                continue
            for u in target_units:
                trial.add_unit(u)

            ok_reinsert = True
            for d_id in deps_to_reinsert:
                dt = ctx.tasks_by_id[d_id]
                re_units = _find_best_chunks_assignment(
                    trial, dt, ctx.split_options_by_task[d_id], strategy_mode="TIGHT_PACK", strict_crit_zero=False
                )
                if re_units is None:
                    ok_reinsert = False
                    break
                for u in re_units:
                    trial.add_unit(u)

            if ok_reinsert:
                # Commit into live state cleanly
                for u_old_tid in list(state.units_by_task.keys()):
                    state.remove_task(u_old_tid)
                for u_new in trial.all_units():
                    if not u_new.is_pinned:
                        state.add_unit(u_new)
                rescued = True
                break

        # 2. Pair ejection if 1-eject wasn't enough on tight deadlines
        if not rescued and len(ordered_blockers) >= 2:
            top_b = ordered_blockers[:8]
            for i in range(len(top_b)):
                if rescued:
                    break
                for j in range(i + 1, len(top_b)):
                    b1, b2 = top_b[i], top_b[j]
                    trial = state.clone()
                    to_re = []
                    for bid in (b1, b2):
                        if bid not in to_re:
                            to_re.append(bid)
                        for s in ctx.succs_map[bid]:
                            if s not in to_re and trial.has_task_placed(s):
                                to_re.append(s)
                    # Topologically sort reinsertion list
                    re_set = set(to_re)
                    to_re_sorted = [x for x in ctx.topo_order if x in re_set]
                    for d_id in reversed(to_re_sorted):
                        trial.remove_task(d_id)
                    target_units = _find_best_chunks_assignment(
                        trial, t, ctx.split_options_by_task[tid], strategy_mode="TIGHT_PACK", strict_crit_zero=False
                    )
                    if target_units is None:
                        continue
                    for u in target_units:
                        trial.add_unit(u)
                    ok_re = True
                    for d_id in to_re_sorted:
                        dt = ctx.tasks_by_id[d_id]
                        re_units = _find_best_chunks_assignment(
                            trial, dt, ctx.split_options_by_task[d_id], strategy_mode="TIGHT_PACK", strict_crit_zero=False
                        )
                        if re_units is None:
                            ok_re = False
                            break
                        for u in re_units:
                            trial.add_unit(u)
                    if ok_re:
                        for u_old_tid in list(state.units_by_task.keys()):
                            state.remove_task(u_old_tid)
                        for u_new in trial.all_units():
                            if not u_new.is_pinned:
                                state.add_unit(u_new)
                        rescued = True
                        break

        if not rescued:
            remaining.append(tid)

    return remaining


def _task_temporal_window(state: ScheduleState, tid: str) -> Tuple[int, int]:
    """Compute exact legal [earliest_start, latest_end] for task `tid` given placed neighbors."""
    ctx = state.ctx
    earliest = ctx.raw_earliest[tid]
    for p in ctx.preds_map[tid]:
        pe = state.task_max_end_slot(p)
        if pe is not None and pe > earliest:
            earliest = pe

    dl = ctx.raw_deadline[tid]
    latest = dl if dl is not None else ctx.horizon_slots
    for s in ctx.succs_map[tid]:
        s_units = state.units_by_task.get(s)
        if s_units:
            min_s = min(u.start_slot for u in s_units)
            if min_s < latest:
                latest = min_s
    return earliest, min(latest, ctx.horizon_slots)


def polish_schedule_deterministic(
    state: ScheduleState,
    max_passes: int = GREEDY_POLISH_MAX_PASSES,
    time_budget_sec: float = GREEDY_TIME_BUDGET_SEC,
    start_ts: Optional[float] = None,
) -> ScheduleState:
    """
    Deterministic iterative local search optimizing exact `evaluate_state_lex_key`:
      1. Try placing any unplaced high-value / deadline tasks.
      2. For each non-pinned placed task (or individual chunk), search legal repositioning &
         adaptive G1-legal splits across the horizon (focusing on CRIT/WARN repairs,
         better Peak energy alignment, +25% shock survival gaps, SJL & TStd balance).
      3. Try swapping two placed tasks' slots / days when moving 1 alone is blocked.
    """
    ctx = state.ctx
    t0 = start_ts if start_ts is not None else time.perf_counter()
    best = state.clone()
    best_key = evaluate_state_lex_key(best)
    if (time.perf_counter() - t0) > time_budget_sec:
        return best

    unplaced_dl = [tid for tid in ctx.topo_order if ctx.task_is_deadline[tid] and not best.has_task_placed(tid)]
    if unplaced_dl and ctx.rho_deadline <= 1.0 and len(ctx.tasks_by_id) <= 30:
        _kempe_eject_rescue(best, unplaced_dl)
        new_key = evaluate_state_lex_key(best)
        if new_key < best_key:
            best_key = new_key
    elif unplaced_dl and ctx.rho_deadline > 1.0:
        _overload_priority_swap(best)
        new_key = evaluate_state_lex_key(best)
        if new_key < best_key:
            best_key = new_key

    for _pass in range(max_passes):
        if time.perf_counter() - t0 > time_budget_sec:
            break
        improved = False

        # Move / Resplit pass over placed tasks
        culprits_set = set(_identify_culprit_tasks(best))
        placed_list = sorted(
            best.units_by_task.keys(),
            key=lambda tid: (-ctx.task_load[tid], -ctx.tasks_by_id[tid].priority, tid),
        )
        if ctx.horizon_slots > 700 or len(placed_list) > 20:
            if best_key[0] == 0 and best_key[1] == 0 and best_key[3] == 0 and best_key[5] == 0:
                placed_list = [tid for tid in placed_list if tid in culprits_set]
            else:
                placed_list.sort(
                    key=lambda tid: (
                        0 if tid in culprits_set else 1,
                        -ctx.task_load[tid],
                        -ctx.tasks_by_id[tid].priority,
                        tid,
                    )
                )
        small_exact_mode = (
            ctx.energy_aware
            and len(placed_list) <= 14
            and (best_key[1] > 0 or best_key[5] > 0 or best_key[23] > 0 or best_key[24] > 0)
        )
        for tid in placed_list:
            if time.perf_counter() - t0 > time_budget_sec:
                break
            cur_units = best.units_by_task.get(tid, [])
            if not cur_units or any(u.is_pinned for u in cur_units):
                continue

            earliest, latest = _task_temporal_window(best, tid)
            t = ctx.tasks_by_id[tid]
            clean_trial = best.clone()
            clean_trial.remove_task(tid)

            # Evaluate candidate re-placements cleanly constrained to [earliest, latest]
            trial = clean_trial.clone()
            cand_units = _find_best_chunks_assignment_windowed(
                trial, t, ctx.split_options_by_task[tid], earliest, latest
            )
            if cand_units is not None:
                for u in cand_units:
                    trial.add_unit(u)
                cand_key = evaluate_state_lex_key(trial)
                if cand_key < best_key:
                    best = trial
                    best_key = cand_key
                    improved = True
                    continue

            # Exact per-day lex check on small instances (captures coupled SJL + TStd improvements)
            if small_exact_mode and len(ctx.default_chunks_by_task[tid]) == 1 and (time.perf_counter() - t0) <= time_budget_sec:
                ch = ctx.default_chunks_by_task[tid][0]
                dur = ch.duration_slots
                ld = ctx.task_load[tid]
                best_per_day: Dict[int, Tuple[Tuple[int, float], int]] = {}
                for s in range(earliest, min(latest, ctx.horizon_slots) - dur + 1):
                    if not ctx.is_free_base[s] or clean_trial.slot_owner[s]:
                        continue
                    if not clean_trial.is_span_available(s, s + dur):
                        continue
                    flags, cost = score_candidate_unit(clean_trial, t, ch, s, strategy_mode="ERGONOMIC")
                    if flags >= 35:
                        continue
                    d = s // SLOTS_PER_DAY
                    sc = (flags, cost)
                    prev_b = best_per_day.get(d)
                    if prev_b is None or sc < prev_b[0]:
                        best_per_day[d] = (sc, s)
                for _sc, s in sorted(best_per_day.values(), key=lambda x: x[0]):
                    t2 = clean_trial.clone()
                    t2.add_unit(
                        UnitPlacement(
                            task_id=tid,
                            chunk_index=ch.chunk_index,
                            total_chunks=ch.total_chunks,
                            start_slot=s,
                            end_slot=s + dur,
                            duration_slots=dur,
                            cognitive_load=ld,
                            priority=t.priority,
                            category=t.category,
                            preferred_window=t.preferred_window,
                            deadline_slot=ctx.raw_deadline[tid],
                        )
                    )
                    k2 = evaluate_state_lex_key(t2)
                    if k2 < best_key:
                        best = t2
                        best_key = k2
                        improved = True

        # Swap pair pass (swap two non-pinned single-chunk tasks or exchange day placement)
        single_tids = [
            tid
            for tid, units in best.units_by_task.items()
            if len(units) == 1 and not units[0].is_pinned and not ctx.preds_map[tid] and not ctx.succs_map[tid]
        ]
        if len(single_tids) >= 2 and (best_key[1] > 0 or best_key[5] > 0 or best_key[25] > 120.0):
            # Prioritize heavy/high-var tasks swaps cleanly bounded
            single_tids.sort(key=lambda tid: (-ctx.task_load[tid], tid))
            limit_n = min(len(single_tids), 14)
            for i in range(limit_n):
                if time.perf_counter() - t0 > time_budget_sec:
                    break
                a = single_tids[i]
                ua = best.units_by_task[a][0]
                for j in range(i + 1, limit_n):
                    b = single_tids[j]
                    ub = best.units_by_task[b][0]
                    if (ua.start_slot // SLOTS_PER_DAY) == (ub.start_slot // SLOTS_PER_DAY) and ua.cognitive_load == ub.cognitive_load:
                        continue
                    # Direct swap test if durations compatible & deadlines valid
                    e_a, l_a = _task_temporal_window(best, a)
                    e_b, l_b = _task_temporal_window(best, b)
                    if not (e_a <= ub.start_slot and ub.start_slot + ua.duration_slots <= l_a):
                        continue
                    if not (e_b <= ua.start_slot and ua.start_slot + ub.duration_slots <= l_b):
                        continue
                    trial = best.clone()
                    trial.remove_task(a)
                    trial.remove_task(b)
                    if not (trial.is_span_available(ub.start_slot, ub.start_slot + ua.duration_slots)):
                        continue
                    trial.add_unit(
                        UnitPlacement(
                            task_id=a,
                            chunk_index=ua.chunk_index,
                            total_chunks=ua.total_chunks,
                            start_slot=ub.start_slot,
                            end_slot=ub.start_slot + ua.duration_slots,
                            duration_slots=ua.duration_slots,
                            cognitive_load=ua.cognitive_load,
                            priority=ua.priority,
                            category=ua.category,
                            preferred_window=ua.preferred_window,
                            deadline_slot=ua.deadline_slot,
                        )
                    )
                    if not trial.is_span_available(ua.start_slot, ua.start_slot + ub.duration_slots):
                        continue
                    trial.add_unit(
                        UnitPlacement(
                            task_id=b,
                            chunk_index=ub.chunk_index,
                            total_chunks=ub.total_chunks,
                            start_slot=ua.start_slot,
                            end_slot=ua.start_slot + ub.duration_slots,
                            duration_slots=ub.duration_slots,
                            cognitive_load=ub.cognitive_load,
                            priority=ub.priority,
                            category=ub.category,
                            preferred_window=ub.preferred_window,
                            deadline_slot=ub.deadline_slot,
                        )
                    )
                    cand_key = evaluate_state_lex_key(trial)
                    if cand_key < best_key:
                        best = trial
                        best_key = cand_key
                        improved = True
                        break

        if not improved:
            break

    return best


def _find_best_chunks_assignment_windowed(
    state: ScheduleState,
    task: Task,
    chunk_options: List[List[TaskChunk]],
    earliest_slot: int,
    latest_slot: int,
) -> Optional[List[UnitPlacement]]:
    """Same as `_find_best_chunks_assignment` but bounded strictly by `[earliest_slot, latest_slot]`."""
    ctx = state.ctx
    tid = task.task_id
    ld = ctx.task_load[tid]
    best_score: Optional[Tuple[int, float]] = None
    best_units: Optional[List[UnitPlacement]] = None

    for chunks in chunk_options:
        k = len(chunks)
        if k == 1:
            ch = chunks[0]
            dur = ch.duration_slots
            max_st = latest_slot - dur
            if earliest_slot > max_st:
                continue
            for s in range(earliest_slot, max_st + 1):
                if not ctx.is_free_base[s] or state.slot_owner[s]:
                    continue
                if not state.is_span_available(s, s + dur):
                    continue
                flags, cost = score_candidate_unit(state, task, ch, s, strategy_mode="ERGONOMIC")
                cand_score = (flags, cost)
                if best_score is None or cand_score < best_score:
                    best_score = cand_score
                    best_units = [
                        UnitPlacement(
                            task_id=tid,
                            chunk_index=ch.chunk_index,
                            total_chunks=ch.total_chunks,
                            start_slot=s,
                            end_slot=s + dur,
                            duration_slots=dur,
                            cognitive_load=ld,
                            priority=task.priority,
                            category=task.category,
                            preferred_window=task.preferred_window,
                            deadline_slot=ctx.raw_deadline[tid],
                        )
                    ]
        else:
            seq = _place_multichunk_chain(state, task, chunks, earliest_slot, latest_slot, "ERGONOMIC", False)
            if seq is not None:
                c_sc, c_un = seq
                if best_score is None or c_sc < best_score:
                    best_score = c_sc
                    best_units = c_un
    return best_units


def _identify_culprit_tasks(state: ScheduleState) -> List[str]:
    """Identify tasks currently contributing to WARN/CRIT violations or sub-optimal pillars."""
    ctx = state.ctx
    units = state.all_units()
    culprits: Set[str] = set()
    # Check daily totals & L3 caps
    bad_days = {
        d
        for d in range(ctx.num_days)
        if state.day_l3_count[d] > ERGONOMIC_DAILY_HEAVY_CAP
        or (state.day_study_slots[d] + ctx.base_class_slots_per_day[d]) > ERGONOMIC_DAILY_TOTAL_SOFT_SLOTS
    }
    prev_u: Optional[UnitPlacement] = None
    seen_l3_first: Set[str] = set()
    for u in units:
        if u.is_pinned:
            continue
        d = u.start_slot // SLOTS_PER_DAY
        if d in bad_days:
            culprits.add(u.task_id)
        if u.cognitive_load == 3:
            if ctx.energy_aware and any(e == 1 for e in ctx.energy_levels[u.start_slot:u.end_slot]):
                culprits.add(u.task_id)
            if not state.is_recovery_slot(u.end_slot) or ctx.after_long_class[u.start_slot]:
                culprits.add(u.task_id)
            if u.task_id not in seen_l3_first:
                seen_l3_first.add(u.task_id)
                if ctx.task_is_deadline.get(u.task_id, False) and u.deadline_slot is not None:
                    win_t = max(1, u.deadline_slot - ctx.raw_earliest[u.task_id])
                    if (u.start_slot - ctx.raw_earliest[u.task_id]) > 0.55 * float(win_t):
                        culprits.add(u.task_id)
        if u.deadline_slot is not None and u.start_slot >= u.deadline_slot - ERGONOMIC_CRAM_WINDOW_SLOTS:
            culprits.add(u.task_id)
        # Shock collision
        sh = _shock25_extra_slots(u.duration_slots)
        for s in range(u.end_slot, min(ctx.horizon_slots, u.end_slot + sh)):
            if not ctx.is_free_base[s] or state.slot_owner[s]:
                culprits.add(u.task_id)
                break
        if prev_u is not None:
            gap = u.start_slot - prev_u.end_slot
            if gap == 0 and u.cognitive_load >= 2 and prev_u.cognitive_load >= 2:
                culprits.add(u.task_id)
                if not prev_u.is_pinned:
                    culprits.add(prev_u.task_id)
            if u.cognitive_load == 3 and prev_u.cognitive_load == 3 and gap < ERGONOMIC_HEAVY_MIN_GAP_SLOTS:
                culprits.add(u.task_id)
        prev_u = u
    return sorted(culprits)


def _find_top2_slots_single(
    state: ScheduleState, task: Task, chunk: TaskChunk, earliest: int, latest: int
) -> Tuple[Optional[Tuple[int, float, int]], Optional[Tuple[int, float, int]]]:
    """Return `(best, second_best)` tuples `(flags, cost, start_slot)` for Regret-2 insertion."""
    best: Optional[Tuple[int, float, int]] = None
    second: Optional[Tuple[int, float, int]] = None
    dur = chunk.duration_slots
    max_st = latest - dur
    for s in range(earliest, max_st + 1):
        if not state.ctx.is_free_base[s] or state.slot_owner[s]:
            continue
        if not state.is_span_available(s, s + dur):
            continue
        flags, cost = score_candidate_unit(state, task, chunk, s, strategy_mode="ERGONOMIC")
        cand = (flags, cost, s)
        if best is None or cand < best:
            # Count second-best on a non-adjacent slot (>= 2 slots away) for true regret diversity
            if best is not None and abs(best[2] - cand[2]) >= 2:
                second = best
            best = cand
        elif second is None or (cand < second and abs(cand[2] - best[2]) >= 2):
            second = cand
    return best, second


def run_alns_deterministic(
    initial_states: List[ScheduleState],
    max_iters: int = ALNS_MAX_ITERS,
    time_budget_sec: float = ALNS_TIME_BUDGET_SEC,
) -> ScheduleState:
    """
    Deterministic Adaptive Large Neighborhood Search (ALNS) with Regret-2 Insertion:
      - Takes a multi-strategy constructive portfolio.
      - Uses 5 Ruin operators (Worst-Pillar, Day-Congestion, Shaw-Related, Dependency-Chain,
        Random Split-Perturb) and 2 Repair operators (Regret-2 & Ergonomic Critical Greedy).
      - Optimizes exact `evaluate_state_lex_key` cleanly within deterministic & wall-clock bounds.
    """
    t0 = time.perf_counter()
    best = min(initial_states, key=evaluate_state_lex_key).clone()
    best_key = evaluate_state_lex_key(best)
    current = best.clone()
    cur_key = best_key

    ctx = best.ctx
    rng = random.Random(20261120)
    ruin_weights = [3.0, 2.5, 2.0, 1.5, 1.5]
    repair_weights = [3.0, 2.0]

    movable_ids = [
        tid
        for tid in ctx.topo_order
        if not any(u.is_pinned for u in best.units_by_task.get(tid, []))
    ]
    if len(movable_ids) < 2:
        return polish_schedule_deterministic(best, max_passes=ALNS_POLISH_MAX_PASSES, time_budget_sec=time_budget_sec, start_ts=t0)

    k_remove_min = 2
    k_remove_max = max(2, min(6, len(movable_ids) // 2 + 1))
    eff_iters = min(max_iters, 40) if ctx.horizon_slots > 700 else max_iters
    alns_search_budget = time_budget_sec * 0.72

    for it in range(eff_iters):
        if time.perf_counter() - t0 > alns_search_budget:
            break
        # Stop early ONLY if already perfect (0 unplaced DL, 0 CRIT, 0 WARN, 100% shock25, 100% APk, TStd<=90)
        if best_key[0] == 0 and best_key[3] == 0 and best_key[5] == 0 and best_key[7] <= -99.9 and best_key[13] <= -99.9 and best_key[25] <= 90.0:
            break

        # Deterministic roulette wheel over ruin operators
        tot_rw = sum(ruin_weights)
        r_pick = rng.random() * tot_rw
        ruin_idx = 0
        acc = 0.0
        for idx, w in enumerate(ruin_weights):
            acc += w
            if r_pick <= acc:
                ruin_idx = idx
                break

        k_rem = rng.randint(k_remove_min, k_remove_max)
        work = current.clone()
        removed: List[str] = []

        if ruin_idx == 0:  # Worst-Pillar Ruin
            culprits = [c for c in _identify_culprit_tasks(work) if c in movable_ids]
            rng.shuffle(culprits)
            for tid in culprits[:k_rem]:
                removed.append(tid)
        elif ruin_idx == 1:  # Day-Congestion Ruin
            busiest_day = max(
                range(ctx.num_days),
                key=lambda d: work.day_study_slots[d] + ctx.base_class_slots_per_day[d],
            )
            day_tids = sorted({u.task_id for u in work.day_units[busiest_day] if not u.is_pinned and u.task_id in movable_ids})
            rng.shuffle(day_tids)
            removed.extend(day_tids[:k_rem])
        elif ruin_idx == 2:  # Shaw-Related Ruin
            seed_tid = rng.choice(movable_ids)
            seed_units = work.units_by_task.get(seed_tid, [])
            seed_start = seed_units[0].start_slot if seed_units else 0
            related = sorted(
                movable_ids,
                key=lambda tid: (
                    abs((work.units_by_task[tid][0].start_slot if work.units_by_task.get(tid) else 0) - seed_start)
                    + (0 if ctx.tasks_by_id[tid].category == ctx.tasks_by_id[seed_tid].category else 40),
                    tid,
                ),
            )
            removed.extend(related[:k_rem])
        elif ruin_idx == 3:  # Dependency / Deadline Cluster Ruin
            with_deps = [tid for tid in movable_ids if ctx.preds_map[tid] or ctx.succs_map[tid]]
            pool = with_deps if with_deps else movable_ids
            anchor = rng.choice(pool)
            cluster = [anchor] + list(ctx.preds_map[anchor]) + list(ctx.succs_map[anchor])
            for tid in cluster:
                if tid in movable_ids and tid not in removed:
                    removed.append(tid)
                    if len(removed) >= k_rem:
                        break
        else:  # Random + Unplaced Injection
            pool = list(movable_ids)
            rng.shuffle(pool)
            removed.extend(pool[:k_rem])

        # Supplement if under k_rem, also include any unplaced tasks to give them fresh chances
        for tid in movable_ids:
            if not work.has_task_placed(tid) and tid not in removed:
                removed.append(tid)
        while len(removed) < k_rem:
            cand = rng.choice(movable_ids)
            if cand not in removed:
                removed.append(cand)
            else:
                break

        # Also remove any placed successors of removed tasks so topological repair stays 100% consistent
        rem_set = set(removed)
        changed = True
        while changed:
            changed = False
            for tid in list(rem_set):
                for s in ctx.succs_map[tid]:
                    if s in movable_ids and s not in rem_set and work.has_task_placed(s):
                        rem_set.add(s)
                        changed = True

        removed_topo = [tid for tid in ctx.topo_order if tid in rem_set]
        for tid in reversed(removed_topo):
            work.remove_task(tid)

        # Select Repair Operator (Regret-2 vs Critical Ergonomic)
        rep_idx = 0 if rng.random() * sum(repair_weights) <= repair_weights[0] else 1
        pending = list(removed_topo)

        if rep_idx == 0:  # Regret-2 Insertion Repair respecting dependencies
            while pending:
                ready = [
                    tid
                    for tid in pending
                    if all(
                        (work.is_task_fully_placed(p) if p in ctx.tasks_by_id else True)
                        for p in ctx.preds_map[tid]
                    )
                ]
                if not ready:
                    break
                # Evaluate regret for ready tasks
                best_regret_choice: Optional[Tuple[int, float, str, List[UnitPlacement]]] = None
                fallback_choice: Optional[Tuple[int, float, str, List[UnitPlacement]]] = None

                for tid in ready:
                    t = ctx.tasks_by_id[tid]
                    earliest, latest = _task_temporal_window(work, tid)
                    opts = ctx.split_options_by_task[tid]
                    # Fast Regret-2 on atomic option; general best for multi-chunk
                    if len(opts[0]) == 1:
                        b1, b2 = _find_top2_slots_single(work, t, opts[0][0], earliest, latest)
                        if b1 is not None:
                            f1, c1, s1 = b1
                            ch = opts[0][0]
                            units_b1 = [
                                UnitPlacement(
                                    task_id=tid,
                                    chunk_index=ch.chunk_index,
                                    total_chunks=ch.total_chunks,
                                    start_slot=s1,
                                    end_slot=s1 + ch.duration_slots,
                                    duration_slots=ch.duration_slots,
                                    cognitive_load=ctx.task_load[tid],
                                    priority=t.priority,
                                    category=t.category,
                                    preferred_window=t.preferred_window,
                                    deadline_slot=ctx.raw_deadline[tid],
                                )
                            ]
                            if b2 is not None:
                                regret = (b2[0] - f1) * 50.0 + (b2[1] - c1)
                            else:
                                regret = 500.0 + t.priority * 10.0  # Unique/scarce option -> highest urgency!
                            dl_boost = 200.0 if ctx.task_is_deadline[tid] else 0.0
                            prio = (1 if ctx.task_is_deadline[tid] else 0, -(regret + dl_boost))
                            if best_regret_choice is None or (-prio[1], tid) > (best_regret_choice[1], best_regret_choice[2]):
                                best_regret_choice = (prio[0], regret + dl_boost, tid, units_b1)
                            continue
                    # Multi-chunk or adaptive-split fallback (limit to 2 splits during ALNS speed loop)
                    if (time.perf_counter() - t0) > alns_search_budget:
                        break
                    units = _find_best_chunks_assignment_windowed(work, t, opts[:2], earliest, latest)
                    if units is not None:
                        prio_val = 400.0 + t.priority * 15.0 if ctx.task_is_deadline[tid] else float(t.priority)
                        if fallback_choice is None or prio_val > fallback_choice[1]:
                            fallback_choice = (0, prio_val, tid, units)

                chosen = best_regret_choice if best_regret_choice is not None else fallback_choice
                if chosen is None:
                    # Leave remaining unable-to-fit tasks (habits under tight overload) cleanly unplaced
                    break
                _, _, chosen_tid, chosen_units = chosen
                for u in chosen_units:
                    work.add_unit(u)
                pending.remove(chosen_tid)
        else:
            # Critical Ergonomic Ordered Repair with adaptive splits
            ordered_rep = sorted(
                pending,
                key=lambda tid: (
                    0 if ctx.task_is_deadline[tid] else 1,
                    ctx.eff_deadline[tid] if ctx.eff_deadline[tid] is not None else 999999,
                    -ctx.task_load[tid],
                    -ctx.tasks_by_id[tid].priority,
                    tid,
                ),
            )
            # Keep topological safety
            placed_pending: Set[str] = set()
            for _round in range(len(ordered_rep)):
                progress = False
                for tid in ordered_rep:
                    if tid in placed_pending:
                        continue
                    if any(not work.has_task_placed(p) for p in ctx.preds_map[tid]):
                        continue
                    if (time.perf_counter() - t0) > alns_search_budget:
                        break
                    t = ctx.tasks_by_id[tid]
                    earliest, latest = _task_temporal_window(work, tid)
                    units = _find_best_chunks_assignment_windowed(
                        work, t, ctx.split_options_by_task[tid][:2], earliest, latest
                    )
                    if units is not None:
                        for u in units:
                            work.add_unit(u)
                        placed_pending.add(tid)
                        progress = True
                if not progress:
                    break

        work_key = evaluate_state_lex_key(work)
        reward = 0.0
        if work_key < best_key:
            best = work.clone()
            best_key = work_key
            current = work
            cur_key = work_key
            reward = 5.0
        elif work_key < cur_key:
            current = work
            cur_key = work_key
            reward = 2.0
        elif work_key[:4] <= best_key[:4] and abs(work_key[5] - best_key[5]) <= 1 and it % 3 == 0:
            # Record-to-Record acceptance within 1 warning of best
            current = work
            cur_key = work_key
            reward = 0.5

        ruin_weights[ruin_idx] = 0.85 * ruin_weights[ruin_idx] + 0.15 * (1.0 + reward)
        repair_weights[rep_idx] = 0.85 * repair_weights[rep_idx] + 0.15 * (1.0 + reward)

    # Final strict polish pass
    return polish_schedule_deterministic(
        best, max_passes=ALNS_POLISH_MAX_PASSES, time_budget_sec=time_budget_sec, start_ts=t0
    )


def prepare_solver_context(
    solver: Any,
    profile: CommitmentsProfile,
    tasks: List[Task],
    pinned_blocks: Optional[List[ScheduleBlock]],
    energy_aware: bool,
) -> Tuple[
    ErgonomicContext,
    TimeGridManager,
    List[UnitPlacement],
    List[ScheduleBlock],
    Dict[str, str],
    List[Any],
    List[str],
]:
    """Shared deterministic setup for all ergonomic solvers."""
    week_start_iso = profile.planning_week_start
    now_slot = solver.resolve_now_slot(profile)
    horizon_slots = solver.resolve_horizon_slots(
        tasks, week_start_iso=week_start_iso, horizon_days=profile.horizon_days
    )

    grid = TimeGridManager(total_slots=horizon_slots)
    grid.initialize_from_profile(profile)
    locked_grid = grid.clone()

    accepted_pinned, pinned_slots_by_task, _pinned_chunk_map, pin_warnings = solver.prepare_pinned_blocks(
        grid, tasks, pinned_blocks, now_slot, week_start_iso
    )
    capacity_reports = solver.check_deadline_capacity(
        grid,
        tasks,
        now_slot=now_slot,
        week_start_iso=week_start_iso,
        pinned_slots_by_task=pinned_slots_by_task,
    )

    past_due_map = solver.detect_past_due_tasks(tasks, week_start_iso=week_start_iso)
    non_past_tasks = [t for t in tasks if t.task_id not in past_due_map]
    ordered_tasks, dep_blocked = solver.partition_dependency_order(non_past_tasks, non_past_tasks)
    blocked_map: Dict[str, str] = {}
    blocked_map.update(past_due_map)
    blocked_map.update(dep_blocked)

    ctx = ErgonomicContext.build(
        base_grid=grid,
        profile=profile,
        schedulable_tasks=ordered_tasks,
        pinned_blocks=accepted_pinned,
        now_slot=now_slot,
        horizon_slots=horizon_slots,
        week_start_iso=week_start_iso,
        energy_aware=energy_aware,
        solver_split_fn=solver.split_task_into_chunks,
    )

    pinned_units: List[UnitPlacement] = []
    for pb in accepted_pinned:
        t = ctx.tasks_by_id.get(pb.task_id)
        ld = _effective_load(t) if t is not None else (pb.cognitive_load or 2)
        pinned_units.append(
            UnitPlacement(
                task_id=pb.task_id,
                chunk_index=pb.chunk_index,
                total_chunks=pb.total_chunks,
                start_slot=pb.start_slot,
                end_slot=pb.end_slot,
                duration_slots=pb.end_slot - pb.start_slot,
                cognitive_load=ld,
                priority=pb.priority,
                category=pb.category,
                preferred_window=t.preferred_window if t is not None else None,
                deadline_slot=pb.deadline_slot,
                is_pinned=True,
            )
        )

    return ctx, locked_grid, pinned_units, accepted_pinned, blocked_map, capacity_reports, pin_warnings


def materialize_schedule_output(
    solver: Any,
    ctx: ErgonomicContext,
    state: ScheduleState,
    locked_grid: TimeGridManager,
    profile: CommitmentsProfile,
    tasks: List[Task],
    accepted_pinned: List[ScheduleBlock],
    blocked_map: Dict[str, str],
    capacity_reports: List[Any],
    pin_warnings: List[str],
    exec_ms: float,
    algo_tag: str,
) -> Tuple[Any, TimeGridManager]:
    """
    Convert the chosen `ScheduleState` cleanly into `(ScheduleOutput, TimeGridManager)` using
    `BaseScheduler`'s exact grid, REST reservation, block schema, and unplaced reporting contracts.
    """
    # Auto-promote Crunch Tier 1 only when all deadlines placed yet >=1 L3 block unavoidably lacks recovery
    unplaced_dl = any(
        ctx.task_is_deadline.get(tid, False) and not state.is_task_fully_placed(tid)
        for tid in ctx.tasks_by_id
    )
    if state.crunch_tier_used == 0 and not unplaced_dl:
        l3_units = [u for u in state.all_units() if u.cognitive_load == 3]
        if l3_units and any(not state.is_recovery_slot(u.end_slot) for u in l3_units):
            state.crunch_tier_used = 1

    final_grid = locked_grid.clone()
    final_blocks: List[ScheduleBlock] = []
    warnings = list(pin_warnings)

    # Re-apply pinned blocks cleanly to grid
    for pb in accepted_pinned:
        for s in range(pb.start_slot, pb.end_slot):
            if final_grid.grid[s] == TimeGridManager.STATE_FREE:
                final_grid.grid[s] = f"{TimeGridManager.STATE_BLOCK}:{pb.task_id}"
                final_grid.labels[s] = pb.title or pb.task_id
        final_blocks.append(pb)

    placed_units = [u for u in state.all_units() if not u.is_pinned]
    # Place study blocks first on final_grid
    for u in placed_units:
        t = ctx.tasks_by_id[u.task_id]
        final_grid.place_block(u.start_slot, u.duration_slots, u.task_id, t.title)

    # Tier 0 rest materialization (exact match with BaseScheduler)
    if state.crunch_tier_used == 0:
        final_grid.mark_dead_zones_as_rest()

    for order_idx, u in enumerate(placed_units, start=1):
        t = ctx.tasks_by_id[u.task_id]
        rest_reserved = 0
        if state.crunch_tier_used == 0 and (
            u.duration_slots * MINUTES_PER_SLOT >= MIN_DEEP_WORK_BREAK_TRIGGER_MIN
            or u.cognitive_load >= 3
        ):
            rest_reserved = final_grid.reserve_rest_break(u.end_slot, MANDATORY_REST_SLOTS, task_id=u.task_id)

        avg_e = (
            ctx.span_energy_sum(u.start_slot, u.end_slot) / float(u.duration_slots)
            if ctx.energy_aware
            else 2.0
        )
        chunk_obj = TaskChunk(
            chunk_id=f"{u.task_id}_C{u.chunk_index}",
            task_id=u.task_id,
            title=t.title,
            chunk_index=u.chunk_index,
            total_chunks=u.total_chunks,
            duration_min=u.duration_slots * MINUTES_PER_SLOT,
            duration_slots=u.duration_slots,
            deadline_slot=u.deadline_slot,
            deadline_str=t.format_deadline_label(week_start_iso=ctx.week_start_iso),
            priority=u.priority,
            depends_on=list(t.depends_on),
            is_splittable=t.is_splittable,
            min_chunk_min=int(t.min_chunk_min or 45),
            cognitive_load=t.cognitive_load,
            category=u.category,
            preferred_window=u.preferred_window,
        )

        primary_text = (
            f"[{algo_tag}] Khối #{order_idx} (Ưu tiên {u.priority}, "
            f"Tải {u.cognitive_load}, Năng lượng {avg_e:.1f}/3)."
        )
        reason_text, reason_codes = solver.build_chunk_reasons(
            task=t,
            chunk=chunk_obj,
            start_slot=u.start_slot,
            avg_energy=avg_e,
            primary_code=algo_tag,
            primary_text=primary_text,
            has_prereq=bool(t.depends_on),
            rest_reserved=rest_reserved,
            profile=profile,
            placed_blocks=final_blocks,
            crunch_tier_used=state.crunch_tier_used,
        )
        blk = solver.build_schedule_block(
            chunk=chunk_obj,
            start_slot=u.start_slot,
            reason_text=reason_text,
            reason_codes=reason_codes,
            week_start_iso=ctx.week_start_iso,
        )
        final_blocks.append(blk)

    # Recompute exact unplaced task entries
    unplaced_tasks: List[Dict[str, Any]] = []
    for t in tasks:
        tid = t.task_id
        if state.is_task_fully_placed(tid):
            continue
        b_reason = blocked_map.get(tid)
        if b_reason:
            r_code = "DEPENDENCY_CYCLE" if "Vòng phụ thuộc" in b_reason else "PAST_DUE"
            r_msg = b_reason
        else:
            dl = ctx.raw_deadline.get(tid)
            if dl is not None:
                sa = ctx.raw_earliest.get(tid, ctx.now_slot)
                avail = locked_grid.count_free_slots_in_range(start_from=sa, up_to=min(dl, ctx.horizon_slots))
                need = ctx.task_planned_slots.get(tid, t.get_planned_slots())
                if avail < need:
                    r_code = "CAPACITY_SHORTAGE"
                    r_msg = f"Không đủ thời gian trống trước hạn ({avail * 15}p < {need * 15}p)."
                else:
                    r_code = "FRAGMENTATION_FAILURE"
                    r_msg = f"Không còn khoảng trống liên tục phù hợp trước hạn ({t.format_deadline_label(week_start_iso=ctx.week_start_iso)})."
            else:
                r_code = "CAPACITY_SHORTAGE"
                r_msg = "Không đủ khung giờ trống phù hợp trong tuần."

        unplaced_tasks.append(
            {
                "task_id": tid,
                "title": t.title,
                "duration_min": t.get_planned_duration_min(),
                "deadline": t.format_deadline_label(week_start_iso=ctx.week_start_iso),
                "deadline_slot": t.resolve_deadline_slot(week_start_iso=ctx.week_start_iso),
                "reason": r_msg,
                "reason_code": r_code,
                "priority": t.priority,
            }
        )

    final_blocks.sort(key=lambda b: (b.start_slot, b.task_id, b.chunk_index))
    output = solver.finalize_output(
        grid_manager=final_grid,
        tasks=tasks,
        blocks=final_blocks,
        unplaced_tasks=unplaced_tasks,
        capacity_reports=capacity_reports,
        exec_ms=exec_ms,
        week_start_iso=ctx.week_start_iso,
        warnings=warnings,
        profile=profile,
        now_slot=ctx.now_slot,
        crunch_tier_used=state.crunch_tier_used,
    )
    return output, final_grid
