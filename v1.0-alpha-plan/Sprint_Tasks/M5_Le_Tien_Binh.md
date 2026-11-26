# M5 — Lê Tiến Bình (`25125007`) · Builder 1
**Vai trò theo `work_division.pdf`:** Builder 1 · Lead **§7 System Architecture**, Support **§6 Algorithmic Design**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m5-disruption-repair-and-crud-api`  
**Đợt thực hiện (Wave):** **Wave 1 — Ưu tiên Merge đầu tiên** (Tạo PR trước **22:00 Thứ Sáu, 27/11/2026**)

---

## 1. Dành cho Thành Viên (Giải thích dễ hiểu)
Ở đợt tinh giản giao diện trước, nhóm đã gỡ nút *"Báo sự cố đột xuất & Sửa lịch"* khỏi menu Cài đặt vì muốn người dùng nhắn thẳng sự cố vào khung chat. Tuy nhiên hiện tại:
- Khi người dùng nhắn *"Chiều thứ 3 từ 14h đến 16h mình phải họp CLB đột xuất"*, khung chat lại xếp lại toàn bộ lịch từ đầu thay vì gọi động cơ **`LocalRepairEngine` (Sửa lịch cục bộ — giữ nguyên $\ge 90\%$ các buổi học không bị đụng)** mà bạn đã xây rất mạnh ở tầng Core!
- Ngoài ra, lịch mặc định khi khởi tạo mới đang neo cứng vào ngày cũ `02/11/2026`, và giao diện thiếu các API gọn nhẹ để sửa/xóa lẻ 1 lớp học cố định hoặc 1 công việc.

**Nhiệm vụ của bạn trong `v1.0-alpha`:**
1. **Xử lý Sự cố Đột xuất qua Chat bằng `LocalRepairEngine` (`disruption_chat.py`):** Khi sinh viên báo bận đột xuất, chèn sự kiện đó và chạy `LOCAL_INSERTION` để chỉ dịch chuyển đúng những phiên học bị trùng giờ, giữ ổn định tối đa lịch tuần và báo rõ cho người dùng biết bao nhiêu buổi được giữ nguyên!
2. **Hàm khởi tạo Tuần Thực Tế hiện tại & API Xóa/Sửa lẻ từng mục (`controller.py` & `app.py`):** Cung cấp nền tảng API vững chắc cho Đức Minh (`M1` — Onboarding tuần hiện tại) và Minh Nhật (`M6` — nút Xóa/Sửa trên Lịch).

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (Conflict-Free Guarantee)
- **CREATE:**
  - `smartschedule/api/chat/disruption_chat.py`
  - `tests/logical/test_disruption_chat_and_crud.py`
- **MODIFY (Wave 1 ONLY):**
  - `smartschedule/core/controller.py` *(SOLE OWNER in this sprint!)*
  - `smartschedule/api/app.py` *(SOLE OWNER in this sprint!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*` *(keep all 6 solvers bit-identical!)*, `smartschedule/api/chat/handlers.py` *(`M4` imports your `handle_disruption_chat_turn` automatically!)*, or `smartschedule/ui/*`.

### Engineering Requirements
1. **Conversational Disruption Repair (`smartschedule/api/chat/disruption_chat.py`):**
   Expose:
   ```python
   def handle_disruption_chat_turn(
       prompt: str,
       profile: CommitmentsProfile,
       tasks_raw: list[dict],
       pinned_raw: list[dict],
       completed_blocks: dict,
       current_schedule: dict | None,
       algorithm: str,
       workspace_id: str,
       auto_save: bool,
   ) -> dict[str, Any]: ...
   ```
   - Extract event title, weekday (including `"hôm nay"`, `"ngày mai"`, `"chiều thứ 4"`), and `start_time`–`end_time`. If time range or day is missing, return `status="NEEDS_CLARIFICATION"` with quick chips.
   - Build a `DisruptionEvent` and run `LocalRepairEngine.repair_disruption(..., mode="LOCAL_INSERTION", algorithm=eff_algo)` (generating baseline schedule first if `current_schedule` is None).
   - Append the new `FixedEvent` (`category="MEETING"`) to `updated_commitments`, persist workspace if `auto_save=True`, and craft a clear Vietnamese reply highlighting `stability_score` (e.g. *"Đã chèn lịch đột xuất và chỉ dời nhẹ X phiên bị trùng (giữ nguyên 95% lịch tuần của bạn)"*).
2. **Real-Time Current-Monday Helper (`smartschedule/core/controller.py`):**
   - Add `ScheduleController.build_empty_current_week_profile(sleep_start="23:30", sleep_end="06:30", focus_preference="BALANCED", estimate_habit="SOMETIMES", now_dt=None) -> CommitmentsProfile` that computes the real local Monday `00:00:00+07:00` and real ISO `now` timestamp. *(Never change `data/presets/*` or `T01–T10` dates!)*
3. **Clean Workspace Init & Item CRUD Endpoints (`smartschedule/api/app.py`):**
   - `POST /api/workspace/init-real-week`: Creates & saves a fresh real-week empty workspace (with optional sleep/focus/habit settings) and returns `{commitments, tasks: [], schedule}`.
   - `POST /api/tasks/delete`: Deletes `task_id` from workspace state (and drops matching `pinned_blocks`), re-solves, and returns updated state + schedule.
   - `POST /api/fixed-events/upsert` & `POST /api/fixed-events/delete`: Edits/adds or deletes a single `FixedEvent` by `event_id`, re-solves, and returns updated commitments + schedule.

### Verification Commands (Must Pass 100% Before PR)
```powershell
python -B -m pytest tests/logical/test_disruption_chat_and_crud.py tests/benchmark/test_edf_solver.py -q
python -B tests/clean_runner.py --pass
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [ ] Tạo `smartschedule/api/chat/disruption_chat.py` nối câu chat báo bận đột xuất vào `LocalRepairEngine` (`LOCAL_INSERTION`).
- [ ] Thêm hàm `build_empty_current_week_profile()` trong `controller.py` (neo đúng Thứ Hai tuần thực tế).
- [ ] Mở các endpoint `/api/workspace/init-real-week`, `/api/tasks/delete`, `/api/fixed-events/upsert`, `/api/fixed-events/delete` trong `app.py`.
- [ ] Viết test `tests/logical/test_disruption_chat_and_crud.py` và chạy xanh `clean_runner.py --pass` + `Testing_System/tests`.
