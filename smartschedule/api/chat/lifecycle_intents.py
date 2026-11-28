"""
Workspace-Grounded Lifecycle Chat Intents (`smartschedule.api.chat.lifecycle_intents`, owned by `M4`).

Handles the chat intents that act on items the student *already has* instead of creating one
new task from a single string (the "weak context-parsing" complaint):

  DELETE_ITEM      xóa / hủy / bỏ a task or a fixed event          (cleans orphan `depends_on`)
  COMPLETE_TASK    "làm xong X rồi"                                (logs actual vs estimate for P13)
  QUERY_SCHEDULE   "thứ 5 tuần này có lịch gì"                     (read-only, INFO_ONLY)
  ADAPT_NEXT_WEEK  "rút kinh nghiệm cho tuần sau"                  (M5 `adapt_preferences_for_next_week`, LoA-4)
  BATCH_ADD_TASKS  bullet lists / "xong A rồi mới làm B"           (sequential `depends_on`, P10)
  LINK_DEPENDENCY  "làm B sau khi xong A" with A, B already stored (3-color DFS cycle guard, P10)

plus the attachment cross-check `USER_VS_DOC_UNDERESTIMATE` (P14a) used by `handlers.py` ADD_TASK.

Every function returns the frozen chat-turn contract of `README_agents.md §2.1`. Functions that
mutate the schedule receive `finalize`, a pre-bound `handlers._finalize_solve_and_package`.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from smartschedule.api.chat.thinking_stage import build_post_actions
from smartschedule.core.controller import ScheduleController
from smartschedule.core.models import CommitmentsProfile, ScheduleOutput, Task
from smartschedule.core.storage import append_completion_log, list_completion_logs
from smartschedule.core.task_tracer import enrich_task_trace_metadata, resolve_target_task_from_prompt
from smartschedule.core.utils import round_up_to_15
from smartschedule.nlp.clause_condenser import (
    _OFFLINE_NL,
    _WEEKDAY_VI_MAP,
    _clean_conversational_title,
    _extract_flexible_duration_min,
    _resolve_day_token,
)
from smartschedule.nlp.intent_classifier import (
    IntentResult,
    PrerequisiteSplit,
    fold,
    split_prerequisite_clause,
)
from smartschedule.nlp.parser_controller import WEEKDAYS

DOC_UNDERESTIMATE_RATIO: float = 0.5

P10_RULE: Dict[str, str] = {
    "pattern_id": "P10",
    "pattern_name": "Prerequisite Chain Bottlenecks (Topological DAG Cascade)",
    "causal_link_vi": "Việc tiền đề phải xong trước việc phụ thuộc; thêm cạnh mới chỉ khi không tạo vòng lặp",
    "deterministic_rule": "3-color DFS: reject u->v if v reaches u; H5: max(end_u) <= min(start_v)",
}
P14A_RULE: Dict[str, str] = {
    "pattern_id": "P14",
    "pattern_name": "Document-to-Constraint Abstraction (DocumentConstraintDigest)",
    "causal_link_vi": "Đề bài đính kèm cho biết khối lượng thật; ước lượng tay quá thấp là dấu hiệu Planning Fallacy",
    "deterministic_rule": "user_min < 0.5 * suggested_total_min -> USER_VS_DOC_UNDERESTIMATE",
}

_APPLY_RE = re.compile(r"\b(?:ap\s*dung|dong\s*y|apply|chap\s*nhan|ok\s+lam\s+di)\b")
_KEEP_RE = re.compile(r"\b(?:giu\s*nguyen|khong\s+ap\s*dung|bo\s+qua|thoi\s+khong)\b")
_DOC_USE_RE = re.compile(r"\b(?:dung\s+(?:cac\s+)?moc|theo\s+(?:de\s*bai|file|tai\s*lieu)|dung\s+de\s*bai|use\s+(?:the\s+)?(?:spec|milestones))\b")
_DOC_KEEP_RE = re.compile(r"\b(?:giu\s+(?:nguyen\s+)?(?:thoi\s*luong|so\s+phut|uoc\s*luong)|keep\s+(?:my\s+)?(?:duration|estimate))\b")
_EVENT_TAG_RE = re.compile(r"\[event:([A-Za-z0-9_\-]+)\]")
_ORDERED_HEADER_RE = re.compile(r"\b(?:theo\s+thu\s+tu|lan\s+luot|tuan\s+tu|in\s+order|step\s+by\s+step)\b")
_SEQ_LINE_RE = re.compile(r"^\s*(?:[-*•+]|\d{1,2}\s*[.)]|[a-e]\s*[.)])?\s*(?:roi|sau\s+do|tiep\s+theo|xong\s+roi|then)\b")
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•+]|\d{1,2}\s*[.)]|[a-e]\s*[.)])\s*")
_LEAD_VERB_STRIP_RE = re.compile(
    r"^\s*(?:(?:minh|toi|em|cho\s+minh|giup\s+minh|hay)\s+)?(?:muon\s+|can\s+)?"
    r"(?:xoa(?:\s*bo)?|go\s*bo|loai\s*bo|huy(?:\s*bo)?|bo|delete|remove)\s+"
)
_STOP_TOKENS = frozenset(
    "lich bai viec cong task mon su kien cua minh toi em ban nay do kia tuan thu ngay hom nay mai "
    "co dinh hang moi xoa huy bo go loai di nhe nha voi cho giup the la".split()
)


@dataclass
class ChatTurnContext:
    prompt: str
    profile: CommitmentsProfile
    tasks_raw: List[Dict[str, Any]]
    pinned_raw: List[Dict[str, Any]]
    completed_blocks: Dict[str, Any]
    algorithm: str
    workspace_id: str
    auto_save: bool
    now_day: str
    t0: float
    last_task_id: Optional[str] = None
    pending_draft: Optional[Dict[str, Any]] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    saved_state: Dict[str, Any] = field(default_factory=dict)

    @property
    def norm(self) -> str:
        return fold(self.prompt)


# ---------------------------------------------------------------------------
# Generic response helpers
# ---------------------------------------------------------------------------


def _elapsed_ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000.0, 2)


def non_applied_response(
    ctx: ChatTurnContext,
    *,
    status: str,
    intent: str,
    reply_vi: str,
    quick_chips: Optional[List[Dict[str, str]]] = None,
    pending_draft: Optional[Dict[str, Any]] = None,
    missing_fields: Optional[List[str]] = None,
    profile: Optional[CommitmentsProfile] = None,
    tasks_raw: Optional[List[Dict[str, Any]]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """Build a `NEEDS_CLARIFICATION` / `INFO_ONLY` / `CANCELLED` response that never mutates state."""
    out: Dict[str, Any] = {
        "status": status,
        "intent": intent,
        "finalized": False,
        "finalized_message_vi": "",
        "reply_vi": reply_vi,
        "thinking_summary": None,
        "pending_draft": pending_draft,
        "missing_fields": list(missing_fields or []),
        "quick_chips": list(quick_chips or []),
        "mutated_task_id": None,
        "traced_task": None,
        "remaining_estimation": None,
        "edge_case": None,
        "post_actions": build_post_actions(),
        "updated_commitments": (profile or ctx.profile).model_dump(mode="json"),
        "updated_tasks": tasks_raw if tasks_raw is not None else ctx.tasks_raw,
        "updated_pinned_blocks": ctx.pinned_raw,
        "schedule": None,
        "execution_time_ms": _elapsed_ms(ctx.t0),
    }
    out.update(extra)
    return out


def _task_chip(prefix_vi: str, task: Dict[str, Any], verb_prompt: str) -> Dict[str, str]:
    th = str(task.get("trace_hash") or "")[:8]
    return {"label": f"{prefix_vi} {task.get('title')}", "prompt": f"{verb_prompt} [trace:{th}]"}


def _day_vi(day: Optional[str]) -> str:
    return _WEEKDAY_VI_MAP.get(str(day or ""), str(day or "linh hoạt"))


# ---------------------------------------------------------------------------
# DAG utilities (Pattern P10)
# ---------------------------------------------------------------------------


def find_dependency_cycle(
    tasks: Sequence[Dict[str, Any]],
    dependent_id: str,
    prerequisite_id: str,
) -> Optional[List[str]]:
    """
    Return the cycle path `[dependent, prerequisite, ..., dependent]` that adding the edge
    `dependent.depends_on += prerequisite` would close, or `None` if the graph stays acyclic.

    Edge direction follows `depends_on` (child -> parent). The new edge closes a cycle iff
    `prerequisite` can already reach `dependent` by following `depends_on` links (3-color DFS,
    iterative so a 500-task chain cannot hit Python's recursion limit).
    """
    if dependent_id == prerequisite_id:
        return [dependent_id, dependent_id]
    graph: Dict[str, List[str]] = {
        str(t.get("task_id")): [str(d) for d in (t.get("depends_on") or [])] for t in tasks if t.get("task_id")
    }
    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {}
    parent: Dict[str, Optional[str]] = {prerequisite_id: None}
    stack: List[Tuple[str, int]] = [(prerequisite_id, 0)]
    color[prerequisite_id] = GRAY
    while stack:
        node, i = stack[-1]
        children = graph.get(node, [])
        if i < len(children):
            stack[-1] = (node, i + 1)
            nxt = children[i]
            if nxt == dependent_id:
                cur: Optional[str] = node
                rev: List[str] = []
                while cur is not None:
                    rev.append(cur)
                    cur = parent.get(cur)
                # rev = [node, ..., prerequisite]; cycle: dependent -> prerequisite -> ... -> node -> dependent
                return [dependent_id] + list(reversed(rev)) + [dependent_id]
            if color.get(nxt, WHITE) == WHITE:
                color[nxt] = GRAY
                parent[nxt] = node
                stack.append((nxt, 0))
        else:
            color[node] = BLACK
            stack.pop()
    return None


def add_dependency_edge(
    tasks: List[Dict[str, Any]],
    dependent_id: str,
    prerequisite_id: str,
) -> Tuple[bool, Optional[List[str]]]:
    """Append `prerequisite_id` to `dependent.depends_on` in place unless it closes a cycle."""
    cycle = find_dependency_cycle(tasks, dependent_id, prerequisite_id)
    if cycle is not None:
        return False, cycle
    for idx, t in enumerate(tasks):
        if t.get("task_id") == dependent_id:
            deps = [str(d) for d in (t.get("depends_on") or [])]
            if prerequisite_id not in deps:
                deps.append(prerequisite_id)
            upd = dict(t)
            upd["depends_on"] = deps
            tasks[idx] = upd
            break
    return True, None


def _titles_for(tasks: Sequence[Dict[str, Any]], ids: Sequence[str]) -> List[str]:
    by_id = {str(t.get("task_id")): str(t.get("title") or t.get("task_id")) for t in tasks}
    return [by_id.get(i, i) for i in ids]


def cycle_clarification(ctx: ChatTurnContext, intent: str, cycle: List[str], tasks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    titles = _titles_for(tasks, cycle)
    chain_vi = " → ".join(f"**{t}**" for t in titles)
    return non_applied_response(
        ctx,
        status="NEEDS_CLARIFICATION",
        intent=intent,
        reply_vi=(
            f"Mình chưa thể nối thứ tự này vì sẽ tạo **vòng lặp phụ thuộc**: {chain_vi}. "
            "Không có việc nào bắt đầu được nếu mỗi việc đều chờ việc kia xong trước. "
            "Bạn muốn giữ thứ tự nào?"
        ),
        quick_chips=[
            {"label": "↩️ Giữ thứ tự cũ", "prompt": "Hủy thao tác"},
        ],
        missing_fields=["dependency_order"],
        conflict="CIRCULAR_DEPENDENCY",
        cycle_task_ids=cycle,
    )


# ---------------------------------------------------------------------------
# Task construction (mirrors handlers.py ADD_TASK so batch items behave identically)
# ---------------------------------------------------------------------------


def _new_task_id(tasks_raw: Sequence[Dict[str, Any]], salt: int = 0) -> str:
    existing = {str(t.get("task_id")) for t in tasks_raw}
    base = int(time.time() * 1000) % 100000
    n = len(tasks_raw) + 1 + salt
    tid = f"T_CHAT_{base}_{n}"
    while tid in existing:
        n += 1
        tid = f"T_CHAT_{base}_{n}"
    return tid


def build_task_dict(
    *,
    task_id: str,
    title: str,
    duration_min: int,
    deadline_day: str,
    deadline_time: str = "23:59",
    category: str = "ASSIGNMENT",
    priority: int = 3,
    cognitive_load: int = 2,
    depends_on: Optional[List[str]] = None,
    preferred_window: Optional[str] = None,
) -> Dict[str, Any]:
    dur = max(15, round_up_to_15(int(duration_min)))
    is_split = dur > 180
    task_obj = Task(
        task_id=task_id,
        title=title,
        duration_min=dur,
        deadline_day=deadline_day,
        deadline_time=deadline_time or "23:59",
        priority=max(1, min(5, int(priority))),
        category=category or "ASSIGNMENT",
        cognitive_load=max(1, min(3, int(cognitive_load))),
        is_splittable=is_split,
        work_rhythm=None if is_split else "FLOW",
        min_chunk_min=45 if is_split else dur,
        max_chunk_min=90 if is_split else max(180, dur),
        preferred_window=preferred_window,
        depends_on=list(depends_on or []),
        buffer_mode="COGNITIVE_LOAD",
    )
    return enrich_task_trace_metadata(task_obj.model_dump(mode="json"))


@dataclass
class ParsedItem:
    title: str
    duration_min: Optional[int]
    deadline_day: Optional[str]
    deadline_time: Optional[str]
    category: str
    priority: int
    cognitive_load: int
    after_previous: bool = False
    prerequisite_text: Optional[str] = None


def parse_task_clause(text: str, now_day: str) -> ParsedItem:
    """Parse one clause into a task draft with the same offline helpers as single ADD_TASK."""
    clean = _BULLET_PREFIX_RE.sub("", text).strip()
    norm = fold(clean)
    after_prev = bool(_SEQ_LINE_RE.match(fold(text)))
    if after_prev:
        clean = re.sub(r"^\s*(?:rồi|roi|sau\s+đó|sau\s+do|tiếp\s+theo|tiep\s+theo|xong\s+rồi|xong\s+roi|then)\s*,?\s*", "", clean, flags=re.IGNORECASE)
        norm = fold(clean)

    prereq_text: Optional[str] = None
    split = split_prerequisite_clause(clean)
    if split is not None:
        prereq_text = split.prerequisite_text
        clean = split.dependent_text
        norm = fold(clean)

    dur, dur_inferred = _extract_flexible_duration_min(norm)
    dl_day, day_inferred = _OFFLINE_NL.extract_deadline_day(norm, now_day)
    dl_time, time_inferred, _, _ = _OFFLINE_NL.extract_clock_time(norm)
    cat, prio, load = _OFFLINE_NL.extract_category_priority_load(clean.lower(), norm)
    title = _clean_conversational_title(clean) or clean.strip(" ,.;:-")
    return ParsedItem(
        title=title,
        duration_min=None if dur_inferred else dur,
        deadline_day=None if day_inferred else (dl_day if dl_day in WEEKDAYS else None),
        deadline_time=None if time_inferred else dl_time,
        category=cat,
        priority=prio,
        cognitive_load=load,
        after_previous=after_prev,
        prerequisite_text=prereq_text,
    )


def _flatten_chain(text: str) -> List[str]:
    """'A rồi sau đó B, sau đó C' -> ['A', 'B', 'C'] (surface order == execution order)."""
    split = split_prerequisite_clause(text)
    if split is None:
        return [text]
    # Execution order is always prerequisite first, whatever the surface order of the sentence.
    return _flatten_chain(split.prerequisite_text) + _flatten_chain(split.dependent_text)


# ---------------------------------------------------------------------------
# DELETE_ITEM
# ---------------------------------------------------------------------------


def _event_score(prompt_norm: str, title: str, event_days: Any, prompt_day: Optional[str]) -> float:
    tokens = [tok for tok in re.findall(r"[a-z0-9]+", fold(title)) if len(tok) >= 2 and tok not in _STOP_TOKENS]
    if not tokens:
        return 0.0
    hits = sum(1 for tok in tokens if re.search(rf"\b{re.escape(tok)}\b", prompt_norm))
    score = hits / float(len(tokens))
    if hits and prompt_day:
        days = event_days if isinstance(event_days, list) else [event_days]
        if prompt_day in days or "ALL" in [str(d).upper() for d in days]:
            score += 0.10
    return min(1.0, score)


def handle_delete_item(ctx: ChatTurnContext, finalize: Callable[..., Dict[str, Any]]) -> Dict[str, Any]:
    norm = ctx.norm
    target_norm = _LEAD_VERB_STRIP_RE.sub("", norm)
    target_text = ctx.prompt
    prompt_day = _resolve_day_token(ctx.prompt, ctx.now_day)

    # Explicit fixed-event tag from a clarification chip
    tag = _EVENT_TAG_RE.search(ctx.prompt)
    events = list(ctx.profile.fixed_events)
    best_event = None
    best_event_score = 0.0
    if tag:
        best_event = next((e for e in events if e.event_id == tag.group(1)), None)
        best_event_score = 1.0 if best_event else 0.0
    else:
        for ev in events:
            sc = _event_score(target_norm, ev.title, ev.day_of_week, prompt_day)
            if sc > best_event_score:
                best_event, best_event_score = ev, sc

    trace = resolve_target_task_from_prompt(target_text, ctx.tasks_raw, last_task_id=ctx.last_task_id)
    task_conf = float(trace.get("confidence") or 0.0) if trace.get("matched") else 0.0

    if task_conf >= 0.60 and task_conf >= best_event_score:
        return _delete_task(ctx, finalize, trace)
    if best_event is not None and best_event_score >= 0.50:
        return _delete_fixed_event(ctx, finalize, best_event)

    chips: List[Dict[str, str]] = []
    for c in (trace.get("candidates") or [])[:3]:
        if c.get("title"):
            chips.append(_task_chip("🗑️", c, "Xóa"))
    for ev in events[:3]:
        chips.append({"label": f"🗑️ {ev.title} (lịch cố định)", "prompt": f"Xóa lịch cố định [event:{ev.event_id}]"})
    return non_applied_response(
        ctx,
        status="NEEDS_CLARIFICATION",
        intent="DELETE_ITEM",
        reply_vi="Mình chưa chắc bạn muốn xóa mục nào. Bạn chọn đúng công việc hoặc lịch cố định bên dưới nhé:",
        quick_chips=chips,
        missing_fields=["target_item"],
    )


def _delete_task(ctx: ChatTurnContext, finalize: Callable[..., Dict[str, Any]], trace: Dict[str, Any]) -> Dict[str, Any]:
    tid = str(trace["task_id"])
    title = str((trace.get("task") or {}).get("title") or tid)
    kept: List[Dict[str, Any]] = []
    orphan_fixed: List[str] = []
    for t in ctx.tasks_raw:
        if t.get("task_id") == tid:
            continue
        deps = [str(d) for d in (t.get("depends_on") or [])]
        if tid in deps:
            t = dict(t)
            t["depends_on"] = [d for d in deps if d != tid]
            orphan_fixed.append(str(t.get("title") or t.get("task_id")))
        kept.append(t)
    pinned = [p for p in ctx.pinned_raw if p.get("task_id") != tid]
    completed = {k: v for k, v in ctx.completed_blocks.items() if not (str(k) == tid or str(k).startswith(f"{tid}_"))}
    note_dep = (
        f" Các việc từng chờ việc này ({', '.join(orphan_fixed)}) giờ có thể bắt đầu ngay."
        if orphan_fixed
        else ""
    )
    return finalize(
        intent="DELETE_ITEM",
        profile=ctx.profile,
        tasks_raw=kept,
        pinned_raw=pinned,
        completed_blocks=completed,
        mutated_task_id=None,
        context_note_vi=(
            f"Truy vết công việc cần xóa **{title}** (SHA-256 `#{str(trace.get('trace_hash') or '')[:8]}`, "
            f"độ khớp `{float(trace.get('confidence') or 0):.2f}`) · dọn `{len(orphan_fixed)}` cạnh `depends_on` mồ côi."
        ),
        reply_vi=f"Đã xóa **{title}** khỏi danh sách và sắp xếp lại lịch tuần.{note_dep}",
        traced_task={"task_id": tid, "title": title, "trace_hash": trace.get("trace_hash"), "deleted": True},
    )


def _delete_fixed_event(ctx: ChatTurnContext, finalize: Callable[..., Dict[str, Any]], event: Any) -> Dict[str, Any]:
    prof = ctx.profile.model_copy(deep=True)
    prof.fixed_events = [e for e in prof.fixed_events if e.event_id != event.event_id]
    days = event.day_of_week if isinstance(event.day_of_week, list) else [event.day_of_week]
    days_vi = "hằng ngày" if "ALL" in [str(d).upper() for d in days] else ", ".join(_day_vi(d) for d in days)
    return finalize(
        intent="DELETE_ITEM",
        profile=prof,
        tasks_raw=ctx.tasks_raw,
        pinned_raw=ctx.pinned_raw,
        completed_blocks=ctx.completed_blocks,
        mutated_task_id=None,
        context_note_vi=f"Gỡ lịch cố định **{event.title}** (`{event.event_id}`, {days_vi} {event.start_time}–{event.end_time}).",
        reply_vi=(
            f"Đã gỡ lịch cố định **{event.title}** ({days_vi}, {event.start_time} – {event.end_time}). "
            "Khung giờ này đã trống để xếp việc khác."
        ),
    )


# ---------------------------------------------------------------------------
# COMPLETE_TASK
# ---------------------------------------------------------------------------


def handle_complete_task(ctx: ChatTurnContext, finalize: Callable[..., Dict[str, Any]]) -> Dict[str, Any]:
    trace = resolve_target_task_from_prompt(ctx.prompt, ctx.tasks_raw, last_task_id=ctx.last_task_id)
    if not trace.get("matched") or float(trace.get("confidence") or 0.0) < 0.60:
        chips = [_task_chip("✅", c, "Đã làm xong") for c in (trace.get("candidates") or [])[:4] if c.get("title")]
        return non_applied_response(
            ctx,
            status="NEEDS_CLARIFICATION",
            intent="COMPLETE_TASK",
            reply_vi="Chúc mừng bạn! Bạn vừa hoàn thành công việc nào để mình đánh dấu nhé?",
            quick_chips=chips,
            missing_fields=["target_task"],
        )

    tid = str(trace["task_id"])
    task = dict(trace.get("task") or {})
    title = str(task.get("title") or tid)
    est_min = int(task.get("duration_min") or 60)
    act_val, act_inferred = _extract_flexible_duration_min(ctx.norm)
    actual_min = int(act_val) if (act_val and not act_inferred) else est_min

    log_entry: Optional[Dict[str, Any]] = None
    if ctx.payload.get("record_completion", True):
        try:
            log_entry = append_completion_log(
                task_id=tid,
                category=str(task.get("category") or "OTHER"),
                estimated_duration_min=est_min,
                actual_duration_min=actual_min,
                workspace_id=ctx.workspace_id,
            )
        except Exception:
            log_entry = None

    unblocked: List[str] = []
    kept: List[Dict[str, Any]] = []
    for t in ctx.tasks_raw:
        if t.get("task_id") == tid:
            continue
        deps = [str(d) for d in (t.get("depends_on") or [])]
        if tid in deps:
            t = dict(t)
            t["depends_on"] = [d for d in deps if d != tid]
            unblocked.append(str(t.get("title") or t.get("task_id")))
        kept.append(t)
    pinned = [p for p in ctx.pinned_raw if p.get("task_id") != tid]

    ratio = actual_min / float(max(1, est_min))
    if ratio >= 1.15:
        ratio_vi = f" Thực tế mất `{actual_min}p` so với ước lượng `{est_min}p` (×{ratio:.2f}) — mình đã ghi lại để tuần sau trừ hao sát hơn."
    elif ratio <= 0.85:
        ratio_vi = f" Bạn làm nhanh hơn dự kiến (`{actual_min}p` / `{est_min}p`) — mình đã ghi lại để tuần sau bớt dự phòng."
    else:
        ratio_vi = ""
    unblock_vi = f" Giờ bạn có thể bắt đầu: {', '.join(f'**{u}**' for u in unblocked)}." if unblocked else ""
    return finalize(
        intent="COMPLETE_TASK",
        profile=ctx.profile,
        tasks_raw=kept,
        pinned_raw=pinned,
        completed_blocks=ctx.completed_blocks,
        mutated_task_id=None,
        context_note_vi=(
            f"Đánh dấu hoàn thành **{title}** (SHA-256 `#{str(trace.get('trace_hash') or '')[:8]}`) · "
            f"ghi `completion_logs` A/E = `{actual_min}/{est_min}` cho học thích nghi xuyên tuần (P13)."
        ),
        reply_vi=f"🎉 Tuyệt vời! Đã đánh dấu hoàn thành **{title}** và giải phóng lịch còn lại.{ratio_vi}{unblock_vi}",
        traced_task={"task_id": tid, "title": title, "trace_hash": trace.get("trace_hash"), "completed": True},
        extra_fields={"completion_log": log_entry},
    )


# ---------------------------------------------------------------------------
# QUERY_SCHEDULE (read-only)
# ---------------------------------------------------------------------------


def _resolve_query_schedule(ctx: ChatTurnContext) -> Optional[ScheduleOutput]:
    raw = ctx.payload.get("schedule") or ctx.payload.get("current_schedule") or ctx.saved_state.get("currentSchedule")
    if isinstance(raw, dict) and isinstance(raw.get("blocks"), list) and isinstance(raw.get("summary"), dict):
        try:
            return ScheduleOutput.model_validate(raw)
        except Exception:
            pass
    if not ctx.tasks_raw:
        return None
    try:
        tasks = [Task.model_validate(t) for t in ctx.tasks_raw]
        out, _ = ScheduleController.solve_schedule(ctx.profile, tasks, algorithm="SCORED_GREEDY")
        return out
    except Exception:
        return None


def handle_query_schedule(ctx: ChatTurnContext) -> Dict[str, Any]:
    day = _resolve_day_token(ctx.prompt, ctx.now_day)
    sched = _resolve_query_schedule(ctx)
    blocks = sorted(list(sched.blocks) if sched else [], key=lambda b: (b.start_slot, b.end_slot))

    def _events_on(d: str) -> List[Any]:
        out = []
        for ev in ctx.profile.fixed_events:
            days = ev.day_of_week if isinstance(ev.day_of_week, list) else [ev.day_of_week]
            if d in days or "ALL" in [str(x).upper() for x in days]:
                out.append(ev)
        return sorted(out, key=lambda e: e.start_time)

    if day:
        lines: List[Tuple[str, str]] = []
        for b in blocks:
            if b.day == day:
                part = f" (phiên {b.chunk_index}/{b.total_chunks})" if (b.total_chunks or 1) > 1 else ""
                lines.append((b.start_time, f"• `{b.start_time}–{b.end_time}` {b.title}{part}"))
        for ev in _events_on(day):
            lines.append((ev.start_time, f"• `{ev.start_time}–{ev.end_time}` {ev.title} _(lịch cố định)_"))
        lines.sort(key=lambda x: x[0])
        due_today = [str(t.get("title")) for t in ctx.tasks_raw if t.get("deadline_day") == day]
        if lines:
            body = "\n".join(l for _, l in lines)
            reply = f"📅 **{_day_vi(day)}** bạn có `{len(lines)}` mục:\n{body}"
        else:
            reply = f"📅 **{_day_vi(day)}** hiện chưa có phiên học hay lịch cố định nào — ngày này đang trống."
        if due_today:
            reply += f"\n⏰ Hạn chót trong ngày: {', '.join(f'**{d}**' for d in due_today)}."
    else:
        per_day: Dict[str, int] = {}
        for b in blocks:
            per_day[b.day] = per_day.get(b.day, 0) + 1
        if per_day:
            parts = [f"{_day_vi(d)}: `{per_day[d]}` phiên" for d in WEEKDAYS if d in per_day]
            reply = f"🗓️ Tuần này có `{len(blocks)}` phiên học cho `{len(ctx.tasks_raw)}` công việc — " + "; ".join(parts) + "."
        else:
            reply = "🗓️ Tuần này chưa có phiên học nào được xếp. Bạn thử thêm một công việc nhé!"
        unplaced = list(sched.unplaced_tasks) if sched else []
        if unplaced:
            reply += f"\n⚠️ Còn `{len(unplaced)}` việc chưa xếp được."

    chips = [{"label": f"📅 {_day_vi(d)}", "prompt": f"{_day_vi(d)} có lịch gì?"} for d in WEEKDAYS if d != day][:3]
    return non_applied_response(ctx, status="INFO_ONLY", intent="QUERY_SCHEDULE", reply_vi=reply, quick_chips=chips, query_day=day)


# ---------------------------------------------------------------------------
# ADAPT_NEXT_WEEK (Pattern P13 via M5 `adapt_preferences_for_next_week`)
# ---------------------------------------------------------------------------


def collect_timeline_logs(ctx: ChatTurnContext) -> List[Dict[str, Any]]:
    provided = ctx.payload.get("timeline_logs")
    if isinstance(provided, list) and provided:
        logs = [dict(x) for x in provided if isinstance(x, dict)]
    else:
        try:
            logs = list(reversed(list_completion_logs(workspace_id=ctx.workspace_id, limit=200)))
        except Exception:
            logs = []
        for row in logs:
            row.setdefault("adhered", True)
    for d in ctx.saved_state.get("disruption_logs") or []:
        if isinstance(d, dict) and d.get("disruption_slot_window"):
            logs.append({"disruption_slot_window": d["disruption_slot_window"]})
    return logs


def summarize_adaptation_vi(res: Dict[str, Any]) -> Tuple[str, int]:
    """Human Vietnamese summary of learned category buffers + preference shifts; returns (text, n_samples)."""
    lines: List[str] = []
    n_total = 0
    for cat, info in sorted((res.get("category_alphas") or {}).items()):
        n = int(info.get("sample_count") or 0)
        if n <= 0:
            continue
        n_total += n
        lines.append(
            f"• **{cat}** (`{n}` lần ghi nhận): dự phòng việc nhẹ ×`{float(info['alpha_light']):.2f}`, "
            f"việc nặng ×`{float(info['alpha_heavy']):.2f}`"
        )
    for shift in res.get("preference_shifts") or []:
        if shift.get("shift_type") == "CATEGORY_BUFFER":
            continue
        if shift.get("message_vi"):
            lines.append(f"• {shift['message_vi']}")
    return "\n".join(lines), n_total


def handle_adapt_next_week(
    ctx: ChatTurnContext,
    finalize: Callable[..., Dict[str, Any]],
    adapter: Optional[Callable[..., Dict[str, Any]]],
) -> Dict[str, Any]:
    if _KEEP_RE.search(ctx.norm):
        return non_applied_response(
            ctx, status="INFO_ONLY", intent="ADAPT_NEXT_WEEK",
            reply_vi="Đã giữ nguyên các thông số hiện tại. Khi nào muốn, bạn cứ nhắn *\"rút kinh nghiệm cho tuần sau\"* nhé.",
        )
    if adapter is None:
        return non_applied_response(
            ctx, status="INFO_ONLY", intent="ADAPT_NEXT_WEEK",
            reply_vi="Tính năng học thích nghi xuyên tuần chưa được cài trên máy chủ này, nên lịch được giữ nguyên.",
        )

    logs = collect_timeline_logs(ctx)
    tasks = [Task.model_validate(t) for t in ctx.tasks_raw]
    res = adapter(ctx.profile, tasks, logs)
    summary_vi, n_samples = summarize_adaptation_vi(res)
    has_shift = bool(res.get("preference_shifts"))

    if n_samples == 0 and not has_shift:
        return non_applied_response(
            ctx, status="INFO_ONLY", intent="ADAPT_NEXT_WEEK",
            reply_vi=(
                "Mình chưa có đủ lịch sử để rút kinh nghiệm (chưa có lần hoàn thành nào được ghi lại). "
                "Hệ số dự phòng tạm giữ mặc định ×`1.20` (việc nhẹ) / ×`1.35` (việc nặng). "
                "Mỗi khi xong việc, bạn nhắn *\"làm xong X rồi, mất N phút\"* để mình học dần nhé."
            ),
            adaptation=_compact_adaptation(res),
        )

    if not _APPLY_RE.search(ctx.norm):
        return non_applied_response(
            ctx, status="INFO_ONLY", intent="ADAPT_NEXT_WEEK",
            reply_vi=(
                f"📈 Từ `{n_samples}` lần làm thực tế, mình đề xuất điều chỉnh cho tuần sau:\n{summary_vi or '• Không có thay đổi đáng kể.'}\n"
                "Bạn có muốn áp dụng không? (Mình chỉ đổi khi bạn đồng ý.)"
            ),
            quick_chips=[
                {"label": "✅ Áp dụng cho tuần sau", "prompt": "Áp dụng thích nghi cho tuần sau"},
                {"label": "✋ Giữ nguyên", "prompt": "Giữ nguyên, không áp dụng thích nghi tuần sau"},
            ],
            adaptation=_compact_adaptation(res),
        )

    adapted_profile: CommitmentsProfile = res["adapted_profile"]
    adapted_tasks = [enrich_task_trace_metadata(t) for t in res.get("adapted_tasks_dump") or []]
    return finalize(
        intent="ADAPT_NEXT_WEEK",
        profile=adapted_profile,
        tasks_raw=adapted_tasks,
        pinned_raw=[],
        completed_blocks=ctx.completed_blocks,
        mutated_task_id=None,
        context_note_vi=f"Học thích nghi xuyên tuần (P13) từ `{n_samples}` bản ghi A/E: Bayes–EWMA co rút κ=3, kẹp α ∈ [1.00, 1.60].",
        reply_vi=f"✅ Đã áp dụng bài học từ tuần trước:\n{summary_vi}\nLịch đã được xếp lại theo thông số mới.",
        pattern_rules=list(res.get("pattern_rules") or []),
        extra_fields={"adaptation": _compact_adaptation(res)},
    )


def _compact_adaptation(res: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "category_alphas": res.get("category_alphas") or {},
        "preference_shifts": res.get("preference_shifts") or [],
        "chronic_disruption_zones": res.get("chronic_disruption_zones") or [],
        "pacing_adjusted": bool(res.get("pacing_adjusted")),
    }


# ---------------------------------------------------------------------------
# LINK_DEPENDENCY & BATCH_ADD_TASKS (Pattern P10)
# ---------------------------------------------------------------------------


def handle_link_dependency(ctx: ChatTurnContext, finalize: Callable[..., Dict[str, Any]], result: IntentResult) -> Dict[str, Any]:
    dep_id = str(result.dependent_task_id)
    pre_id = str(result.prerequisite_task_id)
    tasks = [dict(t) for t in ctx.tasks_raw]
    ok, cycle = add_dependency_edge(tasks, dep_id, pre_id)
    if not ok:
        return cycle_clarification(ctx, "LINK_DEPENDENCY", cycle or [dep_id, pre_id], tasks)
    dep_title, pre_title = _titles_for(tasks, [dep_id, pre_id])
    return finalize(
        intent="LINK_DEPENDENCY",
        profile=ctx.profile,
        tasks_raw=tasks,
        pinned_raw=[p for p in ctx.pinned_raw if p.get("task_id") != dep_id],
        completed_blocks=ctx.completed_blocks,
        mutated_task_id=dep_id,
        context_note_vi=f"Nối cạnh phụ thuộc `{pre_id} → {dep_id}` (**{pre_title}** trước **{dep_title}**) sau khi DFS 3 màu xác nhận không có chu trình.",
        reply_vi=f"Đã ghi nhận: làm **{pre_title}** xong rồi mới đến **{dep_title}**.",
        pattern_rules=[P10_RULE],
        has_dag=True,
    )


def handle_batch_add_tasks(ctx: ChatTurnContext, finalize: Callable[..., Dict[str, Any]], result: IntentResult) -> Dict[str, Any]:
    draft = dict(ctx.pending_draft or {})
    if draft.get("intent") == "BATCH_ADD_TASKS" and isinstance(draft.get("items"), list):
        items: List[Dict[str, Any]] = [dict(x) for x in draft["items"]]
        resume_day, inferred = _OFFLINE_NL.extract_deadline_day(ctx.norm, ctx.now_day)
        resume_day = _resolve_day_token(ctx.prompt, ctx.now_day) or (None if inferred else resume_day)
        for it in items:
            if not it.get("deadline_day") and resume_day in WEEKDAYS:
                it["deadline_day"] = resume_day
        linked_existing = draft.get("link_existing_dependent")
    else:
        items, linked_existing = _parse_batch_items(ctx, result)

    if len(items) < 1:
        return non_applied_response(
            ctx, status="NEEDS_CLARIFICATION", intent="BATCH_ADD_TASKS",
            reply_vi="Mình chưa tách được danh sách công việc. Bạn ghi mỗi việc một dòng (bắt đầu bằng `-`) nhé.",
            missing_fields=["items"],
        )

    if any(not it.get("deadline_day") for it in items):
        chips = [{"label": f"📅 {_day_vi(d)}", "prompt": f"Hạn chót {_day_vi(d)}"} for d in ("Friday", "Saturday", "Sunday")]
        names = ", ".join(f"**{it['title']}**" for it in items if not it.get("deadline_day"))
        return non_applied_response(
            ctx, status="NEEDS_CLARIFICATION", intent="BATCH_ADD_TASKS",
            reply_vi=f"Mình đã tách được `{len(items)}` việc. Các việc {names} cần hoàn thành trước **ngày nào**?",
            quick_chips=chips,
            missing_fields=["deadline_day"],
            pending_draft={"intent": "BATCH_ADD_TASKS", "items": items, "link_existing_dependent": linked_existing},
        )

    tasks = [dict(t) for t in ctx.tasks_raw]
    created_ids: List[str] = []
    defaulted: List[str] = []
    for i, it in enumerate(items):
        deps: List[str] = []
        prev_ref = it.get("depends_on_index")
        if isinstance(prev_ref, int) and 0 <= prev_ref < len(created_ids):
            deps.append(created_ids[prev_ref])
        if it.get("depends_on_existing"):
            deps.append(str(it["depends_on_existing"]))
        dur = it.get("duration_min")
        if not dur:
            dur = 60 if int(it.get("cognitive_load") or 2) < 3 else 90
            defaulted.append(str(it["title"]))
        tid = _new_task_id(tasks, salt=i)
        tasks.append(
            build_task_dict(
                task_id=tid,
                title=str(it["title"]),
                duration_min=int(dur),
                deadline_day=str(it["deadline_day"]),
                deadline_time=str(it.get("deadline_time") or "23:59"),
                category=str(it.get("category") or "ASSIGNMENT"),
                priority=int(it.get("priority") or 3),
                cognitive_load=int(it.get("cognitive_load") or 2),
                depends_on=deps,
            )
        )
        created_ids.append(tid)

    if linked_existing and created_ids:
        ok, cycle = add_dependency_edge(tasks, str(linked_existing), created_ids[-1])
        if not ok:
            return cycle_clarification(ctx, "BATCH_ADD_TASKS", cycle or [], tasks)

    n_edges = sum(len(t.get("depends_on") or []) for t in tasks if t.get("task_id") in created_ids) + (1 if linked_existing else 0)
    order_vi = " → ".join(f"**{t}**" for t in _titles_for(tasks, created_ids))
    default_vi = f" (Mình tạm ước lượng thời lượng cho {', '.join(defaulted)} — bạn có thể sửa lại.)" if defaulted else ""
    return finalize(
        intent="BATCH_ADD_TASKS",
        profile=ctx.profile,
        tasks_raw=tasks,
        pinned_raw=ctx.pinned_raw,
        completed_blocks=ctx.completed_blocks,
        mutated_task_id=created_ids[-1] if created_ids else None,
        context_note_vi=f"Tách `{len(created_ids)}` công việc từ một tin nhắn · nối `{n_edges}` cạnh `depends_on` theo thứ tự (P10).",
        reply_vi=f"Đã thêm `{len(created_ids)}` công việc: {order_vi}.{default_vi}",
        pattern_rules=[P10_RULE] if n_edges else [],
        has_dag=bool(n_edges),
        extra_fields={"created_task_ids": created_ids},
    )


def _parse_batch_items(ctx: ChatTurnContext, result: IntentResult) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Turn a bulleted list or a prerequisite chain into ordered item dicts with dependency refs."""
    global_day, g_inf = _OFFLINE_NL.extract_deadline_day(ctx.norm, ctx.now_day)
    global_day = None if g_inf or global_day not in WEEKDAYS else global_day
    linked_existing: Optional[str] = None

    if result.batch_lines:
        header = "\n".join(ln for ln in ctx.prompt.splitlines() if ln.strip() and ln not in result.batch_lines)
        ordered = bool(_ORDERED_HEADER_RE.search(fold(header)))
        hdr_day, h_inf = _OFFLINE_NL.extract_deadline_day(fold(header), ctx.now_day) if header else (None, True)
        global_day = (hdr_day if (not h_inf and hdr_day in WEEKDAYS) else None) or global_day
        clauses = list(result.batch_lines)
    else:
        ordered = True
        clauses = _flatten_chain(ctx.prompt)
        if result.dependent_task_id and result.prerequisite is not None:
            # "<existing B> sau khi xong <new A>": only A is new; B gets linked to it
            clauses = _flatten_chain(result.prerequisite.prerequisite_text)
            linked_existing = result.dependent_task_id

    items: List[Dict[str, Any]] = []
    for idx, clause in enumerate(clauses):
        p = parse_task_clause(clause, ctx.now_day)
        if not p.title:
            continue
        it: Dict[str, Any] = {
            "title": p.title,
            "duration_min": p.duration_min,
            "deadline_day": p.deadline_day or global_day,
            "deadline_time": p.deadline_time,
            "category": p.category,
            "priority": p.priority,
            "cognitive_load": p.cognitive_load,
        }
        if items and (ordered or p.after_previous):
            it["depends_on_index"] = len(items) - 1
        if p.prerequisite_text:
            ref = _resolve_prereq_reference(p.prerequisite_text, items, ctx.tasks_raw)
            if isinstance(ref, int):
                it["depends_on_index"] = ref
            elif isinstance(ref, str):
                it["depends_on_existing"] = ref
        items.append(it)

    # A chain like "A rồi B trước thứ 6": the deadline sits on the last clause -> share it backwards
    shared_day = next((it["deadline_day"] for it in reversed(items) if it.get("deadline_day")), None)
    for it in items:
        if not it.get("deadline_day") and shared_day:
            it["deadline_day"] = shared_day
    return items, linked_existing


def _resolve_prereq_reference(text: str, items: List[Dict[str, Any]], tasks_raw: List[Dict[str, Any]]) -> Optional[Any]:
    pseudo = [
        enrich_task_trace_metadata({"task_id": f"__ITEM_{i}", "title": it["title"], "duration_min": 60})
        for i, it in enumerate(items)
    ]
    tr = resolve_target_task_from_prompt(text, pseudo)
    if tr.get("matched") and float(tr.get("confidence") or 0) >= 0.55:
        return int(str(tr["task_id"]).split("_")[-1])
    tr2 = resolve_target_task_from_prompt(text, tasks_raw)
    if tr2.get("matched") and float(tr2.get("confidence") or 0) >= 0.60:
        return str(tr2["task_id"])
    return None


# ---------------------------------------------------------------------------
# Attachment cross-check (Pattern P14a, consumes M7 `parse_document_constraint_digest`)
# ---------------------------------------------------------------------------


def digest_attachments(
    attachments: Any,
    parser: Optional[Callable[[str, Any], Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """Parse attachments and return the most informative compact digest (no raw text), or `None`."""
    if parser is None or not isinstance(attachments, list) or not attachments:
        return None
    best: Optional[Dict[str, Any]] = None
    for att in attachments:
        if not isinstance(att, dict):
            continue
        name = str(att.get("filename") or att.get("name") or "attachment.txt")
        content = att.get("content")
        if content is None:
            continue
        try:
            dg = parser(name, content)
        except Exception:
            continue
        total = int(dg.get("suggested_total_min") or 0)
        if total <= 0 or not dg.get("milestones"):
            continue
        if best is None or total > int(best["suggested_total_min"]):
            best = {
                "filename": name,
                "milestones": list(dg.get("milestones") or []),
                "suggested_total_min": total,
                "suggested_priority": int(dg.get("suggested_priority") or 3),
                "suggested_load": int(dg.get("suggested_load") or 2),
            }
    return best


def is_doc_underestimate(user_min: Optional[int], digest: Dict[str, Any]) -> bool:
    total = int(digest.get("suggested_total_min") or 0)
    return bool(user_min and total > 0 and user_min < DOC_UNDERESTIMATE_RATIO * total)


def detect_doc_choice(norm_prompt: str) -> Optional[str]:
    if _DOC_USE_RE.search(norm_prompt):
        return "USE_DOC"
    if _DOC_KEEP_RE.search(norm_prompt):
        return "KEEP_USER"
    return None


def doc_conflict_response(ctx: ChatTurnContext, draft: Dict[str, Any], digest: Dict[str, Any], user_min: int) -> Dict[str, Any]:
    total = int(digest["suggested_total_min"])
    n_ms = len(digest.get("milestones") or [])
    pend = dict(draft)
    pend["intent"] = "ADD_TASK"
    pend["doc_conflict"] = True
    pend["attachment_digest"] = digest
    return non_applied_response(
        ctx,
        status="NEEDS_CLARIFICATION",
        intent="ADD_TASK",
        reply_vi=(
            f"Bạn nhập **{user_min} phút** cho **{draft.get('title')}**, nhưng đề bài đính kèm "
            f"(`{digest['filename']}`) có `{n_ms}` phần việc, ước tính khoảng **{total} phút** — "
            f"thời lượng bạn nhập chưa bằng một nửa. Bạn muốn xếp theo cách nào?"
        ),
        quick_chips=[
            {"label": f"📑 Dùng {n_ms} mốc từ đề bài ({total} phút)", "prompt": "Dùng các mốc trong đề bài đính kèm"},
            {"label": f"✍️ Giữ thời lượng tự nhập ({user_min} phút)", "prompt": "Giữ thời lượng mình đã nhập"},
        ],
        pending_draft=pend,
        missing_fields=["doc_duration_choice"],
        conflict="USER_VS_DOC_UNDERESTIMATE",
        attachment_digest=digest,
    )


def build_milestone_tasks(
    tasks_raw: List[Dict[str, Any]],
    draft: Dict[str, Any],
    digest: Dict[str, Any],
    now_day: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Expand a digest into one task per milestone, chaining `depends_on_prev` edges (P10 + P14a)."""
    tasks = [dict(t) for t in tasks_raw]
    created: List[str] = []
    base_title = str(draft.get("title") or digest.get("filename") or "Đề bài")
    for i, ms in enumerate(digest.get("milestones") or []):
        tid = _new_task_id(tasks, salt=i)
        deps = [created[-1]] if (created and ms.get("depends_on_prev")) else []
        tasks.append(
            build_task_dict(
                task_id=tid,
                title=f"{base_title} · {ms.get('title') or f'Phần {i + 1}'}",
                duration_min=int(ms.get("estimated_min") or 60),
                deadline_day=str(draft.get("deadline_day") or now_day),
                deadline_time=str(draft.get("deadline_time") or "23:59"),
                category=str(draft.get("category") or "ASSIGNMENT"),
                priority=int(digest.get("suggested_priority") or draft.get("priority") or 3),
                cognitive_load=int(ms.get("cognitive_load") or 2),
                depends_on=deps,
            )
        )
        created.append(tid)
    return tasks, created
