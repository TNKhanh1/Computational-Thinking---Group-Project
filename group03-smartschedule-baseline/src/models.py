"""
Pydantic Data Models & Schemas for SmartSchedule Baseline (V0).
Supports both:
  1. Baseline Schema (baseline_plan.md §6: deadline_day, deadline_time, commitments.json, tasks.json)
  2. Improve Plan Contract (improve_plan.md §7: ISO-8601 datetimes, explicit `now`, reason codes)
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, model_validator

from src.utils import (
    MINUTES_PER_SLOT,
    SLOTS_PER_WEEK,
    day_time_to_slot,
    iso_to_slot,
    minutes_to_slots,
    round_up_to_15,
    slot_to_day_time,
    slot_to_iso,
)

GRADE_WEIGHT_TO_PRIORITY = {
    "30+": 5,
    "20-29": 4,
    "10-19": 3,
    "<10": 2,
    "none": 1,
    "not_graded": 1,
}

EFFORT_TO_LOAD = {
    "DEEP": 3,
    "MEDIUM": 2,
    "MED": 2,
    "LIGHT": 1,
    "SHALLOW": 1,
}


class SleepSchedule(BaseModel):
    daily_start_time: str = Field(default="23:30", description="Nightly sleep start time HH:MM")
    daily_end_time: str = Field(default="06:30", description="Morning wake-up time HH:MM")
    is_hard_lock: bool = Field(default=True, description="Hard constraint H2/H5: never schedule over sleep")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "start" in data and "daily_start_time" not in data:
                data["daily_start_time"] = data["start"]
            if "end" in data and "daily_end_time" not in data:
                data["daily_end_time"] = data["end"]
        return data


class FixedEvent(BaseModel):
    event_id: str = Field(default="EVENT_1")
    title: str = Field(default="Fixed Commitment")
    day_of_week: Union[str, List[str]] = Field(default="Monday")
    start_time: str = Field(default="08:00")
    end_time: str = Field(default="10:00")
    category: str = Field(default="ACADEMIC_CLASS")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "id" in data and "event_id" not in data:
                data["event_id"] = data["id"]
            if "days" in data and "day_of_week" not in data:
                data["day_of_week"] = data["days"]
            if "start" in data and "start_time" not in data:
                data["start_time"] = data["start"]
            if "end" in data and "end_time" not in data:
                data["end_time"] = data["end"]
        return data


class CommitmentsProfile(BaseModel):
    student_id: str = Field(default="STUDENT_SAMPLE_01")
    planning_week_start: str = Field(default="2026-11-02T00:00:00+07:00")
    now: Optional[str] = Field(default=None, description="Explicit current time (ISO-8601 or Day HH:MM)")
    sleep_schedule: SleepSchedule = Field(default_factory=SleepSchedule)
    fixed_events: List[FixedEvent] = Field(default_factory=list)


class Task(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    title: str = Field(default="", description="Human-readable task title")
    duration_min: int = Field(..., gt=0, description="Estimated duration in minutes (raw T_estimate in V0)")
    deadline_day: Optional[str] = Field(default=None, description="Weekday name (e.g. Wednesday, Next Monday) or None")
    deadline_time: Optional[str] = Field(default="23:59", description="Deadline time HH:MM")
    due: Optional[str] = Field(default=None, description="ISO-8601 deadline datetime (Improve Plan §7)")
    priority: int = Field(default=3, ge=1, le=5, description="Task importance priority (1=Lowest .. 5=Highest)")
    grade_weight: Optional[str] = Field(default=None, description="Optional grade weight mapping to priority")
    category: str = Field(default="DEADLINE", description="DEADLINE, HABIT, ASSIGNMENT, EXAM, PROJECT")
    is_splittable: bool = Field(default=False, description="Whether task can be split into chunks")
    min_chunk_min: int = Field(default=45, ge=15, description="Minimum chunk length in minutes")
    max_chunk_min: int = Field(default=90, ge=15, description="Maximum chunk length in minutes")
    depends_on: List[str] = Field(default_factory=list, description="Prerequisite task_ids that must finish first")
    cognitive_load: Optional[int] = Field(default=None, description="Optional 1..3 load (ignored by pure V0 EDF/LST)")

    @model_validator(mode="before")
    @classmethod
    def normalize_task_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        # Map Improve Plan keys -> Baseline keys
        if "id" in out and "task_id" not in out:
            out["task_id"] = str(out["id"])
        if "estimate_min" in out and "duration_min" not in out:
            out["duration_min"] = int(out["estimate_min"])
        if "splittable" in out and "is_splittable" not in out:
            out["is_splittable"] = bool(out["splittable"])
        if "min_part_min" in out and "min_chunk_min" not in out:
            out["min_chunk_min"] = int(out["min_part_min"])
        if "after" in out and "depends_on" not in out:
            out["depends_on"] = list(out["after"] or [])
        if "type" in out and "category" not in out:
            out["category"] = str(out["type"]).upper()

        # Priority inference from grade_weight if priority not explicitly set
        if "priority_override" in out and out["priority_override"] is not None:
            out["priority"] = int(out["priority_override"])
        elif "priority" not in out or out["priority"] is None:
            gw = str(out.get("grade_weight") or "").strip().lower()
            out["priority"] = GRADE_WEIGHT_TO_PRIORITY.get(gw, 3)

        # Effort / cognitive load normalization
        if "effort" in out and "cognitive_load" not in out and out["effort"]:
            out["cognitive_load"] = EFFORT_TO_LOAD.get(str(out["effort"]).upper(), 2)

        # Clean empty deadline_day
        dd = out.get("deadline_day")
        if isinstance(dd, str) and dd.strip().lower() in ("", "none", "null", "empty", "(empty)"):
            out["deadline_day"] = None
            if out.get("category", "DEADLINE") == "DEADLINE":
                out["category"] = "HABIT"

        if not out.get("title"):
            out["title"] = out.get("task_id", "Untitled Task")

        if out.get("min_chunk_min") is None or int(out.get("min_chunk_min", 0) or 0) < 15:
            out["min_chunk_min"] = 45

        return out

    def get_planned_duration_min(self) -> int:
        """
        Baseline V0 Principle §1.1 (Zero Behavioral Psychology):
        Keep raw estimate T_planned = round_up_to_15(T_estimate), NO x1.2 or x1.35 buffer.
        """
        return round_up_to_15(self.duration_min)

    def get_planned_slots(self) -> int:
        return minutes_to_slots(self.get_planned_duration_min())

    def resolve_deadline_slot(self, week_start_iso: str = "2026-11-02T00:00:00+07:00") -> Optional[int]:
        """
        Resolve task deadline into a 0-based slot index.
        Returns None if the task has no deadline (e.g., HABIT / chores).
        Supports both `due` (ISO-8601) and (`deadline_day`, `deadline_time`).
        """
        if self.due:
            return iso_to_slot(self.due, week_start_iso=week_start_iso, is_end_or_deadline=True)
        if self.deadline_day:
            d_time = self.deadline_time if self.deadline_time else "23:59"
            return day_time_to_slot(self.deadline_day, d_time, is_end_or_deadline=True)
        return None

    def format_deadline_label(self, week_start_iso: str = "2026-11-02T00:00:00+07:00") -> str:
        slot = self.resolve_deadline_slot(week_start_iso=week_start_iso)
        if slot is None:
            return "No deadline (Flexible / Habit)"
        if self.deadline_day:
            return f"{self.deadline_day} {self.deadline_time or '23:59'}"
        day_name, time_str = slot_to_day_time(slot, is_end_time=True)
        return f"{day_name} {time_str}"


class TaskChunk(BaseModel):
    """Represents a schedulable unit (either an atomic task or one chunk of a splittable task)."""
    chunk_id: str
    task_id: str
    title: str
    chunk_index: int = 1
    total_chunks: int = 1
    duration_min: int
    duration_slots: int
    deadline_slot: Optional[int] = None
    deadline_str: str = "No deadline"
    priority: int = 3
    depends_on: List[str] = Field(default_factory=list)
    original_order: int = 0
    is_splittable: bool = False
    min_chunk_min: int = 45


class ScheduleBlock(BaseModel):
    block_id: str = Field(default="")
    task_id: str
    title: str
    day: str
    start_time: str
    end_time: str
    start_iso: str = Field(default="")
    end_iso: str = Field(default="")
    start_slot: int
    end_slot: int
    duration_min: int = 0
    priority: int = 3
    deadline_str: str = ""
    deadline_slot: Optional[int] = None
    chunk_index: int = 1
    total_chunks: int = 1
    part: int = 1
    parts: int = 1
    state: str = "ACCEPTED"  # ACCEPTED | PROPOSED | PINNED | DONE
    reason: str = ""
    reasons: List[Dict[str, Any]] = Field(default_factory=list)
    allowed_starts: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def populate_computed_fields(self) -> "ScheduleBlock":
        if not self.block_id:
            self.block_id = f"{self.task_id}_P{self.chunk_index}"
        if self.duration_min <= 0:
            self.duration_min = (self.end_slot - self.start_slot) * MINUTES_PER_SLOT
        self.part = self.chunk_index
        self.parts = self.total_chunks
        return self


class OverloadReport(BaseModel):
    error_type: str = Field(..., description="CAPACITY_SHORTAGE | FRAGMENTATION_FAILURE")
    type: str = Field(default="NOT_ENOUGH_TIME", description="NOT_ENOUGH_TIME | NO_SCHEDULE_FOUND")
    message: str
    deadline: str
    deadline_slot: Optional[int] = None
    total_free_minutes_available: int
    total_planned_work_minutes: int
    shortage_minutes: int
    unplaced_tasks: List[str] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    options: List[Dict[str, Any]] = Field(default_factory=list)


class ScheduleSummary(BaseModel):
    total_tasks_requested: int
    tasks_placed: int
    tasks_unplaced: int
    parts_total: int = 0
    parts_placed: int = 0
    parts_unplaced: int = 0
    hard_constraint_violations: int = 0
    deadline_satisfaction_rate: float = 100.0
    free_slots_remaining: int = 0
    occupied_slots: int = 0
    sleep_slots: int = 0
    block_slots: int = 0
    fragmentation_index: float = 0.0


class ScheduleOutput(BaseModel):
    status: str = Field(..., description="SUCCESS | PARTIAL_OVERLOAD | INFEASIBLE_CAPACITY | NO_SCHEDULE_FOUND")
    solver_used: str
    execution_time_ms: float
    determinism_hash: str = ""
    summary: ScheduleSummary
    blocks: List[ScheduleBlock] = Field(default_factory=list)
    unplaced_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    overload_reports: List[OverloadReport] = Field(default_factory=list)
    overload: Optional[OverloadReport] = None
    warnings: List[str] = Field(default_factory=list)
    grid_states: Optional[List[str]] = None


class DisruptionEvent(BaseModel):
    event_id: str = Field(default="DISRUPTION_1")
    title: str = Field(default="Urgent Interruption")
    day_of_week: str = Field(default="Wednesday")
    start_time: str = Field(default="08:00")
    end_time: str = Field(default="10:00")
    now_day: Optional[str] = Field(default=None)
    now_time: Optional[str] = Field(default=None)
    now_iso: Optional[str] = Field(default=None)


class RepairChange(BaseModel):
    block_id: str
    task_id: str
    title: str
    old_day: str
    old_start_time: str
    old_end_time: str
    old_start_slot: int
    old_end_slot: int
    new_day: Optional[str] = None
    new_start_time: Optional[str] = None
    new_end_time: Optional[str] = None
    new_start_slot: Optional[int] = None
    new_end_slot: Optional[int] = None
    status: str = "MOVED"  # MOVED | UNPLACED | UNCHANGED


class RepairOutput(BaseModel):
    status: str
    repair_mode: str  # LOCAL_INSERTION | FULL_REBUILD | RIPPLE_SHIFT
    execution_time_ms: float
    stability_score: float
    total_unaffected_blocks: int
    unchanged_unaffected_blocks: int
    directly_hit_blocks: int
    moved_blocks_count: int
    unplaced_blocks_count: int
    changes: List[RepairChange] = Field(default_factory=list)
    schedule: ScheduleOutput

