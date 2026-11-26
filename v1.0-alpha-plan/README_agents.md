# SmartSchedule `v1.0-alpha` — Master Agent Execution & Zero-Conflict Sprint Plan (`v1.0-alpha-plan/README_agents.md`)

> [!IMPORTANT]
> **MANDATORY INSTRUCTIONS FOR ALL AI CODING AGENTS (7-MEMBER FINAL `v1.0-alpha` SPRINT):**
> 1. **Identify Your Assigned Member (`M1`–`M7`) First:** Ask your human user which team member they are (or infer from their branch/request), then **immediately read ONLY their dedicated brief in [`Sprint_Tasks/`](Sprint_Tasks/)** *(Note: Core Technical Trio **`M7`, `M5`, `M4`** owns all deep algorithmic, simulation, cross-week adaptation & verification tasks; **`M1`, `M2`, `M3`, `M6`** stay strictly lightweight)*:
>    - [`M1_Pham_Duc_Minh.md`](Sprint_Tasks/M1_Pham_Duc_Minh.md) — Leader (`25125028` · *Lightweight*): First-Time Onboarding (Empty Real Week vs. Sample I/O Preset), User Profile Popover & Wave 2B/3 Integration
>    - [`M2_Tran_Nguyen_Khanh.md`](Sprint_Tasks/M2_Tran_Nguyen_Khanh.md) — Thinker 1 (`25125019` · *Lightweight*): Free Lazy-Loaded Negation/Context Helper (`avoid_windows`) & `14 Patterns -> Rule` Thinking Stage Formatter
>    - [`M3_Hoang_Minh_Anh.md`](Sprint_Tasks/M3_Hoang_Minh_Anh.md) — Thinker 2 (`25125001` · *Lightweight*): Conversational Sleep (`P6`)/Chronotype (`P3`)/`PersonalHabit` Coach & 7-Member Blind Evaluation (`Calibration_Report.md`)
>    - [`M4_Nguyen_Trong_Tien.md`](Sprint_Tasks/M4_Nguyen_Trong_Tien.md) — Thinker 3 (`25125037` · **Core Verify & Router Lead**): Grounded `handlers.py` Router (`DELETE`, `COMPLETE`, `DAG`, `ADAPT_NEXT_WEEK`, Doc-Conflict Chips) & **Independent Claude-Plan Mathematical Verification** of `M5` & `M7`
>    - [`M5_Le_Tien_Binh.md`](Sprint_Tasks/M5_Le_Tien_Binh.md) — Builder 1 (`25125007` · **Core Coding Lead**): `CrossWeekPreferenceAdapter` (`P13`: Category Shrinkage Fallacy Buffer & Revealed-Preference Next-Week Learning), `LOCAL_INSERTION` Disruption Chat (`P8`), & Adaptation/Simulation/CRUD APIs
>    - [`M6_Le_Minh_Nhat.md`](Sprint_Tasks/M6_Le_Minh_Nhat.md) — Builder 2 (`25125032` · *Lightweight Pure UI JS*): `📎` File Upload UI Hook, Chat Persistence across `F5`, 1-Click Undo, Item Delete UI & `Pattern -> Rule` Badges
>    - [`M7_Nguyen_Nguyen_Gia_Bao.md`](Sprint_Tasks/M7_Nguyen_Nguyen_Gia_Bao.md) — Builder 3 (`25125006` · **Core Coding & Idea Lead**): `InSilicoStudentSimulator` (`P14b` 5-Equation Multi-Week Behavioral Twin), `doc_attachment_parser.py` (`P14a` Logical Syllabus-to-DAG Digest), Mobile CSS, `INV-1..6` Guardrails & Full E2E Gate
> 2. **Strict Zero-Conflict File Lock:** Never edit files outside the *Exclusive File Ownership* section of your member's brief. Do **NOT** modify `agents/commit_changes.md`, `docs/commit_changes.md`, or `v1.0-alpha-plan/README*.md` on feature branches — tick `[x]` checkboxes **only** inside your member's `Sprint_Tasks/M<k>_*.md` file!

---

## 1. Sprint Timeline & Conflict-Free Merge Order (Thu Nov 26 $\to$ Sun Morning Nov 29, 2026)

| Wave | Window (`UTC+7`) | PR Merge Order & Owner | Scope & Why Merge Conflicts = `0%` |
| :--- | :--- | :--- | :--- |
| **Wave 0** | **Thu Nov 26, `22:30–23:59`** | All 7 Members (`git checkout -b v1.0-alpha/m<k>-...` from `main`) | Shared plug-in function signatures frozen below; zero overlapping files assigned. |
| **Wave 1A** | **Fri Nov 27 (`10:00–23:00`)** | **1st:** `M5` (Lê Tiến Bình — `cross_week_adapter.py` + `controller.py` + `app.py` + `disruption_chat.py`)<br>**2nd:** `M7-Core` (Gia Bảo — `student_simulator.py` + `doc_attachment_parser.py`) | Core Trio lays down Pure Layer 1 adaptation/simulation engines & Layer 4 document parser in 100% disjoint files. |
| **Wave 1B** | **Sat Nov 28 (`08:00–12:30`)** | **3rd:** `M2` (Khánh — lightweight negation + `thinking_stage.py`)<br>**4th:** `M3` (Minh Anh — `profile_habit_chat.py`)<br>**5th:** `M4` (Trọng Tiến — `handlers.py` grounded router + **Claude-Plan Verification Audit** of `M5` & `M7`) | `handlers.py` safely wires `M5`/`M7`/`M3` via `try/except ImportError`; `M4` verifies mathematical invariants before UI waves. |
| **Wave 2A** | **Sat Nov 28, `08:00–19:00`** | **5th:** `M6` (Lê Minh Nhật — Sat `19:00`) | Owns component JS modules exclusively (`undo-history.js`, `chat-assistant.js`, `modals.js`, `render-list.js`, `state.js`, `api.js`) without touching `index.html` or `app.js`. |
| **Wave 2B** | **Sat Nov 28, `19:00–22:30`** | **6th:** `M1` (Phạm Đức Minh — Sat `22:00`)<br>**7th:** `M7` (Nguyễn Nguyễn Gia Bảo — Sat `22:30`) | Rebased onto Wave 1 + Wave 2A: `M1` owns `index.html` + `app.js` + `onboarding.*`; `M7` owns `css/{shell,calendar,chat}.css` + `tests/architecture/*` + E2E tests. |
| **Wave 3** | **Sat Nov 28 `22:30` $\to$ Sun Nov 29 `10:00`** | **All 7** (Blind Eval on `:8010`) $\to$ **`M3`** (`Calibration_Report.md` Sun `09:00`) $\to$ **`M7`** (QA Gate Sun `09:30`) $\to$ **`M1`** (Tag `v1.0-alpha` Sun `10:00`) | Final human-vs-`v2.1` calibration, `clean_runner.py --pass` + `Testing_System` verification, single consolidated `commit_changes.md` entry, and `v1.0-alpha` tag. |

---

## 2. Shared Cross-Module Plug-In Contracts (Frozen at Wave 0)

To let **Wave 1 (`M2`, `M3`, `M4`, `M5`)** and **Wave 2 (`M1`, `M6`, `M7`)** develop in parallel without waiting on each other, adhere strictly to these interfaces:

### 2.1. Chat Turn Response Contract (`POST /api/chat/turn`)
Every new chat sub-handler (`profile_habit_chat.py` in `M3`, `lifecycle_intents.py` in `M4`, `disruption_chat.py` in `M5`) MUST return a dictionary compatible with `handlers.py` (`process_chat_turn`):
```python
{
    "status": "APPLIED" | "NEEDS_CLARIFICATION" | "INFO_ONLY" | "CANCELLED",
    "intent": str,                        # e.g. "DELETE_ITEM", "COMPLETE_TASK", "DISRUPTION_REPAIR", "UPDATE_PROFILE_HABIT", "QUERY_SCHEDULE"
    "finalized": bool,
    "finalized_message_vi": str,
    "reply_vi": str,                      # Friendly, jargon-free Vietnamese reply
    "thinking_summary": dict | None,      # Built via build_thinking_summary(...) for Developer Mode
    "pending_draft": dict | None,
    "missing_fields": list[str],
    "quick_chips": list[dict[str, str]],  # [{"label": "...", "prompt": "..."}]
    "mutated_task_id": str | None,
    "traced_task": dict | None,
    "remaining_estimation": dict | None,
    "edge_case": dict | None,
    "post_actions": list[dict[str, str]], # Default: [{"action": "OPEN_CALENDAR", "label": "🗓️ Kiểm tra lịch trình"}]
    "updated_commitments": dict,
    "updated_tasks": list[dict],
    "updated_pinned_blocks": list[dict],
    "schedule": dict | None,              # Enriched ScheduleOutput dict when status == "APPLIED"
    "execution_time_ms": float,
}
```

### 2.2. Backend Item CRUD & Real-Week Init Endpoints (`M5` $\leftrightarrow$ `M1`, `M6`)
- `POST /api/workspace/init-real-week`
  - Request: `{"workspace_id": "default", "sleep_start": "23:30", "sleep_end": "06:30", "focus_preference": "BALANCED", "estimate_habit": "SOMETIMES"}`
  - Response: `{"commitments": {...}, "tasks": [], "pinned_blocks": [], "schedule": {...}}`
- `POST /api/tasks/delete`
  - Request: `{"workspace_id": "default", "commitments": {...}, "tasks": [...], "pinned_blocks": [...], "task_id": "...", "algorithm": "SCORED_GREEDY"}`
  - Response: `{"deleted_task_id": "...", "updated_tasks": [...], "updated_pinned_blocks": [...], "schedule": {...}}`
- `POST /api/fixed-events/upsert` & `POST /api/fixed-events/delete`
  - Request: `{"workspace_id": "default", "commitments": {...}, "tasks": [...], "pinned_blocks": [...], "event": {...} | "event_id": "...", "algorithm": "SCORED_GREEDY"}`
  - Response: `{"updated_commitments": {...}, "schedule": {...}}`
- `POST /api/workspace/adapt-next-week` *(Cross-Week Fallacy Buffer & Revealed-Preference Adaptation — `M5`)*
  - Request: `{"workspace_id": "default", "commitments": {...}, "next_week_tasks": [...], "timeline_logs": [...], "apply": false}`
  - Response: `{"adapted_commitments": {...}, "adapted_tasks": [...], "category_alphas": {...}, "preference_shifts": [...], "chronic_disruption_zones": [...], "schedule": {...}}`
- `POST /api/simulation/multi-week` *(Closed-Loop In-Silico Student Behavioral Simulation — `M5` endpoint calling `M7`'s `student_simulator.py` + `M5`'s `cross_week_adapter.py`)*
  - Request: `{"weeks": 4, "n_students": 25, "seed": 42, "commitments": {...}, "tasks": [...]}`
  - Response: `{"weeks_summary": [{"week": 1, "adherence_pct": float, "on_time_value_pct": float, "learned_alphas": dict, "learned_focus": str}, ...], "converged": bool, "determinism_hash": str, "execution_time_ms": float}`

### 2.3. Frontend Undo & Attachment Exports (`M6` $\leftrightarrow$ `M1`)
- `smartschedule/ui/js/undo-history.js` (`M6`) exports:
  - `pushUndoSnapshot(state, actionLabel)`
  - `popUndoSnapshot(state)` $\to$ returns `{ snapshot, actionLabel } | null`
  - `canUndo()` $\to$ `boolean`

### 2.4. Context Extraction & `Pattern -> Deterministic Logic Rule` Contracts (`M2` $\leftrightarrow$ `M4`, `M5`, `M6`)
To directly address instructor feedback on **problem thinking depth** and **explicit Pattern $\to$ Deterministic Logic Rule traceability** (see [`Testing_Plan/Formal_Spec_And_Patterns.md`](Testing_Plan/Formal_Spec_And_Patterns.md)):
1. **`parse_context_with_online_model()` (`smartschedule/nlp/context_router.py`, owned by `M2`)** returns backward-compatible dict keys plus optional fields consumed by `M4` (`handlers.py`):
   - `"avoid_windows": list[str]` — e.g. `["EVENING"]` when negation precedes a window (*"không/tránh làm buổi tối"*, Pattern `P12b`).
   - `"prerequisite_hint": str | None` — raw prerequisite task phrase when causal ordering is stated (*"xong A mới làm B"*, *"sau khi hoàn thành A"*, Pattern `P10`).
   - `"week_offset_hint": int` — `0` (current week) or `1` (*"tuần sau"* / *"next week"*).
   - `"parser_engine_used": str` & `"parse_ms": float`.
2. **`build_thinking_summary(...)` (`smartschedule/api/chat/thinking_stage.py`, owned by `M2`)** preserves all existing keyword arguments and adds optional defaulted kwargs (`pattern_rules: list[dict] | None = None`, `has_dag: bool = False`, `avoided_windows: list[str] | None = None`, `repair_stability_pct: float | None = None`, `overload_triage: bool = False`), returning `"pattern_rules"` inside `thinking_summary`:
   ```python
   "pattern_rules": [
       {
           "pattern_id": "P10",                        # "P1" .. "P12"
           "pattern_name": "Topological DAG Cascade",
           "causal_link_vi": "Cha phải xong trước con & siết ngược hạn chót",
           "deterministic_rule": "max(end_u) <= min(start_v) & D_eff(u) <= D_eff(v) - dur(v)",
       },
   ]
   ```
   `M6` (`chat-assistant.js`) renders `thinkingSummary.pattern_rules` (when non-empty) inside `_renderThinkingStage` and `task.depends_on` inside `_renderHiddenParamDebugCard`.

### 2.5. Cross-Week Adaptation, In-Silico Simulation & Document Digest Contracts (`M7` $\leftrightarrow$ `M5` $\leftrightarrow$ `M4`)
1. **`smartschedule/nlp/doc_attachment_parser.py` (Owned by `M7` Gia Bảo — moved off `M6`!):**
   - `parse_document_constraint_digest(filename: str, raw_bytes_or_text: bytes | str) -> dict`:
     Returns `{"filename": str, "extracted_text": str, "milestones": [{"title": str, "weight_pct": int | None, "estimated_min": int, "cognitive_load": int, "depends_on_prev": bool}], "suggested_total_min": int, "suggested_priority": int, "suggested_load": int}`.
   - `POST /api/chat/turn` (`M4` `handlers.py`) accepts optional `attachments: list[{"filename": str, "content": str}]` and cross-checks user prompt duration against `suggested_total_min` (`USER_VS_DOC_UNDERESTIMATE` clarification chip when user estimate $< 0.5 \times \text{suggested\_total\_min}$).
2. **`smartschedule/core/cross_week_adapter.py` (Owned by `M5` Tiến Bình — Pure Layer 1):**
   - `adapt_preferences_for_next_week(profile: CommitmentsProfile, next_tasks: list[Task], timeline_logs: list[dict], kappa: float = 3.0) -> dict`:
     Computes Bayesian-shrinkage per-category fallacy buffers $\hat{\alpha}_{c,\ell} \in [1.00, 1.60]$ (injected into `Task.alpha_light` / `Task.alpha_heavy` with `buffer_mode="COGNITIVE_LOAD"`, zero solver changes!), revealed-preference `focus_preference` / `CircadianEnergyProfile.hourly_levels` shifts, post-crunch `work_rhythm` smoothing (`FLOW -> BALANCED`), and `chronic_disruption_zones`.
3. **`smartschedule/core/student_simulator.py` (Owned by `M7` Gia Bảo — Pure Layer 1):**
   - `InSilicoStudentSimulator(student_id: str, seed: int, latent_profile: dict | None = None)`:
     Implements the 5-equation psychometric model (`MCTQ` peak, `Buehler` category Log-Normal fallacy, `Steel 2007 TMT` with $\Gamma$ denominator, `McFadden 1974 RUM` adherence logit, `Albulescu 2022` fatigue recovery) and `simulate_week_execution(profile, tasks, schedule) -> list[dict]` returning `timeline_logs` directly consumable by `M5`'s `adapt_preferences_for_next_week(...)`!

---

## 3. Non-Negotiable Architecture & Performance Guardrails (`INV-1` to `INV-6`)

1. **`INV-1` & `INV-2` Layer Purity:** `smartschedule/core/` must NEVER import `smartschedule.api`, `smartschedule.nlp`, `fastapi`, `spacy`, `transformers`, `docling`, or `google-genai`. `models.py` never imports `controller` or `solvers`.
2. **`INV-3` & `INV-4` Frozen Solver Portfolio:** Do **NOT** modify `smartschedule/core/solvers/*` or `v1.0-alpha-plan/Testing_System/*`. All 6 solvers (`EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`) must retain bit-identical `determinism_hash` outputs and protect `SLEEP`/`OCCUPIED` masks.
3. **`INV-5` Memory & Latency SLA:**
   - Optional NLP/PDF libraries (`spacy`, `onnxruntime`, `transformers`, `docling`, `pypdf`) belong in `environments/requirements-nlp-extra.txt` and MUST be lazy-imported inside Layer 4 functions so 50 consecutive solves keep heap growth `< 350 KB` (`peak < 10 MB`).
   - Solver SLA `<= 1,000 ms` (`N <= 50`); end-to-end `/api/chat/turn` SLA `< 10,000 ms` (`< 150 ms` local deterministic path).
4. **Backward-Compatible DOM Contracts:** Never remove contracted DOM IDs in `smartschedule/ui/index.html` (`#viewChat`, `#viewCalendar`, `#viewList`, `#viewWeights`, `#viewBenchmark`, `#viewShowcase`, `#inputModal`, `#devSidePanel`, `#stFocusTimerPanel`, `#stHealthV21Panel`, `#chkSettingEnergy`, `#btnOpenDisruption`).

---

## 4. Directory Map & Mandatory Pre-PR Verification

- **Codebase Index:** [`environments/CODEBASE_INDEX.md`](../environments/CODEBASE_INDEX.md) (respect [`environments/.agentignore`](../environments/.agentignore))
- **Member Sprint Briefs:** [`Sprint_Tasks/M1_Pham_Duc_Minh.md`](Sprint_Tasks/M1_Pham_Duc_Minh.md) .. [`Sprint_Tasks/M7_Nguyen_Nguyen_Gia_Bao.md`](Sprint_Tasks/M7_Nguyen_Nguyen_Gia_Bao.md)
- **Completed Pre-Sprint Specs:** [`Completed_Blueprints/`](Completed_Blueprints/) (`folder_division_plan.md`, `UI_Rebuild_Plan/`)
- **Academic, Formal Spec & Evaluator Specs:** [`Testing_Plan/Formal_Spec_And_Patterns.md`](Testing_Plan/Formal_Spec_And_Patterns.md), [`Testing_Plan/`](Testing_Plan/) & [`Testing_System/`](Testing_System/)

```powershell
# Run from repository root before opening any PR:
python -B tests/clean_runner.py --pass
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
python -B tests/fixtures/nl_cases/verify_hybrid_200.py
node --check smartschedule/ui/app.js
```
