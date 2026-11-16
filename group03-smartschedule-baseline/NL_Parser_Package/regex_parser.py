"""
regex_parser.py
Fast deterministic Regex-based Entity & Pattern Recognition Extractor for SmartSchedule.
Extracts duration, workload multipliers, priority, tags, splittability, cognitive demand,
precedence cues, and clean title in O(N) time.
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple
from schema import PriorityLevel, ConstraintType, CognitiveDemand, WorkRhythm, SplittingConfig
from tokenizer import clean_and_normalize


# ---------------------------------------------------------------------------
# PATTERN DICTIONARIES
# ---------------------------------------------------------------------------

PRIORITY_PATTERNS = [
    (r"\b(urgent|asap|crit(ical)?|emergency|immediately|highest\s+priority|p1)\b", PriorityLevel.URGENT),
    (r"\b(high\s+priority|important|crucial|p2)\b", PriorityLevel.HIGH),
    (r"\b(low\s+priority|optional|whenever|trivial|chill|p4)\b", PriorityLevel.LOW),
    (r"\b(medium\s+priority|normal|standard|p3)\b", PriorityLevel.MEDIUM),
]

CONSTRAINT_PATTERNS = [
    (r"\b(fixed|hard\s+deadline|strict|mandatory|lecture|exam|midterm|final|doctor|dentist|flight)\b", ConstraintType.HARD),
]

COGNITIVE_DEMAND_PATTERNS = [
    (r"\b(program(ming)?|code|debug|math|proof|algorithm|discrete\s+structure|write\s+(paper|essay|report)|deep\s+work|research)\b", CognitiveDemand.DEEP_WORK),
    (r"\b(email|reply|submit|slides|light\s+reading|organize|review\s+notes|fill\s+form)\b", CognitiveDemand.SHALLOW_WORK),
    (r"\b(break|rest|gym|workout|walk|meditate|recharge)\b", CognitiveDemand.RECOVERY),
]

SPLIT_PRESET_PATTERNS = [
    (r"\b(?:in\s+)?(?:\d+\s*(?:m|mins?|minutes?)\s+)?pomodoro(?:\s+sessions?|\s+chunks?)?\b|\b(25m(in)?\s+chunks?|25\s+mins?\s+chunks?)\b", 25, WorkRhythm.LIGHT),
    (r"\b(?:in\s+)?45\s*(?:m|mins?|minutes?)\s*(?:sessions?|chunks?)\b|\bstandard\s+chunks?\b", 45, WorkRhythm.BALANCED),
    (r"\b(?:in\s+)?90\s*(?:m|mins?|minutes?)\s*(?:sessions?|chunks?)\b|\b(deep\s+work|marathon)\b", 90, WorkRhythm.FLOW),
]

ATOMIC_PATTERNS = [
    r"\b(do\s+not\s+split|no\s+split|atomic|single\s+session|uninterrupted|all\s+at\s+once)\b"
]

DOCUMENT_REFERENCE_PATTERNS = [
    r"\b(refer\s+to|check|see|read|attached|in|from|following|according\s+to)\s+(the\s+)?(document|pdf|file|rubric|textbook|slides|attachment|syllabus|manual|recipe|atlas|guide|checklist|report)\b",
    r"\.(pdf|txt|html|md|xlsx|docx|zip)\b",
    r"\b(chapters?|ch\.?\s*\d+|problem\s+sets?|case\s+studies)\b",
    r"\b(discrete\s+structure\s+exercises?|math\s+problems?\s+in\s+chapter)\b",
]

CHAPTER_DIFFICULTY_CITATION_PATTERNS = [
    r"\b(\d+\s+chapters?|chapter\s+\d+(?:\s+to\s+\d+)?|chapters?\s+\d+\s*(?:to|-)\s*\d+)\b",
    r"\b(discrete\s+structure\s+exercises?|math\s+problems?\s+in\s+chapter\s+\d+|problem\s+sets?|case\s+studies)\b",
]


# ---------------------------------------------------------------------------
# EXTRACTION FUNCTIONS
# ---------------------------------------------------------------------------

def extract_document_reference_trigger(text: str) -> bool:
    """Checks if the user prompt refers to external documents, chapters, or exercises."""
    for pattern in DOCUMENT_REFERENCE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def detect_chapter_citation_requirement(text: str) -> Tuple[bool, Optional[str]]:
    """
    Detects if the prompt mentions chapters, exercises, or problem sets that require
    a textbook citation or attached document for the solver to evaluate task difficulty.
    """
    for pattern in CHAPTER_DIFFICULTY_CITATION_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return True, m.group(0).strip()
    return False, None


def extract_section_workload_multiplier(text: str) -> Tuple[Optional[int], Optional[int], str]:
    """
    Detects if the user specified per-section workload durations:
    Example 1: 'finishing 3 chapters, 45 mins each' -> (3, 45)
    Example 2: '4 exercises, around 30m each' -> (4, 30)
    Example 3: 'each chapter takes 1.5 hours' (with count 3) -> (count, 90)
    Returns (section_count, duration_per_section_minutes, stripped_text).
    """
    cleaned = text
    
    # Pattern 1: Count + Section word + optional descriptor + comma/space + Duration + "each" or "per section"
    match = re.search(
        r"(\d+)\s*(?:chapters?|sections?|parts?|modules?|exercises?|problems?)(?:\s+(?:of|in|on|for)\s+[^,\n]{1,35})?(?:,\s*|\s+)(?:takes?|is|about|around)?\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\s*(?:each|per\s+(?:section|chapter|part|exercise))\b",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        count = int(match.group(1))
        dur_val = float(match.group(2))
        unit = match.group(3).lower()
        dur_mins = int(dur_val * 60) if unit.startswith("h") else int(dur_val)
        cleaned = re.sub(re.escape(match.group(0)), "", cleaned)
        return count, dur_mins, cleaned

    # Pattern 2: "each section takes X mins"
    match2 = re.search(
        r"\beach\s+(?:chapter|section|part|exercise)\s+(?:takes?|is|about|around)?\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b",
        cleaned,
        re.IGNORECASE,
    )
    if match2:
        dur_val = float(match2.group(1))
        unit = match2.group(2).lower()
        dur_mins = int(dur_val * 60) if unit.startswith("h") else int(dur_val)
        # Check if there is an existing count elsewhere
        count_match = re.search(r"\b(\d+)\s+(?:chapters?|sections?|parts?|modules?|exercises?)\b", cleaned, re.IGNORECASE)
        count = int(count_match.group(1)) if count_match else None
        cleaned = re.sub(re.escape(match2.group(0)), "", cleaned)
        return count, dur_mins, cleaned

    return None, None, cleaned


def extract_section_chunk_constraint(text: str) -> Tuple[Optional[int], str]:
    """
    Detects upper boundary constraints on individual sections:
    Example: 'each section should be less than a hour', 'each session under 45 mins', 'each chapter at most 45m',
    'each practicing session should be less than 60 mins'
    Returns (max_chunk_minutes, stripped_text).
    """
    cleaned = text
    match = re.search(
        r"\beach\s+(?:[a-zA-Z]+\s+)?(?:section|chapter|part|session|chunk|sitting|block)\s+(?:should\s+be\s+|must\s+be\s+|is\s+|takes?\s+|around\s+)?(?:less\s+than|under|at\s+most|around|<=|<)?\s*(a|an|\d+)?\s*(hours?|hrs?|h|minutes?|mins?|m)\b(?:[^\.\,;]*)?",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        num_str = match.group(1) or "1"
        unit = match.group(2).lower()
        val = 1 if num_str in ("a", "an") else int(num_str)
        # If less than an hour, default to 45m chunk; else compute minutes
        matched_phrase = match.group(0).lower()
        if "less than" in matched_phrase or "under" in matched_phrase:
            chunk_mins = 45 if (val == 1 and unit.startswith("h")) else (val * 60 if unit.startswith("h") else val)
        else:
            chunk_mins = val * 60 if unit.startswith("h") else val
        cleaned = re.sub(re.escape(match.group(0)), "", cleaned)
        return chunk_mins, cleaned

    return None, cleaned


def extract_chapter_count_hint(text: str) -> Tuple[Optional[int], str]:
    """
    Detects structured milestone counts:
    Example: 'finishing 3 chapters', 'solving 4 problems', 'completing 2 modules'
    Returns (count, stripped_text).
    """
    cleaned = text
    match = re.search(
        r"\b(?:finishing|completing|doing|reading|solving|writing)?\s*(\d+)\s+(chapters?|sections?|parts?|modules?|exercises?|problems?|units?)\b",
        cleaned,
        re.IGNORECASE,
    )
    if match:
        count = int(match.group(1))
        cleaned = re.sub(re.escape(match.group(0)), "", cleaned)
        return count, cleaned
    return None, cleaned


def extract_duration_minutes(text: str) -> Tuple[Optional[int], str]:
    """
    Extracts explicit total duration in minutes if specified by user:
    'total of 3 hours', 'in total 90 mins', 'for 2 hours', '1.5 hrs'.
    Returns (duration_minutes, stripped_text).
    """
    cleaned = text

    # Case 0: Explicit total phrases like "total of 3 hours", "in total 2.5h"
    total_match = re.search(
        r"\b(?:in\s+total|total\s+of|total)\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h|minutes?|mins?|m)\b",
        cleaned,
        re.IGNORECASE,
    )
    if total_match:
        val = float(total_match.group(1))
        unit = re.search(r"hours?|hrs?|h", total_match.group(0), re.IGNORECASE)
        total = int(val * 60) if unit else int(val)
        cleaned = re.sub(re.escape(total_match.group(0)), "", cleaned)
        return total, cleaned

    # Combined hours and minutes: e.g. "2 hours 30 minutes", "1h 15m"
    combined_match = re.search(
        r"(\d+)\s*(?:hours?|hrs?|h)\s*(?:and\s*)?(\d+)\s*(?:minutes?|mins?|m)\b",
        cleaned,
        re.IGNORECASE,
    )
    if combined_match:
        h = int(combined_match.group(1))
        m = int(combined_match.group(2))
        total = h * 60 + m
        cleaned = re.sub(re.escape(combined_match.group(0)), "", cleaned)
        return total, cleaned

    # Fractional hours: e.g. "1.5 hours", "0.5 hr", "2.5h"
    fractional_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b",
        cleaned,
        re.IGNORECASE,
    )
    if fractional_match:
        h_val = float(fractional_match.group(1))
        total = int(h_val * 60)
        cleaned = re.sub(re.escape(fractional_match.group(0)), "", cleaned)
        return total, cleaned

    # Minutes only: e.g. "45 minutes", "90 mins", "30m"
    minutes_match = re.search(
        r"(\d+)\s*(?:minutes?|mins?|m)\b",
        cleaned,
        re.IGNORECASE,
    )
    if minutes_match:
        m_val = int(minutes_match.group(1))
        cleaned = re.sub(re.escape(minutes_match.group(0)), "", cleaned)
        return m_val, cleaned

    return None, cleaned


def extract_priority(text: str) -> Tuple[PriorityLevel, str]:
    """Extracts priority and removes priority keywords from text."""
    cleaned = text
    for pattern, level in PRIORITY_PATTERNS:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            return level, cleaned
    return PriorityLevel.MEDIUM, cleaned


def extract_constraint_type(text: str) -> Tuple[ConstraintType, str]:
    """Classifies hard vs soft constraint."""
    cleaned = text
    for pattern, ctype in CONSTRAINT_PATTERNS:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            return ctype, cleaned
    return ConstraintType.SOFT, cleaned


def extract_cognitive_demand(text: str) -> CognitiveDemand:
    """Classifies cognitive intensity to align with chronotype energy curves."""
    for pattern, demand in COGNITIVE_DEMAND_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return demand
    return CognitiveDemand.DEEP_WORK


def extract_tags(text: str) -> Tuple[List[str], str]:
    """Extracts hashtags like #cs252 #homework and strips them from title."""
    tags = re.findall(r"#([a-zA-Z0-9_\-]+)", text)
    cleaned = re.sub(r"#[a-zA-Z0-9_\-]+", "", text)
    return [t.lower() for t in tags], cleaned


def extract_splitting_config(text: str, total_duration: Optional[int]) -> Tuple[bool, Optional[SplittingConfig], Optional[int], WorkRhythm, str]:
    """
    Extracts user splitting preferences and bounds.
    Returns (is_splittable, SplittingConfig, prompt_max_chunk, work_rhythm, stripped_text).
    """
    cleaned = text
    effective_duration = total_duration or 60

    # 1. Explicit atomic request -> Splitting is null
    for pattern in ATOMIC_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            return False, None, None, WorkRhythm.BALANCED, cleaned

    # 2. Section chunk constraint (e.g. "each section less than an hour")
    section_chunk, cleaned = extract_section_chunk_constraint(cleaned)
    if section_chunk:
        cfg = SplittingConfig(
            preferred_chunk_minutes=min(45, section_chunk),
            min_chunk_minutes=15,
            max_chunk_minutes=section_chunk,
        )
        return True, cfg, section_chunk, WorkRhythm.BALANCED, cleaned

    # 3. Preset matches (Pomodoro, 45m, Deep Work)
    for pattern, chunk_size, zone in SPLIT_PRESET_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            cfg = SplittingConfig(
                preferred_chunk_minutes=chunk_size,
                min_chunk_minutes=min(15, chunk_size),
                max_chunk_minutes=max(chunk_size, 90),
            )
            return True, cfg, None, zone, cleaned

    # 4. Explicit split request: "split into X parts" or "split"
    split_parts_match = re.search(r"\bsplit(?:\s+into)?\s+(\d+)\s*(?:sessions?|parts?|chunks?)\b", cleaned, re.IGNORECASE)
    if split_parts_match:
        parts = max(2, min(8, int(split_parts_match.group(1))))
        chunk_size = max(15, effective_duration // parts)
        cleaned = re.sub(re.escape(split_parts_match.group(0)), "", cleaned)
        cfg = SplittingConfig(
            preferred_chunk_minutes=chunk_size,
            min_chunk_minutes=15,
            max_chunk_minutes=max(45, chunk_size),
        )
        return True, cfg, None, WorkRhythm.BALANCED, cleaned

    if re.search(r"\b(split|splittable|in\s+chunks)\b", cleaned, re.IGNORECASE):
        cleaned = re.sub(r"\b(split|splittable|in\s+chunks)\b", "", cleaned, flags=re.IGNORECASE)
        cfg = SplittingConfig(
            preferred_chunk_minutes=45,
            min_chunk_minutes=15,
            max_chunk_minutes=60,
        )
        return True, cfg, None, WorkRhythm.BALANCED, cleaned

    # Default: Single Session -> is_task_splittable = False, splitting = None
    return False, None, None, WorkRhythm.BALANCED, cleaned


def clean_title(text: str) -> str:
    """Removes leftover prepositions, conjunctions, subordinate clauses, and formatting artifacts to produce a clean title."""
    title = clean_and_normalize(text)
    
    title = re.sub(r"\bto\s+(finish|complete|do)\s+(all\s+of\s+)?this\b", "", title, flags=re.IGNORECASE)

    # If the clause starts with a subordinate temporal or prerequisite clause (e.g., "Before coding, I need to read the guidelines.pdf"),
    # the actual deliverable/task verb is in the second (main) clause.
    subordinate_match = re.match(r"^(?:before|prior\s+to|after|once|when)\s+[^,]+,\s*(.+)$", title, flags=re.IGNORECASE)
    if subordinate_match:
        title = subordinate_match.group(1).strip()
    elif "," in title:
        # If there is a trailing descriptive clause (e.g., "finish bits.c source code, running on Linux Virtual Machine"), keep the main clause
        parts = [p.strip() for p in title.split(",") if len(p.strip()) > 3]
        if parts:
            title = parts[0]

    # Strip conversational filler prefixes
    title = re.sub(r"^(?:i\s+need\s+to|i\s+have\s+to|i\s+must|we\s+need\s+to|please|make\s+sure\s+to)\s+", "", title, flags=re.IGNORECASE).strip()

    for _ in range(3):
        title = re.sub(r"^(for|at|with|on|in|by|to|before|after|until|till)\s+", "", title, flags=re.IGNORECASE).strip()
        title = re.sub(r"\s+(for|at|with|on|in|by|to|before|after|until|till)$", "", title, flags=re.IGNORECASE).strip()

    title = title.strip(" ,.-:;#/\\")
    if len(title) > 90:
        title = title[:87] + "..."

    return title[:1].upper() + title[1:] if title else "Untitled Task"


def parse_with_regex(prompt: str) -> Dict:
    """
    Executes end-to-end Regex entity extraction.
    Returns dictionary with raw extracted values ready for schema instantiation.
    """
    # Separate header line from any multi-line bullet list so bullets don't pollute title
    header_part = re.split(r"(?:\n\s*[-*•✅⏳⬜]|\bHere\s+is\s+my\s+detailed\s+work\s*:)", prompt, maxsplit=1, flags=re.IGNORECASE)[0]
    raw_clean = clean_and_normalize(header_part)
    full_clean = clean_and_normalize(prompt)

    # Detect if priority, pacing, or session mode were explicitly stated in the text
    priority_from_text = any(re.search(p, full_clean, re.IGNORECASE) for p, _ in PRIORITY_PATTERNS)
    pacing_from_text = any(re.search(p, full_clean, re.IGNORECASE) for p, _, _ in SPLIT_PRESET_PATTERNS)
    session_from_text = (
        any(re.search(p, full_clean, re.IGNORECASE) for p in ATOMIC_PATTERNS)
        or pacing_from_text
        or bool(re.search(r"\b(split|splittable|in\s+chunks|each\s+(?:section|chapter|part|session|chunk))\b", full_clean, re.IGNORECASE))
    )
    vague_duration_detected = bool(
        re.search(
            r"\b(less\s+than|under|at\s+most|around|about|roughly|i\s+guess|couple\s+of\s+hours|\d+\s*(?:to|-|or)\s*\d+\s*(?:hours?|hrs?|h|minutes?|mins?|m))\b",
            full_clean,
            re.IGNORECASE,
        )
    )

    # 1. Tags
    tags, text = extract_tags(raw_clean)

    # 2. Priority
    priority, text = extract_priority(text)

    # 3. Constraint type
    constraint_type, text = extract_constraint_type(text)

    # 4. Cognitive demand
    cognitive_demand = extract_cognitive_demand(full_clean)

    # 5. Section workload multiplier (e.g. 3 chapters, 45m each)
    sec_count, sec_dur, text = extract_section_workload_multiplier(text)
    if sec_count is None:
        hint_count, text = extract_chapter_count_hint(text)
        if hint_count is not None:
            sec_count = hint_count

    # 5b. Section chunk constraint (e.g. "each practicing session should be less than 60 mins")
    # Stripped BEFORE extract_duration_minutes so session caps are not confused with total duration!
    early_chunk, text = extract_section_chunk_constraint(text)

    # 6. Splitting & Work Rhythm (presets, chunk bounds, Pomodoro, etc. stripped first so session caps are not confused with total duration)
    is_splittable, splitting_cfg, prompt_max_chunk, work_rhythm, text = extract_splitting_config(text, None)
    if early_chunk:
        prompt_max_chunk = early_chunk
        is_splittable = True
        splitting_cfg = SplittingConfig(
            preferred_chunk_minutes=min(45, early_chunk),
            min_chunk_minutes=15,
            max_chunk_minutes=early_chunk,
        )

    # 7. Total Duration (explicit)
    explicit_dur, text = extract_duration_minutes(text)

    # If section duration was not directly set by multiplier, check prompt_max_chunk
    if sec_dur is None and prompt_max_chunk:
        sec_dur = prompt_max_chunk

    # Resolve effective total duration:
    if explicit_dur is not None:
        total_dur = explicit_dur
    elif sec_count and sec_dur:
        total_dur = sec_count * sec_dur
    elif sec_count and prompt_max_chunk:
        total_dur = sec_count * prompt_max_chunk
    else:
        total_dur = None

    # 8. Document & Chapter Citation Triggers (for difficulty evaluation)
    has_doc_ref = extract_document_reference_trigger(full_clean)
    needs_citation, citation_phrase = detect_chapter_citation_requirement(full_clean)
    if needs_citation:
        has_doc_ref = True

    # 9. Remaining text cleaned as title
    title = clean_title(text)

    return {
        "title": title,
        "raw_prompt": prompt,
        "duration_minutes": total_dur,
        "explicit_header_duration": explicit_dur,
        "total_sections_count": sec_count,
        "section_duration_minutes": sec_dur,
        "priority": priority,
        "priority_from_text": priority_from_text,
        "pacing_from_text": pacing_from_text,
        "session_from_text": session_from_text,
        "vague_duration_detected": vague_duration_detected,
        "needs_chapter_citation": needs_citation,
        "citation_target_phrase": citation_phrase,
        "constraint_type": constraint_type,
        "cognitive_demand": cognitive_demand,
        "work_rhythm": work_rhythm,
        "comfort_zone": work_rhythm,
        "tags": tags,
        "is_task_splittable": is_splittable,
        "splitting": splitting_cfg,
        "prompt_max_chunk": prompt_max_chunk,
        "requires_document_analysis": has_doc_ref,
    }
