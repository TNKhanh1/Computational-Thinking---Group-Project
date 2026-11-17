"""
schema.py
Canonical Pydantic Data Models for the SmartSchedule Natural Language Parser Subsystem.
Strictly formalizes task contracts, user-declared subtasks (with per-subtask workflow states,
priorities, pacing, lags, and DAG dependencies), diagnostic codes (E_*/W_*), breakdown triggers,
and document attachments (<=20MB).
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator, field_validator


MAX_ATTACHMENT_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB cap


class ContractStatus(str, Enum):
    """Overall validation and readiness state of the compiled task contract."""
    OK = "OK"                              # Clean contract, no errors or warnings
    OK_WITH_WARNINGS = "OK_WITH_WARNINGS"  # Schedulable contract with non-fatal warnings/defaults
    NEEDS_FIX = "NEEDS_FIX"                # Contains >= 1 blocking error (contradiction, invalid file, etc.)
    REJECTED = "REJECTED"                  # Trolling, gibberish, or adversarial input


class SubtaskWorkflowStatus(str, Enum):
    """Workflow state for an individual user-declared subtask."""
    TODO = "TODO"                # Not started; full duration counts toward remaining work
    IN_PROGRESS = "IN_PROGRESS"  # Partially completed; only remaining minutes count
    DONE = "DONE"                # Completed; contributes 0 minutes to remaining work
    WAITING = "WAITING"          # Blocked on external actor or event


class PriorityLevel(IntEnum):
    """Priority level conforming to SmartSchedule EDF and heuristic weightings (1 is highest)."""
    URGENT = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class ConstraintType(str, Enum):
    """Constraint classification: HARD (fixed slots) vs SOFT (flexible schedulable)."""
    HARD = "HARD"      # Immovable: lectures, fixed meetings, exams
    SOFT = "SOFT"      # Flexible: self-study, homework, project work


class CognitiveDemand(str, Enum):
    """Cognitive demand matching chronotype / energy peak curves."""
    DEEP_WORK = "DEEP_WORK"        # High focus: programming, math, discrete structures, writing
    SHALLOW_WORK = "SHALLOW_WORK"  # Routine tasks: email, filing, light reading
    RECOVERY = "RECOVERY"          # Rest, exercise, reflection


class WorkRhythm(str, Enum):
    """
    Humane user work pacing profile determining session chunking and buffer intervals.
    """
    LIGHT = "LIGHT"        # Steady & Light: 25m Pomodoro, frequent breaks, lower fatigue
    BALANCED = "BALANCED"  # Balanced Focus: 45m standard sessions, 15m breaks
    FLOW = "FLOW"          # Deep Flow: 90m uninterrupted focus marathon
    CUSTOM = "CUSTOM"      # User-defined custom min and max session intervals


# Backwards-compatibility alias
ComfortZone = WorkRhythm


class AttachmentMetadata(BaseModel):
    """Metadata and URI link of a relevant reference document attached to a task (max 20MB)."""
    attachment_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    filename: str = Field(..., max_length=255)
    file_path_or_uri: str = Field(default="", description="Absolute path or URI to the document")
    file_type: str = Field(..., description="Extension: txt, pdf, html, md")
    size_bytes: int = Field(default=0, ge=0, description="Size in bytes, must be <= 20MB")
    is_mandatory_reading: bool = Field(default=True, description="True if downstream solver/partitioner must read this")
    document_role: str = Field(default="EXERCISE_SOURCE", description="EXERCISE_SOURCE | RUBRIC | REFERENCE")
    summary_excerpt: str = Field(default="", max_length=1000, description="Extracted text snippet")

    @field_validator("size_bytes")
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        if v > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError(f"Attachment exceeds 20MB limit: {v / (1024*1024):.2f} MB")
        return v


class PrecedenceRelation(BaseModel):
    """Represents a Directed Acyclic Graph (DAG) ordering constraint between work portions."""
    predecessor_id: str = Field(..., description="Description or ID of portion that must finish first")
    successor_id: str = Field(..., description="Description or ID of portion that can only start after predecessor")
    relation_type: str = Field(default="FINISH_TO_START", description="FINISH_TO_START | STRICT_BEFORE")
    description: str = Field(default="", description="Human explanation of ordering")


class DeclaredSubtask(BaseModel):
    """
    User-declared subtask extracted from bullet lists, numbered steps, or sequential clauses.
    The NLP Parser formalizes user-declared subtasks only and never invents arbitrary ones.
    """
    id: str = Field(..., description="Canonical subtask identifier: s1, s2, ...")
    title: str = Field(..., min_length=1, max_length=250, description="Cleaned subtask action title")
    status: SubtaskWorkflowStatus = Field(default=SubtaskWorkflowStatus.TODO, description="TODO | IN_PROGRESS | DONE | WAITING")
    minutes: Optional[int] = Field(default=None, ge=0, description="Remaining active work minutes (0 if DONE/external, None if unknown)")
    priority: Optional[int] = Field(default=3, ge=1, le=4, description="Subtask-specific priority (1..4)")
    pacing: Optional[WorkRhythm] = Field(default=None, description="Subtask-specific pacing override (if specified)")
    deadline: Optional[datetime] = Field(default=None, description="Subtask-specific due date if stated")
    lag_after_minutes: int = Field(default=0, ge=0, description="Passive waiting time after this step (e.g. drying, machine cycle)")
    external: bool = Field(default=False, description="True if performed by an external person/service (0 user work minutes)")
    inferred_dependency: bool = Field(default=False, description="True if dependency was inferred from strict causal necessity")
    depends_on: List[str] = Field(default_factory=list, description="IDs of predecessor subtasks in the DAG")


class SplittingConfig(BaseModel):
    """User choices and boundaries for splitting tasks into multi-session chunks."""
    min_chunk_minutes: int = Field(default=15, ge=5, le=180, description="Minimum allowable session length")
    max_chunk_minutes: int = Field(default=90, ge=5, le=240, description="Maximum allowable session length")
    preferred_chunk_minutes: int = Field(default=45, ge=5, le=180, description="Target chunk size for splits")
    custom_min_time: Optional[int] = Field(default=None, description="User-specified minimum session length")
    custom_max_time: Optional[int] = Field(default=None, description="User-specified maximum session length")

    @model_validator(mode="after")
    def validate_chunk_bounds(self) -> SplittingConfig:
        if self.custom_min_time is not None:
            self.min_chunk_minutes = max(5, self.custom_min_time)
        if self.custom_max_time is not None:
            self.max_chunk_minutes = max(self.min_chunk_minutes, self.custom_max_time)
        if self.min_chunk_minutes > self.max_chunk_minutes:
            self.min_chunk_minutes = self.max_chunk_minutes
        if not (self.min_chunk_minutes <= self.preferred_chunk_minutes <= self.max_chunk_minutes):
            self.preferred_chunk_minutes = self.min_chunk_minutes
        return self


class TaskSchema(BaseModel):
    """
    Canonical data model compiled by the Natural Language Parser.
    Summarizes formalized requirements, user-declared subtasks, diagnostic codes,
    and breakdown recommendations for the Scheduling Engine Solver and Task Partitioner.
    """
    task_id: str = Field(default_factory=lambda: f"TASK-{str(uuid.uuid4())[:8].upper()}")
    status: ContractStatus = Field(default=ContractStatus.OK, description="OK | OK_WITH_WARNINGS | NEEDS_FIX | REJECTED")
    title: str = Field(..., min_length=1, max_length=250, description="Cleaned title of the task")
    raw_prompt: str = Field(default="", max_length=2200, description="Original human prompt (max 2000 chars)")

    # Workload fields
    duration_minutes: int = Field(..., ge=5, description="Effective scheduling duration in minutes")
    total_work_minutes: Optional[int] = Field(default=None, description="Remaining active work minutes (None if unstated)")
    work_minutes_lower_bound: Optional[int] = Field(default=None, description="Known subtask sum when some subtasks lack durations")
    total_range: Optional[List[int]] = Field(default=None, description="[low, high] duration range when hedged or ranged")
    total_sections_count: Optional[int] = Field(default=None, description="Number of chapters/sections detected")
    section_duration_minutes: Optional[int] = Field(default=None, description="Duration per section if specified")

    # Temporal horizon & recurrence
    deadline: Optional[datetime] = Field(default=None, description="Due date and time constraint")
    start_after: Optional[datetime] = Field(default=None, description="Earliest allowable start time")
    repeat: Optional[Dict[str, Any]] = Field(default=None, description="Recurrence rule if repeating habit/routine")

    # Priority & Cognitive Pacing
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="Task urgency and importance")
    priority_rating: Optional[int] = Field(default=3, description="1 to 4 user rating (or None if uncertain)")
    is_uncertain_priority: bool = Field(default=False, description="True if user chose 'I'm Not Sure'")
    constraint_type: ConstraintType = Field(default=ConstraintType.SOFT, description="Hard vs Soft scheduling constraint")
    cognitive_demand: CognitiveDemand = Field(default=CognitiveDemand.DEEP_WORK)
    work_rhythm: WorkRhythm = Field(default=WorkRhythm.BALANCED)
    comfort_zone: WorkRhythm = Field(default=WorkRhythm.BALANCED)
    tags: List[str] = Field(default_factory=list, description="Extracted category/domain tags")

    # Splittability: If False, splitting MUST be null
    is_task_splittable: bool = Field(default=False, description="Whether the task can be split into multiple sessions")
    splitting: Optional[SplittingConfig] = Field(default=None, description="Splitting boundaries (null if atomic single session)")
    conflict_resolution_notice: Optional[str] = Field(default=None, description="Notice if prompt boundary overrode UI setting")

    # User-declared subtasks, DAG precedence, topology & complexity overload
    subtasks: List[DeclaredSubtask] = Field(default_factory=list, description="User-declared subtasks with individual states/priorities")
    precedence_constraints: List[PrecedenceRelation] = Field(default_factory=list, description="DAG order constraints")
    subtask_network: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Formal dependency network graph G = (V, E) of subtask vertices and directed precedence edges, delegated to Engine Solver."
    )
    topological_execution_order: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Topological execution sequence computed from subtask DAG dependencies (Kahn's algorithm)"
    )
    breakdown_required: bool = Field(default=False, description="True if task exceeds complexity thresholds and needs decomposition")

    # Document linking & Diagnostics
    requires_document_analysis: bool = Field(default=False, description="Flag telling solver/partitioner to read docs")
    attachments: List[AttachmentMetadata] = Field(default_factory=list, description="Associated reference files")
    solver_delegated_fields: List[str] = Field(
        default_factory=list,
        description="Optional parameters omitted from prompt and delegated to the downstream Engine Solver"
    )
    errors: List[str] = Field(default_factory=list, description="Diagnostic error codes (E_*)")
    warnings: List[str] = Field(default_factory=list, description="Diagnostic warning codes (W_*)")
    suggestions: List[str] = Field(default_factory=list, description="Actionable user guidance & breakdown solutions")

    @model_validator(mode="after")
    def enforce_single_session_null_splitting(self) -> TaskSchema:
        """Enforces that if is_task_splittable is False, splitting is strictly null."""
        if not self.is_task_splittable:
            self.splitting = None
        return self

    def to_context_chunk(self) -> str:
        """Compact string representation for downstream LLM context window injection."""
        dl_str = self.deadline.strftime("%Y-%m-%d %H:%M") if self.deadline else "Flexible"
        sa_str = f" | StartAfter:{self.start_after.strftime('%Y-%m-%d %H:%M')}" if self.start_after else ""
        split_str = f"Split({self.splitting.preferred_chunk_minutes}m)" if (self.is_task_splittable and self.splitting) else "Atomic(SingleSession)"
        doc_str = f" | Docs({len(self.attachments)}, RequiresAnalysis={self.requires_document_analysis})" if self.attachments else ""
        pri_str = "Auto/Uncertain" if self.is_uncertain_priority else f"P{self.priority.value}"
        order_str = f" | Precedence({len(self.precedence_constraints)})" if self.precedence_constraints else ""
        sub_str = f" | Subtasks({len(self.subtasks)})" if self.subtasks else ""
        sec_str = f" | {self.total_sections_count} sections" if self.total_sections_count else ""
        return (
            f"[{self.task_id}][{self.status.value}] '{self.title}' | {self.duration_minutes}m{sec_str} | "
            f"Due: {dl_str}{sa_str} | Pri:{pri_str} | {self.constraint_type.value} | {split_str}{sub_str}{doc_str}{order_str}"
        )
