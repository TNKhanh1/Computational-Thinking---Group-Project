# Progress Documentation Index (`agents/progress/`)

> [!IMPORTANT]
> **Start at [`agents/README.md`](../README.md) and [`v1.0-alpha-plan/README_agents.md`](../../v1.0-alpha-plan/README_agents.md)** for active `v1.0-alpha` roadmaps, codebase layout, and live checklists. Historical pre-`v1.0-alpha` plans live in [`agents/archive/`](../archive/).

---

## Active Reference Guides (`agents/progress/`)

1. **[`v1.0-alpha-plan/README_agents.md`](../../v1.0-alpha-plan/README_agents.md)** — **Primary Active Blueprint (`v1.0-alpha`)**
   - Modular layout (`smartschedule/`, `data/`, `tests/`, `tools/`, `environments/`), Chat-First UI/UX, Merged Online + Clause Context Parser, 6-solver kernel, and active execution checklists.
2. **[`system_architecture.md`](system_architecture.md)**
   - Deep-dive into the 5-layer dependency model and Architectural Invariants `INV-1` through `INV-6`.
3. **[`verification_and_benchmarks.md`](verification_and_benchmarks.md)**
   - Guide to `tests/` verification layers, `tests/clean_runner.py`, Test Studio, and `Testing_System v2.1` + `T01–T10` benchmarks.
4. **[`feature_001_estimate_buffer.md`](feature_001_estimate_buffer.md)**
   - Mathematical & behavioral specification of Planning-Fallacy buffering (`smartschedule/core/estimate_buffer.py`).
5. **[`hybrid_nl_parser.md`](hybrid_nl_parser.md)**
   - Hybrid 6-stage EN/VI NL pipeline merged with `v1.0-alpha` online lightweight context parsing (`context_router.py` + `clause_condenser.py`).
