# SmartSchedule — AI Agent Synchronization Hub & Rolling Change Log

> [!IMPORTANT]
> **START AT [`agents/README.md`](README.md) FIRST!**
> Per `v1.0-alpha` rules, **AI agents only need to read [`agents/README.md`](README.md)** and then **[`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md)** for full onboarding, rules of thumb, modular directory paths (`smartschedule/`, `data/`, `tests/`, `tools/`), and checkable task lists.
> - Historical Entries `001–015` have been moved to [`agents/archive/commit_changes_v0_v3.md`](archive/commit_changes_v0_v3.md).
> - Updated dependency & layer rules live in [`agents/requirements.md`](requirements.md) (synced with root [`requirements.txt`](../requirements.txt)).

---

## 1. Current Operational Status (`v1.0-alpha/ui-ux-chat`)

- **Modular Repository Layout:** `group03-smartschedule-baseline/` has been cleanly divided into [`smartschedule/`](../smartschedule/) (`core/`, `nlp/`, `api/`, `ui/`), [`data/`](../data/) (`presets/`, `scenarios/`, `calibration/`, `runtime/`), [`tests/`](../tests/) (`ui/`, `architecture/`, `logical/`, `benchmark/`, `gaps/`, `fixtures/nl_cases/`), and [`tools/`](../tools/) (`member_eval/`, `benchmarks/`, `docker/`, `scripts/`), with [`pyproject.toml`](../pyproject.toml), [`.agentignore`](../.agentignore), and [`CODEBASE_INDEX.md`](../CODEBASE_INDEX.md) at repo root.
- **Chat-First UI/UX & Online Context Parsing:** Spacious `"Trợ lý xếp lịch"` entry (`#viewChat`), collapsible left sidebar, synchronized right calendar copilot (`#calendarCopilotDrawer`), Developer Mode `💭` Thinking Stage + hidden badges, SHA-256 keyword task tracing (`smartschedule/core/task_tracer.py`), and merged 3-layer context parsing (`clause_condenser.py` + `context_router.py` via `gemini-2.5-flash-lite` + offline safety net).
- **Scheduling Core & Evaluation (`V3`, 6 Solvers):** Stateless `ergonomic_engine.py` + 6 registered solvers (`EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`) + `Testing_System v2.1`.
- **Verification Status:** `tests/clean_runner.py --pass` (**`194/194 PASSED`**), `pytest v1.0-alpha-plan/Testing_System/tests -q` (**`39/39 passed`**), `tests/fixtures/nl_cases/verify_hybrid_200.py` (**`200/200 passed`**), and `node --check` (**`exit 0`**).

---

## 2. Recent Changelog Entries (`016–024`)

### Entry 024 — 2026-11-21 | Modular Folder Division (`smartschedule/`, `data/`, `tests/`, `tools/`, `environments/`, `Project_Drafts/`), File Splitting & `v1.0-alpha-plan` Documentation Hubs (`v1.0-alpha/ui-ux-chat`)
- **Authors:** User + Antigravity Agent
- **Branch:** `v1.0-alpha/ui-ux-chat` (Commits `e56ab06`, `5a96211`, plus `agents/`/`docs/`/`v1.0-alpha-plan/` sync)
- **Summary:** Executed `v1.0-alpha-plan/folder_division_plan.md` eliminating `group03-smartschedule-baseline/` (`e56ab06`), consolidated historical course proposals into `Project_Drafts/` (`5a96211`), moved all environment/packaging/index files into `environments/` (leaving only `.gitignore` and `README.md` at repo root), authored unified hubs (`v1.0-alpha-plan/README.md`, `v1.0-alpha-plan/README_agents.md`, `agents/README.md`, `docs/README.md`), removed stale/unusable progress items from `README` & `progress/`, updated `requirements.md`, and archived Entries `001–015`.
- **Key Changes:**
  - **Repository Modularization (`smartschedule/`, `data/`, `tests/`, `tools/`, `environments/`, `Project_Drafts/`):** Moved all source packages, static assets, partitioned `data/{presets,scenarios,calibration,runtime}`, categorized `tests/{ui,architecture,logical,benchmark,gaps,fixtures}`, tooling (`tools/{member_eval,benchmarks,docker,scripts}`), environment manifests into [`environments/`](../environments/) (keeping only `.gitignore` and `README.md` as loose root files), and historical drafts (`Baseline_Plan`, `Improve_Plan`, `Proposal`) into [`Project_Drafts/`](../Project_Drafts/) while preserving `.env` and `data/runtime/local_state.db`.
  - **Bloated Module Splitting:** Split `chat_service.py` (`72.5 KB`) into [`smartschedule/nlp/clause_condenser.py`](../smartschedule/nlp/clause_condenser.py), [`smartschedule/nlp/context_router.py`](../smartschedule/nlp/context_router.py), and [`smartschedule/api/chat/{thinking_stage,edge_cases,handlers}.py`](../smartschedule/api/chat/__init__.py); split `app.css` (`2082 lines`) into `shell.css`, `dev-panel.css`, `calendar.css`, and `chat.css`.
  - **Centralized Path Config & Imports:** Added repo-aware constants (`CORE_DIR`, `UI_DIR`, `NLP_DIR`, `TESTS_DIR`, `TOOLS_DIR`, `PRESETS_DIR`, `SCENARIOS_DIR`, `CALIBRATION_DIR`, `DEFAULT_DB_PATH`) in [`smartschedule/core/config.py`](../smartschedule/core/config.py) and rewired all `67+` source/test imports plus `[tool.pytest.ini_options] pythonpath` in `pyproject.toml`.
  - **Documentation & Onboarding Overhaul:** Authored [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md), [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md), [`agents/README.md`](README.md) (single AI entrypoint), and [`docs/README.md`](../docs/README.md); moved obsolete `baseline_plan`/`improved_plan`/`student_mode_ui` docs and Entries `001–015` to `archive/`; refreshed `progress/` docs & both `requirements.md` files.
- **Verification:** `node --check smartschedule/ui/app.js` & `smartschedule/ui/js/*.js` (`exit 0`), `python -B tests/clean_runner.py --pass` (**`194 Passed | 0 Failed`** in `57.35s`), `python -B -m pytest v1.0-alpha-plan/Testing_System/tests -q` (**`39 passed`** in `53.28s`), `python -B tests/fixtures/nl_cases/verify_hybrid_200.py` (**`200/200 (100.0%)`** in `789.0 ms`).

---

### Entry 023 — 2026-11-21 | Merged Online Context-Parsing Model, Clause-Level Title Condenser & Calendar Alignment Fixes (`v1.0-alpha/ui-ux-chat`)
- **Authors:** User + Antigravity Agent
- **Summary:** Merged the previous 2-layer clause/cross-day context parser with an efficient online lightweight context-parsing model (`gemini-2.5-flash-lite` / `gemini-2.5-flash` via `google-genai`, `0 MB` local RAM, `thinking_budget=0`) and an upgraded Clause-Level Vietnamese Title Condenser, fixed `"Hôm nay"` header/pill alignment in Calendar view, and hid `"💬 Mở trợ lý"` (`#btnExpandCopilotDrawer`) whenever `#calendarCopilotDrawer` is already open.

---

### Entry 022 — 2026-11-21 | Chat-First UI/UX Revision 2: Ultra-Minimal Navigation, Cross-Day Single-Task Context Parser & Developer Mode Thinking Stage (`v1.0-alpha/ui-ux-chat`)
- **Authors:** User + Antigravity Agent
- **Summary:** Made clicking `SS SmartSchedule` transition to `"Trợ lý xếp lịch"` (`#viewChat`), removed `"Nền năng lượng sinh học"` / `"Tiện ích nhanh"` from Settings and `"Chuyển nhanh tuần"` / `"Chỉnh nhanh việc đã lưu"`, hid left sidebar completely on collapse, made right copilot arrow `#btnToggleCopilotDrawer` collapse in-place, standardized response button to **`🗓️ Kiểm tra lịch trình`**, fixed cross-day window single-task parsing, and added Antigravity-style Developer Mode **Thinking Stage (`💭`)**.

---

### Entry 021 — 2026-11-21 | Chat-First UI/UX Overhaul, Left Vertical Taskbar Slider, SHA-256 Task Traceability & Synchronized Calendar Copilot (`v1.0-alpha/ui-ux-chat`)
- **Authors:** User + Antigravity Agent
- **Summary:** Launched Chat-First empty entry (`#viewChat`), collapsible left sidebar (`#leftNavSidebar`), synced right Calendar Copilot (`#calendarCopilotDrawer`), pure Layer 1 SHA-256 task keyword traceability (`task_tracer.py`), multi-turn clarification + remaining-time/habit calculation (`POST /api/chat/turn`), Deadlock / Dense-Schedule edge-case handling, and `193/193` passing baseline verification.

---

### Entry 020 — 2026-11-21 | Mainline `UI v3` Feature Integration (`d0489b3..1e5e494`), Docker Grouping & Repo Cleanup (`main`)
- **Authors:** nttien255, ltbinh + AI Agents
- **Summary:** Integrated `UI v3` evaluation contracts (`normalizeEvaluation()`), `Testing_System` Regime `R1–R6` & `FuzzGenerator v2` suite picker, 7-case Showcase (`GET /api/test-showcase`), view-only week navigation with `PAST_DUE` banners, and `Clear All Schedule` dialog onto `main` (`193/193` tests green).

---

### Entry 019 — 2026-11-21 | Restore UI v3 ES Module Wiring & API Endpoint Compatibility (`feat/v3-solvers-and-member-eval`)
- **Authors:** ltbinh + Antigravity Agent
- **Summary:** Fixed merge corruption across `app.js`, `index.html`, and API endpoints, restoring clean UI v3 ES modules, `HYBRID_ALNS`, live `Testing_System v2.1` panels, and `P3.3` Focus Timer / EWMA calibration controls (`186/186`).

---

### Entry 018 — 2026-11-20 | `P3` Commercial SaaS Foundations: Multi-Tenant Auth (`P3.1`), `.ics`/LMS Import (`P3.2`), Focus Timer & Notifications (`P3.3`), Docker + CI (`P3.4`) (`feat/v3-solvers-and-member-eval`)
- **Authors:** Lê Minh Nhật + Antigravity Agent
- **Summary:** Added PBKDF2/HS256 multi-tenant auth (`/api/auth/*`), pure stdlib RFC 5545 `.ics`/Moodle/Canvas importer (`/api/import/ics`), Pomodoro -> M7 Focus Timer + browser notifications, and Docker configuration (`178/178`).

---

### Entry 017 — 2026-11-20 | `P1.3` Docs Sync, `P2.1` Extreme Tight-Load Alpha Stress (`>= 1.70`) & `P2.2` M7 EWMA Calibration API (`feat/v3-solvers-and-member-eval`)
- **Authors:** Lê Minh Nhật + Antigravity Agent
- **Summary:** Proved the `alpha >= 1.70` Over-Buffering Cliff (`20.0%` false drop vs `0.0%` at `1.20/1.35`) and implemented pure Layer 1 M7 EWMA calibration (`calibration.py` + `GET /api/tasks/calibration`) (`171/171`).

---

### Entry 016 — 2026-11-20 | Member-in-the-Loop Blind Evaluator (`member_eval/`) & `P1` Web UI/API Upgrade (`HYBRID_ALNS` + Real-Time `v2.1` Health) (`feat/v3-solvers-and-member-eval`)
- **Authors:** Hoàng Minh Anh + Antigravity Agent
- **Summary:** Built standalone blind multi-solver evaluation portal (`tools/member_eval/` on `:8010`) and exposed `HYBRID_ALNS` + live `v2.1` 4-pillar & Vietnamese `ICEE` telemetry across `/api/plan`, `/api/compare`, and `/api/evaluate` (`167/167`).

---

*(Earlier Entries `001–015` from `2026-10-29` to `2026-11-20` are preserved in [`agents/archive/commit_changes_v0_v3.md`](archive/commit_changes_v0_v3.md).)*

---

## 3. Instructions for Updating Logs & Checklists

When finishing an approved change on `v1.0-alpha`:
1. Tick `[x]` on completed tasks in [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md) & [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md).
2. Prepend a concise new Entry here and mirror it in [`docs/commit_changes.md`](../docs/commit_changes.md) (Vietnamese).
3. Update [`agents/requirements.md`](requirements.md) and [`docs/requirements.md`](../docs/requirements.md) whenever [`requirements.txt`](../requirements.txt) changes.
