"""
Standalone FastAPI Server for Member-in-the-Loop Blind Schedule Evaluation (`127.0.0.1:8010`).

Strictly decoupled from `Testing_System/` internals (`INV-1..INV-6`): only exposes
the blind UI viewer, blind session creation, review submission (unlocking the sealed
`revealed_oracle`), agreement confirmation, EN/VI NL task parsing, and aggregated calibration reports.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional


def _ensure_paths() -> None:
    baseline_root = str(Path(__file__).resolve().parents[1])
    repo_root = str(Path(__file__).resolve().parents[2])
    for p in (repo_root, baseline_root):
        if p not in sys.path:
            sys.path.insert(0, p)


_ensure_paths()

from fastapi import Body, FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

from member_eval import (  # noqa: E402
    OFFICIAL_BLOCK_TAGS,
    OFFICIAL_BLOCK_TAGS_META,
    TEAM_MEMBERS,
    UX_CRITERIA,
)
from member_eval.aggregator import (  # noqa: E402
    aggregate_reviews,
    load_reviews,
    render_calibration_report_md,
)
from member_eval.blind_runner import (  # noqa: E402
    build_blind_packet,
    get_packets_dir,
    get_reviews_dir,
    load_packet,
    sanitize_slug,
    save_packet,
    strip_oracle_for_blind_client,
)
from member_eval.scenarios import get_personal_week_template, list_scenarios  # noqa: E402
from src.nl_parser import parse_natural_language_task  # noqa: E402

MODULE_DIR = Path(__file__).resolve().parent
VIEWER_HTML = MODULE_DIR / "viewer.html"

app = FastAPI(
    title="SmartSchedule — Member-in-the-Loop Blind Evaluator",
    description="Blind A/B Multi-Solver Evaluation Portal for Group 03 & Real Students (Port 8010)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
def serve_viewer():
    return FileResponse(VIEWER_HTML)


@app.get("/api/eval/meta")
def api_eval_meta():
    reviews_dir = get_reviews_dir()
    reviews = load_reviews(reviews_dir)
    summary = aggregate_reviews(reviews)
    return {
        "members": TEAM_MEMBERS,
        "ux_criteria": UX_CRITERIA,
        "block_tags": OFFICIAL_BLOCK_TAGS_META,
        "official_block_tags": list(OFFICIAL_BLOCK_TAGS),
        "scenarios": list_scenarios(),
        "personal_week_template": get_personal_week_template(),
        "saved_reviews_count": len(reviews),
        "reviews_summary": {
            "total_sessions": summary["total_sessions"],
            "unique_members": summary["unique_members"],
            "sessions_by_category": summary["sessions_by_category"],
        },
    }


@app.post("/api/eval/nl-parse")
def api_eval_nl_parse(payload: Dict[str, Any] = Body(...)):
    prompt = str(payload.get("prompt") or payload.get("text") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt text cannot be empty.")
    try:
        return parse_natural_language_task(
            prompt=prompt,
            now=payload.get("now"),
            existing_count=int(payload.get("existing_count") or 0),
            engine=payload.get("engine") or "offline",
            translation_backend=str(payload.get("translation_backend") or "rule"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/eval/session")
def api_eval_create_session(payload: Dict[str, Any] = Body(...)):
    """Create a blind evaluation packet and return ONLY `blind_view` (zero oracle/solver leakage)."""
    try:
        member_id = str(payload.get("member_id") or "guest_student").strip() or "guest_student"
        scenario_id = str(payload.get("scenario_id") or "R1_LOOSE_S1").strip()
        mode = str(payload.get("mode") or "standard_3").strip().lower()
        solvers = payload.get("solvers") if isinstance(payload.get("solvers"), list) else None
        seed = int(payload.get("seed") if payload.get("seed") is not None else 2026)

        custom_profile = payload.get("commitments") or payload.get("custom_profile")
        custom_tasks = payload.get("tasks") or payload.get("custom_tasks")
        custom_pinned = payload.get("pinned_blocks")

        packet = build_blind_packet(
            member_id=member_id,
            scenario_id=scenario_id,
            mode=mode,
            solvers=solvers,
            custom_profile=custom_profile,
            custom_tasks=custom_tasks,
            custom_pinned=custom_pinned,
            custom_title_vi=payload.get("custom_title_vi"),
            seed=seed,
        )
        save_packet(packet, packets_dir=get_packets_dir())
        return strip_oracle_for_blind_client(packet)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/eval/submit")
def api_eval_submit_review(payload: Dict[str, Any] = Body(...)):
    """Validate blind review, persist JSON review, and unlock `revealed_oracle`."""
    packet_id = str(payload.get("packet_id") or "").strip()
    if not packet_id:
        raise HTTPException(status_code=400, detail="Missing packet_id.")

    try:
        packet = load_packet(packet_id, packets_dir=get_packets_dir())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    blind_view = packet["blind_view"]
    oracle = packet["revealed_oracle"]
    blind_mapping: Dict[str, str] = oracle["blind_mapping"]
    candidate_ids = [c["blind_id"] for c in blind_view["blind_candidates"]]

    member_id = str(payload.get("member_id") or blind_view.get("member_id") or "guest_student").strip()
    role = str(payload.get("role") or "").strip()
    if not role:
        matched = next((m for m in TEAM_MEMBERS if m["member_id"] == member_id), None)
        role = matched["role"] if matched else "Student Evaluator"

    blind_winner_id = str(payload.get("blind_winner_id") or "").strip()
    if blind_winner_id not in candidate_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid blind_winner_id '{blind_winner_id}'. Must be one of {candidate_ids}.",
        )

    scores_raw = payload.get("scores_by_blind_id")
    if not isinstance(scores_raw, dict):
        raise HTTPException(status_code=400, detail="Missing scores_by_blind_id mapping.")

    validated_scores: Dict[str, Dict[str, int]] = {}
    for cid in candidate_ids:
        c_scores = scores_raw.get(cid)
        if not isinstance(c_scores, dict):
            raise HTTPException(status_code=400, detail=f"Missing UX scores for candidate '{cid}'.")
        clean_cand: Dict[str, int] = {}
        for idx in range(1, 6):
            uk = f"UX-{idx}"
            val = c_scores.get(uk)
            if not isinstance(val, (int, float)) or isinstance(val, bool) or int(val) < 1 or int(val) > 5:
                raise HTTPException(
                    status_code=400,
                    detail=f"Score {cid}.{uk} must be integer in 1..5 (got {val!r}).",
                )
            clean_cand[uk] = int(val)
        validated_scores[cid] = clean_cand

    raw_tags = payload.get("block_tags") or []
    validated_tags: List[Dict[str, Any]] = []
    if not isinstance(raw_tags, list):
        raise HTTPException(status_code=400, detail="block_tags must be a list.")
    for item in raw_tags:
        if not isinstance(item, dict):
            continue
        tag_name = str(item.get("tag") or "").strip().upper()
        if tag_name not in OFFICIAL_BLOCK_TAGS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported block tag '{tag_name}'. Official tags: {OFFICIAL_BLOCK_TAGS}",
            )
        b_cand = str(item.get("blind_id") or "").strip()
        if b_cand not in candidate_ids:
            raise HTTPException(status_code=400, detail=f"Tag references invalid blind_id '{b_cand}'.")
        validated_tags.append({
            "blind_id": b_cand,
            "block_id": str(item.get("block_id") or ""),
            "task_id": str(item.get("task_id") or ""),
            "tag": tag_name,
            "note": str(item.get("note") or ""),
        })

    free_text_notes = str(payload.get("free_text_notes") or "").strip()
    winner_solver = blind_mapping[blind_winner_id]
    winner_rep = oracle["reports_by_blind_id"][blind_winner_id]
    rank1_row = oracle["cross_solver_ranking"][0] if oracle["cross_solver_ranking"] else None
    v21_rank1_solver = rank1_row["solver_name"] if rank1_row else winner_solver
    v21_rank1_blind = rank1_row.get("blind_id") if rank1_row else blind_winner_id

    machine_vs_human = {
        "human_winner_blind_id": blind_winner_id,
        "human_winner_solver": winner_solver,
        "human_winner_verdict": winner_rep["verdict"],
        "human_winner_v21_rank": winner_rep["lexicographic_rank"],
        "v21_rank1_blind_id": v21_rank1_blind,
        "v21_rank1_solver": v21_rank1_solver,
        "v21_rank1_verdict": rank1_row["verdict"] if rank1_row else winner_rep["verdict"],
        "agreed_top1": winner_solver == v21_rank1_solver,
        "agreed_top2": int(winner_rep["lexicographic_rank"]) <= 2,
    }

    review_record = {
        "review_version": "1.0",
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "packet_id": packet_id,
        "member_id": member_id,
        "role": role,
        "scenario_id": blind_view["scenario_id"],
        "scenario_title_vi": blind_view["scenario_title_vi"],
        "scenario_category": blind_view["scenario_category"],
        "mode": blind_view["mode"],
        "blind_mapping": blind_mapping,
        "scores_by_blind_id": validated_scores,
        "blind_winner_id": blind_winner_id,
        "blind_winner_solver": winner_solver,
        "block_tags": validated_tags,
        "free_text_notes": free_text_notes,
        "revealed_diff_agree": payload.get("revealed_diff_agree"),
        "machine_vs_human": machine_vs_human,
        "reports_by_blind_id": oracle["reports_by_blind_id"],
        "cross_solver_ranking": oracle["cross_solver_ranking"],
    }

    reviews_dir = get_reviews_dir()
    review_filename = f"{sanitize_slug(member_id)}_{sanitize_slug(blind_view['scenario_id'])}.json"
    review_path = reviews_dir / review_filename
    review_path.write_text(json.dumps(review_record, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "status": "SUBMITTED_AND_REVEALED",
        "review_file": review_filename,
        "blind_mapping": blind_mapping,
        "machine_vs_human": machine_vs_human,
        "cross_solver_ranking": oracle["cross_solver_ranking"],
        "reports_by_blind_id": oracle["reports_by_blind_id"],
    }


@app.post("/api/eval/confirm-agreement")
def api_eval_confirm_agreement(payload: Dict[str, Any] = Body(...)):
    member_id = str(payload.get("member_id") or "").strip()
    scenario_id = str(payload.get("scenario_id") or "").strip()
    review_file = str(payload.get("review_file") or "").strip()
    agree = payload.get("revealed_diff_agree")
    if not isinstance(agree, bool):
        raise HTTPException(status_code=400, detail="revealed_diff_agree must be boolean.")

    reviews_dir = get_reviews_dir()
    if review_file:
        target = reviews_dir / Path(review_file).name
    elif member_id and scenario_id:
        target = reviews_dir / f"{sanitize_slug(member_id)}_{sanitize_slug(scenario_id)}.json"
    else:
        raise HTTPException(status_code=400, detail="Provide review_file or (member_id, scenario_id).")

    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Review file '{target.name}' not found.")

    data = json.loads(target.read_text(encoding="utf-8"))
    data["revealed_diff_agree"] = agree
    if payload.get("post_reveal_note") is not None:
        data["post_reveal_note"] = str(payload.get("post_reveal_note"))
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "UPDATED", "review_file": target.name, "revealed_diff_agree": agree}


@app.get("/api/eval/report")
def api_eval_report(write_md: bool = False):
    reviews_dir = get_reviews_dir()
    reviews = load_reviews(reviews_dir)
    summary = aggregate_reviews(reviews)
    md = render_calibration_report_md(summary)
    if write_md:
        target = reviews_dir.parent / "Calibration_Report.md"
        target.write_text(md, encoding="utf-8")
    return {"summary": summary, "markdown": md}
