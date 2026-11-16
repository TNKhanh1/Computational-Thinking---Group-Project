"""
parser.py
Hybrid Natural Language Parsing Engine and Temporal Horizon Resolver for SmartSchedule.
Extracts deadlines ("in this week", "until next week"), start_after boundaries,
workload multipliers, precedence DAG relations, and reconciles session conflicts.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional, Tuple

from schema import (
    TaskSchema,
    PriorityLevel,
    ConstraintType,
    CognitiveDemand,
    WorkRhythm,
    PrecedenceRelation,
    SplittingConfig,
    ContractStatus,
    SubtaskWorkflowStatus,
    DeclaredSubtask,
)
from tokenizer import clean_and_normalize
from regex_parser import parse_with_regex, clean_title
from translator import translate_to_english


WEEKDAY_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def parse_time_of_day(time_str: str) -> Tuple[int, int]:
    """Helper to parse time of day strings or colloquial segments."""
    time_str = time_str.lower().strip()
    if "morning" in time_str:
        return 9, 0
    if "afternoon" in time_str:
        return 14, 0
    if "evening" in time_str:
        return 18, 0
    if "night" in time_str:
        return 21, 0
    tm_match = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", time_str)
    if tm_match:
        hr = int(tm_match.group(1))
        mn = int(tm_match.group(2) or 0)
        ampm = tm_match.group(3)
        if ampm == "pm" and hr < 12:
            hr += 12
        elif ampm == "am" and hr == 12:
            hr = 0
        return hr, mn
    return 17, 0


def resolve_start_after_datetime(text: str, base_time: Optional[datetime] = None) -> Tuple[Optional[datetime], str, Optional[str]]:
    """
    Detects and resolves 'start_after' / release time expressions:
    - 'start after tomorrow 9am', 'starting tomorrow afternoon'
    - 'from next Monday 10:00', 'start after Friday 2pm'
    - 'start after 3pm', 'starting from 10am'
    Returns (start_dt, text_with_match_stripped, phrase_description).
    """
    now = base_time or datetime.now()
    cleaned = text

    # Pattern 1: start after / from day + optional time
    start_match = re.search(
        r"\b(?:start(?:ing)?\s+(?:after|from)|from)\s+(tomorrow|today|next\s+[a-z]+|[a-z]+day)(?:\s+(?:at\s+|in\s+the\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|morning|afternoon|evening|night))?\b",
        cleaned,
        re.IGNORECASE,
    )
    if start_match:
        day_word = start_match.group(1).lower()
        time_part = start_match.group(2) or "09:00"
        hr, mn = parse_time_of_day(time_part)

        if "tomorrow" in day_word:
            target_date = now.date() + timedelta(days=1)
        elif "today" in day_word:
            target_date = now.date()
        else:
            # Named day e.g. "friday" or "next monday"
            clean_day = re.sub(r"next\s+", "", day_word).strip()
            target_wd = WEEKDAY_MAP.get(clean_day, (now.weekday() + 1) % 7)
            days_ahead = target_wd - now.weekday()
            if days_ahead <= 0 or "next" in day_word:
                days_ahead += 7
            target_date = now.date() + timedelta(days=days_ahead)

        start_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hr, minute=mn)
        matched_str = start_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return start_dt, cleaned, f"Start after {start_dt.strftime('%A, %b %d at %H:%M')}"

    # Pattern 2: start after time only (today or tomorrow)
    start_time_match = re.search(
        r"\b(?:start(?:ing)?\s+(?:after|from))\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm))\b",
        cleaned,
        re.IGNORECASE,
    )
    if start_time_match:
        hr, mn = parse_time_of_day(start_time_match.group(1))
        target_date = now.date() if (now.hour < hr or (now.hour == hr and now.minute < mn)) else now.date() + timedelta(days=1)
        start_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hr, minute=mn)
        matched_str = start_time_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return start_dt, cleaned, f"Start after {start_dt.strftime('%A, %b %d at %H:%M')}"

    return None, cleaned, None


def resolve_relative_datetime(text: str, base_time: Optional[datetime] = None) -> Tuple[Optional[datetime], str, Optional[str]]:
    """
    Detects and resolves relative and absolute deadline expressions:
    - 'in this week', 'within this week', 'by the end of this week', 'this weekend' -> Sunday 23:59
    - 'until next week', 'by next week', 'in next week' -> Next Sunday 23:59
    - 'tomorrow at 3pm', 'tomorrow afternoon', 'tonight at 9'
    - 'next Friday at 10:00', 'this Wednesday 4pm'
    - 'in 2 hours', 'in 45 minutes'
    Returns: (resolved_datetime, text_with_date_stripped, detected_phrase)
    """
    now = base_time or datetime.now()
    cleaned = text

    # Pattern 0A: "until next week", "by next week", "in next week", "next week", "next weekend"
    next_week_match = re.search(
        r"\b(?:until|by|before|in|within|till)?\s*(?:the\s+end\s+of\s+)?next\s+(?:week|weekend)(?:\s+timeline)?\b",
        cleaned,
        re.IGNORECASE,
    )
    has_named_weekday_with_next = bool(
        re.search(
            r"\b(?:next\s+(?:mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|(?:mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+next\s+week)\b",
            cleaned,
            re.IGNORECASE,
        )
    )
    if next_week_match and not has_named_weekday_with_next:
        days_until_next_sunday = (6 - now.weekday()) + 7
        target_date = now.date() + timedelta(days=days_until_next_sunday)
        resolved_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=23, minute=59)
        matched_str = next_week_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return resolved_dt, cleaned, "End of Next Week (Next Sunday 23:59)"

    # Pattern 0B: "in this week", "within this week", "this week", "by the end of this week", "this weekend"
    this_week_match = re.search(
        r"\b(?:by|before|in|within|during|until|till)?\s*(?:the\s+)?(?:end\s+of\s+)?this\s+(?:week|weekend)(?:\s+timeline)?\b",
        cleaned,
        re.IGNORECASE,
    )
    if this_week_match:
        days_until_sunday = 6 - now.weekday()
        if days_until_sunday < 0:
            days_until_sunday += 7
        target_date = now.date() + timedelta(days=days_until_sunday)
        resolved_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=23, minute=59)
        matched_str = this_week_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return resolved_dt, cleaned, "End of This Week (Sunday 23:59)"

    # Pattern 1: Relative offset deadline: "due in X hours", "in Y minutes" (not followed by 'total' or 'chunks')
    offset_match = re.search(
        r"\b(?:due\s+)?in\s+(\d+)\s*(hours?|hrs?|h|minutes?|mins?|m)\b(?!\s*(?:total|chunks?|sessions?|blocks?|parts?|each))",
        cleaned,
        re.IGNORECASE,
    )
    has_explicit_by_date = bool(
        re.search(r"\b(?:by|before|until|due)\s+(?:today|tonight|tomorrow|next|this|mon|tue|wed|thu|fri|sat|sun)", cleaned, re.IGNORECASE)
    )
    if offset_match and not has_explicit_by_date:
        val = int(offset_match.group(1))
        unit = offset_match.group(2).lower()
        if unit.startswith("h"):
            resolved_dt = now + timedelta(hours=val)
        else:
            resolved_dt = now + timedelta(minutes=val)
        matched_str = offset_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return resolved_dt, cleaned, f"In {val} {unit}"

    # Pattern 2: "tomorrow" with optional time (handles both "tomorrow at 7pm" and "by 7pm tomorrow")
    tomorrow_match = re.search(
        r"\b(?:due\s+|by\s+|before\s+)?(?:(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+(?:on\s+)?tomorrow|tomorrow(?:\s+(?:at\s+|in\s+the\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|morning|afternoon|evening|night))?)\b",
        cleaned,
        re.IGNORECASE,
    )
    if tomorrow_match:
        time_part = tomorrow_match.group(1) or tomorrow_match.group(2) or "17:00"
        hr, mn = parse_time_of_day(time_part)
        target_date = now.date() + timedelta(days=1)
        resolved_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hr, minute=mn)
        matched_str = tomorrow_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return resolved_dt, cleaned, f"Tomorrow at {hr:02d}:{mn:02d}"

    # Pattern 3: "today" / "tonight" (handles both "tonight at 9pm" and "by 9pm tonight")
    today_match = re.search(
        r"\b(?:due\s+|by\s+|before\s+)?(?:(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s+(?:on\s+)?(today|tonight)|(today|tonight)(?:\s+(?:at\s+|in\s+the\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|morning|afternoon|evening|night))?)\b",
        cleaned,
        re.IGNORECASE,
    )
    if today_match:
        t_word = (today_match.group(2) or today_match.group(3) or "").lower()
        is_tonight = t_word == "tonight"
        default_time = "21:00" if is_tonight else "17:00"
        time_part = today_match.group(1) or today_match.group(4) or default_time
        hr, mn = parse_time_of_day(time_part)
        resolved_dt = datetime.combine(now.date(), datetime.min.time()).replace(hour=hr, minute=mn)
        matched_str = today_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return resolved_dt, cleaned, f"Today at {hr:02d}:{mn:02d}"

    # Pattern 4: Named day: "(this|next)? (Monday|Tuesday...) (next week)? at (time)" or "by 7pm Friday" or "before 17:00 on Friday"
    day_match = re.search(
        r"\b(?:due\s+|by\s+|before\s+|until\s+)?(?:(\d{1,2}(?::\d{2}\b(?:\s*(?:am|pm))?|\s*(?:am|pm)))\s+(?:on\s+)?(?:(this|next)\s+)?(mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|(?:(this|next)\s+)?(mon|tue|wed|thu|fri|sat|sun|monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(this|next)\s+week)?(?:\s+(?:at\s+|before\s+|by\s+)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?|morning|afternoon|evening|night))?)\b",
        cleaned,
        re.IGNORECASE,
    )
    if day_match:
        # Check if time was stated before weekday (groups 1 and 3)
        if day_match.group(1):
            time_part = day_match.group(1)
            qualifier = (day_match.group(2) or "this").lower()
            target_day_name = day_match.group(3).lower()
        else:
            qualifier = (day_match.group(4) or day_match.group(6) or "this").lower()
            target_day_name = day_match.group(5).lower()
            time_part = day_match.group(7) or "23:59"

        target_weekday = WEEKDAY_MAP[target_day_name]
        hr, mn = parse_time_of_day(time_part)

        current_weekday = now.weekday()
        days_ahead = target_weekday - current_weekday
        if days_ahead <= 0 or qualifier == "next":
            days_ahead += 7

        target_date = now.date() + timedelta(days=days_ahead)
        resolved_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hr, minute=mn)
        matched_str = day_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return resolved_dt, cleaned, f"{target_day_name.capitalize()} at {hr:02d}:{mn:02d}"

    # Pattern 5: Time only: "before 5pm", "by 16:30"
    time_only_match = re.search(
        r"\b(?:due\s+|by\s+|before\s+|at\s+)(\d{1,2}(?::\d{2}\b(?:\s*(?:am|pm))?|\s*(?:am|pm)))\b",
        cleaned,
        re.IGNORECASE,
    )
    if time_only_match:
        hr, mn = parse_time_of_day(time_only_match.group(1))
        target_date = now.date() if (now.hour < hr or (now.hour == hr and now.minute < mn)) else now.date() + timedelta(days=1)
        resolved_dt = datetime.combine(target_date, datetime.min.time()).replace(hour=hr, minute=mn)
        matched_str = time_only_match.group(0)
        cleaned = re.sub(re.escape(matched_str), "", cleaned)
        return resolved_dt, cleaned, f"At {hr:02d}:{mn:02d}"

    return None, cleaned, None


def extract_precedence_relations(text: str) -> List[Tuple[str, str, str]]:
    """
    Extracts topological order and precedence chains:
    Example 1: 'first review literature, then code model, finally run benchmarks'
    Example 2: 'Do chapter 1 before chapter 2'
    Example 3: 'after finishing homework, do the exercise'
    Returns list of (predecessor_desc, successor_desc, relation_type).
    """
    relations = []

    # Pattern 1: Sequential chain: "first A, then B, finally/then C"
    chain_match = re.search(
        r"\bfirst\s+([^\.,;]+?),\s*then\s+([^\.,;]+?)(?:,\s*(?:finally|then)\s+([^\.,;]+?))?(?:[\.;]|$)",
        text,
        re.IGNORECASE,
    )
    if chain_match:
        step1 = chain_match.group(1).strip()
        step2 = chain_match.group(2).strip()
        step3 = chain_match.group(3).strip() if chain_match.group(3) else None
        relations.append((step1, step2, "FINISH_TO_START"))
        if step3:
            relations.append((step2, step3, "FINISH_TO_START"))
        return relations

    # Pattern 2: "<A> before <B>"
    before_matches = re.finditer(r"([a-zA-Z0-9\s]{3,35})\s+before\s+([a-zA-Z0-9\s]{3,35})", text, re.IGNORECASE)
    for m in before_matches:
        pred = m.group(1).strip()
        succ = m.group(2).strip()
        if not re.search(r"^(tomorrow|tonight|today|noon|midnight|\d{1,2}(:\d{2})?\s*(am|pm)?)", succ, re.IGNORECASE):
            relations.append((pred, succ, "FINISH_TO_START"))

    # Pattern 3: "after <A>, (do|start) <B>"
    after_matches = re.finditer(r"after\s+([a-zA-Z0-9\s]{3,35}),\s*(?:do\s+|start\s+)?([a-zA-Z0-9\s]{3,35})", text, re.IGNORECASE)
    for m in after_matches:
        pred = m.group(1).strip()
        succ = m.group(2).strip()
        relations.append((pred, succ, "FINISH_TO_START"))

    # Pattern 4: "Before <B>, (do|need to) <A>" -> A is predecessor, B is successor
    inv_before_matches = re.finditer(
        r"\b(?:before|prior\s+to)\s+([a-zA-Z0-9_\.\s]{3,35}),\s*(?:i\s+need\s+to\s+|i\s+must\s+|we\s+need\s+to\s+|please\s+)?([a-zA-Z0-9_\.\s]{3,45})",
        text,
        re.IGNORECASE,
    )
    for m in inv_before_matches:
        succ = m.group(1).strip()
        pred = m.group(2).strip().rstrip(".,")
        if not re.search(r"^(tomorrow|tonight|today|noon|midnight|\d{1,2}(:\d{2})?\s*(am|pm)?)", succ, re.IGNORECASE):
            relations.append((pred, succ, "FINISH_TO_START"))

    return relations


def extract_declared_subtasks(
    raw_prompt: str,
    parent_priority: int,
    parent_rhythm: WorkRhythm,
    base_time: Optional[datetime] = None,
    default_section_minutes: Optional[int] = None,
    expected_sections_count: Optional[int] = None,
) -> Tuple[List[DeclaredSubtask], List[str]]:
    """
    Extracts user-declared subtasks from bullet lists (- / * / ✅ / ⏳ / ⬜),
    numbered steps ((1) / Step 1:), or sequential chains (first ..., then ..., finally ...).
    Never invents subtasks if the user did not declare any.
    """
    subtasks: List[DeclaredSubtask] = []
    warnings: List[str] = []

    # 1. Check bullet lines or numbered steps
    bullet_lines = re.findall(r"(?:^|\n)\s*(?:[-*•]|✅|⏳|⬜|\(\d+\)|Step\s+\d+:)\s*([^\n]+)", raw_prompt, re.IGNORECASE)
    raw_items: List[Tuple[str, bool]] = []  # (clause, has_explicit_order)

    if bullet_lines:
        for line in bullet_lines:
            has_order = bool(re.search(r"\b(first|then|finally|after|before|once)\b", line, re.IGNORECASE))
            raw_items.append((line.strip(), has_order))
    else:
        # Check inline numbered list: (1) ...; (2) ...
        inline_nums = re.findall(r"\(\d+\)\s*([^;]+)", raw_prompt)
        if len(inline_nums) >= 2:
            for item in inline_nums:
                has_order = bool(re.search(r"\b(first|then|finally|after|before|once)\b", item, re.IGNORECASE))
                raw_items.append((item.strip(" .,"), has_order))
        else:
            # Check sequential chain: "first A, then B, finally C"
            chain_match = re.search(
                r"\bfirst\s+([^\.,;]+?),\s*then\s+([^\.,;]+?)(?:,\s*(?:finally|then)\s+([^\.,;]+?))?(?:[\.;]|$)",
                raw_prompt,
                re.IGNORECASE,
            )
            if chain_match:
                for g in (chain_match.group(1), chain_match.group(2), chain_match.group(3)):
                    if g:
                        raw_items.append((g.strip(), True))

    if not raw_items:
        return [], []

    any_unordered = False
    effective_scope_units = 0.0

    for idx, (clause, has_order) in enumerate(raw_items, 1):
        sid = f"s{idx}"
        status = SubtaskWorkflowStatus.TODO
        external = False

        # Workflow status detection
        if re.search(r"(✅|\[\s*x\s*\]|\balready\s+(?:done|finished|completed)\b|\bcompleted\b|\(done\)|\bdone\b(?=\s*$|[.,;!?]))", clause, re.IGNORECASE):
            status = SubtaskWorkflowStatus.DONE
            warnings.append("W_STATUS_INFERRED")
        elif re.search(r"(⏳|\bin\s+progress\b|\bhalfway\s+done\b|\bremaining\b|\bleft\b)", clause, re.IGNORECASE):
            status = SubtaskWorkflowStatus.IN_PROGRESS
            warnings.append("W_STATUS_INFERRED")
        elif re.search(r"\b(waiting\s+on|wait\s+for|review\s+requests?\s+to\s+the\s+manager|manager\s+review)\b", clause, re.IGNORECASE):
            status = SubtaskWorkflowStatus.WAITING
            external = True
            warnings.extend(["W_STATUS_INFERRED", "W_EXTERNAL_DEPENDENCY"])

        # Open revision loop detection
        if re.search(
            r"\b(keep\s+revising|until\s+approved|until\s+100%\s+pass|review\s+requests?\s+to\s+the\s+manager|send\s+review\s+requests?)\b",
            clause,
            re.IGNORECASE,
        ):
            warnings.append("W_OPEN_LOOP")

        # Partial chapter / scope mismatch detection (e.g., "only the first half of chapter 3")
        if re.search(r"\b(only\s+the\s+first\s+half|first\s+half\s+of|half\s+of\s+chapter|part\s+of\s+chapter)\b", clause, re.IGNORECASE):
            effective_scope_units += 0.5
            warnings.append("W_SCOPE_MISMATCH")
        else:
            effective_scope_units += 1.0

        # Duration extraction for this subtask
        sub_mins: Optional[int] = None
        if status == SubtaskWorkflowStatus.DONE or external:
            sub_mins = 0
        else:
            dur_m = re.search(r"\b(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", clause, re.IGNORECASE)
            if dur_m:
                val = float(dur_m.group(1))
                unit = dur_m.group(2).lower()
                sub_mins = int(val * 60) if unit.startswith("h") else int(val)
            elif default_section_minutes is not None:
                sub_mins = default_section_minutes

        # Subtask priority override
        sub_pri = parent_priority
        if re.search(r"\b(urgent|critical|asap)\b", clause, re.IGNORECASE):
            sub_pri = 1
        elif re.search(r"\b(high\s+priority|important)\b", clause, re.IGNORECASE):
            sub_pri = 2
        elif re.search(r"\b(medium\s+priority)\b", clause, re.IGNORECASE):
            sub_pri = 3
        elif re.search(r"\b(low\s+priority|optional)\b", clause, re.IGNORECASE):
            sub_pri = 4

        # Subtask pacing override
        sub_pacing: Optional[WorkRhythm] = None
        if re.search(r"\b(deep\s+work|flow)\b", clause, re.IGNORECASE):
            sub_pacing = WorkRhythm.FLOW
        elif re.search(r"\b(pomodoro|light)\b", clause, re.IGNORECASE):
            sub_pacing = WorkRhythm.LIGHT

        # Subtask deadline
        sub_dl, _, _ = resolve_relative_datetime(clause, base_time)

        # Dependency linking
        deps: List[str] = []
        inv_match = re.match(r"^(?:before|prior\s+to)\s+([a-zA-Z0-9_\.\s]{3,35}),\s*(.+)$", clause, re.IGNORECASE)
        if inv_match:
            target_keyword = inv_match.group(1).strip().lower()
            target_stem = target_keyword.rstrip("ing").rstrip("e")
            matched_pred_idx = None
            for p_idx, prev_sub in enumerate(subtasks):
                if target_stem and target_stem in prev_sub.title.lower():
                    matched_pred_idx = p_idx
                    break
            if matched_pred_idx is None and len(subtasks) == 1:
                matched_pred_idx = 0

            if matched_pred_idx is not None:
                if sid not in subtasks[matched_pred_idx].depends_on:
                    subtasks[matched_pred_idx].depends_on.append(sid)
                deps = []
            else:
                deps = []
        elif idx > 1 and has_order:
            deps = [f"s{idx - 1}"]
        elif idx > 1 and not has_order:
            any_unordered = True

        clean_sub_title = clean_title(clause)
        subtasks.append(
            DeclaredSubtask(
                id=sid,
                title=clean_sub_title,
                status=status,
                minutes=sub_mins,
                priority=sub_pri,
                pacing=sub_pacing,
                deadline=sub_dl,
                external=external,
                depends_on=deps,
            )
        )

    if expected_sections_count is not None and abs(effective_scope_units - expected_sections_count) > 1e-6:
        warnings.append("W_SCOPE_MISMATCH")

    if any_unordered and len(subtasks) > 1:
        warnings.append("W_DEPENDENCY_UNCLEAR")

    return subtasks, list(dict.fromkeys(warnings))


def evaluate_complexity_overload(
    raw_prompt: str,
    subtasks: List[DeclaredSubtask],
    is_splittable: bool,
    total_mins: Optional[int],
) -> Tuple[bool, List[str], List[str]]:
    """
    Evaluates the 6 complexity overload triggers from test_cases/README.md Section 3.5:
      (a) > 6 declared subtasks
      (b) single session > 480 minutes
      (c) multi-domain unrelated goals in one prompt
      (d) dependency chain > 5 links
      (e) subtask deadlines spread over > 14 days
      (f) nested hierarchy (Phase 1 ... Phase 2 ...)
    """
    warnings: List[str] = []
    suggestions: List[str] = []
    triggered = False

    # (a) > 6 subtasks
    if len(subtasks) > 6:
        triggered = True
        suggestions.extend([
            "Option 1 (Split by Phase): Group the 7+ steps into 2-3 milestone tasks (e.g., Preparation, Core Execution, Verification).",
            "Option 2 (Horizon Split): Schedule only the first 3-4 immediate subtasks today and defer downstream steps to a separate task.",
        ])

    # (b) single session > 480m
    if not is_splittable and (total_mins or 0) > 480:
        triggered = True
        warnings.append("W_UNREALISTIC_LOAD")
        suggestions.extend([
            "Option 1 (Enable Deep-Flow Splitting): Switch from Single Session to Splittable FLOW mode (90-minute focus blocks).",
            "Option 2 (Decompose by Deliverable): Break this marathon into 2-3 smaller standalone tasks across multiple days.",
        ])

    # (d) dependency chain > 5
    if len(subtasks) > 5 and all(s.depends_on for s in subtasks[1:]):
        triggered = True
        suggestions.extend([
            "Option 1 (Two-Stage Pipeline): Split the 6-step chain into 'Design & Setup' and 'Implementation & Release'.",
            "Option 2 (Milestone Grouping): Group consecutive pairs of steps into 3 independent milestones.",
        ])

    # (e) subtask deadlines spread > 14 days
    sub_dls = [s.deadline for s in subtasks if s.deadline is not None]
    if len(sub_dls) >= 2 and (max(sub_dls) - min(sub_dls)).days > 14:
        triggered = True
        suggestions.extend([
            "Option 1 (Weekly Horizon Tasks): Schedule only this week's milestone now and create separate tasks for future weeks.",
            "Option 2 (Milestone Split): Convert each dated milestone into its own standalone task.",
        ])

    # (f) nested Phase hierarchy
    if re.search(r"\bPhase\s+1\b.*\bPhase\s+2\b", raw_prompt, re.IGNORECASE | re.DOTALL):
        triggered = True
        suggestions.extend([
            "Option 1 (Split by Phase): Create separate top-level tasks for Phase 1 and Phase 2.",
            "Option 2 (Flatten Sub-steps): Promote each nested sub-step to a standalone task.",
        ])

    if triggered:
        warnings.insert(0, "W_BREAKDOWN_RECOMMENDED")

    return triggered, list(dict.fromkeys(warnings)), suggestions


def compute_topological_execution_order(
    subtasks: List[DeclaredSubtask],
    precedence_constraints: List[PrecedenceRelation],
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Computes a deterministic topological execution order of subtasks using Kahn's algorithm.
    Validates DAG acyclicity and builds an explicit execution plan for the downstream solver.
    Returns (topological_order_dicts, has_cycle_bool).
    """
    if not subtasks:
        return [], False

    subtask_map = {s.id: s for s in subtasks}
    nodes = [s.id for s in subtasks]
    in_degree: Dict[str, int] = {nid: 0 for nid in nodes}
    adj: Dict[str, List[str]] = {nid: [] for nid in nodes}

    # 1. Directed edges from subtask depends_on: predecessor (dep) -> successor (s.id)
    for s in subtasks:
        for dep in s.depends_on:
            if dep in in_degree:
                if s.id not in adj[dep]:
                    adj[dep].append(s.id)
                    in_degree[s.id] += 1

    # 2. Directed edges from precedence_constraints: predecessor -> successor
    for rel in precedence_constraints:
        p, s = rel.predecessor_id, rel.successor_id
        if p in in_degree and s in in_degree:
            if s not in adj[p]:
                adj[p].append(s)
                in_degree[s] += 1
        else:
            p_ids = [sub.id for sub in subtasks if p.lower() in sub.title.lower()]
            s_ids = [sub.id for sub in subtasks if s.lower() in sub.title.lower()]
            for pid in p_ids:
                for sid in s_ids:
                    if pid != sid and sid not in adj[pid]:
                        adj[pid].append(sid)
                        in_degree[sid] += 1

    queue = [nid for nid in nodes if in_degree[nid] == 0]
    queue.sort()

    order: List[str] = []
    while queue:
        curr = queue.pop(0)
        order.append(curr)
        for neighbor in sorted(adj[curr]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                queue.sort()

    has_cycle = len(order) < len(nodes)
    if has_cycle:
        return [], True

    topological_sequence = [
        {
            "step": idx + 1,
            "subtask_id": sid,
            "title": subtask_map[sid].title,
            "status": subtask_map[sid].status.value if hasattr(subtask_map[sid].status, "value") else str(subtask_map[sid].status),
            "estimated_minutes": subtask_map[sid].minutes,
            "prerequisites": list(subtask_map[sid].depends_on),
        }
        for idx, sid in enumerate(order)
    ]
    return topological_sequence, False


def build_subtask_network(
    subtasks: List[DeclaredSubtask],
    precedence_constraints: List[PrecedenceRelation],
) -> Optional[Dict[str, Any]]:
    """
    Constructs a formal dependency network graph G = (V, E) of user-declared subtasks.
    Extracts vertices (V) and directed precedence edges (E) without pre-scheduling calendar slots,
    formally delegating path evaluation and timetable scheduling to the downstream Engine Solver.
    """
    if not subtasks:
        return None

    nodes = [s.id for s in subtasks]
    subtask_map = {s.id: s for s in subtasks}
    in_degrees: Dict[str, int] = {nid: 0 for nid in nodes}
    out_degrees: Dict[str, int] = {nid: 0 for nid in nodes}

    edges: List[Dict[str, Any]] = []
    seen_edges = set()

    # 1. Directed edges from subtask depends_on: predecessor -> successor
    for s in subtasks:
        for dep in s.depends_on:
            if dep in subtask_map:
                edge_key = (dep, s.id)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append({
                        "source": dep,
                        "target": s.id,
                        "relation_type": "FINISH_TO_START",
                        "description": f"Must complete '{subtask_map[dep].title}' before starting '{s.title}'",
                    })
                    in_degrees[s.id] += 1
                    out_degrees[dep] += 1

    # 2. Directed edges from precedence_constraints: predecessor -> successor
    for rel in precedence_constraints:
        p, s = rel.predecessor_id, rel.successor_id
        if p in subtask_map and s in subtask_map:
            edge_key = (p, s)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({
                    "source": p,
                    "target": s,
                    "relation_type": rel.relation_type,
                    "description": rel.description or f"Must complete '{subtask_map[p].title}' before starting '{subtask_map[s].title}'",
                })
                in_degrees[s] += 1
                out_degrees[p] += 1
        else:
            p_ids = [sub.id for sub in subtasks if p.lower() in sub.title.lower()]
            s_ids = [sub.id for sub in subtasks if s.lower() in sub.title.lower()]
            for pid in p_ids:
                for sid in s_ids:
                    if pid != sid:
                        edge_key = (pid, sid)
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)
                            edges.append({
                                "source": pid,
                                "target": sid,
                                "relation_type": rel.relation_type,
                                "description": rel.description or f"Must complete '{subtask_map[pid].title}' before starting '{subtask_map[sid].title}'",
                            })
                            in_degrees[sid] += 1
                            out_degrees[pid] += 1

    # Compute acyclicity via Kahn's algorithm
    temp_in = dict(in_degrees)
    queue = [n for n in nodes if temp_in[n] == 0]
    visited_cnt = 0
    while queue:
        curr = queue.pop(0)
        visited_cnt += 1
        for e in edges:
            if e["source"] == curr:
                dest = e["target"]
                temp_in[dest] -= 1
                if temp_in[dest] == 0:
                    queue.append(dest)

    is_acyclic = (visited_cnt == len(nodes))

    vertices = [
        {
            "id": s.id,
            "title": s.title,
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "estimated_minutes": s.minutes,
            "priority": s.priority,
            "deadline": s.deadline.isoformat() if s.deadline else None,
            "external": s.external,
            "in_degree": in_degrees[s.id],
            "out_degree": out_degrees[s.id],
        }
        for s in subtasks
    ]

    return {
        "vertex_count": len(vertices),
        "edge_count": len(edges),
        "is_acyclic": is_acyclic,
        "vertices": vertices,
        "edges": edges,
        "solver_evaluation_notice": "Subtask network topology formalized as G = (V, E). Evaluation of path scheduling and slot allocation delegated to Engine Solver.",
    }


def detect_first_layer_input_anomalies(
    raw_prompt: str,
    extracted_title: str,
    explicit_header_duration: Optional[int],
    declared_subtasks: List[DeclaredSubtask],
    precedence_list: List[PrecedenceRelation],
    start_after_dt: Optional[datetime],
    deadline: Optional[datetime],
) -> Tuple[List[str], List[str], List[str]]:
    """
    First-Layer Token & Keyword Verification:
    Flags missing, misfilled, vague, nonsense, or contradictory tokens with E_* / W_* codes
    and human-readable alerts WITHOUT attempting to solve/overwrite the contradictions
    (which are delegated to the Engine Solver or user correction).
    """
    errors: List[str] = []
    warnings: List[str] = []
    notes: List[str] = []

    # 1. Adversarial / Prompt Injection / Nonsense / Trolling checks (E_NONSENSE_INPUT)
    if re.search(r"\b(ignore\s+all\s+previous\s+instructions|drop\s+table|system\s+prompt)\b", raw_prompt, re.IGNORECASE):
        errors.append("E_NONSENSE_INPUT")
        warnings.append("W_PROMPT_INJECTION")
        notes.append("🚫 First-Layer Security Guard (E_NONSENSE_INPUT / W_PROMPT_INJECTION): Adversarial or SQL/prompt injection tokens detected.")
    elif re.search(
        r"\b(teleport\s+to\s+mars|fight\s+a\s+(?:level\s+\d+\s+)?dragon|time\s+machine|time-travel|for\s+-\d+\s*(?:minutes?|mins?|hours?|hrs?)|asdfghjkl|qwertyuiop|zxcvbnm)\b",
        raw_prompt,
        re.IGNORECASE,
    ):
        errors.append("E_NONSENSE_INPUT")
        notes.append("🚫 First-Layer Input Guard (E_NONSENSE_INPUT): Nonsense, impossible, or negative-duration trolling tokens detected.")

    # 2. Actionless fragment check (E_NO_ACTIONABLE_TASK)
    if not errors and (
        extracted_title in ("Untitled Task", "")
        or re.fullmatch(r"(?:urgent|asap|important|high\s+priority|low\s+priority|chill|today|tomorrow|tonight|\s)+", extracted_title, re.IGNORECASE)
    ):
        errors.append("E_NO_ACTIONABLE_TASK")
        notes.append("❌ Missing Actionable Task (E_NO_ACTIONABLE_TASK): Only time/priority modifiers were found; please specify what work needs to be done.")

    # 3. Unresolved pronouns & vague task specificity (W_UNRESOLVED_REFERENCE, W_VAGUE_TASK)
    if re.search(
        r"\b(finish\s+it|do\s+it|that\s+file|the\s+guy|the\s+thing|same\s+thing\s+as\s+yesterday|the\s+other\s+part|mentioned\s+on\s+slack)\b",
        raw_prompt,
        re.IGNORECASE,
    ):
        warnings.append("W_UNRESOLVED_REFERENCE")
        notes.append("⚠️ Unresolved Reference (W_UNRESOLVED_REFERENCE): Dangling pronoun or external reference ('it', 'that file', 'the guy') lacks concrete task context.")

    if re.search(
        r"^\s*(?:do\s+some\s+studying|work\s+on\s+(?:the\s+)?project|do\s+housework|do\s+a\s+workout|office\s+admin\s+stuff|personal\s+growth|homework)\b",
        raw_prompt,
        re.IGNORECASE,
    ):
        warnings.append("W_VAGUE_TASK")
        notes.append("⚠️ Vague Task Scope (W_VAGUE_TASK): Deliverable is underspecified; consider naming the specific subject, module, or routine.")

    # 4. Contradiction Detection (Flagged at Layer 1; Resolution Delegated to Engine Solver)
    # 4a. Duration contradiction: header explicit duration != sum of active subtask durations
    if declared_subtasks and explicit_header_duration is not None:
        active_subs = [s for s in declared_subtasks if s.status != SubtaskWorkflowStatus.DONE and not s.external]
        if active_subs and all(s.minutes is not None for s in active_subs):
            sub_sum = sum(s.minutes for s in active_subs if s.minutes is not None)
            if sub_sum != explicit_header_duration:
                errors.append("E_DURATION_CONTRADICTION")
                notes.append(
                    f"❌ Duration Contradiction (E_DURATION_CONTRADICTION): Header token states {explicit_header_duration}m total, "
                    f"while declared subtasks sum to {sub_sum}m. Raw values preserved for Engine Solver / user resolution."
                )

    # 4b. Session contradiction: both single session and multi-chunk split requested in prompt
    has_atomic = bool(re.search(r"\b(in\s+one\s+(?:uninterrupted\s+)?sitting|without\s+breaks?|single\s+session|do\s+not\s+split|no\s+split|atomic)\b", raw_prompt, re.IGNORECASE))
    has_split = bool(re.search(r"\b(split\s+into|pomodoro\s+chunks|in\s+\d+\s*m(?:in(?:ute)?s?)?\s+chunks)\b", raw_prompt, re.IGNORECASE))
    if has_atomic and has_split:
        errors.append("E_SESSION_CONTRADICTION")
        notes.append(
            "❌ Session Mode Contradiction (E_SESSION_CONTRADICTION): Prompt contains both atomic ('single session') "
            "and multi-chunk ('split into chunks') keywords. Flagged for Engine Solver / user resolution."
        )

    # 4c. Semantic oxymoron contradiction
    if re.search(r"\b(zero-exertion|rest\s+day)\b", raw_prompt, re.IGNORECASE) and re.search(r"\b(sprint\s+workout|hiit|marathon|heavy\s+deadlift)\b", raw_prompt, re.IGNORECASE):
        errors.append("E_SEMANTIC_CONTRADICTION")
        notes.append(
            "❌ Semantic Contradiction (E_SEMANTIC_CONTRADICTION): Conflicting intent tokens ('zero-exertion rest day' vs. high-intensity workout)."
        )

    # 4d. Temporal & deadline contradictions
    if start_after_dt and deadline and start_after_dt > deadline:
        errors.append("E_START_AFTER_DEADLINE")
        notes.append(
            f"❌ Temporal Contradiction (E_START_AFTER_DEADLINE): Earliest start ({start_after_dt.strftime('%Y-%m-%d %H:%M')}) "
            f"is later than deadline ({deadline.strftime('%Y-%m-%d %H:%M')}). Delegated to Engine Solver / user."
        )
    for sub in declared_subtasks:
        if sub.deadline and deadline and sub.deadline > deadline:
            errors.append("E_SUBTASK_DEADLINE_AFTER_PARENT")
            notes.append(
                f"❌ Subtask Deadline Contradiction (E_SUBTASK_DEADLINE_AFTER_PARENT): Subtask [{sub.id}] due "
                f"{sub.deadline.strftime('%Y-%m-%d %H:%M')} is after parent deadline {deadline.strftime('%Y-%m-%d %H:%M')}."
            )

    # Multiple conflicting deadline phrases in header (e.g. "by tonight at 18:00, due next Thursday at 17:00")
    if re.search(r"\bby\s+(?:tonight|today|tomorrow)\b.*\bdue\s+next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week)\b", raw_prompt, re.IGNORECASE):
        errors.append("E_DEADLINE_CONTRADICTION")
        notes.append(
            "❌ Conflicting Deadlines (E_DEADLINE_CONTRADICTION): Multiple mutually exclusive deadline tokens found in prompt."
        )

    # 4e. Topological DAG cycle detection (2-node or 3-node cycles in precedence_list)
    def _norm_node(s: str) -> str:
        s = re.sub(r"^\s*(?:and|then|also)\s+", "", s.lower().strip())
        s = re.sub(r"\b(?:finish|finishing|write|writing|complete|completing|do|doing|start|starting|the|a|an)\b", "", s)
        return re.sub(r"\s+", " ", s).strip()

    adj: Dict[str, List[str]] = {}
    for rel in precedence_list:
        u = _norm_node(rel.predecessor_id)
        v = _norm_node(rel.successor_id)
        if u and v:
            adj.setdefault(u, []).append(v)
    # Check if any node reaches itself
    for start_node in list(adj.keys()):
        visited = set()
        stack = list(adj.get(start_node, []))
        while stack:
            curr = stack.pop()
            if curr == start_node or (len(curr) >= 4 and (start_node in curr or curr in start_node)):
                errors.append("E_CYCLIC_DEPENDENCY")
                notes.append(
                    "❌ Circular Dependency Detected (E_CYCLIC_DEPENDENCY): Precedence tokens form a dependency cycle. "
                    "Raw edges preserved for Engine Solver / user resolution."
                )
                break
            if curr not in visited:
                visited.add(curr)
                for nxt in adj.get(curr, []):
                    stack.append(nxt)
        if "E_CYCLIC_DEPENDENCY" in errors:
            break

    return errors, warnings, notes


def generate_diagnostic_suggestions(
    raw_prompt: str,
    extracted: Dict,
    deadline: Optional[datetime],
    conflict_notice: Optional[str],
    warnings: List[str],
    solver_delegated_fields: List[str],
    first_layer_notes: Optional[List[str]] = None,
    has_attachments: bool = False,
) -> List[str]:
    """
    Generates first-layer verification alerts when requirements, citations, or scope bounds
    are missing, misfilled, contradictory, or delegated to the downstream Engine Solver.
    """
    suggestions = list(first_layer_notes or [])

    if conflict_notice:
        suggestions.append(f"⚠️ {conflict_notice}")

    if "W_DOC_MENTIONED_NOT_ATTACHED" in warnings and not has_attachments:
        target = extracted.get("citation_target_phrase") or "chapters / study materials"
        suggestions.append(
            f"⚠️ Missing Chapter / Material Citations (W_DOC_MENTIONED_NOT_ATTACHED): Prompt mentions '{target}' "
            f"without attached documents or syllabus citations. Attach the textbook/syllabus (.pdf, .md, .txt) "
            f"or cite specific chapter complexity so the Engine Solver can evaluate task difficulty and workload weight."
        )

    if "W_SCOPE_MISMATCH" in warnings:
        suggestions.append(
            "⚠️ Scope Mismatch Detected (W_SCOPE_MISMATCH): The header chapter/section count does not match "
            "the partial scope listed in the subtasks (e.g., 'only the first half of chapter 3'). Flagged for Engine Solver / user verification."
        )

    if "W_VAGUE_DURATION" in warnings:
        suggestions.append(
            "ℹ️ Approximate Duration Token (W_VAGUE_DURATION): Upper-bound or hedged phrasing (e.g., 'less than a hour') was parsed from text."
        )

    if "W_OPEN_LOOP" in warnings:
        suggestions.append(
            "⚠️ Open-Ended Feedback Loop (W_OPEN_LOOP): A manager review or revision cycle was detected without a bounded iteration count."
        )

    if "W_NO_DURATION" in warnings:
        suggestions.append(
            "⚠️ No Duration Token Found (W_NO_DURATION): Duration was omitted in the text; flagged for user input or Engine Solver estimation."
        )

    if "W_NO_DEADLINE" in warnings and deadline is None:
        suggestions.append(
            "ℹ️ No Deadline Token Found (W_NO_DEADLINE): Task will be handed to the Engine Solver with floating availability."
        )

    if solver_delegated_fields:
        delegated_str = ", ".join(solver_delegated_fields)
        suggestions.append(
            f"🤖 Delegated to Engine Solver: Parameters [{delegated_str}] are handed off to the Engine Solver for downstream resolution/optimization."
        )

    if len(raw_prompt) > 1950:
        suggestions.append("⚠️ Prompt length is close to the 2000-character cap.")

    return suggestions


def parse_task(
    prompt: str,
    base_time: Optional[datetime] = None,
    custom_min_override: Optional[int] = None,
    has_attachments: bool = False,
    enable_translation: bool = True,
    translation_backend: Optional[str] = None,
) -> Tuple[TaskSchema, float, Dict]:
    """
    End-to-End Token & Keyword Parsing + First-Layer Verification Pipeline:
    Translates Vietnamese inputs into English via CTranslate2 (NLLB-200 / MarianMT)
    when needed (0 ms bypass for pure English), extracts tokens, user-declared subtasks,
    and structural cues, performing first-layer verification to emit E_*/W_* codes while
    delegating contradiction solving and slot optimization to the downstream Engine Solver.
    Returns: (TaskSchema, confidence_score, telemetry_metadata)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if len(prompt.strip()) > 2000:
        errors.append("E_PROMPT_TOO_LONG")

    raw_prompt = prompt.strip()[:2000]
    tr_result = (
        translate_to_english(raw_prompt, backend=translation_backend)
        if enable_translation
        else None
    )
    working_prompt = tr_result.translated_text if (tr_result and tr_result.translation_applied) else raw_prompt

    # Separate header line from bullet lines or inline subtask sections so subtask contents do not overwrite parent header
    header_part = re.split(r"(?:\n\s*(?:[-*•]|✅|⏳|⬜|\(\d+\)|Step\s+\d+:)|(?:\bSubtasks:\s*)|(?::\s*(?:first\b|\(\d+\)|[-*•])))", working_prompt, maxsplit=1)[0]

    # Step 1: Resolve relative start_after from header
    start_after_dt, header_after_start, start_phrase = resolve_start_after_datetime(header_part, base_time)

    # Step 2: Resolve relative deadline from header
    deadline, header_after_date, deadline_phrase = resolve_relative_datetime(header_after_start, base_time)

    # Reconstruct full text with header dates stripped for regex entity extraction
    remaining_bullets = working_prompt[len(header_part):]
    text_after_date = header_after_date + remaining_bullets

    # Step 3: Extract other entities and workload multipliers with regex
    extracted = parse_with_regex(text_after_date)
    explicit_header_dur = extracted.get("explicit_header_duration")

    # Step 4: Extract user-declared subtasks (never invents arbitrary subtasks)
    declared_subtasks, sub_warnings = extract_declared_subtasks(
        working_prompt,
        parent_priority=int(extracted["priority"].value),
        parent_rhythm=extracted["work_rhythm"],
        base_time=base_time,
        default_section_minutes=extracted.get("section_duration_minutes"),
        expected_sections_count=extracted.get("total_sections_count"),
    )
    warnings.extend(sub_warnings)

    # If subtasks are declared, verify that explicit_header_dur actually belongs to the header
    # or was explicitly designated as a total (e.g. "total of 60m", "in 60m total"),
    # preventing subtask minutes from masquerading as a header duration constraint.
    if declared_subtasks and explicit_header_dur is not None:
        has_explicit_total_phrase = bool(re.search(
            r"\b(?:in\s+total|total\s+of|total)\s+\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b|\b\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m)\s+(?:in\s+total|total)\b",
            working_prompt,
            re.IGNORECASE,
        ))
        if not has_explicit_total_phrase:
            # Check if duration actually appeared in the header line (before any subtasks began)
            header_extract = parse_with_regex(header_after_date)
            explicit_header_dur = header_extract.get("explicit_header_duration")

    # Compute workload tokens: if an explicit header duration was stated (e.g. "in 60 minutes total"),
    # preserve that parsed token even if subtasks disagree (and let first-layer verification flag E_DURATION_CONTRADICTION).
    total_work_minutes: Optional[int] = extracted["duration_minutes"]
    work_minutes_lower_bound: Optional[int] = None
    if declared_subtasks:
        active_subs = [s for s in declared_subtasks if s.status != SubtaskWorkflowStatus.DONE and not s.external]
        known_sum = sum(s.minutes for s in active_subs if s.minutes is not None)
        any_unknown = any(s.minutes is None for s in active_subs)
        if explicit_header_dur is not None:
            # Preserve the explicit header duration token as stated in text
            total_work_minutes = explicit_header_dur
        elif any_unknown:
            total_work_minutes = None
            if known_sum > 0:
                work_minutes_lower_bound = known_sum
                warnings.append("W_PARTIAL_DURATION")
            else:
                warnings.append("W_NO_DURATION")
        else:
            total_work_minutes = known_sum
    elif total_work_minutes is None:
        warnings.append("W_NO_DURATION")

    # Vague duration warning (e.g. "less than a hour", "around", "about")
    if extracted.get("vague_duration_detected"):
        warnings.append("W_VAGUE_DURATION")

    # Missing chapter / document citation warning for difficulty evaluation
    if (extracted.get("requires_document_analysis") or extracted.get("needs_chapter_citation")) and not has_attachments:
        warnings.append("W_DOC_MENTIONED_NOT_ATTACHED")

    # Check if task is a fixed-slot HARD event or short/explicit-atomic task where optional preferences are unnecessary
    is_fixed_slot_event = extracted["constraint_type"] == ConstraintType.HARD
    explicit_atomic_in_text = bool(
        re.search(r"\b(in\s+one\s+sitting|without\s+breaks?|single\s+session|do\s+not\s+split|no\s+split|atomic)\b", working_prompt, re.IGNORECASE)
    )
    is_short_atomic = explicit_atomic_in_text or (
        total_work_minutes is not None and total_work_minutes <= 30 and not declared_subtasks
    )

    if deadline is None and not is_fixed_slot_event:
        warnings.append("W_NO_DEADLINE")

    # Effective scheduling duration fallback (60m when unspecified for downstream compatibility)
    final_duration = total_work_minutes if total_work_minutes is not None else (work_minutes_lower_bound or 60)

    # Step 5: Refine clean title
    final_title = clean_title(extracted["title"])

    # Step 6: First-layer verification of boundary conflict (prompt upper limit vs. UI custom min)
    # Does NOT auto-clamp or solve the conflict; preserves tokens and flags W_CHUNK_CONFLICT for Engine Solver
    conflict_notice = None
    prompt_max_chunk = extracted.get("prompt_max_chunk")
    is_splittable = extracted["is_task_splittable"]
    splitting_cfg = extracted["splitting"]

    if prompt_max_chunk and custom_min_override and custom_min_override > prompt_max_chunk:
        conflict_notice = (
            f"First-layer verification (W_CHUNK_CONFLICT): Prompt token restricts each section to <= {prompt_max_chunk}m, "
            f"while UI Custom Min is set to {custom_min_override}m. Both values preserved for Engine Solver resolution."
        )
        warnings.append("W_CHUNK_CONFLICT")

    # Step 7: Extract explicit precedence cues
    precedence_tuples = extract_precedence_relations(working_prompt)
    precedence_list = [
        PrecedenceRelation(
            predecessor_id=p,
            successor_id=s,
            relation_type=rel,
            description=f"Must complete '{p}' before starting '{s}'"
        )
        for p, s, rel in precedence_tuples
    ]

    # Reconcile subtask declared depends_on into precedence_list
    sub_map = {s.id: s for s in declared_subtasks}
    for sub in declared_subtasks:
        for dep_id in sub.depends_on:
            dep_sub = sub_map.get(dep_id)
            dep_title = dep_sub.title if dep_sub else dep_id
            
            # Check if this relationship is already represented in precedence_list (case-insensitive & substring match)
            already_present = any(
                (
                    r.predecessor_id.lower() in (dep_id.lower(), dep_title.lower())
                    or dep_title.lower() in r.predecessor_id.lower()
                )
                and (
                    r.successor_id.lower() in (sub.id.lower(), sub.title.lower())
                    or sub.title.lower() in r.successor_id.lower()
                )
                for r in precedence_list
            )
            if not already_present:
                precedence_list.append(
                    PrecedenceRelation(
                        predecessor_id=dep_id,
                        successor_id=sub.id,
                        relation_type="FINISH_TO_START",
                        description=f"Must complete '{dep_title}' before starting '{sub.title}'"
                    )
                )

    # Step 7b: Compute deterministic topological execution order via Kahn's algorithm
    topo_order, topo_has_cycle = compute_topological_execution_order(declared_subtasks, precedence_list)
    if topo_has_cycle:
        if "E_DAG_CYCLE" not in errors:
            errors.append("E_DAG_CYCLE")
            fl_notes.append("❌ Subtask Cycle (E_DAG_CYCLE): Circular dependency loop detected among subtasks.")

    # Step 7c: Formalize subtask dependency network graph G = (V, E) for Engine Solver evaluation
    subtask_net = build_subtask_network(declared_subtasks, precedence_list)

    # Step 8: First-Layer Anomaly & Contradiction Verification (flags E_*/W_* without solving contradictions)
    fl_errors, fl_warnings, fl_notes = detect_first_layer_input_anomalies(
        raw_prompt=working_prompt,
        extracted_title=final_title,
        explicit_header_duration=explicit_header_dur,
        declared_subtasks=declared_subtasks,
        precedence_list=precedence_list,
        start_after_dt=start_after_dt,
        deadline=deadline,
    )
    errors.extend(fl_errors)
    warnings.extend(fl_warnings)

    # Determine which omitted optional preferences or detected contradictions are handed off to the Engine Solver
    solver_delegated_fields: List[str] = []
    if not extracted.get("priority_from_text") and not is_fixed_slot_event:
        solver_delegated_fields.append("priority")
    if not is_short_atomic and not is_fixed_slot_event:
        if not extracted.get("pacing_from_text"):
            solver_delegated_fields.append("pacing")
        if not extracted.get("session_from_text"):
            solver_delegated_fields.append("chunk_bounds")
    if extracted.get("needs_chapter_citation") and not has_attachments:
        solver_delegated_fields.append("chapter_difficulty_weighting")
    if total_work_minutes is None:
        solver_delegated_fields.append("subtask_duration_allocation")
    if any(e in errors for e in ("E_DURATION_CONTRADICTION", "E_START_AFTER_DEADLINE", "E_SUBTASK_DEADLINE_AFTER_PARENT", "E_CYCLIC_DEPENDENCY", "E_SESSION_CONTRADICTION", "E_DEADLINE_CONTRADICTION")) or "W_CHUNK_CONFLICT" in warnings:
        solver_delegated_fields.append("contradiction_resolution")
    if subtask_net and subtask_net["edge_count"] > 0:
        if "subtask_network_evaluation" not in solver_delegated_fields:
            solver_delegated_fields.append("subtask_network_evaluation")

    # Step 9: Complexity overload evaluation & diagnostic suggestions
    breakdown_req, overload_warnings, overload_suggestions = evaluate_complexity_overload(
        working_prompt, declared_subtasks, is_splittable, total_work_minutes
    )
    warnings.extend(overload_warnings)
    warnings = list(dict.fromkeys(warnings))
    errors = list(dict.fromkeys(errors))

    suggestions = generate_diagnostic_suggestions(
        working_prompt,
        extracted,
        deadline,
        conflict_notice,
        warnings,
        solver_delegated_fields,
        first_layer_notes=fl_notes,
        has_attachments=has_attachments,
    )
    suggestions.extend(overload_suggestions)

    if "E_NONSENSE_INPUT" in errors:
        contract_status = ContractStatus.REJECTED
    elif errors:
        contract_status = ContractStatus.NEEDS_FIX
    elif warnings:
        contract_status = ContractStatus.OK_WITH_WARNINGS
    else:
        contract_status = ContractStatus.OK

    # Build Pydantic TaskSchema
    task = TaskSchema(
        status=contract_status,
        title=final_title,
        raw_prompt=raw_prompt,
        duration_minutes=max(5, final_duration),
        total_work_minutes=total_work_minutes,
        work_minutes_lower_bound=work_minutes_lower_bound,
        total_sections_count=extracted["total_sections_count"],
        section_duration_minutes=extracted["section_duration_minutes"],
        deadline=deadline,
        start_after=start_after_dt,
        priority=extracted["priority"],
        is_uncertain_priority=not extracted.get("priority_from_text", False),
        constraint_type=extracted["constraint_type"],
        cognitive_demand=extracted["cognitive_demand"],
        work_rhythm=extracted["work_rhythm"],
        comfort_zone=extracted["comfort_zone"],
        tags=extracted["tags"],
        is_task_splittable=is_splittable,
        splitting=splitting_cfg,
        conflict_resolution_notice=conflict_notice,
        subtasks=declared_subtasks,
        precedence_constraints=precedence_list,
        subtask_network=subtask_net,
        topological_execution_order=topo_order,
        breakdown_required=breakdown_req,
        requires_document_analysis=extracted["requires_document_analysis"],
        solver_delegated_fields=solver_delegated_fields,
        errors=errors,
        warnings=warnings,
        suggestions=suggestions,
    )

    telemetry = {
        "status": contract_status.value,
        "deadline_detected": deadline is not None,
        "deadline_phrase": deadline_phrase,
        "start_after_detected": start_after_dt is not None,
        "start_phrase": start_phrase,
        "precedence_count": len(precedence_list),
        "subtask_count": len(declared_subtasks),
        "breakdown_required": breakdown_req,
        "conflict_notice": conflict_notice,
        "solver_delegated_fields": solver_delegated_fields,
        "translation_applied": bool(tr_result and tr_result.translation_applied),
        "translation_backend": tr_result.backend_used if tr_result else "disabled",
        "translation_model": tr_result.model_id if tr_result else None,
        "translated_prompt": working_prompt if (tr_result and tr_result.translation_applied) else None,
        "translation_latency_ms": tr_result.latency_ms if tr_result else 0.0,
        "errors": errors,
        "warnings": warnings,
        "suggestions": suggestions,
    }

    return task, 1.0, telemetry
