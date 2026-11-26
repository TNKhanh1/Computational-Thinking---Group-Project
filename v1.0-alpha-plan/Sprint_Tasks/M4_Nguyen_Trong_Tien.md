# M4 — Nguyễn Trọng Tiến (`25125037`) · Thinker 3 (Grounded Router & Claude-Plan Verification Lead)
**Vai trò theo `work_division.pdf` & Sprint Nâng Cấp:** Thinker 3 · Lead **§5 Pillar 3: Abstraction**, Support **§9 Evaluation Plan** · **Core Router & Independent Verification Lead (cùng `M7` Gia Bảo & `M5` Tiến Bình)**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m4-grounded-chat-and-verification`  
**Đợt thực hiện (Wave):** **Wave 1B** (Tạo PR trước **12:00 Trưa Thứ Bảy, 28/11/2026**) & **Vòng Kiểm Định Độc Lập Bằng Claude Plan** (Chiều/Tối Thứ Bảy 28/11)

---

## 1. Trọng Tâm Của Bạn Trong Kế Hoạch Nâng Cấp Điểm Tối Đa
Trong nhóm 3 nòng cốt kỹ thuật (`M7` Gia Bảo, `M5` Tiến Bình, và bạn `M4`), bạn nắm **2 vai trò quyết định**:
1. **Bộ Điều Phối Hội Thoại Có Neo Dữ Liệu (`intent_classifier.py`, `lifecycle_intents.py`, `handlers.py`):**
   - Khắc phục triệt để điểm yếu *"context-parsing model yếu khi chỉ đọc chuỗi chữ đơn lẻ"*: truyền **ngữ cảnh công việc hiện có (`workspace_context`) + kết quả đọc đề cương đính kèm (`doc_attachment_parser` của `M7`)** vào luồng xử lý chat!
   - Xử lý trọn vẹn các ý định vòng đời (`DELETE_ITEM`, `COMPLETE_TASK`, `BATCH_ADD_TASKS`, `QUERY_SCHEDULE`, `ADAPT_NEXT_WEEK`), nối tự động **Đồ thị Phụ thuộc Thứ tự `DAG` (`depends_on` — Pattern `P10`)** (*"xong A mới làm B"*), kiểm tra chu trình trước khi lưu, và cảnh báo thông minh khi thời lượng người dùng gõ mâu thuẫn với file đề bài đính kèm (`USER_VS_DOC_UNDERESTIMATE` — Pattern `P14a`).
2. **Kiểm Định Toán Học & Ca Biên Độc Lập Bằng Claude Plan (Verification Gate cho `M5` & `M7`) + Chủ Trì Slide §5 Abstraction:**
   - Dùng **Claude Plan** của bạn để rà soát độc lập toàn bộ công thức & mã nguồn `cross_week_adapter.py` (của Bình `M5`) và `student_simulator.py` + `doc_attachment_parser.py` (của Bảo `M7`), đảm bảo không dính lỗi nhân đôi buffer (*Double-Buffering*), không vượt trần Over-Buffering Cliff $\alpha \le 1.60$, đúng phương trình `Steel (2007) TMT` + `McFadden (1974) RUM`, và hội tụ đơn điệu qua 4 tuần mô phỏng!
   - Chuẩn bị phần trình bày 4 slide ***"Abstraction of Problem Definition into Formal Specification"*** từ [`../Testing_Plan/Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md).

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (`0%` Merge Conflict Guarantee)
- **CREATE:**
  - `smartschedule/nlp/intent_classifier.py`
  - `smartschedule/api/chat/lifecycle_intents.py`
  - `tests/logical/test_chat_lifecycle_and_grounding.py`
- **MODIFY (Wave 1B ONLY):**
  - `smartschedule/api/chat/handlers.py` *(SOLE OWNER of `handlers.py` across all 7 members!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*`, `smartschedule/nlp/context_router.py` (`M2`), `smartschedule/core/cross_week_adapter.py` (`M5`), `smartschedule/core/student_simulator.py` (`M7`), or `smartschedule/ui/*`.

### Engineering Requirements
1. **Deterministic Intent Taxonomy (`smartschedule/nlp/intent_classifier.py`, `< 2 ms`):**
   - `DELETE_ITEM` (*"xóa bài tập..."*, *"hủy lịch..."*), `COMPLETE_TASK` (*"làm xong ... rồi"*, *"hoàn thành ..."*), `BATCH_ADD_TASKS` (bulleted/numbered lists or multi-clause chains *"xong A ... rồi mới làm B ..."*), `QUERY_SCHEDULE` (*"thứ 5 tuần này có lịch gì"*), `ADAPT_NEXT_WEEK` (*"tối ưu / rút kinh nghiệm cho tuần sau từ lịch sử tuần này"*, *"học thói quen tuần trước"*), `DISRUPTION_REPAIR` ($\to$ `M5`), `UPDATE_PROFILE_HABIT` ($\to$ `M3`), plus `ADJUST_DEADLINE`, `MODIFY_HIDDEN`, `ADD_RECURRING`, `ADD_TASK`.
2. **Fault-Tolerant Dynamic Imports in `smartschedule/api/chat/handlers.py`:**
   Use `try / except ImportError` around `M5` (`disruption_chat`, `cross_week_adapter`), `M7` (`doc_attachment_parser`), and `M3` (`profile_habit_chat`) + `inspect.signature` around `build_thinking_summary` (`M2`) so `handlers.py` passes 100% of tests regardless of merge order!
3. **Workspace-Grounded Context, DAG Wiring (`P10`), Attachment Sanity Check (`P14a`), & Next-Week Adaptation (`P13`):**
   - **Workspace Grounding & `depends_on` DAG:** Resolve prerequisite clauses (*"sau khi xong X"*, *"hoàn thành X trước rồi mới làm Y"*, or `online_ctx.get("prerequisite_hint")`) against `tasks_raw` via `resolve_target_task_from_prompt()` (and across sequential items in `BATCH_ADD_TASKS`). Run a quick DFS cycle check before appending `depends_on`: if adding `u -> v` creates a cycle, return `status="NEEDS_CLARIFICATION"` explaining the circular dependency instead of silently dropping it!
   - **Attachment Contradiction Check:** When `payload.get("attachments")` is non-empty and `parse_document_constraint_digest` (`M7`) is available, extract milestones & `suggested_total_min`. If user typed an explicit duration $< 0.5 \times \text{suggested\_total\_min}$, return `status="NEEDS_CLARIFICATION"` (`conflict="USER_VS_DOC_UNDERESTIMATE"`) with 1-click `quick_chips` offering **(1) Use structured milestones + DAG from attached spec (`suggested_total_min`m)** vs **(2) Keep user's manual duration**. If user gave no duration, auto-populate from the attachment digest!
   - **Conversational Cross-Week Adaptation (`ADAPT_NEXT_WEEK`):** Invoke `M5`'s `adapt_preferences_for_next_week(...)` on stored `completion_logs` / `timeline_logs` and return a clear Vietnamese summary of learned category $\hat{\alpha}_{c,\ell}$ buffers and revealed chronotype shifts (`Pattern P13`).

---

## 3. Claude-Plan Independent Verification Protocol (Audit Gate for `M5` & `M7`)
Once `M5` and `M7` open their Wave 1A PRs, run your **Claude Plan verification audit** across these 5 mathematical invariants:
1. **No Double-Buffering Invariant (`M5`):** Verify `adapt_preferences_for_next_week` always scales raw `Task.duration_min` (never multiplying a previously buffered `planned_duration_min` a second time!) and strictly clamps $\hat{\alpha}_{c,\ell} \in [1.00, 1.60]$ (avoiding the $\alpha \ge 1.70$ Over-Buffering Cliff).
2. **Cold-Start Shrinkage Stability (`M5`):** Verify that with $n_c = 0$ logs, $\hat{\alpha}_{c,\ell} == \alpha_0(\ell)$ (`1.20 / 1.35`), and a single extreme outlier ($A/E = 5.0$) is clipped to `2.50` and shrunk by $\kappa = 3.0$ so Week 2 never explodes.
3. **Psychometric Formula & RNG Isolation (`M7`):** Verify `student_simulator.py` uses an isolated `random.Random(seed)` (3 runs with `seed=42` produce bit-identical `SHA-256` hashes), includes $\Gamma$ in the denominator of Steel's TMT equation ($1 + \Gamma \cdot s_h/24$), and restores fatigue on $\ge 15\text{m}$ breaks.
4. **Closed-Loop Multi-Week Convergence (`M5` + `M7`):** Verify on a miscalibrated Night-Owl + Coding-Underestimator seed that Week 4 outperforms Week 1 in adhered on-time value and reduces overrun collisions.
5. **Zero Regression on Frozen `Testing_System v2.1` (`39/39`) & `clean_runner.py --pass` (`100%`).**

### Verification Commands
```powershell
python -B -m pytest tests/logical/test_chat_lifecycle_and_grounding.py tests/logical/test_chat_first_ui_and_task_tracer.py -q
python -B tests/clean_runner.py --pass
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
```

---

## 4. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [ ] Tạo `intent_classifier.py` + `lifecycle_intents.py` (`DELETE`, `COMPLETE`, `BATCH_ADD`, `QUERY`, `ADAPT_NEXT_WEEK`).
- [ ] Nâng cấp `handlers.py` nối `depends_on` DAG (có chặn chu trình), đối chiếu đề bài đính kèm (`M7`), học thích nghi tuần sau (`M5`), và điều phối an toàn `M3`/`M5`/`M7`.
- [ ] Viết `tests/logical/test_chat_lifecycle_and_grounding.py` và chạy xanh toàn bộ test.
- [ ] **(Chiều/Tối T7 28/11)** Chạy **Claude Plan Verification Audit** kiểm chứng toán học & ca biên trên code của `M5` (Bình) & `M7` (Bảo), và chốt 4 slide §5 Abstraction từ [`Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md).
