# SmartSchedule — Hướng Dẫn Kiểm Thử & Chạy Benchmark

**Dự án:** SmartSchedule — Trợ Lý Tối Ưu Hóa & Tự Động Xếp Lịch Học Tập  
**Phụ trách:** Builder 3 (Kiến Trúc Hệ Thống & Kiểm Thử Triển Khai)  
**Vị trí mã nguồn:** `group03-smartschedule-baseline/verification_tests/`  
**Mục tiêu tài liệu:** Hướng dẫn trực quan, dễ hiểu nhất cho mọi thành viên trong nhóm để chạy test, viết thêm test và đọc kết quả chẩn đoán lỗi.  

---

## 1. Tổng Quan: Ma Trận Kiểm Thử 60/40

Nhóm chúng ta đã xây dựng trọn vẹn **56 bài kiểm thử tự động**, chia thành 2 nhóm theo nguyên lý công nghệ phần mềm thực tế:

```text
Tổng Cộng: 56 Bài Kiểm Thử Tự Động
├── ~60% Ca Trung Bình / Kiểm Thử Vận Hành Đang Pass (50 bài):
│   ├── Kiểm tra giao diện HTML, các API xuất lịch (.ics, .csv, .json)
│   ├── Kiểm tra toán lưới 672 ô (196 ô ngủ + 132 ô học cố định + 344 ô rảnh)
│   ├── Kiểm tra tính tất định (chạy 3 lần băm ra mã SHA-256 giống nhau 100%)
│   ├── Kiểm tra kiến trúc: Solver tuyệt đối không dính mã web hay FastAPI
│   ├── Kiểm tra rò rỉ bộ nhớ: Chạy 50 lần giải lịch bộ nhớ tăng < 350 KB
│   └── Kiểm tra 10 kịch bản đối chứng chuẩn của môn học (T01 đến T10)
│
└── ~40% Ca Biên Nguy Hiểm & Bài Test Mục Tiêu (6 bài):
    ├── Đụng độ hạn chót đồng thời: Giữ bài điểm cao (P5), bỏ bài điểm thấp (P1)
    ├── Phân mảnh cực đoan: 4 tiếng rảnh bị xé vụn thành mười sáu ô 15 phút
    ├── Tràn viền Chủ Nhật: Việc đêm muộn không được nhảy lọt sang Thứ Hai
    ├── Đa luồng: 2 sinh viên gửi yêu cầu cùng lúc không bị rò rỉ việc của nhau
    └── 5 bài test báo lỗi chủ đích để theo dõi tiến độ kế hoạch cải tiến
```

---

## 2. Cách Chạy Kiểm Thử Dễ Dàng Nhất

### Cách 1: Dùng Giao Diện Đồ Họa Test Studio (Khuyên Dùng Cho Mọi Thành Viên)
1. Vào thư mục `group03-smartschedule-baseline/verification_tests/`.
2. Nhấp đúp chuột vào file: **`run_test_studio.bat`**.
3. Cửa sổ ứng dụng sẽ mở ra:
   - **Bên trái:** Cây thư mục 5 loại bài test, bấm vào file nào sẽ hiện mã nguồn ở khung giữa.
   - **Thanh công cụ trên cùng:**
     - **`▶ Run Selected`**: Chạy riêng file test bạn đang xem.
     - **`🚀 Run Production Tests`**: Chạy toàn bộ 50 bài test cơ bản (đảm bảo hệ thống đang chạy ổn).
     - **`🚩 Track Improve Plan Gaps`**: Chạy 5 bài test mục tiêu cải tiến để xem còn thiếu tính năng gì.
     - **`📊 Run 60/40 Matrix`**: Chạy toàn bộ cả 56 bài test.
     - **`➕ Add Test File`**: Tạo nhanh 1 file test mới từ các mẫu có sẵn.

---

### Cách 2: Dùng Dòng Lệnh Batch (Trong Terminal hoặc Command Prompt)
Mở terminal tại thư mục `group03-smartschedule-baseline/` và gõ:

```powershell
# Chạy bộ test cơ bản đang vận hành (100% xanh)
.\verification_tests\run_verification_tests.bat --pass

# Chạy 5 bài test mục tiêu của kế hoạch cải tiến
.\verification_tests\run_verification_tests.bat --gaps

# Chạy toàn bộ 56 bài test (Ma trận 60/40)
.\verification_tests\run_verification_tests.bat --all

# Chạy riêng các ca biên (Edge cases)
.\verification_tests\run_verification_tests.bat --edge

# Chạy riêng theo từng phần
.\verification_tests\run_verification_tests.bat --ui      # Kiểm tra giao diện & API
.\verification_tests\run_verification_tests.bat --arch    # Kiểm tra kiến trúc & bộ nhớ
.\verification_tests\run_verification_tests.bat --logic   # Kiểm tra logic thuật toán
.\verification_tests\run_verification_tests.bat --bench   # Chạy 10 kịch bản T01-T10
```

---

## 3. Cách Đọc Màn Hình Console Sạch Mới

Để tránh cho các bạn bị hoa mắt bởi hàng trăm dòng cảnh báo kỹ thuật (Starlette, HTTPX, traceback dài dằng dặc), màn hình console mới đã được thiết kế lại cực kỳ gọn gàng với đúng **3 thành phần chính**:

1. **Tín hiệu khởi chạy (Running Signal):** Cho biết đang chạy nhóm test nào và thời gian chạy.
2. **Giai đoạn chạy (Running Phase):** Phân chia theo 5 tầng kiến trúc rõ ràng.
3. **Trạng thái từng file (PASSED hoặc FAILED):**
   - Nếu file **PASSED**: Hiện số lượng test thành công (ví dụ `PASSED (5/5 tests)`).
   - Nếu file **FAILED**: Chỉ rõ ngay lập tức tên bài test bị lỗi, **nguyên nhân lỗi là gì** (`Point to: ...`), và **sai khác giá trị ở đâu** (`Details: Discrepancy: ...`).

### Ví dụ màn hình báo lỗi rõ ràng khi chạy tính năng chưa hoàn thiện:
```text
[PHASE 1/1] Improve Plan Target Feature Gaps (Expected Failures) (verification_tests/development_gap_tests)
  [FILE] test_improve_plan_gaps.py ............................. FAILED (0 passed, 5 failed)
    -> [ISSUE] test_fail_circadian_energy_matching
       Point to: [IMPROVE PLAN GAP: §3.3] Circadian rhythm matching is not implemented in V0. Deep task was placed at Monday 06:30 instead of evening focus hours (>= 18:00).
       Details:  Discrepancy: assert 6 >= 18
    -> [ISSUE] test_fail_rest_break_insertion_after_deep_work
       Point to: [IMPROVE PLAN GAP: Decision D2] 15-minute rest break after Deep work is not implemented in V0. Gap between tasks is 0 min instead of >= 15 min.
       Details:  Discrepancy: assert 0 >= 1
```

Nhìn vào đây, bạn sẽ thấy ngay: Bài tập Deep đang bị xếp vào lúc 6 giờ sáng thay vì tối ($\ge 18$ giờ), hoặc khoảng nghỉ giữa 2 việc đang là 0 phút thay vì 15 phút. Sửa đúng điểm này là test sẽ chuyển sang màu xanh!

