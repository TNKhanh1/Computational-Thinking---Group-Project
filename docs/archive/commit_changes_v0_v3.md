# SmartSchedule — Kho Lưu Trữ Nhật Ký Thay Đổi (Lần Cập Nhật 001–015: V0 Baseline đến Đại Tu V3)

> [!NOTE]
> Tệp lưu trữ này bảo toàn lịch sử **Lần cập nhật 001 đến 015** (`29/10/2026` – `20/11/2026`) được tách ra khỏi [`docs/commit_changes.md`](../commit_changes.md) để giữ nhật ký chính gọn nhẹ cho thành viên và AI Agent. Các đường dẫn ghi trong các mục lịch sử này phản ánh cấu trúc cũ (`group03-smartschedule-baseline/src/`, `web/`, `verification_tests/`, `NL_Parser_Package/`) trước khi tổ chức lại sang `smartschedule/`, `data/`, `tests/`, `tools/`. Để bắt đầu làm việc theo chuẩn `v1.0-alpha`, vui lòng xem [`v1.0-alpha-plan/README.md`](../../v1.0-alpha-plan/README.md) và [`docs/README.md`](../README.md).

---

### Lần cập nhật 015 — 2026-11-20 | Đại Tu V3 Bộ 5 Thuật Toán & Thiết Kế Thuật Toán Thứ 6 `HYBRID_ALNS` (`testing-system/v2.1-fuzz-handoff`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `testing-system/v2.1-fuzz-handoff`
- **Tóm tắt thay đổi:** Hoàn thiện kế hoạch `Testing_Plan/ultimate_plan.md`, xây lại toàn bộ bộ giải (`WSPT`, `LST`, `SCORED_GREEDY`, `BACKTRACK`) và tạo thuật toán cao cấp thứ 6 (`HYBRID_ALNS`) qua hạt nhân chung `src/solvers/ergonomic_engine.py` (không chạm `Testing_System/` và giữ nguyên `EDF` làm mốc V0): xóa sạch **`SUBOPT → 0/220`** trên mọi thuật toán, nâng **`LOOSE HIGH_PRODUCTIVITY`** từ `0/24` lên **`22–23/24` (`91.7%–95.8%`)** ở Fuzz `1001..1050` và **`25/25` (`100.0%`)** trên tập ẩn `5001..5050`.
- **Chi tiết kỹ thuật:**
  1. **Hạt nhân Công thái học Tĩnh-Trạng-Thái (`src/config.py`, `src/solvers/ergonomic_engine.py`):** Thêm ngưỡng bảo vệ sinh học; xây `ErgonomicContext` với prefix-sum `O(1)`, lan truyền hạn DAG ngược, `ScheduleState` tăng dần, công thức `SJL` vòng Smarr & Schirmer, hàm đánh giá từ điển 10 cấp `evaluate_state_lex_key`, tách mảnh thích ứng chuẩn `G1`, cứu hạn Kempe `1/2-eject`, sàn khả thi First-Fit, ba lô ưu tiên `OVERLOAD_PACK`, `polish_schedule_deterministic` và `run_alns_deterministic` (`5` toán tử Ruin + Regret-2 Insertion). Tuân thủ trọn vẹn `INV-1..6`.
  2. **Nâng cấp 5 Solver + Tạo Thuật Toán Thứ 6:** Giữ nguyên `greedy_edf.py` (V0); `WSPT` & `LST` thuần mù năng lượng (`Q10`: `MORNING == EVENING`); `SCORED_GREEDY` tối ưu mặc định Web UI; `BACKTRACK` nhánh-cận trạng thái sống; bổ sung `HybridALNSSolver` (`HYBRID_ALNS`/`ALNS`/`ULTIMATE`).
  3. **Kiểm thử & Tài liệu:** Thêm 6 test V3 trong `test_ergonomic_solvers_v3.py`, cập nhật Báo cáo Benchmark và CT Log (`#14–#16`).
- **Kiểm thử xác nhận:** `clean_runner.py --all` (`161/161`), `benchmark_runner.py`, `pytest Testing_System/tests -v` (`39/39`), và evaluation 220 đề × 6 thuật (`1.320` lượt: `0 INVALID`, `0 SUBOPT`).

---

### Lần cập nhật 014 — 2026-11-17 | Thanh Trượt Ngang Lịch & Lịch Tháng Hiển Thị Chuỗi Ngày Đang Quan Sát (`M1-NL-Parser`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:** Bổ sung thanh cuộn ngang + thanh trượt ngang (`range slider`) đồng bộ 2 chiều, dải mini-map đánh dấu chuỗi ngày đang hiện trên khung hình (`#stObservedDaysStrip`), hiển thị liên tục cả `14` ngày và popup **Lịch Tháng** (`#observedRangeCalendarPopover`).

---

### Lần cập nhật 013 — 2026-11-17 | Tái Thiết Lập UI: Trục Ngày Cụ Thể (`DD/MM/YYYY`), Gọn Giao Diện Sinh Viên & Lab Nghiên Cứu 3 Workspace (`M1-NL-Parser`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:** Hiển thị đầy đủ ngày `DD/MM/YYYY` và trạng thái Quá khứ / Đang diễn ra / Sắp tới, thêm telemetry sinh học & đúc kết A/B (`compute_schedule_insights`, `verdict_winner`, `block_diffs`), mở quản lý `PersonalHabit` và nâng cấp Lab Mode thành 3 workspace phân tích.
- **Kiểm thử xác nhận:** `clean_runner.py --all` (`155/155`).

---

### Lần cập nhật 012 — 2026-11-17 | Hoàn Thiện Cột Mốc 2 — Sẵn Sàng Thực Tế Hằng Ngày (`Gói A.0`, `Gói A.1–A.3`, `Gói B`) (`M1-NL-Parser`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:** Triển khai Progressive Disclosure `#stTaskModal` (`STUDENT` vs `LAB`), lưu trữ SQLite + `localStorage` qua F5 (`src/storage.py`, `/api/state`), đồng hồ thực & lập lịch đa tuần `horizon_days=7..14` (`1344` slots), Sửa Task + `PersonalHabit` UI (`Q7.3 = A3`), nối `start_after`/`work_rhythm`/`preferred_window` vào Solver, vá offline regex cụm giờ, mặc định `COGNITIVE_LOAD` cho Student UI và tách `requirements-nllb.txt`.
- **Kiểm thử xác nhận:** `clean_runner.py --all` (`153/153`).

---

### Lần cập nhật 011 — 2026-11-17 | Hoàn Tất `Q10` Nhịp 2 (Tách `EDF` Energy-Blind, Forward `_repair_full_rebuild`), Chốt Toàn Bộ `☑ Q1–Q10` & Kế Hoạch UX Modal (`M1-NL-Parser`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:** Tách `SOLVER_REGISTRY` (`src/solvers/registry.py`), đưa `EDF`/`LST`/`WSPT` về thuần Energy-Blind V0 cho bảng đối chứng `T09`, nối `algorithm` qua `FULL_REBUILD`/`/api/repair`, chốt toàn bộ `☑ Q1–Q10`.
- **Kiểm thử xác nhận:** `clean_runner.py --all` (`147/147`).

---

### Lần cập nhật 010 — 2026-11-17 | Hoàn Thiện Cột Mốc 1 Pre-Merge (`M1-NL-Parser`), Mặc Định `SCORED_GREEDY` (`Q10` Nhịp 1) & Hợp Nhất `Proposal/`
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Nhánh Git:** `M1-NL-Parser`
- **Tóm tắt thay đổi:** Sạch hóa relative import trong `NL_Parser_Package/`, sửa lỗi `attachments: list[str]`, bổ sung telemetry `ai_status` và bảo toàn giờ buổi cho Gemini (`extract_coarse_window_time()`), đặt `SCORED_GREEDY` làm mặc định và thêm 16 câu EN/VI thực tế.
- **Kiểm thử xác nhận:** `clean_runner.py --all` (`146/146`), `verify_hybrid_200.py` (`200/200`).

---

### Lần cập nhật 009 — 2026-11-16 | Tích Hợp Hybrid EN/VI NL Parser, Nâng Cấp Modal Nhập Liệu & Chốt Phương Án A (`Q9`) (`ltbinh/sync-proposal`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Tóm tắt thay đổi:** Đưa `NL_Parser_Package/` 7 module lõi vào baseline, mở rộng `#stTaskModal` kèm kéo-thả tệp và trích dẫn `[[filename]]`/`@[path]`, chốt `Q9` Phương án A (`INFEASIBLE_CAPACITY` + `Early Extension Alert` + `SHORTEN_TASK`), đồng bộ `PyYAML` vào `requirements.txt`.
- **Kiểm thử xác nhận:** `pytest` (`142 passed`), `verify_hybrid_200.py` (`200/200`).

---

### Lần cập nhật 008 — 2026-11-15 | Vá Lỗi Kiểm Toán & Đồng Bộ Tài Liệu (`ltbinh/sync-proposal`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Tóm tắt thay đổi:** Đồng bộ hợp đồng `/api/validate-move` (`proposed_block`), thêm `buffer_mode="NONE"` từng task, bảo vệ khối `PINNED`/`DONE` khi `repair_overrun`, gộp 1 ID `DIS_xxxx` mỗi sự cố, đưa `SCORED_GREEDY` vào benchmark.
- **Kiểm thử xác nhận:** `clean_runner.py --pass` (`107/107`), `--gaps` (`5/5`).

---

### Lần cập nhật 007 — 2026-11-15 | Đồng Bộ Toàn Bộ Proposal & Presentation2 (`ltbinh/sync-proposal`)
- **Người thực hiện:** ltbinh (hỗ trợ bởi Antigravity AI)
- **Tóm tắt thay đổi:** Sửa lỗi `A1–A12`, chuẩn hóa `now_day`/`now_slot` động, bổ sung `PersonalHabit` + bảo vệ ngủ `>= 6h`, xây dựng `ScoredGreedySolver` + 8 Human Behavioral Patterns, tích hợp `OverloadTriageEngine`, M1/M7 pipeline và `benchmark_alpha_grid.py`.

---

### Lần cập nhật 006 — 06/11/2026 | Giao Diện Chế Độ Sinh Viên (Student Mode) Tối Giản & Nút Chuyển Đổi Dual-Mode
- **Người thực hiện:** Đức Minh (hỗ trợ bởi Antigravity AI)
- **Tóm tắt thay đổi:** Tạo nút chuyển `[Chế Độ Sinh Viên]` / `[Chế Độ Lab]`, 3 màn hình sinh viên (Lịch tuần, Hôm nay, Hàng đợi bài tập), hộp thoại 3 ô và nút Ghim / Check-in / Xem lý do.

---

### Lần cập nhật 005 — 06/11/2026 | Tính năng 001: Bộ Đệm Ước Lượng Thời Gian (Chống Planning Fallacy)
- **Người thực hiện:** Nguyễn Trọng Tiến (Thinker 3 — hỗ trợ bởi Claude Code)
- **Tóm tắt thay đổi:** Xây dựng module thuần `src/estimate_buffer.py` (`RARELY` x1.00, `SOMETIMES` x1.10, `OFTEN` x1.25), làm tròn số nguyên tất định theo ô 15 phút, gắn reason code `ESTIMATE_BUFFER` và bổ sung 34 bài test logic (`clean_runner.py --pass`: `84/84`).

---

### Lần cập nhật 004 — 04/11/2026 | Danh Mục Thư Viện (`requirements.md`) & Cài Đặt Tự Động 1-Click
- **Người thực hiện:** Nguyễn Nguyễn Gia Bảo (Builder 3)
- **Tóm tắt thay đổi:** Biên soạn `agents/requirements.md` & `docs/requirements.md`, tạo `setup_env.bat` và quy định đồng bộ thư viện.

---

### Lần cập nhật 003 — 04/11/2026 | Màn Hình Console Chẩn Đoán Sạch Sẽ & Cổng Tài Liệu Nhóm
- **Người thực hiện:** Nguyễn Nguyễn Gia Bảo (Builder 3)
- **Tóm tắt thay đổi:** Xây dựng `clean_runner.py` (`InterpretableConsolePlugin`), nối GUI `test_studio.py` và lập cổng tài liệu song ngữ `agents/` & `docs/` (`50/50` pass, `5/5` gap).

---

### Lần cập nhật 002 — 04/11/2026 | Ma Trận Kiểm Thử 60/40 & Giao Diện Test Studio
- **Người thực hiện:** Nguyễn Nguyễn Gia Bảo (Builder 3)
- **Tóm tắt thay đổi:** Tổ chức lại 56 bài test theo ma trận 60/40 và xây dựng ứng dụng desktop `test_studio.py`.

---

### Lần cập nhật 001 — 29/10/2026 | Khởi Tạo Bản Baseline V0 & Kịch Bản Môn Học
- **Người thực hiện:** Toàn thể Nhóm 03 (*The Seven Dwarfs*)
- **Tóm tắt thay đổi:** Khởi tạo lưới 672 ô, Pydantic schemas, 3 solver cơ sở (`EDF`, `LST`, `WSPT`), FastAPI workbench và 10 kịch bản `T01–T10`.
