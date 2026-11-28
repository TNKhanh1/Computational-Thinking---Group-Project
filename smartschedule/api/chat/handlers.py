"""
Conversational Scheduling Turn Handlers (`smartschedule.api.chat.handlers`).

Routes user turns cleanly across:
  - MODIFY_HIDDEN (SHA-256 task keyword traceability + hidden parameter tuning)
  - ADJUST_DEADLINE (Deadline update + remaining-time/habit/EWMA buffer recalculation)
  - ADD_RECURRING (Fixed daily/weekly event with multi-turn slot filling)
  - ADD_TASK (Merged Online Context Model + Clause-Level Title Condenser + cross-day bounds)
  - v1.0-alpha M4 grounded router (`nlp/intent_classifier.py` + `api/chat/lifecycle_intents.py`):
    DELETE_ITEM, COMPLETE_TASK, QUERY_SCHEDULE, ADAPT_NEXT_WEEK (M5), BATCH_ADD_TASKS,
    LINK_DEPENDENCY (P10 DAG + cycle guard), attachment cross-check (M7, P14a),
    DISRUPTION_REPAIR (-> M5) and UPDATE_PROFILE_HABIT (-> M3).

Plug-ins owned by other members are imported fault-tolerantly so this router passes its tests
whatever the merge order of `M3` / `M5` / `M7` is.
"""

from __future__ import annotations

import functools
import inspect
import re
import time
from typing import Any, Callable, Dict, List, Optional

from smartschedule.api.chat.edge_cases import (
    analyze_schedule_edge_cases,
    compute_remaining_and_habit_buffer,
)
from smartschedule.api.chat.lifecycle_intents import (
    P10_RULE,
    P14A_RULE,
    ChatTurnContext,
    build_milestone_tasks,
    detect_doc_choice,
    digest_attachments,
    doc_conflict_response,
    find_dependency_cycle,
    cycle_clarification,
    handle_adapt_next_week,
    handle_batch_add_tasks,
    handle_complete_task,
    handle_delete_item,
    handle_link_dependency,
    handle_query_schedule,
    is_doc_underestimate,
)
from smartschedule.api.chat.thinking_stage import build_post_actions, build_thinking_summary
from smartschedule.core.controller import ScheduleController
from smartschedule.core.models import CommitmentsProfile, FixedEvent, ScheduleBlock, Task
from smartschedule.core.storage import load_workspace_state, save_workspace_state
from smartschedule.core.task_tracer import (
    enrich_task_trace_metadata,
    extract_hidden_criteria_updates,
    resolve_target_task_from_prompt,
)
from smartschedule.core.utils import round_up_to_15
from smartschedule.nlp.clause_condenser import (
    _OFFLINE_NL,
    _WEEKDAY_VI_MAP,
    _clean_conversational_title,
    _date_iso_for_weekday,
    _extract_cross_day_window,
    _extract_flexible_duration_min,
    _extract_recurring_days,
    _extract_time_range,
    _infer_fixed_category,
    _resolve_now_weekday,
)
from smartschedule.nlp.context_router import parse_context_with_online_model
from smartschedule.nlp.intent_classifier import IntentResult, classify_intent
from smartschedule.nlp.parser_controller import WEEKDAYS, _strip_accents

# ---------------------------------------------------------------------------
# Fault-tolerant plug-ins (M5 / M7 / M3). Each is optional: when absent the
# router degrades to the v0.9 behaviour instead of failing to import.
# ---------------------------------------------------------------------------
try:  # M5 — conversational LOCAL_INSERTION repair (Pattern P8)
    from smartschedule.api.chat.disruption_chat import (  # type: ignore
        handle_disruption_chat_turn as _m5_disruption_turn,
        is_disruption_intent as _m5_is_disruption,
    )
except ImportError:  # pragma: no cover - exercised only on branches without M5
    _m5_disruption_turn = None
    _m5_is_disruption = None

try:  # M5 — cross-week preference adaptation (Pattern P13)
    from smartschedule.core.cross_week_adapter import adapt_preferences_for_next_week as _m5_adapt  # type: ignore
except ImportError:  # pragma: no cover
    _m5_adapt = None

try:  # M7 — DocumentConstraintDigest (Pattern P14a)
    from smartschedule.nlp.doc_attachment_parser import parse_document_constraint_digest as _m7_parse_doc  # type: ignore
except ImportError:  # pragma: no cover
    _m7_parse_doc = None

try:  # M3 — sleep / chronotype / habit chat
    from smartschedule.api.chat.profile_habit_chat import (  # type: ignore
        handle_profile_or_habit_turn as _m3_profile_turn,
        is_profile_or_habit_intent as _m3_is_profile,
    )
except ImportError:
    _m3_profile_turn = None
    _m3_is_profile = None


def _call_with_supported_kwargs(fn: Callable[..., Any], **kwargs: Any) -> Any:
    """Call `fn` passing only the keyword arguments its signature accepts (merge-order safety)."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return fn(**kwargs)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return fn(**kwargs)
    return fn(**{k: v for k, v in kwargs.items() if k in params})


def _build_thinking_summary_compat(*, pattern_rules: Optional[List[Dict[str, str]]] = None, has_dag: bool = False, **base: Any) -> Dict[str, Any]:
    """M2 may or may not have added `pattern_rules` / `has_dag` yet; inject them afterwards if not."""
    summary = _call_with_supported_kwargs(build_thinking_summary, pattern_rules=pattern_rules, has_dag=has_dag, **base)
    if pattern_rules and not summary.get("pattern_rules"):
        summary["pattern_rules"] = list(pattern_rules)
    return summary


def _normalize_delegated_response(res: Dict[str, Any], fallback_algorithm: str) -> Dict[str, Any]:
    """Keep `thinking_summary.selected_algorithm` a real solver key (UI stores it as `activeSolver`)."""
    ts = res.get("thinking_summary")
    if isinstance(ts, dict):
        sel = str(ts.get("selected_algorithm") or "")
        if sel and sel not in ScheduleController.SOLVER_REGISTRY:
            ts["repair_engine"] = sel
            ts["selected_algorithm"] = fallback_algorithm if fallback_algorithm in ScheduleController.SOLVER_REGISTRY else "SCORED_GREEDY"
    return res


def _detect_intent(
    prompt: str,
    mode_hint: str,
    pending_draft: Optional[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    last_task_id: Optional[str],
    profile: CommitmentsProfile,
) -> str:
    norm = _strip_accents(prompt).lower()
    hint = (mode_hint or "AUTO").strip().upper()
    if pending_draft and pending_draft.get("intent"):
        return str(pending_draft["intent"])
    if hint in ("ADD_RECURRING", "ADD_TASK", "MODIFY_HIDDEN", "ADJUST_DEADLINE"):
        return hint

    deadline_adj_cue = bool(
        re.search(
            r"\b(?:doi|chuyen|gia\s*han|lui|cap\s*nhat|sua)\b.*\b(?:deadline|han\s*chot|han\s*nop|han)\b"
            r"|\b(?:deadline|han\s*chot|han\s*nop)\b.*\b(?:sang|thanh|ve|den|toi)\b"
            r"|\b(?:con\s*lai|lam\s*tiep|uoc\s*luong|estimate|moi\s*lam\s*duoc)\b",
            norm,
        )
    )
    if deadline_adj_cue and tasks:
        return "ADJUST_DEADLINE"

    recurring_cue = bool(
        re.search(
            r"\b(?:hang\s*ngay|moi\s*ngay|lap\s*lai|hang\s*tuan|moi\s*tuan|co\s*dinh|"
            r"thoi\s*khoa\s*bieu|lich\s*hoc|lop\s*hoc|di\s*lam\s*them|bua\s*an|daily|weekly)\b",
            norm,
        )
    )
    if recurring_cue:
        return "ADD_RECURRING"

    now_day = _resolve_now_weekday(profile)
    has_cross_window = _extract_cross_day_window(norm, now_day) is not None
    dur_val, dur_inferred = _extract_flexible_duration_min(norm)
    has_explicit_dur = not dur_inferred and dur_val is not None
    has_add_verb = bool(re.match(r"^\s*(?:them|tao|add|create|len\s*lich|lam|hoc|on|viet|code|doc|chuan\s*bi|nop)\b", norm))
    has_modify_verb = bool(re.search(r"\b(?:sua|chinh|cap\s*nhat|dieu\s*chinh|tach|chia\s*nho|gop|nang\s*qua|qua\s*nang)\b", norm))

    if (has_cross_window or has_explicit_dur) and not has_modify_verb:
        return "ADD_TASK"

    trace = resolve_target_task_from_prompt(prompt, tasks, last_task_id=last_task_id)
    hidden = extract_hidden_criteria_updates(prompt, focus_preference=profile.focus_preference)
    if trace["matched"] and trace["confidence"] >= 0.60 and (hidden["has_hidden_updates"] or has_modify_verb) and not (has_add_verb and has_explicit_dur):
        return "MODIFY_HIDDEN"

    return "ADD_TASK"


def _finalize_solve_and_package(
    *,
    intent: str,
    profile: CommitmentsProfile,
    tasks_raw: List[Dict[str, Any]],
    pinned_raw: List[Dict[str, Any]],
    completed_blocks: Dict[str, Any],
    algorithm: str,
    workspace_id: str,
    auto_save: bool,
    mutated_task_id: Optional[str],
    context_note_vi: str,
    reply_vi: str,
    t0: float,
    traced_task: Optional[Dict[str, Any]] = None,
    remaining_estimation: Optional[Dict[str, Any]] = None,
    pattern_rules: Optional[List[Dict[str, str]]] = None,
    has_dag: bool = False,
    quick_chips: Optional[List[Dict[str, str]]] = None,
    extra_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    task_models = [Task.model_validate(t) for t in tasks_raw]
    pinned_models = [ScheduleBlock.model_validate(pb) for pb in pinned_raw]

    dominant_subset = ("SCORED_GREEDY", "HYBRID_ALNS", "BACKTRACK")
    eff_algo = algorithm if algorithm in dominant_subset else "SCORED_GREEDY"
    escalated = False

    out, _ = ScheduleController.solve_schedule(
        profile=profile,
        tasks=task_models,
        algorithm=eff_algo,
        pinned_blocks=pinned_models,
    )
    if eff_algo == "SCORED_GREEDY" and out.summary.tasks_unplaced > 0 and "HYBRID_ALNS" in ScheduleController.SOLVER_REGISTRY:
        alns_out, _ = ScheduleController.solve_schedule(
            profile=profile,
            tasks=task_models,
            algorithm="HYBRID_ALNS",
            pinned_blocks=pinned_models,
        )
        if alns_out.summary.tasks_unplaced < out.summary.tasks_unplaced:
            out = alns_out
            eff_algo = "HYBRID_ALNS"
            escalated = True

    insights = ScheduleController.compute_schedule_insights(profile, out)
    sched_dict = out.model_dump()
    sched_dict["unplaced"] = sched_dict["unplaced_tasks"]
    b_energies = insights.get("block_energies", {})
    for blk in sched_dict.get("blocks", []):
        blk["energy_level"] = b_energies.get(blk.get("block_id"))
    sched_dict["metrics"] = {
        "hard_violations": out.summary.hard_constraint_violations,
        "deadline_rate": round(out.summary.deadline_satisfaction_rate / 100.0, 4),
        "deadline_satisfaction_pct": out.summary.deadline_satisfaction_rate,
        "exec_ms": out.execution_time_ms,
        "free_slots": out.summary.free_slots_remaining,
        "rest_slots": out.summary.rest_slots,
        "fragmentation_index": out.summary.fragmentation_index,
        "experience_rating": out.summary.experience_rating,
        "experience_label": out.summary.experience_label,
        "crunch_tier_used": out.summary.crunch_tier_used,
        "peak_match_rate_pct": insights.get("peak_match_rate_pct", 100.0),
        "deep_peak_match_pct": insights.get("deep_peak_match_pct", 100.0),
        "avg_energy_level": insights.get("avg_energy_level", 0.0),
        "context_switches": insights.get("context_switches", 0),
        "batched_pairs": insights.get("batched_pairs", 0),
    }

    if mutated_task_id:
        placed_for_task = [b for b in out.blocks if b.task_id == mutated_task_id]
        if placed_for_task:
            slots_txt = ", ".join(
                f"**{b.start_time} – {b.end_time} {_WEEKDAY_VI_MAP.get(b.day, b.day)}**"
                for b in placed_for_task
            )
            reply_vi = f"{reply_vi} Mình đã xếp vào khung giờ: {slots_txt}."

    edge_case = analyze_schedule_edge_cases(profile, out, task_models)
    comm_dict = profile.model_dump(mode="json")

    if auto_save:
        save_workspace_state(
            {
                "suiteLabel": "Lịch trình của bạn",
                "commitments": comm_dict,
                "tasks": tasks_raw,
                "pinnedBlocks": pinned_raw,
                "completedBlocks": completed_blocks,
                "activeSolver": eff_algo,
            },
            workspace_id=workspace_id,
        )

    total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    thinking_summary = _build_thinking_summary_compat(
        intent=intent,
        context_note_vi=context_note_vi,
        chosen_solver=eff_algo,
        escalated_from_greedy=escalated,
        exec_ms=float(out.execution_time_ms or total_ms),
        peak_match_pct=float(insights.get("peak_match_rate_pct", 100.0)),
        tasks_placed=int(out.summary.tasks_placed),
        tasks_total=int(out.summary.total_tasks_requested),
        pattern_rules=pattern_rules,
        has_dag=has_dag,
    )

    response = {
        "status": "APPLIED",
        "intent": intent,
        "finalized": edge_case is None or edge_case.get("type") != "DEADLOCK",
        "finalized_message_vi": (
            "⚠️ Lịch trình đang bị kẹt — hãy chọn một hướng gỡ rối bên dưới."
            if edge_case and edge_case.get("type") == "DEADLOCK"
            else "✅ Đã hoàn tất và chốt lịch trình mới!"
        ),
        "reply_vi": reply_vi,
        "thinking_summary": thinking_summary,
        "pending_draft": None,
        "missing_fields": [],
        "quick_chips": list(quick_chips or []),
        "mutated_task_id": mutated_task_id,
        "traced_task": traced_task,
        "remaining_estimation": remaining_estimation,
        "edge_case": edge_case,
        "post_actions": build_post_actions(mutated_task_id),
        "updated_commitments": comm_dict,
        "updated_tasks": tasks_raw,
        "updated_pinned_blocks": pinned_raw,
        "schedule": sched_dict,
        "execution_time_ms": total_ms,
    }
    if extra_fields:
        response.update(extra_fields)
    return response


def process_chat_turn(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a single conversational scheduling turn cleanly in < 10s SLA."""
    t0 = time.perf_counter()
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Prompt cannot be empty.")

    workspace_id = str(payload.get("workspace_id") or "default").strip() or "default"
    auto_save = bool(payload.get("auto_save", True))
    mode_hint = str(payload.get("mode_hint") or "AUTO").strip().upper()
    algorithm = str(payload.get("algorithm") or "SCORED_GREEDY").strip().upper()
    last_task_id = payload.get("last_task_id")
    pending_draft = payload.get("pending_draft") if isinstance(payload.get("pending_draft"), dict) else None

    saved_record = load_workspace_state(workspace_id) if (payload.get("commitments") is None or payload.get("tasks") is None) else None
    saved_state = (saved_record or {}).get("state") or {}

    comm_raw = payload.get("commitments") if isinstance(payload.get("commitments"), dict) else saved_state.get("commitments")
    if not isinstance(comm_raw, dict):
        comm_raw = {
            "student_id": "STUDENT_01",
            "planning_week_start": "2026-11-02T00:00:00+07:00",
            "now": "2026-11-02T08:00:00+07:00",
            "sleep_schedule": {"daily_start_time": "23:30", "daily_end_time": "06:30", "is_hard_lock": True},
            "fixed_events": [],
            "buffer_mode": "COGNITIVE_LOAD",
            "focus_preference": "BALANCED",
            "horizon_days": 7,
        }

    tasks_raw: List[Dict[str, Any]] = [
        enrich_task_trace_metadata(t)
        for t in (payload.get("tasks") if isinstance(payload.get("tasks"), list) else (saved_state.get("tasks") or []))
        if isinstance(t, dict)
    ]
    pinned_raw = payload.get("pinned_blocks") if isinstance(payload.get("pinned_blocks"), list) else (saved_state.get("pinnedBlocks") or [])
    completed_blocks = payload.get("completed_blocks") if isinstance(payload.get("completed_blocks"), dict) else (saved_state.get("completedBlocks") or {})

    profile = CommitmentsProfile.model_validate(comm_raw)
    now_day = _resolve_now_weekday(profile)
    norm_prompt = _strip_accents(prompt).lower()

    if pending_draft and re.match(r"^\s*(?:huy|thoi|bo\s*qua|cancel|lam\s*lai)\s*$", norm_prompt):
        return {
            "status": "CANCELLED",
            "intent": "CANCELLED",
            "reply_vi": "Đã hủy thao tác đang dở. Bạn có thể nhập yêu cầu mới bất cứ lúc nào.",
            "pending_draft": None,
            "missing_fields": [],
            "quick_chips": [],
            "post_actions": build_post_actions(),
            "updated_commitments": profile.model_dump(mode="json"),
            "updated_tasks": tasks_raw,
            "updated_pinned_blocks": pinned_raw,
            "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }

    routing: IntentResult = classify_intent(
        prompt,
        mode_hint=mode_hint,
        pending_draft=pending_draft,
        tasks=tasks_raw,
        last_task_id=last_task_id,
        legacy_detector=lambda: _detect_intent(prompt, "AUTO", None, tasks_raw, last_task_id, profile),
        disruption_detector=(lambda p: bool(_m5_is_disruption(p))) if _m5_is_disruption else None,
        profile_detector=(lambda p: bool(_m3_is_profile(p))) if _m3_is_profile else None,
    )
    intent = routing.intent

    if intent in ("QUERY_SCHEDULE", "ADAPT_NEXT_WEEK") and not saved_state:
        try:
            saved_state = (load_workspace_state(workspace_id) or {}).get("state") or {}
        except Exception:
            saved_state = {}

    ctx = ChatTurnContext(
        prompt=prompt,
        profile=profile,
        tasks_raw=tasks_raw,
        pinned_raw=pinned_raw,
        completed_blocks=completed_blocks,
        algorithm=algorithm,
        workspace_id=workspace_id,
        auto_save=auto_save,
        now_day=now_day,
        t0=t0,
        last_task_id=last_task_id,
        pending_draft=pending_draft,
        payload=payload,
        saved_state=saved_state,
    )
    finalize = functools.partial(
        _finalize_solve_and_package,
        algorithm=algorithm,
        workspace_id=workspace_id,
        auto_save=auto_save,
        t0=t0,
    )

    if intent == "DISRUPTION_REPAIR":
        if _m5_disruption_turn is not None:
            delegated = dict(payload)
            delegated["workspace_id"] = workspace_id
            delegated.setdefault("commitments", profile.model_dump(mode="json"))
            delegated.setdefault("tasks", tasks_raw)
            return _normalize_delegated_response(_m5_disruption_turn(delegated), algorithm)
        intent = _detect_intent(prompt, "AUTO", None, tasks_raw, last_task_id, profile)
    if intent == "UPDATE_PROFILE_HABIT":
        if _m3_profile_turn is not None:
            return _normalize_delegated_response(
                _call_with_supported_kwargs(
                    _m3_profile_turn,
                    prompt=prompt,
                    profile=profile,
                    tasks_raw=tasks_raw,
                    pinned_raw=pinned_raw,
                    completed_blocks=completed_blocks,
                    algorithm=algorithm,
                    workspace_id=workspace_id,
                    auto_save=auto_save,
                ),
                algorithm,
            )
        intent = _detect_intent(prompt, "AUTO", None, tasks_raw, last_task_id, profile)
    if intent == "DELETE_ITEM":
        return handle_delete_item(ctx, finalize)
    if intent == "COMPLETE_TASK":
        return handle_complete_task(ctx, finalize)
    if intent == "QUERY_SCHEDULE":
        return handle_query_schedule(ctx)
    if intent == "ADAPT_NEXT_WEEK":
        return handle_adapt_next_week(
            ctx,
            finalize,
            (lambda prof, tks, logs: _m5_adapt(prof, tks, logs)) if _m5_adapt else None,
        )
    if intent == "LINK_DEPENDENCY":
        return handle_link_dependency(ctx, finalize, routing)
    if intent == "BATCH_ADD_TASKS":
        return handle_batch_add_tasks(ctx, finalize, routing)

    if intent == "MODIFY_HIDDEN":
        trace = resolve_target_task_from_prompt(prompt, tasks_raw, last_task_id=last_task_id)
        if not trace["matched"]:
            cands = trace.get("candidates") or []
            chips = [
                {
                    "label": f"📌 {c['title']}",
                    "prompt": f"[trace:{str(c.get('trace_hash') or '')[:8]}] {prompt}",
                }
                for c in cands
                if c.get("title")
            ]
            return {
                "status": "NEEDS_CLARIFICATION",
                "intent": "MODIFY_HIDDEN",
                "reply_vi": (
                    "Mình chưa xác định chắc chắn bạn muốn điều chỉnh công việc nào. "
                    "Bạn bấm chọn đúng công việc bên dưới nhé:"
                ),
                "pending_draft": {"intent": "MODIFY_HIDDEN", "original_prompt": prompt},
                "missing_fields": ["target_task"],
                "quick_chips": chips,
                "post_actions": build_post_actions(),
                "updated_commitments": profile.model_dump(mode="json"),
                "updated_tasks": tasks_raw,
                "updated_pinned_blocks": pinned_raw,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

        target_id = trace["task_id"]
        hidden_info = extract_hidden_criteria_updates(prompt, focus_preference=profile.focus_preference)
        if not hidden_info["has_hidden_updates"]:
            return {
                "status": "NEEDS_CLARIFICATION",
                "intent": "MODIFY_HIDDEN",
                "reply_vi": (
                    f"Mình đã tìm thấy công việc **{trace['task']['title']}**. "
                    "Bạn muốn điều chỉnh tiêu chí nào cho việc này?"
                ),
                "pending_draft": {
                    "intent": "MODIFY_HIDDEN",
                    "target_task_id": target_id,
                    "trace_hash": trace["trace_hash"],
                },
                "missing_fields": ["hidden_criteria"],
                "quick_chips": [
                    {"label": "🧠 Việc nặng — thêm trừ hao & xếp giờ tỉnh táo", "prompt": f"[trace:{trace['trace_hash'][:8]}] Việc này nặng quá, xếp giờ tỉnh táo nhất và thêm buffer"},
                    {"label": "🧩 Chia nhỏ nhiều buổi ngắn", "prompt": f"[trace:{trace['trace_hash'][:8]}] Chia nhỏ ra nhiều buổi ngắn"},
                    {"label": "🔒 Không chia nhỏ, làm liền 1 mạch", "prompt": f"[trace:{trace['trace_hash'][:8]}] Không chia nhỏ, làm liền 1 mạch"},
                    {"label": "🌅 Chuyển sang buổi sáng", "prompt": f"[trace:{trace['trace_hash'][:8]}] Chuyển sang buổi sáng"},
                ],
                "post_actions": build_post_actions(),
                "traced_task": trace,
                "updated_commitments": profile.model_dump(mode="json"),
                "updated_tasks": tasks_raw,
                "updated_pinned_blocks": pinned_raw,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

        mutated_task = None
        for idx, t in enumerate(tasks_raw):
            if t.get("task_id") == target_id:
                updated = dict(t)
                for k, v in hidden_info["updates"].items():
                    updated[k] = v
                if hidden_info["updates"].get("is_splittable") is False:
                    updated["min_chunk_min"] = max(15, int(updated.get("duration_min") or 60))
                    updated["max_chunk_min"] = updated["min_chunk_min"]
                updated = enrich_task_trace_metadata(updated)
                tasks_raw[idx] = updated
                mutated_task = updated
                break

        pinned_raw = [p for p in pinned_raw if p.get("task_id") != target_id]
        context_note = (
            f"Truy vết công việc đã lưu **{mutated_task['title']}** (SHA-256 `#{mutated_task['trace_hash'][:8]}`) "
            f"và điều chỉnh tiêu chí ẩn: {'; '.join(hidden_info['summary_vi'])}."
        )
        return _finalize_solve_and_package(
            intent="MODIFY_HIDDEN",
            profile=profile,
            tasks_raw=tasks_raw,
            pinned_raw=pinned_raw,
            completed_blocks=completed_blocks,
            algorithm=algorithm,
            workspace_id=workspace_id,
            auto_save=auto_save,
            mutated_task_id=target_id,
            context_note_vi=context_note,
            reply_vi=(
                f"Đã cập nhật **{mutated_task['title']}** ({'; '.join(hidden_info['summary_vi'])}) "
                "và sắp xếp lại lịch trình cho bạn."
            ),
            traced_task={
                "task_id": target_id,
                "title": mutated_task["title"],
                "trace_hash": mutated_task["trace_hash"],
                "matched_keywords": trace.get("matched_keywords", []),
                "hidden_updates": hidden_info["updates"],
                "summary_vi": hidden_info["summary_vi"],
            },
            t0=t0,
        )

    if intent == "ADJUST_DEADLINE":
        trace = resolve_target_task_from_prompt(prompt, tasks_raw, last_task_id=last_task_id)
        if not trace["matched"]:
            cands = trace.get("candidates") or []
            return {
                "status": "NEEDS_CLARIFICATION",
                "intent": "ADJUST_DEADLINE",
                "reply_vi": "Bạn muốn đổi hạn chót và tính lại thời gian làm tiếp cho công việc nào?",
                "pending_draft": {"intent": "ADJUST_DEADLINE", "original_prompt": prompt},
                "missing_fields": ["target_task"],
                "quick_chips": [
                    {"label": f"📌 {c['title']}", "prompt": f"[trace:{str(c.get('trace_hash') or '')[:8]}] {prompt}"}
                    for c in cands
                    if c.get("title")
                ],
                "post_actions": build_post_actions(),
                "updated_commitments": profile.model_dump(mode="json"),
                "updated_tasks": tasks_raw,
                "updated_pinned_blocks": pinned_raw,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

        target_id = trace["task_id"]
        new_dl_day, day_inferred = _OFFLINE_NL.extract_deadline_day(norm_prompt, now_day)
        new_dl_time, time_inferred, _, _ = _OFFLINE_NL.extract_clock_time(norm_prompt)

        mutated_task = None
        rem_info: Optional[Dict[str, Any]] = None
        for idx, t in enumerate(tasks_raw):
            if t.get("task_id") == target_id:
                updated = dict(t)
                rem_info = compute_remaining_and_habit_buffer(
                    prompt=prompt,
                    task_dict=updated,
                    profile=profile,
                    completed_blocks=completed_blocks,
                    workspace_id=workspace_id,
                )
                updated["duration_min"] = rem_info["remaining_raw_min"]
                updated["buffer_mode"] = "COGNITIVE_LOAD"
                updated["buffer_multiplier"] = rem_info["applied_alpha"]
                updated["alpha_light"] = rem_info["applied_alpha"]
                updated["alpha_heavy"] = rem_info["applied_alpha"]
                if not day_inferred and new_dl_day:
                    updated["deadline_day"] = new_dl_day
                    updated["due"] = None
                if not time_inferred and new_dl_time:
                    updated["deadline_time"] = new_dl_time
                    updated["due"] = None
                updated = enrich_task_trace_metadata(updated)
                tasks_raw[idx] = updated
                mutated_task = updated
                break

        pinned_raw = [p for p in pinned_raw if p.get("task_id") != target_id]
        dl_vi = _WEEKDAY_VI_MAP.get(str(mutated_task.get("deadline_day") or ""), str(mutated_task.get("deadline_day") or "linh hoạt"))
        dl_time_str = mutated_task.get("deadline_time") or "23:59"
        context_note = (
            f"Cập nhật hạn chót cho **{mutated_task['title']}** (SHA-256 `#{mutated_task['trace_hash'][:8]}`) "
            f"sang `{dl_time_str} {dl_vi}` · Thời lượng còn lại `{rem_info['remaining_raw_min']}p` -> dự phòng `{rem_info['buffered_duration_min']}p` (×{rem_info['applied_alpha']:.2f})."
        )

        return _finalize_solve_and_package(
            intent="ADJUST_DEADLINE",
            profile=profile,
            tasks_raw=tasks_raw,
            pinned_raw=pinned_raw,
            completed_blocks=completed_blocks,
            algorithm=algorithm,
            workspace_id=workspace_id,
            auto_save=auto_save,
            mutated_task_id=target_id,
            context_note_vi=context_note,
            reply_vi=(
                f"Đã cập nhật hạn chót mới cho **{mutated_task['title']}** sang **{dl_time_str} {dl_vi}**. "
                f"{rem_info['explanation_vi']}"
            ),
            remaining_estimation=rem_info,
            traced_task={
                "task_id": target_id,
                "title": mutated_task["title"],
                "trace_hash": mutated_task["trace_hash"],
                "matched_keywords": trace.get("matched_keywords", []),
            },
            t0=t0,
        )

    if intent == "ADD_RECURRING":
        draft = dict(pending_draft or {"intent": "ADD_RECURRING"})
        s_time, e_time = _extract_time_range(norm_prompt)
        days_parsed = _extract_recurring_days(norm_prompt)
        title_parsed = _clean_conversational_title(prompt)

        if title_parsed and not draft.get("title"):
            draft["title"] = title_parsed
        if s_time and e_time:
            draft["start_time"] = s_time
            draft["end_time"] = e_time
        if days_parsed is not None:
            draft["day_of_week"] = days_parsed
        if not draft.get("category"):
            draft["category"] = _infer_fixed_category(norm_prompt)

        missing: List[str] = []
        if not draft.get("title"):
            missing.append("title")
        if not draft.get("start_time") or not draft.get("end_time"):
            missing.append("time_range")

        if missing:
            if "title" in missing and "time_range" in missing:
                q_vi = "Bạn muốn thêm lịch lặp lại với **nội dung gì** và trong khung **giờ bắt đầu – giờ kết thúc** nào?"
                chips = [
                    {"label": "🍳 Ăn sáng 07:00 – 07:30 hằng ngày", "prompt": "Ăn sáng từ 07:00 đến 07:30 hằng ngày"},
                    {"label": "🏃 Tập thể dục 17:30 – 18:30 hằng ngày", "prompt": "Tập thể dục từ 17:30 đến 18:30 hằng ngày"},
                    {"label": "🏫 Học trên trường 07:30 – 11:00 Thứ 2, 4", "prompt": "Học trên trường từ 07:30 đến 11:00 thứ 2 và thứ 4"},
                ]
            elif "time_range" in missing:
                q_vi = f"Với lịch lặp **{draft['title']}**, bạn cần **thời gian bắt đầu và kết thúc** từ mấy giờ đến mấy giờ?"
                chips = [
                    {"label": "🌅 07:30 – 09:30", "prompt": "từ 07:30 đến 09:30"},
                    {"label": "☀️ 13:30 – 15:30", "prompt": "từ 13:30 đến 15:30"},
                    {"label": "🌆 18:00 – 19:00", "prompt": "từ 18:00 đến 19:00"},
                    {"label": "🌙 20:00 – 21:30", "prompt": "từ 20:00 đến 21:30"},
                ]
            else:
                q_vi = f"Trong khung giờ **{draft['start_time']} – {draft['end_time']}**, nội dung công việc / lịch lặp là gì?"
                chips = [
                    {"label": "🏫 Lịch học trên lớp", "prompt": "Học trên lớp"},
                    {"label": "💼 Làm thêm", "prompt": "Đi làm thêm"},
                    {"label": "🏃 Tập thể dục", "prompt": "Tập thể dục"},
                ]

            return {
                "status": "NEEDS_CLARIFICATION",
                "intent": "ADD_RECURRING",
                "reply_vi": q_vi,
                "pending_draft": draft,
                "missing_fields": missing,
                "quick_chips": chips,
                "post_actions": build_post_actions(),
                "updated_commitments": profile.model_dump(mode="json"),
                "updated_tasks": tasks_raw,
                "updated_pinned_blocks": pinned_raw,
                "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            }

        day_val = draft.get("day_of_week") or "ALL"
        new_event = FixedEvent(
            event_id=f"FE_CHAT_{int(time.time() * 1000) % 100000}",
            title=str(draft["title"]),
            day_of_week=day_val,
            start_time=str(draft["start_time"]),
            end_time=str(draft["end_time"]),
            category=str(draft.get("category") or "ACADEMIC_CLASS"),
        )
        comm_updated = profile.model_dump(mode="json")
        comm_updated.setdefault("fixed_events", []).append(new_event.model_dump(mode="json"))
        profile = CommitmentsProfile.model_validate(comm_updated)
        day_desc = "hằng ngày" if day_val == "ALL" else (
            ", ".join(_WEEKDAY_VI_MAP.get(d, d) for d in day_val) if isinstance(day_val, list) else _WEEKDAY_VI_MAP.get(str(day_val), str(day_val))
        )
        context_note = (
            f"Nhận diện 1 lịch cố định lặp lại: **{new_event.title}** · Khung giờ `{new_event.start_time} – {new_event.end_time}` ({day_desc})."
        )
        return _finalize_solve_and_package(
            intent="ADD_RECURRING",
            profile=profile,
            tasks_raw=tasks_raw,
            pinned_raw=pinned_raw,
            completed_blocks=completed_blocks,
            algorithm=algorithm,
            workspace_id=workspace_id,
            auto_save=auto_save,
            mutated_task_id=None,
            context_note_vi=context_note,
            reply_vi=(
                f"Đã thêm lịch lặp **{new_event.title}** ({new_event.start_time} – {new_event.end_time}, {day_desc}) "
                "và cập nhật lại lịch tuần cho bạn."
            ),
            t0=t0,
        )

    # ADD_TASK (Merged Online Context Model + Clause-Level Title Condenser)
    draft = dict(pending_draft or {"intent": "ADD_TASK"})
    draft["intent"] = "ADD_TASK"

    # (P14a) Resume a USER_VS_DOC_UNDERESTIMATE clarification
    resume_keep = False
    if draft.get("doc_conflict"):
        choice = detect_doc_choice(norm_prompt)
        digest_saved = draft.get("attachment_digest") or {}
        if choice == "USE_DOC" and digest_saved:
            ms_tasks, created_ids = build_milestone_tasks(tasks_raw, draft, digest_saved, now_day)
            return finalize(
                intent="ADD_TASK",
                profile=profile,
                tasks_raw=ms_tasks,
                pinned_raw=pinned_raw,
                completed_blocks=completed_blocks,
                mutated_task_id=created_ids[-1] if created_ids else None,
                context_note_vi=(
                    f"Biên dịch đề bài `{digest_saved.get('filename')}` thành `{len(created_ids)}` mốc "
                    f"(tổng `{digest_saved.get('suggested_total_min')}p`) và nối `depends_on` theo thứ tự (P14a + P10)."
                ),
                reply_vi=(
                    f"Đã tạo `{len(created_ids)}` phần việc theo đề bài cho **{draft.get('title')}** "
                    f"(tổng khoảng {digest_saved.get('suggested_total_min')} phút)."
                ),
                pattern_rules=[P14A_RULE, P10_RULE],
                has_dag=True,
                extra_fields={"created_task_ids": created_ids},
            )
        if choice == "KEEP_USER":
            resume_keep = True
            draft.pop("doc_conflict", None)
            draft.pop("attachment_digest", None)
            draft["doc_checked"] = True
        else:
            return doc_conflict_response(ctx, draft, digest_saved, int(draft.get("duration_min") or 0))

    # (P10) Parse only the dependent clause when the prompt names an existing prerequisite
    parse_prompt = prompt
    if routing.prerequisite is not None and routing.prerequisite_task_id:
        parse_prompt = routing.prerequisite.dependent_text
        deps_now = [str(d) for d in (draft.get("depends_on") or [])]
        if routing.prerequisite_task_id not in deps_now:
            deps_now.append(str(routing.prerequisite_task_id))
        draft["depends_on"] = deps_now
    if resume_keep:
        parse_prompt = ""
    parse_norm = _strip_accents(parse_prompt).lower()

    cross_win = _extract_cross_day_window(parse_norm, now_day)
    s_time, e_time = (None, None) if cross_win else _extract_time_range(parse_norm)
    dur_min, dur_inferred = _extract_flexible_duration_min(parse_norm)
    dl_day, day_inferred = _OFFLINE_NL.extract_deadline_day(parse_norm, now_day)
    dl_time, time_inferred, _, _ = _OFFLINE_NL.extract_clock_time(parse_norm)
    title_parsed = _clean_conversational_title(parse_prompt) if parse_prompt else ""
    cat, prio, cog_load = _OFFLINE_NL.extract_category_priority_load(parse_prompt.lower(), parse_norm)
    hidden = (
        extract_hidden_criteria_updates(parse_prompt, focus_preference=profile.focus_preference)
        if parse_prompt
        else {"has_hidden_updates": False, "updates": {}, "summary_vi": []}
    )

    online_ctx = (
        parse_context_with_online_model(
            parse_prompt,
            now_day,
            api_key_override=str(payload.get("gemini_api_key") or "").strip() or None,
        )
        if not pending_draft and parse_prompt
        else None
    )
    if online_ctx and online_ctx.get("prerequisite_hint") and not draft.get("depends_on"):
        hint_trace = resolve_target_task_from_prompt(str(online_ctx["prerequisite_hint"]), tasks_raw)
        if hint_trace.get("matched") and float(hint_trace.get("confidence") or 0.0) >= 0.60:
            draft["depends_on"] = [str(hint_trace["task_id"])]

    if online_ctx:
        if online_ctx.get("concise_title"):
            title_parsed = str(online_ctx["concise_title"]).strip()
        if dur_inferred and online_ctx.get("duration_min"):
            dur_min = int(online_ctx["duration_min"])
            dur_inferred = False
        if day_inferred and online_ctx.get("deadline_day") in WEEKDAYS:
            dl_day = str(online_ctx["deadline_day"])
            day_inferred = False
        if time_inferred and online_ctx.get("deadline_time"):
            dl_time = str(online_ctx["deadline_time"])
            time_inferred = False
        if not cross_win and online_ctx.get("start_after_day") in WEEKDAYS:
            draft["start_after_day"] = str(online_ctx["start_after_day"])
            if online_ctx.get("start_after_time"):
                draft["start_after_time"] = str(online_ctx["start_after_time"])
        if "is_splittable" not in hidden["updates"] and online_ctx.get("is_splittable") is not None:
            draft["is_splittable"] = bool(online_ctx["is_splittable"])
            if not draft["is_splittable"]:
                draft["work_rhythm"] = "FLOW"
        if "cognitive_load" not in hidden["updates"] and online_ctx.get("cognitive_load"):
            cog_load = int(online_ctx["cognitive_load"])
        if "preferred_window" not in hidden["updates"] and online_ctx.get("preferred_window"):
            draft["preferred_window"] = str(online_ctx["preferred_window"])

    if title_parsed and ((online_ctx and online_ctx.get("concise_title")) or not draft.get("title")):
        draft["title"] = title_parsed

    if cross_win:
        draft["start_after_day"] = cross_win["start_day"]
        draft["start_after_time"] = cross_win["start_time"]
        draft["deadline_day"] = cross_win["end_day"]
        draft["deadline_time"] = cross_win["end_time"]
        if not dur_inferred and dur_min is not None:
            draft["duration_min"] = round_up_to_15(dur_min)
            draft["has_time_bounds"] = True
        elif cross_win["start_day"] == cross_win["end_day"]:
            sh, sm = map(int, cross_win["start_time"].split(":"))
            eh, em = map(int, cross_win["end_time"].split(":"))
            if (eh * 60 + em) > (sh * 60 + sm):
                draft["start_time"] = cross_win["start_time"]
                draft["end_time"] = cross_win["end_time"]
                draft["duration_min"] = max(15, round_up_to_15((eh * 60 + em) - (sh * 60 + sm)))
                draft["has_time_bounds"] = True
    elif s_time and e_time:
        draft["start_time"] = s_time
        draft["end_time"] = e_time
        sh, sm = map(int, s_time.split(":"))
        eh, em = map(int, e_time.split(":"))
        draft["duration_min"] = max(15, round_up_to_15((eh * 60 + em) - (sh * 60 + sm)))
        draft["deadline_time"] = e_time
        draft["has_time_bounds"] = True
    elif not dur_inferred and dur_min is not None:
        draft["duration_min"] = round_up_to_15(dur_min)
        draft["has_time_bounds"] = True

    if not cross_win:
        if not day_inferred and dl_day:
            draft["deadline_day"] = dl_day
        if not time_inferred and dl_time and not (s_time and e_time):
            draft["deadline_time"] = dl_time
        if parse_prompt and parse_prompt != prompt and not draft.get("deadline_day"):
            # "Làm B sau khi xong A trước thứ 6": the deadline sits inside the prerequisite clause
            full_day, full_day_inf = _OFFLINE_NL.extract_deadline_day(norm_prompt, now_day)
            if not full_day_inf and full_day:
                draft["deadline_day"] = full_day

    draft.setdefault("category", cat)
    draft.setdefault("priority", prio)
    draft.setdefault("cognitive_load", cog_load)
    for k, v in hidden["updates"].items():
        draft[k] = v

    # (P14a) Cross-check the typed duration against an attached assignment spec (M7 digest)
    if not draft.get("doc_checked") and payload.get("attachments"):
        digest = digest_attachments(payload.get("attachments"), _m7_parse_doc)
        if digest:
            draft["doc_checked"] = True
            user_min = int(draft["duration_min"]) if draft.get("has_time_bounds") and draft.get("duration_min") else None
            if user_min is None:
                draft["duration_min"] = int(digest["suggested_total_min"])
                draft["priority"] = max(int(draft.get("priority") or 3), int(digest["suggested_priority"]))
                draft["cognitive_load"] = max(int(draft.get("cognitive_load") or 2), int(digest["suggested_load"]))
                draft["doc_autofilled_from"] = digest["filename"]
            elif is_doc_underestimate(user_min, digest):
                draft.setdefault("title", title_parsed or digest["filename"])
                return doc_conflict_response(ctx, draft, digest, user_min)

    missing = []
    if not draft.get("title"):
        missing.append("title")
    has_explicit_window = bool(draft.get("start_time") and draft.get("end_time"))
    has_duration_and_deadline = bool(draft.get("duration_min") and draft.get("deadline_day"))
    if not has_explicit_window and not has_duration_and_deadline:
        if not draft.get("duration_min"):
            missing.append("time_range")
        if not draft.get("deadline_day") and not has_explicit_window:
            missing.append("deadline_day")

    if missing:
        if "title" in missing and ("time_range" in missing or "deadline_day" in missing):
            q_vi = "Bạn muốn thêm **công việc gì**, và cần làm **từ mấy giờ đến mấy giờ** (hoặc mất khoảng bao lâu, hạn ngày nào)?"
            chips = [
                {"label": "📝 Làm bài tập Giải tích 90p trước Thứ 6", "prompt": "Làm bài tập Giải tích 90 phút trước Thứ 6"},
                {"label": "📊 Chuẩn bị slide từ 14:00 – 16:00 Thứ 5", "prompt": "Chuẩn bị slide từ 14:00 đến 16:00 Thứ 5"},
            ]
        elif "title" in missing:
            time_desc = (
                f"{draft['start_time']} – {draft['end_time']}"
                if has_explicit_window
                else f"{draft.get('duration_min', 60)} phút"
            )
            q_vi = f"Bạn muốn làm **nội dung công việc gì** cho khung thời gian {time_desc} này?"
            chips = [
                {"label": "📚 Ôn tập bài giảng", "prompt": "Ôn tập bài giảng"},
                {"label": "💻 Code bài thực hành", "prompt": "Code bài thực hành"},
                {"label": "📝 Viết báo cáo", "prompt": "Viết báo cáo"},
            ]
        elif "time_range" in missing and "deadline_day" in missing:
            q_vi = (
                f"Với công việc **{draft['title']}**, bạn dự định làm **từ mấy giờ đến mấy giờ** "
                "(hoặc trong **bao lâu** và **hạn chót ngày nào**)?"
            )
            chips = [
                {"label": "🕗 Sáng mai 08:00 – 09:30", "prompt": "ngày mai từ 08:00 đến 09:30"},
                {"label": "⏱ 60 phút · Hạn Thứ 6", "prompt": "khoảng 60 phút trước Thứ 6"},
                {"label": "⏱ 90 phút · Hạn Chủ nhật", "prompt": "khoảng 90 phút trước Chủ nhật"},
            ]
        elif "time_range" in missing:
            q_vi = f"Bạn ước lượng **{draft['title']}** cần làm trong **bao lâu** (hoặc từ mấy giờ đến mấy giờ)?"
            chips = [
                {"label": "⏱ 45 phút", "prompt": "khoảng 45 phút"},
                {"label": "⏱ 60 phút", "prompt": "khoảng 60 phút"},
                {"label": "⏱ 90 phút", "prompt": "khoảng 90 phút"},
                {"label": "⏱ 2 tiếng", "prompt": "khoảng 2 tiếng"},
            ]
        else:
            q_vi = f"Công việc **{draft['title']}** ({draft['duration_min']} phút) cần hoàn thành trước **ngày nào**?"
            chips = [
                {"label": "📅 Hôm nay", "prompt": "trước 23:59 hôm nay"},
                {"label": "📅 Ngày mai", "prompt": "trước 23:59 ngày mai"},
                {"label": "📅 Thứ Sáu", "prompt": "trước 23:59 Thứ Sáu"},
                {"label": "📅 Chủ Nhật", "prompt": "trước 23:59 Chủ Nhật"},
            ]

        return {
            "status": "NEEDS_CLARIFICATION",
            "intent": "ADD_TASK",
            "reply_vi": q_vi,
            "pending_draft": draft,
            "missing_fields": missing,
            "quick_chips": chips,
            "post_actions": build_post_actions(),
            "updated_commitments": profile.model_dump(mode="json"),
            "updated_tasks": tasks_raw,
            "updated_pinned_blocks": pinned_raw,
            "execution_time_ms": round((time.perf_counter() - t0) * 1000.0, 2),
        }

    new_tid = f"T_CHAT_{int(time.time() * 1000) % 100000}_{len(tasks_raw) + 1}"
    target_day = draft.get("deadline_day") or now_day
    final_dur = int(draft.get("duration_min") or 60)
    start_after_iso = None
    buf_mode = str(draft.get("buffer_mode") or "COGNITIVE_LOAD")

    if has_explicit_window:
        day_iso = _date_iso_for_weekday(profile, str(target_day))
        start_after_iso = f"{day_iso}T{draft['start_time']}:00+07:00"
        buf_mode = "NONE"
    elif draft.get("start_after_day"):
        sa_iso = _date_iso_for_weekday(profile, str(draft["start_after_day"]))
        sa_time = str(draft.get("start_after_time") or "08:00")
        start_after_iso = f"{sa_iso}T{sa_time}:00+07:00"

    explicit_split_req = "is_splittable" in hidden["updates"]
    if explicit_split_req:
        is_split = bool(draft["is_splittable"])
    elif online_ctx and online_ctx.get("is_splittable") is not None:
        is_split = bool(online_ctx["is_splittable"])
    else:
        is_split = final_dur > 180
    min_c = int(draft.get("min_chunk_min") or (45 if is_split else final_dur))
    max_c = int(draft.get("max_chunk_min") or (90 if is_split else max(180, final_dur)))

    task_obj = Task(
        task_id=new_tid,
        title=str(draft["title"]),
        duration_min=final_dur,
        deadline_day=str(target_day),
        deadline_time=str(draft.get("deadline_time") or "23:59"),
        priority=int(draft.get("priority") or 3),
        category=str(draft.get("category") or "ASSIGNMENT"),
        cognitive_load=int(draft.get("cognitive_load") or 2),
        is_splittable=is_split,
        work_rhythm=draft.get("work_rhythm") if is_split else "FLOW",
        min_chunk_min=min_c,
        max_chunk_min=max_c,
        preferred_window=draft.get("preferred_window"),
        start_after=start_after_iso,
        buffer_mode=buf_mode,
        buffer_multiplier=float(draft.get("buffer_multiplier") or 1.0),
        depends_on=[str(d) for d in (draft.get("depends_on") or [])],
    )
    enriched_new = enrich_task_trace_metadata(task_obj.model_dump(mode="json"))
    for prereq_id in list(task_obj.depends_on):
        cycle = find_dependency_cycle(tasks_raw + [enriched_new], new_tid, prereq_id)
        if cycle is not None:
            return cycle_clarification(ctx, "ADD_TASK", cycle, tasks_raw + [enriched_new])
    tasks_raw.append(enriched_new)

    rules_used: List[Dict[str, str]] = []
    extra_notes: List[str] = []
    if task_obj.depends_on:
        rules_used.append(P10_RULE)
        prereq_titles = [str(t.get("title")) for t in tasks_raw if t.get("task_id") in task_obj.depends_on]
        extra_notes.append(f"Việc này chỉ bắt đầu sau khi xong {', '.join(f'**{p}**' for p in prereq_titles)}.")
    if draft.get("doc_autofilled_from"):
        rules_used.append(P14A_RULE)
        extra_notes.append(f"Thời lượng lấy theo đề bài đính kèm `{draft['doc_autofilled_from']}`.")

    day_vi = _WEEKDAY_VI_MAP.get(str(target_day), str(target_day))
    if has_explicit_window:
        time_desc = f"{draft['start_time']} – {draft['end_time']} {day_vi}"
    elif draft.get("start_after_day"):
        sa_day_vi = _WEEKDAY_VI_MAP.get(str(draft["start_after_day"]), str(draft["start_after_day"]))
        time_desc = (
            f"{task_obj.duration_min} phút, trong khung từ {draft.get('start_after_time', '08:00')} {sa_day_vi} "
            f"đến {task_obj.deadline_time} {day_vi}"
        )
    else:
        time_desc = f"{task_obj.duration_min} phút, hạn {task_obj.deadline_time} {day_vi}"

    parser_tag = (
        f"Online AI ({online_ctx.get('model_used', 'gemini')})"
        if online_ctx
        else "Hybrid Clause Condenser"
    )
    ai_note = (
        f" · {online_ctx['human_thinking_summary_vi']}"
        if online_ctx and online_ctx.get("human_thinking_summary_vi")
        else ""
    )
    context_note = (
        f"[{parser_tag}] Tóm tắt thành 1 công việc duy nhất: **{task_obj.title}** (SHA-256 `#{enriched_new['trace_hash'][:8]}`) · "
        f"Thời gian: `{time_desc}` · Giữ liền 1 khối liên tục (không chia nhỏ){ai_note}."
        if not is_split
        else f"[{parser_tag}] Tóm tắt thành 1 công việc: **{task_obj.title}** (SHA-256 `#{enriched_new['trace_hash'][:8]}`) · "
        f"Thời gian: `{time_desc}` · Cho phép chia thành các phiên `{min_c}–{max_c}p`{ai_note}."
    )

    return _finalize_solve_and_package(
        intent="ADD_TASK",
        profile=profile,
        tasks_raw=tasks_raw,
        pinned_raw=pinned_raw,
        completed_blocks=completed_blocks,
        algorithm=algorithm,
        workspace_id=workspace_id,
        auto_save=auto_save,
        mutated_task_id=new_tid,
        context_note_vi=context_note,
        reply_vi=" ".join([f"Đã lên lịch cho **{task_obj.title}** ({time_desc})."] + extra_notes),
        traced_task={
            "task_id": new_tid,
            "title": task_obj.title,
            "trace_hash": enriched_new["trace_hash"],
            "keyword_hashes": enriched_new["keyword_hashes"],
        },
        t0=t0,
        pattern_rules=rules_used or None,
        has_dag=bool(task_obj.depends_on),
    )
