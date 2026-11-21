"""
Blind Packet Builder & CLI Runner (`member_eval/blind_runner.py`).

Generates shuffled, strictly anonymized schedule candidates (#A, #B, #C...) alongside
a hidden `Testing_System v2.1` Oracle (`revealed_oracle`) unlocked only after submission.
"""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _ensure_paths() -> None:
    baseline_root = Path(__file__).resolve().parents[1]
    repo_root = baseline_root.parent
    plan_root = repo_root / "v1.0-alpha-plan"
    for p in (str(repo_root), str(plan_root), str(baseline_root)):
        if p not in sys.path:
            sys.path.insert(0, p)


_ensure_paths()

from Testing_System.evaluator.schedule_evaluator import ScheduleEvaluator  # noqa: E402
from Testing_System.evaluator.verdict_and_icee import rank_cross_solver_reports  # noqa: E402
from Testing_System.sut_adapter import resolve_horizon_slots_safe  # noqa: E402
from member_eval import ALL_6_SOLVERS, BLIND_LABELS, STANDARD_3_SOLVERS, STANDARD_4_SOLVERS  # noqa: E402
from member_eval.scenarios import (  # noqa: E402
    build_custom_personal_bundle,
    list_scenarios,
    load_scenario_bundle,
)
from src.controller import ScheduleController  # noqa: E402
from src.grid_manager import TimeGridManager  # noqa: E402
from src.models import CommitmentsProfile, ScheduleBlock, Task  # noqa: E402


def get_eval_base_dir() -> Path:
    env_dir = os.environ.get("SMARTSCHEDULE_EVAL_DIR")
    if env_dir:
        return Path(env_dir)
    return Path(__file__).resolve().parent


def sanitize_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "item").strip())
    return cleaned.strip("_") or "item"


def resolve_solver_selection(mode: str = "standard_3", solvers: Optional[Sequence[str]] = None) -> List[str]:
    if solvers:
        return [str(s).strip().upper() for s in solvers if str(s).strip()]
    key = str(mode or "standard_3").strip().lower()
    if key in ("all_6", "all", "6"):
        return list(ALL_6_SOLVERS)
    if key in ("standard_4", "4"):
        return list(STANDARD_4_SOLVERS)
    return list(STANDARD_3_SOLVERS)


def deterministic_blind_order(
    solvers: Sequence[str],
    seed: int,
    member_id: str,
    scenario_id: str,
) -> List[Tuple[str, str]]:
    """Assign deterministic randomized blind labels `#A, #B, #C...` using sha256(seed, member, scenario)."""
    digest = hashlib.sha256(f"{seed}:{member_id}:{scenario_id}".encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    shuffled = list(solvers)
    rng.shuffle(shuffled)
    pairs: List[Tuple[str, str]] = []
    for idx, solver_name in enumerate(shuffled):
        label = BLIND_LABELS[idx] if idx < len(BLIND_LABELS) else f"#CAND_{idx + 1}"
        pairs.append((label, solver_name))
    return pairs


def _sanitize_unplaced_reason(raw_reason: Any) -> str:
    txt = str(raw_reason or "")
    for token in (
        "SCORED_GREEDY",
        "HYBRID_ALNS",
        "BACKTRACKING_B_AND_B",
        "BACKTRACKING_BRANCH_AND_BOUND",
        "BACKTRACK",
        "GREEDY_EDF_FIRST_FIT",
        "EDF_FIRST_FIT",
        "GREEDY_LST_BEST_FIT",
        "GREEDY_WSPT_SMITH_RULE",
        "GreedyEDF",
        "WSPT",
        "LST",
        "EDF",
        "ALNS",
    ):
        txt = txt.replace(f"[{token}]", "").replace(token, "Thuật toán")
    return txt.strip() or "Không đủ khoảng trống trước hạn"


def _extract_v21_vector(entry_dict: Dict[str, Any], report_dict: Dict[str, Any]) -> Dict[str, Any]:
    p1 = report_dict.get("p1_value_timeliness", {})
    p2 = report_dict.get("p2_cognitive_biology", {})
    p3 = report_dict.get("p3_sustainable_pacing", {})
    p4 = report_dict.get("p4_robustness_stability", {})
    gates = report_dict.get("gates", {})
    shock25 = entry_dict.get("p4_shock25_survived_pct", 100.0)
    shock50 = 100.0
    for sr in p4.get("shock_results", []):
        if abs(float(sr.get("shock_pct", 0.0)) - 50.0) < 1e-6:
            shock50 = float(sr.get("survived_priority_pct", 100.0))
    return {
        "lexicographic_rank": entry_dict.get("lexicographic_rank"),
        "verdict": entry_dict.get("verdict"),
        "g1_violations": gates.get("g1_total_violations", 0),
        "rho_total": gates.get("rho_total", 0.0),
        "rho_deadline": gates.get("rho_deadline", 0.0),
        "p1_deadline_val_pct": p1.get("deadline_value_rate_pct", 100.0),
        "p1_last10h_pct": p1.get("unjustified_last_10h_crowding_pct", 0.0),
        "p1_heavy_onset_pct": p1.get("heavy_onset_delay_pct"),
        "p1_habit_rate_pct": p1.get("habit_value_rate_pct"),
        "p4_shock25_pct": shock25,
        "p4_shock50_pct": shock50,
        "p4_buffer_task_pct": p4.get("true_buffer_task_pct", 0.0),
        "p2_recovery_pct": p2.get("heavy_recovery_rate_pct"),
        "p2_max_streak_l2_min": p2.get("max_multi_block_streak_l2_min", 0),
        "p2_post_class_violations": p2.get("post_class_buffer_violations", 0),
        "p2_off_peak_mismatch": p2.get("off_peak_heavy_mismatch_count", 0),
        "p2_achievable_peak_pct": p2.get("achievable_heavy_peak_match_pct"),
        "p2_preferred_window_pct": p2.get("preferred_window_match_pct"),
        "p2_sjl_minutes": p2.get("sjl_minutes"),
        "p2_sjl_direction": p2.get("sjl_direction"),
        "p2_sjl_neutral_unpaired": p2.get("sjl_neutral_unpaired", False),
        "p3_corne_vector": p3.get("corne_lexicographic_vector", [0, 0, 0]),
        "p3_max_daily_total_min": p3.get("max_daily_total_min", 0),
        "p3_total_daily_std_min": p3.get("total_daily_load_std_min", 0.0),
        "p3_effective_std_limit_min": p3.get("effective_daily_std_limit_min", 180.0),
        "p3_context_switches": p3.get("focus_context_switches", 0),
        "exec_ms": entry_dict.get("exec_ms", 0.0),
        "sla_exceeded": entry_dict.get("v2_sla_exceeded", False),
    }


def build_blind_packet(
    member_id: str,
    scenario_id: str,
    mode: str = "standard_3",
    solvers: Optional[Sequence[str]] = None,
    custom_profile: Optional[CommitmentsProfile] = None,
    custom_tasks: Optional[List[Task]] = None,
    custom_pinned: Optional[List[ScheduleBlock]] = None,
    custom_title_vi: Optional[str] = None,
    seed: int = 2026,
) -> Dict[str, Any]:
    """
    Build a complete blind evaluation packet containing:
      - `blind_view`: 100% solver-anonymized candidate timetables safe for frontend display.
      - `revealed_oracle`: sealed `v2.1` evaluation results, ranks, ICEE critiques & blind mapping.
    """
    if custom_profile is not None and custom_tasks is not None:
        bundle = build_custom_personal_bundle(
            commitments_dict=custom_profile.model_dump() if isinstance(custom_profile, CommitmentsProfile) else custom_profile,
            tasks_list=[t.model_dump() if isinstance(t, Task) else t for t in custom_tasks],
            pinned_list=[b.model_dump() if isinstance(b, ScheduleBlock) else b for b in (custom_pinned or [])],
            scenario_id=scenario_id or "PERSONAL_WEEK",
        )
    else:
        bundle = load_scenario_bundle(scenario_id)

    spec = bundle["spec"]
    profile: CommitmentsProfile = bundle["profile"].model_copy(deep=True)
    raw_tasks: List[Task] = [t.model_copy(deep=True) for t in bundle["tasks"]]
    pinned_blocks: List[ScheduleBlock] = [b.model_copy(deep=True) for b in (bundle.get("pinned_blocks") or [])]

    solver_list = resolve_solver_selection(mode=mode, solvers=solvers)
    pairs = deterministic_blind_order(solver_list, seed=seed, member_id=member_id, scenario_id=spec.scenario_id)

    horizon_days = int(getattr(profile, "horizon_days", 7) or 7)
    horizon_slots = resolve_horizon_slots_safe(profile, raw_tasks, pinned_blocks)
    horizon_days = max(horizon_days, max(7, (horizon_slots + 95) // 96))

    energy_prof = profile.get_energy_profile()
    energy_by_slot = [energy_prof.level_for_slot(s) for s in range(horizon_slots)]

    # Build background fixed/sleep bands once so the viewer renders realistic blocks without leaking solver internals.
    base_grid = TimeGridManager(total_slots=horizon_slots)
    base_grid.initialize_from_profile(profile.model_copy(deep=True))

    outputs_by_solver: Dict[str, Any] = {}
    reports_by_solver: Dict[str, Any] = {}
    elapsed_by_solver: Dict[str, float] = {}

    for _blind_id, solver_name in pairs:
        prof_run = profile.model_copy(deep=True)
        tasks_run = [t.model_copy(deep=True) for t in raw_tasks]
        pins_run = [b.model_copy(deep=True) for b in pinned_blocks]

        t0 = time.perf_counter()
        out, _grid = ScheduleController.solve_schedule(
            profile=prof_run,
            tasks=tasks_run,
            algorithm=solver_name,
            pinned_blocks=pins_run,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        if out.execution_time_ms <= 0.0:
            out.execution_time_ms = elapsed_ms

        rep = ScheduleEvaluator.evaluate(
            profile=profile.model_copy(deep=True),
            tasks=[t.model_copy(deep=True) for t in raw_tasks],
            schedule=out,
            input_pinned_blocks=[b.model_copy(deep=True) for b in pinned_blocks],
        )
        outputs_by_solver[solver_name] = out
        reports_by_solver[solver_name] = rep
        elapsed_by_solver[solver_name] = float(out.execution_time_ms)

    ranking_entries = rank_cross_solver_reports(reports_by_solver)
    solver_to_blind = {s: b_id for b_id, s in pairs}
    entry_by_solver = {e.solver_name: e for e in ranking_entries}

    blind_candidates: List[Dict[str, Any]] = []
    reports_by_blind_id: Dict[str, Any] = {}
    blind_mapping: Dict[str, str] = {}

    # Preserve canonical #A, #B, #C... display order
    for blind_id, solver_name in pairs:
        out = outputs_by_solver[solver_name]
        rep = reports_by_solver[solver_name]
        entry = entry_by_solver[solver_name]
        blind_mapping[blind_id] = solver_name

        # Construct strictly anonymized candidate view (zero solver_used, zero solver-tagged reasons)
        anon_blocks: List[Dict[str, Any]] = []
        total_sched_min = 0
        for b in out.blocks:
            total_sched_min += int(b.duration_min)
            anon_blocks.append({
                "block_id": b.block_id,
                "task_id": b.task_id,
                "title": b.title,
                "day": b.day,
                "start_slot": b.start_slot,
                "end_slot": b.end_slot,
                "start_time": b.start_time,
                "end_time": b.end_time,
                "duration_min": b.duration_min,
                "chunk_index": b.chunk_index,
                "total_chunks": b.total_chunks,
                "priority": b.priority,
                "cognitive_load": b.cognitive_load,
                "category": b.category,
                "state": b.state,
                "deadline_str": b.deadline_str,
                "energy_level": energy_prof.level_for_slot(b.start_slot),
            })

        anon_unplaced = [
            {
                "task_id": u.get("task_id"),
                "title": u.get("title"),
                "duration_min": u.get("duration_min"),
                "deadline": u.get("deadline"),
                "reason": _sanitize_unplaced_reason(u.get("reason")),
            }
            for u in (out.unplaced_tasks or [])
        ]

        blind_candidates.append({
            "blind_id": blind_id,
            "blocks": anon_blocks,
            "unplaced_tasks": anon_unplaced,
            "summary_basic": {
                "placed_count": out.summary.tasks_placed,
                "total_tasks": out.summary.total_tasks_requested,
                "unplaced_count": out.summary.tasks_unplaced,
                "total_scheduled_min": total_sched_min,
                "rest_slots": out.summary.rest_slots,
                "deadline_satisfaction_rate": out.summary.deadline_satisfaction_rate,
            },
        })

        entry_dict = entry.model_dump()
        rep_dict = rep.model_dump()
        reports_by_blind_id[blind_id] = {
            "blind_id": blind_id,
            "solver_name": solver_name,
            "verdict": rep.verdict.value,
            "lexicographic_rank": entry.lexicographic_rank,
            "exec_ms": elapsed_by_solver[solver_name],
            "critical_breaches": list(rep.critical_breaches),
            "moderate_warnings": list(rep.moderate_warnings),
            "verdict_reasons_vi": list(rep.verdict_reasons_vi),
            "v21_vector": _extract_v21_vector(entry_dict, rep_dict),
            "top_icee": [c.model_dump() for c in rep.d1_icee_critiques],
        }

    created_at = datetime.now(timezone.utc).isoformat()
    packet_id = f"PKT_{sanitize_slug(member_id)}_{sanitize_slug(spec.scenario_id)}_{seed}_{int(time.time() * 1000) % 100000}"

    cross_ranking_rows = []
    for e in ranking_entries:
        ed = e.model_dump()
        ed["blind_id"] = solver_to_blind.get(e.solver_name, "?")
        cross_ranking_rows.append(ed)

    packet = {
        "packet_version": "1.0",
        "blind_view": {
            "packet_id": packet_id,
            "created_at": created_at,
            "member_id": member_id,
            "scenario_id": spec.scenario_id,
            "scenario_title_vi": custom_title_vi or spec.title_vi,
            "scenario_category": spec.category,
            "scenario_description_vi": spec.description_vi,
            "mode": mode,
            "seed": seed,
            "horizon_days": horizon_days,
            "horizon_slots": horizon_slots,
            "profile": {
                **profile.model_dump(),
                "energy_by_slot": energy_by_slot,
                "base_grid_states": list(base_grid.grid),
            },
            "tasks": [t.model_dump() for t in raw_tasks],
            "pinned_blocks": [b.model_dump() for b in pinned_blocks],
            "blind_candidates": blind_candidates,
        },
        "revealed_oracle": {
            "blind_mapping": blind_mapping,
            "cross_solver_ranking": cross_ranking_rows,
            "reports_by_blind_id": reports_by_blind_id,
        },
    }
    return packet


def strip_oracle_for_blind_client(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Return ONLY the blind portion (`blind_view`) with zero solver identity or oracle leakage."""
    return copy.deepcopy(packet["blind_view"])


def get_packets_dir(base_dir: Optional[Path] = None) -> Path:
    d = (base_dir or get_eval_base_dir()) / "packets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_reviews_dir(base_dir: Optional[Path] = None) -> Path:
    d = (base_dir or get_eval_base_dir()) / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_packet(packet: Dict[str, Any], packets_dir: Optional[Path] = None) -> Path:
    pdir = packets_dir or get_packets_dir()
    pdir.mkdir(parents=True, exist_ok=True)
    pid = sanitize_slug(packet["blind_view"]["packet_id"])
    target = pdir / f"{pid}.json"
    target.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_packet(packet_id: str, packets_dir: Optional[Path] = None) -> Dict[str, Any]:
    pdir = packets_dir or get_packets_dir()
    pid = sanitize_slug(packet_id)
    target = pdir / f"{pid}.json"
    if not target.exists():
        raise FileNotFoundError(f"Blind packet '{packet_id}' not found in {pdir}")
    return json.loads(target.read_text(encoding="utf-8"))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate blind multi-solver packets for Member-in-the-Loop evaluation.")
    parser.add_argument("--member", required=True, help="Member ID (e.g. duc_minh, minh_anh)")
    parser.add_argument("--scenario", default="all", help="Scenario ID or 'all'")
    parser.add_argument("--mode", default="standard_3", choices=["standard_3", "standard_4", "all_6"])
    parser.add_argument("--solvers", nargs="*", help="Explicit solver override list")
    parser.add_argument("--seed", type=int, default=2026, help="Blind shuffle seed")
    parser.add_argument("--out-dir", default=None, help="Output directory for generated packets")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir) if args.out_dir else get_packets_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    if str(args.scenario).strip().lower() == "all":
        sc_ids = [s["scenario_id"] for s in list_scenarios()]
    else:
        sc_ids = [args.scenario]

    generated: List[str] = []
    for sc_id in sc_ids:
        packet = build_blind_packet(
            member_id=args.member,
            scenario_id=sc_id,
            mode=args.mode,
            solvers=args.solvers,
            seed=args.seed,
        )
        saved_path = save_packet(packet, packets_dir=out_dir)
        generated.append(str(saved_path))
        cand_summary = ", ".join(
            f"{c['blind_id']}(placed={c['summary_basic']['placed_count']}/{c['summary_basic']['total_tasks']})"
            for c in packet["blind_view"]["blind_candidates"]
        )
        print(f"[BLIND PACKET] {sc_id} -> {saved_path.name} | {cand_summary}")

    print(f"Generated {len(generated)} blind packet(s) cleanly in {out_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
