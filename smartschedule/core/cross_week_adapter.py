"""
Cross-Week Fallacy Buffer & Preference Adaptation Engine (Pattern P13 — Proposal §7.8.3 & §7.8.4).

Pure Layer-1 domain module (`INV-1`..`INV-5` compliant: zero web, NLP, solver, or storage imports).
Learns next-week personal parameters from prior execution logs (`timeline_logs` from
`InSilicoStudentSimulator` or real-user `completion_logs` + workspace state):
  1. Empirical Bayes Shrinkage Category Buffers (`alpha_hat` in [1.00, 1.60], kappa=3.0)
     with unbiased first-sample EWMA initialization (no double-shrinkage, no double-buffering).
  2. Revealed vs. Stated Chronotype Discovery (`MORNING` / `AFTERNOON` / `EVENING` adherence & speed).
  3. Post-Crunch Ultradian Pacing (`45-75m` chunk bounds) & Day-Specific Chronic Disruption Buffers
     (preserving 7-day `hourly_levels` integrity on non-disrupted days).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from smartschedule.core.config import ALPHA_HEAVY_DEFAULT, ALPHA_LIGHT_DEFAULT
from smartschedule.core.estimate_buffer import multiplier_for_load
from smartschedule.core.models import (
    CIRCADIAN_PROFILE_DEFAULTS,
    CircadianEnergyProfile,
    CommitmentsProfile,
    FixedEvent,
    Task,
)
from smartschedule.core.utils import parse_time_to_slot_offset

LAMBDA_CATEGORY_EWMA: float = 0.30
KAPPA_EMPIRICAL_BAYES: float = 3.0
RATIO_CLIP_MIN: float = 0.50
RATIO_CLIP_MAX: float = 2.50
ALPHA_SAFE_MIN: float = 1.00
ALPHA_SAFE_MAX: float = 1.60

EFF_RATIO_CLIP_MIN: float = 0.60
EFF_RATIO_CLIP_MAX: float = 1.25
CHRONOTYPE_SHIFT_MARGIN: float = 0.22
CHRONOTYPE_MIN_WINDOW_SAMPLES: int = 2
STATED_ADHERENCE_MAX_FOR_SHIFT: float = 0.75

FATIGUE_PACING_THRESHOLD: float = 0.65
LONG_BLOCK_MIN_THRESHOLD: int = 60
LONG_BLOCK_OVERRUN_RATE_THRESHOLD: float = 0.50
PACED_MIN_CHUNK_MIN: int = 45
PACED_MAX_CHUNK_MIN: int = 75

CHRONIC_DISRUPTION_MIN_COUNT: int = 2
ADVISORY_BUFFER_MAX_RHO: float = 0.90

VALID_WINDOWS: Tuple[str, str, str] = ("MORNING", "AFTERNOON", "EVENING")

_WINDOW_VI_LABELS: Dict[str, str] = {
    "MORNING": "Buổi sáng (06:00–12:00)",
    "AFTERNOON": "Buổi chiều (12:00–18:00)",
    "EVENING": "Buổi tối (18:00–24:00)",
    "BALANCED": "Cân bằng cả ngày",
}

_WEEKDAY_CANONICAL: Dict[str, str] = {
    "monday": "Monday",
    "mon": "Monday",
    "tuesday": "Tuesday",
    "tue": "Tuesday",
    "wednesday": "Wednesday",
    "wed": "Wednesday",
    "thursday": "Thursday",
    "thu": "Thursday",
    "friday": "Friday",
    "fri": "Friday",
    "saturday": "Saturday",
    "sat": "Saturday",
    "sunday": "Sunday",
    "sun": "Sunday",
}


def _clip(val: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, float(val)))


def _window_from_hour(hour_val: float) -> str:
    h = int(hour_val) % 24
    if 6 <= h < 12:
        return "MORNING"
    if 12 <= h < 18:
        return "AFTERNOON"
    if 18 <= h < 24:
        return "EVENING"
    return "NIGHT"


def _infer_window_from_entry(entry: Dict[str, Any]) -> Optional[str]:
    raw_win = str(entry.get("window") or "").strip().upper()
    if raw_win in ("MORNING", "AFTERNOON", "EVENING", "NIGHT"):
        return raw_win

    if entry.get("start_hour") is not None:
        try:
            return _window_from_hour(float(entry["start_hour"]))
        except (TypeError, ValueError):
            pass

    start_time = str(entry.get("start_time") or "").strip()
    if re.match(r"^\d{1,2}:\d{2}$", start_time):
        try:
            hh = int(start_time.split(":", 1)[0])
            return _window_from_hour(hh)
        except ValueError:
            pass

    completed_at = str(entry.get("completed_at") or "").strip()
    if completed_at:
        try:
            iso_clean = completed_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_clean)
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone(timedelta(hours=7)))
            return _window_from_hour(dt.hour)
        except ValueError:
            pass
    return None


def _ensure_chronological_order(logs: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reverse newest-first SQLite `completion_logs` (`ORDER BY id DESC`) into chronological order."""
    items = [dict(row) for row in (logs or []) if isinstance(row, dict)]
    if len(items) < 2:
        return items
    if all(isinstance(r.get("id"), int) for r in items):
        ids = [int(r["id"]) for r in items]
        if ids[0] > ids[-1] and all(ids[i] >= ids[i + 1] for i in range(len(ids) - 1)):
            return list(reversed(items))
    return items


def _compute_unbiased_ewma(ratios: Sequence[float], lambda_ewma: float) -> float:
    """
    Compute chronological EWMA initialized directly at `ratios[0]` so subsequent
    Empirical Bayes shrinkage performs a single, exact prior pull (Fix M-2).
    """
    ewma = float(ratios[0])
    for r in ratios[1:]:
        ewma = lambda_ewma * float(r) + (1.0 - lambda_ewma) * ewma
    return ewma


def _shrink_alpha(ewma_val: float, n_samples: int, prior_alpha: float, kappa: float) -> float:
    if n_samples <= 0:
        return _clip(prior_alpha, ALPHA_SAFE_MIN, ALPHA_SAFE_MAX)
    weight_obs = float(n_samples) / (float(n_samples) + float(kappa))
    weight_prior = float(kappa) / (float(n_samples) + float(kappa))
    raw_alpha = weight_obs * float(ewma_val) + weight_prior * float(prior_alpha)
    return round(_clip(raw_alpha, ALPHA_SAFE_MIN, ALPHA_SAFE_MAX), 4)


def _normalize_focus_pref(raw_pref: Optional[str]) -> str:
    cleaned = str(raw_pref or "BALANCED").strip().upper()
    alias = {
        "EARLY_BIRD": "MORNING",
        "MORNING_LARK": "MORNING",
        "NIGHT_OWL": "EVENING",
        "NIGHT": "EVENING",
    }.get(cleaned, cleaned)
    return alias if alias in CIRCADIAN_PROFILE_DEFAULTS else "BALANCED"


def _build_hourly_energy_profile(preference: str) -> CircadianEnergyProfile:
    base = CircadianEnergyProfile.from_preference(preference)
    hourly: Dict[int, int] = {}
    for h in range(24):
        if 6 <= h < 12:
            hourly[h] = base.morning_level
        elif 12 <= h < 18:
            hourly[h] = base.afternoon_level
        elif 18 <= h < 24:
            hourly[h] = base.evening_level
        else:
            hourly[h] = base.night_level
    base.hourly_levels = hourly
    return base


def _parse_disruption_zone(raw_zone: Any) -> Optional[Tuple[str, str, str]]:
    """Parse `'Thursday 19:30-21:00'` or dict into canonical `(day_of_week, start_hhmm, end_hhmm)`."""
    if isinstance(raw_zone, dict):
        day_raw = str(raw_zone.get("day_of_week") or raw_zone.get("day") or "").strip().lower()
        s_raw = str(raw_zone.get("start_time") or "").strip()
        e_raw = str(raw_zone.get("end_time") or "").strip()
        day_canon = _WEEKDAY_CANONICAL.get(day_raw)
        if day_canon and re.match(r"^\d{1,2}:\d{2}$", s_raw) and re.match(r"^\d{1,2}:\d{2}$", e_raw):
            sh, sm = map(int, s_raw.split(":"))
            eh, em = map(int, e_raw.split(":"))
            if (eh * 60 + em) > (sh * 60 + sm):
                return day_canon, f"{sh:02d}:{sm:02d}", f"{eh:02d}:{em:02d}"
        return None

    text = str(raw_zone or "").strip()
    if not text:
        return None
    m = re.match(
        r"^([A-Za-z]+)\s+(\d{1,2}:\d{2})\s*(?:-|–|—|to)\s*(\d{1,2}:\d{2})$",
        text,
    )
    if not m:
        return None
    day_canon = _WEEKDAY_CANONICAL.get(m.group(1).lower())
    if not day_canon:
        return None
    sh, sm = map(int, m.group(2).split(":"))
    eh, em = map(int, m.group(3).split(":"))
    if (eh * 60 + em) <= (sh * 60 + sm):
        return None
    return day_canon, f"{sh:02d}:{sm:02d}", f"{eh:02d}:{em:02d}"


def _estimate_weekly_load_ratio(profile: CommitmentsProfile, tasks: Sequence[Task]) -> float:
    """Fast Layer-1 weekly load ratio estimate (rho) to guard advisory buffer insertion."""
    sleep_s = parse_time_to_slot_offset(profile.sleep_schedule.daily_start_time, is_end_or_deadline=False)
    sleep_e = parse_time_to_slot_offset(profile.sleep_schedule.daily_end_time, is_end_or_deadline=True)
    sleep_slots_per_day = (sleep_e - sleep_s) % 96
    if sleep_slots_per_day <= 0:
        sleep_slots_per_day = 28

    horizon_days = max(7, int(getattr(profile, "horizon_days", 7) or 7))
    total_slots = 96 * horizon_days
    occupied_slots = sleep_slots_per_day * horizon_days

    for ev in profile.fixed_events:
        try:
            es = parse_time_to_slot_offset(ev.start_time, is_end_or_deadline=False)
            ee = parse_time_to_slot_offset(ev.end_time, is_end_or_deadline=True)
            span = max(0, ee - es)
        except Exception:
            span = 0
        if isinstance(ev.day_of_week, list):
            days_cnt = len(ev.day_of_week)
        elif str(ev.day_of_week).strip().upper() == "ALL":
            days_cnt = horizon_days
        else:
            days_cnt = 1
        occupied_slots += span * days_cnt

    free_min = max(60, (total_slots - occupied_slots) * 15)
    demand_min = sum(t.get_planned_duration_min() for t in tasks)
    for h in getattr(profile, "personal_habits", None) or []:
        demand_min += int(h.duration_min) * max(1, int(h.frequency_per_week))
    return float(demand_min) / float(free_min)


def adapt_preferences_for_next_week(
    profile: CommitmentsProfile,
    next_tasks: Sequence[Task],
    timeline_logs: Sequence[Dict[str, Any]],
    kappa: float = KAPPA_EMPIRICAL_BAYES,
    lambda_ewma: float = LAMBDA_CATEGORY_EWMA,
) -> Dict[str, Any]:
    """
    Adapt fallacy buffers, circadian peak window, ultradian chunk pacing, and day-specific
    recurring disruption buffers for Week t+1 from Week <= t execution logs (Pattern P13).
    """
    eff_kappa = max(0.0, float(kappa))
    eff_lambda = _clip(float(lambda_ewma), 0.05, 0.95)
    ordered_logs = _ensure_chronological_order(timeline_logs)

    adapted_profile = profile.model_copy(deep=True)
    raw_tasks_copy: List[Task] = [t.model_copy(deep=True) for t in (next_tasks or [])]
    preference_shifts: List[Dict[str, Any]] = []
    pattern_rules: List[Dict[str, str]] = []

    # ------------------------------------------------------------------
    # 1. Empirical Bayes Shrinkage Category Fallacy Buffers (P13.i)
    # ------------------------------------------------------------------
    cat_all_ratios: Dict[str, List[float]] = {}
    cat_light_ratios: Dict[str, List[float]] = {}
    cat_heavy_ratios: Dict[str, List[float]] = {}
    all_valid_ratios: List[float] = []

    for entry in ordered_logs:
        est_raw = entry.get("estimated_duration_min") or entry.get("estimated_min")
        act_raw = entry.get("actual_duration_min") or entry.get("actual_min")
        adhered_flag = entry.get("adhered")
        if adhered_flag is False and (act_raw is None or float(act_raw or 0) <= 0):
            continue
        if est_raw is None or act_raw is None:
            continue
        try:
            est_f = float(est_raw)
            act_f = float(act_raw)
        except (TypeError, ValueError):
            continue
        if est_f <= 0.0 or act_f <= 0.0:
            continue

        ratio = _clip(act_f / est_f, RATIO_CLIP_MIN, RATIO_CLIP_MAX)
        cat = str(entry.get("category") or "OTHER").strip().upper() or "OTHER"
        cat_all_ratios.setdefault(cat, []).append(ratio)
        all_valid_ratios.append(ratio)

        load_val = entry.get("cognitive_load")
        if load_val is not None:
            try:
                if int(load_val) >= 3:
                    cat_heavy_ratios.setdefault(cat, []).append(ratio)
                else:
                    cat_light_ratios.setdefault(cat, []).append(ratio)
            except (TypeError, ValueError):
                pass

    known_categories = sorted(
        set(cat_all_ratios.keys())
        | {str(t.category or "DEADLINE").strip().upper() or "DEADLINE" for t in raw_tasks_copy}
    )

    category_alphas: Dict[str, Dict[str, Any]] = {}
    for cat in known_categories:
        ratios_all = cat_all_ratios.get(cat, [])
        n_all = len(ratios_all)
        if n_all == 0:
            category_alphas[cat] = {
                "sample_count": 0,
                "ewma_ratio": None,
                "alpha_light": round(ALPHA_LIGHT_DEFAULT, 4),
                "alpha_heavy": round(ALPHA_HEAVY_DEFAULT, 4),
            }
            continue

        ewma_all = _compute_unbiased_ewma(ratios_all, eff_lambda)
        ratios_l = cat_light_ratios.get(cat, [])
        ratios_h = cat_heavy_ratios.get(cat, [])

        if ratios_l:
            a_light = _shrink_alpha(_compute_unbiased_ewma(ratios_l, eff_lambda), len(ratios_l), ALPHA_LIGHT_DEFAULT, eff_kappa)
        else:
            a_light = _shrink_alpha(ewma_all, n_all, ALPHA_LIGHT_DEFAULT, eff_kappa)

        if ratios_h:
            a_heavy_raw = _shrink_alpha(_compute_unbiased_ewma(ratios_h, eff_lambda), len(ratios_h), ALPHA_HEAVY_DEFAULT, eff_kappa)
        else:
            a_heavy_raw = _shrink_alpha(ewma_all, n_all, ALPHA_HEAVY_DEFAULT, eff_kappa)

        a_heavy = round(_clip(max(a_light, a_heavy_raw), ALPHA_SAFE_MIN, ALPHA_SAFE_MAX), 4)
        category_alphas[cat] = {
            "sample_count": n_all,
            "ewma_ratio": round(ewma_all, 4),
            "alpha_light": a_light,
            "alpha_heavy": a_heavy,
        }

        if abs(a_heavy - ALPHA_HEAVY_DEFAULT) >= 0.03 or abs(a_light - ALPHA_LIGHT_DEFAULT) >= 0.03:
            pct_h = int(round((a_heavy - 1.0) * 100))
            direction_vi = "tăng mức dự phòng" if a_heavy >= ALPHA_HEAVY_DEFAULT else "giảm nhẹ mức dự phòng"
            preference_shifts.append(
                {
                    "shift_type": "CATEGORY_BUFFER",
                    "target": cat,
                    "old_value": round(ALPHA_HEAVY_DEFAULT, 2),
                    "new_value": round(a_heavy, 2),
                    "alpha_light": round(a_light, 2),
                    "alpha_heavy": round(a_heavy, 2),
                    "sample_count": n_all,
                    "message_vi": (
                        f"Nhóm việc {cat} ({n_all} phiên tuần trước) được đề xuất {direction_vi} "
                        f"lên +{pct_h}% cho bài tập nặng để sát thời gian làm thực tế."
                    ),
                    "pattern_id": "P13",
                    "deterministic_rule": (
                        f"alpha_hat({cat}) = clip(({n_all}/({n_all}+{eff_kappa:.1f}))*{ewma_all:.2f} "
                        f"+ ({eff_kappa:.1f}/({n_all}+{eff_kappa:.1f}))*alpha_0, 1.00, 1.60) -> ({a_light:.2f}, {a_heavy:.2f})"
                    ),
                }
            )

    if all_valid_ratios:
        global_ewma = _compute_unbiased_ewma(all_valid_ratios, eff_lambda)
        n_tot = len(all_valid_ratios)
        adapted_profile.buffer_mode = "COGNITIVE_LOAD"
        adapted_profile.alpha_light = _shrink_alpha(global_ewma, n_tot, ALPHA_LIGHT_DEFAULT, eff_kappa)
        adapted_profile.alpha_heavy = max(
            adapted_profile.alpha_light,
            _shrink_alpha(global_ewma, n_tot, ALPHA_HEAVY_DEFAULT, eff_kappa),
        )

    adapted_tasks: List[Task] = []
    for t in raw_tasks_copy:
        if str(getattr(t, "buffer_mode", "HABIT")).strip().upper() == "NONE":
            t_none = t.model_copy(update={"buffer_mode": "NONE", "buffer_multiplier": 1.0}, deep=True)
            t_none.model_fields_set.update({"buffer_mode", "buffer_multiplier"})
            adapted_tasks.append(t_none)
            continue

        cat_key = str(t.category or "DEADLINE").strip().upper() or "DEADLINE"
        cat_info = category_alphas.get(cat_key)
        a_l = float(cat_info["alpha_light"]) if cat_info else float(ALPHA_LIGHT_DEFAULT)
        a_h = float(cat_info["alpha_heavy"]) if cat_info else float(ALPHA_HEAVY_DEFAULT)
        mult = multiplier_for_load(t.cognitive_load, a_l, a_h)

        # Strictly preserve raw t.duration_min to guarantee zero double-buffering across weeks!
        t_upd = t.model_copy(
            update={
                "buffer_mode": "COGNITIVE_LOAD",
                "alpha_light": a_l,
                "alpha_heavy": a_h,
                "buffer_multiplier": mult,
            },
            deep=True,
        )
        t_upd.model_fields_set.update({"buffer_mode", "alpha_light", "alpha_heavy", "buffer_multiplier"})
        adapted_tasks.append(t_upd)

    # ------------------------------------------------------------------
    # 2. Revealed Chronotype & Window Preference Shift (P13.ii)
    # ------------------------------------------------------------------
    win_total: Dict[str, int] = {w: 0 for w in VALID_WINDOWS}
    win_adhered: Dict[str, int] = {w: 0 for w in VALID_WINDOWS}
    win_speed_ratios: Dict[str, List[float]] = {w: [] for w in VALID_WINDOWS}

    for entry in ordered_logs:
        w = _infer_window_from_entry(entry)
        if w not in VALID_WINDOWS:
            continue
        win_total[w] += 1
        adhered_bool = bool(entry.get("adhered", True))
        if adhered_bool:
            win_adhered[w] += 1
            est_r = entry.get("estimated_duration_min") or entry.get("estimated_min")
            act_r = entry.get("actual_duration_min") or entry.get("actual_min")
            try:
                if est_r and act_r and float(est_r) > 0 and float(act_r) > 0:
                    win_speed_ratios[w].append(float(est_r) / float(act_r))
            except (TypeError, ValueError):
                pass

    window_effectiveness: Dict[str, Dict[str, Any]] = {}
    eligible_windows: Dict[str, float] = {}
    for w in VALID_WINDOWS:
        n_w = win_total[w]
        if n_w == 0:
            window_effectiveness[w] = {
                "sample_count": 0,
                "adherence_rate": None,
                "speed_factor": None,
                "effectiveness": None,
            }
            continue
        adh_rate = float(win_adhered[w]) / float(n_w)
        if win_speed_ratios[w]:
            mean_est_over_act = sum(win_speed_ratios[w]) / float(len(win_speed_ratios[w]))
            speed_factor = _clip(mean_est_over_act, EFF_RATIO_CLIP_MIN, EFF_RATIO_CLIP_MAX)
        else:
            speed_factor = EFF_RATIO_CLIP_MIN
        eff_score = round(adh_rate * speed_factor, 4)
        window_effectiveness[w] = {
            "sample_count": n_w,
            "adherence_rate": round(adh_rate, 4),
            "speed_factor": round(speed_factor, 4),
            "effectiveness": eff_score,
        }
        if n_w >= CHRONOTYPE_MIN_WINDOW_SAMPLES:
            eligible_windows[w] = eff_score

    stated_pref = _normalize_focus_pref(adapted_profile.focus_preference)
    shifted_window: Optional[str] = None
    if eligible_windows:
        best_win = max(
            VALID_WINDOWS,
            key=lambda cand: (
                eligible_windows.get(cand, -1.0),
                1 if cand == stated_pref else 0,
            ),
        )
        best_eff = eligible_windows.get(best_win, -1.0)
        if best_win != stated_pref and best_eff > 0:
            if stated_pref in eligible_windows:
                stated_eff = eligible_windows[stated_pref]
                stated_adh = float(window_effectiveness[stated_pref]["adherence_rate"] or 0.0)
                if (best_eff - stated_eff) >= CHRONOTYPE_SHIFT_MARGIN and stated_adh <= STATED_ADHERENCE_MAX_FOR_SHIFT:
                    shifted_window = best_win
            elif stated_pref == "BALANCED" and len(eligible_windows) >= 2:
                other_effs = [v for k, v in eligible_windows.items() if k != best_win]
                if other_effs and (best_eff - min(other_effs)) >= CHRONOTYPE_SHIFT_MARGIN and best_eff >= 0.80:
                    shifted_window = best_win

    if shifted_window is not None:
        old_label = _WINDOW_VI_LABELS.get(stated_pref, stated_pref)
        new_label = _WINDOW_VI_LABELS.get(shifted_window, shifted_window)
        adapted_profile.focus_preference = shifted_window
        adapted_profile.energy_profile = _build_hourly_energy_profile(shifted_window)

        updated_deep_tasks: List[Task] = []
        for t in adapted_tasks:
            eff_load = int(t.cognitive_load) if t.cognitive_load is not None else (3 if t.priority >= 5 else 2)
            cur_pw = str(t.preferred_window or "").strip().upper()
            has_explicit_lock = "preferred_window" in t.model_fields_set and cur_pw in VALID_WINDOWS
            if eff_load >= 3 and not has_explicit_lock:
                t_pw = t.model_copy(update={"preferred_window": shifted_window}, deep=True)
                t_pw.model_fields_set.add("preferred_window")
                updated_deep_tasks.append(t_pw)
            else:
                updated_deep_tasks.append(t)
        adapted_tasks = updated_deep_tasks

        stated_eff_val = window_effectiveness.get(stated_pref, {}).get("effectiveness")
        best_eff_val = window_effectiveness[shifted_window]["effectiveness"]
        preference_shifts.append(
            {
                "shift_type": "CHRONOTYPE_WINDOW",
                "target": "focus_preference",
                "old_value": stated_pref,
                "new_value": shifted_window,
                "message_vi": (
                    f"Thực tế tuần trước bạn hoàn thành phiên học ở {new_label} hiệu quả hơn hẳn so với "
                    f"{old_label}. Hệ thống đề xuất chuyển khung giờ ưu tiên việc khó sang {new_label}."
                ),
                "pattern_id": "P13",
                "deterministic_rule": (
                    f"Eff({shifted_window})={best_eff_val:.2f} - Eff({stated_pref})="
                    f"{(stated_eff_val if stated_eff_val is not None else 0.0):.2f} >= {CHRONOTYPE_SHIFT_MARGIN:.2f}"
                ),
            }
        )

    # ------------------------------------------------------------------
    # 3. Ultradian Fatigue Pacing & Day-Specific Disruption Zones (§7.8.4)
    # ------------------------------------------------------------------
    fatigue_values: List[float] = []
    long_block_total = 0
    long_block_troubled = 0

    for entry in ordered_logs:
        if entry.get("fatigue_after") is not None:
            try:
                fv = float(entry["fatigue_after"])
                if 0.0 <= fv <= 1.5:
                    fatigue_values.append(fv)
            except (TypeError, ValueError):
                pass

        ref_dur = entry.get("planned_duration_min") or entry.get("estimated_duration_min") or 0
        act_dur = entry.get("actual_duration_min") or 0
        try:
            ref_dur_f = float(ref_dur)
            act_dur_f = float(act_dur)
        except (TypeError, ValueError):
            ref_dur_f, act_dur_f = 0.0, 0.0

        if ref_dur_f > LONG_BLOCK_MIN_THRESHOLD:
            long_block_total += 1
            adhered_ok = bool(entry.get("adhered", True))
            if (not adhered_ok) or (act_dur_f > ref_dur_f * 1.10):
                long_block_troubled += 1

    mean_fatigue = (sum(fatigue_values) / float(len(fatigue_values))) if fatigue_values else 0.0
    long_overrun_rate = (float(long_block_troubled) / float(long_block_total)) if long_block_total > 0 else 0.0
    pacing_adjusted = bool(
        (fatigue_values and mean_fatigue > FATIGUE_PACING_THRESHOLD)
        or (long_block_total >= 2 and long_overrun_rate >= LONG_BLOCK_OVERRUN_RATE_THRESHOLD)
    )

    if pacing_adjusted:
        paced_tasks: List[Task] = []
        paced_count = 0
        for t in adapted_tasks:
            eff_load = int(t.cognitive_load) if t.cognitive_load is not None else 2
            explicitly_atomic = (
                "is_splittable" in t.model_fields_set
                and t.is_splittable is False
                and str(t.work_rhythm or "").strip().upper() not in ("FLOW", "")
            )
            if eff_load >= 2 and t.duration_min > PACED_MAX_CHUNK_MIN and not explicitly_atomic:
                t_paced = t.model_copy(
                    update={
                        "work_rhythm": "BALANCED",
                        "min_chunk_min": PACED_MIN_CHUNK_MIN,
                        "max_chunk_min": PACED_MAX_CHUNK_MIN,
                        "is_splittable": True,
                    },
                    deep=True,
                )
                t_paced.model_fields_set.update(
                    {"work_rhythm", "min_chunk_min", "max_chunk_min", "is_splittable"}
                )
                paced_tasks.append(t_paced)
                paced_count += 1
            else:
                paced_tasks.append(t)
        adapted_tasks = paced_tasks

        if paced_count > 0:
            preference_shifts.append(
                {
                    "shift_type": "WORK_RHYTHM_PACING",
                    "target": "work_rhythm",
                    "old_value": "FLOW (60–120m)",
                    "new_value": f"BALANCED ({PACED_MIN_CHUNK_MIN}–{PACED_MAX_CHUNK_MIN}m)",
                    "affected_tasks": paced_count,
                    "message_vi": (
                        f"Các phiên học dài tuần trước có dấu hiệu quá sức hoặc dễ lố giờ. "
                        f"Hệ thống đề xuất chia nhỏ {paced_count} việc lớn thành các chặng {PACED_MIN_CHUNK_MIN}–{PACED_MAX_CHUNK_MIN} phút có nghỉ giữa giờ."
                    ),
                    "pattern_id": "P13",
                    "deterministic_rule": (
                        f"mean_fatigue={mean_fatigue:.2f}>{FATIGUE_PACING_THRESHOLD} OR "
                        f"long_overrun_rate={long_overrun_rate:.2f}>={LONG_BLOCK_OVERRUN_RATE_THRESHOLD} -> chunk in [45m, 75m]"
                    ),
                }
            )

    # Day-specific Chronic Disruption Zones (Fix M-3: never corrupt 7-day periodic hourly_levels!)
    zone_counts: Dict[Tuple[str, str, str], int] = {}
    for entry in ordered_logs:
        raw_z = entry.get("disruption_slot_window")
        parsed_z = _parse_disruption_zone(raw_z) if raw_z else None
        if parsed_z is not None:
            zone_counts[parsed_z] = zone_counts.get(parsed_z, 0) + 1

    chronic_disruption_zones: List[Dict[str, Any]] = []
    if zone_counts:
        est_rho = _estimate_weekly_load_ratio(adapted_profile, adapted_tasks)
        existing_spans = {
            (str(fe.day_of_week), fe.start_time, fe.end_time)
            for fe in adapted_profile.fixed_events
            if isinstance(fe.day_of_week, str)
        }
        for (day_canon, s_hhmm, e_hhmm), cnt in sorted(zone_counts.items()):
            if cnt < CHRONIC_DISRUPTION_MIN_COUNT:
                continue
            can_reserve = est_rho <= ADVISORY_BUFFER_MAX_RHO and (day_canon, s_hhmm, e_hhmm) not in existing_spans
            action_tag = "ADVISORY_BUFFER_ADDED" if can_reserve else "ADVISORY_WARNING_ONLY"
            if can_reserve:
                adapted_profile.fixed_events.append(
                    FixedEvent(
                        event_id=f"ADV_RESERVE_{day_canon[:3].upper()}_{s_hhmm.replace(':', '')}",
                        title=f"Khoảng đệm dự phòng phát sinh ({day_canon} {s_hhmm}–{e_hhmm})",
                        day_of_week=day_canon,
                        start_time=s_hhmm,
                        end_time=e_hhmm,
                        category="ADVISORY_BUFFER",
                    )
                )
                existing_spans.add((day_canon, s_hhmm, e_hhmm))

            chronic_disruption_zones.append(
                {
                    "day_of_week": day_canon,
                    "start_time": s_hhmm,
                    "end_time": e_hhmm,
                    "slot_window": f"{day_canon} {s_hhmm}-{e_hhmm}",
                    "occurrences": cnt,
                    "action": action_tag,
                }
            )
            preference_shifts.append(
                {
                    "shift_type": "CHRONIC_DISRUPTION_ZONE",
                    "target": f"{day_canon} {s_hhmm}–{e_hhmm}",
                    "old_value": "FREE",
                    "new_value": action_tag,
                    "occurrences": cnt,
                    "message_vi": (
                        f"Khung giờ {day_canon} {s_hhmm}–{e_hhmm} đã có việc đột xuất lặp lại {cnt} lần. "
                        f"Hệ thống tự động khoanh vùng dự phòng riêng ngày {day_canon} để tránh xếp bài quan trọng vào đây."
                    ),
                    "pattern_id": "P13",
                    "deterministic_rule": (
                        f"count(disruption[{day_canon} {s_hhmm}-{e_hhmm}])={cnt} >= 2 -> day-scoped ADVISORY_BUFFER"
                    ),
                }
            )

    if preference_shifts:
        pattern_rules.append(
            {
                "pattern_id": "P13",
                "pattern_name": "Cross-Week Category Fallacy & Revealed Chronotype Learning",
                "causal_link_vi": (
                    "Co rút thực nghiệm Bayes-EWMA chống nhiễu mẫu nhỏ đầu kỳ và đối chiếu tỷ lệ bám lịch thực tế theo buổi"
                ),
                "deterministic_rule": (
                    "alpha_hat_{c,l} = clip((n_c/(n_c+3))*EWMA_c + (3/(n_c+3))*alpha_0(l), 1.00, 1.60); "
                    "shift focus_preference iff Delta_Eff(w) >= 0.22"
                ),
            }
        )

    return {
        "adapted_profile": adapted_profile,
        "adapted_commitments": adapted_profile.model_dump(),
        "adapted_tasks": adapted_tasks,
        "adapted_tasks_dump": [t.model_dump() for t in adapted_tasks],
        "category_alphas": category_alphas,
        "window_effectiveness": window_effectiveness,
        "preference_shifts": preference_shifts,
        "chronic_disruption_zones": chronic_disruption_zones,
        "pacing_adjusted": pacing_adjusted,
        "pattern_rules": pattern_rules,
    }
