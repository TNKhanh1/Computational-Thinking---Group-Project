# Hướng Dẫn Sử Dụng Giao Diện Chế Độ Sinh Viên (Student Mode)

**Môn học:** CS252 — Tư Duy Tính Toán · FIT-HCMUS  
**Nhóm:** Nhóm 03 (*The Seven Dwarfs*)  
**Người thực hiện:** Đức Minh (Tuần 4)  
**Trạng thái:** Đã tích hợp trực tiếp trên giao diện web `http://127.0.0.1:8000`  

> [!NOTE]
> **Cập nhật kiến trúc `UI v3` (`2026-11-21`, xem [`docs/commit_changes.md`](../commit_changes.md) `Lần cập nhật 019–020`):** Giao diện nút chuyển 2 chế độ `#studentAppLayout` / `#labWorkbenchLayout` cũ dưới đây đã được nâng cấp lên kiến trúc **UI v3** ES module tách gọn (`web/index.html`, `web/app.js`, `web/js/*.js`, `web/css/*`) với thanh điều hướng Lịch / Danh sách / Bảng Dev thu gọn (`#devSidePanel`), Bảng so sánh 7 bộ test Showcase và bộ chọn `Regime`/`Fuzz v2`.

---

## 1. Tại Sao Lại Có Giao Diện Này?

Ở bản cũ (V0), giao diện chỉ toàn thuật ngữ khô khan dành cho giảng viên chấm điểm (ma trận 672 dòng, mã băm SHA-256, chỉ số slot 0..671), sinh viên nhìn vào hoa mắt và phải cuộn chuột mỏi tay qua 96 hàng mỗi ngày.

👉 **Đức Minh đã làm mới giao diện thành Chế Độ Sinh Viên (Student Mode):**
* Giấu đi các bảng tính phức tạp, chỉ hiển thị lịch tuần dạng thẻ hiện đại giống Google Calendar / Notion.
* Mở web lên là vào thẳng Chế Độ Sinh Viên, sinh viên dùng được ngay mà không cần học cách dùng!

---

## 2. Nút Chuyển Đổi 2 Chế Độ (Dual-Mode Switch)

Ngay góc trên thanh điều hướng có một nút chuyển đổi cực tiện:
* **🎓 Chế Độ Sinh Viên (Gọn):** Giao diện sạch sẽ, ít nút bấm, dành cho sinh viên dùng hàng ngày.
* **🔬 Chế Độ Lab (Benchmark):** Giao diện kỹ thuật đầy đủ ma trận 672 slot và các kịch bản đối chứng T01–T10 để giảng viên chấm thuật toán.

> *Dữ liệu giữa 2 chế độ dùng chung 100%: Bạn thêm task ở Chế độ Sinh viên thì khi bấm sang Chế độ Lab vẫn thấy đầy đủ, không sợ mất mát gì cả!*

---

## 3. 3 Góc Nhìn Cực Tiện Cho Sinh Viên

### Góc nhìn 1: Lịch Tuần Thông Minh (`Lịch Tuần`)
* **Gấp gọn giờ ngủ:** Thay vì hiển thị 28 dòng trống nửa đêm (00:00–06:30 và 23:30–24:00), hệ thống thu gọn lại thành một thanh màu tím nhạt siêu gọn: `🌙 23:30 – 06:30 (Ngủ) · Bảo vệ`.
* **Thẻ màu phân biệt rõ ràng:**
  * Giờ học trên lớp: Thẻ màu xám có icon ổ khóa 🔒.
  * Giờ ăn trưa/tối: Thẻ màu vàng ấm 🍴.
  * Giờ tự học: Thẻ màu xanh tím indigo hiện rõ tên môn, mức ưu tiên và hạn chót.

### Góc nhìn 2: Hôm Nay ("Đang Làm Gì & Việc Tiếp Theo")
* Trả lời ngay câu hỏi quan trọng nhất mỗi ngày: *"Bây giờ mình nên làm bài gì tiếp theo?"*
* **Bảng tiêu điểm (Hero Banner):** Nổi bật việc học sắp tới với đồng hồ đếm ngược và nút bấm to rõ để hoàn thành nhanh.
* **Dòng thời gian trong ngày:** Danh sách việc từ sáng đến tối, có ô tích chọn để tích xong việc ngay khi làm xong.

### Góc nhìn 3: Danh Sách Việc Cần Làm (`Danh Sách`)
* Bảng thống kê toàn bộ các bài tập đã nạp vào, xem bài nào đã xếp lịch xong (`✓ ĐÃ XẾP LỊCH`) và bài nào bị kẹt chưa xếp được (`⚠️ CHƯA XẾP ĐƯỢC`), kèm nhãn đệm an toàn `🛡️ +20%`.

---

## 4. 3 Nút Bấm "Thần Thánh" Trên Từng Thẻ Việc

Khi rê chuột vào một buổi học trên lịch tuần, bạn có thể bấm:
1. **📌 Ghim (Pin):** Khóa cứng buổi học này lại vào đúng giờ này. Sau này khi bạn thêm bài tập mới hay bấm xếp lại lịch, buổi học đã ghim **tuyệt đối không bao giờ bị dời đi chỗ khác**!
2. **✓ Hoàn thành (Check-in):** Đánh dấu đã học xong. Thẻ việc sẽ mờ đi và có gạch ngang tên bài, giúp bạn cảm thấy nhẹ nhõm vì đã hoàn thành mục tiêu.
3. **💡 Tại sao? (Why here?):** Bấm vào sẽ hiện ra hộp thoại giải thích bằng tiếng Việt dễ hiểu: Vì sao thuật toán lại chọn giờ này (do khung giờ năng lượng tốt, kịp trước hạn nộp bài, và không đụng giờ học cố định).

---

## 5. Tạo Bài Tập Siêu Nhanh Trong 10 Giây

Bấm nút **`➕ Thêm Việc Nhanh`**, bạn chỉ cần điền đúng 3 ô:
1. **Tên bài:** Ví dụ *"Làm bài tập Tư duy tính toán"*.
2. **Thời gian làm:** Chọn nhanh bằng nút bấm `[30p]`, `[45p]`, `[60p]`, `[90p]`.
3. **Hạn chót:** Chọn Thứ và Giờ nộp bài.

*Có sẵn công tắc đệm an toàn $+20\%$:* Gõ 60 phút sẽ tự động hiện xem trước thành **75 phút**, giúp bạn không bao giờ bị trễ bài!
