"""
translator.py
Offline, Free, Educational-Friendly Vietnamese -> English Translation Bridge for NL_Parser_Package.

Uses CTranslate2 (int8 CPU quantization) + SentencePiece with zero PyTorch dependency:
  1. Primary ("nllb"): Meta NLLB-200-distilled-600M (`JustFrederik/nllb-200-distilled-600M-ct2-int8`,
     CC-BY-NC-4.0 educational/non-commercial license) — high fluency on Vietnamese & code-switching.
  2. Light ("opus"): Helsinki-NLP MarianMT (`dekthedev/opus-mt-vi-en-ct2-int8`, Apache-2.0, ~74 MB).
  3. Offline Rule Fallback ("rule"): Zero-download deterministic phrase mapper if model files are absent.

Key engineering safeguards:
  - English-first fast bypass: pure English prompts incur 0 ms translation overhead.
  - Protected shorthand extraction: `#hashtags`, `~<min>`, `after:<ids>`, `p1..p5` are detached
    before MT and cleanly re-attached afterwards so neural MT never corrupts solver tokens.
  - Deterministic Vietnamese cue pre-normalization: stabilizes `17h30`, `thứ 2..CN`, `đã xong`,
    `bắt đầu sau`, `không chia nhỏ`, and `mỗi phần` before feeding NLLB-200.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import ctranslate2
except ImportError:  # Graceful fallback when running minimal offline environments
    ctranslate2 = None  # type: ignore

try:
    import sentencepiece as spm
except ImportError:
    spm = None  # type: ignore

try:
    from huggingface_hub import snapshot_download
except ImportError:
    snapshot_download = None  # type: ignore


NLLB_REPO_ID = "JustFrederik/nllb-200-distilled-600M-ct2-int8"  # CC-BY-NC-4.0 (Educational / Non-Commercial)
OPUS_REPO_ID = "dekthedev/opus-mt-vi-en-ct2-int8"                # Apache-2.0 (~74 MB lightweight)

_VI_DIACRITIC_RE = re.compile(
    r"[ăâđêôơưĂÂĐÊÔƠƯàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]",
    re.IGNORECASE,
)
_VI_UNACCENTED_CUE_RE = re.compile(
    r"\b(?:thu\s*[2-7]|chu\s*nhat|ngay\s*mai|ngay\s*kia|hom\s*nay|hom\s*qua|"
    r"on\s*thi|lam\s*bai|hop\s*nhom|bai\s*tap|do\s*an|thoi\s*gian|"
    r"tieng|phut|gio|truoc|buoi\s*(?:sang|chieu|toi)|da\s*xong|khong\s*chia)\b",
    re.IGNORECASE,
)

_VI_WEEKDAYS = {
    "2": "Monday",
    "hai": "Monday",
    "3": "Tuesday",
    "ba": "Tuesday",
    "4": "Wednesday",
    "tu": "Wednesday",
    "tư": "Wednesday",
    "5": "Thursday",
    "nam": "Thursday",
    "năm": "Thursday",
    "6": "Friday",
    "sau": "Friday",
    "sáu": "Friday",
    "7": "Saturday",
    "bay": "Saturday",
    "bảy": "Saturday",
}

_RULE_PHRASE_MAP: Tuple[Tuple[str, str], ...] = (
    (r"\b(?:ôn\s*thi|on\s*thi)\b", "review for exam"),
    (r"\b(?:ôn\s*tập|on\s*tap|ôn\s*bài|on\s*bai)\b", "review"),
    (r"\b(?:làm\s*bài\s*tập|lam\s*bai\s*tap|bài\s*tập|bai\s*tap)\b", "do homework"),
    (r"\b(?:họp\s*nhóm|hop\s*nhom)\b", "team meeting"),
    (r"\b(?:đồ\s*án|do\s*an)\b", "project"),
    (r"\b(?:hệ\s*điều\s*hành|he\s*dieu\s*hanh)\b", "Operating Systems"),
    (r"\b(?:giải\s*tích|giai\s*tich)\b", "Calculus"),
    (r"\b(?:toán\s*rời\s*rạc|toan\s*roi\s*rac|cấu\s*trúc\s*rời\s*rạc)\b", "Discrete Structures"),
    (r"\b(?:đọc\s*tài\s*liệu|doc\s*tai\s*lieu)\b", "read documentation"),
    (r"\b(?:tập\s*gym|tap\s*gym)\b", "gym workout"),
    (r"\b(?:chạy\s*bộ|chay\s*bo)\b", "running"),
    (r"\b(?:hôm\s*qua|hom\s*qua)\b", "yesterday"),
    (r"\b(?:hôm\s*kia|hom\s*kia)\b", "2 days ago"),
    (r"\b(?:cày\s*phim|cay\s*phim)\b", "binge-watched movies"),
    (r"\b(?:thức\s*(?:tới|đến)|thuc\s*(?:toi|den))\b", "stayed up until"),
    (r"\b(?:thức|thuc)\b", "stayed up"),
    (r"\b(?:mệt\s*quá|met\s*qua)\b", "so tired"),
    (r"\b(?:ở\s*phòng|o\s*phong|tại\s*phòng|tai\s*phong)\b", "in room"),
    (r"\b(?:ở|o|tại|tai)\b", "at"),
    (r"\b(?:trong)\b", "for"),
)


@dataclass
class TranslationResult:
    """Result returned by VietnameseToEnglishTranslator."""

    translated_text: str
    original_text: str
    translation_applied: bool
    backend_used: str
    model_id: Optional[str]
    latency_ms: float


def contains_vietnamese(text: str) -> bool:
    """Fast O(N) check deciding whether translation is needed."""
    if not text:
        return False
    return bool(_VI_DIACRITIC_RE.search(text) or _VI_UNACCENTED_CUE_RE.search(text))


def _extract_protected_tokens(line: str) -> Tuple[str, List[str]]:
    """
    Strip shorthand & hashtags (`#deep`, `~30`, `after:TASK_1`, `p1..p5`)
    so neural translation cannot corrupt or space-split them.
    """
    protected: List[str] = []

    def _collect(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return " "

    pattern = re.compile(r"#\w+|~\d+[mh]?\b|\bafter:[A-Za-z0-9_,-]+|\bp[1-5]\b", re.IGNORECASE)
    cleaned = pattern.sub(_collect, line)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned, protected


def _format_12h_clock(hour: int, minute: int = 0) -> str:
    """Format 24h integers as unambiguous English 12h AM/PM so NLLB preserves PM."""
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    ampm = "AM" if hour < 12 else "PM"
    h12 = hour % 12
    if h12 == 0:
        h12 = 12
    return f"{h12}:{minute:02d} {ampm}"


def _normalize_vi_weekdays(s: str) -> str:
    s = re.sub(r"\b(?:chủ\s*nhật|chu\s*nhat|cn)\b", "Sunday", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\b(?:thứ|thu)\s*(2|3|4|5|6|7|hai|ba|tu|tư|nam|năm|sau|sáu|bay|bảy)\b",
        lambda m: _VI_WEEKDAYS[m.group(1).lower()],
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(r"\bt([2-7])\b", lambda m: _VI_WEEKDAYS[m.group(1)], s, flags=re.IGNORECASE)
    s = re.sub(
        r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+(?:tuần\s*này|tuan\s*nay|this\s*week)\b",
        r"\1",
        s,
        flags=re.IGNORECASE,
    )
    return s


def _pre_normalize_vietnamese_cues(line: str) -> Tuple[str, List[str]]:
    """
    Extract deterministic Vietnamese temporal/duration/multiplier/constraint clauses
    BEFORE neural MT so NLLB receives fluent Vietnamese prose and never drops
    weekdays, PM markers, half-hours, or `do not split` constraints.
    Returns `(normalized_line_for_mt, detached_english_clauses)`.
    """
    s = line
    suffix_tokens: List[str] = []

    def _detach(pattern: str, repl_fn, flags: int = re.IGNORECASE) -> None:
        nonlocal s
        def _grab(m: re.Match[str]) -> str:
            val = repl_fn(m) if callable(repl_fn) else repl_fn
            if val:
                suffix_tokens.append(val)
            return " "
        s = re.sub(pattern, _grab, s, flags=flags)

    # Past-narrative guard: keep prose intact with idiom normalization instead of detaching slots
    is_past_narrative = bool(re.search(r"\b(?:hôm\s*qua|hom\s*qua|hôm\s*kia|hom\s*kia)\b", s, re.IGNORECASE))

    _detach(
        r"\b(?:không\s*chia(?:\s*nhỏ)?|khong\s*chia(?:\s*nho)?|liền\s*mạch|lien\s*mach)\b",
        "do not split",
    )
    _detach(r"\b(?:khẩn\s*cấp|khan\s*cap|rất\s*gấp|rat\s*gap)\b", "urgent")

    if is_past_narrative:
        s = re.sub(r"\b(?:hôm\s*qua|hom\s*qua)\b", "yesterday", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:thức\s*(?:tới|đến)|thuc\s*(?:toi|den))\b", "stayed up until", s, flags=re.IGNORECASE)
        s = re.sub(r"\b(?:cày\s*phim|cay\s*phim)\b", "watching movies", s, flags=re.IGNORECASE)
        s = re.sub(
            r"\b(\d{1,2})\s*(?:h|giờ|gio)\s*(sáng|sang|trưa|trua|chiều|chieu|tối|toi|đêm|dem)\b",
            lambda m: _format_tod_clock(int(m.group(1)), m.group(2)),
            s,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s{2,}", " ", s).strip(), suffix_tokens

    # Detach release-date clauses cleanly (`bắt đầu từ ngày mai`)
    _detach(
        r"\b(?:bắt\s*đầu\s*(?:từ|sau)|bat\s*dau\s*(?:tu|sau))\s+([^,;]+?)(?=,|;|$)",
        lambda m: f"starting after {_normalize_vi_weekdays(_translate_relative_day(m.group(1)))}",
    )

    # Detach section multipliers (`mỗi chương 45 phút`, `mỗi phần 1 tiếng`)
    _detach(
        r"\bmỗi\s*(chương|phần|bài)\s*(\d+)\s*(phút|phut|p|tiếng|tieng|giờ|gio)\b",
        lambda m: (
            f"each chapter {int(m.group(2)) * (60 if m.group(3).lower()[0] in ('t', 'g') else 1)} minutes"
        ),
    )
    s = re.sub(r"\bmỗi\s*(?:chương|phần|bài)\s*(?:dưới|tối\s*đa|<)\b", "each chapter under", s, flags=re.IGNORECASE)

    # Detach combined deadline/event time+day (`hạn 17h thứ 6 tuần này`, `lúc 14h ngày mai`, `trước 17h30 thứ 5`)
    _day_expr = (
        r"(?:ngày\s*mai|ngay\s*mai|mai|hôm\s*nay|hom\s*nay|tối\s*nay|toi\s*nay|"
        r"chiều\s*mai|chieu\s*mai|sáng\s*mai|sang\s*mai|tối\s*mai|toi\s*mai|"
        r"(?:(?:thứ|thu)\s*(?:2|3|4|5|6|7|hai|ba|tu|tư|nam|năm|sau|sáu|bay|bảy)|chủ\s*nhật|chu\s*nhat|cn|t[2-7])(?:\s+(?:tuần\s*này|tuan\s*nay|tuần\s*tới|tuan\s*toi))?)"
    )
    _detach(
        rf"\b(?:trước|truoc|hạn|han)\s*(\d{{1,2}})\s*(?:h|giờ|gio)\s*(\d{{1,2}})?\s*({_day_expr})\b",
        lambda m: f"before {_format_12h_clock(int(m.group(1)), int(m.group(2) or 0))} {_normalize_vi_weekdays(_translate_relative_day(m.group(3)))}",
    )
    _detach(
        rf"\b(?:lúc|luc|vào|vao)\s*(\d{{1,2}})\s*(?:h|giờ|gio)\s*(\d{{1,2}})?\s*({_day_expr})\b",
        lambda m: f"at {_format_12h_clock(int(m.group(1)), int(m.group(2) or 0))} {_normalize_vi_weekdays(_translate_relative_day(m.group(3)))}",
    )
    _detach(
        r"\b(?:trước|truoc|hạn|han)\s*(\d{1,2})\s*(?:h|giờ|gio)\s*(\d{1,2})?\b",
        lambda m: f"before {_format_12h_clock(int(m.group(1)), int(m.group(2) or 0))}",
    )
    _detach(
        r"\b(?:lúc|luc|vào|vao)\s*(\d{1,2})\s*(?:h|giờ|gio)\s*(\d{1,2})?\b",
        lambda m: f"at {_format_12h_clock(int(m.group(1)), int(m.group(2) or 0))}",
    )

    # Detach half-hour & integer durations (`1 tiếng rưỡi` -> `for 90 minutes`, `trong 2 tiếng` -> `for 2 hours`)
    _detach(
        r"\b(?:trong\s*)?(\d+)\s*(?:tiếng|tieng|giờ|gio)\s*(?:rưỡi|ruoi)\b",
        lambda m: f"for {int(m.group(1)) * 60 + 30} minutes",
    )
    _detach(
        r"\b(?:trong\s*)?(\d+(?:\.\d+)?)\s*(?:tiếng|tieng|giờ|gio)\b",
        lambda m: f"for {m.group(1)} hours",
    )
    _detach(
        r"\b(?:trong\s*)?(\d+)\s*(?:phút|phut|p)\b",
        lambda m: f"for {m.group(1)} minutes",
    )

    # Detach standalone relative dayparts/days if remaining (`tối nay`, `ngày mai`)
    _detach(
        rf"\b({_day_expr})\b",
        lambda m: _normalize_vi_weekdays(_translate_relative_day(m.group(1))),
    )

    # Clean dangling punctuation left by detached trailing slots (e.g. "3 chương , ,")
    s = re.sub(r"(?:,\s*)+$", "", s)
    s = re.sub(r",\s*,+", ",", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" ,")
    return s, suffix_tokens


def _translate_relative_day(text: str) -> str:
    t = text.strip()
    t = re.sub(r"\b(?:chiều\s*mai|chieu\s*mai)\b", "tomorrow afternoon", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:sáng\s*mai|sang\s*mai)\b", "tomorrow morning", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:tối\s*mai|toi\s*mai)\b", "tomorrow evening", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:ngày\s*mai|ngay\s*mai|mai)\b", "tomorrow", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:hôm\s*nay|hom\s*nay)\b", "today", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:tối\s*nay|toi\s*nay)\b", "tonight", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:tuần\s*này|tuan\s*nay)\b", "this week", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(?:tuần\s*tới|tuan\s*toi)\b", "next week", t, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", t).strip()


def _format_tod_clock(hour: int, tod: str) -> str:
    t = tod.lower()
    if t in ("chiều", "chieu", "tối", "toi", "đêm", "dem") and hour < 12:
        if t in ("đêm", "dem") and hour <= 4:
            pass  # 2h đêm -> 2:00 AM
        else:
            hour += 12
    elif t in ("trưa", "trua") and hour < 11:
        hour += 12
    return _format_12h_clock(hour, 0)


_NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def _post_normalize_english(text: str) -> str:
    """Restore spelled-out small numbers, spacing, and inline subtask status markers."""
    s = re.sub(r"\b(AM|PM)(?=[A-Za-z])", r"\1 ", text)
    s = re.sub(r"\ban\s+hour\b", "1 hour", s, flags=re.IGNORECASE)
    s = re.sub(
        r"\b(" + "|".join(_NUMBER_WORDS.keys()) + r")\s+(chapters?|sections?|parts?|modules?|units?|hours?|hrs?|minutes?|mins?)\b",
        lambda m: f"{_NUMBER_WORDS[m.group(1).lower()]} {m.group(2)}",
        s,
        flags=re.IGNORECASE,
    )
    # Map NLLB inline subtask status words to canonical tokens
    s = re.sub(r"\(\s*(?:completed|finished)\s*\)", "(done)", s, flags=re.IGNORECASE)
    s = re.sub(r"\(\s*(?:working|ongoing|doing)\s*\)", "(in progress)", s, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", s).strip()


def _rule_translate_line(line: str) -> str:
    """Zero-dependency deterministic fallback when CT2 model weights are unavailable."""
    out = line
    for pat, repl in _RULE_PHRASE_MAP:
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


class VietnameseToEnglishTranslator:
    """Singleton-cacheable CTranslate2 Vietnamese -> English translator."""

    def __init__(self, backend: Optional[str] = None, local_files_only: bool = False):
        req = (backend or os.getenv("NL_TRANSLATOR_BACKEND") or "nllb").strip().lower()
        self.requested_backend = req
        self.local_files_only = local_files_only
        self._backend_loaded: Optional[str] = None
        self._model_id: Optional[str] = None
        self._translator = None
        self._sp_src = None
        self._sp_tgt = None

    def _ensure_loaded(self) -> str:
        if self._backend_loaded is not None:
            return self._backend_loaded

        if self.requested_backend == "rule" or ctranslate2 is None or spm is None or snapshot_download is None:
            self._backend_loaded = "rule"
            return "rule"

        candidates = (
            [("nllb", NLLB_REPO_ID), ("opus", OPUS_REPO_ID)]
            if self.requested_backend != "opus"
            else [("opus", OPUS_REPO_ID), ("nllb", NLLB_REPO_ID)]
        )

        for kind, repo_id in candidates:
            try:
                try:
                    model_dir = snapshot_download(repo_id, local_files_only=True)
                except Exception:
                    if self.local_files_only:
                        raise
                    model_dir = snapshot_download(repo_id, local_files_only=False)
                translator = ctranslate2.Translator(model_dir, device="cpu", compute_type="int8")
                if kind == "nllb":
                    sp = spm.SentencePieceProcessor(os.path.join(model_dir, "sentencepiece.bpe.model"))
                    self._sp_src = sp
                    self._sp_tgt = sp
                else:
                    self._sp_src = spm.SentencePieceProcessor(os.path.join(model_dir, "source.spm"))
                    self._sp_tgt = spm.SentencePieceProcessor(os.path.join(model_dir, "target.spm"))
                self._translator = translator
                self._backend_loaded = kind
                self._model_id = repo_id
                return kind
            except Exception:
                continue

        self._backend_loaded = "rule"
        self._model_id = None
        return "rule"

    def _translate_segment_ct2(self, segment: str, kind: str) -> str:
        if not segment.strip():
            return ""
        if kind == "nllb":
            src_tokens = ["vie_Latn"] + self._sp_src.encode(segment, out_type=str) + ["</s>"]
            res = self._translator.translate_batch([src_tokens], target_prefix=[["eng_Latn"]], beam_size=2)
            hyp = [tok for tok in res[0].hypotheses[0] if tok not in ("eng_Latn", "</s>")]
            return self._sp_tgt.decode(hyp).strip()

        src_tokens = self._sp_src.encode(segment, out_type=str) + ["</s>"]
        res = self._translator.translate_batch([src_tokens], beam_size=2)
        return self._sp_tgt.decode(res[0].hypotheses[0]).strip()

    def _translate_line(self, raw_line: str) -> Tuple[str, str]:
        stripped = raw_line.strip()
        if not stripped:
            return "", self._ensure_loaded()

        # Preserve bullet/step prefix verbatim so extract_declared_subtasks() stays intact
        bullet_prefix = ""
        body = stripped
        m_bullet = re.match(r"^(\s*(?:[-*•]|✅|⏳|⬜|\(\d+\)|Step\s+\d+:)\s*)(.+)$", stripped, re.IGNORECASE)
        if m_bullet:
            bullet_prefix = m_bullet.group(1)
            body = m_bullet.group(2)

        body_no_tags, protected = _extract_protected_tokens(body)
        norm_body, suffix_tokens = _pre_normalize_vietnamese_cues(body_no_tags)

        kind = self._ensure_loaded()
        if not norm_body:
            en_body = ""
        elif re.fullmatch(r"\s*(?:tập\s*gym|tap\s*gym)\s*", norm_body, re.IGNORECASE):
            en_body = "Gym workout"
        elif contains_vietnamese(norm_body):
            # Translate fluent full line (do not split on `:`, which causes NLLB to drop parentheticals)
            if kind in ("nllb", "opus"):
                en_body = self._translate_segment_ct2(norm_body, kind)
            else:
                en_body = _rule_translate_line(norm_body)
        else:
            en_body = norm_body

        en_body = _post_normalize_english(en_body)
        segments = [en_body] if en_body else []
        if suffix_tokens:
            segments.append(", ".join(suffix_tokens))
        base_str = ", ".join(s.rstrip("., ") for s in segments if s)
        rebuilt = " ".join(p for p in [base_str, *protected] if p).strip()
        rebuilt = re.sub(r"\s{2,}", " ", rebuilt)
        return f"{bullet_prefix}{rebuilt}", kind

    def translate(self, text: str) -> TranslationResult:
        t0 = time.perf_counter()
        if not contains_vietnamese(text):
            return TranslationResult(
                translated_text=text,
                original_text=text,
                translation_applied=False,
                backend_used="bypass_en",
                model_id=None,
                latency_ms=0.0,
            )

        lines = text.splitlines()
        translated_lines: List[str] = []
        used_kind = "rule"
        for line in lines:
            en_line, used_kind = self._translate_line(line)
            translated_lines.append(en_line)

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return TranslationResult(
            translated_text="\n".join(translated_lines),
            original_text=text,
            translation_applied=True,
            backend_used=used_kind,
            model_id=self._model_id,
            latency_ms=round(elapsed_ms, 2),
        )


_TRANSLATOR_CACHE: Dict[Tuple[str, bool], VietnameseToEnglishTranslator] = {}


def get_translator(backend: Optional[str] = None, local_files_only: bool = False) -> VietnameseToEnglishTranslator:
    key = ((backend or os.getenv("NL_TRANSLATOR_BACKEND") or "nllb").strip().lower(), bool(local_files_only))
    if key not in _TRANSLATOR_CACHE:
        _TRANSLATOR_CACHE[key] = VietnameseToEnglishTranslator(backend=key[0], local_files_only=key[1])
    return _TRANSLATOR_CACHE[key]


def translate_to_english(
    text: str,
    *,
    backend: Optional[str] = None,
    local_files_only: bool = False,
) -> TranslationResult:
    """Public entry point: translates Vietnamese prompts to English while bypassing pure English."""
    return get_translator(backend=backend, local_files_only=local_files_only).translate(text)
