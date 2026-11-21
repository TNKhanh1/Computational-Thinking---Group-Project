# SmartSchedule — Project Environments, Tooling Config & Agent Context Files (`environments/`)

This folder groups **all repository-level environment, packaging, dependency, secret template, and AI-workspace configuration files** so the repository root stays clean with only [`.gitignore`](../.gitignore) and [`README.md`](../README.md).

---

## Contents & Purpose

| File | Category | Purpose & How to Use It |
| :--- | :--- | :--- |
| **[`requirements.txt`](requirements.txt)** | Python Runtime Environment | Core runtime dependencies (`fastapi`, `uvicorn`, `pydantic`, `httpx`, `python-dateutil`, `pytest`, `PyYAML`, `google-genai`, `python-dotenv`). Installed via `pip install -r environments/requirements.txt` or `.\tools\scripts\setup_env.bat`. |
| **[`requirements-nllb.txt`](requirements-nllb.txt)** | Optional Offline NLP Environment | Heavy local neural translation packages (`ctranslate2`, `sentencepiece`, `huggingface-hub`) separated from core runtime to avoid ~2 GB downloads unless offline NLLB translation is explicitly enabled. |
| **[`pyproject.toml`](pyproject.toml)** | Python Packaging & Pytest Config | Package discovery (`smartschedule*`, `tools*`) and Pytest `pythonpath` settings (`python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q`). |
| **[`.env.example`](.env.example)** / **`.env`** | Environment Variables & Secrets | Template (`.env.example`) for local secrets (`GEMINI_API_KEY`, `NL_PARSER_ENGINE`, `GEMINI_MODEL`). Copy to `environments/.env` (gitignored). Loaded automatically by `smartschedule/nlp/parser_controller.py` and `context_router.py`. |
| **[`.agentignore`](.agentignore)** | AI Agent Scan Environment | Excludes bulky PDFs, images, SQLite databases, YAML NL fixtures, and archived drafts from AI code scans to minimize token overhead. |
| **[`CODEBASE_INDEX.md`](CODEBASE_INDEX.md)** | AI Agent Navigation Index | Compact symbol & directory lookup map for AI assistants working inside `smartschedule/`, `data/`, `tests/`, and `tools/`. |

---

## Quick Environment Setup (From Repository Root)

```powershell
# 1. Automated .venv setup & dependency install on Windows
.\tools\scripts\setup_env.bat

# 2. Manual installation
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r environments/requirements.txt

# 3. Enable online Gemini context-parsing model (optional — offline fallback always works)
Copy-Item environments/.env.example environments/.env
# Add your GEMINI_API_KEY=... inside environments/.env

# 4. Run Testing_System v2.1 tests with explicit environment config
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
```
