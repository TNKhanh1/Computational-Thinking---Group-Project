"""
Empirical Hyperparameter Tuning & Shock Stress Test for Alpha (`α`)
(Presentation2 Slide 17 / Proposal §6 & §8).

Performs a 1D Grid Search over α ∈ [1.00, 1.60] (step 0.05) across feasible
student benchmark weeks (`sample_week`, `lan_week`, `T01`, `T02`, `T08`, `T09`),
plus Planning Fallacy overrun stress tests (+25% and +50% actual duration shocks).

Outputs:
  - Detailed console table for Slide 17 empirical calibration
  - JSON summary (`data/alpha_grid_calibration.json`) when `--save-json` is passed
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.config import ALPHA_GRID_MAX, ALPHA_GRID_MIN, ALPHA_GRID_STEP, ALPHA_HEAVY_DEFAULT, ALPHA_LIGHT_DEFAULT
from src.controller import ScheduleController
from src.estimate_buffer import planned_duration_roundup_15
from src.models import CommitmentsProfile, Task

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"


def _load_calibration_benchmarks() -> List[Tuple[str, CommitmentsProfile, List[Task]]]:
    benchmarks: List[Tuple[str, CommitmentsProfile, List[Task]]] = []

    def _add(name: str, prof_raw: dict, tasks_raw: Any) -> None:
        items = tasks_raw if isinstance(tasks_raw, list) else tasks_raw.get("tasks", [])
        benchmarks.append(
            (
                name,
                CommitmentsProfile.model_validate(prof_raw),
                [Task.model_validate(t) for t in items],
            )
        )

    _add(
        "MinhWeek",
        json.loads((DATA_DIR / "sample_week_commitments.json").read_text(encoding="utf-8")),
        json.loads((DATA_DIR / "sample_week_tasks.json").read_text(encoding="utf-8")),
    )
    _add(
        "LanWeek",
        json.loads((DATA_DIR / "lan_week_commitments.json").read_text(encoding="utf-8")),
        json.loads((DATA_DIR / "lan_week_tasks.json").read_text(encoding="utf-8")),
    )
    for fname, label in [
        ("t01_normal_feasible.json", "T01_Normal"),
        ("t02_overlapping_deadlines.json", "T02_Overlap"),
        ("t05_duration_overrun.json", "T05_Overrun"),
        ("t08_unclear_priority.json", "T08_Unclear"),
        ("t09_circadian_comparison.json", "T09_Circadian"),
    ]:
        sc = json.loads((DATA_DIR / "test_scenarios" / fname).read_text(encoding="utf-8"))
        _add(label, sc["commitments"], sc["tasks"])

    return benchmarks


def _load_tight_stress_benchmarks() -> List[Tuple[str, CommitmentsProfile, List[Task]]]:
    """
    Build deterministic tight high-utilization student weeks (rho ~ 0.65-0.75 at alpha=1.0)
    that remain 100% feasible at recommended alpha (1.20/1.35) but expose the Over-Buffering
    Cliff when alpha >= 1.70 (Presentation2 Slide 17 / Q1.3).
    """
    lan_prof = CommitmentsProfile.model_validate(
        json.loads((DATA_DIR / "lan_week_commitments.json").read_text(encoding="utf-8"))
    )
    minh_prof = CommitmentsProfile.model_validate(
        json.loads((DATA_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    )

    # Scenario A: Tight Mon-Tue cluster on Lan's busy work+class schedule (~14.5h free before Tue 22:00)
    # Raw demand = 540m (9h): fits 100% at alpha=1.20/1.35 (~11.5h), overflows free slots at alpha>=1.70 (~15.5h+)
    tight_midweek_tasks = [
        Task(
            task_id="TIGHT-A1",
            title="Midterm Algorithms Review",
            category="EXAM_PREP",
            duration_min=180,
            deadline_day="Monday",
            deadline_time="22:00",
            priority=5,
            cognitive_load=3,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
        Task(
            task_id="TIGHT-A2",
            title="OS Kernel Lab Report",
            category="CODING",
            duration_min=180,
            deadline_day="Tuesday",
            deadline_time="21:00",
            priority=5,
            cognitive_load=3,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
        Task(
            task_id="TIGHT-A3",
            title="Database Schema Assignment",
            category="ASSIGNMENT",
            duration_min=150,
            deadline_day="Tuesday",
            deadline_time="22:00",
            priority=4,
            cognitive_load=2,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
        Task(
            task_id="TIGHT-A4",
            title="Linear Algebra Problem Set",
            category="STUDY",
            duration_min=180,
            deadline_day="Wednesday",
            deadline_time="21:00",
            priority=4,
            cognitive_load=2,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
        Task(
            task_id="TIGHT-A5",
            title="Technical Writing Draft",
            category="WRITING",
            duration_min=180,
            deadline_day="Wednesday",
            deadline_time="22:00",
            priority=3,
            cognitive_load=1,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
    ]

    # Scenario B: High-utilization Mon-Wed crunch on Minh's profile
    # Raw demand = 1230m before Wed 22:00: fits 100% at alpha=1.20/1.35, overflows at alpha>=1.70
    tight_fullweek_tasks = [
        Task(
            task_id="TIGHT-B1",
            title="Capstone Architecture Design",
            category="PROJECT",
            duration_min=270,
            deadline_day="Monday",
            deadline_time="22:00",
            priority=5,
            cognitive_load=3,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
        Task(
            task_id="TIGHT-B2",
            title="ML Pipeline Implementation",
            category="CODING",
            duration_min=300,
            deadline_day="Tuesday",
            deadline_time="22:00",
            priority=5,
            cognitive_load=3,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
        Task(
            task_id="TIGHT-B3",
            title="Probability Quiz Prep",
            category="EXAM_PREP",
            duration_min=240,
            deadline_day="Wednesday",
            deadline_time="22:00",
            priority=4,
            cognitive_load=3,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
        Task(
            task_id="TIGHT-B4",
            title="Computer Networks Lab",
            category="LAB",
            duration_min=240,
            deadline_day="Wednesday",
            deadline_time="22:00",
            priority=4,
            cognitive_load=2,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
        Task(
            task_id="TIGHT-B5",
            title="Ethics Reading Summary",
            category="READING",
            duration_min=180,
            deadline_day="Thursday",
            deadline_time="22:00",
            priority=3,
            cognitive_load=1,
            is_splittable=True,
            min_chunk_min=45,
            max_chunk_min=90,
        ),
    ]

    return [
        ("TightStress_LanMidweek", lan_prof, tight_midweek_tasks),
        ("TightStress_MinhCluster", minh_prof, tight_fullweek_tasks),
    ]


def evaluate_alpha_point(
    alpha_light: float,
    alpha_heavy: float,
    benchmarks: List[Tuple[str, CommitmentsProfile, List[Task]]],
    algorithm: str = "SCORED_GREEDY",
) -> Dict[str, Any]:
    hard_violations = 0
    dl_rates: List[float] = []
    frags: List[float] = []
    ratings: List[float] = []
    slack_mins: List[float] = []
    shock25_zero_repair_rates: List[float] = []
    shock25_sim_dl_rates: List[float] = []
    shock50_sim_dl_rates: List[float] = []

    for _name, base_prof, base_tasks in benchmarks:
        prof = base_prof.model_copy(deep=True)
        prof.buffer_mode = "COGNITIVE_LOAD"
        prof.alpha_light = alpha_light
        prof.alpha_heavy = alpha_heavy

        tasks = [t.model_copy(deep=True) for t in base_tasks]
        buffered_tasks = ScheduleController.apply_estimate_buffer(prof, tasks)
        out, _ = ScheduleController.solve_schedule(prof, buffered_tasks, algorithm=algorithm)

        hard_violations += out.summary.hard_constraint_violations
        dl_rates.append(out.summary.deadline_satisfaction_rate)
        frags.append(out.summary.fragmentation_index)
        ratings.append(out.summary.experience_rating)
        slack_mins.append(float(out.summary.free_slots_remaining * 15))

        # Check buffer absorption & simultaneous +25% / +50% Planning Fallacy shocks
        # Any unabsorbed extra minutes across originally placed academic tasks must be repaired in place
        placed_ids = {b.task_id for b in out.blocks}
        academic = [
            (raw_t, buf_t)
            for raw_t, buf_t in zip(tasks, buffered_tasks)
            if raw_t.task_id in placed_ids and raw_t.category != "HABIT"
        ]
        if not academic:
            academic = list(zip(tasks, buffered_tasks))

        absorbed_count_25 = 0
        # Simulate simultaneous overrun: keep original placements as 'pre-shock' capacity;
        # unabsorbed overruns force full re-solve with actual durations from mid-week (or single overrun repair)
        tasks_25: List[Task] = []
        tasks_50: List[Task] = []
        for raw_t, buf_t in zip(tasks, buffered_tasks):
            planned_m = buf_t.get_planned_duration_min()
            if raw_t.category == "HABIT":
                tasks_25.append(buf_t.model_copy(deep=True))
                tasks_50.append(buf_t.model_copy(deep=True))
                continue

            req_25 = planned_duration_roundup_15(raw_t.duration_min, 1.25)
            req_50 = planned_duration_roundup_15(raw_t.duration_min, 1.50)

            if raw_t.task_id in placed_ids and planned_m >= req_25:
                absorbed_count_25 += 1

            # Actual execution duration needed under shock is max(planned_m, req_s)
            t25 = raw_t.model_copy(
                update={"duration_min": max(planned_m, req_25), "buffer_mode": "HABIT", "buffer_multiplier": 1.0},
                deep=True,
            )
            t50 = raw_t.model_copy(
                update={"duration_min": max(planned_m, req_50), "buffer_mode": "HABIT", "buffer_multiplier": 1.0},
                deep=True,
            )
            tasks_25.append(t25)
            tasks_50.append(t50)

        shock25_zero_repair_rates.append(100.0 * absorbed_count_25 / max(1, len(academic)))

        # Evaluate schedule feasibility under +25% and +50% real durations WITHOUT changing profile alpha
        prof_shock = prof.model_copy(update={"buffer_mode": "HABIT", "estimate_habit": None}, deep=True)
        # Keep original academic placements count vs shocked capacity: also simulate cascading local overrun on bottleneck task
        target_raw, target_buf = max(academic, key=lambda pair: (pair[0].priority, pair[0].duration_min))
        short_25 = max(0, planned_duration_roundup_15(target_raw.duration_min, 1.25) - target_buf.get_planned_duration_min())
        short_50 = max(0, planned_duration_roundup_15(target_raw.duration_min, 1.50) - target_buf.get_planned_duration_min())

        # If base schedule couldn't even place a task due to over-inflation, base R_dl already reflects false overload;
        # additionally check cascading simultaneous shock survival when schedule already committed its slots
        out_25, _ = ScheduleController.solve_schedule(prof_shock, tasks_25, algorithm=algorithm)
        out_50, _ = ScheduleController.solve_schedule(prof_shock, tasks_50, algorithm=algorithm)

        # Blend direct overrun repair on largest task with simultaneous shock survival
        if short_25 == 0:
            dl_25 = out.summary.deadline_satisfaction_rate
        else:
            res25 = ScheduleController.handle_task_overrun(
                profile=prof,
                tasks=buffered_tasks,
                task_id=target_raw.task_id,
                extra_minutes=short_25,
                algorithm="EDF" if algorithm == "SCORED_GREEDY" else algorithm,
            )
            dl_25 = min(out_25.summary.deadline_satisfaction_rate, res25["after_schedule"].summary.deadline_satisfaction_rate)
        if short_50 == 0:
            dl_50 = out.summary.deadline_satisfaction_rate
        else:
            res50 = ScheduleController.handle_task_overrun(
                profile=prof,
                tasks=buffered_tasks,
                task_id=target_raw.task_id,
                extra_minutes=short_50,
                algorithm="EDF" if algorithm == "SCORED_GREEDY" else algorithm,
            )
            dl_50 = min(out_50.summary.deadline_satisfaction_rate, res50["after_schedule"].summary.deadline_satisfaction_rate)

        shock25_sim_dl_rates.append(dl_25)
        shock50_sim_dl_rates.append(dl_50)

    n = float(len(benchmarks))
    avg_dl = sum(dl_rates) / n
    avg_frag = sum(frags) / n
    avg_rating = sum(ratings) / n
    avg_s25_zero = sum(shock25_zero_repair_rates) / n
    avg_s25_dl = sum(shock25_sim_dl_rates) / n
    avg_s50_dl = sum(shock50_sim_dl_rates) / n

    # Balanced calibration objective: maximize base feasibility + shock survival + zero-repair absorption,
    # while penalizing over-buffering burnout (Experience Rating) & fragmentation
    composite = (
        0.35 * avg_dl
        + 0.25 * avg_s25_dl
        + 0.20 * avg_s50_dl
        + 0.20 * avg_s25_zero
        - 4.0 * max(0.0, avg_rating - 2.0)
        - 2.0 * avg_frag
        - 100.0 * hard_violations
    )

    return {
        "alpha_light": round(alpha_light, 2),
        "alpha_heavy": round(alpha_heavy, 2),
        "hard_violations": hard_violations,
        "avg_deadline_rate": round(avg_dl, 2),
        "avg_shock25_absorbed_no_repair_pct": round(avg_s25_zero, 1),
        "avg_shock25_post_dl_rate": round(avg_s25_dl, 2),
        "avg_shock50_post_dl_rate": round(avg_s50_dl, 2),
        "avg_fragmentation": round(avg_frag, 2),
        "avg_experience_rating": round(avg_rating, 2),
        "avg_free_min": round(sum(slack_mins) / n, 0),
        "composite_score": round(composite, 2),
    }


def run_grid_search(algorithm: str = "SCORED_GREEDY") -> Dict[str, Any]:
    benchmarks = _load_calibration_benchmarks()
    grid_rows: List[Dict[str, Any]] = []

    val = ALPHA_GRID_MIN
    while val <= ALPHA_GRID_MAX + 1e-9:
        a = round(val, 2)
        grid_rows.append(evaluate_alpha_point(a, a, benchmarks, algorithm=algorithm))
        val += ALPHA_GRID_STEP

    dual_default = evaluate_alpha_point(
        ALPHA_LIGHT_DEFAULT, ALPHA_HEAVY_DEFAULT, benchmarks, algorithm=algorithm
    )

    best_1d = max(grid_rows, key=lambda r: (r["composite_score"], -abs(r["alpha_light"] - 1.25)))
    return {
        "algorithm": algorithm,
        "scenarios": [b[0] for b in benchmarks],
        "grid_range": [ALPHA_GRID_MIN, ALPHA_GRID_MAX, ALPHA_GRID_STEP],
        "grid_results": grid_rows,
        "best_1d": best_1d,
        "recommended_asym_default": dual_default,
    }


def run_extreme_tight_stress(
    algorithm: str = "SCORED_GREEDY",
    alphas: List[float] | None = None,
) -> Dict[str, Any]:
    """
    Evaluate extreme alpha values (including alpha >= 1.70 up to 2.00) on tight high-utilization
    weeks to quantify the Over-Buffering Cliff (false infeasibility caused purely by excess buffer).
    """
    stress_benchmarks = _load_tight_stress_benchmarks()
    test_alphas = alphas or [1.00, 1.20, 1.35, 1.50, 1.60, 1.70, 1.80, 1.90, 2.00]
    base_row = evaluate_alpha_point(1.00, 1.00, stress_benchmarks, algorithm=algorithm)
    base_dl = float(base_row["avg_deadline_rate"])

    rows: List[Dict[str, Any]] = []
    for a in test_alphas:
        r = evaluate_alpha_point(a, a, stress_benchmarks, algorithm=algorithm)
        r["over_buffer_infeasible_rate_pct"] = round(max(0.0, base_dl - float(r["avg_deadline_rate"])), 2)
        rows.append(r)

    asym_row = evaluate_alpha_point(
        ALPHA_LIGHT_DEFAULT, ALPHA_HEAVY_DEFAULT, stress_benchmarks, algorithm=algorithm
    )
    asym_row["over_buffer_infeasible_rate_pct"] = round(
        max(0.0, base_dl - float(asym_row["avg_deadline_rate"])), 2
    )

    cliff_points = [r for r in rows if r["alpha_light"] >= 1.70]
    max_cliff_drop = max((r["over_buffer_infeasible_rate_pct"] for r in cliff_points), default=0.0)

    return {
        "algorithm": algorithm,
        "scenarios": [b[0] for b in stress_benchmarks],
        "baseline_alpha_1_00_dl_rate": base_dl,
        "recommended_asym_default": asym_row,
        "stress_results": rows,
        "over_buffering_cliff_detected": max_cliff_drop > 0.0,
        "max_cliff_dl_drop_pct": round(max_cliff_drop, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="1D Grid Search calibration for Planning Fallacy α")
    parser.add_argument("--algorithm", default="SCORED_GREEDY", help="Solver algorithm (default: SCORED_GREEDY)")
    parser.add_argument(
        "--include-extreme",
        action="store_true",
        help="Also run extreme tight-load stress test for alpha >= 1.70 up to 2.00",
    )
    parser.add_argument("--save-json", action="store_true", help="Write calibration output to data/alpha_grid_calibration.json")
    args = parser.parse_args()

    res = run_grid_search(algorithm=args.algorithm)
    print(f"=== ALPHA 1D GRID SEARCH (Algorithm={res['algorithm']}, Scenarios={len(res['scenarios'])}) ===")
    print(f"{'Alpha(L/H)':<12} {'C_hard':<6} {'R_dl%':<8} {'+25%NoRep':<10} {'+25%Rdl%':<9} {'+50%Rdl%':<9} {'Frag':<6} {'Exp(1-5)':<9} {'Score':<8}")
    print("-" * 82)
    for r in res["grid_results"]:
        lbl = f"{r['alpha_light']:.2f}/{r['alpha_heavy']:.2f}"
        print(
            f"{lbl:<12} {r['hard_violations']:<6} {r['avg_deadline_rate']:<8.2f} "
            f"{r['avg_shock25_absorbed_no_repair_pct']:<10.1f} {r['avg_shock25_post_dl_rate']:<9.2f} "
            f"{r['avg_shock50_post_dl_rate']:<9.2f} {r['avg_fragmentation']:<6.2f} "
            f"{r['avg_experience_rating']:<9.2f} {r['composite_score']:<8.2f}"
        )
    print("-" * 82)
    d = res["recommended_asym_default"]
    b = res["best_1d"]
    print(
        f"Asym Default ({d['alpha_light']:.2f}/{d['alpha_heavy']:.2f}): "
        f"R_dl={d['avg_deadline_rate']}%, +25%NoRep={d['avg_shock25_absorbed_no_repair_pct']}%, "
        f"+25%Rdl={d['avg_shock25_post_dl_rate']}%, +50%Rdl={d['avg_shock50_post_dl_rate']}%, "
        f"Exp={d['avg_experience_rating']}, Score={d['composite_score']}"
    )
    print(
        f"Best 1D Alpha ({b['alpha_light']:.2f}): Score={b['composite_score']}, "
        f"R_dl={b['avg_deadline_rate']}%, +50%Rdl={b['avg_shock50_post_dl_rate']}%"
    )

    if args.include_extreme:
        ext = run_extreme_tight_stress(algorithm=args.algorithm)
        res["extreme_tight_stress"] = ext
        print(f"\n=== EXTREME TIGHT-LOAD STRESS TEST (alpha >= 1.70 Over-Buffering Cliff, Scenarios={len(ext['scenarios'])}) ===")
        print(f"{'Alpha(L/H)':<12} {'C_hard':<6} {'R_dl%':<8} {'CliffDrop%':<11} {'+25%NoRep':<10} {'Exp(1-5)':<9} {'Score':<8}")
        print("-" * 72)
        for r in ext["stress_results"]:
            lbl = f"{r['alpha_light']:.2f}/{r['alpha_heavy']:.2f}"
            print(
                f"{lbl:<12} {r['hard_violations']:<6} {r['avg_deadline_rate']:<8.2f} "
                f"{r['over_buffer_infeasible_rate_pct']:<11.2f} "
                f"{r['avg_shock25_absorbed_no_repair_pct']:<10.1f} "
                f"{r['avg_experience_rating']:<9.2f} {r['composite_score']:<8.2f}"
            )
        ad = ext["recommended_asym_default"]
        print("-" * 72)
        print(
            f"Asym Default ({ad['alpha_light']:.2f}/{ad['alpha_heavy']:.2f}) on Tight Stress: "
            f"R_dl={ad['avg_deadline_rate']}%, CliffDrop={ad['over_buffer_infeasible_rate_pct']}%, "
            f"Score={ad['composite_score']} | Cliff Detected (>=1.70): {ext['over_buffering_cliff_detected']} "
            f"(max drop={ext['max_cliff_dl_drop_pct']}%)"
        )

    if args.save_json:
        out_path = DATA_DIR / "alpha_grid_calibration.json"
        out_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
        print(f"Saved JSON calibration report to {out_path}")


if __name__ == "__main__":
    main()
