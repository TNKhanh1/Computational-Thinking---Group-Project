# SmartSchedule `v1.0-alpha` — Master Technical Guide & Execution Checklist (`v1.0-alpha-plan/README_agents.md`)

> [!IMPORTANT]
> **MANDATORY AGENT HUB (`v1.0-alpha/ui-ux-chat`):**
> After reading [`agents/README.md`](../agents/README.md), read this document completely before planning edits. It unifies all four `v1.0-alpha` workstreams — **Modular Directory Rebase**, **Ultra-Minimal Chat-First UI/UX**, **Algorithmic Engine & Dominant Subset Design**, and **Merged Online Lightweight Context Parsing** — with exact module paths and checkable `[x]`/`[ ]` progress trackers.

---

## 1. Unified `v1.0-alpha` Architecture Overview

### 1.1. Modular Codebase Division (`folder_division_plan.md`)
Legacy `group03-smartschedule-baseline/` has been permanently replaced at repository root:
- **`smartschedule/`** — Installable Python application (`pyproject.toml`):
  - `smartschedule/core/` (**Layers 1–3**): Pure domain models, workspace/parameter config (`config.py`), grid math (`utils.py`), Planning-Fallacy buffering (`estimate_buffer.py`), M7 EWMA calibration (`calibration.py`), SHA-256 keyword tracer (`task_tracer.py`), SQLite persistence (`storage.py`), `.ics` importer (`ics_importer.py`), orchestration (`controller.py`, `overload_triage.py`), grid (`grid_manager.py`), and 6 stateless solvers (`solvers/`).
  - `smartschedule/nlp/` (**Layer 4A**): M1 Gemini + deterministic controller (`parser_controller.py`), 7-module 6-stage offline pipeline (`hybrid_pipeline/`), `v1.0-alpha` online lightweight context extractor (`context_router.py`), and clause-level Vietnamese subject title condenser (`clause_condenser.py`).
  - `smartschedule/api/` (**Layer 4B**): FastAPI server (`app.py`), modular Chat-First subpackage (`chat/handlers.py`, `chat/thinking_stage.py`, `chat/edge_cases.py`), auth (`auth.py`), `Testing_System v2.1` bridge (`health_v21.py`), V3 catalog/benchmark services (`v3_services.py`), and showcase (`test_showcase.py`).
  - `smartschedule/ui/` (**Layer 4B Static Assets**): `index.html`, ES module coordinator `app.js`, submodules `js/*.js`, and modular stylesheets `css/{tokens,shell,dev-panel,calendar,chat}.css` loaded via `css/app.css`.
- **`data/`** — `presets/`, `scenarios/` (`t01..t10`), `calibration/` (`alpha_grid_calibration.json`), and gitignored `runtime/local_state.db`.
- **`tests/`** — `clean_runner.py`, `test_studio.py`, `conftest.py`, `ui/`, `architecture/`, `logical/`, `benchmark/`, `gaps/`, and `fixtures/nl_cases/`.
- **`tools/`** — `member_eval/` (Blind Human Evaluation on `:8010`), `benchmarks/`, `docker/`, and Windows runners in `scripts/*.bat`.
- **`v1.0-alpha-plan/`** — Planning specs ([`UI_Rebuild_Plan/`](UI_Rebuild_Plan/), [`folder_division_plan.md`](folder_division_plan.md), [`Testing_Plan/`](Testing_Plan/)) and automated evaluator ([`Testing_System/`](Testing_System/)).

### 1.2. Ultra-Minimal Chat-First UI/UX ([`UI_Rebuild_Plan/agent_pipeline.md`](UI_Rebuild_Plan/agent_pipeline.md))
- **Default Entry (`#viewChat`, `"Trợ lý xếp lịch"`):** Antigravity-clean spacious chat canvas. Clicking `#btnBrandHome` (`SS SmartSchedule`) always returns to `#viewChat`.
- **Collapsible Left Sidebar (`#leftNavSidebar`):** Only 3 views (`Trợ lý xếp lịch`, `Lịch Trình Tuần`, `Danh Sách Việc`) + bottom `Developer Mode` switch (`#chkDeveloperMode`). Collapsing hides the entire sidebar (`display: none !important`); `"Chuyển nhanh tuần"` is removed.
- **Minimal Settings & Zero Composer Clutter:** `"Nền năng lượng sinh học"` and `"Tiện ích nhanh"` removed from `#settingsPopover` (backward-compatible DOM IDs retained `.sr-only` `hidden`); `"Chỉnh nhanh việc đã lưu"` removed; clicking either suggestion card sets mode badge hints without injecting text prefixes; every assistant reply exposes a single post-action button **`🗓️ Kiểm tra lịch trình`**.
- **Calendar + Collapsible Right Copilot (`#calendarCopilotDrawer`, `"Trợ lý tinh chỉnh trực tiếp"`):**
  - Aligned `"Hôm nay"` week pill (`#topbarWeekPill`) & clean single-row day headers in `render-calendar.js`.
  - Header arrow `#btnToggleCopilotDrawer` collapses the right drawer in-place to expand the calendar; `#btnExpandCopilotDrawer` (`"💬 Mở trợ lý"`) is strictly `display: none !important` whenever the copilot is open.
- **Developer Mode (`💭 Thinking Stage` + Hidden Badges):** Renders `.chat-thinking-stage` summarizing parsed context, why weaker dominated solvers (`EDF`/`LST`/`WSPT`) were pruned in favor of circadian-aware solvers (`SCORED_GREEDY`, `HYBRID_ALNS`), and SHA-256 hidden parameter mutations.

### 1.3. Algorithmic Kernel & Constraints (`smartschedule/core/`)
- **6 Registered Solvers (`solvers/registry.py`):** `EDF` (`V0` anchor), `LST` & `WSPT` (`V3` Energy-Blind), `SCORED_GREEDY` (fast circadian portfolio default), `BACKTRACK` (Branch-and-Bound), and `HYBRID_ALNS` (`ALNS` Ruin-and-Recreate + Regret-2).
- **Behavioral Modules:** `estimate_buffer.py` (`RARELY`/`SOMETIMES`/`OFTEN` + `COGNITIVE_LOAD` `1.20/1.35`), `calibration.py` (M7 EWMA), `task_tracer.py` (deterministic stdlib SHA-256 keyword fingerprinting), and `edge_cases.py` (`DEADLOCK` red recovery vs `DENSE_WARNING` yellow warning).
- **Non-Negotiable Invariants (`INV-1..6`):** Never import `smartschedule.api`, `smartschedule.nlp`, `fastapi`, or `google-genai` into `smartschedule/core/`; never mutate solver outputs or introduce memory growth (`< 350 KB` over 50 runs); keep end-to-end chat turn SLA `< 10,000 ms` (`< 1s` local).

### 1.4. Merged Online Lightweight Context-Parsing Model (`smartschedule/nlp/`)
- **Layer A (`< 2 ms`, local):** [`clause_condenser.py`](../smartschedule/nlp/clause_condenser.py) splits clauses on commas, extracts cross-day windows (`start_after` + `deadline`), total duration, and atomic continuity (`"liên tục"` -> `is_splittable=False`), preventing multi-day single-task prompts from splitting into multiple tasks.
- **Layer B (`220–550 ms`, `0 MB` local RAM):** [`context_router.py`](../smartschedule/nlp/context_router.py) invokes `gemini-2.5-flash-lite` / `gemini-2.5-flash` (when `GEMINI_API_KEY` exists in `environments/.env` / env) enforcing `ChatContextExtractionSchema` to summarize titles concisely (e.g. `"Làm bài tập Computational Thinking"`) and return a humanized thinking summary.
- **Layer C (`< 1 ms`, offline safety net):** Syntactic subject title condenser strips temporal/duration clauses and filler nouns (`"môn"`, `"học phần"`) when offline/CI so behavior stays deterministic.

---

## 2. Core Directory & File Reference Map

- **Entrypoint / Environments:** [`smartschedule/main.py`](../smartschedule/main.py), [`smartschedule/core/config.py`](../smartschedule/core/config.py), [`environments/README.md`](../environments/README.md), [`environments/pyproject.toml`](../environments/pyproject.toml), [`environments/CODEBASE_INDEX.md`](../environments/CODEBASE_INDEX.md), [`Project_Drafts/README.md`](../Project_Drafts/README.md)
- **Domain Core (Layers 1–3):** [`smartschedule/core/models.py`](../smartschedule/core/models.py), [`controller.py`](../smartschedule/core/controller.py), [`task_tracer.py`](../smartschedule/core/task_tracer.py), [`estimate_buffer.py`](../smartschedule/core/estimate_buffer.py), [`calibration.py`](../smartschedule/core/calibration.py), [`solvers/ergonomic_engine.py`](../smartschedule/core/solvers/ergonomic_engine.py)
- **NLP & Context Model (Layer 4A):** [`smartschedule/nlp/context_router.py`](../smartschedule/nlp/context_router.py), [`clause_condenser.py`](../smartschedule/nlp/clause_condenser.py), [`parser_controller.py`](../smartschedule/nlp/parser_controller.py), [`hybrid_pipeline/hybrid_parser.py`](../smartschedule/nlp/hybrid_pipeline/hybrid_parser.py)
- **API & Chat Orchestration (Layer 4B):** [`smartschedule/api/app.py`](../smartschedule/api/app.py), [`chat/handlers.py`](../smartschedule/api/chat/handlers.py), [`chat/thinking_stage.py`](../smartschedule/api/chat/thinking_stage.py), [`chat/edge_cases.py`](../smartschedule/api/chat/edge_cases.py)
- **Frontend UI (Layer 4B):** [`smartschedule/ui/index.html`](../smartschedule/ui/index.html), [`app.js`](../smartschedule/ui/app.js), [`js/chat-assistant.js`](../smartschedule/ui/js/chat-assistant.js), [`js/render-calendar.js`](../smartschedule/ui/js/render-calendar.js), [`css/chat.css`](../smartschedule/ui/css/chat.css)
- **Verification & Tooling:** [`tests/clean_runner.py`](../tests/clean_runner.py), [`tests/logical/test_chat_first_ui_and_task_tracer.py`](../tests/logical/test_chat_first_ui_and_task_tracer.py), [`v1.0-alpha-plan/Testing_System/tests/`](Testing_System/tests/), [`tools/member_eval/`](../tools/member_eval/)

---

## 3. Verified Commands (Run From Repository Root)

```powershell
# Verification suites (Verified 100% green after modular rebase)
python -B tests/clean_runner.py --pass                                              # 194/194 passed
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q   # 39/39 passed
python -B tests/fixtures/nl_cases/verify_hybrid_200.py                              # 200/200 passed
node --check smartschedule/ui/app.js                           # JS syntax check

# Run servers
python -B -m smartschedule.main --serve                        # Web App :8000
python -B -m uvicorn tools.member_eval.app:app --port 8010     # Blind Eval :8010
```

---

## 4. `v1.0-alpha` Execution Checklist (Tick `[x]` Upon Verified Completion)

### Phase 1 — Codebase Modularization (`folder_division_plan.md`)
- [x] Eliminate `group03-smartschedule-baseline/` via `git mv` into `smartschedule/`, `data/`, `tests/`, `tools/` (preserving `.env` & `data/runtime/local_state.db`).
- [x] Modularize `chat_service.py` -> `smartschedule/nlp/{clause_condenser,context_router}.py` + `smartschedule/api/chat/{thinking_stage,edge_cases,handlers}.py`.
- [x] Split `app.css` -> `shell.css`, `dev-panel.css`, `calendar.css`, `chat.css` and consolidate environment/packaging files into [`environments/`](../environments/) + historical course drafts into [`Project_Drafts/`](../Project_Drafts/).
- [x] Rewire `smartschedule.core.config` path constants, `environments/pyproject.toml` `[tool.pytest.ini_options]`, and all test/tool paths (`194/194`, `39/39`, `200/200` green).
- [x] Overhaul `agents/README.md` (single AI entrypoint), `docs/README.md`, `agents/requirements.md`, `docs/requirements.md`, `progress/README.md`, archive Entries `001–015`, and commit modular division (`e56ab06`) + `Project_Drafts/` (`5a96211`).
- [ ] Final pre-merge branch review on `v1.0-alpha/ui-ux-chat` once team validation completes.

### Phase 2 — Chat-First UI/UX & Online Context Parsing (`UI_Rebuild_Plan/`)
- [x] Implement Revision 2–4 ultra-minimal UI rules (`#viewChat` entry, `#btnBrandHome`, clean Settings, full left sidebar collapse, in-place right copilot collapse + strictly hidden `#btnExpandCopilotDrawer`, aligned `"Hôm nay"`).
- [x] Implement 3-layer Merged Context Parser (Layer A pre-parser + Layer B `gemini-2.5-flash-lite` online model + Layer C `clause_condenser.py` offline safety net) & Developer Mode `💭` Thinking Stage.
- [x] Add automated verification in `tests/logical/test_chat_first_ui_and_task_tracer.py` (`7/7` passed).
- [ ] Perform live interactive browser verification (Chrome/Edge desktop & mobile widths) after server startup and inspect visual screenshots.
- [ ] Test live Gemini context extraction (`environments/.env` `GEMINI_API_KEY`) end-to-end against noisy student phrasing and refine academic title stop-words if needed.

### Phase 3 — Algorithmic & Evaluation Milestones
- [x] Keep `INV-1..6`, 6 solvers (`EDF`..`HYBRID_ALNS`), `DEADLOCK`/`DENSE_WARNING` chat reporting, and `Testing_System v2.1` (`39/39`) green.
- [ ] Collect blind human evaluation sessions across all 7 team members in `tools/member_eval/` and generate updated `Calibration_Report.md` (`>= 25%` friction cluster audit).
- [ ] Run updated multi-regime benchmarks (`tools/benchmarks/benchmark_runner.py`, `benchmark_alpha_grid.py`) for final CS252 report & slides.
