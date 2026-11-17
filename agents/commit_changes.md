# SmartSchedule — AI Agent Synchronization Hub & Change Log

**Project:** SmartSchedule — Personal Productivity Assistant  
**Course:** CS252 — Computational Thinking (2026) · FIT-HCMUS  
**Team:** Group 03 — *The Seven Dwarfs*  
**Document:** `agents/commit_changes.md`  
**Target Audience:** ALL AI Coding Assistants (Antigravity, Cursor, GitHub Copilot, Claude, ChatGPT, etc.) assisting any member of Group 03  

---

> [!IMPORTANT]
> ## 🚨 MANDATORY PROTOCOL FOR ALL AI AGENTS
> Every AI agent assisting any team member in this repository **MUST** adhere to the following rules:
> 1. **Read Before Coding:** Read `agents/commit_changes.md` and the documents in `agents/progress/` before generating or modifying code to understand the current architecture, data contracts, and layer boundaries.
> 2. **Never Break Architectural Invariants:** Do not violate `INV-1` to `INV-6` (e.g. never import `web` or `fastapi` inside `src/solvers/` or `src/models.py`).
> 3. **Run Pre-Deployment Tests:** Always run `python verification_tests/clean_runner.py --pass` before concluding any coding task.
> 4. **Mandatory Documentation Sync:**
>    Whenever you complete a task, feature, bug fix, or test addition, **AND the human owner/member approves the changes**, you **MUST IMMEDIATELY UPDATE BOTH:**
>    - `agents/commit_changes.md` (this file, in English)
>    - `docs/commit_changes.md` (the companion file, in Vietnamese)
>    Log the author, role, summary of changes, affected files, tests run, and the downstream impact on other teammates.
> 5. **Simultaneous Dependency Updates:**
>    Whenever you add, modify, or remove any external dependency in `group03-smartschedule-baseline/requirements.txt`, you **MUST SIMULTANEOUSLY UPDATE BOTH:**
>    - `agents/requirements.md` (English dependency catalog)
>    - `docs/requirements.md` (Vietnamese dependency catalog)
>    Clearly stating which architectural layer it belongs to and why it is necessary.

---

## 1. Project Context & Current Operational Status

SmartSchedule is an automated weekly task and timetable scheduling assistant for university students.
The project is currently at the transition point between the **Baseline Engine (V0)** and the **Improve Plan (V1/V2)**:

- **Baseline Engine (V0):** Fully functional. Classical CSP solver operating on a 672-slot discrete grid (15 minutes/slot, 7 days/week). Implements greedy Earliest Deadline First (EDF), Least Slack Time (LST), and Weighted Shortest Processing Time (WSPT) algorithms, adhering to hard constraints $H_1$ to $H_5$.
- **Web Workbench:** Operational at `http://127.0.0.1:8000`. Delivers interactive 672-slot timetable visualization, manual block drag-and-drop validation, and export to `.ics`, `.csv`, and `.json`.
- **Improve Plan & Presentation2 Synchronization (V1/V2):** Implemented across `src/` and `web/`: `ScoredGreedySolver` (`SCORED_GREEDY`, `E1–E4` energy/context/procrastination/fragmentation weights), dual Estimate Buffer (`HABIT` + `COGNITIVE_LOAD` with `α_light=1.20`, `α_heavy=1.35`), 8 Human Behavioral Patterns, Two-Tier Crunch & `Early Extension Alert (24–48h)`, Experience Rating (`1–5`), `OverloadTriageEngine` (`/api/overload/preview`), M1 Multilingual EN/VI Natural Language Parser (`src/nl_parser.py`), M7 completion tracking (`/api/tasks/complete`), and `benchmark_alpha_grid.py` (1D grid `α ∈ [1.00, 1.60]` + `+25%/+50%` overrun stress test).
- **Verification Infrastructure:** Upgraded to **149 passing operational tests** (`--pass`, 100% pass) + **5/5 passing Improve Plan feature tests** (`--gaps`, 100% pass) + **1 resolved Sprint-Mode compression & triage test** (`test_fail_edge_sprint_mode_compression_recovery`, resolved via `Q9` Option A) = **155/155 passing automated `pytest` tests** (`--all` & `pytest -q`), plus **200/200 passing Hybrid NL Parser YAML cases** (`verify_hybrid_200.py`, `100.0%`), **16 fresh EN/VI prompts regression tests**, **T09 Controlled Ablation (`EDF` Energy-Blind vs `SCORED_GREEDY`)**, Milestone 2 & UI Redesign regression suite (`8/8` in `test_milestone2_production_readiness.py`), and verified **Live Gemini API (`AI_GEMINI`)**.

---

## 2. Chronological Log of System Changes

### Entry 014 — 2026-11-17 | Horizontal Timeline Scrubber & Month Range Calendar Popover (`M1-NL-Parser`)
- **Authors:** ltbinh + Antigravity Agent
- **Branch:** `M1-NL-Parser`
- **Summary:** Added a horizontal scrollable calendar track with an interactive range slider scrubber, live viewport day-chain indicator (`#stObservedDaysStrip`), continuous 14-day rendering (`#stExtraWeek2Columns`), and a clickable Month Range Calendar popover (`#observedRangeCalendarPopover`) highlighting the exact observed chain of days across both Student and Lab modes.
- **Key Changes:**
  - **Horizontal Calendar Track & Range Slider (`web/index.html`, `web/app.js`):** Styled `.calendar-h-scroll` scrollbar; converted Student `#stViewWeek` to horizontal `#stCalendarScrollContainer` (`min-width` columns `265–280px`) with two-way synchronized `#stCalendarHorizontalSlider`, pan controls (`panCalendarByDays()`, `scrollToTodayColumn()`), continuous Days `7..13` (`_ensureWeek2DayColumns()`) when `horizon_days == 14`, and live viewport detection (`updateObservedViewportRange()`, `#stObservedRangeLabel`, `#stObservedDaysStrip`); added matching horizontal slider `#labGridHorizontalSlider` and `#labObservedRangePill` to Lab `#singleGridPanel`.
  - **Month Range Calendar Popover (`web/index.html`, `web/app.js`):** Turned header `#topWeekRangePill` and `📆 Lịch` (`#btnToggleObservedCalendar`) plus `#btnStOpenMonthCal` into interactive triggers for `#observedRangeCalendarPopover` (`toggleObservedRangeCalendar()`, `renderObservedRangeCalendar()`, `shiftMiniCalendarMonth()`, `onMiniCalendarDateClick()`), visually highlighting currently viewed dates (solid indigo pill), remaining planning horizon dates (soft indigo), and today's date ring, with direct scroll-to-day or week switching.
  - **UI Contract Tests (`verification_tests/logical_tests/test_milestone2_production_readiness.py`):** Extended `test_redesigned_temporal_student_and_lab_ui_contracts` to verify `#stCalendarScrollContainer`, `#stCalendarHorizontalSlider`, `#observedRangeCalendarPopover`, `#labGridHorizontalSlider`, and their JS handlers.
- **Verification:** `node --check web/app.js`, bidirectional HTML ID / JS handler check, and `clean_runner.py --all` / `pytest -q` (`155/155`).

---

### Entry 013 — 2026-11-17 | Temporal Axis (`DD/MM/YYYY`), Student UI Cleanup & Lab Research Workbench Redesign (`M1-NL-Parser`)
- **Authors:** ltbinh + Antigravity Agent
- **Branch:** `M1-NL-Parser`
- **Summary:** Rebuilt the Student & Lab UI (`web/index.html`, `web/app.js`) and enriched comparative/block telemetry (`src/controller.py`, `web/api.py`) so every calendar view shows concrete `DD/MM/YYYY` dates with clear Past/Active/Future separation, removes duplicated Student buttons/Lab task forms, surfaces `PersonalHabit` management directly in the Tasks & Habits tab, and upgrades Lab Mode into a 3-tab research workbench (Single Analysis, A/B Algorithm Comparison Studio with Verdict + Delta Scorecard + Placement Diff Table, and T04/T05 Resilience & 3x Determinism Proof Ledger).
- **Key Changes:**
  - **Backend Telemetry & Winner Synthesis (`src/controller.py`, `web/api.py`):** Added `ScheduleController.compute_schedule_insights(profile, out)` returning per-block `energy_level`, `peak_match_rate_pct`, `deep_peak_match_pct`, `avg_energy_level`, `context_switches`, and `batched_pairs` (exposed via `_enrich_response()` on `/api/plan`, `/api/compare`, `/api/repair`, `/api/progress`); enriched `ScheduleController.compare_algorithms()` with `block_diffs`, weighted `verdict_winner`, and `verdict_highlights`, and set `/api/compare` default `algo_right` to `SCORED_GREEDY`.
  - **Concrete Dates (`DD/MM/YYYY`) & Live `PAST / ACTIVE / FUTURE` Axis (`web/index.html`, `web/app.js`):** Added unified header week/date navigation (`#inpWeekStartDate`, `#topWeekRangePill`, `#btnStWeekPrev/Next`, `#stHorizonDaysSelect`, `#btnStJumpRealtime`), `#temporalContextBanner` with `rebaseScheduleToCurrentWeek()`, first-visit `loadPresetIntoCurrentWeek("minh")` aligned to the real week while keeping `/api/presets` fixtures deterministic, concrete `DD/MM/YYYY` headers across Student Week (`#stDayDate_0..6`, `#stDayTemporal_0..6`), Today pills/timeline (`#stTodayActiveDateTitle`), Task Queue (`resolveDeadlineDisplay()` countdowns/overdue pills), Lab Grid (`#labGridHeader_0..6`), and live `─── 🔴 BÂY GIỜ (HH:MM) ───` / `▶ ĐANG DIỄN RA` markers.
  - **Student UI Cleanup & Direct `PersonalHabit` Workspace (`web/index.html`, `web/app.js`):** Consolidated top header actions into single primary `➕ Thêm Việc`, `⚙️ Cài Đặt`, and `⋯ Dữ Liệu & Tiện Ích` dropdown (`#studentToolsMenu`); added direct `🏃 Thói Quen Tuần (PersonalHabit)` sub-tab (`#stSubHabitsPane`, `#stMainHabitsList`, `addStudentHabitFromMainTab()`) bidirectionally synced with `#stSettingsModal`; added inline Today Hero M7 Check-in (`stHeroActualMin` -> `submitBlockCheckIn()`).
  - **Analytical 3-Tab Lab Research Workbench (`web/index.html`, `web/app.js`):** Replaced duplicate 12-field `#inpTask*` form with 3-col Control Rail (Active Solver, unified experimental params, modal trigger + 1-line `#quickAddInput`, collapsible Sleep/Fixed events) and 9-col 3-Tab Analytical Stage: Tab 1 (6 KPI cards incl. `#kpiPeakMatch` & `#kpiExperienceVal`/`#kpiContextSwitches`, Grid + pinned `#labFixedInspectorPanel`, Energy/Reason Placed Blocks table); Tab 2 (A/B Comparison Studio defaulting `EDF` vs `SCORED_GREEDY` + 3 quick pair presets, `#compareVerdictBanner`, 9-row `#compareMetricsBox`, `#compareDiffTableBody` filter, collapsible `#compareFullGridsDetails`); Tab 3 (`#labPanelResilience` with `T04`/`T05` visual comparison bars and 5-solver `#determinismLedgerBody`).
  - **Expanded Automated Verification (`verification_tests/logical_tests/test_milestone2_production_readiness.py`):** Added `test_plan_and_compare_scientific_insights_and_block_diffs` (verifying `/api/plan` energy telemetry and `/api/compare` `EDF` vs `SCORED_GREEDY` improvements on Minh & `T01`) and `test_redesigned_temporal_student_and_lab_ui_contracts`.
- **Verification:** `clean_runner.py --pass` (`149/149`), `--gaps` (`5/5`), `--all` (`155/155`, 17.77s), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `620.6 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, Table 5 `T09` Ablation intact), `node --check web/app.js` (`exit 0`), bidirectional HTML ID / JS handler check (zero broken handlers). Live Chrome browser interactive check not executed in-turn.

---

### Entry 012 — 2026-11-17 | Milestone 2 Production Readiness (`Gói A.0`, `Gói A.1–A.3`, `Gói B`) (`M1-NL-Parser`)
- **Authors:** ltbinh + Antigravity Agent
- **Branch:** `M1-NL-Parser`
- **Summary:** Implemented the complete Milestone 2 Production Readiness suite on `M1-NL-Parser` (`153/153` passing tests): Progressive Disclosure for `#stTaskModal` (`STUDENT` vs `LAB` mode without breaking UI contracts), SQLite workspace + M7 completion persistence across reloads (`GET/PUT/DELETE /api/state`, `GET /api/tasks/completions`), real-time Monday/clock navigation & `horizon_days=7..14` multi-week scheduling (`1344` slots), full Student Task Edit + `PersonalHabit` UI (`Q7.3 = A3`), `start_after`/`work_rhythm`/`preferred_window` solver wiring, offline regex clock-token hardening, Student UI `COGNITIVE_LOAD` default, `.venv`-aware `.bat` runners, and optional `requirements-nllb.txt` split.
- **Key Changes:**
  - **Progressive Disclosure Modal UI (`web/index.html`, `web/app.js`):** Added `.app-mode-student .st-lab-only-modal` CSS hiding rules and `syncTaskModalModeVisibility()` so `STUDENT` Mode renders a minimalist chat bar (`#stNlPrompt` + compact `📎` attach trigger + `Phân tích`), 4 core fields (Title, Duration, Deadline Day/Time, Priority P1–P4 + Category), and collapsed `<details id="stTaskAdvDetails">` while `LAB` Mode auto-opens every technical panel and preserves 100% of contracted DOM IDs/handlers.
  - **SQLite + `localStorage` Workspace & M7 Persistence (`src/storage.py`, `web/api.py`, `web/app.js`, `.gitignore`):** Added pure standard-library SQLite module `src/storage.py` (`SMARTSCHEDULE_DB_PATH` env override, default gitignored `data/local_state.db`); added `GET /api/state`, `PUT /api/state`, `DELETE /api/state`, `GET /api/tasks/completions`, and persisted `POST /api/tasks/complete` records; updated `DOMContentLoaded` to restore saved workspace state via `restorePersistedWorkspace()` before falling back to `loadPreset("minh")` on first visit.
  - **Real-Time Clock & Multi-Week `horizon_days` (`src/models.py`, `src/solvers/*.py`, `src/controller.py`, `web/index.html`, `web/app.js`):** Added `horizon_days: int = Field(default=7, ge=7, le=14)` to `CommitmentsProfile`; updated `BaseScheduler.resolve_horizon_slots()` and `grid_states` (`base_solver.py`, `greedy_lst.py`, `backtracking.py`, `local_repair.py`, `controller.py`) to expose up to 1344 slots cleanly; added `getCurrentMondayIso()`, `jumpToCurrentWeek()`, `shiftStudentCalendarWeek()`, `changeStudentHorizonDays()`, Week 1/Week 2 UI navigation, and Week 2 slot rendering across Student Cards/Today/Lab Grid.
  - **Student CRUD, `PersonalHabit` (`Q7.3 = A3`), Solver Constraints & Regex Fixes (`src/models.py`, `src/controller.py`, `src/solvers/base_solver.py`, `src/solvers/backtracking.py`, `src/nl_parser.py`, `web/index.html`, `web/app.js`):** Added `✏️ Sửa` + `editStudentTask(tid)` reusing `#stTaskModal`; built `#stSettingsModal` `PersonalHabit` UI (`addStudentPersonalHabit()`, `removeStudentPersonalHabit()`) and upgraded `ScheduleController.expand_personal_habits()` to distribute weekly occurrences across days `[now_day..6]` honoring `preferred_window` (`MORNING`/`AFTERNOON`/`EVENING`) in `score_candidate_slot()`; added `Task.start_after` + `resolve_start_after_slot()` + `Task.work_rhythm` (`LIGHT`/`BALANCED`/`FLOW`) enforced in `place_task_with_constraints()` and `BacktrackingSolver`; unhardcoded `"offline"` in Lab `analyzeQuickAddHybrid()`; updated `OfflineNLParser.extract_duration_min()` to strip clock intervals (`14h00 - 16h00`) and 24h clock times (`19h30`) so `"Làm lab mạng 19h30 khoảng 90p"` extracts `90` instead of `1170` while preserving `"1h30 trước 18:30"`.
  - **Gói B Technical Cleanup & Tests (`web/app.js`, `requirements.txt`, `requirements-nllb.txt`, `run_app.bat`, `setup_env.bat`, `verification_tests/run_*.bat`, `agents/requirements.md`, `docs/requirements.md`, `verification_tests/logical_tests/test_milestone2_production_readiness.py`):** Defaulted Student UI/Settings & `"empty"` preset to `"COGNITIVE_LOAD"` (`1.20/1.35`, preserving Pydantic `"HABIT"` V0 fallback); moved `ctranslate2`, `sentencepiece`, `huggingface-hub` to `requirements-nllb.txt`; updated `.bat` runners to prefer `.venv\Scripts\python.exe`; added 6 Milestone 2 verification tests.
- **Verification:** `clean_runner.py --pass` (`147/147`), `--gaps` (`5/5`), `--all` (`153/153`), `pytest -q` (`153 passed`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `659.8 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, Table 5 `EDF 4268107a006d` vs `SCORED_GREEDY f65266353eff -> ac905601e5bf`), `node --check web/app.js` (`exit 0`).

---

### Entry 011 — 2026-11-17 | `Q10` Phase 2 Controlled Ablation (`EDF` Energy-Blind & `FULL_REBUILD` Forwarding), `Q1–Q10` Ratification & User Modal UX Plan (`M1-NL-Parser`)
- **Authors:** ltbinh + Antigravity Agent
- **Branch:** `M1-NL-Parser`
- **Summary:** Completed `Q10` Phase 2 (pure Energy-Blind V0 `EDF`/`LST`/`WSPT` separation for `T09` Controlled Ablation, `--gaps` update to `SCORED_GREEDY`, shared solver registry for `_repair_full_rebuild()` / `/api/repair`), ratified all remaining open decisions **`Q1–Q10`** (`☑`) in `Proposal/`, recorded the user's successful manual UI verification on `http://127.0.0.1:8000`, and documented the Progressive Disclosure UX plan (`Gói A.0`) to simplify `#stTaskModal` in `STUDENT` Mode vs `LAB` Mode.
- **Key Changes:**
  - **Shared Solver Registry (`src/solvers/registry.py`, `src/controller.py`):** Extracted `SOLVER_REGISTRY` and `resolve_solver()` into a clean leaf domain module reused by both `ScheduleController` and `LocalRepairEngine` without duplicating registry mappings or violating `INV-1`–`INV-6`.
  - **Energy-Blind V0 Greedy Solvers (`src/solvers/base_solver.py`, `src/solvers/backtracking.py`):** Switched `BaseScheduler.should_prefer_energy_placement()` to `False` so `EDF`/`LST`/`WSPT` operate as strictly Energy-Blind V0 baselines, converted `build_chunk_reasons()` to `@classmethod` gating `ENERGY_MATCH`/`ENERGY_FALLBACK`/`BATCHED_CATEGORY` on `cls.should_prefer_energy_placement()`, and preserved energy/batching optimization on `BacktrackingSolver` and `ScoredGreedySolver`.
  - **Active Algorithm Forwarding on Full Rebuild (`src/solvers/local_repair.py`, `src/controller.py`, `web/api.py`, `web/app.js`):** Added `algorithm` forwarding across `LocalRepairEngine.repair_disruption()`, `_repair_full_rebuild()`, `ScheduleController.compare_repair_modes()`, `POST /api/repair`, `runDisruptionRepair()`, and `runDisruptionComparison()`.
  - **Controlled Ablation Benchmarks & Tests (`benchmark_runner.py`, `test_improve_plan_gaps.py`, `test_sync_algorithm_fixes.py`):** Updated `test_fail_circadian_energy_matching` and `test_fail_why_popover_structured_reason_codes` to use `SCORED_GREEDY`; added Table 5 (`T09 Circadian Controlled Ablation`) in `benchmark_runner.py` and `test_q10_phase2_edf_energy_blind_ablation_and_full_rebuild_solver_forwarding` in `test_sync_algorithm_fixes.py`.
  - **Decision Ratification & UX Plan (`Proposal/`):** Marked all `Q1–Q10` checkboxes as `☑` per owner approval and added `Gói A.0` (`STUDENT` vs `LAB` Progressive Disclosure plan for `#stTaskModal`) in `Proposal/Production_Readiness_And_Decision_Analysis.md`, `Proposal/Open_Decisions_For_Team.md`, and `Proposal/Sync_Completion_Report.md`.
- **Verification:** `clean_runner.py --pass` (`141/141`), `--gaps` (`5/5`), `--all` (`147/147`), `pytest -q` (`147 passed`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `696.3 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, Table 5 `EDF 4268107a006d == 4268107a006d` vs `SCORED_GREEDY f65266353eff -> ac905601e5bf`), `node --check web/app.js` (`exit 0`), and owner manual UI walkthrough on `http://127.0.0.1:8000`.

---

### Entry 010 — 2026-11-17 | Milestone 1 Pre-Merge Hardening (`M1-NL-Parser`), `SCORED_GREEDY` Default (`Q10` Phase 1), Live Gemini Telemetry & `Proposal/` Consolidation
- **Authors:** ltbinh + Antigravity Agent
- **Branch:** `M1-NL-Parser`
- **Summary:** Executed Milestone 1 Pre-Merge PR #4 remediation items without breaking solver invariants (`INV-1`–`INV-6`): eliminated the `ui.attachments: list[str]` crash, cleaned `NL_Parser_Package/` imports to relative imports, added explicit `ai_status` telemetry and coarse time-of-day window preservation for Gemini outputs, switched the Web UI & `/api/plan` default solver to `SCORED_GREEDY` (`Q10` Phase 1), expanded regression coverage to **146 `clean_runner.py --all` tests** (including **16 fresh EN/VI student prompts**), verified **Live Gemini (`gemini-3-flash-preview`)** end-to-end, and consolidated `Proposal/` decisions (`Q6.2 = A2`, `Q7.3 = A3`, `Q1.3` composite formula).
- **Key Changes:**
  - **NL Package Clean Imports, Attachment Guard & Urgency Docs (`NL_Parser_Package/`, `verification_tests/`):** Replaced internal `sys.path` hacks and absolute imports across `__init__.py`, `hybrid_parser.py`, `parser.py`, `regex_parser.py`, `tokenizer.py`, `src/nl_parser.py`, `verify_hybrid_200.py`, and `test_hybrid_unbiased_generalization.py` with clean package/relative imports; added `_normalize_attachment_items()` so `ui.attachments` / `ui.linked_files` safely accept `str`, `dict`, or mixed lists; documented `{1: 5, 2: 4, 3: 3, 4: 1}` on `map_user_urgency_to_solver_priority()`.
  - **AI Telemetry & Coarse Time-of-Day Preservation (`src/nl_parser.py`):** Populated `validation["ai_status"]` (`ACTIVE`, `OFFLINE_REQUESTED`, `MISSING_GOOGLE_GENAI_PACKAGE`, `MISSING_API_KEY`, `FALLBACK_AFTER_ERROR`) plus visible `assumptions` warnings instead of silent offline fallback; extracted `OfflineNLParser.extract_coarse_window_time()` (`sáng->11:00`, `trưa->12:00`, `chiều->17:00`, `tối->21:30`) and wired it into `GeminiNLParser` prompt Rule 6 and `parse()` fallback when `deadline_time=None`.
  - **`Q10` Phase 1 Default Solver (`web/index.html`, `web/app.js`, `web/api.py`):** Switched `#solverSelect`, `#stSetSolver`, `#kpiSolverLabel`, `app.js` fallbacks (preserving `compareAlgoLeft` baseline comparison), and `POST /api/plan` default fallback to `SCORED_GREEDY`.
  - **Regression & Generalization Suite (`verification_tests/logical_tests/test_hybrid_nl_integration.py`):** Grew from 8 to 12 tests covering `list[str]` / mixed attachments, clean relative package imports, all `ai_status` paths, mocked Gemini coarse-window fallback (`chiều->17:00`), `/api/plan` default `SCORED_GREEDY`, and 16 fresh EN/VI prompts outside the 200 YAML corpus.
  - **Documentation & Decision Consolidation (`Proposal/`, `agents/`, `docs/`):** Merged `bao_response.md` Live Gemini findings into `Proposal/Production_Readiness_And_Decision_Analysis.md` (alongside settled `Q1.3`, `Q6.2 = A2`, `Q7.3 = A3`), removed duplicate `Proposal/bao_response.md`, updated `Proposal/Open_Decisions_For_Team.md` and `Proposal/Sync_Completion_Report.md`, marked `Proposal/Sync_Audit_And_Fix_Guide.md` as Archived, and updated both `commit_changes.md` logs.
- **Verification & Notes:** `clean_runner.py --pass` (`140/140`), `--gaps` (`5/5`), `--all` (`146/146`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `616.5 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, `T04` `100.00%` Stability), `node --check web/app.js` (`exit 0`), and Live Gemini FastAPI `TestClient` (`POST /api/tasks/natural-add` -> `POST /api/plan`, `200 OK`, `AI_GEMINI` -> `SCORED_GREEDY`). Automated `chrome_devtools` browser check was `BLOCKED` because Chrome remote debugging (`DevToolsActivePort`) was inactive; manual interactive Chrome/Edge check remains prior to merging PR #4.

---

### Entry 009 — 2026-11-16 | Hybrid EN/VI NL Parser Integration, Modal UI/UX Overhaul & `Q9` Option A Resolution (`ltbinh/sync-proposal`)
- **Authors:** Antigravity Agent + Team 03
- **Summary:** Integrated the personal `NL_Parser_Package` into `group03-smartschedule-baseline/NL_Parser_Package/` alongside M1 (`src/nl_parser.py`, `web/api.py`), overhauled the Student Task Modal (`web/index.html`, `web/app.js`) with cross-browser drag-and-drop `[[filename]]`/`@[path]` lossless citation verification, resolved open question `Q9` using **Option A** (Lossless Compression & Early Extension Alert), aligned `requirements.txt`, and expanded automated test coverage to **142 `pytest` tests + 200 YAML NL benchmark cases**.
- **Key Changes:**
  - **Hybrid 6-Stage EN/VI NL Parser (`NL_Parser_Package/`, `src/nl_parser.py`, `web/api.py`):** Relocated and stripped `NL_Parser_Package/` to the 7 core deployed modules (`__init__.py`, `hybrid_parser.py`, `parser.py`, `regex_parser.py`, `schema.py`, `tokenizer.py`, `translator.py`). Added `1=Urgent..4=Low -> 5..1` urgency mapping, `[[filename]]`/`@[path/file]` lossless citation extraction & validation (`E_INVALID_CITATION_FORMAT`), `ui.linked_files` comparison (fixing substring false positives), category-derived priority sync between `draft` and `hybrid`, and VI→EN translation backend selection (`rule`, `nllb`, `opus_mt`).
  - **Student Task Modal UI/UX & Cross-Browser Drag-and-Drop (`web/index.html`, `web/app.js`):** Widened `#stTaskModal` (`max-w-3xl lg:max-w-4xl`, `max-h-[90vh]`, scrollable body), added top-right `✕` + Esc/backdrop close, `localStorage` draft persistence (`#stModalDraftBadge`, `#btnStClearDraft`), unified chat-style `#stNlPromptBox` + `#stNlFileLinkBox` with red invalid-format/missing-citation error blocks, inline splittability toggle (`✂️ Cho phép cắt nhỏ` | `🔒 Làm liền 1 buổi`), editable `Task ID` (`#stInpTaskId`) + clickable `#stExistingTaskIdChips` for `"Task cần phải làm trước đó (Task ID)"`, and cross-browser drag-and-drop protection across Chrome, Edge, Firefox, and Safari (`window` + `document` handlers, `dt.items` fallback, `decodeURIComponent`).
  - **Sprint Mode `Q9` Option A & Unbiased Test Suites (`verification_tests/`):** Updated `test_fail_edge_sprint_mode_compression_recovery` to verify lossless `INFEASIBLE_CAPACITY` + `Early Extension Alert` + confirmed `SHORTEN_TASK` recovery and Tier-1 `Cut breaks` rescue (`crunch_tier_used == 1`). Added `verification_tests/NL_Parser_test_cases/` (200-case YAML suite + `validate_cases.py` + `verify_hybrid_200.py`), `test_hybrid_nl_integration.py` (8 tests), and `test_hybrid_unbiased_generalization.py` (9 tests).
  - **Dependency Alignment (`requirements.txt`, `agents/requirements.md`, `docs/requirements.md`):** Updated `requirements.txt` to include `PyYAML>=6.0`, `ctranslate2>=4.5.0`, `sentencepiece>=0.2.0`, and `huggingface-hub>=0.25.0`.

---

### Entry 008 — 2026-11-15 | Post-Sync Audit Fixes & Documentation Alignment (`ltbinh/sync-proposal`)
- **Author / Lead:** ltbinh (assisted by Antigravity AI)
- **Branch:** `ltbinh/sync-proposal`
- **Summary of Changes:**
  1. **Manual Move & Drag/Drop API Contract:** `ScheduleController.validate_manual_move` (`src/controller.py`) now returns `"proposed_block"` (`state="PINNED"`) on valid moves; `POST /api/validate-move` (`web/api.py`) accepts `blocks`, fallback `current_blocks`, or `schedule.blocks`; `handleGridDrop` (`web/app.js`) sends `algorithm`, `blocks`, and `current_blocks`.
  2. **Per-Task Buffer Opt-Out (`buffer_mode="NONE"`):** Added `"NONE"`/`"OFF"`/`"DISABLED"`/`"NO_BUFFER"` support across `Task` validator (`src/models.py`), `planned_duration_for_task_mode` (`src/estimate_buffer.py`), `apply_estimate_buffer` (`src/controller.py`), and `saveStudentTask` (`web/app.js`).
  3. **Overload Triage & Overrun Pin Guard:** `SHORTEN_TASK` (`src/overload_triage.py`) preserves contiguous chunks when `new_dur <= 90` while keeping `15m` chunk packing for `new_dur > 90` (`T06`); `preview_overload_resolution` (`src/controller.py`) expands `PersonalHabit` upfront on a clean `preview_profile`; `LocalRepairEngine.repair_overrun` (`src/solvers/local_repair.py`) locks `PINNED`/`DONE` blocks before overrun re-allocation and rolls back with `OVERRUN_OVERLOAD` if infeasible.
  4. **Disruption ID, CLI, Benchmark & Docs Sync:** `applyStudentDisruption` (`web/app.js`) reuses a single `DIS_xxxx` event ID before `/api/repair`; `main.py` adds `--solver SCORED_GREEDY`, `Experience Rating`, `Crunch Tier`, and `REST` slots in `672-Slot Breakdown`; `benchmark_runner.py` includes `SCORED_GREEDY` in Table 2 (5 solvers); updated `README.md`, `group03-smartschedule-baseline/README.md`, `agents/requirements.md`, `docs/requirements.md`, `Proposal/Open_Decisions_For_Team.md` (`Q1–Q10`), and `Proposal/Sync_Completion_Report.md`.
- **Verification (run after final edit):** `clean_runner.py --pass` (`107/107 PASSED`), `clean_runner.py --gaps` (`5/5 PASSED`), `clean_runner.py --all` (`112 Passed | 1 Failed | Total: 113`), `pytest -v` (`112 passed, 1 failed`), `benchmark_runner.py` (5-solver Table 2, `T04` `100.00%` Stability), `main.py --preset minh --solver SCORED_GREEDY` & `EDF`.

### Entry 007 — 2026-11-15 | Full Proposal & Presentation2 Synchronization (`ltbinh/sync-proposal`)
- **Author / Lead:** ltbinh (assisted by Antigravity AI)
- **Branch:** `ltbinh/sync-proposal` (branched from `main` at `4c0a85a`, leaving `main` untouched)
- **Summary of Changes:**
  1. **Core Fixes (`A1–A12`) & Cleanup:** Removed stale `web/Log.md` and `t07` `"grep_weight"` typo; unified `now_day`/`now_slot` dynamic anchoring (zero hardcoded Wednesday defaults); added `PersonalHabit` (sleep `>= 6h` enforcement via Pattern 6, `0.25x` habit weight), dynamic `horizon_days`, deterministic tie-breaking, and two-pass progressive chunk relaxation in `src/solvers/local_repair.py` (`T04` stability `100.00%`, `C_hard=0`).
  2. **8 Human Behavioral Patterns & `ScoredGreedySolver`:** Implemented `src/solvers/scored_greedy.py` (`SCORED_GREEDY`) combining Energy Matching ($E_1$), Context Batching ($E_2$), Hyperbolic Urgency ($E_3$), and Dead-Zone Avoidance ($E_4$); added `buffer_mode` (`HABIT` + `COGNITIVE_LOAD` $\alpha_{\text{light}}=1.20$, $\alpha_{\text{heavy}}=1.35$), Active Rest (`>=15m` gap), Dead-Zone `<30m` `REST` classification, Two-Tier Crunch (`Tier 1` extend active window / cut breaks; `Tier 2` sacrifice flexible habits), `Early Extension Alert (24–48h)`, and deterministic `Experience Rating (1–5)`.
  3. **Overload Triage & M1/M7 Pipelines:** Selective integration of `src/overload_triage.py` (`OverloadTriageEngine`, wired to `/api/overload/preview`), multilingual EN/VI parser `src/nl_parser.py` (`/api/tasks/natural-add`), and completion tracking `/api/tasks/complete`.
  4. **Student & Lab UI Sync (`web/index.html`, `web/app.js`):** Removed hardcoded week dates, `23:30–06:30` static sleep banners, and client-side `* 1.2` double buffering; added dynamic settings (`focus_preference`, `buffer_mode`, `alpha_light`, `alpha_heavy`; Web UI solver default currently remains `GREEDY_EDF_FIRST_FIT` pending `Q10`), M1 quick-add, Overload preview/apply/undo, M5 Local Repair trigger, M7 completion check-in, Experience Rating & Early Alert banners, `.slot-rest` styling, and `POST /api/validate-move` drag/drop wiring.
  5. **Calibration & Reporting:** Added `benchmark_alpha_grid.py` (`--save-json` -> `data/alpha_grid_calibration.json`); authored `Proposal/Open_Decisions_For_Team.md` (`Q1–Q10`) and `Proposal/Sync_Completion_Report.md`.
- **Verification (initial sync baseline, superseded by Entry 008):** `clean_runner.py --pass`, `clean_runner.py --gaps`, `benchmark_runner.py`, `benchmark_alpha_grid.py`.

### Entry 006 — 2026-11-06 | Student-Facing Minimalist UI & Dual-Mode Architecture
- **Author / Lead:** Duc Minh (assisted by Antigravity AI — Gemini 3.8 Flash)
- **Approved by:** Duc Minh (Developer & User Experience Lead)
- **Summary of Changes:**
  1. **Dual-Mode Architecture (Toggle Switch):**
     - Replaced the technical-only header with a global mode switch pill: `[🎓 Chế Độ Sinh Viên (Gọn)]` $\longleftrightarrow$ `[🔬 Chế Độ Lab (Benchmark)]`.
     - Defaults to **Student Mode** on page load for immediate clean student usability, while keeping the full technical benchmark workbench one click away in **Lab Mode**.
  2. **Three Student-Centric Calendar Views:**
     - **View 1: Weekly Smart Calendar (`#stViewWeek`):** Folds 28 nocturnal sleep rows into a single slim bar (`🌙 23:30 – 06:30 (Ngủ) · Bảo vệ`), and aggregates slots into high-contrast modern card blocks (Fixed Classes, Meals, Study Sessions).
     - **View 2: Today Focus ("Now & Next" — `#stViewToday`):** Prominent hero focus banner detecting the immediate next study block, accompanied by a chronological daily timeline with instant completion checkboxes.
     - **View 3: Task Queue Manager (`#stViewTasks`):** Clean table displaying status, safety buffer badges (`🛡️ +20%`), deadlines, and quick deletion.
  3. **Frictionless 3-Field Task Input Modal:**
     - Captures title, estimated duration (with quick-select chips: 30p, 45p, 60p, 90p, 120p), and deadline dropdown.
     - Live Planning Fallacy buffer toggle ($\times 1.2$) displaying real-time buffered duration previews ($T_{\text{buffered}} = \lceil \frac{\lceil T_{\text{raw}} \times 1.2 \rceil}{15} \rceil \times 15$).
     - Advanced options (priorities 1–5, splittability, prerequisites) organized in an accordion drawer.
  4. **Interactive Block Controls:**
     - **Block Pinning (📌):** `togglePinBlock` adds block to `state.pinnedBlocks` and passes `pinned_blocks` to `/api/plan`. The solver pre-locks these slots before unpinned placement, guaranteeing pinned study blocks never move.
     - **Task Check-in (✔️):** `toggleDoneBlock` marks completed tasks with 60% opacity and strikethrough.
     - **Algorithmic Explainability ("Why here? 💡"):** Modal explaining feasibility, energy alignment, and prerequisite clearance.
  5. **Shared State & Zero-Interference Contract:** Both modes share `state.commitments`, `state.tasks`, `state.pinnedBlocks`, and `state.currentSchedule` with zero backend solver mutation.
- **Affected Files:**
  - `group03-smartschedule-baseline/web/index.html` (Modified: layout, modals, dual-mode containers)
  - `group03-smartschedule-baseline/web/app.js` (Modified: view switches, renderers, pinning, buffer preview)
  - `agents/progress/student_mode_ui.md` (Created)
- **Impact on Project & Teammates:**
  - Provides a polished, non-technical interface for demoing and daily testing.
  - Zero disruption to backend solvers or benchmark suites (T01–T10).

### Entry 005 — 2026-11-06 | Feature 001: Estimate Buffer (Planning-Fallacy Correction)
- **Author / Lead:** Nguyễn Trọng Tiến (Thinker 3 — Abstraction & Algorithmic Design), assisted by Claude Code
- **Approved by:** Nguyễn Trọng Tiến (member). Branch `feature/estimate-buffer`, not merged yet; needs team review.
- **Summary of Changes:**
  1. **Spec-driven docs:** `specs/001-estimate-buffer/` (spec, clarifications C1–C5, plan, tasks, Mermaid diagrams).
  2. **New pure module `src/estimate_buffer.py`:** `estimate_habit` → multiplier (`RARELY` ×1.00, `SOMETIMES` ×1.10, `OFTEN` ×1.25). Planned duration = `max(round_up_to_15(T), nearest_15(T × m))`, computed in integers, so it stays deterministic. Rounding to the *nearest* slot means small tasks are not doubled (15 min × 1.25 → 15, not 30).
  3. **Models:** `CommitmentsProfile.estimate_habit` (validated, default `None` = V0 behaviour). `Task.buffer_multiplier` (1.0–2.0). `Task.get_planned_duration_min()` now calls the buffer rule.
  4. **Controller:** `apply_estimate_buffer()` returns buffered *copies* (INV-3, idempotent). `solve_schedule()` applies it and adds the reason code `ESTIMATE_BUFFER` to blocks that grew. `handle_task_overrun()` adds the overrun to the raw estimate and returns `new_estimate_min`. The repair comparison receives buffered tasks.
  5. **API:** reads `estimate_habit` from `commitments`, the Improve Plan `profile` or the top level. Buffer applied in `_extract_profile_and_tasks`, so all endpoints agree. `/api/progress` returns `new_estimate_min`.
  6. **Workbench:** habit selector + "planned X min" preview in the task form, "estimate → planned" in the task queue and the placed-blocks table. The overrun log stores the raw estimate (no compounding buffer).
  7. **Gap test input fix:** `test_fail_planning_fallacy_buffer_multiplier` now passes `estimate_habit="OFTEN"` (its docstring precondition). The test name is unchanged; Builder 3 may move it out of `development_gap_tests/`.
- **Affected Files:**
  - `group03-smartschedule-baseline/src/estimate_buffer.py` (Created)
  - `group03-smartschedule-baseline/src/models.py`, `src/controller.py` (Modified)
  - `group03-smartschedule-baseline/web/api.py`, `web/app.js`, `web/index.html` (Modified)
  - `group03-smartschedule-baseline/verification_tests/logical_tests/test_estimate_buffer.py` (Created, 34 tests)
  - `group03-smartschedule-baseline/verification_tests/development_gap_tests/test_improve_plan_gaps.py` (Modified: input of 1 test)
  - `specs/001-estimate-buffer/*` (Created)
  - **Not touched:** `src/solvers/*`, the quick-add / natural-language parser, `requirements.txt`.
- **Tests Executed:**
  - `python -B verification_tests/clean_runner.py --pass` → **84 Passed | 0 Failed** (50 existing + 34 new).
  - `python -B verification_tests/clean_runner.py --gaps` → 1 Passed (buffer) | 4 Failed (circadian, rest break, reason codes, SKIP_HABIT: still open).
- **Impact on Project & Teammates:**
  - With no `estimate_habit`, every result (T01–T10, presets, hashes) is identical to V0.
  - Solver owners: no merge conflict. Solvers only see larger `get_planned_duration_min()` values. Overload numbers now use buffered minutes.
  - UI owners: the student-facing TaskSheet (F06) can show `reasons[code=ESTIMATE_BUFFER].planned_min` directly.
  - Known limit (out of scope): tasks under 15 min still take a full slot (grid D2). Bundling several micro-tasks into one slot needs a solver change.

### Entry 004 — 2026-11-04 | Environment & Dependency Specifications (`requirements.md`)
- **Author / Lead:** Nguyễn Nguyễn Gia Bảo (Builder 3 — System Architecture & Testing)
- **Approved by:** Owner / Team Lead
- **Summary of Changes:**
  1. **Dependency Documentation Catalog (`requirements.md`):**
     - Authored [`agents/requirements.md`](requirements.md) (English) and [`docs/requirements.md`](../docs/requirements.md) (Vietnamese) breaking down all 6 dependencies from `requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `python-dateutil`).
     - Explicitly mapped each dependency to its permitted architectural layer (e.g. `fastapi` and `uvicorn` strictly in Layer 4, forbidden in Layer 2 solvers and Layer 1 models).
     - Documented Python standard library zero-install utilities (`ast`, `tracemalloc`, `threading`, `tkinter`, `hashlib`).
  2. **Automated Setup Script (`setup_env.bat`):**
     - Created `group03-smartschedule-baseline/setup_env.bat` for 1-click Python virtual environment (`.venv`) creation, activation, and automated `requirements.txt` installation on Windows.
  3. **Mandatory Simultaneous Update Protocol:**
     - Enforced protocol requiring all AI agents and teammates to update both `agents/requirements.md` and `docs/requirements.md` simultaneously whenever any dependency is added or modified.
- **Affected Files:**
  - `agents/requirements.md` (Created)
  - `docs/requirements.md` (Created)
  - `group03-smartschedule-baseline/setup_env.bat` (Created)
  - `agents/commit_changes.md` (Updated)
  - `docs/commit_changes.md` (Updated)
- **Impact on Project & Teammates:**
  - Teammates understand the exact purpose of every installed package and have a 1-click installer.
  - Future AI agents have explicit layer boundaries for third-party libraries.

### Entry 003 — 2026-11-04 | Interpretable Diagnostic Console & Documentation Hub
- **Author / Lead:** Nguyễn Nguyễn Gia Bảo (Builder 3 — System Architecture & Testing)
- **Approved by:** Owner / Team Lead
- **Summary of Changes:**
  1. **Interpretable Console Runner (`clean_runner.py`):**
     - Developed a custom pytest hook plugin (`InterpretableConsolePlugin`) that suppresses raw terminal noise (`-p no:terminal`, suppressing Starlette deprecation warnings and internal tracebacks).
     - Standardized console logs into 3 clear components:
       - **Running Signal:** Active target, timestamp, and runner status.
       - **Running Phase:** Sequenced execution headers for each of the 5 architectural layers.
       - **Files: PASSED or FAILED:** Directly points to the exact root cause (`Point to: ...`) and evaluated comparison (`Details: Discrepancy: ...`) upon failure.
  2. **Test Studio GUI & Batch Integration:**
     - Updated `verification_tests/test_studio.py` to route all test actions (`Run Selected`, `Run Production`, `Track Gaps`, `Run All Matrix`) through `clean_runner.py` with `-B` flag.
     - Streamlined `verification_tests/run_verification_tests.bat` to delegate directly to `clean_runner.py %*`.
  3. **Documentation Hub Creation (`agents/` & `docs/`):**
     - Created `agents/` knowledge base with deep architectural, baseline, improvement, and test documentation.
     - Created `docs/` companion knowledge base in Vietnamese for human teammates.
     - Established the mandatory AI Agent update protocol.
- **Affected Files:**
  - `group03-smartschedule-baseline/verification_tests/clean_runner.py` (Created)
  - `group03-smartschedule-baseline/verification_tests/test_studio.py` (Modified)
  - `group03-smartschedule-baseline/verification_tests/run_verification_tests.bat` (Modified)
  - `group03-smartschedule-baseline/verification_tests/run_test_studio.bat` (Modified)
  - `Progress/04_11_26_Builder 3.md` (Modified)
  - `agents/commit_changes.md`, `agents/progress/*` (Created)
  - `docs/commit_changes.md`, `docs/progress/*` (Created)
- **Tests Executed:**
  - `python verification_tests/clean_runner.py --pass`: 50 passed in 3.42s (100% green).
  - `python verification_tests/clean_runner.py --gaps`: 5 expected gap failures clearly diagnosed with direct pointers.
  - `python verification_tests/clean_runner.py --all`: 56 tests executed cleanly.
- **Impact on Project & Teammates:**
  - Teammates now see clean, instant diagnostic feedback without confusing terminal tracebacks.
  - Future AI agents working with other teammates have clear boundaries and explicit instructions on how to update project documentation.

---

### Entry 002 — 2026-11-04 | 60/40 Verification Matrix & Pre-deployment Infrastructure
- **Author / Lead:** Nguyễn Nguyễn Gia Bảo (Builder 3 — System Architecture & Testing)
- **Approved by:** Owner / Team Lead
- **Summary of Changes:**
  1. Consolidated all tests into `group03-smartschedule-baseline/verification_tests/`.
  2. Implemented the **60% Average Cases / 40% Edge Cases & Developmental Failures** matrix across 5 layers:
     - `ui_tests/`: Contract tests for ISO-8601 schema (§7.3) and endpoint delivery.
     - `architecture_tests/`: AST layer audits, memory leak detection (`tracemalloc`), and multi-thread concurrency.
     - `logical_tests/`: Circular dependency traps, undefined behaviors, solver fuzzing, and scheduling edge cases.
     - `benchmark_tests/`: Discrete grid math, hard constraint invariants ($H_1$–$H_5$), determinism, and feasibility proofs.
     - `development_gap_tests/`: 5 intentional target failure tests defining V1/V2 milestones.
  3. Built `test_studio.py` minimal native GUI window for visual test management.
  4. Added `setup_env.bat` for 1-click Python virtual environment and dependency installation.
- **Affected Files:**
  - `group03-smartschedule-baseline/verification_tests/*` (56 test files, GUI, batch runners)
  - `group03-smartschedule-baseline/setup_env.bat`
- **Impact on Project & Teammates:**
  - Establishes automated regression verification before production deployment.
  - Provides a visible developmental target backlog for teammates working on upcoming sprints.

---

### Entry 001 — 2026-10-29 | Initial Baseline Engine (V0) & Course Benchmarks
- **Author / Lead:** Group 03 Core Team
- **Summary of Changes:**
  1. Formulated the 672-slot discrete time representation on a 7-day grid.
  2. Implemented baseline Pydantic data schemas (`src/models.py`).
  3. Implemented EDF, LST, and WSPT greedy heuristic solvers (`src/solvers/`).
  4. Developed FastAPI delivery API and technical web workbench (`web/`).
  5. Implemented standard course benchmark scenarios T01–T10.
- **Affected Files:**
  - `group03-smartschedule-baseline/src/*`
  - `group03-smartschedule-baseline/web/*`
  - `group03-smartschedule-baseline/data/*`
  - `group03-smartschedule-baseline/main.py`, `benchmark_runner.py`
- **Impact on Project & Teammates:**
  - Provided the functioning, runnable V0 baseline engine for the group project.

---

## 3. How Changes Impact Specific Group Roles

| Role / Builder | Scope | How Current Changes Impact Their Work |
| :--- | :--- | :--- |
| **Builder 1** | Data Models & User Profile | Can add new fields (e.g. `energy_level`, `chronotype`) to `src/models.py`. Architecture test `test_models_layer_is_pure` ensures the model layer remains decoupled. |
| **Builder 2** | Solvers & Optimization | When implementing circadian matching, rest breaks, or buffer multipliers, can run `clean_runner.py --gaps` to observe developmental gap tests turning green one by one. |
| **Builder 3** | System Architecture & Testing | Maintains test gates, memory leak limits ($< 350\text{ KB}$), AST boundaries, and runner clean reporting. |
| **Builder 4** | UI/UX & Web Delivery | Can safely refactor frontend templates or API endpoints while running `clean_runner.py --ui` to guarantee JSON contract compliance (§7.3). |
| **Builder 5–7**| Scenarios, Analytics & Docs | Can run `clean_runner.py --bench` to benchmark algorithm efficiency against standardized course scenarios T01–T10. |

---

## 4. Instructions for Future AI Agents Updating This File

When you (the AI agent) finish implementing a change and the human user approves it:
1. Append a new numbered entry under Section 2 (`Entry 00X — YYYY-MM-DD | Title`).
2. Include:
   - **Author / Lead:** The team member name and role you are assisting.
   - **Approved by:** Owner / Member approval status.
   - **Summary of Changes:** Bulleted list of architectural and functional changes.
   - **Affected Files:** Specific paths of files created, modified, or removed.
   - **Tests Executed:** Exact command run and test results.
   - **Impact on Project & Teammates:** Downstream effects on solvers, models, API, or frontend.
3. Mirror the entry into `docs/commit_changes.md` in Vietnamese.

