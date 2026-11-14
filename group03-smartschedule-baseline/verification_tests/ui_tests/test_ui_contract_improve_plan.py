"""
UI Test: Improve Plan (§7.3) JSON Data Contract Compliance
Author: Nguyen Nguyen Gia Bao (Builder 3 - System Architecture & Testing)
Validates:
  - Input contract with ISO 8601 datetimes, explicit 'now', and 'week_start'
  - Profile structure (sleep, focus preference, fixed events)
  - Output contract: 'blocks' containing 'state', 'reasons', 'allowed_starts', and 'metrics'
"""

from fastapi.testclient import TestClient
from web.api import app

client = TestClient(app)


def test_improve_plan_section7_json_contract():
    """
    Validates that POST /api/plan strictly accepts the Improve Plan §7.3 payload
    and produces the required structure for the student-facing Weekly UI.
    """
    request_payload = {
        "now": "2026-11-02T06:00:00+07:00",
        "week_start": "2026-11-02T00:00:00+07:00",
        "algorithm": "EDF",
        "profile": {
            "sleep": {"daily_start_time": "23:30", "daily_end_time": "06:30"},
            "focus_preference": "EVENING",
            "estimate_habit": "SOMETIMES",
        },
        "fixed_events": [
            {
                "event_id": "LEC_1",
                "title": "Computer Architecture",
                "day_of_week": "Monday",
                "start_time": "07:30",
                "end_time": "11:30",
            }
        ],
        "tasks": [
            {
                "task_id": "T1",
                "title": "Essay: write body",
                "duration_min": 60,
                "deadline_day": "Wednesday",
                "deadline_time": "23:59",
                "priority": 3,
                "is_splittable": True,
                "min_chunk_min": 45,
            }
        ],
        "pinned_blocks": [],
    }

    res = client.post("/api/plan", json=request_payload)
    assert res.status_code == 200, f"Contract rejection: {res.text}"
    data = res.json()

    # Verify Improve Plan §7.3 response fields
    assert "status" in data
    assert "blocks" in data
    assert "unplaced" in data
    assert "metrics" in data

    blocks = data["blocks"]
    assert len(blocks) >= 1
    b0 = blocks[0]

    # Verify block structure
    assert "block_id" in b0
    assert "task_id" in b0
    assert "start_time" in b0
    assert "end_time" in b0
    assert "state" in b0
    assert "reasons" in b0
    assert "allowed_starts" in b0

    # Verify metrics structure
    metrics = data["metrics"]
    assert "hard_violations" in metrics
    assert "deadline_rate" in metrics
    assert "exec_ms" in metrics
    assert metrics["hard_violations"] == 0






