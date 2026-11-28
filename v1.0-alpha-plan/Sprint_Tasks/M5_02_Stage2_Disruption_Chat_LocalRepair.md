# M5_02 — Stage 2 Plan: Conversational Disruption Repair (`disruption_chat.py` — Pattern `P8`)
**Trạng thái Stage 2:** `[x] DONE`  
**Nhánh Git:** `v1.0-alpha/m5-cross-week-adaptation-and-repair`  
**Điều kiện tiên quyết:** Stage 1 (`M5_01`) đã `[x] DONE`  
**Phạm vi File của Stage 2 (DUY NHẤT 1 FILE MỚI):**
1. **CREATE:** `smartschedule/api/chat/disruption_chat.py`  
*(TUYỆT ĐỐI KHÔNG CHẠM VÀO `smartschedule/api/chat/handlers.py` hay `thinking_stage.py`!)*

---

## 1. BỐI CẢNH GHÉP NỐI LIÊN THÀNH VIÊN (`M5` $\leftrightarrow$ `M4` & `M2`)

1. **Với `M4` Trọng Tiến (`handlers.py` ở Wave 1B):**
   - `M4` sẽ import động `from smartschedule.api.chat.disruption_chat import ...` bên trong `try / except ImportError`.
   - Do `M4` có thể truyền nguyên `payload: dict` HOẶC truyền các đối số rời giống `M3` (`prompt`, `profile`, `tasks_raw`, `pinned_raw`, `completed_blocks`, `algorithm`, `workspace_id`, `auto_save`), hàm `handle_disruption_chat_turn` của chúng ta **PHẢI HỖ TRỢ ĐỒNG THỜI CẢ HAI CÁCH GỌI** để đảm bảo 0% lỗi `TypeError` khi ghép nhánh!
2. **Với `M2` Nguyên Khánh (`thinking_stage.py` ở Wave 1B):**
   - Hiện tại trên nhánh của ta, `build_thinking_summary(...)` trong `thinking_stage.py` chỉ nhận 8 tham số bắt buộc (`intent`, `context_note_vi`, `chosen_solver`, `escalated_from_greedy`, `exec_ms`, `peak_match_pct`, `tasks_placed`, `tasks_total`).
   - Sau khi `M2` merge, `build_thinking_summary` sẽ có thêm `pattern_rules`, `repair_stability_pct`.
   - Vì vậy, trong `disruption_chat.py`, ta dùng `inspect.signature(build_thinking_summary)` để truyền thêm `repair_stability_pct` / `pattern_rules` nếu có, **VÀ** luôn tự gán bổ sung `thinking["pattern_rules"] = [...]` nếu dict trả về chưa có khóa `"pattern_rules"`! Nhờ vậy `M6` (`chat-assistant.js`) luôn hiển thị được huy hiệu **`Pattern P8 -> LOCAL_INSERTION`** bất kể thứ tự merge!

---

## 2. ĐẶC TẢ CHI TIẾT `smartschedule/api/chat/disruption_chat.py`

### 2.1. Bộ Nhận Diện Ý Định Sự Cố Đột Xuất (`is_disruption_intent` & alias `is_disruption_prompt` — `Fix M-6`)

```python
def is_disruption_intent(
    prompt: str,
    mode_hint: str = "AUTO",
    pending_draft: Optional[Dict[str, Any]] = None,
) -> bool:
```
*(Cung cấp thêm alias `def is_disruption_prompt(prompt: str) -> bool: return is_disruption_intent(prompt)` để tương thích mọi cách gọi).*

**Quy tắc phân loại chính xác cao (`< 1 ms`, không bắt nhầm lịch cố định hàng tuần hoặc bài tập):**
1. Nếu `pending_draft` là dict và `pending_draft.get("intent") == "DISRUPTION_REPAIR"` $\to$ trả về `True` ngay (đang trả lời bổ sung giờ/thứ cho sự cố hỏi dở ở lượt trước!).
2. Nếu `(mode_hint or "").strip().upper() in ("DISRUPTION", "DISRUPTION_REPAIR")` $\to$ trả về `True`.
3. Chuẩn hóa không dấu chữ thường `norm = _strip_accents(prompt or "").lower()`.
4. **Rào chắn loại trừ (Negative Guards — cực kỳ quan trọng!):**
   - Nếu câu có từ khóa **lặp lại định kỳ hàng tuần/hàng ngày** (`hang ngay`, `moi ngay`, `hang tuan`, `moi tuan`, `moi thu`, `lap lai`, `thoi khoa bieu`, `co dinh`, `daily`, `weekly`, `ca hoc`, `lich hoc`) mà **KHÔNG** có từ khóa khẩn cấp (`dot xuat`, `khan cap`, `phat sinh`, `ket lich`) $\to$ trả về `False` (để nhường cho `ADD_RECURRING`).
   - Nếu câu là yêu cầu xóa/hoàn thành/đổi deadline (`xoa `, `huy `, `lam xong`, `hoan thanh`, `doi deadline`, `gia han`) $\to$ trả về `False`.
5. **Từ khóa kích hoạt sự cố đột xuất một lần (Positive Disruption Cues):**
   - Nhóm 1 (Từ khóa sự cố rõ ràng): `\b(?:dot\s*xuat|khan\s*cap|phat\s*sinh|bat\s*ngo|cup\s*dien|mat\s*dien|ket\s*lich|ket\s*xe|hong\s*xe|di\s*kham|nhap\s*vien|om\s*dot\s*xuat|urgent|emergency|unexpected)\b`
   - Nhóm 2 (Báo bận/kẹt/họp chèn vào khung giờ cụ thể): `\b(?:ban\s+viec|ban\s+hop|co\s+lich\s+hop|hop\s+clb|hop\s+nhom\s+gap|viec\s+rieng|viec\s+gia\s*dinh|busy)\b` đi kèm dấu hiệu thời gian/buổi/thứ (và không có từ khóa giao bài tập như `deadline`, `nop bai`, `lam bai`).

---

### 2.2. Bóc Tách Thông Tin Sự Cố Từ Câu Chat Tiếng Việt / Tiếng Anh (`extract_disruption_fields`)
Tận dụng trực tiếp các hàm chuẩn sẵn có trong `smartschedule.nlp.clause_condenser` (`_extract_time_range`, `_resolve_day_token`, `_resolve_now_weekday`, `_clean_conversational_title`, `_WEEKDAY_VI_MAP`) + `smartschedule.nlp.parser_controller` (`_strip_accents`):
1. **`day_of_week`:**
   - Gộp dữ liệu từ `pending_draft` (nếu có) với câu trả lời mới của user.
   - Dò thứ trong tuần qua `_resolve_day_token(prompt, now_day)` (`Thứ 2..CN`, `hôm nay`, `ngày mai`, `ngày kia`).
2. **`start_time` & `end_time`:**
   - Ưu tiên `_extract_time_range(norm)` (bắt chuẩn `"từ 14h đến 16h"`, `"19:30 - 21:00"`, `"7h30 tối đến 9h tối"`).
   - Fallback thông minh nếu người dùng nói `"lúc 14h kéo dài 2 tiếng"` / `"từ 19h30 trong 90 phút"`: bắt giờ bắt đầu + cộng thời lượng để suy ra `end_time`!
   - Kiểm tra hợp lệ: `end_slot_offset > start_slot_offset` (không cho phép sự cố 0 phút hoặc ngược giờ).
3. **`title`:**
   - Làm sạch câu để lấy tên sự kiện tự nhiên (ví dụ: `"Họp CLB đột xuất"`, `"Bận việc cá nhân đột xuất"` nếu câu quá ngắn chỉ ghi `"bận đột xuất thứ 5 14h-16h"`).

---

### 2.3. Xử Lý Hỏi Lại Đa Lượt (`NEEDS_CLARIFICATION`) Khi Thiếu Thứ Hoặc Khung Giờ
Nếu thiếu `day_of_week` hoặc thiếu `(start_time, end_time)`:
- Trả về dictionary chuẩn `/api/chat/turn` với:
  - `status = "NEEDS_CLARIFICATION"`
  - `intent = "DISRUPTION_REPAIR"`
  - `finalized = False`
  - `pending_draft = {"intent": "DISRUPTION_REPAIR", "title": title, "day_of_week": day_of_week, "start_time": start_time, "end_time": end_time}`
  - `missing_fields = [...]` (ví dụ `["day_of_week"]` hoặc `["time_range"]`)
  - `reply_vi`: Câu hỏi thân thiện, ngắn gọn bằng tiếng Việt (ví dụ: *"Bạn bị bận đột xuất vào khung giờ nào (từ mấy giờ đến mấy giờ) trong ngày Thứ Tư để mình dời nhẹ các phiên học bị trùng nhé?"*)
  - `quick_chips`: 3 gợi ý 1 chạm thực tế (ví dụ: `[{"label": "14:00 – 16:00", "prompt": "Từ 14h đến 16h"}, {"label": "19:00 – 21:00", "prompt": "Từ 19h đến 21h"}, {"label": "Hủy báo bận", "prompt": "Hủy thao tác"}]` — và hỗ trợ hủy sạch `status="CANCELLED"` nếu người dùng bấm/gõ `"hủy thao tác"`!).

---

### 2.4. Thực Thi `LocalRepairEngine` (`LOCAL_INSERTION`) + Hậu Kiểm Công Thái Học (`Fix M-8`) + Lưu Vết Sự Cố (`Fix M-5`)

Khi đã có đủ `(day_of_week, start_time, end_time)`:
1. **Chuẩn bị lịch hiện tại (`current_schedule`):**
   - Nếu caller/workspace đã có `current_schedule` hợp lệ (khớp danh sách task hiện tại) $\to$ validate thành `ScheduleOutput`.
   - Nếu chưa có $\to$ gọi `ScheduleController.solve_adaptive(profile, task_models, algorithm=algorithm, pinned_blocks=pinned_models)`.
2. **Chạy sửa cục bộ giữ ổn định tối đa (`Pattern P8`):**
   - Tạo `disruption = DisruptionEvent(event_id=f"DISR_{uuid6}", title=title, day_of_week=day_of_week, start_time=start_time, end_time=end_time, now_iso=profile.now)`.
   - Gọi `buffered_tasks = ScheduleController.apply_estimate_buffer(profile, ScheduleController.expand_personal_habits(profile, task_models))`.
   - Gọi `rep_out = LocalRepairEngine.repair_disruption(profile=profile, tasks=buffered_tasks, current_schedule=current_schedule, disruption=disruption, mode="LOCAL_INSERTION", algorithm=eff_algo)`.
   - Chú ý: `ScheduleController.annotate_estimate_buffer(profile, buffered_tasks, rep_out.schedule)` để bảo toàn nhãn giải thích trên các block.
3. **Cập nhật `updated_profile.fixed_events`:**
   - Thêm sự kiện mới `FixedEvent(event_id=disruption.event_id, title=title, day_of_week=day_of_week, start_time=start_time, end_time=end_time, category="DISRUPTION")` vào bản sao `updated_profile` (kiểm tra chống trùng lặp nếu đã tồn tại cùng `(day_of_week, start_time, end_time, title)`).
4. **Hậu kiểm công thái học (`Fix M-8`):**
   - Gọi `ergo_check = ScheduleController.inspect_repair_ergonomics(updated_profile, rep_out)`.
   - Xây dựng lời phản hồi `reply_vi` rõ ràng cho người dùng thường (không viết tên biến code!):
     - Nêu rõ: Đã ghi nhận lịch bận **`<title>` (`<Thứ Tiếng Việt> <start>–<end>`)**.
     - Nếu `rep_out.directly_hit_blocks == 0`: *"Khung giờ này đang trống nên toàn bộ lịch học của bạn được giữ nguyên 100%!"*
     - Nếu có dời lịch: nêu ngắn gọn số phiên vừa dời sang ô trống gần nhất, độ ổn định lịch đạt **`{rep_out.stability_score:.1f}%`** (các phiên khác không bị xáo trộn).
     - Nếu `ergo_check["has_ergonomic_degradation"]` là `True`: thêm 1 câu nhắc tinh tế *"Lưu ý: phiên học tập trung cao vừa dời tạm sang khung giờ năng lượng thấp để giữ lịch tuần ít xáo trộn nhất. Nếu muốn ưu tiên sức khỏe hơn, bạn có thể bấm nút xếp tối ưu lại bên dưới."* kèm `quick_chips` gợi ý.
5. **Lưu trạng thái & Ghi vết `disruption_logs` (`Fix M-5`):**
   - Nếu `auto_save=True`: tải `existing_state = load_workspace_state(workspace_id)` (nếu có), cập nhật `commitments`, `tasks`, `pinnedBlocks`, `currentSchedule`, và nối thêm bản ghi `{"event_id": disruption.event_id, "title": title, "day_of_week": day_of_week, "start_time": start_time, "end_time": end_time, "disruption_slot_window": f"{day_of_week} {start_time}-{end_time}"}` vào mảng `disruption_logs` (giữ tối đa `50` mục gần nhất) rồi gọi `save_workspace_state(..., workspace_id=workspace_id)`.
6. **Đóng gói `thinking_summary` (có `Pattern P8` tường minh) & Trả về đúng Schema 20 khóa (`README_agents.md §2.1`):**
   - Đính kèm `pattern_rules`:
     ```python
     [
         {
             "pattern_id": "P8",
             "pattern_name": "Schedule Whiplash Prevention (Minimum-Perturbation Repair)",
             "causal_link_vi": "Đóng băng các phiên không va chạm để tránh đảo lộn thói quen cả tuần khi có việc đột xuất",
             "deterministic_rule": f"LOCAL_INSERTION: freeze PINNED/DONE & non-colliding blocks -> min |Δs| (Stability = {rep_out.stability_score:.1f}%)",
         }
     ]
     ```
   - Kèm thêm khóa phụ `"repair_summary"` (`stability_score`, `moved_blocks_count`, `directly_hit_blocks`, `changes`, `ergonomic_check`) để cả UI lẫn unit test kiểm tra trực tiếp dễ dàng.

---

## 3. LỆNH KIỂM THỬ ĐỘC LẬP KẾT THÚC STAGE 2

Sau khi tạo xong `smartschedule/api/chat/disruption_chat.py`, chạy ngay lệnh kiểm tra sau:
```powershell
python -B -c "import json; from pathlib import Path; from smartschedule.api.chat.disruption_chat import is_disruption_intent, handle_disruption_chat_turn; assert is_disruption_intent('Chiều thứ 4 từ 14h đến 16h họp CLB đột xuất') is True; assert is_disruption_intent('Thêm lịch học cố định mỗi thứ 4 từ 8h đến 10h') is False; assert is_disruption_intent('Làm bài tập Giải tích 2 tiếng trước thứ 6') is False; comm=json.loads(Path('data/presets/sample_week_commitments.json').read_text('utf-8')); tasks=json.loads(Path('data/presets/sample_week_tasks.json').read_text('utf-8')); res=handle_disruption_chat_turn({'prompt': 'Thứ Hai từ 08:00 đến 09:30 họp CLB đột xuất', 'commitments': comm, 'tasks': tasks, 'auto_save': False}); assert res['status'] == 'APPLIED' and res['repair_summary']['stability_score'] >= 90.0, res; print('STAGE 2 SMOKE OK: stability =', res['repair_summary']['stability_score'])"
```
Nếu lệnh in ra `STAGE 2 SMOKE OK` với `stability >= 90.0`, đánh dấu `[x] DONE` ở đầu file này và trong [`M5_00_Master_Index.md`](./M5_00_Master_Index.md), rồi chuyển sang [`M5_03_Stage3_FastAPI_Endpoints_And_MultiWeekSim.md`](./M5_03_Stage3_FastAPI_Endpoints_And_MultiWeekSim.md).
