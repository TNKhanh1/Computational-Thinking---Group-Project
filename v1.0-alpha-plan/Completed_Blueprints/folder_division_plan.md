# Folder Division, File Modularization & Token-Optimization Plan (`group03-smartschedule-baseline` -> `v1.0-alpha`)

**Target Scope:** `group03-smartschedule-baseline/` & root workspace structure  
**Status:** Design & Refactoring Blueprint (pre-execution — no folders or files moved yet)  
**Verified Audit Baseline:** `141` active files (`2,361.8 KB`, excluding `__pycache__` / `.pytest_cache`) · `194` verification tests (`clean_runner.py --pass`) + `39` `Testing_System` tests

---

## 1. Problem Diagnosis: Why Directory Division *and* File Splitting Are Both Required

### 1.1. Misleading Folder Name
- `group03-smartschedule-baseline/` was named during the Week 1 V0 academic baseline, even though the codebase is now **`v1.0-alpha`** featuring a Chat-First UI + Online Context-Parsing Router, Developer Mode Thinking Stage, 6 optimization solvers (`EDF`, `WSPT`, `LST`, `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`), SQLite workspace/auth persistence, `.ics` import, and `Testing_System v2.1`.
- Both contributors and AI coding agents repeatedly mistake `group03-smartschedule-baseline/` for a frozen baseline folder and lose tokens scanning top-level files to locate the active app.

### 1.2. Measured Repository Footprint & Token-Bloat Hotspots
Direct audit of `group03-smartschedule-baseline/` (`141 files`, `2,361.8 KB`):

| Directory / Component | Files | Disk Footprint | Operational Role | Context / Token Bloat Problem |
| :--- | :---: | :---: | :--- | :--- |
| `web/` *(incl. `assets/`)* | 23 | **~810 KB** *(incl. 314.1 KB WebP)* | FastAPI API routes + Chat/Calendar JS/CSS + 2 WebP images | Mixes backend Python services, static frontend ES modules, and 314 KB binary background images under one folder. |
| `src/` | 26 | **~502 KB** | Core solvers, models, controller, SQLite storage, SHA-256 tracer, plus `nl_parser.py` | Layer 4 `nl_parser.py` (`55.5 KB`) lives inside `src/`, while `ergonomic_engine.py` alone is `125.3 KB`. |
| `verification_tests/` | 49 | **~491 KB** *(225.0 KB YAML)* | 194 pytest cases + `NL_Parser_test_cases/` (10 YAML suites) + `clean_runner.py` | 49% of test folder bytes are 10 large YAML fixture files (`B2` 58.8 KB, `B1` 49.4 KB) pulled into grep/find scans. |
| `NL_Parser_Package/` | 7 | **202.5 KB** | 6-stage EN/VI hybrid parser (`hybrid_parser.py` 86.8 KB, `parser.py` 57.0 KB) | Separated from `src/nl_parser.py` at repo level yet coupled directly to it, bloating root searches. |
| `member_eval/` | 7 | **~153 KB** | Port `8010` standalone blind human evaluator (`viewer.html` 51 KB, `evaluate_schedule.py` 39 KB) | Independent secondary web tool bundled inside the main app directory. |
| `data/` | 16 | **~74 KB** *(incl. `local_state.db` 32 KB)* | Presets, T01–T10 JSONs, calibration grid, and runtime SQLite DB | Mixes immutable test/preset JSONs with mutable `local_state.db` runtime state. |
| Root files & `docker/` | 12 | **~129 KB** | `README.md` (**55.1 KB**), `benchmark_*.py` (`30 KB`), `.bat`, `docker/` | Huge single `README.md` (55.1 KB) + standalone benchmark scripts sit in the application root. |

### 1.3. Second Hidden Token Hog: Oversized Monolithic Source Files (`> 50 KB`)
Moving folders alone is **not enough** if agents still have to read `1,200–3,000+` lines for a tiny change. The current top monolithic source files are:

| Monolithic File | Size (KB) | Lines | Why It Wastes Agent Tokens |
| :--- | :---: | :---: | :--- |
| `src/solvers/ergonomic_engine.py` | **125.3 KB** | **3,072** | Combines circadian grid indexing, adaptive splitting, objective scoring, and Kempe eject/repair in 1 file. |
| `NL_Parser_Package/hybrid_parser.py` | **86.8 KB** | **1,834** | Combines rule tables, translation hooks, chunking heuristics, and adapter compilation. |
| `web/chat_service.py` | **72.5 KB** | **1,565** | Mixes Gemini online model routing, clause/regex title condenser, edge-case detection, Thinking Stage, and turn handlers. |
| `web/app.js` | **61.6 KB** | **1,614** | Combines bootstrap, chat orchestration, drag/drop/check-in, benchmark/weights, and P3.3 Focus Timer. |
| `src/solvers/base_solver.py` | **55.9 KB** | **1,232** | Combines core hard-constraint validator, block placement helpers, and legacy utilities. |
| `src/nl_parser.py` | **55.5 KB** | **1,231** | Combines `GeminiNLParser`, `OfflineNLParser`, and `NLParserController` in one Layer 4 file inside `src/`. |
| `web/css/app.css` | **52.2 KB** | **2,082** | Single monolithic stylesheet for shell, calendar grid, chat bubbles, dev panel, and showcase tables. |
| `src/solvers/local_repair.py` | **51.5 KB** | **1,150** | Disruption insertion + repair heuristics in one large file. |
| `web/v3_services.py` + `web/api.py` | **91.6 KB** | **1,965** | Large FastAPI endpoint handlers mixed with suite catalog/benchmark aggregation helpers. |

Additionally, outside `group03-smartschedule-baseline/`:
- `agents/commit_changes.md` (**75.0 KB, 436 lines**) and `docs/commit_changes.md` (**75.7 KB, 427 lines**) hold Entries `001–023` in one rolling file.
- `v1.0-alpha-plan/Testing_Plan/` holds multi-megabyte research PDFs (`> 24 MB` total).

---

## 2. Target Clean Directory Architecture (`v1.0-alpha`)

Divide the repository into **6 sharply bounded top-level domains**, separating core scheduling math, NLP/AI parsing, FastAPI delivery, static UI, tests, and auxiliary tooling:

```text
Computational-Thinking---Group-Project/
├── smartschedule/                 # PRODUCTION APPLICATION ONLY (installable via pyproject.toml)
│   ├── core/                      # Layer 1–3: Pure scheduling domain (zero web/fastapi/NLP/UI imports)
│   │   ├── solvers/               # registry.py, base_solver.py, ergonomic_engine.py, hybrid_alns.py, edf/lst/wspt/scored/backtrack/local_repair
│   │   ├── config.py              # Constants + centralized paths (DATA_DIR, UI_DIR, REPO_ROOT)
│   │   ├── models.py              # Pydantic Task, CommitmentsProfile, ScheduleBlock, ScheduleOutput
│   │   ├── controller.py          # ScheduleController + compute_schedule_insights
│   │   ├── grid_manager.py        # 672-slot availability & sleep/fixed lock grid
│   │   ├── task_tracer.py         # Pure stdlib SHA-256 task keyword fingerprinting & hidden criteria extraction
│   │   ├── estimate_buffer.py     # Habit & cognitive-load fallacy buffers
│   │   ├── calibration.py         # M7 completion log EWMA alpha calibration
│   │   ├── overload_triage.py     # O1-O4 deadlock relief options
│   │   ├── metrics.py             # Schedule quality & experience metrics
│   │   ├── storage.py             # Stdlib SQLite workspace, completion log & auth persistence
│   │   ├── ics_importer.py        # .ics calendar feed parser
│   │   ├── exporter.py            # .ics / .csv / .json schedule exporter
│   │   └── utils.py               # Slot arithmetic & circadian curves
│   │
│   ├── nlp/                       # Layer 4 NL & Online Context Subsystem (decoupled from core solvers & web routes)
│   │   ├── parser_controller.py   # Former src/nl_parser.py (GeminiNLParser + OfflineNLParser + NLParserController)
│   │   ├── context_router.py      # Extracted from web/chat_service.py: Online Gemini Flash-Lite router + ChatContextExtractionSchema
│   │   ├── clause_condenser.py    # Extracted from web/chat_service.py: Cross-day windows, flexible duration, Vietnamese title condenser
│   │   └── hybrid_pipeline/       # Former NL_Parser_Package/ (7 modules)
│   │
│   ├── api/                       # Layer 4 FastAPI server & service layer
│   │   ├── app.py                 # Former web/api.py (route registration)
│   │   ├── auth.py                # Tenant & API auth middleware
│   │   ├── chat/                  # Split conversational turns (`handlers.py`, `thinking_stage.py`, `edge_cases.py`)
│   │   ├── health_v21.py          # Testing_System v2.1 bridge
│   │   ├── v3_services.py         # Suite catalog & benchmark-all orchestrator
│   │   └── test_showcase.py       # 7-case solver comparison showcase
│   │
│   ├── ui/                        # Pure static frontend assets (zero Python files)
│   │   ├── index.html
│   │   ├── app.js                 # Coordinator (~500 lines after extracting timer & dev telemetry modules)
│   │   ├── js/                    # api.js, state.js, utils.js, chat-assistant.js, render-*.js, modals.js, input-drawer.js, focus-timer.js, dev-telemetry.js
│   │   ├── css/                   # tokens.css, shell.css, chat.css, calendar.css, dev-panel.css
│   │   └── assets/                # theme-botanical.webp, theme-dark-forest.webp (excluded in .agentignore)
│   │
│   └── main.py                    # CLI & Uvicorn server entrypoint
│
├── data/                          # Strictly partitioned fixtures vs. mutable runtime DB
│   ├── presets/                   # sample_week_*.json, lan_week_*.json
│   ├── scenarios/                 # t01..t10 JSON scenarios
│   ├── calibration/               # alpha_grid_calibration.json
│   └── runtime/                   # local_state.db (gitignored via .gitignore & .agentignore)
│
├── tests/                         # Former verification_tests/ (completely outside smartschedule/)
│   ├── conftest.py                # Sets SMARTSCHEDULE_DB_PATH, TESTING_SYSTEM paths cleanly
│   ├── clean_runner.py            # Verification orchestrator (--pass, --all, --ui, --gaps)
│   ├── test_studio.py             # Tk GUI runner (optional desktop tool)
│   ├── ui/                        # Former ui_tests/
│   ├── architecture/              # Former architecture_tests/ (INV-1..INV-6 + memory leak gates)
│   ├── logical/                   # Former logical_tests/
│   ├── benchmark/                 # Former benchmark_tests/
│   ├── gaps/                      # Former development_gap_tests/
│   └── fixtures/
│       └── nl_cases/              # Former NL_Parser_test_cases/ (225 KB YAML suites, ignored during normal code search)
│
├── tools/                         # Auxiliary benchmarks, blind human eval, infra & launchers
│   ├── member_eval/               # Standalone Port 8010 Blind Human Evaluator
│   ├── benchmarks/                # benchmark_runner.py, benchmark_alpha_grid.py
│   ├── docker/                    # Dockerfile, docker-compose.yml
│   └── scripts/                   # setup_env.bat, run_app.bat, run_member_eval.bat
│
├── v1.0-alpha-plan/               # Plans, specs & v2.1 evaluation engine
│   ├── Testing_System/            # 4-pillar evaluator & Fuzz v2 generator (`39/39` tests)
│   ├── Testing_Plan/              # Evaluation specs + `papers/` subfolder for 24 MB PDFs
│   ├── UI_Rebuild_Plan/           # Consolidated Chat-First UI/UX plans (agent_pipeline.md, proposal_pipeline.md)
│   └── folder_division_plan.md    # This document
│
├── agents/                        # AI agent specs & rolling changelog
│   ├── archive/                   # Historical Entries 001–015 moved out of hot context
│   ├── progress/                  # Architecture & milestone specs
│   ├── commit_changes.md          # Rolling log (Entries 016+ only, < 18 KB)
│   └── requirements.md
│
├── docs/                          # Team Vietnamese documentation (mirrors agents/archive/ split)
├── .agentignore                   # Skips PDFs, WebP images, runtime SQLite DBs, YAML fixtures & archives
├── CODEBASE_INDEX.md              # < 4 KB single-page map ("To edit X -> read file Y")
├── pyproject.toml                 # Editable package root (`pip install -e .`) eliminating sys.path hacks
├── README.md                      # Concise root overview (moved out of nested app folder)
├── requirements.txt               # Core runtime deps
└── requirements-nllb.txt          # Optional offline neural translation deps
```

---

## 3. File-Level Modularization Plan (Fixing the `50 KB+` God Files)

Even after separating top-level folders, splitting the largest files guarantees every file an agent opens fits comfortably within **150–450 lines (`5–18 KB`)**:

| Oversized Target | Current Size | Clean Sub-Modules After Split | Priority |
| :--- | :---: | :--- | :---: |
| **`web/chat_service.py`** | `72.5 KB` (`1,565L`) | `nlp/context_router.py` (`Gemini` schema + model fallback) + `nlp/clause_condenser.py` (cross-day + duration + title condenser) + `api/chat/thinking_stage.py` + `api/chat/edge_cases.py` + `api/chat/handlers.py` | **High (Do in Migration)** |
| **`web/css/app.css`** | `52.2 KB` (`2,082L`) | `ui/css/shell.css` + `ui/css/calendar.css` + `ui/css/chat.css` + `ui/css/dev-panel.css` (linked directly or `@import`) | **High (Do in Migration)** |
| **`web/app.js`** | `61.6 KB` (`1,614L`) | Extract `ui/js/focus-timer.js` (~210L) & `ui/js/dev-telemetry.js` (~260L) + keep slim coordinator `ui/app.js` (~700L) | **Medium (Safe ES module split)** |
| **`agents/commit_changes.md` & `docs/`** | `~75 KB` each | Archive Entries `001–015` into `agents/archive/` & `docs/archive/`, keep only latest 8–10 entries active (`< 18 KB`) | **High (Immediate token win)** |
| **`src/solvers/ergonomic_engine.py`** | `125.3 KB` (`3,072L`) | **Optional Future Pass:** Split into `ergonomic_grid.py`, `ergonomic_scoring.py`, `ergonomic_splitting.py`, **only** behind a dedicated PR gated by `3x` `determinism_hash` equality (`test_ergonomic_solvers_v3.py`). Do **NOT** touch during folder move. | **Defer (Protect `INV-2`)** |

---

## 4. `.agentignore` + `CODEBASE_INDEX.md` Optimization

Adding a root `.agentignore` and a compact `< 4 KB` `CODEBASE_INDEX.md` prevents AI assistants from wasting search/index tokens on non-code artifacts:

```gitignore
# .agentignore — Exclude bulky static, historical & generated files from AI scans
**/*.pdf
**/*.webp
**/*.png
**/*.jpg
**/*.db
**/*.db-journal
**/__pycache__/
**/.pytest_cache/
tests/fixtures/nl_cases/*.yaml
v1.0-alpha-plan/Testing_Plan/papers/
agents/archive/
docs/archive/
```

`CODEBASE_INDEX.md` provides a 25-row lookup table (*"Need Chat UI -> edit `smartschedule/ui/js/chat-assistant.js`; Need Context Model -> edit `smartschedule/nlp/context_router.py`"*) so agents locate exact files in 1 turn instead of running exploratory `grep`/`find` loops.

---

## 5. Token-Efficiency & Context Savings Breakdown

| Engineering Task | Current Footprint (`group03-smartschedule-baseline/`) | Target Footprint (`smartschedule/` + `.agentignore` + splits) | Expected Reduction |
| :--- | :--- | :--- | :---: |
| **Chat UI & Context Model Work** | Scans `141` mixed files (`2,361.8 KB`) + reads `chat_service.py` (`72.5 KB`) & `app.css` (`52.2 KB`) | Reads only `ui/js/chat-assistant.js` + `ui/css/chat.css` + `nlp/context_router.py` (~35 KB total) | **~80% fewer tokens** |
| **Frontend Calendar & Styles** | Scans `web/` (`810 KB` incl. WebPs & API Python files) + reads `app.js` (`61.6 KB`) | Isolated `smartschedule/ui/` (zero Python files, zero WebP index hits) | **~70% smaller surface** |
| **Core Solver / Buffer Maintenance** | `src/` sits alongside `tests/` (49 files), `NL_Parser_Package/`, `nl_parser.py`, `member_eval/` | Isolated `smartschedule/core/` (`< 450 KB`, strictly Layer 1–3) | **~82% fewer search hits** |
| **NLP & YAML Suite Work** | `NL_Parser_test_cases/` (`225 KB` YAML) triggers false matches in code searches | YAML suites isolated in `tests/fixtures/nl_cases/` + ignored by `.agentignore` | **Zero YAML noise in code grep** |
| **Agent Onboarding (`commit_changes.md`)** | Reads `75 KB` monolithic file (Entries `001–023`) | Reads `< 18 KB` rolling log (last 8 entries) | **~76% fewer onboarding tokens** |

---

## 6. Hardcoded Path Inventory & Architectural Boundary Preservation (`INV-1` to `INV-6`)

### 6.1. Hardcoded `"group03-smartschedule-baseline"` References Discovered in Audit
The migration PR must update every reference found across the repository:
1. `group03-smartschedule-baseline/docker/Dockerfile` (`6` occurrences) & `docker/docker-compose.yml` (`6` occurrences)
2. `v1.0-alpha-plan/Testing_System/sut_adapter.py` (`3` occurrences)
3. `group03-smartschedule-baseline/verification_tests/conftest.py` (`1` occurrence)
4. `group03-smartschedule-baseline/NL_Parser_Package/__init__.py` (`1` occurrence) & `hybrid_parser.py` (`1` occurrence)
5. `agents/commit_changes.md`, `agents/requirements.md`, `docs/commit_changes.md`, `docs/requirements.md`

### 6.2. Strict Layer Invariants (`INV-1` to `INV-6`)
Moving folders **must not** relax any invariant verified by `tests/architecture/`:
1. **`smartschedule/core/` (`INV-1`, `INV-2`):** Zero imports from `smartschedule.api`, `smartschedule.nlp`, `fastapi`, `starlette`, or `Testing_System`.
2. **`smartschedule/nlp/`:** Pure NLP/context extraction; zero imports from `smartschedule.api` or `smartschedule.core.solvers` (`nlp -> core.models` / `core.task_tracer` only).
3. **`smartschedule/api/`:** One-way dependency `api -> core`, `api -> nlp`, and optional `api -> Testing_System`.
4. **`tools/member_eval/`:** Zero reverse imports from `smartschedule/` into `tools/member_eval/`.
5. **Centralized Config & Data Separation:** Resolve `REPO_ROOT`, `DATA_DIR`, `UI_DIR`, and `DB_PATH` once in `smartschedule/core/config.py` (with `SMARTSCHEDULE_DATA_DIR` / `SMARTSCHEDULE_DB_PATH` overrides); default SQLite to `data/runtime/local_state.db`.

---

## 7. Phased Safe Migration Checklist (Next Dedicated Refactoring PR)

Execute cleanly in small, verifiable commits on a dedicated migration branch:

1. **Commit 1 — Packaging Shell & Central Path Resolver:**
   - Add root `pyproject.toml`, `.agentignore`, and `CODEBASE_INDEX.md`.
   - Centralize `REPO_ROOT`, `DATA_DIR`, `UI_DIR`, and `DB_PATH` inside `src/config.py` so zero files rely on brittle `parents[N]` offsets.
2. **Commit 2 — Mechanical `git mv` Directory Division (Preserves Full Git History):**
   - `group03-smartschedule-baseline/src` $\to$ `smartschedule/core` (and relocate `nl_parser.py` $\to$ `smartschedule/nlp/parser_controller.py`)
   - `group03-smartschedule-baseline/NL_Parser_Package` $\to$ `smartschedule/nlp/hybrid_pipeline`
   - `group03-smartschedule-baseline/web` $\to$ Python backend files into `smartschedule/api/`, static assets into `smartschedule/ui/`
   - `group03-smartschedule-baseline/data` $\to$ partitioned under `data/{presets,scenarios,calibration,runtime}/`
   - `group03-smartschedule-baseline/verification_tests` $\to$ `tests/` (`NL_Parser_test_cases/` $\to$ `tests/fixtures/nl_cases/`)
   - `group03-smartschedule-baseline/{member_eval,docker,benchmark_*.py,*.bat}` $\to$ `tools/`
   - `v1.0-alpha-plan/Testing_Plan/*.pdf` $\to$ `v1.0-alpha-plan/Testing_Plan/papers/`
   - Move `README.md`, `requirements*.txt`, `.env.example` to repo root; keep `.env` & `data/runtime/*.db` untracked.
3. **Commit 3 — Import Rewrites & Tooling Config Update:**
   - Rewrite `from src.*` $\to$ `from smartschedule.core.*`, `from web.*` $\to$ `from smartschedule.api.*`, `from NL_Parser_Package.*` $\to$ `from smartschedule.nlp.hybrid_pipeline.*`.
   - Update `tools/docker/Dockerfile`, `tools/docker/docker-compose.yml`, `tools/scripts/*.bat`, `tests/conftest.py`, `v1.0-alpha-plan/Testing_System/sut_adapter.py`, and AST architecture tests (`test_system_architecture.py`).
4. **Commit 4 — Split High-Bloat Layer 4 Files & Archive Old Changelogs:**
   - Split `chat_service.py` (`72.5 KB`), `css/app.css` (`52.2 KB`), and extract `focus-timer.js` / `dev-telemetry.js` from `app.js` (`61.6 KB`).
   - Archive Entries `001–015` from `agents/commit_changes.md` and `docs/commit_changes.md` into `agents/archive/` and `docs/archive/`.
   - Remove the empty `group03-smartschedule-baseline/` directory once `git status` shows zero leftover tracked files.
5. **Mandatory Verification Gate Before Merging Migration:**
   - `python -B tests/clean_runner.py --pass` (**194/194+ tests**, including AST boundary & memory leak gates `< 350 KB`)
   - `python -B -m pytest v1.0-alpha-plan/Testing_System/tests -q` (**39/39 passed**)
   - `node --check smartschedule/ui/app.js` and all `smartschedule/ui/js/*.js`
   - Smoke-boot both entrypoints: `uvicorn smartschedule.api.app:app` (`http://127.0.0.1:8000`) and `python tools/member_eval/evaluate_schedule.py --mode serve --port 8010`.
