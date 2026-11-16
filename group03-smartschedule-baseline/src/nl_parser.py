"""
Hybrid M1 Natural Language Task Parser (Dual-Engine: Gemini AI + Offline Deterministic).

Unifies the W04 Dual-Engine architecture (`NLParserController`: Cloud LLM with
graceful degradation to local deterministic regex) with SmartSchedule Group 03's
672-slot scheduling domain schema:
  - Stage 1 (Optional AI Engine): Google Gemini structured JSON extraction when
    `GEMINI_API_KEY` and `google-genai` are available and engine != "offline".
  - Stage 2 (Offline Deterministic Engine): Accent-insensitive EN/VI regex parser
    supporting Intent Gatekeeping (`NO_TASK`), clean title/location extraction,
    relative dates from `now`, category (7 domain classes), priority (1-5),
    cognitive load (1-3), splittability, Fixed-Event hints, and suggestion chips.
  - Stage 3 (Python Schema Validation): Validates against `Task` Pydantic rules and
    generates deterministic SHA-256 `TASK_NL_<HEX6>` identifiers (H4).
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from .models import Task

try:
    from dotenv import load_dotenv
except ImportError:  # Optional dependency when running minimal offline setup
    load_dotenv = None

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # Graceful fallback when google-genai is not installed
    genai = None
    genai_types = None

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
VALID_TASK_CATEGORIES = ("EXAM", "QUIZ", "PROJECT", "LAB", "ASSIGNMENT", "READING", "HABIT")
VALID_FIXED_CATEGORIES = ("ACADEMIC_CLASS", "MEAL", "WORK", "MEETING")
DEFAULT_GEMINI_MODELS = (
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
)
# Models verified as 404/deprecated or severely throttled; skip immediately if others exist
_UNAVAILABLE_MODELS = {"gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite"}
_CLIENT_CACHE: Dict[str, Any] = {}
_ENV_LOADED = False
DURATION_CHIP_OPTIONS = (30, 60, 90, 120)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _PROJECT_ROOT.parent


def _load_local_env() -> None:
    """Load optional `.env` from project/repo root once without failing if absent."""
    global _ENV_LOADED
    if _ENV_LOADED or load_dotenv is None:
        return
    _ENV_LOADED = True
    for candidate in (_PROJECT_ROOT / ".env", _REPO_ROOT / ".env"):
        if candidate.is_file():
            load_dotenv(dotenv_path=candidate, override=False)


class GeminiNLSchema(BaseModel):
    """Structured JSON schema expected from Gemini AI before Python validation."""

    is_schedulable_task: bool = Field(
        description="False ONLY if input is past narrative, idle chatter, sarcasm, or nonsense."
    )
    rejection_reason: Optional[str] = Field(
        default=None,
        description="Friendly Vietnamese explanation if is_schedulable_task is False.",
    )
    intent_type: Literal["TASK", "FIXED_EVENT", "HABIT"] = Field(
        default="TASK",
        description="FIXED_EVENT for timed appointments/meetings/classes; HABIT for routines; else TASK.",
    )
    title: str = Field(
        default="",
        description="Concise clean task name stripped of temporal/priority clutter.",
    )
    category: Literal["EXAM", "QUIZ", "PROJECT", "LAB", "ASSIGNMENT", "READING", "HABIT"] = Field(
        default="ASSIGNMENT"
    )
    priority: int = Field(default=3, ge=1, le=5)
    cognitive_load: int = Field(default=2, ge=1, le=3)
    duration_min: Optional[int] = Field(
        default=None,
        description="Duration in minutes ONLY if stated or strongly implied; otherwise null.",
    )
    deadline_day: Optional[str] = Field(
        default=None,
        description="Monday..Sunday (or Next Monday), resolved from reference weekday; null if unspecified.",
    )
    deadline_time: Optional[str] = Field(
        default=None,
        description="Deadline time HH:MM (24h) if stated; otherwise null.",
    )
    start_time: Optional[str] = Field(
        default=None,
        description="Explicit start time HH:MM (24h) for fixed appointments/meetings; else null.",
    )
    is_fixed_event: bool = Field(default=False)
    fixed_category: Optional[Literal["ACADEMIC_CLASS", "MEAL", "WORK", "MEETING"]] = Field(default=None)
    is_splittable: bool = Field(default=True)
    location: Optional[str] = Field(default=None)
    assumptions: List[str] = Field(default_factory=list)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


_WEEKDAY_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"\b(?:monday|mon|thu\s*2|t2)\b", "Monday"),
    (r"\b(?:tuesday|tue|tues|thu\s*3|t3)\b", "Tuesday"),
    (r"\b(?:wednesday|wed|thu\s*4|t4)\b", "Wednesday"),
    (r"\b(?:thursday|thurs|thu\s*5|t5)\b|\bthu\b(?!\s*[2-7])", "Thursday"),
    (r"\b(?:friday|fri|thu\s*6|t6)\b", "Friday"),
    (r"\b(?:saturday|sat|thu\s*7|t7)\b", "Saturday"),
    (r"\b(?:sunday|sun|chu\s*nhat|cn)\b", "Sunday"),
)


def _resolve_now_day(now_iso_or_day: Optional[str]) -> str:
    if not now_iso_or_day:
        return "Monday"
    s = now_iso_or_day.strip()
    for wd in WEEKDAYS:
        if wd.lower() == s.lower():
            return wd
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return WEEKDAYS[dt.weekday()]
    except Exception:
        return "Monday"


def _normalize_weekday(value: Optional[str], fallback_day: str) -> Tuple[Optional[str], bool]:
    """Normalize a weekday string from AI/regex into SmartSchedule day naming."""
    if not value:
        return None, True
    norm = _strip_accents(value.strip().lower())
    if "next monday" in norm or "thu 2 tuan sau" in norm or "thu hai tuan sau" in norm:
        return "Next Monday", False
    for wd in WEEKDAYS:
        if wd.lower() == norm:
            return wd, False
    for pattern, wd in _WEEKDAY_PATTERNS:
        if re.search(pattern, norm):
            return wd, False
    now_idx = WEEKDAYS.index(fallback_day) if fallback_day in WEEKDAYS else 0
    return WEEKDAYS[min(now_idx + 2, 6)], True


def _round_15_min(minutes: int) -> int:
    return max(15, ((int(minutes) + 14) // 15) * 15)


def _normalize_hhmm(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(value))
    if not m:
        return None
    hh, mm = int(m.group(1)), int(m.group(2))
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return f"{hh:02d}:{mm:02d}"
    return None


def _compute_end_time(start_hhmm: str, duration_min: int) -> str:
    hh, mm = map(int, start_hhmm.split(":"))
    start_total = hh * 60 + mm
    end_total = min(start_total + max(15, int(duration_min)), 23 * 60 + 59)
    return f"{end_total // 60:02d}:{end_total % 60:02d}"


def _build_deterministic_task_id(raw: str, now_day: str, existing_count: int) -> str:
    digest = hashlib.sha256(f"{raw}|{now_day}|{existing_count}".encode("utf-8")).hexdigest()[:6].upper()
    return f"TASK_NL_{digest}"


def _apply_explicit_overrides(
    raw_lower: str,
    norm_text: str,
    category: str,
    priority: int,
    cognitive_load: int,
    is_splittable: bool,
) -> Tuple[str, int, int, bool]:
    """Enforce explicit user hashtags and constraint keywords uniformly across AI and Offline engines."""
    has_diacritics = any(ord(ch) > 127 for ch in raw_lower)
    is_urgent = (
        bool(re.search(r"\b(?:gấp|khẩn\s*cấp)\b", raw_lower))
        if has_diacritics
        else bool(re.search(r"\b(?:rat\s*gap|khan\s*cap)\b|\bgap\b(?!\s*(?:go|mat|ban|nhau|mentor|thay|co)\b)", norm_text))
    ) or bool(re.search(r"\b(?:urgent|asap)\b", norm_text))
    is_heavy_word = (
        bool(re.search(r"\bnặng\b", raw_lower))
        if has_diacritics
        else bool(re.search(r"\bnang\b(?!\s*cao\b)", norm_text))
    )
    is_light_word = (
        bool(re.search(r"\b(?:nhẹ|nhẹ\s*nhàng)\b", raw_lower))
        if has_diacritics
        else bool(re.search(r"\b(?:nhe|nhe\s*nhang)\b", norm_text))
    )

    p_tag = re.search(r"#p([1-5])\b|\bpriority\s*[:=]?\s*([1-5])\b|\buu\s*tien\s*([1-5])\b", norm_text)
    if p_tag:
        priority = int(next(g for g in p_tag.groups() if g is not None))
    elif "#deep" in norm_text or is_urgent:
        priority = max(priority, 5)
    elif re.search(r"\b(?:quan\s*trong|uu\s*tien\s*cao|high\s*priority)\b", norm_text):
        priority = max(priority, 4)
    elif is_light_word or re.search(r"#light\b|\b(?:thong\s*tha|luc\s*nao\s*cung\s*duoc|low\s*priority|relax)\b", norm_text):
        priority = min(priority, 2)

    if is_heavy_word or re.search(r"#deep\b|\b(?:deep\s*work|tap\s*trung\s*cao|hard)\b", norm_text):
        cognitive_load = 3
    elif is_light_word or re.search(r"#light\b|\b(?:light|easy)\b", norm_text):
        cognitive_load = 1

    if re.search(r"\b(?:khong\s*chia|lien\s*mach|lien\s*tuc|unsplittable|no\s*split|single\s*block)\b", norm_text):
        is_splittable = False

    return category, priority, cognitive_load, is_splittable


def _capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _build_missing_suggestions(missing_fields: List[str], now_day: str) -> List[Dict[str, Any]]:
    suggestions: List[Dict[str, Any]] = []
    if "duration_min" in missing_fields:
        for mins in DURATION_CHIP_OPTIONS:
            suggestions.append({
                "field": "duration_min",
                "label": f"⏱ {mins}p",
                "value": mins,
            })
    if "deadline_day" in missing_fields:
        now_idx = WEEKDAYS.index(now_day) if now_day in WEEKDAYS else 0
        tomorrow = WEEKDAYS[(now_idx + 1) % 7]
        suggestions.extend([
            {"field": "deadline_day", "label": f"📅 Hôm nay ({now_day})", "value": now_day},
            {"field": "deadline_day", "label": f"📅 Ngày mai ({tomorrow})", "value": tomorrow},
            {"field": "deadline_day", "label": "📅 Thứ Sáu (Friday)", "value": "Friday"},
            {"field": "deadline_day", "label": "♻️ Không hạn chót (Habit)", "value": ""},
        ])
    return suggestions


def _reject_payload(
    raw: str,
    reason: str,
    engine_used: str,
    parser_mode: str,
    status: str = "NO_TASK",
) -> Dict[str, Any]:
    return {
        "status": status,
        "parse_status": status,
        "intent_type": "NONE",
        "engine_used": engine_used,
        "confidence_score": 0.15 if status == "NO_TASK" else 0.0,
        "prompt": raw,
        "draft": None,
        "location": None,
        "suggested_fixed_event": None,
        "missing_fields": [],
        "suggestions": [],
        "assumptions": [],
        "rejection_reason": reason,
        "validation": {
            "is_valid": False,
            "warnings": [reason],
            "parser_mode": parser_mode,
            "inferred_fields": [],
        },
    }


def _finalize_parsed_payload(
    *,
    raw: str,
    now_day: str,
    existing_count: int,
    title: str,
    category: str,
    priority: int,
    cognitive_load: int,
    duration_min: Optional[int],
    dur_inferred: bool,
    deadline_day: Optional[str],
    day_inferred: bool,
    deadline_time: Optional[str],
    time_inferred: bool,
    start_time: Optional[str],
    is_fixed_event: bool,
    fixed_category: Optional[str],
    is_splittable: bool,
    location: Optional[str],
    engine_used: str,
    parser_mode: str,
    assumptions: List[str],
    intent_type: Optional[str] = None,
) -> Dict[str, Any]:
    warnings: List[str] = []
    missing_fields: List[str] = []
    inferred_fields: List[str] = []

    clean_cat = category.upper() if category and category.upper() in VALID_TASK_CATEGORIES else "ASSIGNMENT"
    norm_start_time = _normalize_hhmm(start_time)
    norm_deadline_time = _normalize_hhmm(deadline_time)
    resolved_intent = intent_type or (
        "FIXED_EVENT" if is_fixed_event and norm_start_time else ("HABIT" if clean_cat == "HABIT" else "TASK")
    )

    if resolved_intent == "HABIT" and day_inferred:
        final_deadline_day: Optional[str] = None
        day_inferred = False
    elif deadline_day:
        final_deadline_day = deadline_day
    else:
        now_idx = WEEKDAYS.index(now_day) if now_day in WEEKDAYS else 0
        final_deadline_day = WEEKDAYS[min(now_idx + 2, 6)]
        day_inferred = True

    if day_inferred and final_deadline_day:
        missing_fields.append("deadline_day")
        inferred_fields.append("deadline_day")
        warnings.append(
            f"Chưa nêu rõ ngày hạn chót; tạm suy luận {final_deadline_day} (theo ngày hiện tại {now_day})."
        )

    final_deadline_time = norm_deadline_time or "23:59"
    if time_inferred and norm_deadline_time:
        inferred_fields.append("deadline_time")
        warnings.append(f"Giờ được suy luận theo buổi là {final_deadline_time}.")

    if duration_min is None:
        final_duration = 60
        dur_inferred = True
    else:
        final_duration = _round_15_min(duration_min)

    if dur_inferred:
        missing_fields.append("duration_min")
        inferred_fields.append("duration_min")
        warnings.append("Chưa nêu rõ thời lượng; tạm đặt 60 phút (chọn chip bên dưới để chỉnh nhanh).")

    final_priority = max(1, min(5, int(priority)))
    final_load = max(1, min(3, int(cognitive_load)))
    task_id = _build_deterministic_task_id(raw, now_day, existing_count)
    clean_title = (title or "").split("\n")[0][:80].strip() or raw[:80]

    task_obj = Task(
        task_id=task_id,
        title=clean_title,
        duration_min=final_duration,
        deadline_day=final_deadline_day,
        deadline_time=final_deadline_time,
        priority=final_priority,
        category=clean_cat,
        cognitive_load=final_load,
        is_splittable=is_splittable,
        min_chunk_min=45 if is_splittable else final_duration,
    )

    draft = task_obj.model_dump(mode="json")
    draft["effort"] = "DEEP" if final_load >= 3 else ("LIGHT" if final_load == 1 else "MEDIUM")
    draft["status"] = "DRAFT_READY"

    suggested_fixed_event: Optional[Dict[str, Any]] = None
    if is_fixed_event and norm_start_time and final_deadline_day:
        fc = fixed_category if fixed_category in VALID_FIXED_CATEGORIES else "MEETING"
        suggested_fixed_event = {
            "event_id": task_id.replace("TASK_NL_", "FIXED_NL_"),
            "title": clean_title,
            "day_of_week": final_deadline_day,
            "start_time": norm_start_time,
            "end_time": _compute_end_time(norm_start_time, final_duration),
            "category": fc,
            "location": location,
        }

    parse_status = "NEEDS_SUGGESTION" if missing_fields else "SUCCESS"
    confidence = (0.93 if engine_used == "AI_GEMINI" else 0.88) if not missing_fields else 0.76

    return {
        "status": "DRAFT_READY",
        "parse_status": parse_status,
        "intent_type": resolved_intent,
        "engine_used": engine_used,
        "confidence_score": confidence,
        "prompt": raw,
        "draft": draft,
        "location": location,
        "suggested_fixed_event": suggested_fixed_event,
        "missing_fields": missing_fields,
        "suggestions": _build_missing_suggestions(missing_fields, now_day),
        "assumptions": assumptions,
        "rejection_reason": None,
        "validation": {
            "is_valid": True,
            "warnings": warnings,
            "parser_mode": parser_mode,
            "inferred_fields": inferred_fields,
        },
    }


class OfflineNLParser:
    """Deterministic zero-dependency EN/VI regex parser with Intent Gatekeeper."""

    _PAST_CUE_RE = re.compile(
        r"\b(?:hom\s*qua|tuan\s*truoc|thang\s*truoc|nam\s*ngoai|hoi\s*nay|vua\s*roi|"
        r"yesterday|last\s*week|last\s*night|earlier|ago)\b"
    )
    _PAST_STATE_RE = re.compile(
        r"\b(?:ngu|thuc|xong\s*roi|da\s*xong|da\s*lam|met|cay\s*phim|binge|slept|"
        r"stayed\s*up|watched|finished)\b"
    )
    _FUTURE_COMMITMENT_RE = re.compile(
        r"\b(?:mai|ngay\s*mai|ngay\s*kia|ngay\s*mot|cuoi\s*tuan|tuan\s*sau|tomorrow|"
        r"phai|can\s*phai|nho\s*lam|on\s*thi|nop|submit|hop|meeting|do\s*an|project|lab|exam|quiz)\b"
    )
    _TASK_SIGNAL_RE = re.compile(
        r"\b(?:on\s*thi|on\s*bai|on\s*tap|hoc|lam|doc|viet|code|lap\s*trinh|nop|submit|"
        r"hop|meeting|thi|exam|quiz|kiem\s*tra|do\s*an|project|lab|thuc\s*hanh|bao\s*cao|"
        r"report|essay|gym|chay\s*bo|the\s*duc|giat\s*do|don\s*phong|laundry|clean|study|"
        r"read|review|revise|homework|assignment|research)\b"
    )
    _CHATTER_RE = re.compile(
        r"\b(?:vui\s*qua|buon\s*qua|chan\s*qua|met\s*qua|haha+|hihi+|hehe+|lol|lmao|omg)\b"
    )
    _DOUBT_SARCASM_RE = re.compile(
        r"\bchac\b.*\b(?:day|lam|di|hoc)\b.*\bnoi\b|\bnoi\s*dau\b|\bchac\s*chet\b"
    )

    def detect_noise_or_past(self, norm_text: str) -> Optional[str]:
        """Layer 1 Gatekeeper: reject obvious past narratives, idle chatter, or sarcasm."""
        if not re.search(r"[a-z]", norm_text):
            return "Không tìm thấy nội dung công việc hợp lệ trong câu nhập."

        if self._PAST_CUE_RE.search(norm_text) and self._PAST_STATE_RE.search(norm_text):
            if not self._FUTURE_COMMITMENT_RE.search(norm_text):
                return "Câu đang kể lại sự việc trong quá khứ, không phải việc cần lên lịch."

        if re.search(r"\b(\d{1,2}h)\b.*\b\1\b", norm_text):
            return "Phát hiện câu cảm thán / lặp số, không phải đầu việc học tập."

        if (re.search(r"([a-z])\1{4,}", norm_text) or self._CHATTER_RE.search(norm_text)) and not self._TASK_SIGNAL_RE.search(norm_text):
            return "Phát hiện câu trò chuyện / cảm thán không chứa hành động cần xếp lịch."

        if self._DOUBT_SARCASM_RE.search(norm_text):
            return "Phát hiện câu nói giả định / bông đùa, không tạo task rác trên lịch."

        return None

    def extract_clock_time(self, norm_text: str) -> Tuple[Optional[str], bool, bool, bool]:
        """
        Extract clock time as `(HH:MM or None, inferred_flag, is_deadline_cue, is_anchor_cue)`.
        Returns exact times for HH:MM, Xam/pm, cue-preceded times, or contextual hours.
        """
        # 1. Explicit HH:MM with optional cue / am-pm
        m = re.search(
            r"\b(?:(truoc|before|by|han|deadline)|(at|luc|vao))?\s*(\d{1,2}):(\d{2})\s*(am|pm)?\b",
            norm_text,
        )
        if m:
            is_dl = bool(m.group(1))
            is_anchor = bool(m.group(2))
            hh, mm = int(m.group(3)), int(m.group(4))
            ampm = (m.group(5) or "").lower()
            if ampm == "pm" and hh < 12:
                hh += 12
            elif ampm == "am" and hh == 12:
                hh = 0
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return f"{hh:02d}:{mm:02d}", False, is_dl, is_anchor or not is_dl

        # 2. Explicit am/pm without colon (e.g., "5pm", "at 9 AM")
        m = re.search(r"\b(?:(truoc|before|by|han|deadline)|(at|luc|vao))?\s*(\d{1,2})\s*(am|pm)\b", norm_text)
        if m:
            is_dl = bool(m.group(1))
            is_anchor = bool(m.group(2))
            hh = int(m.group(3))
            ampm = m.group(4).lower()
            if ampm == "pm" and hh < 12:
                hh += 12
            elif ampm == "am" and hh == 12:
                hh = 0
            if 0 <= hh <= 23:
                return f"{hh:02d}:00", False, is_dl, is_anchor or not is_dl

        # 3. Cue-preceded hour (`trước 17h30`, `lúc 14h`, `hạn 9 giờ tối`, `lúc 7 giờ rưỡi`)
        m = re.search(
            r"\b(?:(truoc|before|by|han|deadline)|(at|luc|vao))\s+(\d{1,2})\s*(?:h|gio)\s*(\d{1,2}|ruoi)?\s*(sang|trua|chieu|toi|dem)?\b",
            norm_text,
        )
        if m:
            is_dl = bool(m.group(1))
            is_anchor = bool(m.group(2))
            hh = int(m.group(3))
            mm_raw = m.group(4)
            mm = 30 if mm_raw == "ruoi" else (int(mm_raw) if mm_raw else 0)
            tod = (m.group(5) or "").lower()
            if tod in ("chieu", "toi", "dem") and hh < 12:
                hh += 12
            elif tod == "trua" and hh < 11:
                hh += 12
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return f"{hh:02d}:{mm:02d}", False, is_dl, is_anchor

        # 4. Bare `<hour>h<min>` >= 6h (`17h30`, `8h15`) OR hour with explicit time-of-day suffix (`9h toi`, `7 gio ruoi sang`)
        m = re.search(
            r"\b(\d{1,2})h(\d{2})\b|\b(\d{1,2})\s*(?:h|gio)\s*(ruoi)?\s*(sang|trua|chieu|toi|dem)\b",
            norm_text,
        )
        if m:
            if m.group(1) is not None:
                hh, mm = int(m.group(1)), int(m.group(2))
                if 6 <= hh <= 23 and 0 <= mm <= 59:
                    return f"{hh:02d}:{mm:02d}", False, False, True
            else:
                hh = int(m.group(3))
                mm = 30 if m.group(4) else 0
                tod = m.group(5).lower()
                if tod in ("chieu", "toi", "dem") and hh < 12:
                    hh += 12
                elif tod == "trua" and hh < 11:
                    hh += 12
                if 0 <= hh <= 23:
                    return f"{hh:02d}:{mm:02d}", False, False, True

        # 5. Context-preceded hour (`chiều mai 2h`, `tối nay 8h`, `sáng thứ 5 9h`) not preceded by duration marker
        m = re.search(
            r"\b(sang|trua|chieu|toi|dem)\s+(?:nay|mai|mot|kia|t[2-7]|cn|thu\s*(?:[2-7]|hai|ba|tu|nam|sau|bay)|chu\s*nhat)?\s*(\d{1,2})\s*(?:h|gio)\b",
            norm_text,
        )
        if m:
            tod = m.group(1).lower()
            hh = int(m.group(2))
            if tod in ("chieu", "toi", "dem") and hh < 12:
                hh += 12
            elif tod == "trua" and hh < 11:
                hh += 12
            if 0 <= hh <= 23:
                return f"{hh:02d}:00", False, False, True

        # 6. Coarse keyword windows (normalized: trưa/noon -> 12:00 instead of W04's MORNING 09:00 bug)
        if re.search(r"\b(?:trua|noon)\b", norm_text):
            return "12:00", True, False, False
        if re.search(r"\b(?:chieu|afternoon)\b", norm_text):
            return "17:00", True, False, False
        if re.search(r"\b(?:toi|evening)\b", norm_text):
            return "21:30", True, False, False
        if re.search(r"\b(?:sang|morning)\b", norm_text):
            return "11:00", True, False, False

        return None, True, False, False

    def extract_duration_min(self, norm_text: str) -> Tuple[Optional[int], bool]:
        """Extract duration in minutes while stripping clock-time tokens first."""
        cleaned = re.sub(
            r"\b(?:truoc|before|by|at|luc|han|deadline|vao)\s+\d{1,2}\s*(?:h|gio|:)\s*(?:\d{1,2}|ruoi)?\s*(?:sang|trua|chieu|toi|dem)?\b",
            " ",
            norm_text,
        )
        cleaned = re.sub(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b", " ", cleaned)
        cleaned = re.sub(r"\b\d{1,2}\s*(?:am|pm)\b", " ", cleaned)
        cleaned = re.sub(
            r"\b(sang|trua|chieu|toi|dem)\s+(?:nay|mai|mot|kia|t[2-7]|cn|thu\s*(?:[2-7]|hai|ba|tu|nam|sau|bay)|chu\s*nhat)?\s*\d{1,2}\s*(?:h|gio)\b",
            " ",
            cleaned,
        )
        cleaned = re.sub(
            r"\b\d{1,2}\s*(?:h|gio)\s*(?:ruoi)?\s*(?:sang|trua|chieu|toi|dem)\b",
            " ",
            cleaned,
        )

        # Compound: 1h30 / 1h30m / 2 gio 15 phut
        m = re.search(r"\b(\d+)\s*(?:h|gio|tieng)\s*(\d{1,2})\s*(?:m|min|phut|p)?\b", cleaned)
        if m:
            mins = int(m.group(1)) * 60 + int(m.group(2))
            if 10 <= mins <= 1200:
                return mins, False

        if re.search(r"\b(?:nua\s*tieng|half\s+an?\s+hour)\b", cleaned):
            return 30, False

        m = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:tieng|hours?|hrs?|gio|h)\b", cleaned)
        if m:
            val = float(m.group(1))
            if val <= 12:
                mins = int(round(val * 60))
                if mins >= 15:
                    return mins, False

        m = re.search(r"\b(\d+)\s*(?:phut|mins?|minutes?|m|p)\b", cleaned)
        if m:
            mins = int(m.group(1))
            if 10 <= mins <= 1200:
                return mins, False

        return None, True

    def extract_deadline_day(self, norm_text: str, now_day: str) -> Tuple[Optional[str], bool]:
        if re.search(r"\b(?:thu\s*(?:2|hai)|monday|mon)\s+tuan\s*sau\b", norm_text):
            return "Next Monday", False

        for pattern, weekday in _WEEKDAY_PATTERNS:
            if re.search(pattern, norm_text):
                return weekday, False

        now_idx = WEEKDAYS.index(now_day) if now_day in WEEKDAYS else 0
        if re.search(r"\b(?:ngay\s*kia|ngay\s*mot|day\s*after\s*tomorrow)\b", norm_text):
            return WEEKDAYS[(now_idx + 2) % 7], False
        if re.search(r"\b(?:ngay\s*mai|sang\s*mai|trua\s*mai|chieu\s*mai|toi\s*mai|tomorrow|mai)\b", norm_text):
            return WEEKDAYS[(now_idx + 1) % 7], False
        if re.search(r"\b(?:hom\s*nay|today|toi\s*nay|chieu\s*nay|sang\s*nay|trua\s*nay)\b", norm_text):
            return now_day, False
        if re.search(r"\b(?:cuoi\s*tuan|weekend)\b", norm_text):
            return "Sunday", False

        return None, True

    def extract_category_priority_load(self, raw_lower: str, norm_text: str) -> Tuple[str, int, int]:
        category = "ASSIGNMENT"
        priority = 3
        cognitive_load = 2

        if re.search(r"\b(?:on\s*thi|thi|exam|midterm|final|giua\s*ky|cuoi\s*ky|#exam)\b", norm_text):
            category, priority, cognitive_load = "EXAM", 5, 3
        elif re.search(r"\b(?:quiz|kiem\s*tra|test|#quiz)\b", norm_text):
            category, priority, cognitive_load = "QUIZ", 4, 3
        elif re.search(r"\b(?:do\s*an|project|capstone|de\s*tai|#project)\b", norm_text):
            category, priority, cognitive_load = "PROJECT", 4, 3
        elif re.search(r"\b(?:lab|thuc\s*hanh|thi\s*nghiem|code|lap\s*trinh|#lab)\b", norm_text):
            category, priority, cognitive_load = "LAB", 4, 3
        elif re.search(r"\b(?:bai\s*tap|assignment|homework|essay|bao\s*cao|report|nop|submit|#assignment)\b", norm_text):
            category, priority, cognitive_load = "ASSIGNMENT", 3, 2
        elif re.search(r"\b(?:doc|read|reading|slide|tai\s*lieu|on\s*bai|chuan\s*bi|#reading)\b", norm_text):
            category, priority, cognitive_load = "READING", 2, 1
        elif re.search(r"\b(?:gym|chay\s*bo|the\s*duc|habit|thoi\s*quen|giat\s*do|don\s*phong|uong\s*thuoc|laundry|#habit)\b", norm_text):
            category, priority, cognitive_load = "HABIT", 1, 1

        category, priority, cognitive_load, _ = _apply_explicit_overrides(
            raw_lower, norm_text, category, priority, cognitive_load, True
        )
        return category, priority, cognitive_load

    def extract_location(self, raw_text: str) -> Optional[str]:
        m = re.search(
            r"\b(?:ở|o|tại|tai|at)\s+"
            r"(?!\d|sao\b|vì\b|vi\b|morning\b|afternoon\b|evening\b|night\b|noon\b|today\b|tomorrow\b|"
            r"sáng\b|sang\b|trưa\b|trua\b|chiều\b|chieu\b|tối\b|toi\b|đêm\b|dem\b)"
            r"([A-Za-z0-9À-ỹ_ \-]{2,40}?)"
            r"(?=\s*(?:,|;|\.|#|\b(?:vào|vao|lúc|luc|trước|truoc|trong|từ|tu|ưu\s*tiên|uu\s*tien|"
            r"before|by|for|ngày|ngay|hôm|hom|thứ|thu|t[2-7]|cn|"
            r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
            r"mai|mốt|mot|chiều|chieu|sáng|sang|tối|toi|đêm|dem)\b|\d+\s*(?:p|phút|phut|tiếng|tieng|giờ|gio|h|m|min)\b|$))",
            raw_text,
            flags=re.IGNORECASE,
        )
        if not m:
            return None
        loc = re.sub(r"\s+(?:vào|vao|lúc|luc|khoảng|khoang)$", "", m.group(1).strip(), flags=re.IGNORECASE)
        loc = re.sub(r"\s+", " ", loc).strip(" .,-:;")
        return _capitalize_first(loc) if len(loc) >= 2 else None

    def detect_fixed_event_hint(
        self,
        norm_text: str,
        clock_time: Optional[str],
        time_inferred: bool,
        is_deadline_cue: bool,
    ) -> Tuple[bool, Optional[str]]:
        if not clock_time or time_inferred or is_deadline_cue:
            return False, None
        is_exam_review = bool(re.search(r"\b(?:on\s*thi|luyen\s*thi|review|prep|prepare)\b", norm_text))
        is_fixed_meeting = bool(
            re.search(r"\b(?:hop|meeting|phong\s*van|interview|kham\s*benh|appointment|chuyen\s*bay|flight|gap\s+mentor)\b", norm_text)
        )
        is_fixed_class = bool(
            re.search(r"\b(?:lich\s*hoc|tiet\s*hoc|class|lecture)\b", norm_text)
            or (not is_exam_review and re.search(r"\b(?:di\s*thi|ca\s*thi|ky\s*thi|exam)\b", norm_text))
        )
        if is_fixed_class:
            return True, "ACADEMIC_CLASS"
        if is_fixed_meeting:
            return True, "MEETING"
        return False, None

    def clean_title(self, raw_text: str) -> str:
        cleaned = raw_text.split("\n")[0]
        patterns = (
            r"\[\[[^\[\]\n]*?\]\]",
            r"@\[[^\[\]\n]*?\]",
            r"\[?\bp[1-4]\b\]?",
            r"\s*#[a-zA-Z0-9_]+\b",
            r"\b(?:không\s*chia(?:\s*nhỏ)?|khong\s*chia(?:\s*nho)?|liền\s*mạch|lien\s*mach|liên\s*tục|lien\s*tuc|unsplittable|no\s*split|single\s*block)\b",
            r"(?:,\s*)?\b(?:ưu\s*tiên(?:\s*(?:cao|thấp|[1-5]))?|uu\s*tien(?:\s*(?:cao|thap|[1-5]))?|priority\s*[:=]?\s*[1-5]|khẩn\s*cấp|khan\s*cap|rất\s*gấp|rat\s*gap|urgent|asap)\b",
            r"\b(?:ở|o|tại|tai|at)\s+(?!\d|sao\b|vì\b|vi\b|morning\b|afternoon\b|evening\b|night\b|noon\b|today\b|tomorrow\b|sáng\b|sang\b|trưa\b|trua\b|chiều\b|chieu\b|tối\b|toi\b|đêm\b|dem\b)[A-Za-z0-9À-ỹ_ \-]{2,40}?(?=\s*(?:,|;|\.|#|\b(?:vào|vao|lúc|luc|trước|truoc|trong|từ|tu|ưu\s*tiên|uu\s*tien|before|by|for|ngày|ngay|hôm|hom|thứ|thu|t[2-7]|cn|monday|tuesday|wednesday|thursday|friday|saturday|sunday|mai|mốt|mot|chiều|chieu|sáng|sang|tối|toi|đêm|dem)\b|\d+\s*(?:p|phút|phut|tiếng|tieng|giờ|gio|h|m|min)\b|$))",
            r"\b(?:trong|for)?\s*\d+\s*(?:h|giờ|gio|tiếng|tieng)\s*\d{1,2}\s*(?:m|min|phút|phut|p)?\b",
            r"\b(?:trong|for)?\s*(?:nửa\s*tiếng|nua\s*tieng|half\s+an?\s+hour)\b",
            r"\b(?:trước|truoc|before|by|at|lúc|luc|hạn|han|deadline|vào|vao)\s+\d{1,2}\s*(?:h|giờ|gio|:)\s*(?:\d{1,2}|rưỡi|ruoi)?\s*(?:am|pm|sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\b",
            r"\b(?:trước|truoc|before|by|at|lúc|luc|hạn|han|deadline|vào|vao)?\s*\d{1,2}\s*(?:am|pm)\b",
            r"\b\d{1,2}:\d{2}\b",
            r"\b(?:[6-9]|1\d|2[0-3])h\d{2}\b",
            r"\b\d{1,2}\s*(?:h|giờ|gio)\s*(?:rưỡi|ruoi)\s*(?:sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)?\b",
            r"\b\d{1,2}\s*(?:h|giờ|gio)\s*(?:sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)\b",
            r"\b(?:trong|for)?\s*\d+(?:\.\d+)?\s*(?:tiếng|tieng|hours?|hrs?|giờ|gio|h)\b",
            r"\b(?:trong|for)?\s*\d+\s*(?:phút|phut|mins?|minutes?|p|m)\b",
            r"\b(?:trước|truoc|before|by|vào|vao)?\s*(?:ngày\s*mai|ngay\s*mai|ngày\s*kia|ngay\s*kia|ngày\s*mốt|ngay\s*mot|hôm\s*nay|hom\s*nay|cuối\s*tuần|cuoi\s*tuan|sáng\s*mai|sang\s*mai|trưa\s*mai|trua\s*mai|chiều\s*mai|chieu\s*mai|tối\s*mai|toi\s*mai|sáng\s*nay|sang\s*nay|trưa\s*nay|trua\s*nay|chiều\s*nay|chieu\s*nay|tối\s*nay|toi\s*nay|tomorrow|today|day\s*after\s*tomorrow|weekend|thứ\s*[2-7]|thu\s*[2-7]|thứ\s*(?:hai|ba|tư|tu|năm|nam|sáu|sau|bảy|bay)|thu\s*(?:hai|ba|tu|nam|sau|bay)|chủ\s*nhật|chu\s*nhat|monday|mon|tuesday|tues?|wednesday|wed|thursday|thurs?|friday|fri|saturday|sat|sunday|sun|\bt[2-7]\b|\bcn\b)(?:\s*(?:tuần\s*(?:này|sau)|tuan\s*(?:nay|sau)))?\b",
            r"\b(?:vào\s+)?(?:buổi\s+)?(?:sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem|morning|noon|afternoon|evening|night)\b",
        )
        for pat in patterns:
            cleaned = re.sub(pat, " ", cleaned, flags=re.IGNORECASE)

        cleaned = re.sub(
            r"\s+(?:trước|truoc|vào|vao|lúc|luc|tại|tai|ở|o|trong|for|at|by|before)$",
            "",
            cleaned.strip(),
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" -,:;.")
        if len(cleaned) >= 3:
            return _capitalize_first(cleaned[:80])
        fallback = re.sub(r"\s*#[a-zA-Z0-9_]+\b", "", raw_text.split("\n")[0]).strip(" -,:;.")
        return _capitalize_first((fallback or raw_text)[:80])

    def parse(self, raw: str, *, now_day: str, existing_count: int) -> Dict[str, Any]:
        # Strip [[filename]] and @[path/filename] citation blocks before temporal/duration regexes
        parse_raw = re.sub(r"\[\[[^\[\]\n]*?\]\]|@\[[^\[\]\n]*?\]", " ", raw) if ("[[" in raw or "@[" in raw) else raw
        norm = _strip_accents(parse_raw.lower())
        rejection = self.detect_noise_or_past(norm)
        if rejection:
            return _reject_payload(
                raw=raw,
                reason=rejection,
                engine_used="OFFLINE_DETERMINISTIC",
                parser_mode="HYBRID_DETERMINISTIC",
                status="NO_TASK",
            )

        deadline_day, day_inferred = self.extract_deadline_day(norm, now_day)
        clock_time, time_inferred, is_deadline_cue, _ = self.extract_clock_time(norm)
        duration_min, dur_inferred = self.extract_duration_min(norm)
        category, priority, cognitive_load = self.extract_category_priority_load(parse_raw.lower(), norm)
        location = self.extract_location(parse_raw)
        is_fixed, fixed_cat = self.detect_fixed_event_hint(norm, clock_time, time_inferred, is_deadline_cue)

        unsplittable = bool(
            re.search(r"\b(?:khong\s*chia|lien\s*mach|lien\s*tuc|unsplittable|no\s*split|single\s*block)\b", norm)
        )
        clean_title = self.clean_title(raw)

        return _finalize_parsed_payload(
            raw=raw,
            now_day=now_day,
            existing_count=existing_count,
            title=clean_title,
            category=category,
            priority=priority,
            cognitive_load=cognitive_load,
            duration_min=duration_min,
            dur_inferred=dur_inferred,
            deadline_day=deadline_day,
            day_inferred=day_inferred,
            deadline_time="23:59" if is_fixed else clock_time,
            time_inferred=time_inferred,
            start_time=clock_time if is_fixed else None,
            is_fixed_event=is_fixed,
            fixed_category=fixed_cat,
            is_splittable=not unsplittable,
            location=location,
            engine_used="OFFLINE_DETERMINISTIC",
            parser_mode="HYBRID_DETERMINISTIC",
            assumptions=[],
        )


def _get_gemini_client(api_key: str) -> Any:
    """Reuse google-genai Client per API key with tight 12s HTTP timeout (>=10s API min) and single attempt."""
    cached = _CLIENT_CACHE.get(api_key)
    if cached is not None:
        return cached
    client_kwargs: Dict[str, Any] = {"api_key": api_key}
    if genai_types is not None and hasattr(genai_types, "HttpOptions"):
        http_kwargs: Dict[str, Any] = {"timeout": 12000}
        if hasattr(genai_types, "HttpRetryOptions"):
            http_kwargs["retry_options"] = genai_types.HttpRetryOptions(attempts=1)
        client_kwargs["http_options"] = genai_types.HttpOptions(**http_kwargs)
    client = genai.Client(**client_kwargs)
    _CLIENT_CACHE[api_key] = client
    return client


class GeminiNLParser:
    """Cloud LLM parser using Google Gemini structured output aligned with SmartSchedule."""

    def __init__(self, api_key: str, model_candidates: Optional[Tuple[str, ...]] = None):
        if genai is None or genai_types is None:
            raise RuntimeError("google-genai package is not installed.")
        self.client = _get_gemini_client(api_key)
        configured = os.getenv("GEMINI_MODEL", "").strip()
        ordered: List[str] = []
        raw_list = ([configured] if configured else []) + list(model_candidates or DEFAULT_GEMINI_MODELS)
        for m in raw_list:
            if m and m not in ordered and m not in _UNAVAILABLE_MODELS:
                ordered.append(m)
        if not ordered:
            ordered = list(DEFAULT_GEMINI_MODELS)
        self.models = tuple(ordered)

    def _build_prompt(self, raw: str, now_day: str) -> str:
        return (
            "You are the SmartSchedule M1 Student Task & Timetable Parser.\n"
            f"Reference current weekday: {now_day}.\n"
            f'User input: "{raw}"\n\n'
            "Rules:\n"
            "1. Intent Gatekeeper: Set is_schedulable_task=false ONLY for past narratives "
            "(e.g. 'Hôm qua thức 7h liền'), idle chatter/laughter, or sarcastic doubts. "
            "Short academic topics like 'Giải tích' or 'Lab 04' ARE valid schedulable tasks.\n"
            "2. title: Extract a concise clean title in the user's language, removing date/time/duration/hashtag clutter.\n"
            "3. category: Pick one of EXAM, QUIZ, PROJECT, LAB, ASSIGNMENT, READING, HABIT.\n"
            "4. priority (1..5) & cognitive_load (1=light, 2=medium, 3=deep): "
            "EXAM/urgent/#deep -> priority=5, load=3; QUIZ/PROJECT/LAB -> priority=4, load=3; "
            "ASSIGNMENT -> priority=3, load=2; READING -> priority=2, load=1; HABIT -> priority=1, load=1.\n"
            "5. If the prompt describes a timed meeting/class/appointment (e.g. 'họp nhóm 14h chiều mai'), "
            "set intent_type='FIXED_EVENT', is_fixed_event=true, start_time='HH:MM', and fixed_category in "
            "{ACADEMIC_CLASS, MEAL, WORK, MEETING}. For homework/study deadlines (e.g. 'trước 17h thứ 6'), "
            "set is_fixed_event=false and deadline_time='17:00'.\n"
            "6. Leave duration_min or deadline_day null ONLY if omitted in the prompt.\n"
        )

    def parse(self, raw: str, *, now_day: str, existing_count: int) -> Dict[str, Any]:
        prompt_text = self._build_prompt(raw, now_day)
        last_err: Optional[Exception] = None
        parsed: Optional[GeminiNLSchema] = None

        config_kwargs: Dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": GeminiNLSchema,
            "temperature": 0.1,
        }
        if hasattr(genai_types, "ThinkingConfig"):
            config_kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=0)
        gen_config = genai_types.GenerateContentConfig(**config_kwargs)

        for model_name in self.models:
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=prompt_text,
                    config=gen_config,
                )
                parsed = response.parsed
                if parsed is not None:
                    break
            except Exception as exc:
                last_err = exc
                err_msg = str(exc).lower()
                if "404" in err_msg or "not_found" in err_msg or "no longer available" in err_msg:
                    _UNAVAILABLE_MODELS.add(model_name)

        if parsed is None:
            raise RuntimeError(f"All Gemini models failed: {last_err}")

        if not parsed.is_schedulable_task:
            return _reject_payload(
                raw=raw,
                reason=parsed.rejection_reason or "Câu nhập không phải đầu việc cần xếp lịch.",
                engine_used="AI_GEMINI",
                parser_mode="AI_GEMINI",
                status="NO_TASK",
            )

        norm_day, day_inferred = _normalize_weekday(parsed.deadline_day, now_day)
        if not parsed.deadline_day:
            norm_day, day_inferred = None, True

        norm_raw = _strip_accents(raw.lower())
        final_cat, final_prio, final_load, final_split = _apply_explicit_overrides(
            raw.lower(),
            norm_raw,
            parsed.category,
            parsed.priority,
            parsed.cognitive_load,
            parsed.is_splittable,
        )
        loc = _capitalize_first(parsed.location.strip()) if parsed.location and parsed.location.strip() else None

        return _finalize_parsed_payload(
            raw=raw,
            now_day=now_day,
            existing_count=existing_count,
            title=parsed.title or raw,
            category=final_cat,
            priority=final_prio,
            cognitive_load=final_load,
            duration_min=parsed.duration_min,
            dur_inferred=parsed.duration_min is None,
            deadline_day=norm_day,
            day_inferred=day_inferred,
            deadline_time=parsed.deadline_time,
            time_inferred=parsed.deadline_time is None and not parsed.start_time,
            start_time=parsed.start_time,
            is_fixed_event=parsed.is_fixed_event,
            fixed_category=parsed.fixed_category,
            is_splittable=final_split,
            location=loc,
            engine_used="AI_GEMINI",
            parser_mode="AI_GEMINI",
            assumptions=list(parsed.assumptions or []),
            intent_type=parsed.intent_type,
        )


class NLParserController:
    """Dual-Engine coordinator routing between Gemini AI and Offline deterministic fallback,
    enriched with the unified 6-stage Hybrid Parser (`NL_Parser_Package/hybrid_parser.py`)."""

    def __init__(self, offline_parser: Optional[OfflineNLParser] = None):
        self.offline = offline_parser or OfflineNLParser()

    @staticmethod
    def _load_hybrid_module():
        for candidate in (_PROJECT_ROOT / "NL_Parser_Package", _REPO_ROOT / "NL_Parser_Package"):
            if candidate.is_dir():
                pkg_str = str(candidate)
                if pkg_str not in sys.path:
                    sys.path.insert(0, pkg_str)
                try:
                    import hybrid_parser as _hp  # type: ignore

                    return _hp
                except Exception:
                    return None
        return None

    @staticmethod
    def _solver_to_user_urgency(solver_prio: int) -> int:
        if solver_prio >= 5:
            return 1
        if solver_prio == 4:
            return 2
        if solver_prio == 3:
            return 3
        return 4

    def _enrich_with_hybrid(
        self,
        raw: str,
        result: Dict[str, Any],
        *,
        now: Optional[str],
        existing_count: int,
        ui: Optional[Dict[str, Any]],
        translation_backend: str,
    ) -> Dict[str, Any]:
        hp = self._load_hybrid_module()
        if hp is None:
            return result

        bundle = hp.compile_hybrid_to_smartschedule(
            raw,
            ui=ui,
            now=now,
            existing_count=existing_count,
            translation_backend=translation_backend or "rule",
        )
        hybrid = bundle["hybrid"]
        adapter = bundle["solver_adapter"]

        # Always attach hybrid diagnostics & translation metadata
        if result.get("status") == "NO_TASK":
            result["hybrid"] = hybrid
            result["solver_adapter"] = adapter
            result["translation"] = {
                "applied": bool(hybrid.get("translation_applied")),
                "backend": hybrid.get("translation_backend"),
                "translated_prompt": hybrid.get("translated_prompt"),
            }
            return result

        # Hard nonsense / injection rejection (only when E_NONSENSE_INPUT fires)
        if "E_NONSENSE_INPUT" in (hybrid.get("errors") or []):
            rejected = _reject_payload(
                raw=raw,
                reason="Đầu vào không phải đầu việc hợp lệ hoặc chứa nội dung không an toàn (E_NONSENSE_INPUT).",
                engine_used=str(result.get("engine_used") or "OFFLINE_DETERMINISTIC"),
                parser_mode=str(result.get("validation", {}).get("parser_mode") or "HYBRID_DETERMINISTIC"),
                status="NO_TASK",
            )
            rejected["hybrid"] = hybrid
            rejected["solver_adapter"] = adapter
            rejected["translation"] = {
                "applied": bool(hybrid.get("translation_applied")),
                "backend": hybrid.get("translation_backend"),
                "translated_prompt": hybrid.get("translated_prompt"),
            }
            rejected["validation"]["hybrid_errors"] = list(hybrid.get("errors") or [])
            rejected["validation"]["hybrid_warnings"] = list(hybrid.get("warnings") or [])
            return rejected

        draft = result.get("draft")
        if isinstance(draft, dict):
            ui_dict = dict(ui) if isinstance(ui, dict) else {}
            raw_ui_prio = ui_dict.get("priority")
            try:
                explicit_ui_prio = int(raw_ui_prio) if raw_ui_prio not in (None, "", "not_sure") else None
            except (TypeError, ValueError):
                explicit_ui_prio = None

            # Priority synchronization: user 1=Urgent..4=Low <-> solver 5..1
            explicit_text_prio = (
                hybrid.get("priority") in (1, 2, 3, 4)
                and "W_PRIORITY_DEFAULTED" not in (hybrid.get("warnings") or [])
                and bool(re.search(r"\[?\bp[1-4]\b\]?|\b(?:priority|prio)\s*[:=]?\s*[1-4]\b", raw.lower()))
            )
            if explicit_ui_prio in (1, 2, 3, 4) or explicit_text_prio:
                draft["user_priority"] = hybrid.get("priority")
                if hybrid.get("solver_priority") is not None:
                    draft["priority"] = int(hybrid["solver_priority"])
            else:
                inferred_urg = self._solver_to_user_urgency(int(draft.get("priority") or 3))
                draft["user_priority"] = inferred_urg
                if "W_PRIORITY_DEFAULTED" in (hybrid.get("warnings") or []):
                    hybrid["priority"] = inferred_urg
                    hybrid["solver_priority"] = int(draft.get("priority") or 3)

            # WorkRhythm & Chunking reconciliation
            draft["work_rhythm"] = hybrid.get("work_rhythm") or "BALANCED"
            explicit_ui_session = ui_dict.get("session") in ("single", "splittable")
            explicit_ui_pacing = ui_dict.get("pacing") in ("LIGHT", "BALANCED", "FLOW", "CUSTOM")
            explicit_chunk_hint = bool(
                re.search(
                    r"~\d+m\b|\b\d+\s*(?:minutes?|mins?|m)\s+each\b|\bsplit\s+into\s+\d+-minute|\bpomodoro\b|\bless\s+than\s+(?:an?\s+)?hour\b",
                    raw.lower(),
                )
            )
            if explicit_ui_session and hybrid.get("is_task_splittable") is not None:
                draft["is_splittable"] = bool(hybrid["is_task_splittable"])

            splitting = hybrid.get("splitting")
            if not draft.get("is_splittable", False):
                draft["min_chunk_min"] = int(draft.get("duration_min") or 60)
                draft["max_chunk_min"] = None
            elif isinstance(splitting, dict) and (explicit_ui_session or explicit_ui_pacing or explicit_chunk_hint):
                min_c = max(15, int(splitting.get("min", 30)))
                max_c = max(min_c, int(splitting.get("max", 60)))
                draft["min_chunk_min"] = min_c
                draft["max_chunk_min"] = max_c
                draft["preferred_chunk_min"] = int(splitting.get("pref", min_c))
            elif isinstance(splitting, dict):
                draft["max_chunk_min"] = max(int(draft.get("min_chunk_min") or 45), int(splitting.get("max", 90)))
                draft["preferred_chunk_min"] = int(splitting.get("pref", draft.get("min_chunk_min") or 45))

            # Multi-subtask total duration override when M1 regex only caught the first chunk
            subtasks = hybrid.get("subtasks") or []
            if len(subtasks) >= 2 and hybrid.get("total_work_minutes"):
                rounded_sum = _round_15_min(int(hybrid["total_work_minutes"]))
                draft["duration_min"] = rounded_sum
                if "duration_min" in result.get("missing_fields", []):
                    result["missing_fields"] = [f for f in result["missing_fields"] if f != "duration_min"]
                    result["suggestions"] = _build_missing_suggestions(
                        result["missing_fields"], _resolve_now_day(now)
                    )
                    if not result["missing_fields"]:
                        result["parse_status"] = "SUCCESS"

            draft["start_after"] = hybrid.get("start_after")
            draft["subtasks"] = subtasks
            draft["breakdown_required"] = bool(hybrid.get("breakdown_required", False))
            draft["work_minutes_lower_bound"] = hybrid.get("work_minutes_lower_bound")

        result["hybrid"] = hybrid
        result["solver_adapter"] = adapter
        result["translation"] = {
            "applied": bool(hybrid.get("translation_applied")),
            "backend": hybrid.get("translation_backend"),
            "translated_prompt": hybrid.get("translated_prompt"),
        }
        val = result.setdefault("validation", {})
        val["hybrid_status"] = hybrid.get("status")
        val["hybrid_errors"] = list(hybrid.get("errors") or [])
        val["hybrid_warnings"] = list(hybrid.get("warnings") or [])
        return result

    def parse(
        self,
        prompt: str,
        *,
        now: Optional[str] = None,
        existing_count: int = 0,
        engine: Optional[str] = None,
        ui: Optional[Dict[str, Any]] = None,
        translation_backend: str = "rule",
    ) -> Dict[str, Any]:
        raw = (prompt or "").strip()
        if not raw:
            raise ValueError("Prompt text cannot be empty.")

        _load_local_env()
        now_day = _resolve_now_day(now)
        requested_engine = (engine or os.getenv("NL_PARSER_ENGINE") or "auto").strip().lower()
        api_key = os.getenv("GEMINI_API_KEY", "").strip()

        if requested_engine != "offline" and api_key and genai is not None:
            try:
                ai_engine = GeminiNLParser(api_key=api_key)
                res = ai_engine.parse(raw, now_day=now_day, existing_count=existing_count)
                return self._enrich_with_hybrid(
                    raw, res, now=now, existing_count=existing_count, ui=ui, translation_backend=translation_backend
                )
            except Exception as exc:
                result = self.offline.parse(raw, now_day=now_day, existing_count=existing_count)
                result.setdefault("assumptions", []).append(
                    f"AI Engine unavailable ({type(exc).__name__}); automatically fell back to Offline Deterministic engine."
                )
                return self._enrich_with_hybrid(
                    raw, result, now=now, existing_count=existing_count, ui=ui, translation_backend=translation_backend
                )

        result = self.offline.parse(raw, now_day=now_day, existing_count=existing_count)
        return self._enrich_with_hybrid(
            raw, result, now=now, existing_count=existing_count, ui=ui, translation_backend=translation_backend
        )


_DEFAULT_CONTROLLER = NLParserController()


def parse_natural_language_task(
    prompt: str,
    *,
    now: Optional[str] = None,
    existing_count: int = 0,
    engine: Optional[str] = None,
    ui: Optional[Dict[str, Any]] = None,
    translation_backend: str = "rule",
) -> Dict[str, Any]:
    """
    Public M1 + Hybrid NL Parser entry point used by FastAPI and tests.
    Supports `engine="auto" | "offline" | "ai"`, optional sidebar `ui` controls
    (`priority` in `1=Urgent..4=Low`, `session`, `pacing`, `custom`, `attachments`),
    and `translation_backend` (`"rule"` | `"nllb"` | `"opus_mt"`).
    """
    return _DEFAULT_CONTROLLER.parse(
        prompt,
        now=now,
        existing_count=existing_count,
        engine=engine,
        ui=ui,
        translation_backend=translation_backend,
    )
