"""
Estimate Buffer (Planning-Fallacy Correction) — Feature 001.

Spec: specs/001-estimate-buffer/spec.md
Source: Improve Plan §6.2 (planned duration), §7.3 (profile.estimate_habit), F04, F06.

Pure functions only (Layer 1): no imports from web, fastapi, controller or solvers (INV-1, INV-2).
All arithmetic is done on integers so results are deterministic on every platform.
"""

import math
from typing import Any, Dict, Optional

from smartschedule.core.config import ALPHA_HEAVY_DEFAULT, ALPHA_LIGHT_DEFAULT
from smartschedule.core.utils import MINUTES_PER_SLOT, round_up_to_15

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


def multiplier_for_load(
    cognitive_load: Optional[int],
    alpha_light: float = ALPHA_LIGHT_DEFAULT,
    alpha_heavy: float = ALPHA_HEAVY_DEFAULT,
) -> float:
    """
    Proposal / Presentation2 Pattern 1 α scaling by cognitive load:
      - load == 3 (Heavy / Deep Work) -> α_heavy (1.35)
      - load in {1, 2, None} (Light / Medium) -> α_light (1.20)
    """
    if cognitive_load is not None and int(cognitive_load) >= 3:
        return float(alpha_heavy)
    return float(alpha_light)


def planned_duration_roundup_15(estimate_min: int, multiplier: float = 1.0) -> int:
    """
    Presentation2 Slide 7 & Slide 17 exact formula:
      Planned_Duration = RoundUp_15(Estimated_Duration * α)
    """
    estimate = int(estimate_min)
    if estimate <= 0:
        return 0
    raw_scaled = int(math.ceil(estimate * float(multiplier) - 1e-9))
    return max(round_up_to_15(estimate), round_up_to_15(raw_scaled))


def planned_duration_for_task_mode(
    estimate_min: int,
    buffer_multiplier: float = 1.0,
    cognitive_load: Optional[int] = None,
    buffer_mode: str = "HABIT",
    alpha_light: float = ALPHA_LIGHT_DEFAULT,
    alpha_heavy: float = ALPHA_HEAVY_DEFAULT,
) -> int:
    """Dispatch planned duration cleanly between Feature 001 (HABIT), Presentation2 (COGNITIVE_LOAD), and NONE (opt-out)."""
    mode = (buffer_mode or "HABIT").strip().upper()
    if mode in ("NONE", "OFF", "DISABLED", "NO_BUFFER"):
        return round_up_to_15(int(estimate_min))
    if mode == "COGNITIVE_LOAD":
        alpha = multiplier_for_load(cognitive_load, alpha_light=alpha_light, alpha_heavy=alpha_heavy)
        return planned_duration_roundup_15(estimate_min, alpha)
    return planned_duration_min(estimate_min, buffer_multiplier)
