# Báo Cáo Kiểm Chứng & Thẩm Định Kế Hoạch `M5` Trước Khi Triển Khai Code
**Đối tượng thẩm định:** [`M5_Le_Tien_Binh.md`](./M5_Le_Tien_Binh.md) (`Builder 1 — Core Engineering & Idea Lead`)  
**Ngày kiểm chứng:** `27/11/2026`  
**Phạm vi đối chiếu trực tiếp trên mã nguồn `main` (`8f334b1`):**
- Core Domain: [`controller.py`](../../smartschedule/core/controller.py), [`models.py`](../../smartschedule/core/models.py), [`calibration.py`](../../smartschedule/core/calibration.py), [`estimate_buffer.py`](../../smartschedule/core/estimate_buffer.py), [`storage.py`](../../smartschedule/core/storage.py)
- Solvers & API: [`local_repair.py`](../../smartschedule/core/solvers/local_repair.py), [`ergonomic_engine.py`](../../smartschedule/core/solvers/ergonomic_engine.py), [`app.py`](../../smartschedule/api/app.py), [`handlers.py`](../../smartschedule/api/chat/handlers.py)
- Đồng bộ liên thành viên: [`M1_Pham_Duc_Minh.md`](./M1_Pham_Duc_Minh.md), [`M4_Nguyen_Trong_Tien.md`](./M4_Nguyen_Trong_Tien.md), [`M6_Le_Minh_Nhat.md`](./M6_Le_Minh_Nhat.md), [`M7_Nguyen_Nguyen_Gia_Bao.md`](./M7_Nguyen_Nguyen_Gia_Bao.md), [`Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md)

---

## 1. KẾT LUẬN TỔNG QUAN (VERDICT)

> [!IMPORTANT]
> ### **PHÁN QUYẾT: ĐỒNG Ý CÓ ĐIỀU KIỆN (APPROVE WITH 6 MANDATORY MODIFICATIONS)**
> - **Không bác bỏ kế hoạch `M5`**, vì 4 mảnh ghép của `M5` giải quyết đúng những khoảng trống lớn nhất của SmartSchedule hiện tại (khởi tạo tuần thực tế + CRUD lẻ cho người dùng thật, sửa lịch cục bộ chống xáo trộn `P8`, và vòng lặp học thích nghi xuyên tuần `P13`).
> - **TUY NHIÊN, TUYỆT ĐỐI KHÔNG CODE NGUYÊN XI 100% THEO MÔ TẢ SƠ BỘ TRONG `M5.md` MÀ CHƯA SỬA 6 LỖ HỔNG KỸ THUẬT & SẢN PHẨM DƯỚI ĐÂY.** Đối chiếu trực tiếp với source code hiện hữu cho thấy: nếu code ngây thơ theo đúng chữ trên `M5.md`, tính năng đắt giá nhất (`CrossWeekPreferenceAdapter` gán $\hat{\alpha}_{c,\ell}$ theo môn) **sẽ bị hàm `ScheduleController.apply_estimate_buffer()` ghi đè mất sạch 100% khi chạy solver**, đồng thời 2/3 nhánh học hành vi sẽ chỉ chạy được trên dữ liệu giả lập (`Simulator`) mà bị "mù dữ liệu" đối với người dùng thật trên SQLite!
> - Tin rất tốt: **Cả 6 điểm cần điều chỉnh đều nằm gọn 100% trong các file thuộc quyền sở hữu độc quyền (Exclusive Ownership) của `M5`** (`cross_week_adapter.py`, `disruption_chat.py`, `controller.py`, `app.py`) — không cần phá vỡ quy tắc `0% Merge Conflict` hay sửa sang file của thành viên khác.

---

## 2. ĐÁNH GIÁ CHI TIẾT TỪNG HẠNG MỤC: HIỆU QUẢ DỰ ÁN vs. THỰC TẾ THƯƠNG MẠI

| Hạng mục trong `M5.md` | Giá trị Đồ án CT (Academic) | Giá trị Thực tế & Thương mại (Commercial SaaS) | Lợi ích vs. Bất lợi | Kết luận Hạng mục |
| :--- | :---: | :---: | :--- | :---: |
| **1. `init-real-week` + API Xóa/Sửa lẻ (`tasks/delete`, `fixed-events/*`)** | **8.5 / 10** (Mở khóa Wave 2 UI của `M1` & `M6`) | **10 / 10 (Bắt buộc phải có)** | Hiện mở app bị ép nạp lịch mẫu ngày `02/11/2026` và thiếu API xóa/sửa lẻ sự kiện cố định. Không có cụm này thì sản phẩm không thể dùng hàng ngày. **0 bất lợi.** | **ĐỒNG Ý 100%** |
| **2. Chat Báo Bận Đột Xuất $\to$ `LocalRepairEngine` (`disruption_chat.py` — `P8`)** | **9.5 / 10** (Hiện thực hóa trực tiếp Pattern `P8` trên khung hội thoại) | **9.5 / 10 (Lợi thế cạnh tranh lớn so với Motion / Reclaim.ai)** | Điểm bị phàn nàn nhiều nhất ở các app thương mại (*Motion*, *SkedPal*) là **"Schedule Whiplash"**: thêm 1 cuộc họp 1 tiếng làm đảo lộn 70% lịch cả tuần. Dùng `LOCAL_INSERTION` giữ nguyên $\ge 90\%$ các ca không va chạm là tính năng cực kỳ ăn tiền ngoài đời thực. Cần lọc kỹ câu lệnh để không nhầm với thêm lịch cố định hàng tuần. | **ĐỒNG Ý (Cần rào chắn phân loại câu lệnh)** |
| **3. Học Thích Nghi Xuyên Tuần (`cross_week_adapter.py` — `P13`)** | **10 / 10** (Trả lời trực tiếp `Proposal §7.8.3–7.8.4` & câu hỏi phản biện về thích nghi cá nhân) | **8.5 / 10 nếu giữ chuẩn `LoA-4` (Preview + Xác nhận); tụt xuống `3 / 10` nếu tự động sửa ngầm!** | Học hệ số trừ hao theo từng loại việc (`Code` hay lố giờ hơn `Đọc bài`) thực tế hơn hẳn 1 hệ số chung. **NHƯNG** nếu tự ý lật nhịp sinh học (`Sáng -> Tối`) hoặc tự bóp giờ mà không hỏi ý kiến người dùng sẽ gây mất kiểm soát ("Hiệu ứng Clippy"). Ngoài ra đang có **4 lỗi khớp nối với code gốc** cần sửa ngay. | **ĐỒNG Ý NHƯNG BẮT BUỘC MODIFY 4 ĐIỂM** |
| **4. Mô Phỏng Đa Tuần (`/api/simulation/multi-week` — `P14b`)** | **10 / 10** (Vũ khí chốt điểm thuyết trình cuối kỳ & kiểm chứng toán học 4 tuần trong vài trăm ms) | **7.0 / 10 (Công cụ R&D / Digital-Twin Sandbox & Demo B2B, KHÔNG phải tính năng cho end-user)** | Trong sản phẩm thương mại, người dùng phổ thông không bấm "Chạy mô phỏng 25 sinh viên ảo". Đặt nó ở tầng API nghiên cứu / `Developer Mode` là hoàn toàn chuẩn xác (vừa ăn trọn điểm học thuật, vừa không làm rối UI người dùng thật). Cần chỉnh lại thông số mặc định `n_students` để không vỡ SLA `< 500 ms`. | **ĐỒNG Ý (Đặt đúng chỗ ở API / Dev Mode + chỉnh SLA)** |

---

## 3. PHÁT HIỆN 6 LỖI KỸ THUẬT & CẠM BẪY SẢN PHẨM KHI ĐỐI CHIẾU SOURCE CODE THẬT

Đây là lý do việc kiểm chứng trước khi code là cực kỳ cần thiết. Dưới đây là **6 phát hiện có bằng chứng trực tiếp từ mã nguồn hiện tại**:

### 🚨 Phát hiện #1 (Lỗi Nghiêm Trọng Nhất): `controller.py` hiện đang GHI ĐÈ XÓA SẠCH $\hat{\alpha}_{c,\ell}$ riêng từng môn!
- **Bằng chứng trong code gốc:** Xem [`smartschedule/core/controller.py`](../../smartschedule/core/controller.py#L104-L143) (`ScheduleController.apply_estimate_buffer`) và dòng `145–164` (`annotate_estimate_buffer`):
  - Khi `profile.buffer_mode == "COGNITIVE_LOAD"`, dòng `119–128` lặp qua toàn bộ `tasks` và **ép cứng mọi task** về `alpha_light = profile.alpha_light` (`1.20`) và `alpha_heavy = profile.alpha_heavy` (`1.35`)!
  - Ngược lại, khi `profile.buffer_mode == "HABIT"` (mặc định của hệ thống), nếu `profile.estimate_habit` có giá trị (`RARELY`/`SOMETIMES`/`OFTEN`), dòng `141` cũng **ghi đè ngược** `t.buffer_mode = "HABIT"` và xóa sạch `COGNITIVE_LOAD` trên từng task; còn nếu `estimate_habit == None` thì `annotate_estimate_buffer` (dòng `151`) thoát sớm, bỏ qua luôn thẻ giải thích `ESTIMATE_BUFFER`!
- **Hậu quả nếu code nguyên xi `M5.md`:** Dù `cross_week_adapter.py` có tính đúng $\hat{\alpha}_{\text{CODING}} = 1.42$ và $\hat{\alpha}_{\text{READING}} = 1.08$ rồi gán vào `next_tasks`, ngay khoảnh khắc gọi `ScheduleController.solve_schedule()`, toàn bộ hệ số theo môn bị xóa trắng về cùng 1 số!
- **Cách sửa triệt để (Nằm gọn trong `controller.py` do `M5` độc quyền sở hữu):**
  - Trong `ScheduleController.apply_estimate_buffer()`: Nếu một `Task` đã được gắn cờ hiệu chuẩn riêng (ví dụ `t.buffer_mode == "COGNITIVE_LOAD"` và task có `alpha_light` / `alpha_heavy` đã được adapter tinh chỉnh khác mặc định hoặc có trong `t.model_fields_set`), **giữ nguyên `t.alpha_light`, `t.alpha_heavy` và tính `t.buffer_multiplier = multiplier_for_load(t.cognitive_load, t.alpha_light, t.alpha_heavy)` của riêng task đó**, tuyệt đối không lấy `profile.alpha_*` đè lên!
  - Trong `annotate_estimate_buffer()`: Cho phép gắn lý do giải thích nếu `buf_mode == "COGNITIVE_LOAD"` ở cấp `profile` **HOẶC** ở cấp từng `task`.

---

### 🚨 Phát hiện #2 (Lỗi Toán Học): Bẫy "Co Rút Kép" (Double-Shrinkage) làm mô hình học chậm gấp 3 lần thiết kế
- **Bằng chứng trong code gốc:** Trong [`smartschedule/core/calibration.py`](../../smartschedule/core/calibration.py#L110), biến `per_category_ewma` được khởi tạo tại `default_alpha` ($\alpha_0 = 1.20$).
- **Phân tích toán học:**
  - Giả sử tuần 1 sinh viên làm `1` bài `CODING` bị lố giờ thực tế $r_1 = 1.60$ ($\lambda = 0.30, \kappa = 3.0$).
  - Nếu khởi tạo $\text{EWMA}_c^{(0)} = \alpha_0 = 1.20$, ta có $\text{EWMA}_c^{(1)} = 0.30(1.60) + 0.70(1.20) = 1.32$ (đã bị kéo $70\%$ về $\alpha_0$).
  - Sau đó lại đưa tiếp vào công thức co rút Bayes trong `M5.md`:
    $$\hat{\alpha}_{c} = \frac{1}{1 + 3}(1.32) + \frac{3}{1 + 3}(1.20) = \mathbf{1.23}$$
  - Trọng số thực sự của dữ liệu quan sát bị tụt từ $\frac{1}{1+3} = 25\%$ xuống chỉ còn $0.30 \times 25\% = \mathbf{7.5\%}$! Hệ quả là qua 4 tuần mô phỏng, hệ số $\hat{\alpha}_c$ nhích quá chậm, làm giảm hiệu quả hội tụ của biểu đồ đánh giá cuối kỳ.
- **Cách sửa chuẩn xác trong `cross_week_adapter.py`:**
  - Khởi tạo $\text{EWMA}_c$ thuần mẫu tại quan sát đầu tiên: $\text{EWMA}_c^{(1)} = r_1$, và từ mẫu thứ $k \ge 2$ mới cập nhật $\text{EWMA}_c^{(k)} = \lambda r_k + (1 - \lambda)\text{EWMA}_c^{(k-1)}$.
  - Khi đó $\text{EWMA}_c$ là ước lượng trung bình trượt có trọng số thời gian không chệch của mẫu thực tế, còn nhân tử Bayes $\frac{n_c}{n_c + \kappa}$ đảm nhiệm **đúng 1 lần co rút duy nhất** về tiên nghiệm $\alpha_0(\ell) \in \{1.20, 1.35\}$! (Với $r_1 = 1.60 \implies \hat{\alpha}_c = 0.25(1.60) + 0.75(1.20) = \mathbf{1.30}$ — hợp lý và nhạy đúng kỳ vọng).

---

### 🚨 Phát hiện #3 (Lỗi Kiến Trúc Dữ Liệu): Hạ `hourly_levels` cho `chronic_disruption_zones` sẽ làm hỏng cả 6 ngày còn lại trong tuần!
- **Bằng chứng trong code gốc:** Xem [`smartschedule/core/models.py`](../../smartschedule/core/models.py#L122-L160) (`CircadianEnergyProfile.level_for_slot`):
  ```python
  slot_in_day = int(slot) % 96
  hour = slot_in_day // 4
  return self.level_for_hour(hour)
  ```
  `hourly_levels` chỉ có khóa `0..23` (24 giờ trong ngày) và **áp dụng lặp lại tuần hoàn cho cả 7 ngày trong tuần (`slot % 96`)**!
- **Hậu quả nếu chọn phương án A trong `M5.md` (dòng 40):** Nếu sinh viên chỉ hay họp CLB đột xuất vào **Tối Thứ Năm `19:30–21:00`**, việc hạ `hourly_levels[19..20]` xuống `1` sẽ khiến thuật toán tưởng sinh viên bị kiệt sức lúc `19:00–21:00` vào cả **Thứ Hai, Thứ Ba, Thứ Tư, Thứ Sáu, Thứ Bảy và Chủ Nhật** (phạt nhầm $6/7 \approx 86\%$ khung giờ tối của cả tuần)!
- **Cách sửa chuẩn xác trong `cross_week_adapter.py`:**
  - **Loại bỏ phương án hạ `hourly_levels` theo ngày lẻ**; chỉ cập nhật `hourly_levels` khi đổi nhịp sinh học toàn cục (`focus_preference`).
  - Đối với `chronic_disruption_zones` lặp lại $\ge 2$ lần tại đúng cặp `(day_of_week, hour_band)`, **luôn dùng phương án B đã mở ngoặc trong `M5.md`**: sinh ra một sự kiện đệm dự phòng `FixedEvent(event_id="ADV_RESERVE_...", category="ADVISORY_BUFFER", day_of_week=day, start_time=..., end_time=...)` vào đúng thứ đó (kèm điều kiện an toàn: chỉ chèn khối đệm này nếu tổng tải tuần tới chưa vượt ngưỡng quá tải $\rho \le 0.90$, để không vô tình đẩy lịch sang trạng thái sập deadline).

---

### 🚨 Phát hiện #4 (Khoảng Trống Thực Tế vs. Giả Lập): Bảng `completion_logs` của người dùng thật đang thiếu trường dữ liệu cho Nhánh 2 & Nhánh 3!
- **Bằng chứng trong code gốc:** Xem [`smartschedule/core/storage.py`](../../smartschedule/core/storage.py#L58-L66) và [`smartschedule/api/app.py`](../../smartschedule/api/app.py#L746-L790):
  - Bảng SQLite `completion_logs` hiện chỉ lưu đúng 6 trường: `(task_id, category, estimated_duration_min, actual_duration_min, completed_at)`.
  - Nó **KHÔNG lưu** `window` (`MORNING`/`AFTERNOON`/`EVENING`), `cognitive_load`, `adhered` (`True/False`), `fatigue_after`, hay `disruption_slot_window`!
- **Đánh giá thực tế thương mại:**
  - Trong `InSilicoStudentSimulator` của Gia Bảo (`M7`), máy tự sinh ra đủ `fatigue_after = 0.74`, `adhered = False`, `window = "MORNING"`.
  - Nhưng **ngoài đời thực, không một người dùng thương mại nào ngồi nhập "Độ mệt mỏi sau ca học của tôi là 0.74" cả!** Nếu `cross_week_adapter.py` chỉ đọc các trường của Simulator, thì khi người dùng thật bấm `adapt-next-week`, hệ thống chỉ chạy được mỗi Nhánh 1 (hệ số $\alpha$), còn Nhánh 2 (Nhịp sinh học thực tế) và Nhánh 3 (Điều nhịp & Vùng sự cố) sẽ tê liệt hoàn toàn!
- **Cách sửa thông minh ngay trong `app.py` + `cross_week_adapter.py` (Không cần sửa `storage.py`!):**
  1. **Tự suy luận `window` cho người dùng thật:** Trong `cross_week_adapter.py` và `app.py`, nếu bản ghi log từ `completion_logs` không có trường `window`, tự động suy ra buổi (`06–12h -> MORNING`, `12–18h -> AFTERNOON`, `18–24h -> EVENING`) từ giờ của khối lịch đã hoàn thành (`completedBlocks` trong `workspace_state`) hoặc từ dấu thời gian `completed_at`!
  2. **Đo tỷ lệ bám lịch thật (`AdherenceRate`) từ `workspace_state`:** Đối chiếu danh sách `currentSchedule.blocks` với `completedBlocks` của tuần vừa qua trong `workspace_state` để biết buổi sáng người dùng bỏ lỡ bao nhiêu ca so với buổi tối.
  3. **Ghi vết sự cố thật vào `workspace_state["disruption_logs"]`:** Mỗi khi `/api/repair` hoặc `disruption_chat.py` chạy (đều nằm trong file của `M5`), tự động lưu nhẹ `{day_of_week, start_time, end_time}` (giữ tối đa 50 mục gần nhất) ngay trong JSON `workspace_state`. Nhờ vậy, tính năng phát hiện "Chiều Thứ 5 tuần nào cũng bận đột xuất" hoạt động **100% với người dùng thật**!
  4. **Kích hoạt điều nhịp (`Pacing`) bằng tín hiệu thực tế:** Dùng tỷ lệ lố giờ ở các ca dài `> 60 phút` ($\ge 50\%$) hoặc lịch sử tuần trước bị Crunch làm tín hiệu chính cho người dùng thật; còn `mean_fatigue > 0.65` đóng vai trò tín hiệu bổ trợ khi chạy `InSilicoStudentSimulator`.

---

### 🚨 Phát hiện #5 (Bẫy Pydantic v2 & Ngưỡng Tách Khối): Gán `work_rhythm="BALANCED"` qua `model_copy` không tự thu nhỏ `max_chunk_min`!
- **Bằng chứng trong code gốc:** Xem [`smartschedule/core/models.py`](../../smartschedule/core/models.py#L31-L35) và dòng `337–349`:
  - Hằng số `WORK_RHYTHM_BOUNDS["BALANCED"]` trong `models.py` là `(45, 90)` (tối đa vẫn `90 phút`), trong khi mục tiêu của `M5.md` (dòng 16 & 40) là giảm độ dài phiên xuống `45–75 phút` sau tuần căng thẳng khi các ca `> 60 phút` bị đứt gãy.
  - Hơn nữa, trong Pydantic v2, gọi `task.model_copy(update={"work_rhythm": "BALANCED"})` **không tự chạy lại `@model_validator(mode="after")`**, nên nếu task cũ đang có `max_chunk_min = 120` (`FLOW`), nó vẫn giữ nguyên `120 phút` khi vào bộ giải [`ergonomic_engine.py`](../../smartschedule/core/solvers/ergonomic_engine.py#L140-L144)!
- **Cách sửa trong `cross_week_adapter.py`:** Khi điều chỉnh nhịp làm việc cho tuần kế tiếp, cập nhật tường minh cả 4 thuộc tính trên bản sao của task: `work_rhythm="BALANCED"` (hoặc `"CUSTOM"`), `min_chunk_min=45`, `max_chunk_min=75`, và `is_splittable=True` (nếu `duration_min > 75`).

---

### 🚨 Phát hiện #6 (Rủi ro UX Thương Mại & Mâu Thuẫn SLA `< 500 ms` ở Mô Phỏng Đa Tuần)
1. **Rủi ro UX Thương mại ("Bất lợi nhiều hơn tiện lợi" nếu thiếu rào chắn):**
   - *Tình huống thực tế:* Sinh viên vốn thích học sáng (`MORNING`), nhưng tuần thi giữa kỳ bị dồn việc nên phải thức đến `22:30` làm bù trước hạn `23:59`. Nếu bộ lọc ngây thơ thấy nhiều việc hoàn thành buổi tối mà tự ý lật hồ sơ sang Cú Đêm (`EVENING`), tuần sau toàn bộ bài khó bị đẩy xuống 9 giờ tối $\to$ **người dùng sẽ xóa app ngay lập tức!**
   - *Rào chắn bắt buộc trong `cross_week_adapter.py` & `app.py`:*
     - **Mặc định `apply=False` trên `/api/workspace/adapt-next-week` (Chuẩn `LoA-4`):** Hệ thống đóng vai trò *Cố vấn thông minh* — trả về bảng đối chiếu rõ ràng (`preference_shifts` bằng tiếng Việt dễ hiểu cho người dùng thường, kèm mã quy tắc `P13` cho `Developer Mode`) để người dùng bấm đồng ý mới áp dụng.
     - **Điều kiện lật nhịp sinh học chặt chẽ:** Chỉ đề xuất đổi `focus_preference` từ $w_{\text{stated}} \to w_{\text{best}}$ khi **cả hai khung giờ đều có ít nhất $n_w \ge 2$ phiên được xếp lịch**, điểm hiệu quả chênh lệch $\ge 0.22$, **VÀ** tỷ lệ bám lịch ở khung giờ khai báo ban đầu thực sự thấp ($< 65\%$).
     - **Chống phình hệ số kép (Anti-Double-Buffering) & Cho phép phục hồi:** Giữ nguyên `Task.duration_min` gốc của người dùng (chỉ cập nhật `alpha_light`/`alpha_heavy` trong đoạn khóa cứng `[1.00, 1.60]`), đồng thời nếu tuần tiếp theo sinh viên làm đúng giờ trở lại, EWMA tự động hạ $\hat{\alpha}_{c,\ell}$ nhẹ nhàng về `1.00–1.20` thay vì chỉ tăng một chiều.
2. **Mâu thuẫn thông số SLA `< 500 ms` giữa `M5.md` và `README_agents.md`:**
   - `M5.md` dòng 48 yêu cầu `K=4` tuần chạy trong **`< 500 ms`**, nhưng ví dụ payload ở [`README_agents.md`](../README_agents.md#L74) lại ghi `{"weeks": 4, "n_students": 25}`.
   - `25 sinh viên × 4 tuần = 100 lần gọi bộ giải SCORED_GREEDY` (`~40–70 ms/lần`) sẽ tốn khoảng **`4.0 – 7.0 giây`**, chắc chắn vượt `500 ms`!
   - *Cách xử lý chuẩn:* Đặt mặc định `n_students: int = 1, weeks: int = 4` cho chế độ tương tác trực tiếp (`4 lần giải ≈ 150–300 ms`, **đạt chuẩn `< 500 ms` 100%**), đồng thời vẫn hỗ trợ truyền `n_students = 25` khi chạy kịch bản lấy số liệu thống kê hàng loạt cho báo cáo/slide! Ngoài ra, cài sẵn nhánh dự phòng tự thân (`fallback simulator` gọn nhẹ) bên trong `try ... except ImportError` khi import `student_simulator` để PR của `M5` ở Wave 1A chạy độc lập xanh 100% ngay cả khi nhánh của `M7` chưa merge trước.

---

## 4. KIỂM CHỨNG KHỚP NỐI LIÊN THÀNH VIÊN (`0%` XUNG ĐỘT GIT)

| Thành viên phối hợp | Điểm giao tiếp với `M5` | Rủi ro xung đột / Lệch hợp đồng | Phương án khóa an toàn cho `M5` |
| :--- | :--- | :--- | :--- |
| **`M4` Trọng Tiến** (`Wave 1B`) | `M4` sửa `handlers.py` và gọi `handle_disruption_chat_turn` từ `disruption_chat.py` của `M5` | Nếu `M5` đổi tên hàm hoặc trả thiếu khóa JSON của `/api/chat/turn`, Wave 1B của `M4` sẽ gãy. | Thiết kế chữ ký hàm `handle_disruption_chat_turn(payload, ...)` + hàm phụ trợ `is_disruption_prompt(prompt)` thật sạch, trả về đúng chuẩn schema `/api/chat/turn` (`status`, `intent="DISRUPTION_REPAIR"`, `reply_vi`, `schedule`, `repair_summary`, `thinking_summary`). Đồng thời gắn fallback điều hướng an toàn trong `api_chat_turn` (`app.py`) khi `mode_hint == "DISRUPTION"` để test độc lập ngay ở Wave 1A. |
| **`M7` Gia Bảo** (`Wave 1A`) | `M7` tạo `student_simulator.py` gọi `adapt_preferences_for_next_week` của `M5`; `M5` mở `/api/simulation/multi-week` gọi ngược `InSilicoStudentSimulator` của `M7` | Hai bên cùng làm ở Wave 1A nên lúc viết test riêng chưa có file của nhau trên nhánh. | Thống nhất cứng chữ ký `adapt_preferences_for_next_week(profile, next_tasks, timeline_logs, kappa=3.0)` nhận linh hoạt cả dict từ Simulator lẫn dict từ `completion_logs` SQLite; bên trong `/api/simulation/multi-week` dùng `try/except ImportError` kèm bộ mô phỏng fallback tất định theo `seed`. |
| **`M6` Minh Nhật** (`Wave 2A`) & **`M1` Đức Minh** (`Wave 2B`) | Giao diện gọi `POST /api/workspace/init-real-week`, `/api/tasks/delete`, `/api/fixed-events/upsert`, `/api/fixed-events/delete` | UI có thể gửi thiếu `workspace_id` hoặc gửi cả state trực tiếp trong body lẫn lưu trong SQLite. | Cả 4 endpoint trong `app.py` đều hỗ trợ kép: vừa cập nhật vào SQLite `workspace_state` (qua `resolve_workspace_id`), vừa nhận/trả về `commitments`, `tasks`, `schedule` đã giải lại (`_enrich_response`) để UI cập nhật tức thì chỉ với 1 request. |

---

## 5. BẢNG TỔNG HỢP CÁC ĐIỂM MODIFY TRƯỚC KHI BẮT TAY VÀO CODE

| STT | Thành phần / File (Đều thuộc quyền `M5`) | Kế hoạch gốc trong `M5.md` | Chỉnh sửa chuẩn hóa khi triển khai Code |
| :-: | :--- | :--- | :--- |
| **M-1** | [`smartschedule/core/controller.py`](../../smartschedule/core/controller.py) | Chưa nhắc tới việc sửa `apply_estimate_buffer` | Giữ nguyên `t.alpha_light` & `t.alpha_heavy` cấp từng `Task` khi task đã được hiệu chuẩn theo môn (`COGNITIVE_LOAD` cấp task), không để `profile` ghi đè xóa mất. |
| **M-2** | `smartschedule/core/cross_week_adapter.py` | Tính EWMA rồi co rút Bayes | Khởi tạo $\text{EWMA}_c^{(1)} = r_1$ (tránh co rút kép 2 lần về $\alpha_0$); kẹp chặt $\hat{\alpha}_{c,\ell} \in [1.00, 1.60]$. |
| **M-3** | `smartschedule/core/cross_week_adapter.py` | Hạ `hourly_levels` hoặc thêm sự kiện dự phòng khi có sự cố lặp lại | **Không hạ `hourly_levels`** cho sự cố đơn ngày (tránh phạt nhầm cả 7 ngày/tuần); dùng sự kiện đệm `ADVISORY_BUFFER` đúng thứ đó khi tổng tải $\rho \le 0.90$. |
| **M-4** | `smartschedule/core/cross_week_adapter.py` | Đổi sang `work_rhythm="BALANCED"` | Gán tường minh `min_chunk_min=45, max_chunk_min=75, is_splittable=True` qua `model_copy` để vượt qua giới hạn không chạy lại validator của Pydantic v2. |
| **M-5** | [`smartschedule/api/app.py`](../../smartschedule/api/app.py) + `cross_week_adapter.py` | Phụ thuộc nhiều vào `timeline_logs` giàu thông tin của Simulator | Tự động suy luận `window` từ giờ hoàn thành/khối lịch, đối chiếu `completedBlocks` và lưu lịch sử sự cố nhẹ trong `workspace_state` để **người dùng thật hưởng trọn cả 3 nhánh học thích nghi**, mặc định `apply=False` (`LoA-4`). |
| **M-6** | [`smartschedule/api/app.py`](../../smartschedule/api/app.py) + `disruption_chat.py` | `/api/simulation/multi-week` `< 500 ms` | Mặc định `n_students=1, weeks=4` (`< 500 ms` chuẩn xác với `SCORED_GREEDY`), vẫn hỗ trợ `n_students > 1` cho chạy thống kê lô; lọc chặt câu lệnh sự cố đột xuất một lần (`P8`) không đụng với lịch học lặp lại hàng tuần. |

---

## 6. QUYẾT ĐỊNH HÀNH ĐỘNG TIẾP THEO (PHẦN KẾ HOẠCH `M5`)

- **Kết luận phần `M5`:** Kế hoạch `M5` có **tính thực tiễn cao, ăn khớp chặt chẽ với cả mục tiêu chấm điểm đồ án Tư duy Tính toán lẫn hướng phát triển sản phẩm thương mại**, miễn là áp dụng đầy đủ **6 hiệu chỉnh kỹ thuật (`M-1` $\to$ `M-6`)** nêu trên (cùng **2 hiệu chỉnh điều phối thuật toán `M-7`, `M-8`** ở Phần Bổ Sung bên dưới).
- **Trạng thái hiện tại:** Chưa tạo nhánh mới và chưa chỉnh sửa bất kỳ dòng code nào trong `smartschedule/`.

---

## 7. KIỂM ĐỊNH BỔ SUNG: HỆ THUẬT TOÁN LẬP LỊCH, MÁY SINH TEST & MỨC ĐỘ SẴN SÀNG THƯƠNG MẠI

*(Bổ sung theo yêu cầu rà soát toàn diện hệ thuật toán lõi, bộ sinh đề kiểm thử `Testing_System v2.1 + Fuzz v2`, phân công trong nhóm, và khả năng đưa ra thực tế thương mại).*

### 7.1. Kiểm tra Phân Công Trong Team: Hiện Có Ai Đang Phụ Trách Sửa Thuật Toán Không?
Qua rà soát toàn bộ **7 bản kế hoạch cá nhân (`M1` $\to$ `M7`)** trong `Sprint_Tasks/`:
- **Tầng lõi 6 bộ giải (`smartschedule/core/solvers/*`) & Máy chấm/sinh đề (`v1.0-alpha-plan/Testing_System/*`):** Cả **7/7 thành viên đều bị khóa quy tắc `DO NOT TOUCH`**. Lý do: bộ giải đã được nâng cấp lớn lên bản **V3** (ngày `20/11/2026`, xem [`Solver_Benchmark_Report.md`](../Testing_Plan/Solver_Benchmark_Report.md)) và đóng băng để giữ nguyên `1.320` lượt chạy benchmark + `39/39` bài test kiểm định bất biến (`M3` Hoàng Minh Anh chỉ tổ chức chấm mù đối chiếu Người–Máy `member_eval` vào tối Thứ Bảy, không sửa code solver).
- **Tầng Điều phối & Đấu nối Thuật toán vào App (`smartschedule/core/controller.py` & `smartschedule/api/app.py`):** **Không ai khác ngoài chính `M5` (Lê Tiến Bình) nắm quyền sở hữu!** Tức là mọi bất cập về cách App chọn thuật toán, chuyển đổi dự phòng, hay hậu kiểm lịch sửa cục bộ đều nằm trong tay `M5` (nếu `M5` không xử lý thì không ai trong nhóm xử lý).

---

### 7.2. Thẩm Định Máy Sinh Test (`InputGenerator` + `FuzzGenerator v2`) & Kết Quả Thực Nghiệm Hiện Tại

Đối chiếu trực tiếp [`Solver_Benchmark_Report.md`](../Testing_Plan/Solver_Benchmark_Report.md), [`input_generator.py`](../Testing_System/generator/input_generator.py) và [`fuzz_generator.py`](../Testing_System/generator/fuzz_generator.py):

1. **Điểm rất mạnh (Đạt `9.5 / 10` ở góc độ Đồ án Đại học & Kiểm chứng Thuật toán Tĩnh):**
   - Quy mô kiểm thử nghiêm ngặt hiếm có ở cấp đồ án: **`220` đề bài × `6` thuật toán = `1.320` lượt giải & chấm** (`120` đề `Regimes R1–R6`, `50` đề `Fuzz v2 1001..1050`, và `50` đề ẩn chống học vẹt `Held-Out Unseen Fuzz 5001..5050`).
   - Kỹ thuật **Plant-a-Witness** trong `FuzzGenerator v2` (gieo lời giải chứng nhân $\pi^*$ hợp lệ trên lưới trống trước rồi mới suy ngược deadline, chuỗi `DAG`, `PINNED`) triệt tiêu hoàn toàn thiên vị thuật toán.
   - Bộ đôi thuật toán chủ lực **`SCORED_GREEDY` (V3 — mặc định UI)** và **`HYBRID_ALNS` (V3 — siêu heuristic thứ 6)** đạt:
     - **`0 / 220` lỗi luật cứng (`INVALID = 0`)** — không bao giờ đè giờ ngủ, lớp học, bữa ăn hay trễ hạn ngầm.
     - **`0 / 220` lỗi rớt việc vô lý (`SUBOPT = 0`)** khi đề bài đủ sức chứa ($\rho \le 1$) — khắc phục triệt để điểm yếu chí mạng của bản V0 cũ (từng rớt `16/20` đề ở `R2`).
     - **`25 / 25` (`100%`) nhãn `HIGH_PRODUCTIVITY`** trên tập ẩn chưa từng chạm (`5001..5050` nhóm `LOOSE`).

2. **4 "Điểm Mù" của Máy Sinh Test khi đối chiếu với Đời Thực & Thương Mại:**
   - **Điểm mù T1 — Thiên lệch "Lập lịch tĩnh đầu tuần" (*Cold-Start Static Bias*):** Hơn `90%` số đề trong `Regimes 1–5` và `Fuzz v2` xuất phát từ trạng thái đầu tuần sạch sẽ (`Thứ Hai 08:00`), trong khi người dùng thương mại sống trong **đường chân trời cuốn chiếu liên tục (*Rolling Horizon*)**: tối Thứ Tư mới nhập việc gấp, làm dở 40% một bài rồi bỏ ngang, kéo-thả ghim lộn xộn, và có việc vắt từ Chủ Nhật tuần này sang Thứ Tư tuần sau.
   - **Điểm mù T2 — Chưa sinh các "Công việc Vụn `< 15 phút`" (*Micro-Task Inflation*):** Máy sinh test chỉ sinh các task chẵn bội số `15–30 phút` ($\ge 30\text{p}$). Ngoài đời thực, nếu người dùng nhập 8 việc lặt vặt kiểu *"Trả lời mail thầy (5p)"*, *"Điền form điểm danh (10p)"*, phép làm tròn lưới `RoundUp_15` + nhân đệm $\alpha = 1.20$ biến mỗi việc 10p thành khối `15–30p`, thổi phồng `60p` việc vặt thành `180–240p` chiếm sạch lưới lịch!
   - **Điểm mù T3 — Đứt gãy tính năng "Né nhiều khung giờ" (`avoid_windows`):** `M2` (`free_context_engine.py`) và `M6` (`chat-assistant.js`) được giao bắt và hiển thị `avoid_windows = ["EVENING"]` (*"tránh buổi tối"*), nhưng kiểm tra toàn bộ `smartschedule/` cho thấy **`Task` trong `models.py` và cả 6 bộ giải hoàn toàn CHƯA CÓ trường `avoid_windows`** (chỉ có 1 chuỗi dương `preferred_window` mềm)! Nếu né buổi tối mà gán cứng `preferred_window = "MORNING"` thì thuật toán lại phạt oan cả buổi chiều (`AFTERNOON`), và khi chật lịch vẫn xếp đè vào buổi tối.
   - **Điểm mù T4 — Chỉ kiểm thử đơn luồng trên máy rảnh CPU:** Bộ test chưa mô phỏng tải đồng thời nhiều người dùng cùng bấm giải lịch trên server.

---

### 7.3. Đánh Giá Thẳng Thắn: Thuật Toán Hiện Tại Đã Đem Ra Thực Tế & Thương Mại Được Chưa?

| Bối cảnh triển khai | Điểm đánh giá | Nhận định thực chất |
| :--- | :---: | :--- |
| **1. Đồ án Môn học & Demo Học thuật / MVP Cá nhân chạy Local (`1 người dùng`)** | **9.5 / 10 (Rất xuất sắc)** | Hoàn toàn vượt kỳ vọng. Tổ hợp `SCORED_GREEDY` + `HYBRID_ALNS` + `OverloadTriageEngine` xử lý mượt cả nhịp sinh học, nghỉ phục hồi `15p`, chuỗi `DAG`, chống học dồn `<10h` và cắt giảm quá tải. |
| **2. Đưa ra Thực tế cho Sinh viên dùng hàng ngày (Bản Beta miễn phí)** | **7.5 / 10 (Khả thi sau khi vá điều phối ở `M5`)** | Dùng tốt cho việc lập kế hoạch tuần `7–14 ngày`, **với điều kiện phải vá 3 lỗ hổng đấu nối ở tầng `controller.py` / `app.py` bên dưới** (đặc biệt là lỗi sửa lịch cục bộ làm rơi chất lượng sinh học và lệch thuật toán giữa Chat với nút Xếp lịch). |
| **3. Thương mại hóa SaaS quy mô lớn (Cạnh tranh trực tiếp với Motion / Reclaim.ai, hàng trăm user đồng thời)** | **5.8 / 10 (CHƯA SẴN SÀNG nếu giữ nguyên kiến trúc thực thi hiện tại)** | Vướng **3 rào cản thương mại lớn** cần lộ trình nâng cấp kiến trúc ở phiên bản `v2.0` (chi tiết mục 7.4). |

---

### 7.4. Năm Bất Ổn Thực Tế Của Hệ Thuật Toán (Chia Rõ: Cái Gì `M5` Vá Luôn Được vs. Cái Gì Thuộc Giới Hạn Kiến Trúc Đóng Băng)

#### 🔧 Nhóm A — 3 Lỗ Hổng Đấu Nối Thuật Toán Mà `M5` CÓ THỂ VÁ LUÔN Trong `controller.py` & `app.py` (Không chạm `solvers/*`!)

1. **Bất ổn A1 — "Lệch não" giữa Khung Chat và API `/api/solve` + Mặc định ngầm `EDF` (`0% HIGH`) trong `controller.py`:**
   - **Bằng chứng code:**
     - Khi chat qua [`handlers.py`](../../smartschedule/api/chat/handlers.py#L125-L142), nếu `SCORED_GREEDY` để lọt công việc chưa xếp được (`tasks_unplaced > 0`), hệ thống tự động cầu viện siêu heuristic **`HYBRID_ALNS`** để cứu hạn.
     - Nhưng khi gọi qua [`POST /api/solve`](../../smartschedule/api/app.py#L418-L431) hoặc các hàm nội bộ trong [`controller.py`](../../smartschedule/core/controller.py#L89) (`solve_schedule(..., algorithm="EDF")`, `preview_overload_resolution(..., algorithm="EDF")` dòng `589`), hệ thống **không hề có bước tự cầu viện `HYBRID_ALNS`**, thậm chí nếu thiếu tham số `algorithm` thì rơi thẳng về **`EDF` bản V0 (thuật toán đạt `0/120 HIGH_PRODUCTIVITY`, nhồi học thông 13 tiếng/ngày không nghỉ)!** Đồng thời mảng `state.solvers` khởi tạo tĩnh trong [`state.js`](../../smartschedule/ui/js/state.js#L31-L37) còn đang liệt kê thiếu `HYBRID_ALNS`.
   - **Giải pháp `M5` làm ngay (`M-7`):** Giữ nguyên mặc định chữ ký `solve_schedule(..., algorithm="EDF")` để không làm sai lệch bất kỳ bài test baseline/Testing_System cũ nào, **nhưng** đổi mặc định ở `preview_overload_resolution` và toàn bộ API mới của `M5` (`init-real-week`, `tasks/delete`, `fixed-events/*`, `adapt-next-week`, `simulation/multi-week`) sang **`SCORED_GREEDY` kèm cơ chế tự động leo thang sang `HYBRID_ALNS` khi `tasks_unplaced > 0` và đề chưa quá tải cứng** (giống hệt khung Chat!).

2. **Bất ổn A2 — `LocalRepairEngine` ("Sửa lịch cục bộ" `P8`) đang MÙ Năng Lượng & MÙ Nghỉ Phục Hồi:**
   - **Bằng chứng code:** Xem [`local_repair.py`](../../smartschedule/core/solvers/local_repair.py#L146-L204) (`_find_nearest_valid_slot` dòng `202`: `candidates.sort(key=lambda s: (abs(s - block.start_slot), s))`).
   - Khi có sự cố đột xuất hoặc tràn giờ, `LocalRepairEngine` chỉ tìm ô trống gần vị trí cũ nhất mà **bỏ qua hoàn toàn nhịp sinh học (`energy=1`), bỏ qua nghỉ `15p` sau bài nặng (`load=3`), bỏ qua trần `600p/ngày` và kẹp bữa ăn!** Hệ quả thực tế: đầu tuần `SCORED_GREEDY` xếp lịch đạt chuẩn `HIGH_PRODUCTIVITY` rất đẹp, nhưng giữa tuần sinh viên báo bận 1 cuộc họp CLB qua `disruption_chat.py`, khối bài khó bị dịch sang đúng khung buồn ngủ `energy=1` hoặc dính liền 4 tiếng không nghỉ!
   - **Giải pháp `M5` làm ngay mà không cần mở khóa `local_repair.py` (`M-8`):** Trong `disruption_chat.py` (và helper trong `controller.py`), ngay sau khi `LocalRepairEngine.repair_disruption(..., mode="LOCAL_INSERTION")` trả về lịch sửa cục bộ:
     - Chạy kiểm tra nhanh công thái học của các khối vừa bị dịch chuyển (xem khối `load=3` có bị đẩy vào đáy năng lượng `energy=1` hoặc vi phạm trần ngày nghiêm trọng không).
     - Nếu ổn định cao ($\ge 90\%$) và an toàn $\to$ áp dụng ngay. Nếu khối nặng bị ép vào giờ kiệt sức hoặc rớt việc trong khi `HYBRID_ALNS` có ghim mềm các khối khác cứu được $\to$ đính kèm cảnh báo minh bạch & gợi ý 1 chạm trên `quick_chips` để người dùng chọn giữa *"Giữ tối đa lịch cũ (`LOCAL_INSERTION`)"* vs *"Tối ưu lại sức khỏe cho phần còn lại của tuần (`SCORED_GREEDY/ALNS`)"*. Đây chính là chuẩn mực UX của sản phẩm thương mại!

3. **Bất ổn A3 — Gọi lặp dư thừa `apply_estimate_buffer` 2–4 lần trên cùng 1 request:**
   - **Bằng chứng code:** [`app.py`](../../smartschedule/api/app.py#L151) gọi `apply_estimate_buffer` trong `_extract_profile_and_tasks()`, rồi truyền vào `solve_schedule()` gọi lại lần 2; riêng `handle_task_overrun()` ([`controller.py`](../../smartschedule/core/controller.py#L528-L552)) gọi tổng cộng **4 lần** liên tiếp!
   - **Giải pháp `M5` làm ngay (gộp vào `M-1`):** Đảm bảo `apply_estimate_buffer` có tính **lũy đẳng tuyệt đối (Idempotent)** và truyền `apply_buffer=False` ở tầng trích xuất `app.py` trước khi gọi `solve_schedule` / `handle_task_overrun` để tiết kiệm thời gian clone Pydantic và ngăn chặn mọi nguy cơ ghi đè hệ số đệm.

---

#### 🏗️ Nhóm B — 3 Giới Hạn Kiến Trúc Cần Ghi Nhận Thẳng Thắn Khi Đánh Giá Thương Mại Hóa (Dùng cho Mục §8 Edge Cases / §11 Future Work của Báo cáo, KHÔNG tự ý phá khóa `solvers/*` ở Sprint này)

1. **Dao động kết quả & Tụt chất lượng khi Server chịu tải đồng thời (*Wall-Clock Budget Non-Determinism under CPU Load*):**
   - Ngay tại mục **2.6 (dòng 129)** của [`Solver_Benchmark_Report.md`](../Testing_Plan/Solver_Benchmark_Report.md#L129) đã ghi nhận thực nghiệm: vì `SCORED_GREEDY` (`0.42s`), `BACKTRACK` (`0.52s`) và `HYBRID_ALNS` (`0.65s`) cắt vòng lặp tối ưu theo đồng hồ thời gian thực `time.perf_counter()`, nên khi chỉ có **2 luồng giải song song** trên cùng tiến trình Python (bị nghẽn GIL), chỉ số chống sốc `Shk25` trên đề `Fuzz 1001` **tụt thẳng từ `94.9%` xuống `67.8%`**, đồng thời mã băm `SHA-256` bị đổi theo độ bận của CPU!
   - *Hướng giải quyết khi thương mại hóa:* Thay giới hạn `time.perf_counter()` bằng **ngân sách số bước lặp cố định (`fixed iteration/evaluation count`)** để tất định 100% bất chấp tải máy, kết hợp chạy đa tiến trình worker (`uvicorn --workers 4` / hàng đợi bất đồng bộ Celery/Redis) hoặc biên dịch nhân [`ergonomic_engine.py`](../../smartschedule/core/solvers/ergonomic_engine.py) (`3.072` dòng Python thuần) sang Cython/Rust (nhanh gấp `20–50x`, hạ từ `400ms` xuống `< 10ms`).

2. **Trần Đường Chân Trời Cứng `14 Ngày` (`horizon_days <= 14` trong `models.py`):**
   - Hệ thống hiện chỉ lập lịch chi tiết trong cửa sổ `7` hoặc `14` ngày (`672` / `1344` ô 15 phút). Với đồ án môn học kéo dài `4–8 tuần` ngoài thực tế, sản phẩm thương mại cần thêm **Tầng Quy hoạch Vĩ mô (*Macro Milestone Allocator*)** chia tải tuần tự từ tháng xuống từng tuần trước khi đưa vào lưới 672 ô.

3. **Gom cụm việc vặt `< 15 phút` (*Micro-Task Batching*):**
   - Trước khi thương mại hóa rộng rãi, cần thêm bước tiền xử lý gom các đầu việc `< 15 phút` cùng loại thành một khối `"Xử lý việc nhanh (30–45p)"` thay vì làm tròn từng việc lên `15–30 phút`.

---

## 8. CẬP NHẬT BẢNG TỔNG HỢP 8 ĐIỂM HIỆU CHỈNH (`M-1` $\to$ `M-8`) TRONG PHẠM VI FILE CỦA `M5`

Ngoài bảng `M-1` $\to$ `M-6` ở Mục 5, bổ sung thêm **2 hiệu chỉnh điều phối thuật toán (`M-7`, `M-8`)** hoàn toàn nằm trong `controller.py`, `app.py` và `disruption_chat.py` của `M5`:

| STT | Thành phần / File (Thuộc quyền `M5`) | Vấn đề thực tế của Thuật toán trong App | Cách `M5` xử lý gọn ngay trong Wave 1A |
| :-: | :--- | :--- | :--- |
| **M-7** | [`smartschedule/core/controller.py`](../../smartschedule/core/controller.py) & [`smartschedule/api/app.py`](../../smartschedule/api/app.py) | Lệch hành vi giữa Chat (có tự leo thang sang `HYBRID_ALNS`) với `/api/solve` & API mới (không leo thang, hoặc rơi về `EDF` V0 ở helper phụ). | Bổ sung helper `ScheduleController.solve_adaptive(...)` (chạy `SCORED_GREEDY`, tự động cầu viện `HYBRID_ALNS` nếu còn rớt việc khi chưa quá tải cứng) và dùng thống nhất cho mọi endpoint mới của `M5` + giảm gọi thừa `apply_estimate_buffer`, vẫn giữ nguyên `solve_schedule` gốc 100% cho `Testing_System`. |
| **M-8** | `smartschedule/api/chat/disruption_chat.py` & `controller.py` | `LocalRepairEngine` chỉ tìm ô gần nhất theo khoảng cách $|\Delta s|$ mà mù năng lượng (`energy=1`) và nghỉ phục hồi. | Hậu kiểm công thái học ngay sau `LOCAL_INSERTION`: nếu khối bài nặng (`load=3`) bị đẩy vào giờ kiệt sức `energy=1` hoặc rớt việc, báo rõ trong lời giải thích tiếng Việt và kèm lựa chọn tối ưu lại bằng `SCORED_GREEDY/ALNS` cho phần lịch tương lai. |

