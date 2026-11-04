# SmartSchedule — Kế Hoạch Cải Tiến (Phiên Bản Nâng Cấp V1/V2)

**Dự án:** SmartSchedule — Trợ Lý Tối Ưu Hóa & Tự Động Xếp Lịch Học Tập  
**Nguồn tham chiếu:** `Improve_Plan/improve_plan.md`  
**Mục tiêu tài liệu:** Tóm lược lộ trình nâng cấp hệ thống thành trợ lý thân thiện cho sinh viên thật sự sử dụng mỗi ngày.  

---

## 1. Tầm Nhìn Cải Tiến: Từ Công Cụ Thuật Toán Đến Trợ Lý Đời Sống

Bản Baseline (V0) dù xếp lịch tốt nhưng chỉ như một "cỗ máy kỹ thuật" khô khan: dùng thuật ngữ chuyên môn (slot, solver, hard constraint) và nhồi nhét việc như xếp gạch.

Kế hoạch cải tiến (Improve Plan) định hướng:
> **"Sinh viên nhìn thấy một ứng dụng quản lý tuần nhẹ nhàng, trực quan; còn Giảng viên/Kỹ sư có thể bật chế độ Lab Mode để soi rõ từng bước thuật toán bên trong. Cả hai đều dùng chung một bộ lõi."**

---

## 2. 7 Khoảnh Khắc Sử Dụng Của Sinh Viên ($M_1$ đến $M_7$)

Ứng dụng được thiết kế xoay quanh 7 thời điểm mà sinh viên thật sự cần đến lịch:

| Khoảnh Khắc | Câu Hỏi Của Sinh Viên | Hệ Thống Cần Phải Làm Gì | Giai Đoạn |
| :-: | :--- | :--- | :--- |
| **$M_1$** | *"Đầu kỳ rồi, có phải nhập lại thời khóa biểu mỗi tuần không?"* | Nhập thời khóa biểu 1 lần duy nhất, các tuần sau tự động kế thừa. | Phase 1 |
| **$M_2$** | *"Vừa có bài tập mới, ghi chú nhanh kẻo quên!"* | Popup ghi nhận siêu tốc trong 10 giây với gợi ý thông minh. | Phase 1 |
| **$M_3$** | *"Chủ Nhật rồi, tuần tới làm bài vào lúc nào đây?"* | Bấm 1 nút sinh ngay đề xuất lịch cả tuần tối ưu. | Phase 1 |
| **$M_4$** | *"Bây giờ mình nên làm gì tiếp theo?"* | Widget trực quan hiển thị rõ: Đang làm gì (Now) và Việc kế tiếp (Next). | Phase 2 |
| **$M_5$** | *"Đột xuất có việc gấp, đừng làm đảo lộn cả tuần của mình!"* | Ripple Repair: chỉ xê dịch những việc bị va chạm, giữ nguyên $\ge 90\%$ lịch còn lại. | Phase 1 |
| **$M_6$** | *"Bài vở nhiều quá, tuần này có kham nổi không?"* | Trợ lý quá tải: tính rõ số phút bị thiếu và gợi ý phương án cứu nguy (bỏ bớt việc phụ). | Phase 1 |
| **$M_7$** | *"Hôm nay mình chưa kịp làm xong bài."* | Điểm danh 30 giây cuối ngày; tự động dồn thời gian chưa xong sang ô dự phòng hôm sau. | Phase 2 |

---

## 3. 5 Nâng Cấp Tâm Lý Học & Nhịp Sinh Học

Các tính năng này khắc phục điểm yếu "máy móc" của bản Baseline V0:

### 3.1. Khớp Nhịp Sinh Học Năng Lượng (Circadian Rhythm Matching)
- **Điểm yếu ở V0:** Thuật toán nhét bừa việc viết tiểu luận khó vào 06:30 sáng Thứ Hai (lúc sinh viên vừa ngủ dậy, chưa tỉnh táo).
- **Cải tiến:**
  - Phân loại việc: `DEEP` (việc nặng, cần tập trung cao như giải thuật, viết bài), `MEDIUM`, `SHALLOW` (việc nhẹ như trả lời email, dọn bàn).
  - Sinh viên chọn khung giờ tập trung: `MORNING` (08:00–11:30) hoặc `EVENING` (18:00–21:00).
  - Thuật toán ưu tiên đẩy việc `DEEP` vào đúng khung giờ sinh học sung mãn nhất.

### 3.2. Bắt Buộc Nghỉ Giải Lao 15 Phút Sau Việc Nặng
- **Điểm yếu ở V0:** Xếp 2 ca học 90 phút dính liền nhau không có lấy 1 phút nghỉ, gây mệt mỏi não bộ.
- **Cải tiến:** Sau mỗi khối việc `DEEP` kéo dài $\ge 90\text{ phút}$, hệ thống tự động khóa 1 ô (15 phút) làm ô nghỉ ngơi trước khi được xếp việc tiếp theo.

### 3.3. Hệ Số Đệm An Toàn Chống Ảo Tưởng Thời Gian ($1.25\times$)
- **Điểm yếu ở V0:** Sinh viên luôn nghĩ làm bài tập mất 60 phút, nhưng thực tế thường mất 75–80 phút (Planning Fallacy).
- **Cải tiến:** Tự động nhân hệ số đệm $1.25\times$. Bài tập 60 phút sẽ được dành riêng 75 phút trên lịch để không bị trễ hạn chót.

### 3.4. Xử Lý Quá Tải Thông Minh (Bỏ Thói Quen Trước, Giữ Bài Tập)
- **Điểm yếu ở V0:** Khi thiếu giờ, thuật toán vứt bỏ bừa bãi bài tập có độ ưu tiên thấp.
- **Cải tiến:**
  - Phân biệt việc học bắt buộc (`ACADEMIC`) và thói quen sinh hoạt (`HABIT` như tập gym, đọc sách).
  - Khi quá tải, hệ thống gợi ý theo thứ tự:
    1. `SKIP_HABIT`: Tạm hoãn 1 buổi gym/đọc sách để cứu deadline bài thi.
    2. `SHORTEN_TASK`: Cắt bớt thời gian đệm an toàn.
    3. `POSTPONE_LOWEST`: Chỉ hoãn bài tập khi đã hết cách và có xác nhận của sinh viên.

### 3.5. Chế Độ Nước Rút (Sprint Mode)
- Khi một bài tập chỉ thiếu 15 phút là kịp nộp bài, thay vì báo thất bại và vứt bài vào thùng rác, hệ thống tự động kích hoạt chế độ nén tạm thời để cứu bài tập.

---

## 4. Chuẩn Dữ Liệu Trao Đổi API (§7.3 JSON Data Contract)

Giao diện Web và Thuật toán giao tiếp với nhau bằng chuẩn JSON ISO-8601 rõ ràng:
- Mỗi khối việc xếp xong phải trả về mảng lý do `reasons`: ví dụ `["ENERGY_MATCH", "BEFORE_DEADLINE", "BREAK_AFTER"]`. Nhờ vậy người dùng rê chuột vào có thể biết **tại sao việc lại được xếp vào giờ này**.

---

## 5. 5 Bài Test Mục Tiêu (Hiện Đang Báo Đỏ Để Chờ Thành Viên Viết Code)

Để theo dõi tiến độ hoàn thành các tính năng cải tiến trên, nhóm đã viết sẵn 5 bài test chủ đích báo lỗi trong `group03-smartschedule-baseline/verification_tests/development_gap_tests/test_improve_plan_gaps.py`:

1. `test_fail_circadian_energy_matching`: Kiểm tra việc `DEEP` đã được xếp vào buổi tối ($\ge 18:00$) chưa.
2. `test_fail_rest_break_insertion_after_deep_work`: Kiểm tra đã có khoảng nghỉ 15 phút sau việc 90 phút chưa.
3. `test_fail_planning_fallacy_buffer_multiplier`: Kiểm tra bài 60 phút đã được xếp đủ 75 phút chưa.
4. `test_fail_why_popover_structured_reason_codes`: Kiểm tra popup giải thích đã có mã `ENERGY_MATCH` chưa.
5. `test_fail_overload_habit_skipping_recommendation`: Kiểm tra hộp thoại quá tải đã biết gợi ý `SKIP_HABIT` chưa.

> 🎯 **Khi các thành viên cài đặt xong các tính năng này ở những tuần tới, 5 bài test này sẽ tự động chuyển từ ĐỎ sang XANH.**

