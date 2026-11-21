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

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response

from src.calibration import compute_ewma_calibration, format_pilot_markdown_report
from src.controller import ScheduleController
from src.exporter import export_to_csv, export_to_ics, export_to_json
from src.ics_importer import parse_ics_calendar
from src.models import (
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
from src.nl_parser import parse_natural_language_task
from src.solvers.local_repair import LocalRepairEngine
from src.storage import (
    append_completion_log,
    create_user,
    delete_workspace_state,
    get_user_by_id,
    list_completion_logs,
    load_workspace_state,
    save_workspace_state,
    verify_user_credentials,
)
from web.auth import (
    extract_bearer_claims,
    get_allowed_origins,
    issue_access_token,
    resolve_workspace_id,
)
from web.health_v21 import evaluate_schedule_v21
from web.v3_services import (
    compute_solver_weights,
    get_available_solvers,
    get_test_suites_catalog,
    load_test_suite,
    parse_ics_content,
    run_benchmark_all,
)

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
    """Load any preset, T01-T10 scenario, or seeded R1-R6 Testing_System regime."""
    source = str(payload.get("source") or "preset")
    suite_id = str(payload.get("id") or "")
    seed = int(payload.get("seed") or 42)
    try:
        presets_dict = get_presets()["presets"]
        return load_test_suite(
            source=source,
            suite_id=suite_id,
            seed=seed,
            presets_dict=presets_dict,
            scenarios_dir=SCENARIOS_DIR,
        )
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
        profile, tasks, algorithm, pinned_blocks = _extract_profile_and_tasks(payload)
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
        profile, tasks, _, pinned_blocks = _extract_profile_and_tasks(payload)
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

