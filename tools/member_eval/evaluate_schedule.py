"""
Intermediate Member Evaluation Workbench (`member_eval/evaluate_schedule.py`).

Bridges `Testing_System v2.1` proxy metrics and real student UX across Group 03:
  - Supports 6 solvers (`EDF`, `SCORED_GREEDY`, `HYBRID_ALNS`, `BACKTRACK`, `WSPT`, `LST`)
  - Randomizes & masks solver identities into `#A`, `#B`, `#C`, ... for unbiased review
  - Computes exact `Testing_System v2.1` 11-criteria scorecards & Top ICEE critiques, kept
    hidden until after a member submits UX ratings (`UX-1..UX-5`) + blind vote & block tags (`UX-6`)
  - Saves JSON reviews and aggregates a live `Calibration_Report.md` contrasting Human Preference
    against `v2.1` Lexicographic Rankings.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import random
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

_THIS_DIR = Path(__file__).resolve().parent
_WORKSPACE_ROOT = _THIS_DIR.parents[1]
_PLAN_ROOT = _WORKSPACE_ROOT / "v1.0-alpha-plan"
for _p in (str(_WORKSPACE_ROOT), str(_PLAN_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from smartschedule.core.config import PRESETS_DIR  # noqa: E402
from smartschedule.core.controller import ScheduleController  # noqa: E402
from smartschedule.core.grid_manager import TimeGridManager  # noqa: E402
from smartschedule.core.models import CommitmentsProfile, ScheduleBlock, Task  # noqa: E402
from Testing_System.evaluator import ScheduleEvaluator  # noqa: E402
from Testing_System.generator import FuzzGenerator, InputGenerator  # noqa: E402
from Testing_System.schemas import RegimeName  # noqa: E402

DATA_DIR = PRESETS_DIR
REVIEWS_DIR = _THIS_DIR / "reviews"

ALL_SOLVERS: Tuple[str, ...] = ("EDF", "WSPT", "LST", "SCORED_GREEDY", "BACKTRACK", "HYBRID_ALNS")

SOLVER_PRESETS: Dict[str, Tuple[str, ...]] = {
    "BLIND_3": ("EDF", "SCORED_GREEDY", "HYBRID_ALNS"),
    "BLIND_4": ("EDF", "SCORED_GREEDY", "BACKTRACK", "HYBRID_ALNS"),
    "ALL_6": ALL_SOLVERS,
}

SOLVER_DESCRIPTIONS: Dict[str, str] = {
    "EDF": "Baseline V0 Earliest-Deadline First-Fit (Energy-Blind)",
    "SCORED_GREEDY": "V3 Production Default (Circadian Portfolio + Polish)",
    "HYBRID_ALNS": "V3 6th Algorithm (Portfolio + ALNS Ruin-Recreate + Regret-2)",
    "BACKTRACK": "V3 Live-State Ergonomic Branch-and-Bound",
    "WSPT": "V3 Energy-Blind Smith Rule + Overload Knapsack",
    "LST": "V3 Energy-Blind Least-Slack Early-Best-Fit",
}

GROUP_MEMBERS: List[Dict[str, str]] = [
    {"member_id": "25125028", "name": "Phạm Đức Minh", "role": "Leader (Lead §9 Evaluation Plan)"},
    {"member_id": "25125019", "name": "Trần Nguyên Khánh", "role": "Thinker 1 (Lead §6 Algorithmic Design)"},
    {"member_id": "25125001", "name": "Hoàng Minh Anh", "role": "Thinker 2 (Lead §11 Conclusion)"},
    {"member_id": "25125037", "name": "Nguyễn Trọng Tiến", "role": "Thinker 3 (Lead §5 Abstraction)"},
    {"member_id": "25125007", "name": "Lê Tiến Bình", "role": "Builder 1 (Lead §7 System Architecture)"},
    {"member_id": "25125032", "name": "Lê Minh Nhật", "role": "Builder 2 (Lead §10 Design to Action)"},
    {"member_id": "25125006", "name": "Nguyễn Nguyễn Gia Bảo", "role": "Builder 3 (Lead §8 Edge Cases & Trade-offs)"},
]

BLOCK_ISSUE_TAGS: List[Dict[str, str]] = [
    {"code": "AWKWARD_SPLIT", "label": "Cắt mảnh vụn / khó theo"},
    {"code": "BAD_TIME_OF_DAY", "label": "Sai khung giờ tỉnh táo"},
    {"code": "TOO_TIGHT_GAP", "label": "Quá gấp / thiếu giờ nghỉ"},
    {"code": "CONTEXT_JUMP", "label": "Nhảy môn gây phân tâm"},
    {"code": "DAY_OVERLOAD", "label": "Ngày bị nhồi quá nặng"},
    {"code": "HABIT_MISPLACED", "label": "Xếp lệch thói quen"},
    {"code": "WRONG_PRIORITY", "label": "Sai ưu tiên việc quan trọng"},
]

UX_DIMENSIONS: List[Dict[str, str]] = [
    {"key": "ux_1_efficiency", "label": "UX-1 · Hiệu quả xử lý task (đúng việc, đúng hạn)"},
    {"key": "ux_2_energy_fit", "label": "UX-2 · Hợp nhịp năng lượng thật (sáng/chiều/tối)"},
    {"key": "ux_3_fatigue_breaks", "label": "UX-3 · Sức bền & khoảng nghỉ tự nhiên"},
    {"key": "ux_4_split_flow", "label": "UX-4 · Độ mượt chia mảnh & chuyển môn"},
    {"key": "ux_5_resilience", "label": "UX-5 · Độ bền nếu trễ giờ ngoài đời"},
]

SCENARIO_CATALOG: List[Dict[str, Any]] = [
    {
        "scenario_id": "PERSONAL_MINH",
        "title": "Tuần chuẩn của Minh (9 tasks, lớp T2-T6)",
        "tier": "PERSONAL",
        "description": "Hồ sơ chuẩn mẫu với các deadline Toán, Lab và chuỗi đồ án phụ thuộc.",
    },
    {
        "scenario_id": "PERSONAL_LAN",
        "title": "Tuần bận rộn của Lan (Học + Làm thêm + CLB)",
        "tier": "PERSONAL",
        "description": "Nhiều ràng buộc cố định và công việc đan xen cuối tuần.",
    },
    {
        "scenario_id": "REGIME_1_LOOSE",
        "title": "Regime 1 · Tải nhẹ khả thi (seed=1)",
        "tier": "LOOSE",
        "description": "Quỹ thời gian rộng để kiểm tra mức độ sạch sẽ, không nhồi ngày.",
    },
    {
        "scenario_id": "REGIME_2_TIGHT",
        "title": "Regime 2 · Deadline dồn sát T3–T5 (seed=42)",
        "tier": "TIGHT",
        "description": "Cụm deadline dày đặc thử khả năng giữ 100% việc đúng hạn.",
    },
    {
        "scenario_id": "REGIME_3_CIRCADIAN",
        "title": "Regime 3 · Cú đêm & Lớp lệch T2/T4/T6 (seed=5)",
        "tier": "LOOSE",
        "description": "Thử khả năng khớp giờ đỉnh năng lượng và giữ đều nhịp SJL.",
    },
    {
        "scenario_id": "REGIME_4_DAG",
        "title": "Regime 4 · Chuỗi DAG phụ thuộc & Hạn xa (seed=1)",
        "tier": "LOOSE",
        "description": "Kiểm tra khởi phát sớm, không dồn nước đến chân mới nhảy.",
    },
    {
        "scenario_id": "REGIME_5_OVERLOAD",
        "title": "Regime 5 · Quá tải thật (Overload Triage, seed=1)",
        "tier": "OVERLOAD",
        "description": "Không thể xếp hết mọi việc — đánh giá thuật toán giữ việc ưu tiên cao nhất.",
    },
    {
        "scenario_id": "FUZZ_LOOSE_14D",
        "title": "Fuzz v2 · Tuần kép 14 ngày LOOSE (seed=1041)",
        "tier": "LOOSE",
        "description": "Bài toán 14 ngày nhiều task + thói quen ngẫu nhiên có lời giải vàng.",
    },
    {
        "scenario_id": "FUZZ_TIGHT_7D",
        "title": "Fuzz v2 · Học sinh THPT nước rút TIGHT (seed=1001)",
        "tier": "TIGHT",
        "description": "Tải ~78.8%, lớp chính khóa dày buổi sáng.",
    },
    {
        "scenario_id": "FUZZ_OVERLOAD_14D",
        "title": "Fuzz v2 · Ôn thi 14 ngày OVERLOAD 62 tasks (seed=1049)",
        "tier": "OVERLOAD",
        "description": "Quá tải quy mô lớn thử tốc độ SLA < 1s và lựa chọn ưu tiên.",
    },
]

_SCENARIO_META_MAP: Dict[str, Dict[str, Any]] = {item["scenario_id"]: item for item in SCENARIO_CATALOG}
_MEMBER_MAP: Dict[str, Dict[str, str]] = {m["member_id"]: m for m in GROUP_MEMBERS}

# In-memory packet cache for the interactive web session
_PACKET_CACHE: Dict[str, Dict[str, Any]] = {}


def _strip_solver_identity(text: str, blind_id: str) -> str:
    """Remove solver algorithm names from block reason strings before blind display."""
    if not text:
        return f"[Phương án {blind_id}]"
    pattern = r"\[(GREEDY_[A-Z_]+|SCORED_GREEDY|BACKTRACK[A-Z_]*|HYBRID_ALNS|EDF|WSPT|LST)\]"
    return re.sub(pattern, f"[Phương án {blind_id}]", text)


def load_scenario_bundle(
    scenario_id: str,
    seed: int = 42,
    custom_payload: Optional[Dict[str, Any]] = None,
) -> Tuple[CommitmentsProfile, List[Task], List[ScheduleBlock], Dict[str, Any]]:
    """Resolve a built-in scenario, Regime, Fuzz seed, or custom member payload."""
    if custom_payload is not None:
        raw_prof = dict(custom_payload.get("profile") or {})
        raw_tasks = list(custom_payload.get("tasks") or [])
        raw_pins = list(custom_payload.get("pinned_blocks") or [])
        profile = CommitmentsProfile.model_validate(raw_prof)
        tasks = [Task.model_validate(t) for t in raw_tasks]
        pins = [ScheduleBlock.model_validate(b) for b in raw_pins]
        return (
            profile,
            tasks,
            pins,
            {
                "scenario_id": scenario_id or "CUSTOM_WEEK",
                "title": str(custom_payload.get("title") or "Lịch cá nhân tự nhập (Custom)"),
                "tier": "PERSONAL",
                "horizon_days": profile.horizon_days,
                "description": "Lịch do thành viên trực tiếp nhập để đánh giá trải nghiệm thật.",
            },
        )

    sid = (scenario_id or "PERSONAL_MINH").strip().upper()
    if sid == "PERSONAL_MINH":
        prof = CommitmentsProfile.model_validate(
            json.loads((DATA_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
        )
        tasks = [
            Task.model_validate(x)
            for x in json.loads((DATA_DIR / "sample_week_tasks.json").read_text(encoding="utf-8"))
        ]
        meta = dict(_SCENARIO_META_MAP[sid])
        meta["horizon_days"] = prof.horizon_days
        return prof, tasks, [], meta

    if sid == "PERSONAL_LAN":
        prof = CommitmentsProfile.model_validate(
            json.loads((DATA_DIR / "lan_week_commitments.json").read_text(encoding="utf-8"))
        )
        tasks = [
            Task.model_validate(x)
            for x in json.loads((DATA_DIR / "lan_week_tasks.json").read_text(encoding="utf-8"))
        ]
        meta = dict(_SCENARIO_META_MAP[sid])
        meta["horizon_days"] = prof.horizon_days
        return prof, tasks, [], meta

    regime_lookup = {
        "REGIME_1_LOOSE": (RegimeName.LOOSE_FEASIBLE, 1),
        "REGIME_2_TIGHT": (RegimeName.TIGHT_DEADLINE_CLUSTER, 42),
        "REGIME_3_CIRCADIAN": (RegimeName.CIRCADIAN_SJL_AND_RECOVERY, 5),
        "REGIME_4_DAG": (RegimeName.PROCRASTINATION_ONSET_AND_DAG, 1),
        "REGIME_5_OVERLOAD": (RegimeName.OVERLOAD_INFEASIBLE, 1),
    }
    if sid in regime_lookup:
        reg, def_seed = regime_lookup[sid]
        bundle = InputGenerator.generate(regime=reg, seed=def_seed)
        meta = dict(_SCENARIO_META_MAP[sid])
        meta["horizon_days"] = bundle.profile.horizon_days
        return bundle.profile, bundle.tasks, bundle.pinned_blocks, meta

    fuzz_seeds = {"FUZZ_LOOSE_14D": 1041, "FUZZ_TIGHT_7D": 1001, "FUZZ_OVERLOAD_14D": 1049}
    if sid in fuzz_seeds or sid.startswith("FUZZ_"):
        f_seed = fuzz_seeds.get(sid)
        if f_seed is None:
            try:
                f_seed = int(sid.split("_")[-1])
            except ValueError:
                f_seed = int(seed)
        bundle = FuzzGenerator.generate(seed=f_seed)
        base_meta = dict(
            _SCENARIO_META_MAP.get(
                sid,
                {
                    "scenario_id": sid,
                    "title": f"Fuzz v2 Seed={f_seed} ({bundle.metadata.fuzz_tier})",
                    "tier": bundle.metadata.fuzz_tier or "CUSTOM",
                    "description": bundle.metadata.notes,
                },
            )
        )
        base_meta["horizon_days"] = bundle.profile.horizon_days
        return bundle.profile, bundle.tasks, bundle.pinned_blocks, base_meta

    raise ValueError(f"Unknown scenario_id: {scenario_id}")


def _build_grid_overlay(profile: CommitmentsProfile, horizon_days: int) -> Dict[str, Any]:
    """Extract sleep, meals, classes, and circadian energy grid for clean visual rendering."""
    total_slots = max(1, horizon_days) * 96
    grid = TimeGridManager(total_slots=total_slots)
    grid.initialize_from_profile(profile.model_copy(deep=True))
    energy_prof = profile.get_energy_profile()

    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "Next Monday",
        "Next Tuesday",
        "Next Wednesday",
        "Next Thursday",
        "Next Friday",
        "Next Saturday",
        "Next Sunday",
    ][:horizon_days]

    fixed_spans: List[Dict[str, Any]] = []
    for ev in profile.fixed_events:
        days = grid._resolve_event_days(ev.day_of_week)
        for d_idx in days:
            if d_idx >= horizon_days:
                continue
            from smartschedule.core.utils import day_time_to_slot

            d_label = day_names[d_idx]
            st = day_time_to_slot(d_label, ev.start_time, is_end_or_deadline=False)
            en = day_time_to_slot(d_label, ev.end_time, is_end_or_deadline=True)
            fixed_spans.append(
                {
                    "event_id": ev.event_id,
                    "title": ev.title,
                    "category": ev.category,
                    "day_idx": d_idx,
                    "start_slot": st,
                    "end_slot": en,
                    "start_time": ev.start_time,
                    "end_time": ev.end_time,
                }
            )

    return {
        "horizon_days": horizon_days,
        "day_names": day_names,
        "sleep_start": profile.sleep_schedule.daily_start_time,
        "sleep_end": profile.sleep_schedule.daily_end_time,
        "energy_levels_by_hour": [energy_prof.level_for_hour(h) for h in range(24)],
        "fixed_spans": fixed_spans,
    }


def generate_blind_packet(
    scenario_id: str = "PERSONAL_MINH",
    member_id: str = "25125028",
    solvers: Optional[Sequence[str]] = None,
    seed: int = 42,
    custom_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Execute all chosen solvers, compute hidden `Testing_System v2.1` evaluation reports,
    and return an anonymized `#A/#B/#C...` blind review packet + separated `oracle_reveal`.
    """
    chosen_solvers = [s.strip().upper() for s in (solvers or SOLVER_PRESETS["BLIND_3"]) if s.strip()]
    profile, tasks, pinned_blocks, meta = load_scenario_bundle(
        scenario_id=scenario_id, seed=seed, custom_payload=custom_payload
    )

    reports: Dict[str, Any] = {}
    outputs: Dict[str, Any] = {}
    insights: Dict[str, Dict[str, Any]] = {}

    for algo in chosen_solvers:
        prof_c = profile.model_copy(deep=True)
        tasks_c = [t.model_copy(deep=True) for t in tasks]
        pins_c = [p.model_copy(deep=True) for p in pinned_blocks]
        out, _grid = ScheduleController.solve_schedule(
            profile=prof_c, tasks=tasks_c, algorithm=algo, pinned_blocks=pins_c or None
        )
        rep = ScheduleEvaluator.evaluate(
            profile=profile.model_copy(deep=True),
            tasks=[t.model_copy(deep=True) for t in tasks],
            schedule=out.model_copy(deep=True),
            input_pinned_blocks=[p.model_copy(deep=True) for p in pinned_blocks] if pinned_blocks else None,
        )
        ins = ScheduleController.compute_schedule_insights(profile, out)
        outputs[algo] = out
        reports[algo] = rep
        insights[algo] = ins

    ranking = ScheduleEvaluator.compare_solvers(reports)
    rank_by_solver = {e.solver_name: e for e in ranking}

    # Deterministically anonymize solver order for this member + scenario
    shuffled = list(chosen_solvers)
    rng = random.Random(f"{member_id}:{meta['scenario_id']}:{seed}")
    rng.shuffle(shuffled)
    labels = [f"#{chr(ord('A') + i)}" for i in range(len(shuffled))]

    blind_to_solver: Dict[str, str] = {}
    solver_to_blind: Dict[str, str] = {}
    blind_candidates: List[Dict[str, Any]] = []

    h_days = max(profile.horizon_days, max((b.end_slot for out in outputs.values() for b in out.blocks), default=0) // 96 + 1)
    h_days = 14 if h_days > 7 else 7
    energy_prof = profile.get_energy_profile()

    for blind_id, algo in zip(labels, shuffled):
        blind_to_solver[blind_id] = algo
        solver_to_blind[algo] = blind_id
        out = outputs[algo]
        ins = insights[algo]

        blind_blocks: List[Dict[str, Any]] = []
        for b in sorted(out.blocks, key=lambda x: (x.start_slot, x.end_slot)):
            bd = b.model_dump()
            bd["reason"] = _strip_solver_identity(str(bd.get("reason", "")), blind_id)
            span = max(1, b.end_slot - b.start_slot)
            avg_e = sum(energy_prof.level_for_slot(s) for s in range(b.start_slot, b.end_slot)) / float(span)
            bd["energy_level"] = round(avg_e, 2)
            bd["day_idx"] = b.start_slot // 96
            blind_blocks.append(bd)

        # Compute plain student-friendly day hours summary (without revealing v2.1 score or solver name)
        day_study_min = [0] * h_days
        for b in out.blocks:
            d = b.start_slot // 96
            if 0 <= d < h_days:
                day_study_min[d] += max(0, (b.end_slot - b.start_slot) * 15)

        blind_candidates.append(
            {
                "blind_id": blind_id,
                "blocks": blind_blocks,
                "unplaced_tasks": list(out.unplaced_tasks),
                "summary": {
                    "tasks_requested": out.summary.total_tasks_requested,
                    "tasks_placed": out.summary.tasks_placed,
                    "tasks_unplaced": out.summary.tasks_unplaced,
                    "total_blocks": len(blind_blocks),
                    "total_study_min": sum(day_study_min),
                    "day_study_min": day_study_min,
                    "peak_match_pct": ins.get("deep_peak_match_pct", 0.0),
                    "context_switches": ins.get("context_switches", 0),
                },
            }
        )

    ranking_rows: List[Dict[str, Any]] = []
    critiques_by_solver: Dict[str, List[Dict[str, Any]]] = {}
    for entry in ranking:
        algo = entry.solver_name
        rep = reports[algo]
        row = entry.model_dump(mode="json")
        row["blind_id"] = solver_to_blind[algo]
        row["solver_description"] = SOLVER_DESCRIPTIONS.get(algo, algo)
        row["critical_breaches"] = list(rep.critical_breaches)
        row["moderate_warnings"] = list(rep.moderate_warnings)
        ranking_rows.append(row)
        critiques_by_solver[algo] = [c.model_dump(mode="json") for c in rep.d1_icee_critiques]

    packet_id = f"{member_id}_{meta['scenario_id']}_{len(chosen_solvers)}s"
    packet = {
        "packet_id": packet_id,
        "member": _MEMBER_MAP.get(member_id, {"member_id": member_id, "name": member_id, "role": "Member"}),
        "scenario": meta,
        "grid_overlay": _build_grid_overlay(profile, h_days),
        "tasks_count": len(tasks),
        "blind_candidates": blind_candidates,
        "oracle_reveal": {
            "blind_to_solver": blind_to_solver,
            "solver_to_blind": solver_to_blind,
            "v21_top1_solver": ranking[0].solver_name if ranking else chosen_solvers[0],
            "v21_ranking": ranking_rows,
            "critiques_by_solver": critiques_by_solver,
        },
    }
    _PACKET_CACHE[packet_id] = packet
    return packet


def save_member_review(
    review_data: Dict[str, Any],
    reviews_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Validate, enrich with hidden `oracle_reveal` comparison, persist JSON, and re-aggregate."""
    target_dir = Path(reviews_dir) if reviews_dir is not None else REVIEWS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    member_id = str(review_data.get("member_id") or "25125028").strip()
    scenario_id = str(review_data.get("scenario_id") or "PERSONAL_MINH").strip().upper()
    blind_winner = str(review_data.get("blind_winner_id") or "").strip()

    packet_id = str(review_data.get("packet_id") or "")
    packet = _PACKET_CACHE.get(packet_id)
    blind_to_solver: Dict[str, str] = dict(review_data.get("blind_to_solver") or {})
    v21_top1_solver = str(review_data.get("v21_top1_solver") or "")
    v21_verdict_by_solver: Dict[str, str] = dict(review_data.get("v21_verdict_by_solver") or {})

    if packet is not None:
        oracle = packet["oracle_reveal"]
        if not blind_to_solver:
            blind_to_solver = dict(oracle["blind_to_solver"])
        if not v21_top1_solver:
            v21_top1_solver = str(oracle["v21_top1_solver"])
        if not v21_verdict_by_solver:
            v21_verdict_by_solver = {r["solver_name"]: r["verdict"] for r in oracle["v21_ranking"]}

    winner_solver = blind_to_solver.get(blind_winner, str(review_data.get("winner_solver") or ""))
    if not blind_winner or not winner_solver:
        raise ValueError("Phải chọn đúng 1 phương án thắng mù (`blind_winner_id`, ví dụ `#A`).")

    # Map blind candidate UX scores -> real solver UX scores
    raw_ux = dict(review_data.get("ux_scores") or {})
    ux_by_solver: Dict[str, Dict[str, float]] = {}
    for b_id, score_map in raw_ux.items():
        real_algo = blind_to_solver.get(b_id, b_id)
        if isinstance(score_map, dict):
            ux_by_solver[real_algo] = {
                str(k): float(v) for k, v in score_map.items() if v is not None
            }

    # Resolve real solver onto each block issue tag
    enriched_tags: List[Dict[str, str]] = []
    for item in review_data.get("block_tags") or []:
        if not isinstance(item, dict):
            continue
        b_id = str(item.get("blind_id") or "")
        enriched_tags.append(
            {
                "blind_id": b_id,
                "solver": blind_to_solver.get(b_id, str(item.get("solver") or "")),
                "block_id": str(item.get("block_id") or ""),
                "task_id": str(item.get("task_id") or ""),
                "tag": str(item.get("tag") or "UNKNOWN"),
            }
        )

    m_info = _MEMBER_MAP.get(member_id, {"member_id": member_id, "name": member_id, "role": "Member"})
    tier = str(review_data.get("scenario_tier") or _SCENARIO_META_MAP.get(scenario_id, {}).get("tier") or "CUSTOM")
    agreed_top1 = (winner_solver == v21_top1_solver) if v21_top1_solver else None

    record = {
        "member_id": member_id,
        "member_name": m_info["name"],
        "member_role": m_info["role"],
        "scenario_id": scenario_id,
        "scenario_tier": tier,
        "blind_to_solver": blind_to_solver,
        "blind_winner_id": blind_winner,
        "winner_solver": winner_solver,
        "winner_v21_verdict": v21_verdict_by_solver.get(winner_solver, "UNKNOWN"),
        "v21_top1_solver": v21_top1_solver,
        "agreed_with_v21_top1": agreed_top1,
        "ux_by_solver": ux_by_solver,
        "block_tags": enriched_tags,
        "notes": str(review_data.get("notes") or "").strip(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    safe_sid = re.sub(r"[^A-Za-z0-9_-]", "_", scenario_id)
    out_file = target_dir / f"{member_id}_{safe_sid}.json"
    out_file.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    agg = aggregate_reviews(target_dir)
    return {"status": "SAVED", "review_file": str(out_file), "record": record, "aggregation": agg}


def aggregate_reviews(reviews_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Aggregate all member JSON reviews and emit `Calibration_Report.md` beside the reviews dir."""
    target_dir = Path(reviews_dir) if reviews_dir is not None else REVIEWS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    report_path = target_dir.parent / "Calibration_Report.md"

    records: List[Dict[str, Any]] = []
    for fpath in sorted(target_dir.glob("*.json")):
        try:
            records.append(json.loads(fpath.read_text(encoding="utf-8")))
        except Exception:
            continue

    total_reviews = len(records)
    wins = Counter()
    ux_lists: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    tags_by_solver: Dict[str, Counter] = defaultdict(Counter)
    overall_tags = Counter()
    tier_wins: Dict[str, Counter] = defaultdict(Counter)
    agreements = 0
    agreements_checked = 0
    disagreements: List[Dict[str, Any]] = []
    unique_members = set()

    for rec in records:
        unique_members.add(rec.get("member_id", ""))
        w_algo = rec.get("winner_solver", "")
        tier = rec.get("scenario_tier", "CUSTOM")
        if w_algo:
            wins[w_algo] += 1
            tier_wins[tier][w_algo] += 1

        if rec.get("agreed_with_v21_top1") is not None:
            agreements_checked += 1
            if rec["agreed_with_v21_top1"]:
                agreements += 1
            else:
                disagreements.append(
                    {
                        "member_name": rec.get("member_name", rec.get("member_id")),
                        "scenario_id": rec.get("scenario_id"),
                        "human_choice": w_algo,
                        "v21_top1": rec.get("v21_top1_solver"),
                        "notes": rec.get("notes", ""),
                    }
                )

        for algo, sc_map in (rec.get("ux_by_solver") or {}).items():
            vals: List[float] = []
            for uk in [u["key"] for u in UX_DIMENSIONS]:
                if uk in sc_map and sc_map[uk] is not None:
                    v = float(sc_map[uk])
                    ux_lists[algo][uk].append(v)
                    vals.append(v)
            if vals:
                ux_lists[algo]["mean"].append(sum(vals) / float(len(vals)))

        for tag_obj in rec.get("block_tags") or []:
            tag = str(tag_obj.get("tag") or "")
            algo = str(tag_obj.get("solver") or "")
            if tag:
                overall_tags[tag] += 1
                if algo:
                    tags_by_solver[algo][tag] += 1

    solver_stats: List[Dict[str, Any]] = []
    all_seen_solvers = sorted(set(wins.keys()) | set(ux_lists.keys()) | set(tags_by_solver.keys()))
    for algo in all_seen_solvers:
        w_cnt = wins[algo]
        win_pct = round(100.0 * w_cnt / total_reviews, 1) if total_reviews else 0.0
        mean_scores = {
            k: round(sum(xs) / len(xs), 2) if xs else None for k, xs in ux_lists[algo].items()
        }
        solver_stats.append(
            {
                "solver": algo,
                "blind_wins": w_cnt,
                "blind_win_rate_pct": win_pct,
                "mean_ux": mean_scores.get("mean"),
                "ux_breakdown": mean_scores,
                "top_block_tags": tags_by_solver[algo].most_common(4),
            }
        )
    solver_stats.sort(key=lambda x: (-x["blind_wins"], -(x["mean_ux"] or 0.0), x["solver"]))

    agree_pct = round(100.0 * agreements / agreements_checked, 1) if agreements_checked else 0.0
    summary = {
        "total_reviews": total_reviews,
        "participating_members": len(unique_members),
        "v21_top1_agreement_pct": agree_pct,
        "agreements_checked": agreements_checked,
        "agreements": agreements,
        "solver_stats": solver_stats,
        "overall_block_tags": overall_tags.most_common(7),
        "tier_wins": {t: dict(c) for t, c in tier_wins.items()},
        "disagreements": disagreements[:20],
        "report_path": str(report_path),
    }

    lines = [
        "# Báo Cáo Tổng Hợp Đánh Giá Mù Từ Thành Viên (`Member Calibration Report`)",
        "",
        f"- **Tổng số phiếu đánh giá:** `{total_reviews}` (`{len(unique_members)} / {len(GROUP_MEMBERS)}` thành viên đã tham gia)",
        f"- **Tỷ lệ đồng thuận Người dùng vs. `Testing_System v2.1` Rank #1:** `{agreements}/{agreements_checked}` (`{agree_pct}%`)",
        f"- **Cụm phàn nàn Block Tags nhiều nhất:** `{overall_tags.most_common(5)}`",
        "",
        "## 1. Bảng Xếp Hạng Trải Nghiệm Thực Tế Theo Thuật Toán",
        "",
        "| Thuật toán | Số lần thắng mù | Tỷ lệ thắng | Mean UX (`1–5`) | UX-1 | UX-2 | UX-3 | UX-4 | UX-5 | Tag phàn nàn hay gặp |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |",
    ]
    for st in solver_stats:
        ub = st["ux_breakdown"]
        mean_s = f"{st['mean_ux']:.2f}" if st["mean_ux"] is not None else "-"
        ux_cols = [
            f"{ub.get(u['key']):.2f}" if ub.get(u["key"]) is not None else "-" for u in UX_DIMENSIONS
        ]
        tags_s = ", ".join(f"{t}({n})" for t, n in st["top_block_tags"]) or "—"
        lines.append(
            f"| `{st['solver']}` | {st['blind_wins']} | {st['blind_win_rate_pct']}% | {mean_s} | "
            + " | ".join(ux_cols)
            + f" | {tags_s} |"
        )

    lines.extend(["", "## 2. Các Ca Bất Đồng (`Human Vote != v2.1 Rank #1`) Cần Xem Xét Tinh Chỉnh", ""])
    if disagreements:
        for d in disagreements:
            note_s = f" — *{d['notes']}*" if d.get("notes") else ""
            lines.append(
                f"- **{d['member_name']}** (`{d['scenario_id']}`): Chọn **`{d['human_choice']}`** thay vì `v2.1 #1` (`{d['v21_top1']}`){note_s}"
            )
    else:
        lines.append("- Chưa có ca bất đồng nào hoặc chưa có dữ liệu đánh giá.")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


class _MemberEvalHandler(BaseHTTPRequestHandler):
    """Lightweight stdlib HTTP handler serving `viewer.html` and JSON evaluation APIs."""

    def log_message(self, format: str, *args: Any) -> None:
        return  # Keep console uncluttered

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html_bytes = (_THIS_DIR / "viewer.html").read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
            return

        if path == "/api/eval/meta":
            self._send_json(
                HTTPStatus.OK,
                {
                    "members": GROUP_MEMBERS,
                    "scenarios": SCENARIO_CATALOG,
                    "solver_presets": {k: list(v) for k, v in SOLVER_PRESETS.items()},
                    "all_solvers": list(ALL_SOLVERS),
                    "ux_dimensions": UX_DIMENSIONS,
                    "block_issue_tags": BLOCK_ISSUE_TAGS,
                },
            )
            return

        if path == "/api/eval/aggregate":
            self._send_json(HTTPStatus.OK, aggregate_reviews(REVIEWS_DIR))
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Unknown route: {path}"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            body = self._read_json_body()
            if path == "/api/eval/generate":
                sid = str(body.get("scenario_id") or "PERSONAL_MINH")
                mid = str(body.get("member_id") or "25125028")
                preset = str(body.get("solver_preset") or "BLIND_3").upper()
                solvers = body.get("solvers") or list(SOLVER_PRESETS.get(preset, SOLVER_PRESETS["BLIND_3"]))
                seed = int(body.get("seed") or 42)
                custom_payload = body.get("custom_payload")
                packet = generate_blind_packet(
                    scenario_id=sid,
                    member_id=mid,
                    solvers=solvers,
                    seed=seed,
                    custom_payload=custom_payload,
                )
                self._send_json(HTTPStatus.OK, packet)
                return

            if path == "/api/eval/submit":
                res = save_member_review(body, reviews_dir=REVIEWS_DIR)
                self._send_json(HTTPStatus.OK, res)
                return

            self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Unknown route: {path}"})
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def _print_cli_packet(packet: Dict[str, Any], reveal: bool = True) -> None:
    """Format a readable CLI diagnostic view for terminal evaluation."""
    sc = packet["scenario"]
    print(f"=== CHẤM LỊCH TRUNG GIAN: {sc['scenario_id']} — {sc['title']} ({sc['horizon_days']} ngày) ===")
    print(f"Thành viên: {packet['member']['name']} ({packet['member']['member_id']}) | Tasks: {packet['tasks_count']}\n")
    for cand in packet["blind_candidates"]:
        sm = cand["summary"]
        print(
            f"  Phương án {cand['blind_id']}: Xếp {sm['tasks_placed']}/{sm['tasks_requested']} việc "
            f"({sm['total_blocks']} blocks, {sm['total_study_min']}p tự học), "
            f"Khớp giờ đỉnh (L>=2)={sm['peak_match_pct']}%, Đổi môn={sm['context_switches']}"
        )
    if not reveal:
        return

    oracle = packet["oracle_reveal"]
    print("\n--- BẢNG MỞ KHÓA ĐỐI CHIẾU `Testing_System v2.1` ---")
    print(f"Solver Rank #1 theo máy chấm v2.1: {oracle['v21_top1_solver']} ({oracle['solver_to_blind'][oracle['v21_top1_solver']]})")
    print(
        f"{'Rk':<3} {'Mù':<4} {'Solver':<14} {'Verdict':<29} {'G1':<3} {'P1.1%':<6} {'Shk25':<6} "
        f"{'Rec/Stk/PCl':<12} {'OffP/APk%':<10} {'<10h':<6} {'Crn/MaxD':<11} {'Ctx':<4} {'Hab/Prf':<10} {'SJL/TStd':<9} {'ms':<6}"
    )
    for row in oracle["v21_ranking"]:
        rc = f"{row['p2_recovery_rate_pct']:.0f}" if row["p2_recovery_rate_pct"] is not None else "-"
        rec_g = f"{rc}/{row['v2_max_streak_l2_min']}/{row['v2_post_class_violations']}"
        apk = f"{row['v2_achievable_peak_pct']:.0f}" if row["v2_achievable_peak_pct"] is not None else "N/A"
        bio_g = f"{row['v2_off_peak_mismatch']}/{apk}"
        crn = "/".join(str(x) for x in row["p3_corne_vector"])
        cap_g = f"{crn}/{row['v2_max_daily_total_min']}m"
        hab = f"{row['v2_habit_rate_pct']:.0f}" if row["v2_habit_rate_pct"] is not None else "-"
        prf = f"{row['v2_preferred_window_pct']:.0f}" if row["v2_preferred_window_pct"] is not None else "-"
        pref_g = f"{hab}/{prf}"
        sjl = f"{row['v2_sjl_effective_min']:.0f}" if row["v2_sjl_effective_min"] is not None else "-"
        pace_g = f"{sjl}/{row['v2_total_daily_std_min']:.0f}"
        print(
            f"#{row['lexicographic_rank']:<2} {row['blind_id']:<4} {row['solver_name']:<14} {row['verdict']:<29} "
            f"{row['g1_violations']:<3} {row['p1_value_rate_pct']:<6.1f} {row['p4_shock25_survived_pct']:<6.1f} "
            f"{rec_g:<12} {bio_g:<10} {row['p1_unjustified_last10h_pct']:<6.1f} {cap_g:<11} "
            f"{row['v2_context_switches']:<4} {pref_g:<10} {pace_g:<9} {row['exec_ms']:<6.1f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Group 03 Intermediate Schedule Evaluation Tool")
    parser.add_argument("--mode", choices=["serve", "cli", "aggregate"], default="serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--scenario", default="PERSONAL_MINH")
    parser.add_argument("--member", default="25125028")
    parser.add_argument("--solvers", nargs="+", default=list(SOLVER_PRESETS["BLIND_3"]))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--interactive", action="store_true", help="Prompt for CLI blind vote & UX scores")
    args = parser.parse_args()

    if args.mode == "aggregate":
        summary = aggregate_reviews(REVIEWS_DIR)
        print(Path(summary["report_path"]).read_text(encoding="utf-8"))
        return 0

    if args.mode == "cli":
        packet = generate_blind_packet(
            scenario_id=args.scenario, member_id=args.member, solvers=args.solvers, seed=args.seed
        )
        _print_cli_packet(packet, reveal=not args.interactive)
        if args.interactive:
            valid_ids = [c["blind_id"] for c in packet["blind_candidates"]]
            winner = input(f"\nChọn phương án bạn thích nhất {valid_ids}: ").strip().upper()
            if not winner.startswith("#"):
                winner = f"#{winner}"
            ux_scores = {}
            for c in packet["blind_candidates"]:
                b_id = c["blind_id"]
                row = {}
                print(f"Chấm điểm 1..5 cho Phương án {b_id}:")
                for u in UX_DIMENSIONS:
                    raw_v = input(f"  {u['label']}: ").strip() or "4"
                    row[u["key"]] = max(1, min(5, int(raw_v)))
                ux_scores[b_id] = row
            notes = input("Ghi chú điểm chưa hài lòng (tùy chọn): ").strip()
            res = save_member_review(
                {
                    "packet_id": packet["packet_id"],
                    "member_id": args.member,
                    "scenario_id": packet["scenario"]["scenario_id"],
                    "blind_winner_id": winner,
                    "ux_scores": ux_scores,
                    "notes": notes,
                }
            )
            _print_cli_packet(packet, reveal=True)
            print(f"\nĐã lưu phiếu chấm tại: {res['review_file']}")
        return 0

    server = ThreadingHTTPServer((args.host, args.port), _MemberEvalHandler)
    print(f"SmartSchedule Member Evaluation Workbench running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Member Evaluation Workbench.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
