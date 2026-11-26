# M3 — Hoàng Minh Anh (`25125001`) · Thinker 2
**Vai trò theo `work_division.pdf`:** Thinker 2 · Lead **§11 Conclusion** · Phụ trách Hành vi Người học & Đánh giá Chấm mù (`member_eval`)  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m3-profile-coach-and-eval`  
**Đợt thực hiện (Wave):** **Wave 1** (Module Chat xong trước **12:00 Trưa Thứ Bảy, 28/11/2026**) & **Wave 3** (Tổng hợp Chấm mù 7 thành viên trước **09:00 Sáng Chủ Nhật, 29/11/2026**)

---

## 1. Dành cho Thành Viên (Giải thích dễ hiểu)
Trong thực tế sử dụng, sinh viên rất hay nhắn cho trợ lý các câu liên quan đến **nhịp sinh hoạt và thói quen cá nhân**, chẳng hạn:
- *"Đổi giờ ngủ của mình thành 23:00 đến 06:30 nhé"*
- *"Mình thuộc tuýp cú đêm, tỉnh táo nhất vào buổi tối"*
- *"Thêm thói quen chạy bộ 3 buổi một tuần, mỗi buổi 45 phút vào buổi chiều"*

Hiện tại khung chat chưa hiểu nhóm câu này (nó đang hiểu nhầm thành thêm bài tập mới!). Bên cạnh đó, để hoàn thiện trọn vẹn `v1.0-alpha` và phục vụ phần Kết luận (§11), nhóm cần chạy xong đợt **Chấm mù 7 thành viên** trên cổng `8010` để xuất báo cáo đối chiếu thực tế.

**Nhiệm vụ của bạn trong `v1.0-alpha`:**
1. **Trợ lý hội thoại chỉnh Giờ ngủ, Nhịp sinh học & Thói quen tuần (`profile_habit_chat.py`):** Giúp trợ lý hiểu và cập nhật nhẹ nhàng giờ ngủ (nhắc khéo nếu ngủ dưới 6 tiếng!), khung giờ tập trung cao nhất, và thêm/xóa các thói quen cá nhân (`PersonalHabit`).
2. **Tổ chức & Tổng hợp Chấm mù 7 thành viên (`tools/member_eval/`):** Tối Thứ Bảy (`20:00 – 23:30`), hướng dẫn 7 thành viên vào cổng `http://127.0.0.1:8010` chấm mù 3–4 kịch bản (mất ~10 phút/người), sau đó chạy công cụ tổng hợp ra file `tools/member_eval/Calibration_Report.md`.

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (Conflict-Free Guarantee)
- **CREATE:**
  - `smartschedule/api/chat/profile_habit_chat.py`
  - `tests/logical/test_profile_habit_chat.py`
  - `tools/member_eval/Calibration_Report.md` *(generated in Wave 3 after collecting `tools/member_eval/reviews/*.json`)*
- **MODIFY (if polish needed):**
  - `tools/member_eval/viewer.html` or `tools/member_eval/aggregator.py` *(SOLE OWNER of `tools/member_eval/*`!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*`, `smartschedule/api/chat/handlers.py` *(Thinker 3 `M4` wires the 3-line import call to your `handle_profile_or_habit_turn`!)*, or `smartschedule/ui/*`.

### Engineering Requirements
1. **Standardized Plug-In Contract (`smartschedule/api/chat/profile_habit_chat.py`):**
   Expose two clean functions so `M4` (`handlers.py`) can plug them in with zero friction:
   ```python
   def is_profile_or_habit_intent(prompt: str) -> bool: ...
   def handle_profile_or_habit_turn(
       prompt: str,
       profile: CommitmentsProfile,
       tasks_raw: list[dict],
       pinned_raw: list[dict],
       completed_blocks: dict,
       algorithm: str,
       workspace_id: str,
       auto_save: bool,
   ) -> dict[str, Any]: ...
   ```
2. **Supported Behavioral Mutations:**
   - **Sleep Schedule Update:** e.g. *"Ngủ từ 23h30 đến 6h30"*, *"Đổi giờ thức dậy sang 6h sáng"*. Enforce biological minimum $\ge 6\text{h}$ (`360m`): if user requests $< 6\text{h}$ sleep, return a caring Vietnamese warning (`status="NEEDS_CLARIFICATION"` with safe 6h+ quick chips) instead of crashing Pydantic validation!
   - **Chronotype / Focus Preference & Estimate Habit:** e.g. *"Mình học hiệu quả nhất buổi sáng"* $\to$ `focus_preference = "MORNING"`; *"Mình hay ước lượng thiếu giờ lắm"* $\to$ `estimate_habit = "OFTEN"`.
   - **`PersonalHabit` Add / Remove:** e.g. *"Đọc sách 3 lần/tuần mỗi lần 45 phút buổi tối"* $\to$ appends `PersonalHabit` (`frequency_per_week=3`, `duration_min=45`, `preferred_window="EVENING"`), re-solves via `ScheduleController.solve_schedule`, saves workspace state if `auto_save=True`, and returns standard chat turn response dict (`status="APPLIED"`, `reply_vi`, `updated_commitments`, `schedule`, `post_actions`).
3. **Blind Evaluation Aggregation (`Wave 3`):**
   - Verify `python -B tools/member_eval/evaluate_schedule.py --mode report` / `GET /api/eval/report?write_md=true` cleanly aggregates all member review JSONs into `tools/member_eval/Calibration_Report.md`.

### Verification Commands (Must Pass 100% Before PR)
```powershell
python -B -m pytest tests/logical/test_profile_habit_chat.py tests/logical/test_member_eval_system.py -q
python -B tests/clean_runner.py --pass
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [ ] Tạo `smartschedule/api/chat/profile_habit_chat.py` xử lý đổi Giờ ngủ ($\ge 6\text{h}$), Nhịp sinh học, và thêm/xóa Thói quen hàng tuần (`PersonalHabit`).
- [ ] Viết unit test `tests/logical/test_profile_habit_chat.py` kiểm tra đủ các câu tiếng Việt tự nhiên & cảnh báo khi ngủ dưới 6 tiếng.
- [ ] **(Tối Thứ Bảy 28/11 — Wave 3)** Mở cổng `8010`, thu thập đủ phiếu chấm mù của 7 thành viên và xuất `tools/member_eval/Calibration_Report.md`.
