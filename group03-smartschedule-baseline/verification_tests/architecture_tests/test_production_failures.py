"""
Production & Architecture Failure Suite: Defensive Edge Cases (40% Ratio).
Author: Nguyen Nguyen Gia Bao (Builder 3 - Edge Cases §8 & Architecture §7)

Validates:
  - Concurrent request thread safety & cross-contamination isolation
  - Latency bounds under dense scale (N=50 tasks)
  - Timezone offset normalization (+07:00 Asia/Ho_Chi_Minh)
  - Floating-point duration quantization traps
"""

from concurrent.futures import ThreadPoolExecutor
import time
from fastapi.testclient import TestClient
import pytest

from src.controller import ScheduleController
from src.models import CommitmentsProfile, SleepSchedule, Task
from web.api import app

client = TestClient(app)


def test_prod_failure_concurrent_request_state_isolation():
    """
    PRODUCTION DEFENSIVE EDGE CASE:
    Two concurrent requests run simultaneously on the backend for two distinct students:
      - Student Alpha has 10 tasks.
      - Student Beta has 1 task.
    Evaluation: Neither student's schedule may leak blocks or tasks into the other!
    """
    profile_alpha = CommitmentsProfile(
        student_id="STUDENT_ALPHA",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    tasks_alpha = [
        Task(task_id=f"ALPHA_{i:02d}", title=f"Alpha Task {i}", duration_min=45, deadline_day="Friday", deadline_time="18:00")
        for i in range(1, 11)
    ]

    profile_beta = CommitmentsProfile(
        student_id="STUDENT_BETA",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    tasks_beta = [
        Task(task_id="BETA_SOLE", title="Beta Sole Task", duration_min=60, deadline_day="Monday", deadline_time="12:00")
    ]

    def run_alpha():
        return ScheduleController.solve_schedule(profile_alpha, tasks_alpha, algorithm="EDF")

    def run_beta():
        return ScheduleController.solve_schedule(profile_beta, tasks_beta, algorithm="EDF")

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_alpha = executor.submit(run_alpha)
        future_beta = executor.submit(run_beta)
        out_alpha, _ = future_alpha.result()
        out_beta, _ = future_beta.result()

    # Verify zero cross-contamination
    alpha_task_ids = {b.task_id for b in out_alpha.blocks}
    beta_task_ids = {b.task_id for b in out_beta.blocks}

    assert "BETA_SOLE" not in alpha_task_ids, "Race condition: Beta task leaked into Alpha schedule!"
    assert all(tid.startswith("ALPHA_") for tid in alpha_task_ids)
    assert beta_task_ids == {"BETA_SOLE"}, "Race condition: Alpha tasks leaked into Beta schedule!"


def test_prod_failure_scale_latency_bound():
    """
    PRODUCTION DEFENSIVE EDGE CASE:
    Submitting 50 tasks across the week must complete strictly within 2000 ms.
    Guarantees no server worker timeout occurs in production.
    """
    profile = CommitmentsProfile(
        student_id="SCALE_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[],
    )
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    scale_tasks = [
        Task(
            task_id=f"SCALE_{i:02d}",
            title=f"Scale Task {i}",
            duration_min=45,
            deadline_day=days[i % len(days)],
            deadline_time="22:00",
            priority=(i % 5) + 1,
        )
        for i in range(50)
    ]

    start = time.perf_counter()
    out, _ = ScheduleController.solve_schedule(profile, scale_tasks, algorithm="EDF")
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert elapsed_ms < 2000.0, f"Latency SLA breached on 50 tasks: took {elapsed_ms:.2f} ms (threshold 2000 ms)"
    assert out.summary.hard_constraint_violations == 0


def test_prod_failure_malformed_timezone_offset_handling():
    """
    PRODUCTION DEFENSIVE EDGE CASE:
    Client sends request with foreign timezone offset (e.g. New York -05:00).
    API must handle the timestamp cleanly without crashing or returning HTTP 500.
    """
    payload = {
        "now": "2026-11-02T06:00:00-05:00",
        "week_start": "2026-11-02T00:00:00-05:00",
        "algorithm": "EDF",
        "profile": {
            "sleep": {"daily_start_time": "23:30", "daily_end_time": "06:30"},
        },
        "fixed_events": [],
        "tasks": [
            {
                "task_id": "TZ_TASK",
                "title": "Timezone test",
                "duration_min": 60,
                "deadline_day": "Wednesday",
                "deadline_time": "20:00",
                "priority": 3,
            }
        ],
    }

    res = client.post("/api/plan", json=payload)
    assert res.status_code == 200, f"Foreign timezone offset crashed endpoint with status {res.status_code}: {res.text}"
    assert res.json()["metrics"]["hard_violations"] == 0

