"""
Unit tests for Hard Constraints H1–H5 and auditor (`src/metrics.py` & `src/controller.py`).
Verifies:
  - H1: Zero overlap with fixed commitments (OCCUPIED)
  - H2: Zero overlap with sleep windows (SLEEP)
  - H3: Tasks placed strictly inside confirmed FREE slots
  - H4: Strict deadline adherence (end_slot <= deadline_slot)
  - H5: Task dependency topological ordering (`depends_on`)
  - Manual drag/move validation rejects illegal placements with human-readable explanation
"""

import json
from pathlib import Path

from src.controller import ScheduleController
from src.models import CommitmentsProfile, Task

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load_tasks(path: Path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw.get("tasks", [])
    return [Task.model_validate(t) for t in items]


def test_hard_constraints_zero_violation_on_presets():
    for comm_file, task_file in [
        ("sample_week_commitments.json", "sample_week_tasks.json"),
        ("lan_week_commitments.json", "lan_week_tasks.json"),
    ]:
        profile = CommitmentsProfile.model_validate(json.loads((DATA_DIR / comm_file).read_text(encoding="utf-8")))
        tasks = _load_tasks(DATA_DIR / task_file)

        for solver in ["EDF", "LST", "WSPT"]:
            output, _ = ScheduleController.solve_schedule(profile, tasks, algorithm=solver)
            assert output.summary.hard_constraint_violations == 0
            assert output.summary.deadline_satisfaction_rate == 100.0


def test_manual_move_validation_rejects_sleep_and_class_overlap():
    profile = CommitmentsProfile.model_validate(
        json.loads((DATA_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    )
    tasks = _load_tasks(DATA_DIR / "sample_week_tasks.json")

    output, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    first_block = output.blocks[0]

    # Attempt to move first_block into Monday 01:00 (SLEEP slot 4)
    res_sleep = ScheduleController.validate_manual_move(
        profile=profile,
        tasks=tasks,
        current_blocks=output.blocks,
        block_id=first_block.block_id,
        new_day="Monday",
        new_time="01:00",
    )
    assert res_sleep["ok"] is False
    assert any("SLEEP" in v["code"] for v in res_sleep["violations"])

    # Attempt to move first_block into Monday 13:00 (Class slot 52)
    res_class = ScheduleController.validate_manual_move(
        profile=profile,
        tasks=tasks,
        current_blocks=output.blocks,
        block_id=first_block.block_id,
        new_day="Monday",
        new_time="13:00",
    )
    assert res_class["ok"] is False
    assert any("COMMITMENT" in v["code"] for v in res_class["violations"])


def test_dependency_chain_strict_ordering():
    """Verifies H5: Task B depending on Task A is strictly scheduled after all chunks of Task A complete."""
    profile = CommitmentsProfile.model_validate(
        json.loads((DATA_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    )
    tasks = [
        Task(
            task_id="DEP-B",
            title="[SE301] Dependent Implementation (After Spec)",
            duration_min=90,
            deadline_day="Wednesday",
            deadline_time="22:00",
            priority=5,
            depends_on=["DEP-A"],
        ),
        Task(
            task_id="DEP-A",
            title="[SE301] Prerequisite Architecture Spec",
            duration_min=90,
            deadline_day="Thursday",
            deadline_time="22:00",
            priority=2,
            depends_on=[],
        ),
    ]

    output, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    assert output.summary.hard_constraint_violations == 0

    blocks_a = [b for b in output.blocks if b.task_id == "DEP-A"]
    blocks_b = [b for b in output.blocks if b.task_id == "DEP-B"]
    assert len(blocks_a) >= 1 and len(blocks_b) >= 1

    max_end_a = max(b.end_slot for b in blocks_a)
    min_start_b = min(b.start_slot for b in blocks_b)
    assert min_start_b >= max_end_a, f"Dependency violated: B started at {min_start_b} before A ended at {max_end_a}"
