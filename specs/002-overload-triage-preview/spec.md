# Feature Spec 002 — Smart Overload Triage, Habit-Skipping & Interactive Trade-off Preview Engine

| Field | Value |
|---|---|
| **Feature ID** | `002-overload-triage-preview` (Feature F15) |
| **Source** | `Improve_Plan/improve_plan.md` §5.1 (F15), §6.7 (Screen 4 — Overload alert), §7.2 (`POST /api/overload/preview`), §7.3 (`Overload` object & `SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST`); `Proposal/Proposal_Report.pdf` §2.7 (R6, S4) & Pillar 4 (Perspective 4: Overload & Alerts) |
| **Acceptance Test** | `verification_tests/development_gap_tests/test_improve_plan_gaps.py::test_fail_overload_habit_skipping_recommendation` + `tests/test_overload_triage.py` |
| **Author** | Hoàng Minh Anh (Thinker 2 — Perspective 4: Overload & Alerts / UI-UX Review Flow) |
| **Branch** | `hmanh` |
| **Status** | Implemented on branch `hmanh` |

---

## 1. Problem Statement

When a student's weekly workload exceeds the available free time before a deadline bottleneck ($W_{\text{total}}(D) > C_{\text{free}}(D)$) or when an unsplittable task cannot fit into any contiguous free gap before its deadline, the Baseline (V0) engine reports an `OverloadReport` (`CAPACITY_SHORTAGE` or `FRAGMENTATION_FAILURE`). However, V0 has three critical user-facing and algorithmic gaps identified in `Improve_Plan/improve_plan.md` (§5.1 F15, §6.7, §7.2, §7.3) and `test_improve_plan_gaps.py`:

1. **No Distinction Between Habits/Optional Tasks and Graded Assignments (`SKIP_HABIT` Missing):** V0 only suggests dropping the lowest-priority task (`POSTPONE_LOWEST`) or shortening/splitting an unplaced task (`SHORTEN_TASK` / `ALLOW_SPLIT`). It never scans the week for flexible habits (`category == "HABIT"`, `deadline_day is None`) or low-weight optional tasks (`priority <= 2`) to suggest `SKIP_HABIT`, causing Gap Test #5 (`test_fail_overload_habit_skipping_recommendation`) to fail.
2. **No Dependency-Graph (`depends_on`) Safety Check in Triage Recommendations:** Suggesting to skip or postpone a task that is a prerequisite (`depends_on`) for a high-priority deadline task would break Hard Constraint $H_3$ (Topological Prerequisite Ordering).
3. **No Interactive "What-If" Preview (`POST /api/overload/preview`) or Undo Flow:** On the Web Workbench (`web/index.html`, `web/app.js`), the overload alert is a static red banner. The student cannot click an option to preview how the 672-slot timetable would change (with affected/newly-placed blocks highlighted as `state = "PROPOSED"` in dashed borders), nor apply an option with 1-click Undo.

---

## 2. User Stories

* **US1 (Least-Harm Habit & Optional Task Skipping):** As a student facing an overloaded week, I want the engine to recommend skipping flexible habits (`category="HABIT"`, no deadline) or low-priority optional tasks (`priority <= 2`) first (`SKIP_HABIT`), so that my core graded academic assignments are protected without sacrificing sleep (`SLEEP`) or fixed classes (`OCCUPIED`).
* **US2 (Clear Overload Math & Concrete Trade-off Options):** As a student, when my schedule cannot fit all tasks before a deadline $D$, I want to see the exact numbers (`Available Free Minutes` vs. `Planned Work Minutes` vs. `Shortage Minutes`) and 2–4 concrete, dependency-safe resolution options (`SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST`) with exact minutes freed or reduced.
* **US3 (Non-Destructive What-If Preview on the 672-Slot Grid):** As a student, I want to click **"Preview"** on any overload resolution option to see the simulated schedule on the 7-day timetable with newly placed or modified blocks rendered in a distinct dashed border (`state = "PROPOSED"`) and a before/after metrics comparison, without immediately overwriting my task list.
* **US4 (Apply with 1-Click Undo):** As a student, I want to click **"Apply"** to commit the chosen overload resolution option to my schedule and have a 1-click **"Undo"** button to restore my previous task list and schedule if I change my mind.

---

## 3. Functional Requirements

| ID | Requirement |
|---|---|
| **FR1** | **Pure Overload Triage Module (`src/overload_triage.py`):** Implement `OverloadTriageEngine` as a pure domain service that inspects `CommitmentsProfile`, `List[Task]`, and `ScheduleOutput` without importing `web` or `fastapi` (`INV-1`) and without mutating caller inputs (`INV-3`). |
| **FR2** | **Least-Harm Option Ranking (`SKIP_HABIT` $\to$ `SHORTEN_TASK` $\to$ `ALLOW_SPLIT` $\to$ `POSTPONE_LOWEST`):** Enrich every `OverloadReport` with standardized `options[]` ordered from least academic harm to greatest harm:<br>1. `SKIP_HABIT`: Suggest skipping/deferring flexible habits (`category == "HABIT"` or `deadline is None`) or low-priority optional tasks (`priority <= 2`) that are NOT prerequisites (`depends_on`) of higher-priority tasks.<br>2. `SHORTEN_TASK`: For `CAPACITY_SHORTAGE`, suggest reducing the bottleneck task's duration by `shortage_min` (rounded up to 15m slots, respecting `min_chunk_min >= 15`).<br>3. `ALLOW_SPLIT`: For `FRAGMENTATION_FAILURE` (or unsplittable tasks $\ge 60\text{ min}$), suggest converting `is_splittable = True` with `min_chunk_min = 45`.<br>4. `POSTPONE_LOWEST`: Suggest moving the lowest-priority non-prerequisite task in the bottleneck window past the bottleneck deadline (`Sunday 23:59` or `Next Monday 23:59`). |
| **FR3** | **Hard Constraint Protection (`INV-4`):** Overload triage options and mutations must NEVER unlock, shorten, or clear `SLEEP` (`H2`/`H5`) or `OCCUPIED` (`H1`) slots, and must NEVER violate prerequisite chains (`H3`). |
| **FR4** | **Deterministic Option Transformation (`apply_triage_option`):** Given `(profile, tasks, option_id, option_code, target_task_id, shortage_min)`, return a deep-copied `List[Task]` with the exact transformation applied deterministically. |
| **FR5** | **Controller Integration (`ScheduleController`):** Automatically enrich `ScheduleOutput.overload` and `ScheduleOutput.overload_reports` in `ScheduleController.solve_schedule()` and expose `ScheduleController.preview_overload_resolution()` for full What-If simulation. |
| **FR6** | **Interactive Preview Endpoint (`POST /api/overload/preview`):** Accept `{ commitments/profile, tasks, option_id, option_code, target_task_id, algorithm, schedule }`, execute the simulation on deep-copied inputs, mark newly placed or modified blocks with `state = "PROPOSED"`, and return `{ status, preview_mode, option_id, option_applied, resolved_tasks, before_summary, after_summary, blocks, changes, schedule }`. Maintain backward compatibility with minimal `{ option_id, schedule }` payloads. |
| **FR7** | **Interactive Workbench UI (`web/index.html`, `web/app.js`):** Render interactive option cards inside `#overloadAlertBox` with **Preview** (`👁️ Xem Trước`) and **Apply** (`✅ Áp Dụng`) buttons, render `state === "PROPOSED"` blocks with dashed borders (`.slot-block-proposed`), and provide a Preview Banner (`Áp Dụng` / `Hủy Xem Trước`) plus a 1-click **Undo** (`↩️ Hoàn Tác`) bar after applying an option. |
| **FR8** | **Zero Solver Modification:** Do not modify any file in `src/solvers/*` or `requirements.txt` to guarantee zero merge conflicts with teammates working on solver heuristics. |

---

## 4. Edge Cases & Input/Output Conditions

### 4.1. Input Conditions
* `profile`: `CommitmentsProfile` with `planning_week_start`, `sleep_schedule`, and `fixed_events`.
* `tasks`: `List[Task]` where each task has `task_id`, `duration_min > 0`, `priority` ($1..5$), `category`, `is_splittable`, `min_chunk_min`, and `depends_on`.
* `option_id` / `option_code`: Selected from `overload.options` (`O1`, `O2`, `O3`, `O4` or `SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST`).

### 4.2. Edge Cases Handled
* **Edge Case E1 (Overload with only academic deadline tasks, e.g., Scenario `T06`):** When `T06` has 3 deadline tasks (`T06-EXTRA-1` p=5, `T06-EXTRA-2` p=4, `T06-EXTRA-3` p=2) and no explicit `category="HABIT"` task, the triage engine identifies `T06-EXTRA-3` (`priority <= 2`, optional/low-weight work, not a prerequisite) as eligible for `SKIP_HABIT` (deferring optional low-priority work) in addition to `SHORTEN_TASK` and `POSTPONE_LOWEST`.
* **Edge Case E2 (Overload when scheduled habits occupy free slots, e.g., Minh's Week + extra deadline task):** Even if a habit task (`TASK-08` or `TASK-09`, `category="HABIT"`) was already placed or remains in the task list, the triage engine surfaces `SKIP_HABIT` targeting that habit so its slots can be reclaimed or spared.
* **Edge Case E3 (Prerequisite Protection on `depends_on`):** If a low-priority task $T_A$ (`priority=1`) is listed in `T_B.depends_on` where $T_B$ has `priority=5`, $T_A$ is excluded from `SKIP_HABIT` and `POSTPONE_LOWEST` to prevent breaking $T_B$'s prerequisite chain ($H_3$).
* **Edge Case E4 (Shortening Floor Boundary):** If `duration_min - shortage_min < min_chunk_min` (or $< 15\text{ min}$), `SHORTEN_TASK` clamps the shortened duration to `max(15, min_chunk_min)` and reports the exact `reduces_min = old_duration - new_duration`.
* **Edge Case E5 (Minimal Stub Payload on `/api/overload/preview`):** If a caller sends only `{"option_id": "O1", "schedule": {"blocks": [...]}}` without `tasks`, the endpoint gracefully falls back to marking the provided blocks as `state = "PROPOSED"` so existing contract tests pass without error.

---

## 5. Clarifications & Design Decisions

| # | Question | Decision | Rationale |
|---|---|---|---|
| **C1** | Why implement Overload Triage in `src/overload_triage.py` + `src/controller.py` instead of editing `src/solvers/base_solver.py`? | Keep `src/solvers/*` 100% untouched; enrich `ScheduleOutput` in `ScheduleController.solve_schedule()` via `OverloadTriageEngine`. | Prevents Git merge conflicts with Builder 2 (who owns solver modifications) while ensuring every solver (`EDF`, `LST`, `WSPT`, `Backtracking`) automatically gets enriched overload options. |
| **C2** | How should `SKIP_HABIT` behave on Scenario `T06` where all 3 tasks have Tuesday deadlines? | Identify both explicit habits (`category == "HABIT"` or `deadline is None`) AND optional low-priority tasks (`priority <= 2`, not depended upon) as `SKIP_HABIT` candidates. | `test_fail_overload_habit_skipping_recommendation` in `test_improve_plan_gaps.py` specifically loads `/api/scenarios/t06` and asserts `"SKIP_HABIT" in option_codes`. In `T06`, `T06-EXTRA-3` has `priority=2` ("Optional Lab Practice"). Treating `priority <= 2` non-prerequisite tasks as skippable optional habits/practice satisfies both `T06` and general habit-skipping. |
| **C3** | What happens when a user clicks **Preview** vs. **Apply** in the UI? | **Preview** calls `POST /api/overload/preview` and renders the proposed schedule with dashed `PROPOSED` blocks without overwriting `state.tasks`. **Apply** pushes a deep copy of `state.tasks` and `state.lastSchedule` onto `state.overloadUndoStack`, updates `state.tasks` with `resolved_tasks`, and re-solves. | Directly implements `Improve_Plan/improve_plan.md` §6.7: *"Clicking an option previews the change on the grid (affected blocks get a dashed outline). Apply commits the change; Undo in the top bar reverts it."* |

---

## 6. Acceptance Criteria

| ID | Given | When | Then |
|---|---|---|---|
| **AC1** | Scenario `T06` (`t06_overload_capacity.json`) loaded via `/api/scenarios/t06` and solved via `POST /api/plan` | Checking `response.json()["overload"]["options"]` | `option_codes` contains `"SKIP_HABIT"`, `"SHORTEN_TASK"`, and `"POSTPONE_LOWEST"` (Gap Test #5 `test_fail_overload_habit_skipping_recommendation` PASSES). |
| **AC2** | Scenario `T06` (`shortage_min = 105`) | Calling `POST /api/overload/preview` with `option_code="SHORTEN_TASK"` on `T06-EXTRA-3` | `after_summary.tasks_placed == 3`, `after_summary.tasks_unplaced == 0`, `after_summary.hard_constraint_violations == 0`, and affected blocks have `state == "PROPOSED"`. |
| **AC3** | Scenario `T03` (`t03_large_unsplittable.json` with 240-min unsplittable task) | Calling `POST /api/overload/preview` with `option_code="ALLOW_SPLIT"` | Task `T03-BIG` becomes `is_splittable=True, min_chunk_min=45` in `resolved_tasks`, is placed across valid free gaps with `0` hard violations, and its chunks are marked `state == "PROPOSED"`. |
| **AC4** | A low-priority task `T_PREREQ` (`priority=1`) that is in `depends_on` of `T_CAPSTONE` (`priority=5`) | Building overload triage options | `T_PREREQ` is never recommended for `SKIP_HABIT` or `POSTPONE_LOWEST` past `T_CAPSTONE`'s deadline. |
| **AC5** | Caller's `profile` and `tasks` objects passed into `solve_schedule` or `preview_overload_resolution` | Inspecting caller's `tasks` after execution | Caller's original `Task` objects are 100% unmodified (`INV-3` statelessness) and `SLEEP`/`OCCUPIED` slots are untouched (`INV-4`). |
| **AC6** | Running `ScheduleController.verify_determinism` (3x runs) on `T06` and previewing any triage option 3 times | Comparing SHA-256 hashes and preview outputs | All 3 runs produce identical SHA-256 hashes and identical block coordinates. |
