"""
M4 (Nguyễn Trọng Tiến) — Grounded Chat Router & Lifecycle Intents.

Covers `smartschedule/nlp/intent_classifier.py`, `smartschedule/api/chat/lifecycle_intents.py`
and the v1.0-alpha wiring inside `smartschedule/api/chat/handlers.py`:
  - deterministic intent taxonomy (< 2 ms) incl. delete-vs-disruption precedence
  - DELETE_ITEM / COMPLETE_TASK / QUERY_SCHEDULE on workspace items
  - P10 DAG wiring (ADD_TASK prerequisite, LINK_DEPENDENCY, BATCH_ADD_TASKS) + DFS cycle guard
  - P14a attachment cross-check USER_VS_DOC_UNDERESTIMATE (M7 digest)
  - P13 ADAPT_NEXT_WEEK via M5 adapter (LoA-4 preview -> apply, no double-buffering)
  - fault-tolerant plug-ins when M5 / M7 modules are missing
"""

from __future__ import annotations

import ast
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from smartschedule.api.app import app
from smartschedule.api.chat import handlers
from smartschedule.api.chat.handlers import process_chat_turn
from smartschedule.api.chat.lifecycle_intents import add_dependency_edge, find_dependency_cycle
from smartschedule.core.storage import list_completion_logs
from smartschedule.core.task_tracer import enrich_task_trace_metadata
from smartschedule.nlp.intent_classifier import classify_intent, split_prerequisite_clause

REPO_ROOT = Path(__file__).resolve().parents[2]

SPEC_MD = (
    "# Đồ án Cấu trúc dữ liệu\n"
    "## Phần 1: Cài đặt thuật toán (40%)\nCài đặt cây AVL.\n"
    "## Phần 2: Kiểm thử (20%)\nViết test sau khi cài đặt xong.\n"
    "## Phần 3: Báo cáo (10%)\nViết báo cáo 2 trang.\n"
)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("SMARTSCHEDULE_DB_PATH", str(tmp_path / "m4_chat.db"))


def _commitments() -> Dict[str, Any]:
    return {
        "student_id": "M4_TEST",
        "planning_week_start": "2026-11-02T00:00:00+07:00",
        "now": "2026-11-02T08:00:00+07:00",
        "sleep_schedule": {"daily_start_time": "23:30", "daily_end_time": "06:30", "is_hard_lock": True},
        "fixed_events": [
            {
                "event_id": "FE_CLB",
                "title": "Họp CLB",
                "day_of_week": "Thursday",
                "start_time": "19:30",
                "end_time": "21:00",
                "category": "CLUB",
            }
        ],
        "buffer_mode": "COGNITIVE_LOAD",
        "focus_preference": "BALANCED",
        "horizon_days": 7,
    }


def _tasks() -> List[Dict[str, Any]]:
    return [
        enrich_task_trace_metadata(
            {
                "task_id": "T_CODE",
                "title": "Code thuật toán AVL",
                "duration_min": 120,
                "deadline_day": "Thursday",
                "priority": 4,
                "category": "CODING",
                "cognitive_load": 3,
            }
        ),
        enrich_task_trace_metadata(
            {
                "task_id": "T_RPT",
                "title": "Viết báo cáo đồ án",
                "duration_min": 60,
                "deadline_day": "Friday",
                "priority": 3,
                "category": "ASSIGNMENT",
                "cognitive_load": 2,
                "depends_on": ["T_CODE"],
            }
        ),
    ]


def _turn(prompt: str, **extra: Any) -> Dict[str, Any]:
    payload = {"prompt": prompt, "commitments": _commitments(), "tasks": _tasks(), "auto_save": False}
    payload.update(extra)
    return process_chat_turn(payload)


def _by_id(tasks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {t["task_id"]: t for t in tasks}


# ---------------------------------------------------------------------------
# 1. Deterministic taxonomy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "prompt, expected",
    [
        ("Hủy lịch họp CLB thứ 5", "DELETE_ITEM"),
        ("Mình muốn xóa bài viết báo cáo đồ án", "DELETE_ITEM"),
        ("Không cần làm code thuật toán AVL nữa", "DELETE_ITEM"),
        ("Làm xong code thuật toán AVL rồi, mất 3 tiếng", "COMPLETE_TASK"),
        ("Đã xong bài lab 3", "COMPLETE_TASK"),
        ("Thứ 5 tuần này có lịch gì?", "QUERY_SCHEDULE"),
        ("Rút kinh nghiệm cho tuần sau", "ADAPT_NEXT_WEEK"),
        ("Học thói quen tuần trước", "ADAPT_NEXT_WEEK"),
        ("Học Giải tích 2 tiếng rồi mới làm bài tập Giải tích", "BATCH_ADD_TASKS"),
        ("- Đọc chương 3 45 phút\n- Làm bài tập chương 3 1 tiếng", "BATCH_ADD_TASKS"),
        ("Viết báo cáo đồ án sau khi xong code thuật toán AVL", "LINK_DEPENDENCY"),
        ("Làm slide 45 phút sau khi xong viết báo cáo đồ án", "ADD_TASK"),
        ("Mới làm được một nửa code thuật toán AVL", "LEGACY"),
        ("Làm bài tập CT, từ 19h thứ 3 đến 21h thứ 5, cần hoàn thành trong 2 tiếng", "LEGACY"),
        ("Phải hoàn thành báo cáo trước thứ 6", "LEGACY"),
        ("Mình đã hoàn thành code thuật toán AVL", "COMPLETE_TASK"),
        ("Làm bài tập Giải tích 90 phút trước Thứ 6", "LEGACY"),
    ],
)
def test_intent_taxonomy(prompt: str, expected: str) -> None:
    res = classify_intent(prompt, tasks=_tasks(), legacy_detector=lambda: "LEGACY")
    assert res.intent == expected, (prompt, res)


def test_delete_beats_disruption_detector_and_prereq_chain_is_not_completion() -> None:
    """Lexicographic decision list: an explicit delete never becomes a new busy event (bug B5)."""
    always_disruption = lambda _p: True  # noqa: E731
    assert classify_intent("Hủy lịch họp CLB thứ 5", disruption_detector=always_disruption).intent == "DELETE_ITEM"
    assert classify_intent("xong code thuật toán AVL rồi mới viết slide", tasks=_tasks()).intent != "COMPLETE_TASK"


def test_classifier_latency_under_2ms() -> None:
    tasks = _tasks()
    prompts = ["Làm xong code thuật toán AVL rồi", "Thứ 5 có lịch gì?", "Hủy lịch họp CLB", "Rút kinh nghiệm cho tuần sau"]
    t0 = time.perf_counter()
    n = 0
    for _ in range(50):
        for p in prompts:
            classify_intent(p, tasks=tasks)
            n += 1
    assert (time.perf_counter() - t0) * 1000.0 / n < 2.0


def test_split_prerequisite_keeps_vietnamese_accents() -> None:
    sp = split_prerequisite_clause("Làm slide thuyết trình sau khi xong viết báo cáo đồ án")
    assert sp is not None
    assert sp.dependent_text == "Làm slide thuyết trình"
    assert sp.prerequisite_text == "viết báo cáo đồ án"


def test_intent_classifier_layer_purity() -> None:
    src = (REPO_ROOT / "smartschedule" / "nlp" / "intent_classifier.py").read_text(encoding="utf-8")
    mods = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
        elif isinstance(node, ast.Import):
            mods.update(a.name for a in node.names)
    assert not any(m.startswith(("smartschedule.api", "fastapi")) for m in mods), mods


# ---------------------------------------------------------------------------
# 2. Lifecycle intents
# ---------------------------------------------------------------------------

def test_delete_task_cleans_orphan_dependencies_and_pins() -> None:
    res = _turn("Xóa code thuật toán AVL", pinned_blocks=[{"block_id": "T_CODE_1", "task_id": "T_CODE", "title": "x", "day": "Monday", "start_slot": 40, "end_slot": 48, "start_time": "10:00", "end_time": "12:00", "duration_min": 120}])
    assert res["status"] == "APPLIED" and res["intent"] == "DELETE_ITEM"
    ids = _by_id(res["updated_tasks"])
    assert "T_CODE" not in ids
    assert ids["T_RPT"]["depends_on"] == []
    assert all(p.get("task_id") != "T_CODE" for p in res["updated_pinned_blocks"])
    assert all(b["task_id"] != "T_CODE" for b in res["schedule"]["blocks"])


def test_delete_fixed_event_via_router_not_disruption() -> None:
    res = _turn("Hủy lịch họp CLB thứ 5")
    assert res["status"] == "APPLIED" and res["intent"] == "DELETE_ITEM"
    assert res["updated_commitments"]["fixed_events"] == []
    assert len(res["updated_tasks"]) == 2


def test_delete_unknown_item_asks_with_chips() -> None:
    res = _turn("Xóa cái kia đi")
    assert res["status"] == "NEEDS_CLARIFICATION"
    assert res["missing_fields"] == ["target_item"]
    assert any("[event:FE_CLB]" in c["prompt"] for c in res["quick_chips"])


def test_complete_task_logs_actual_vs_estimate_and_unblocks_dependents() -> None:
    res = _turn("Làm xong code thuật toán AVL rồi, mất 3 tiếng", workspace_id="ws_complete")
    assert res["status"] == "APPLIED" and res["intent"] == "COMPLETE_TASK"
    ids = _by_id(res["updated_tasks"])
    assert "T_CODE" not in ids and ids["T_RPT"]["depends_on"] == []
    logs = list_completion_logs(workspace_id="ws_complete")
    assert logs and logs[0]["task_id"] == "T_CODE"
    assert (logs[0]["estimated_duration_min"], logs[0]["actual_duration_min"]) == (120, 180)
    assert "Viết báo cáo đồ án" in res["reply_vi"]


def test_query_schedule_is_read_only() -> None:
    res = _turn("Thứ 5 tuần này có lịch gì?")
    assert res["status"] == "INFO_ONLY" and res["intent"] == "QUERY_SCHEDULE"
    assert res["schedule"] is None
    assert res["updated_tasks"] == _tasks()
    assert "Họp CLB" in res["reply_vi"] and res["query_day"] == "Thursday"


# ---------------------------------------------------------------------------
# 3. P10 DAG wiring + cycle guard
# ---------------------------------------------------------------------------

def test_find_dependency_cycle_cases() -> None:
    tasks = [
        {"task_id": "A", "depends_on": []},
        {"task_id": "B", "depends_on": ["A"]},
        {"task_id": "C", "depends_on": ["B"]},
    ]
    assert find_dependency_cycle(tasks, "A", "A") == ["A", "A"]
    assert find_dependency_cycle(tasks, "A", "C") == ["A", "C", "B", "A"]
    assert find_dependency_cycle(tasks, "C", "A") is None
    ok, cyc = add_dependency_edge(tasks, "A", "C")
    assert not ok and cyc and tasks[0]["depends_on"] == []
    # 600-node chain: iterative DFS must not hit the recursion limit
    chain = [{"task_id": f"N{i}", "depends_on": [f"N{i - 1}"] if i else []} for i in range(600)]
    assert find_dependency_cycle(chain, "N0", "N599") is not None


def test_link_dependency_rejects_cycle_and_accepts_valid_edge() -> None:
    bad = _turn("Code thuật toán AVL sau khi xong viết báo cáo đồ án")
    assert bad["status"] == "NEEDS_CLARIFICATION" and bad["conflict"] == "CIRCULAR_DEPENDENCY"
    assert bad["cycle_task_ids"][0] == bad["cycle_task_ids"][-1] == "T_CODE"

    tasks = _tasks()
    tasks[1]["depends_on"] = []
    ok = process_chat_turn({"prompt": "Viết báo cáo đồ án sau khi xong code thuật toán AVL", "commitments": _commitments(), "tasks": tasks, "auto_save": False})
    assert ok["status"] == "APPLIED" and ok["intent"] == "LINK_DEPENDENCY"
    assert _by_id(ok["updated_tasks"])["T_RPT"]["depends_on"] == ["T_CODE"]
    assert any(r["pattern_id"] == "P10" for r in ok["thinking_summary"]["pattern_rules"])


def test_add_task_links_existing_prerequisite_and_keeps_trailing_deadline() -> None:
    res = _turn("Làm slide thuyết trình 45 phút sau khi xong viết báo cáo đồ án trước thứ 6")
    assert res["status"] == "APPLIED" and res["intent"] == "ADD_TASK"
    new = res["updated_tasks"][-1]
    assert new["title"] == "Làm slide thuyết trình"
    assert new["depends_on"] == ["T_RPT"] and new["deadline_day"] == "Friday"
    assert any(r["pattern_id"] == "P10" for r in res["thinking_summary"]["pattern_rules"])
    blocks = res["schedule"]["blocks"]
    rpt_end = max(b["end_slot"] for b in blocks if b["task_id"] == "T_RPT")
    assert min(b["start_slot"] for b in blocks if b["task_id"] == new["task_id"]) >= rpt_end


def test_batch_chain_shares_deadline_and_links_sequentially() -> None:
    res = _turn("Học Giải tích 2 tiếng rồi mới làm bài tập Giải tích 1 tiếng trước thứ 7")
    assert res["status"] == "APPLIED" and res["intent"] == "BATCH_ADD_TASKS"
    first, second = res["updated_tasks"][-2:]
    assert (first["duration_min"], second["duration_min"]) == (120, 60)
    assert first["deadline_day"] == second["deadline_day"] == "Saturday"
    assert second["depends_on"] == [first["task_id"]]


def test_batch_bullets_resolve_inline_prerequisite_and_ask_missing_deadline() -> None:
    prompt = "Việc tuần này:\n- Đọc chương 3 45 phút\n- Làm bài tập chương 3 1 tiếng sau khi xong đọc chương 3\n- Ôn thi 2 tiếng"
    ask = _turn(prompt)
    assert ask["status"] == "NEEDS_CLARIFICATION" and ask["missing_fields"] == ["deadline_day"]
    assert len(ask["pending_draft"]["items"]) == 3

    done = _turn("Hạn chót Thứ Sáu", pending_draft=ask["pending_draft"])
    assert done["status"] == "APPLIED"
    read, hw, review = done["updated_tasks"][-3:]
    assert hw["depends_on"] == [read["task_id"]] and review["depends_on"] == []
    assert {read["deadline_day"], hw["deadline_day"], review["deadline_day"]} == {"Friday"}


# ---------------------------------------------------------------------------
# 4. P14a attachment cross-check (M7 digest)
# ---------------------------------------------------------------------------

def _attach() -> List[Dict[str, str]]:
    return [{"filename": "spec.md", "content": SPEC_MD}]


def test_attachment_underestimate_offers_two_chips_then_milestones_dag() -> None:
    ask = _turn("Làm đồ án cấu trúc dữ liệu 30 phút trước thứ 6", attachments=_attach())
    assert ask["status"] == "NEEDS_CLARIFICATION" and ask["conflict"] == "USER_VS_DOC_UNDERESTIMATE"
    assert len(ask["quick_chips"]) == 2
    total = ask["attachment_digest"]["suggested_total_min"]
    assert 30 < 0.5 * total

    use = _turn(ask["quick_chips"][0]["prompt"], pending_draft=ask["pending_draft"])
    assert use["status"] == "APPLIED"
    created = use["updated_tasks"][2:]
    assert len(created) == 3 and sum(t["duration_min"] for t in created) >= total - 15
    assert created[1]["depends_on"] == [created[0]["task_id"]]
    assert all(t["deadline_day"] == "Friday" for t in created)

    keep = _turn(ask["quick_chips"][1]["prompt"], pending_draft=ask["pending_draft"])
    assert keep["status"] == "APPLIED"
    assert [t["duration_min"] for t in keep["updated_tasks"][2:]] == [30]


def test_attachment_autofills_duration_when_user_gives_none() -> None:
    res = _turn("Làm đồ án cấu trúc dữ liệu trước thứ 6", attachments=_attach())
    assert res["status"] == "APPLIED"
    new = res["updated_tasks"][-1]
    assert new["duration_min"] >= 180 and new["priority"] >= 4
    assert any(r["pattern_id"] == "P14" for r in res["thinking_summary"]["pattern_rules"])


def test_attachment_ignored_when_m7_parser_missing(monkeypatch) -> None:
    monkeypatch.setattr(handlers, "_m7_parse_doc", None)
    res = _turn("Làm đồ án cấu trúc dữ liệu 30 phút trước thứ 6", attachments=_attach())
    assert res["status"] == "APPLIED" and res["updated_tasks"][-1]["duration_min"] == 30


# ---------------------------------------------------------------------------
# 5. P13 ADAPT_NEXT_WEEK (M5 adapter, LoA-4)
# ---------------------------------------------------------------------------

def _coding_overrun_logs(n: int = 5) -> List[Dict[str, Any]]:
    return [
        {"task_id": "T_CODE", "category": "CODING", "cognitive_load": 3, "estimated_duration_min": 60,
         "actual_duration_min": 90, "adhered": True, "start_hour": 20.0}
        for _ in range(n)
    ]


def test_adapt_cold_start_keeps_defaults() -> None:
    res = _turn("Rút kinh nghiệm cho tuần sau", workspace_id="ws_cold")
    assert res["status"] == "INFO_ONLY" and res["intent"] == "ADAPT_NEXT_WEEK"
    assert "1.20" in res["reply_vi"] and "1.35" in res["reply_vi"]


def test_adapt_preview_then_apply_without_double_buffering() -> None:
    preview = _turn("Rút kinh nghiệm cho tuần sau", timeline_logs=_coding_overrun_logs())
    assert preview["status"] == "INFO_ONLY" and len(preview["quick_chips"]) == 2
    alphas = preview["adaptation"]["category_alphas"]["CODING"]
    assert alphas["sample_count"] == 5 and 1.35 < alphas["alpha_heavy"] <= 1.60

    applied = _turn(preview["quick_chips"][0]["prompt"], timeline_logs=_coding_overrun_logs())
    assert applied["status"] == "APPLIED" and applied["intent"] == "ADAPT_NEXT_WEEK"
    code = _by_id(applied["updated_tasks"])["T_CODE"]
    assert code["duration_min"] == 120  # raw estimate untouched (no double-buffering)
    assert 1.0 <= code["alpha_heavy"] <= 1.60
    assert any(r["pattern_id"] == "P13" for r in applied["thinking_summary"]["pattern_rules"])

    keep = _turn(preview["quick_chips"][1]["prompt"], timeline_logs=_coding_overrun_logs())
    assert keep["status"] == "INFO_ONLY" and keep["schedule"] is None


def test_adapt_degrades_when_m5_adapter_missing(monkeypatch) -> None:
    monkeypatch.setattr(handlers, "_m5_adapt", None)
    res = _turn("Rút kinh nghiệm cho tuần sau", timeline_logs=_coding_overrun_logs())
    assert res["status"] == "INFO_ONLY" and res["schedule"] is None


# ---------------------------------------------------------------------------
# 6. Delegation to M5 + contract normalisation
# ---------------------------------------------------------------------------

def test_disruption_delegation_keeps_real_solver_key() -> None:
    res = _turn("Thứ 5 mình bận đột xuất từ 14h đến 16h")
    assert res["intent"] == "DISRUPTION_REPAIR"
    if res["status"] == "APPLIED":
        ts = res["thinking_summary"]
        assert ts["selected_algorithm"] in handlers.ScheduleController.SOLVER_REGISTRY  # bug U1 guard
        assert ts.get("repair_engine") == "LOCAL_INSERTION"


def test_router_contract_keys_present_for_every_status() -> None:
    required = {"status", "intent", "reply_vi", "pending_draft", "missing_fields", "quick_chips",
                "post_actions", "updated_commitments", "updated_tasks", "updated_pinned_blocks", "execution_time_ms"}
    for p in ["Thứ 5 có lịch gì?", "Xóa cái kia đi", "Hủy lịch họp CLB thứ 5", "Rút kinh nghiệm cho tuần sau"]:
        res = _turn(p)
        assert required <= set(res), (p, required - set(res))
        assert res["execution_time_ms"] < 10_000


@pytest.mark.xfail(strict=True, reason="Bug B5 (M5 app.py): /api/chat/turn routes 'hủy lịch ...' to disruption before handlers.py")
def test_http_delete_fixed_event_reaches_router() -> None:
    client = TestClient(app)
    r = client.post("/api/chat/turn", json={"prompt": "Hủy lịch họp CLB thứ 5", "commitments": _commitments(), "tasks": _tasks(), "auto_save": False})
    assert r.status_code == 200
    assert r.json()["intent"] == "DELETE_ITEM"
