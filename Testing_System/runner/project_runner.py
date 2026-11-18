"""
Middle Step (`Run Project`): executes SmartSchedule cleanly across all 5 solvers
plus Regime 6 repairs/overruns via both Direct Controller execution and isolated HTTP API E2E.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from schedule_testing_system.generator.input_generator import GeneratedCaseBundle
from schedule_testing_system.sut_adapter import (
    FIVE_SOLVERS,
    CommitmentsProfile,
    DisruptionEvent,
    FixedEvent,
    LocalRepairEngine,
    RepairOutput,
    ScheduleOutput,
    build_api_payload,
    create_isolated_http_client,
    day_time_to_slot,
    preprocess_tasks,
    run_overrun_direct,
    run_repair_direct,
    run_solver_direct,
)


@dataclass
class RepairExecutionRecord:
    mode_label: str
    disruption_profile: CommitmentsProfile
    baseline_schedule: ScheduleOutput
    repaired_schedule: ScheduleOutput
    repair_now_slot: int
    disruption_span: Tuple[int, int]
    is_overrun_context: bool = False
    check_pinned_blocks: bool = True
    completion_logs: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ProjectRunBundle:
    execution_mode: str
    solver_outputs: Dict[str, ScheduleOutput]
    repair_records: Dict[str, RepairExecutionRecord] = field(default_factory=dict)


def _augmented_profile_for_disruption(
    profile: CommitmentsProfile, disruption: DisruptionEvent
) -> Tuple[CommitmentsProfile, int, Tuple[int, int]]:
    d_start, d_end, now_slot = LocalRepairEngine.resolve_disruption_slots(
        disruption, week_start_iso=profile.planning_week_start
    )
    prof = profile.model_copy(deep=True)
    prof.fixed_events.append(
        FixedEvent(
            event_id=disruption.event_id,
            title=disruption.title,
            day_of_week=disruption.day_of_week,
            start_time=disruption.start_time,
            end_time=disruption.end_time,
            category="DISRUPTION_EVENT",
        )
    )
    return prof, now_slot, (d_start, d_end)


def execute_project_direct(
    bundle: GeneratedCaseBundle,
    solvers: Tuple[str, ...] = FIVE_SOLVERS,
) -> ProjectRunBundle:
    """Execute SmartSchedule directly through the controller/engine without HTTP overhead."""
    solver_outputs: Dict[str, ScheduleOutput] = {}
    for solver_name in solvers:
        out, _ = run_solver_direct(
            profile=bundle.profile,
            tasks=bundle.tasks,
            algorithm=solver_name,
            pinned_blocks=bundle.pinned_blocks,
        )
        solver_outputs[solver_name] = out

    repair_records: Dict[str, RepairExecutionRecord] = {}
    if bundle.regime6_suite is not None:
        suite = bundle.regime6_suite
        base_algo = "SCORED_GREEDY" if "SCORED_GREEDY" in solver_outputs else solvers[0]
        base_sched = solver_outputs[base_algo]

        # Dynamically aim Level A disruption directly at an unpinned block if possible so it genuinely perturbs
        disr_a = suite.level_a_single_disruption.model_copy(deep=True)
        hit_candidates = [
            b for b in sorted(base_sched.blocks, key=lambda x: x.start_slot)
            if b.state not in ("PINNED", "DONE") and (b.end_slot - b.start_slot) >= 2
        ]
        if hit_candidates:
            target_b = hit_candidates[0]
            disr_a.day_of_week = target_b.day
            disr_a.start_time = target_b.start_time
            disr_a.end_time = target_b.end_time
            disr_a.now_day = target_b.day
            disr_a.now_time = "07:00" if target_b.start_slot % 96 >= 32 else target_b.start_time

        prof_a, now_a, span_a = _augmented_profile_for_disruption(bundle.profile, disr_a)
        for mode in ("LOCAL_INSERTION", "RIPPLE_SHIFT", "FULL_REBUILD"):
            rep: RepairOutput = run_repair_direct(
                profile=bundle.profile,
                tasks=bundle.tasks,
                baseline_schedule=base_sched,
                disruption=disr_a,
                mode=mode,
                algorithm=base_algo,
            )
            repair_records[f"DISRUPTION_LVL_A::{mode}"] = RepairExecutionRecord(
                mode_label=f"DISRUPTION_LVL_A::{mode}",
                disruption_profile=prof_a,
                baseline_schedule=base_sched,
                repaired_schedule=rep.schedule,
                repair_now_slot=now_a,
                disruption_span=span_a,
                is_overrun_context=False,
            )

        # Level B: Task duration overrun (+50% on target prerequisite task)
        overrun_rep = run_overrun_direct(
            profile=bundle.profile,
            tasks=bundle.tasks,
            baseline_schedule=base_sched,
            target_task_id=suite.level_b_overrun_task_id,
            overrun_pct=suite.level_b_overrun_pct,
        )
        repair_records["OVERRUN_LVL_B::LOCAL_INSERTION"] = RepairExecutionRecord(
            mode_label="OVERRUN_LVL_B::LOCAL_INSERTION",
            disruption_profile=bundle.profile.model_copy(deep=True),
            baseline_schedule=base_sched,
            repaired_schedule=overrun_rep.schedule,
            repair_now_slot=0,
            disruption_span=(-1, -1),
            is_overrun_context=True,
        )

        # Level C: Compound disruption on FULL_REBUILD vs LOCAL_INSERTION
        disr_c = suite.level_c_compound_disruption
        prof_c, now_c, span_c = _augmented_profile_for_disruption(bundle.profile, disr_c)
        for mode in ("LOCAL_INSERTION", "FULL_REBUILD"):
            rep_c = run_repair_direct(
                profile=bundle.profile,
                tasks=bundle.tasks,
                baseline_schedule=base_sched,
                disruption=disr_c,
                mode=mode,
                algorithm=base_algo,
            )
            repair_records[f"DISRUPTION_LVL_C::{mode}"] = RepairExecutionRecord(
                mode_label=f"DISRUPTION_LVL_C::{mode}",
                disruption_profile=prof_c,
                baseline_schedule=base_sched,
                repaired_schedule=rep_c.schedule,
                repair_now_slot=now_c,
                disruption_span=span_c,
                is_overrun_context=False,
            )

    return ProjectRunBundle(
        execution_mode="DIRECT_CONTROLLER",
        solver_outputs=solver_outputs,
        repair_records=repair_records,
    )


def execute_project_http_e2e(
    bundle: GeneratedCaseBundle,
    solvers: Tuple[str, ...] = ("EDF", "SCORED_GREEDY", "BACKTRACK"),
    db_path: Optional[str] = None,
    transport: str = "in_process",
) -> ProjectRunBundle:
    """
    Execute SmartSchedule through real FastAPI endpoints (`/api/plan`, `/api/repair`, `/api/progress`, `/api/tasks/complete`)
    using an isolated SQLite DB so baseline workspace state stays untouched.
    """
    client = create_isolated_http_client(db_path=db_path, transport=transport)
    solver_outputs: Dict[str, ScheduleOutput] = {}

    for solver_name in solvers:
        payload = build_api_payload(bundle.profile, bundle.tasks, solver_name, bundle.pinned_blocks)
        resp = client.post("/api/plan", json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"POST /api/plan failed ({solver_name}): {resp.status_code} {resp.text}")
        solver_outputs[solver_name] = ScheduleOutput.model_validate(resp.json())

    repair_records: Dict[str, RepairExecutionRecord] = {}
    if bundle.regime6_suite is not None:
        suite = bundle.regime6_suite
        base_algo = "SCORED_GREEDY" if "SCORED_GREEDY" in solver_outputs else solvers[0]
        base_sched = solver_outputs[base_algo]

        disr_a = suite.level_a_single_disruption.model_copy(deep=True)
        hit_candidates = [
            b for b in sorted(base_sched.blocks, key=lambda x: x.start_slot)
            if b.state not in ("PINNED", "DONE") and (b.end_slot - b.start_slot) >= 2
        ]
        if hit_candidates:
            target_b = hit_candidates[0]
            disr_a.day_of_week = target_b.day
            disr_a.start_time = target_b.start_time
            disr_a.end_time = target_b.end_time
            disr_a.now_day = target_b.day
            disr_a.now_time = "07:00" if target_b.start_slot % 96 >= 32 else target_b.start_time

        prof_a, now_a, span_a = _augmented_profile_for_disruption(bundle.profile, disr_a)
        for mode in ("LOCAL_INSERTION", "FULL_REBUILD"):
            rep_payload = build_api_payload(bundle.profile, bundle.tasks, base_algo, bundle.pinned_blocks)
            rep_payload["schedule"] = base_sched.model_dump(mode="json")
            rep_payload["disruption"] = disr_a.model_dump(mode="json")
            rep_payload["mode"] = mode
            r_resp = client.post("/api/repair", json=rep_payload)
            if r_resp.status_code != 200:
                raise RuntimeError(f"POST /api/repair ({mode}) failed: {r_resp.status_code} {r_resp.text}")
            rep_out = RepairOutput.model_validate(r_resp.json())
            repair_records[f"DISRUPTION_LVL_A::{mode}"] = RepairExecutionRecord(
                mode_label=f"DISRUPTION_LVL_A::{mode}",
                disruption_profile=prof_a,
                baseline_schedule=base_sched,
                repaired_schedule=rep_out.schedule,
                repair_now_slot=now_a,
                disruption_span=span_a,
            )

        # Call /api/progress (overrun) and /api/tasks/complete + /api/tasks/completions
        ws_id = f"http_e2e_{bundle.metadata.seed}"
        prog_payload = build_api_payload(bundle.profile, bundle.tasks, base_algo, bundle.pinned_blocks)
        prog_payload["task_id"] = suite.level_b_overrun_task_id
        prog_payload["overrun_pct"] = suite.level_b_overrun_pct
        p_resp = client.post("/api/progress", json=prog_payload)
        if p_resp.status_code != 200:
            raise RuntimeError(f"POST /api/progress failed: {p_resp.status_code} {p_resp.text}")
        p_json = p_resp.json()
        before_ov = ScheduleOutput.model_validate(p_json["before_schedule"])
        after_ov = ScheduleOutput.model_validate(p_json["after_schedule"])

        target_raw = next((t for t in bundle.tasks if t.task_id == suite.level_b_overrun_task_id), bundle.tasks[0])
        comp_payload = {
            "workspace_id": ws_id,
            "task_id": target_raw.task_id,
            "category": target_raw.category,
            "estimated_min": target_raw.duration_min,
            "actual_duration_min": int(round(target_raw.duration_min * (1.0 + suite.level_b_overrun_pct / 100.0))),
            "completed": True,
        }
        c_resp = client.post("/api/tasks/complete", json=comp_payload)
        if c_resp.status_code != 200:
            raise RuntimeError(f"POST /api/tasks/complete failed: {c_resp.status_code} {c_resp.text}")
        logs_resp = client.get("/api/tasks/completions", params={"workspace_id": ws_id})
        logs = logs_resp.json().get("completions", []) if logs_resp.status_code == 200 else []

        repair_records["OVERRUN_LVL_B::HTTP_PROGRESS"] = RepairExecutionRecord(
            mode_label="OVERRUN_LVL_B::HTTP_PROGRESS",
            disruption_profile=bundle.profile.model_copy(deep=True),
            baseline_schedule=before_ov,
            repaired_schedule=after_ov,
            repair_now_slot=0,
            disruption_span=(-1, -1),
            is_overrun_context=True,
            check_pinned_blocks=False,  # Baseline POST /api/progress discards pinned_blocks when resolving before_schedule
            completion_logs=logs,
        )

    return ProjectRunBundle(
        execution_mode="HTTP_E2E",
        solver_outputs=solver_outputs,
        repair_records=repair_records,
    )

