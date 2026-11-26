# M4 — Nguyễn Trọng Tiến (`25125037`) · Thinker 3
**Vai trò theo `work_division.pdf`:** Thinker 3 · Lead **§5 Pillar 3: Abstraction**, Support **§9 Evaluation Plan**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m4-chat-lifecycle-intents`  
**Đợt thực hiện (Wave):** **Wave 1** (Tạo PR trước **23:30 Thứ Sáu, 27/11/2026** · Hạn trễ nhất **12:00 Trưa Thứ Bảy, 28/11/2026**)

---

## 1. Dành cho Thành Viên (Giải thích dễ hiểu)
Hiện nay khung chat mới chỉ biết **Thêm việc** và **Đổi hạn chót / độ nặng**, dẫn tới một lỗi trải nghiệm rất lớn:
- Nếu người dùng gõ *"Xóa bài tập Giải tích giúp mình"* hoặc *"Mình làm xong đồ án Mạng rồi"*, bot lại... **tạo thêm một công việc mới tên là "Xóa bài tập Giải tích"**!
- Nếu sinh viên copy-paste danh sách **2–4 đầu việc gạch đầu dòng** vào ô chat cùng lúc, bot gộp tất cả thành 1 việc khổng lồ duy nhất.
- Nếu sinh viên hỏi *"Thứ 5 này mình có những lịch gì?"*, bot cũng đòi nhập thời lượng để tạo việc mới!

**Nhiệm vụ của bạn trong `v1.0-alpha`:**
1. **Bộ phân loại toàn diện Ý định người dùng & Tách danh sách nhiều việc (`intent_classifier.py`):** Nhận diện chính xác khi nào người dùng muốn **Xóa việc / Xóa lịch cố định**, **Báo đã làm xong**, **Thêm nhiều việc cùng lúc**, **Hỏi xem lịch ngày X**, **Báo bận đột xuất**, hay **Đổi giờ ngủ / thói quen**.
2. **Xử lý trọn vòng đời công việc qua Chat (`lifecycle_intents.py`) & Điều phối `handlers.py`:** Dùng mã vân tay từ khóa `SHA-256` để tìm đúng việc cần xóa / cần đánh dấu hoàn thành, trả lời lịch trong ngày dễ hiểu, và cắm (plug-in) các nhánh xử lý của bạn + Bình (`M5`) + Minh Anh (`M3`) vào `handlers.py`.

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (Conflict-Free Guarantee)
- **CREATE:**
  - `smartschedule/nlp/intent_classifier.py`
  - `smartschedule/api/chat/lifecycle_intents.py`
  - `tests/logical/test_chat_lifecycle_intents.py`
- **MODIFY (Wave 1 ONLY):**
  - `smartschedule/api/chat/handlers.py` *(SOLE OWNER of `handlers.py` across all 7 members!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*`, `smartschedule/nlp/context_router.py` (`M2`), `smartschedule/ui/*`, or `agents/commit_changes.md`.

### Engineering Requirements
1. **Intent Taxonomy (`smartschedule/nlp/intent_classifier.py`):**
   Classify prompts deterministically (`< 2 ms`) into:
   - `DELETE_ITEM`: *"xóa bài tập..."*, *"hủy lịch..."*, *"bỏ môn..."*, *"delete/remove..."*
   - `COMPLETE_TASK`: *"làm xong ... rồi"*, *"hoàn thành ..."*, *"đánh dấu xong ..."*, *"finished/done..."*
   - `BATCH_ADD_TASKS`: multi-line bulleted/numbered lists (`1. ...\n2. ...` or `- ...\n- ...` or `;`-separated distinct tasks with durations/deadlines)
   - `QUERY_SCHEDULE`: *"hôm nay có lịch gì"*, *"thứ 5 tuần này làm gì"*, *"còn bao nhiêu việc chưa xong"* (read-only answer, zero state mutation!)
   - `DISRUPTION_REPAIR`: urgent unexpected one-off conflict cues (*"họp đột xuất"*, *"bận đột xuất"*, *"sự cố khẩn"*, *"kẹt lịch đột xuất"*) $\to$ delegate to `M5`'s `disruption_chat.py`!
   - `UPDATE_PROFILE_HABIT`: sleep/chronotype/weekly habit cues $\to$ delegate to `M3`'s `profile_habit_chat.py`!
   - Existing intents: `ADJUST_DEADLINE`, `MODIFY_HIDDEN`, `ADD_RECURRING`, `ADD_TASK`.
2. **Fault-Tolerant Plug-In Dispatch in `smartschedule/api/chat/handlers.py`:**
   Use safe dynamic imports so your PR works independently BEFORE or AFTER `M3` and `M5` merge:
   ```python
   try:
       from smartschedule.api.chat.disruption_chat import handle_disruption_chat_turn
   except ImportError:
       handle_disruption_chat_turn = None
   try:
       from smartschedule.api.chat.profile_habit_chat import handle_profile_or_habit_turn, is_profile_or_habit_intent
   except ImportError:
       handle_profile_or_habit_turn = None
       is_profile_or_habit_intent = lambda _p: False
   ```
3. **Lifecycle Implementations (`smartschedule/api/chat/lifecycle_intents.py`):**
   - `DELETE_ITEM`: Resolve target task via `resolve_target_task_from_prompt()` (or `fixed_events` title substring). If ambiguous, return `status="NEEDS_CLARIFICATION"` with clickable `quick_chips` for candidate items; if matched, remove item + stale pins, re-solve, persist state, and reply naturally in Vietnamese.
   - `COMPLETE_TASK`: Resolve target task, log completion to SQLite (`record_task_completion` in `smartschedule/core/storage.py`), remove finished task & pins, re-solve remaining tasks, and reply with encouraging Vietnamese confirmation.
   - `BATCH_ADD_TASKS`: Parse up to 6 lines/bullets via existing task extraction; schedule all complete items at once and list any incomplete items cleanly.
   - `QUERY_SCHEDULE`: Summarize fixed classes + scheduled study blocks for the asked day (or today) in friendly Vietnamese bullet points without mutating tasks.

### Verification Commands (Must Pass 100% Before PR)
```powershell
python -B -m pytest tests/logical/test_chat_lifecycle_intents.py tests/logical/test_chat_first_ui_and_task_tracer.py -q
python -B tests/clean_runner.py --pass
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [ ] Tạo `smartschedule/nlp/intent_classifier.py` nhận diện đủ các ý định `DELETE`, `COMPLETE`, `BATCH_ADD`, `QUERY`, `DISRUPTION`, `PROFILE_HABIT`.
- [ ] Tạo `smartschedule/api/chat/lifecycle_intents.py` xử lý Xóa việc/lịch cố định, Báo hoàn thành việc, Thêm danh sách nhiều việc 1 lượt, và Hỏi lịch trong ngày.
- [ ] Gắn bộ điều phối (có `try/except ImportError` an toàn cho `M3` & `M5`) vào `smartschedule/api/chat/handlers.py`.
- [ ] Viết test `tests/logical/test_chat_lifecycle_intents.py` và chạy xanh toàn bộ `clean_runner.py --pass`.
