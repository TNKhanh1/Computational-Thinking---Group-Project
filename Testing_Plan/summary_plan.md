# Tóm Tắt Công Việc Hiện Tại & Hướng Dẫn Cải Tiến App Dành Cho Thành Viên + AI Agent

> **Nhánh làm việc hiện tại:** `feat/v3-solvers-and-member-eval` *(tách an toàn từ `testing-system/v2.1-fuzz-handoff` `8b93bae`)*  
> **Đối tượng đọc:** 7 thành viên Nhóm 03 (*The Seven Dwarfs*) & mọi AI Agent cộng tác trên repo SmartSchedule.  
> **Quy tắc gốc bắt buộc đọc kèm:** [AGENTS.md](../AGENTS.md) · [agents/commit_changes.md](../agents/commit_changes.md) · [docs/commit_changes.md](../docs/commit_changes.md).

---

## I. Tôi Đang Làm Gì? (Bức Tranh Dễ Hiểu Cho Cả Nhóm)

Cho đến hiện tại trên nhánh **`feat/v3-solvers-and-member-eval`**, tôi đã hoàn thành trọn vẹn **3 cụm công việc nối tiếp nhau** để đưa bộ lập lịch của SmartSchedule từ bản V0/V2 (*xếp không trùng nhưng còn mệt, dễ gãy ở tải khít*) sang bản V3 hướng trải nghiệm sinh viên — có số liệu kiểm chứng chặt chẽ và công cụ cho cả nhóm trực tiếp chấm điểm:

### 1. Đại tu 5 thuật toán cũ + Thiết kế thuật toán thứ 6 (`HYBRID_ALNS`)
* Thay vì để 5 file solver tự đặt slot rời rạc, tôi gom toàn bộ bộ não công thái học dùng chung vào [`src/solvers/ergonomic_engine.py`](../group03-smartschedule-baseline/src/solvers/ergonomic_engine.py) (prefix-sum `O(1)`, đếm trần ngày `<= 2` ca nặng & tổng `lớp + tự học <= 540–600p`, nghỉ `>= 15p` sau `load=3` & sau lớp dài, chặn thông mạch `load>=2 <= 120p`, né `energy=1`, giữ đệm sốc `+25%`, cân bằng pha `SJL` & độ đều tải `TStd`, chia mảnh hợp chuẩn `G1`, cứu hạn Kempe `1/2-eject` và sàn khả thi First-Fit).
* **Trạng thái 6 thuật toán trong [`src/solvers/registry.py`](../group03-smartschedule-baseline/src/solvers/registry.py):**
  1. **`EDF`** ([`greedy_edf.py`](../group03-smartschedule-baseline/src/solvers/greedy_edf.py)): **Giữ nguyên 100% V0** làm mốc đối chứng mù sinh học (`T09`).
  2. **`WSPT` & `LST`** ([`greedy_wspt.py`](../group03-smartschedule-baseline/src/solvers/greedy_wspt.py), [`greedy_lst.py`](../group03-smartschedule-baseline/src/solvers/greedy_lst.py)): Nâng cấp khả năng cứu hạn (`0 SUBOPT`) nhưng **khóa bất biến Mù Năng Lượng (`Q10`)** (`MORNING == EVENING` từng bit).
  3. **`SCORED_GREEDY`** ([`scored_greedy.py`](../group03-smartschedule-baseline/src/solvers/scored_greedy.py)): **Mặc định Web UI** — portfolio 3 chiến lược + local polish, nhanh và đứng `#1` nhiều nhất.
  4. **`BACKTRACK`** ([`backtracking.py`](../group03-smartschedule-baseline/src/solvers/backtracking.py)): Nâng cấp thành **Nhánh–Cận trạng thái sống** có warm-start + cắt tỉa theo tải tích lũy ngày.
  5. **`HYBRID_ALNS`** *(mới — thuật thứ 6, [`hybrid_alns.py`](../group03-smartschedule-baseline/src/solvers/hybrid_alns.py), alias `ALNS`/`ULTIMATE`)*: Portfolio 4 chiến lược + **80 vòng ALNS** (*5 toán tử Ruin + chèn Regret-2*) + đánh bóng 3 lượt.

### 2. Chứng minh bằng số liệu trên 220 kịch bản (gồm 50 đề ẩn chống học vẹt)
* Toàn bộ chi tiết bảng 11 tiêu chí nằm ở [Solver_Benchmark_Report.md](Solver_Benchmark_Report.md) và [ultimate_plan.md](ultimate_plan.md); **`Testing_System/` giữ nguyên 0 dòng sửa**:
  * **`clean_runner.py --all`:** **`164 / 164` Passed** *(gồm 6 test V3 tại [`test_ergonomic_solvers_v3.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_ergonomic_solvers_v3.py) và 3 test tool đánh giá tại [`test_member_eval_program.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_member_eval_program.py))*.
  * **`benchmark_runner.py`:** **`EXIT = 0`** (`T01–T10 C_hard=0`, `3x Determ PASS`, `T04 LOCAL_INSERTION Stability=100.00%`, `T09` Ablation PASS).
  * **`pytest Testing_System/tests -v`:** **`39 / 39` passed**.
  * **Benchmark 220 đề × 6 thuật (`1.320` lượt chạy):** **`0 INVALID`, `0 SUBOPT`, `0/220` invariant thất bại, `0/220` nghịch lý xếp hạng, `max_exec_ms <= 774.8 ms` (`< 1000 ms`)**:
    * **`SCORED_GREEDY`:** Hạng TB **`2.22`** Regimes (`77/120 HIGH`), **`22/24` (`91.7%`)** Fuzz `LOOSE HIGH`, **`25/25` (`100.0%`)** tập ẩn `5001..5050` (`AvgRk 2.48`).
    * **`HYBRID_ALNS`:** Dẫn đầu tổng số ca **`HIGH_PRODUCTIVITY`** (**`79/120`** Regimes gồm **`19/20 R1`**, **`22/24`** Fuzz `LOOSE`, **`25/25`** Unseen `LOOSE`, `APk=84.1%` / `71.9%`, `max <= 774.8 ms`).
    * **`BACKTRACK`:** **`23/24` (`95.8%`)** Fuzz `LOOSE HIGH` (`AvgRk 2.30`), **`24/25`** Unseen `LOOSE HIGH`.

### 3. Xây Chương trình Trung Gian cho cả 7 thành viên chấm thử lịch ngoài đời (`member_eval/`)
* Vì máy chấm `v2.1` mới chỉ đo trên đề tổng hợp, tôi đã lập kế hoạch [evaluation_plan.md](evaluation_plan.md) và cài đặt xong chương trình trung gian tại [`group03-smartschedule-baseline/member_eval/`](../group03-smartschedule-baseline/member_eval/evaluate_schedule.py):
  * Chạy 1 chạm qua [`run_member_eval.bat`](../group03-smartschedule-baseline/run_member_eval.bat) (`http://127.0.0.1:8010`) hoặc CLI (`--mode cli`).
  * **Chấm mù (`#A / #B / #C...`):** Ẩn tên thật của solver khi thành viên xem thời khóa biểu tuần (`7/14 ngày`) hoặc tuần thật tự nhập, bấm thẳng vào block để gắn nhãn lỗi (`AWKWARD_SPLIT`, `BAD_TIME_OF_DAY`, `TOO_TIGHT_GAP`, `CONTEXT_JUMP`, `DAY_OVERLOAD`, `HABIT_MISPLACED`, `WRONG_PRIORITY`), chấm `UX-1..UX-5` & chọn lịch thắng mù (`UX-6`) trước khi mở khóa bảng chuẩn `Testing_System v2.1` + `Top ICEE`.
  * **Tổng hợp tự động:** Phiếu lưu ở `member_eval/reviews/` được gộp thành `member_eval/Calibration_Report.md` chỉ rõ người dùng thật đồng ý hay bất đồng với máy chấm ở đâu.

---

## II. Việc Nhóm & Các AI Agent Khác Cần Làm Tiếp Để Hoàn Thiện App

### Bước 0 — Việc ngay cho 7 thành viên Nhóm 03 (không cần biết code sâu)
1. Kéo nhánh **`feat/v3-solvers-and-member-eval`**, mở [`run_member_eval.bat`](../group03-smartschedule-baseline/run_member_eval.bat) → vào `http://127.0.0.1:8010`.
2. Chọn đúng tên của bạn trong **7 thành viên** ([`work_division.pdf`](../Proposal/work_division.pdf)) và chấm tối thiểu **3 ca**:
   * **Ca 1:** Tuần học thật của chính bạn (*bấm `"Tự nhập tuần"` -> nạp mẫu sửa nhanh*).
   * **Ca 2:** Một kịch bản tải vừa (`REGIME_3_CIRCADIAN` hoặc `FUZZ_LOOSE_14D`).
   * **Ca 3:** Một kịch bản nước rút / quá tải (`FUZZ_TIGHT_7D` hoặc `REGIME_5_OVERLOAD`).
3. Nộp phiếu xong chạy `python -B group03-smartschedule-baseline/member_eval/evaluate_schedule.py --mode aggregate` để xuất `Calibration_Report.md`.

---

### Hướng dẫn chi tiết cho **AI Agent** cải tiến App (`Priority P1 -> P3`)

#### Nhiệm vụ 1 (`P0` — Hiệu chỉnh Solver dựa trên phản hồi người thật từ `Calibration_Report.md`)
* **Đọc trước khi sửa:** [`member_eval/Calibration_Report.md`](../group03-smartschedule-baseline/member_eval/evaluate_schedule.py), [`Testing_Plan/evaluation_plan.md`](evaluation_plan.md), [`src/solvers/ergonomic_engine.py`](../group03-smartschedule-baseline/src/solvers/ergonomic_engine.py).
* **Cách làm cho Agent:**
  * Kiểm tra các ca *Disagreement* (`Human Vote != v2.1 #1`) và cụm `Block Issue Tags >= 25%`:
    * Nếu dính `AWKWARD_SPLIT`: tăng ưu tiên phương án ít chia mảnh (`opts[0]`) và thêm phạt nhẹ theo số chunk trong `score_candidate_unit()`.
    * Nếu dính `CONTEXT_JUMP`: tăng trọng số phạt `context_switch` trong `score_candidate_unit()`.
    * Nếu dính `BAD_TIME_OF_DAY` / `HABIT_MISPLACED`: tinh chỉnh phạt `preferred_window` hoặc cửa sổ `MORNING`/`AFTERNOON`/`EVENING` trong `ergonomic_engine.py` *(nhớ bảo vệ test `test_personal_habit_preferred_window_and_day_spreading`)*.
  * **Tuyệt đối không phá:** `G1 == 0`, `0 SUBOPT`, `Q10` mù năng lượng của `WSPT`/`LST`, `Regime 3` `SCORED_GREEDY` Rank `#1`, và trần `exec_ms <= 1000 ms`.

#### Nhiệm vụ 2 (`P1` — Đưa `HYBRID_ALNS` & Chỉ số `v2.1` lên Giao Diện Web Chính `web/`)
* **Hiện trạng đã phát hiện trong repo:** Thuật toán thứ 6 `HYBRID_ALNS` mới nằm ở backend [`src/solvers/registry.py`](../group03-smartschedule-baseline/src/solvers/registry.py) và `member_eval/`, **chưa xuất hiện trong HTML/JS của App chính** (`#stAlgoSelect`, `#solverSelect`, `#compareLeftAlgo`, `#compareRightAlgo`, và Ledger Determinism trong [`web/index.html`](../group03-smartschedule-baseline/web/index.html) / [`web/app.js`](../group03-smartschedule-baseline/web/app.js)), cũng như chưa có mặt trong Bảng 2 của [`benchmark_runner.py`](../group03-smartschedule-baseline/benchmark_runner.py).
* **Cách làm cho Agent:**
  1. Giữ **`SCORED_GREEDY`** làm tùy chọn mặc định (*Nhanh / Chuẩn hàng ngày*) và thêm option **`HYBRID_ALNS`** (*Tối ưu sâu / Deep Optimize*) vào cả Student Mode & Lab Mode (gồm A/B Compare và bảng 3x Determinism Ledger).
  2. Bổ sung telemetry sức khỏe `v2.1` vào `ScheduleController.compute_schedule_insights()` ([`src/controller.py`](../group03-smartschedule-baseline/src/controller.py)) → [`web/api.py`](../group03-smartschedule-baseline/web/api.py) → [`web/app.js`](../group03-smartschedule-baseline/web/app.js): tổng tải `lớp + tự học/ngày` (`<= 540/600p`), cảnh báo chuỗi `load>=2 > 120p`, `OffP/APk%`, sức sống sót dưới sốc `+25%`, `Ctx`.
  3. **Lưu ý ranh giới kiến trúc (`INV-1..6`):** Nếu viết lại công thức chấm hoặc chia sẻ logic, đặt vào tầng Domain thuần (`src/metrics.py` / `src/controller.py`), **tuyệt đối không** import `Testing_System` hay `fastapi`/`web` vào `src/solvers/` hoặc `src/models.py`.
  4. Chạy trình duyệt thật kiểm tra toàn luồng tại `http://127.0.0.1:8000` + giữ xanh các test hợp đồng UI (`test_ui_contract_improve_plan.py`, `test_ui_endpoints.py`, `test_milestone2_production_readiness.py`).

#### Nhiệm vụ 3 (`P2` — Pilot Thực Tế 1 Tuần, `α >= 1.7` & Tài Liệu Bảo Vệ)
* Thu thập log hoàn thành thực tế `actual_duration_min` từ `/api/tasks/complete` (`src/storage.py`), mở rộng kịch bản tải hẹp `α >= 1.7` vào [`benchmark_alpha_grid.py`](../group03-smartschedule-baseline/benchmark_alpha_grid.py).
* Cập nhật [`README.md`](../README.md) và [`Testing_System/README.md`](../Testing_System/README.md) phản ánh đủ 6 solvers, `v2.1`, `164` app tests, `39` Testing_System pytests và chương trình `member_eval/`.
* Đưa bảng trước/sau V0 → V3 và 17 lập luận trong [`CT_Rationale_Log.md`](CT_Rationale_Log.md) vào slide báo cáo cuối kỳ (`Proposal/Presentation2.pdf`).

---

## III. Điều Luật Bắt Buộc Cho Mọi AI Agent Trước Khi Kết Thúc Task

1. **Vùng Cấm Sửa (Read-Only):**
   * **KHÔNG ĐƯỢC SỬA** bất kỳ file nào trong `Testing_System/`.
   * **KHÔNG ĐƯỢC SỬA** [`src/solvers/greedy_edf.py`](../group03-smartschedule-baseline/src/solvers/greedy_edf.py) *(mốc V0 đối chứng)*.
   * **KHÔNG ĐƯỢC ĐỌC `energy_profile`** khi `energy_aware=False` (bảo toàn bất biến mù năng lượng `Q10` cho `WSPT` & `LST`).
2. **Bất Biến Kiến Trúc (`INV-1..6`):**
   * `src/solvers/` và `src/models.py` không import `web`/`fastapi`.
   * Mọi `solver.solve()` phải **stateless 100%** (3x SHA-256 giống nhau), không mutate input, trả đúng `(ScheduleOutput, TimeGridManager)`.
   * Tôn trọng `AGENTS.md`: mọi con số báo cáo phải trích trực tiếp từ output chạy thật — cấm suy đoán.
3. **Bộ Kiểm Định Bắt Buộc Chạy Sau Lần Sửa Code Cuối Cùng:**
   ```powershell
   python -B group03-smartschedule-baseline/verification_tests/clean_runner.py --all
   python -B group03-smartschedule-baseline/benchmark_runner.py
   python -B -m pytest Testing_System/tests -v
   ```
   *(Nếu có sửa giao diện `web/app.js`, chạy thêm `node --check group03-smartschedule-baseline/web/app.js` và test lại bằng trình duyệt sống.)*
4. **Bắt Buộc Đồng Bộ Tài Liệu & Commit Sạch:**
   * Ghi thêm 1 dòng lập luận CT vào [`Testing_Plan/CT_Rationale_Log.md`](CT_Rationale_Log.md) (`Rule 1`).
   * Nếu benchmark đa thuật toán trên `Testing_System`, cập nhật đủ 5 mục trong [`Testing_Plan/Solver_Benchmark_Report.md`](Solver_Benchmark_Report.md) (`Rule 2`).
   * Cập nhật đồng thời cả [`agents/commit_changes.md`](../agents/commit_changes.md) (Tiếng Anh) và [`docs/commit_changes.md`](../docs/commit_changes.md) (Tiếng Việt) thành Entry tiếp theo trước khi commit; không commit `.env`, `data/*.db`, hay `__pycache__/`.
