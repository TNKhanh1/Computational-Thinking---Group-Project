"""
Online Lightweight Context-Parsing Model Router (Layer 4 NLP — Layer B).

Uses Google Gemini Flash-Lite / Flash with strict structured JSON schema output
(`thinking_budget=0`, `0 MB` local RAM, `~220-550 ms` cloud latency) to distill natural
prompts into crisp titles, bounds, and human thinking summaries, falling back transparently
to the deterministic Clause-Level Condenser when offline or during unit tests.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from smartschedule.nlp.clause_condenser import _clean_conversational_title
from smartschedule.nlp.parser_controller import _load_local_env, genai, genai_types

_ONLINE_CONTEXT_MODELS = (
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-3-flash-preview",
)
_UNAVAILABLE_CONTEXT_MODELS: set[str] = set()


class ChatContextExtractionSchema(BaseModel):
    """Structured JSON schema returned by the online lightweight context-parsing model."""

    intent: Literal["ADD_TASK", "ADD_RECURRING", "MODIFY_HIDDEN", "ADJUST_DEADLINE"] = "ADD_TASK"
    is_single_task: bool = Field(
        default=True,
        description="True when the prompt describes 1 single task with a start bound, deadline bound, and duration.",
    )
    concise_title: str = Field(
        default="",
        description=(
            "Clean, concise 3-7 word Vietnamese/English task title stripped of all time bounds, durations, "
            "and filler words like 'môn', 'học phần', 'cần hoàn thành trong tổng thời gian'. "
            "Example: 'Làm bài tập Computational Thinking'."
        ),
    )
    start_after_day: Optional[str] = Field(default=None, description="Monday..Sunday if start bound is stated.")
    start_after_time: Optional[str] = Field(default=None, description="HH:MM (24h) earliest start time.")
    deadline_day: Optional[str] = Field(default=None, description="Monday..Sunday (or Next Monday) deadline day.")
    deadline_time: Optional[str] = Field(default=None, description="HH:MM (24h) deadline time.")
    duration_min: Optional[int] = Field(default=None, description="Total work duration in minutes (e.g. 2 tiếng -> 120).")
    is_splittable: Optional[bool] = Field(
        default=None,
        description="False when user states 'liên tục', 'liền mạch', or 'không chia nhỏ'; True if 'chia nhỏ'.",
    )
    cognitive_load: Optional[int] = Field(default=None, ge=1, le=3)
    preferred_window: Optional[Literal["MORNING", "AFTERNOON", "EVENING", "ANYTIME"]] = None
    human_thinking_summary_vi: str = Field(
        default="",
        description="1 short natural Vietnamese sentence explaining how context and hidden criteria were parsed.",
    )


def parse_context_with_online_model(
    prompt: str,
    now_day: str,
    api_key_override: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Invoke the online lightweight Gemini context model if available.
    Returns `None` in unit tests (unless `ENABLE_ONLINE_CONTEXT_MODEL_IN_TESTS=1`) or when offline.
    """
    _load_local_env()
    if os.getenv("PYTEST_CURRENT_TEST") and os.getenv("ENABLE_ONLINE_CONTEXT_MODEL_IN_TESTS") != "1":
        return None

    api_key = (api_key_override or os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key or genai is None or genai_types is None:
        return None

    sys_prompt = (
        "You are SmartSchedule's fast context extraction engine for Vietnamese & English student scheduling.\n"
        f"Reference current weekday: {now_day}.\n"
        f'User prompt: "{prompt}"\n\n'
        "Rules:\n"
        "1. Treat the prompt as 1 single task (`is_single_task=true`) when a start bound, deadline bound, and work duration describe one assignment.\n"
        "2. Summarize `concise_title` into a natural 3-7 word action phrase in the prompt's language, stripping ALL dates, times, durations, and filler words like 'môn', 'học phần', 'cần hoàn thành trong tổng thời gian', 'liên tục'. "
        "For example, 'Làm bài tập môn Computational Thinking, từ 19h tối thứ 3, đến 21h tối thứ 5, cần hoàn thành trong tổng thời gian 2 tiếng liên tục' -> concise_title='Làm bài tập Computational Thinking'.\n"
        "3. Map weekdays to Monday..Sunday (thứ 2=Monday, thứ 3=Tuesday, thứ 4=Wednesday, thứ 5=Thursday, thứ 6=Friday, thứ 7=Saturday, chủ nhật=Sunday) and 24h times ('19h tối'->'19:00', '21h tối'->'21:00').\n"
        "4. Set `is_splittable=false` if user specifies 'liên tục', 'liền mạch', 'không chia nhỏ'.\n"
        "5. Provide a 1-sentence Vietnamese `human_thinking_summary_vi` explaining what you understood."
    )

    try:
        client = genai.Client(api_key=api_key)
    except Exception:
        return None

    cfg_kwargs: Dict[str, Any] = {
        "response_mime_type": "application/json",
        "response_schema": ChatContextExtractionSchema,
        "temperature": 0.0,
    }
    if hasattr(genai_types, "ThinkingConfig"):
        cfg_kwargs["thinking_config"] = genai_types.ThinkingConfig(thinking_budget=0)

    try:
        gen_config = genai_types.GenerateContentConfig(**cfg_kwargs)
    except Exception:
        return None

    for model_name in _ONLINE_CONTEXT_MODELS:
        if model_name in _UNAVAILABLE_CONTEXT_MODELS:
            continue
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=sys_prompt,
                config=gen_config,
            )
            parsed = getattr(resp, "parsed", None)
            if parsed is None and getattr(resp, "text", None):
                parsed = ChatContextExtractionSchema.model_validate_json(resp.text)
            if parsed is None:
                continue

            data = parsed.model_dump()
            raw_title = str(data.get("concise_title") or "").strip()
            if raw_title:
                data["concise_title"] = _clean_conversational_title(raw_title) or raw_title
            data["model_used"] = model_name
            return data
        except Exception as exc:
            err_msg = str(exc).lower()
            if "404" in err_msg or "not_found" in err_msg or "no longer available" in err_msg:
                _UNAVAILABLE_CONTEXT_MODELS.add(model_name)
            continue

    return None
