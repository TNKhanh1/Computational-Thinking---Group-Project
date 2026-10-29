"""
Unit tests for Baseline Solvers (`GreedyEDFSolver`, `GreedyLSTSolver`, `GreedyWSPTSolver`, `BacktrackingSolver`)
and `LocalRepairEngine` (`LOCAL_INSERTION` vs `FULL_REBUILD` vs `RIPPLE_SHIFT`).
"""

import json
from pathlib import Path

from src.controller import ScheduleController
from src.models import CommitmentsProfile, DisruptionEvent, Task

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def test_3x_determinism_hash_equality():
    profile = CommitmentsProfile.model_validate(
        json.loads((DATA_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    )
    raw_tasks = json.loads((DATA_DIR / "sample_week_tasks.json").read_text(encoding="utf-8"))
    items = raw_tasks if isinstance(raw_tasks, list) else raw_tasks.get("tasks", [])
    tasks = [Task.model_validate(t) for t in items]

    for solver_key in ["EDF", "LST", "WSPT", "BACKTRACK"]:
        det = ScheduleController.verify_determinism(profile, tasks, algorithm=solver_key, runs=3)
        assert det["is_deterministic"] is True
        assert len(det["unique_hash"]) >= 16


def test_local_repair_vs_full_rebuild_stability():
    """Verifies that Local Insertion preserves unaffected study blocks during a mid-week disruption."""
    t04_path = DATA_DIR / "test_scenarios" / "t04_event_disruption.json"
    raw = json.loads(t04_path.read_text(encoding="utf-8"))
    profile = CommitmentsProfile.model_validate(raw["commitments"])
    tasks = [Task.model_validate(t) for t in raw["tasks"]]
    dis_raw = raw.get("disruption") or raw.get("disruption_event")
    disruption = DisruptionEvent.model_validate(dis_raw)

    initial, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    cmp = ScheduleController.compare_repair_modes(profile, tasks, initial, disruption)

    loc = cmp["local_repair"]
    full = cmp["full_rebuild"]

    assert loc.schedule.summary.hard_constraint_violations == 0
    assert full.schedule.summary.hard_constraint_violations == 0
    assert loc.schedule.summary.deadline_satisfaction_rate == 100.0
    assert loc.stability_score >= 90.0
    assert loc.stability_score >= full.stability_score
