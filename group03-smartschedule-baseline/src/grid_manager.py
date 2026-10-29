"""
Discrete 672-Slot Time Grid & Hard Constraint Manager (Module M2).
Each week has 672 slots of 15 minutes (7 days x 24 hours x 4 slots/hour).
Enforces Hard Constraints H1-H5:
  - H1: Zero overlap with fixed commitments (OCCUPIED)
  - H2: Protected biological sleep window locked (SLEEP)
  - H3: Tasks placed strictly inside confirmed FREE slots
  - H4: Task blocks must finish at or before their deadline (end_slot <= deadline_slot)
  - H5: Prerequisite dependency order (start_slot >= max(end_slot of depends_on))
"""

from copy import deepcopy
from typing import Dict, List, Optional, Tuple, Union

from src.models import CommitmentsProfile, FixedEvent, SleepSchedule
from src.utils import (
    DAYS_OF_WEEK,
    DAYS_PER_WEEK,
    MINUTES_PER_SLOT,
    SLOTS_PER_DAY,
    SLOTS_PER_WEEK,
    parse_day_to_index,
    parse_time_to_slot_offset,
)


class TimeGridManager:
    """Manages the 672-slot weekly discrete time grid and hard constraint checks."""

    STATE_FREE = "FREE"
    STATE_SLEEP = "SLEEP"
    STATE_OCCUPIED = "OCCUPIED"
    STATE_BLOCK = "BLOCK"

    def __init__(self, total_slots: int = SLOTS_PER_WEEK):
        self.total_slots: int = total_slots
        # Raw state per slot: "FREE", "SLEEP", "OCCUPIED:<event_id>", or "BLOCK:<task_id>"
        self.grid: List[str] = [self.STATE_FREE] * total_slots
        # Human-readable label per slot (for UI tooltips and inspection)
        self.labels: List[str] = [""] * total_slots
        # Snapshot of baseline immutable states (SLEEP and OCCUPIED) for violation auditing
        self._locked_mask: List[str] = [self.STATE_FREE] * total_slots

    def clone(self) -> "TimeGridManager":
        """Create a fast deep copy of the current grid state (used in Backtracking & Repair trials)."""
        copied = TimeGridManager(self.total_slots)
        copied.grid = list(self.grid)
        copied.labels = list(self.labels)
        copied._locked_mask = list(self._locked_mask)
        return copied

    def initialize_from_profile(self, profile: CommitmentsProfile) -> None:
        """Reset the grid and lock sleep schedule + fixed commitments from a CommitmentsProfile."""
        self.grid = [self.STATE_FREE] * self.total_slots
        self.labels = [""] * self.total_slots
        self._locked_mask = [self.STATE_FREE] * self.total_slots

        if profile.sleep_schedule and profile.sleep_schedule.is_hard_lock:
            self.lock_sleep_schedule(profile.sleep_schedule)

        for event in profile.fixed_events:
            self.lock_fixed_event(event)

    def lock_sleep_schedule(self, sleep: SleepSchedule) -> None:
        """
        Lock nightly sleep slots across all days in the grid.
        Example: 23:30 to 06:30 locks [00:00..06:30) and [23:30..24:00) on each day (28 slots/day = 196 slots/week).
        """
        start_offset = parse_time_to_slot_offset(sleep.daily_start_time, is_end_or_deadline=False)
        end_offset = parse_time_to_slot_offset(sleep.daily_end_time, is_end_or_deadline=True)

        num_days = self.total_slots // SLOTS_PER_DAY
        for day_idx in range(num_days):
            day_base = day_idx * SLOTS_PER_DAY
            if start_offset > end_offset:
                # Crosses midnight: [0, end_offset) and [start_offset, 96)
                for offset in range(0, end_offset):
                    idx = day_base + offset
                    self.grid[idx] = self.STATE_SLEEP
                    self._locked_mask[idx] = self.STATE_SLEEP
                    self.labels[idx] = f"Sleep ({sleep.daily_start_time}–{sleep.daily_end_time})"
                for offset in range(start_offset, SLOTS_PER_DAY):
                    idx = day_base + offset
                    self.grid[idx] = self.STATE_SLEEP
                    self._locked_mask[idx] = self.STATE_SLEEP
                    self.labels[idx] = f"Sleep ({sleep.daily_start_time}–{sleep.daily_end_time})"
            elif start_offset < end_offset:
                # Within same day: [start_offset, end_offset)
                for offset in range(start_offset, end_offset):
                    idx = day_base + offset
                    self.grid[idx] = self.STATE_SLEEP
                    self._locked_mask[idx] = self.STATE_SLEEP
                    self.labels[idx] = f"Sleep ({sleep.daily_start_time}–{sleep.daily_end_time})"

    def lock_fixed_event(self, event: FixedEvent) -> None:
        """
        Lock slots for a fixed commitment (class, meal, work shift, meeting).
        Note: SLEEP always takes precedence if a fixed event overlaps sleep.
        """
        start_offset = parse_time_to_slot_offset(event.start_time, is_end_or_deadline=False)
        end_offset = parse_time_to_slot_offset(event.end_time, is_end_or_deadline=True)
        if end_offset <= start_offset:
            raise ValueError(
                f"Invalid fixed event '{event.event_id}': end_time ({event.end_time}) must be after start_time ({event.start_time})."
            )

        day_indices = self._resolve_event_days(event.day_of_week)
        state_tag = f"{self.STATE_OCCUPIED}:{event.event_id}"

        for day_idx in day_indices:
            if day_idx * SLOTS_PER_DAY >= self.total_slots:
                continue
            day_base = day_idx * SLOTS_PER_DAY
            for offset in range(start_offset, end_offset):
                idx = day_base + offset
                if 0 <= idx < self.total_slots:
                    # Preserve SLEEP if already marked SLEEP
                    if self.grid[idx] != self.STATE_SLEEP:
                        self.grid[idx] = state_tag
                        self._locked_mask[idx] = state_tag
                        self.labels[idx] = f"{event.title} ({event.start_time}–{event.end_time})"

    def _resolve_event_days(self, day_spec: Union[str, List[str]]) -> List[int]:
        """Resolve 'ALL', single weekday name, or list of weekday names into day indices."""
        num_days = self.total_slots // SLOTS_PER_DAY
        if isinstance(day_spec, list):
            indices = []
            for d in day_spec:
                if str(d).strip().upper() == "ALL":
                    return list(range(num_days))
                base_d = parse_day_to_index(str(d))
                indices.append(base_d)
                if num_days > DAYS_PER_WEEK and base_d < DAYS_PER_WEEK:
                    indices.append(base_d + DAYS_PER_WEEK)
            return sorted(set(indices))

        cleaned = str(day_spec).strip()
        if cleaned.upper() == "ALL":
            return list(range(num_days))
        if "," in cleaned:
            parts = [p.strip() for p in cleaned.split(",") if p.strip()]
            return self._resolve_event_days(parts)

        base_d = parse_day_to_index(cleaned)
        indices = [base_d]
        if num_days > DAYS_PER_WEEK and base_d < DAYS_PER_WEEK:
            indices.append(base_d + DAYS_PER_WEEK)
        return indices

    def is_slot_free(self, slot_idx: int) -> bool:
        """Return True iff slot_idx is within bounds and in state FREE."""
        return 0 <= slot_idx < self.total_slots and self.grid[slot_idx] == self.STATE_FREE

    def is_range_free(self, start_slot: int, length_slots: int, max_slot: Optional[int] = None) -> bool:
        """Check whether [start_slot, start_slot + length_slots) consists strictly of FREE slots."""
        limit = self.total_slots if max_slot is None else min(self.total_slots, max_slot)
        if length_slots <= 0:
            return False
        if start_slot < 0 or start_slot + length_slots > limit:
            return False
        for s in range(start_slot, start_slot + length_slots):
            if self.grid[s] != self.STATE_FREE:
                return False
        return True

    def can_place_chunk(
        self,
        start_slot: int,
        length_slots: int,
        deadline_slot: Optional[int] = None,
        earliest_start_slot: int = 0,
        max_grid_slot: Optional[int] = None,
    ) -> bool:
        """
        Verify all Hard Constraints H1-H5 for placing a chunk of `length_slots` at `start_slot`:
          - H1, H2, H3: Range [start_slot, end_slot) is completely FREE
          - H4: end_slot <= deadline_slot (if task has a deadline)
          - H5: start_slot >= earliest_start_slot (respects `now` and `depends_on` end slots)
        """
        if start_slot < earliest_start_slot:
            return False
        end_slot = start_slot + length_slots
        if deadline_slot is not None and end_slot > deadline_slot:
            return False
        return self.is_range_free(start_slot, length_slots, max_slot=max_grid_slot)

    def explain_violation(
        self,
        start_slot: int,
        length_slots: int,
        deadline_slot: Optional[int] = None,
        earliest_start_slot: int = 0,
    ) -> List[Dict[str, str]]:
        """Return detailed violation reasons if a placement at `start_slot` is invalid (used by /api/validate-move)."""
        violations: List[Dict[str, str]] = []
        end_slot = start_slot + length_slots

        if start_slot < 0 or end_slot > self.total_slots:
            violations.append({"code": "OUT_OF_BOUNDS", "message": "Vị trí nằm ngoài phạm vi lưới tuần (0..672)."})
            return violations

        if start_slot < earliest_start_slot:
            violations.append({
                "code": "H5_DEPENDENCY_OR_PAST",
                "message": "Vi phạm thứ tự phụ thuộc (depends_on) hoặc đặt trước thời điểm hiện tại (now).",
            })

        if deadline_slot is not None and end_slot > deadline_slot:
            violations.append({
                "code": "H4_DEADLINE_VIOLATION",
                "message": "Khối công việc kết thúc sau hạn chót (Deadline).",
            })

        hit_sleep = False
        hit_occupied = False
        hit_block = False
        for s in range(start_slot, end_slot):
            state = self.grid[s]
            if state == self.STATE_SLEEP:
                hit_sleep = True
            elif state.startswith(self.STATE_OCCUPIED):
                hit_occupied = True
            elif state.startswith(self.STATE_BLOCK):
                hit_block = True

        if hit_sleep:
            violations.append({
                "code": "H2_SLEEP_VIOLATION",
                "message": "Không thể đặt vào khung giờ ngủ được bảo vệ (SLEEP).",
            })
        if hit_occupied:
            violations.append({
                "code": "H1_COMMITMENT_OVERLAP",
                "message": "Trùng với lịch học cố định hoặc sinh hoạt cá nhân (OCCUPIED).",
            })
        if hit_block:
            violations.append({
                "code": "H3_TASK_OVERLAP",
                "message": "Trùng với một khối công việc khác đã được xếp trên lịch.",
            })

        return violations

    def place_block(self, start_slot: int, length_slots: int, task_id: str, title: str = "") -> None:
        """Mark [start_slot, start_slot + length_slots) as BLOCK:<task_id>."""
        if not self.is_range_free(start_slot, length_slots):
            raise ValueError(
                f"Cannot place task '{task_id}' at [{start_slot}, {start_slot + length_slots}): slots not FREE."
            )
        tag = f"{self.STATE_BLOCK}:{task_id}"
        label = title or task_id
        for s in range(start_slot, start_slot + length_slots):
            self.grid[s] = tag
            self.labels[s] = label

    def remove_block(self, start_slot: int, length_slots: int) -> None:
        """Release a previously placed task block back to FREE (only if not locked by SLEEP/OCCUPIED)."""
        for s in range(start_slot, min(self.total_slots, start_slot + length_slots)):
            if self._locked_mask[s] == self.STATE_FREE:
                self.grid[s] = self.STATE_FREE
                self.labels[s] = ""
            else:
                self.grid[s] = self._locked_mask[s]

    def get_free_intervals(self, start_from: int = 0, up_to: Optional[int] = None) -> List[Tuple[int, int]]:
        """
        Return all contiguous runs of FREE slots inside [start_from, up_to) as a list of (run_start, run_length).
        Used by Best-Fit (LST) and Fragmentation Analysis.
        """
        limit = self.total_slots if up_to is None else min(self.total_slots, up_to)
        intervals: List[Tuple[int, int]] = []
        idx = max(0, start_from)
        while idx < limit:
            if self.grid[idx] == self.STATE_FREE:
                run_start = idx
                while idx < limit and self.grid[idx] == self.STATE_FREE:
                    idx += 1
                intervals.append((run_start, idx - run_start))
            else:
                idx += 1
        return intervals

    def count_free_slots_in_range(self, start_from: int = 0, up_to: Optional[int] = None) -> int:
        """Count total number of FREE slots inside [start_from, up_to)."""
        limit = self.total_slots if up_to is None else min(self.total_slots, up_to)
        lo = max(0, start_from)
        if lo >= limit:
            return 0
        return sum(1 for s in range(lo, limit) if self.grid[s] == self.STATE_FREE)

    def get_slot_counts(self, up_to: int = SLOTS_PER_WEEK) -> Dict[str, int]:
        """Count SLEEP, OCCUPIED, BLOCK, and FREE slots in the primary 672-slot week."""
        limit = min(self.total_slots, up_to)
        counts = {"SLEEP": 0, "OCCUPIED": 0, "BLOCK": 0, "FREE": 0}
        for s in range(limit):
            st = self.grid[s]
            if st == self.STATE_SLEEP:
                counts["SLEEP"] += 1
            elif st.startswith(self.STATE_OCCUPIED):
                counts["OCCUPIED"] += 1
            elif st.startswith(self.STATE_BLOCK):
                counts["BLOCK"] += 1
            else:
                counts["FREE"] += 1
        return counts

