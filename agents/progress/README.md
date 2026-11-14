# SmartSchedule — Agents Progress Documentation Index

**Directory:** `agents/progress/`  
**Purpose:** Comprehensive Knowledge Base for AI Coding Agents assisting Group 03  
**Target:** All AI Agents & Developers working on SmartSchedule  

---

## Document Index

1. **[`system_architecture.md`](file:///d:/Projects/Computational-Thinking---Group-Project/agents/progress/system_architecture.md)**
   - Explains the 5-layer decoupled architecture (Models, Solvers, Controller, Web/Delivery, Verification).
   - Details the 6 strict system invariants (`INV-1` to `INV-6`) that must never be violated.
   - Contains mermaid component diagram and data flow specifications.

2. **[`baseline_plan.md`](file:///d:/Projects/Computational-Thinking---Group-Project/agents/progress/baseline_plan.md)**
   - Details the Baseline V0 specification from `Baseline_Plan/baseline_plan.md`.
   - Explains the 672-slot discrete grid ($7 \times 24 \times 4$), 15-minute slot math, and enum states.
   - Formalizes the 5 hard constraints ($H_1$ to $H_5$) and the three greedy solvers (EDF, LST, WSPT).
   - Summarizes the 10 benchmark scenarios (T01–T10).

3. **[`improved_plan.md`](file:///d:/Projects/Computational-Thinking---Group-Project/agents/progress/improved_plan.md)**
   - Details the user-facing and cognitive upgrades from `Improve_Plan/improve_plan.md`.
   - Outlines the 7 student moments ($M_1$ to $M_7$).
   - Explains circadian energy matching, 15m rest breaks, planning buffer multipliers ($1.25\times$), overload habit skipping, and the ISO-8601 JSON Data Contract (§7.3).
   - Lists the 5 intentional developmental gap tests tracking upcoming sprint deliverables.

4. **[`verification_and_benchmarks.md`](file:///d:/Projects/Computational-Thinking---Group-Project/agents/progress/verification_and_benchmarks.md)**
   - Complete inventory and architecture of the 56 automated verification tests.
   - Explains the 60% average passing cases / 40% edge cases & developmental failures matrix.
   - Documents the Interpretable Test Runner (`clean_runner.py`), the GUI Test Studio (`test_studio.py`), and CLI execution batch files.

5. **[`requirements.md`](file:///d:/Projects/Computational-Thinking---Group-Project/agents/requirements.md)**
   - Comprehensive environment & package breakdown (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `python-dateutil`).
   - Architectural layer scoping for each dependency and standard library utilities (`ast`, `tracemalloc`, `tkinter`).
   - Mandatory simultaneous update instructions.

---

## Quick Navigation to Commit Log
For the active change log and mandatory synchronization instructions for AI agents, refer to:
👉 **[`agents/commit_changes.md`](file:///d:/Projects/Computational-Thinking---Group-Project/agents/commit_changes.md)**

