# Verification, Benchmarks & Evaluation Infrastructure (`agents/progress/verification_and_benchmarks.md`)

**Owner:** Builder 3 (System Architecture & Verification)  
**Test Suite Location:** [`tests/`](../../tests/) · **Automated Judge:** [`v1.0-alpha-plan/Testing_System/`](../../v1.0-alpha-plan/Testing_System/README.md) · **Tools:** [`tools/benchmarks/`](../../tools/benchmarks/)  
**See Also:** [`v1.0-alpha-plan/README_agents.md`](../../v1.0-alpha-plan/README_agents.md)

---

## 1. Modular Test Directory (`tests/`)

Reorganized in `v1.0-alpha` from `group03-smartschedule-baseline/verification_tests/` into clean concise packages wired to `smartschedule.core.config` paths (`PRESETS_DIR`, `SCENARIOS_DIR`, `CORE_DIR`, `UI_DIR`):

```text
tests/
├── clean_runner.py         # Interpretable Pytest CLI runner (-p no:terminal)
├── test_studio.py          # Tkinter Desktop Test Manager GUI
├── conftest.py             # Adds repo root + v1.0-alpha-plan/ to sys.path
├── ui/                     # UI DOM/JS contracts & FastAPI endpoints
├── architecture/           # AST invariants (INV-1..6), tracemalloc (<350 KB), thread safety
├── logical/                # Determinism, V3 solvers, NL parser, Chat-First, SHA-256 tracer, P1–P3
├── benchmark/              # 672-slot grid math, H1–H5 constraints, T01–T10, feasibility proofs
├── gaps/                   # Development gap tracking tests
└── fixtures/nl_cases/      # 200-case YAML corpus + validate_cases.py + verify_hybrid_200.py
```

*(Data presets & `T01–T10` JSONs now live in [`data/presets/`](../../data/presets/) and [`data/scenarios/`](../../data/scenarios/), and `Testing_System` papers live in [`v1.0-alpha-plan/Testing_Plan/papers/`](../../v1.0-alpha-plan/Testing_Plan/papers/).)*

---

## 2. How to Run Verification & Benchmarks (From Repo Root)

```powershell
# 1. Operational Verification Suite (UI, Arch, Logical, Benchmark)
python -B tests/clean_runner.py --pass

# 2. Specific Layers / Edge Cases
python -B tests/clean_runner.py --ui
python -B tests/clean_runner.py --arch
python -B tests/clean_runner.py --logic
python -B tests/clean_runner.py --bench
python -B tests/clean_runner.py --gaps

# 3. Testing_System v2.1 Automated Evaluator & Fuzz Suite
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q

# 4. 200-Case Bilingual NL Parser Corpus
python -B tests/fixtures/nl_cases/validate_cases.py
python -B tests/fixtures/nl_cases/verify_hybrid_200.py

# 5. Benchmarks & Alpha Grid Calibration
python -B tools/benchmarks/benchmark_runner.py
python -B tools/benchmarks/benchmark_alpha_grid.py --include-extreme --save-json

# 6. Windows Quick Wrappers & GUI Studio
.\tools\scripts\run_verification_tests.bat --pass
.\tools\scripts\run_test_studio.bat
```

---

## 3. Reading `clean_runner.py` Console Output

`clean_runner.py` suppresses noisy Pytest warnings (`-p no:terminal`) and prints 3 structured sections:
1. **`[RUNNING]` Signal:** Target suite & start timestamp.
2. **`[PHASE i/N]` Groups:** Files grouped by `tests/ui`, `tests/architecture`, `tests/logical`, `tests/benchmark`.
3. **`[FINAL SUMMARY]`:** Exact pass/fail counts, elapsed seconds, and on failure exact `Point to:` + `Details:` diagnostics.
