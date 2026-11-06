# Feature 002 — Implementation Plan (`002-overload-triage-preview`)

## 1. Architectural Constraints & Invariants

To integrate cleanly into the Group 03 repository without breaking architectural tests (`verification_tests/architecture_tests/test_system_architecture.py`) or conflicting with teammates' branches:

* **INV-1 (Domain Layer Isolation):** `src/overload_triage.py` and `src/models.py` must NEVER import `web`, `fastapi`, `starlette`, or HTTP clients.
* **INV-2 (Pure Data Model Layer):** `src/models.py` must never import `src.controller` or `src.solvers`.
* **INV-3 (Statelessness & Deep-Copy Immutability):** `OverloadTriageEngine` and `ScheduleController.preview_overload_resolution()` must always clone tasks via `t.model_copy(deep=True)` and never mutate the caller's list or task instances in-place.
* **INV-4 (Hard Constraint Lock Tamper Resistance):** Overload triage options must never clear or modify `SLEEP` (`H2`/`H5`) or `OCCUPIED` (`H1`) slots on the 672-slot grid.
* **Zero Solver Edits:** `src/solvers/*` and `requirements.txt` remain 100% untouched.

---

## 2. Layered Architecture Design

| Layer | File | Responsibility & Changes |
|---|---|---|
| **Layer 1 — Domain Service** | `group03-smartschedule-baseline/src/overload_triage.py` *(NEW)* | Pure Python module implementing `OverloadTriageEngine`:<br>• `build_triage_options(profile, tasks, report, unplaced_tasks)`: Analyzes bottleneck deadline, identifies prerequisite-safe candidates, and generates ranked least-harm options (`SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST`).<br>• `enrich_schedule_overload(output, profile, tasks)`: Enriches `output.overload` and `output.overload_reports` in-place on the new `ScheduleOutput` with enriched `options[]` and human-readable `suggested_actions[]`.<br>• `apply_triage_option(profile, tasks, option_id, option_code, target_task_id, shortage_min)`: Pure function returning `(resolved_tasks, change_record)` on deep-copied tasks. |
| **Layer 3 — Orchestration** | `group03-smartschedule-baseline/src/controller.py` *(MODIFIED)* | • In `ScheduleController.solve_schedule()`: Call `OverloadTriageEngine.enrich_schedule_overload(out, profile, tasks)` before returning `(out, grid)`.<br>• Add `ScheduleController.preview_overload_resolution(...)`: Runs before/after comparison on deep-copied tasks, marks newly placed or shifted blocks as `state = "PROPOSED"`, and returns full comparison metrics + `resolved_tasks`. |
| **Layer 4 — Web API** | `group03-smartschedule-baseline/web/api.py` *(MODIFIED)* | • Upgrade `POST /api/overload/preview` to invoke `ScheduleController.preview_overload_resolution()` when `tasks` are provided in the payload, while preserving backward compatibility for minimal `{ option_id, schedule }` stub payloads. |
| **Layer 4 — Web Workbench UI** | `group03-smartschedule-baseline/web/index.html`<br>`group03-smartschedule-baseline/web/app.js` *(MODIFIED)* | • Add `.slot-block-proposed` CSS styling (dashed border + subtle diagonal stripe / badge) for `state === "PROPOSED"` blocks.<br>• Upgrade `renderOverloadBox(schedule)` in `web/app.js` to render interactive triage option cards (`SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST`) with **Xem Trước (Preview)** and **Áp Dụng (Apply)** buttons.<br>• Add Preview Mode banner (`Áp Dụng Phương Án Này` / `Hủy Xem Trước`) and 1-click **Hoàn Tác (Undo)** bar backed by `state.overloadUndoStack`. |
| **Layer 5 — Verification** | `group03-smartschedule-baseline/tests/test_overload_triage.py` *(NEW)*<br>`group03-smartschedule-baseline/verification_tests/logical_tests/test_overload_triage.py` *(NEW)* | • Comprehensive unit + FastAPI endpoint tests covering `AC1–AC6`, Scenario `T06`, Scenario `T03`, Minh's Week overload, prerequisite protection, deep-copy immutability (`INV-3`), sleep/commitment lock safety (`INV-4`), and 3x SHA-256 determinism. |

---

## 3. Triage Option Generation & Transformation Rules

### 3.1. Prerequisite Safety Set (`protected_prereq_ids`)
Before selecting any task for `SKIP_HABIT` or `POSTPONE_LOWEST`, `OverloadTriageEngine` computes:
$$\text{ProtectedPrereqs} = \bigcup_{t \in \text{Tasks}} \{ p \in t.\text{depends\_on} \mid t.\text{priority} \ge 3 \}$$
Any task $u \in \text{ProtectedPrereqs}$ is protected from being skipped or postponed past its dependent's deadline.

### 3.2. Option 1: `SKIP_HABIT` (Skip / Defer Habit or Low-Priority Optional Work)
* **Candidate Criteria:** Tasks $t \notin \text{ProtectedPrereqs}$ matching either:
  1. Explicit habit / flexible task: `t.category.upper() == "HABIT"` or `t.resolve_deadline_slot() is None`.
  2. Optional / low-priority practice task: `t.priority <= 2` (when no explicit `HABIT` exists or alongside habits).
* **Sorting Order:** Explicit `HABIT` / no-deadline tasks first, then lowest `priority` ($1 \to 2$), then largest `get_planned_duration_min()` (frees the most time first), then deterministic `task_id`.
* **Transformation (`apply_triage_option`):** Removes the target habit/optional task from the active week's `resolved_tasks` (deferring it out of the overloaded week), freeing `frees_min = t.get_planned_duration_min()`.

### 3.3. Option 2: `SHORTEN_TASK` (Reduce Duration to Fit Capacity)
* **Candidate Criteria:** When `shortage_min > 0` (`CAPACITY_SHORTAGE`), targets the unplaced task (or lowest-priority bottleneck task) $t$ whose `get_planned_duration_min() > 15`.
* **Calculation:**
  $$\text{floor\_min} = \max(15, \min(t.\text{min\_chunk\_min}, 45))$$
  $$\text{new\_duration} = \max\left(\text{floor\_min}, t.\text{get\_planned\_duration\_min}() - \text{round\_up\_to\_15}(\text{shortage\_min})\right)$$
  $$\text{reduces\_min} = t.\text{get\_planned\_duration\_min}() - \text{new\_duration}$$
* **Transformation (`apply_triage_option`):** Updates `t_copy.duration_min = new_duration` (and if `t_copy.min_chunk_min > new_duration`, clamps `min_chunk_min = new_duration`).

### 3.4. Option 3: `ALLOW_SPLIT` (Split Large Unsplittable Task into 45m+ Chunks)
* **Candidate Criteria:** Any unplaced or bottleneck task $t$ with `not t.is_splittable` and `t.get_planned_duration_min() >= 60`.
* **Transformation (`apply_triage_option`):** Sets `t_copy.is_splittable = True` and `t_copy.min_chunk_min = 45`.

### 3.5. Option 4: `POSTPONE_LOWEST` (Defer Lowest-Priority Bottleneck Task)
* **Candidate Criteria:** Lowest-priority task $t \notin \text{ProtectedPrereqs}$ among tasks competing before the bottleneck deadline (or among unplaced tasks).
* **Transformation (`apply_triage_option`):** Moves `t_copy.deadline_day` to `"Sunday"` (`23:59`) if its current deadline is earlier than Sunday, or to `"Next Monday"` (`23:59`) if its deadline is already on Sunday, clearing `t_copy.due = None` so `resolve_deadline_slot` uses the new deferred deadline.

---

## 4. Risk Mitigation Matrix

| Risk | Mitigation Strategy |
|---|---|
| Breaking existing `T01–T10` benchmark assertions | Feasible scenarios (`T01`, `T02`, `T04`, `T05`, `T07–T10`) have `overload = None`, so `enrich_schedule_overload` is a pure no-op on feasible schedules. On `T03` and `T06`, existing fields (`error_type`, `type`, `shortage_minutes`, `unplaced_tasks`) remain untouched; only `options` and `suggested_actions` are enriched. |
| Breaking `test_improve_plan_section7_json_contract` or existing `/api/overload/preview` callers | `/api/overload/preview` checks if `tasks` are supplied; if only `{option_id, schedule}` is passed, it executes the lightweight block-marking path and still returns `status: "OK"`, `preview_mode: True`, `option_id`, `blocks`, `changes`. |
| Mutating caller task lists during preview | Every method in `OverloadTriageEngine` and `ScheduleController.preview_overload_resolution` clones tasks via `model_copy(deep=True)` before modification. |
