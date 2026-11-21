# Tính Năng Đệm Thời Gian Chống Trễ Hạn (Estimate Buffer)

**Môn học:** CS252 — Tư Duy Tính Toán · FIT-HCMUS  
**Nhóm:** Nhóm 03 (*The Seven Dwarfs*)  
**Người thực hiện:** Nguyễn Trọng Tiến (Thinker 3)  
**Trạng thái:** Đã xong 100% và vượt qua toàn bộ 34 bài kiểm thử!  

---

## 1. Tính Năng Này Để Làm Gì? (Giải Thích Đơn Giản)

Sinh viên chúng ta hầu như ai cũng mắc bệnh **"ảo tưởng thời gian" (Planning Fallacy)**:
* Lúc tính thì nghĩ: *"Bài tập này dễ ợt, làm 1 tiếng là xong!"*
* Nhưng khi bắt tay vào làm: Đọc đề mất 15p, viết code mất 45p, sửa lỗi mất thêm 30p $\implies$ Mất tổng cộng 1 tiếng rưỡi (90 phút).
* **Hậu quả ở bản cũ (V0):** Bản V0 xếp lịch sát sạt đúng 60 phút, nên khi bị lố 30 phút, toàn bộ các lịch học sau đó bị đè lên nhau, vỡ tan tành cả tuần!

👉 **Giải pháp mới:** Hệ thống tự động hỏi bạn: *"Bạn có hay ước lượng thiếu giờ không?"* và tự cộng thêm **thời gian dự phòng (đệm an toàn)** trước khi xếp lịch!

---

## 2. Cách Chọn Thói Quen Ước Lượng

Khi nhập thông tin cá nhân hoặc tạo task, bạn có 3 mức lựa chọn:

| Mức độ bạn chọn | Hệ số nhân | Ví dụ bài ước lượng 60 phút | Kết quả lịch xếp |
| :--- | :---: | :---: | :---: |
| **HIẾM KHI** (`RARELY`) | $\times 1.00$ | $60 \times 1.00 = 60\text{ phút}$ | Xếp đúng **60 phút** (giữ nguyên như bản gốc V0) |
| **THỈNH THOẢNG** (`SOMETIMES`) | $\times 1.10$ | $60 \times 1.10 = 66\text{ phút}$ | Làm tròn slot 15p $\implies$ Xếp **75 phút** |
| **THƯỜNG XUYÊN** (`OFTEN`) | $\times 1.25$ | $60 \times 1.25 = 75\text{ phút}$ | Làm tròn slot 15p $\implies$ Xếp **75 phút** (+15p đệm) |

*Nếu bạn không chọn gì: Hệ thống mặc định $\times 1.00$ để không làm ảnh hưởng đến các kịch bản chấm điểm gốc.*

---

## 3. Quy Tắc Làm Tròn Khôn Ngoan (Không Lo Bị Lãng Phí Giờ)

Nhiều bạn thắc mắc: *"Nếu việc của mình chỉ mất 15 phút, nhân 1.25 lên là 18.75 phút, vậy có bị biến thành 30 phút không?"*

👉 **Câu trả lời là KHÔNG!** Thuật toán làm tròn tới **ô 15 phút gần nhất**:
* Việc **15 phút** $\times 1.25 = 18.75\text{p} \implies$ Làm tròn về **15 phút** (không bị đội lên 30p).
* Việc **45 phút** $\times 1.25 = 56.25\text{p} \implies$ Làm tròn thành **60 phút** (+15p đệm).
* Việc **60 phút** $\times 1.25 = 75.00\text{p} \implies$ Làm tròn thành **75 phút** (+15p đệm).
* Việc **90 phút** $\times 1.25 = 112.5\text{p} \implies$ Làm tròn thành **120 phút** (+30p đệm).

Nhờ vậy, những việc lặt vặt (5–15 phút) không bao giờ bị tăng giờ vô lý!

---

## 4. Các Thành Viên Khác Cần Lưu Ý Gì?

1. **Bạn làm thuật toán (Solver):** Bạn **không cần sửa gì** trong solver cả! Bộ đệm được xử lý sẵn ở tầng Controller, solver chỉ việc nhận thời lượng đã tính đệm và xếp vào ô trống.
2. **Bạn làm giao diện & Trợ lý Chat (`Frontend`):** Khi dời hạn chót qua khung chat, trợ lý hiển thị rõ phần tính lại `⏳ Tính lại thời gian theo thói quen` và bảng `Danh Sách Việc` hiển thị thời lượng dự trù đã cộng đệm.
3. **Kiểm tra kết quả:** Gõ lệnh `python -B tests/clean_runner.py --pass`, bạn sẽ thấy cả **34 bài test mới của bộ đệm đều xanh 100%**!
