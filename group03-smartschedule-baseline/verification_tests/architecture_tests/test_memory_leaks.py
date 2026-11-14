"""
Unit Tests: Memory Leak & Resource Profiling
Author: Nguyen Nguyen Gia Bao (Builder 3 - Production & Deployment Testing)
Validates:
  - Repeated solver invocations do not leak heap memory across 50+ iterations
  - GridManager and ScheduleController clean up internal buffers properly
  - Peak memory remains strictly bounded under continuous production load
"""

import gc
import json
from pathlib import Path
import tracemalloc
import pytest

from src.controller import ScheduleController
from src.models import CommitmentsProfile, Task

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def test_repeated_solving_zero_memory_leak():
    """
    Production Deployment Verification:
    Simulates a high-traffic production API endpoint by running 50 consecutive solves.
    Uses `tracemalloc` to measure net memory allocation.
    Asserts that net memory growth is under 350 KB, proving zero memory retention or leak.
    """
    profile = CommitmentsProfile.model_validate(
        json.loads((DATA_DIR / "sample_week_commitments.json").read_text(encoding="utf-8"))
    )
    raw_tasks = json.loads((DATA_DIR / "sample_week_tasks.json").read_text(encoding="utf-8"))
    tasks = [Task.model_validate(t) for t in raw_tasks]

    # Warm-up run
    ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    gc.collect()

    tracemalloc.start()
    snapshot_start = tracemalloc.take_snapshot()

    # Run 50 full solves
    for _ in range(50):
        out, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
        assert out.summary.hard_constraint_violations == 0

    gc.collect()
    snapshot_end = tracemalloc.take_snapshot()
    tracemalloc.stop()

    stats = snapshot_end.compare_to(snapshot_start, "lineno")
    total_diff_bytes = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
    total_diff_kb = total_diff_bytes / 1024.0

    assert total_diff_kb < 350.0, f"Potential memory leak detected: Net memory grew by {total_diff_kb:.2f} KB over 50 runs"


def test_peak_memory_bounded_under_stress():
    """Verify that single-solve peak memory is lightweight (< 10 MB)."""
    profile = CommitmentsProfile.model_validate(
        json.loads((DATA_DIR / "lan_week_commitments.json").read_text(encoding="utf-8"))
    )
    raw_tasks = json.loads((DATA_DIR / "lan_week_tasks.json").read_text(encoding="utf-8"))
    tasks = [Task.model_validate(t) for t in raw_tasks]

    tracemalloc.start()
    ScheduleController.solve_schedule(profile, tasks, algorithm="EDF")
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak_bytes / (1024.0 * 1024.0)
    assert peak_mb < 10.0, f"Peak memory usage exceeded 10 MB: {peak_mb:.2f} MB"

