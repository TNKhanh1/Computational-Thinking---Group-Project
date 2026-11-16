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

Below is the complete inventory of external packages specified in [`requirements.txt`](../group03-smartschedule-baseline/requirements.txt):

```text
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
pytest>=7.4.0
httpx>=0.24.0
python-dateutil>=2.8.2
google-genai>=0.1.0
python-dotenv>=1.0.0
PyYAML>=6.0
ctranslate2>=4.5.0
sentencepiece>=0.2.0
huggingface-hub>=0.25.0
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
- **Used For:** Hosting the FastAPI web application and serving the Dual-Mode Web Workbench (`web/index.html`, `web/app.js`).
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
  - Running **141 pytest verification tests** (`136` `--pass` operational including M1 Hybrid NL & unbiased generalization + `5` `--gaps` Improve Plan feature tests) across `ui_tests/`, `architecture_tests/`, `logical_tests/`, `benchmark_tests/`, and `development_gap_tests/`.
  - Driven cleanly via `verification_tests/clean_runner.py` with custom plugin hooks (`InterpretableConsolePlugin`).

#### 5. `httpx>=0.24.0`
- **Purpose:** Fully featured HTTP client library for Python.
- **Architectural Scope:** **Layer 5: Verification & Contract Testing** (`verification_tests/ui_tests/`).
- **Used For:**
  - Underpins FastAPI's `TestClient` (`from fastapi.testclient import TestClient`).
  - Enables in-memory, zero-network HTTP testing of all REST API endpoints without needing to launch a background server process.

#### 6. `python-dateutil>=2.8.2`
- **Purpose:** Robust extensions to the standard Python `datetime` module.
- **Architectural Scope:** **Layer 1 & Layer 4** (`src/utils.py`, `src/models.py`, `web/api.py`, `NL_Parser_Package/`).
- **Used For:**
  - Parsing ISO-8601 timestamps and calendar date strings (`dateutil.parser.isoparse`).
  - Calculating relative week start dates (`datetime + timedelta`) and timezone offset calculations (`+07:00`).

#### 7. `google-genai>=0.1.0` & `python-dotenv>=1.0.0` (Optional Cloud LLM NL Mode)
- **Purpose:** Google Gemini structured JSON extraction SDK and `.env` loader (`GEMINI_API_KEY`).
- **Architectural Scope:** **Layer 4: NL Adapter (`src/nl_parser.py`)**.
- **Used For:** Powering optional `AI_GEMINI` extraction in `NLParserController` while automatically falling back to zero-network `OFFLINE_DETERMINISTIC` + Hybrid 6-Stage parsing when offline or unconfigured.

#### 8. `ctranslate2>=4.5.0`, `sentencepiece>=0.2.0` & `huggingface-hub>=0.25.0` (Offline Neural VI→EN Translation)
- **Purpose:** Fast quantized neural machine translation runtime (`NLLB-200` / `Opus-MT`), subword tokenizer, and local model hub downloader.
- **Architectural Scope:** **Layer 4: NL Package (`NL_Parser_Package/translator.py`)**.
- **Used For:** Translating Vietnamese prompts into structured English inside `NL_Parser_Package/hybrid_parser.py` (`backend="nllb"` / `"opus_mt"`), with instant stdlib `backend="rule"` fallback if weights or libraries are absent.

#### 9. `PyYAML>=6.0`
- **Purpose:** YAML parser for loading structured NLP verification datasets.
- **Architectural Scope:** **Layer 5: Verification (`verification_tests/NL_Parser_test_cases/`)**.
- **Used For:** Parsing the 200-case hybrid NLP evaluation suite (`validate_cases.py`, `verify_hybrid_200.py`).

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

