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
- **Giao diện Web Workbench & Chương trình Chấm Mù:** Web chính chạy tại `http://127.0.0.1:8000` (kiến trúc UI v3 ES module tách gọn `web/js/*.js` + `web/css/*`, Dev Side Panel thu gọn, 6 thuật toán gồm `HYBRID_ALNS`, chẩn đoán 4 Trụ Cột `Testing_System v2.1` + `ICEE`, chọn bộ test `R1–R6` & `FuzzGenerator v2`, 7 bảng đối chiếu Showcase `GET /api/test-showcase`, điều hướng tuần chỉ-xem kèm cảnh báo quá hạn, `Xóa tất cả lịch…`, `Focus Timer` & hiệu chuẩn `EWMA`) cùng đóng gói Docker tại [`group03-smartschedule-baseline/docker/`](../group03-smartschedule-baseline/docker/docker-compose.yml) và cổng chấm mù `member_eval/` độc lập tại `http://127.0.0.1:8010`.
- **Hệ thống Kiểm thử (Verification Tests):** Mở rộng lên **`199` bài test** trong `clean_runner.py --all` (bao gồm `+6` bài test mới tại [`test_chat_first_ui_and_task_tracer.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_chat_first_ui_and_task_tracer.py)) và **`39 / 39` passed** trong `pytest Testing_System/tests -q`, giữ nguyên toàn vẹn bộ đánh giá `Testing_System/`.
- **Nhánh hiện tại (`v1.0-alpha/ui-ux-chat`):** Đang triển khai tái thiết kế giao diện Chat-First tối giản kiểu Antigravity tách riêng khỏi `main`.

---

## 2. Nhật Ký Chi Tiết Các Thay Đổi Mã Nguồn

### Lần cập nhật 022 — 2026-11-21 | Tinh Chỉnh UI Chat-First Bản 2: Tối Giản Hóa Tuyệt Đối, Sửa Phân Tích Ngữ Cảnh 1 Task Nhiều Ngày & Hộp Suy Nghĩ Developer Mode (`v1.0-alpha/ui-ux-chat`)
- **Người thực hiện:** Thành viên dự án + Antigravity AI
- **Nhánh Git:** `v1.0-alpha/ui-ux-chat`
- **Tóm tắt thay đổi:** Tinh chỉnh toàn diện giao diện và bộ phân tích ngữ cảnh theo phản hồi thực tế: bấm logo `SS SmartSchedule` (`#btnBrandHome`) quay thẳng về **`Trợ lý xếp lịch`** (`#viewChat`); gỡ bỏ `"Nền năng lượng sinh học"` và `"Tiện ích nhanh"` khỏi menu Cài đặt góc phải; bỏ thanh `"Chỉnh nhanh việc đã lưu"` và bỏ tiền tố tự chèn trong khung nhập chat; ẩn hoàn toàn `#leftNavSidebar` khi đóng thanh trượt trái (kèm xóa mục `"Chuyển nhanh tuần"`); sửa nút mũi tên ở `"Trợ lý tinh chỉnh trực tiếp"` (`#btnToggleCopilotDrawer`) thành thu gọn khung chat phải tại chỗ để mở rộng lịch tuần; chuẩn hóa nút xem lịch dưới mỗi phản hồi thành **`🗓️ Kiểm tra lịch trình`**; sửa lỗi câu lệnh có khung thời gian跨ngày bị hiểu nhầm thành 3 việc; và bổ sung hộp **💭 Quá trình suy nghĩ (Thinking Stage)** khi bật Developer Mode.
- **Chi tiết kỹ thuật:**
  1. **Kế hoạch cải tiến UI Bản 2 ([`v1.0-alpha-plan/UI_Rebuild_Plan/improved_ui_plan.md`](../v1.0-alpha-plan/UI_Rebuild_Plan/improved_ui_plan.md), [`agent_pipeline.md`](../v1.0-alpha-plan/UI_Rebuild_Plan/agent_pipeline.md), [`proposal_pipeline.md`](../v1.0-alpha-plan/UI_Rebuild_Plan/proposal_pipeline.md)):** Đặc tả chi tiết 10 hạng mục tinh giản giao diện, thuật toán tách khung giờ bắt đầu–hạn chót khác ngày, và cơ chế giải thích chọn tập con thuật toán tối ưu.
  2. **Sửa lỗi Phân tích ngữ cảnh 1 công việc & Thinking Stage ([`src/task_tracer.py`](../group03-smartschedule-baseline/src/task_tracer.py), [`web/chat_service.py`](../group03-smartschedule-baseline/web/chat_service.py)):** Sửa lỗi từ `"tới 21h"` khi bỏ dấu (`"toi"`) bị khớp nhầm với `"buổi tối"`, bổ sung từ dừng và nâng ngưỡng khớp task cũ lên `0.45`; thêm hàm `_extract_cross_day_window()` hiểu chính xác câu *"Làm bài tập môn Computational Thinking, từ 19h ngày thứ 3, tới 21h ngày thứ 5, cần thực hiện trong 2 tiếng"* là **1 công việc duy nhất** (`duration_min=120`, `start_after=Thứ Ba 19:00`, `deadline=Thứ Năm 21:00`, giữ nguyên 1 khối); và trả về `thinking_summary` giải thích cách loại bỏ nhóm thuật toán mù năng lượng (`EDF`, `WSPT`, `LST`) để chọn `SCORED_GREEDY` / `HYBRID_ALNS`.
  3. **Giao diện tối giản & Thu gọn Trợ lý lịch bên phải ([`web/index.html`](../group03-smartschedule-baseline/web/index.html), [`web/js/chat-assistant.js`](../group03-smartschedule-baseline/web/js/chat-assistant.js), [`web/js/state.js`](../group03-smartschedule-baseline/web/js/state.js), [`web/app.js`](../group03-smartschedule-baseline/web/app.js), [`web/css/app.css`](../group03-smartschedule-baseline/web/css/app.css)):** Gắn `#btnBrandHome`, đổi tên `#navBtnChat` thành `"Trợ lý xếp lịch"`, ẩn hoàn toàn `.left-nav-sidebar.collapsed`, thêm `setCopilotCollapsed()` thu gọn/mở lại `#calendarCopilotDrawer`, hiển thị nút **`🗓️ Kiểm tra lịch trình`** và hộp `.chat-thinking-stage` trong Developer Mode.
  4. **Kiểm thử ([`test_chat_first_ui_and_task_tracer.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_chat_first_ui_and_task_tracer.py)):** Thêm bài test `test_cross_day_window_single_task_parsing_and_thinking_stage` (`7/7` passed, `200/200` trong `clean_runner.py --pass`).

---

### Lần cập nhật 021 — 2026-11-21 | Tái Thiết Kế Giao Diện Chat-First, Thanh Trượt Dọc Bên Trái, Truy Vết Task SHA-256 & Trợ Lý Lịch Trực Tiếp (`v1.0-alpha/ui-ux-chat`)
- **Người thực hiện:** Thành viên dự án + Antigravity AI
- **Nhánh Git:** `v1.0-alpha/ui-ux-chat`
- **Tóm tắt thay đổi:** Thiết kế lại toàn bộ giao diện người dùng theo hướng lấy khung trò chuyện trống trải làm đầu vào mặc định (`#viewChat`), thêm thanh trượt dọc thu gọn bên trái (`#leftNavSidebar`), màn hình Lịch Tuần có trợ lý AI đi kèm bên phải (`#calendarCopilotDrawer`) đồng bộ chuyển động đổi lịch trực tiếp, cơ chế truy vết công việc bằng SHA-256 để chỉnh sửa thông số ẩn (`src/task_tracer.py`), tính lại thời gian còn lại theo thói quen cá nhân (`POST /api/chat/turn`), xử lý edge case kẹt lịch / lịch quá dày, và công tắc **Developer Mode** (`#chkDeveloperMode`) tách biệt giao diện kỹ thuật khỏi người dùng phổ thông.
- **Chi tiết kỹ thuật:**
  1. **Truy vết công việc SHA-256 ở Tầng 1 ([`src/task_tracer.py`](../group03-smartschedule-baseline/src/task_tracer.py)) & Sửa nhận diện Thứ Hai ([`src/nl_parser.py`](../group03-smartschedule-baseline/src/nl_parser.py)):** Chuẩn hóa từ khóa không dấu, sinh `trace_hash` và `keyword_hashes` SHA-256 cho từng công việc, tìm đúng task từ câu chat tự nhiên (`resolve_target_task_from_prompt`), và trích xuất cập nhật tiêu chí ẩn (độ nặng, nhịp sinh học, thời gian trừ hao, chia nhỏ). Khắc phục lỗi `"Thứ Hai"` bị nhận nhầm thành `"Thu"` (Thứ Năm).
  2. **API Hội Thoại & Tính Lại Deadline ([`web/chat_service.py`](../group03-smartschedule-baseline/web/chat_service.py), [`web/api.py`](../group03-smartschedule-baseline/web/api.py)):** Bổ sung `POST /api/chat/turn` (luôn chạy dưới 10 giây, xử lý nội bộ < 100ms) hỗ trợ hỏi bổ sung khi thiếu giờ bắt đầu/kết thúc hoặc nội dung, chỉnh thông số ẩn qua SHA-256, dời deadline kèm tính lại thời gian làm tiếp với bộ đệm EWMA/thói quen, và phát hiện hai edge case `DEADLOCK` (báo lỗi đỏ + gợi ý gỡ kẹt) / `DENSE_WARNING` (cảnh báo vàng + gợi ý giãn lịch).
  3. **Giao Diện Tối Giản, Lịch + Copilot & Developer Mode ([`web/index.html`](../group03-smartschedule-baseline/web/index.html), [`web/js/chat-assistant.js`](../group03-smartschedule-baseline/web/js/chat-assistant.js), [`web/js/render-calendar.js`](../group03-smartschedule-baseline/web/js/render-calendar.js), [`web/js/render-list.js`](../group03-smartschedule-baseline/web/js/render-list.js), [`web/js/state.js`](../group03-smartschedule-baseline/web/js/state.js), [`web/js/api.js`](../group03-smartschedule-baseline/web/js/api.js), [`web/app.js`](../group03-smartschedule-baseline/web/app.js), [`web/css/app.css`](../group03-smartschedule-baseline/web/css/app.css)):** Đặt `#viewChat` làm màn hình mở đầu, gắn thanh trượt dọc `#leftNavSidebar`, hiệu ứng `.cal-block-enter` / `.cal-block-moved` trên lịch khi copilot bên phải cập nhật, và công tắc Developer Mode bật/tắt nhãn thông số ẩn cùng `#devSidePanel`.
  4. **Kiểm thử & Tài liệu kế hoạch ([`test_chat_first_ui_and_task_tracer.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_chat_first_ui_and_task_tracer.py), [`v1.0-alpha-plan/`](../v1.0-alpha-plan/folder_division_plan.md), [`UI_Rebuild_Plan/`](../v1.0-alpha-plan/UI_Rebuild_Plan/proposal_pipeline.md)):** Bổ sung 6 test mới cho toàn bộ luồng Chat-First, SHA-256 tracer, multi-turn, remaining-time buffer, edge cases và bản kế hoạch chia lại cấu trúc thư mục giảm tải token.
- **Kiểm thử xác nhận:** `node --check` xanh trên toàn bộ module JS mới/sửa; `test_chat_first_ui_and_task_tracer.py` đạt `6/6`; `python -B group03-smartschedule-baseline/verification_tests/clean_runner.py --pass` đạt **`193 Passed | 0 Failed`** (`61.27s`) sau khi chuyển `Testing_System/` vào `v1.0-alpha-plan/`; và `python -B -m pytest Testing_System/tests -q` đạt **`39 passed`** (`39.83s`).

---

### Lần cập nhật 020 — 2026-11-21 | Tích Hợp `UI v3` Lên `main` (`d0489b3..1e5e494`), Gom Thư Mục Docker & Dọn File Thừa (`main`)
- **Người thực hiện:** nttien255, ltbinh + AI Agents
- **Nhánh Git:** `main`
- **Tóm tắt thay đổi:** Gộp hoàn chỉnh các bản vá contract `v3`, bộ chọn suite `Testing_System` (`Regimes` & `Fuzz v2`), chế độ xem 7 bảng đối chiếu `Showcase`, duyệt tuần chỉ-xem có xử lý việc quá hạn (`PAST_DUE`), và nút `Xóa tất cả lịch…` lên nhánh `main` (`193/193` test xanh), đồng thời gỡ các file dư thừa và gom file Docker vào [`group03-smartschedule-baseline/docker/`](../group03-smartschedule-baseline/docker/docker-compose.yml).
- **Chi tiết kỹ thuật:**
  1. **Đồng bộ Contract Đánh giá `UI v3` & Cache (`2e7a461` — [`web/api.py`](../group03-smartschedule-baseline/web/api.py), [`web/app.js`](../group03-smartschedule-baseline/web/app.js), [`web/js/utils.js`](../group03-smartschedule-baseline/web/js/utils.js), [`web/css/app.css`](../group03-smartschedule-baseline/web/css/app.css), [`web/index.html`](../group03-smartschedule-baseline/web/index.html)):** Bổ sung `normalizeEvaluation()` ánh xạ gọn payload `v2.1` (`/api/plan` `health_v21`, `/api/evaluate`) để hiển thị đúng `P1.1`, `Sốc +25%`, `P2–P4` và Top `ICEE`; nối `P3.3` Focus Timer + EWMA dùng `start_iso` và gắn `Cache-Control: no-cache` cho tài nguyên web tĩnh.
  2. **Bộ Chọn Suite `Testing_System` & 7 Bảng Showcase (`f0ec940` — [`web/test_showcase.py`](../group03-smartschedule-baseline/web/test_showcase.py), [`web/js/render-showcase.js`](../group03-smartschedule-baseline/web/js/render-showcase.js), [`web/v3_services.py`](../group03-smartschedule-baseline/web/v3_services.py), [`web/js/modals.js`](../group03-smartschedule-baseline/web/js/modals.js), [`Testing_Plan/CT_Rationale_Log.md`](../Testing_Plan/CT_Rationale_Log.md) `#20`, [`Testing_Plan/Solver_Benchmark_Report.md`](../Testing_Plan/Solver_Benchmark_Report.md)):** Mở chọn đủ `Regimes R1–R6` + `FuzzGenerator v2` (`RANDOM`/`LOOSE`/`TIGHT`/`OVERLOAD`) kèm seed/horizon; thêm `GET /api/test-showcase` phân tích 7 bộ đề nổi bật nơi 6 thuật toán phân thắng-bại theo thứ tự từ điển; phân tách task `PAST_DUE`/`DEADLINE_IN_PAST` khỏi quá tải thật, cùng hai file test [`test_showcase_and_fuzz_suites.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_showcase_and_fuzz_suites.py) & [`test_week_navigation_past_due.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_week_navigation_past_due.py).
  3. **Duyệt Tuần Chỉ-Xem & Xóa Lịch (`1e5e494` — [`web/app.js`](../group03-smartschedule-baseline/web/app.js), [`web/js/render-calendar.js`](../group03-smartschedule-baseline/web/js/render-calendar.js), [`web/js/state.js`](../group03-smartschedule-baseline/web/js/state.js), [`web/index.html`](../group03-smartschedule-baseline/web/index.html)):** Nút `<` / `>` đổi sang chỉ dịch khung nhìn (`state.viewWeekOffset`), tuần ngoài kỳ lập lịch hiển thị banner mời `Về kỳ đang lập lịch` hoặc bấm `Lập kế hoạch cho tuần này`; thêm dialog `Settings → Xóa tất cả lịch…`.
  4. **Gom Thư Mục Docker & Dọn Repo (working tree):** Gom thành [`group03-smartschedule-baseline/docker/Dockerfile`](../group03-smartschedule-baseline/docker/Dockerfile) và [`group03-smartschedule-baseline/docker/docker-compose.yml`](../group03-smartschedule-baseline/docker/docker-compose.yml) (chỉnh `context: ../..`, đường dẫn volume và command `member_eval/evaluate_schedule.py --mode serve --host 0.0.0.0 --port 8010`), đồng thời xóa các file thừa `docker-compose.yml` ở gốc, `group03-smartschedule-baseline/Dockerfile`, `.github/workflows/ci.yml`, `REVIEW_SUMMARY.md`, `Testing_Plan/summary_plan.md` và `Testing_Plan/ultimate_plan.md`.
- **Kiểm thử xác nhận (sau mọi thay đổi):** `python -B group03-smartschedule-baseline/verification_tests/clean_runner.py --all` (**`193 Passed | 0 Failed`**, `105.07s`) và `python -B -m pytest Testing_System/tests -q` (**`39 passed`**, `15.52s`).

---

### Lần cập nhật 019 — 2026-11-21 | Sửa Lỗi Merge UI v3 & Khôi Phục API Endpoint Đồng Bộ (`feat/v3-solvers-and-member-eval`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `feat/v3-solvers-and-member-eval`
- **Tóm tắt thay đổi:** Khắc phục trọn vẹn lỗi ghép nhánh từ commit `bc978d2` (`Renew UI`) trên [`web/app.js`](../group03-smartschedule-baseline/web/app.js), [`web/index.html`](../group03-smartschedule-baseline/web/index.html) và [`web/api.py`](../group03-smartschedule-baseline/web/api.py); khôi phục giao diện UI v3 ES module sạch, lựa chọn `HYBRID_ALNS`, thẻ sức khỏe 4 trụ cột `Testing_System v2.1` + `ICEE`, cùng bộ đếm `Focus Timer` & hiệu chuẩn `EWMA (P3.3)`.
- **Chi tiết kỹ thuật:**
  1. **Sửa sạch ES Module Coordinator ([`web/app.js`](../group03-smartschedule-baseline/web/app.js)):** Loại bỏ các mảnh code cũ lồng lỗi vào hàm không `async` (`SyntaxError: Unexpected reserved word`), hoàn chỉnh luồng UI v3 (`bootstrap`, `persistWorkspace`, `evaluateCurrentScheduleV21`, `solveActiveSolver`, `runBenchmarkAll`, `fetchSolverWeights`, `loadSuite`, `handleDropMoveBlock`, `handleTogglePin`, `handleCheckinBlock`, `handleOverrunBlock`, `handleRunRepair`, `handlePreviewOverload`, `handleApplyOverloadPreview`, `handleCancelOverloadPreview`, `handleExport`, `handleResetState`, `renderAll`, `setActiveView`, `applyTheme`, `wireStaticListeners`), bổ sung `renderHealthV21Panels` với `HYBRID_ALNS` và các hàm `P3.3`.
  2. **Làm sạch khung HTML UI v3 ([`web/index.html`](../group03-smartschedule-baseline/web/index.html)):** Nạp `/app.js` với `type="module"`, gỡ bỏ phần DOM cũ bị chèn lẫn (`labFixedInspectorPanel`, `determinismLedgerBody`, `studentAppLayout`, `labWorkbenchLayout`), khôi phục thanh tuần (`#btnWeekPrev`, `#btnWeekToday`, `#btnWeekNext`) & `#inputModal`, đồng thời đặt bảng `v2.1` + `Focus Timer / EWMA` gọn gàng trong `#devSidePanel`.
  3. **Khôi phục Route API FastAPI ([`web/api.py`](../group03-smartschedule-baseline/web/api.py)):** Bổ sung hàm `_extract_profile_and_tasks`, mở lại đủ các route UI v3 (`/api/solvers`, `/api/test-suites/catalog`, `/api/test-suites/load`, `/api/benchmark-all`, `/api/solver-weights`) từ [`web/v3_services.py`](../group03-smartschedule-baseline/web/v3_services.py), và giữ tương thích ngược cho `/api/tasks/calibration` cùng `/api/import/ics`.
- **Kiểm thử xác nhận:** `node --check` xanh trên `web/app.js` và toàn bộ `web/js/*.js` (`ESM_IMPORT_OK`), `clean_runner.py --all` đạt **`186 / 186` Passed** (`83.43s`), `Testing_System/` giữ nguyên không chỉnh sửa.

---

### Lần cập nhật 018 — 2026-11-20 | Hạ Tầng Thương Mại Hóa `P3`: Multi-Tenant Auth (`P3.1`), Nhập `.ics`/LMS (`P3.2`), Focus Timer & Nhắc Giờ (`P3.3`), Docker + CI (`P3.4`) (`feat/v3-solvers-and-member-eval`)
- **Người thực hiện:** Lê Minh Nhật (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `feat/v3-solvers-and-member-eval`
- **Tóm tắt thay đổi:** Triển khai trọn bộ 4 gói thương mại hóa `P3` (`Testing_Plan/HANDOFF_V3_MEMBER_EVAL_AND_P1.md §V.3`) bằng hoàn toàn thư viện chuẩn Python (0 gói ngoài mới) và không chỉnh sửa `Testing_System/*.py`, `src/solvers/`, `src/models.py` hay `requirements.txt`.
- **Chi tiết kỹ thuật:**
  1. **`P3.1` Xác thực & Cô lập Đa Người Dùng ([`src/storage.py`](../group03-smartschedule-baseline/src/storage.py), [`web/auth.py`](../group03-smartschedule-baseline/web/auth.py), [`web/api.py`](../group03-smartschedule-baseline/web/api.py), [`test_p3_1_auth_multitenant.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_p3_1_auth_multitenant.py)):** Bổ sung bảng `users` (PBKDF2-HMAC-SHA256), token JWT HS256 (`/api/auth/register`, `/api/auth/login`, `/api/auth/me`), cô lập cứng `user:<user_id>`, cờ `SMARTSCHEDULE_AUTH_REQUIRED`, và siết CORS theo `SMARTSCHEDULE_ALLOWED_ORIGINS`.
  2. **`P3.2` Nhập `.ics` Thời Khóa Biểu & Moodle/Canvas LMS ([`src/ics_importer.py`](../group03-smartschedule-baseline/src/ics_importer.py), [`web/api.py`](../group03-smartschedule-baseline/web/api.py), [`test_p3_2_ics_importer.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_p3_2_ics_importer.py)):** Parser RFC 5545 thuần stdlib (`POST /api/import/ics`) giải mã lịch lặp tuần `RRULE` thành `FixedEvent` và deadline Moodle/Canvas thành nháp `Task` (LoA Level 4).
  3. **`P3.3` Focus Timer (Pomodoro → M7), Thẻ Hiệu Chuẩn EWMA & Nhắc Giờ ([`web/index.html`](../group03-smartschedule-baseline/web/index.html), [`web/app.js`](../group03-smartschedule-baseline/web/app.js), [`test_p3_3_focus_timer_ui.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_p3_3_focus_timer_ui.py)):** Bổ sung bộ đếm tập trung nối thẳng `POST /api/tasks/complete`, thẻ gợi ý EWMA α nối `GET /api/tasks/calibration` (LoA-4) và thông báo nhắc giờ trình duyệt.
  4. **`P3.4` Đóng Gói Docker & CI (đường dẫn mới):** Đã chuyển cấu hình Docker sang [`docker/Dockerfile`](../group03-smartschedule-baseline/docker/Dockerfile) & [`docker/docker-compose.yml`](../group03-smartschedule-baseline/docker/docker-compose.yml) (`.github/workflows/ci.yml` và file gốc đã dọn gọn ở Lần cập nhật 020): Hỗ trợ chạy Web App `8000` + profile `eval` cho `member_eval` `8010`.
- **Kiểm thử xác nhận:** `pytest Testing_System/tests -q` (`39/39`), `clean_runner.py --all` (`178/178`), `benchmark_runner.py` (`exit 0`).

---

### Lần cập nhật 017 — 2026-11-20 | Đồng Bộ `P1.3`, Stress Test Quá Đệm `α >= 1.70` (`P2.1`) & API Hiệu Chuẩn EWMA M7 (`P2.2`) (`feat/v3-solvers-and-member-eval`)
- **Người thực hiện:** Lê Minh Nhật (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `feat/v3-solvers-and-member-eval`
- **Tóm tắt thay đổi:** Hoàn tất Đợt 1 của `Testing_Plan/HANDOFF_V3_MEMBER_EVAL_AND_P1.md §V`: cập nhật `Testing_System/README.md` theo chuẩn `v2.1 + Fuzz v2` (`39/39` tests), mở rộng `benchmark_alpha_grid.py` với stress test tải hẹp cho `α >= 1.70..2.00` chứng minh điểm gãy quá đệm (*Over-Buffering Cliff* `20.0%` vs `0.0%` ở `1.20/1.35`), và bổ sung module thuần tầng 1 `src/calibration.py` + endpoint `GET /api/tasks/calibration` (LoA Level 4) phục vụ Pilot 7 ngày. Giữ nguyên **0 dòng thay đổi** trong `Testing_System/*.py`, `src/solvers/`, `src/models.py` và `requirements.txt`.
- **Chi tiết kỹ thuật:**
  1. **Đồng bộ `P1.3` ([`Testing_System/README.md`](../Testing_System/README.md)):** Cập nhật Cổng `#0 HARD-RULE` (`G1 == 0`, `SLA <= 1000 ms`), xếp hạng Từ Điển 10 cấp `v2.1`, Top 5 `ICEE`, `FuzzGenerator v2`, lệnh `--mode fuzz` và bộ `39/39` pytest tests.
  2. **Stress test tải hẹp `P2.1` ([`benchmark_alpha_grid.py`](../group03-smartschedule-baseline/benchmark_alpha_grid.py), [`data/alpha_grid_calibration.json`](../group03-smartschedule-baseline/data/alpha_grid_calibration.json)):** Thêm `_load_tight_stress_benchmarks()`, `run_extreme_tight_stress()` và cờ `--include-extreme`. Xác nhận `1.20/1.35` đạt `100.0% R_dl` (`CliffDrop=0.0%`, `Score=89.84`), trong khi `α >= 1.70` gây rớt hạn giả `20.0%` (`R_dl=80.0%`, `Score=78.16–78.75`).
  3. **Hiệu chuẩn EWMA M7 `P2.2` ([`src/calibration.py`](../group03-smartschedule-baseline/src/calibration.py), [`web/api.py`](../group03-smartschedule-baseline/web/api.py)):** Bổ sung `compute_ewma_calibration()` và `format_pilot_markdown_report()` (thuần Layer 1, kẹp outlier `[0.5, 2.5]`, ngưỡng `min_samples`, giới hạn an toàn `[1.00, 1.60]`) cùng endpoint `GET /api/tasks/calibration`.
  4. **Kiểm thử tự động ([`verification_tests/logical_tests/test_p2_alpha_calibration.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_p2_alpha_calibration.py)):** Thêm `4/4` test kiểm tra AST `INV-1`/`INV-2`, toán EWMA/gating, API E2E với SQLite cô lập, và điểm gãy quá đệm `α >= 1.70`.
- **Kiểm thử xác nhận:** `pytest Testing_System/tests -q` (`39/39`), `clean_runner.py --all` (`171/171`), `benchmark_alpha_grid.py --include-extreme --save-json` (`exit 0`).

---

### Lần cập nhật 016 — 2026-11-20 | Triển Khai Chương Trình Chấm Mù `member_eval/` & Nâng Cấp `P1` Web UI/API (`HYBRID_ALNS` + Chẩn Đoán `v2.1`) (`feat/v3-solvers-and-member-eval`)
- **Người thực hiện:** Hoàng Minh Anh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `feat/v3-solvers-and-member-eval`
- **Tóm tắt thay đổi:** Hiện thực hóa trọn vẹn `Testing_Plan/evaluation_plan.md` (chương trình trung gian chấm mù A/B cho 7 thành viên và sinh viên dùng thử tại `http://127.0.0.1:8010`) và hoàn tất cụm `P1` trong `Testing_Plan/HANDOFF_SUMMARY_AND_NEXT_TASKS.md` (đưa thuật toán thứ 6 `HYBRID_ALNS` + chẩn đoán 4 Trụ Cột `v2.1` & cảnh báo `ICEE` thời gian thực lên Web App chính). Giữ nguyên **0 dòng thay đổi** trong `Testing_System/`, `src/solvers/`, `src/models.py` và `requirements.txt`.
- **Chi tiết kỹ thuật:**
  1. **Gói Chấm Mù Độc Lập (`group03-smartschedule-baseline/member_eval/`, `run_member_eval.bat`):**
     - Tạo [`member_eval/__init__.py`](../group03-smartschedule-baseline/member_eval/__init__.py), [`scenarios.py`](../group03-smartschedule-baseline/member_eval/scenarios.py) (7 kịch bản khóa seed + `PERSONAL_WEEK` nhập trực tiếp hoặc dùng Hybrid NL Parser), [`blind_runner.py`](../group03-smartschedule-baseline/member_eval/blind_runner.py) (tráo mã `#A/#B/#C` tất định theo SHA-256, làm sạch tên solver khỏi `blind_view` và khóa kín `revealed_oracle`), [`aggregator.py`](../group03-smartschedule-baseline/member_eval/aggregator.py) (tính tỷ lệ thắng mù, điểm `UX-1..5`, đồng thuận Máy vs Người, phát hiện cụm nhãn `>=25%` trỏ về `ergonomic_engine.py`, xuất `Calibration_Report.md`), [`app.py`](../group03-smartschedule-baseline/member_eval/app.py), [`viewer.html`](../group03-smartschedule-baseline/member_eval/viewer.html), và [`run_member_eval.bat`](../group03-smartschedule-baseline/run_member_eval.bat).
  2. **Nâng Cấp `P1` Web UI/API (`web/health_v21.py`, `web/api.py`, `web/index.html`, `web/app.js`):**
     - Bổ sung cầu nối Tầng 4 [`web/health_v21.py`](../group03-smartschedule-baseline/web/health_v21.py) (`evaluate_schedule_v21`); gắn `"health_v21"` cho `/api/plan`, `/api/compare` (truyền đúng raw unbuffered `Task`) và thêm `POST /api/evaluate` chấm lại lịch sửa tay/sự cố.
     - Mở tùy chọn `HYBRID_ALNS` trong Cài đặt Sinh viên, Active Solver, A/B Comparison Studio (kèm preset `SCORED_GREEDY` vs `HYBRID_ALNS`), Ledger SHA-256 6 thuật toán; bổ sung 4 thẻ sức khỏe Sinh viên (`#stHealthV21Panel` + Top 3 `ICEE`), bảng 12 chỉ số `v2.1` ở Lab Tab 1 (`#labHealthV21Panel`), và hàng so sánh `v2.1` ở Lab Tab 2.
  3. **Kiểm thử tự động (`verification_tests/logical_tests/`):** Bổ sung [`test_member_eval_system.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_member_eval_system.py) (`3/3`) và [`test_p1_v21_ui_and_api.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_p1_v21_ui_and_api.py) (`3/3`).
- **Kiểm thử xác nhận:** `clean_runner.py --all` (`167/167` trong `7.54s`), `pytest Testing_System/tests -v` (`39/39` trong `13.54s`), `benchmark_runner.py` (`exit 0`), `node --check web/app.js` (`exit 0`), kiểm tra JS của `member_eval/viewer.html` (`exit 0`), và `POST /api/compare` (`SCORED_GREEDY` vs `HYBRID_ALNS` -> `200 OK`, đều đạt `HIGH_PRODUCTIVITY`).

---

### Lần cập nhật 015 — 2026-11-20 | Đại Tu V3 Bộ 5 Thuật Toán & Thiết Kế Thuật Toán Thứ 6 `HYBRID_ALNS` (`testing-system/v2.1-fuzz-handoff`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `testing-system/v2.1-fuzz-handoff`
- **Tóm tắt thay đổi:** Hoàn thiện kế hoạch `Testing_Plan/ultimate_plan.md`, xây lại toàn bộ bộ giải (`WSPT`, `LST`, `SCORED_GREEDY`, `BACKTRACK`) và tạo thuật toán cao cấp thứ 6 (`HYBRID_ALNS`) qua hạt nhân chung [`src/solvers/ergonomic_engine.py`](../group03-smartschedule-baseline/src/solvers/ergonomic_engine.py) (không chạm `Testing_System/` và giữ nguyên `EDF` làm mốc V0): xóa sạch **`SUBOPT → 0/220`** trên mọi thuật toán, nâng **`LOOSE HIGH_PRODUCTIVITY`** từ `0/24` lên **`22–23/24` (`91.7%–95.8%`)** ở Fuzz `1001..1050` và **`25/25` (`100.0%`)** trên tập ẩn `5001..5050`.
- **Chi tiết kỹ thuật:**
  1. **Hạt nhân Công thái học Tĩnh-Trạng-Thái (`src/config.py`, `src/solvers/ergonomic_engine.py`):** Thêm ngưỡng bảo vệ sinh học trong `config.py`; xây `ErgonomicContext` với prefix-sum `O(1)` (`pref_free`, `pref_low`, `pref_peak`, `pref_energy_sum`, `pref_tod_sin/cos`), lan truyền hạn DAG ngược, `ScheduleState` tăng dần (`placed_l3_slots_count`, `cls_sin/cos`, `non_sin/cos`), công thức `SJL` vòng Smarr & Schirmer chính xác + ghép cặp nhẹ tránh `SJL=None` mà vẫn giữ `<= 1 WARN`, hàm đánh giá từ điển 10 cấp `evaluate_state_lex_key`, tách mảnh thích ứng chuẩn `G1`, cứu hạn Kempe `1/2-eject`, sàn khả thi First-Fit `build_feasibility_first_fit_state`, giới hạn thời gian cứu hạn `OVERLOAD` quy mô lớn (`seed=1049`), ba lô ưu tiên `OVERLOAD_PACK`, `polish_schedule_deterministic` ưu tiên culprit trước, và `run_alns_deterministic` (`5` toán tử Ruin + Regret-2 Insertion). Tuân thủ trọn vẹn `INV-1..6`.
  2. **Nâng cấp 5 Solver + Tạo Thuật Toán Thứ 6 (`src/solvers/greedy_wspt.py`, `greedy_lst.py`, `scored_greedy.py`, `backtracking.py`, `hybrid_alns.py`, `registry.py`):** Giữ nguyên `greedy_edf.py` (V0); `WSPT` & `LST` thuần mù năng lượng (`Q10`: `MORNING == EVENING` từng bit); `SCORED_GREEDY` tối ưu mặc định Web UI (`AvgRk 2.22` Regimes / `2.48` Unseen, giữ `#1` Regime 3 & reason codes); `BACKTRACK` nhánh-cận trạng thái sống (`23/24` Fuzz `LOOSE HIGH`, `max 680.8ms`); bổ sung [`HybridALNSSolver`](../group03-smartschedule-baseline/src/solvers/hybrid_alns.py) (`HYBRID_ALNS`/`ALNS`/`ULTIMATE` — dẫn đầu **`79/120` Regimes [`19/20 R1`!] + `22/24` Fuzz + `25/25` Unseen `LOOSE HIGH`**, `max 774.8ms`).
  3. **Kiểm thử & Tài liệu (`verification_tests/logical_tests/test_ergonomic_solvers_v3.py`, `Testing_Plan/ultimate_plan.md`, `Solver_Benchmark_Report.md`, `CT_Rationale_Log.md`):** Thêm 6 test V3 (tất định 3x, bất biến mù `Q10`, tách nhịp sinh học, cứu hạn hẹp, `PINNED`+14d, `N=50 <= 1000ms`); cập nhật đủ 5 mục Báo cáo Benchmark và CT Log (`#14–#16`).
- **Kiểm thử xác nhận:** `clean_runner.py --all` (`161/161`, `47.31s`), `benchmark_runner.py` (`T01–T10 C_hard=0`, `3x Determ PASS`, `T04 100.00%`, `T09 Ablation PASS`), `pytest Testing_System/tests -v` (`39/39`, `40.25s`), và evaluation 220 đề × 6 thuật (`1.320` lượt: `0 INVALID`, `0 SUBOPT`, `0` invariant thất bại, `0` nghịch lý, `max <= 774.8ms`).

---

### Lần cập nhật 014 — 2026-11-17 | Thanh Trượt Ngang Lịch & Lịch Tháng Hiển Thị Chuỗi Ngày Đang Quan Sát (`M1-NL-Parser`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:** Bổ sung thanh cuộn ngang rõ nét + thanh trượt ngang (`range slider`) đồng bộ 2 chiều, dải mini-map đánh dấu chuỗi ngày đang hiện trên khung hình (`#stObservedDaysStrip`), hiển thị liên tục cả `14` ngày trên cùng trục cuộn ngang, và popup **Lịch Tháng** (`#observedRangeCalendarPopover`) đánh dấu trực quan chuỗi ngày đang quan sát cho cả Student Mode và Lab Mode.
- **Chi tiết kỹ thuật:**
  1. **Trục Cuộn Ngang & Thanh Trượt Ngang (`web/index.html`, `web/app.js`):** Thêm `.calendar-h-scroll`; chuyển `#stViewWeek` sang luồng ngang `#stCalendarScrollContainer` (`w-[265px] sm:w-[280px]`) kết nối `#stCalendarHorizontalSlider`, nút trượt `◀ / ▶` (`panCalendarByDays()`), nút `📍 Về Hôm Nay` (`scrollToTodayColumn()`), sinh tự động Tuần 2 (`_ensureWeek2DayColumns()` cho `horizon_days = 14`), và hàm đo khung hình thực (`updateObservedViewportRange()`, `#stObservedRangeLabel`, `#stObservedDaysStrip`); thêm thanh trượt ngang `#labGridHorizontalSlider` & `#labObservedRangePill` cho `#singleGridPanel`.
  2. **Popup Lịch Tháng Chuỗi Ngày (`web/index.html`, `web/app.js`):** Nối `#topWeekRangePill`, `#btnToggleObservedCalendar` (`📆 Lịch`) và `#btnStOpenMonthCal` mở `#observedRangeCalendarPopover` (`toggleObservedRangeCalendar()`, `renderObservedRangeCalendar()`, `shiftMiniCalendarMonth()`, `onMiniCalendarDateClick()`), tô đậm vùng ngày đang quan sát trên màn hình, vùng horizon `7/14 ngày`, viền hôm nay, và bấm ngày để cuộn/nhảy tuần.
  3. **Kiểm thử hợp đồng UI (`verification_tests/logical_tests/test_milestone2_production_readiness.py`):** Mở rộng `test_redesigned_temporal_student_and_lab_ui_contracts` kiểm tra toàn bộ ID thanh trượt ngang và Lịch Tháng.
- **Kiểm thử xác nhận:** `node --check web/app.js`, kiểm tra chéo HTML ID / JS handler, và `clean_runner.py --all` / `pytest -q` (`155/155`).

---

### Lần cập nhật 013 — 2026-11-17 | Tái Thiết Lập UI: Trục Ngày Cụ Thể (`DD/MM/YYYY`), Gọn Giao Diện Sinh Viên & Lab Nghiên Cứu 3 Workspace (`M1-NL-Parser`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:** Thiết kế lại giao diện Sinh viên và Phòng Lab (`web/index.html`, `web/app.js`) kết hợp bổ sung telemetry khoa học ở backend (`src/controller.py`, `web/api.py`): hiển thị đầy đủ ngày `DD/MM/YYYY` và trạng thái Quá khứ / Đang diễn ra / Sắp tới, loại bỏ nút bấm/form trùng lặp, mở quản lý `PersonalHabit` trực tiếp ở tab Việc & Thói Quen, và nâng cấp Lab Mode thành 3 workspace phân tích có đúc kết định lượng (`verdict_winner`, `block_diffs`, thanh `S_stability`, bảng SHA-256 5 solvers).
- **Chi tiết kỹ thuật:**
  1. **Telemetry Sinh học & Đúc kết A/B từ Backend (`src/controller.py`, `web/api.py`):** Bổ sung `ScheduleController.compute_schedule_insights(profile, out)` tính `energy_level` từng block, `peak_match_rate_pct`, `deep_peak_match_pct`, `avg_energy_level`, `context_switches` và `batched_pairs` (gắn qua `_enrich_response()` cho `/api/plan`, `/api/compare`, `/api/repair`, `/api/progress`); mở rộng `compare_algorithms()` trả thêm `block_diffs`, `verdict_winner`, `verdict_highlights` và mặc định `algo_right="SCORED_GREEDY"`.
  2. **Ngày Cụ Thể `DD/MM/YYYY` & Trục Quá Khứ / Hiện Tại / Tương Lai (`web/index.html`, `web/app.js`):** Thêm thanh điều hướng tuần & ngày thực tế (`#inpWeekStartDate`, `#topWeekRangePill`, `#btnStWeekPrev/Next`, `#stHorizonDaysSelect`, `#btnStJumpRealtime`), banner `#temporalContextBanner` kèm nút `rebaseScheduleToCurrentWeek()`, nạp mặc định lần đầu `loadPresetIntoCurrentWeek("minh")` theo tuần hiện tại (vẫn giữ `/api/presets` tất định cho T01–T10), gắn ngày `DD/MM/YYYY` + badge `Đã qua` / `HÔM NAY` / `Sắp tới`, vạch đỏ `─── 🔴 BÂY GIỜ (HH:MM) ───`, thẻ `▶ ĐANG DIỄN RA` và đếm ngược/quá hạn deadline (`resolveDeadlineDisplay()`).
  3. **Gọn Student Mode & Tab `PersonalHabit` Trực Tiếp (`web/index.html`, `web/app.js`):** Thống nhất header còn `➕ Thêm Việc`, `⚙️ Cài Đặt` và menu `⋯ Dữ Liệu & Tiện Ích` (`#studentToolsMenu`); thêm sub-tab `🏃 Thói Quen Tuần (PersonalHabit)` (`#stSubHabitsPane`, `#stMainHabitsList`, `addStudentHabitFromMainTab()`) đồng bộ 2 chiều với `#stSettingsModal`; thêm Check-in M7 inline ngay trên thẻ Hero Hôm Nay (`stHeroActualMin` -> `submitBlockCheckIn()`).
  4. **Lab Research Workbench 3 Tab (`web/index.html`, `web/app.js`):** Gỡ form `#inpTask*` 12 ô trùng lặp; tách 3 cột Control Rail + 9 cột 3 Tab: Tab 1 (6 KPI khoa học gồm `#kpiPeakMatch` & `#kpiExperienceVal`/`#kpiContextSwitches`, Grid có ngày + `#labFixedInspectorPanel` khi click, bảng Placed Blocks có `energy_level` & reason codes); Tab 2 (A/B Comparison Studio mặc định `EDF` vs `SCORED_GREEDY` + 3 preset đối chứng, `#compareVerdictBanner`, bảng 9 chỉ số `#compareMetricsBox`, bảng đối chiếu từng phiên `#compareDiffTableBody`, lưới 672 slot thu gọn `#compareFullGridsDetails`); Tab 3 (`#labPanelResilience` cho `T04`/`T05` kèm progress bar và Ledger SHA-256 3x cho cả 5 solvers).
  5. **Mở rộng Regression Tests (`verification_tests/logical_tests/test_milestone2_production_readiness.py`):** Thêm `test_plan_and_compare_scientific_insights_and_block_diffs` và `test_redesigned_temporal_student_and_lab_ui_contracts` (`8/8` tests xanh).
- **Kiểm thử xác nhận:** `clean_runner.py --pass` (`149/149`), `--gaps` (`5/5`), `--all` (`155/155`, `17.77s`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `620.6 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, Bảng 5 `T09` giữ nguyên), `node --check web/app.js` (`exit 0`), kiểm tra chéo HTML ID & JS handler (0 lỗi). Chưa bấm kiểm chứng trực tiếp trên Chrome sống sau đợt đổi UI này.

---

### Lần cập nhật 012 — 2026-11-17 | Hoàn Thiện Cột Mốc 2 — Sẵn Sàng Thực Tế Hằng Ngày (`Gói A.0`, `Gói A.1–A.3`, `Gói B`) (`M1-NL-Parser`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:** Triển khai trọn vẹn Cột mốc 2 trên nhánh `M1-NL-Parser` (`153/153` tests xanh): tối giản `#stTaskModal` theo chế độ `STUDENT` vs `LAB` (`Gói A.0` giữ nguyên 100% ID/handler), lưu trữ bền vững SQLite + `localStorage` qua F5 (`Gói A.1`), đồng hồ thực & lập lịch đa tuần `horizon_days=7..14` (`Gói A.2`), hoàn thiện Sửa Task + `PersonalHabit` UI (`Q7.3 = A3`) + nối `start_after`/`work_rhythm`/`preferred_window` vào Solver + vá offline regex cụm giờ (`Gói A.3`), đặt Student UI mặc định `COGNITIVE_LOAD`, cập nhật `.bat` ưu tiên `.venv` và tách `requirements-nllb.txt` (`Gói B`).
- **Chi tiết kỹ thuật:**
  1. **Progressive Disclosure cho `#stTaskModal` (`web/index.html`, `web/app.js`):** Thêm `.app-mode-student .st-lab-only-modal { display: none !important; }` và `syncTaskModalModeVisibility()` giúp `STUDENT` Mode chỉ hiển thị thanh chat AI + nút `📎` gọn + **4 trường cốt lõi** (Tên việc, Thời lượng, Hạn chót Thứ/Giờ, Mức ưu tiên P1–P4 / Phân loại) + ngăn `<details id="stTaskAdvDetails">` mặc định đóng, còn `LAB` Mode tự mở đầy đủ bảng kỹ thuật và giữ 100% DOM IDs/handlers.
  2. **Lưu trữ SQLite & M7 Check-in (`src/storage.py`, `web/api.py`, `web/app.js`, `.gitignore`):** Tạo module `src/storage.py` thuần stdlib `sqlite3` (hỗ trợ `SMARTSCHEDULE_DB_PATH`, mặc định `data/local_state.db` đã thêm vào `.gitignore`); bổ sung `GET/PUT/DELETE /api/state`, `GET /api/tasks/completions` và ghi log từ `POST /api/tasks/complete`; `DOMContentLoaded` gọi `restorePersistedWorkspace()` trước khi fallback `loadPreset("minh")` cho người dùng mới.
  3. **Thời gian thực & Đa tuần `horizon_days=7..14` (`src/models.py`, `src/solvers/*.py`, `src/controller.py`, `web/index.html`, `web/app.js`):** Bổ sung `horizon_days: int = Field(default=7, ge=7, le=14)` trên `CommitmentsProfile`; cập nhật `BaseScheduler.resolve_horizon_slots()` và `grid_states` (`base_solver.py`, `greedy_lst.py`, `backtracking.py`, `local_repair.py`, `controller.py`) mở rộng tới `1344` slots; thêm nút `◀ Tuần 1 / Tuần 2 ▶`, `7 ngày / 14 ngày`, `🕒 Tuần này` (`getCurrentMondayIso()`, `jumpToCurrentWeek()`), và hiển thị đúng Tuần 2 ở giao diện Student & Lab Grid.
  4. **Student CRUD, `PersonalHabit` (`Q7.3 = A3`), Solver Constraints & Regex (`src/models.py`, `src/controller.py`, `src/solvers/base_solver.py`, `src/solvers/backtracking.py`, `src/nl_parser.py`, `web/index.html`, `web/app.js`):** Bổ sung nút `✏️ Sửa` + `editStudentTask(tid)`; thêm form `PersonalHabit` trong `#stSettingsModal` (`addStudentPersonalHabit()`, `removeStudentPersonalHabit()`) và cập nhật `expand_personal_habits()` rải đều theo thứ trong tuần + chấm điểm `preferred_window` ở `score_candidate_slot()`; bổ sung `Task.start_after` (`resolve_start_after_slot`) và `Task.work_rhythm` (`LIGHT`/`BALANCED`/`FLOW`) nối vào `BaseScheduler` & `BacktrackingSolver`; gỡ `engine: "offline"` trong `analyzeQuickAddHybrid()`; sửa `OfflineNLParser.extract_duration_min()` lọc chuẩn khoảng giờ `14h00 - 16h00` và giờ 24h `19h30` để `"Làm lab mạng 19h30 khoảng 90p"` ra đúng `90` thay vì `1170`.
  5. **Gói B Dọn kỹ thuật & Kiểm thử (`web/app.js`, `requirements.txt`, `requirements-nllb.txt`, `run_app.bat`, `setup_env.bat`, `verification_tests/run_*.bat`, `agents/requirements.md`, `docs/requirements.md`, `verification_tests/logical_tests/test_milestone2_production_readiness.py`):** Đặt Student UI/Settings & `"empty"` preset mặc định `COGNITIVE_LOAD` (`1.20/1.35`, giữ `"HABIT"` ở Pydantic V0); tách 3 thư viện NLLB sang `requirements-nllb.txt`; sửa 3 file `.bat` tự chọn `.venv\Scripts\python.exe`; bổ sung 6 test hồi quy Cột mốc 2.
- **Kiểm thử xác nhận:** `clean_runner.py --pass` (`147/147`), `--gaps` (`5/5`), `--all` (`153/153`), `pytest -q` (`153 passed`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `659.8 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, Bảng 5 `EDF 4268107a006d` vs `SCORED_GREEDY f65266353eff -> ac905601e5bf`), `node --check web/app.js` (`exit 0`).

---

### Lần cập nhật 011 — 2026-11-17 | Hoàn Tất `Q10` Nhịp 2 (Tách `EDF` Energy-Blind, Forward `_repair_full_rebuild`), Chốt Toàn Bộ `☑ Q1–Q10` & Kế Hoạch UX Modal (`M1-NL-Parser`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:**
  1. **Tách Shared Solver Registry (`src/solvers/registry.py`, `src/controller.py`):** Đưa `SOLVER_REGISTRY` và `resolve_solver()` thành module dùng chung giữa `ScheduleController` và `LocalRepairEngine`, không trùng lặp map solver và giữ nguyên `INV-1`–`INV-6`.
  2. **Tách V0 `EDF`/`LST`/`WSPT` về thuần Energy-Blind (`src/solvers/base_solver.py`, `src/solvers/backtracking.py`):** Đổi `BaseScheduler.should_prefer_energy_placement()` thành `False`, chuyển `build_chunk_reasons()` thành `@classmethod` chỉ sinh `ENERGY_MATCH`/`ENERGY_FALLBACK`/`BATCHED_CATEGORY` cho solver Energy-Aware; giữ `BacktrackingSolver` & `ScoredGreedySolver` tối ưu nhịp sinh học và gom nhóm.
  3. **Truyền đúng solver khi `FULL_REBUILD` (`src/solvers/local_repair.py`, `src/controller.py`, `web/api.py`, `web/app.js`):** Nối tham số `algorithm` qua `repair_disruption()`, `_repair_full_rebuild()`, `compare_repair_modes()`, `POST /api/repair`, `runDisruptionRepair()`, và `runDisruptionComparison()` thay vì gắn cứng `GreedyEDFSolver`.
  4. **Cập nhật `--gaps`, Bảng 5 `benchmark_runner.py` & Regression Tests (`test_improve_plan_gaps.py`, `test_sync_algorithm_fixes.py`):** Chuyển `test_fail_circadian_energy_matching` và `test_fail_why_popover_structured_reason_codes` sang `SCORED_GREEDY`, thêm Bảng 5 đối chứng `T09` (`EDF` bất biến `4268107a006d` vs `SCORED_GREEDY` dịch Peak) và thêm `test_q10_phase2_edf_energy_blind_ablation_and_full_rebuild_solver_forwarding` (`15/15`).
  5. **Chốt `☑ Q1–Q10` & Kế hoạch `Gói A.0` (`Proposal/`):** Đánh dấu chốt toàn bộ `☑ Q1–Q10` theo xác nhận của owner, ghi nhận kết quả test tay Web UI (`http://127.0.0.1:8000`), và bổ sung kế hoạch Progressive Disclosure (`Gói A.0`) tối giản `#stTaskModal` ở `STUDENT` Mode so với `LAB` Mode.
- **Kiểm thử xác nhận:** `clean_runner.py --pass` (`141/141`), `--gaps` (`5/5`), `--all` (`147/147`), `pytest -q` (`147 passed`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `696.3 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, Bảng 5 `T09` tách biệt `EDF` vs `SCORED_GREEDY`), `node --check web/app.js` (`exit 0`), và user test tay Web UI đạt yêu cầu.

---

### Lần cập nhật 010 — 2026-11-17 | Hoàn Thiện Cột Mốc 1 Pre-Merge (`M1-NL-Parser`), Mặc Định `SCORED_GREEDY` (`Q10` Nhịp 1) & Hợp Nhất `Proposal/`
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:**
  1. **Sạch hóa Relative Import, Sửa lỗi `attachments: list[str]` & Docstring thang độ gấp (`NL_Parser_Package/`, `verification_tests/`):** Loại bỏ chèn thư mục con `NL_Parser_Package/` vào `sys.path`, chuyển 5 module nội bộ (`__init__.py`, `hybrid_parser.py`, `parser.py`, `regex_parser.py`, `tokenizer.py`), `src/nl_parser.py`, `verify_hybrid_200.py` và `test_hybrid_unbiased_generalization.py` sang package/relative import sạch; thêm `_normalize_attachment_items()` xử lý an toàn `str`, `dict` và danh sách pha trộn; bổ sung docstring giải thích quy đổi `{1: 5, 2: 4, 3: 3, 4: 1}` ngay tại `map_user_urgency_to_solver_priority()`.
  2. **Telemetry `ai_status` & Bảo toàn giờ buổi (`src/nl_parser.py`):** Gán `validation["ai_status"]` (`ACTIVE`, `OFFLINE_REQUESTED`, `MISSING_GOOGLE_GENAI_PACKAGE`, `MISSING_API_KEY`, `FALLBACK_AFTER_ERROR`) và ghi cảnh báo rõ vào `assumptions` thay vì rơi im lặng về offline; tách helper `OfflineNLParser.extract_coarse_window_time()` (`sáng->11:00`, `trưa->12:00`, `chiều->17:00`, `tối->21:30`) dùng chung cho `GeminiNLParser` (Rule 6 prompt + fallback khi `deadline_time=None`).
  3. **Mặc định `SCORED_GREEDY` cho Web UI & `/api/plan` (`Q10` Nhịp 1 — `web/index.html`, `web/app.js`, `web/api.py`):** Cập nhật `#solverSelect`, `#stSetSolver`, `#kpiSolverLabel`, fallback JS (giữ nguyên `compareAlgoLeft` đối chứng), và fallback `POST /api/plan` sang `SCORED_GREEDY`.
  4. **Mở rộng Regression Tests (`verification_tests/logical_tests/test_hybrid_nl_integration.py`):** Tăng từ 8 lên 12 test kiểm chứng `list[str]` / mixed attachments, clean relative imports, đủ trạng thái `ai_status`, mocked Gemini giữ giờ `"chiều" -> 17:00`, `/api/plan` mặc định `SCORED_GREEDY`, và 16 câu EN/VI thực tế mới ngoài bộ 200 ca YAML.
  5. **Hợp nhất `Proposal/` & Nhật ký (`Proposal/`, `agents/`, `docs/`):** Gộp kết quả Live Gemini `17/11/2026`, `Q1.3`, `Q6.2 = A2`, `Q7.3 = A3` và checklist Cột mốc 1 vào `Proposal/Production_Readiness_And_Decision_Analysis.md`, xóa file trùng `Proposal/bao_response.md`, cập nhật `Proposal/Open_Decisions_For_Team.md` & `Proposal/Sync_Completion_Report.md`, đánh dấu `ARCHIVED` ở `Proposal/Sync_Audit_And_Fix_Guide.md`, đồng bộ `commit_changes.md`.
- **Kiểm thử xác nhận & Lưu ý:** `clean_runner.py --pass` (`140/140`), `--gaps` (`5/5`), `--all` (`146/146`), `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200`, `616.5 ms`), `benchmark_runner.py` (`T01–T10 C_hard=0`, `T04` `100.00%` Stability), `node --check web/app.js` (`exit 0`), Live Gemini qua FastAPI `TestClient` (`200 OK`, `AI_GEMINI`, `"chiều mốt..." -> Wednesday 17:00, dur=90 -> SCORED_GREEDY 1 block`). Kiểm chứng trình duyệt tương tác `chrome_devtools` bị `BLOCKED` do Chrome chưa bật remote debugging (`DevToolsActivePort`), cần test nhanh trên Chrome/Edge trước khi bấm Merge PR #4.

---

### Lần cập nhật 009 — 2026-11-16 | Tích Hợp Hybrid EN/VI NL Parser, Nâng Cấp Modal Nhập Liệu & Chốt Phương Án A (`Q9`) (`ltbinh/sync-proposal`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `ltbinh/sync-proposal`
- **Tóm tắt thay đổi:**
  1. **Bộ phân tích ngôn ngữ tự nhiên Hybrid 6 tầng EN/VI (`NL_Parser_Package/`, `src/nl_parser.py`, `web/api.py`):** Di chuyển `NL_Parser_Package/` vào `group03-smartschedule-baseline/NL_Parser_Package/` và tinh gọn chỉ giữ 7 module chạy thực tế (`__init__.py`, `hybrid_parser.py`, `parser.py`, `regex_parser.py`, `schema.py`, `tokenizer.py`, `translator.py`). Bổ sung ánh xạ `1=Khẩn..4=Thấp -> 5..1`, tách & kiểm tra định dạng trích dẫn `[[filename]]`/`@[path/file]` (`E_INVALID_CITATION_FORMAT`), đối chiếu `ui.linked_files` (sửa lỗi khớp chuỗi con), đồng bộ độ ưu tiên theo `category`, và hỗ trợ backend dịch VI→EN (`rule`, `nllb`, `opus_mt`).
  2. **Nâng cấp UI/UX Modal Công Việc & Kéo-Thả Đa Trình Duyệt (`web/index.html`, `web/app.js`):** Mở rộng `#stTaskModal` (`max-w-3xl lg:max-w-4xl`, `max-h-[90vh]`, cuộn mượt), thêm nút đóng `✕` + Esc/click nền, lưu nháp tự động `localStorage` (`#stModalDraftBadge`, `#btnStClearDraft`), thiết kế ô chat `#stNlPromptBox` + `#stNlFileLinkBox` hiện cảnh báo đỏ khi sai định dạng hoặc thiếu tệp, đưa nút cắt nhỏ (`✂️ Cho phép cắt nhỏ` | `🔒 Làm liền 1 buổi`) lên thanh nhập tự nhiên, thêm `#stInpTaskId` + chip `#stExistingTaskIdChips` cho `"Task cần phải làm trước đó (Task ID)"`, và gia cố kéo-thả trên Chrome, Edge, Firefox, Safari.
  3. **Chốt `Q9` Phương án A & Kiểm thử khách quan (`verification_tests/`):** Cập nhật `test_fail_edge_sprint_mode_compression_recovery` kiểm chứng `INFEASIBLE_CAPACITY` + `Early Extension Alert` + xác nhận nén `SHORTEN_TASK` và Tier-1 `Cut breaks` (`crunch_tier_used == 1`). Thêm `verification_tests/NL_Parser_test_cases/` (200 ca YAML + `validate_cases.py` + `verify_hybrid_200.py`), `test_hybrid_nl_integration.py` (8 tests), và `test_hybrid_unbiased_generalization.py` (9 tests).
  4. **Đồng bộ thư viện (`requirements.txt`, `agents/requirements.md`, `docs/requirements.md`):** Cập nhật `PyYAML>=6.0`, `ctranslate2>=4.5.0`, `sentencepiece>=0.2.0`, `huggingface-hub>=0.25.0`.
- **Kiểm thử xác nhận (trước khi cập nhật tài liệu cuối):** `validate_cases.py` (`200/200`), `verify_hybrid_200.py` (`200/200` / `458.1 ms`), `clean_runner.py --pass` (`136/136`), `clean_runner.py --gaps` (`5/5`), `pytest` (`142 passed`).

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

