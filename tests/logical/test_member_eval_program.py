"""
Verification Tests: Intermediate Member Schedule Evaluation Program (`member_eval`).
Covers:
  1. Blind multi-solver packet generation & solver-identity masking
  2. Review JSON persistence + human-vs-v2.1 aggregation (`Calibration_Report.md`)
  3. 14-day grid overlay + CLI execution smoke test
"""

import json
from pathlib import Path
import subprocess
import sys

from smartschedule.core.config import REPO_ROOT, TOOLS_DIR

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.member_eval.evaluate_schedule import (  # noqa: E402
    GROUP_MEMBERS,
    aggregate_reviews,
    generate_blind_packet,
    save_member_review,
)


def test_blind_packet_masks_solver_names_and_builds_v21_oracle():
    packet = generate_blind_packet(
        scenario_id="PERSONAL_MINH",
        member_id=GROUP_MEMBERS[0]["member_id"],
        solvers=("EDF", "SCORED_GREEDY", "HYBRID_ALNS"),
        seed=42,
    )
    assert len(packet["blind_candidates"]) == 3
    blind_ids = {c["blind_id"] for c in packet["blind_candidates"]}
    assert blind_ids == {"#A", "#B", "#C"}

    # Ensure solver names never leak into blind block reasons
    for cand in packet["blind_candidates"]:
        for blk in cand["blocks"]:
            reason = blk.get("reason", "")
            assert "[SCORED_GREEDY]" not in reason
            assert "[HYBRID_ALNS]" not in reason
            assert "[GREEDY_EDF" not in reason

    oracle = packet["oracle_reveal"]
    assert set(oracle["blind_to_solver"].values()) == {"EDF", "SCORED_GREEDY", "HYBRID_ALNS"}
    assert len(oracle["v21_ranking"]) == 3
    assert oracle["v21_ranking"][0]["g1_violations"] == 0


def test_review_persistence_and_calibration_aggregation(tmp_path):
    reviews_dir = tmp_path / "reviews"
    packet = generate_blind_packet(
        scenario_id="REGIME_3_CIRCADIAN",
        member_id="25125028",
        solvers=("EDF", "SCORED_GREEDY", "HYBRID_ALNS"),
        seed=5,
    )
    oracle = packet["oracle_reveal"]
    scored_blind = oracle["solver_to_blind"]["SCORED_GREEDY"]
    edf_blind = oracle["solver_to_blind"]["EDF"]

    res1 = save_member_review(
        {
            "packet_id": packet["packet_id"],
            "member_id": "25125028",
            "scenario_id": "REGIME_3_CIRCADIAN",
            "blind_winner_id": scored_blind,
            "ux_scores": {
                scored_blind: {
                    "ux_1_efficiency": 5,
                    "ux_2_energy_fit": 5,
                    "ux_3_fatigue_breaks": 5,
                    "ux_4_split_flow": 5,
                    "ux_5_resilience": 4,
                },
                edf_blind: {
                    "ux_1_efficiency": 4,
                    "ux_2_energy_fit": 1,
                    "ux_3_fatigue_breaks": 2,
                    "ux_4_split_flow": 3,
                    "ux_5_resilience": 3,
                },
            },
            "block_tags": [
                {
                    "blind_id": edf_blind,
                    "block_id": "EDF_B1",
                    "task_id": "R3_DEEP1",
                    "tag": "BAD_TIME_OF_DAY",
                }
            ],
            "notes": "SCORED_GREEDY blind schedule felt much better aligned.",
        },
        reviews_dir=reviews_dir,
    )

    assert res1["status"] == "SAVED"
    assert res1["record"]["winner_solver"] == "SCORED_GREEDY"
    assert Path(res1["review_file"]).exists()

    agg = res1["aggregation"]
    assert agg["total_reviews"] == 1
    assert agg["participating_members"] == 1
    assert Path(agg["report_path"]).exists()
    report_text = Path(agg["report_path"]).read_text(encoding="utf-8")
    assert "SCORED_GREEDY" in report_text
    assert "BAD_TIME_OF_DAY" in report_text

    agg2 = aggregate_reviews(reviews_dir=reviews_dir)
    assert agg2["total_reviews"] == 1


def test_14d_fuzz_packet_and_cli_execution():
    packet14 = generate_blind_packet(
        scenario_id="FUZZ_LOOSE_14D",
        member_id="25125007",
        solvers=("EDF", "SCORED_GREEDY", "BACKTRACK"),
        seed=42,
    )
    assert packet14["grid_overlay"]["horizon_days"] == 14
    assert len(packet14["grid_overlay"]["day_names"]) == 14

    script_path = TOOLS_DIR / "member_eval" / "evaluate_schedule.py"
    proc = subprocess.run(
        [sys.executable, "-B", str(script_path), "--mode", "cli", "--scenario", "PERSONAL_MINH", "--member", "25125028"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "PERSONAL_MINH" in proc.stdout
    assert "v2.1" in proc.stdout
