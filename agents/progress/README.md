# SmartSchedule — Agents Progress Documentation Index

**Directory:** `agents/progress/`  
**Purpose:** Comprehensive Knowledge Base for AI Coding Agents assisting Group 03  
**Target:** All AI Agents & Developers working on SmartSchedule  

---

## Document Index

1. **[`system_architecture.md`](system_architecture.md)**
   - Explains the 5-layer decoupled architecture (Models, Solvers, Controller, Web/Delivery, Verification).
   - Details the 6 strict system invariants (`INV-1` to `INV-6`) that must never be violated.
   - Contains mermaid component diagram and data flow specifications.

2. **[`baseline_plan.md`](baseline_plan.md)**
   - Details the Baseline V0 specification from `Baseline_Plan/baseline_plan.md`.
   - Explains the 672-slot discrete grid ($7 \times 24 \times 4$), 15-minute slot math, and enum states.
   - Formalizes the 5 hard constraints ($H_1$ to $H_5$) and the three greedy solvers (EDF, LST, WSPT).
   - Summarizes the 10 benchmark scenarios (T01–T10).

3. **[`improved_plan.md`](improved_plan.md)**
   - Details the user-facing and cognitive upgrades from `Improve_Plan/improve_plan.md`.
   - Outlines the 7 student moments ($M_1$ to $M_7$).
   - Explains circadian energy matching, 15m rest breaks, planning buffer multipliers ($1.25\times$), overload habit skipping, and the ISO-8601 JSON Data Contract (§7.3).
   - Lists the 5 intentional developmental gap tests tracking upcoming sprint deliverables.

4. **[`verification_and_benchmarks.md`](verification_and_benchmarks.md)**
   - Complete inventory and architecture of the 89 automated verification tests (84 passed + 1 passed gap + 4 open gaps).
   - Explains the 60% average passing cases / 40% edge cases & developmental failures matrix.
   - Documents the Interpretable Test Runner (`clean_runner.py`), the GUI Test Studio (`test_studio.py`), and CLI execution batch files.

5. **[`requirements.md`](../requirements.md)**
   - Comprehensive environment & package breakdown (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `python-dateutil`).
   - Architectural layer scoping for each dependency and standard library utilities (`ast`, `tracemalloc`, `tkinter`).
   - Mandatory simultaneous update instructions.

6. **[`feature_001_estimate_buffer.md`](feature_001_estimate_buffer.md)**
   - Specification, integer rounding formulation, architecture, and 34 verification tests for the Planning Fallacy estimate buffer ($1.00\times$, $1.10\times$, $1.25\times$).
   - Explains non-compounding overrun simulation and zero-regression baseline compatibility.

7. **[`student_mode_ui.md`](student_mode_ui.md)**
   - Dual-Mode Architecture (Student Mode vs. Lab Mode), 3 student calendar views (Week, Today "Now & Next", Task Queue).
   - Interactive block controls: Pinning (📌), Check-in (✔️), and "Why here? 💡" algorithmic explainability modal.

---

## Quick Navigation to Commit Log
For the active change log and mandatory synchronization instructions for AI agents, refer to:
👉 **[`agents/commit_changes.md`](../commit_changes.md)**
