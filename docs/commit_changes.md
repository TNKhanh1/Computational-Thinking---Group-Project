# SmartSchedule — Nhật Ký Thay Đổi & Quy Định Đồng Bộ Dự Án (`docs/commit_changes.md`)

> [!IMPORTANT]
> **ĐIỂM BẮT ĐẦU MỚI CHO BẢN `v1.0-alpha`:**
> - **Thành viên nhóm:** Đọc [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md) và [`docs/README.md`](README.md) để nắm kế hoạch tổng thể, cấu trúc thư mục mới (`smartschedule/`, `data/`, `tests/`, `tools/`) và đánh dấu `[x]` vào checklist việc đã làm.
> - **Mọi AI Agent:** Chỉ cần đọc [`agents/README.md`](../agents/README.md) và [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md), tuyệt đối tuân thủ `INV-1..6`, và chạy `python -B tests/clean_runner.py --pass` trước khi bàn giao.
> - *Lịch sử cũ hơn (Lần cập nhật 001–015) đã được cất gọn tại [`docs/archive/commit_changes_v0_v3.md`](archive/commit_changes_v0_v3.md). Quy định thư viện ở [`docs/requirements.md`](requirements.md) (khớp [`requirements.txt`](../requirements.txt) gốc).*

---

## 1. Tình Hình Dự Án Hiện Tại (`v1.0-alpha/ui-ux-chat`)

- **Kiến trúc thư mục chuẩn mới:** Đã thay thế hoàn toàn `group03-smartschedule-baseline/` bằng cấu trúc tách lớp tại gốc repo: [`smartschedule/`](../smartschedule/) (`core/`, `nlp/`, `api/`, `ui/`), [`data/`](../data/) (`presets/`, `scenarios/`, `calibration/`, `runtime/`), [`tests/`](../tests/) (`ui/`, `architecture/`, `logical/`, `benchmark/`, `gaps/`, `fixtures/nl_cases/`), [`tools/`](../tools/) (`member_eval/`, `benchmarks/`, `docker/`, `scripts/`), kèm [`pyproject.toml`](../pyproject.toml), [`.agentignore`](../.agentignore) và [`CODEBASE_INDEX.md`](../CODEBASE_INDEX.md).
- **Giao diện Chat-First & Đọc ngữ cảnh Online:** Màn hình mở đầu thoáng nhẹ **`"Trợ lý xếp lịch"`** (`#viewChat`), thanh trái thu gọn 100%, Lịch Tuần có `"Trợ lý tinh chỉnh trực tiếp"` bên phải, hộp **💭 Quá trình suy nghĩ** trong Developer Mode, truy vết task SHA-256 (`smartschedule/core/task_tracer.py`), và bộ phân tích ngữ cảnh 3 tầng hợp nhất (`clause_condenser.py` + `context_router.py` qua `gemini-2.5-flash-lite`).
- **Động cơ 6 Thuật Toán & Kiểm Định:** `EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS` kèm máy chấm `v1.0-alpha-plan/Testing_System/` (`v2.1`).
- **Kết quả Kiểm thử mới nhất:** `tests/clean_runner.py --pass` đạt **`194/194 PASSED`**, `Testing_System/tests` đạt **`39/39 passed`**, `verify_hybrid_200.py` đạt **`200/200 (100.0%)`**, JS `node --check` sạch **`exit 0`**.

---

## 2. Nhật Ký Các Lần Cập Nhật Gần Đây (`016–024`)

### Lần cập nhật 024 — 21/11/2026 | Chia Lại Cấu Trúc Thư Mục (`smartschedule/`, `data/`, `tests/`, `tools/`, `environments/`, `Project_Drafts/`), Tách Module & Đồng Bộ Cổng `v1.0-alpha-plan` (`v1.0-alpha/ui-ux-chat`)
- **Người thực hiện:** Thành viên dự án + Antigravity AI
- **Nhánh Git:** `v1.0-alpha/ui-ux-chat` (Commit `e56ab06`, `5a96211` và đồng bộ tài liệu `agents/`/`docs/`/`v1.0-alpha-plan/`)
- **Tóm tắt thay đổi:** Thực thi trọn vẹn [`v1.0-alpha-plan/folder_division_plan.md`](../v1.0-alpha-plan/folder_division_plan.md) xóa bỏ `group03-smartschedule-baseline/` (`e56ab06`), gom `Baseline_Plan/`, `Improve_Plan/`, `Proposal/` vào `Project_Drafts/` (`5a96211`), gom toàn bộ cấu hình môi trường vào `environments/` (chỉ để `.gitignore` & `README.md` ở gốc), viết `v1.0-alpha-plan/README.md` & `README_agents.md`, tinh gọn `agents/` và `docs/` (gỡ hoàn toàn tiến độ/link không còn sử dụng), và lưu trữ nhật ký `001–015`.
- **Chi tiết kỹ thuật:**
  1. **Tái cấu trúc thư mục gốc (`smartschedule/`, `data/`, `tests/`, `tools/`, `environments/`, `Project_Drafts/`):** Chuyển sạch lịch sử Git sang các cụm gọn gàng; gom toàn bộ cấu hình môi trường (`.env`, `.env.example`, `requirements*.txt`, `pyproject.toml`, `.agentignore`, `CODEBASE_INDEX.md`) vào [`environments/`](../environments/) và gom `Proposal/`, `Baseline_Plan/`, `Improve_Plan/` vào [`Project_Drafts/`](../Project_Drafts/) để ngoài gốc chỉ còn `.gitignore` và `README.md`.
  2. **Chia nhỏ tệp cồng kềnh:** Tách `chat_service.py` (`72.5 KB`) thành [`smartschedule/nlp/clause_condenser.py`](../smartschedule/nlp/clause_condenser.py), [`smartschedule/nlp/context_router.py`](../smartschedule/nlp/context_router.py) và [`smartschedule/api/chat/{thinking_stage,edge_cases,handlers}.py`](../smartschedule/api/chat/__init__.py); tách `app.css` thành `shell.css`, `dev-panel.css`, `calendar.css`, `chat.css`.
  3. **Chuẩn hóa đường dẫn & import:** Nối [`smartschedule/core/config.py`](../smartschedule/core/config.py) (`CORE_DIR`, `UI_DIR`, `PRESETS_DIR`, `SCENARIOS_DIR`, `CALIBRATION_DIR`, `DEFAULT_DB_PATH`) và chỉnh import trên `67+` file Python + cấu hình `pythonpath` trong `pyproject.toml`.
  4. **Cổng tài liệu `v1.0-alpha` & Dọn link thừa:** Viết mới [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md), [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md), [`agents/README.md`](../agents/README.md), [`docs/README.md`](README.md); gỡ liên kết các file kế hoạch cũ (`ke_hoach_baseline`, `ke_hoach_cai_tien`, `giao_dien_sinh_vien`) sang `docs/archive/` & `agents/archive/`; cập nhật quy tắc trong `requirements.md` và tài liệu `progress/`.
- **Kiểm thử xác nhận:** `node --check smartschedule/ui/app.js` & `smartschedule/ui/js/*.js` (`exit 0`), `python -B tests/clean_runner.py --pass` (**`194 Passed | 0 Failed`**, `57.35s`), `python -B -m pytest v1.0-alpha-plan/Testing_System/tests -q` (**`39 passed`**, `53.28s`), `python -B tests/fixtures/nl_cases/verify_hybrid_200.py` (**`200/200 (100.0%)`**, `789.0 ms`).

---

### Lần cập nhật 023 — 21/11/2026 | Hợp Nhất Mô Hình AI Đọc Ngữ Cảnh Online, Bộ Cô Đọng Tiêu Đề & Sửa Lỗi Căn Lề Lịch (`v1.0-alpha/ui-ux-chat`)
- **Tóm tắt:** Kết hợp bộ phân tích 2 lớp sẵn có với mô hình đọc ngữ cảnh online siêu nhẹ (`gemini-2.5-flash-lite` / `gemini-2.5-flash`, `0 MB` RAM máy) và bộ cô đọng tiêu đề tiếng Việt; sửa lỗi lệch nhãn `"Hôm nay"` và ẩn nút `"💬 Mở trợ lý"` khi khung chat phải đã mở sẵn (`194/194`).

### Lần cập nhật 022 — 21/11/2026 | Tinh Chỉnh UI Chat-First Bản 2: Tối Giản Hóa Tuyệt Đối, Sửa 1 Task Nhiều Ngày & Hộp Suy Nghĩ Developer Mode (`v1.0-alpha/ui-ux-chat`)
- **Tóm tắt:** Bấm logo `SS SmartSchedule` quay về `"Trợ lý xếp lịch"`; gỡ `"Nền năng lượng sinh học"`, `"Tiện ích nhanh"`, `"Chuyển nhanh tuần"`, `"Chỉnh nhanh việc đã lưu"`; ẩn 100% thanh trái khi đóng; sửa nút `⇥` thu gọn khung chat phải tại chỗ; chuẩn hóa nút **`🗓️ Kiểm tra lịch trình`**; sửa nhận diện 1 công việc đa ngày và thêm hộp **💭 Quá trình suy nghĩ** ở Developer Mode.

### Lần cập nhật 021 — 21/11/2026 | Tái Thiết Kế Giao Diện Chat-First, Thanh Trượt Dọc Bên Trái, Truy Vết Task SHA-256 & Trợ Lý Lịch Trực Tiếp (`v1.0-alpha/ui-ux-chat`)
- **Tóm tắt:** Mở đầu trực tiếp bằng `#viewChat`, gắn thanh trượt trái `#leftNavSidebar`, trợ lý lịch bên phải đồng bộ hiệu ứng lịch trực tiếp, module truy vết SHA-256 `task_tracer.py`, hỏi lại nhiều lượt, tính lại deadline với bộ đệm thói quen/EWMA, và xử lý `DEADLOCK`/`DENSE_WARNING` (`193/193`).

### Lần cập nhật 020 — 21/11/2026 | Tích Hợp `UI v3` Lên `main`, Gom Thư Mục Docker & Dọn File Thừa (`main`)
- **Tóm tắt:** Đưa `normalizeEvaluation()`, bộ chọn suite `Regimes R1–R6` & `FuzzGenerator v2`, 7 bảng Showcase, duyệt tuần chỉ-xem với cảnh báo `PAST_DUE`, và `Xóa tất cả lịch…` lên `main` (`193/193`).

### Lần cập nhật 019 — 21/11/2026 | Sửa Lỗi Merge UI v3 & Khôi Phục API Endpoint Đồng Bộ
- **Tóm tắt:** Khôi phục sạch ES module `app.js`, nút chọn `HYBRID_ALNS`, bảng sức khỏe `v2.1` + `ICEE` và Focus Timer `P3.3` (`186/186`).

### Lần cập nhật 018 — 20/11/2026 | Hạ Tầng Thương Mại Hóa `P3` (`P3.1` Auth, `P3.2` `.ics`/LMS, `P3.3` Focus Timer, `P3.4` Docker)
- **Tóm tắt:** Bổ sung xác thực đa người dùng PBKDF2/JWT, nhập thời khóa biểu `.ics` Moodle/Canvas thuần stdlib, bộ đếm Pomodoro nối M7, và cấu hình Docker (`178/178`).

### Lần cập nhật 017 — 20/11/2026 | `P1.3` Docs Sync, Stress Test Quá Đệm `α >= 1.70` (`P2.1`) & Hiệu Chuẩn EWMA M7 (`P2.2`)
- **Tóm tắt:** Chứng minh điểm gãy quá đệm `Over-Buffering Cliff` ở `α >= 1.70` (`20%` rớt hạn giả vs `0%` ở `1.20/1.35`) và bổ sung API hiệu chuẩn cá nhân hóa `/api/tasks/calibration` (`171/171`).

### Lần cập nhật 016 — 20/11/2026 | Chương Trình Chấm Mù `member_eval/` & Nâng Cấp `P1` Web UI/API (`HYBRID_ALNS` + `v2.1`)
- **Tóm tắt:** Xây dựng cổng đánh giá mù đa thành viên (`8010`) và đưa `HYBRID_ALNS` + 4 Trụ Cột `v2.1` lên Web App chính (`167/167`).

---

*(Lịch sử chi tiết các Lần cập nhật `001–015` từ `29/10/2026` đến `20/11/2026` xem tại [`docs/archive/commit_changes_v0_v3.md`](archive/commit_changes_v0_v3.md).)*

---

## 3. Quy Trình Đồng Bộ Khi Hoàn Thành Nhiệm Vụ Mới

1. Đánh dấu `[x]` trực tiếp vào danh sách công việc trong [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md) (và [`README_agents.md`](../v1.0-alpha-plan/README_agents.md)).
2. Ghi nhận ngắn gọn mục mới vào file này kèm bản tiếng Anh ở [`agents/commit_changes.md`](../agents/commit_changes.md).
3. Nếu thay đổi thư viện trong [`requirements.txt`](../requirements.txt), cập nhật đồng thời [`docs/requirements.md`](requirements.md) và [`agents/requirements.md`](../agents/requirements.md).
