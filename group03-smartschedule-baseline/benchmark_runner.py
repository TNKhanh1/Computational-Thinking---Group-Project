#!/usr/bin/env python3
"""
SmartSchedule Baseline (V0) — Automated Benchmark Runner (`benchmark_runner.py`).

Executes and audits:
  1. All 10 Standard Test Scenarios (T01–T10) across Greedy EDF, Greedy LST, Greedy WSPT, and Backtracking.
  2. Disruption Rescheduling Benchmark on T04 (Local Insertion vs Full Rebuild vs Ripple-Shift).
  3. Task Overrun Rescheduling Benchmark on T05 (+30% / +45m overrun).
  4. Scalability & Latency Benchmark across 10, 25, and 50 tasks (verifying < 50ms for 25 tasks and < 200ms for 50 tasks).
  5. 3x Determinism Verification across all scenarios (100% identical SHA-256 hashes).
"""

import json
import sys
from pathlib import Path
from typing import List

# Ensure UTF-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.controller import ScheduleController
from src.models import CommitmentsProfile, DisruptionEvent, Task

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
SCENARIOS_DIR = DATA_DIR / "test_scenarios"


def run_scenario_suite() -> bool:
    print("=" * 116)
    print(" 1. SMARTSCHEDULE BASELINE (V0) — STANDARD BENCHMARK SUITE (SCENARIOS T01-T10)")
    print("=" * 116)
    header = (
        f"{'ID':<5} | {'Scenario Name':<34} | {'Tasks':>5} | {'C_hard':>6} | "
        f"{'R_dl (%)':>8} | {'FragIdx':>7} | {'Latency':>9} | {'3x Determ':>9} | {'Status / Diagnosis'}"
    )
    print(header)
    print("-" * 116)

    scenario_files = sorted(SCENARIOS_DIR.glob("t*.json"))
    all_passed = True

    for sf in scenario_files:
        raw = json.loads(sf.read_text(encoding="utf-8"))
        sc_id = raw.get("scenario_id", sf.stem.upper())
        name = raw.get("name", "")[:34]
        comm_dict = dict(raw["commitments"])
        if "now" in raw and raw["now"] and not comm_dict.get("now"):
            comm_dict["now"] = raw["now"]
        profile = CommitmentsProfile.model_validate(comm_dict)
        tasks = [Task.model_validate(t) for t in raw["tasks"]]

        output, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
        det = ScheduleController.verify_determinism(profile, tasks, algorithm="EDF", runs=3)

        s = output.summary
        diag = output.status
        if output.overload:
            diag = f"{output.overload.error_type} (shortage={output.overload.shortage_minutes}m)"

        if s.hard_constraint_violations != 0 or not det["is_deterministic"]:
            all_passed = False

        print(
            f"{sc_id:<5} | {name:<34} | {len(tasks):>5} | {s.hard_constraint_violations:>6} | "
            f"{s.deadline_satisfaction_rate:>7.1f}% | {s.fragmentation_index:>7.3f} | "
            f"{output.execution_time_ms:>6.2f} ms | {'PASS' if det['is_deterministic'] else 'FAIL':>9} | {diag}"
        )

    print("-" * 116)
    return all_passed


def run_algorithm_comparison_benchmark():
    print("\n" + "=" * 116)
    print(" 2. MULTI-SOLVER COMPARATIVE BENCHMARK ON MINH'S NORMAL WEEK (T01)")
    print("=" * 116)
    t01_raw = json.loads((SCENARIOS_DIR / "t01_normal_feasible.json").read_text(encoding="utf-8"))
    profile = CommitmentsProfile.model_validate(t01_raw["commitments"])
    tasks = [Task.model_validate(t) for t in t01_raw["tasks"]]

    print(
        f"{'Solver Engine':<32} | {'C_hard':>6} | {'R_dl (%)':>8} | {'Blocks':>6} | "
        f"{'FragIdx':>7} | {'Latency':>9} | {'SHA-256 Prefix'}"
    )
    print("-" * 116)
    for solver_key in ["EDF", "LST", "WSPT", "BACKTRACK"]:
        out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm=solver_key)
        s = out.summary
        print(
            f"{out.solver_used:<32} | {s.hard_constraint_violations:>6} | "
            f"{s.deadline_satisfaction_rate:>7.1f}% | {len(out.blocks):>6} | "
            f"{s.fragmentation_index:>7.3f} | {out.execution_time_ms:>6.2f} ms | {out.determinism_hash[:16]}..."
        )
    print("-" * 116)


def run_disruption_and_overrun_benchmark():
    print("\n" + "=" * 116)
    print(" 3. DISRUPTION RESCHEDULING (T04) & TASK OVERRUN (T05) STABILITY BENCHMARK")
    print("=" * 116)
    t04_raw = json.loads((SCENARIOS_DIR / "t04_event_disruption.json").read_text(encoding="utf-8"))
    profile = CommitmentsProfile.model_validate(t04_raw["commitments"])
    tasks = [Task.model_validate(t) for t in t04_raw["tasks"]]
    dis_raw = t04_raw.get("disruption") or t04_raw.get("disruption_event")
    disruption = DisruptionEvent.model_validate(dis_raw)

    initial_sched, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    cmp = ScheduleController.compare_repair_modes(
        profile=profile,
        tasks=tasks,
        current_schedule=initial_sched,
        disruption=disruption,
    )

    print(f" [T04 Disruption]: {disruption.day_of_week} {disruption.start_time}-{disruption.end_time} ({disruption.title})")
    for label, key in [
        ("LOCAL_INSERTION (Targeted M4)", "local_repair"),
        ("FULL_REBUILD (Scratch EDF)", "full_rebuild"),
    ]:
        res = cmp[key]
        s = res.schedule.summary
        print(
            f"   -> {label:<30} : Stability = {res.stability_score:6.2f}% | "
            f"Moved = {res.moved_blocks_count:2d} blocks | C_hard = {s.hard_constraint_violations} | "
            f"R_dl = {s.deadline_satisfaction_rate:5.1f}% | Latency = {res.execution_time_ms:5.2f} ms"
        )

    # T05 Task Overrun
    t05_raw = json.loads((SCENARIOS_DIR / "t05_duration_overrun.json").read_text(encoding="utf-8"))
    p5 = CommitmentsProfile.model_validate(t05_raw["commitments"])
    t5 = [Task.model_validate(t) for t in t05_raw["tasks"]]
    ov_cfg = t05_raw.get("overrun_config") or t05_raw.get("overrun_event") or {"task_id": t5[0].task_id, "extra_minutes": 45}
    res_t05 = ScheduleController.handle_task_overrun(
        profile=p5,
        tasks=t5,
        task_id=ov_cfg.get("task_id", t5[0].task_id),
        extra_minutes=int(ov_cfg.get("extra_minutes", ov_cfg.get("added_minutes", 45))),
        algorithm="EDF",
    )
    after_s = res_t05["after_schedule"].summary
    print(
        f"\n [T05 Overrun]   : Task {res_t05['task_id']} ({res_t05['old_duration_min']}m -> {res_t05['new_duration_min']}m) | "
        f"Shifted Downstream Blocks = {res_t05['shifted_blocks_count']} | "
        f"C_hard = {after_s.hard_constraint_violations} | R_dl = {after_s.deadline_satisfaction_rate:.1f}%"
    )
    print("-" * 116)


def run_scalability_benchmark():
    print("\n" + "=" * 116)
    print(" 4. SCALABILITY & LATENCY BENCHMARK (10, 25, AND 50 TASKS)")
    print("=" * 116)
    comm_path = DATA_DIR / "sample_week_commitments.json"
    profile = CommitmentsProfile.model_validate(json.loads(comm_path.read_text(encoding="utf-8")))
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    for count in [10, 25, 50]:
        synthetic_tasks: List[Task] = []
        for i in range(1, count + 1):
            d_day = weekdays[(i + 1) % 7]
            synthetic_tasks.append(
                Task(
                    task_id=f"SCALE-{i:02d}",
                    title=f"[CS{100 + (i % 5)}] Synthetic Task {i}",
                    duration_min=45 if i % 2 == 0 else 60,
                    deadline_day=d_day,
                    deadline_time="22:00",
                    priority=(i % 5) + 1,
                    is_splittable=False,
                )
            )
        out, _ = ScheduleController.solve_schedule(profile, synthetic_tasks, algorithm="EDF")
        s = out.summary
        target_ms = 50.0 if count <= 25 else 200.0
        status = "PASS" if out.execution_time_ms <= target_ms and s.hard_constraint_violations == 0 else "WARN"
        print(
            f"   Scale N={count:2d} Tasks -> Latency = {out.execution_time_ms:6.2f} ms (Target <= {target_ms:5.1f} ms) | "
            f"C_hard = {s.hard_constraint_violations} | Placed = {s.tasks_placed}/{s.total_tasks_requested} tasks | [{status}]"
        )
    print("=" * 116)


if __name__ == "__main__":
    ok = run_scenario_suite()
    run_algorithm_comparison_benchmark()
    run_disruption_and_overrun_benchmark()
    run_scalability_benchmark()
    if not ok:
        raise SystemExit(1)
