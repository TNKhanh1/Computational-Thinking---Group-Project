#!/usr/bin/env python3
"""
SmartSchedule Baseline (V0) — Command-Line Execution & Verification Runner.

Supports:
  - Running Minh's Week or Lan's Week presets (`--preset minh|lan`)
  - Running any of the 10 test scenarios T01–T10 (`--scenario T01..T10`)
  - Selecting solver (`--solver EDF|LST|WSPT|BACKTRACK`)
  - Running 3x Determinism Verification (`--check-determinism`)
  - Exporting output to JSON, CSV, or RFC 5545 iCalendar `.ics`
"""

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.controller import ScheduleController
from src.exporter import export_to_csv, export_to_ics, export_to_json
from src.models import CommitmentsProfile, Task

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
SCENARIOS_DIR = DATA_DIR / "test_scenarios"


def _parse_tasks_json(raw_data):
    if isinstance(raw_data, list):
        return [Task.model_validate(t) for t in raw_data]
    return [Task.model_validate(t) for t in raw_data.get("tasks", [])]


def load_preset_data(preset_name: str):
    key = preset_name.lower()
    if key == "empty":
        profile = CommitmentsProfile(
            student_id="EMPTY_SCHEDULE",
            planning_week_start="2026-11-02T00:00:00+07:00",
        )
        return profile, [], None
    elif key == "lan":
        comm_path = DATA_DIR / "lan_week_commitments.json"
        tasks_path = DATA_DIR / "lan_week_tasks.json"
    else:
        comm_path = DATA_DIR / "sample_week_commitments.json"
        tasks_path = DATA_DIR / "sample_week_tasks.json"

    profile = CommitmentsProfile.model_validate(json.loads(comm_path.read_text(encoding="utf-8")))
    tasks = _parse_tasks_json(json.loads(tasks_path.read_text(encoding="utf-8")))
    return profile, tasks, None


def load_scenario_data(scenario_id: str):
    target = scenario_id.upper()
    for p in sorted(SCENARIOS_DIR.glob("*.json")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw.get("scenario_id", "").upper() == target or p.stem.upper().startswith(target):
            comm_dict = dict(raw["commitments"])
            if "now" in raw and raw["now"] and not comm_dict.get("now"):
                comm_dict["now"] = raw["now"]
            profile = CommitmentsProfile.model_validate(comm_dict)
            tasks = _parse_tasks_json(raw["tasks"])
            return profile, tasks, raw
    raise FileNotFoundError(f"Scenario '{scenario_id}' not found in {SCENARIOS_DIR}")


def print_schedule_report(output, label: str):
    s = output.summary
    print("=" * 92)
    print(f" SmartSchedule Baseline (V0) — {label}")
    print("=" * 92)
    print(f" Status                     : {output.status}")
    print(f" Solver Engine              : {output.solver_used}")
    print(f" Hard Violations (C_hard)   : {s.hard_constraint_violations} (MUST BE 0)")
    print(f" Deadline Satisfaction Rate : {s.deadline_satisfaction_rate:.2f}% ({s.tasks_placed}/{s.total_tasks_requested} tasks, {s.parts_placed}/{s.parts_total} chunks)")
    print(f" Fragmentation Index        : {s.fragmentation_index:.4f}")
    print(f" Execution Latency          : {output.execution_time_ms:.3f} ms")
    print(f" 672-Slot Breakdown         : SLEEP={s.sleep_slots} | OCCUPIED={s.occupied_slots} | BLOCK={s.block_slots} | FREE={s.free_slots_remaining}")
    print(f" Determinism SHA-256        : {output.determinism_hash}")
    print("-" * 92)
    print(f" Placed Study Blocks ({len(output.blocks)} blocks):")
    for b in output.blocks:
        print(
            f"   [{b.block_id:10s}] {b.day:9s} {b.start_time}-{b.end_time} "
            f"(Slots {b.start_slot:3d}..{b.end_slot:3d}, {b.duration_min:3d}m) | {b.title} ({b.chunk_index}/{b.total_chunks})"
        )

    if output.unplaced_tasks:
        print("-" * 92)
        print(f" Unplaced / Overload Diagnosis ({len(output.unplaced_tasks)} tasks):")
        for u in output.unplaced_tasks:
            print(f"   ! [{u.get('task_id')}] {u.get('title')} ({u.get('duration_min')}m) -> {u.get('reason')}")
    if output.overload:
        ov = output.overload
        print(
            f"   [OVERLOAD REPORT] Type={ov.error_type} | Free={ov.total_free_minutes_available}m | "
            f"Planned={ov.total_planned_work_minutes}m | Shortage={ov.shortage_minutes}m"
        )
    print("=" * 92)


def main():
    parser = argparse.ArgumentParser(description="SmartSchedule Baseline V0 CLI Runner")
    parser.add_argument("--preset", choices=["minh", "lan", "empty"], default="minh", help="Preset dataset to load (minh, lan, or empty)")
    parser.add_argument("--scenario", type=str, default=None, help="Run a specific scenario ID (T01..T10)")
    parser.add_argument("--solver", choices=["EDF", "LST", "WSPT", "BACKTRACK"], default="EDF", help="Solver engine")
    parser.add_argument("--check-determinism", action="store_true", help="Run 3x determinism verification")
    parser.add_argument("--export-json", type=str, default=None, help="File path to export JSON schedule")
    parser.add_argument("--export-csv", type=str, default=None, help="File path to export CSV schedule")
    parser.add_argument("--export-ics", type=str, default=None, help="File path to export .ics calendar")

    args = parser.parse_args()

    if args.scenario:
        profile, tasks, meta = load_scenario_data(args.scenario)
        label = f"Scenario {meta.get('scenario_id')}: {meta.get('name')}"
    else:
        profile, tasks, meta = load_preset_data(args.preset)
        label = f"Preset '{args.preset.upper()}' ({profile.student_id})"

    output, _ = ScheduleController.solve_schedule(
        profile=profile,
        tasks=tasks,
        algorithm=args.solver,
    )
    print_schedule_report(output, label)

    if args.check_determinism:
        det = ScheduleController.verify_determinism(
            profile=profile,
            tasks=tasks,
            algorithm=args.solver,
            runs=3,
        )
        print(
            f"[Determinism Check] 3x Runs Identical={det['is_deterministic']} | "
            f"SHA-256={det['unique_hash']} | Latencies={det['latencies_ms']} ms"
        )
        if not det["is_deterministic"]:
            sys.exit(1)

    if args.export_json:
        Path(args.export_json).write_text(export_to_json(output), encoding="utf-8")
        print(f"Exported JSON schedule to {args.export_json}")
    if args.export_csv:
        Path(args.export_csv).write_text(export_to_csv(output), encoding="utf-8")
        print(f"Exported CSV schedule to {args.export_csv}")
    if args.export_ics:
        Path(args.export_ics).write_text(export_to_ics(output, profile=profile), encoding="utf-8")
        print(f"Exported iCalendar (.ics) to {args.export_ics}")


if __name__ == "__main__":
    main()
