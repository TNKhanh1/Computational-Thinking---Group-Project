"""
Estimate Buffer (Planning-Fallacy Correction) — Feature 001.

Spec: specs/001-estimate-buffer/spec.md
Source: Improve Plan §6.2 (planned duration), §7.3 (profile.estimate_habit), F04, F06.

Pure functions only (Layer 1): no imports from web, fastapi, controller or solvers (INV-1, INV-2).
All arithmetic is done on integers so results are deterministic on every platform.
"""

from typing import Any, Dict, Optional

from src.utils import MINUTES_PER_SLOT, round_up_to_15

ESTIMATE_HABITS = ("RARELY", "SOMETIMES", "OFTEN")

# Spec FR2 / clarification C1.
HABIT_MULTIPLIER: Dict[str, float] = {
    "RARELY": 1.00,
    "SOMETIMES": 1.10,
    "OFTEN": 1.25,
}

HABIT_LABEL_VI: Dict[str, str] = {
    "RARELY": "hiếm khi ước lượng thiếu",
    "SOMETIMES": "thỉnh thoảng ước lượng thiếu",
    "OFTEN": "thường ước lượng thiếu",
}


def normalize_habit(value: Any) -> Optional[str]:
    """Return RARELY / SOMETIMES / OFTEN, or None for an empty value. Raise ValueError otherwise."""
    if value is None:
        return None
    text = str(value).strip().upper()
    if text in ("", "NONE", "NULL", "OFF"):
        return None
    if text not in HABIT_MULTIPLIER:
        raise ValueError(f"estimate_habit must be one of {', '.join(ESTIMATE_HABITS)} (got {value!r})")
    return text


def multiplier_for_habit(habit: Any) -> float:
    """Multiplier for a habit. An empty habit means no buffer (exact V0 behaviour)."""
    key = normalize_habit(habit)
    return HABIT_MULTIPLIER[key] if key else 1.0


def planned_duration_min(estimate_min: int, multiplier: float = 1.0) -> int:
    """
    Planned duration for an estimate (spec FR3, clarification C3).

    planned = max(round_up_to_15(estimate), nearest_15(estimate × multiplier))

    * Rounding to the *nearest* slot (half up) instead of rounding up again avoids
      doubling small tasks (15 min × 1.25 = 18.75 → 15, not 30).
    * The floor keeps the planned time from ever dropping below the unbuffered V0 value.
    """
    estimate = int(estimate_min)
    if estimate <= 0:
        return 0
    floor_min = round_up_to_15(estimate)
    pct = int(round(float(multiplier) * 100))
    if pct <= 100:
        return floor_min
    slot_x100 = MINUTES_PER_SLOT * 100
    nearest_slots = (estimate * pct + slot_x100 // 2) // slot_x100
    return max(floor_min, nearest_slots * MINUTES_PER_SLOT)


def buffer_reason(estimate_min: int, planned_min: int, multiplier: float, habit: Optional[str]) -> Dict[str, Any]:
    """Structured reason attached to blocks whose planned time was increased (spec FR5)."""
    label = HABIT_LABEL_VI.get(habit or "", "")
    suffix = f" — bạn {label}" if label else ""
    return {
        "code": "ESTIMATE_BUFFER",
        "estimate_min": int(estimate_min),
        "planned_min": int(planned_min),
        "multiplier": float(multiplier),
        "text": f"Dự trù {planned_min}p cho ước lượng {estimate_min}p (×{multiplier:g}){suffix}",
    }
