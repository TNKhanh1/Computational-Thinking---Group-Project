# Hybrid EN/VI Natural Language Parser & Student Modal UX

> **Module:** `NL_Parser_Package/` + `src/nl_parser.py` (M1) + `web/api.py` + `web/index.html` + `web/app.js`  
> **Status:** Operational — `200/200` YAML benchmark (`rule`, `458.1 ms`), `17/17` pytest integration & unbiased generalization tests passing.

---

## 1. Architecture Overview

The SmartSchedule Hybrid EN/VI NL Parser combines a deterministic **6-stage offline pipeline** (`NL_Parser_Package/hybrid_parser.py`) with the M1 SmartSchedule adapter (`src/nl_parser.py`) and an interactive **Student Task Modal** (`web/index.html`, `web/app.js`).

```text
User Prompt (EN / VI) + UI Metadata (Urgency 1-4, WorkRhythm, Linked Files)
   │
   ▼
[1] Citation Extraction & Validation (`[[filename]]`, `@[path/file]`)
   │   └─ Flags unbracketed doc refs or missing linked attachments (RED alerts)
   ▼
[2] Language Detection & VI→EN Translation (`translator.py`: rule | nllb | opus_mt)
   │
   ▼
[3] Hybrid Draft Extraction (`parser.py` + `regex_parser.py` + `tokenizer.py`)
   │   └─ Duration, Deadline Day/Time, Category (`QUIZ`, `EXAM`, `LAB`, `READING`, ...)
   ▼
[4] Category & Urgency Mapping (`1=Urgent..4=Low -> 5..1` Solver Priority)
   │   └─ Keeps `draft.priority` & `hybrid.urgency` synchronized
   ▼
[5] WorkRhythm & Splittability Synthesis (`pomodoro`, `balanced`, `deep_focus`)
   │   └─ Respects `Cho phép cắt nhỏ` vs `Làm liền 1 buổi` directly from the prompt bar
   ▼
[6] Validation & Normalization Diagnostics (`E_INVALID_CITATION_FORMAT`, warnings)
```

---

## 2. Core Pipeline Files (`group03-smartschedule-baseline/NL_Parser_Package/`)

The package directory inside `group03-smartschedule-baseline/NL_Parser_Package/` contains only the 7 deployed runtime modules:

| File | Responsibility |
| :--- | :--- |
| `__init__.py` | Package entry exports for `hybrid_parser` and runtime schemas |
| `hybrid_parser.py` | 6-stage orchestrator, citation bracket checker, `ui.linked_files` reconciliation |
| `parser.py` | Rule-based + structural semantic extraction for academic task attributes |
| `regex_parser.py` | Bilingual time, duration, date, and academic category pattern matchers |
| `schema.py` | Typed task draft, diagnostic code, and structured response definitions |
| `tokenizer.py` | Quote-preserving & bracket-preserving token segmentation |
| `translator.py` | Offline VI→EN translation router (`rule` fast path + optional CTranslate2 `nllb` / `opus_mt`) |

---

## 3. UI/UX & Cross-Browser Safety Upgrades (`web/index.html`, `web/app.js`)

- **Expanded Modal & Unsaved Draft Persistence:** `#stTaskModal` uses a wide responsive container (`max-w-3xl lg:max-w-4xl`, `max-h-[90vh]`, scrollable body), top-right `✕` + Esc/backdrop close, and `localStorage` draft auto-save (`saveStudentModalDraft`, `restoreStudentModalDraft`, `clearStudentModalDraft`, `#stModalDraftBadge`, `#btnStClearDraft`).
- **Chat-Style File Citation & Lossless Linking:** Unified `#stNlPromptBox` and `#stNlFileLinkBox` let users drag files in or insert `[[filename]]` / `@[path]` tokens into the prompt without losing text, displaying red borders and error cards (`CRITICAL_CITATION_CODES`, `HYBRID_DIAG_LABELS`) whenever citations are malformed or unattached.
- **Dependency Task IDs & Splittability:** Added `#stInpTaskId` plus clickable `#stExistingTaskIdChips` for **"Task cần phải làm trước đó (Task ID)"**, moved the splittability toggle (`✂️ Cho phép cắt nhỏ` | `🔒 Làm liền 1 buổi`) directly into the natural-language bar, and hid the redundant `"Ưu tiên Solver"` dropdown so `Khẩn cấp (1–4)` drives priority consistently.
- **Cross-Browser Drag-and-Drop:** Dual `window` + `document` `dragenter`/`dragover`/`drop`/`dragend` guards with `try { dropEffect = ... }`, `dt.items` fallback, `decodeURIComponent`, and `dragleave` child-element filtering prevent Edge, Chrome, Firefox, and Safari from opening dragged files in a new browser tab.

---

## 4. Verification Coverage

| Suite | Command | Verified Result |
| :--- | :--- | :--- |
| **Schema Validator** | `python -B verification_tests/NL_Parser_test_cases/validate_cases.py` | `200` cases — `All checks passed` |
| **200-Case Hybrid Benchmark** | `python -B verification_tests/NL_Parser_test_cases/verify_hybrid_200.py` | `200/200 (100.0%)` in `458.1 ms` |
| **Hybrid Integration Tests** | `pytest verification_tests/logical_tests/test_hybrid_nl_integration.py` | Included in `142/142` (`8` tests) |
| **Unbiased Generalization Tests** | `pytest verification_tests/logical_tests/test_hybrid_unbiased_generalization.py` | Included in `142/142` (`9` tests) |
