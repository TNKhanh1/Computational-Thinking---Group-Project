"""
Deterministic SHA-256 Task Traceability & Hidden Criteria Extractor (Pure Layer 1).

Provides keyword canonicalization, SHA-256 task/keyword fingerprinting, natural-language
prompt-to-task lookup, and hidden scheduling parameter extraction (cognitive load,
circadian window, splittability/work rhythm, and planning-fallacy buffer) without
touching solvers, controller, or web frameworks (INV-1, INV-2 compliant).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

_STOP_WORDS: frozenset[str] = frozenset(
    {
        # Vietnamese common particles & verbs
        "va", "voi", "cua", "cho", "minh", "ban", "toi", "em", "anh", "chi",
        "nay", "do", "kia", "day", "roi", "nhe", "nha", "a", "ah", "oi", "di",
        "hay", "hoac", "nhung", "ma", "thi", "la", "duoc", "bi", "bi", "se",
        "dang", "da", "can", "phai", "muon", "giup", "sua", "chinh", "cap",
        "nhat", "doi", "thay", "them", "tao", "xoa", "bo", "xep", "sap", "lich",
        "trinh", "viec", "cong", "task", "bai", "nay", "vua", "tren", "duoi",
        "vao", "luc", "truoc", "sau", "tu", "den", "toi", "khoang", "tam",
        "hon", "kem", "qua", "lam", "rat", "hoi", "khong", "the", "co", "du",
        "mot", "hai", "ba", "nhieu", "it", "buoi", "mach", "lien", "tuc",
        # Hidden criteria / temporal words stripped so core subject keywords remain
        "nang", "nhe", "nhang", "kho", "de", "don", "gian", "chia", "nho",
        "tach", "gop", "sang", "trua", "chieu", "toi", "dem", "khuya", "som",
        "nhip", "sinh", "hoc", "tinh", "tao", "gio", "vang", "peak", "deep",
        "light", "flow", "balanced", "buffer", "tru", "hao", "du", "phong",
        "fallacy", "deadline", "han", "chot", "nop", "phut", "tieng", "ngay",
        "mai", "tuan", "thu", "chu", "nhat", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday", "today", "tomorrow",
        "morning", "afternoon", "evening", "night", "split", "unsplittable",
        "heavy", "easy", "hard", "urgent", "gap", "khan", "cap", "uu", "tien",
        "cao", "thap", "please", "help", "me", "the", "for", "and", "to", "in",
        "on", "at", "my", "this", "that", "make", "change", "update", "move",
        "con", "lai", "tiep", "theo", "uoc", "luong", "estimate", "ti", "chut",
    }
)

_ANAPHORA_RE = re.compile(
    r"\b(?:viec\s+do|viec\s+nay|viec\s+vua\s+roi|task\s+do|task\s+nay|"
    r"task\s+vua\s+roi|bai\s+nay|bai\s+do|cong\s+viec\s+tren|no)\b"
)


def strip_accents(text: str) -> str:
    """Normalize Vietnamese diacritics into ASCII-friendly lowercase text."""
    replaced = str(text or "").replace("đ", "d").replace("Đ", "D")
    nfkd = unicodedata.normalize("NFKD", replaced)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def canonicalize_keywords(text: str) -> List[str]:
    """Extract ordered content keywords from a Vietnamese/English title or prompt."""
    norm = strip_accents(text).lower()
    norm = re.sub(r"#sha256:[a-f0-9]+|\[trace:[a-f0-9]+\]", " ", norm)
    tokens = re.findall(r"[a-z0-9]+", norm)
    return [tok for tok in tokens if len(tok) >= 2 and tok not in _STOP_WORDS]


def _sha256_short(token: str, length: int = 8) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:length]


def compute_task_trace_hash(title: str, category: str = "ASSIGNMENT") -> str:
    """Compute a deterministic full SHA-256 fingerprint from canonical task keywords + category."""
    kw = canonicalize_keywords(title)
    if not kw:
        raw_norm = re.sub(r"\s+", " ", strip_accents(title).lower()).strip()
        kw = [raw_norm] if raw_norm else ["untitled"]
    cat = str(category or "ASSIGNMENT").strip().upper()
    seed = f"{' '.join(kw)}|{cat}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def compute_keyword_hashes(title: str) -> List[str]:
    """Build deterministic 8-char SHA-256 digests for unigrams and bigrams in a title."""
    kw = canonicalize_keywords(title)
    if not kw:
        raw_tokens = re.findall(r"[a-z0-9]+", strip_accents(title).lower())
        kw = [t for t in raw_tokens if len(t) >= 2]
    terms: List[str] = list(kw)
    for idx in range(len(kw) - 1):
        terms.append(f"{kw[idx]} {kw[idx + 1]}")
    seen: Set[str] = set()
    hashes: List[str] = []
    for term in terms:
        digest = _sha256_short(term, 8)
        if digest not in seen:
            seen.add(digest)
            hashes.append(digest)
    return hashes


def enrich_task_trace_metadata(task_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Attach deterministic `trace_hash` and `keyword_hashes` to a task dictionary."""
    out = dict(task_dict)
    title = str(out.get("title") or out.get("task_id") or "")
    category = str(out.get("category") or "ASSIGNMENT")
    out["trace_hash"] = compute_task_trace_hash(title, category)
    out["keyword_hashes"] = compute_keyword_hashes(title)
    return out


def resolve_target_task_from_prompt(
    prompt: str,
    tasks: List[Dict[str, Any]],
    last_task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Trace which existing task in `tasks` a natural-language prompt refers to using:
      1. Explicit `#sha256:<hex>` / `[trace:<hex>]` or `task_id` embedded in the prompt.
      2. SHA-256 unigram/bigram keyword hash overlap + normalized substring affinity.
      3. Anaphora fallback (`"việc vừa rồi"`, `"task đó"`) when `last_task_id` is available.
    """
    if not tasks:
        return {
            "matched": False,
            "task": None,
            "task_id": None,
            "trace_hash": None,
            "confidence": 0.0,
            "matched_keywords": [],
            "candidates": [],
        }

    enriched_tasks = [enrich_task_trace_metadata(t) for t in tasks if isinstance(t, dict)]
    prompt_norm = strip_accents(prompt).lower()

    # 1. Explicit embedded SHA-256 trace tag or exact task_id
    explicit_hash_m = re.search(r"(?:#sha256:|\[trace:)([a-f0-9]{6,64})\]?", prompt_norm)
    if explicit_hash_m:
        prefix = explicit_hash_m.group(1)
        for t in enriched_tasks:
            if str(t.get("trace_hash", "")).lower().startswith(prefix):
                return {
                    "matched": True,
                    "task": t,
                    "task_id": t.get("task_id"),
                    "trace_hash": t.get("trace_hash"),
                    "confidence": 1.0,
                    "matched_keywords": [f"sha256:{prefix}"],
                    "candidates": [],
                }

    for t in enriched_tasks:
        tid = str(t.get("task_id") or "").strip()
        if tid and re.search(rf"\b{re.escape(tid.lower())}\b", prompt_norm):
            return {
                "matched": True,
                "task": t,
                "task_id": tid,
                "trace_hash": t.get("trace_hash"),
                "confidence": 1.0,
                "matched_keywords": [tid],
                "candidates": [],
            }

    # 2. Keyword SHA-256 hash matching
    prompt_kw = canonicalize_keywords(prompt)
    prompt_terms: List[str] = list(prompt_kw)
    for idx in range(len(prompt_kw) - 1):
        prompt_terms.append(f"{prompt_kw[idx]} {prompt_kw[idx + 1]}")
    prompt_hash_to_term = {_sha256_short(term, 8): term for term in prompt_terms}
    prompt_hashes = set(prompt_hash_to_term.keys())

    scored: List[Tuple[float, Dict[str, Any], List[str]]] = []
    for t in enriched_tasks:
        title_str = str(t.get("title") or "")
        title_norm = strip_accents(title_str).lower().strip()
        task_kw = canonicalize_keywords(title_str)
        task_hashes = set(t.get("keyword_hashes") or compute_keyword_hashes(title_str))

        overlap_hashes = prompt_hashes & task_hashes
        matched_terms = [prompt_hash_to_term[h] for h in overlap_hashes if h in prompt_hash_to_term]

        containment = len(overlap_hashes) / float(max(1, len(task_hashes)))
        jaccard = len(overlap_hashes) / float(max(1, len(prompt_hashes | task_hashes)))
        score = 0.70 * containment + 0.30 * jaccard

        if title_norm and len(title_norm) >= 3 and title_norm in prompt_norm:
            score = max(score, 0.96)
        elif task_kw:
            kw_phrase = " ".join(task_kw)
            if len(kw_phrase) >= 3 and kw_phrase in prompt_norm:
                score = max(score, 0.90)

        if last_task_id and t.get("task_id") == last_task_id and score > 0.0:
            score += 0.05

        if score > 0.0:
            scored.append((min(1.0, round(score, 4)), t, sorted(set(matched_terms))))

    scored.sort(key=lambda item: item[0], reverse=True)

    if scored and scored[0][0] >= 0.35:
        top_score, top_task, top_kws = scored[0]
        ambiguous = (
            len(scored) >= 2
            and abs(scored[0][0] - scored[1][0]) < 0.06
            and scored[1][0] >= 0.35
            and scored[0][0] < 0.85
        )
        candidates = [
            {
                "task_id": item[1].get("task_id"),
                "title": item[1].get("title"),
                "trace_hash": item[1].get("trace_hash"),
                "score": item[0],
            }
            for item in scored[:4]
        ]
        return {
            "matched": not ambiguous,
            "ambiguous": ambiguous,
            "task": None if ambiguous else top_task,
            "task_id": None if ambiguous else top_task.get("task_id"),
            "trace_hash": None if ambiguous else top_task.get("trace_hash"),
            "confidence": top_score,
            "matched_keywords": top_kws,
            "candidates": candidates,
        }

    # 3. Anaphora fallback to last_task_id
    if last_task_id and _ANAPHORA_RE.search(prompt_norm):
        for t in enriched_tasks:
            if t.get("task_id") == last_task_id:
                return {
                    "matched": True,
                    "task": t,
                    "task_id": t.get("task_id"),
                    "trace_hash": t.get("trace_hash"),
                    "confidence": 0.85,
                    "matched_keywords": ["recent_task_reference"],
                    "candidates": [],
                }

    return {
        "matched": False,
        "ambiguous": False,
        "task": None,
        "task_id": None,
        "trace_hash": None,
        "confidence": 0.0,
        "matched_keywords": [],
        "candidates": [
            {
                "task_id": t.get("task_id"),
                "title": t.get("title"),
                "trace_hash": t.get("trace_hash"),
                "score": 0.0,
            }
            for t in enriched_tasks[:5]
        ],
    }


def extract_hidden_criteria_updates(
    prompt: str,
    focus_preference: Optional[str] = "BALANCED",
) -> Dict[str, Any]:
    """
    Parse natural-language user criteria into hidden scheduling parameters:
      - cognitive_load & fallacy buffer (`COGNITIVE_LOAD` 1.20 / 1.35 or `NONE` 1.00)
      - splittability & work_rhythm (`LIGHT` 30-45m | `BALANCED` 45-90m | `FLOW` atomic)
      - circadian preferred_window (`MORNING` | `AFTERNOON` | `EVENING`)
      - priority escalation / de-escalation
    """
    norm = strip_accents(prompt).lower()
    updates: Dict[str, Any] = {}
    summary_vi: List[str] = []

    # 1. Cognitive load & heaviness
    is_heavy = bool(
        re.search(
            r"\b(?:nang\s*qua|qua\s*nang|nang\s*do|hoi\s*nang|rat\s*nang|"
            r"tap\s*trung\s*sau|ton\s*chat\s*xam|cang\s*nao|kho\s*nhan|deep\s*work)\b"
            r"|\bnang\b(?!\s*cao\b)"
            r"|\b(?:hard|heavy|intense|exhausting)\b",
            norm,
        )
    )
    is_light = bool(
        re.search(
            r"\b(?:nhe\s*nhang|hoi\s*nhe|de\s*tho|don\s*gian|thu\s*gian|chill|light|easy)\b"
            r"|\bnhe\b",
            norm,
        )
    )

    if is_heavy:
        updates["cognitive_load"] = 3
        updates["buffer_mode"] = "COGNITIVE_LOAD"
        updates["alpha_heavy"] = 1.35
        updates["buffer_multiplier"] = 1.35
        summary_vi.append("Cường độ cao (Tập trung sâu) + tự động cộng đệm dự phòng +35%")
    elif is_light:
        updates["cognitive_load"] = 1
        updates["buffer_mode"] = "COGNITIVE_LOAD"
        updates["alpha_light"] = 1.20
        updates["buffer_multiplier"] = 1.20
        summary_vi.append("Cường độ nhẹ + đệm dự phòng nhẹ +20%")

    # 2. Splittability & work rhythm
    no_split = bool(
        re.search(
            r"\b(?:khong\s*(?:the\s*)?chia(?:\s*nho)?|lien\s*1\s*mach|lien\s*mot\s*mach|"
            r"lien\s*mach|lien\s*tuc|1\s*buoi|mot\s*buoi|dut\s*diem|lam\s*lien|"
            r"unsplittable|no\s*split|single\s*block)\b",
            norm,
        )
    )
    yes_split = bool(
        re.search(
            r"\b(?:chia\s*nho|co\s*the\s*chia|tach\s*nho|tach\s*ra|chia\s*ra|"
            r"nhieu\s*buoi|moi\s*lan\s*mot\s*it|split)\b",
            norm,
        )
    )
    if no_split:
        updates["is_splittable"] = False
        updates["work_rhythm"] = "FLOW"
        summary_vi.append("Giữ liền 1 mạch (không tách nhỏ)")
    elif yes_split:
        is_short_chunk = bool(re.search(r"\b(?:nho|ngan|it|30p|45p|30\s*phut|45\s*phut)\b", norm))
        updates["is_splittable"] = True
        if is_short_chunk:
            updates["work_rhythm"] = "LIGHT"
            updates["min_chunk_min"] = 30
            updates["max_chunk_min"] = 45
            summary_vi.append("Cho phép chia nhỏ thành từng phiên ngắn 30–45 phút")
        else:
            updates["work_rhythm"] = "BALANCED"
            updates["min_chunk_min"] = 45
            updates["max_chunk_min"] = 90
            summary_vi.append("Cho phép chia nhiều buổi 45–90 phút")

    # 3. Circadian / biological rhythm window
    if re.search(r"\b(?:buoi\s*sang|sang\s*som|luc\s*sang|morning)\b", norm):
        updates["preferred_window"] = "MORNING"
        summary_vi.append("Ưu tiên xếp vào buổi sáng")
    elif re.search(r"\b(?:buoi\s*chieu|chieu|afternoon)\b", norm):
        updates["preferred_window"] = "AFTERNOON"
        summary_vi.append("Ưu tiên xếp vào buổi chiều")
    elif re.search(r"\b(?:buoi\s*toi|toi|dem|khuya|evening|night)\b", norm):
        updates["preferred_window"] = "EVENING"
        summary_vi.append("Ưu tiên xếp vào buổi tối")
    elif re.search(r"\b(?:nhip\s*sinh\s*hoc|tinh\s*tao|gio\s*vang|minh\s*man|peak)\b", norm):
        pref = str(focus_preference or "BALANCED").upper()
        peak_win = pref if pref in ("MORNING", "AFTERNOON", "EVENING") else "MORNING"
        updates["preferred_window"] = peak_win
        win_label = {"MORNING": "buổi sáng", "AFTERNOON": "buổi chiều", "EVENING": "buổi tối"}.get(peak_win, "giờ vàng")
        summary_vi.append(f"Xếp theo nhịp sinh học ({win_label} lúc bạn tỉnh táo nhất)")

    # 4. Explicit Fallacy Buffer tweaks
    if re.search(r"\b(?:them\s*buffer|tru\s*hao|du\s*phong|so\s*tre|so\s*khong\s*kip|hay\s*lo\s*gio|fallacy)\b", norm):
        updates["buffer_mode"] = "COGNITIVE_LOAD"
        updates["alpha_heavy"] = 1.35
        updates["buffer_multiplier"] = max(float(updates.get("buffer_multiplier", 1.20)), 1.35)
        if not any("đệm" in s for s in summary_vi):
            summary_vi.append("Tăng thời gian dự phòng chống trễ (+35%)")
    elif re.search(r"\b(?:bo\s*buffer|tat\s*dem|khong\s*tru\s*hao|dung\s*gio\s*goc|no\s*buffer)\b", norm):
        updates["buffer_mode"] = "NONE"
        updates["buffer_multiplier"] = 1.0
        summary_vi.append("Tắt thời gian trừ hao (dùng đúng thời lượng gốc)")

    # 5. Priority signals
    if re.search(r"\b(?:rat\s*gap|khan\s*cap|gap\s*lam|uu\s*tien\s*nhat|urgent|asap)\b", norm):
        updates["priority"] = 5
        summary_vi.append("Nâng mức ưu tiên lên cao nhất")
    elif re.search(r"\b(?:uu\s*tien\s*cao|quan\s*trong|high\s*priority)\b", norm):
        updates["priority"] = 4
        summary_vi.append("Nâng mức ưu tiên lên cao")

    return {
        "has_hidden_updates": bool(updates),
        "updates": updates,
        "summary_vi": summary_vi,
    }
