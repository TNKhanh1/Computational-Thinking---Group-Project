"""
Logical Syllabus & Assignment Attachment Compiler (`doc_attachment_parser.py`, Pattern P14a).

Extracts structured milestones, grade weights, cognitive-load estimates, sequential
dependency hints (`depends_on_prev`), and realistic duration lower bounds from
`.pdf`, `.md`, and `.txt` assignment/syllabus attachments.

Architectural compliance (`INV-5` Memory Budget):
  - Optional PDF libraries (`pypdf`, `docling`) are strictly lazy-imported inside
    function scope with a pure-Python stdlib fallback so baseline import RAM delta is ~0 KB.
  - Enforces a hard `<= 20 MB` attachment size guardrail.
"""

from __future__ import annotations

import base64
import io
import math
import os
import re
import tempfile
import unicodedata
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from smartschedule.core.models import GRADE_WEIGHT_TO_PRIORITY
from smartschedule.core.utils import round_up_to_15

MAX_ATTACHMENT_BYTES: int = 20 * 1024 * 1024  # 20 MB hard cap

_MILESTONE_HEADING_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:[-*•]\s*)?"
    r"(?:\*{0,2})"
    r"(?:(?:Part|Phan|Phần|Section|Muc|Mục|Task|Bai(?:\s+tap)?|Bài(?:\s+tập)?|"
    r"Problem|Question|Cau(?:\s+hoi)?|Câu(?:\s+hỏi)?|Step|Buoc|Bước|"
    r"Milestone|Phase|Stage|Giai\s*doan|Giai\s*đoạn|Requirement|Yeu\s*cau|Yêu\s*cầu)\s*"
    r"(?:[0-9]+|[IVX]+|[A-Z])(?:\.[0-9]+)?\b"
    r"|(?:[0-9]{1,2})[.)]\s+(?=\S))"
    r"[:\-–—.)\s*]*(.+)$",
    re.IGNORECASE,
)

_NUMBERED_PREFIX_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?(?:[-*•]\s*)?\*{0,2}"
    r"((?:Part|Phan|Phần|Section|Muc|Mục|Task|Bai(?:\s+tap)?|Bài(?:\s+tập)?|"
    r"Problem|Question|Cau(?:\s+hoi)?|Câu(?:\s+hỏi)?|Step|Buoc|Bước|"
    r"Milestone|Phase|Stage|Giai\s*doan|Giai\s*đoạn|Requirement|Yeu\s*cau|Yêu\s*cầu)\s*"
    r"(?:[0-9]+|[IVX]+|[A-Z])(?:\.[0-9]+)?|[0-9]{1,2}[.)])\s*[:\-–—.)\s*]*",
    re.IGNORECASE,
)

_SKIP_SECTION_RE = re.compile(
    r"^(?:overview|introduction|background|submission(?:\s+guidelines?)?|"
    r"academic\s+integrity|references|grading\s+rubric|notes?|"
    r"tong\s*quan|gioi\s*thieu|quy\s*dinh\s*nop\s*bai|tai\s*lieu\s*tham\s*khao)$",
    re.IGNORECASE,
)

_COURSE_WEIGHT_RE = re.compile(
    r"(?:worth|counts?\s+for|chiem|chiếm|trong\s*so|trọng\s*số)\s*(?:about\s*)?"
    r"(100|[1-9]\d?)\s*%\s*(?:of\s+(?:final\s+)?grade|diem|điểm)?",
    re.IGNORECASE,
)

_PCT_RE = re.compile(r"\b(100|[1-9]\d?)\s*(?:%|(?:percent|phần\s*trăm)\b)", re.IGNORECASE)
_PTS_RE = re.compile(r"\b(100|[1-9]\d?)\s*(?:pts|points?|diem|điểm)\b", re.IGNORECASE)
_TEN_SCALE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*/\s*10\s*(?:pts|points?|diem|điểm)?\b", re.IGNORECASE)

_EXPLICIT_HOURS_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h|tieng|tiếng|gio|giờ)\b",
    re.IGNORECASE,
)
_EXPLICIT_MINUTES_RE = re.compile(
    r"\b(\d{1,3})\s*(?:minutes?|mins?|min|phut|phút|p)\b",
    re.IGNORECASE,
)

_DEEP_KEYWORDS_RE = re.compile(
    r"\b(?:implement|code|coding|program|algorithm|prove|proof|derive|optimize|"
    r"solver|simulate|simulation|architecture|parser|compiler|backend|database|dag|"
    r"graph|dynamic\s+programming|backtracking|alns|cuda|kernel|"
    r"lap\s*trinh|lập\s*trình|cai\s*dat|cài\s*đặt|thuat\s*toan|thuật\s*toán|"
    r"chung\s*minh|chứng\s*minh|toi\s*uu|tối\s*ưu|mo\s*phong|mô\s*phỏng)\b"
    r"|\.(?:py|cpp|c|java|ts|js|rs|go)\b",
    re.IGNORECASE,
)

_LIGHT_KEYWORDS_RE = re.compile(
    r"\b(?:install|setup|set\s+up|configure|read|reading|skim|zip|package|submit|"
    r"upload|format|checklist|doc|đọc|nộp\s*bài|nop\s*bai|đóng\s*gói|dong\s*goi|"
    r"cài\s*môi\s*trường|cai\s*moi\s*truong)\b",
    re.IGNORECASE,
)

_MEDIUM_KEYWORDS_RE = re.compile(
    r"\b(?:test|testing|unit\s*test|benchmark|evaluate|evaluation|analyze|analysis|"
    r"report|summary|slide|slides|diagram|chart|compare|verify|verification|"
    r"kiem\s*thu|kiểm\s*thử|danh\s*gia|đánh\s*giá|bao\s*cao|báo\s*cáo|"
    r"phan\s*tich|phân\s*tích|thuyet\s*trinh|thuyết\s*trình)\b",
    re.IGNORECASE,
)

_DEPENDENCY_CUES_RE = re.compile(
    r"\b(?:after|once|based\s+on|built?\s+on|from\s+(?:part|step|task|phase|section)|"
    r"using\s+(?:the\s+)?(?:output|result|results|part|step)|integrate|integrating|"
    r"following|then|finally|requires?\s+(?:part|step|task)|depends?\s+on|"
    r"sau\s*khi|dua\s*tren|dựa\s*trên|tu\s*(?:phan|phần|bai|bài|buoc|bước)|"
    r"tich\s*hop|tích\s*hợp|tiep\s*theo|tiếp\s*theo|cuoi\s*cung|cuối\s*cùng)\b",
    re.IGNORECASE,
)

_SEQUENTIAL_STAGE_RE = re.compile(
    r"^\s*(?:step|buoc|bước|phase|stage|giai\s*doan|giai\s*đoạn)\b",
    re.IGNORECASE,
)

_VERIFICATION_AFTER_BUILD_RE = re.compile(
    r"\b(?:test|testing|unit\s*test|benchmark|evaluate|evaluation|final\s+report|"
    r"integration|verify|verification|kiểm\s*thử|kiem\s*thu|đánh\s*giá|báo\s*cáo\s*tổng\s*kết)\b",
    re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return stripped.replace("đ", "d").replace("Đ", "D")


def _weight_to_priority(weight_pct: Optional[int]) -> int:
    if weight_pct is None or weight_pct <= 0:
        return GRADE_WEIGHT_TO_PRIORITY["none"]
    if weight_pct >= 30:
        return GRADE_WEIGHT_TO_PRIORITY["30+"]
    if weight_pct >= 20:
        return GRADE_WEIGHT_TO_PRIORITY["20-29"]
    if weight_pct >= 10:
        return GRADE_WEIGHT_TO_PRIORITY["10-19"]
    return GRADE_WEIGHT_TO_PRIORITY["<10"]


def _decode_raw_bytes_or_text(filename: str, raw_bytes_or_text: bytes | str) -> Tuple[bytes, Optional[str]]:
    """
    Validate <= 20 MB cap and normalize either raw bytes, data-URI base64,
    or plain text into `(raw_bytes, decoded_text_if_plain)`.
    """
    if isinstance(raw_bytes_or_text, (bytes, bytearray)):
        raw_bytes = bytes(raw_bytes_or_text)
        if len(raw_bytes) > MAX_ATTACHMENT_BYTES:
            raise ValueError(
                f"Attachment '{filename}' exceeds maximum allowed size of 20 MB ({len(raw_bytes)} bytes)."
            )
        return raw_bytes, None

    if isinstance(raw_bytes_or_text, str):
        text_val = raw_bytes_or_text
        raw_utf8 = text_val.encode("utf-8", errors="ignore")
        if len(raw_utf8) > MAX_ATTACHMENT_BYTES:
            raise ValueError(
                f"Attachment '{filename}' exceeds maximum allowed size of 20 MB ({len(raw_utf8)} bytes)."
            )

        stripped = text_val.strip()
        if stripped.startswith("data:") and ";base64," in stripped[:128]:
            b64_payload = stripped.split(";base64,", 1)[1].strip()
            try:
                decoded = base64.b64decode(b64_payload, validate=False)
                if len(decoded) > MAX_ATTACHMENT_BYTES:
                    raise ValueError(f"Decoded attachment '{filename}' exceeds 20 MB limit.")
                return decoded, None
            except ValueError:
                raise
            except Exception:
                pass

        if str(filename or "").lower().endswith(".pdf") and stripped.startswith("JVBERi0"):
            try:
                decoded = base64.b64decode(stripped, validate=False)
                if len(decoded) > MAX_ATTACHMENT_BYTES:
                    raise ValueError(f"Decoded attachment '{filename}' exceeds 20 MB limit.")
                return decoded, None
            except ValueError:
                raise
            except Exception:
                pass

        return raw_utf8, text_val

    raise TypeError(f"Unsupported attachment payload type: {type(raw_bytes_or_text).__name__}")


def _unescape_pdf_literal(raw_literal: bytes) -> str:
    """Decode PDF string literal bytes inside `(...)`, handling common escape sequences."""
    out = bytearray()
    i = 0
    n = len(raw_literal)
    while i < n:
        ch = raw_literal[i]
        if ch == 0x5C and i + 1 < n:  # backslash
            nxt = raw_literal[i + 1]
            if nxt == ord("n"):
                out.append(0x0A)
                i += 2
                continue
            if nxt == ord("r"):
                out.append(0x0D)
                i += 2
                continue
            if nxt == ord("t"):
                out.append(0x09)
                i += 2
                continue
            if nxt in (ord("("), ord(")"), ord("\\")):
                out.append(nxt)
                i += 2
                continue
            if ord("0") <= nxt <= ord("7"):
                oct_digits = raw_literal[i + 1 : i + 4]
                m = re.match(rb"[0-7]{1,3}", oct_digits)
                if m:
                    out.append(int(m.group(0), 8) & 0xFF)
                    i += 1 + len(m.group(0))
                    continue
        out.append(ch)
        i += 1
    try:
        return out.decode("utf-8")
    except UnicodeDecodeError:
        return out.decode("latin-1", errors="ignore")


def _extract_balanced_pdf_literals(inner: bytes) -> List[str]:
    """Extract PDF text lines from `BT ... ET` block, breaking lines on `Td`/`TD`/`T*` positioning."""
    lines: List[str] = []
    current_parts: List[str] = []
    n = len(inner)
    i = 0
    while i < n:
        if inner[i] == 0x28:  # '('
            depth = 1
            j = i + 1
            buf = bytearray()
            while j < n and depth > 0:
                ch = inner[j]
                if ch == 0x5C and j + 1 < n:
                    buf.append(ch)
                    buf.append(inner[j + 1])
                    j += 2
                    continue
                if ch == 0x28:
                    depth += 1
                    buf.append(ch)
                elif ch == 0x29:
                    depth -= 1
                    if depth > 0:
                        buf.append(ch)
                else:
                    buf.append(ch)
                j += 1
            decoded = _unescape_pdf_literal(bytes(buf)).strip()
            if decoded:
                current_parts.append(decoded)
            i = j
        elif inner[i : i + 2] in (b"Td", b"TD", b"T*") and (i == 0 or inner[i - 1 : i] in (b" ", b"\n", b"\r", b"\t")):
            if current_parts:
                lines.append(" ".join(current_parts))
                current_parts = []
            i += 2
        else:
            i += 1
    if current_parts:
        lines.append(" ".join(current_parts))
    return lines


def _extract_pdf_text_stdlib_fallback(raw_bytes: bytes) -> str:
    """
    Pure-Python stdlib PDF text stream fallback when `pypdf`/`docling` are absent.
    Decompresses FlateDecode streams and extracts text literals from `BT ... ET` blocks.
    """
    stream_chunks: List[bytes] = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\n?endstream", raw_bytes, re.DOTALL):
        stream_data = m.group(1)
        try:
            stream_chunks.append(zlib.decompress(stream_data))
        except Exception:
            stream_chunks.append(stream_data)

    chunks = stream_chunks if stream_chunks else [raw_bytes]

    extracted_lines: List[str] = []
    for blob_bytes in chunks:
        for bt_block in re.finditer(rb"BT(.*?)ET", blob_bytes, re.DOTALL):
            extracted_lines.extend(_extract_balanced_pdf_literals(bt_block.group(1)))

    if extracted_lines:
        return "\n".join(extracted_lines)

    # Final fallback for uncompressed plain-text embedded PDFs
    printable = [
        line.strip()
        for line in raw_bytes.decode("utf-8", errors="ignore").splitlines()
        if line.strip()
        and not line.lstrip().startswith(("%PDF", "obj", "endobj", "xref", "trailer", "startxref", "<<", ">>"))
    ]
    return "\n".join(printable)


def _extract_pdf_text(raw_bytes: bytes) -> str:
    """
    Extract text from PDF bytes using lazy-loaded `pypdf` -> `docling` -> pure stdlib fallback.
    All optional third-party imports stay strictly inside function scope (`INV-5`).
    """
    # 1. Lazy pypdf
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        joined = "\n".join(p for p in pages if p.strip()).strip()
        if joined:
            return joined
    except Exception:
        pass

    # 2. Lazy docling (optional)
    try:
        from docling.document_converter import DocumentConverter  # type: ignore

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(raw_bytes)
            tmp_path = tmp.name
        try:
            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            doc_text = result.document.export_to_markdown()
            if doc_text and doc_text.strip():
                return doc_text.strip()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    except Exception:
        pass

    # 3. Pure-Python stdlib fallback
    return _extract_pdf_text_stdlib_fallback(raw_bytes)


def _extract_text_payload(filename: str, raw_bytes_or_text: bytes | str) -> str:
    raw_bytes, direct_text = _decode_raw_bytes_or_text(filename, raw_bytes_or_text)
    is_pdf = raw_bytes.lstrip().startswith(b"%PDF") or (
        direct_text is None and str(filename or "").lower().endswith(".pdf")
    )
    if is_pdf:
        text = _extract_pdf_text(raw_bytes)
    elif direct_text is not None:
        text = direct_text
    else:
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw_bytes.decode("latin-1", errors="replace")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _extract_weight_pct(text: str) -> Optional[int]:
    m_pct = _PCT_RE.search(text)
    if m_pct:
        val = int(m_pct.group(1))
        if 1 <= val <= 100:
            return val
    m_pts = _PTS_RE.search(text)
    if m_pts:
        val = int(m_pts.group(1))
        if 1 <= val <= 100:
            return val
    m_ten = _TEN_SCALE_RE.search(text)
    if m_ten:
        val = int(round(float(m_ten.group(1)) * 10.0))
        if 1 <= val <= 100:
            return val
    return None


def _extract_explicit_duration_min(text: str) -> Optional[int]:
    total_min = 0.0
    matched = False
    for m_hr in _EXPLICIT_HOURS_RE.finditer(text):
        total_min += float(m_hr.group(1)) * 60.0
        matched = True
    for m_min in _EXPLICIT_MINUTES_RE.finditer(text):
        total_min += float(m_min.group(1))
        matched = True
    if not matched or total_min <= 0:
        return None
    return max(15, round_up_to_15(int(math.ceil(total_min))))


def _infer_cognitive_load(text: str) -> int:
    if _DEEP_KEYWORDS_RE.search(text):
        return 3
    if _LIGHT_KEYWORDS_RE.search(text) and not _MEDIUM_KEYWORDS_RE.search(text):
        return 1
    return 2


def _estimate_milestone_minutes(body_text: str, cognitive_load: int, weight_pct: Optional[int]) -> int:
    explicit = _extract_explicit_duration_min(body_text)
    if explicit is not None:
        return explicit
    base_by_load = {1: 30, 2: 60, 3: 75}
    est = base_by_load.get(cognitive_load, 60)
    if weight_pct is not None:
        if weight_pct >= 40:
            est += 30
        elif weight_pct >= 25:
            est += 15
        elif weight_pct < 10:
            est -= 15
    return max(15, round_up_to_15(est))


def _clean_milestone_title(raw_line: str) -> str:
    cleaned = raw_line.strip()
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned)
    cleaned = re.sub(r"^[-*•]\s*", "", cleaned)
    cleaned = cleaned.replace("**", "").replace("__", "").strip()
    cleaned = re.sub(r"\s*[\(\[]\s*\d+(?:\.\d+)?\s*(?:%|pts|points?|điểm|diem)\s*[\)\]]\s*", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([:.,;])", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :-–—")
    if len(cleaned) > 110:
        cleaned = cleaned[:107].rstrip() + "..."
    return cleaned


def _segment_milestones(extracted_text: str, filename: str) -> List[Tuple[str, str, str]]:
    """
    Segment extracted document text into `(prefix_token, title, full_section_text)` tuples.
    Filters out purely administrative sections when real assignment parts exist.
    """
    lines = extracted_text.splitlines()
    candidates: List[Tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _MILESTONE_HEADING_RE.match(stripped):
            m_prefix = _NUMBERED_PREFIX_RE.match(stripped)
            prefix = m_prefix.group(1).strip() if m_prefix else ""
            title = _clean_milestone_title(stripped)
            if title:
                candidates.append((idx, prefix, title))

    sections: List[Tuple[str, str, str]] = []
    if candidates:
        for pos, (start_idx, prefix, title) in enumerate(candidates):
            end_idx = candidates[pos + 1][0] if pos + 1 < len(candidates) else len(lines)
            body = "\n".join(lines[start_idx:end_idx]).strip()
            sections.append((prefix, title, body))

        filtered = [
            sec
            for sec in sections
            if not _SKIP_SECTION_RE.match(_strip_accents(sec[1]).strip())
        ]
        if filtered:
            return filtered
        return sections

    # Fallback: single milestone derived from first Markdown heading or filename stem
    first_heading = ""
    for line in lines:
        s = line.strip()
        if s:
            first_heading = _clean_milestone_title(s)
            break
    fallback_title = first_heading or Path(filename or "Assignment").stem.replace("_", " ").strip() or "Document Task"
    return [("", fallback_title, extracted_text)]


def parse_document_constraint_digest(filename: str, raw_bytes_or_text: bytes | str) -> Dict[str, Any]:
    """
    Compile an attached syllabus / assignment specification (`.pdf`, `.md`, `.txt`)
    into a quantitative `DocumentConstraintDigest` dictionary:
      {
        "filename": str,
        "extracted_text": str,
        "milestones": [{"title", "weight_pct", "estimated_min", "cognitive_load", "depends_on_prev"}],
        "suggested_total_min": int,
        "suggested_priority": int,
        "suggested_load": int,
      }
    """
    safe_name = str(filename or "attachment.txt")
    extracted_text = _extract_text_payload(safe_name, raw_bytes_or_text)
    if not extracted_text:
        return {
            "filename": safe_name,
            "extracted_text": "",
            "milestones": [],
            "suggested_total_min": 0,
            "suggested_priority": 3,
            "suggested_load": 2,
        }

    sections = _segment_milestones(extracted_text, safe_name)
    milestones: List[Dict[str, Any]] = []

    for idx, (prefix, title, body) in enumerate(sections):
        weight_pct = _extract_weight_pct(title)
        if weight_pct is None:
            weight_pct = _extract_weight_pct(body)
        load = _infer_cognitive_load(body)
        est_min = _estimate_milestone_minutes(body, load, weight_pct)

        if idx == 0:
            depends_on_prev = False
        else:
            prev_load = milestones[-1]["cognitive_load"]
            has_prior_deep = any(m["cognitive_load"] == 3 for m in milestones)
            has_explicit_dep = bool(_DEPENDENCY_CUES_RE.search(body))
            is_seq_stage = bool(_SEQUENTIAL_STAGE_RE.match(prefix))
            is_post_build_verify = (prev_load == 3 or has_prior_deep) and bool(
                _VERIFICATION_AFTER_BUILD_RE.search(title + " " + body)
            )
            depends_on_prev = bool(has_explicit_dep or is_seq_stage or is_post_build_verify)

        milestones.append(
            {
                "title": title,
                "weight_pct": weight_pct,
                "estimated_min": int(est_min),
                "cognitive_load": int(load),
                "depends_on_prev": depends_on_prev,
            }
        )

    suggested_total_min = round_up_to_15(sum(m["estimated_min"] for m in milestones))
    suggested_load = max((m["cognitive_load"] for m in milestones), default=2)

    # Priority resolution: course weight mention -> max milestone weight -> effort floor
    course_match = _COURSE_WEIGHT_RE.search(extracted_text)
    if course_match:
        suggested_priority = _weight_to_priority(int(course_match.group(1)))
    else:
        weights = [m["weight_pct"] for m in milestones if m["weight_pct"] is not None]
        if weights:
            suggested_priority = max(_weight_to_priority(w) for w in weights)
        elif suggested_total_min >= 180 and suggested_load == 3:
            suggested_priority = 4
        else:
            suggested_priority = 3

    return {
        "filename": safe_name,
        "extracted_text": extracted_text,
        "milestones": milestones,
        "suggested_total_min": int(suggested_total_min),
        "suggested_priority": int(suggested_priority),
        "suggested_load": int(suggested_load),
    }


def detect_user_underestimate(
    user_duration_min: Optional[int],
    digest: Dict[str, Any],
    threshold_ratio: float = 0.5,
) -> Dict[str, Any]:
    """
    Compare a student's manual prompt duration against `digest['suggested_total_min']`
    and flag `USER_VS_DOC_UNDERESTIMATE` when `user_duration_min < threshold_ratio * suggested_total_min`.
    """
    suggested_total = int(digest.get("suggested_total_min") or 0)
    if user_duration_min is None or user_duration_min <= 0 or suggested_total <= 0:
        return {
            "is_underestimate": False,
            "conflict_code": None,
            "user_duration_min": user_duration_min,
            "suggested_total_min": suggested_total,
            "ratio": None,
        }

    ratio = float(user_duration_min) / float(suggested_total)
    is_under = ratio < float(threshold_ratio)
    return {
        "is_underestimate": is_under,
        "conflict_code": "USER_VS_DOC_UNDERESTIMATE" if is_under else None,
        "user_duration_min": int(user_duration_min),
        "suggested_total_min": suggested_total,
        "ratio": round(ratio, 3),
    }
