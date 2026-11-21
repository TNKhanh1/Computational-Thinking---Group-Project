"""
Verification tests for Chat-First UI/UX Rebuild, Left Taskbar, Developer Mode,
SHA-256 Task Traceability, Multi-Turn Clarification, Remaining-Time + Habit Buffer,
and Deadlock / Dense-Schedule Edge Cases.
"""

from __future__ import annotations

import ast
import os
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from src.task_tracer import (
    compute_keyword_hashes,
    compute_task_trace_hash,
    enrich_task_trace_metadata,
    extract_hidden_criteria_updates,
    resolve_target_task_from_prompt,
)
from web.api import app

BASELINE_ROOT = Path(__file__).resolve().parents[2]
client = TestClient(app)


def _base_commitments():
    return {
        "student_id": "TEST_CHAT_UI",
        "planning_week_start": "2026-11-02T00:00:00+07:00",
        "now": "2026-11-02T08:00:00+07:00",
        "sleep_schedule": {"daily_start_time": "23:30", "daily_end_time": "06:30", "is_hard_lock": True},
        "fixed_events": [],
        "estimate_habit": "SOMETIMES",
        "focus_preference": "MORNING",
        "buffer_mode": "COGNITIVE_LOAD",
        "alpha_light": 1.2,
        "alpha_heavy": 1.35,
        "horizon_days": 7,
        "personal_habits": [],
    }


def test_task_tracer_layer1_ast_purity() -> None:
    """INV-1 & INV-2: src/task_tracer.py must remain pure Layer 1 stdlib only."""
    tracer_path = BASELINE_ROOT / "src" / "task_tracer.py"
    tree = ast.parse(tracer_path.read_text(encoding="utf-8"), filename=str(tracer_path))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    for imp in imported:
        assert not imp.startswith("web"), f"Layer violation in task_tracer.py: {imp}"
        assert not imp.startswith("fastapi"), f"Layer violation in task_tracer.py: {imp}"
        assert not imp.startswith("src.controller"), f"Layer violation in task_tracer.py: {imp}"
        assert not imp.startswith("src.solvers"), f"Layer violation in task_tracer.py: {imp}"


def test_sha256_task_traceability_and_hidden_criteria_extraction() -> None:
    """Deterministic SHA-256 keyword fingerprinting must locate tasks and extract hidden parameters."""
    t1 = enrich_task_trace_metadata(
        {
            "task_id": "T_MATH",
            "title": "Bài tập Giải tích 2",
            "duration_min": 90,
            "deadline_day": "Friday",
            "category": "ASSIGNMENT",
        }
    )
    t2 = enrich_task_trace_metadata(
        {
            "task_id": "T_ENG",
            "title": "Thuyết trình Tiếng Anh",
            "duration_min": 60,
            "deadline_day": "Thursday",
            "category": "PROJECT",
        }
    )
    assert len(t1["trace_hash"]) == 64
    assert t1["trace_hash"] == compute_task_trace_hash("Bài tập Giải tích 2", "ASSIGNMENT")
    assert len(t1["keyword_hashes"]) >= 2

    match = resolve_target_task_from_prompt(
        "Bài tập Giải tích nặng quá, chia nhỏ ra nhiều buổi và xếp vào buổi sáng giúp mình",
        [t1, t2],
    )
    assert match["matched"] is True
    assert match["task_id"] == "T_MATH"
    assert match["trace_hash"] == t1["trace_hash"]

    hidden = extract_hidden_criteria_updates(
        "Bài này nặng quá, chia nhỏ ra nhiều buổi ngắn và xếp theo nhịp sinh học lúc tỉnh táo",
        focus_preference="MORNING",
    )
    assert hidden["has_hidden_updates"] is True
    assert hidden["updates"]["cognitive_load"] == 3
    assert hidden["updates"]["is_splittable"] is True
    assert hidden["updates"]["work_rhythm"] == "LIGHT"
    assert hidden["updates"]["preferred_window"] == "MORNING"
    assert hidden["updates"]["buffer_multiplier"] == 1.35


def test_chat_turn_multi_turn_clarification_and_recurring_schedule(tmp_path, monkeypatch) -> None:
    """Missing content or start/end time must trigger clarification, then apply in < 10s SLA."""
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "chat_test.db"))
    comm = _base_commitments()
    # Turn 1: Missing time range for recurring schedule
    r1 = client.post(
        "/api/chat/turn",
        json={
            "prompt": "Thêm lịch tập gym hằng ngày",
            "mode_hint": "ADD_RECURRING",
            "commitments": comm,
            "tasks": [],
            "auto_save": False,
        },
    )
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["status"] == "NEEDS_CLARIFICATION"
    assert "time_range" in d1["missing_fields"]
    assert len(d1["quick_chips"]) >= 2

    # Turn 2: Provide start/end time -> applied immediately
    r2 = client.post(
        "/api/chat/turn",
        json={
            "prompt": "từ 18:00 đến 19:00",
            "mode_hint": "ADD_RECURRING",
            "pending_draft": d1["pending_draft"],
            "commitments": d1["updated_commitments"],
            "tasks": d1["updated_tasks"],
            "auto_save": False,
        },
    )
    assert r2.status_code == 200, r2.text
    d2 = r2.json()
    assert d2["status"] == "APPLIED"
    assert d2["execution_time_ms"] < 10000.0
    fixed = d2["updated_commitments"]["fixed_events"]
    assert any(ev["start_time"] == "18:00" and ev["end_time"] == "19:00" for ev in fixed)
    assert any(act["action"] == "OPEN_CALENDAR" and "Kiểm tra lịch trình" in act["label"] for act in d2["post_actions"])


def test_cross_day_window_single_task_parsing_and_thinking_stage(tmp_path, monkeypatch) -> None:
    """User prompt 'từ 19h ngày thứ 3, tới 21h ngày thứ 5, cần thực hiện trong 2 tiếng' must be 1 task, not 3."""
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "chat_cross_day.db"))
    comm = _base_commitments()
    preset_tasks = [
        enrich_task_trace_metadata(
            {
                "task_id": "T_P1",
                "title": "Đọc tài liệu tham khảo",
                "duration_min": 60,
                "deadline_day": "Wednesday",
                "category": "SELF_STUDY",
            }
        ),
        enrich_task_trace_metadata(
            {
                "task_id": "T_P2",
                "title": "Ôn thi giữa kỳ Đại số tuyến tính",
                "duration_min": 90,
                "deadline_day": "Friday",
                "category": "EXAM_PREP",
            }
        ),
        enrich_task_trace_metadata(
            {
                "task_id": "T_P3",
                "title": "Nộp bài tập nhóm Vật lý đại cương",
                "duration_min": 90,
                "deadline_day": "Thursday",
                "category": "ASSIGNMENT",
            }
        ),
    ]

    r = client.post(
        "/api/chat/turn",
        json={
            "prompt": "Làm bài tập môn Computational Thinking, từ 19h ngày thứ 3, tới 21h ngày thứ 5, cần thực hiện trong 2 tiếng",
            "commitments": comm,
            "tasks": preset_tasks,
            "auto_save": False,
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "APPLIED", f"Expected APPLIED single task, got: {d}"
    assert d["intent"] == "ADD_TASK"
    assert len(d["updated_tasks"]) == len(preset_tasks) + 1

    new_task = [t for t in d["updated_tasks"] if t["task_id"] == d["mutated_task_id"]][0]
    assert "Computational Thinking" in new_task["title"]
    assert new_task["duration_min"] == 120
    assert new_task["deadline_day"] == "Thursday"
    assert new_task["deadline_time"] == "21:00"
    assert new_task["is_splittable"] is False
    assert new_task["start_after"] is not None and "2026-11-03T19:00" in new_task["start_after"]

    # Verify Developer Mode Thinking Stage summary is returned with dominant algorithm pruning
    ts = d["thinking_summary"]
    assert ts is not None
    assert ts["selected_algorithm"] in ("SCORED_GREEDY", "HYBRID_ALNS")
    pruned_keys = {p if isinstance(p, str) else p["key"] for p in ts["pruned_algorithms"]}
    assert {"EDF", "WSPT", "LST"}.issubset(pruned_keys)
    assert any(act["label"] == "🗓️ Kiểm tra lịch trình" for act in d["post_actions"])


def test_chat_turn_modify_hidden_via_sha256_and_deadline_remaining_buffer(tmp_path, monkeypatch) -> None:
    """Requirement 1 & 3: Trace task via SHA-256 keywords, mutate hidden criteria, and adjust deadline + remaining time."""
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "chat_trace.db"))
    comm = _base_commitments()
    tasks = [
        enrich_task_trace_metadata(
            {
                "task_id": "T_PRJ",
                "title": "Đồ án Mạng máy tính",
                "duration_min": 180,
                "deadline_day": "Thursday",
                "deadline_time": "23:59",
                "priority": 4,
                "category": "PROJECT",
                "cognitive_load": 2,
                "is_splittable": True,
            }
        )
    ]

    # 1. Modify hidden parameters via prompt keywords
    t_start = time.perf_counter()
    r_mod = client.post(
        "/api/chat/turn",
        json={
            "prompt": "Đồ án Mạng máy tính nặng quá, không thể chia nhỏ mà làm liền 1 mạch buổi sáng nhé",
            "commitments": comm,
            "tasks": tasks,
            "auto_save": True,
        },
    )
    assert r_mod.status_code == 200, r_mod.text
    d_mod = r_mod.json()
    assert d_mod["status"] == "APPLIED"
    assert d_mod["intent"] == "MODIFY_HIDDEN"
    assert d_mod["traced_task"]["task_id"] == "T_PRJ"
    mutated = d_mod["updated_tasks"][0]
    assert mutated["cognitive_load"] == 3
    assert mutated["is_splittable"] is False
    assert mutated["preferred_window"] == "MORNING"
    assert mutated["buffer_multiplier"] >= 1.35
    assert (time.perf_counter() - t_start) * 1000.0 < 10000.0

    # 2. Adjust deadline + remaining duration with habit buffer
    r_dl = client.post(
        "/api/chat/turn",
        json={
            "prompt": "Đổi deadline Đồ án Mạng máy tính sang Chủ nhật lúc 20:00, mình ước lượng cần làm tiếp 90 phút",
            "commitments": d_mod["updated_commitments"],
            "tasks": d_mod["updated_tasks"],
            "auto_save": True,
        },
    )
    assert r_dl.status_code == 200, r_dl.text
    d_dl = r_dl.json()
    assert d_dl["status"] == "APPLIED"
    assert d_dl["intent"] == "ADJUST_DEADLINE"
    rem = d_dl["remaining_estimation"]
    assert rem["remaining_raw_min"] == 90
    assert rem["buffered_duration_min"] > 90
    assert d_dl["updated_tasks"][0]["deadline_day"] == "Sunday"
    assert d_dl["updated_tasks"][0]["deadline_time"] == "20:00"
    assert d_dl["execution_time_ms"] < 10000.0


def test_chat_turn_deadlock_and_dense_warning_edge_cases(tmp_path, monkeypatch) -> None:
    """Requirement 2 Edge Cases: Deadlock error vs. Yellow high-density feasible warning."""
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "chat_edges.db"))
    comm = _base_commitments()
    # Edge Case A: Dense feasible day (>= 420m on Monday) -> Yellow Warning
    dense_tasks = [
        {
            "task_id": "T_D1",
            "title": "Ôn tập Chương 1",
            "duration_min": 180,
            "deadline_day": "Monday",
            "deadline_time": "23:59",
            "priority": 4,
            "is_splittable": True,
        },
        {
            "task_id": "T_D2",
            "title": "Làm Lab 1",
            "duration_min": 180,
            "deadline_day": "Monday",
            "deadline_time": "23:59",
            "priority": 4,
            "is_splittable": True,
        },
    ]
    r_dense = client.post(
        "/api/chat/turn",
        json={
            "prompt": "Thêm Ôn tập Chương 2 60 phút trước 23:59 Thứ Hai",
            "commitments": comm,
            "tasks": dense_tasks,
            "auto_save": False,
        },
    )
    assert r_dense.status_code == 200, r_dense.text
    d_dense = r_dense.json()
    assert d_dense["status"] == "APPLIED"
    assert d_dense["finalized"] is True
    assert d_dense["edge_case"] is not None
    assert d_dense["edge_case"]["type"] == "DENSE_WARNING"
    assert d_dense["edge_case"]["severity"] == "warn"

    # Edge Case B: Deadlocked overlapping deadlines (more work before Monday 12:00 than hours exist)
    r_dead = client.post(
        "/api/chat/turn",
        json={
            "prompt": "Thêm Báo cáo khẩn 360 phút trước 12:00 Thứ Hai",
            "commitments": comm,
            "tasks": [
                {
                    "task_id": "T_EXIST",
                    "title": "Bài kiểm tra sáng",
                    "duration_min": 180,
                    "deadline_day": "Monday",
                    "deadline_time": "12:00",
                    "priority": 5,
                    "is_splittable": False,
                }
            ],
            "auto_save": False,
        },
    )
    assert r_dead.status_code == 200, r_dead.text
    d_dead = r_dead.json()
    assert d_dead["status"] == "APPLIED"
    assert d_dead["edge_case"] is not None
    assert d_dead["edge_case"]["type"] == "DEADLOCK"
    assert d_dead["edge_case"]["severity"] == "danger"
    assert len(d_dead["edge_case"]["suggestions"]) >= 1


def test_chat_first_ui_shell_left_sidebar_copilot_and_dev_mode() -> None:
    """Verify UI serves Antigravity-style default chat, left sidebar slider, calendar right copilot, and Developer Mode."""
    html = client.get("/").text
    for required_id in (
        "btnBrandHome",
        "leftNavSidebar",
        "btnToggleLeftSidebar",
        "navBtnChat",
        "navBtnCalendar",
        "chkDeveloperMode",
        "devTaskHiddenInspectorList",
        "viewChat",
        "calendarMainStage",
        "calendarCopilotDrawer",
        "btnExpandCopilotDrawer",
    ):
        assert required_id in html, f"Missing Chat-First UI element: {required_id}"

    assert "Trợ lý xếp lịch" in html
    assert "Chuyển nhanh tuần" not in html
    assert "Nền năng lượng sinh học" not in html

    # Default entry view must be #viewChat active (not #viewCalendar active)
    assert '<div class="view-panel active" id="viewChat"' in html
    assert '<div class="view-panel" id="viewCalendar"' in html

    chat_js = client.get("/js/chat-assistant.js")
    assert chat_js.status_code == 200
    assert "renderChatWorkspaces" in chat_js.text
    assert "renderDevHiddenTaskInspector" in chat_js.text
    assert "dev-hidden-card" in chat_js.text
    assert "chat-thinking-stage" in chat_js.text
    assert "btnToggleCopilotDrawer" in chat_js.text
    assert "Chỉnh nhanh việc đã lưu" not in chat_js.text
    assert "data-suggest-template" not in chat_js.text

    app_js = client.get("/app.js").text
    assert "handleChatPrompt" in app_js
    assert "setDeveloperMode" in app_js
    assert "setLeftSidebarOpen" in app_js
    assert "setCopilotCollapsed" in app_js
    assert "Kiểm tra lịch trình" in app_js
