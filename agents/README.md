# SmartSchedule — Primary AI Agent Entrypoint (`agents/README.md`)

> [!IMPORTANT]
> **SINGLE ENTRYPOINT FOR ALL AI AGENTS:**
> You only need to read **`agents/README.md`** (this file) to learn the project's active rules of thumb, workspace layout, and invariants — **and you MUST next read [`v1.0-alpha-plan/`](../v1.0-alpha-plan/README_agents.md)** (`v1.0-alpha-plan/README_agents.md` and relevant plans inside [`v1.0-alpha-plan/`](../v1.0-alpha-plan/)) before editing any code!
> Legacy pre-`v1.0-alpha` docs and old Entries `001–015` have been moved to [`agents/archive/`](archive/).

**Project:** SmartSchedule — Personal AI Timetable & Cognitive-Ergonomic Scheduler (`CS252`, Group 03 *The Seven Dwarfs*, FIT-HCMUS)  
**Active Branch:** `v1.0-alpha/ui-ux-chat` | **Human Partner Hub:** [`docs/README.md`](../docs/README.md) & [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md)

---

## 1. Mandatory First Steps Before Coding

1. **Read [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md)** first — it is the master technical index for `v1.0-alpha` (modular codebase map, Chat-First UI/UX, 6-solver algorithmic kernel + Dominant Subset pruning, Online Context-Parsing Model merge, and live task checklists `[x]`/`[ ]`).
2. **Respect Token Discipline ([`environments/.agentignore`](../environments/.agentignore) & [`environments/CODEBASE_INDEX.md`](../environments/CODEBASE_INDEX.md)):** Never dump large files in `data/scenarios/`, `data/calibration/`, `Project_Drafts/`, or `tests/fixtures/nl_cases/` into context. Use [`environments/CODEBASE_INDEX.md`](../environments/CODEBASE_INDEX.md) to locate symbols directly.
3. **Import Paths:** The legacy `group03-smartschedule-baseline/` directory no longer exists. Always run Python from the **repository root** using package paths `smartschedule.*` and `tools.*`, and read shared paths from `smartschedule.core.config` (`CORE_DIR`, `NLP_DIR`, `UI_DIR`, `PRESETS_DIR`, `SCENARIOS_DIR`, `CALIBRATION_DIR`, `DEFAULT_DB_PATH`).

---

## 2. Active Workstreams in `v1.0-alpha`

| Workstream | Core Directories & Entrypoints | Authoritative Specification |
| :--- | :--- | :--- |
| **1. Modular Codebase (`smartschedule/`)** | [`smartschedule/core/`](../smartschedule/core/), [`smartschedule/nlp/`](../smartschedule/nlp/), [`smartschedule/api/`](../smartschedule/api/), [`smartschedule/ui/`](../smartschedule/ui/), [`data/`](../data/), [`tests/`](../tests/), [`tools/`](../tools/) | [`v1.0-alpha-plan/folder_division_plan.md`](../v1.0-alpha-plan/folder_division_plan.md) |
| **2. Chat-First Ultra-Minimal UI/UX** | [`smartschedule/ui/index.html`](../smartschedule/ui/index.html), [`smartschedule/ui/app.js`](../smartschedule/ui/app.js), `ui/js/*.js`, `ui/css/{shell,dev-panel,calendar,chat}.css`, [`smartschedule/api/chat/`](../smartschedule/api/chat/) | [`v1.0-alpha-plan/UI_Rebuild_Plan/agent_pipeline.md`](../v1.0-alpha-plan/UI_Rebuild_Plan/agent_pipeline.md) |
| **3. Context-Parsing Upgrade + SHA-256 Tracer** | [`smartschedule/nlp/clause_condenser.py`](../smartschedule/nlp/clause_condenser.py), [`smartschedule/nlp/context_router.py`](../smartschedule/nlp/context_router.py), [`smartschedule/nlp/parser_controller.py`](../smartschedule/nlp/parser_controller.py), [`smartschedule/core/task_tracer.py`](../smartschedule/core/task_tracer.py) | [`v1.0-alpha-plan/UI_Rebuild_Plan/agent_pipeline.md`](../v1.0-alpha-plan/UI_Rebuild_Plan/agent_pipeline.md) |
| **4. Algorithmic Engine & Verification (`v2.1`)** | [`smartschedule/core/solvers/`](../smartschedule/core/solvers/) (`EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`), [`v1.0-alpha-plan/Testing_System/`](../v1.0-alpha-plan/Testing_System/) | [`v1.0-alpha-plan/Testing_Plan/Testing_Plan.md`](../v1.0-alpha-plan/Testing_Plan/Testing_Plan.md) |

---

## 3. Rules of Thumb & Non-Negotiable Invariants (`INV-1` to `INV-6`)

1. **`INV-1` Strict Layer Purity:** Never import `smartschedule.api`, `smartschedule.nlp`, `fastapi`, or HTTP packages inside `smartschedule/core/solvers/`, `smartschedule/core/models.py`, `smartschedule/core/task_tracer.py`, `calibration.py`, or `ics_importer.py`.
2. **`INV-2` Zero Circular Model Coupling:** `smartschedule/core/models.py` must never import `controller` or `solvers`.
3. **`INV-3` Solver Statelessness & Determinism:** `solve()` must produce bit-identical `determinism_hash` across repeated calls. **Do NOT alter solver math** in `smartschedule/core/solvers/` unless explicitly tasked by the algorithmic spec.
4. **`INV-4` Protected Time Masks:** `SLEEP` and `OCCUPIED` slots on the `672`/`1344`-slot grid can never be overwritten or freed by task operations.
5. **`INV-5` Memory Budget (`< 350 KB` heap delta, `< 10 MB` peak):** Heavy NLP or online context models stay lazy or API-based (`0 MB` local RAM via `google-genai` `GEMINI_API_KEY`) inside Layer 4 `smartschedule/nlp/` / `smartschedule/api/`.
6. **`INV-6` Thread Safety:** Never mutate shared module-level solver state or mix per-request SQLite workspaces (`SMARTSCHEDULE_DB_PATH`).
7. **Verification Before Wrapping Up:** Run from repo root:
   - `python -B tests/clean_runner.py --pass`
   - `python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q`
   - `node --check smartschedule/ui/app.js` (when JS changed)
8. **Bilingual Doc & Dependency Sync:**
   - Check off finished items in [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md) & [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md).
   - Update [`agents/requirements.md`](requirements.md) and [`docs/requirements.md`](../docs/requirements.md) whenever [`environments/requirements.txt`](../environments/requirements.txt) changes.
   - Log approved changes in [`agents/commit_changes.md`](commit_changes.md) and [`docs/commit_changes.md`](../docs/commit_changes.md). Do **not** commit if the user asks for an uncommitted working tree.
