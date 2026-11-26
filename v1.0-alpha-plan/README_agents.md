# SmartSchedule `v1.0-alpha` — Master Agent Execution & Zero-Conflict Sprint Plan (`v1.0-alpha-plan/README_agents.md`)

> [!IMPORTANT]
> **MANDATORY INSTRUCTIONS FOR ALL AI CODING AGENTS (7-MEMBER FINAL `v1.0-alpha` SPRINT):**
> 1. **Identify Your Assigned Member (`M1`–`M7`) First:** Ask your human user which team member they are (or infer from their branch/request), then **immediately read ONLY their dedicated brief in [`Sprint_Tasks/`](Sprint_Tasks/)**:
>    - [`M1_Pham_Duc_Minh.md`](Sprint_Tasks/M1_Pham_Duc_Minh.md) — Leader (`25125028`): First-Time Onboarding, Real-Week Start, User Profile Popover & Wave 2B/3 Integration
>    - [`M2_Tran_Nguyen_Khanh.md`](Sprint_Tasks/M2_Tran_Nguyen_Khanh.md) — Thinker 1 (`25125019`): Free Lazy-Loaded Context Engine (`spaCy`/HF Encoders), Negation Rules & Thinking Stage
>    - [`M3_Hoang_Minh_Anh.md`](Sprint_Tasks/M3_Hoang_Minh_Anh.md) — Thinker 2 (`25125001`): Conversational Sleep/Chronotype/`PersonalHabit` Coach & 7-Member Blind Evaluation (`Calibration_Report.md`)
>    - [`M4_Nguyen_Trong_Tien.md`](Sprint_Tasks/M4_Nguyen_Trong_Tien.md) — Thinker 3 (`25125037`): Full Chat Lifecycle Intents (`DELETE`, `COMPLETE`, `BATCH_ADD`, `QUERY`) & `handlers.py` Plug-in Dispatcher
>    - [`M5_Le_Tien_Binh.md`](Sprint_Tasks/M5_Le_Tien_Binh.md) — Builder 1 (`25125007`): Conversational Emergency Disruption $\to$ `LocalRepairEngine` (`LOCAL_INSERTION`) & Real-Week / Item CRUD APIs
>    - [`M6_Le_Minh_Nhat.md`](Sprint_Tasks/M6_Le_Minh_Nhat.md) — Builder 2 (`25125032`): `.ics` / Syllabus Chat Upload (`Docling`), Chat Persistence across `F5`, 1-Click Undo & Item Delete/Edit UI
>    - [`M7_Nguyen_Nguyen_Gia_Bao.md`](Sprint_Tasks/M7_Nguyen_Nguyen_Gia_Bao.md) — Builder 3 (`25125006`): Mobile/Tablet Slide-Over CSS, `INV-1..6` Lazy-Import Memory Guardrails (`<350KB`) & Full E2E Release Gate
> 2. **Strict Zero-Conflict File Lock:** Never edit files outside the *Exclusive File Ownership* section of your member's brief. Do **NOT** modify `agents/commit_changes.md`, `docs/commit_changes.md`, or `v1.0-alpha-plan/README*.md` on feature branches — tick `[x]` checkboxes **only** inside your member's `Sprint_Tasks/M<k>_*.md` file!

---

## 1. Sprint Timeline & Conflict-Free Merge Order (Thu Nov 26 $\to$ Sun Morning Nov 29, 2026)

| Wave | Window (`UTC+7`) | PR Merge Order & Owner | Scope & Why Merge Conflicts = `0%` |
| :--- | :--- | :--- | :--- |
| **Wave 0** | **Thu Nov 26, `22:30–23:59`** | All 7 Members (`git checkout -b v1.0-alpha/m<k>-...` from `main`) | Shared plug-in function signatures frozen below; zero overlapping files assigned. |
| **Wave 1** | **Fri Nov 27 $\to$ Sat Nov 28 `12:30`** | **1st:** `M5` (Lê Tiến Bình — Fri `22:00`)<br>**2nd:** `M2` (Trần Nguyên Khánh — Fri `23:00`)<br>**3rd:** `M3` (Hoàng Minh Anh — Sat `12:00`)<br>**4th:** `M4` (Nguyễn Trọng Tiến — Fri `23:30` / Sat `12:30`) | Pure backend/NLP modules in disjoint files (`controller.py`/`app.py` vs `context_router.py`/`thinking_stage.py` vs `profile_habit_chat.py` vs `lifecycle_intents.py`/`handlers.py` with `try/except ImportError` dynamic dispatch). |
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

### 2.3. Frontend Undo & Attachment Exports (`M6` $\leftrightarrow$ `M1`)
- `smartschedule/ui/js/undo-history.js` (`M6`) exports:
  - `pushUndoSnapshot(state, actionLabel)`
  - `popUndoSnapshot(state)` $\to$ returns `{ snapshot, actionLabel } | null`
  - `canUndo()` $\to$ `boolean`

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
- **Academic & Evaluator Specs:** [`Testing_Plan/`](Testing_Plan/) & [`Testing_System/`](Testing_System/)

```powershell
# Run from repository root before opening any PR:
python -B tests/clean_runner.py --pass
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
python -B tests/fixtures/nl_cases/verify_hybrid_200.py
node --check smartschedule/ui/app.js
```
