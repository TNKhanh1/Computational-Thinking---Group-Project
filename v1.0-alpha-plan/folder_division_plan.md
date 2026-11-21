# Folder Division & Token-Optimization Plan (`group03-smartschedule-baseline` -> `v1.0-alpha` Modular Layout)

**Target Scope:** `group03-smartschedule-baseline/` & root workspace structure  
**Target Directory:** `v1.0-alpha-plan/`  
**Status:** Design Blueprint (pre-execution — no folders moved yet)

---

## 1. Problem Diagnosis: Why `group03-smartschedule-baseline` Must Be Divided & Renamed

### 1.1. Misleading Naming
- The name `group03-smartschedule-baseline` reflects the Week 1 V0 academic baseline, even though the repository has now evolved into **`v1.0-alpha`** featuring a Chat-First UI, 6 optimization solvers (`EDF`, `WSPT`, `LST`, `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`), SQLite workspace/auth persistence, `.ics` calendar import, M7 EWMA calibration, and live `Testing_System v2.1` telemetry.
- New contributors and AI coding agents consistently misidentify `group03-smartschedule-baseline/` as legacy/read-only baseline code rather than the active production application.

### 1.2. High Token Cost & Context Bloat for AI Agents
Measured footprint inside `group03-smartschedule-baseline/` (excluding `__pycache__` and `.pytest_cache`):

| Subdirectory / Root File | File Count | Disk Footprint | Operational Role | Token Impact Problem |
| :--- | :---: | :---: | :--- | :--- |
| `web/` | 23 | **810.0 KB** | FastAPI API + Frontend JS/CSS + WebP assets | Mixes backend API routes (`api.py`, `v3_services.py`, `chat_service.py`) with static UI assets |
| `src/` | 26 | **502.1 KB** | Core 672-slot solvers, models, storage, NL adapter | Co-located with test suites, benchmark scripts, and evaluation portals |
| `verification_tests/` | 49 | **490.7 KB** | 199 pytest cases + 200 YAML NL cases | Agents searching `group03-smartschedule-baseline/` repeatedly scan 49 test files + YAML fixtures |
| `NL_Parser_Package/` | 7 | **202.4 KB** | 6-stage EN/VI hybrid NL parser package | Large regex/rule tables pulled into root workspace grep results |
| `member_eval/` | 7 | **153.3 KB** | Port `8010` standalone blind human evaluator | Separate secondary app bundled inside the main app folder |
| `data/` | 16 | **74.2 KB** | JSON presets, T01–T10 scenarios, `local_state.db` | Mixes static fixture JSONs with mutable SQLite runtime state |
| Root scripts & docs (`README.md` 53.8 KB, `benchmark_*.py` 30.2 KB, `.bat`, `docker/`) | 12 | **100.7 KB** | Docs, benchmark runners, Docker, launchers | Single `README.md` (53.8 KB) + scripts clutter project root discovery |
| **Total inside `group03-smartschedule-baseline/`** | **140 files** | **~2,333 KB** | **7 distinct concerns in 1 directory** | **Every broad agent scan traverses ~140 mixed files** |

Additionally, outside `group03-smartschedule-baseline/`:
- `v1.0-alpha-plan/Testing_Plan/` holds multi-megabyte research PDFs (`1010803411-MIT.pdf` 20.6 MB, `34_Million_...pdf` 2.6 MB, `Plan_Stability_...pdf` 1.5 MB, `journal.pone.0272460.pdf`).
- `agents/commit_changes.md` and `docs/commit_changes.md` exceed ~70 KB each because Entries `001–021` live in one monolithic changelog file.

---

## 2. Target Clean Directory Architecture (`v1.0-alpha`)

Split the monolithic `group03-smartschedule-baseline/` into clear, single-responsibility top-level folders so humans and AI agents load **only the exact slice they need**:

```text
Computational-Thinking---Group-Project/
├── smartschedule/                 # Production application ONLY (cleanly separated layers)
│   ├── core/                      # Layer 1–3: Pure scheduling domain (models, solvers, controller, tracer, storage)
│   │   ├── solvers/               # base_solver.py, ergonomic_engine.py, hybrid_alns.py, edf/lst/wspt/scored/backtrack/repair
│   │   ├── models.py
│   │   ├── controller.py
│   │   ├── task_tracer.py
│   │   ├── calibration.py
│   │   ├── estimate_buffer.py
│   │   ├── overload_triage.py
│   │   ├── storage.py
│   │   ├── ics_importer.py
│   │   ├── exporter.py
│   │   └── utils.py
│   ├── nlp/                       # Layer 4 NL subsystem (isolated from core solvers & UI)
│   │   ├── nl_parser.py           # Dual-engine Gemini + Offline controller
│   │   └── hybrid_pipeline/       # Former NL_Parser_Package/ (7 modules)
│   ├── api/                       # Layer 4 FastAPI server & service adapters
│   │   ├── app.py                 # Former web/api.py
│   │   ├── auth.py
│   │   ├── chat_service.py
│   │   ├── health_v21.py
│   │   ├── v3_services.py
│   │   └── test_showcase.py
│   ├── ui/                        # Pure static frontend assets (HTML, CSS, ES modules, images)
│   │   ├── index.html
│   │   ├── app.js
│   │   ├── js/
│   │   ├── css/
│   │   └── assets/
│   ├── main.py                    # CLI & server entrypoint
│   └── pyproject.toml             # Editable package metadata (`pip install -e ./smartschedule`)
│
├── data/                          # Strictly partitioned data & runtime state
│   ├── presets/                   # sample_week_*.json, lan_week_*.json
│   ├── scenarios/                 # t01..t10 JSON scenarios
│   ├── calibration/               # alpha_grid_calibration.json
│   └── runtime/                   # local_state.db (gitignored)
│
├── tests/                         # Former verification_tests/ (completely outside production app/)
│   ├── conftest.py
│   ├── clean_runner.py
│   ├── test_studio.py
│   ├── ui/
│   ├── architecture/
│   ├── logical/
│   ├── benchmark/
│   ├── gaps/
│   └── nl_cases/                  # Former NL_Parser_test_cases/ (200 YAML cases)
│
├── tools/                         # Auxiliary benchmarks, blind human eval, infra & scripts
│   ├── member_eval/               # Standalone Port 8010 Blind Human Evaluator
│   ├── benchmarks/                # benchmark_runner.py, benchmark_alpha_grid.py
│   ├── docker/                    # Dockerfile, docker-compose.yml
│   └── scripts/                   # setup_env.bat, run_app.bat, run_member_eval.bat
│
├── v1.0-alpha-plan/               # Plans, specs & v2.1 evaluation harness (already organized)
│   ├── Testing_System/            # 4-pillar evaluator & Fuzz v2 generator
│   ├── Testing_Plan/              # Evaluation specs + `papers/` subfolder for reference PDFs
│   ├── UI_Rebuild_Plan/           # Chat-First UI/UX execution & proposal plans
│   └── folder_division_plan.md    # This document
│
├── agents/                        # AI agent specs (with archived old changelog entries)
│   ├── archive/                   # Historical Entries 001–015 moved out of hot context
│   ├── progress/
│   ├── commit_changes.md          # Active rolling log (last 5 entries only, < 15 KB)
│   └── requirements.md
│
├── docs/                          # Team Vietnamese documentation (mirrors agents/archive/ split)
├── .agentignore                   # Tells AI tools/searchers to skip PDFs, runtime DBs, and archives
├── requirements.txt               # Core runtime deps
└── requirements-nllb.txt          # Optional offline neural translation deps
```

---

## 3. Token-Efficiency & Context Savings Breakdown

| Engineering Task | Current Scan Footprint (`group03-smartschedule-baseline/`) | Target Scan Footprint (`smartschedule/` split) | Reduction |
| :--- | :--- | :--- | :---: |
| **Frontend UI / Chat Work** | Scans 140 files (`~2,333 KB` incl. tests, NL tables, data, eval) | Only `smartschedule/ui/` + `smartschedule/api/chat_service.py` (~30 files, binary assets excluded) | **~65% fewer files** |
| **Core Solver / Buffer Tuning** | Scans `src/` mixed with `web/`, `tests/`, `member_eval/`, `NL_Parser_Package/` | Only `smartschedule/core/` (25 small modules, `< 350 KB`) | **~85% smaller search space** |
| **NLP / Prompt Extraction** | Scans `NL_Parser_Package/` + 200 YAML cases in mixed tree | Isolated `smartschedule/nlp/` (8 files); YAML corpus in `tests/nl_cases/` | **~75% fewer grep hits** |
| **Agent Onboarding (`commit_changes.md`)** | Reads `~68 KB` monolithic file (Entries `001–021`) | Reads `< 15 KB` active log (last 5 entries); `001–015` archived | **~78% fewer onboarding tokens** |
| **Test Execution & Discovery** | Mixed inside application folder (`verification_tests/`) | Cleanly isolated in `tests/` + `v1.0-alpha-plan/Testing_System/` | **Zero test-noise in `smartschedule/`** |

---

## 4. Architectural Boundary Preservation (`INV-1` to `INV-6`)

Moving folders **must not** relax any architectural invariant:
1. **`smartschedule/core/` (`INV-1`, `INV-2`):** Zero imports from `smartschedule.api`, `fastapi`, `starlette`, `smartschedule.nlp`, or `Testing_System`.
2. **`smartschedule/api/`:** One-way dependency `api -> core`, `api -> nlp`, and optional `api -> Testing_System` (from `v1.0-alpha-plan/Testing_System`).
3. **`tools/member_eval/`:** Zero imports of `member_eval` inside `smartschedule/core/` or `v1.0-alpha-plan/Testing_System/`.
4. **Data & Runtime Separation:** All `.json` fixtures read via centralized `DATA_DIR` in `smartschedule/core/config.py` (configurable via `SMARTSCHEDULE_DATA_DIR`), and SQLite defaults to `data/runtime/local_state.db` (`SMARTSCHEDULE_DB_PATH`).

---

## 5. Safe Migration Execution Checklist (Next PR / Step)

Execute in small, verifiable commits on a dedicated branch after approving this plan:

1. **Step 1 — Package & Path Abstraction (Pre-Move):**
   - Introduce `smartschedule/core/paths.py` (resolving `REPO_ROOT`, `DATA_DIR`, `UI_DIR`, `TESTING_SYSTEM_DIR`) so zero modules hardcode `Path(__file__).resolve().parents[N]` or `"group03-smartschedule-baseline"`.
2. **Step 2 — Move via `git mv` (Preserves Full Git Blame History):**
   - `git mv group03-smartschedule-baseline/src smartschedule/core`
   - `git mv group03-smartschedule-baseline/NL_Parser_Package smartschedule/nlp/hybrid_pipeline`
   - `git mv smartschedule/core/nl_parser.py smartschedule/nlp/nl_parser.py`
   - `git mv group03-smartschedule-baseline/web/*` -> split Python modules into `smartschedule/api/` and static web assets (`index.html`, `app.js`, `js/`, `css/`, `assets/`) into `smartschedule/ui/`.
   - `git mv group03-smartschedule-baseline/data/* data/` (organized into `presets/`, `scenarios/`, `calibration/`).
   - `git mv group03-smartschedule-baseline/verification_tests tests`
   - `git mv group03-smartschedule-baseline/member_eval tools/member_eval`
   - `git mv group03-smartschedule-baseline/docker tools/docker`
   - `git mv group03-smartschedule-baseline/benchmark_*.py tools/benchmarks/`
   - `git mv group03-smartschedule-baseline/*.bat tools/scripts/`
   - Move `v1.0-alpha-plan/Testing_Plan/*.pdf` -> `v1.0-alpha-plan/Testing_Plan/papers/` and add `.agentignore`.
3. **Step 3 — Import & Config Rewrite:**
   - Replace `from src.*` with `from smartschedule.core.*`, `from web.*` with `from smartschedule.api.*`, and `from NL_Parser_Package.*` with `from smartschedule.nlp.hybrid_pipeline.*` (supported cleanly via root `pyproject.toml` editable install or `sitecustomize` / `conftest.py`).
   - Update `tools/docker/Dockerfile`, `tools/docker/docker-compose.yml`, `tools/scripts/*.bat`, and `v1.0-alpha-plan/Testing_System/sut_adapter.py`.
4. **Step 4 — Changelog Archival & Verification:**
   - Move Entries `001–015` to `agents/archive/commit_changes_v0_v3.md` and `docs/archive/commit_changes_v0_v3.md`.
   - Run full verification gates:
     - `python -B tests/clean_runner.py --all` (assert all tests pass, including AST boundary checks)
     - `python -B -m pytest v1.0-alpha-plan/Testing_System/tests -q` (`39/39` passed)
     - `node --check smartschedule/ui/app.js smartschedule/ui/js/*.js`
5. **Step 5 — Delete Empty Legacy Shell:**
   - Remove the empty `group03-smartschedule-baseline/` directory once all suites pass 100%.
