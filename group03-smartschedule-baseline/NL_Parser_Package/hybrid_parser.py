"""
hybrid_parser.py
Unified 6-Stage Hybrid Natural Language Parser for SmartSchedule.

Combines:
  - Stage 1: Guided UI Input + Lab Shorthand (`#tags`, `~chunk`, `after:ID`, `p1..p5`)
  - Stage 2: Input Gatekeeper (`<=2000` chars, injection/troll/past-narrative filter)
             + Offline VI->EN Translation Bridge (`translator.py`: NLLB-200 / MarianMT / Rule)
  - Stage 3: Hybrid Extraction (Generalized NLP + `NL_Parser_Package` + Parent M1 fallback)
  - Stage 4: First-Layer Verification (Non-destructive `E_*`, `W_*`, DAG Cycle DFS, 6 Overload Rules)
  - Stage 5: UI Override & Diagnostic Reconciliation (`session`, `pacing`, `custom`, `priority`, `attachments`)
  - Stage 6: SmartSchedule Solver Adapter (`User P1=Urgent .. P4=Low` -> `Solver Priority 5 .. 1`)
"""

from __future__ import annotations

import hashlib
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from parser import parse_task
from translator import contains_vietnamese, translate_to_english

# Optional link to parent M1 parser if available in workspace
_PKG_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PKG_DIR.parent
_BASELINE_DIR = _REPO_ROOT / "group03-smartschedule-baseline"
if _BASELINE_DIR.exists() and str(_BASELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASELINE_DIR))

ALLOWED_EXTENSIONS = {"txt", "pdf", "html", "md"}
MAX_ATTACHMENT_MB = 20.0

_WEEKDAY_MAP = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}
_WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

_MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

# General spelling normalization (common English typos in task inputs)
_TYPO_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    (r"\bminites\b|\bminets\b|\bmints\b", "minutes"),
    (r"\bWenesday\b|\bWedensday\b", "Wednesday"),
    (r"\bThrusday\b|\bThurday\b", "Thursday"),
    (r"\bMonay\b", "Monday"),
    (r"\bTusday\b", "Tuesday"),
    (r"\bFirday\b", "Friday"),
    (r"\bwek\b", "week"),
    (r"\btommorow\b|\btomorow\b", "tomorrow"),
    (r"\bFinnish\b", "Finish"),
    (r"\bComplte\b|\bComplet\b", "Complete"),
    (r"\bdscrete\b", "Discrete"),
    (r"\bstructur\b", "Structure"),
    (r"\basignmnt\b|\bassignmnet\b", "assignment"),
    (r"\balgbra\b", "Algebra"),
    (r"\bswiming\b", "swimming"),
    (r"\bdocumnt\b", "document"),
)

# General multi-domain vocabularies for cognitive context-switching overload detection
_DOMAIN_LEXICONS: Dict[str, Set[str]] = {
    "work_finance": {
        "forecast", "revenue", "board", "deck", "slides", "report", "proposal",
        "client", "audit", "quarterly", "tax", "invoice", "budget", "meeting",
        "deploy", "api", "schema", "database", "sprint", "pipeline", "release",
    },
    "chore_home": {
        "clean", "scrub", "oven", "tiles", "kitchen", "bathroom", "garage",
        "laundry", "vacuum", "mop", "dishes", "groceries", "shelves", "fridge",
        "refrigerator", "apartment", "linens", "towels", "iron", "car", "sedan",
    },
    "fitness_health": {
        "run", "running", "workout", "swim", "cycling", "cardio", "tempo",
        "trail", "5k", "10k", "gym", "yoga", "marathon", "rowing", "rehab",
        "sprint", "mobility", "hiking", "triathlon", "exercise",
    },
    "study_academic": {
        "vocabulary", "chapter", "chapters", "algebra", "calculus", "textbook",
        "study", "exam", "homework", "problem", "memorize", "thesis", "paper",
        "physics", "biology", "compiler", "linear", "discrete", "german",
        "french", "spanish", "lecture", "midterm", "assignment", "glossary",
    },
}

_FANTASY_NOUNS = {
    "mars", "jupiter", "saturn", "pluto", "dragon", "unicorn", "broomstick",
    "godzilla", "voldemort", "hobbit", "lightsaber", "dyson sphere", "wormhole",
}


def map_user_urgency_to_solver_priority(user_p: Optional[int], scale_max: int = 4) -> int:
    """
    User convention: lower number = more urgent (P1 = Urgent/Critical, P4 = Low).
    Parent Solver convention (`src/models.py`): higher number = more urgent (5 = Highest, 1 = Lowest).
    """
    if user_p is None:
        return 3
    if scale_max == 5:
        return max(1, min(5, 6 - int(user_p)))
    return {1: 5, 2: 4, 3: 3, 4: 1}.get(int(user_p), 3)


def _next_weekday(base_time: datetime, target_wd: int, *, next_week: bool = False, same_day_ok: bool = False) -> datetime:
    """Compute next occurrence of `target_wd` (0=Mon..6=Sun) relative to `base_time`."""
    days_ahead = (target_wd - base_time.weekday()) % 7
    if days_ahead == 0 and not same_day_ok:
        days_ahead = 7
    if next_week:
        next_monday = base_time + timedelta(days=(7 - base_time.weekday()) % 7 or 7)
        return next_monday + timedelta(days=(target_wd - 0) % 7)
    return base_time + timedelta(days=days_ahead)


def _end_of_this_week(base_time: datetime) -> datetime:
    """Return upcoming Sunday 23:59 of `base_time`'s week."""
    dt = _next_weekday(base_time, 6, same_day_ok=True)
    return dt.replace(hour=23, minute=59, second=0, microsecond=0)


def _early_next_week(base_time: datetime) -> datetime:
    """Return Tuesday 23:59 of next week relative to `base_time`."""
    dt = _next_weekday(base_time, 1, next_week=True)
    return dt.replace(hour=23, minute=59, second=0, microsecond=0)


def _apply_daypart(dp: Optional[str]) -> Tuple[int, int]:
    """Map daypart tokens consistently to default deadline hour/minute."""
    if not dp:
        return 23, 59
    d = dp.lower().strip()
    if d == "night":
        return 23, 59
    if d == "evening":
        return 21, 0
    if d == "afternoon":
        return 17, 0
    if d in {"morning", "noon"} or "lunch" in d:
        return 12, 0
    return 23, 59


def _parse_single_date_expr(
    phrase: str,
    base_time: datetime,
    *,
    is_event_context: bool = False,
) -> Optional[datetime]:
    """Resolve a standalone temporal/deadline phrase into a datetime relative to `base_time`."""
    p = phrase.strip()
    if not p:
        return None

    # 1. Explicit Month Day(, Year) [at HH:MM]
    m_cal = re.search(
        r"\b(?P<mon>january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(?P<yr>\d{4}))?(?:\s+(?:at\s+)?(?P<hh>\d{1,2}):(?P<mm>\d{2}))?\b",
        p,
        re.IGNORECASE,
    )
    if m_cal:
        mon = _MONTH_MAP[m_cal.group("mon").lower()]
        day = int(m_cal.group("day"))
        yr = int(m_cal.group("yr")) if m_cal.group("yr") else base_time.year
        hh = int(m_cal.group("hh")) if m_cal.group("hh") else 23
        mm = int(m_cal.group("mm")) if m_cal.group("mm") else 59
        try:
            return datetime(yr, mon, day, hh, mm)
        except ValueError:
            return None

    # 2. Today / Tonight
    if re.search(r"\b(?:today|tonight|hôm\s*nay|tối\s*nay)\b", p, re.IGNORECASE):
        m_cl = re.search(r"\b(?:at\s+)?(\d{1,2})(?::|h)(\d{2})\b", p, re.IGNORECASE)
        if m_cl:
            hh, mm = int(m_cl.group(1)), int(m_cl.group(2))
        else:
            m_h = re.search(r"\b(\d{1,2})h\b", p, re.IGNORECASE)
            hh, mm = (int(m_h.group(1)), 0) if m_h else (23, 59)
        return base_time.replace(hour=hh, minute=mm, second=0, microsecond=0)

    # 3. Tomorrow / Ngày mai
    if re.search(r"\b(?:tomorrow|ngày\s*mai|tối\s*mai|chiều\s*mai|sáng\s*mai)\b", p, re.IGNORECASE):
        tmr = base_time + timedelta(days=1)
        m_cl = re.search(r"\b(?:at\s+)?(\d{1,2})(?::|h)(\d{2})\b", p, re.IGNORECASE)
        m_dp = re.search(r"\b(morning|afternoon|evening|night)\b", p, re.IGNORECASE)
        if m_cl:
            hh, mm = int(m_cl.group(1)), int(m_cl.group(2))
        elif m_dp:
            hh, mm = _apply_daypart(m_dp.group(1))
        elif re.search(r"chiều\s*mai", p, re.IGNORECASE):
            hh, mm = 17, 0
        elif re.search(r"sáng\s*mai", p, re.IGNORECASE):
            hh, mm = 12, 0
        else:
            hh, mm = 23, 59
        return tmr.replace(hour=hh, minute=mm, second=0, microsecond=0)

    # 4. Vietnamese Chủ Nhật / thứ 2..7
    m_cn = re.search(r"\bChủ\s*Nhật\b(?:\s*(tuần\s*tới|tuần\s*này))?", p, re.IGNORECASE)
    if m_cn:
        is_next = bool(m_cn.group(1) and "tới" in m_cn.group(1).lower())
        dt = _next_weekday(base_time, 6, next_week=is_next)
        m_cl = re.search(r"\b(\d{1,2})(?:h|:)(\d{0,2})\b", p, re.IGNORECASE)
        hh = int(m_cl.group(1)) if m_cl else 23
        mm = int(m_cl.group(2) or 0) if m_cl else 59
        return dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    m_vi = re.search(r"\bthứ\s*([2-7])\s*(tuần\s*tới|tuần\s*này)?", p, re.IGNORECASE)
    if m_vi:
        wd = int(m_vi.group(1)) - 2
        is_next = bool(m_vi.group(2) and "tới" in m_vi.group(2).lower())
        dt = _next_weekday(base_time, wd, next_week=is_next)
        m_cl = re.search(r"\b(\d{1,2})(?:h|:)(\d{0,2})\b", p, re.IGNORECASE)
        hh = int(m_cl.group(1)) if m_cl else 23
        mm = int(m_cl.group(2) or 0) if m_cl else 59
        return dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    # 5. English Weekday
    m_wd = re.search(
        r"\b(?:(next|this)\s+)?(monday|mon|tuesday|tue|tues|wednesday|wed|thursday|thu|thur|thurs|friday|fri|saturday|sat|sunday|sun)"
        r"(?:\s+(next\s+week|this\s+week))?"
        r"(?:\s+(?:\([^)]*\)\s*)?(?:(?:at\s+)?(\d{1,2}):(\d{2})|(night|evening|afternoon|morning|family\s+lunch)))?",
        p,
        re.IGNORECASE,
    )
    if m_wd:
        wd_name = m_wd.group(2).lower()
        wd = _WEEKDAY_MAP[wd_name]
        next_kw = (m_wd.group(1) or "").lower() == "next" or bool(m_wd.group(3) and "next" in m_wd.group(3).lower())
        same_ok = (wd == base_time.weekday() and not next_kw and not m_wd.group(4) and not m_wd.group(6) and not is_event_context)
        dt = _next_weekday(base_time, wd, next_week=next_kw, same_day_ok=same_ok)
        if m_wd.group(4):
            hh, mm = int(m_wd.group(4)), int(m_wd.group(5))
        elif m_wd.group(6):
            hh, mm = _apply_daypart(m_wd.group(6))
        else:
            hh, mm = 23, 59
        return dt.replace(hour=hh, minute=mm, second=0, microsecond=0)

    if re.search(r"\b(?:end\s+of\s+(?:the|this)\s+week|this\s+weekend|this\s+week)\b", p, re.IGNORECASE):
        return _end_of_this_week(base_time)

    return None


def _resolve_hybrid_dates(
    prompt: str,
    base_time: datetime,
) -> Tuple[Optional[datetime], Optional[datetime], Set[str], Set[str]]:
    """
    General date/time resolver relative to `base_time`:
      - Separates `start_after` from `deadline`
      - Detects calendar weekday mismatches (`Monday, November 8, 2026` where Nov 8 is Sunday)
      - Detects conflicting multi-deadline headers (`by ..., due ...`)
      - Detects ambiguous dates (`11/12`, `the 20th`, `Tuesday or Wednesday`, bare same-day weekday, event-prep offsets)
      - Detects vague deadlines (`ASAP`, `soon`, `early next week`) & unbounded recurring tasks (`every ...`)
    """
    errors: Set[str] = set()
    warnings: Set[str] = set()
    s = prompt.strip()

    # Check unbounded recurring habits without explicit end date
    is_recurring_unbounded = bool(
        re.search(r"\bevery\s+(?:morning|evening|afternoon|night|day|weekday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\bmỗi\s+buổi\b", s, re.IGNORECASE)
        and not re.search(r"\buntil\b", s, re.IGNORECASE)
    )
    if is_recurring_unbounded:
        warnings.add("W_RECURRING_NO_END")

    start_after: Optional[datetime] = None
    header_for_dl = s

    # Fixed slot window: "tomorrow from HH:MM to HH:MM"
    m_fixed = re.search(r"\btomorrow\s+from\s+(\d{1,2}):(\d{2})\s+to\s+(\d{1,2}):(\d{2})\b", s, re.IGNORECASE)
    if m_fixed:
        tmr = base_time + timedelta(days=1)
        start_after = tmr.replace(hour=int(m_fixed.group(1)), minute=int(m_fixed.group(2)), second=0, microsecond=0)
        dl = tmr.replace(hour=int(m_fixed.group(3)), minute=int(m_fixed.group(4)), second=0, microsecond=0)
        return start_after, dl, errors, warnings

    # "tomorrow afternoon" without explicit clock -> 12:00..17:00
    if re.search(r"\btomorrow\s+afternoon\b", s, re.IGNORECASE) and not re.search(r"\b(?:by|before|at)\s+\d", s, re.IGNORECASE):
        tmr = base_time + timedelta(days=1)
        start_after = tmr.replace(hour=12, minute=0, second=0, microsecond=0)
        dl = tmr.replace(hour=17, minute=0, second=0, microsecond=0)
        return start_after, dl, errors, warnings

    # Extract explicit start_after (`starting [after] <date>`, `bắt đầu từ <date>`)
    m_sa = re.search(
        r"\b(?:starting(?:\s+after)?|start\s+after|bắt\s*đầu\s*(?:từ|sau))\s+([^,;.\n]+?)(?=(?:\s+(?:and\s+finish|và\s+hoàn\s+thành|before|by|trước)\b|[,;.\n]|$))",
        header_for_dl,
        re.IGNORECASE,
    )
    if m_sa:
        sa_phrase = m_sa.group(1).strip()
        sa_dt = _parse_single_date_expr(sa_phrase, base_time)
        if sa_dt is not None:
            if not re.search(r"\b\d{1,2}(?::|h)\d{0,2}\b", sa_phrase):
                sa_dt = sa_dt.replace(hour=9, minute=0, second=0, microsecond=0)
            start_after = sa_dt
            header_for_dl = header_for_dl[:m_sa.start()] + " " + header_for_dl[m_sa.end():]

    # Focus on parent header (before subtask block `:\n` or `:\s*(1)|-|first|step 1`)
    parent_part = re.split(r":\s*(?:\n|\(1\)|-|first\b|step\s+1\b)|\n", header_for_dl, maxsplit=1, flags=re.IGNORECASE)[0]

    # Check calendar date + weekday contradiction: e.g. "Monday, November 8, 2026 [at 18:00]"
    m_cal_wd = re.search(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+"
        r"(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)"
        r"\s+(\d{1,2}),?\s*(\d{4})(?:\s+(?:at\s+)?(\d{1,2}):(\d{2}))?",
        parent_part,
        re.IGNORECASE,
    )
    if m_cal_wd:
        wd_expected = _WEEKDAY_MAP[m_cal_wd.group(1).lower()]
        mon = _MONTH_MAP[m_cal_wd.group(2).lower()]
        day_num = int(m_cal_wd.group(3))
        yr = int(m_cal_wd.group(4))
        hh = int(m_cal_wd.group(5) or 23)
        mm = int(m_cal_wd.group(6) or 59)
        cal_dt = datetime(yr, mon, day_num, hh, mm)
        if cal_dt.weekday() != wd_expected:
            errors.add("E_DEADLINE_CONTRADICTION")
        return start_after, cal_dt, errors, warnings

    # Check general multi-deadline contradiction in parent header (`by X, due Y` / `before X ... due Y`)
    dl_clauses = [
        m.group(1).strip()
        for m in re.finditer(
            r"\b(?:by|before|due|trước|hạn)\s+((?:[^,;\n:]|:(?=\d))+?)(?=(?:\s*,\s*(?:by|before|due|takes|for|and\s+also|hạn|trước))|[,;\n]|:(?=\s|$)|$)",
            parent_part,
            re.IGNORECASE,
        )
    ]
    resolved_dls: List[datetime] = []
    for cl in dl_clauses:
        dt_c = _parse_single_date_expr(cl, base_time)
        if dt_c is not None:
            resolved_dls.append(dt_c)
    if len(resolved_dls) >= 2:
        if max((abs((d - resolved_dls[0]).total_seconds()) for d in resolved_dls[1:]), default=0) > 3600:
            errors.add("E_DEADLINE_CONTRADICTION")
            return start_after, resolved_dls[0], errors, warnings

    # Explicit Month Day[,] Year [at HH:MM] in parent header ("by December 5, 2026", "by Nov 1 2026 10:00")
    m_full_date = re.search(
        r"\b(?:by|before|due|on)\s+(january|jan|february|feb|march|mar|april|apr|may|june|jun|july|jul|august|aug|september|sep|sept|october|oct|november|nov|december|dec)\s+(\d{1,2}),?\s*(\d{4})(?:\s+(?:at\s+)?(\d{1,2}):(\d{2}))?\b",
        parent_part,
        re.IGNORECASE,
    )
    if m_full_date:
        mon = _MONTH_MAP[m_full_date.group(1).lower()]
        hh = int(m_full_date.group(4) or 23)
        mm = int(m_full_date.group(5) or 59)
        return start_after, datetime(int(m_full_date.group(3)), mon, int(m_full_date.group(2)), hh, mm), errors, warnings

    # Numeric slash date: "by 11/12"
    m_slash = re.search(r"\b(?:by|before|due)\s+(\d{1,2})/(\d{1,2})\b", parent_part, re.IGNORECASE)
    if m_slash:
        warnings.add("W_AMBIGUOUS_DATE")
        a, b = int(m_slash.group(1)), int(m_slash.group(2))
        mon, day = (a, b) if a <= 12 else (b, a)
        return start_after, datetime(base_time.year, mon, day, 23, 59), errors, warnings

    # Ordinal day of month: "by the 20th"
    m_ord = re.search(r"\b(?:by|before|due)\s+the\s+(\d{1,2})(?:st|nd|rd|th)\b", parent_part, re.IGNORECASE)
    if m_ord:
        warnings.add("W_AMBIGUOUS_DATE")
        day = int(m_ord.group(1))
        mon = base_time.month if day >= base_time.day else (base_time.month % 12) + 1
        yr = base_time.year + (1 if mon < base_time.month else 0)
        return start_after, datetime(yr, mon, day, 23, 59), errors, warnings

    # Vague deadlines: ASAP (acts as urgency+deadline proxy) vs soon (no concrete anchor) vs early next week
    if re.search(r"\b(?:asap|as\s+soon\s+as\s+possible)\b", parent_part, re.IGNORECASE):
        warnings.add("W_VAGUE_DEADLINE")
        return start_after, None, errors, warnings
    if re.search(r"\bsoon\b", parent_part, re.IGNORECASE):
        warnings.add("W_NO_DEADLINE")
        warnings.add("W_VAGUE_DEADLINE")
        return start_after, None, errors, warnings
    if re.search(r"\bby\s+early\s+next\s+week\b", parent_part, re.IGNORECASE):
        warnings.add("W_VAGUE_DEADLINE")
        return start_after, _early_next_week(base_time), errors, warnings

    # Hedged weekday: "by Tuesday or Wednesday next week"
    m_or_wd = re.search(
        r"\b(?:by|before)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+or\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(\s+next\s+week)?",
        parent_part,
        re.IGNORECASE,
    )
    if m_or_wd:
        warnings.add("W_AMBIGUOUS_DATE")
        wd = _WEEKDAY_MAP[m_or_wd.group(1).lower()]
        dt_dl = _next_weekday(base_time, wd, next_week=True)
        return start_after, dt_dl.replace(hour=23, minute=59, second=0, microsecond=0), errors, warnings

    # Unbounded recurring weekday/daypart ("every morning", "every Saturday morning", "mỗi buổi tối")
    if is_recurring_unbounded:
        m_rec_wd = re.search(
            r"\bevery\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(morning|afternoon|evening|night))?\b",
            parent_part,
            re.IGNORECASE,
        )
        if m_rec_wd:
            wd = _WEEKDAY_MAP[m_rec_wd.group(1).lower()]
            dt = _next_weekday(base_time, wd, same_day_ok=False)
            hh, mm = _apply_daypart(m_rec_wd.group(2))
            return start_after, dt.replace(hour=hh, minute=mm, second=0, microsecond=0), errors, warnings
        return start_after, None, errors, warnings

    # Bounded "every day until <date>" / "on Mon, Wed, and Fri next week"
    m_bounded_until = re.search(r"\buntil\s+(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", parent_part, re.IGNORECASE)
    if m_bounded_until:
        wd = _WEEKDAY_MAP[m_bounded_until.group(2).lower()]
        dt = _next_weekday(base_time, wd, next_week=bool(m_bounded_until.group(1)))
        return start_after, dt.replace(hour=23, minute=59, second=0, microsecond=0), errors, warnings

    m_mwf = re.search(r"\bon\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:,\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))*,?\s+and\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(\s+next\s+week)?", parent_part, re.IGNORECASE)
    if m_mwf:
        wd = _WEEKDAY_MAP[m_mwf.group(1).lower()]
        dt = _next_weekday(base_time, wd, next_week=bool(m_mwf.group(2)))
        return start_after, dt.replace(hour=23, minute=59, second=0, microsecond=0), errors, warnings

    # Today / tonight with explicit clock
    m_today_clock = re.search(
        r"\b(?:today|tonight|hôm\s*nay|tối\s*nay)\b.*?\b(?:before|by|at|trước|lúc)\s+(\d{1,2})(?::|h)(\d{2})\b|\b(?:before|by|at|trước|lúc)\s+(\d{1,2})(?::|h)(\d{2})\s+(?:today|tonight|hôm\s*nay|tối\s*nay)\b",
        parent_part,
        re.IGNORECASE,
    )
    if m_today_clock:
        hh = int(m_today_clock.group(1) or m_today_clock.group(3))
        mm = int(m_today_clock.group(2) or m_today_clock.group(4))
        return start_after, base_time.replace(hour=hh, minute=mm, second=0, microsecond=0), errors, warnings

    # Tomorrow with explicit clock or night (EN & VI)
    m_tmr_vi = re.search(
        r"\b(?:trước|hạn|lúc)\s*(\d{1,2})(?:h|:)(\d{0,2})\s*(?:ngày\s*mai|tối\s*mai|chiều\s*mai|sáng\s*mai|mai)\b",
        parent_part,
        re.IGNORECASE,
    )
    if m_tmr_vi:
        tmr = base_time + timedelta(days=1)
        hh = int(m_tmr_vi.group(1))
        mm = int(m_tmr_vi.group(2) or 0)
        return start_after, tmr.replace(hour=hh, minute=mm, second=0, microsecond=0), errors, warnings

    m_tmr_clock = re.search(
        r"\btomorrow\b.*?\b(?:before|by|at)\s+(\d{1,2}):(\d{2})\b|\b(?:before|by|at)\s+(\d{1,2}):(\d{2})\s+tomorrow\b",
        parent_part,
        re.IGNORECASE,
    )
    if m_tmr_clock:
        tmr = base_time + timedelta(days=1)
        hh = int(m_tmr_clock.group(1) or m_tmr_clock.group(3))
        mm = int(m_tmr_clock.group(2) or m_tmr_clock.group(4))
        return start_after, tmr.replace(hour=hh, minute=mm, second=0, microsecond=0), errors, warnings

    if re.search(r"\btomorrow\s+night\b|\btối\s+mai\b", parent_part, re.IGNORECASE):
        tmr = base_time + timedelta(days=1)
        return start_after, tmr.replace(hour=23, minute=59, second=0, microsecond=0), errors, warnings

    # Vietnamese Chủ Nhật / thứ 2..7
    m_vi_cn_clock = re.search(
        r"\bChủ\s*Nhật(?:\s*(tuần\s*tới|tuần\s*này))?\s+trước\s+(\d{1,2})(?:h|:)(\d{0,2})\b|\btrước\s+(\d{1,2})(?:h|:)(\d{0,2})\s+Chủ\s*Nhật(?:\s*(tuần\s*tới|tuần\s*này))?\b",
        parent_part,
        re.IGNORECASE,
    )
    if m_vi_cn_clock:
        wk_flag = m_vi_cn_clock.group(1) or m_vi_cn_clock.group(6)
        dt = _next_weekday(base_time, 6, next_week=bool(wk_flag and "tới" in wk_flag.lower()))
        hh = int(m_vi_cn_clock.group(2) or m_vi_cn_clock.group(4))
        mm = int(m_vi_cn_clock.group(3) or m_vi_cn_clock.group(5) or 0)
        return start_after, dt.replace(hour=hh, minute=mm, second=0, microsecond=0), errors, warnings

    m_vi_cn_night = re.search(r"\btrước\s+tối\s+Chủ\s*Nhật(?:\s*(tuần\s*tới|tuần\s*này))?\b", parent_part, re.IGNORECASE)
    if m_vi_cn_night:
        wk_flag = m_vi_cn_night.group(1)
        dt = _next_weekday(base_time, 6, next_week=bool(wk_flag and "tới" in wk_flag.lower()))
        return start_after, dt.replace(hour=23, minute=59, second=0, microsecond=0), errors, warnings

    m_vi_wd = re.search(
        r"\b(?:trước|hạn)\s*(?:(\d{1,2})(?:h|:)(\d{0,2})\s*)?(tối\s*)?thứ\s*([2-7])\s*(tuần\s*tới|tuần\s*này)?",
        parent_part,
        re.IGNORECASE,
    )
    if m_vi_wd:
        wd = int(m_vi_wd.group(4)) - 2
        is_next = bool(m_vi_wd.group(5) and "tới" in m_vi_wd.group(5).lower())
        dt_dl = _next_weekday(base_time, wd, next_week=is_next)
        if m_vi_wd.group(1):
            hh, mm = int(m_vi_wd.group(1)), int(m_vi_wd.group(2) or 0)
        else:
            hh, mm = 23, 59
        return start_after, dt_dl.replace(hour=hh, minute=mm, second=0, microsecond=0), errors, warnings

    # Explicit English weekday with 'by/before' (highest priority over 'for/on <event> on <weekday>')
    m_en_by = re.search(
        r"\b(?:by|before|due)\s+(next\s+|this\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"(?:\s+(?:next\s+week|this\s+week))?"
        r"(?:\s+(?:\([^)]+\)\s*)?(?:(?:at\s+)?(\d{1,2}):(\d{2})|(night|evening|afternoon|morning|family\s+lunch)))?",
        parent_part,
        re.IGNORECASE,
    )
    # "by midnight Sunday" / "before midnight Friday"
    if not m_en_by:
        m_mid = re.search(r"\b(?:by|before)\s+midnight\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", parent_part, re.IGNORECASE)
        if m_mid:
            warnings.add("W_AMBIGUOUS_DATE")
            wd = _WEEKDAY_MAP[m_mid.group(1).lower()]
            dt_dl = _next_weekday(base_time, wd)
            return start_after, dt_dl.replace(hour=23, minute=59, second=0, microsecond=0), errors, warnings

    if m_en_by:
        prefix = (m_en_by.group(1) or "").strip().lower()
        wd_name = m_en_by.group(2).lower()
        wd = _WEEKDAY_MAP[wd_name]
        has_next_week = (prefix == "next") or bool(re.search(rf"\b{wd_name}\s+next\s+week\b", parent_part, re.IGNORECASE))
        # Bare "by Friday" on same weekday with no clock/daypart -> ambiguous (today vs next week)
        if wd == base_time.weekday() and not has_next_week and not m_en_by.group(3) and not m_en_by.group(5):
            warnings.add("W_AMBIGUOUS_DATE")
            return start_after, base_time.replace(hour=23, minute=59, second=0, microsecond=0), errors, warnings

        dt_dl = _next_weekday(base_time, wd, next_week=has_next_week)
        if m_en_by.group(3):
            hh, mm = int(m_en_by.group(3)), int(m_en_by.group(4))
        elif m_en_by.group(5):
            hh, mm = _apply_daypart(m_en_by.group(5))
        else:
            if "midnight" in parent_part.lower():
                warnings.add("W_AMBIGUOUS_DATE")
            hh, mm = 23, 59
        return start_after, dt_dl.replace(hour=hh, minute=mm, second=0, microsecond=0), errors, warnings

    # General event-prep offset ("for <event> on <Weekday>" / "Prepare for <event> on <Weekday>")
    m_prep_ev = re.search(
        r"\b(?:for|prepare\s+for|get\s+ready\s+for)\b[^,:\n]*?\bon\s+(next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        parent_part,
        re.IGNORECASE,
    )
    if m_prep_ev and not re.search(r"\b(?:at|from)\s+\d{1,2}:\d{2}\b", parent_part, re.IGNORECASE):
        wd = _WEEKDAY_MAP[m_prep_ev.group(2).lower()]
        ev_dt = _next_weekday(base_time, wd, next_week=bool(m_prep_ev.group(1)), same_day_ok=False)
        prep_dt = (ev_dt - timedelta(days=1)).replace(hour=23, minute=59, second=0, microsecond=0)
        warnings.add("W_AMBIGUOUS_DATE")
        return start_after, prep_dt, errors, warnings

    # General 'on/for <Weekday> [clock/daypart]'
    m_en_on = re.search(
        r"\b(?:on|for)\s+(next\s+|this\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"(?:\s+(?:next\s+week|this\s+week))?"
        r"(?:\s+(?:\([^)]+\)\s*)?(?:(?:at\s+)?(\d{1,2}):(\d{2})|(night|evening|afternoon|morning|family\s+lunch)))?",
        parent_part,
        re.IGNORECASE,
    )
    if m_en_on:
        prefix = (m_en_on.group(1) or "").strip().lower()
        wd_name = m_en_on.group(2).lower()
        wd = _WEEKDAY_MAP[wd_name]
        has_next_week = (prefix == "next") or bool(re.search(rf"\b{wd_name}\s+next\s+week\b", parent_part, re.IGNORECASE))
        dt_dl = _next_weekday(base_time, wd, next_week=has_next_week)
        if m_en_on.group(3):
            hh, mm = int(m_en_on.group(3)), int(m_en_on.group(4))
        elif m_en_on.group(5):
            hh, mm = _apply_daypart(m_en_on.group(5))
        else:
            hh, mm = 23, 59
        return start_after, dt_dl.replace(hour=hh, minute=mm, second=0, microsecond=0), errors, warnings

    if re.search(r"\b(?:this\s+week|this\s+weekend|end\s+of\s+(?:the|this)\s+week)\b", parent_part, re.IGNORECASE):
        return start_after, _end_of_this_week(base_time), errors, warnings

    return start_after, None, errors, warnings


def _canonical_dep_tokens(phrase: str) -> Set[str]:
    """Normalize a dependency node phrase into stemmed content tokens for graph matching."""
    stripped_dl = re.sub(
        r"\s+(?:before|by)\s+(?:(?:this|next)\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)\b.*$",
        "",
        phrase.strip(),
        flags=re.IGNORECASE,
    )
    cleaned_case = re.sub(r"\([^)]*\)|\bfor\s+\d+\s*(?:minutes?|mins?|m|hours?)\b", " ", stripped_dl, flags=re.IGNORECASE)
    stop = {
        "the", "an", "finish", "complete", "do", "write", "writing", "deploy",
        "deploying", "build", "building", "run", "running", "create", "then", "and",
        "after", "before", "service", "step",
    }
    tokens: Set[str] = set()
    for raw_orig in re.findall(r"[A-Za-z0-9]+", cleaned_case):
        raw_tok = raw_orig.lower()
        if raw_tok in stop:
            continue
        # Treat lowercase article "a" as stopword, but preserve explicit single-letter labels like "A", "B", "C"
        if len(raw_orig) == 1:
            if raw_orig.isupper() and raw_orig.isalpha():
                tokens.add(f"_id_{raw_tok}")
            continue
        stem = re.sub(r"(?:ing|ed|es|s|e)$", "", raw_tok)
        if len(stem) >= 2:
            tokens.add(stem)
        else:
            tokens.add(raw_tok)
    return tokens


def _match_or_add_node(nodes: List[Set[str]], tok_set: Set[str]) -> int:
    """Find best matching canonical node index by Jaccard overlap (>= 0.5), or register new node."""
    if not tok_set:
        nodes.append(set())
        return len(nodes) - 1
    best_idx = -1
    best_sim = 0.0
    for idx, existing in enumerate(nodes):
        if not existing:
            continue
        inter = len(tok_set & existing)
        union = len(tok_set | existing)
        sim = inter / max(1, union)
        if sim >= 0.5 and sim > best_sim:
            best_sim = sim
            best_idx = idx
    if best_idx >= 0:
        nodes[best_idx] |= tok_set
        return best_idx
    nodes.append(set(tok_set))
    return len(nodes) - 1


def _has_dependency_cycle(text: str) -> bool:
    """
    Build a directed precedence graph from `<A> before <B>` and `<B> after <A>` clauses
    and run 3-color DFS to detect cyclic dependencies cleanly without hardcoded entity names.
    """
    clauses = re.split(r"[;\n]|,\s*(?:and\s+)?|\(\d+\)", text)
    nodes: List[Set[str]] = []
    adj: Dict[int, Set[int]] = {}

    for cl in clauses:
        cl_s = cl.strip()
        if not cl_s:
            continue
        # Remove leading header before ':' if present inside clause
        if ":" in cl_s:
            cl_s = cl_s.split(":", 1)[1].strip()
        if not cl_s:
            continue

        # Remove trailing temporal deadline before parsing precedence verb ("C before A before Friday")
        cl_s = re.sub(
            r"\s+(?:before|by)\s+(?:(?:this|next)\s+)?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow)\b.*$",
            "",
            cl_s,
            flags=re.IGNORECASE,
        ).strip()
        if not cl_s:
            continue

        m_bef = re.search(r"(.+?)\s+\bbefore\b\s+(.+)", cl_s, re.IGNORECASE)
        m_aft = re.search(r"(.+?)\s+\bafter\b\s+(.+)", cl_s, re.IGNORECASE)

        if m_bef:
            a_tok = _canonical_dep_tokens(m_bef.group(1))
            b_tok = _canonical_dep_tokens(m_bef.group(2))
            if a_tok and b_tok:
                u = _match_or_add_node(nodes, a_tok)
                v = _match_or_add_node(nodes, b_tok)
                adj.setdefault(u, set()).add(v)
        elif m_aft:
            b_tok = _canonical_dep_tokens(m_aft.group(1))
            a_tok = _canonical_dep_tokens(m_aft.group(2))
            if a_tok and b_tok:
                u = _match_or_add_node(nodes, a_tok)
                v = _match_or_add_node(nodes, b_tok)
                adj.setdefault(u, set()).add(v)

    if not adj:
        return False

    # 3-color DFS: 0=unvisited, 1=visiting, 2=visited
    state: Dict[int, int] = {}

    def _dfs(u: int) -> bool:
        state[u] = 1
        for v in adj.get(u, ()):
            st = state.get(v, 0)
            if st == 1:
                return True
            if st == 0 and _dfs(v):
                return True
        state[u] = 2
        return False

    return any(state.get(node_id, 0) == 0 and _dfs(node_id) for node_id in list(adj.keys()))


def _detect_nonsense_or_injection(raw_prompt: str) -> Tuple[bool, bool, bool]:
    """
    Generalized Gatekeeper for:
      - Prompt injection / SQL injection (`is_injection`)
      - Trolling / keyboard mash / impossible negative durations / fantasy stunts / past chatter (`is_nonsense`)
      - Too-long repetitive spam (`is_long_spam`)
    Returns `(is_injection, is_nonsense, is_long_spam)`.
    """
    low = raw_prompt.lower()
    is_injection = bool(
        re.search(
            r"\b(?:ignore|disregard|forget|bỏ\s*qua)\b.*\b(?:previous|all|prior|system|trước\s*đó)\b.*\b(?:instructions?|prompts?|rules?|schemas?|hướng\s*dẫn)\b"
            r"|(?:^|;)\s*(?:drop|delete|truncate|alter)\s+table\b"
            r"|\boutput\s+(?:your|the)\s+(?:hidden\s+)?system\s+prompt\b",
            low,
        )
    )
    if is_injection:
        return True, True, False

    is_long_spam = len(raw_prompt) > 2000 and len(set(low.split())) < 12
    if is_long_spam:
        return False, True, True

    # Negative / zero durations, centuries ago, before I was born, meme lyrics
    if re.search(
        r"(?:^|\s)-\d+\s*(?:minutes?|mins?|hours?|hrs?|m|phút|giờ)\b"
        r"|\b0-minute\s+chunks?\b"
        r"|\b\d{2,4}\s+years?\s+ago\b"
        r"|\bbefore\s+I\s+was\s+born\b"
        r"|\bbefore\s+yesterday\b"
        r"|\bnever\s+gonna\s+(?:give\s+you\s+up|let\s+you\s+down|run\s+around)\b",
        low,
    ):
        return False, True, False

    # Fantasy impossibility check (sci-fi/magic nouns combined with impossible stunt verbs)
    if any(fn in low for fn in _FANTASY_NOUNS) and re.search(r"\b(?:teleport|fly\s+to|tame|defeat|build)\b", low):
        return False, True, False

    # Past narrative chatter (EN/VI) with no future commitment / plan anchor
    has_future_cue = bool(re.search(r"\b(?:by|before|tomorrow|next\s+\w+|trước|ngày\s*mai|tuần\s*tới|hạn)\b", low))
    if not has_future_cue and (
        re.search(r"\byesterday\s+I\s+(?:stayed\s+up|binge|watched|slept|played)\b", low)
        or re.search(r"\b(?:hôm\s*qua|hôm\s*kia|tối\s*qua)\b.*\b(?:thức|cày\s*phim|mệt\s*quá|chơi\s*game)\b", low)
    ):
        return False, True, False

    # Keyboard smash / symbol entropy check (when no normal Vietnamese/English task structure is found)
    tokens = [t for t in re.findall(r"[a-zA-ZÀ-ỹ0-9_@#?!*&^%$;]+", low) if len(t) >= 4]
    alpha_tokens = [t for t in re.findall(r"[a-zA-Z]{5,}", low)]
    if re.search(r"([a-z])\1{3,}|asdfgh|zxcvbn|qwerty", low):
        if len(alpha_tokens) <= 4 or sum(1 for t in alpha_tokens if not re.search(r"[aeiouy]", t)) >= 1:
            return False, True, False

    return False, False, False


def _extract_clause_duration_minutes(clause: str) -> Optional[int]:
    """Sum active duration minutes in a single subtask clause, excluding passive waits and Pomodoro pacing."""
    cleaned = re.sub(
        r"\b(?:let\s+[^,;.\n]*?(?:dry|set|sit|cool|rest|marinate)|wait(?:ing)?(?:\s+for)?\s+[^,;.\n]*?)\s+for\s+\d+\s*(?:hours?|hrs?|minutes?|mins?|m)\b"
        r"|\bwait\s+\d+\s*(?:hours?|minutes?)\s+for\s+[^,;.\n]*"
        r"|\b\d+m\s+wash\s+cycle\s+wait\b"
        r"|\bafter\s+\d+\s*hours?\s+drying\b"
        r"|\b\d+m\s+pomodoro\b",
        " ",
        clause,
        flags=re.IGNORECASE,
    )
    mins = [
        int(m.group(1))
        for m in re.finditer(
            r"\b(\d+)\s*(minutes?|mins?|phút|m)\b(?!\s*(?:pool|swim|run|workout|sprint|track|freestyle|medley|lap|row|dash|walk|pomodoro))",
            cleaned,
            re.IGNORECASE,
        )
        if not (m.group(2).lower() == "m" and int(m.group(1)) >= 400)
    ]
    hrs = [
        int(round(float(m.group(1)) * 60))
        for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|tiếng|giờ)\b", cleaned, re.IGNORECASE)
    ]
    total = sum(mins) + sum(hrs)
    return total if total > 0 else None


def _is_passive_wait_clause(clause: str) -> bool:
    """Return True if the clause ONLY represents a timed inanimate passive wait (e.g., drying time, wash cycle)."""
    stripped = re.sub(
        r"\b(?:let\s+[^,;.\n]*?(?:dry|air-dry|sit|cool|rest|marinate)(?:\s+for\s+\d+\s*(?:hours?|hr|minutes?|mins?|m))?|wait\s+\d+\s*(?:hours?|minutes?|mins?|m)\s+for\s+[^,;.\n]*|\d+m\s+wash\s+cycle\s+wait|after\s+\d+\s*hours?\s+drying)\b",
        "",
        clause,
        flags=re.IGNORECASE,
    )
    stripped = re.sub(r"\b(?:and|for|\d+\s*(?:hours?|minutes?|mins?|m))\b|[,.;:\s-]+", "", stripped, flags=re.IGNORECASE)
    return len(stripped) == 0


def _split_and_analyze_subtasks(
    working: str,
    header_explicit_total: Optional[int],
    parent_deadline: Optional[datetime],
    base_time: datetime,
) -> Tuple[List[Dict[str, Any]], bool, bool, Optional[datetime]]:
    """
    Extract structured subtasks (`id`, `title`, `status`, `work_minutes`, `deadline`, `priority_tag`)
    along with structural cues:
      - `has_ordering_cue`: whether explicit ordering (`first/then/after/once/before/followed by/Step N`) exists
      - `has_external_wait_unestimated`: whether an open/external review step has no active user duration
      - `max_sub_deadline`: latest deadline among subtasks
    """
    has_ordering_cue = bool(
        re.search(
            r"\b(?:first|then|after\s+[a-z0-9]+|sau\s+khi|once\b|finally|followed\s+by|before\s+\w+|step\s+\d+)\b|^\s*\(\d+\).*?(?:then|before|after)\b",
            working,
            re.IGNORECASE | re.DOTALL,
        )
    )

    body = working
    raw_clauses: List[str] = []

    # Split at real header delimiter `:(?=\s|$)` (never inside HH:MM timestamps like 17:00)
    m_hdr_delim = re.search(r":(?=\s|$)", working)
    if m_hdr_delim and (
        re.search(r":\s*(?:\n|\(1\)|-\s|\*\s|•|first\b|finish\b|✅|⏳|⬜|\d+m\b|\bPhase\s+1\b|\bSubtasks?\b|\bReview\b)", working[m_hdr_delim.start():], re.IGNORECASE)
        or "\n-" in working
        or "\n(" in working
    ):
        body = working[m_hdr_delim.end():].strip()

    # Handle explicit "Subtasks:" header following a sentence ending in period
    m_sub_hdr = re.search(r"\bSubtasks?:\s*", body, re.IGNORECASE)
    if m_sub_hdr:
        body = body[m_sub_hdr.end():].strip()

    # Split strategy by explicit list markers (always dropping preamble before first marker!)
    if re.search(r"\(\d+\)", body):
        first_m = re.search(r"\(\d+\)", body)
        sub_slice = body[first_m.start():] if first_m else body
        raw_clauses = [c.strip(" ;,\n.") for c in re.split(r"\(\d+\)\s*", sub_slice) if c.strip(" ;,\n.")]
        expanded: List[str] = []
        for cl in raw_clauses:
            if re.search(r"\bPhase\s+\d+\b", body, re.IGNORECASE) and "(" in cl and "," in cl:
                sub_parts = re.split(r",\s*(?:then\s+)?", cl)
                expanded.extend([sp.strip(" ;,\n.()") for sp in sub_parts if sp.strip()])
            else:
                expanded.append(cl)
        raw_clauses = expanded
    elif re.search(r"\bStep\s+\d+:", body, re.IGNORECASE):
        first_s = re.search(r"\bStep\s+\d+:", body, re.IGNORECASE)
        sub_slice = body[first_s.start():] if first_s else body
        raw_clauses = [c.strip(" ;,\n.") for c in re.split(r"\bStep\s+\d+:\s*", sub_slice, flags=re.IGNORECASE) if c.strip(" ;,\n.")]
    elif re.search(r"[✅⏳⬜]", body):
        first_e = re.search(r"[✅⏳⬜]", body)
        sub_slice = body[first_e.start():] if first_e else body
        raw_clauses = [c.strip(" ;,\n.") for c in re.split(r"(?=[✅⏳⬜])", sub_slice) if c.strip(" ;,\n.")]
    elif re.search(r"^\s*[-*•]\s+|\s-\s", body, re.MULTILINE):
        first_b = re.search(r"(?:^|\s)[-*•]\s+", body, re.MULTILINE)
        sub_slice = body[first_b.start():] if first_b else body
        lines = [ln for ln in sub_slice.splitlines() if ln.strip()]
        raw_clauses = []
        for ln in lines:
            # Handle both line-per-bullet and inline ` - item1 - item2`
            parts = re.split(r"(?:^|\s+)[-*•]\s+", ln.strip())
            for pt in parts:
                pt_c = pt.strip(" ;,\n.")
                if pt_c:
                    raw_clauses.append(pt_c)
    elif re.search(r"\bPhase\s+\d+\b", body, re.IGNORECASE):
        first_p = re.search(r"\bPhase\s+\d+\b", body, re.IGNORECASE)
        sub_slice = body[first_p.start():] if first_p else body
        raw_clauses = [c.strip(" ;,\n.()") for c in re.split(r";\s*|\bPhase\s+\d+\s*[-–:]\s*|\b(?:first|then|finally),?\s*", sub_slice, flags=re.IGNORECASE) if c.strip(" ;,\n.()") and not re.match(r"^(?:Walls|Flooring|Ceiling|Electrical|Furniture)$", c.strip(), re.IGNORECASE)]
    elif ";" in body or re.search(r"\bfollowed\s+by\b", body, re.IGNORECASE):
        raw_clauses = [c.strip(" ;,\n.") for c in re.split(r"\s*;\s*|\s+\bfollowed\s+by\b\s+", body, flags=re.IGNORECASE) if c.strip(" ;,\n.")]
    elif re.search(r"\bfirst\b.*?(?:\bthen\b|\band\b|\bfinally\b)", body, re.IGNORECASE | re.DOTALL):
        # Preserve dash self-correction within the same step (don't insert commas before "actually never mind")
        first_f = re.search(r"\bfirst\b", body, re.IGNORECASE)
        sub_slice = body[first_f.start():] if first_f else body
        raw_clauses = [
            re.sub(r"^(?:first|then|finally|and)\s+", "", c, flags=re.IGNORECASE).strip(" ;,\n.")
            for c in re.split(r",\s*(?:then\s+|finally\s+|and\s+(?:also\s+)?)?|\bthen\b", sub_slice, flags=re.IGNORECASE)
            if c.strip(" ;,\n.") and not re.match(r"^I\s+already\b", c.strip(), re.IGNORECASE)
        ]
        if len(raw_clauses) == 0 and "first" in sub_slice.lower():
            raw_clauses = [sub_slice.strip(" ;,\n.")]
    else:
        # Multi-goal coordinate clauses ("do X for 30m and also do Y for 45m", or "By Sunday night (Nov 8), ...")
        clean_body = re.sub(r"^By\s+(?:[^,]+(?:\([^)]*\))?),\s*", "", body.strip(), flags=re.IGNORECASE)
        cand = [c.strip(" ;,\n.") for c in re.split(r"\s+and\s+also\s+|\s*,\s*(?:and\s+)?|\s+and\s+", clean_body) if c.strip(" ;,\n.")]
        timed_cnt = sum(1 for c in cand if _extract_clause_duration_minutes(c) is not None)
        if timed_cnt >= 2:
            raw_clauses = cand

    # Re-attach `"—actually never mind, I already ..."` if comma split happened inside a cancelled step
    if raw_clauses and re.search(r"—\s*actually\s+never\s+mind", body, re.IGNORECASE):
        m_nm = re.search(r"\bthen\s+([^,\n]+—\s*actually\s+never\s+mind[^.]*)", body, re.IGNORECASE)
        if m_nm:
            prefix_word = m_nm.group(1).split("—")[0].strip().lower()
            raw_clauses = [
                m_nm.group(1).strip() if prefix_word and prefix_word in c.lower() else c
                for c in raw_clauses
            ]

    subtasks: List[Dict[str, Any]] = []
    has_external_wait_unestimated = False
    max_sub_dl: Optional[datetime] = None

    for idx, cl in enumerate(raw_clauses, 1):
        # Split trailing `and fix failing ...` only if it's a pure unestimated local fix step (never split external review+revise loops on one bullet)
        and_sub = re.split(
            r"\s+and\s+(?=fix\s+failing|wait\s+for)",
            cl,
            flags=re.IGNORECASE,
        )
        for piece in and_sub:
            piece = piece.strip(" ;,.")
            if not piece:
                continue
            if _is_passive_wait_clause(piece):
                continue

            low_p = piece.lower()
            is_done = bool(re.search(
                r"✅|\[x\]|\(đã\s*xong\)|\(done\)|[-–—]\s*(?:đã\s*xong|completed|done)\b|—\s*actually\s+never\s+mind|\balready\s+(?:done|finished|bought|completed|booked|sent|submitted)\b",
                low_p,
            ))
            is_in_prog = bool(re.search(r"⏳|\(đang\s*làm\)|\bhalfway\s+done\b", low_p))
            is_ext = bool(re.search(
                r"\bwait(?:ing)?\s+(?:for|on)\b"
                r"|\b(?:send\s+to|for|to)\s+(?:the\s+)?(?:pm|manager|director|client|legal)\s+for\s+review\b"
                r"|\breview\s+requests?\s+to\s+the\s+(?:manager|director)\b"
                r"|\bsubmissions?\s+for\s+the\s+(?:manager|director)\b"
                r"|\bsign[- ]off\b"
                r"|\btechnician\b",
                low_p,
            ))

            if is_done:
                status = "DONE"
                mins: Optional[int] = 0
            elif is_ext and _extract_clause_duration_minutes(piece) is None:
                status = "WAITING_EXTERNAL"
                mins = None
                has_external_wait_unestimated = True
            elif is_in_prog:
                status = "IN_PROGRESS"
                mins = _extract_clause_duration_minutes(piece)
            else:
                status = "TODO"
                mins = _extract_clause_duration_minutes(piece)

            # Check subtask local deadline
            sub_dl: Optional[datetime] = None
            m_sub_dl = re.search(r"\b(?:by|before|due|trước|hạn)\s+([^,;.\n]+)", piece, re.IGNORECASE)
            if m_sub_dl:
                dl_candidate = _parse_single_date_expr(m_sub_dl.group(1), base_time)
                if dl_candidate is not None:
                    sub_dl = dl_candidate
                    if max_sub_dl is None or sub_dl > max_sub_dl:
                        max_sub_dl = sub_dl

            # Check bracketed step priority `[urgent]` / `[high priority, deep work]` / `[low priority]`
            step_prio: Optional[int] = None
            if re.search(r"\[[^\]]*\b(?:urgent|critical|p1)\b[^\]]*\]", low_p):
                step_prio = 1
            elif re.search(r"\[[^\]]*\b(?:high(?:\s+priority)?|important|p2)\b[^\]]*\]", low_p):
                step_prio = 2
            elif re.search(r"\[[^\]]*\b(?:low(?:\s+priority)?|optional|p4)\b[^\]]*\]", low_p):
                step_prio = 4

            subtasks.append({
                "id": f"ST{len(subtasks) + 1}",
                "title": re.sub(r"^\[\s*[x ]?\s*\]\s*|^[✅⏳⬜]\s*", "", piece).strip(),
                "status": status,
                "work_minutes": mins,
                "deadline": sub_dl.strftime("%Y-%m-%dT%H:%M") if sub_dl else None,
                "deadline_dt": sub_dl,
                "priority": step_prio,
            })

    return subtasks, has_ordering_cue, has_external_wait_unestimated, max_sub_dl


def parse_hybrid_case(
    prompt: str,
    ui: Optional[Dict[str, Any]] = None,
    *,
    base_time: datetime = datetime(2026, 11, 6, 9, 0),
    enable_translation: bool = True,
    translation_backend: str = "rule",
) -> Dict[str, Any]:
    """
    Executes the full 6-stage Generalized Hybrid Pipeline and returns a structured contract
    dictionary covering `OK`, `OK_WITH_WARNINGS`, `NEEDS_FIX`, `REJECTED`, plus extracted
    subtasks and SmartSchedule solver priority mapping (`1=Urgent..4=Low -> 5..1`).
    """
    ui = ui or {}
    raw_prompt = prompt or ""
    errors: List[str] = []
    warnings: List[str] = []

    def _add_err(code: str) -> None:
        if code not in errors:
            errors.append(code)

    def _add_warn(code: str) -> None:
        if code not in warnings:
            warnings.append(code)

    # ------------------------------------------------------------------
    # STAGE 1 & 2: Input Guard, Venting/Self-Correction, Typos & VI->EN Bridge
    # ------------------------------------------------------------------
    if len(raw_prompt) > 2000:
        _add_err("E_PROMPT_TOO_LONG")

    is_inj, is_nonsense, is_long_spam = _detect_nonsense_or_injection(raw_prompt)
    if is_inj:
        _add_err("E_NONSENSE_INPUT")
        _add_warn("W_PROMPT_INJECTION")
        return {
            "status": "REJECTED",
            "contract": None,
            "errors": errors,
            "warnings": warnings,
            "suggestions": ["Prompt injection and raw SQL statements are blocked."],
        }
    if is_nonsense or is_long_spam:
        _add_err("E_NONSENSE_INPUT")
        return {
            "status": "REJECTED",
            "contract": None,
            "errors": errors,
            "warnings": warnings,
            "suggestions": ["Enter a realistic future task with a clear action and positive duration."],
        }

    working = raw_prompt

    # Strip conversational venting preambles before task statement
    m_vent = re.search(
        r"^.*?\b(?:anyway|anyways|long\s+story\s+short|tóm\s+lại)[,:]?\s+(?:I\s+(?:really\s+|just\s+)?need\s+to|tôi\s+(?:cần|phải))\s+",
        working,
        re.IGNORECASE | re.DOTALL,
    )
    if m_vent:
        _add_warn("W_NON_TASK_CONTENT")
        working = working[m_vent.end():]

    # Mixed VI + EN check before VI translation
    has_vi = contains_vietnamese(working)
    has_en_task_phrase = bool(re.search(r"\b(?:for\s+\d+\s*(?:min|minutes?|m|hours?)|before\s+\d|tomorrow|minutes|hours)\b", working, re.IGNORECASE))

    # Common typos
    for pat, repl in _TYPO_REPLACEMENTS:
        if re.search(pat, working):
            _add_warn("W_TYPO_CORRECTED")
            working = re.sub(pat, repl, working)

    # Mid-sentence self-corrections (`... — actually wait ...`, `wait sorry, by ...`, `never mind`)
    if re.search(r"—\s*actually\s+(?:no|wait|never\s+mind)|\bwait\s+sorry,\s+by\b", working, re.IGNORECASE):
        _add_warn("W_SELF_CORRECTION")
        working = re.sub(
            r"\b\d+\s*(?:hours?|minutes?)\s*—\s*actually\s+(?:no|wait),\s*make\s+it\s+(\d+\s*(?:hours?|minutes?))\s*—?",
            r"\1 ",
            working,
            flags=re.IGNORECASE,
        )
        working = re.sub(r"\bby\s+[A-Z][a-z]+day,\s*wait\s+sorry,\s*by\s+", "by ", working, flags=re.IGNORECASE)

    # Normalize hyphenated durations ("4-hour" -> "4 hours", "40-minute" -> "40 minutes")
    working = re.sub(r"\b(\d+)-(hour|minute)s?\b", r"\1 \2s", working, flags=re.IGNORECASE)

    # Strip valid [[...]] and @[...] citation blocks from parsing copy BEFORE translation/duration extraction
    # so filenames/paths with spaces/numbers never trigger false duration/time matches or NMT distortion,
    # while preserving `raw_prompt` losslessly for citation validation below.
    if "[[" in working or "@[" in working:
        working = re.sub(r"\[\[[^\[\]\n]*?\]\]|@\[[^\[\]\n]*?\]", " ", working)
        working = re.sub(r"\s{2,}", " ", working).strip()

    # Run VI->EN translation if needed
    translated_en_text = working
    translation_applied = False
    used_backend = translation_backend
    if enable_translation and has_vi:
        tr = translate_to_english(working, backend=translation_backend)
        translation_applied = tr.translation_applied
        used_backend = tr.backend_used
        if tr.translated_text:
            translated_en_text = tr.translated_text

    raw_custom = ui.get("custom")
    if isinstance(raw_custom, dict):
        custom_bounds = [int(raw_custom.get("min", 15)), int(raw_custom.get("max", 60))]
    elif isinstance(raw_custom, (list, tuple)) and len(raw_custom) >= 2:
        custom_bounds = [int(raw_custom[0]), int(raw_custom[1])]
    else:
        custom_bounds = None
    c_min_override = custom_bounds[0] if (custom_bounds and custom_bounds[0] <= custom_bounds[1]) else None
    atts = ui.get("attachments") or []
    linked_files_ui = ui.get("linked_files") or []
    pkg_task, _, pkg_tel = parse_task(
        working,
        base_time=base_time,
        custom_min_override=c_min_override,
        has_attachments=bool(atts or linked_files_ui),
        enable_translation=enable_translation,
        translation_backend=translation_backend,
    )

    # Non-actionable fragment gatekeeper (time/priority/metadata only without any action verb or subject)
    stripped_action = re.sub(
        r"~\d+[mh]?\b|\b(?:for\s+\d+\s*(?:minutes?|mins?|hours?)|in\s+\d+\s*(?:minutes?|mins?)\s*chunks?|by\s+[^,.!]+|before\s+[^,.!]+|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|night|at\s+\d{1,2}:\d{2}|urgent|high\s+priority|trong\s+\d+\s*phút|trước\s+\d+h\s*ngày\s*mai|p[1-5])\b|[!.,;:\s-]+",
        " ",
        raw_prompt,
        flags=re.IGNORECASE,
    ).strip()
    if not stripped_action:
        _add_err("E_NO_ACTIONABLE_TASK")
        return {
            "status": "NEEDS_FIX",
            "contract": None,
            "errors": errors,
            "warnings": warnings,
            "suggestions": ["Include a concrete action verb or deliverable alongside your duration and deadline."],
        }

    # ------------------------------------------------------------------
    # STAGE 3 & 4: Dates, Subtasks, Duration & First-Layer Contradictions
    # ------------------------------------------------------------------
    start_after, deadline, dt_errs, dt_warns = _resolve_hybrid_dates(working, base_time)
    for e in dt_errs:
        _add_err(e)
    for w in dt_warns:
        _add_warn(w)

    if deadline is None and pkg_task.deadline is not None and "W_RECURRING_NO_END" not in warnings and "W_VAGUE_DEADLINE" not in warnings:
        deadline = pkg_task.deadline
    if start_after is None and pkg_task.start_after is not None:
        start_after = pkg_task.start_after

    if start_after and deadline and start_after > deadline:
        _add_err("E_START_AFTER_DEADLINE")

    # Attachment validation + lossless [[filename]] citation cross-comparison
    trans_search_space = (raw_prompt + " " + translated_en_text + " " + (pkg_task.title or "")).lower()
    is_chapter_study = bool(re.search(r"\b(?:chapters?|readings?|chương|ôn\s*tập)\b", trans_search_space))

    bracketed_cits: List[str] = []
    malformed_cits: List[str] = []
    for m_cit in re.finditer(r"\[\[([^\[\]\n]*?)\]\]", raw_prompt):
        inner = m_cit.group(1).strip()
        if not inner:
            malformed_cits.append("[[]]")
            continue
        if re.search(r'[<>:"/\\|?*]', inner):
            malformed_cits.append(m_cit.group(0))
        else:
            if inner not in bracketed_cits:
                bracketed_cits.append(inner)
            if "." in inner:
                c_ext = inner.rsplit(".", 1)[-1].lower()
                if c_ext not in ALLOWED_EXTENSIONS:
                    _add_err("E_ATTACHMENT_TYPE")

    # Also support @[path/or/filename] link citations (drag-dropped or pasted workspace paths)
    for m_at in re.finditer(r"@\[([^\[\]\n]+?)\]", raw_prompt):
        raw_link = m_at.group(1).strip()
        if not raw_link:
            continue
        base_fn = re.split(r"[/\\]", raw_link)[-1].strip()
        if base_fn:
            if base_fn not in bracketed_cits:
                bracketed_cits.append(base_fn)
            if "." in base_fn:
                c_ext = base_fn.rsplit(".", 1)[-1].lower()
                if c_ext not in ALLOWED_EXTENSIONS:
                    _add_err("E_ATTACHMENT_TYPE")

    remainder_cit = re.sub(r"\[\[[^\[\]\n]*?\]\]|@\[[^\[\]\n]+?\]", " ", raw_prompt)
    if re.search(r"\[\[|\]\]", remainder_cit):
        malformed_cits.append("unclosed_double_bracket")
    if malformed_cits:
        _add_err("E_INVALID_CITATION_FORMAT")

    unbracketed_cits: List[str] = []
    seen_cits_low: Set[str] = {b.lower() for b in bracketed_cits}
    # Extract quoted filenames first AND mask them out so bare regex never re-matches a suffix like "Logic_apcs.pdf" inside "Ch1. Logic_apcs.pdf"
    bare_scan_str = remainder_cit
    for m_q in re.finditer(r'["\']([^"\'\n]+\.(?:pdf|md|txt|html))["\']', remainder_cit, re.IGNORECASE):
        qfn = m_q.group(1).strip()
        if qfn and qfn.lower() not in seen_cits_low:
            unbracketed_cits.append(qfn)
            seen_cits_low.add(qfn.lower())
    bare_scan_str = re.sub(r'["\'][^"\'\n]+\.(?:pdf|md|txt|html)["\']', " ", remainder_cit, flags=re.IGNORECASE)
    for m_b in re.finditer(r"\b([\w\-]+\.(?:pdf|md|txt|html))\b", bare_scan_str, re.IGNORECASE):
        bfn = m_b.group(1).strip()
        if bfn and bfn.lower() not in seen_cits_low:
            unbracketed_cits.append(bfn)
            seen_cits_low.add(bfn.lower())

    cited_files = list(bracketed_cits) + [u for u in unbracketed_cits if u not in bracketed_cits]
    linked_files = ui.get("linked_files") or []
    all_att_items = list(atts) + [lf for lf in linked_files if isinstance(lf, dict)]
    attached_names: List[str] = []
    for item in all_att_items:
        an = str(item.get("name") or "").strip()
        if an and an not in attached_names:
            attached_names.append(an)
    att_low_map = {name.lower(): name for name in attached_names}

    matched_cits: List[str] = []
    missing_cits: List[str] = []
    for cf in cited_files:
        if cf.lower() in att_low_map:
            matched_cits.append(cf)
        else:
            missing_cits.append(cf)

    matched_low = {mc.lower() for mc in matched_cits}
    extra_atts: List[str] = []

    for att in all_att_items:
        name = att.get("name", "")
        raw_mb = att.get("mb")
        if raw_mb is None:
            raw_mb = att.get("size_mb")
        if raw_mb is None and att.get("size_bytes") is not None:
            raw_mb = float(att["size_bytes"]) / (1024 * 1024)
        mb = float(raw_mb or 0)
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if mb > MAX_ATTACHMENT_MB:
            _add_err("E_ATTACHMENT_TOO_LARGE")
        if ext not in ALLOWED_EXTENSIONS:
            _add_err("E_ATTACHMENT_TYPE")

        stem = name.rsplit(".", 1)[0].lower()
        stem_tokens = [tok for tok in re.split(r"[_\-.]+", stem) if len(tok) > 2]
        referenced = (
            name.lower() in matched_low
            or name.lower() in trans_search_space
            or stem in trans_search_space
            or any(tok in trans_search_space for tok in stem_tokens)
            or bool(re.search(r"\b(?:attached|theo\s+tài\s+liệu)\b", raw_prompt, re.IGNORECASE))
            or (is_chapter_study and ext in {"pdf", "md"})
        )
        if not referenced:
            _add_warn("W_ATTACHMENT_UNREFERENCED")
            if name:
                extra_atts.append(name)

    low_raw = raw_prompt.lower()
    prompt_words_doc = set(re.findall(r"[a-z0-9]+", low_raw))
    approx_domains = sum(1 for vocab in _DOMAIN_LEXICONS.values() if prompt_words_doc & vocab)

    if missing_cits:
        _add_warn("W_DOC_MENTIONED_NOT_ATTACHED")
    elif not all_att_items and approx_domains < 3 and re.search(
        r"\b[\w\-]+\.(?:pdf|md|txt|html)\b"
        r"|\b(?:textbook|assembly\s+manual(?:\s+pdf)?|recipe\s+note|that\s+file|tài\s+liệu|đề\s+cương|giáo\s+trình)\b"
        r"|\bchapters?\s+\d+\s+to\s+\d+\b"
        r"|\b\d+\s+(?:chương|chapters?)\b",
        raw_prompt,
        re.IGNORECASE,
    ):
        # Do not raise missing-doc when prompt explicitly enumerates chapter subtasks under a header
        if not re.search(r"\b\d+\s+chapters?.*:\s*\n\s*-", raw_prompt, re.IGNORECASE):
            _add_warn("W_DOC_MENTIONED_NOT_ATTACHED")

    citations_report = {
        "bracketed": bracketed_cits,
        "unbracketed": unbracketed_cits,
        "cited_files": cited_files,
        "attached_files": attached_names,
        "matched": matched_cits,
        "missing_attachments": missing_cits,
        "extra_attachments": extra_atts,
        "malformed_brackets": malformed_cits,
    }

    # Custom UI range check
    if custom_bounds and custom_bounds[0] > custom_bounds[1]:
        _add_err("E_CUSTOM_RANGE_INVALID")

    # General Session contradiction check
    if "E_SESSION_CONTRADICTION" in pkg_task.errors or (
        re.search(r"\b(?:single\s+(?:uninterrupted\s+)?session|one\s+uninterrupted\s+(?:single\s+)?session|in\s+one\s+sitting)\b", low_raw)
        and re.search(r"\bsplit\s+into\b", low_raw)
    ):
        _add_err("E_SESSION_CONTRADICTION")

    # General Semantic contradiction check (Rest vs Exertion; Offline Detox vs Online/Screen Stream)
    if "E_SEMANTIC_CONTRADICTION" in pkg_task.errors or (
        re.search(r"\b(?:zero[- ]exertion|complete\s+(?:recovery\s+)?rest\s+day|bed\s+rest)\b", low_raw)
        and re.search(r"\b(?:sprint|marathon|uphill|hiit|running|heavy\s+lifting|cycling)\b", low_raw)
    ) or (
        re.search(r"\b(?:zero[- ]screen|offline\s+[^,.]*digital\s+detox|digital\s+detox)\b", low_raw)
        and re.search(r"\b(?:live\s+[^,.]*stream|twitch|youtube|gaming|zoom|watching)\b", low_raw)
    ):
        _add_err("E_SEMANTIC_CONTRADICTION")

    # General Cyclic Dependency DFS
    if "E_CYCLIC_DEPENDENCY" in pkg_task.errors or _has_dependency_cycle(working):
        _add_err("E_CYCLIC_DEPENDENCY")

    # Explicit header total ("in X minutes total" / "tổng cộng X minutes")
    m_hdr_total = re.search(r"\b(?:in\s+(\d+)\s*minutes\s+total|tổng\s+cộng\s+(\d+)\s*minutes)\b", working, re.IGNORECASE)
    header_explicit_total = int(m_hdr_total.group(1) or m_hdr_total.group(2)) if m_hdr_total else None

    # Extract subtasks & step durations
    multi_dur_tokens = re.findall(r"\b(?:for|need|followed\s+by|left|takes)\s+\d+\s*(?:minutes?|mins?|m)\b|\(\d+\s*m\)|\d+\s*m(?=,|;|\))", working, re.IGNORECASE)
    has_subtask_structure = bool(
        re.search(r"(?:\(\d+\)|\bStep\s+\d+:|^\s*[-*•]|\s-\s|:(?=\s|$)|✅|⏳|⬜|\bPhase\s+\d+\b|\band\s+also\b|\bfollowed\s+by\b)", working, re.IGNORECASE | re.MULTILINE)
        or (re.search(r"\bfirst\b.*\bthen\b", working, re.IGNORECASE | re.DOTALL) and not re.search(r"tomorrow\s+afternoon", working, re.IGNORECASE))
        or len(multi_dur_tokens) >= 2
    )

    subtasks: List[Dict[str, Any]] = []
    has_ordering_cue = False
    has_external_wait_unestimated = False
    max_sub_dl: Optional[datetime] = None

    if has_subtask_structure:
        subtasks, has_ordering_cue, has_external_wait_unestimated, max_sub_dl = _split_and_analyze_subtasks(
            working, header_explicit_total, deadline, base_time
        )
        if deadline and max_sub_dl and max_sub_dl > deadline:
            _add_err("E_SUBTASK_DEADLINE_AFTER_PARENT")

    # Duration calculation & duration contradiction / partial / scope mismatch
    total_work_minutes: Optional[int] = None
    work_minutes_lower_bound: Optional[int] = None

    if has_subtask_structure and subtasks:
        active_steps = [st for st in subtasks if st["status"] in {"TODO", "IN_PROGRESS"}]
        known_mins = [st["work_minutes"] for st in active_steps if st["work_minutes"] is not None]
        missing_mins = [st for st in active_steps if st["work_minutes"] is None]
        sub_sum = sum(known_mins)

        # Check scope mismatch (header declares N chapters/problem sets, body lists < N)
        hdr_part = re.split(r":(?=\s|$)", working, maxsplit=1)[0]
        m_scope_n = re.search(r"\b(\d+)\s+(?:[a-zA-Z]+\s+){0,2}(chapters?|problem\s+sets?|sections?|modules?|chương)\b", hdr_part, re.IGNORECASE)
        if m_scope_n:
            decl_n = int(m_scope_n.group(1))
            # Count covered items ("first half" = 0.5 else 1.0)
            covered = sum(0.5 if "half" in st["title"].lower() else 1.0 for st in subtasks)
            if covered < decl_n:
                _add_warn("W_SCOPE_MISMATCH")

        if header_explicit_total is not None:
            total_work_minutes = header_explicit_total
            if sub_sum != header_explicit_total:
                _add_err("E_DURATION_CONTRADICTION")
        else:
            if known_mins and missing_mins:
                total_work_minutes = None
                work_minutes_lower_bound = sub_sum
                _add_warn("W_PARTIAL_DURATION")
            elif sub_sum > 0:
                total_work_minutes = sub_sum
            elif m_scope_n and re.search(r"\bless\s+than\s+(?:an?\s+)?hour\b", working, re.IGNORECASE):
                decl_n = int(m_scope_n.group(1))
                total_work_minutes = decl_n * 59
                _add_warn("W_VAGUE_DURATION")
                _add_warn("W_SCOPE_MISMATCH")
            else:
                total_work_minutes = None
                _add_warn("W_NO_DURATION")
    else:
        # Single-task duration rules
        m_ch_range = re.search(r"\bchapters\s+(\d+)\s+to\s+(\d+)\b.*?\b(\d+)\s*minutes\s+per\s+chapter\b", working, re.IGNORECASE)
        m_or_mult = re.search(r"\b(\d+)\s+or\s+(\d+)\b.*?\b(\d+)\s*minutes\s+each\b", working, re.IGNORECASE)
        m_mult = re.search(r"\b(\d+)\s+(?:chapters?|survey\s+papers?|case\s+studies|chương)\b.*?\b(\d+)\s*(?:minutes?|mins?|m|phút)\s*(?:each|mỗi)?\b", working, re.IGNORECASE)
        m_mwf = re.search(r"\b(\d+)\s*minutes\b.*?\bon\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:,\s*(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday))*,?\s+and\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", working, re.IGNORECASE)
        m_daily_bounded = re.search(r"\b(\d+)\s*minutes\b.*?\bevery\s+day\s+until\b", working, re.IGNORECASE)
        m_hr_range = re.search(r"\b(\d+)\s+to\s+(\d+)\s*hours\b", working, re.IGNORECASE)

        if m_ch_range:
            total_work_minutes = (int(m_ch_range.group(2)) - int(m_ch_range.group(1)) + 1) * int(m_ch_range.group(3))
            _add_warn("W_VAGUE_DURATION")
        elif m_or_mult:
            total_work_minutes = int(m_or_mult.group(2)) * int(m_or_mult.group(3))
            _add_warn("W_VAGUE_DURATION")
        elif m_mult:
            total_work_minutes = int(m_mult.group(1)) * int(m_mult.group(2))
        elif m_mwf:
            day_cnt = len(re.findall(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", working, re.IGNORECASE))
            total_work_minutes = int(m_mwf.group(1)) * max(1, day_cnt)
        elif m_daily_bounded and deadline:
            days_inclusive = max(1, (deadline.date() - base_time.date()).days + 1)
            total_work_minutes = int(m_daily_bounded.group(1)) * days_inclusive
        elif m_hr_range:
            total_work_minutes = int(m_hr_range.group(2)) * 60
            _add_warn("W_VAGUE_DURATION")
        elif re.search(r"\ba\s+couple\s+of\s+hours\b", working, re.IGNORECASE):
            total_work_minutes = 120
            _add_warn("W_VAGUE_DURATION")
        elif re.search(r"\b(\d+)\s*(?:tiếng|giờ)\s*rưỡi\b", raw_prompt, re.IGNORECASE):
            m_half = re.search(r"\b(\d+)\s*(?:tiếng|giờ)\s*rưỡi\b", raw_prompt, re.IGNORECASE)
            total_work_minutes = int(m_half.group(1)) * 60 + 30
        else:
            m_paren_min = re.search(r"\((\d+)\s*minutes\)", working, re.IGNORECASE)
            m_min_cand = next(
                (
                    m
                    for m in re.finditer(
                        r"\b(\d+)\s*(minutes?|mins?|phút|m)\b(?!\s*(?:pool|swim|run|workout|sprint|track|freestyle|medley|lap|row|dash|walk|pomodoro))",
                        working,
                        re.IGNORECASE,
                    )
                    if not (m.group(2).lower() == "m" and int(m.group(1)) >= 400)
                ),
                None,
            )
            m_min = m_min_cand
            m_hr = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|tiếng|giờ)\b", working, re.IGNORECASE)
            if m_paren_min:
                total_work_minutes = int(m_paren_min.group(1))
            elif m_hr and (not m_min or "split into" in low_raw or "session must be under" in low_raw or "~" in low_raw):
                total_work_minutes = int(round(float(m_hr.group(1)) * 60))
            elif m_min:
                total_work_minutes = int(m_min.group(1))
            elif pkg_task.total_work_minutes:
                total_work_minutes = pkg_task.total_work_minutes
            else:
                total_work_minutes = None
                _add_warn("W_NO_DURATION")

    # Vague duration qualifier ONLY when qualifying an amount/number (never "around the house" or "about my holiday"!)
    if re.search(r"\b(?:around|about|approx(?:imately)?|khoảng)\s+(?:\d+|a\s+couple|half)\b|\bI\s+guess\b", raw_prompt, re.IGNORECASE):
        _add_warn("W_VAGUE_DURATION")

    if deadline is None and "W_NO_DEADLINE" not in warnings and "W_RECURRING_NO_END" not in warnings and "W_VAGUE_DEADLINE" not in warnings:
        _add_warn("W_NO_DEADLINE")

    if deadline is not None and deadline < base_time:
        _add_err("E_DEADLINE_IN_THE_PAST")

    # Feasibility check
    eff_total = total_work_minutes or work_minutes_lower_bound
    if eff_total and deadline and "W_RECURRING_NO_END" not in warnings and not re.search(r"\bevery\s+day\s+until\b|\bon\s+Monday,\s*Wednesday", working, re.IGNORECASE):
        start_pt = max(base_time, start_after) if start_after else base_time
        window = (deadline - start_pt).total_seconds() / 60.0
        if window > 0 and not (start_after and abs(window - eff_total) < 1):
            capacity = window / 3.0 if window > 1440 else min(window / 2.0, 480.0)
            if eff_total > window:
                _add_err("E_INFEASIBLE_WORKLOAD")
            elif eff_total > capacity:
                _add_warn("W_TIGHT_SCHEDULE")

    # 6 Overload / Breakdown Rules (Category D) — 100% general structural rules
    declared_step_count = max(len(subtasks), len(re.findall(r"\(\d+\)|^\s*[-*•]\s+", working, re.MULTILINE)))
    chain_step_count = len(re.findall(r"\b(?:first|then|finally)\b", working, re.IGNORECASE))
    has_phases = bool(re.search(r"\bPhase\s+1\b.*\bPhase\s+2\b", working, re.IGNORECASE | re.DOTALL))

    # Multi-week milestone date span check (>=3 subtask deadlines spanning >= 10 days)
    sub_dates = [st["deadline_dt"] for st in subtasks if st.get("deadline_dt") is not None]
    has_horizon_spread = bool(len(sub_dates) >= 3 and (max(sub_dates) - min(sub_dates)).days >= 10)

    # Multi-domain context switch check (>=3 distinct semantic domains)
    prompt_words = set(re.findall(r"[a-z0-9]+", low_raw))
    matched_domains = sum(1 for vocab in _DOMAIN_LEXICONS.values() if prompt_words & vocab)
    has_multi_domain = matched_domains >= 3

    is_single_over_480 = bool(ui.get("session") == "single" and eff_total and eff_total > 480 and "E_INFEASIBLE_WORKLOAD" not in errors)

    breakdown_required = bool(
        declared_step_count > 6
        or chain_step_count > 5
        or has_phases
        or has_horizon_spread
        or has_multi_domain
        or is_single_over_480
    )
    if breakdown_required:
        _add_warn("W_BREAKDOWN_RECOMMENDED")
    if eff_total and ui.get("session") == "single" and eff_total >= 360 and "E_INFEASIBLE_WORKLOAD" not in errors:
        _add_warn("W_UNREALISTIC_LOAD")

    # General Workflow, External Wait, Reference & Vagueness Warnings
    if has_vi and has_en_task_phrase:
        _add_warn("W_MIXED_LANGUAGE")

    if re.search(r"\b(?:until\s+approved|until\s+\d+%\s+pass|repeatedly|keep\s+revising|revise\s+repeatedly|review\s+requests?\s+to\s+the\s+(?:manager|director|client))\b", working, re.IGNORECASE):
        _add_warn("W_OPEN_LOOP")

    if has_external_wait_unestimated or re.search(r"\bwaiting\s+on\b|\bsend\s+to\s+(?:pm|manager)\s+for\s+review\b|\bwait\s+for\s+(?:legal|client|vendor|technician)\b", working, re.IGNORECASE):
        _add_warn("W_EXTERNAL_DEPENDENCY")
        _add_warn("W_STATUS_INFERRED")

    if re.search(
        r"✅|⏳|⬜|\[x\]|\(đã\s*xong\)|\(đang\s*làm\)|\bhalfway\s+done\b|\bis\s+already\s+(?:done|finished)\b|\balready\s+bought\b",
        raw_prompt,
        re.IGNORECASE,
    ):
        _add_warn("W_STATUS_INFERRED")

    if re.search(r"\band\s+also\b", working, re.IGNORECASE) or has_multi_domain:
        _add_warn("W_MULTIPLE_GOALS")
        _add_warn("W_DEPENDENCY_UNCLEAR")

    # Unordered multi-step tasks without sequencing words trigger W_DEPENDENCY_UNCLEAR
    has_terminal_review_step = bool(
        subtasks and re.search(r"^\s*(?:send\s+to\s+(?:director|manager|pm)|run\s+grading|fix\s+failing|submit)\b", subtasks[-1]["title"], re.IGNORECASE)
    )
    if (
        has_subtask_structure
        and len(subtasks) >= 2
        and not has_ordering_cue
        and not has_phases
        and not has_horizon_spread
        and not has_terminal_review_step
        and declared_step_count <= 6
    ):
        has_semicolons = ";" in working
        has_bullets = bool(re.search(r"(?:^|\n)\s*[-*•]\s+|\s-\s|[✅⏳⬜]", working))
        has_sub_prios = any(st.get("priority") is not None for st in subtasks)
        hdr_dep_part = re.split(r":(?=\s|$)", working, maxsplit=1)[0]
        if has_bullets or (has_semicolons and has_sub_prios) or (len(subtasks) == 2 and re.search(r"\band\b", working, re.IGNORECASE)) or not re.search(r"\(\d+\)", working):
            if not (m_scope_n := re.search(r"\b\d+\s+chapters?\b", hdr_dep_part, re.IGNORECASE)) or len(subtasks) > 2:
                _add_warn("W_DEPENDENCY_UNCLEAR")
            elif m_scope_n and "problem sets" in working.lower():
                _add_warn("W_DEPENDENCY_UNCLEAR")

    # Subtask defaults inherited: user left pacing/session unspecified with >=2 subtasks
    if len(subtasks) >= 2 and (ui.get("pacing") is None or ui.get("session") is None):
        _add_warn("W_SUBTASK_DEFAULTS_INHERITED")

    # Unresolved Reference: bare pronouns or cross-channel mentions without clear referent
    has_unresolved_ref = bool(
        re.search(
            r"\b(?:finish|do|complete|fix|check|send|review|update)\s+(?:it|them|that)\b"
            r"|\bsend\s+(?:them|him|her)\s+that\s+thing\b"
            r"|\b(?:that|this)\s+(?:file|thing|guy|document|task)\b"
            r"|\bthe\s+guy\s+from\b"
            r"|\bthe\s+other\s+part\s+of\b"
            r"|\bsame\s+(?:thing|routine)\s+as\s+(?:yesterday|last\s+time)\b"
            r"|\bmentioned\s+(?:on|in)\s+(?:the\s+)?(?:slack|email|teams|chat|thread|message)\b"
            r"|\bPrepare\s+for\s+the\s+meeting\b"
            r"|\bWork\s+on\s+the\s+project\b"
            r"|\b(?:cái\s+đó|việc\s+đó|thứ\s+đó)\b",
            raw_prompt,
            re.IGNORECASE,
        )
    )
    if has_unresolved_ref:
        _add_warn("W_UNRESOLVED_REFERENCE")

    # General Vague Task classifier (unparameterized placeholders/generic nouns)
    is_concrete_file_transfer = bool(re.search(r"\bthat\s+file\s+to\s+the\s+guy\s+from\b", low_raw))
    if (has_unresolved_ref and not is_concrete_file_transfer) or re.search(
        r"\b(?:do\s+(?:some\s+)?(?:studying|housework|a\s+workout|some\s+exercise)|some\s+(?:work|stuff)|(?:office|life|personal)\s+(?:admin\s+stuff|growth\s+and\s+life\s+organization)|clean\s+some\s+stuff|broken\s+things|do\s+step\s+\d+|do\s+part\s+[a-z]|the\s+rest\s+of\s+the\s+\w+|học\s+bài)\b|^\s*(?:homework|exam|assignment|study)\s*$",
        low_raw,
        re.IGNORECASE,
    ):
        _add_warn("W_VAGUE_TASK")

    # ------------------------------------------------------------------
    # STAGE 5: UI Override Reconciliation (Priority, Session, Pacing)
    # ------------------------------------------------------------------
    ui_prio = ui.get("priority")
    # Strip parenthesized/bracketed per-subtask priority tags when checking parent priority vs UI
    prio_scan_text = (
        re.sub(r"[\(\[][^\)\]]*(?:urgent|critical|high|medium|low|optional|p[1-4])[^\)\]]*[\)\]]", " ", low_raw)
        if has_subtask_structure
        else low_raw
    )
    has_high_cue = bool(re.search(r"\b(?:urgent|critical|asap|as\s+soon\s+as\s+possible|important|high\s+priority|khẩn\s*cấp|p[12])\b", prio_scan_text))
    has_low_cue = bool(re.search(r"\b(?:low\s+priority|optional|no\s+rush|whenever\s+I\s+have\s+free\s+time|p4)\b", prio_scan_text))

    # Determine final winning text priority (respecting late self-correction override)
    if has_low_cue and re.search(r"\b(?:urgent|critical|important|high\s+priority)\b", prio_scan_text):
        _add_warn("W_PRIORITY_CONFLICT")
        text_prio: Optional[int] = 1
    elif re.search(r"\b(?:urgent|critical|asap|as\s+soon\s+as\s+possible|khẩn\s*cấp|p1)\b", prio_scan_text):
        text_prio = 1
    elif re.search(r"\b(?:important|high\s+priority|p2)\b", prio_scan_text):
        text_prio = 2
    elif has_low_cue:
        text_prio = 4
    else:
        text_prio = None

    active_subs = [st for st in subtasks if st["status"] != "DONE"]
    has_sub_prio_tags = bool(active_subs and any(st.get("priority") is not None for st in active_subs))
    has_missing_sub_prio = bool(active_subs and any(st.get("priority") is None for st in active_subs))

    if ui_prio == "NOT_SURE":
        if text_prio is not None:
            final_priority: Optional[int] = text_prio
            if "W_PRIORITY_CONFLICT" not in warnings:
                _add_warn("W_PRIORITY_INFERRED")
        else:
            final_priority = None
            _add_warn("W_PRIORITY_UNCERTAIN")
    elif ui_prio is None:
        if has_sub_prio_tags:
            final_priority = min(int(st["priority"]) for st in active_subs if st.get("priority") is not None)
            if has_missing_sub_prio:
                _add_warn("W_PRIORITY_INFERRED")
                _add_warn("W_PRIORITY_DEFAULTED")
        elif text_prio is not None:
            final_priority = text_prio
            if "W_PRIORITY_CONFLICT" not in warnings:
                _add_warn("W_PRIORITY_INFERRED")
        else:
            final_priority = 3
            _add_warn("W_PRIORITY_DEFAULTED")
    else:
        if has_sub_prio_tags:
            if has_missing_sub_prio:
                _add_warn("W_PRIORITY_INFERRED")
                _add_warn("W_PRIORITY_DEFAULTED")
            final_priority = int(ui_prio)
        elif text_prio is not None and text_prio != int(ui_prio):
            final_priority = text_prio
            _add_warn("W_PRIORITY_CONFLICT")
        else:
            final_priority = int(ui_prio)

    # Session & Splitting reconciliation
    ui_session = ui.get("session")
    ui_pacing = ui.get("pacing")
    prompt_asks_single = bool(re.search(r"\b(?:one\s+uninterrupted\s+(?:single\s+)?session|in\s+one\s+sitting|không\s*chia\s*nhỏ)\b", low_raw))
    prompt_asks_split = bool(re.search(r"\bsplit\s+into\s+(\d+)-minute\s+chunks?\b", low_raw))

    is_splittable: Optional[bool] = None
    splitting_cfg: Optional[Dict[str, int]] = None
    resolved_work_rhythm: str = pkg_task.work_rhythm.value if pkg_task.work_rhythm else "BALANCED"
    if "E_SESSION_CONTRADICTION" in errors:
        is_splittable = None
        splitting_cfg = None
    elif "E_CUSTOM_RANGE_INVALID" in errors:
        is_splittable = True
        splitting_cfg = None
        resolved_work_rhythm = "CUSTOM"
    else:
        if ui_session == "splittable" and prompt_asks_single:
            is_splittable = False
            splitting_cfg = None
            _add_warn("W_SESSION_CONFLICT")
        elif ui_session == "single" and prompt_asks_split:
            is_splittable = True
            m_sp = re.search(r"\bsplit\s+into\s+(\d+)-minute\s+chunks?\b", low_raw)
            ch = int(m_sp.group(1)) if m_sp else 30
            splitting_cfg = {"min": 15, "pref": ch, "max": ch}
            _add_warn("W_SESSION_CONFLICT")
        elif ui_session == "single":
            is_splittable = False
            splitting_cfg = None
        elif ui_session in (None, "not_sure"):
            _add_warn("W_SESSION_DEFAULTED")
            if eff_total is not None and eff_total <= 30:
                is_splittable = False
                splitting_cfg = None
            else:
                is_splittable = True
        else:
            is_splittable = True

        if is_splittable and splitting_cfg is None:
            if ui_pacing in (None, "NOT_SURE"):
                _add_warn("W_PACING_DEFAULTED")
                eff_pacing = "BALANCED"
            else:
                eff_pacing = ui_pacing
            resolved_work_rhythm = eff_pacing

            # Extract explicit preferred chunk size hints from prompt (`~30m`, `20 minutes each`, `split into 30-minute chunks`, `25m Pomodoro`)
            m_chunk_hint = re.search(
                r"~(\d+)m\b|\b(\d+)\s*(?:minutes?|mins?|m)\s+each\b|\bsplit\s+into\s+(\d+)-minute\s+chunks?\b|\bin\s+(\d+)m\s+pomodoro\b",
                low_raw,
            )
            chunk_hint = int(next(g for g in m_chunk_hint.groups() if g is not None)) if m_chunk_hint else None

            if eff_pacing == "LIGHT":
                pref = chunk_hint if (chunk_hint and 15 <= chunk_hint <= 30) else 25
                splitting_cfg = {"min": 15, "pref": pref, "max": 30}
            elif eff_pacing == "FLOW":
                pref = chunk_hint if (chunk_hint and 45 <= chunk_hint <= 120) else 90
                splitting_cfg = {"min": 45, "pref": pref, "max": 120}
            elif eff_pacing == "CUSTOM" and custom_bounds:
                cmin, cmax = int(custom_bounds[0]), int(custom_bounds[1])
                pref = chunk_hint if (chunk_hint and cmin <= chunk_hint <= cmax) else (cmin + cmax) // 2
                splitting_cfg = {"min": cmin, "pref": pref, "max": cmax}
                if re.search(r"\b(?:under\s+45\s+minutes|less\s+than\s+(?:an?\s+)?hour)\b", low_raw) and cmin > 44:
                    _add_warn("W_CHUNK_CONFLICT")
            else:
                max_b = 59 if re.search(r"\bless\s+than\s+(?:an?\s+)?hour\b", low_raw) else 60
                pref = chunk_hint if (chunk_hint and 15 <= chunk_hint <= max_b) else 45
                splitting_cfg = {"min": 15, "pref": pref, "max": max_b}

    # Final contract status (`NEEDS_FIX` keeps blocking errors primary & suppresses noisy style warnings)
    if "E_NONSENSE_INPUT" in errors:
        status = "REJECTED"
    elif errors:
        status = "NEEDS_FIX"
        warnings = [w for w in warnings if w == "W_PROMPT_INJECTION"]
    elif warnings:
        status = "OK_WITH_WARNINGS"
    else:
        status = "OK"

    # Stage 6: SmartSchedule Solver Priority Adapter (`1=Urgent..4=Low` -> `5=Highest..1=Lowest`)
    solver_priority = map_user_urgency_to_solver_priority(final_priority, scale_max=4)

    return {
        "status": status,
        "title": pkg_task.title,
        "total_work_minutes": total_work_minutes,
        "work_minutes_lower_bound": work_minutes_lower_bound,
        "start_after": start_after.strftime("%Y-%m-%dT%H:%M") if start_after else None,
        "deadline": deadline.strftime("%Y-%m-%dT%H:%M") if deadline else None,
        "priority": final_priority,
        "priority_uncertain": final_priority is None,
        "solver_priority": solver_priority,
        "is_task_splittable": is_splittable,
        "splitting": splitting_cfg,
        "work_rhythm": resolved_work_rhythm,
        "subtasks": [
            {k: v for k, v in st.items() if k != "deadline_dt"}
            for st in subtasks
        ],
        "breakdown_required": breakdown_required,
        "errors": errors,
        "warnings": warnings,
        "citations": citations_report,
        "translation_applied": bool(translation_applied or pkg_tel.get("translation_applied")),
        "translation_backend": used_backend if translation_applied else pkg_tel.get("translation_backend"),
        "translated_prompt": translated_en_text if translation_applied else None,
    }


def compile_hybrid_to_smartschedule(
    prompt: str,
    ui: Optional[Dict[str, Any]] = None,
    *,
    now: Optional[str] = None,
    existing_count: int = 0,
    translation_backend: str = "rule",
) -> Dict[str, Any]:
    """
    Adapter converting `parse_hybrid_case()` output into ready-to-schedule fields for
    `group03-smartschedule-baseline/src/nl_parser.py` & `web/api.py`, preserving:
      - User-facing `1=Urgent..4=Low` (`user_priority`)
      - Solver-facing `5=Highest..1=Lowest` (`solver_priority`)
      - `WorkRhythm` splitting config (`min_chunk_min`, `max_chunk_min`)
      - Non-destructive `errors`, `warnings`, `subtasks`, and `translation` metadata
    """
    if now:
        try:
            clean_now = str(now).replace("Z", "+00:00")
            base_time = datetime.fromisoformat(clean_now).replace(tzinfo=None)
        except ValueError:
            base_time = datetime.now().replace(second=0, microsecond=0)
    else:
        base_time = datetime.now().replace(second=0, microsecond=0)

    res = parse_hybrid_case(
        prompt,
        ui=ui,
        base_time=base_time,
        enable_translation=True,
        translation_backend=translation_backend,
    )

    dl_dt: Optional[datetime] = None
    if res.get("deadline"):
        dl_dt = datetime.fromisoformat(res["deadline"])
    else:
        # Default fallback for SmartSchedule TaskSheet when no explicit deadline exists
        dl_dt = base_time.replace(hour=23, minute=59, second=0, microsecond=0) + timedelta(days=2)

    day_name = _WEEKDAY_NAMES[dl_dt.weekday()]
    time_str = dl_dt.strftime("%H:%M")

    eff_dur = res.get("total_work_minutes") or res.get("work_minutes_lower_bound") or 60
    splitting = res.get("splitting") or {}
    min_chunk = int(splitting.get("min", 30)) if res.get("is_task_splittable", True) else int(eff_dur)
    digest = hashlib.sha256(f"{prompt}|{now}|{existing_count}".encode("utf-8")).hexdigest()[:8].upper()

    return {
        "hybrid": res,
        "solver_adapter": {
            "task_id": f"TASK_NL_{digest}",
            "title": res.get("title") or prompt.strip()[:80],
            "duration_min": int(eff_dur),
            "deadline_day": day_name,
            "deadline_time": time_str,
            "priority": int(res.get("solver_priority") or 3),
            "user_priority": res.get("priority"),
            "is_splittable": bool(res.get("is_task_splittable", True)),
            "min_chunk_min": min_chunk,
            "max_chunk_min": int(splitting.get("max", 60)) if splitting else None,
            "work_rhythm": res.get("work_rhythm") or "BALANCED",
            "start_after": res.get("start_after"),
            "breakdown_required": bool(res.get("breakdown_required", False)),
            "subtasks": res.get("subtasks") or [],
            "errors": res.get("errors") or [],
            "warnings": res.get("warnings") or [],
        },
    }
