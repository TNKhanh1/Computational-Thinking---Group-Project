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
- **Hệ thống Kiểm thử (Verification Tests):** Hiện có **107 bài test vận hành chạy xanh 100%** (`--pass`) + **5/5 bài test Improve Plan** (`--gaps`, `100% pass`) + **1 bài test mở Sprint Mode** (`test_fail_edge_sprint_mode_compression_recovery`, theo dõi tại `Q9`). Tổng cộng: **113 bài test tự động** (`112 Passed | 1 Failed` trên `--all` và `pytest -v`).
- **Nhánh đồng bộ mới nhất (`ltbinh/sync-proposal`):** Hoàn tất đồng bộ mã nguồn `src/` và `web/` theo `Proposal/` và `Presentation2.pdf` kèm đợt vá kiểm toán bổ sung (`validate-move` `proposed_block`, opt-out `buffer_mode="NONE"`, `SHORTEN_TASK`, `repair_overrun` Pin Guard, đồng bộ CLI/Benchmark/Tài liệu và tổng hợp biểu quyết `Q1–Q10`).

---

## 2. Nhật Ký Chi Tiết Các Thay Đổi Mã Nguồn

### Lần cập nhật 008 — 2026-11-15 | Vá Lỗi Kiểm Toán & Đồng Bộ Tài Liệu (`ltbinh/sync-proposal`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `ltbinh/sync-proposal`
- **Tóm tắt thay đổi:**
  1. **Khớp hợp đồng Kéo thả & API `/api/validate-move`:** `ScheduleController.validate_manual_move` (`src/controller.py`) trả thêm `"proposed_block"` (`state="PINNED"`) khi hợp lệ; `api_validate_move` (`web/api.py`) nhận đủ `blocks`, fallback `current_blocks` và `schedule.blocks`; `handleGridDrop` (`web/app.js`) gửi kèm `algorithm`, `blocks`, `current_blocks`.
  2. **Tắt buffer từng task (`buffer_mode="NONE"`):** Bổ sung hỗ trợ `"NONE"`/`"OFF"`/`"DISABLED"`/`"NO_BUFFER"` ở `Task` (`src/models.py`), `planned_duration_for_task_mode` (`src/estimate_buffer.py`), `apply_estimate_buffer` (`src/controller.py`) và `saveStudentTask` (`web/app.js`).
  3. **Cân bằng `SHORTEN_TASK` & Pin Guard khi Overrun:** `SHORTEN_TASK` (`src/overload_triage.py`) giữ nguyên khối khi `new_dur <= 90` và giữ `15p` cho `new_dur > 90` (`T06`); `preview_overload_resolution` (`src/controller.py`) mở rộng `PersonalHabit` trước bằng `preview_profile`; `LocalRepairEngine.repair_overrun` (`src/solvers/local_repair.py`) khóa `PINNED`/`DONE` trước khi phân bổ thêm slot và rollback kèm `OVERRUN_OVERLOAD` nếu thiếu slot.
  4. **Trùng ID sự kiện, CLI, Benchmark & Tài liệu:** `applyStudentDisruption` (`web/app.js`) dùng chung 1 `DIS_xxxx`; `main.py` thêm `--solver SCORED_GREEDY`, `Experience Rating`, `Crunch Tier` và `REST` trong `672-Slot Breakdown`; `benchmark_runner.py` thêm `SCORED_GREEDY` vào Bảng 2 (5 solvers); đồng bộ `README.md`, `group03-smartschedule-baseline/README.md`, `agents/requirements.md`, `docs/requirements.md`, `Proposal/Open_Decisions_For_Team.md` (`Q1–Q10`) và `Proposal/Sync_Completion_Report.md`.
- **Kiểm thử xác nhận (sau chỉnh sửa cuối cùng):** `clean_runner.py --pass` (`107/107 PASSED`), `clean_runner.py --gaps` (`5/5 PASSED`), `clean_runner.py --all` (`112 Passed | 1 Failed | Total: 113`), `pytest -v` (`112 passed, 1 failed`), `benchmark_runner.py` (5 solvers, `T04` Stability `100.00%`), `main.py --preset minh --solver SCORED_GREEDY` & `EDF`.

### Lần cập nhật 007 — 2026-11-15 | Đồng Bộ Toàn Bộ Proposal & Presentation2 (`ltbinh/sync-proposal`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `ltbinh/sync-proposal` (tách từ `main` tại `4c0a85a`, giữ nguyên `main`)
- **Tóm tắt thay đổi:**
  1. **Sửa lỗi cốt lõi (`A1–A12`) & Dọn dẹp kỹ thuật:** Xóa `web/Log.md` lỗi thời, sửa typo `"grep_weight"` -> `"grade_weight"` trong `t07`, chuẩn hóa `now_day`/`now_slot` động (bỏ hardcode Thứ Tư), thêm `PersonalHabit` (bảo vệ giấc ngủ `>= 6h`, trọng số `0.25x`), mở rộng `horizon_days` động, phá hòa tất định, và sửa `src/solvers/local_repair.py` 2-pass chunk relaxation (`T04` đạt Stability `100.00%`, `C_hard=0`).
  2. **8 Human Behavioral Patterns & `ScoredGreedySolver`:** Bổ sung `src/solvers/scored_greedy.py` (`SCORED_GREEDY`) với hàm mục tiêu $E_1$–$E_4$ (Circadian Energy Matching, Context Batching, Hyperbolic Urgency, Dead-Zone Avoidance); hỗ trợ buffer kép `HABIT` + `COGNITIVE_LOAD` ($\alpha_{\text{light}}=1.20$, $\alpha_{\text{heavy}}=1.35$), nghỉ ngơi chủ động (`REST` cho khe `<30m` và `>=15m` sau mỗi phiên), Two-Tier Crunch, `Early Extension Alert (24–48h)` và `Experience Rating (1–5)`.
  3. **Overload Triage & M1/M7 Pipeline:** Tích hợp có chọn lọc `src/overload_triage.py` (`OverloadTriageEngine` nối với `/api/overload/preview`), bộ phân tích ngôn ngữ tự nhiên EN/VI `src/nl_parser.py` (`/api/tasks/natural-add`), và `/api/tasks/complete` (M7 check-in).
  4. **Đồng bộ Giao diện Web (`web/index.html`, `web/app.js`):** Bỏ ngày tuần cứng, banner ngủ cứng `23:30–06:30` và lỗi nhân đôi buffer `* 1.2` phía client; bổ sung cấu hình động (`focus_preference`, `buffer_mode`, `alpha_light`, `alpha_heavy`; solver mặc định UI giữ `GREEDY_EDF_FIRST_FIT` chờ `Q10`), Overload Preview/Apply/Undo, M5 Local Repair, M7 actual duration check-in, Experience Rating & Early Alert, kéo thả nối `POST /api/validate-move`.
  5. **Hiệu chỉnh tham số & Báo cáo:** Bổ sung `benchmark_alpha_grid.py` (`--save-json` -> `data/alpha_grid_calibration.json`); lập `Proposal/Open_Decisions_For_Team.md` (`Q1–Q10`) và `Proposal/Sync_Completion_Report.md`.
- **Kiểm thử xác nhận (đợt đồng bộ đầu, cập nhật tiếp tại Lần cập nhật 008):** `clean_runner.py --pass`, `clean_runner.py --gaps`, `benchmark_runner.py`, `benchmark_alpha_grid.py`.
- **Lộ trình tiếp theo:** Họp nhóm chốt 10 hạng mục `Q1–Q10`, hoàn thiện UI nhập `PersonalHabit`/`horizon_days`, bổ sung bộ stress-test `α >= 1.7` + log thực tế `1-week peer study`, và cập nhật `Proposal/Presentation2.pdf`.

---

## 3. Nhật Ký Chi Tiết Các Lần Cập Nhật Trước Đó

### Lần cập nhật 006 — 06/11/2026 | Giao Diện Chế Độ Sinh Viên (Student Mode) Tối Giản & Nút Chuyển Đổi Dual-Mode
- **Người thực hiện:** Đức Minh (Trưởng nhóm phụ trách Giao diện & Trải nghiệm Người dùng), có sự hỗ trợ của Antigravity AI (Gemini 3.8 Flash)
- **Được phê duyệt bởi:** Đức Minh (Đã kiểm tra trực tiếp trên trình duyệt)
- **Nội dung thay đổi:**
  1. **Nút chuyển đổi 2 chế độ (Dual-Mode Switch):**
     - Thêm nút gạt trên thanh tiêu đề: `[🎓 Chế Độ Sinh Viên (Gọn)]` $\longleftrightarrow$ `[🔬 Chế Độ Lab (Benchmark)]`.
     - Mặc định mở web là vào ngay **Chế độ Sinh viên** để dùng được liền, nhưng vẫn giữ nguyên vẹn **Chế độ Lab** cho giảng viên chấm điểm đối chứng T01–T10.
  2. **3 Góc nhìn thân thiện cho sinh viên:**
     - **Lịch tuần thông minh (`#stViewWeek`):** Tự động thu gọn 28 hàng giờ ngủ nửa đêm thành một thanh tím mỏng gọn gàng, gộp các ô 15 phút thành thẻ sự kiện đẹp mắt (Giờ học, Giờ ăn, Buổi tự học).
     - **Hôm nay ("Đang làm gì & Việc kế tiếp" — `#stViewToday`):** Hiện thẻ tiêu điểm việc sắp làm với đồng hồ đếm ngược và dòng thời gian việc trong ngày.
     - **Hàng đợi bài tập (`#stViewTasks`):** Bảng quản lý việc học, xem nhãn đệm an toàn `🛡️ +20%` và hạn nộp bài.
  3. **Hộp thoại thêm việc siêu tốc (chỉ 3 ô):**
     - Nhập Tên việc, Thời gian (có nút chọn nhanh 30p, 45p, 60p, 90p), và Hạn chót. Tự động tính nhẩm trước thời gian đệm $+20\%$ ra số phút dự trù.
  4. **3 Tính năng tương tác trực tiếp trên lịch:**
     - **📌 Ghim việc (Pin):** Bấm ghim để khóa cứng buổi học lại; thuật toán cam kết không bao giờ dịch chuyển buổi học đã ghim.
     - **✓ Điểm danh (Check-in):** Đánh dấu đã học xong (thẻ mờ đi, có gạch ngang tên bài).
     - **💡 Xem lý do (Why here?):** Hiện popup giải thích bằng tiếng Việt dễ hiểu vì sao thuật toán lại xếp việc vào giờ này.
  5. **Dùng chung dữ liệu an toàn:** Hai chế độ dùng chung 100% dữ liệu, không sửa đổi gì vào mã nguồn solver backend.
- **Các file bị tác động:**
  - `group03-smartschedule-baseline/web/index.html` (Thêm layout Chế độ Sinh viên và các modal)
  - `group03-smartschedule-baseline/web/app.js` (Thêm hàm chuyển chế độ, vẽ thẻ lịch, ghim việc, check-in)
  - `docs/progress/giao_dien_sinh_vien.md` (Tạo mới)
- **Tác động đến dự án:** Giúp nhóm có bản demo trực quan tuyệt đẹp để thuyết trình mà không làm ảnh hưởng đến mã nguồn chấm điểm của các bạn khác.

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
     - Biên soạn [`docs/requirements.md`](requirements.md) (Tiếng Việt) và [`agents/requirements.md`](../agents/requirements.md) (Tiếng Anh) giải thích chi tiết mục đích của cả 6 thư viện trong `requirements.txt` (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `python-dateutil`).
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

