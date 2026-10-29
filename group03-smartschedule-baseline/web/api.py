"""
FastAPI REST Backend for SmartSchedule Baseline (V0) Workbench.
Implements all endpoints specified in baseline_plan.md §8 and improve_plan.md §7.2:
  - GET  /                         -> Serves Baseline Technical Workbench UI (index.html)
  - GET  /app.js                   -> Serves Frontend JS controller (app.js)
  - GET  /api/presets              -> Returns Minh's Week & Lan's Week presets
  - GET  /api/scenarios            -> Lists scenarios T01–T10
  - GET  /api/scenarios/{id}       -> Returns specific scenario T01–T10
  - POST /api/plan (or /api/solve) -> Solves weekly schedule (EDF, LST, WSPT, Backtracking)
  - POST /api/compare              -> Runs Dual-Algorithm Side-by-Side Comparison
  - POST /api/repair               -> Runs Disruption Rescheduling (Local Repair vs Full Rebuild vs Ripple-Shift)
  - POST /api/progress             -> Simulates Task Duration Overrun (T05 / UC9)
  - POST /api/validate-move        -> Validates manual drag/move against Hard Constraints H1–H5
  - POST /api/determinism-check    -> Runs 3x Determinism Verification (SHA-256 hash comparison)
  - POST /api/export/{fmt}         -> Exports schedule as .ics, .csv, or .json
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from src.controller import ScheduleController
from src.exporter import export_to_csv, export_to_ics, export_to_json
from src.models import (
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    ScheduleBlock,
    ScheduleOutput,
    SleepSchedule,
    Task,
)
from src.solvers.local_repair import LocalRepairEngine

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCENARIOS_DIR = DATA_DIR / "test_scenarios"
WEB_DIR = BASE_DIR / "web"

app = FastAPI(
    title="SmartSchedule Baseline (V0) — Technical Benchmark Workbench API",
    description="Deterministic 672-Slot Scheduling Engine & Benchmark API (CSC10014 - Group 03)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_profile_and_tasks(payload: Dict[str, Any]) -> Tuple[CommitmentsProfile, List[Task], str, List[ScheduleBlock]]:
    """
    Parse request payload supporting BOTH:
      1. Baseline Schema: { "commitments": {...}, "tasks": [...], "algorithm": "EDF" }
      2. Improve Plan Contract (§7.3): { "now": ..., "week_start": ..., "profile": {...}, "fixed_events": [...], "tasks": [...] }
    """
    algorithm = str(payload.get("algorithm") or payload.get("solver") or "GREEDY_EDF_FIRST_FIT")

    if "commitments" in payload and isinstance(payload["commitments"], dict):
        comm_dict = dict(payload["commitments"])
        if "now" in payload and payload["now"] and not comm_dict.get("now"):
            comm_dict["now"] = payload["now"]
        if "week_start" in payload and payload["week_start"] and not comm_dict.get("planning_week_start"):
            comm_dict["planning_week_start"] = payload["week_start"]
        profile = CommitmentsProfile.model_validate(comm_dict)
    else:
        # Improve Plan §7.3 contract format
        prof_part = payload.get("profile") or {}
        sleep_part = prof_part.get("sleep") or payload.get("sleep_schedule") or {"daily_start_time": "23:30", "daily_end_time": "06:30"}
        fixed_list = payload.get("fixed_events") or prof_part.get("fixed_events") or []
        profile = CommitmentsProfile(
            student_id=str(payload.get("student_id") or prof_part.get("student_id") or "STUDENT_01"),
            planning_week_start=str(payload.get("week_start") or payload.get("planning_week_start") or "2026-11-02T00:00:00+07:00"),
            now=payload.get("now"),
            sleep_schedule=SleepSchedule.model_validate(sleep_part),
            fixed_events=[FixedEvent.model_validate(fe) for fe in fixed_list],
        )

    raw_tasks = payload.get("tasks") or []
    tasks = [Task.model_validate(t) for t in raw_tasks]

    raw_pinned = payload.get("pinned_blocks") or []
    pinned_blocks = [ScheduleBlock.model_validate(pb) for pb in raw_pinned]

    return profile, tasks, algorithm, pinned_blocks


def _enrich_response(out: ScheduleOutput) -> Dict[str, Any]:
    """Attach Improve Plan §7.3 alias fields alongside Baseline §6.2 fields."""
    data = out.model_dump()
    data["unplaced"] = data["unplaced_tasks"]
    data["metrics"] = {
        "hard_violations": out.summary.hard_constraint_violations,
        "deadline_rate": round(out.summary.deadline_satisfaction_rate / 100.0, 4),
        "deadline_satisfaction_pct": out.summary.deadline_satisfaction_rate,
        "exec_ms": out.execution_time_ms,
        "free_slots": out.summary.free_slots_remaining,
        "fragmentation_index": out.summary.fragmentation_index,
    }
    return data


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/app.js", include_in_schema=False)
def serve_app_js():
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript")


@app.get("/api/presets")
def get_presets():
    """Return built-in presets (Minh's Week, Lan's Busy Week, and Empty Blank Week)."""
    minh_comm = json.loads((DATA_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    minh_tasks = json.loads((DATA_DIR / "sample_week_tasks.json").read_text(encoding="utf-8"))
    lan_comm = json.loads((DATA_DIR / "lan_week_commitments.json").read_text(encoding="utf-8"))
    lan_tasks = json.loads((DATA_DIR / "lan_week_tasks.json").read_text(encoding="utf-8"))
    empty_comm = {
        "student_id": "EMPTY_SCHEDULE",
        "planning_week_start": "2026-11-02T00:00:00+07:00",
        "sleep_schedule": {
            "daily_start_time": "23:30",
            "daily_end_time": "06:30",
            "is_hard_lock": True,
        },
        "fixed_events": [],
    }

    return {
        "presets": {
            "minh": {
                "id": "minh",
                "name": "Tuần của Minh (9 tasks chuẩn trong Báo cáo §2.8 & §6.7)",
                "commitments": minh_comm,
                "tasks": minh_tasks,
            },
            "lan": {
                "id": "lan",
                "name": "Tuần bận rộn của Lan (Học + Lab + Đi làm thêm + CLB + Deadline tuần sau)",
                "commitments": lan_comm,
                "tasks": lan_tasks,
            },
            "empty": {
                "id": "empty",
                "name": "Lịch Trống Hoàn Toàn (0 Sự kiện cố định, 0 Task — Tự nhập từ đầu)",
                "commitments": empty_comm,
                "tasks": [],
            },
        }
    }


@app.get("/api/scenarios")
def list_scenarios():
    """List all 10 benchmark scenarios (T01 - T10)."""
    items = []
    if SCENARIOS_DIR.exists():
        for path in sorted(SCENARIOS_DIR.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            items.append({
                "scenario_id": raw.get("scenario_id", path.stem.upper()),
                "file": path.name,
                "name": raw.get("name", path.stem),
                "description": raw.get("description", ""),
                "expected_status": raw.get("expected_status", "SUCCESS"),
                "task_count": len(raw.get("tasks", [])),
                "has_disruption": "disruption" in raw,
                "has_overrun": "overrun_config" in raw,
            })
    return {"scenarios": items}


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    """Load a specific benchmark scenario by ID (e.g., T01, t01, t01_normal_feasible)."""
    key = scenario_id.strip().lower()
    if SCENARIOS_DIR.exists():
        for path in sorted(SCENARIOS_DIR.glob("*.json")):
            raw = json.loads(path.read_text(encoding="utf-8"))
            sid = str(raw.get("scenario_id", "")).strip().lower()
            if key in (sid, path.stem.lower(), path.name.lower()):
                return raw
    raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")


@app.post("/api/plan")
@app.post("/api/solve")
def api_solve_schedule(payload: Dict[str, Any] = Body(...)):
    """Run the selected Baseline scheduling algorithm on the 672-slot grid."""
    try:
        profile, tasks, algorithm, pinned_blocks = _extract_profile_and_tasks(payload)
        out, _ = ScheduleController.solve_schedule(
            profile=profile,
            tasks=tasks,
            algorithm=algorithm,
            pinned_blocks=pinned_blocks,
        )
        return JSONResponse(content=_enrich_response(out))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/compare")
def api_compare_algorithms(payload: Dict[str, Any] = Body(...)):
    """Run two algorithms side-by-side for Dual-Algorithm Comparative View (baseline_plan.md §7.4 Option 3)."""
    try:
        profile, tasks, _, _ = _extract_profile_and_tasks(payload)
        algo_left = str(payload.get("algo_left") or "GREEDY_EDF_FIRST_FIT")
        algo_right = str(payload.get("algo_right") or "GREEDY_LST_BEST_FIT")
        res = ScheduleController.compare_algorithms(
            profile=profile,
            tasks=tasks,
            algo_left=algo_left,
            algo_right=algo_right,
        )
        return {
            "left": _enrich_response(res["left"]),
            "right": _enrich_response(res["right"]),
            "comparison": res["comparison"],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/repair")
def api_repair_schedule(payload: Dict[str, Any] = Body(...)):
    """
    Run Disruption Rescheduling (Scenario T04).
    Supports mode: 'LOCAL_INSERTION' | 'FULL_REBUILD' | 'RIPPLE_SHIFT' | 'COMPARE_BOTH'.
    """
    try:
        profile, tasks, algorithm, pinned_blocks = _extract_profile_and_tasks(payload)
        if "schedule" in payload and isinstance(payload["schedule"], dict):
            current_schedule = ScheduleOutput.model_validate(payload["schedule"])
        else:
            current_schedule, _ = ScheduleController.solve_schedule(
                profile=profile, tasks=tasks, algorithm=algorithm, pinned_blocks=pinned_blocks
            )

        disruption_raw = payload.get("new_event") or payload.get("disruption") or {
            "event_id": "URGENT_EVENT",
            "title": "Sự kiện đột xuất khẩn cấp",
            "day_of_week": "Monday",
            "start_time": "07:30",
            "end_time": "09:30",
        }
        disruption = DisruptionEvent.model_validate(disruption_raw)
        mode = str(payload.get("mode") or "LOCAL_INSERTION").upper()

        if mode in ("COMPARE_BOTH", "COMPARE"):
            comp = ScheduleController.compare_repair_modes(
                profile=profile,
                tasks=tasks,
                current_schedule=current_schedule,
                disruption=disruption,
            )
            return {
                "original_schedule": _enrich_response(current_schedule),
                "local_repair": comp["local_repair"].model_dump(),
                "full_rebuild": comp["full_rebuild"].model_dump(),
                "comparison": comp["comparison"],
            }

        rep_out = LocalRepairEngine.repair_disruption(
            profile=profile,
            tasks=tasks,
            current_schedule=current_schedule,
            disruption=disruption,
            mode=mode,
        )
        return rep_out.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/progress")
@app.post("/api/overrun")
def api_task_overrun(payload: Dict[str, Any] = Body(...)):
    """Simulate Task Duration Overrun (Scenario T05 / Use Case UC9)."""
    try:
        profile, tasks, algorithm, _ = _extract_profile_and_tasks(payload)
        task_id = str(payload.get("task_id") or payload.get("block_id") or (tasks[0].task_id if tasks else ""))
        extra_min = int(payload.get("extra_min") or payload.get("extra_minutes") or 0)
        overrun_pct = float(payload.get("overrun_pct") or 30.0)

        res = ScheduleController.handle_task_overrun(
            profile=profile,
            tasks=tasks,
            task_id=task_id,
            extra_minutes=extra_min,
            overrun_pct=overrun_pct,
            algorithm=algorithm,
        )
        return {
            "task_id": res["task_id"],
            "old_duration_min": res["old_duration_min"],
            "new_duration_min": res["new_duration_min"],
            "shifted_blocks_count": res["shifted_blocks_count"],
            "before_schedule": _enrich_response(res["before_schedule"]),
            "after_schedule": _enrich_response(res["after_schedule"]),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/validate-move")
def api_validate_move(payload: Dict[str, Any] = Body(...)):
    """Check whether moving a scheduled block to a new time satisfies Hard Constraints H1-H5."""
    try:
        profile, tasks, algorithm, _ = _extract_profile_and_tasks(payload)
        raw_blocks = payload.get("blocks")
        if raw_blocks is None and "schedule" in payload and isinstance(payload["schedule"], dict):
            raw_blocks = payload["schedule"].get("blocks", [])
        if raw_blocks is None:
            sched, _ = ScheduleController.solve_schedule(profile, tasks, algorithm=algorithm)
            current_blocks = sched.blocks
        else:
            current_blocks = [ScheduleBlock.model_validate(b) for b in raw_blocks]

        block_id = str(payload.get("block_id", ""))
        new_start_slot = payload.get("new_start_slot")
        new_start_iso = payload.get("new_start")
        new_day = payload.get("new_day")
        new_time = payload.get("new_time")

        return ScheduleController.validate_manual_move(
            profile=profile,
            tasks=tasks,
            current_blocks=current_blocks,
            block_id=block_id,
            new_start_slot=int(new_start_slot) if new_start_slot is not None else None,
            new_start_iso=new_start_iso,
            new_day=new_day,
            new_time=new_time,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/determinism-check")
def api_determinism_check(payload: Dict[str, Any] = Body(...)):
    """Run the solver 3 times on the same input and compare SHA-256 output hashes."""
    try:
        profile, tasks, algorithm, _ = _extract_profile_and_tasks(payload)
        runs = int(payload.get("runs") or 3)
        res = ScheduleController.verify_determinism(
            profile=profile, tasks=tasks, algorithm=algorithm, runs=runs
        )
        return {
            "is_deterministic": res["is_deterministic"],
            "runs": res["runs"],
            "hashes": res["hashes"],
            "unique_hash": res["unique_hash"],
            "latencies_ms": res["latencies_ms"],
            "avg_latency_ms": res["avg_latency_ms"],
            "schedule": _enrich_response(res["schedule"]) if res["schedule"] else None,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/export/{fmt}")
def api_export_schedule(fmt: str, payload: Dict[str, Any] = Body(...)):
    """Export schedule as .json, .csv, or .ics."""
    try:
        profile, tasks, algorithm, pinned_blocks = _extract_profile_and_tasks(payload)
        if "schedule" in payload and isinstance(payload["schedule"], dict):
            schedule = ScheduleOutput.model_validate(payload["schedule"])
        else:
            schedule, _ = ScheduleController.solve_schedule(
                profile=profile, tasks=tasks, algorithm=algorithm, pinned_blocks=pinned_blocks
            )

        fmt_clean = fmt.strip().lower()
        if fmt_clean == "ics":
            ics_text = export_to_ics(schedule, profile=profile)
            return Response(
                content=ics_text,
                media_type="text/calendar; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="smartschedule_baseline.ics"'},
            )
        elif fmt_clean == "csv":
            csv_text = export_to_csv(schedule)
            return Response(
                content=csv_text,
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="smartschedule_baseline.csv"'},
            )
        else:
            json_text = export_to_json(schedule)
            return Response(
                content=json_text,
                media_type="application/json; charset=utf-8",
                headers={"Content-Disposition": 'attachment; filename="schedule_output.json"'},
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
