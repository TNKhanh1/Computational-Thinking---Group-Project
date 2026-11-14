# SmartSchedule — Nhật Ký Thay Đổi & Quy Định Đồng Bộ Dự Án

**Dự án:** SmartSchedule — Trợ Lý Tối Ưu Hóa & Tự Động Xếp Lịch Học Tập  
**Môn học:** CS252 — Tư Duy Tính Toán (2026) · FIT-HCMUS  
**Nhóm thực hiện:** Nhóm 03 — *The Seven Dwarfs*  
**Tài liệu:** `docs/commit_changes.md`  
**Đối tượng:** Mọi thành viên trong nhóm & Tất cả các AI Agent hỗ trợ thành viên "vibe code"  

---

> [!IMPORTANT]
> ## 🚨 QUY ĐỊNH BẮT BUỘC DÀNH CHO TẤT CẢ CÁC AI AGENT TRONG DỰ ÁN
> Vì tất cả thành viên trong nhóm đều sẽ "vibe code" với các AI Agent khác nhau (Cursor, Antigravity, GitHub Copilot, ChatGPT, Claude...), để tránh tình trạng mã nguồn bị gãy, tài liệu bị lệch pha hoặc xung đột logic, **MỌI AI AGENT BẮT BUỘC PHẢI TUÂN THỦ 4 ĐIỀU SAU:**
> 
> 1. **Đọc Tài Liệu Trước Khi Code:** Trước khi sinh code hay chỉnh sửa bất kỳ file nào, AI Agent phải đọc `docs/commit_changes.md` và các file trong `docs/progress/` để nắm vững kiến trúc 5 tầng, mô hình lưới 672 ô và các ràng buộc hiện tại.
> 2. **Tuyệt Đối Không Phá Vỡ 6 Quy Tắc Bất Biến (INV-1 đến INV-6):** Không được import `web`/`fastapi` vào trong `src/solvers/` hoặc `src/models.py`.
> 3. **Chạy Kiểm Thử Trước Khi Hoàn Thành:** Luôn luôn chạy lệnh `python verification_tests/clean_runner.py --pass` để đảm bảo 50 bài test cơ bản vẫn xanh 100%.
> 4. **BẮT BUỘC CẬP NHẬT NHẬT KÝ KHI XONG VIỆC:**
>    Ngay khi hoàn thành một tính năng, sửa lỗi hay thêm test, **VÀ ĐƯỢC THÀNH VIÊN / OWNER CHẤP THUẬN (APPROVE) THAY ĐỔI**, AI Agent **BẮT BUỘC PHẢI CẬP NHẬT NGAY VÀO CẢ 2 FILE:**
>    - `docs/commit_changes.md` (File này — Tiếng Việt)
>    - `agents/commit_changes.md` (File đồng bộ AI — Tiếng Anh)
>    Ghi rõ: Ngày giờ, Người thực hiện, Nội dung đã làm, Các file đã đụng tới, Kết quả chạy test, và Hướng dẫn cho các bạn khác trong nhóm.
> 5. **BẮT BUỘC ĐỒNG BỘ ĐỒNG THỜI FILE REQUIREMENTS:**
>    Khi thêm, sửa hoặc xóa bất kỳ thư viện nào trong `group03-smartschedule-baseline/requirements.txt`, AI Agent **BẮT BUỘC PHẢI CẬP NHẬT ĐỒNG THỜI CẢ 2 FILE:**
>    - `docs/requirements.md` (Bản tiếng Việt cho thành viên nhóm)
>    - `agents/requirements.md` (Bản tiếng Anh cho AI Agent)
>    Ghi rõ tên thư viện, mục đích sử dụng, và tầng kiến trúc được phép sử dụng.

---

## 1. Tình Hình Dự Án Hiện Tại

Dự án SmartSchedule đang ở bước chuyển tiếp quan trọng từ **Bản mốc chuẩn (Baseline V0)** sang **Kế hoạch cải tiến (Improve Plan V1/V2)**:

- **Bản Baseline (V0):** Đã hoàn thiện và chạy rất mượt. Bộ giải toán CSP trên lưới 672 ô (15 phút/ô) với các thuật toán tham lam EDF, LST, WSPT đảm bảo 5 ràng buộc cứng $H_1$–$H_5$.
- **Giao diện Web Workbench:** Đang chạy tại `http://127.0.0.1:8000`, hiển thị thời khóa biểu tuần trực quan và cho phép kéo thả thử nghiệm.
- **Hệ thống Kiểm thử (Verification Tests):** Đã xây dựng xong trọn bộ **56 bài test tự động** (Ma trận 60/40), có giao diện đồ họa Test Studio và màn hình chẩn đoán sạch sẽ, chỉ rõ lỗi nếu có.
- **Lộ trình sắp tới:** Cài đặt các tính năng tâm lý học hành vi theo `Improve_Plan/improve_plan.md` (khớp nhịp sinh học sáng/tối, đệm $1.25\times$, nghỉ giải lao 15p, chế độ nước rút, giải quyết quá tải).

---

## 2. Nhật Ký Chi Tiết Các Thay Đổi Mã Nguồn

### Lần cập nhật 005 — 06/11/2026 | Tính năng 001: Bộ Đệm Ước Lượng Thời Gian (Chống Planning Fallacy)
- **Người thực hiện:** Nguyễn Trọng Tiến (Thinker 3 — Trừu tượng hóa & Thiết kế thuật toán), có hỗ trợ của Claude Code
- **Được phê duyệt bởi:** Nguyễn Trọng Tiến (thành viên). Nằm trên branch `feature/estimate-buffer`, chưa merge, cần nhóm review.
- **Nội dung thay đổi:**
  1. **Tài liệu spec:** `specs/001-estimate-buffer/` (spec, các quyết định làm rõ C1–C5, plan, tasks, diagram Mermaid).
  2. **Module mới `src/estimate_buffer.py` (hàm thuần):** `estimate_habit` → hệ số (`RARELY` ×1.00, `SOMETIMES` ×1.10, `OFTEN` ×1.25). Thời gian dự trù = `max(làm_tròn_lên_15(T), làm_tròn_gần_nhất_15(T × hệ số))`, tính bằng số nguyên nên luôn tất định. Làm tròn tới ô *gần nhất* giúp task nhỏ không bị nhân đôi (15p × 1.25 → 15p, không phải 30p).
  3. **Models:** thêm `CommitmentsProfile.estimate_habit` (mặc định `None` = giữ nguyên V0) và `Task.buffer_multiplier`. `Task.get_planned_duration_min()` dùng công thức mới.
  4. **Controller:** `apply_estimate_buffer()` trả về *bản sao* task đã gắn hệ số (không sửa input, gọi nhiều lần vẫn cho cùng kết quả). `solve_schedule()` gắn lý do `ESTIMATE_BUFFER` cho block bị kéo dài. Mô phỏng lố giờ cộng thêm vào ước lượng gốc rồi mới áp bộ đệm, trả về `new_estimate_min`.
  5. **API:** đọc `estimate_habit` từ `commitments`, từ `profile` (hợp đồng Improve Plan) hoặc từ cấp ngoài cùng. Mọi endpoint dùng cùng thời lượng đã đệm.
  6. **Workbench:** ô chọn "Bạn có hay ước lượng thiếu không?", dòng xem trước "dự trù X phút", cột "ước lượng → dự trù" ở hàng đợi task và bảng block. Mô phỏng lố giờ lưu lại ước lượng gốc (không cộng dồn bộ đệm).
  7. **Sửa input gap test:** `test_fail_planning_fallacy_buffer_multiplier` được truyền thêm `estimate_habit="OFTEN"` (đúng điều kiện ghi trong docstring). Giữ nguyên tên test; Bảo có thể chuyển test ra khỏi `development_gap_tests/`.
- **Các file bị tác động:**
  - `group03-smartschedule-baseline/src/estimate_buffer.py` (Tạo mới)
  - `src/models.py`, `src/controller.py`, `web/api.py`, `web/app.js`, `web/index.html` (Cập nhật)
  - `verification_tests/logical_tests/test_estimate_buffer.py` (Tạo mới, 34 test)
  - `verification_tests/development_gap_tests/test_improve_plan_gaps.py` (Sửa input 1 test)
  - `specs/001-estimate-buffer/*` (Tạo mới)
  - **Không đụng tới:** `src/solvers/*`, bộ parse nhập nhanh / ngôn ngữ tự nhiên, `requirements.txt`.
- **Kiểm thử đã chạy:**
  - `python -B verification_tests/clean_runner.py --pass` → **84 Passed | 0 Failed** (50 test cũ + 34 test mới).
  - `python -B verification_tests/clean_runner.py --gaps` → 1 Passed (bộ đệm) | 4 Failed (giờ năng lượng, nghỉ sau Deep, reason code, SKIP_HABIT: vẫn còn mở).
- **Tác động đến dự án:**
  - Không chọn `estimate_habit` thì mọi kết quả (T01–T10, các mẫu, mã hash) giống hệt V0.
  - Người làm solver: không conflict, solver chỉ nhận thời lượng dự trù lớn hơn. Số liệu quá tải giờ tính theo thời gian đã đệm.
  - Người làm UI: TaskSheet (F06) có thể lấy thẳng `reasons[code=ESTIMATE_BUFFER].planned_min` để hiển thị.
  - Giới hạn đã biết (ngoài phạm vi): task dưới 15 phút vẫn chiếm trọn 1 ô (lưới D2). Gộp nhiều task siêu nhỏ vào 1 ô cần sửa solver.

### Lần cập nhật 004 — 04/11/2026 | Danh Mục Thư Viện (`requirements.md`) & Cài Đặt Tự Động 1-Click
- **Người thực hiện:** Nguyễn Nguyễn Gia Bảo (Builder 3 — Kiến Trúc Hệ Thống & Kiểm Thử Triển Khai)
- **Được phê duyệt bởi:** Owner / Trưởng nhóm
- **Nội dung thay đổi:**
  1. **Tài liệu đặc tả thư viện (`requirements.md`):**
     - Biên soạn [`docs/requirements.md`](file:///d:/Projects/Computational-Thinking---Group-Project/docs/requirements.md) (Tiếng Việt) và [`agents/requirements.md`](file:///d:/Projects/Computational-Thinking---Group-Project/agents/requirements.md) (Tiếng Anh) giải thích chi tiết mục đích của cả 6 thư viện trong `requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `python-dateutil`).
     - Phân định rõ tầng kiến trúc được phép sử dụng (FastAPI và Uvicorn chỉ thuộc Tầng 4; cấm dùng trong Tầng 2 Solvers và Tầng 1 Data Models).
     - Liệt kê các thư viện chuẩn zero-install của Python (`ast`, `tracemalloc`, `threading`, `tkinter`, `hashlib`).
  2. **File cài đặt môi trường tự động (`setup_env.bat`):**
     - Tạo file `group03-smartschedule-baseline/setup_env.bat` cho phép thành viên trên Windows nhấp đúp để tự động tạo môi trường ảo `.venv`, kích hoạt và cài toàn bộ thư viện chỉ trong 30 giây.
  3. **Quy định đồng bộ bắt buộc:**
     - Bắt buộc mọi thành viên và AI Agent khi cài thêm thư viện mới phải cập nhật đồng thời cả hai file `docs/requirements.md` và `agents/requirements.md`.
- **Các file bị tác động:**
  - `docs/requirements.md` (Tạo mới)
  - `agents/requirements.md` (Tạo mới)
  - `group03-smartschedule-baseline/setup_env.bat` (Tạo mới)
  - `docs/commit_changes.md` (Cập nhật)
  - `agents/commit_changes.md` (Cập nhật)
- **Tác động đến dự án:**
  - Giúp các bạn trong nhóm hiểu rõ máy mình đang cài những gì và có công cụ cài tự động không lo lỗi môi trường.

### Lần cập nhật 003 — 04/11/2026 | Màn Hình Console Chẩn Đoán Sạch Sẽ & Cổng Tài Liệu Nhóm
- **Người thực hiện:** Nguyễn Nguyễn Gia Bảo (Builder 3 — Kiến Trúc Hệ Thống & Kiểm Thử Triển Khai)
- **Được phê duyệt bởi:** Owner / Trưởng nhóm
- **Nội dung thay đổi:**
  1. **Bộ chạy test sạch `clean_runner.py` (Interpretable Console Runner):**
     - Viết plugin pytest tùy chỉnh (`InterpretableConsolePlugin`) dẹp bỏ hoàn toàn 200+ dòng rác cảnh báo (Starlette/HTTPX deprecation, traceback dài dòng).
     - Định dạng màn hình console chuẩn hóa chỉ gồm 3 phần:
       - **Tín hiệu chạy (Running Signal):** Mục tiêu test và mốc thời gian.
       - **Giai đoạn chạy (Running Phase):** Tách bạch theo 5 tầng kiến trúc.
       - **Trạng thái từng file (PASSED / FAILED):** Nếu lỗi, trỏ thẳng vào tên bài test, tóm tắt lý do lỗi (`Point to: ...`), và giá trị sai lệch cụ thể (`Details: Discrepancy: ...`).
  2. **Tích hợp vào Giao diện Test Studio & Script Batch:**
     - Cập nhật giao diện `test_studio.py` để mọi nút bấm đều chạy qua `clean_runner.py` với cờ `-B` (chống tạo file rác `.pyc`).
     - Tối ưu `run_verification_tests.bat` để các bạn chỉ cần gõ cờ `--pass`, `--gaps`, `--edge`, `--all`.
  3. **Xây dựng Cổng Tài Liệu `agents/` và `docs/`:**
     - Tạo thư mục `agents/` làm kim chỉ nam chuẩn tiếng Anh cho các AI Agent.
     - Tạo thư mục `docs/` tóm lược dễ hiểu bằng tiếng Việt cho các thành viên trong nhóm.
     - Đặt ra quy định đồng bộ bắt buộc cho AI Agent.
- **Các file bị tác động:**
  - `group03-smartschedule-baseline/verification_tests/clean_runner.py` (Tạo mới)
  - `group03-smartschedule-baseline/verification_tests/test_studio.py` (Cập nhật)
  - `group03-smartschedule-baseline/verification_tests/run_verification_tests.bat` (Cập nhật)
  - `group03-smartschedule-baseline/verification_tests/run_test_studio.bat` (Cập nhật)
  - `Progress/04_11_26_Builder 3.md` (Cập nhật)
  - `agents/*` & `docs/*` (Tạo mới)
- **Kết quả chạy kiểm thử:**
  - `python verification_tests/clean_runner.py --pass`: 50/50 bài test xanh 100% (3.42s).
  - `python verification_tests/clean_runner.py --gaps`: 5 bài test mục tiêu báo lỗi rõ ràng, trỏ đúng lý do cần cải tiến.
- **Tác động đến dự án:**
  - Thành viên nhóm khi chạy test không còn bị hoa mắt bởi rác màn hình.
  - Các AI Agent của các bạn khác khi code sẽ biết rõ quy chuẩn và không làm hỏng kiến trúc chung.

---

### Lần cập nhật 002 — 04/11/2026 | Ma Trận Kiểm Thử 60/40 & Giao Diện Test Studio
- **Người thực hiện:** Nguyễn Nguyễn Gia Bảo (Builder 3 — Kiến Trúc Hệ Thống & Kiểm Thử Triển Khai)
- **Được phê duyệt bởi:** Owner / Trưởng nhóm
- **Nội dung thay đổi:**
  1. Gom toàn bộ kiểm thử vào thư mục chuẩn hóa: `group03-smartschedule-baseline/verification_tests/`.
  2. Xây dựng **56 bài test** theo ma trận 60% ca trung bình và 40% ca biên/mục tiêu cải tiến qua 5 tầng:
     - `ui_tests/`: Kiểm tra giao diện và chuẩn JSON API (§7.3).
     - `architecture_tests/`: Soi AST cấm import web vào solver, đo rò rỉ bộ nhớ heap bằng `tracemalloc`, đa luồng.
     - `logical_tests/`: Bẫy vòng lặp phụ thuộc (vòng tròn $A \to B \to A$), giờ giấc sai trái, ca biên dồn hạn chót.
     - `benchmark_tests/`: Toán lưới 672 ô, tính tất định SHA-256, 10 kịch bản chuẩn T01–T10, và chứng minh toán học về tính khả thi.
     - `development_gap_tests/`: 5 bài test chủ đích báo đỏ định nghĩa trước các tính năng của Improve Plan.
  3. Viết ứng dụng giao diện `test_studio.py` để chỉnh sửa và chạy test trực quan bằng chuột.
  4. Viết file `setup_env.bat` cài đặt môi trường tự động bằng 1 cú nhấp đúp.
- **Các file bị tác động:**
  - Toàn bộ thư mục `group03-smartschedule-baseline/verification_tests/`
  - `group03-smartschedule-baseline/setup_env.bat`
- **Tác động đến dự án:**
  - Đảm bảo an toàn tuyệt đối trước khi đem sản phẩm đi nộp hoặc triển khai thực tế.
  - Vạch sẵn đích đến cho các thành viên phụ trách thuật toán cải tiến.

---

### Lần cập nhật 001 — 29/10/2026 | Khởi Tạo Bản Baseline V0 & Kịch Bản Môn Học
- **Người thực hiện:** Toàn thể Nhóm 03 (The Seven Dwarfs)
- **Nội dung thay đổi:**
  1. Khởi tạo mô hình thời gian lưới rời rạc 672 ô (15 phút/ô).
  2. Cài đặt các schema dữ liệu Pydantic (`src/models.py`).
  3. Cài đặt 3 thuật toán tham lam cơ sở: EDF, LST, WSPT (`src/solvers/`).
  4. Xây dựng FastAPI và giao diện Web Technical Workbench (`web/`).
  5. Cài đặt dữ liệu cho 10 kịch bản đối chứng chuẩn hóa T01–T10.
- **Các file bị tác động:**
  - `group03-smartschedule-baseline/src/*`
  - `group03-smartschedule-baseline/web/*`
  - `group03-smartschedule-baseline/data/*`

---

## 3. Ảnh Hưởng Của Những Thay Đổi Đến Từng Thành Viên Nhóm

| Thành Viên / Vai Trò | Trách Nhiệm Chính | Thay Đổi Này Giúp Gì Cho Bạn? |
| :--- | :--- | :--- |
| **Builder 1** | Mô hình dữ liệu & Hồ sơ sinh viên | Bạn có thể thoải mái thêm trường dữ liệu mới vào `src/models.py`. Bài test `test_models_layer_is_pure` sẽ tự động bảo vệ giúp bạn không bị ai import chéo gây lỗi. |
| **Builder 2** | Thuật toán & Tối ưu hóa | Khi bạn viết code cho nhịp sinh học, khoảng nghỉ hay đệm thời gian, bạn chỉ cần chạy `clean_runner.py --gaps` để thấy 5 bài test mục tiêu chuyển dần từ ĐỎ sang XANH. |
| **Builder 3** | Kiến trúc & Kiểm thử | Duy trì cổng kiểm soát chất lượng, theo dõi rò rỉ bộ nhớ ($< 350\text{ KB}$), bảo vệ tính toàn vẹn của mã nguồn. |
| **Builder 4** | UI/UX & Giao diện người dùng | Bạn có thể tự tin chỉnh sửa giao diện HTML/CSS/JS; bài test `clean_runner.py --ui` sẽ đảm bảo bạn không làm lệch chuẩn JSON API đã thống nhất (§7.3). |
| **Builder 5–7**| Kịch bản, Phân tích & Tài liệu | Dễ dàng chạy thử 10 kịch bản đối chứng bằng lệnh `clean_runner.py --bench` để lấy số liệu vẽ biểu đồ và viết báo cáo. |

---

## 4. Hướng Dẫn Dành Cho AI Agent Khi Ghi Nhận Thay Đổi Mới

Khi bạn (AI Agent) hoàn thành bất kỳ việc gì cho thành viên nhóm và được chấp thuận:
1. Thêm một mục mới vào Phần 2 (`Lần cập nhật 00X — Ngày/Tháng/Năm | Tiêu đề công việc`).
2. Điền đầy đủ:
   - **Người thực hiện:** Tên thành viên và vai trò bạn đang hỗ trợ.
   - **Được phê duyệt bởi:** Tên thành viên / Owner xác nhận.
   - **Nội dung thay đổi:** Tóm tắt ngắn gọn các gạch đầu dòng tính năng mới hoặc sửa lỗi.
   - **Các file bị tác động:** Đường dẫn cụ thể các file tạo mới, sửa đổi hoặc xóa.
   - **Kết quả chạy kiểm thử:** Lệnh đã chạy và trạng thái test (phải đảm bảo không làm vỡ các test cũ).
   - **Tác động đến dự án:** Ảnh hưởng thế nào đến các bạn khác trong nhóm.
3. Đồng bộ nội dung tương ứng sang `agents/commit_changes.md` bằng tiếng Anh.

