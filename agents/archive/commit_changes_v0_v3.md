# SmartSchedule — Archived Change Log (Entries 001–015: V0 Baseline through V3 Ergonomic Rebuild)

> [!NOTE]
> This archive preserves historical Entries `001` through `015` (`2026-10-29` to `2026-11-20`) moved out of [`agents/commit_changes.md`](../commit_changes.md) to keep the active rolling log concise. Paths recorded inside these historical entries reflect the legacy layout (`group03-smartschedule-baseline/src/`, `web/`, `verification_tests/`, `NL_Parser_Package/`) prior to the modularization into `smartschedule/`, `data/`, `tests/`, and `tools/`. For current workspace paths and `v1.0-alpha` directives, start at [`agents/README.md`](../README.md) and [`v1.0-alpha-plan/README_agents.md`](../../v1.0-alpha-plan/README_agents.md).

---

### Entry 015 — 2026-11-20 | V3 5-Solver Ergonomic Rebuild + 6th Algorithm `HYBRID_ALNS` (`testing-system/v2.1-fuzz-handoff`)
- **Authors:** ltbinh + Antigravity Agent
- **Branch:** `testing-system/v2.1-fuzz-handoff`
- **Summary:** Completed `Testing_Plan/ultimate_plan.md` and rebuilt the solver portfolio (`WSPT`, `LST`, `SCORED_GREEDY`, `BACKTRACK`) plus added a higher-end 6th algorithm (`HYBRID_ALNS`) powered by a shared stateless domain kernel `src/solvers/ergonomic_engine.py`, eliminating all `SUBOPT` failures across 220 scenarios and lifting `LOOSE HIGH_PRODUCTIVITY` from `0/24` to `22–23/24` (`91.7%–95.8%`) on Fuzz `1001..1050` and `25/25` (`100.0%`) on held-out Unseen Fuzz `5001..5050` while keeping `Testing_System/` 100% untouched and `EDF` untouched as the V0 baseline.
- **Key Changes:**
  - **Shared Stateless Ergonomic Kernel (`src/config.py`, `src/solvers/ergonomic_engine.py`):** Added ergonomic guardrail constants (`ERGONOMIC_DAILY_HEAVY_CAP=2`, `SOFT=36/HARD=40` slots, `L2_STREAK=8/12`, `HEAVY_MIN_GAP=2`, `CRAM_WINDOW=40`) and built `ErgonomicContext` with `O(1)` prefix sums (`pref_free`, `pref_low`, `pref_peak`, `pref_energy_sum`, `pref_tod_sin/cos`), DAG backward deadlines, incremental `ScheduleState` (`placed_l3_slots_count`, `cls_sin/cos`, `non_sin/cos`), exact Smarr & Schirmer circular SJL, exact 10-level bucketed `evaluate_state_lex_key` (with unpaired-SJL soft pairing tie-break preserving `<= 1 WARN`), `G1`-legal adaptive splitting (`min_chunk <= c_i <= max_chunk`), chronological First-Fit feasibility floor (`build_feasibility_first_fit_state`), Kempe `1/2-eject` rescue, overload bounded rescue (`deadline_ts` preventing `>1s` scans on 62-task 14-day overloads), overload priority knapsack swaps, culprit-first `polish_schedule_deterministic`, and deterministic ALNS (`5` Ruin + Regret-2 insertion). Preserved `INV-1..6` (zero web imports, stateless per-call `solve()`, exact `(ScheduleOutput, TimeGridManager)` return).
  - **5-Solver Rebuild + 6th Algorithm (`src/solvers/greedy_wspt.py`, `greedy_lst.py`, `scored_greedy.py`, `backtracking.py`, `hybrid_alns.py`, `registry.py`):** Kept `greedy_edf.py` untouched (`V0` anchor); upgraded `WSPT` & `LST` strictly Energy-Blind (`should_prefer_energy_placement -> False`, `energy_aware=False`, `Q10` `MORNING == EVENING` identical); upgraded `SCORED_GREEDY` as fast circadian portfolio default (`AvgRk 2.22` Regimes / `2.48` Unseen, `#1` on `Regime 3`, preserves `compute_task_score` & `ENERGY_MATCH` reasons); upgraded `BACKTRACK` to Live-State Ergonomic Branch-and-Bound (`23/24` Fuzz `LOOSE HIGH`, `max 680.8ms`); created & registered `HybridALNSSolver` (`HYBRID_ALNS` / `ALNS` / `ULTIMATE` — top `79/120` Regimes + `22/24` Fuzz + `25/25` Unseen `LOOSE HIGH`, `max 774.8ms`).
  - **Regression Tests & Documentation (`verification_tests/logical_tests/test_ergonomic_solvers_v3.py`, `Testing_Plan/ultimate_plan.md`, `Solver_Benchmark_Report.md`, `CT_Rationale_Log.md`):** Added 6 unit/regression tests covering 3x determinism, `Q10` Energy-Blind invariance, circadian `T09`/R3 separation, tight-deadline rescue, partial `PINNED` + `14-day` horizon, and `N=50 <= 1000ms`; updated benchmark report (all 5 sections) and CT log (`#14–#16`).
- **Verification:** `clean_runner.py --all` (`161/161`, `47.31s`), `benchmark_runner.py` (`T01–T10 C_hard=0`, `3x Determ PASS`, `T04 LOCAL_INSERTION 100.00%`, `T09` Ablation PASS), `pytest Testing_System/tests -v` (`39/39`, `40.25s`), and 220-scenario × 6-solver eval (`1,320` runs: `0 INVALID`, `0 SUBOPT`, `0` invariants failed, `0` paradoxes, `max <= 774.8ms`).

---

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
- **Verification:** `clean_runner.py --pass` (`149/149`), `--gaps` (`5/5`), `--all` (`155/155`, 17.77s), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `620.6 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, Table 5 `T09` Ablation intact), `node --check web/app.js` (`exit 0`), bidirectional HTML ID / JS handler check (zero broken handlers).

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
  - **Decision Ratification & UX Plan (`Proposal/`):** Marked all `Q1–Q10` checkboxes as `☑` per owner approval and added `Gói A.0` (`STUDENT` vs `LAB` Progressive Disclosure plan for `#stTaskModal`).
- **Verification:** `clean_runner.py --pass` (`141/141`), `--gaps` (`5/5`), `--all` (`147/147`), `pytest -q` (`147 passed`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `696.3 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, Table 5 `EDF 4268107a006d == 4268107a006d` vs `SCORED_GREEDY f65266353eff -> ac905601e5bf`), `node --check web/app.js` (`exit 0`), and owner manual UI walkthrough on `http://127.0.0.1:8000`.

---

### Entry 010 — 2026-11-17 | Milestone 1 Pre-Merge Hardening (`M1-NL-Parser`), `SCORED_GREEDY` Default (`Q10` Phase 1), Live Gemini Telemetry & `Proposal/` Consolidation
- **Authors:** ltbinh + Antigravity Agent
- **Branch:** `M1-NL-Parser`
- **Summary:** Executed Milestone 1 Pre-Merge PR #4 remediation items without breaking solver invariants (`INV-1`–`INV-6`): eliminated the `ui.attachments: list[str]` crash, cleaned `NL_Parser_Package/` imports to relative imports, added explicit `ai_status` telemetry and coarse time-of-day window preservation for Gemini outputs, switched the Web UI & `/api/plan` default solver to `SCORED_GREEDY` (`Q10` Phase 1), expanded regression coverage to **146 `clean_runner.py --all` tests** (including **16 fresh EN/VI student prompts**), verified **Live Gemini (`gemini-3-flash-preview`)** end-to-end, and consolidated `Proposal/` decisions (`Q6.2 = A2`, `Q7.3 = A3`, `Q1.3` composite formula).
- **Key Changes:**
  - **NL Package Clean Imports, Attachment Guard & Urgency Docs (`NL_Parser_Package/`, `verification_tests/`):** Replaced internal `sys.path` hacks and absolute imports with clean package/relative imports; added `_normalize_attachment_items()`; documented `{1: 5, 2: 4, 3: 3, 4: 1}` on `map_user_urgency_to_solver_priority()`.
  - **AI Telemetry & Coarse Time-of-Day Preservation (`src/nl_parser.py`):** Populated `validation["ai_status"]` plus visible `assumptions` warnings; extracted `OfflineNLParser.extract_coarse_window_time()` and wired it into `GeminiNLParser`.
  - **`Q10` Phase 1 Default Solver (`web/index.html`, `web/app.js`, `web/api.py`):** Switched defaults to `SCORED_GREEDY`.
  - **Regression & Generalization Suite (`verification_tests/logical_tests/test_hybrid_nl_integration.py`):** Grew from 8 to 12 tests covering attachments, clean relative imports, all `ai_status` paths, mocked Gemini fallback, `/api/plan` default `SCORED_GREEDY`, and 16 fresh EN/VI prompts.
- **Verification:** `clean_runner.py --pass` (`140/140`), `--gaps` (`5/5`), `--all` (`146/146`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `616.5 ms`), `benchmark_runner.py`, `node --check web/app.js` (`exit 0`), and Live Gemini FastAPI `TestClient`.

---

### Entry 009 — 2026-11-16 | Hybrid EN/VI NL Parser Integration, Modal UI/UX Overhaul & `Q9` Option A Resolution (`ltbinh/sync-proposal`)
- **Authors:** Antigravity Agent + Team 03
- **Summary:** Integrated the personal `NL_Parser_Package` into `group03-smartschedule-baseline/NL_Parser_Package/` alongside M1 (`src/nl_parser.py`, `web/api.py`), overhauled the Student Task Modal (`web/index.html`, `web/app.js`) with cross-browser drag-and-drop `[[filename]]`/`@[path]` lossless citation verification, resolved open question `Q9` using **Option A** (Lossless Compression & Early Extension Alert), aligned `requirements.txt`, and expanded automated test coverage to **142 `pytest` tests + 200 YAML NL benchmark cases**.
- **Verification:** `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200` / `458.1 ms`), `clean_runner.py --pass` (`136/136`), `clean_runner.py --gaps` (`5/5`), `pytest` (`142 passed`).

---

### Entry 008 — 2026-11-15 | Post-Sync Audit Fixes & Documentation Alignment (`ltbinh/sync-proposal`)
- **Author / Lead:** ltbinh (assisted by Antigravity AI)
- **Branch:** `ltbinh/sync-proposal`
- **Summary:** Aligned manual move & drag/drop API contract (`proposed_block`), per-task `buffer_mode="NONE"`, `SHORTEN_TASK` contiguous guard (`new_dur <= 90`) + `LocalRepairEngine.repair_overrun` pin guard, `DIS_xxxx` event ID reuse, 5-solver benchmark tables, and synchronized docs.
- **Verification:** `clean_runner.py --pass` (`107/107`), `clean_runner.py --gaps` (`5/5`), `benchmark_runner.py`.

---

### Entry 007 — 2026-11-15 | Full Proposal & Presentation2 Synchronization (`ltbinh/sync-proposal`)
- **Author / Lead:** ltbinh (assisted by Antigravity AI)
- **Branch:** `ltbinh/sync-proposal`
- **Summary:** Fixed core defects (`A1–A12`), unified dynamic `now_day`/`now_slot`, added `PersonalHabit` + sleep `>= 6h`, implemented `ScoredGreedySolver` (`SCORED_GREEDY`) and 8 Human Behavioral Patterns, integrated `OverloadTriageEngine` & M1/M7 pipelines, removed client-side double buffering, and created `benchmark_alpha_grid.py`.

---

### Entry 006 — 2026-11-06 | Student-Facing Minimalist UI & Dual-Mode Architecture
- **Author / Lead:** Duc Minh (assisted by Antigravity AI — Gemini 3.8 Flash)
- **Summary:** Introduced the dual-mode switch (`Student Mode` vs `Lab Mode`), 3 student-centric views (Weekly Calendar, Today Focus, Task Queue), 3-field task modal with live buffer preview, and Pin / Check-in / "Why here?" interactive controls.

---

### Entry 005 — 2026-11-06 | Feature 001: Estimate Buffer (Planning-Fallacy Correction)
- **Author / Lead:** Nguyễn Trọng Tiến (Thinker 3 — Abstraction & Algorithmic Design), assisted by Claude Code
- **Summary:** Created pure module `src/estimate_buffer.py` (`RARELY` x1.00, `SOMETIMES` x1.10, `OFTEN` x1.25 with deterministic integer nearest-15-min rounding), wired `apply_estimate_buffer()` and `ESTIMATE_BUFFER` reason codes, and added 34 logical tests.
- **Verification:** `clean_runner.py --pass` (`84 Passed | 0 Failed`).

---

### Entry 004 — 2026-11-04 | Environment & Dependency Specifications (`requirements.md`)
- **Author / Lead:** Nguyễn Nguyễn Gia Bảo (Builder 3 — System Architecture & Testing)
- **Summary:** Authored `agents/requirements.md` and `docs/requirements.md`, created `setup_env.bat`, and established the simultaneous dependency update protocol.

---

### Entry 003 — 2026-11-04 | Interpretable Diagnostic Console & Documentation Hub
- **Author / Lead:** Nguyễn Nguyễn Gia Bảo (Builder 3 — System Architecture & Testing)
- **Summary:** Built `clean_runner.py` (`InterpretableConsolePlugin`), integrated Test Studio batch actions, and created the bilingual `agents/` & `docs/` documentation hubs (`50/50` passing baseline, `5/5` gap tests).

---

### Entry 002 — 2026-11-04 | 60/40 Verification Matrix & Pre-deployment Infrastructure
- **Author / Lead:** Nguyễn Nguyễn Gia Bảo (Builder 3 — System Architecture & Testing)
- **Summary:** Organized `verification_tests/` into 5 layers implementing the 60/40 verification matrix alongside `test_studio.py`.

---

### Entry 001 — 2026-10-29 | Initial Baseline Engine (V0) & Course Benchmarks
- **Author / Lead:** Group 03 Core Team
- **Summary:** Formulated the 672-slot discrete grid, baseline Pydantic schemas, V0 `EDF`/`LST`/`WSPT` greedy solvers, FastAPI workbench, and course scenarios `T01–T10`.
