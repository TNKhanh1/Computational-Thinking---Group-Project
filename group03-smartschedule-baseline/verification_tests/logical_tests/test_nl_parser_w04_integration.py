"""
Verification Tests for Standardized W04 Dual-Engine NL Parser Architecture
Integrated into SmartSchedule Group 03.
"""

from fastapi.testclient import TestClient
import pytest

from src import nl_parser
from src.nl_parser import VALID_TASK_CATEGORIES, parse_natural_language_task
from web.api import app

client = TestClient(app)


@pytest.mark.parametrize(
    "noise_prompt",
    [
        "Hôm qua thức 7h liền mệt quá",
        "7h vui quá 7h",
        "hahaha vui quá đi",
        "Chắc 7h sáng mai dậy nổi",
        "Yesterday I stayed up for 7 hours binge watching",
        "123456 ???",
    ],
)
def test_zero_noise_gatekeeper_rejects_chatter_and_past(noise_prompt):
    res = parse_natural_language_task(noise_prompt, now="2026-11-04T10:00:00+07:00", engine="offline")
    assert res["status"] == "NO_TASK"
    assert res["parse_status"] == "NO_TASK"
    assert res["draft"] is None
    assert res["rejection_reason"]

    api_res = client.post(
        "/api/tasks/natural-add",
        json={"prompt": noise_prompt, "engine": "offline"},
    )
    assert api_res.status_code == 200
    body = api_res.json()
    assert body["status"] == "NO_TASK"
    assert body["draft"] is None


@pytest.mark.parametrize("short_title", ["Giải tích", "Ôn Giải tích", "Lab 04"])
def test_short_academic_titles_not_falsely_rejected(short_title):
    res = parse_natural_language_task(short_title, now="2026-11-02T08:00:00+07:00", engine="offline")
    assert res["status"] == "DRAFT_READY"
    assert res["parse_status"] == "NEEDS_SUGGESTION"
    assert res["draft"] is not None
    assert res["draft"]["category"] in VALID_TASK_CATEGORIES
    assert "duration_min" in res["missing_fields"]
    chip_values = [c["value"] for c in res["suggestions"] if c.get("field") == "duration_min"]
    assert chip_values == [30, 60, 90, 120]


def test_clean_title_location_word_boundaries_and_noon_fix():
    res = parse_natural_language_task(
        "Ôn thi Giải tích 2 tiếng trước 17h thứ 6 #deep",
        now="2026-11-02T08:00:00+07:00",
        engine="offline",
    )
    d = res["draft"]
    assert res["parse_status"] == "SUCCESS"
    assert d["title"] == "Ôn thi Giải tích"
    assert d["category"] == "EXAM"
    assert d["priority"] == 5
    assert d["cognitive_load"] == 3
    assert d["deadline_day"] == "Friday"
    assert d["deadline_time"] == "17:00"
    assert d["duration_min"] == 120

    # Habit + half an hour + location + evening coarse window
    habit_res = parse_natural_language_task(
        "Tối nay chạy bộ nửa tiếng ở công viên",
        now="2026-11-04T10:00:00+07:00",
        engine="offline",
    )
    assert habit_res["draft"]["title"] == "Chạy bộ"
    assert habit_res["draft"]["category"] == "HABIT"
    assert habit_res["draft"]["duration_min"] == 30
    assert habit_res["location"] == "Công viên"

    # Word-boundary & diacritics guard:
    # "nâng cao" -> NOT "nặng"; "Gặp mentor" -> NOT "gấp"
    wb_res = parse_natural_language_task(
        "Làm bài nâng cao chương 3 60p thứ 5",
        now="2026-11-02T08:00:00+07:00",
        engine="offline",
    )
    assert wb_res["draft"]["category"] == "ASSIGNMENT"
    assert wb_res["draft"]["cognitive_load"] == 2

    meet_res = parse_natural_language_task(
        "Gặp mentor chiều mai 3h 30p",
        now="2026-11-02T08:00:00+07:00",
        engine="offline",
    )
    assert meet_res["draft"]["priority"] == 3
    assert meet_res["intent_type"] == "FIXED_EVENT"
    assert meet_res["suggested_fixed_event"]["start_time"] == "15:00"
    assert meet_res["suggested_fixed_event"]["end_time"] == "15:30"

    # Noon fix: "trưa" should map to 12:00 rather than W04's MORNING 09:00 bug
    noon_res = parse_natural_language_task(
        "Nộp báo cáo trưa thứ 6 60p",
        now="2026-11-02T08:00:00+07:00",
        engine="offline",
    )
    assert noon_res["draft"]["deadline_time"] == "12:00"


def test_fixed_event_detection_and_english_location():
    res = parse_natural_language_task(
        "Chiều mai 2h họp nhóm CT 2 tiếng ở thư viện, ưu tiên cao",
        now="2026-11-04T10:00:00+07:00",  # Wednesday
        engine="offline",
    )
    assert res["intent_type"] == "FIXED_EVENT"
    assert res["location"] == "Thư viện"
    assert res["draft"]["title"] == "Họp nhóm CT"
    assert res["draft"]["duration_min"] == 120
    fe = res["suggested_fixed_event"]
    assert fe is not None
    assert fe["day_of_week"] == "Thursday"
    assert fe["start_time"] == "14:00"
    assert fe["end_time"] == "16:00"
    assert fe["category"] == "MEETING"

    en_res = parse_natural_language_task(
        "Submit Lab 04 report tomorrow at 5pm at classroom 1h",
        now="2026-11-04T10:00:00+07:00",
        engine="offline",
    )
    assert en_res["location"] == "Classroom"
    assert en_res["draft"]["deadline_day"] == "Thursday"
    assert en_res["draft"]["deadline_time"] == "17:00"
    assert en_res["draft"]["duration_min"] == 60


def test_dual_engine_ai_routing_graceful_fallback_and_determinism(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy-test-key")
    monkeypatch.setattr(nl_parser, "genai", object())

    # 1. Mock AI parser raising quota error -> falls back cleanly to offline
    def _failing_ai(self, raw, *, now_day, existing_count):
        raise RuntimeError("Quota exhausted")

    monkeypatch.setattr(nl_parser.GeminiNLParser, "__init__", lambda self, api_key: None)
    monkeypatch.setattr(nl_parser.GeminiNLParser, "parse", _failing_ai)

    fb_res = client.post(
        "/api/tasks/natural-add",
        json={"prompt": "Làm lab mạng máy tính 1h30 trước 18:30 thứ 3 #lab", "engine": "auto"},
    )
    assert fb_res.status_code == 200
    fb_data = fb_res.json()
    assert fb_data["engine_used"] == "OFFLINE_DETERMINISTIC"
    assert fb_data["draft"]["duration_min"] == 90
    assert fb_data["draft"]["deadline_day"] == "Tuesday"
    assert any("Offline Deterministic" in a for a in fb_data["assumptions"])

    # 2. Mock AI parser succeeding -> AI_GEMINI payload flows through
    def _mock_ai_ok(self, raw, *, now_day, existing_count):
        return nl_parser._finalize_parsed_payload(
            raw=raw,
            now_day=now_day,
            existing_count=existing_count,
            title="Ôn thi Giải tích",
            category="EXAM",
            priority=5,
            cognitive_load=3,
            duration_min=120,
            dur_inferred=False,
            deadline_day="Friday",
            day_inferred=False,
            deadline_time="17:00",
            time_inferred=False,
            start_time=None,
            is_fixed_event=False,
            fixed_category=None,
            is_splittable=True,
            location=None,
            engine_used="AI_GEMINI",
            parser_mode="AI_GEMINI",
            assumptions=[],
            intent_type="TASK",
        )

    monkeypatch.setattr(nl_parser.GeminiNLParser, "parse", _mock_ai_ok)

    ai_res = client.post(
        "/api/tasks/natural-add",
        json={"prompt": "Ôn thi Giải tích 2 tiếng trước 17h thứ 6", "engine": "auto"},
    )
    assert ai_res.status_code == 200
    assert ai_res.json()["engine_used"] == "AI_GEMINI"

    # 3. Explicit engine="offline" bypasses AI even when key is present
    off_res = client.post(
        "/api/tasks/natural-add",
        json={"prompt": "Ôn thi Giải tích 2 tiếng trước 17h thứ 6", "engine": "offline"},
    )
    assert off_res.status_code == 200
    assert off_res.json()["engine_used"] == "OFFLINE_DETERMINISTIC"

    # 4. Reproducibility (H4): identical inputs yield identical SHA-256 task_id
    ids = [
        parse_natural_language_task("Ôn thi Giải tích 2 tiếng trước 17h thứ 6", now="2026-11-02T08:00:00+07:00", engine="offline")["draft"]["task_id"]
        for _ in range(3)
    ]
    assert len(set(ids)) == 1 and ids[0].startswith("TASK_NL_")

