"""
Unit tests for 672-Slot Discrete Time Grid representation (`src/grid_manager.py` and `src/utils.py`).
Verifies:
  - 7 days * 96 slots/day = 672 slots exact math
  - Minh's Week exact slot accounting: 196 SLEEP + 132 OCCUPIED + 344 FREE = 672 slots
  - Cross-midnight sleep locking and interval queries
"""

import json
from pathlib import Path

from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile
from src.utils import MINUTES_PER_SLOT, day_time_to_slot, minutes_to_slots, slot_to_day_time

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_slot_conversion_math():
    assert minutes_to_slots(15) == 1
    assert minutes_to_slots(60) == 4
    assert minutes_to_slots(90) == 6
    assert 4 * MINUTES_PER_SLOT == 60

    # Monday 00:00 -> slot 0
    assert day_time_to_slot("Monday", "00:00") == 0
    # Monday 06:30 -> slot 26
    assert day_time_to_slot("Monday", "06:30") == 26
    # Sunday 23:45 -> slot 671
    assert day_time_to_slot("Sunday", "23:45") == 671
    # Sunday 23:59 (end boundary) -> 672
    assert day_time_to_slot("Sunday", "23:59", is_end_or_deadline=True) == 672

    day, start = slot_to_day_time(0)
    assert (day, start) == ("Monday", "00:00")


def test_minh_week_exact_672_slot_accounting():
    """
    Verifies the exact slot breakdown specified in Proposal_Report.pdf §2.8 & §5.5:
      Total = 672 slots (10,080 minutes)
      SLEEP = 196 slots (2,940 minutes)
      OCCUPIED = 132 slots (1,980 minutes)
      FREE = 344 slots (5,160 minutes)
    """
    comm_path = DATA_DIR / "sample_week_commitments.json"
    raw = json.loads(comm_path.read_text(encoding="utf-8"))
    profile = CommitmentsProfile.model_validate(raw)

    gm = TimeGridManager()
    gm.initialize_from_profile(profile)
    summary = gm.get_slot_counts()

    assert len(gm.grid) == 672
    assert summary["SLEEP"] == 196, f"Expected 196 SLEEP slots, got {summary['SLEEP']}"
    assert summary["OCCUPIED"] == 132, f"Expected 132 OCCUPIED slots, got {summary['OCCUPIED']}"
    assert summary["FREE"] == 344, f"Expected 344 FREE slots, got {summary['FREE']}"
    assert summary["BLOCK"] == 0
    assert sum(summary.values()) == 672


def test_sleep_and_fixed_event_locking():
    comm_path = DATA_DIR / "sample_week_commitments.json"
    profile = CommitmentsProfile.model_validate(json.loads(comm_path.read_text(encoding="utf-8")))
    gm = TimeGridManager()
    gm.initialize_from_profile(profile)

    # Monday 01:00 (slot 4) must be SLEEP
    assert gm.grid[4] == TimeGridManager.STATE_SLEEP
    assert not gm.is_range_free(0, 8)
    violations_sleep = gm.explain_violation(0, 8)
    assert any("SLEEP" in v["code"] for v in violations_sleep)

    # Monday 13:00-17:00 (slots 52..68) is class -> OCCUPIED
    assert gm.grid[52].startswith(TimeGridManager.STATE_OCCUPIED)
    assert not gm.is_range_free(52, 4)
    violations_occ = gm.explain_violation(52, 4)
    assert any("COMMITMENT" in v["code"] for v in violations_occ)
