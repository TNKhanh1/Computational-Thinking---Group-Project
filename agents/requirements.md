# SmartSchedule — Project Dependencies, Architecture Boundaries & AI Workspace Rules (`agents/requirements.md`)

**Project:** SmartSchedule (`v1.0-alpha` Modular Layout)  
**Dependency Source Files:** [`environments/requirements.txt`](../environments/requirements.txt) & [`environments/requirements-nllb.txt`](../environments/requirements-nllb.txt) (inside [`environments/`](../environments/); [`environments/pyproject.toml`](../environments/pyproject.toml) defines packages `smartschedule*` and `tools*`)  
**Audience:** Developers & All AI Coding Assistants

> [!IMPORTANT]
> **MANDATORY AGENT RULES (`v1.0-alpha`):**
> 1. **Single Onboarding Rule:** Agents must start by reading [`agents/README.md`](README.md) and **MUST read [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md)** before modifying any source file.
> 2. **Token Efficiency Rule:** Respect [`environments/.agentignore`](../environments/.agentignore) and consult [`environments/CODEBASE_INDEX.md`](../environments/CODEBASE_INDEX.md) before scanning files. Do **not** load large benchmark JSON/YAML corpora (`data/scenarios/`, `data/calibration/`, `tests/fixtures/`) or `Project_Drafts/` PDFs unless specifically needed.
> 3. **Clean Root & Legacy Folder Ban:** Only `.gitignore` and `README.md` live as loose files at repo root; all environment/config files belong in [`environments/`](../environments/), historical course drafts belong in [`Project_Drafts/`](../Project_Drafts/), and never recreate `group03-smartschedule-baseline/`, `src/`, `web/`, or `verification_tests/`.
> 4. **Simultaneous Dependency Sync Rule:** Whenever you add, update, or remove a library in [`environments/requirements.txt`](../environments/requirements.txt) or [`environments/requirements-nllb.txt`](../environments/requirements-nllb.txt), **simultaneously update both [`agents/requirements.md`](requirements.md) and [`docs/requirements.md`](../docs/requirements.md)** with its version, purpose, and allowed architectural layer.

---

## 1. Production Dependencies ([`environments/requirements.txt`](../environments/requirements.txt))

| Package | Version | Architectural Layer | Permitted Scope & Purpose |
| :--- | :---: | :--- | :--- |
| **`fastapi`** | `>=0.115.0` | **Layer 4 (`smartschedule/api/`, `tools/member_eval/`)** | REST API routing, request/response serialization, OpenAPI docs, static UI mount. **Strictly forbidden in `smartschedule/core/` (`INV-1`).** |
| **`uvicorn[standard]`** | `>=0.30.0` | **Layer 4 (CLI / Server)** | High-speed ASGI server invoked by `python -B -m smartschedule.main --serve` and `tools/scripts/run_app.bat`. |
| **`pydantic`** | `>=2.8.0` | **Layer 1 & 4** | Strictly typed domain contracts in [`smartschedule/core/models.py`](../smartschedule/core/models.py) and structured online LLM schemas in [`smartschedule/nlp/`](../smartschedule/nlp/). |
| **`httpx`** | `>=0.27.0` | **Layer 4 & 5 (`tests/`, `smartschedule/nlp/`)** | FastAPI `TestClient` backend + optional async/sync HTTPS calls to online Open-Weights context-parsing endpoints (`CONTEXT_MODEL_URL`). **Forbidden in `smartschedule/core/` (`INV-1`).** |
| **`python-dateutil`** | `>=2.9.0` | **Layer 1 / 3 / 4** | ISO-8601 datetime & timezone arithmetic. |
| **`pytest`** | `>=8.0.0` | **Layer 5 (`tests/`, `v1.0-alpha-plan/Testing_System/tests/`)** | Automated verification runner orchestrated by [`tests/clean_runner.py`](../tests/clean_runner.py). |
| **`PyYAML`** | `>=6.0` | **Layer 4 & 5** | Loads the 200-case bilingual NL corpus in `tests/fixtures/nl_cases/` (`verify_hybrid_200.py`). |
| **`google-genai`** | `>=1.0.0` | **Layer 4 (`smartschedule/nlp/` ONLY)** | Calls Google Gemini structured JSON extraction (`GEMINI_API_KEY`) for **NL Task Parsing (`gemini-3-flash-preview`)** and the **`v1.0-alpha` Online Lightweight Context-Parsing Model (`gemini-2.5-flash-lite` / `gemini-2.5-flash`, `0 MB` local RAM, `thinking_budget=0`)**. Never imported in `smartschedule/core/`. |
| **`python-dotenv`** | `>=1.0.0` | **Layer 4 (`smartschedule/nlp/parser_controller.py`)** | Automatically loads `environments/.env` (`GEMINI_API_KEY`) in local development while keeping `.env` gitignored. |

---

## 2. Optional Heavy Offline Translation Dependencies ([`environments/requirements-nllb.txt`](../environments/requirements-nllb.txt))

Only required if explicitly running offline CTranslate2 neural translation (`backend="nllb"` / `"opus_mt"`). Kept out of [`environments/requirements.txt`](../environments/requirements.txt) to avoid ~2 GB downloads and preserve the **zero-RAM default**.

| Package | Version | Architectural Layer | Purpose |
| :--- | :---: | :--- | :--- |
| **`ctranslate2`** | `>=4.5.0` | Layer 4 Lazy Import (`smartschedule/nlp/hybrid_pipeline/translator.py`) | Quantized offline NLLB/Marian inference. |
| **`sentencepiece`** | `>=0.2.0` | Layer 4 Lazy Import | Subword tokenizer for CTranslate2 models. |
| **`huggingface-hub`** | `>=0.25.0` | Layer 4 Lazy Import | Downloads NLLB-200 / Opus-MT weights when explicitly requested. |

---

## 3. Zero-Dependency Standard Library Core (`INV-1` & `INV-5` Compliance)

`smartschedule/core/` and verification/developer utilities rely purely on Python 3.10+ stdlib:
- **`sqlite3`** (`smartschedule/core/storage.py` $\to$ `data/runtime/local_state.db`)
- **`hashlib`** (`smartschedule/core/task_tracer.py` SHA-256 keyword fingerprinting, solver determinism hashes)
- **`ast` / `tracemalloc` / `threading`** (`tests/architecture/` invariant & memory leak checks `< 350 KB`)
- **`tkinter`** (`tests/test_studio.py`)

---

## 4. Environment & Quick Installation

```powershell
# From repository root:
.\tools\scripts\setup_env.bat                         # Creates .venv and installs environments/requirements.txt
Copy-Item environments/.env.example environments/.env  # Optional: add GEMINI_API_KEY for online context model
python -B -m smartschedule.main --serve
```
