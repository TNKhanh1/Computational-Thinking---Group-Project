# SmartSchedule — Environment & Dependency Specifications

**Project:** SmartSchedule — Personal Productivity Assistant  
**Target Audience:** AI Coding Assistants & System Engineers  
**Location:** `agents/requirements.md`  
**Reference File:** `group03-smartschedule-baseline/requirements.txt`  

---

> [!IMPORTANT]
> ## 🚨 MANDATORY DEPENDENCY & DOCUMENTATION SYNC RULE
> Whenever any AI agent or team member introduces, updates, or removes an external Python package:
> 1. Update `group03-smartschedule-baseline/requirements.txt` with pinned or minimum version constraints.
> 2. **Simultaneously update both:**
>    - `agents/requirements.md` (this file, in English)
>    - `docs/requirements.md` (the companion file, in Vietnamese)
> 3. Document the rationale for the dependency, which architectural layer it belongs to, and record the change in `agents/commit_changes.md` and `docs/commit_changes.md`.

---

## 1. Runtime Environment Specifications

| Component | Minimum Version | Recommended Version | Notes |
| :--- | :--- | :--- | :--- |
| **Python** | `Python >= 3.10` | `Python 3.12+` (or 3.14) | Tested on CPython 3.12 and 3.14 (Win32 / x64). |
| **Operating System** | Cross-platform | Windows 10/11, macOS, Linux | All paths use `pathlib.Path` for cross-platform safety. |
| **GUI Framework** | Tkinter | Python standard `tkinter` | Native desktop UI for `test_studio.py` (comes bundled with standard Python on Windows/macOS). |

---

## 2. External Package Inventory (`requirements.txt`)

Below is the complete inventory of external packages specified in [`requirements.txt`](file:///d:/Projects/Computational-Thinking---Group-Project/group03-smartschedule-baseline/requirements.txt):

```text
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
pytest>=7.4.0
httpx>=0.24.0
python-dateutil>=2.8.2
```

### Detailed Breakdown & Architectural Layer Scoping

#### 1. `fastapi>=0.100.0`
- **Purpose:** High-performance, modern web framework for building REST APIs with standard Python type hints.
- **Architectural Scope:** **Layer 4: Delivery / Interface ONLY** (`web/api.py`).
- **Used For:** Exposing HTTP endpoints (`/api/solve`, `/api/presets`, `/api/validate-move`, `/api/export/{fmt}`).
- **Strict Constraint:** **NEVER** import into Layer 1 (`src/models.py`) or Layer 2 (`src/solvers/`). Violating this triggers an instant architectural failure in `test_system_architecture.py`.

#### 2. `uvicorn>=0.23.0`
- **Purpose:** Lightning-fast ASGI (Asynchronous Server Gateway Interface) web server implementation for Python.
- **Architectural Scope:** **Layer 4: Server Runtime** (`web/` and CLI startup scripts).
- **Used For:** Hosting the FastAPI web application and serving the static Technical Workbench (`web/static/`).
- **Standard Command:** `uvicorn web.api:app --host 127.0.0.1 --port 8000`.

#### 3. `pydantic>=2.0.0`
- **Purpose:** Data validation and data transformation library using Python type annotations.
- **Architectural Scope:** **Layer 1: Pure Data Models** (`src/models.py`) and API schemas.
- **Used For:**
  - Defining `CommitmentsProfile`, `Task`, `FixedEvent`, `SleepSchedule`, and `ScheduleOutput`.
  - Automatic validation of field constraints (e.g. `duration_min > 0`, `1 <= priority <= 5`).
  - Serializing and deserializing JSON payloads compliant with the ISO-8601 Data Contract (Improve Plan §7.3).

#### 4. `pytest>=7.4.0`
- **Purpose:** Scalable testing framework for unit, integration, invariant, and benchmark testing.
- **Architectural Scope:** **Layer 5: Verification Infrastructure** (`verification_tests/`).
- **Used For:**
  - Running the 56 automated verification tests across `ui_tests/`, `architecture_tests/`, `logical_tests/`, `benchmark_tests/`, and `development_gap_tests/`.
  - Driven cleanly via `verification_tests/clean_runner.py` with custom plugin hooks (`InterpretableConsolePlugin`).

#### 5. `httpx>=0.24.0`
- **Purpose:** Fully featured HTTP client library for Python.
- **Architectural Scope:** **Layer 5: Verification & Contract Testing** (`verification_tests/ui_tests/`).
- **Used For:**
  - Underpins FastAPI's `TestClient` (`from fastapi.testclient import TestClient`).
  - Enables in-memory, zero-network HTTP testing of all REST API endpoints without needing to launch a background server process.

#### 6. `python-dateutil>=2.8.2`
- **Purpose:** Robust extensions to the standard Python `datetime` module.
- **Architectural Scope:** **Layer 1 & Layer 4** (`src/utils.py`, `src/models.py`, `web/api.py`).
- **Used For:**
  - Parsing ISO-8601 timestamps and calendar date strings (`dateutil.parser.isoparse`).
  - Calculating relative week start dates (`datetime + timedelta`) and timezone offset calculations (`+07:00`).

---

## 3. Standard Library Modules Utilized (Zero-Install)

The project leverages Python's standard library extensively to minimize external attack surface:
- **`ast`:** Abstract Syntax Tree parsing for architectural boundary enforcement (`test_system_architecture.py`).
- **`tracemalloc`:** Deterministic heap allocation profiler for memory leak detection (`test_memory_leaks.py`).
- **`threading`:** Used in `test_studio.py` for background test execution and `test_production_failures.py` for multi-threaded concurrency safety.
- **`argparse`:** CLI parameter parsing for `clean_runner.py` and `main.py`.
- **`pathlib`:** Object-oriented cross-platform filesystem path manipulation.
- **`hashlib`:** Cryptographic SHA-256 schedule hashing for determinism proofs.
- **`tkinter`:** Native GUI desktop interface for `test_studio.py`.

---

## 4. Environment Setup Instructions

### 4.1. Automatic Setup (Windows)
Double-click `group03-smartschedule-baseline/setup_env.bat` or run:
```bat
cd group03-smartschedule-baseline
setup_env.bat
```

### 4.2. Manual Installation
```bash
cd group03-smartschedule-baseline

# 1. Create virtual environment
python -m venv .venv

# 2. Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# 3. Upgrade pip and install
python -m pip install --upgrade pip
pip install -r requirements.txt
```

