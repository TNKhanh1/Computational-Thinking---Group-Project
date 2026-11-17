> [!NOTE]
> **ARCHIVED / TÀI LIỆU KIỂM TOÁN TIỀN ĐỒNG BỘ (LỊCH SỬ):** Tài liệu này phản ánh ảnh chụp kiểm toán mã nguồn trước đồng bộ trên `main` (`4c0a85a`), trước khi thực hiện đồng bộ trên `ltbinh/sync-proposal` và `M1-NL-Parser`. Không cập nhật đè số liệu mới lên file này; vui lòng xem trạng thái, số liệu kiểm thử mới nhất (`140` `--pass`, `5` `--gaps`, `146` `--all`, `200/200` YAML) và quyết định `Q1–Q10` tại [`Proposal/Sync_Completion_Report.md`](Sync_Completion_Report.md) và [`Proposal/Production_Readiness_And_Decision_Analysis.md`](Production_Readiness_And_Decision_Analysis.md).

# Báo Cáo Đối Chiếu, Rà Soát Thuật Toán & Hướng Dẫn Đồng Bộ App — SmartSchedule

> **Đối tượng đối chiếu:** Bộ tài liệu thiết kế trong `Proposal/` (`Proposal_Report.pdf`, `Presentation.pdf`, `work_division.pdf`, và bản mới nhất `Presentation2.pdf`), `Improve_Plan/improve_plan.md`, `Baseline_Plan/baseline_plan.md` **so với** mã nguồn hiện tại trên nhánh `main` (`4c0a85a`).
>
> **Nhánh đồng bộ vừa khởi tạo:** `ltbinh/sync-proposal` (tách từ `main` tại `4c0a85a`, owner: `ltbinh812` — Lê Tiến Bình, Builder 1 theo `Proposal/work_division.pdf` & `Proposal_Report.pdf` §10.2).
>
> **Nguyên tắc tài liệu:** Mọi vị trí file, tên hàm/biến, số dòng và kết quả đo đạc đều bám sát kiểm tra thực tế trên `main` (`4c0a85a`). Tài liệu này chỉ phân tích và chỉ dẫn sửa, chưa chỉnh sửa bất kỳ dòng code nào trong `group03-smartschedule-baseline/`.

---

## Mục lục

1. [Tổng quan trạng thái Repository, Git & Kết quả kiểm thử hiện tại](#1-tổng-quan-trạng-thái-repository-git--kết-quả-kiểm-thử-hiện-tại)
2. [Những điểm ĐÃ HOÀN THÀNH](#2-những-điểm-đã-hoàn-thành)
3. [Rà soát CHUYÊN SÂU THUẬT TOÁN: 12 Lỗi & Khiếm khuyết Cốt lõi (`A1–A12`)](#3-rà-soát-chuyên-sâu-thuật-toán-12-lỗi--khiếm-khuyết-cốt-lõi-a1a12)
4. [Những điểm CHƯA HOÀN THÀNH so với `Presentation2.pdf` & `Proposal_Report.pdf`](#4-những-điểm-chưa-hoàn-thành-so-với-presentation2pdf--proposal_reportpdf)
5. [Những điểm ĐANG LÀM SAI / LỆCH THIẾT KẾ / STUB / HARDCODE](#5-những-điểm-đang-làm-sai--lệch-thiết-kế--stub--hardcode)
6. [Những điểm DƯ THỪA, TRÙNG LẶP & Cảnh báo xung đột nhánh `origin/hmanh`](#6-những-điểm-dư-thừa-trùng-lặp--cảnh-báo-xung-đột-nhánh-originmanh)
7. [Chỉ dẫn & Lộ trình đồng bộ từng bước trên nhánh `ltbinh/sync-proposal`](#7-chỉ-dẫn--lộ-trình-đồng-bộ-từng-bước-trên-nhánh-ltbinhsync-proposal)

---

## 1. Tổng quan trạng thái Repository, Git & Kết quả kiểm thử hiện tại

### 1.1. Trạng thái Git

* **Nhánh gốc:** `main` tại commit `4c0a85a` (đồng bộ với `origin/main`).
* **Nhánh đồng bộ mới:** `ltbinh/sync-proposal` (vừa tạo bằng `git checkout -b ltbinh/sync-proposal` từ `main`).
* **File chưa commit trước khi đồng bộ:** `Proposal/Presentation2.pdf` (18 trang, hiện ở trạng thái untracked) và file hướng dẫn này `Proposal/Sync_Audit_And_Fix_Guide.md`.
* **Các nhánh khác đang tồn tại:** `dminh`, `feature/estimate-buffer`, `hmanh`, `verification_tests_ver1`, `remotes/origin/hmanh` (`5d8a30d`).
* **Cảnh báo nhánh `origin/hmanh` (`5d8a30d`):** `git diff --stat main origin/hmanh` thay đổi **47 files (`+3006 / -2530`)**. Nhánh này có thêm Feature 002 (`src/overload_triage.py`, tests, real `/api/overload/preview`, preview/undo UI) **nhưng đã XÓA** `src/estimate_buffer.py`, `test_estimate_buffer.py`, `web/Log.md`, `student_mode_ui.md`, `feature_001_estimate_buffer.md`, `giao_dien_sinh_vien.md`, `tinh_nang_dem_thoi_gian.md` (xem chi tiết cách xử lý ở Mục 6.4).

### 1.2. Kết quả chạy thực tế các bộ kiểm thử trên `main` (`4c0a85a`)

Chạy tại `group03-smartschedule-baseline/`:

| Bộ kiểm thử | Lệnh chạy | Kết quả thực tế | Chi tiết đáng chú ý |
| :--- | :--- | :--- | :--- |
| **Regression Suite (`--pass`)** | `python -B verification_tests/clean_runner.py --pass` | **84 Passed \| 0 Failed** (`4.79s`) | Phase 1 UI: `1+5`; Phase 2 Arch: `2+3+4`; Phase 3 Logical: `4+34+4+3+4`; Phase 4 Benchmark: `3+2+5+7+3` |
| **Gap Audit Suite (`--gaps`)** | `python -B verification_tests/clean_runner.py --gaps` | **1 Passed \| 4 Failed** (`0.73s`) | **PASS (1):** `test_fail_planning_fallacy_buffer_multiplier` (với `estimate_habit="OFTEN"`).<br>**FAIL (4):**<br>1. `test_fail_circadian_energy_matching`<br>2. `test_fail_rest_break_insertion_after_deep_work`<br>3. `test_fail_why_popover_structured_reason_codes`<br>4. `test_fail_overload_habit_skipping_recommendation` |
| **Benchmark Scenarios** | `python benchmark_runner.py` | **T01–T10 `C_hard=0`**, Determinism 3x **PASS** | • Latency T01–T10: `0.33–4.64 ms`<br>• T03: `CAPACITY_SHORTAGE (shortage=90m)`, T06: `CAPACITY_SHORTAGE (shortage=105m)`<br>• T01 (4 solvers): `C_hard=0`, `R_dl=100.0%` (`0.89–8.28 ms`)<br>• T04: `LOCAL_INSERTION` `100.00%` stability (`Moved=2`, `0.93 ms`) vs `FULL_REBUILD` `0.00%` (`Moved=12`, `5.64 ms`)<br>• T05: `90m -> 135m`, `Shifted=3`<br>• Scale `N=10 / 25 / 50`: `3.09 ms` / `7.61 ms` / `13.25 ms` (`PASS` so với ngưỡng `50/200ms`) |

---

## 2. Những điểm ĐÃ HOÀN THÀNH

Tính đến `4c0a85a`, codebase đã hoàn thiện tốt **lớp lõi Baseline V0** và một phần khung giao diện/kiểm thử:

1. **Data Models & Time Grid Discretization (`src/models.py`, `src/utils.py`, `src/grid_manager.py`):**
   * Đã rời rạc hóa tuần chuẩn thành slot 15 phút (`SLOTS_PER_WEEK = 672`), có hằng số horizon tối đa 2 tuần (`MAX_HORIZON_SLOTS = 1344`), hàm làm tròn/chuyển đổi ISO weekday ↔ slot (`utils.py:1-191`).
   * Định nghĩa đầy đủ cấu trúc dữ liệu (`SleepSchedule`, `FixedEvent`, `CommitmentsProfile`, `Task`, `TaskChunk`, `ScheduleBlock`, `OverloadReport`, `ScheduleSummary`, `ScheduleOutput`, `DisruptionEvent`, `RepairChange`, `RepairOutput`).
   * `TimeGridManager` quản lý 4 trạng thái (`STATE_FREE`, `STATE_SLEEP`, `STATE_OCCUPIED`, `STATE_BLOCK`), hỗ trợ khóa lịch ngủ/cố định, kiểm tra đặt chunk (`can_place_chunk`), và giải thích vi phạm (`explain_violation`).
2. **4 Bộ giải lập lịch + Local Repair Engine (`src/solvers/`):**
   * `GreedyEDFSolver` (`greedy_edf.py`), `GreedyLSTSolver` (`greedy_lst.py`), `GreedyWSPTSolver` (`greedy_wspt.py`), `BacktrackingSolver` (`backtracking.py`).
   * `LocalRepairEngine` (`local_repair.py`) chạy ổn định ở kịch bản T04 (`LOCAL_INSERTION` giữ `100.00%` stability, `Moved=2`, `0.93 ms`).
3. **Metrics, Determinism & Controller (`src/metrics.py`, `src/controller.py`):**
   * Đã có `audit_hard_constraint_violations`, `calculate_deadline_satisfaction_rate`, `calculate_schedule_stability`, `calculate_fragmentation_index`, `compute_determinism_hash`.
   * Đã có `SOLVER_REGISTRY`, `verify_determinism`, `compare_algorithms`, `compare_repair_modes`, `validate_manual_move`.
4. **Multi-format Exporter (`src/exporter.py:1-153`):**
   * Đã hỗ trợ xuất đủ 3 định dạng **JSON**, **CSV**, **ICS**.
5. **Khung Web API & 2 Chế độ UI (`web/api.py`, `web/index.html`, `web/app.js`):**
   * Có giao diện Student Mode & Lab/Benchmark Mode, kéo thả block, xem lý do (còn hardcode), Quick Add (JS parser).
6. **Hệ thống Verification & Benchmark (`verification_tests/`, `benchmark_runner.py`):**
   * 84 test regression pass toàn bộ cùng bộ kịch bản `t01`–`t10` làm lưới an toàn khi sửa code.

---

## 3. Rà soát CHUYÊN SÂU THUẬT TOÁN: 12 Lỗi & Khiếm khuyết Cốt lõi (`A1–A12`)

Đây là phần trọng tâm cần ưu tiên xử lý trên nhánh `ltbinh/sync-proposal`. Nhiều lỗi hiện đang **bị che khuất** vì bộ 84 test hiện tại chưa phủ hết biên dữ liệu (edge cases).

---

### Lỗi A1 — `split_task_into_chunks()` có thể tạo chunk vượt quá `max_chunk_min` (vi phạm Pattern 2 & H2)

* **Vị trí:** `group03-smartschedule-baseline/src/solvers/base_solver.py:83-116`
* **Hiện trạng lỗi:**
  ```python
  num_parts = int(math.ceil(total_slots / float(max_slots_per_part)))
  while num_parts > 1 and (total_slots // num_parts) < min_slots_per_part:
      num_parts -= 1
  ```
* **Phản chứng (Counterexample):**
  * Cho task `is_splittable = True`, `planned_min = 105` (`7` slots), `max_chunk_min = 90` (`6` slots), `min_chunk_min = 60` (`4` slots — đúng bằng `min_chunk_min=60` đang dùng trong `data/test_scenarios/t10_cross_week_deadline.json:46`).
  * `num_parts` khởi tạo là `ceil(7 / 6) = 2`.
  * Kiểm tra `7 // 2 = 3 < 4` (`True`) → vòng `while` hạ `num_parts` xuống **`1`**!
  * Kết quả: sinh ra **1 chunk duy nhất dài `105 min > max_chunk_min (90 min)`**, trực tiếp vi phạm **H2** và **Pattern 2 (Deep Work Cap max 90m)**! Tương tự với `120 min` và `min_chunk_min = 75` → trả về 1 chunk `120 min`.
* **Hướng dẫn sửa:**
  1. Không bao giờ hạ `num_parts` nếu phần chia tối đa mới `math.ceil(total_slots / (num_parts - 1))` vượt quá `max_slots_per_part`.
  2. Quy tắc chuẩn hóa kích thước chia ở `BaseSolver.split_task_into_chunks`:
     ```python
     # Bảo vệ bất biến H2: chunk không được vượt max_slots_per_part khi is_splittable=True
     min_possible_parts = int(math.ceil(total_slots / float(max_slots_per_part)))
     if min_slots_per_part > max_slots_per_part:
         # Guard cấu hình mâu thuẫn: ưu tiên giữ trần max_slots_per_part
         effective_min_slots = max_slots_per_part
     else:
         effective_min_slots = min_slots_per_part

     num_parts = min_possible_parts
     # Chỉ hạ num_parts nếu vẫn đảm bảo không chunk nào vượt max_slots_per_part
     while num_parts > 1 and (total_slots // num_parts) < effective_min_slots:
         next_parts = num_parts - 1
         next_max_chunk = (total_slots + next_parts - 1) // next_parts
         if next_max_chunk > max_slots_per_part:
             break
         num_parts = next_parts
     ```
  3. Trường hợp còn lại (vd `105 min` chia 2 thành `60m + 45m` khi `min_chunk=60`): chấp nhận phần đuôi `< min_chunk` **hoặc** bổ sung chiến lược kiểm tra trước khi chia để giữ H2 (`<= 90m`) làm ràng buộc cứng cao hơn `min_chunk` mềm (kèm `reason_code` cảnh báo nếu phần cuối ngắn hơn `min_chunk`), thay vì âm thầm phình vượt `max_chunk_min`.

---

### Lỗi A2 — `GreedyWSPTSolver.wspt_sort_key()` lỗi truthiness `deadline_slot == 0` & thiếu mã chẩn đoán

* **Vị trí:** `group03-smartschedule-baseline/src/solvers/greedy_wspt.py:56,128,134-154`
* **Hiện trạng lỗi:**
  1. Dòng 56 viết: `d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso) or 999999`. Nếu task có deadline đúng `00:00 Thứ Hai` (`d_slot == 0`), toán tử `or` coi `0` là `False` và biến nó thành `999999` (bị coi là **không có deadline**!), trái với 3 solver còn lại (`greedy_edf.py:66`, `greedy_lst.py:64`, `backtracking.py:70`) đều kiểm tra tường minh `if d_slot is None:`.
  2. Dòng `128` và `134–154`: thiếu thêm mã `AFTER_PREREQ` vào `reason_codes` khi task có tiên quyết, và thiếu phân biệt nguyên nhân thất bại giữa **Capacity Shortage** vs **Fragmentation** trong `fail_reason` như các solver khác.
* **Hướng dẫn sửa:**
  * Sửa dòng 56 thành:
    ```python
    raw_d = t.resolve_deadline_slot(week_start_iso=week_start_iso)
    d_slot = raw_d if raw_d is not None else 999999
    ```
  * Đồng bộ logic sinh `reason_codes` (`AFTER_PREREQ`, buffer, circadian...) và phân biệt `fail_reason` (`CAPACITY_SHORTAGE` vs `FRAGMENTATION`) qua helper dùng chung ở `BaseSolver`.

---

### Lỗi A3 — `GreedyLSTSolver` tính slack tĩnh, bỏ qua `depends_on` & dung lượng rảnh thực tế

* **Vị trí:** `group03-smartschedule-baseline/src/solvers/greedy_lst.py:61-67`
* **Hiện trạng lỗi:**
  * Công thức hiện tại: `slack_slots = d_slot - now_slot - t.get_planned_slots()`.
  * Có 2 khiếm khuyết:
    1. **Bỏ qua `depends_on`:** Nếu `Task B` phụ thuộc `Task A` (dài `180m = 12 slots`) và cùng xuất phát từ `now_slot`, thời điểm bắt đầu sớm nhất thực tế của `B` là `now_slot + 12`, không phải `now_slot`. Tính slack tĩnh làm `B` bị đánh giá thừa độ rảnh so với thực tế.
    2. **Sắp xếp tĩnh một lần (Static Sort):** Không tính lại lượng **slot thực sự còn trống (`FREE`)** trong khoảng `[earliest_start, d_slot]` sau khi các task ưu tiên trước đã chiếm lưới và trừ đi giờ ngủ/lịch cố định.
* **Hướng dẫn sửa:**
  * Tính `effective_earliest_start(t)`: quy hoạch động trên DAG topo = `max(now_slot, earliest_start(p) + planned_slots(p) với mọi p in t.depends_on)`.
  * Nâng cấp LST từ static sort sang **vòng lặp chọn động (Dynamic LST)** cho mỗi bước trong danh sách ứng viên đã thỏa điều kiện tiên quyết:
    * `available_free_slots = grid.count_free_slots(earliest_t, d_slot)` (hoặc ước lượng nhanh khoảng trống chưa bị chiếm từ `max(now_slot, max_prereq_end)` đến `d_slot`).
    * `dynamic_slack = available_free_slots - t.get_planned_slots()`.
    * Với quy mô `N <= 50`, độ phức tạp chỉ `O(N^2)` nên độ trễ vẫn ở mức vài mili-giây (< 20ms).

---

### Lỗi A4 — Chuỗi 4 lỗi nghiêm trọng về `pinned_blocks` lặp lại trên TẤT CẢ 4 solvers

* **Vị trí:**
  * `greedy_edf.py:45-58, 109-227`
  * `greedy_lst.py:43-57, 112-228`
  * `greedy_wspt.py:37-49, 96-190`
  * `backtracking.py:50-62, 117-121`
  * `base_solver.py:201-203, 360`
* **Hiện trạng lỗi (4 vấn đề cùng lúc):**
  1. **Đếm trùng dung lượng (Double-counting Capacity):** Cả 4 solver khóa `pinned_blocks` lên `grid` **trước**, sau đó gọi `self.check_deadline_capacity(...)`. Nhưng `check_deadline_capacity()` (`base_solver.py:201-203`) lại cộng toàn bộ `t.get_planned_duration_min()` của task (chưa trừ thời lượng các chunk đã `PINNED`) đem so với phần slot rảnh *còn lại* trên `grid`! Điều này khiến solver trừ 2 lần phần thời lượng đã pin và có thể báo lỗi `CAPACITY_SHORTAGE` giả.
  2. **Rollback nửa chừng gây mâu thuẫn trạng thái:** Nếu Task có Chunk 1 là `PINNED` và Chunk 2 không đặt được (`task_failed = True`), đoạn rollback (`for tb in task_temp_blocks: grid.remove_block(...)`) chỉ gỡ các `temp_blocks`, **để nguyên `PINNED` chunk nằm trên `grid` và `placed_blocks`**, trong khi `base_solver.py:360` vẫn đưa `task_id` vào `unplaced_tasks`! Kết quả: task vừa mang danh `UNPLACED`, vừa có một phần block chiếm chỗ vĩnh viễn trên lưới.
  3. **Đặt chunk sai thứ tự thời gian (Out-of-order Chunks):** Khi Chunk 2 đã là `PINNED` và Chunk 1 chưa được pin, vòng lặp `for chunk in chunks` không chặn cận trên `max_end <= pinned_chunk_2.start_slot` cho Chunk 1 → Chunk 1 có thể bị xếp **sau** Chunk 2!
  4. **Thiếu kiểm tra H4 & `now_slot` cho `pinned_blocks`:** Khi khóa `pinned_blocks`, solver chỉ gọi `is_range_free()`, hoàn toàn bỏ qua kiểm tra **H4** (`pb.end_slot <= deadline_slot`) và ranh giới `pb.start_slot >= now_slot` (hoặc thứ tự đối với các prerequisite đã pin).
* **Hướng dẫn sửa (Tránh lặp code theo nguyên tắc gom helper vào `BaseSolver`):**
  1. Gom toàn bộ tiền xử lý `pinned_blocks` vào 1 phương thức chung ở `BaseSolver` (vd: `prepare_pinned_blocks(grid, tasks, pinned_blocks, now_slot, week_start_iso)`):
     * Kiểm tra với mỗi `pb`: khoảng slot phải rảnh (`H1/H3`), thỏa `pb.end_slot <= deadline_slot` (`H4`), và xác định xem block đó hợp lệ để giữ cố định.
     * Tính `pinned_slots_by_task[task_id]` và `pinned_chunk_slots[(task_id, chunk_index)]`.
  2. Cập nhật `check_deadline_capacity()` (`base_solver.py:201-203`): trừ `pinned_slots_by_task.get(t.id, 0)` khỏi nhu cầu `remaining_slots_needed` trước khi so với số slot `FREE` còn lại.
  3. Khi đặt danh sách `chunks` cho một task:
     * Tính sẵn ràng buộc thứ tự: với `chunk[i]`, `min_start` là `max(effective_earliest, prev_chunk_end)` và `max_end` là `min(deadline_slot, next_pinned_chunk_start - gap_between_chunks)`.
     * Nếu 1 chunk sau thất bại **nhưng** task đã có chunk `PINNED`: không đẩy nửa vời; nếu chính sách là *giữ chunk đã pin và báo thiếu phần còn lại* hay *không cho pin block mồ côi*, phải quy ước rõ **hoặc** từ chối các task còn phần unplaced ra khỏi `placed_blocks` một cách nhất quán (tốt nhất: ghi nhận rõ `pinned_slots` đã tiêu thụ và chỉ rollout đúng các `temp_blocks`, chỉ mark `PARTIAL` hoặc tách clearly thay vì vừa giữ `placed_blocks` vừa liệt kê toàn bộ `task_id` vào `unplaced_tasks` không giải thích).

---

### Lỗi A5 — `BacktrackingSolver` không thực sự tối ưu & có thể bỏ sót nghiệm hợp lệ

* **Vị trí:** `group03-smartschedule-baseline/src/solvers/backtracking.py:107, 130-142, 226`
* **Hiện trạng lỗi:**
  1. `generate_candidate_slots_for_task()` giới hạn cứng `max_candidates_per_task = 6` và **chỉ lấy mép trái `cand_s = iv_start`** của từng khoảng rảnh liên tiếp. Nếu một khoảng rảnh dài ở giữa có điểm nghẽn năng lượng (Circadian) hoặc có task khác cần nhường mép trái/căn chỉnh cạnh, solver không bao giờ thử các điểm dịch bên trong khoảng rảnh đó.
  2. Dòng `226`: `if best_score[0] == num_tasks and self.nodes_explored > 500: return` — ngay khi tìm được **bất kỳ** phương án nào xếp đủ `num_tasks` và số node vượt `500`, thuật toán lập tức thoát khỏi nhánh tìm kiếm mà **không tối ưu tiếp** các tiêu chí bậc dưới (priority, `sum_end_slots`, Circadian energy match, category batching).
* **Hướng dẫn sửa:**
  1. Thay đổi sinh ứng viên: vẫn ưu tiên `iv_start`, nhưng với mỗi khoảng rảnh lớn hơn kích thước chunk, bổ sung thêm các điểm ứng viên đại diện (vd: đầu khoảng rảnh, vị trí bắt đầu vùng Peak Energy phù hợp với `cognitive_load`, vị trí liền kề block cùng category để tăng `neighbour_score`, và cuối khoảng rảnh trước deadline) với giới hạn linh hoạt (`max_candidates_per_task` cấu hình được, vd 12–16).
  2. Dòng `226`: tách rõ trạng thái **đặt đủ 100% task** với **ngân sách tối ưu hóa (`max_nodes` / timeout)**: không `return` sớm chỉ vì `nodes_explored > 500` khi vẫn còn nhánh cải thiện hàm mục tiêu (hoặc giữ `upper_bound` pruning / Branch & Bound theo tổng trọng số mục tiêu + giới hạn node trần cao hơn, vd `max_nodes = 5000`, để đảm bảo tính xác định `Determinism` mà không cắt ngang nghiệm tốt hơn).

---

### Lỗi A6 — `LocalRepairEngine` thiếu 5 cơ chế cốt lõi của Proposal §6.6 & §7

* **Vị trí:** `group03-smartschedule-baseline/src/solvers/local_repair.py:132-135, 246-272, 296-374, 408, 470-605, 661-672`
* **Hiện trạng lỗi (5 lỗi/thiếu sót gộp trong 1 module):**
  1. **Không bảo vệ `PINNED` ở chế độ Local Insertion (L132–135):** `_repair_local_insertion` đưa cả block có `state == "PINNED"` bị `disruption` đè vào `affected_blocks` rồi dời đi (trong khi `_repair_full_rebuild` ở L408 có lọc `b.state == "PINNED"`). Cũng không phát cảnh báo khi disruption va chạm vào block người dùng đã ghim cứng.
  2. **Thiếu Step 4 Progressive Unfreezing (L246–272):** Theo `Proposal_Report.pdf` §6.6 Step 4, khi một block bị ảnh hưởng không nhét vừa khoảng trống còn lại, hệ thống phải **"unfreeze not-yet-started blocks of lowest-score task, one task at a time"** (tháo băng từng task điểm thấp nhất ở vùng tương lai để nhường chỗ) rồi mới đẩy phần bất khả thi sang Overload. Code hiện tại bỏ qua hoàn toàn bước này và đánh dấu `UNPLACED` ngay!
  3. **Sửa phụ thuộc sau khi dời không theo thứ tự Topo & làm sai log (L296–374):** `_enforce_post_move_dependencies` duyệt `for t in tasks:` theo thứ tự đầu vào tùy ý. Nếu có chuỗi `A -> B -> C` mà `C` đứng trước `B` trong list: sửa `B` xong mới làm `C` bị vi phạm H5 mà không quay lại sửa `C`! Ngoài ra, một block bị dời 2 lần tạo ra **2 bản ghi `RepairChange` trùng**, và hàm tìm chỗ đặt mới chỉ quét **first-fit** thay vì tìm slot hợp lệ **gần vị trí gốc nhất** (làm giảm Stability).
  4. **`_repair_ripple_shift` bỏ qua `now_slot` và không kiểm tra H5 (L470–605):** Có thể đẩy block về vùng quá khứ (`< now_slot`) nếu tính toán trượt bị âm/lệch và **hoàn toàn không gọi `_enforce_post_move_dependencies`**.
  5. **Không xuất `OverloadReport` khi quá tải cục bộ (L661–672):** `_build_repair_output` gán cứng `overload_reports=[]` và `overload=None` ngay cả khi `status == "PARTIAL_OVERLOAD"`, làm Step 5 / Crunch Mode không có dữ liệu để xử lý.
* **Hướng dẫn sửa:**
  1. **Pin Guard:** Trong `_repair_local_insertion`, tách riêng các `PINNED` blocks: không tự ý dời; chỉ dời khi người dùng xác nhận override, hoặc nếu bất khả kháng do `Fixed/Disruption` chồng cứng thì ghi rõ `pin_conflict_warnings` / loại bỏ hoặc báo conflict tường minh.
  2. **Topo Sort trong `_enforce_post_move_dependencies`:** Duyệt `tasks` theo thứ tự topo thực sự (dùng helper `enforce_dependency_order()` đã sửa không cycle). Theo dõi vị trí ban đầu `original_slot[block_id]` để cuối hàm chỉ ghi nhận đúng **1** `RepairChange` thực từ vị trí gốc → vị trí cuối, và chọn slot bằng chiến lược **nearest valid slot** (`min(abs(cand - orig_start))`) thỏa `>= now_slot` và `>= max_prereq_end`.
  3. **Progressive Unfreezing (§6.6 Step 4):** Khi một block ưu tiên cao bị kẹt không đặt được ở Bước 3, lọc các block chưa diễn ra (`start_slot >= now_slot`, không `PINNED`) của các task còn lại theo thứ tự **điểm ưu tiên tăng dần**; lần lượt gỡ 1 task, thử đặt lại block bị kẹt + re-insert task vừa gỡ; dừng ngay khi đặt được hoặc khi không còn ứng viên điểm thấp hơn → chuyển phần còn thiếu sang Step 5.
  4. **Ripple Shift an toàn:** Truyền và ép `start_slot >= now_slot` trong `_repair_ripple_shift`, sau đó bắt buộc gọi `_enforce_post_move_dependencies`.
  5. **Tích hợp Step 5 vào `_build_repair_output`:** Khi có `unplaced` / `PARTIAL_OVERLOAD`, tạo đầy đủ `OverloadReport` (tính `shortage_minutes`, gợi ý dời hạn / tách nhỏ / bỏ qua thói quen).

---

### Lỗi A7 — Xử lý `depends_on` vòng lặp (Cycle) & ID không tồn tại tạo lịch hỏng H5

* **Vị trí:**
  * `group03-smartschedule-baseline/src/solvers/base_solver.py:142-172`
  * `group03-smartschedule-baseline/src/solvers/greedy_edf.py:84-101`
  * `group03-smartschedule-baseline/src/metrics.py:80-96`
  * `group03-smartschedule-baseline/verification_tests/logical_tests/test_circular_dependencies.py:72-74`
* **Hiện trạng lỗi:**
  * Khi có chu trình `A -> B -> A` hoặc tự phụ thuộc `A -> A`, hàm `visit()` trong `enforce_dependency_order()` chỉ gặp `# Cycle detected` rồi âm thầm thoát đệ quy.
  * Solver vẫn xếp cả `A` và `B` vào lịch theo một thứ tự tùy ý.
  * Kết quả: `metrics.py:92-96` phát hiện `A` hoặc `B` đặt sai ràng buộc tiên quyết và chấm **`hard_constraint_violations >= 1` (vi phạm H5)**! Lý do test không phát hiện là `test_circular_dependencies.py:72-74` chỉ assert `out is not None` mà **không assert `hard_constraint_violations == 0`**!
  * Lỗi tương tự xảy ra nếu `depends_on` chứa một `task_id` không tồn tại: solver bỏ qua khi đặt lịch nhưng `metrics.py:85-89` lại tính là vi phạm H5.
* **Hướng dẫn sửa:**
  1. Nâng cấp `enforce_dependency_order()` ở `BaseSolver` để trả về cả `(ordered_tasks, invalid_dep_tasks)` trong đó phân loại rõ:
     * `CIRCULAR_DEPENDENCY` cho mọi task nằm trong chu trình hoặc phụ thuộc xuôi dòng vào chu trình.
     * `MISSING_PREREQUISITE` cho mọi task trỏ tới `dep_id` không có trong tập task đầu vào.
  2. Không xếp lịch cho các task trong `invalid_dep_tasks`; đưa thẳng vào `unplaced_tasks` kèm `fail_reason` và `reason_codes` tường minh.
  3. Cập nhật `audit_hard_constraint_violations()` (`metrics.py:80-96`) đồng nhất quy ước: nếu một task không được xếp (`unplaced`) do `CIRCULAR_DEPENDENCY` / `MISSING_PREREQUISITE` thì **chấp nhận không đặt lên lưới** (`C_hard = 0` trên lịch đã xếp, thay vì sinh ra vi phạm chồng chéo/đặt ngược). Đồng thời siết `test_circular_dependencies.py` phải kiểm tra `C_hard == 0` và `unplaced_tasks` ghi đúng lý do.

---

### Lỗi A8 — Chân trời lập lịch bị khóa 1 tuần (`T10`) & chưa chặn giờ ngủ `< 6h` (Pattern 6)

* **Vị trí:**
  * `group03-smartschedule-baseline/src/solvers/base_solver.py:175-204`
  * `group03-smartschedule-baseline/src/solvers/greedy_edf.py:39, 124`
  * `group03-smartschedule-baseline/src/grid_manager.py:75-93`
  * `group03-smartschedule-baseline/src/utils.py:16`
* **Hiện trạng lỗi:**
  1. `utils.py:16` đã định nghĩa `MAX_HORIZON_SLOTS = 1344` (2 tuần), và `Proposal_Report.pdf` §5.5 thiết kế mở rộng grid sang tuần sau khi có deadline cross-week (hiện tại `t10_cross_week_deadline.json` cần cơ chế này; chỉ render UI tuần hiện tại). Tuy nhiên các solver & `check_deadline_capacity()` hiện đang kẹp ở `SLOTS_PER_WEEK = 672`, không khai thác dải `672..1343`.
  2. `TimeGridManager.lock_sleep_schedule()` (`grid_manager.py:75-93`): nếu `start_offset == end_offset` (khóa `0` slot) hoặc thời lượng ngủ `< 6h` (`< 24` slots), hàm lặng lẽ cho qua mà **không kiểm tra Pattern 6 (Biological Sleep Recovery: bắt buộc tối thiểu `>= 6h` mỗi đêm)**.
* **Hướng dẫn sửa:**
  1. Cho phép `TimeGridManager` và `BaseSolver` mở rộng `horizon_slots = MAX_HORIZON_SLOTS` (`1344`) tự động khi có task mang deadline vượt tuần (`> 672` hoặc tuần kế tiếp), khóa cả `sleep_schedule` và `fixed_events` lặp lại cho tuần 2 (`slots 672..1343`), đồng thời tách riêng `display_horizon_slots = 672` khi tổng hợp UI.
  2. Trong `TimeGridManager.lock_sleep_schedule()`: kiểm tra số slot ngủ mỗi đêm `sleep_slots_per_night >= 24` (`6h`). Nếu `sleep_slots_per_night < 24` (hoặc `start == end`), ném `ValueError` / chuẩn hóa tối thiểu 6h kèm cảnh báo rõ (chú ý kiểm tra các fixture test hiện có để không có test cố tình truyền 0h ngủ trước khi siết cứng, hoặc chỉ nâng chuẩn/cảnh báo nếu fixture lab cần).

---

### Lỗi A9 — `handle_task_overrun()` dùng Full Rebuild phá vỡ Stability (Pattern 8)

* **Vị trí:** `group03-smartschedule-baseline/src/controller.py:268-319`
* **Hiện trạng lỗi:**
  * Khi task chạy lố giờ (overrun), `handle_task_overrun()` xóa lịch và gọi lại `solve_schedule()` (`FULL_REBUILD`), làm xáo trộn toàn bộ các block còn lại trong tuần, đi ngược **Pattern 8 (Schedule Churn Aversion: giữ `>= 90%` stability)** và **§7.3 Route `Progress/duration change -> M4 -> M3`**.
* **Hướng dẫn sửa:**
  * Chuyển `handle_task_overrun()` sang dùng `LocalRepairEngine` (`LOCAL_INSERTION` với Progressive Unfreezing):
    1. Giữ nguyên toàn bộ block đã hoàn thành / đang diễn ra trước `now_slot`.
    2. Cập nhật phần thời lượng bổ sung của task bị overrun (làm block mở rộng / phần dư từ `now_slot`).
    3. Đóng băng mọi block tương lai không xung đột; chỉ đưa các block bị phần mở rộng chèn trúng vào `affected_blocks` và gọi `LocalRepairEngine` để sửa cục bộ, đảm bảo stability `>= 90%`.

---

### Lỗi A10 — Mặc định `is_splittable = False` mâu thuẫn với Step 2 (`Slide 16`)

* **Vị trí:** `group03-smartschedule-baseline/src/models.py:107`
* **Hiện trạng lỗi:** `Task.is_splittable` mặc định `False`. Nếu task dài `> 90 phút` mà người dùng không truyền cờ `is_splittable`, hệ thống không tự tách thành khối `45–90 phút` như `Slide 16` Step 2 yêu cầu.
* **Hướng dẫn sửa:** Trong `normalize_task_input()`, nếu payload **không** truyền `is_splittable`/`splittable` tường minh và `duration_min > max_chunk_min`, tự động bật `is_splittable = True`, đồng thời vẫn tôn trọng tuyệt đối nếu người dùng chủ đích truyền `is_splittable = False` (các test atomic như `T03-UNSPLITTABLE`, `T_ATOMIC_150` không bị ảnh hưởng).

---

### Lỗi A11 — Bỏ qua khóa ngủ khi `is_hard_lock=False` & `FixedEvent` lỗi với ca qua đêm

* **Vị trí:** `group03-smartschedule-baseline/src/grid_manager.py:58, 100-121`
* **Hiện trạng lỗi:**
  1. Dòng 58 chỉ khóa `SLEEP` nếu `profile.sleep_schedule.is_hard_lock == True`, tạo khe hở phá **Pattern 6** (`>= 6h` ngủ bảo vệ cứng mỗi đêm).
  2. Dòng 102 `if end_offset <= start_offset: raise ValueError(...)` chặn lịch cố định vắt qua nửa đêm (vd ca làm đêm `22:00–02:00`), trong khi `lock_sleep_schedule()` đã xử lý được trường hợp qua đêm.
* **Hướng dẫn sửa:** Luôn khóa lịch ngủ tối thiểu `>= 6h` (`24` slots) ở `TimeGridManager` (và cảnh báo/chuẩn hóa nếu nhập `< 6h`), đồng thời hỗ trợ `FixedEvent` qua đêm tương tự `lock_sleep_schedule()` bằng cách cắt sang nửa đầu ngày kế tiếp.

---

### Lỗi A12 — `iso_to_slot()` kẹp deadline quá khứ thành Thứ Hai `00:00`

* **Vị trí:** `group03-smartschedule-baseline/src/utils.py:139-151`
* **Hiện trạng lỗi:** `return max(0, min(MAX_HORIZON_SLOTS, slot))` khiến deadline ISO nằm trong quá khứ (`< week_start_iso`) bị ép về `slot = 0` (`Monday 00:00`) thay vì báo trạng thái quá hạn (`OVERDUE`).
* **Hướng dẫn sửa:** Tách helper `iso_to_slot_with_status()` trả về `(clamped_slot, is_past_due, beyond_horizon)` để solver nhận diện ngay task quá hạn trước khi đặt lịch thay vì lặng lẽ coi là hạn Thứ Hai `00:00`.

---

## 4. Những điểm CHƯA HOÀN THÀNH so với `Presentation2.pdf` & `Proposal_Report.pdf`

Bảng đối chiếu **8 Behavioral Patterns** (theo `Presentation2.pdf`, `Slide 6–17`, và `Proposal_Report.pdf` §4.5, §6–7) + Các tính năng mở rộng:

| Hạng mục thiết kế (`Presentation2` / `Proposal`) | Yêu cầu thiết kế chuẩn | Trạng thái hiện có trên `main` (`4c0a85a`) | Gap kiểm thử & File liên quan |
| :--- | :--- | :--- | :--- |
| **Mô hình Grid & 3 Formats (`Slide 6, 13, 14`)** | Grid 4 trạng thái (`FREE`, `OCCUPIED`, `SLEEP`, **`REST`**); 3 Formats (**`Personal Habits (intervals, weights)`**, `Fixed Commitments`, `Dynamic Tasks`); **`CircadianEnergyProfile`** | **THIẾU MODEL & STATE:** `TimeGridManager` chưa có `STATE_REST`; chưa có schema `PersonalHabit` & `CircadianEnergyProfile` độc lập | Cần bổ sung vào `src/models.py` & `src/grid_manager.py` |
| **M1: NL Parser (LLM) (`Slide 10`)** | Phân tích câu tự nhiên thành `Task` chuẩn qua LLM (+ fallback) | **STUB CHẾT + TRÙNG JS:** `web/api.py:416-459` là regex hardcode Thứ Tư không dùng tới; UI chạy JS `parseQuickAdd` riêng | Cần hợp nhất về 1 M1 Hybrid Parser (LLM optional + Backend deterministic parser) |
| **Pattern 1: Planning Fallacy (`Slide 7, 17`)** | `Planned_Duration = RoundUp_15(Estimated_Duration × α)` (`α_light=1.20`, `α_heavy=1.35`); **`1D Grid Search`** `α ∈ [1.00, 1.60]` step `0.05` + **`Stress Test (+25%, +50%)`** + log **`Actual / Estimated`** | **LỆCH & THIẾU CALIBRATION:** `estimate_buffer.py` dùng `estimate_habit` (`1.0/1.1/1.25`), `app.js:1749-1752` nhân đôi `1.2`; **chưa có 1D Grid Search & Stress Test & actual log** | Pass 1 test giả (`OFTEN`) trong `--gaps`; cần giữ Feature 001 test + thêm chế độ load `α` & script Grid Search |
| **Pattern 2: Cognitive Fatigue (`Slide 7, 16`)** | Trần deep work `max 90 phút` + tự động chèn **`15 phút REST`** sau phiên deep work; auto tách task `> 90m` | **CHƯA ĐẠT + BUG A1, A10:** Chưa chèn `15-min REST`; Lỗi A1 cho chunk vượt `90p` (`105m`); A10 mặc định `is_splittable=False` | `test_fail_rest_break_insertion_after_deep_work` **FAIL** |
| **Pattern 3: Circadian Energy (`Slide 7, 9, 14`)** | Khớp `energy_level (1–3)` / `focus_preference`: Load-3 → Peak Energy (Level-3); Load-1 → Low-Energy (mức mềm/2-tầng còn chờ nhóm chốt) | **CHƯA ĐẠT:** Chưa có `CircadianEnergyProfile` & chấm điểm Circadian | `test_fail_circadian_energy_matching` **FAIL**; `t09` chưa thể hiện khác biệt |
| **Pattern 4: Context Switching (`Slide 7`)** | Gom nhóm task cùng category (`Category Batching`) và phạt chuyển ngữ cảnh (`neighbour_score`) | **CHƯA CÓ:** Chưa có trọng số/hàm tính `neighbour_score` | Cần tích hợp vào `SCORED_GREEDY` & `BacktrackingSolver` |
| **Pattern 5: Fragmented Dead-Zones (`Slide 8, 16`)** | Tiền đánh dấu khe hở `< 30 phút` thành **`STATE_REST`** (`Active Rest`); cấm đặt deep focus vào dead-zone | **CHƯA CÓ:** Chưa có pass tiền đánh dấu `< 30p` thành `STATE_REST` ở Step 1 solver (cần giữ nguyên `test_minh_week_exact_672_slot_accounting`) | Cần thêm helper ở `TimeGridManager` gọi trong `solve()` |
| **Pattern 6: Biological Sleep Recovery (`Slide 8, 16`)** | Khóa cứng tối thiểu **`>= 6h`** (`24 slots`) ngủ mỗi đêm | **THIẾU VALIDATION (A8, A11):** `lock_sleep_schedule()` cho phép `< 6h` và bị bỏ qua nếu `is_hard_lock=False` | Cần siết cứng trong `src/grid_manager.py` |
| **Pattern 7: Hyperbolic Urgency (`Slide 8, 16`)** | `Urgency = exp(-slack / γ) × Importance` (`γ` chưa chốt, mặc định `24h`), xếp cao điểm sớm nhất | **CHƯA CÓ (STUB ALIAS):** `SCORED_GREEDY` tại `controller.py:35` chỉ trỏ bí danh sang `GreedyEDFSolver` | Cần viết `ScoredGreedySolver` thực thụ |
| **Pattern 8: Schedule Churn Aversion (`Slide 5, 8, 16`)** | Đóng băng block an toàn, dời task bị ảnh hưởng, giữ stability **`>= X%`** (`90%`) | **ĐẠT MỘT PHẦN:** T04 đạt `100%`, nhưng còn lỗi **A6** (`LocalRepair`) và **A9** (`handle_task_overrun` dùng Full Rebuild) | Cần vá A6 + A9 |
| **Experience Rating (`Slide 6`)** | Hàm mục tiêu tính mức độ mệt mỏi của lịch theo thang **`1–5 (Comfortable → Exhausting)`** | **CHƯA CÓ:** Hoàn toàn chưa tính chỉ số này trong `ScheduleSummary` | Cần thiết kế công thức tổng hợp đưa vào `ScheduleSummary` + UI |
| **Step 5: Two-Tier Crunch & Overload (`Slide 10, 16`)** | Tier 1 Sprint (**Cut breaks**, nới mềm); Tier 2 Task Triage (gợi ý bỏ thói quen/hoãn/rút ngắn); báo missing minutes + **Early Extension Alert (24–48h)** | **CHƯA HOÀN THIỆN:** `main` mới có `OverloadReport` cơ bản & stub; cần port `overload_triage.py` từ `origin/hmanh` + bổ sung Cut breaks & Early Extension Alert | `test_fail_overload_habit_skipping_recommendation` **FAIL** |
| **Explainability & Student UI (`Slide 5, 6`)** | Why Popover trả mảng `reasons[]` chuẩn (`ENERGY_MATCH`, `BREAK_AFTER`, `ESTIMATE_BUFFER`...); Student UI đủ Settings, M5 Disruption, M6 Overload Triage, M7 Check-in & log thời lượng thực | **CHƯA ĐẠT:** Frontend `app.js:1839-1845` hardcode chữ tĩnh; thiếu settings/M5/M6/M7; `doneBlocks` mất khi F5 | `test_fail_why_popover_structured_reason_codes` **FAIL** |

---

## 5. Những điểm ĐANG LÀM SAI / LỆCH THIẾT KẾ / STUB / HARDCODE

1. **Sai công thức & nhân đôi Buffer (Planning Fallacy Double-Buffering):**
   * `src/estimate_buffer.py` dùng `estimate_habit` (`RARELY=1.0`, `SOMETIMES=1.1`, `OFTEN=1.25`, mặc định `None=1.0`) và làm tròn gần nhất thay vì `RoundUp_15(duration * α)` với `α_light=1.20 / α_heavy=1.35` như `Presentation2.pdf` & `Proposal_Report.pdf` §4.5.
   * Đồng thời, `saveStudentTask()` tại `web/app.js:1749-1752` lại tự động tính `Math.ceil(Math.ceil(rawDur * 1.2) / 15) * 15` ở phía trình duyệt. Khi `state.commitments` có `estimate_habit` là `SOMETIMES` hoặc `OFTEN`, task sẽ bị **nhân buffer 2 lần liên tiếp**.
2. **`SCORED_GREEDY` chỉ là bí danh giả (`controller.py:35`):**
   * `SOLVER_REGISTRY["SCORED_GREEDY"]` đang trỏ thẳng vào `GreedyEDFSolver` chứ chưa có thuật toán chấm điểm tổ hợp (Pattern 3 + 4 + 7).
3. **API Stubs trong `web/api.py`:**
   * `/api/tasks/natural-add` (`web/api.py:416-459`): dùng regex thô, gán cứng hạn chót `Wednesday 23:59` và `is_splittable=True`, hiện **không được UI gọi**.
   * `/api/overload/preview` (`web/api.py:462-491`): trả bản copy giả có `state="PROPOSED"`, hiện **không được UI gọi**.
   * `/api/validate-move`: đã có endpoint ở backend nhưng UI kéo-thả chưa gọi để kiểm chứng ràng buộc cứng qua backend chuẩn.
4. **Hardcode hiển thị trong Frontend (`web/app.js` & `web/index.html`):**
   * `openWhyHereModal()` (`web/app.js:1839-1845`): luôn in chuỗi tĩnh `"Earliest Deadline First (EDF)"` và `"(23:30–06:30)"` bất kể người dùng chọn solver nào hay đổi giờ ngủ nào.
   * `web/index.html:205, 257-349`: hardcode tuần hiển thị `"2 Thg 11 – 8 Thg 11, 2026"` và khung giờ ngủ `"23:30–06:30"`.
5. **Lỗi chính tả dữ liệu kiểm thử:**
   * `data/test_scenarios/t07_incomplete_metadata.json:49`: viết nhầm field thành `"grep_weight": "30+"` (nhiều khả năng ý định là `"grade_weight"`).

---

## 6. Những điểm DƯ THỪA, TRÙNG LẶP & Cảnh báo xung đột nhánh `origin/hmanh`

1. **File rác trong thư mục mã nguồn:**
   * `group03-smartschedule-baseline/web/Log.md`: chứa 357 dòng paste log PowerShell terminal, không phải tài liệu dự án → cần xóa.
2. **Trùng lặp logic NLP Quick-Add:**
   * Tồn tại song song 2 bộ phân tích câu tự nhiên rời rạc: `parseQuickAdd()` viết bằng JS trong `web/app.js` (đang chạy ở UI) và regex stub `/api/tasks/natural-add` trong `web/api.py:416-459` (chết). Nên hợp nhất về 1 luồng chuẩn (Backend parse → Frontend chỉ gọi API, hoặc bỏ hẳn stub Python nếu chỉ dùng JS rồi chuẩn hóa JSON gửi lên).
3. **Tài liệu lỗi thời & trùng lặp cấu trúc (`README.md`, `docs/`, `agents/`):**
   * `README.md`, `group03-smartschedule-baseline/README.md`, `docs/commit_changes.md`, và `agents/requirements.md` nhắc tới nhiều file/thư mục/khái niệm **không còn khớp thực tế** (`Task_Assignment.md`, `run_tests.bat`, `tests/`, `web/static/`, `specs/001-estimate-buffer/`, `"LLF vs Energy-First"`).
   * Nội dung đặc tả bị nhân đôi giữa `agents/` (tiếng Anh) và `docs/` (tiếng Việt). Cần thống nhất nguồn chuẩn duy nhất (Single Source of Truth) sau khi đồng bộ code.
4. **Xung đột nghiêm trọng với nhánh `origin/hmanh` (`5d8a30d`) — CÁCH XỬ LÝ AN TOÀN:**
   * `origin/hmanh` được phát triển song song với Feature 002 (`overload_triage`) nhưng đã **xóa nhầm Feature 001 (`src/estimate_buffer.py`, `test_estimate_buffer.py`) và toàn bộ doc Student UI** (`student_mode_ui.md`, `feature_001_estimate_buffer.md`, `giao_dien_sinh_vien.md`, `tinh_nang_dem_thoi_gian.md`, `web/Log.md`).
   * **Quy tắc tuyệt đối:** Không chạy `git merge origin/hmanh`. Thay vào đó, đứng trên `ltbinh/sync-proposal` dùng `git show origin/hmanh:<path>` để **port chọn lọc** các file giá trị:
     * `src/overload_triage.py`
     * `verification_tests/logical_tests/test_overload_triage.py` (và các test liên quan trong `tests/test_overload_triage.py` đưa về cấu trúc chuẩn)
     * Logic thật của `/api/overload/preview` và UI Preview/Undo trong `specs/002-overload-triage-preview/`.

---

## 7. Chỉ dẫn & Lộ trình đồng bộ từng bước trên nhánh `ltbinh/sync-proposal`

Thực hiện lần lượt 5 pha dưới đây trên nhánh `ltbinh/sync-proposal`, **sau mỗi pha đều phải chạy regression test để đảm bảo `clean_runner.py --pass` luôn giữ `>= 84 Passed | 0 Failed`**:

```powershell
cd group03-smartschedule-baseline
python -B verification_tests/clean_runner.py --pass
python -B verification_tests/clean_runner.py --gaps
python benchmark_runner.py
```

### Pha 0 — Khóa lưới an toàn & Dọn rác nhẹ (Không đổi hành vi lõi)
1. Thêm unit tests tái hiện sẵn các lỗi **A1 (chunk 105m > 90m)**, **A2 (`d_slot == 0`)**, **A4 (`pinned_blocks` 4 case)**, **A6 (LocalRepair topo & Pin)**, **A7 (cycle phải ra `C_hard == 0`)** vào thư mục test (kỳ vọng FAIL trước khi vá ở Pha 1).
2. Xóa `group03-smartschedule-baseline/web/Log.md`.
3. Sửa typo `"grep_weight"` → `"grade_weight"` (hoặc giữ key chuẩn theo schema) ở `data/test_scenarios/t07_incomplete_metadata.json:49` sau khi kiểm tra các test liên quan.

### Pha 1 — Vá triệt để 12 lỗi thuật toán (`A1` → `A12`)
*Ưu tiên đúng thứ tự sau để ít va chạm nhau:*
1. **Sửa `BaseSolver` (`src/solvers/base_solver.py`), `Models`, `Utils` & `GridManager`:**
   * Vá **A1** (`split_task_into_chunks`): bảo vệ bất biến `chunk_slots <= max_slots_per_part`.
   * Vá **A7** (`enforce_dependency_order`): tách và cô lập `CIRCULAR_DEPENDENCY` & `MISSING_PREREQUISITE` trước khi giải, cập nhật `metrics.py:80-96` để không chấm oan `C_hard` cho task bị từ chối hợp lệ.
   * Gộp helper **A4** (`prepare_pinned_blocks` + trừ `pinned_slots` trong `check_deadline_capacity` + bound thứ tự chunk trước/sau pinned chunk + rollback đồng bộ).
   * Mở rộng **A8** (`horizon_slots = MAX_HORIZON_SLOTS = 1344` khi có task cross-week `T10`; kiểm tra ngủ tối thiểu `>= 24 slots = 6h`).
   * Vá **A10** (`is_splittable=True` tự động khi `> 90m` nếu không khóa `False`), **A11** (khóa `SLEEP` bắt buộc + hỗ trợ `FixedEvent` qua đêm), và **A12** (phát hiện `OVERDUE` ở `iso_to_slot` không kẹp ngầm về `slot 0`).
2. **Sửa 4 Solvers (`greedy_edf.py`, `greedy_lst.py`, `greedy_wspt.py`, `backtracking.py`):**
   * Gỡ đoạn code xử lý pin lặp lại trên 4 file, gọi helper chung vừa tạo ở `BaseSolver` (vá **A4**).
   * Vá **A2** ở `greedy_wspt.py:56` (`if d_slot is None:`) + bổ sung `AFTER_PREREQ` & `fail_reason`.
   * Nâng cấp **A3** ở `greedy_lst.py` (tính earliest start theo DAG phụ thuộc + dynamic slack theo slot rảnh thực).
   * Nâng cấp **A5** ở `backtracking.py` (đa dạng điểm ứng viên trong khoảng rảnh lớn + không cắt sớm ở `nodes_explored > 500` khi còn cải thiện objective, vẫn đảm bảo `< 2s`).
3. **Sửa `LocalRepairEngine` & `Controller` (`local_repair.py`, `controller.py`):**
   * Vá **A6**: bảo vệ `PINNED` trong `_repair_local_insertion`; thêm Step 4 **Progressive Unfreezing**; sửa `_enforce_post_move_dependencies` theo topo sort + nearest-slot + chống ghi trùng `RepairChange`; thêm `now_slot` & dependency check vào `_repair_ripple_shift`; sinh đầy đủ `OverloadReport` trong `_build_repair_output`.
   * Vá **A9**: đổi `handle_task_overrun()` (`controller.py:268-319`) sang gọi `LocalRepairEngine` thay vì Full Rebuild.

### Pha 2 — Hiện thực chuẩn các Patterns, Metrics & Grid Search (`Presentation2.pdf`)
1. **Pattern 1 & Slide 17 Calibration:**
   * Giữ tương thích ngược cho Feature 001 (`estimate_habit="OFTEN"`...) đồng thời bổ sung công thức `RoundUp_15(duration * α)` theo `cognitive_load` (`α_light=1.20`, `α_heavy=1.35`).
   * **Bỏ hẳn** đoạn tự nhân `1.2` tại `web/app.js:1749-1752` để chấm dứt lỗi **Double-Buffering**.
   * Viết script `benchmark_alpha_grid.py` thực hiện **`1D Grid Search`** (`α ∈ [1.00, 1.60]` bước `0.05`) + **`Stress Test`** (`+25%` và `+50%` overrun shocks), cộng thêm field `actual_duration_min` để chuẩn bị dữ liệu `Actual / Estimated`.
2. **Pattern 2 & Pattern 5 (`STATE_REST`):** Thêm `STATE_REST` vào `TimeGridManager`; pre-mark khe `< 30p` thành dead-zone `REST` ở Step 1 solver (giữ nguyên `initialize_from_profile` để không gãy `test_minh_week_exact_672_slot_accounting`); tự động chèn `15-min REST` sau deep work (`test_fail_rest_break_insertion_after_deep_work` → **PASS**).
3. **Pattern 3 & Pattern 4 & Models (`Slide 6, 14`):** Bổ sung `CircadianEnergyProfile`, `PersonalHabit` model, khớp năng lượng (`ENERGY_MATCH`) & gom nhóm môn (`neighbour_score`) (`test_fail_circadian_energy_matching` → **PASS**).
4. **Pattern 7 & Experience Rating (`Slide 6, 8`):** Viết `ScoredGreedySolver` thật dùng `Urgency = exp(-slack / γ) * Importance` (`γ = 24h`), xóa alias EDF tại `controller.py:35`; thêm tính **`Experience Rating (1–5)`** (`Comfortable → Exhausting`) vào `ScheduleSummary`.

### Pha 3 — Port chọn lọc Feature 002 (`origin/hmanh`) & Hoàn thiện Step 5 Crunch Mode
1. Port chọn lọc `src/overload_triage.py`, tests và endpoint `/api/overload/preview` thật từ `origin/hmanh` (giữ nguyên `estimate_buffer.py` và toàn bộ tài liệu).
2. Bổ sung đề xuất **habit-skipping / sprint relaxation / triage** trong `OverloadReport` và **Early Extension 24–48h Alert** khi phát hiện nguy cơ trượt hạn sớm (`test_fail_overload_habit_skipping_recommendation` → **PASS**).

### Pha 4 — Đồng bộ API, Explainability & Student UI (`web/`)
1. Chuẩn hóa `reason_codes` có cấu trúc từ mọi solver & repair (`test_fail_why_popover_structured_reason_codes` → **PASS**).
2. Xóa các giá trị hardcode trong `web/app.js:1839-1845` (tên thuật toán, khung giờ ngủ) và `web/index.html:205,257-349` (tuần hiển thị, giờ ngủ). Render động hoàn toàn từ `ScheduleOutput` / `ScheduleSummary` và `CommitmentsProfile`.
3. Nối kéo-thả block trên UI qua `/api/validate-move` để kiểm tra H1–H5 thật bằng backend.
4. Bỏ regex stub chết `/api/tasks/natural-add` hoặc hợp nhất chuẩn 1 parser duy nhất giữa JS & Python.
5. Bổ sung vào Student Mode các mảnh ghép còn thiếu:
   * Form cài đặt Sleep (`>= 6h`), Fixed Events, Habit / Energy Curve (`focus_preference`).
   * Lưu bền vững trạng thái hoàn thành (`doneBlocks` hiện chỉ nằm ở JS `Set` tại `app.js:48,1810`) + M7 Progress Check-in + `Experience Rating (1-5)`.
   * Luồng UI cho M5 (báo sự cố/overrun gọi Local Repair) & M6 (Overload Preview / Triage UI từ Feature 002).

### Pha 5 — Cập nhật Tài liệu & Chốt Nghiệm thu (`Verification Gate`)
1. Cập nhật `README.md`, `group03-smartschedule-baseline/README.md`, dọn sự chồng chéo giữa `agents/` và `docs/` để phản ánh đúng file thực tế.
2. Kiểm tra điều kiện chốt PR trước khi merge `ltbinh/sync-proposal` vào `main`:
   * `python -B verification_tests/clean_runner.py --pass` → **100% PASS** (`>= 84/84` + toàn bộ unit tests mới cho `A1–A9`).
   * `python -B verification_tests/clean_runner.py --gaps` → **`5 Passed | 0 Failed`** (nâng từ `1/5` lên `5/5`).
   * `python benchmark_runner.py` → Toàn bộ `T01–T10` đạt `C_hard = 0`, Determinism 3x `PASS`, T04 Local Insertion `>= 90%` stability, `T09` thể hiện rõ chênh lệch năng lượng Circadian, `T10` xếp được sang tuần 2 trong horizon `1344`, Scale `N=50` dưới ngưỡng độ trễ cho phép.

---

### Phân công phối hợp đề xuất (Theo `Proposal/work_division.pdf` & `Proposal_Report.pdf` §10.2)

* **Lê Tiến Bình (Builder 1 — chủ nhánh `ltbinh/sync-proposal`):** Chủ trì **Pha 1** (vá 9 lỗi `A1–A9`, tách helper dùng chung ở `BaseSolver` & hoàn thiện `LocalRepairEngine`) và phần lõi **Pha 2** (`ScoredGreedySolver`, Circadian Energy, 15m Break, Dead-zone `REST`).
* **Thành viên phụ trách Feature 002 / API & Overload (`origin/hmanh`):** Phối hợp **Pha 3** port chọn lọc `overload_triage.py`, `/api/overload/preview` và Crunch Mode mà không ghi đè mất Feature 001 / UI.
* **Thành viên phụ trách Frontend Student UI & Docs / QA:** Phối hợp **Pha 4 & Pha 5** tháo hardcode `index.html`/`app.js`, bỏ double-buffer JS, nối `/api/validate-move` + Why Popover thật + Settings/M5–M7/Rating, dọn `web/Log.md` và cập nhật bộ verification `--gaps` đạt `5/5 PASS`.

