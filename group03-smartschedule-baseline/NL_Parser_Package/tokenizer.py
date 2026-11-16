"""
tokenizer.py
Token estimation, context budgeting, and text normalization utility for SmartSchedule.
Guarantees O(N) linear time cleaning and prevents downstream context window overflow.
"""

from __future__ import annotations
import re
from typing import List, Tuple
from schema import TaskSchema


# Common conversational noise patterns to strip for abstraction
CONVERSATIONAL_PADDING = [
    r"^(hey\s+)?(smartschedule|assistant|bot)[:,]?\s*",
    r"^(could\s+you\s+)?(please\s+)?(schedule|add|create|put|insert|remind\s+me\s+to)\s+",
    r"^(i\s+need\s+to|i\s+have\s+to|i\s+want\s+to|don't\s+forget\s+to)\s+",
    r"\s+(please|thanks|thank\s+you)[\.!]?\s*$",
]


def clean_and_normalize(text: str) -> str:
    """
    Cleans raw text:
    1. Normalizes unicode whitespace and smart quotes.
    2. Strips leading/trailing conversational fluff.
    3. Collapses multiple spaces.
    """
    if not text:
        return ""

    # Replace smart quotes & dashes
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    text = text.replace("—", "-").replace("–", "-")

    # Strip conversational noise iteratively
    cleaned = text.strip()
    for pattern in CONVERSATIONAL_PADDING:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # Collapse multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else text.strip()


def estimate_tokens(text: str) -> int:
    """
    Estimates token count in O(N) using standard BPE character/word boundary heuristics.
    Rule of thumb for English/Code: 1 token ≈ 4 characters or 0.75 words.
    For mixed languages/punctuation, counts word tokens + punctuation offsets.
    """
    if not text:
        return 0
    words = re.findall(r"\w+|[^\w\s]", text, re.UNICODE)
    char_len = len(text)
    heuristic_by_words = int(len(words) * 1.3)
    heuristic_by_chars = max(1, (char_len + 3) // 4)
    # Blend word and character heuristics for balanced estimation
    return max(1, (heuristic_by_words + heuristic_by_chars) // 2)


def check_budget(text: str, max_tokens: int = 256) -> Tuple[bool, int, str]:
    """
    Checks whether a user's prompt is within the allocated context window ingestion budget.
    Returns: (is_within_budget, token_count, status_message)
    """
    token_count = estimate_tokens(text)
    if token_count <= max_tokens:
        pct = (token_count / max_tokens) * 100
        return True, token_count, f"Optimal ({token_count}/{max_tokens} tokens - {pct:.1f}% used)"
    else:
        overflow = token_count - max_tokens
        return False, token_count, f"Warning: Context overflow by +{overflow} tokens ({token_count}/{max_tokens})"


def compact_context_window(tasks: List[TaskSchema], max_budget: int = 1500) -> Tuple[str, int]:
    """
    Compacts a list of TaskSchema objects into a dense prompt context block
    for downstream LLM scheduling agents or constraint solvers.
    Stops appending if max_budget is reached to prevent token overflow.
    """
    lines = [
        "### ACTIVE SCHEDULE CONTEXT",
        f"Total Tasks: {len(tasks)}",
        "-" * 45,
    ]

    truncation_notice_reserve = 18
    effective_budget = max_budget - truncation_notice_reserve
    current_tokens = estimate_tokens("\n".join(lines))
    included_count = 0

    for task in tasks:
        chunk = task.to_context_chunk()
        chunk_tokens = estimate_tokens(chunk)
        if current_tokens + chunk_tokens > effective_budget:
            break
        lines.append(chunk)
        current_tokens += chunk_tokens
        included_count += 1

    if included_count < len(tasks):
        lines.append(f"... [{len(tasks) - included_count} remaining tasks truncated]")

    result_text = "\n".join(lines)
    # Final guard: if somehow over budget, pop until <= max_budget
    while len(lines) > 3 and estimate_tokens("\n".join(lines)) > max_budget:
        lines.pop(-2 if lines[-1].startswith("...") else -1)
    result_text = "\n".join(lines)
    return result_text, estimate_tokens(result_text)
