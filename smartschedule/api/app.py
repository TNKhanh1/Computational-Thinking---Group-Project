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

from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import json
import math
from pathlib import Path
import random
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from smartschedule.core.calibration import compute_ewma_calibration, format_pilot_markdown_report
from smartschedule.core.controller import ScheduleController
from smartschedule.core.cross_week_adapter import adapt_preferences_for_next_week
from smartschedule.core.exporter import export_to_csv, export_to_ics, export_to_json
from smartschedule.core.ics_importer import parse_ics_calendar
from smartschedule.core.models import (
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    PersonalHabit,
    ScheduleBlock,
    ScheduleOutput,
    ScheduleSummary,
    SleepSchedule,
    Task,
)
from smartschedule.nlp.parser_controller import parse_natural_language_task
from smartschedule.core.solvers.local_repair import LocalRepairEngine
from smartschedule.core.storage import (
    append_completion_log,
    create_user,
    delete_workspace_state,
    get_user_by_id,
    list_completion_logs,
    load_workspace_state,
    save_workspace_state,
    verify_user_credentials,
)
from smartschedule.api.auth import (
    extract_bearer_claims,
    get_allowed_origins,
    issue_access_token,
    resolve_workspace_id,
)
from smartschedule.api.chat import process_chat_turn
from smartschedule.api.chat.disruption_chat import handle_disruption_chat_turn, is_disruption_intent
from smartschedule.api.health_v21 import evaluate_schedule_v21
from smartschedule.api.test_showcase import get_showcase_case, list_showcase
from smartschedule.api.v3_services import (
    compute_solver_weights,
    get_available_solvers,
    get_test_suites_catalog,
    load_test_suite,
    parse_ics_content,
    run_benchmark_all,
)

from smartschedule.core.config import (
    DATA_DIR,
    PRESETS_DIR,
    SCENARIOS_DIR,
    UI_DIR,
)

WEB_DIR = UI_DIR

app = FastAPI(
    title="SmartSchedule Baseline (V0) — Technical Benchmark Workbench API",
    description="Deterministic 672-Slot Scheduling Engine & Benchmark API (CSC10014 - Group 03)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _extract_profile_and_tasks_impl(
    payload: Dict[str, Any], apply_buffer: bool = True
) -> Tuple[CommitmentsProfile, List[Task], str, List[ScheduleBlock]]:
    """
    Parse request payload supporting BOTH:
      1. Baseline Schema: { "commitments": {...}, "tasks": [...], "algorithm": "EDF" }
      2. Improve Plan Contract (§7.3): { "now": ..., "week_start": ..., "profile": {...}, "fixed_events": [...], "tasks": [...] }
    """
    algorithm = str(payload.get("algorithm") or payload.get("solver") or "SCORED_GREEDY")

    if "commitments" in payload and isinstance(payload["commitments"], dict):
        comm_dict = dict(payload["commitments"])
        if "now" in payload and payload["now"] and not comm_dict.get("now"):
            comm_dict["now"] = payload["now"]
        if "week_start" in payload and payload["week_start"] and not comm_dict.get("planning_week_start"):
            comm_dict["planning_week_start"] = payload["week_start"]
        for opt_key in (
            "estimate_habit",
            "focus_preference",
            "buffer_mode",
            "alpha_light",
            "alpha_heavy",
            "horizon_days",
            "personal_habits",
        ):
            if payload.get(opt_key) is not None and comm_dict.get(opt_key) is None:
                comm_dict[opt_key] = payload[opt_key]
        profile = CommitmentsProfile.model_validate(comm_dict)
    else:
        # Improve Plan §7.3 contract format
        prof_part = payload.get("profile") or {}
        sleep_part = prof_part.get("sleep") or payload.get("sleep_schedule") or {"daily_start_time": "23:30", "daily_end_time": "06:30"}
        fixed_list = payload.get("fixed_events") or prof_part.get("fixed_events") or []
        habits_raw = prof_part.get("personal_habits") or payload.get("personal_habits") or []
        profile_kwargs: Dict[str, Any] = {
            "student_id": str(payload.get("student_id") or prof_part.get("student_id") or "STUDENT_01"),
            "planning_week_start": str(payload.get("week_start") or payload.get("planning_week_start") or "2026-11-02T00:00:00+07:00"),
            "now": payload.get("now"),
            "sleep_schedule": SleepSchedule.model_validate(sleep_part),
            "fixed_events": [FixedEvent.model_validate(fe) for fe in fixed_list],
            "estimate_habit": prof_part.get("estimate_habit") or payload.get("estimate_habit"),
            "focus_preference": prof_part.get("focus_preference") or payload.get("focus_preference") or "BALANCED",
            "buffer_mode": prof_part.get("buffer_mode") or payload.get("buffer_mode") or "HABIT",
            "personal_habits": [PersonalHabit.model_validate(h) for h in habits_raw],
        }
        if prof_part.get("alpha_light") is not None or payload.get("alpha_light") is not None:
            profile_kwargs["alpha_light"] = float(prof_part.get("alpha_light") or payload.get("alpha_light"))
        if prof_part.get("alpha_heavy") is not None or payload.get("alpha_heavy") is not None:
            profile_kwargs["alpha_heavy"] = float(prof_part.get("alpha_heavy") or payload.get("alpha_heavy"))
        if prof_part.get("horizon_days") is not None or payload.get("horizon_days") is not None:
            profile_kwargs["horizon_days"] = int(prof_part.get("horizon_days") or payload.get("horizon_days"))
        profile = CommitmentsProfile(**profile_kwargs)

    raw_tasks = payload.get("tasks") or []
    tasks = [Task.model_validate(t) for t in raw_tasks]
    if apply_buffer:
        tasks = ScheduleController.apply_estimate_buffer(profile, tasks)
    raw_pinned = payload.get("pinned_blocks") or []
    pinned_blocks = [ScheduleBlock.model_validate(pb) for pb in raw_pinned]

    return profile, tasks, algorithm, pinned_blocks


def _extract_profile_and_tasks(
    payload: Dict[str, Any], apply_buffer: bool = True
) -> Tuple[CommitmentsProfile, List[Task], str, List[ScheduleBlock]]:
    """Backward-compatible helper delegating to `_extract_profile_and_tasks_impl`."""
    return _extract_profile_and_tasks_impl(payload, apply_buffer=apply_buffer)


def _extract_raw_tasks(payload: Dict[str, Any]) -> List[Task]:
    """Parse raw un-expanded/un-buffered Task models for downstream v2.1 evaluation."""
    return [Task.model_validate(t) for t in (payload.get("tasks") or [])]


def _enrich_response(
    out: ScheduleOutput,
    profile: Optional[CommitmentsProfile] = None,
    raw_tasks: Optional[List[Task]] = None,
    pinned_blocks: Optional[List[ScheduleBlock]] = None,
) -> Dict[str, Any]:
    """Attach Improve Plan §7.3 alias fields, Circadian/Batching insights, and v2.1 4-pillar health telemetry."""
    data = out.model_dump()
    data["unplaced"] = data["unplaced_tasks"]
    data["experience_rating"] = out.summary.experience_rating
    data["experience_label"] = out.summary.experience_label
    data["crunch_tier_used"] = out.summary.crunch_tier_used
    data["early_extension_alerts"] = list(out.summary.early_extension_alerts)

    insights: Dict[str, Any] = {}
    if profile is not None:
        insights = ScheduleController.compute_schedule_insights(profile, out)
        b_energies = insights.get("block_energies", {})
        for blk_dict in data.get("blocks", []):
            blk_dict["energy_level"] = b_energies.get(blk_dict.get("block_id"))

    data["metrics"] = {
        "hard_violations": out.summary.hard_constraint_violations,
        "deadline_rate": round(out.summary.deadline_satisfaction_rate / 100.0, 4),
        "deadline_satisfaction_pct": out.summary.deadline_satisfaction_rate,
        "exec_ms": out.execution_time_ms,
        "free_slots": out.summary.free_slots_remaining,
        "rest_slots": out.summary.rest_slots,
        "fragmentation_index": out.summary.fragmentation_index,
        "experience_rating": out.summary.experience_rating,
        "experience_label": out.summary.experience_label,
        "crunch_tier_used": out.summary.crunch_tier_used,
        "peak_match_rate_pct": insights.get("peak_match_rate_pct", 100.0),
        "deep_peak_match_pct": insights.get("deep_peak_match_pct", 100.0),
        "avg_energy_level": insights.get("avg_energy_level", 0.0),
        "context_switches": insights.get("context_switches", 0),
        "batched_pairs": insights.get("batched_pairs", 0),
    }

    if profile is not None and raw_tasks is not None:
        data["health_v21"] = evaluate_schedule_v21(
            profile=profile,
            raw_tasks=raw_tasks,
            schedule=out,
            pinned_blocks=pinned_blocks,
        )
    return data


# UI shell files are ES modules that change together; force browser revalidation
# (ETag → cheap 304) so a merge/branch switch never mixes stale and fresh modules.
_NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(WEB_DIR / "index.html", headers=_NO_CACHE_HEADERS)


@app.get("/app.js", include_in_schema=False)
def serve_app_js():
    return FileResponse(WEB_DIR / "app.js", media_type="application/javascript", headers=_NO_CACHE_HEADERS)


@app.get("/css/{file_path:path}", include_in_schema=False)
def serve_css_asset(file_path: str):
    target = (WEB_DIR / "css" / file_path).resolve()
    css_root = (WEB_DIR / "css").resolve()
    if not str(target).startswith(str(css_root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="CSS asset not found")
    return FileResponse(target, media_type="text/css", headers=_NO_CACHE_HEADERS)


@app.get("/js/{file_path:path}", include_in_schema=False)
def serve_js_asset(file_path: str):
    target = (WEB_DIR / "js" / file_path).resolve()
    js_root = (WEB_DIR / "js").resolve()
    if not str(target).startswith(str(js_root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="JS asset not found")
    return FileResponse(target, media_type="application/javascript", headers=_NO_CACHE_HEADERS)


@app.get("/assets/{file_path:path}", include_in_schema=False)
def serve_media_asset(file_path: str):
    target = (WEB_DIR / "assets" / file_path).resolve()
    assets_root = (WEB_DIR / "assets").resolve()
    if not str(target).startswith(str(assets_root)) or not target.is_file():
        raise HTTPException(status_code=404, detail="Media asset not found")
    return FileResponse(target)


@app.get("/api/presets")
def get_presets():
    """Return built-in presets (Minh's Week, Lan's Busy Week, and Empty Blank Week)."""
    minh_comm = json.loads((PRESETS_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    minh_tasks = json.loads((PRESETS_DIR / "sample_week_tasks.json").read_text(encoding="utf-8"))
    lan_comm = json.loads((PRESETS_DIR / "lan_week_commitments.json").read_text(encoding="utf-8"))
    lan_tasks = json.loads((PRESETS_DIR / "lan_week_tasks.json").read_text(encoding="utf-8"))
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


@app.get("/api/solvers")
def api_list_solvers():
    """Return canonical solver metadata registered in SOLVER_REGISTRY."""
    return {"solvers": get_available_solvers()}


@app.get("/api/test-suites/catalog")
def api_test_suites_catalog():
    """Return unified test suite catalog (Presets, Scenarios T01-T10, Regimes R1-R6)."""
    presets_dict = get_presets()["presets"]
    scenarios_list = list_scenarios()["scenarios"]
    return get_test_suites_catalog(presets_dict, scenarios_list)


@app.post("/api/test-suites/load")
def api_test_suites_load(payload: Dict[str, Any] = Body(...)):
    """Load a preset, T01-T10 scenario, seeded R1-R6 regime (optional horizon 7/14) or FuzzGenerator v2 tier."""
    source = str(payload.get("source") or "preset")
    suite_id = str(payload.get("id") or "")
    seed = int(payload.get("seed") or 42)
    horizon_raw = payload.get("horizon_days")
    horizon = int(horizon_raw) if str(horizon_raw) in ("7", "14") else None
    try:
        presets_dict = get_presets()["presets"]
        return load_test_suite(
            source=source,
            suite_id=suite_id,
            seed=seed,
            presets_dict=presets_dict,
            scenarios_dir=SCENARIOS_DIR,
            horizon_days=horizon,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/test-showcase")
def api_test_showcase_list():
    """List curated Testing_System cases where the 6 solvers diverge (no solving; instant)."""
    return list_showcase()


@app.get("/api/test-showcase/{index}")
def api_test_showcase_case(index: int, refresh: bool = False):
    """Solve + evaluate + rank one showcase case and return its table with a data-driven explanation."""
    try:
        return get_showcase_case(index, force=refresh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/benchmark-all")
def api_benchmark_all(payload: Dict[str, Any] = Body(...)):
    """Run and evaluate every available canonical solver on the same raw input."""
    try:
        profile, _, _, pinned_blocks = _extract_profile_and_tasks(payload, apply_buffer=False)
        raw_tasks = _extract_raw_tasks(payload)
        return run_benchmark_all(
            profile=profile,
            raw_tasks=raw_tasks,
            pinned_blocks=pinned_blocks,
            enrich_fn=lambda out, prof=None: _enrich_response(
                out, profile=prof, raw_tasks=raw_tasks, pinned_blocks=pinned_blocks
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/solver-weights")
def api_solver_weights(payload: Dict[str, Any] = Body(...)):
    """Inspect per-task weights, circadian energy levels, and config constants."""
    try:
        profile, _, _, pinned_blocks = _extract_profile_and_tasks(payload, apply_buffer=False)
        raw_tasks = _extract_raw_tasks(payload)
        return compute_solver_weights(profile=profile, raw_tasks=raw_tasks, pinned_blocks=pinned_blocks)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/plan")
@app.post("/api/solve")
def api_solve_schedule(payload: Dict[str, Any] = Body(...)):
    """Run the selected scheduling algorithm on the discrete 15-min grid and return v2.1 health telemetry."""
    try:
        profile, tasks, algorithm, pinned_blocks = _extract_profile_and_tasks(payload, apply_buffer=False)
        raw_tasks = _extract_raw_tasks(payload)
        out, _ = ScheduleController.solve_schedule(
            profile=profile,
            tasks=tasks,
            algorithm=algorithm,
            pinned_blocks=pinned_blocks,
        )
        return JSONResponse(
            content=_enrich_response(out, profile=profile, raw_tasks=raw_tasks, pinned_blocks=pinned_blocks)
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/compare")
def api_compare_algorithms(payload: Dict[str, Any] = Body(...)):
    """Run two algorithms side-by-side for Dual-Algorithm Comparative View (baseline_plan.md §7.4 Option 3)."""
    try:
        profile, tasks, _, pinned_blocks = _extract_profile_and_tasks(payload, apply_buffer=False)
        raw_tasks = _extract_raw_tasks(payload)
        algo_left = str(payload.get("algo_left") or "GREEDY_EDF_FIRST_FIT")
        algo_right = str(payload.get("algo_right") or "SCORED_GREEDY")
        res = ScheduleController.compare_algorithms(
            profile=profile,
            tasks=tasks,
            algo_left=algo_left,
            algo_right=algo_right,
        )
        return {
            "left": _enrich_response(res["left"], profile=profile, raw_tasks=raw_tasks, pinned_blocks=pinned_blocks),
            "right": _enrich_response(res["right"], profile=profile, raw_tasks=raw_tasks, pinned_blocks=pinned_blocks),
            "comparison": res["comparison"],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/evaluate")
def api_evaluate_schedule(payload: Dict[str, Any] = Body(...)):
    """Evaluate a planned or manually adjusted schedule against Checking Engine v2.1 (`G1/G2` + `P1–P4` + `ICEE`)."""
    try:
        profile, _buffered_tasks, algorithm, pinned_blocks = _extract_profile_and_tasks(payload)
        raw_tasks = _extract_raw_tasks(payload)

        if "schedule" in payload and isinstance(payload["schedule"], dict):
            schedule = ScheduleOutput.model_validate(payload["schedule"])
        elif "blocks" in payload and isinstance(payload["blocks"], list):
            blocks = [ScheduleBlock.model_validate(b) for b in payload["blocks"]]
            placed_ids = {b.task_id for b in blocks}
            schedule = ScheduleOutput(
                status="SUCCESS",
                solver_used=algorithm,
                execution_time_ms=0.0,
                summary=ScheduleSummary(
                    total_tasks_requested=len(raw_tasks),
                    tasks_placed=len(placed_ids),
                    tasks_unplaced=max(0, len(raw_tasks) - len(placed_ids)),
                ),
                blocks=blocks,
            )
        else:
            schedule, _ = ScheduleController.solve_schedule(
                profile=profile,
                tasks=raw_tasks,
                algorithm=algorithm,
                pinned_blocks=pinned_blocks,
            )

        base_sched = None
        if "baseline_schedule" in payload and isinstance(payload["baseline_schedule"], dict):
            base_sched = ScheduleOutput.model_validate(payload["baseline_schedule"])

        dis_span = payload.get("disruption_span")
        span_tuple = (int(dis_span[0]), int(dis_span[1])) if isinstance(dis_span, (list, tuple)) and len(dis_span) == 2 else None
        repair_now = int(payload["repair_now_slot"]) if payload.get("repair_now_slot") is not None else None

        return evaluate_schedule_v21(
            profile=profile,
            raw_tasks=raw_tasks,
            schedule=schedule,
            pinned_blocks=pinned_blocks,
            baseline_schedule=base_sched,
            disruption_span=span_tuple,
            repair_now_slot=repair_now,
            is_overrun_context=bool(payload.get("is_overrun_context", False)),
        )
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
                algorithm=algorithm,
            )
            return {
                "original_schedule": _enrich_response(current_schedule, profile=profile),
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
            algorithm=algorithm,
        )
        if payload.get("workspace_id"):
            ws_id = str(payload["workspace_id"]).strip()
            rec = load_workspace_state(workspace_id=ws_id)
            if isinstance(rec, dict) and isinstance(rec.get("state"), dict):
                st = dict(rec["state"])
                d_logs = list(st.get("disruption_logs") or [])
                d_logs.append(
                    {
                        "event_id": disruption.event_id,
                        "title": disruption.title,
                        "day_of_week": disruption.day_of_week,
                        "start_time": disruption.start_time,
                        "end_time": disruption.end_time,
                        "disruption_slot_window": f"{disruption.day_of_week} {disruption.start_time}-{disruption.end_time}",
                    }
                )
                st["disruption_logs"] = d_logs[-50:]
                save_workspace_state(st, workspace_id=ws_id)
        return rep_out.model_dump()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/progress")
@app.post("/api/overrun")
def api_task_overrun(payload: Dict[str, Any] = Body(...)):
    """Simulate Task Duration Overrun or Set Target Task Duration (Scenario T05 / Use Case UC9)."""
    try:
        profile, tasks, algorithm, _ = _extract_profile_and_tasks(payload, apply_buffer=False)
        task_id = str(payload.get("task_id") or payload.get("block_id") or (tasks[0].task_id if tasks else ""))
        extra_min = int(payload.get("extra_min") or payload.get("extra_minutes") or 0)
        overrun_pct = float(payload.get("overrun_pct") or 30.0)
        raw_target_dur = payload.get("target_duration_min")
        if raw_target_dur is None:
            raw_target_dur = payload.get("set_duration_min")
        target_duration_min = max(15, int(raw_target_dur)) if raw_target_dur is not None else None

        res = ScheduleController.handle_task_overrun(
            profile=profile,
            tasks=tasks,
            task_id=task_id,
            extra_minutes=extra_min,
            overrun_pct=overrun_pct,
            algorithm=algorithm,
            target_duration_min=target_duration_min,
        )
        return {
            "task_id": res["task_id"],
            "old_duration_min": res["old_duration_min"],
            "new_duration_min": res["new_duration_min"],
            "new_estimate_min": res.get("new_estimate_min", res["new_duration_min"]),
            "shifted_blocks_count": res["shifted_blocks_count"],
            "before_schedule": _enrich_response(res["before_schedule"], profile=profile),
            "after_schedule": _enrich_response(res["after_schedule"], profile=profile),
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/validate-move")
def api_validate_move(payload: Dict[str, Any] = Body(...)):
    """Check whether moving a scheduled block to a new time satisfies Hard Constraints H1-H5."""
    try:
        profile, tasks, algorithm, _ = _extract_profile_and_tasks(payload)
        raw_blocks = payload.get("blocks")
        if raw_blocks is None:
            raw_blocks = payload.get("current_blocks")
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


@app.post("/api/tasks/natural-add")
def api_natural_language_add(payload: Dict[str, Any] = Body(...)):
    """
    Convert natural-language input into a validated TaskSheet draft
    using the Dual-Engine M1 NL Parser enriched with the Hybrid 6-stage Pipeline
    (AI Gemini / Offline Deterministic + WorkRhythm, 1=Urgent..4=Low urgency mapping,
    subtask extraction, VI->EN translation, and First-Layer E_*/W_* diagnostics).
    """
    prompt = str(payload.get("prompt") or payload.get("text") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt text cannot be empty.")

    ui_opts = payload.get("ui") if isinstance(payload.get("ui"), dict) else None
    trans_backend = str(payload.get("translation_backend") or "rule").strip().lower() or "rule"

    try:
        return parse_natural_language_task(
            prompt=prompt,
            now=payload.get("now"),
            existing_count=int(payload.get("existing_count") or 0),
            engine=payload.get("engine"),
            ui=ui_opts,
            translation_backend=trans_backend,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat/turn")
def api_chat_turn(payload: Dict[str, Any] = Body(...), request: Request = None):
    """
    Conversational Scheduling Turn Endpoint (< 10s SLA):
      - Emergency one-off disruption routing via LocalRepairEngine (Pattern P8, >= 90% stability).
      - Multi-turn slot filling for missing content or start/end time.
      - SHA-256 keyword task traceability & hidden criteria tuning.
      - Deadline adjustment + remaining-time & personal habit/EWMA buffer re-estimation.
      - Fast re-solving + Deadlock / Overly Dense edge-case diagnostics.
    """
    try:
        enriched_payload = dict(payload)
        enriched_payload["workspace_id"] = resolve_workspace_id(
            request, str(payload.get("workspace_id") or "default")
        )
        prompt_str = str(enriched_payload.get("prompt") or enriched_payload.get("text") or "").strip()
        mode_hint = str(enriched_payload.get("mode_hint") or "AUTO")
        pending_draft = (
            enriched_payload.get("pending_draft")
            if isinstance(enriched_payload.get("pending_draft"), dict)
            else None
        )
        if is_disruption_intent(prompt_str, mode_hint=mode_hint, pending_draft=pending_draft):
            return handle_disruption_chat_turn(enriched_payload)
        return process_chat_turn(enriched_payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/complete")
def api_task_complete(payload: Dict[str, Any] = Body(...), request: Request = None):
    """
    M7 Execution Tracking & Feedback Loop:
    Records actual minutes spent on a task/block and recommends estimate-habit calibration
    or triggers remaining overrun repair when actual duration exceeds estimate.
    """
    try:
        task_id = str(payload.get("task_id") or "")
        category = str(payload.get("category") or "OTHER").strip().upper()
        workspace_id = resolve_workspace_id(request, str(payload.get("workspace_id") or "default"))
        estimated_min = int(
            payload.get("estimated_duration_min")
            or payload.get("estimated_min")
            or payload.get("duration_min")
            or 60
        )
        actual_min = int(payload.get("actual_duration_min") or payload.get("actual_min") or estimated_min)
        completed = bool(payload.get("completed", True))
        ratio = round(actual_min / max(1, estimated_min), 2)

        recommended_habit = "RARELY"
        if ratio >= 1.30:
            recommended_habit = "OFTEN"
        elif ratio >= 1.15:
            recommended_habit = "SOMETIMES"

        completion_entry = append_completion_log(
            task_id=task_id,
            category=category,
            estimated_duration_min=estimated_min,
            actual_duration_min=actual_min,
            workspace_id=workspace_id,
        )

        response: Dict[str, Any] = {
            "status": "COMPLETED" if completed else "PARTIAL_OVERRUN",
            "task_id": task_id,
            "estimated_min": estimated_min,
            "actual_duration_min": actual_min,
            "overrun_ratio": ratio,
            "recommended_estimate_habit": recommended_habit,
            "recommended_alpha": round(max(1.0, min(1.6, ratio)), 2),
            "completion_log": completion_entry,
        }

        if not completed and actual_min > estimated_min and payload.get("tasks"):
            profile, tasks, algorithm, _ = _extract_profile_and_tasks(payload)
            extra = max(15, actual_min - estimated_min)
            res = ScheduleController.handle_task_overrun(
                profile=profile,
                tasks=tasks,
                task_id=task_id,
                extra_minutes=extra,
                algorithm=algorithm,
            )
            response["repair"] = {
                "shifted_blocks_count": res["shifted_blocks_count"],
                "after_schedule": _enrich_response(res["after_schedule"]),
            }

        return response
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/overload/preview")
def api_overload_preview(payload: Dict[str, Any] = Body(...)):
    """
    Preview an overload resolution option before applying changes
    (Improve Plan §6.7 & §7.2 — Feature 002 / F15).
    Supports both:
      1. Full What-If simulation when `tasks` (and `commitments`/`profile`) are provided.
      2. Lightweight block-marking fallback when only `{option_id, schedule}` is provided.
    """
    try:
        option_id = str(payload.get("option_id") or "O1")
        option_code = payload.get("option_code") or payload.get("code")
        target_task_id = payload.get("target_task_id") or payload.get("task_id") or payload.get("task")

        raw_tasks = payload.get("tasks")
        if isinstance(raw_tasks, list) and len(raw_tasks) > 0:
            profile, tasks, algorithm, _ = _extract_profile_and_tasks(payload)
            current_schedule: Optional[ScheduleOutput] = None
            raw_sched = payload.get("schedule")
            if isinstance(raw_sched, dict) and "summary" in raw_sched and "solver_used" in raw_sched:
                try:
                    current_schedule = ScheduleOutput.model_validate(raw_sched)
                except Exception:
                    current_schedule = None

            res = ScheduleController.preview_overload_resolution(
                profile=profile,
                tasks=tasks,
                option_id=option_id,
                option_code=str(option_code) if option_code else None,
                target_task_id=str(target_task_id) if target_task_id else None,
                algorithm=algorithm,
                current_schedule=current_schedule,
            )
            return {
                "status": "OK",
                "preview_mode": True,
                "option_id": res["option_id"],
                "option_code": res["option_code"],
                "target_task_id": res["target_task_id"],
                "option_applied": res["option_applied"],
                "resolved_tasks": res["resolved_tasks"],
                "before_summary": res["before_summary"],
                "after_summary": res["after_summary"],
                "blocks": res["blocks"],
                "proposed_block_ids": res["proposed_block_ids"],
                "changes": res["changes"],
                "schedule": _enrich_response(res["schedule"]),
            }

        raw_schedule = payload.get("schedule") or {}
        blocks = raw_schedule.get("blocks", []) if isinstance(raw_schedule, dict) else []

        # Fallback: simulate proposal/dashed state for the selected preview option
        preview_blocks = []
        for b in blocks:
            b_copy = dict(b)
            b_copy["state"] = "PROPOSED"
            preview_blocks.append(b_copy)

        return {
            "status": "OK",
            "preview_mode": True,
            "option_id": option_id,
            "blocks": preview_blocks,
            "changes": [
                {
                    "action": "PREVIEW_SIMULATION",
                    "option_id": option_id,
                    "description": f"Applied option {option_id} in preview mode.",
                }
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/register")
def api_auth_register(payload: Dict[str, Any] = Body(...)):
    """Register a multi-tenant student account and return a signed HS256 Bearer token."""
    email = str(payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    display_name = str(payload.get("display_name") or "").strip()
    try:
        user = create_user(email=email, password=password, display_name=display_name, provider="local")
    except ValueError as exc:
        msg = str(exc)
        status = 409 if "already registered" in msg.lower() else 400
        raise HTTPException(status_code=status, detail=msg) from exc

    token = issue_access_token(user["user_id"], user["email"], user["display_name"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "workspace_id": f"user:{user['user_id']}",
        "user": user,
    }


@app.post("/api/auth/login")
def api_auth_login(payload: Dict[str, Any] = Body(...)):
    """Authenticate an existing account and return a signed HS256 Bearer token."""
    email = str(payload.get("email") or "").strip()
    password = str(payload.get("password") or "")
    user = verify_user_credentials(email=email, password=password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token = issue_access_token(user["user_id"], user["email"], user["display_name"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "workspace_id": f"user:{user['user_id']}",
        "user": user,
    }


@app.get("/api/auth/me")
def api_auth_me(request: Request):
    """Return the authenticated user profile and isolated tenant workspace_id."""
    claims = extract_bearer_claims(request)
    if claims is None:
        raise HTTPException(status_code=401, detail="Missing Bearer token.")
    user = get_user_by_id(claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="User account no longer exists.")
    return {
        "workspace_id": f"user:{user['user_id']}",
        "user": user,
    }


@app.get("/api/state")
def api_get_state(workspace_id: str = "default", request: Request = None):
    """Load persisted workspace state (commitments, tasks, pins, done blocks, algorithm) from SQLite."""
    ws_id = resolve_workspace_id(request, workspace_id)
    try:
        record = load_workspace_state(workspace_id=ws_id)
        if record is None:
            return {
                "exists": False,
                "workspace_id": ws_id,
                "state": None,
                "updated_at": None,
            }
        return {"exists": True, **record}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.put("/api/state")
def api_put_state(payload: Dict[str, Any] = Body(...), request: Request = None):
    """Save or overwrite persisted workspace state in SQLite."""
    ws_id = resolve_workspace_id(request, str(payload.get("workspace_id") or "default"))
    try:
        state_data = payload.get("state")
        if not isinstance(state_data, dict):
            state_data = {k: v for k, v in payload.items() if k != "workspace_id"}
        updated_at = save_workspace_state(state_data, workspace_id=ws_id)
        return {
            "status": "saved",
            "workspace_id": ws_id,
            "updated_at": updated_at,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/state")
def api_delete_state(workspace_id: str = "default", request: Request = None):
    """Reset/delete persisted workspace state in SQLite."""
    ws_id = resolve_workspace_id(request, workspace_id)
    try:
        removed = delete_workspace_state(workspace_id=ws_id)
        return {
            "status": "deleted",
            "workspace_id": ws_id,
            "removed": removed,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/tasks/completions")
def api_list_completions(workspace_id: str = "default", limit: int = 200, request: Request = None):
    """Retrieve historical M7 actual duration completion logs from SQLite."""
    ws_id = resolve_workspace_id(request, workspace_id)
    try:
        rows = list_completion_logs(workspace_id=ws_id, limit=limit)
        return {
            "workspace_id": ws_id,
            "completions": rows,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/tasks/calibration")
def api_tasks_calibration(
    workspace_id: str = "default",
    limit: int = 200,
    lambda_ewma: float = 0.25,
    min_samples: int = 5,
    include_markdown: bool = False,
    request: Request = None,
):
    """Compute M7 empirical Actual/Estimated ratios and EWMA personal alpha recommendations (LoA-4)."""
    ws_id = resolve_workspace_id(request, workspace_id)
    try:
        rows = list_completion_logs(workspace_id=ws_id, limit=limit)
        cal = compute_ewma_calibration(
            rows,
            lambda_ewma=lambda_ewma,
            min_samples=min_samples,
        )
        rec_alpha = cal.get("recommended_alpha_heavy")
        rec_habit = (
            "OFTEN"
            if isinstance(rec_alpha, (int, float)) and rec_alpha >= 1.25
            else ("SOMETIMES" if isinstance(rec_alpha, (int, float)) and rec_alpha >= 1.10 else "RARELY")
        )
        resp: Dict[str, Any] = {
            "workspace_id": ws_id,
            "sample_count": cal["sample_count"],
            "ready_for_calibration": cal["ready_to_apply"],
            "ewma_ratio": cal.get("ewma_overall") or cal.get("mean_ratio"),
            "mean_ratio": cal.get("mean_ratio"),
            "recommended_alpha": rec_alpha,
            "recommended_habit": rec_habit,
            "calibration": cal,
        }
        if include_markdown:
            resp["markdown"] = format_pilot_markdown_report(cal, workspace_id=ws_id)
        return resp
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/import/ics")
def api_import_ics(payload: Dict[str, Any] = Body(...)):
    """
    Parse an uploaded `.ics` timetable or Moodle/Canvas LMS calendar feed into
    preview drafts of FixedEvents and Tasks.
    """
    if "content" in payload and "ics_content" not in payload:
        ics_raw = str(payload.get("content") or "").strip()
        if not ics_raw:
            raise HTTPException(status_code=400, detail="Field 'content' cannot be empty.")
        try:
            return parse_ics_content(ics_raw)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    ics_text = str(payload.get("ics_content") or payload.get("ics") or "").strip()
    if not ics_text:
        raise HTTPException(status_code=400, detail="Field 'ics_content' cannot be empty.")
    tz_offset = int(payload.get("tz_offset_hours", 7))
    default_dur = int(payload.get("default_task_duration_min", 90))
    return parse_ics_calendar(
        ics_text=ics_text,
        tz_offset_hours=tz_offset,
        default_task_duration_min=default_dur,
    )


# ---------------------------------------------------------------------------
# v1.0-alpha M5 Endpoints: Real-Week Init, Single-Item CRUD, Cross-Week
# Preference Adaptation (Pattern P13), & Closed-Loop Multi-Week Simulation
# ---------------------------------------------------------------------------

def _load_workspace_bundle_for_mutation(
    payload: Dict[str, Any],
    request: Optional[Request],
) -> Tuple[str, Optional[Dict[str, Any]], CommitmentsProfile, List[Task], str, List[ScheduleBlock]]:
    ws_id = resolve_workspace_id(request, str(payload.get("workspace_id") or "default"))
    rec = load_workspace_state(workspace_id=ws_id)
    saved_state = dict(rec["state"]) if isinstance(rec, dict) and isinstance(rec.get("state"), dict) else None

    merged = dict(payload)
    if saved_state is not None:
        if "commitments" not in merged and "profile" not in merged and saved_state.get("commitments"):
            merged["commitments"] = saved_state["commitments"]
        if "tasks" not in merged and saved_state.get("tasks") is not None:
            merged["tasks"] = saved_state["tasks"]
        if "pinned_blocks" not in merged and saved_state.get("pinnedBlocks") is not None:
            merged["pinned_blocks"] = saved_state["pinnedBlocks"]
        if "algorithm" not in merged and saved_state.get("activeSolver"):
            merged["algorithm"] = saved_state["activeSolver"]

    profile, raw_tasks, algorithm, pinned_blocks = _extract_profile_and_tasks(merged, apply_buffer=False)
    return ws_id, saved_state, profile, raw_tasks, algorithm, pinned_blocks


def _synthesize_real_user_timeline_logs(
    ws_id: str,
    saved_state: Optional[Dict[str, Any]],
    provided_logs: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Bridge real human SQLite telemetry (`completion_logs` + `completedBlocks` + `disruption_logs`)
    into `CrossWeekPreferenceAdapter`'s unified `timeline_logs` contract (Fix M-5).
    """
    if isinstance(provided_logs, list) and len(provided_logs) > 0:
        out_logs = [dict(x) for x in provided_logs if isinstance(x, dict)]
    else:
        rows = list_completion_logs(workspace_id=ws_id, limit=200)
        sched_blocks = ((saved_state or {}).get("currentSchedule") or {}).get("blocks") or []
        completed_map = (saved_state or {}).get("completedBlocks") or {}

        blocks_by_task: Dict[str, List[Dict[str, Any]]] = {}
        for blk in sched_blocks:
            if isinstance(blk, dict) and blk.get("task_id"):
                blocks_by_task.setdefault(str(blk["task_id"]), []).append(blk)

        out_logs = []
        # Rows come newest-first; reverse so chronological order holds
        for r in reversed(rows):
            entry = dict(r)
            tid = str(entry.get("task_id") or "")
            matched_blks = blocks_by_task.get(tid) or []
            if matched_blks:
                b0 = matched_blks[0]
                if not entry.get("start_time") and b0.get("start_time"):
                    entry["start_time"] = b0["start_time"]
                if entry.get("cognitive_load") is None and b0.get("cognitive_load") is not None:
                    entry["cognitive_load"] = b0["cognitive_load"]
                if entry.get("planned_duration_min") is None and b0.get("duration_min") is not None:
                    entry["planned_duration_min"] = b0["duration_min"]
            entry.setdefault("adhered", True)
            out_logs.append(entry)

        # Include uncompleted scheduled blocks when user tracked partial block completions in workspace
        if isinstance(completed_map, dict) and len(completed_map) > 0 and sched_blocks:
            for blk in sched_blocks:
                if not isinstance(blk, dict):
                    continue
                bid = str(blk.get("block_id") or "")
                if bid and bid not in completed_map:
                    out_logs.append(
                        {
                            "task_id": blk.get("task_id"),
                            "block_id": bid,
                            "category": blk.get("category") or "DEADLINE",
                            "cognitive_load": blk.get("cognitive_load"),
                            "start_time": blk.get("start_time"),
                            "estimated_duration_min": blk.get("duration_min"),
                            "planned_duration_min": blk.get("duration_min"),
                            "actual_duration_min": 0,
                            "adhered": False,
                        }
                    )

    if isinstance(saved_state, dict):
        for d_item in saved_state.get("disruption_logs") or []:
            if isinstance(d_item, dict) and d_item.get("disruption_slot_window"):
                out_logs.append({"disruption_slot_window": d_item["disruption_slot_window"]})
    return out_logs


@app.post("/api/workspace/init-real-week")
def api_init_real_week(payload: Dict[str, Any] = Body(default={}), request: Request = None):
    """Initialize an empty schedule anchored to the current real-world Monday (`00:00:00+07:00`)."""
    try:
        ws_id = resolve_workspace_id(request, str(payload.get("workspace_id") or "default"))
        sleep_start = str(payload.get("sleep_start") or payload.get("daily_start_time") or "23:30")
        sleep_end = str(payload.get("sleep_end") or payload.get("daily_end_time") or "06:30")
        focus_pref = str(payload.get("focus_preference") or "BALANCED")
        est_habit = payload.get("estimate_habit", "SOMETIMES")
        student_id = str(payload.get("student_id") or "STUDENT_USER")

        profile = ScheduleController.build_empty_current_week_profile(
            student_id=student_id,
            daily_start_time=sleep_start,
            daily_end_time=sleep_end,
            focus_preference=focus_pref,
            estimate_habit=est_habit,
        )
        out, _, _ = ScheduleController.solve_adaptive(
            profile=profile,
            tasks=[],
            algorithm="SCORED_GREEDY",
            pinned_blocks=[],
        )
        enriched = _enrich_response(out, profile=profile, raw_tasks=[], pinned_blocks=[])

        if bool(payload.get("save", True)):
            save_workspace_state(
                {
                    "commitments": profile.model_dump(),
                    "tasks": [],
                    "pinnedBlocks": [],
                    "completedBlocks": {},
                    "activeSolver": "SCORED_GREEDY",
                    "currentSchedule": enriched,
                    "chatMessages": [],
                    "disruption_logs": [],
                },
                workspace_id=ws_id,
            )

        return {
            "workspace_id": ws_id,
            "commitments": profile.model_dump(),
            "tasks": [],
            "pinned_blocks": [],
            "schedule": enriched,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tasks/delete")
def api_delete_task(payload: Dict[str, Any] = Body(...), request: Request = None):
    """Delete a single task, clean orphaned `depends_on` references & pins, and re-solve."""
    try:
        target_id = str(payload.get("task_id") or "").strip()
        if not target_id:
            raise ValueError("Field 'task_id' is required.")

        ws_id, saved_state, profile, raw_tasks, algorithm, pinned_blocks = _load_workspace_bundle_for_mutation(
            payload, request
        )
        kept_tasks: List[Task] = []
        for t in raw_tasks:
            if t.task_id == target_id:
                continue
            if target_id in (t.depends_on or []):
                cleaned_deps = [dep for dep in t.depends_on if dep != target_id]
                kept_tasks.append(t.model_copy(update={"depends_on": cleaned_deps}, deep=True))
            else:
                kept_tasks.append(t)

        kept_pins = [pb for pb in pinned_blocks if pb.task_id != target_id]
        out, _, _ = ScheduleController.solve_adaptive(
            profile=profile,
            tasks=kept_tasks,
            algorithm=algorithm,
            pinned_blocks=kept_pins,
        )
        enriched = _enrich_response(out, profile=profile, raw_tasks=kept_tasks, pinned_blocks=kept_pins)

        if bool(payload.get("save", saved_state is not None)):
            next_state = dict(saved_state or {})
            prev_completed = dict(next_state.get("completedBlocks") or {})
            cleaned_completed = {
                bid: binfo
                for bid, binfo in prev_completed.items()
                if not str(bid).startswith(f"{target_id}_") and bid != target_id
            }
            next_state.update(
                {
                    "commitments": profile.model_dump(),
                    "tasks": [t.model_dump() for t in kept_tasks],
                    "pinnedBlocks": [pb.model_dump() for pb in kept_pins],
                    "completedBlocks": cleaned_completed,
                    "currentSchedule": enriched,
                }
            )
            save_workspace_state(next_state, workspace_id=ws_id)

        return {
            "deleted_task_id": target_id,
            "updated_tasks": [t.model_dump() for t in kept_tasks],
            "updated_pinned_blocks": [pb.model_dump() for pb in kept_pins],
            "schedule": enriched,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/fixed-events/upsert")
def api_upsert_fixed_event(payload: Dict[str, Any] = Body(...), request: Request = None):
    """Create or update a single FixedEvent by `event_id` and re-solve the schedule."""
    try:
        ev_raw = payload.get("event") or payload.get("fixed_event")
        if not isinstance(ev_raw, dict):
            raise ValueError("Field 'event' must be an object.")

        ev_dict = dict(ev_raw)
        if not ev_dict.get("event_id") and not ev_dict.get("id"):
            ev_dict["event_id"] = f"EVENT_{uuid.uuid4().hex[:6].upper()}"
        ev_model = FixedEvent.model_validate(ev_dict)
        if ev_model.start_time == ev_model.end_time:
            raise ValueError("FixedEvent start_time and end_time cannot be identical.")

        ws_id, saved_state, profile, raw_tasks, algorithm, pinned_blocks = _load_workspace_bundle_for_mutation(
            payload, request
        )
        updated_profile = profile.model_copy(deep=True)
        replaced = False
        new_events: List[FixedEvent] = []
        for fe in updated_profile.fixed_events:
            if fe.event_id == ev_model.event_id:
                new_events.append(ev_model)
                replaced = True
            else:
                new_events.append(fe)
        if not replaced:
            new_events.append(ev_model)
        updated_profile.fixed_events = new_events

        out, _, _ = ScheduleController.solve_adaptive(
            profile=updated_profile,
            tasks=raw_tasks,
            algorithm=algorithm,
            pinned_blocks=pinned_blocks,
        )
        enriched = _enrich_response(out, profile=updated_profile, raw_tasks=raw_tasks, pinned_blocks=pinned_blocks)

        if bool(payload.get("save", saved_state is not None)):
            next_state = dict(saved_state or {})
            next_state.update(
                {
                    "commitments": updated_profile.model_dump(),
                    "tasks": [t.model_dump() for t in raw_tasks],
                    "pinnedBlocks": [pb.model_dump() for pb in pinned_blocks],
                    "currentSchedule": enriched,
                }
            )
            save_workspace_state(next_state, workspace_id=ws_id)

        return {
            "event": ev_model.model_dump(),
            "updated_commitments": updated_profile.model_dump(),
            "schedule": enriched,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/fixed-events/delete")
def api_delete_fixed_event(payload: Dict[str, Any] = Body(...), request: Request = None):
    """Delete a single FixedEvent by `event_id` and re-solve the schedule."""
    try:
        event_id = str(payload.get("event_id") or "").strip()
        if not event_id:
            raise ValueError("Field 'event_id' is required.")

        ws_id, saved_state, profile, raw_tasks, algorithm, pinned_blocks = _load_workspace_bundle_for_mutation(
            payload, request
        )
        updated_profile = profile.model_copy(deep=True)
        updated_profile.fixed_events = [fe for fe in updated_profile.fixed_events if fe.event_id != event_id]

        out, _, _ = ScheduleController.solve_adaptive(
            profile=updated_profile,
            tasks=raw_tasks,
            algorithm=algorithm,
            pinned_blocks=pinned_blocks,
        )
        enriched = _enrich_response(out, profile=updated_profile, raw_tasks=raw_tasks, pinned_blocks=pinned_blocks)

        if bool(payload.get("save", saved_state is not None)):
            next_state = dict(saved_state or {})
            next_state.update(
                {
                    "commitments": updated_profile.model_dump(),
                    "tasks": [t.model_dump() for t in raw_tasks],
                    "pinnedBlocks": [pb.model_dump() for pb in pinned_blocks],
                    "currentSchedule": enriched,
                }
            )
            save_workspace_state(next_state, workspace_id=ws_id)

        return {
            "deleted_event_id": event_id,
            "updated_commitments": updated_profile.model_dump(),
            "schedule": enriched,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workspace/adapt-next-week")
def api_adapt_next_week(payload: Dict[str, Any] = Body(default={}), request: Request = None):
    """
    Cross-Week Fallacy Buffer & Preference Adaptation Endpoint (`Pattern P13`, LoA-4 default `apply=False`).
    Adapts per-category buffers, revealed chronotype, ultradian pacing, and day-specific advisory buffers.
    """
    try:
        ws_id, saved_state, profile, fallback_tasks, algorithm, _ = _load_workspace_bundle_for_mutation(
            payload, request
        )
        raw_next_list = payload.get("next_week_tasks")
        if isinstance(raw_next_list, list):
            next_tasks = [Task.model_validate(t) for t in raw_next_list]
        else:
            next_tasks = fallback_tasks

        target_profile = profile.model_copy(deep=True)
        if bool(payload.get("advance_week", False)):
            try:
                ws_dt = datetime.fromisoformat(str(target_profile.planning_week_start).replace("Z", "+00:00"))
                next_monday = ws_dt + timedelta(days=7)
                target_profile.planning_week_start = next_monday.isoformat()
                target_profile.now = next_monday.replace(hour=8, minute=0).isoformat()

                # Shift ISO `due` / `start_after` timestamps belonging to the previous week forward +7 days
                shifted_tasks: List[Task] = []
                for nt in next_tasks:
                    upd_fields: Dict[str, Any] = {}
                    if nt.due:
                        try:
                            due_dt = datetime.fromisoformat(str(nt.due).replace("Z", "+00:00"))
                            if due_dt < next_monday:
                                upd_fields["due"] = (due_dt + timedelta(days=7)).isoformat()
                        except ValueError:
                            pass
                    if nt.start_after and "T" in str(nt.start_after):
                        try:
                            sa_dt = datetime.fromisoformat(str(nt.start_after).replace("Z", "+00:00"))
                            if sa_dt < next_monday:
                                upd_fields["start_after"] = (sa_dt + timedelta(days=7)).isoformat()
                        except ValueError:
                            pass
                    shifted_tasks.append(nt.model_copy(update=upd_fields, deep=True) if upd_fields else nt)
                next_tasks = shifted_tasks
            except ValueError:
                pass

        provided_logs = payload.get("timeline_logs") if isinstance(payload.get("timeline_logs"), list) else None
        eff_logs = _synthesize_real_user_timeline_logs(ws_id, saved_state, provided_logs)
        kappa = float(payload.get("kappa", 3.0))

        adapt_res = adapt_preferences_for_next_week(
            profile=target_profile,
            next_tasks=next_tasks,
            timeline_logs=eff_logs,
            kappa=kappa,
        )
        adapted_profile: CommitmentsProfile = adapt_res["adapted_profile"]
        adapted_tasks: List[Task] = adapt_res["adapted_tasks"]

        out, _, _ = ScheduleController.solve_adaptive(
            profile=adapted_profile,
            tasks=adapted_tasks,
            algorithm=algorithm,
            pinned_blocks=[],
        )
        enriched = _enrich_response(out, profile=adapted_profile, raw_tasks=adapted_tasks, pinned_blocks=[])

        apply_changes = bool(payload.get("apply", False))
        if apply_changes:
            next_state = dict(saved_state or {})
            next_state.update(
                {
                    "commitments": adapt_res["adapted_commitments"],
                    "tasks": adapt_res["adapted_tasks_dump"],
                    "pinnedBlocks": [],
                    "completedBlocks": {},
                    "currentSchedule": enriched,
                }
            )
            save_workspace_state(next_state, workspace_id=ws_id)

        return {
            "workspace_id": ws_id,
            "applied": apply_changes,
            "adapted_commitments": adapt_res["adapted_commitments"],
            "adapted_tasks": adapt_res["adapted_tasks_dump"],
            "category_alphas": adapt_res["category_alphas"],
            "preference_shifts": adapt_res["preference_shifts"],
            "chronic_disruption_zones": adapt_res["chronic_disruption_zones"],
            "pattern_rules": adapt_res["pattern_rules"],
            "schedule": enriched,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


class _DeterministicFallbackStudentSimulator:
    """
    Self-contained 5-equation psychometric fallback twin (`MCTQ` + `Buehler LogNormal` +
    `Steel 2007 TMT` + `McFadden RUM` + `Albulescu Fatigue`) used when `student_simulator.py`
    (`M7`) is not yet merged on a standalone Wave 1A branch.
    """

    def __init__(self, student_id: str, seed: int = 42, latent_profile: Optional[Dict[str, Any]] = None) -> None:
        self.student_id = student_id
        self.rng = random.Random(int(seed))
        cfg = dict(latent_profile or {})
        self.true_peak_hour: float = float(cfg.get("true_peak_hour", 20.5))
        self.impulsiveness_gamma: float = float(cfg.get("gamma", self.rng.betavariate(2.0, 5.0)))
        self.category_bias: Dict[str, float] = {
            "CODING": 1.44,
            "PROJECT": 1.38,
            "ASSIGNMENT": 1.25,
            "EXAM": 1.32,
            "READING": 1.05,
            "DEADLINE": 1.20,
            "HABIT": 1.02,
        }
        if isinstance(cfg.get("category_bias"), dict):
            for k, v in cfg["category_bias"].items():
                self.category_bias[str(k).upper()] = float(v)
        self.chronic_disruption_window: Optional[str] = str(
            cfg.get("chronic_disruption_window", "Thursday 19:30-21:00")
        )

    def _window_for_hour(self, h: float) -> str:
        hi = int(h) % 24
        if 6 <= hi < 12:
            return "MORNING"
        if 12 <= hi < 18:
            return "AFTERNOON"
        if 18 <= hi < 24:
            return "EVENING"
        return "NIGHT"

    def simulate_week_execution(
        self,
        profile: CommitmentsProfile,
        tasks: List[Task],
        schedule: ScheduleOutput,
    ) -> List[Dict[str, Any]]:
        task_map = {t.task_id: t for t in tasks}
        ordered_blocks = sorted(schedule.blocks, key=lambda b: (b.start_slot, b.end_slot))
        fatigue = 0.12
        prev_end_slot: Optional[int] = None
        prev_day_idx: Optional[int] = None
        logs: List[Dict[str, Any]] = []

        # Thursday 19:30-21:00 recurring club disruption -> slots [3*96 + 78, 3*96 + 84)
        disr_start, disr_end = 3 * 96 + 78, 3 * 96 + 84

        for blk in ordered_blocks:
            day_idx = blk.start_slot // 96
            if prev_day_idx is not None and day_idx > prev_day_idx:
                fatigue = max(0.05, fatigue * 0.25)
            elif prev_end_slot is not None and (blk.start_slot - prev_end_slot) >= 1:
                fatigue = max(0.05, fatigue * 0.60)

            start_hour = ((blk.start_slot % 96) * 15) / 60.0
            mid_hour = (((blk.start_slot + blk.end_slot) * 0.5 % 96) * 15) / 60.0
            circ_dist = min(abs(mid_hour - self.true_peak_hour), 24.0 - abs(mid_hour - self.true_peak_hour))
            circ_fit = max(0.0, 1.0 - (circ_dist / 8.0))

            t_obj = task_map.get(blk.task_id)
            raw_task_est = int(t_obj.duration_min) if t_obj is not None else int(blk.duration_min)
            total_chunks = max(1, int(blk.total_chunks or 1))
            est_chunk_min = max(15, int(round(raw_task_est / float(total_chunks))))
            planned_min = int(blk.duration_min)
            load = int(blk.cognitive_load or (t_obj.cognitive_load if t_obj and t_obj.cognitive_load else 2))
            prio = int(blk.priority or (t_obj.priority if t_obj else 3))
            cat = str(blk.category or (t_obj.category if t_obj else "DEADLINE")).strip().upper()

            dl_slot = blk.deadline_slot if blk.deadline_slot is not None else (day_idx * 96 + 92)
            slack_hours = max(0.05, ((dl_slot - blk.start_slot) * 15.0) / 60.0)
            expectancy = max(0.08, 0.25 + 0.75 * circ_fit - 0.30 * fatigue)
            u_task = (expectancy * (0.45 + 0.55 * (prio / 5.0))) / (
                1.0 + self.impulsiveness_gamma * min(3.0, slack_hours / 24.0)
            )
            u_distract = 0.30
            logit = 5.0 * (u_task - u_distract - 0.22 * fatigue)
            p_adhere = 1.0 / (1.0 + math.exp(-max(-12.0, min(12.0, logit))))

            collides_disruption = (
                self.chronic_disruption_window is not None
                and blk.start_slot < disr_end
                and blk.end_slot > disr_start
            )
            if collides_disruption:
                p_adhere *= 0.25

            adhered = self.rng.random() < p_adhere
            bias = self.category_bias.get(cat, 1.18)
            noise = math.exp(self.rng.gauss(0.0, 0.07))
            speed_Circ = 1.12 - 0.20 * circ_fit
            actual_min = (
                max(15, int(math.ceil((est_chunk_min * bias * speed_Circ * noise) / 15.0) * 15))
                if adhered
                else 0
            )
            overrun_min = max(0, actual_min - planned_min) if adhered else planned_min

            if adhered:
                hours_spent = actual_min / 60.0
                fatigue_gain = (0.16 if load >= 3 else 0.09) * hours_spent
                fatigue = min(1.0, fatigue + fatigue_gain)

            logs.append(
                {
                    "task_id": blk.task_id,
                    "block_id": blk.block_id,
                    "category": cat,
                    "cognitive_load": load,
                    "day": blk.day,
                    "window": self._window_for_hour(start_hour),
                    "start_hour": round(start_hour, 2),
                    "estimated_duration_min": est_chunk_min,
                    "planned_duration_min": planned_min,
                    "actual_duration_min": actual_min,
                    "adhered": adhered,
                    "overrun_min": overrun_min,
                    "fatigue_after": round(fatigue, 4),
                    "disruption_slot_window": self.chronic_disruption_window if collides_disruption else None,
                }
            )
            prev_end_slot = blk.end_slot
            prev_day_idx = day_idx

        if self.chronic_disruption_window and not any(x.get("disruption_slot_window") for x in logs):
            logs.append({"disruption_slot_window": self.chronic_disruption_window, "adhered": True})
        return logs


def _build_default_multiweek_benchmark_scenario() -> Tuple[CommitmentsProfile, List[Task], Dict[str, Any]]:
    """
    Canonical closed-loop evaluation persona (Formal_Spec_And_Patterns.md §6 Step 4):
    A latent Night-Owl student (`true_peak_hour=20.5`) who initially misreports `'MORNING'`,
    underestimates `CODING`/`PROJECT` tasks (`~1.44x`), and faces recurring Thursday `19:30–21:00`
    club disruptions.
    """
    profile = CommitmentsProfile(
        student_id="SIM_NIGHT_OWL_01",
        planning_week_start="2026-11-02T00:00:00+07:00",
        now="2026-11-02T07:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:45", daily_end_time="06:30", is_hard_lock=True),
        fixed_events=[
            FixedEvent(
                event_id="CLS_MWF",
                title="Lớp chính khóa Chiều T2-T4-T6",
                day_of_week=["Monday", "Wednesday", "Friday"],
                start_time="13:30",
                end_time="16:30",
                category="ACADEMIC_CLASS",
            )
        ],
        estimate_habit=None,
        focus_preference="MORNING",
        buffer_mode="HABIT",
    )
    tasks = [
        Task(
            task_id="SIM_CODE_1",
            title="Cài đặt thuật toán Đồ án",
            duration_min=90,
            deadline_day="Wednesday",
            deadline_time="23:59",
            priority=5,
            category="CODING",
            cognitive_load=3,
            is_splittable=False,
        ),
        Task(
            task_id="SIM_CODE_2",
            title="Tối ưu cấu trúc dữ liệu & Test",
            duration_min=90,
            deadline_day="Friday",
            deadline_time="23:59",
            priority=5,
            category="CODING",
            cognitive_load=3,
            is_splittable=False,
        ),
        Task(
            task_id="SIM_PRJ_1",
            title="Thiết kế kiến trúc mô-đun",
            duration_min=75,
            deadline_day="Thursday",
            deadline_time="22:00",
            priority=4,
            category="PROJECT",
            cognitive_load=3,
            is_splittable=False,
        ),
        Task(
            task_id="SIM_READ_1",
            title="Đọc tài liệu buổi tối T2",
            duration_min=60,
            start_after="Monday 18:30",
            deadline_day="Tuesday",
            deadline_time="23:00",
            priority=3,
            category="READING",
            cognitive_load=2,
            preferred_window="EVENING",
        ),
        Task(
            task_id="SIM_READ_2",
            title="Tổng hợp ghi chú buổi tối T4",
            duration_min=60,
            start_after="Wednesday 18:30",
            deadline_day="Thursday",
            deadline_time="23:00",
            priority=3,
            category="READING",
            cognitive_load=2,
            preferred_window="EVENING",
        ),
        Task(
            task_id="SIM_ASG_1",
            title="Bài tập tự luyện cuối tuần",
            duration_min=60,
            deadline_day="Saturday",
            deadline_time="22:00",
            priority=4,
            category="ASSIGNMENT",
            cognitive_load=3,
        ),
    ]
    latent_cfg = {
        "true_peak_hour": 20.5,
        "category_bias": {"CODING": 1.44, "PROJECT": 1.38, "ASSIGNMENT": 1.28, "READING": 1.05},
        "chronic_disruption_window": "Thursday 19:30-21:00",
    }
    return profile, tasks, latent_cfg


def _instantiate_student_simulator(student_id: str, seed: int, latent_cfg: Dict[str, Any]) -> Tuple[Any, str]:
    try:
        from smartschedule.core.student_simulator import InSilicoStudentSimulator  # type: ignore

        sig = inspect.signature(InSilicoStudentSimulator.__init__).parameters
        kwargs: Dict[str, Any] = {}
        if "student_id" in sig:
            kwargs["student_id"] = student_id
        if "seed" in sig:
            kwargs["seed"] = seed
        if "latent_profile" in sig:
            kwargs["latent_profile"] = latent_cfg
        return InSilicoStudentSimulator(**kwargs), "InSilicoStudentSimulator"
    except ImportError:
        return _DeterministicFallbackStudentSimulator(student_id=student_id, seed=seed, latent_profile=latent_cfg), "DeterministicFallbackTwin"


@app.post("/api/simulation/multi-week")
def api_simulate_multi_week(payload: Dict[str, Any] = Body(default={})):
    """
    Closed-loop K-week behavioral adaptation simulation (`Pattern P13 + P14b`):
    `Solve Week k -> Simulate In-Silico Student -> Adapt Preferences for Week k+1`.
    Defaults to `weeks=4, n_students=1` (`< 500 ms` interactive SLA) and supports cohort runs (`n_students > 1`).
    """
    t0 = time.perf_counter()
    try:
        weeks = max(1, min(12, int(payload.get("weeks") or 4)))
        n_students = max(1, min(50, int(payload.get("n_students") or 1)))
        base_seed = int(payload.get("seed") if payload.get("seed") is not None else 42)
        algorithm = str(payload.get("algorithm") or "SCORED_GREEDY")

        has_custom_tasks = isinstance(payload.get("tasks"), list) and len(payload["tasks"]) > 0
        if has_custom_tasks:
            init_profile, init_tasks, _, _ = _extract_profile_and_tasks(payload, apply_buffer=False)
            latent_cfg = payload.get("latent_profile") if isinstance(payload.get("latent_profile"), dict) else {
                "true_peak_hour": 20.5,
                "category_bias": {"CODING": 1.44, "PROJECT": 1.38, "ASSIGNMENT": 1.28, "READING": 1.05},
                "chronic_disruption_window": "Thursday 19:30-21:00",
            }
        else:
            init_profile, init_tasks, latent_cfg = _build_default_multiweek_benchmark_scenario()
            if isinstance(payload.get("latent_profile"), dict):
                latent_cfg.update(payload["latent_profile"])

        per_week_adherence: List[List[float]] = [[] for _ in range(weeks)]
        per_week_ontime_val: List[List[float]] = [[] for _ in range(weeks)]
        rep_learned_alphas: List[Dict[str, float]] = [{} for _ in range(weeks)]
        rep_learned_focus: List[str] = ["" for _ in range(weeks)]
        backend_name = "DeterministicFallbackTwin"

        for s_idx in range(n_students):
            stu_seed = base_seed + s_idx * 9973
            sim, backend_name = _instantiate_student_simulator(
                student_id=f"{init_profile.student_id}_{s_idx + 1}",
                seed=stu_seed,
                latent_cfg=latent_cfg,
            )
            cur_profile = init_profile.model_copy(deep=True)
            cur_tasks = [t.model_copy(deep=True) for t in init_tasks]
            cumulative_logs: List[Dict[str, Any]] = []

            for w_idx in range(weeks):
                sched_out, _ = ScheduleController.solve_schedule(
                    profile=cur_profile,
                    tasks=cur_tasks,
                    algorithm=algorithm,
                )
                week_logs = sim.simulate_week_execution(cur_profile, cur_tasks, sched_out)
                cumulative_logs.extend(week_logs)

                block_logs = [lg for lg in week_logs if lg.get("task_id")]
                if block_logs:
                    adh_cnt = sum(1 for lg in block_logs if bool(lg.get("adhered", False)))
                    adh_pct = 100.0 * float(adh_cnt) / float(len(block_logs))
                else:
                    adh_pct = 0.0

                # Compute effective on-time priority value accounting for both adherence AND overrun safety
                total_prio = sum(int(t.priority) for t in init_tasks) or 1
                earned_prio = 0.0
                logs_by_tid: Dict[str, List[Dict[str, Any]]] = {}
                for lg in block_logs:
                    logs_by_tid.setdefault(str(lg["task_id"]), []).append(lg)

                for t_raw in init_tasks:
                    t_logs = logs_by_tid.get(t_raw.task_id, [])
                    if not t_logs:
                        continue
                    if all(bool(lg.get("adhered", False)) for lg in t_logs):
                        total_overrun = sum(int(lg.get("overrun_min") or 0) for lg in t_logs)
                        # Unbuffered overruns degrade effective on-time value proportionally
                        overrun_penalty = min(0.45, total_overrun / float(max(30, t_raw.duration_min * 2)))
                        earned_prio += float(t_raw.priority) * (1.0 - overrun_penalty)

                ontime_val_pct = 100.0 * earned_prio / float(total_prio)
                per_week_adherence[w_idx].append(adh_pct)
                per_week_ontime_val[w_idx].append(ontime_val_pct)

                if s_idx == 0:
                    rep_learned_focus[w_idx] = str(cur_profile.focus_preference or "BALANCED")
                    cur_alphas_snap: Dict[str, float] = {}
                    for ct in cur_tasks:
                        cat_u = str(ct.category or "DEADLINE").upper()
                        cur_alphas_snap[cat_u] = round(float(ct.alpha_heavy if (ct.cognitive_load or 2) >= 3 else ct.alpha_light), 3)
                    rep_learned_alphas[w_idx] = cur_alphas_snap

                # Adapt parameters from cumulative logs onto clean raw template tasks for Week w+1
                adapt_next = adapt_preferences_for_next_week(
                    profile=cur_profile,
                    next_tasks=init_tasks,
                    timeline_logs=cumulative_logs,
                    kappa=3.0,
                )
                cur_profile = adapt_next["adapted_profile"]
                cur_tasks = adapt_next["adapted_tasks"]

        weeks_summary: List[Dict[str, Any]] = []
        for w_idx in range(weeks):
            mean_adh = round(sum(per_week_adherence[w_idx]) / float(len(per_week_adherence[w_idx])), 2)
            mean_val = round(sum(per_week_ontime_val[w_idx]) / float(len(per_week_ontime_val[w_idx])), 2)
            weeks_summary.append(
                {
                    "week": w_idx + 1,
                    "adherence_pct": mean_adh,
                    "on_time_value_pct": mean_val,
                    "learned_alphas": rep_learned_alphas[w_idx],
                    "learned_focus": rep_learned_focus[w_idx],
                }
            )

        converged = bool(
            len(weeks_summary) >= 2
            and weeks_summary[-1]["adherence_pct"] >= weeks_summary[0]["adherence_pct"]
            and weeks_summary[-1]["on_time_value_pct"] > weeks_summary[0]["on_time_value_pct"]
        )
        canonical_payload = json.dumps(
            {
                "seed": base_seed,
                "weeks": weeks,
                "n_students": n_students,
                "algorithm": algorithm,
                "weeks_summary": weeks_summary,
            },
            sort_keys=True,
        )
        det_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()[:16]
        exec_ms = round((time.perf_counter() - t0) * 1000.0, 2)

        return {
            "weeks": weeks,
            "n_students": n_students,
            "seed": base_seed,
            "simulator_backend": backend_name,
            "weeks_summary": weeks_summary,
            "converged": converged,
            "determinism_hash": det_hash,
            "execution_time_ms": exec_ms,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

