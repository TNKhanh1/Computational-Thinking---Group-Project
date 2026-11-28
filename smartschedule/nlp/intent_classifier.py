"""
Deterministic Chat Intent Taxonomy (`smartschedule.nlp.intent_classifier`, owned by `M4`).

Pure regex + task-trace routing (`< 2 ms`, zero network, zero LLM) that maps one Vietnamese /
English chat turn onto exactly one intent:

  Lifecycle (M4)  : DELETE_ITEM, COMPLETE_TASK, QUERY_SCHEDULE, ADAPT_NEXT_WEEK,
                    BATCH_ADD_TASKS, LINK_DEPENDENCY
  Delegated       : DISRUPTION_REPAIR (-> M5), UPDATE_PROFILE_HABIT (-> M3)
  Legacy (v0.9)   : ADJUST_DEADLINE, MODIFY_HIDDEN, ADD_RECURRING, ADD_TASK

Priority order matters (CT: *lexicographic decision list* — the first rule that fires wins, so
every prompt has exactly one owner): an explicit cancel/delete must never be mistaken for a new
busy event, and a prerequisite chain "xong A rồi mới làm B" must never be read as "A is done".

Layering: `nlp` may import `core` (never the reverse) and never imports `api`. Detectors owned by
other members (`M5` disruption, `M3` profile/habit) are *injected* as callables by `handlers.py`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from smartschedule.core.task_tracer import resolve_target_task_from_prompt

# ---------------------------------------------------------------------------
# Accent folding with an index map (so spans found on folded text can be cut
# from the original Vietnamese string without losing diacritics).
# ---------------------------------------------------------------------------


def fold_with_index(text: str) -> Tuple[str, List[int]]:
    """Lower-case + strip Vietnamese accents char-by-char; `idx[i]` = original index of folded char `i`."""
    out_chars: List[str] = []
    idx_map: List[int] = []
    for i, ch in enumerate(text or ""):
        if ch in ("đ", "Đ"):
            base = "d"
        else:
            base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        for b in base.lower():
            out_chars.append(b)
            idx_map.append(i)
    return "".join(out_chars), idx_map


def fold(text: str) -> str:
    return fold_with_index(text)[0]


def slice_original(text: str, idx_map: List[int], f_start: int, f_end: int) -> str:
    """Return the original-text substring covering folded span `[f_start, f_end)`."""
    if f_start >= f_end or not idx_map:
        return ""
    o_start = idx_map[max(0, min(f_start, len(idx_map) - 1))]
    o_end = idx_map[min(f_end, len(idx_map)) - 1] + 1
    return text[o_start:o_end]


# ---------------------------------------------------------------------------
# Rule lexicon (all patterns run on folded, lower-case text)
# ---------------------------------------------------------------------------

_DELETE_RE = re.compile(
    r"^\s*(?:(?:minh|toi|em|ban|cho\s+minh|giup\s+minh|hay)\s+)?(?:muon\s+|can\s+)?"
    r"(?:xoa(?:\s*bo)?|go\s*bo|loai\s*bo|bo\s+(?:bai|viec|lich|task|mon|su\s*kien|cong\s*viec)|"
    r"huy(?:\s*bo)?\s+(?!thao\s*tac\b|bao\s*ban\b)\S|delete|remove)"
    r"|\bkhong\s+(?:can|phai)\s+(?:lam|hoc|di|hop)\b.*\bnua\b"
)
_CANCEL_ONLY_RE = re.compile(r"^\s*(?:huy|huy\s*bo|huy\s*thao\s*tac|thoi|bo\s*qua|cancel|stop|lam\s*lai)\s*[.!]?\s*$")

_COMPLETE_RE = re.compile(
    r"\b(?:da\s+|vua\s+)?(?:lam|hoc|viet|code|lam\s+bai|nop|on|doc|chay|test)?\s*xong\s*(?:roi|het|xuoi|ca)?\b\s*[.!]*\s*$"
    r"|\b(?:da|vua)\s+(?:lam\s+)?xong\b"
    r"|\b(?:da|vua)\s+hoan\s*thanh\b(?!.*\b(?:truoc|roi\s+moi|moi\s+(?:lam|hoc|viet))\b)"
    r"|\bhoan\s*thanh\b[^.?!]*\b(?:roi|xong)\b(?!\s+moi)(?!.*\bmoi\b)"
    r"|\b(?:da\s+)?nop\s+(?:bai\s+)?(?:roi|xong)\b"
    r"|\bdone\b|\bfinished\b|\bcompleted\b"
    r"|\bxong\s+(?:bai|viec|task|phan|mon)\b.*\broi\b(?!\s+moi)"
    r"|^\s*(?:(?:minh|toi|em)\s+)?(?:da\s+|vua\s+)?(?:lam|hoc|viet|code|nop|on|doc|chay|test)\s+xong\b(?!.*\b(?:moi|sau\s+do|tiep\s+theo)\b)"
    r"|\bxong\b[^.?!]*\broi\b(?!\s+(?:moi|sau))(?!.*\bmoi\b)"
)
_PARTIAL_PROGRESS_RE = re.compile(r"\b(?:moi\s+lam\s+duoc|con\s+lai|lam\s+tiep|duoc\s+(?:mot\s+)?nua|\d+\s*%)\b")

_QUERY_RE = re.compile(
    r"\b(?:co\s+(?:lich|viec|gi|bai|mon|task)(?:\s+gi)?|lich\s+(?:ra\s+sao|the\s+nao|nhu\s+the\s+nao)|"
    r"xem\s+lich|lich\s+(?:hom\s*nay|ngay\s*mai|mai|tuan\s*nay|thu\s*(?:[2-7]|hai|ba|tu|nam|sau|bay)|chu\s*nhat)|"
    r"(?:phai|can|se)\s+lam\s+(?:gi|nhung\s+gi|viec\s+gi)|nhung\s+(?:viec|gi|bai)\s+nao|bao\s+nhieu\s+(?:viec|bai|task)|"
    r"what(?:'s|\s+is)?\s+(?:on\s+)?(?:my\s+)?schedule|show\s+(?:my\s+)?schedule)\b"
    r"|\?\s*$"
)
_ADD_SIGNAL_RE = re.compile(r"^\s*(?:them|tao|add|create|len\s*lich|dat\s*lich)\b")

_ADAPT_RE = re.compile(
    r"(?:\b(?:tuan\s*(?:sau|toi|ke\s*tiep)|next\s+week)\b.*\b(?:toi\s*uu|rut\s*kinh\s*nghiem|hoc|thich\s*nghi|dieu\s*chinh|"
    r"cai\s*thien|adapt|optimi[sz]e|learn)\b)"
    r"|(?:\b(?:toi\s*uu|rut\s*kinh\s*nghiem|hoc|thich\s*nghi|dieu\s*chinh|cai\s*thien|adapt|optimi[sz]e|learn)\b.*\b(?:tuan\s*(?:sau|toi|ke\s*tiep)|next\s+week)\b)"
    r"|\b(?:thoi\s*quen|lich\s*su|history|habits?)\s+(?:cua\s+)?tuan\s*(?:truoc|nay|vua\s*roi)\b"
    r"|\bap\s*dung\s+(?:thich\s*nghi|hoc\s+thich\s*nghi|de\s*xuat\s+tuan\s*sau)\b"
)

# Prerequisite chains (Pattern P10). Each returns (prerequisite_span, dependent_span) on folded text.
_CHAIN_PATTERNS: Tuple[Tuple[re.Pattern, str], ...] = (
    # "sau khi (lam) xong A, (thi) B"  -> B depends on A
    (re.compile(r"^\s*sau\s+khi\s+(?:lam\s+|hoc\s+|viet\s+)?(?:xong|hoan\s*thanh)\s+(?P<pre>.+?)\s*(?:,|\bthi\b|\broi\b)\s*(?P<dep>.+)$"), "PRE_FIRST"),
    # "B sau khi (lam) xong A"
    (re.compile(r"^(?P<dep>.+?)\s+(?:sau\s+khi|after\s+finishing)\s+(?:lam\s+|hoc\s+|viet\s+)?(?:xong\s+|hoan\s*thanh\s+)?(?P<pre>.+)$"), "DEP_FIRST"),
    # "(lam) xong A (roi) moi (lam) B" / "hoan thanh A truoc roi moi B"
    (re.compile(r"^\s*(?:(?:phai|can)\s+)?(?:lam\s+|hoc\s+|viet\s+)?(?:xong|hoan\s*thanh)\s+(?P<pre>.+?)\s+(?:truoc\s+)?(?:roi\s+)?moi\s+(?:duoc\s+)?(?P<dep>.+)$"), "PRE_FIRST"),
    # "A xong roi moi B" / "A truoc roi moi B" / "A roi sau do B" / "A, sau do B"
    (re.compile(r"^(?P<pre>.+?)\s+(?:xong\s+)?(?:truoc\s+)?roi\s+(?:moi|sau\s+do)\s+(?P<dep>.+)$"), "PRE_FIRST"),
    (re.compile(r"^(?P<pre>.+?)\s*(?:,|;)\s*(?:xong\s+)?(?:roi\s+)?sau\s+do\s+(?P<dep>.+)$"), "PRE_FIRST"),
    # "B depends on A"
    (re.compile(r"^(?P<dep>.+?)\s+depends?\s+on\s+(?P<pre>.+)$"), "DEP_FIRST"),
)

_BULLET_LINE_RE = re.compile(r"^\s*(?:[-*•+]|\d{1,2}\s*[.)]|[a-e]\s*[.)])\s+\S")


@dataclass
class PrerequisiteSplit:
    """A single `prerequisite -> dependent` clause pair cut from the original prompt."""

    prerequisite_text: str
    dependent_text: str
    order: str  # "PRE_FIRST" | "DEP_FIRST" (surface order in the sentence)


@dataclass
class IntentResult:
    intent: str
    confidence: float
    cues: List[str] = field(default_factory=list)
    prerequisite: Optional[PrerequisiteSplit] = None
    prerequisite_task_id: Optional[str] = None
    dependent_task_id: Optional[str] = None
    batch_lines: List[str] = field(default_factory=list)


def split_prerequisite_clause(prompt: str) -> Optional[PrerequisiteSplit]:
    """Detect a single prerequisite chain (`P10`) and return both clauses in original (accented) text."""
    folded, idx_map = fold_with_index(prompt.strip())
    original = prompt.strip()
    for pat, order in _CHAIN_PATTERNS:
        m = pat.match(folded)
        if not m:
            continue
        pre = slice_original(original, idx_map, m.start("pre"), m.end("pre")).strip(" ,.;:-")
        dep = slice_original(original, idx_map, m.start("dep"), m.end("dep")).strip(" ,.;:-")
        if len(fold(pre)) >= 2 and len(fold(dep)) >= 2:
            return PrerequisiteSplit(prerequisite_text=pre, dependent_text=dep, order=order)
    return None


def extract_batch_lines(prompt: str) -> List[str]:
    """Return bulleted / numbered item lines (>= 2) of a multi-line prompt, else `[]`."""
    lines = [ln for ln in (prompt or "").splitlines() if ln.strip()]
    items = [ln for ln in lines if _BULLET_LINE_RE.match(fold(ln))]
    return items if len(items) >= 2 else []


def _match_existing(text: str, tasks: List[Dict[str, Any]], min_conf: float = 0.60) -> Optional[str]:
    if not text or not tasks:
        return None
    tr = resolve_target_task_from_prompt(text, tasks)
    if tr.get("matched") and float(tr.get("confidence") or 0.0) >= min_conf:
        return tr.get("task_id")
    return None


def classify_intent(
    prompt: str,
    *,
    mode_hint: str = "AUTO",
    pending_draft: Optional[Dict[str, Any]] = None,
    tasks: Optional[List[Dict[str, Any]]] = None,
    last_task_id: Optional[str] = None,
    legacy_detector: Optional[Callable[[], str]] = None,
    disruption_detector: Optional[Callable[[str], bool]] = None,
    profile_detector: Optional[Callable[[str], bool]] = None,
) -> IntentResult:
    """
    Deterministic first-match decision list. `legacy_detector()` is the v0.9 router
    (ADJUST_DEADLINE / ADD_RECURRING / MODIFY_HIDDEN / ADD_TASK) used as the final fallback.
    """
    tasks = tasks or []
    norm = fold(prompt or "").strip()
    hint = (mode_hint or "AUTO").strip().upper()

    if pending_draft and pending_draft.get("intent"):
        return IntentResult(str(pending_draft["intent"]), 1.0, ["pending_draft"])
    if hint not in ("", "AUTO"):
        mapped = {"DISRUPTION": "DISRUPTION_REPAIR"}.get(hint, hint)
        return IntentResult(mapped, 1.0, [f"mode_hint:{hint}"])
    if not norm or _CANCEL_ONLY_RE.match(norm):
        return IntentResult("ADD_TASK", 0.2, ["empty_or_cancel"])

    batch_lines = extract_batch_lines(prompt)
    if batch_lines:
        return IntentResult("BATCH_ADD_TASKS", 0.95, ["bulleted_list"], batch_lines=batch_lines)

    if _ADAPT_RE.search(norm):
        return IntentResult("ADAPT_NEXT_WEEK", 0.9, ["adapt_next_week_cue"])

    if _DELETE_RE.search(norm):
        return IntentResult("DELETE_ITEM", 0.9, ["delete_verb"])

    split = split_prerequisite_clause(prompt)
    if split is not None:
        pre_id = _match_existing(split.prerequisite_text, tasks)
        dep_id = _match_existing(split.dependent_text, tasks)
        if pre_id and dep_id and pre_id != dep_id:
            return IntentResult(
                "LINK_DEPENDENCY", 0.9, ["prerequisite_chain", "both_exist"],
                prerequisite=split, prerequisite_task_id=pre_id, dependent_task_id=dep_id,
            )
        if not pre_id and not dep_id:
            return IntentResult("BATCH_ADD_TASKS", 0.85, ["prerequisite_chain", "both_new"], prerequisite=split)
        if pre_id and not dep_id:
            return IntentResult("ADD_TASK", 0.85, ["prerequisite_chain", "prereq_exists"], prerequisite=split, prerequisite_task_id=pre_id)
        # dependent exists but prerequisite is new -> add the new prerequisite and link the existing dependent
        return IntentResult("BATCH_ADD_TASKS", 0.75, ["prerequisite_chain", "dependent_exists"], prerequisite=split, dependent_task_id=dep_id)

    if _COMPLETE_RE.search(norm) and not _PARTIAL_PROGRESS_RE.search(norm):
        return IntentResult("COMPLETE_TASK", 0.85, ["completion_cue"])

    if _QUERY_RE.search(norm) and not _ADD_SIGNAL_RE.match(norm):
        return IntentResult("QUERY_SCHEDULE", 0.8, ["question_cue"])

    if disruption_detector is not None:
        try:
            if disruption_detector(prompt):
                return IntentResult("DISRUPTION_REPAIR", 0.8, ["m5_detector"])
        except Exception:
            pass
    if profile_detector is not None:
        try:
            if profile_detector(prompt):
                return IntentResult("UPDATE_PROFILE_HABIT", 0.8, ["m3_detector"])
        except Exception:
            pass

    legacy = legacy_detector() if legacy_detector is not None else "ADD_TASK"
    return IntentResult(legacy, 0.6, ["legacy_router"])
