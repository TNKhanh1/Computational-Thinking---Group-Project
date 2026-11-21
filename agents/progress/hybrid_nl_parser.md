# Hybrid EN/VI Natural Language Parser & Student Modal UX

> **Module:** `smartschedule/nlp/hybrid_pipeline/` + `smartschedule/nlp/parser_controller.py` (M1) + `smartschedule/nlp/{clause_condenser,context_router}.py` + `smartschedule/api/` + `smartschedule/ui/`  
> **Status:** Operational — `200/200` YAML benchmark (`rule`), `17/17` pytest integration & unbiased generalization tests passing, merged in `v1.0-alpha` with the **Online Lightweight Context Model (`gemini-2.5-flash-lite`)**.

---

## 1. Architecture Overview

The SmartSchedule Hybrid EN/VI NL Parser combines the deterministic **6-stage offline pipeline** ([`smartschedule/nlp/hybrid_pipeline/hybrid_parser.py`](../../smartschedule/nlp/hybrid_pipeline/hybrid_parser.py)) with M1 ([`parser_controller.py`](../../smartschedule/nlp/parser_controller.py)), modular Chat-First context routing (`context_router.py` + `clause_condenser.py`), and the Chat-First UI (`smartschedule/ui/`).

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

## 2. Core Pipeline Files (`smartschedule/nlp/hybrid_pipeline/`)

The refactored package directory inside [`smartschedule/nlp/hybrid_pipeline/`](../../smartschedule/nlp/hybrid_pipeline/) contains the 7 core runtime modules (plus `context_router.py` & `clause_condenser.py` in [`smartschedule/nlp/`](../../smartschedule/nlp/) for `v1.0-alpha` chat context parsing):

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

## 3. Chat-First Entry & Cross-Day Context Upgrades (`smartschedule/nlp/` & `smartschedule/ui/`)

- **Chat-First `"Trợ lý xếp lịch"` Composer (`smartschedule/ui/index.html`, `js/chat-assistant.js`):** Launches directly into `#viewChat` with clean prompt entry (no saved-task pill clutter or prefix injection), citation attachment checking (`[[filename]]` / `@[path]`), and a single **`🗓️ Kiểm tra lịch trình`** post-action button.
- **Merged 3-Layer Context Extraction (`clause_condenser.py` + `context_router.py`):** Pre-splits multi-day prompts into single atomic tasks (`start_after` + `deadline` + `is_splittable=False`), summarizes concise titles via online `gemini-2.5-flash-lite` (`0 MB` local RAM) or offline syntactic condensation (e.g., `"Làm bài tập Computational Thinking"`), and pairs with `task_tracer.py` SHA-256 fingerprints for hidden parameter updates.
- **Cross-Browser Drag-and-Drop:** `window` + `document` drag guards with `dt.items` fallback and `decodeURIComponent` prevent Edge, Chrome, Firefox, and Safari from opening dragged files in a new browser tab.

---

## 4. Verification Coverage

| Suite | Command | Verified Result |
| :--- | :--- | :--- |
| **Schema Validator** | `python -B tests/fixtures/nl_cases/validate_cases.py` | `200` cases — `All checks passed` |
| **200-Case Hybrid Benchmark** | `python -B tests/fixtures/nl_cases/verify_hybrid_200.py` | `200/200 (100.0%)` |
| **Hybrid Integration Tests** | `pytest tests/logical/test_hybrid_nl_integration.py` | Included in `--pass` (`12` tests) |
| **Unbiased Generalization Tests** | `pytest tests/logical/test_hybrid_unbiased_generalization.py` | Included in `--pass` (`9` tests) |
