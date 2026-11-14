# SmartSchedule — Verification Testing & Benchmark Architecture

**Project:** SmartSchedule — Verification & Production Readiness  
**Author / Lead:** Builder 3 (System Architecture & Testing)  
**Location:** `group03-smartschedule-baseline/verification_tests/`  
**Target Audience:** AI Coding Assistants, QA Engineers & Testers  

---

## 1. Overview & Test Suite Philosophy

The SmartSchedule verification testing suite serves as the **production verification gate** for our 10-week development arc. It tests not just typical happy-path executions, but systematically probes memory boundaries, AST architectural compliance, mathematical unsolvability, circular DAG traps, and developmental feature gaps.

### 1.1. The 60/40 Verification Matrix
To ensure realistic software engineering rigor, our **56 automated tests** follow a strict distribution:

```text
Total Test Matrix: 56 Automated Tests
├── ~60% Average / Operational Passing Tests (50 tests):
│   ├── Standard feasible scheduling on typical student weeks (Minh & Lan)
│   ├── 672-slot discrete math calculations (196 SLEEP + 132 OCCUPIED + 344 FREE)
│   ├── Determinism verification (3x identical SHA-256 hash checks)
│   ├── UI static workbench delivery & export endpoints (.ics, .csv, .json)
│   ├── AST architectural boundaries (solvers do not import web/FastAPI)
│   ├── Heap memory leak checks (< 350 KB growth over 50 solves)
│   └── Topo-sort DAG ordering & clean Pydantic schema validation
│
└── ~40% Edge Cases & Developmental Target Failures (6 tests):
    ├── Scheduling result edge cases (simultaneous priority inversions, Sunday boundary)
    ├── Extreme 15-minute slot fragmentation vs. capacity diagnostics
    ├── Code production stress (concurrent thread safety, 50-task scale latency, timezone offsets)
    ├── Mathematical unsolvability proofs via response retrieval (capacity shortage, zero-slack)
    └── 5 Intentional Developmental Failures exposing current V0 Baseline limitations
```

---

## 2. Directory Breakdown & Test Inventory

All tests are strictly located in `group03-smartschedule-baseline/verification_tests/`:

### 2.1. UI & Delivery Tests (`ui_tests/` — 6 tests)
- `test_ui_endpoints.py` (5 tests):
  - `test_workbench_index_html_delivery`: Verifies `/` delivers HTML and contains `#scheduleGrid`.
  - `test_presets_retrieval`: Validates `/api/presets` returns `minh` and `lan` configurations.
  - `test_solve_endpoint_standard_payload`: Executes end-to-end `/api/solve` with sample payload.
  - `test_validate_move_interactive_drag`: Validates manual move collision detection.
  - `test_calendar_export_endpoints`: Tests export generation for `.json`, `.csv`, and `.ics`.
- `test_ui_contract_improve_plan.py` (1 test):
  - `test_ui_contract_fields_compliance`: Enforces ISO-8601 JSON schema matching Improve Plan §7.3.

### 2.2. Architecture & Invariant Tests (`architecture_tests/` — 9 tests)
- `test_system_architecture.py` (4 tests):
  - `test_solvers_do_not_import_web`: Statically inspects AST of all solver files; asserts zero imports of `web` or `fastapi`.
  - `test_models_layer_is_pure`: Asserts `src/models.py` imports neither `solvers` nor `controller`.
  - `test_solver_statelessness_across_runs`: Asserts solver instances retain no cached state across sequential solves.
  - `test_cannot_clear_sleep_or_occupied_masks`: Proves `remove_block()` cannot clear locked `SLEEP` or `OCCUPIED` slots.
- `test_memory_leaks.py` (2 tests):
  - `test_solver_memory_leak_over_50_iterations`: Uses `tracemalloc` to prove heap growth is $< 350\text{ KB}$ across 50 solves.
  - `test_solver_peak_memory_bounded`: Asserts single-solve peak memory is $< 10\text{ MB}$.
- `test_production_failures.py` [Edge Cases] (3 tests):
  - `test_concurrent_solves_thread_safety`: Multi-threaded simultaneous execution of Student A and Student B; asserts zero block leakage between threads.
  - `test_scale_50_tasks_latency_sla`: Stresses solver with 50 tasks; asserts solving latency is strictly $< 2000\text{ ms}$.
  - `test_timezone_offset_handling`: Tests non-local timezone offsets (`-05:00` New York); verifies graceful handling without internal 500 errors.

### 2.3. Logical & Edge Case Tests (`logical_tests/` — 16 tests)
- `test_circular_dependencies.py` (4 tests):
  - Traps mutual cycles ($A \leftrightarrow B$), self-loops ($A \to A$), and transitive 3-node cycles ($A \to B \to C \to A$) without infinite recursion.
- `test_undefined_behaviors.py` (4 tests):
  - Guards against illegal hours (`"25:00"`), slot out-of-bounds queries, negative durations, and clamps priority ($1 \le p \le 5$).
- `test_generation.py` (4 tests):
  - Parameterized test generator evaluating random tasks across `EDF`, `LST`, and `WSPT` while verifying $C_{\text{hard}} = 0$ continuously.
- `test_scheduling_edge_cases.py` (4 tests):
  - `test_edge_simultaneous_deadline_priority_inversion`: Proves high-priority tasks (P5) are preserved while low-priority tasks (P1) are dropped under tight capacity.
  - `test_edge_sunday_boundary_overflow_no_wraparound`: Verifies task ending past Sunday midnight never wraps around to Monday slot 0.
  - `test_edge_extreme_15min_fragmentation`: Partitions 4 hours into sixteen 15m slots; proves atomic 60m task is diagnosed in `unplaced_tasks`.
  - `test_fail_edge_sprint_mode_compression_recovery` [Target Failure]: Tests sprint mode compression when task misses deadline by $\le 15\text{m}$.

### 2.4. Benchmark Tests (`benchmark_tests/` — 20 tests)
- `test_time_grid.py` (3 tests): Discrete math and 672-slot allocation verification.
- `test_constraints.py` (3 tests): Hard constraints $H_1$–$H_5$ on Minh and Lan presets.
- `test_edf_solver.py` (2 tests): 3x SHA-256 hash equality (determinism) and local repair stability ($S_{\text{stability}} \ge 90\%$).
- `test_scenarios_t01_t10.py` (7 tests): Integration testing across standardized course scenarios T01–T10.
- `test_feasibility_benchmarks.py` [Solvability Proofs] (5 tests):
  - Evaluates possible vs impossible schedules via response retrieval:
    1. Tight Feasible Single Gap (Possible)
    2. Capacity Shortage (Impossible — proves 60m shortage retrieval)
    3. Fragmentation Barrier (Impossible — 150m atomic task vs two 90m gaps)
    4. Prerequisite Dependency Chain (Possible — $\text{Arch} \to \text{Impl} \to \text{Test}$)
    5. Deadlocked Zero Free Window (Impossible — preserves sleep $H_2$)

### 2.5. Development Gap Tests (`development_gap_tests/` — 5 tests)
Intentional target failure tests tracking upcoming features from `Improve_Plan/improve_plan.md`:
1. `test_fail_circadian_energy_matching` (Improve Plan §3.3)
2. `test_fail_rest_break_insertion_after_deep_work` (Decision D2)
3. `test_fail_planning_fallacy_buffer_multiplier` (Feature F06)
4. `test_fail_why_popover_structured_reason_codes` (Table §7.3)
5. `test_fail_overload_habit_skipping_recommendation` (Feature F15)

---

## 3. Interpretable Test Runner (`clean_runner.py`)

To eliminate confusing terminal clutter, test execution is managed by [`clean_runner.py`](file:///d:/Projects/Computational-Thinking---Group-Project/group03-smartschedule-baseline/verification_tests/clean_runner.py), which outputs a structured, human-readable format:

```text
========================================================================
[RUNNING] Verification Test Engine Active...
Target:   Operational Verification Suite (Passing Baseline Tests)
Time:     2026-11-04 16:39:33
========================================================================

[PHASE 1/4] UI & Frontend Contract Tests (verification_tests/ui_tests)
  [FILE] test_ui_contract_improve_plan.py ...................... PASSED (1/1 tests)
  [FILE] test_ui_endpoints.py .................................. PASSED (5/5 tests)

[PHASE 2/4] System Architecture & Invariant Tests (verification_tests/architecture_tests)
  [FILE] test_memory_leaks.py .................................. PASSED (2/2 tests)
  [FILE] test_production_failures.py ........................... PASSED (3/3 tests)
  [FILE] test_system_architecture.py ........................... PASSED (4/4 tests)
...
========================================================================
[FINAL SUMMARY] 50 Passed | 0 Failed | Total: 50 Tests
Execution Time: 3.42s | Status: ALL PASSED
========================================================================
```

---

## 4. How to Execute Tests

### 4.1. Via Batch Scripts (Recommended)
- **Run all operational passing tests:**
  ```powershell
  .\group03-smartschedule-baseline\verification_tests\run_verification_tests.bat --pass
  ```
- **Track developmental feature gaps (expected failures):**
  ```powershell
  .\group03-smartschedule-baseline\verification_tests\run_verification_tests.bat --gaps
  ```
- **Run the full 60/40 matrix (all 56 tests):**
  ```powershell
  .\group03-smartschedule-baseline\verification_tests\run_verification_tests.bat --all
  ```
- **Run only the 40% edge cases:**
  ```powershell
  .\group03-smartschedule-baseline\verification_tests\run_verification_tests.bat --edge
  ```

### 4.2. Via Minimal GUI Studio
Double-click `group03-smartschedule-baseline/verification_tests/run_test_studio.bat` to launch the native desktop GUI for point-and-click test editing and execution.

