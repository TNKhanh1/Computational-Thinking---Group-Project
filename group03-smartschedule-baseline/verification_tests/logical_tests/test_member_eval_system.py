"""
Verification Tests: Member-in-the-Loop Blind Evaluation System (`member_eval/`).

Validates `Testing_Plan/evaluation_plan.md`:
  - Strict INV-1..6 isolation (zero imports of `member_eval` in `src/` or `Testing_System/`)
  - Deterministic blind anonymization (`#A/#B/#C`) with zero solver-name or oracle leakage before submit
  - Full blind session -> UX-1..UX-6 submit -> Oracle reveal -> Agreement confirm -> Aggregator calibration flow
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

BASELINE_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BASELINE_ROOT.parent
PLAN_ROOT = REPO_ROOT / "v1.0-alpha-plan"
TESTING_SYS_DIR = (REPO_ROOT / "Testing_System") if (REPO_ROOT / "Testing_System").is_dir() else (PLAN_ROOT / "Testing_System")
for p in (str(REPO_ROOT), str(PLAN_ROOT), str(BASELINE_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from member_eval.app import app as eval_app  # noqa: E402
from member_eval.blind_runner import (  # noqa: E402
    build_blind_packet,
    strip_oracle_for_blind_client,
)
from member_eval.scenarios import get_personal_week_template  # noqa: E402


def _imports_in_file(py_file: Path) -> set[str]:
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def test_member_eval_architecture_isolation() -> None:
    """Neither `src/` nor `Testing_System/` may import `member_eval`."""
    for folder in (BASELINE_ROOT / "src", TESTING_SYS_DIR):
        for py_file in folder.rglob("*.py"):
            imps = _imports_in_file(py_file)
            for mod in imps:
                assert not mod.startswith("member_eval"), f"Layer violation in {py_file}: imports {mod}"


def test_blind_packet_determinism_and_zero_leak() -> None:
    """`strip_oracle_for_blind_client` must be deterministic and leak zero solver identities."""
    p1 = build_blind_packet(member_id="minh_anh", scenario_id="R3_CIRCADIAN_S5", mode="standard_3", seed=2026)
    p2 = build_blind_packet(member_id="minh_anh", scenario_id="R3_CIRCADIAN_S5", mode="standard_3", seed=2026)
    assert p1["revealed_oracle"]["blind_mapping"] == p2["revealed_oracle"]["blind_mapping"]

    blind_payload = strip_oracle_for_blind_client(p1)
    assert [c["blind_id"] for c in blind_payload["blind_candidates"]] == ["#A", "#B", "#C"]

    serialized = json.dumps(blind_payload, ensure_ascii=False)
    forbidden_tokens = (
        "SCORED_GREEDY",
        "HYBRID_ALNS",
        "BACKTRACK",
        "GreedyEDF",
        "GREEDY_EDF",
        "GREEDY_WSPT",
        "GREEDY_LST",
        "revealed_oracle",
        "blind_mapping",
        "v21_vector",
    )
    for token in forbidden_tokens:
        assert token not in serialized, f"Blind payload leaked oracle/solver token: {token}"

    # Verify 14-day Fuzz scenario builds cleanly too
    fuzz_pkt = build_blind_packet(member_id="duc_minh", scenario_id="FUZZ_LOOSE_14D_S1041", mode="standard_3", seed=77)
    fuzz_blind = strip_oracle_for_blind_client(fuzz_pkt)
    assert fuzz_blind["horizon_days"] >= 14
    assert len(fuzz_blind["profile"]["energy_by_slot"]) >= 1344


def test_member_eval_api_full_blind_to_reveal_and_aggregate_flow(tmp_path, monkeypatch) -> None:
    """Verify full E2E API workflow: meta -> NL parse -> session -> submit reveal -> agree -> report."""
    monkeypatch.setenv("SMARTSCHEDULE_EVAL_DIR", str(tmp_path))
    client = TestClient(eval_app)

    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "Phiên Chấm Mù" in r_home.text

    r_meta = client.get("/api/eval/meta")
    assert r_meta.status_code == 200
    meta = r_meta.json()
    assert len(meta["members"]) >= 7
    assert len(meta["scenarios"]) >= 8
    assert len(meta["official_block_tags"]) == 7

    # EN/VI NL parse inside Personal Week helper
    r_nl = client.post("/api/eval/nl-parse", json={"prompt": "Ôn tập CSDL 90p trước tối thứ 6", "engine": "offline"})
    assert r_nl.status_code == 200
    assert r_nl.json()["draft"]["duration_min"] == 90

    # Session 1: Preset R1_LOOSE_S1
    r_sess1 = client.post(
        "/api/eval/session",
        json={"member_id": "minh_anh", "scenario_id": "R1_LOOSE_S1", "mode": "standard_3", "seed": 2026},
    )
    assert r_sess1.status_code == 200
    bv1 = r_sess1.json()
    assert "revealed_oracle" not in bv1
    assert "blind_mapping" not in json.dumps(bv1)
    cand_ids = [c["blind_id"] for c in bv1["blind_candidates"]]
    assert cand_ids == ["#A", "#B", "#C"]

    # Validation check: out-of-range score rejected
    bad_scores = {cid: {f"UX-{i}": 6 for i in range(1, 6)} for cid in cand_ids}
    r_bad = client.post(
        "/api/eval/submit",
        json={
            "packet_id": bv1["packet_id"],
            "member_id": "minh_anh",
            "scores_by_blind_id": bad_scores,
            "blind_winner_id": "#A",
            "block_tags": [],
        },
    )
    assert r_bad.status_code == 400

    # Valid submit unlocks v2.1 oracle and persists review JSON
    first_block = next((c["blocks"][0] for c in bv1["blind_candidates"] if c["blocks"]), None)
    good_scores = {
        "#A": {"UX-1": 4, "UX-2": 5, "UX-3": 4, "UX-4": 4, "UX-5": 4},
        "#B": {"UX-1": 3, "UX-2": 3, "UX-3": 3, "UX-4": 3, "UX-5": 3},
        "#C": {"UX-1": 4, "UX-2": 4, "UX-3": 4, "UX-4": 4, "UX-5": 4},
    }
    tags_payload = []
    if first_block:
        tags_payload.append({
            "blind_id": "#A",
            "block_id": first_block["block_id"],
            "task_id": first_block["task_id"],
            "tag": "CONTEXT_JUMP",
            "note": "Test tag cluster",
        })

    r_sub1 = client.post(
        "/api/eval/submit",
        json={
            "packet_id": bv1["packet_id"],
            "member_id": "minh_anh",
            "scores_by_blind_id": good_scores,
            "blind_winner_id": "#A",
            "block_tags": tags_payload,
            "free_text_notes": "Lịch #A dễ theo dõi.",
        },
    )
    assert r_sub1.status_code == 200
    sub1 = r_sub1.json()
    assert sub1["status"] == "SUBMITTED_AND_REVEALED"
    assert set(sub1["blind_mapping"].keys()) == {"#A", "#B", "#C"}
    assert len(sub1["cross_solver_ranking"]) == 3
    assert sub1["machine_vs_human"]["human_winner_solver"] == sub1["blind_mapping"]["#A"]
    assert (tmp_path / "reviews" / sub1["review_file"]).exists()

    # Confirm post-reveal agreement
    r_agree = client.post(
        "/api/eval/confirm-agreement",
        json={"review_file": sub1["review_file"], "revealed_diff_agree": True},
    )
    assert r_agree.status_code == 200
    assert r_agree.json()["revealed_diff_agree"] is True

    # Session 2: Custom Personal Week
    tpl = get_personal_week_template()
    r_sess2 = client.post(
        "/api/eval/session",
        json={
            "member_id": "duc_minh",
            "scenario_id": "PERSONAL_WEEK",
            "mode": "standard_3",
            "commitments": tpl["commitments"],
            "tasks": tpl["tasks"],
            "seed": 99,
        },
    )
    assert r_sess2.status_code == 200
    bv2 = r_sess2.json()
    assert bv2["scenario_category"] == "PERSONAL"

    # Aggregator report & Calibration_Report.md export
    r_rep = client.get("/api/eval/report?write_md=true")
    assert r_rep.status_code == 200
    rep_data = r_rep.json()
    summary = rep_data["summary"]
    assert summary["total_sessions"] == 1
    assert summary["unique_members"] == ["minh_anh"]
    if tags_payload:
        cj = next(fc for fc in summary["friction_clusters"] if fc["tag"] == "CONTEXT_JUMP")
        assert cj["is_friction_cluster"] is True
        assert "score_candidate_unit" in cj["calibration_hint"]
    assert (tmp_path / "Calibration_Report.md").exists()
    assert "Báo Cáo Tổng Hợp Đánh Giá Mù" in rep_data["markdown"]
