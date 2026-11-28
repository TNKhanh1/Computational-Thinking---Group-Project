"""
UI & Integration Verification Suite for M6 (Le Minh Nhat - Builder 2, Wave 2A).

Validates:
  1. 1-Click Undo Ring Buffer (`undo-history.js`, max 10 entries) & Toast Undo action (`modals.js`)
  2. Chat Persistence across F5 (`state.js` 30-msg cap + `/api/state` round-trip) & Clear Chat (`🧹`)
  3. `.ics` & Document (`.pdf`/`.md`/`.txt`) chat attachments (`chat-assistant.js` + `/api/import/ics` + `/api/chat/turn`)
  4. Single-item Delete/Edit controls (`modals.js`, `render-list.js`) & API CRUD wrappers (`api.js`)
  5. Developer Mode `Pattern -> Deterministic Logic Rule` & `DAG` / `avoid_windows` rendering (`chat-assistant.js`)
  6. ES module syntax sanity & zero regression on contracted DOM/UI guards
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

from smartschedule.api.app import app

client = TestClient(app)

UI_JS_DIR = Path("smartschedule/ui/js")
M6_JS_FILES = [
    UI_JS_DIR / "undo-history.js",
    UI_JS_DIR / "api.js",
    UI_JS_DIR / "state.js",
    UI_JS_DIR / "modals.js",
    UI_JS_DIR / "render-list.js",
    UI_JS_DIR / "chat-assistant.js",
]


def _read_js(filename: str) -> str:
    path = UI_JS_DIR / filename
    assert path.exists(), f"Missing expected M6 JS file: {path}"
    return path.read_text(encoding="utf-8")


def test_undo_history_exports_and_toast_undo_contract():
    undo_js = _read_js("undo-history.js")
    modals_js = _read_js("modals.js")

    for export_sig in (
        "export const MAX_UNDO_ENTRIES = 10",
        "export function pushUndoSnapshot(",
        "export function popUndoSnapshot(",
        "export function canUndo(",
    ):
        assert export_sig in undo_js, f"Missing export in undo-history.js: {export_sig}"

    for field in ("commitments", "tasks", "pinnedBlocks", "completedBlocks", "currentSchedule"):
        assert field in undo_js, f"Undo snapshot missing required workspace key: {field}"

    # Toast supports inline 1-click Undo button while remaining backward-compatible
    assert "export function showToast(message, tone = \"ok\", options = {})" in modals_js
    assert "onUndo" in modals_js
    assert "↩ Hoàn tác" in modals_js
    assert "data-toast-undo" in modals_js


def test_chat_persistence_30_msg_cap_and_api_state_roundtrip():
    state_js = _read_js("state.js")
    chat_js = _read_js("chat-assistant.js")

    assert "export const MAX_PERSISTED_CHAT_MESSAGES = 30" in state_js
    for fn in (
        "export function trimChatMessages(",
        "export function serializeWorkspaceState(",
        "export function hydrateWorkspaceState(",
        "export function saveChatHistoryToStorage(",
        "export function loadChatHistoryFromStorage(",
        "export function clearChatHistoryStorage(",
    ):
        assert fn in state_js, f"Missing chat persistence helper in state.js: {fn}"

    assert "data-clear-chat-history" in chat_js
    assert "🧹 Làm mới chat" in chat_js
    assert "export function clearChatTranscript(" in chat_js

    # Verify /api/state persists chatMessages across F5 reload on an isolated workspace
    ws_id = f"m6_test_chat_persist_{uuid.uuid4().hex[:8]}"
    try:
        minh = client.get("/api/presets").json()["presets"]["minh"]
        sample_msgs = [
            {"id": f"u_{i}", "role": "user" if i % 2 == 0 else "assistant", "text": f"Tin nhắn số {i}"}
            for i in range(30)
        ]
        put_res = client.put(
            "/api/state",
            json={
                "workspace_id": ws_id,
                "state": {
                    "suiteLabel": "M6 Persist Test",
                    "commitments": minh["commitments"],
                    "tasks": minh["tasks"],
                    "pinnedBlocks": [],
                    "completedBlocks": {},
                    "activeSolver": "SCORED_GREEDY",
                    "chatMessages": sample_msgs,
                },
            },
        )
        assert put_res.status_code == 200, put_res.text

        get_res = client.get(f"/api/state?workspace_id={ws_id}")
        assert get_res.status_code == 200, get_res.text
        body = get_res.json()
        assert body["exists"] is True
        restored_msgs = body["state"]["chatMessages"]
        assert len(restored_msgs) == 30
        assert restored_msgs[0]["text"] == "Tin nhắn số 0"
        assert restored_msgs[-1]["text"] == "Tin nhắn số 29"
    finally:
        client.delete(f"/api/state?workspace_id={ws_id}")


def test_ics_import_endpoint_and_chat_attachment_ui_hooks():
    chat_js = _read_js("chat-assistant.js")

    # Composer exposes compact 📎 button, file input accepting .ics/.txt/.md/.pdf, and drag-drop zone
    assert 'accept=".ics,.txt,.md,.pdf"' in chat_js
    assert "data-chat-attach-btn" in chat_js
    assert "data-chat-file-input" in chat_js
    assert "data-chat-dropzone" in chat_js
    assert "dragover" in chat_js and "drop" in chat_js
    assert "api.importIcs(" in chat_js
    assert "✅ Áp dụng vào lịch" in chat_js
    assert "export async function handleChatFilesSelected(" in chat_js
    assert "export async function applyIcsImportToWorkspace(" in chat_js
    assert "api.sendChatTurn(" in chat_js

    # Backend /api/import/ics parses both weekly fixed events and LMS deadline tasks
    ics_payload = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Nhập môn Tư duy Tính toán\r\n"
        "DTSTART:20261102T073000\r\n"
        "DTEND:20261102T093000\r\n"
        "RRULE:FREQ=WEEKLY;BYDAY=MO,TH\r\n"
        "END:VEVENT\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY:Nộp Lab 04 CTDL\r\n"
        "DTSTART:20261106T235900\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    res = client.post("/api/import/ics", json={"content": ics_payload})
    assert res.status_code == 200, res.text
    parsed = res.json()
    assert len(parsed["fixed_events"]) == 1
    assert parsed["fixed_events"][0]["day_of_week"] == ["Monday", "Thursday"]
    assert len(parsed["tasks"]) == 1
    assert "Lab 04" in parsed["tasks"][0]["title"]


def test_document_attachment_chat_turn_and_dev_pattern_dag_badges():
    chat_js = _read_js("chat-assistant.js")

    # Developer Mode Pattern -> Deterministic Logic Rule + DAG & avoid_windows badges
    assert "thinkingSummary.pattern_rules" in chat_js
    assert "🔗 Pattern → Quy tắc Logic Tất định:" in chat_js
    assert "pattern_id" in chat_js and "pattern_name" in chat_js and "deterministic_rule" in chat_js
    assert "Phụ thuộc DAG:" in chat_js
    assert "task.depends_on" in chat_js
    assert "task.avoid_windows" in chat_js
    assert "POST_DISRUPTION_OVERLOAD" in chat_js
    assert "attachmentDigest" in chat_js

    # End-to-end chat turn with Markdown syllabus attachment + severe underestimate triggers clarification
    ws_id = f"m6_test_doc_att_{uuid.uuid4().hex[:8]}"
    try:
        init_res = client.post("/api/workspace/init-real-week", json={"workspace_id": ws_id, "save": True})
        assert init_res.status_code == 200, init_res.text
        init_data = init_res.json()

        syllabus_md = (
            "# Final Project Specification (35% of final grade)\n"
            "## Part 1: Implement Core Graph Solver (40%)\n"
            "Implement dynamic programming and backtracking solver in solver.py (~3 hours).\n"
            "## Part 2: Unit Testing & Benchmark Report (35%)\n"
            "Write unit test suite and analyze benchmark comparison (~2 hours).\n"
            "## Part 3: Final Slides & Submission (25%)\n"
            "Prepare presentation slides and package submission (~1 hour).\n"
        )
        turn_res = client.post(
            "/api/chat/turn",
            json={
                "workspace_id": ws_id,
                "prompt": "Làm đồ án cuối kỳ trong 45 phút trước thứ 6",
                "commitments": init_data["commitments"],
                "tasks": [],
                "pinned_blocks": [],
                "algorithm": "SCORED_GREEDY",
                "attachments": [{"filename": "final_project_spec.md", "content": syllabus_md}],
            },
        )
        assert turn_res.status_code == 200, turn_res.text
        tdata = turn_res.json()
        assert tdata["status"] == "NEEDS_CLARIFICATION"
        assert tdata.get("conflict") == "USER_VS_DOC_UNDERESTIMATE"
        assert tdata.get("attachment_digest", {}).get("suggested_total_min", 0) >= 180
        assert len(tdata.get("quick_chips") or []) >= 2
    finally:
        client.delete(f"/api/state?workspace_id={ws_id}")


def test_single_item_crud_endpoints_and_ui_wrappers():
    api_js = _read_js("api.js")
    modals_js = _read_js("modals.js")
    list_js = _read_js("render-list.js")

    # Verify M6 API helper wrappers
    for wrapper in (
        "deleteTask:",
        "upsertFixedEvent:",
        "deleteFixedEvent:",
        "initRealWeek:",
        "adaptNextWeek:",
        "simulateMultiWeek:",
        "sendChatTurn:",
    ):
        assert wrapper in api_js, f"Missing API wrapper in api.js: {wrapper}"

    # Verify single-item delete/edit controls in modals & list view (and preserve legacy guards)
    assert "btnModalDeleteTask" in modals_js
    assert "🗑️ Xóa công việc này" in modals_js
    assert "callbacks.onDeleteTask" in modals_js
    assert "secFocusTimer" not in modals_js

    assert "data-list-edit-fixed" in list_js
    assert "data-list-delete-fixed" in list_js
    assert "data-list-delete-task" in list_js
    assert "callbacks?.onDeleteFixedEvent" in list_js
    assert "data-list-timer" not in list_js

    # End-to-end backend verification for init-real-week -> fixed-events upsert/delete -> tasks delete
    ws_id = f"m6_test_crud_{uuid.uuid4().hex[:8]}"
    try:
        init_res = client.post(
            "/api/workspace/init-real-week",
            json={
                "workspace_id": ws_id,
                "sleep_start": "23:30",
                "sleep_end": "06:30",
                "focus_preference": "BALANCED",
                "estimate_habit": "SOMETIMES",
            },
        )
        assert init_res.status_code == 200, init_res.text
        ws = init_res.json()
        commitments = ws["commitments"]

        # Upsert fixed event
        up_res = client.post(
            "/api/fixed-events/upsert",
            json={
                "workspace_id": ws_id,
                "commitments": commitments,
                "tasks": [],
                "pinned_blocks": [],
                "event": {
                    "event_id": "CLS_M6_01",
                    "title": "Lớp Tư duy Tính toán",
                    "day_of_week": "Tuesday",
                    "start_time": "08:00",
                    "end_time": "10:00",
                    "category": "ACADEMIC_CLASS",
                },
                "algorithm": "SCORED_GREEDY",
            },
        )
        assert up_res.status_code == 200, up_res.text
        commitments = up_res.json()["updated_commitments"]
        assert any(e["event_id"] == "CLS_M6_01" for e in commitments["fixed_events"])

        # Delete fixed event
        del_ev_res = client.post(
            "/api/fixed-events/delete",
            json={
                "workspace_id": ws_id,
                "commitments": commitments,
                "tasks": [],
                "pinned_blocks": [],
                "event_id": "CLS_M6_01",
                "algorithm": "SCORED_GREEDY",
            },
        )
        assert del_ev_res.status_code == 200, del_ev_res.text
        commitments = del_ev_res.json()["updated_commitments"]
        assert not any(e["event_id"] == "CLS_M6_01" for e in commitments["fixed_events"])

        # Delete single task and clean dependent edge
        tasks = [
            {
                "task_id": "T_M6_A",
                "title": "Đọc tài liệu gốc",
                "duration_min": 60,
                "deadline_day": "Thursday",
                "deadline_time": "22:00",
                "priority": 4,
            },
            {
                "task_id": "T_M6_B",
                "title": "Viết báo cáo tổng hợp",
                "duration_min": 60,
                "deadline_day": "Friday",
                "deadline_time": "22:00",
                "priority": 4,
                "depends_on": ["T_M6_A"],
            },
        ]
        del_task_res = client.post(
            "/api/tasks/delete",
            json={
                "workspace_id": ws_id,
                "commitments": commitments,
                "tasks": tasks,
                "pinned_blocks": [],
                "task_id": "T_M6_A",
                "algorithm": "SCORED_GREEDY",
            },
        )
        assert del_task_res.status_code == 200, del_task_res.text
        ddata = del_task_res.json()
        assert ddata["deleted_task_id"] == "T_M6_A"
        assert len(ddata["updated_tasks"]) == 1
        assert ddata["updated_tasks"][0]["task_id"] == "T_M6_B"
        assert ddata["updated_tasks"][0].get("depends_on") == []
    finally:
        client.delete(f"/api/state?workspace_id={ws_id}")


def test_m6_js_files_syntax_and_node_check_if_available():
    node_bin = shutil.which("node")
    for js_path in M6_JS_FILES:
        src = js_path.read_text(encoding="utf-8")
        assert len(src.strip()) > 0
        # Ensure clean UTF-8 without BOM or stray merge conflict markers
        for marker in ("<<<<<<<", "=======", ">>>>>>>"):
            assert marker not in src, f"Merge conflict marker found in {js_path}"
        if node_bin:
            proc = subprocess.run([node_bin, "--check", str(js_path)], capture_output=True, text=True)
            assert proc.returncode == 0, f"node --check failed for {js_path}: {proc.stderr}"
