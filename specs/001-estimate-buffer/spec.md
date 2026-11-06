# Feature Spec 001 — Estimate Buffer (Planning-Fallacy Correction)

| Field | Value |
|---|---|
| Feature ID | 001-estimate-buffer |
| Source | `Improve_Plan/improve_plan.md` §6.2 (TaskSheet "planned 75 min"), §7.3 (`profile.estimate_habit`), F04 (onboarding question), F06 (planned duration) |
| Acceptance test | `verification_tests/development_gap_tests/test_improve_plan_gaps.py::test_fail_planning_fallacy_buffer_multiplier` |
| Author | Nguyễn Trọng Tiến (Thinker 3 — Abstraction & Algorithmic Design) |
| Status | Implemented on branch `feature/estimate-buffer` |

## 1. Problem

Students usually underestimate how long a task takes (the planning fallacy). The V0 engine schedules exactly the raw estimate, rounded up to the 15-minute grid. A student who always runs over therefore gets a plan that fails every day.

The improvement plan asks one onboarding question, "How often do you underestimate?", and expects the engine to plan **estimate × buffer**. The UI should show the planned time so the buffer is never hidden.

## 2. User stories

* **US1:** As a student who often underestimates, I want my tasks to be planned a bit longer than my estimate, so that my week does not collapse when I run over.
* **US2:** As a student who rarely underestimates, I want my estimates kept as they are, so that no time is wasted.
* **US3:** As a student, I want to see both my estimate and the planned time for every block, so that I understand why a block is longer than I typed.
* **US4:** As a student with many very small tasks (5–15 min), I don't want the buffer to double them, so that small tasks do not waste my free time.

## 3. Functional requirements

| ID | Requirement |
|---|---|
| FR1 | The profile accepts `estimate_habit` ∈ {`RARELY`, `SOMETIMES`, `OFTEN`} or empty. Lower case and the Improve Plan contract field `profile.estimate_habit` are accepted. |
| FR2 | Multipliers: `RARELY` ×1.00, `SOMETIMES` ×1.10, `OFTEN` ×1.25. Empty means no buffer (exactly V0 behaviour). |
| FR3 | Planned duration = estimate × multiplier, **rounded to the nearest 15-minute slot** (half rounds up), but **never below the unbuffered planned duration** `round_up_to_15(estimate)`. |
| FR4 | The buffer is applied once, in the controller layer, before any solver runs. Solvers are not changed. Applying it twice gives the same result (idempotent). |
| FR5 | Every block of a task whose planned time was increased carries the reason code `ESTIMATE_BUFFER` with `estimate_min`, `planned_min`, `multiplier` and a readable text. |
| FR6 | Overload maths (`total_planned_work_minutes`, `shortage_minutes`) uses the buffered durations, so the shortage numbers stay honest. |
| FR7 | Overrun simulation (T05) adds the overrun to the **raw estimate**, then re-buffers. The API also returns `new_estimate_min`, so the UI stores the estimate and not the buffered value (no compounding). |
| FR8 | The workbench has a selector "Thói quen ước lượng" (estimate habit), a live "planned X min" preview under the duration field, and an "estimate → planned" column in the placed-blocks table. |

## 4. Clarifications (decisions made during the spec phase)

| # | Question | Decision | Reason |
|---|---|---|---|
| C1 | The plan only gives ×1.25 for OFTEN. What about RARELY and SOMETIMES? | ×1.00 and ×1.10 | A rare under-estimator needs no buffer. ×1.10 is a light middle step. |
| C2 | The acceptance test builds a profile without `estimate_habit`, but expects 75 min. | Update the test to pass `estimate_habit="OFTEN"`. The default stays "no buffer". | A default of OFTEN would silently change T01–T10 and every existing benchmark. The test had a missing input, not a wrong expectation. |
| C3 | Round up or round to nearest? | Nearest slot, with the unbuffered duration as the floor | Rounding up twice wastes time: a 15-min task × 1.25 = 18.75 → 30 min (doubled). Nearest-with-floor keeps it at 15 min. Error vs. the exact buffered time is at most 7.5 min. |
| C4 | Do small tasks (5–10 min) waste time? | Partly, and not because of the buffer. The 15-min grid already rounds a 5-min task up to 15 min (V0 behaviour). The buffer adds **no extra slot** to any task of 12 min or less (OFTEN). | The grid size is a team decision (D2). Bundling several tiny tasks into one slot needs a solver change and is out of scope (see §6). |
| C5 | Where is the buffer applied? | Controller (`ScheduleController.apply_estimate_buffer`) + `Task.get_planned_duration_min()` | Every solver already calls `get_planned_duration_min()`. No solver file changes, so no conflict with teammates working on the solvers. |

## 5. Acceptance criteria

| # | Given | When | Then |
|---|---|---|---|
| AC1 | `estimate_habit=OFTEN`, task estimate 60 min | plan with EDF | block `duration_min == 75` (gap test passes) |
| AC2 | no `estimate_habit` | plan T01–T10 | results identical to V0 (all 50 existing tests still pass) |
| AC3 | `OFTEN`, estimates 5, 10, 15 min | plan | each block is 15 min, no `ESTIMATE_BUFFER` reason |
| AC4 | `OFTEN`, estimate 60 min | plan | block reasons contain `ESTIMATE_BUFFER` with `estimate_min=60`, `planned_min=75` |
| AC5 | `OFTEN`, the same input run 3 times | determinism check | the 3 hashes are equal |
| AC6 | `OFTEN`, estimate 60 min, overrun +30 min | `/api/progress` | `new_estimate_min == 90`, `new_duration_min == 120` (90 × 1.25 = 112.5 → 120) |
| AC7 | `estimate_habit="often"` via `/api/plan` (Improve Plan contract) | plan | treated as OFTEN |

## 6. Out of scope

* **Micro-task bundling:** placing two or three tasks shorter than 15 min inside one slot. Needs a solver change. Suggested to the solver owner as a follow-up.
* Learning the multiplier from check-in data (Pillar 2 Part B / F23). For now the student chooses the habit.
* Per-task override of the buffer.
