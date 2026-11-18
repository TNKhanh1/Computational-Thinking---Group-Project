"""
Read-only adapter bridging `Testing_System` to the untouched `group03-smartschedule-baseline` project.

Supports:
  1. Preprocessing helpers (`expand_personal_habits`, `apply_estimate_buffer`) & grid reconstruction.
  2. Direct Domain Controller execution across all 5 solvers + Local/Ripple/FullRebuild/Overrun repairs.
  3. HTTP API End-to-End execution via FastAPI TestClient using an isolated SQLite DB path so production state is untouched.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

_WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
_BASELINE_ROOT = _WORKSPACE_ROOT / "group03-smartschedule-baseline"

if str(_BASELINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_BASELINE_ROOT))

# Ensure SQLite writes from API calls never mutate baseline data/local_state.db
_ISOLATED_DB_PATH = str(Path(tempfile.gettempdir()) / "smartschedule_testing_isolated.db")
os.environ.setdefault("SMARTSCHEDULE_DB_PATH", _ISOLATED_DB_PATH)

from src.controller import ScheduleController  # noqa: E402
from src.grid_manager import TimeGridManager  # noqa: E402
from src.metrics import (  # noqa: E402
    audit_hard_constraint_violations,
    calculate_fragmentation_index,
    calculate_schedule_stability,
)
from src.models import (  # noqa: E402
    CircadianEnergyProfile,
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    PersonalHabit,
    RepairOutput,
    ScheduleBlock,
    ScheduleOutput,
    ScheduleSummary,
    SleepSchedule,
    Task,
)
from src.solvers.base_solver import BaseScheduler  # noqa: E402
from src.solvers.local_repair import LocalRepairEngine  # noqa: E402
from src.utils import (  # noqa: E402
    MINUTES_PER_SLOT,
    SLOTS_PER_DAY,
    SLOTS_PER_WEEK,
    day_time_to_slot,
    parse_day_to_index,
    parse_time_to_slot_offset,
    round_up_to_15,
    slot_to_day_time,
)

FIVE_SOLVERS: Tuple[str, ...] = ("EDF", "LST", "WSPT", "SCORED_GREEDY", "BACKTRACK")


def preprocess_tasks(profile: CommitmentsProfile, tasks: List[Task]) -> List[Task]:
    """
    Replicate the exact SmartSchedule task preprocessing pipeline:
      expand_personal_habits(profile, tasks) -> apply_estimate_buffer(profile, expanded)
    Must run before reading `get_planned_duration_min()`.
    """
    profile_copy = profile.model_copy(deep=True)
    raw_copies = [t.model_copy(deep=True) for t in tasks]
    expanded = ScheduleController.expand_personal_habits(profile_copy, raw_copies)
    return ScheduleController.apply_estimate_buffer(profile_copy, expanded)


def resolve_horizon_slots_safe(
    profile: CommitmentsProfile,
    buffered_tasks: List[Task],
    blocks: Optional[List[ScheduleBlock]] = None,
) -> int:
    """Resolve effective grid horizon (672..1344+) without 672-slot truncation."""
    h = BaseScheduler.resolve_horizon_slots(
        buffered_tasks,
        week_start_iso=profile.planning_week_start,
        horizon_days=getattr(profile, "horizon_days", 7),
    )
    if blocks:
        max_end = max((b.end_slot for b in blocks), default=0)
        if max_end > h:
            h = max_end
    return h


def build_base_grid(
    profile: CommitmentsProfile,
    horizon_slots: int,
) -> TimeGridManager:
    """Create a fresh TimeGridManager initialized strictly from profile locks."""
    grid = TimeGridManager(total_slots=horizon_slots)
    grid.initialize_from_profile(profile.model_copy(deep=True))
    return grid


def run_solver_direct(
    profile: CommitmentsProfile,
    tasks: List[Task],
    algorithm: str,
    pinned_blocks: Optional[List[ScheduleBlock]] = None,
) -> Tuple[ScheduleOutput, TimeGridManager]:
    """Run baseline ScheduleController.solve_schedule on defensive deep copies."""
    prof_copy = profile.model_copy(deep=True)
    task_copies = [t.model_copy(deep=True) for t in tasks]
    pin_copies = [b.model_copy(deep=True) for b in pinned_blocks] if pinned_blocks else None
    return ScheduleController.solve_schedule(
        profile=prof_copy,
        tasks=task_copies,
        algorithm=algorithm,
        pinned_blocks=pin_copies,
    )


def run_repair_direct(
    profile: CommitmentsProfile,
    tasks: List[Task],
    baseline_schedule: ScheduleOutput,
    disruption: DisruptionEvent,
    mode: str,
    algorithm: str = "SCORED_GREEDY",
) -> RepairOutput:
    """Run LocalRepairEngine.repair_disruption cleanly with expanded + buffered tasks."""
    prof_copy = profile.model_copy(deep=True)
    prepared_tasks = preprocess_tasks(prof_copy, tasks)
    sched_copy = baseline_schedule.model_copy(deep=True)
    disr_copy = disruption.model_copy(deep=True)
    return LocalRepairEngine.repair_disruption(
        profile=prof_copy,
        tasks=prepared_tasks,
        current_schedule=sched_copy,
        disruption=disr_copy,
        mode=mode,
        algorithm=algorithm,
    )


def run_overrun_direct(
    profile: CommitmentsProfile,
    tasks: List[Task],
    baseline_schedule: ScheduleOutput,
    target_task_id: str,
    overrun_pct: float = 50.0,
) -> RepairOutput:
    """
    Simulate an actual task overrun on the baseline schedule using LocalRepairEngine.repair_overrun
    (preserves PINNED blocks cleanly and avoids modifying baseline controller).
    """
    prof_copy = profile.model_copy(deep=True)
    prepared_tasks = preprocess_tasks(prof_copy, tasks)
    updated_raw: List[Task] = []
    for t in prepared_tasks:
        tc = t.model_copy(deep=True)
        if tc.task_id == target_task_id:
            tc.duration_min = round_up_to_15(int(round(tc.duration_min * (1.0 + overrun_pct / 100.0))))
        updated_raw.append(tc)
    updated_buffered = ScheduleController.apply_estimate_buffer(prof_copy, updated_raw)
    sched_copy = baseline_schedule.model_copy(deep=True)
    return LocalRepairEngine.repair_overrun(
        profile=prof_copy,
        updated_tasks=updated_buffered,
        current_schedule=sched_copy,
        target_task_id=target_task_id,
    )


def build_api_payload(
    profile: CommitmentsProfile,
    tasks: List[Task],
    algorithm: str,
    pinned_blocks: Optional[List[ScheduleBlock]] = None,
) -> Dict[str, Any]:
    """Serialize inputs to exact Baseline JSON contract expected by FastAPI endpoints."""
    payload: Dict[str, Any] = {
        "commitments": profile.model_dump(mode="json"),
        "tasks": [t.model_dump(mode="json") for t in tasks],
        "algorithm": algorithm,
    }
    if pinned_blocks:
        payload["pinned_blocks"] = [b.model_dump(mode="json") for b in pinned_blocks]
    return payload


class _InProcessResponse:
    """Minimal HTTP-like response wrapper carrying real FastAPI handler JSON output."""

    def __init__(self, status_code: int, body_obj: Any):
        self.status_code = status_code
        self._body_obj = body_obj
        import json as _json

        self.text = _json.dumps(body_obj, ensure_ascii=False)

    def json(self) -> Any:
        return self._body_obj


class InProcessFastAPIClient:
    """
    Synchronous in-process dispatcher calling `web.api` FastAPI route handlers with full JSON
    round-trip serialization and isolated SQLite DB, avoiding asyncio/socketpair calls blocked
    in restricted Windows sandboxes while still preserving `TestClient` API parity.
    """

    def post(self, path: str, json: Dict[str, Any]) -> _InProcessResponse:
        import json as _json
        from fastapi import HTTPException  # noqa: E402
        from fastapi.responses import JSONResponse  # noqa: E402
        from web import api as web_api  # noqa: E402

        payload = _json.loads(_json.dumps(json))
        routes = {
            "/api/plan": web_api.api_solve_schedule,
            "/api/solve": web_api.api_solve_schedule,
            "/api/repair": web_api.api_repair_schedule,
            "/api/progress": web_api.api_task_overrun,
            "/api/overrun": web_api.api_task_overrun,
            "/api/tasks/complete": web_api.api_task_complete,
        }
        handler = routes.get(path)
        if handler is None:
            return _InProcessResponse(404, {"detail": f"Unsupported POST route: {path}"})
        try:
            res = handler(payload)
            if isinstance(res, JSONResponse):
                return _InProcessResponse(res.status_code, _json.loads(res.body.decode("utf-8")))
            return _InProcessResponse(200, _json.loads(_json.dumps(res, default=str)))
        except HTTPException as exc:
            return _InProcessResponse(exc.status_code, {"detail": exc.detail})

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> _InProcessResponse:
        import json as _json
        from fastapi import HTTPException  # noqa: E402
        from web import api as web_api  # noqa: E402

        q = params or {}
        try:
            if path == "/api/tasks/completions":
                res = web_api.api_list_completions(
                    workspace_id=str(q.get("workspace_id") or "default"),
                    limit=int(q.get("limit") or 200),
                )
                return _InProcessResponse(200, _json.loads(_json.dumps(res, default=str)))
            return _InProcessResponse(404, {"detail": f"Unsupported GET route: {path}"})
        except HTTPException as exc:
            return _InProcessResponse(exc.status_code, {"detail": exc.detail})


def create_isolated_http_client(db_path: Optional[str] = None, transport: str = "in_process"):
    """
    Create an API client pointing storage to an isolated SQLite DB.
      - transport='in_process' (default): zero-socket dispatcher calling `web.api` handlers synchronously (works in sandbox).
      - transport='testclient': full Starlette `TestClient(app)` (for standard non-sandboxed shells).
    """
    if db_path:
        os.environ["SMARTSCHEDULE_DB_PATH"] = str(db_path)
    else:
        os.environ["SMARTSCHEDULE_DB_PATH"] = _ISOLATED_DB_PATH
    if transport == "testclient":
        from fastapi.testclient import TestClient  # noqa: E402
        from web.api import app  # noqa: E402

        return TestClient(app)
    return InProcessFastAPIClient()


__all__ = [
    "CircadianEnergyProfile",
    "CommitmentsProfile",
    "DisruptionEvent",
    "FIVE_SOLVERS",
    "FixedEvent",
    "LocalRepairEngine",
    "MINUTES_PER_SLOT",
    "PersonalHabit",
    "RepairOutput",
    "SLOTS_PER_DAY",
    "SLOTS_PER_WEEK",
    "ScheduleBlock",
    "ScheduleController",
    "ScheduleOutput",
    "ScheduleSummary",
    "SleepSchedule",
    "Task",
    "TimeGridManager",
    "audit_hard_constraint_violations",
    "build_api_payload",
    "build_base_grid",
    "calculate_fragmentation_index",
    "calculate_schedule_stability",
    "create_isolated_http_client",
    "day_time_to_slot",
    "parse_day_to_index",
    "parse_time_to_slot_offset",
    "preprocess_tasks",
    "resolve_horizon_slots_safe",
    "round_up_to_15",
    "run_overrun_direct",
    "run_repair_direct",
    "run_solver_direct",
    "slot_to_day_time",
]
