# Feature 001 — Implementation Plan

## Constraints from the team repository

* INV-1 / INV-2: `src/models.py` and the new module must not import `web`, `fastapi`, `controller` or `solvers`.
* INV-3: solvers stay stateless. The buffer is applied to **copies** of the tasks, so the caller's objects are never mutated.
* Do not edit `src/solvers/*`. Teammates are working on the solver gaps (energy matching, rest breaks, reason codes).
* Do not touch the natural-language / quick-add parser (owned by another teammate).
* No new dependency. `requirements.txt` stays the same.

## Design

| Layer | File | Change |
|---|---|---|
| 1 Models | `src/estimate_buffer.py` (new) | Pure functions: `normalize_habit`, `multiplier_for_habit`, `planned_duration_min`, `buffer_reason`. Integer arithmetic (percent), so results are deterministic. |
| 1 Models | `src/models.py` | `CommitmentsProfile.estimate_habit` (validated). `Task.buffer_multiplier` (1.0–2.0, default 1.0). `Task.get_planned_duration_min()` calls `planned_duration_min`. |
| 3 Controller | `src/controller.py` | `apply_estimate_buffer(profile, tasks)` (idempotent copy). `solve_schedule` applies it and annotates blocks with `ESTIMATE_BUFFER`. `handle_task_overrun` adds overrun to the raw estimate and returns `new_estimate_min`. Repair paths receive buffered tasks. |
| 4 Web API | `web/api.py` | Read `estimate_habit` from `commitments`, `profile` (Improve Plan contract) or top level. Apply the buffer in `_extract_profile_and_tasks` so every endpoint (repair, export, compare…) sees the same durations. Return `new_estimate_min`. |
| 4 Web UI | `web/index.html`, `web/app.js` | Habit selector in the task form, "planned X min" preview, "Ước lượng → Dự trù" column, overrun keeps the raw estimate. |
| 5 Tests | `verification_tests/feature_tests/test_estimate_buffer.py` (new), gap test input fix | Unit + API tests for AC1–AC7. |

## Rounding rule (integer form)

```
pct      = round(multiplier × 100)                 # 100, 110, 125
nearest  = ((estimate × pct + 750) // 1500) × 15   # nearest 15-min slot, half up
floor    = round_up_to_15(estimate)
planned  = max(floor, nearest)
```

## Risks

| Risk | Mitigation |
|---|---|
| Changing V0 results for existing scenarios | Default habit is empty → multiplier 1.0 → identical output (AC2) |
| Buffer applied twice (API + controller) | `apply_estimate_buffer` *sets* the multiplier, never multiplies it again |
| UI stores the buffered value after an overrun, so the next plan buffers it again | API returns `new_estimate_min`; UI stores that |
