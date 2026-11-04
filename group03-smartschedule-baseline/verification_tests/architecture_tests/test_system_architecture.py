"""
Unit Tests: System Architecture Invariants & Layer Boundaries
Author: Nguyen Nguyen Gia Bao (Builder 3 - System Architecture & Testing)
Validates:
  - Clean Layered Architecture: Strict unidirectional dependency flow
  - Solvers must be purely stateless across consecutive runs
  - Grid manager locked masks (SLEEP, OCCUPIED) cannot be freed by task operations
"""

import ast
from pathlib import Path
import pytest

from src.controller import ScheduleController
from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, SleepSchedule, Task
from src.solvers.greedy_edf import GreedyEDFSolver

SRC_DIR = Path(__file__).resolve().parent.parent.parent / "src"


def _get_imported_modules(py_file: Path):
    """Extract all top-level imported module names from a Python source file using AST."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
    return imported


def test_layer_boundary_solvers_never_import_web_or_ui():
    """
    Architecture Invariant:
    The Scheduling Engine (Domain Core) must remain completely decoupled from
    the Web / Delivery layer. Nothing in `src/solvers/` may import `web` or `fastapi`.
    """
    solvers_dir = SRC_DIR / "solvers"
    for py_file in solvers_dir.glob("*.py"):
        imports = _get_imported_modules(py_file)
        for imp in imports:
            assert not imp.startswith("web"), f"Layer violation: {py_file.name} imports web layer '{imp}'"
            assert not imp.startswith("fastapi"), f"Layer violation: {py_file.name} imports framework '{imp}'"


def test_layer_boundary_models_is_pure_data_layer():
    """
    Architecture Invariant:
    `src/models.py` defines schemas and data contracts; it must never import `controller` or `solvers`.
    """
    models_file = SRC_DIR / "models.py"
    imports = _get_imported_modules(models_file)
    for imp in imports:
        assert not imp.startswith("src.controller"), f"Layer violation: models.py imports controller: '{imp}'"
        assert not imp.startswith("src.solvers"), f"Layer violation: models.py imports solvers: '{imp}'"


def test_solver_statelessness_isolation():
    """
    Architecture Invariant:
    Solvers must be completely stateless. Solving Set A and then Set B using the same solver
    instance must not retain any state, cached chunks, or residuals from Set A.
    """
    solver = GreedyEDFSolver()
    profile = CommitmentsProfile(
        student_id="TEST_STATELESS",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )

    tasks_run1 = [
        Task(task_id="T_RUN1", title="Run 1 Task", duration_min=60, deadline_day="Monday", deadline_time="12:00")
    ]
    tasks_run2 = [
        Task(task_id="T_RUN2", title="Run 2 Task", duration_min=90, deadline_day="Tuesday", deadline_time="18:00")
    ]

    out1, _ = solver.solve(profile, tasks_run1)
    out2, _ = solver.solve(profile, tasks_run2)

    task_ids_out1 = {b.task_id for b in out1.blocks}
    task_ids_out2 = {b.task_id for b in out2.blocks}

    assert "T_RUN1" in task_ids_out1 and "T_RUN2" not in task_ids_out1
    assert "T_RUN2" in task_ids_out2 and "T_RUN1" not in task_ids_out2
    assert out2.summary.total_tasks_requested == 1


def test_grid_mask_tamper_resistance():
    """
    Architecture Invariant:
    A call to remove or release blocks must NEVER be capable of
    clearing locked SLEEP or OCCUPIED commitment masks.
    """
    gm = TimeGridManager()
    profile = CommitmentsProfile(
        student_id="SEC_TEST",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    gm.initialize_from_profile(profile)

    # Monday 02:00 (slot 8) is protected SLEEP
    assert gm.grid[8] == TimeGridManager.STATE_SLEEP
    assert gm._locked_mask[8] == TimeGridManager.STATE_SLEEP

    # Attempt to remove block over slot 8
    gm.remove_block(0, 16)

    # Invariant check: Sleep mask must still be locked
    assert gm._locked_mask[8] == TimeGridManager.STATE_SLEEP
    assert gm.is_range_free(8, 1) is False

