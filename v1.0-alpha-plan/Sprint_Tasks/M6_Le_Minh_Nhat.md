# M6 — Lê Minh Nhật (`25125032`) · Builder 2
**Vai trò theo `work_division.pdf`:** Builder 2 · Lead **§10 From Design to Action**, Support **§5 Abstraction**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m6-ics-undo-persistence-ui`  
**Đợt thực hiện (Wave):** **Wave 2A** (Tạo PR trước **19:00 Tối Thứ Bảy, 28/11/2026** — trước khi Wave 2B ghép `app.js`)

---

## 1. Dành cho Thành Viên (Giải thích dễ hiểu)
Để sinh viên thực sự dùng ứng dụng hằng ngày một cách trơn tru (đúng tinh thần Mục §10 *From Design to Action*), hiện đang thiếu **4 tiện ích thiết thực nhất trên giao diện**:
1. **Nút đính kèm lịch `.ics` (Thời khóa biểu trường / Moodle) & file đề bài ngay tại ô Chat (`📎`):** Ở tầng ngầm bạn đã viết sẵn bộ đọc `.ics` (`ics_importer.py`) rất xịn, nhưng ở giao diện người dùng lại chưa có nút bấm hay kéo-thả tệp `.ics` / `.pdf` vào khung chat để tự động nạp lịch học!
2. **Giữ lại lịch sử trò chuyện khi bấm tải lại trang (`F5`):** Hiện bấm `F5` là toàn bộ tin nhắn chat biến mất sạch dù lịch vẫn còn.
3. **Nút `"↩ Hoàn tác"` (Undo 1 chạm):** Khi lỡ tay kéo nhầm ô lịch, xóa nhầm việc, hoặc trợ lý vừa xếp lại mà chưa ưng, người dùng cần bấm 1 nút **"Hoàn tác"** để quay về ngay trạng thái trước đó.
4. **Sửa / Xóa lẻ từng Việc hoặc Lịch cố định ngay trên Lịch & Danh sách:** Hiện bấm vào lớp học cố định chưa sửa/xóa được, và hộp chi tiết phiên học chưa có nút `"🗑️ Xóa công việc này"`.

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (Conflict-Free Guarantee — Lightweight Pure UI JS Scope)
- **CREATE:**
  - `smartschedule/ui/js/undo-history.js`
  - `tests/ui/test_ics_undo_and_persistence.py`
  *(Lưu ý: Phần xử lý logic đọc file đề bài ở tầng Python `smartschedule/nlp/doc_attachment_parser.py` đã được chuyển sang cho Gia Bảo `M7` đảm nhận để giảm tải kỹ thuật backend cho bạn!)*
- **MODIFY (Wave 2A ONLY):**
  - `smartschedule/ui/js/chat-assistant.js` *(SOLE OWNER in this sprint!)*
  - `smartschedule/ui/js/modals.js` *(SOLE OWNER in this sprint!)*
  - `smartschedule/ui/js/render-list.js` *(SOLE OWNER in this sprint!)*
  - `smartschedule/ui/js/state.js` *(SOLE OWNER in this sprint!)*
  - `smartschedule/ui/js/api.js` *(add helper wrappers for `deleteTask`, `upsertFixedEvent`, `deleteFixedEvent`, `initRealWeek`)*
- **DO NOT TOUCH:** `smartschedule/ui/index.html` or `smartschedule/ui/app.js` *(export clean handler hooks from `undo-history.js` and `chat-assistant.js` so Leader `M1` wires them into `app.js` & `index.html` in Wave 2B with zero conflicts!)*, and never touch `smartschedule/core/solvers/*`.

### Engineering Requirements
1. **1-Click Undo Ring Buffer (`smartschedule/ui/js/undo-history.js`):**
   - Implement `pushUndoSnapshot(state, label)` (deep-cloning `{commitments, tasks, pinnedBlocks, completedBlocks, currentSchedule}`, max `10` entries) and `popUndoSnapshot(state)`.
   - Extend `showToast(message, tone, { onUndo } = {})` in `modals.js` so mutating actions render an inline **`↩ Hoàn tác`** button inside the toast!
2. **Chat Persistence + Clear Chat + `📎` `.ics` / Document Drop (`chat-assistant.js` & `state.js`):**
   - Persist `chatMessages` (trimmed to the latest `30` messages) inside workspace state serialization (`state.js`) so refreshing the browser (`F5`) restores the conversation seamlessly; add a subtle `🧹 Làm mới chat` icon button in the chat/copilot header to clear transcript without deleting scheduled tasks.
   - Add a compact `📎` file button (`accept=".ics,.txt,.md,.pdf"`) + drag-drop zone inside `.chat-composer-form`:
     - `.ics` files call `api.importIcs(...)` (`POST /api/import/ics`) and render a clean confirmation card in chat showing imported classes & deadlines (`[✅ Áp dụng vào lịch]`).
     - `.txt`/`.md`/`.pdf` syllabus/assignment files simply read text/base64 in JS and pass `attachments: [{ filename, content }]` inside the existing `api.sendChatTurn(...)` payload (`M7` & `M4` handle all backend parsing automatically!).
3. **Single-Item Delete/Edit in `modals.js` & `render-list.js` + Developer Mode `Pattern -> Rule` & `DAG` Badges (`chat-assistant.js`):**
   - Add a `"🗑️ Xóa công việc này"` button inside `renderBlockInspectorModal` (`modals.js`) and a delete/edit trigger on Fixed Event rows in `renderListView` (`render-list.js`), invoking `callbacks.onDeleteTask(taskId)` / `callbacks.onDeleteFixedEvent(eventId)`.
   - **Final Presentation Score Booster in `chat-assistant.js`:**
     - Inside `_renderThinkingStage(thinkingSummary)`, if `Array.isArray(thinkingSummary.pattern_rules) && thinkingSummary.pattern_rules.length > 0`, render a crisp `"🔗 Pattern → Quy tắc Logic Tất định:"` block displaying each item's `pattern_id`, `pattern_name`, and `deterministic_rule` (directly answering the instructor's Pattern Recognition feedback live on screen!).
     - Inside `_renderHiddenParamDebugCard(task)`, display `Phụ thuộc DAG: <strong>${esc((task.depends_on || []).join(", ") || "Độc lập")}</strong>` (and `Khung né: ...` if `task.avoid_windows` exists) so live DAG prerequisite demos are visually unmistakable.

### Verification Commands (Must Pass 100% Before PR)
```powershell
node --check smartschedule/ui/js/undo-history.js
node --check smartschedule/ui/js/chat-assistant.js
node --check smartschedule/ui/js/modals.js
python -B -m pytest tests/ui/test_ics_undo_and_persistence.py tests/logical/test_p3_2_ics_importer.py -q
python -B tests/clean_runner.py --pass
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [x] Tạo `smartschedule/ui/js/undo-history.js` và gắn nút **`↩ Hoàn tác`** lên Toast thông báo.
- [x] Lưu giữ 30 tin nhắn gần nhất qua `F5` (`state.js`) + thêm nút `🧹 Làm mới chat` và nút `📎` chọn file `.ics` / đề bài gửi kèm trong khung chat (`chat-assistant.js`).
- [x] Thêm nút **Xóa công việc / Xóa lịch cố định** trong `modals.js` và `render-list.js`, đồng thời hiển thị huy hiệu **`🔗 Pattern → Deterministic Logic Rule`** + **`Phụ thuộc DAG`** ở `Developer Mode` (`chat-assistant.js`).
- [x] Viết test `tests/ui/test_ics_undo_and_persistence.py` và kiểm tra xanh `node --check` + `clean_runner.py --pass` (phối hợp cùng Tiến `M4` chuẩn bị slide §5 Abstraction từ [`Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md)).
