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
- **Improve Plan Backlog (V1/V2):** Specifications defined in `Improve_Plan/improve_plan.md` for student-centered features (Circadian energy matching, 15m rest breaks, planning buffer multipliers, sprint mode, habit skipping overload resolution, and ISO-8601 JSON Data Contract).
- **Verification Infrastructure:** Complete 56-test matrix enforcing architectural purity, heap stability, edge case solvability, and tracking 5 live developmental feature gaps.

---

## 2. Chronological Log of System Changes

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
     - Authored [`agents/requirements.md`](file:///d:/Projects/Computational-Thinking---Group-Project/agents/requirements.md) (English) and [`docs/requirements.md`](file:///d:/Projects/Computational-Thinking---Group-Project/docs/requirements.md) (Vietnamese) breaking down all 6 dependencies from `requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `python-dateutil`).
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

