# SmartSchedule `v1.0-alpha` — Compact Codebase Index (< 4 KB)

Use this lookup table to jump straight to the exact file instead of scanning directories.

| What You Want to Work On | Exact File / Folder |
| :--- | :--- |
| **AI Agent Onboarding & Rules** | [`agents/README.md`](agents/README.md) · [`v1.0-alpha-plan/README_agents.md`](v1.0-alpha-plan/README_agents.md) |
| **Vietnamese Team Roadmap & Checklists** | [`v1.0-alpha-plan/README.md`](v1.0-alpha-plan/README.md) · [`docs/README.md`](docs/README.md) |
| **Chat UI & Thinking Stage (Frontend)** | [`smartschedule/ui/js/chat-assistant.js`](smartschedule/ui/js/chat-assistant.js) · [`smartschedule/ui/css/chat.css`](smartschedule/ui/css/chat.css) |
| **Weekly Calendar & Drag/Drop (Frontend)** | [`smartschedule/ui/js/render-calendar.js`](smartschedule/ui/js/render-calendar.js) · [`smartschedule/ui/css/calendar.css`](smartschedule/ui/css/calendar.css) |
| **App State, Bootstrap & Topbar Shell** | [`smartschedule/ui/index.html`](smartschedule/ui/index.html) · [`smartschedule/ui/app.js`](smartschedule/ui/app.js) · [`smartschedule/ui/js/state.js`](smartschedule/ui/js/state.js) |
| **Online Context-Parsing Model (`Gemini Flash-Lite`)** | [`smartschedule/nlp/context_router.py`](smartschedule/nlp/context_router.py) |
| **Clause Condenser & Cross-Day Window Parser** | [`smartschedule/nlp/clause_condenser.py`](smartschedule/nlp/clause_condenser.py) |
| **Dual-Engine M1 & 6-Stage Hybrid NL Parser** | [`smartschedule/nlp/parser_controller.py`](smartschedule/nlp/parser_controller.py) · [`smartschedule/nlp/hybrid_pipeline/`](smartschedule/nlp/hybrid_pipeline/hybrid_parser.py) |
| **Conversational Turn Handlers, Thinking Stage & Edge Cases** | [`smartschedule/api/chat/handlers.py`](smartschedule/api/chat/handlers.py) · [`thinking_stage.py`](smartschedule/api/chat/thinking_stage.py) · [`edge_cases.py`](smartschedule/api/chat/edge_cases.py) |
| **FastAPI REST Endpoints** | [`smartschedule/api/app.py`](smartschedule/api/app.py) |
| **`v2.1` Telemetry, Showcase & Regimes API Bridge** | [`smartschedule/api/health_v21.py`](smartschedule/api/health_v21.py) · [`v3_services.py`](smartschedule/api/v3_services.py) · [`test_showcase.py`](smartschedule/api/test_showcase.py) |
| **Core Models, Paths, Grid & Controller (`Layer 1–3`)** | [`smartschedule/core/models.py`](smartschedule/core/models.py) · [`config.py`](smartschedule/core/config.py) · [`controller.py`](smartschedule/core/controller.py) · [`grid_manager.py`](smartschedule/core/grid_manager.py) |
| **SHA-256 Task Tracer & Hidden Criteria** | [`smartschedule/core/task_tracer.py`](smartschedule/core/task_tracer.py) |
| **6 Optimization Solvers (`EDF`, `WSPT`, `LST`, `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`)** | [`smartschedule/core/solvers/`](smartschedule/core/solvers/registry.py) |
| **Fallacy Buffer, EWMA Calibration & SQLite Storage** | [`smartschedule/core/estimate_buffer.py`](smartschedule/core/estimate_buffer.py) · [`calibration.py`](smartschedule/core/calibration.py) · [`storage.py`](smartschedule/core/storage.py) |
| **Presets (`minh`/`lan`) & Scenarios (`T01–T10`)** | [`data/presets/`](data/presets/sample_week_tasks.json) · [`data/scenarios/`](data/scenarios/t01_normal_feasible.json) |
| **Verification Test Runner & Suites (`194+` tests)** | [`tests/clean_runner.py`](tests/clean_runner.py) (`python -B tests/clean_runner.py --pass`) |
| **4-Pillar Health Evaluator & FuzzGenerator (`39` tests)** | [`v1.0-alpha-plan/Testing_System/`](v1.0-alpha-plan/Testing_System/README.md) (`python -B -m pytest v1.0-alpha-plan/Testing_System/tests -q`) |
| **Blind Member Evaluator (Port `8010`) & Benchmarks** | [`tools/member_eval/`](tools/member_eval/app.py) · [`tools/benchmarks/`](tools/benchmarks/benchmark_runner.py) |
| **Docker & Windows Batch Scripts** | [`tools/docker/docker-compose.yml`](tools/docker/docker-compose.yml) · [`tools/scripts/`](tools/scripts/run_app.bat) |
