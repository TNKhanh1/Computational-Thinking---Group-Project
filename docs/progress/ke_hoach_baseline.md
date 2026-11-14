# SmartSchedule — Kế Hoạch Phiên Bản Baseline (V0)

**Dự án:** SmartSchedule — Trợ Lý Tối Ưu Hóa & Tự Động Xếp Lịch Học Tập  
**Nguồn tham chiếu:** `Baseline_Plan/baseline_plan.md`  
**Mục tiêu tài liệu:** Tóm tắt ngắn gọn phiên bản mốc chuẩn Baseline (V0) cho thành viên nhóm nắm nhanh cốt lõi bài toán.  

---

## 1. Mục Đích & Nguyên Tắc Của Bản Baseline (V0)

Bản Baseline (V0) là **hệ thống mốc chuẩn** ban đầu để làm căn cứ khoa học so sánh với các bản cải tiến sau này. Bản này tập trung giải quyết bài toán cốt lõi bằng thuật toán cổ điển, chưa áp dụng AI hay tâm lý học.

### 3 Nguyên tắc nền tảng:
1. **Tính Tất Định Tuyệt Đối (Pure Determinism):**
   - Cùng một danh sách công việc và thời khóa biểu, chạy bao nhiêu lần hệ thống cũng phải cho ra đúng 1 kết quả duy nhất.
   - Được kiểm chứng tự động bằng mã băm SHA-256 (3 lần chạy băm ra chuỗi giống hệt nhau).
2. **Không AI / Không Học Máy (Zero AI / Zero ML):**
   - Không sử dụng mô hình ngôn ngữ lớn (LLM) để parse câu chữ tự nhiên.
   - Dữ liệu đầu vào hoàn toàn là các biểu mẫu cấu trúc rõ ràng (JSON, Form nhập liệu).
3. **Không Áp Dụng Tâm Lý Học Hành Vi (Heuristic-Blind):**
   - Giữ nguyên thời lượng ước tính thô ($T_{\text{planned}} = T_{\text{estimate}}$), không tự động nhân thêm hệ số an toàn.
   - Không phân loại công việc thành việc nặng hay nhẹ để xếp theo giờ sinh học.
   - Không tự động chèn 15 phút nghỉ giải lao; việc xếp liên tiếp nếu đủ chỗ trống.
   - Mọi khoảng trống hợp lệ đều có giá trị xếp lịch ngang nhau.

---

## 2. Mô Hình Lưới Thời Gian 672 Ô (15 Phút / Ô)

Để máy tính tính toán được lịch tuần ($10.080$ phút), ta chia tuần học thành một mảng gồm **672 ô (slots)**, mỗi ô tương ứng với **15 phút**:

$$\text{Chỉ số ô (Slot)} = \text{Thứ trong tuần} \times 96 + \text{Giờ} \times 4 + \lfloor \text{Phút} / 15 \rfloor$$

- Thứ Hai bắt đầu từ ô `0` đến `95`.
- Thứ Ba từ ô `96` đến `191`...
- Chủ Nhật kết thúc ở ô `671`.

### 4 Trạng thái của từng ô:
- `0` (`FREE`): Ô trống, sẵn sàng để xếp việc học.
- `1` (`OCCUPIED`): Ô bận do lịch học cố định ở trường, ca trực làm thêm.
- `2` (`SLEEP`): Ô ngủ cố định mỗi ngày (mặc định: 23:30 đêm đến 06:30 sáng hôm sau).
- `100+` (`TASK`): Ô đã được xếp cho một công việc cụ thể.

---

## 3. 5 Ràng Buộc Cứng Bắt Buộc ($H_1$ đến $H_5$)

Bản Baseline xem xếp lịch là bài toán **Thỏa Mãn Ràng Buộc Cổ Điển (CSP)**. Bất kỳ phương án xếp lịch nào cũng phải thỏa mãn 5 điều kiện sau:

| Ràng Buộc | Tên Gọi | Ý Nghĩa Thực Tế | Xử Lý Khi Vi Phạm |
| :-: | :--- | :--- | :--- |
| **$H_1$** | **Không đụng lịch cố định** | Không được xếp việc vào giờ đang học trên lớp hoặc ca làm việc. | Hủy bỏ vị trí xếp ($C_{\text{hard}} = \infty$). |
| **$H_2$** | **Bảo vệ giấc ngủ tuyệt đối** | Không được cắt xén khung giờ ngủ (23:30–06:30) của sinh viên. | Khóa cứng giờ ngủ, cấm ghi đè. |
| **$H_3$** | **Chỉ xếp vào ô trống** | Công việc chỉ được đặt vào khoảng thời gian hoàn toàn rảnh (`FREE`). | Không cho phép đè lên việc khác. |
| **$H_4$** | **Hoàn thành trước hạn chót** | Công việc phải làm xong trước hoặc đúng thời hạn (Deadline). | Nếu không kịp, đẩy vào mục `unplaced_tasks`. |
| **$H_5$** | **Đúng thứ tự tiên quyết (DAG)** | Việc A là điều kiện của việc B thì việc A phải xong trước việc B mới được bắt đầu. | Sắp xếp topo trước khi duyệt thuật toán. |

---

## 4. 3 Thuật Toán Tham Lam Cơ Sở

1. **EDF (Earliest Deadline First — Thuật toán chính):**
   - Ưu tiên xếp những việc có hạn chót gần nhất trước. Nếu trùng hạn chót thì ưu tiên việc có độ ưu tiên cao hơn.
   - Tìm khoảng trống đầu tiên trong tuần (First-Fit) đủ thời lượng để xếp việc vào.
2. **LST (Least Slack Time — Thuật toán biến thể):**
   - Ưu tiên việc có "thời gian rảnh dự phòng" (Slack) nhỏ nhất: $\text{Slack} = \text{Hạn chót} - \text{Thời điểm hiện tại} - \text{Thời lượng việc}$.
3. **WSPT (Weighted Shortest Processing Time — Thuật toán biến thể):**
   - Ưu tiên việc có tỷ số giữa độ ưu tiên và thời lượng là lớn nhất (làm việc nhanh mà điểm cao trước).

---

## 5. 10 Kịch Bản Đối Chứng Chuẩn (T01–T10)

Nhóm đã xây dựng sẵn dữ liệu 10 kịch bản kiểm thử chuẩn hóa từ T01 đến T10 trong thư mục `data/` để kiểm tra độ tin cậy của thuật toán:
- **T01 (Khả thi cơ bản):** Tuần bình thường của sinh viên Minh (15 việc), thuật toán phải xếp thành công 100%.
- **T02 (Ít việc):** Tuần rảnh, kiểm tra thuật toán có bị phân mảnh lịch không cần thiết hay không.
- **T03 (Quá tải năng lực):** 35 tiếng việc đòi xếp vào 20 tiếng rảnh; kiểm tra thuật toán có biết bỏ bớt việc điểm thấp để giữ việc quan trọng hay không.
- **T04 (Dồn dập hạn chót):** Nhiều bài tập nộp cùng 1 buổi chiều; kiểm tra khả năng giữ bài ưu tiên cao.
- **T05 (Lịch học dày đặc):** Tuần thực tập/thí nghiệm bận rộn 40+ tiếng cố định.
- **T06 (Công việc nguyên khối dài):** Buổi học 4 tiếng liền không được cắt nhỏ.
- **T07 (Chuỗi phụ thuộc):** Đề cương $\to$ Bản thảo $\to$ Mã nguồn $\to$ Slide thuyết trình.
- **T08 (Ưu tiên cuối tuần):** Người dùng muốn dồn việc vào Thứ Bảy, Chủ Nhật.
- **T09 (Hạn chót đêm muộn):** Nộp bài lúc 23:59 Chủ Nhật (kiểm tra ô biên 671 không bị tràn sang tuần sau).
- **T10 (Sự cố bất ngờ):** Đột xuất chèn thêm 1 việc gấp 3 tiếng vào giữa tuần, kiểm tra độ ổn định của các việc còn lại.

