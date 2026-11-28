"""
In-Silico Multi-Week Student Behavioral Twin (`InSilicoStudentSimulator`, Pattern P14b).

Pure Layer 1 psychometric simulation engine implementing 5 peer-reviewed deterministic
behavioral equations (isolated per-instance `random.Random(seed)`):
  1. Latent Chronotype Synchrony (Roenneberg et al., 2003 MCTQ; Smarr & Schirmer, 2018)
  2. Category-Asymmetric Log-Normal Planning Fallacy (Buehler et al., 1994)
  3. Corrected Temporal Motivation Theory with Gamma denominator (Steel, 2007 Eq. 3)
  4. Random Utility Discrete Adherence Choice (McFadden, 1974 Conditional Logit RUM)
  5. Ultradian Fatigue Accumulation, >=15m Rest Recovery & Recurring/Poisson Disruptions
     (Albulescu et al., 2022)

Architectural compliance (`INV-1`, `INV-2`, `INV-5`, `INV-6`):
  - Pure Python stdlib + `smartschedule.core.{config,models,utils}` ONLY.
  - Zero `smartschedule.nlp`, `smartschedule.api`, `solvers`, or global `random` state mutation.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from smartschedule.core.config import MIN_SLEEP_HOURS
from smartschedule.core.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task
from smartschedule.core.utils import (
    DAYS_OF_WEEK,
    MINUTES_PER_SLOT,
    SLOTS_PER_DAY,
    SLOTS_PER_WEEK,
    day_time_to_slot,
    format_slot_range,
    parse_day_to_index,
    parse_time_to_slot_offset,
    slot_to_day_time,
)

DEFAULT_CATEGORY_BIAS: Dict[str, float] = {
    "CODING": 1.42,
    "PROJECT": 1.35,
    "THESIS": 1.38,
    "DEEP_WORK": 1.35,
    "LAB": 1.30,
    "EXAM": 1.28,
    "EXAM_PREP": 1.28,
    "ASSIGNMENT": 1.25,
    "DEADLINE": 1.25,
    "QUIZ": 1.15,
    "OTHER": 1.15,
    "READING": 1.08,
    "HABIT": 1.02,
}

CHRONOTYPE_PEAK_PRESETS: Dict[str, float] = {
    "MORNING": 9.0,
    "LARK": 9.0,
    "EARLY_BIRD": 8.5,
    "MORNING_LARK": 9.0,
    "BALANCED": 11.0,
    "FINCH": 11.0,
    "AFTERNOON": 14.5,
    "EVENING": 20.5,
    "NIGHT_OWL": 20.5,
    "OWL": 20.5,
    "NIGHT": 20.5,
}

_FATIGUE_RATE_PER_HOUR: Dict[int, float] = {
    1: 0.08,
    2: 0.14,
    3: 0.22,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _expand_fixed_event_days(day_field: Any) -> List[int]:
    if isinstance(day_field, list):
        days: List[int] = []
        for item in day_field:
            days.extend(_expand_fixed_event_days(item))
        return sorted(set(days))
    raw = str(day_field or "").strip().lower()
    if not raw:
        return []
    if raw in ("all", "daily", "everyday", "hang ngay", "hằng ngày"):
        return list(range(7))
    if raw in ("weekdays", "mon-fri"):
        return [0, 1, 2, 3, 4]
    if raw in ("weekend", "weekends", "sat-sun"):
        return [5, 6]
    try:
        idx = parse_day_to_index(raw)
        return [idx] if 0 <= idx < 7 else []
    except ValueError:
        return []


def _parse_disruption_spec(spec: Any) -> List[Tuple[int, int, str]]:
    """Parse recurring disruption specification(s) into `(start_slot, end_slot, canonical_label)`."""
    if spec is None:
        return []
    if isinstance(spec, list):
        parsed: List[Tuple[int, int, str]] = []
        for item in spec:
            parsed.extend(_parse_disruption_spec(item))
        return parsed

    if isinstance(spec, dict):
        day_raw = spec.get("day") or spec.get("day_of_week") or "Thursday"
        start_raw = str(spec.get("start_time") or spec.get("start") or "19:30").strip()
        end_raw = str(spec.get("end_time") or spec.get("end") or "21:00").strip()
        day_indices = _expand_fixed_event_days(day_raw)
        if not day_indices:
            return []
        s_off = parse_time_to_slot_offset(start_raw, is_end_or_deadline=False)
        e_off = parse_time_to_slot_offset(end_raw, is_end_or_deadline=True)
        out: List[Tuple[int, int, str]] = []
        for d_idx in day_indices:
            if e_off > s_off:
                s_slot = d_idx * SLOTS_PER_DAY + s_off
                e_slot = d_idx * SLOTS_PER_DAY + e_off
                out.append((s_slot, e_slot, format_slot_range(s_slot, e_slot)))
        return out

    if isinstance(spec, str):
        text = spec.strip()
        if not text:
            return []
        parts = text.split(None, 1)
        if len(parts) == 2:
            day_part, time_part = parts
            normalized_range = time_part.replace("–", "-").replace("—", "-")
            if "-" in normalized_range:
                t_start, t_end = [p.strip() for p in normalized_range.split("-", 1)]
                try:
                    s_slot = day_time_to_slot(day_part, t_start, is_end_or_deadline=False)
                    e_slot = day_time_to_slot(day_part, t_end, is_end_or_deadline=True)
                    if e_slot > s_slot:
                        return [(s_slot, e_slot, format_slot_range(s_slot, e_slot))]
                except ValueError:
                    return []
    return []


def _compute_sleep_hours(profile: CommitmentsProfile) -> float:
    """Compute nightly sleep duration in hours, handling midnight wraparound."""
    try:
        s_off = parse_time_to_slot_offset(profile.sleep_schedule.daily_start_time, is_end_or_deadline=False)
        e_off = parse_time_to_slot_offset(profile.sleep_schedule.daily_end_time, is_end_or_deadline=False)
    except ValueError:
        return float(MIN_SLEEP_HOURS + 1)
    sleep_slots = (SLOTS_PER_DAY - s_off + e_off) if e_off <= s_off else (e_off - s_off)
    return round(sleep_slots * (MINUTES_PER_SLOT / 60.0), 2)


def _build_fixed_busy_mask(profile: CommitmentsProfile, total_slots: int) -> List[bool]:
    """Boolean mask marking slots occupied by recurring fixed events (classes, meetings, work, meals)."""
    mask = [False] * total_slots
    weeks = max(1, (total_slots + SLOTS_PER_WEEK - 1) // SLOTS_PER_WEEK)
    for ev in profile.fixed_events:
        day_indices = _expand_fixed_event_days(ev.day_of_week)
        if not day_indices:
            continue
        try:
            s_off = parse_time_to_slot_offset(ev.start_time, is_end_or_deadline=False)
            e_off = parse_time_to_slot_offset(ev.end_time, is_end_or_deadline=True)
        except ValueError:
            continue
        for w in range(weeks):
            for d_idx in day_indices:
                base = w * SLOTS_PER_WEEK + d_idx * SLOTS_PER_DAY
                if e_off > s_off:
                    for s in range(max(0, base + s_off), min(total_slots, base + e_off)):
                        mask[s] = True
                elif e_off < s_off:
                    for s in range(max(0, base + s_off), min(total_slots, base + SLOTS_PER_DAY)):
                        mask[s] = True
                    for s in range(max(0, base), min(total_slots, base + e_off)):
                        mask[s] = True
    return mask


def _window_from_hour(hour: float) -> str:
    h = float(hour) % 24.0
    if 6.0 <= h < 12.0:
        return "MORNING"
    if 12.0 <= h < 18.0:
        return "AFTERNOON"
    return "EVENING"


class InSilicoStudentSimulator:
    """
    Deterministic 5-equation behavioral twin simulating how a student executes a planned schedule.

    Each instance owns an isolated `random.Random(seed)` generator so repeated calls with
    the same `(student_id, seed, latent_profile)` yield bit-identical execution logs without
    touching global PRNG state.
    """

    def __init__(
        self,
        student_id: str = "SIM_STUDENT_01",
        seed: int = 42,
        latent_profile: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.student_id: str = str(student_id)
        self.seed: int = int(seed)
        self._rng: random.Random = random.Random(self.seed)

        cfg = dict(latent_profile or {})

        # Equation 1 parameter: true latent peak hour H* in [7.0, 23.0]
        raw_peak = (
            cfg.get("true_peak_hour")
            if cfg.get("true_peak_hour") is not None
            else cfg.get("peak_hour", cfg.get("latent_peak_hour"))
        )
        if raw_peak is not None:
            self.true_peak_hour: float = round(_clamp(float(raw_peak), 7.0, 23.0), 2)
        else:
            chrono = str(cfg.get("chronotype") or "").strip().upper()
            if chrono in CHRONOTYPE_PEAK_PRESETS:
                self.true_peak_hour = CHRONOTYPE_PEAK_PRESETS[chrono]
            else:
                self.true_peak_hour = round(self._rng.uniform(8.0, 21.5), 2)

        # Equation 2 parameters: category-specific planning-fallacy multipliers + LogNormal sigma
        biases = dict(DEFAULT_CATEGORY_BIAS)
        custom_bias = cfg.get("category_bias")
        if isinstance(custom_bias, dict):
            for cat, mult in custom_bias.items():
                key = str(cat or "OTHER").strip().upper()
                if key:
                    biases[key] = round(_clamp(float(mult), 0.95, 1.85), 4)
        self.category_bias: Dict[str, float] = biases
        self.lognormal_sigma: float = _clamp(float(cfg.get("lognormal_sigma", 0.08)), 0.0, 0.35)

        # Equation 3 parameter: Steel (2007) impulsiveness trait Gamma ~ Beta(2, 5)
        raw_gamma = cfg.get("gamma") if cfg.get("gamma") is not None else cfg.get("gamma_impulsiveness")
        if raw_gamma is not None:
            self.gamma_impulsiveness: float = round(_clamp(float(raw_gamma), 0.01, 2.0), 4)
        else:
            self.gamma_impulsiveness = round(self._rng.betavariate(2.0, 5.0), 4)

        # Equation 4 parameters: McFadden (1974) RUM logit slope, distraction floor, fatigue penalty
        self.u_distract: float = float(cfg.get("u_distract", 0.12))
        self.logit_beta: float = float(cfg.get("logit_beta", 4.0))
        self.fatigue_penalty_weight: float = float(cfg.get("fatigue_penalty_weight", 0.25))

        # Equation 5 parameters: recurring chronic disruptions & random Poisson disruption rate
        raw_disruptions = (
            cfg.get("recurring_disruptions")
            or cfg.get("recurring_disruption")
            or cfg.get("chronic_disruption")
            # M5 contract key (api/app.py multi-week scenario + fallback twin)
            or cfg.get("chronic_disruption_window")
        )
        self.recurring_disruptions: List[Tuple[int, int, str]] = _parse_disruption_spec(raw_disruptions)
        self.poisson_disruption_rate: float = max(0.0, float(cfg.get("poisson_disruption_rate", 0.02)))

    # ------------------------------------------------------------------
    # 5 Mechanistic Psychometric Equations
    # ------------------------------------------------------------------
    def circadian_fit(self, hour: float) -> float:
        """Eq 1 (MCTQ): Circular synchrony fit in [0.0, 1.0] around `true_peak_hour`."""
        h_mod = float(hour) % 24.0
        diff = abs(h_mod - self.true_peak_hour)
        circ_dist = min(diff, 24.0 - diff)
        return max(0.0, 1.0 - (circ_dist / 8.0))

    def sample_actual_duration_min(self, estimated_duration_min: int, category: str) -> int:
        """
        Eq 2 (Buehler et al., 1994): Category-specific Log-Normal execution duration,
        rounded up to the 15-minute slot grid.
        """
        est = max(1, int(estimated_duration_min))
        cat_key = str(category or "OTHER").strip().upper()
        b_cat = self.category_bias.get(cat_key, self.category_bias["OTHER"])
        eps = self._rng.gauss(0.0, self.lognormal_sigma) if self.lognormal_sigma > 0.0 else 0.0
        raw_min = max(1.0, float(est) * b_cat * math.exp(eps))
        return MINUTES_PER_SLOT * int(math.ceil(raw_min / float(MINUTES_PER_SLOT) - 1e-9))

    def compute_tmt_utility(
        self,
        circ_fit: float,
        fatigue: float,
        priority: int,
        slack_hours: float,
    ) -> float:
        """
        Eq 3 (Steel, 2007 Eq. 3): Corrected Temporal Motivation Theory with Gamma denominator:
            U_task = (Expectancy(CircFit, F_t) * (p_i / 5.0)) / (1.0 + Gamma * max(0.05, s_h / 24.0))
        """
        f_clamped = _clamp(fatigue, 0.0, 1.0)
        fit_clamped = _clamp(circ_fit, 0.0, 1.0)
        expectancy = _clamp((0.28 + 0.72 * fit_clamped) * (1.0 - 0.30 * f_clamped), 0.05, 1.0)
        value = _clamp(float(priority) / 5.0, 0.20, 1.0)
        denom = 1.0 + self.gamma_impulsiveness * max(0.05, float(slack_hours) / 24.0)
        return (expectancy * value) / denom

    def adherence_probability(self, u_task: float, fatigue: float) -> float:
        """Eq 4 (McFadden, 1974 RUM): Logistic adherence probability."""
        f_clamped = _clamp(fatigue, 0.0, 1.0)
        z = self.logit_beta * (float(u_task) - self.u_distract - self.fatigue_penalty_weight * f_clamped)
        z_safe = _clamp(z, -30.0, 30.0)
        return 1.0 / (1.0 + math.exp(-z_safe))

    @staticmethod
    def apply_rest_break(fatigue: float, rest_minutes: int) -> float:
        """Eq 5a (Albulescu et al., 2022): Restoring 40% of fatigue after >= 15m rest break."""
        f_clamped = _clamp(fatigue, 0.0, 1.0)
        if int(rest_minutes) >= MINUTES_PER_SLOT:
            return round(_clamp(f_clamped * 0.60, 0.0, 1.0), 6)
        return f_clamped

    @staticmethod
    def accumulate_fatigue(fatigue: float, duration_min: int, cognitive_load: int) -> float:
        """Eq 5b: Ultradian fatigue buildup scaled by block duration and cognitive load."""
        f_clamped = _clamp(fatigue, 0.0, 1.0)
        load = max(1, min(3, int(cognitive_load)))
        rate = _FATIGUE_RATE_PER_HOUR.get(load, 0.14)
        hours = max(0.0, float(duration_min) / 60.0)
        return round(_clamp(f_clamped + rate * hours, 0.0, 1.0), 6)

    # ------------------------------------------------------------------
    # Weekly Execution Simulation Loop
    # ------------------------------------------------------------------
    def _match_recurring_disruption(self, start_slot: int, end_slot: int) -> Optional[str]:
        if not self.recurring_disruptions:
            return None
        dur_slots = max(1, end_slot - start_slot)
        b_week_start = start_slot % SLOTS_PER_WEEK
        b_week_end = b_week_start + dur_slots
        for r_start, r_end, r_label in self.recurring_disruptions:
            if max(b_week_start, r_start) < min(b_week_end, r_end):
                return r_label
        return None

    def simulate_week_execution(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        schedule: ScheduleOutput,
    ) -> List[Dict[str, Any]]:
        """
        Simulate real student execution across all scheduled blocks in `schedule`.

        Never mutates `profile`, `tasks`, or `schedule`.
        Always scales actual duration from unbuffered `Task.duration_min` (preventing
        double-buffering when `planned_duration_min` already includes alpha buffers).
        """
        blocks: List[ScheduleBlock] = sorted(
            schedule.blocks,
            key=lambda b: (b.start_slot, b.end_slot, b.block_id),
        )
        if not blocks:
            return []

        tasks_by_id: Dict[str, Task] = {t.task_id: t for t in tasks}
        total_planned_by_task: Dict[str, int] = {}
        for blk in blocks:
            p_min = max(MINUTES_PER_SLOT, int(blk.duration_min or (blk.end_slot - blk.start_slot) * MINUTES_PER_SLOT))
            total_planned_by_task[blk.task_id] = total_planned_by_task.get(blk.task_id, 0) + p_min

        max_slot = max(
            SLOTS_PER_WEEK,
            int(getattr(profile, "horizon_days", 7) or 7) * SLOTS_PER_DAY,
            max(b.end_slot for b in blocks) + 1,
        )
        fixed_busy = _build_fixed_busy_mask(profile, max_slot)
        sleep_hours = _compute_sleep_hours(profile)
        sleep_debt_base = 0.0 if sleep_hours >= 7.0 else min(0.50, 0.12 * (7.0 - sleep_hours))

        current_fatigue = 0.0
        current_day: Optional[int] = None
        prev_end_slot: Optional[int] = None
        timeline_logs: List[Dict[str, Any]] = []

        for blk in blocks:
            planned_min = max(
                MINUTES_PER_SLOT,
                int(blk.duration_min or (blk.end_slot - blk.start_slot) * MINUTES_PER_SLOT),
            )
            task = tasks_by_id.get(blk.task_id)
            if task is not None:
                denom = max(1, total_planned_by_task.get(blk.task_id, planned_min))
                share = float(planned_min) / float(denom)
                est_min = max(MINUTES_PER_SLOT, int(round(float(task.duration_min) * share)))
                priority = int(task.priority)
                cognitive_load = int(task.cognitive_load or blk.cognitive_load or 2)
                category = str(task.category or blk.category or "DEADLINE").strip().upper()
                deadline_slot = (
                    blk.deadline_slot
                    if blk.deadline_slot is not None
                    else task.resolve_deadline_slot(profile.planning_week_start)
                )
            else:
                est_min = planned_min
                priority = int(blk.priority or 3)
                cognitive_load = int(blk.cognitive_load or 2)
                category = str(blk.category or "DEADLINE").strip().upper()
                deadline_slot = blk.deadline_slot

            day_idx = blk.start_slot // SLOTS_PER_DAY
            slot_in_day = blk.start_slot % SLOTS_PER_DAY
            start_hour = round((slot_in_day * MINUTES_PER_SLOT) / 60.0, 2)
            window = _window_from_hour(start_hour)
            day_name = blk.day or slot_to_day_time(blk.start_slot)[0]

            # Day rollover vs same-day inter-block rest recovery
            if current_day is None or day_idx != current_day:
                carry_over = (0.15 * current_fatigue) if (current_day is not None and sleep_hours < 7.0) else 0.0
                current_fatigue = _clamp(sleep_debt_base + carry_over, 0.0, 1.0)
                current_day = day_idx
                prev_end_slot = None
            elif prev_end_slot is not None and blk.start_slot > prev_end_slot:
                rest_slots = sum(
                    1
                    for s in range(max(0, prev_end_slot), min(max_slot, blk.start_slot))
                    if not fixed_busy[s]
                )
                rest_min = rest_slots * MINUTES_PER_SLOT
                if rest_min >= MINUTES_PER_SLOT:
                    current_fatigue = self.apply_rest_break(current_fatigue, rest_min)

            # Disruption check: recurring chronic window first, then stochastic Poisson interruption
            disruption_window = self._match_recurring_disruption(blk.start_slot, blk.end_slot)
            if disruption_window is None and self.poisson_disruption_rate > 0.0:
                p_disrupt = 1.0 - math.exp(-self.poisson_disruption_rate * (planned_min / 60.0))
                if self._rng.random() < p_disrupt:
                    disruption_window = format_slot_range(blk.start_slot, blk.end_slot)

            # Psychometric equations (1 -> 3 -> 4)
            slack_hours = ((deadline_slot - blk.start_slot) * 0.25) if deadline_slot is not None else 72.0
            circ_fit = self.circadian_fit(start_hour)
            u_task = self.compute_tmt_utility(circ_fit, current_fatigue, priority, slack_hours)
            p_adhere = self.adherence_probability(u_task, current_fatigue)

            if disruption_window is not None:
                adhered = False
                actual_min = 0
                overrun_min = 0
                prev_end_slot = blk.end_slot
            else:
                adhered = bool(self._rng.random() < p_adhere)
                if adhered:
                    actual_min = self.sample_actual_duration_min(est_min, category)
                    overrun_min = max(0, actual_min - planned_min)
                    current_fatigue = self.accumulate_fatigue(current_fatigue, actual_min, cognitive_load)
                    actual_slots = max(1, actual_min // MINUTES_PER_SLOT)
                    prev_end_slot = max(blk.end_slot, blk.start_slot + actual_slots)
                else:
                    actual_min = 0
                    overrun_min = 0
                    prev_end_slot = blk.end_slot

            timeline_logs.append(
                {
                    "task_id": blk.task_id,
                    "block_id": blk.block_id,
                    "category": category,
                    "cognitive_load": cognitive_load,
                    "day": day_name,
                    "window": window,
                    "start_hour": start_hour,
                    "estimated_duration_min": int(est_min),
                    "planned_duration_min": int(planned_min),
                    "actual_duration_min": int(actual_min),
                    "adhered": adhered,
                    "overrun_min": int(overrun_min),
                    "fatigue_after": round(current_fatigue, 4),
                    "disruption_slot_window": disruption_window,
                }
            )

        return timeline_logs


def compute_timeline_hash(timeline_logs: List[Dict[str, Any]]) -> str:
    """Compute a deterministic SHA-256 digest over simulation `timeline_logs`."""
    canonical = json.dumps(timeline_logs, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def summarize_week_execution(
    tasks: List[Task],
    schedule: ScheduleOutput,
    timeline_logs: List[Dict[str, Any]],
    week_start_iso: str = "2026-11-02T00:00:00+07:00",
) -> Dict[str, Any]:
    """
    Aggregate weekly adherence, priority-weighted on-time completion, overrun statistics,
    and determinism digest from a simulated week.
    """
    total_blocks = len(timeline_logs)
    adhered_logs = [row for row in timeline_logs if row.get("adhered")]
    adherence_pct = round((100.0 * len(adhered_logs) / total_blocks), 2) if total_blocks else 0.0

    overruns = [int(row.get("overrun_min") or 0) for row in adhered_logs]
    mean_overrun_min = round(sum(overruns) / len(overruns), 2) if overruns else 0.0
    overrun_blocks = sum(1 for ov in overruns if ov > 0)
    overrun_block_rate_pct = round((100.0 * overrun_blocks / len(adhered_logs)), 2) if adhered_logs else 0.0
    mean_fatigue = (
        round(sum(float(row.get("fatigue_after") or 0.0) for row in timeline_logs) / total_blocks, 4)
        if total_blocks
        else 0.0
    )

    blocks_by_id = {b.block_id: b for b in schedule.blocks}
    logs_by_task: Dict[str, List[Dict[str, Any]]] = {}
    for row in timeline_logs:
        logs_by_task.setdefault(str(row.get("task_id") or ""), []).append(row)

    unplaced_ids = {str(u.get("task_id") or "") for u in (schedule.unplaced_tasks or [])}
    total_value = sum(max(1, int(t.priority)) for t in tasks)
    on_time_value = 0

    for t in tasks:
        if t.task_id in unplaced_ids:
            continue
        t_logs = logs_by_task.get(t.task_id, [])
        if not t_logs or not all(bool(r.get("adhered")) for r in t_logs):
            continue
        deadline_slot = t.resolve_deadline_slot(week_start_iso)
        if deadline_slot is not None:
            on_time = True
            for r in t_logs:
                blk = blocks_by_id.get(str(r.get("block_id") or ""))
                if blk is None:
                    on_time = False
                    break
                act_slots = max(1, int(r.get("actual_duration_min") or 0) // MINUTES_PER_SLOT)
                if blk.start_slot + act_slots > deadline_slot:
                    on_time = False
                    break
            if not on_time:
                continue
        on_time_value += max(1, int(t.priority))

    on_time_value_pct = round((100.0 * on_time_value / total_value), 2) if total_value > 0 else 0.0

    return {
        "total_blocks": total_blocks,
        "adhered_blocks": len(adhered_logs),
        "adherence_pct": adherence_pct,
        "on_time_value_pct": on_time_value_pct,
        "mean_overrun_min": mean_overrun_min,
        "overrun_block_rate_pct": overrun_block_rate_pct,
        "mean_fatigue": mean_fatigue,
        "determinism_hash": compute_timeline_hash(timeline_logs),
    }
