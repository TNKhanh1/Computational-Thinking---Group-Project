# Báo Cáo Hoàn Thành Đồng Bộ Hệ Thống (`ltbinh/sync-proposal`) & Các Điểm Cần Nhóm Quyết Định

> **Nhánh thực hiện:** `ltbinh/sync-proposal` (xuất phát từ `main` commit `4c0a85a`, **không** làm thay đổi `main`).
>
> **Cơ sở đối chiếu:** `Proposal/Sync_Audit_And_Fix_Guide.md` (A1–A12, 8 Human Behavioral Patterns, Presentation2.pdf, Feature 001 + selective port Feature 002 từ `origin/hmanh`).
>
> **Tài liệu đi kèm:** Danh sách biểu quyết chi tiết nằm tại [`Proposal/Open_Decisions_For_Team.md`](Open_Decisions_For_Team.md) (`Q1–Q10`).

---

## 1. Tóm tắt điều hành (Executive Summary)

Toàn bộ các lỗi thuật toán (`A1–A12`), khoảng trống tính năng (`4/4` gap tests còn lại trên `main`), lệch công thức Buffer, hardcode giao diện và các phát hiện kiểm toán bổ sung sau đồng bộ so với `Presentation2.pdf` đã được xử lý trên nhánh `ltbinh/sync-proposal` (riêng 1 bài test Sprint Mode #113 và một số điểm cấu hình mặc định/nghiệp vụ được giữ mở có chủ đích để cả nhóm biểu quyết `Q1–Q10`):

| Hạng mục kiểm chứng | Trước đồng bộ (`main` `4c0a85a`) | Sau đồng bộ & vá kiểm toán (`ltbinh/sync-proposal`) |
| :--- | :--- | :--- |
| **Operational Verification (`clean_runner.py --pass`)** | `84 Passed \| 0 Failed` | **`107 Passed \| 0 Failed`** (`12.09s`, `ALL PASSED`) |
| **Improve Plan Gap Tests (`clean_runner.py --gaps`)** | `1 Passed \| 4 Failed` | **`5 Passed \| 0 Failed`** (`1.64s`, `ALL PASSED`) |
| **Toàn bộ Ma trận Kiểm thử (`--all` & `pytest -v`)** | `89 tests` | **`112 Passed \| 1 Failed \| Total: 113 Tests`** (`test_fail_edge_sprint_mode_compression_recovery` giữ mở theo **`Q9`**) |
| **Benchmark Scenarios (`T01–T10`, `benchmark_runner.py`)** | `C_hard = 0`, 3x Determ PASS (T04 `100%` nhưng chưa vá topo/pin A6) | **`T01–T10 C_hard = 0`**, 3x Determ `PASS`, Bảng 2 đủ **5 solvers** (kèm `SCORED_GREEDY`), T04 `LOCAL_INSERTION` giữ **`100.00%` Stability** (`Moved=2`, `1.54 ms`) vs `FULL_REBUILD` (`0.00%`, `Moved=12`, `2.89 ms`), `N=50` = **`7.89 ms`** (`<= 200 ms`) |
| **1D Alpha Grid Search & Stress Test (`benchmark_alpha_grid.py`)** | Chưa có | Đã hiệu chỉnh `α ∈ [1.00, 1.60]` bước `0.05` + sốc `+25% / +50%`, lưu kết quả tại [`data/alpha_grid_calibration.json`](../group03-smartschedule-baseline/data/alpha_grid_calibration.json) |
| **Trạng thái các điểm cần nhóm chốt (`Q1–Q10`)** | Nằm rải rác `(Unverified)` / `(Planned)` / `X%` / `γ` trong slide | Cấu hình tập trung tại [`src/config.py`](../group03-smartschedule-baseline/src/config.py), tổng hợp đầy đủ ngay tại **Mục 5** bên dưới và [`Proposal/Open_Decisions_For_Team.md`](Open_Decisions_For_Team.md) |

---

## 2. Chi tiết những gì đã thực hiện

### 2.1. Dọn dẹp kỹ thuật & Chuẩn hóa dữ liệu
1. **Xóa file rác:** Đã xóa `group03-smartschedule-baseline/web/Log.md`.
2. **Sửa lỗi chính tả test fixture:** Đã sửa `"grep_weight"` thành `"grade_weight"` trong `group03-smartschedule-baseline/data/test_scenarios/t07_incomplete_metadata.json`.
3. **Cô lập toàn bộ tham số mở:** Tạo module thuần tầng 1 [`src/config.py`](../group03-smartschedule-baseline/src/config.py) chứa `ALPHA_LIGHT_DEFAULT = 1.20`, `ALPHA_HEAVY_DEFAULT = 1.35`, `ALPHA_GRID_MIN/MAX/STEP`, `MAX_DEEP_WORK_MIN = 90`, `MANDATORY_REST_SLOTS = 1`, `CATEGORY_BATCH_BONUS = 0.35`, `CONTEXT_SWITCH_PENALTY = 0.25`, `DEAD_ZONE_MAX_SLOTS = 1`, `MIN_SLEEP_HOURS = 6`, `MIN_SLEEP_SLOTS = 24`, `GAMMA_URGENCY_HOURS = 24.0`, `OVERDUE_URGENCY_CAP = 1.50`, `HABIT_BASE_URGENCY = 0.20`, `STABILITY_TARGET_PCT = 90.0`, `BACKTRACK_MAX_CANDIDATES_PER_TASK = 12`, `BACKTRACK_MAX_NODES = 3000`, `EARLY_EXTENSION_ALERT_MIN_HOURS = 0.0`, `EARLY_EXTENSION_ALERT_MAX_HOURS = 48.0`.

---

### 2.2. Vá triệt để 12 lỗi & khiếm khuyết thuật toán (`A1–A12`)

| Mã lỗi | File & Symbol đã sửa / bổ sung | Giải pháp kỹ thuật đã triển khai |
| :--- | :--- | :--- |
| **A1** | [`src/solvers/base_solver.py`](../group03-smartschedule-baseline/src/solvers/base_solver.py) (`BaseScheduler.split_task_into_chunks`) | Bảo vệ bất biến $H_2$/Pattern 2: không hạ `num_parts` nếu làm chunk vượt `max_slots_per_part` (task `105p` với `max_chunk=90p` không còn phình thành 1 khối `105p`). |
| **A2** | [`src/solvers/greedy_wspt.py`](../group03-smartschedule-baseline/src/solvers/greedy_wspt.py) (`GreedyWSPTSolver._wspt_sort_key`, `solve`) | Sửa bug truthiness `d_slot == 0` (`raw_d if raw_d is not None else 999999`), dùng pipeline chung sinh đủ `AFTER_PREREQ` và mã chẩn đoán thiếu dung lượng / phân mảnh. |
| **A3** | [`src/solvers/greedy_lst.py`](../group03-smartschedule-baseline/src/solvers/greedy_lst.py) (`GreedyLSTSolver.solve`) | Chuyển LST từ static sort sang dynamic laxity tôn trọng thứ tự tiên quyết DAG và số slot `FREE` thực còn lại trong `[effective_earliest, deadline)`. |
| **A4** | [`src/solvers/base_solver.py`](../group03-smartschedule-baseline/src/solvers/base_solver.py) (`prepare_pinned_blocks`, `check_deadline_capacity`, `place_task_with_constraints`) & 4 solvers | Gom logic `pinned_blocks` về helper dùng chung ở `BaseScheduler`: kiểm tra $H_1/H_3/H_4$ + `now_slot`, trừ `pinned_slots_by_task` khi kiểm tra capacity (hết double-counting), chặn thứ tự chunk trước/sau chunk đã pin, rollback an toàn. |
| **A5** | [`src/solvers/backtracking.py`](../group03-smartschedule-baseline/src/solvers/backtracking.py) (`BacktrackingSolver`) | Lấy mẫu đa điểm trong khoảng rảnh dài (đầu khoảng, chuyển mức Peak Energy, điểm giữa, sát mép phải, tối đa `BACKTRACK_MAX_CANDIDATES_PER_TASK = 12`) và tối ưu đa tiêu chí (Circadian + Category Batching) trong trần `BACKTRACK_MAX_NODES = 3000`. |
| **A6** | [`src/solvers/local_repair.py`](../group03-smartschedule-baseline/src/solvers/local_repair.py) (`_find_nearest_valid_slot`, `_try_progressive_unfreeze`, `_repair_local_insertion`) | Bảo vệ `PINNED` trong Local Insertion; bổ sung **Step 4 Progressive Unfreezing** (tháo băng từng task tương lai điểm thấp); sửa `_enforce_post_move_dependencies` theo topo sort, gom `RepairChange`, chiến lược 2-pass relaxation tìm slot gần gốc nhất (`T04` đạt `100.00%` Stability, `C_hard=0`); đồng bộ `now_slot`/H5 trong Ripple Shift và xuất `OverloadReport` khi quá tải cục bộ. |
| **A7** | [`src/solvers/base_solver.py`](../group03-smartschedule-baseline/src/solvers/base_solver.py) (`partition_dependency_order`, `enforce_dependency_order`) & [`src/metrics.py`](../group03-smartschedule-baseline/src/metrics.py) | Cô lập sớm các task thuộc chu trình (`CIRCULAR_DEPENDENCY`) hoặc thiếu tiên quyết (`MISSING_PREREQUISITE`) sang `unplaced_tasks`, giữ $C_{\text{hard}} = 0$ (siết chặt assertion trong `verification_tests/logical_tests/test_circular_dependencies.py`). |
| **A8** | [`src/solvers/base_solver.py`](../group03-smartschedule-baseline/src/solvers/base_solver.py) (`resolve_horizon_slots`) & [`src/grid_manager.py`](../group03-smartschedule-baseline/src/grid_manager.py) (`lock_sleep_schedule`) | Tự động mở rộng horizon lên `MAX_HORIZON_SLOTS = 1344` (2 tuần) khi có deadline cross-week (`T10`), vẫn tổng hợp `display_horizon_slots = SLOTS_PER_WEEK` cho UI; kiểm tra thời lượng ngủ tối thiểu `>= MIN_SLEEP_SLOTS` (`24` slots = `6h`). |
| **A9** | [`src/controller.py`](../group03-smartschedule-baseline/src/controller.py) (`ScheduleController.handle_task_overrun`) | Thay Full Rebuild bằng `LocalRepairEngine.repair_overrun()` kết hợp `apply_estimate_buffer` và `annotate_estimate_buffer` để bảo toàn stability `>= 90%` (Pattern 8). |
| **A10** | [`src/models.py`](../group03-smartschedule-baseline/src/models.py) (`apply_auto_splitting_default`, `normalize_task_input`) | Task `> 90p` không truyền `is_splittable` tường minh sẽ tự bật `is_splittable = True`, nhưng vẫn tôn trọng tuyệt đối nếu truyền `is_splittable = False`. |
| **A11** | [`src/grid_manager.py`](../group03-smartschedule-baseline/src/grid_manager.py) (`initialize_from_profile`, `lock_fixed_event`) | Luôn khóa `SLEEP >= 6h/đêm` theo Pattern 6 bất kể `is_hard_lock=False` (kèm warning); hỗ trợ `FixedEvent` ca qua đêm (vd `22:00–02:00`). |
| **A12** | [`src/utils.py`](../group03-smartschedule-baseline/src/utils.py) (`iso_to_slot_with_status`) & [`src/solvers/base_solver.py`](../group03-smartschedule-baseline/src/solvers/base_solver.py) (`detect_past_due_tasks`) | Phát hiện deadline ISO nằm trong quá khứ (`is_past_due`) và vượt trần horizon (`beyond_horizon`), tránh kẹp ngầm về `Monday 00:00` (`slot 0`). |

---

### 2.3. Hiện thực 8 Behavioral Patterns, `SCORED_GREEDY`, `OverloadTriage`, `Experience Rating`, M1 & M7

1. **Dual Planning Fallacy Buffer (Pattern 1 — [`src/estimate_buffer.py`](../group03-smartschedule-baseline/src/estimate_buffer.py)):**
   * Bảo toàn 100% Feature 001 (`HABIT`: `RARELY=1.0`, `SOMETIMES=1.1`, `OFTEN=1.25` với `planned_duration_min` — `34/34` test xanh).
   * Bổ sung chế độ `COGNITIVE_LOAD` đúng công thức Slide 7 & 17 (`planned_duration_roundup_15` + `multiplier_for_load`: $\alpha_{\text{light}}=1.20$ cho load 1–2, $\alpha_{\text{heavy}}=1.35$ cho load 3) thông qua `planned_duration_for_task_mode()`.
   * Xóa bỏ lỗi nhân đôi buffer `* 1.2` ở `saveStudentTask()` / `updateStBufferPreview()` trong `web/app.js`.
2. **Deep Work Cap + `15m REST` + Dead-Zones `< 30m` (Pattern 2 & Pattern 5 — [`src/grid_manager.py`](../group03-smartschedule-baseline/src/grid_manager.py), [`src/solvers/base_solver.py`](../group03-smartschedule-baseline/src/solvers/base_solver.py)):**
   * Thêm trạng thái `TimeGridManager.STATE_REST` (`"REST"`).
   * Step 1 của solver tiền đánh dấu khe `< 30p` (`DEAD_ZONE_MAX_SLOTS = 1`) thành `STATE_REST` mà không làm thay đổi `initialize_from_profile()` (giữ nguyên tính toán 672-slot gốc).
   * Tự động chèn `15 phút REST` sau phiên deep work (`>= 90p` hoặc `cognitive_load == 3`) ở chế độ thường, trả reason code `BREAK_AFTER` và thống kê `rest_slots` trong `ScheduleSummary`.
3. **Circadian Energy Profile & Context Switching (Pattern 3 & Pattern 4 — [`src/models.py`](../group03-smartschedule-baseline/src/models.py), [`src/solvers/scored_greedy.py`](../group03-smartschedule-baseline/src/solvers/scored_greedy.py)):**
   * Thêm `CircadianEnergyProfile` (`MORNING | AFTERNOON | EVENING | BALANCED` + `level_for_hour` / `level_for_slot`) và `PersonalHabit` (`expand_personal_habits` trong [`src/controller.py`](../group03-smartschedule-baseline/src/controller.py)).
   * Scoring chọn khe đặt ưu tiên khớp mức năng lượng (`Load-3 -> Level-3`, `Load-1 -> Low Energy`), tránh dead-zone và cộng điểm gom nhóm cùng category (`CATEGORY_BATCH_BONUS = 0.35`, `CONTEXT_SWITCH_PENALTY = 0.25`, sinh reason code `BATCHED_CATEGORY` và `ENERGY_MATCH`).
4. **Hyperbolic Urgency `ScoredGreedySolver` (Pattern 7 — [`src/solvers/scored_greedy.py`](../group03-smartschedule-baseline/src/solvers/scored_greedy.py)):**
   * Xóa alias EDF cũ trong `SOLVER_REGISTRY["SCORED_GREEDY"]`, thay bằng `ScoredGreedySolver` thật theo công thức:
     $$\text{Score}(t) = \exp\left(-\frac{\max(0, \text{slack\_hours})}{\gamma}\right) \times \text{Importance}$$
     với `GAMMA_URGENCY_HOURS = 24.0`, kẹp trần quá hạn `OVERDUE_URGENCY_CAP = 1.50`, và trọng số cơ sở `HABIT_BASE_URGENCY = 0.20` cho task/habit không có deadline.
5. **Two-Tier Crunch Mode, Early Extension Alert & `OverloadTriageEngine` (Step 5 & Feature 002 — [`src/overload_triage.py`](../group03-smartschedule-baseline/src/overload_triage.py), [`src/solvers/base_solver.py`](../group03-smartschedule-baseline/src/solvers/base_solver.py)):**
   * **Tier 1 (Sprint Mode):** Khi xếp không hết ở lượt thường, solver tự động thử lượt `crunch_tier_used = 1` (nới `allow_breaks=False` — *Cut breaks*, reason code `CRUNCH_RELAXED`).
   * **Tier 2 (Overload Triage):** Port chọn lọc `OverloadTriageEngine` từ `origin/hmanh` (`SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST` có bảo vệ `get_protected_prerequisite_ids`), nối vào `ScheduleController.preview_overload_resolution()` và `POST /api/overload/preview`.
   * **Early Extension Alert (24–48h):** `compute_early_extension_alerts` phát hiện sớm task có nguy cơ thiếu giờ trong cửa sổ `<= 48h` trước hạn.
6. **Experience Rating `1–5` (Slide 6 — [`src/metrics.py`](../group03-smartschedule-baseline/src/metrics.py)):**
   * `calculate_experience_rating()` trả thang điểm `[1.0, 5.0]` (`1 - Comfortable` → `5 - Exhausting`) dựa trên 4 thành phần: mật độ làm việc `density_penalty`, chuỗi làm liên tục không nghỉ `streak_penalty`, lệch Circadian với block nặng `circadian_penalty`, và áp lực quá tải/Crunch `overload_penalty`.
7. **M1 Multilingual EN/VI Parser & M7 Check-in ([`src/nl_parser.py`](../group03-smartschedule-baseline/src/nl_parser.py), `web/api.py`):**
   * Tạo `parse_natural_language_task()` phân tích đa ngữ EN/VI (ngày tương đối theo `now_day`, thứ trong tuần không còn hardcode `"Wednesday"`, giờ hạn chót, thời lượng `1h30`/`90p`/`2 tiếng`, category/priority/cognitive_load/splittability) và nối vào `POST /api/tasks/natural-add`.
   * Bổ sung `POST /api/tasks/complete` ghi nhận `actual_duration_min` phục vụ thu thập tỷ lệ `Actual / Estimated` (M7).
8. **Đồng bộ Frontend Student & Lab UI (`web/index.html`, `web/app.js`):**
   * Gỡ toàn bộ ngày tuần cố định `"2 Thg 11 – 8 Thg 11, 2026"`, banner ngủ cứng `23:30 – 06:30`, text hardcode EDF trong `openWhyHereModal()` và double-buffer `* 1.2` ở `saveStudentTask()` / `updateStBufferPreview()`.
   * Bổ sung hiển thị Experience Rating, Early Extension Alert banner, `.slot-rest` & `.slot-block-proposed`, `#stSettingsModal` (cấu hình giờ ngủ `>= 6h`, `focus_preference`, `buffer_mode`, `alpha_light`, `alpha_heavy`; lựa chọn solver mặc định giao diện hiện vẫn giữ `GREEDY_EDF_FIRST_FIT` chờ nhóm chốt `Q10`), `#stTaskModal` (M1 Quick-Add + `category`/`cognitive_load` + bật/tắt buffer từng task), `#stDisruptionModal` (M5 Local Repair), Overload Preview/Apply/Undo bar, lưu bền vững `localStorage` (`doneBlocks`, `actualDurations`, `pinnedBlocks`), M7 `actual_duration_min` check-in, và kéo thả nối `POST /api/validate-move`.

---

### 2.4. Các bản vá kiểm toán phát hiện & sửa lỗi bổ sung (Audit Round)

Sau khi rà soát toàn diện đối chiếu mã nguồn với `Presentation2.pdf` và tài liệu hệ thống, các lỗi phát hiện thêm dưới đây đã được sửa và kiểm thử lại:

| Hạng mục | File & Symbol đã sửa | Nội dung sửa lỗi |
| :--- | :--- | :--- |
| **Kéo thả UI & hợp đồng `/api/validate-move`** | [`src/controller.py`](../group03-smartschedule-baseline/src/controller.py) (`validate_manual_move`), [`web/api.py`](../group03-smartschedule-baseline/web/api.py) (`api_validate_move`), [`web/app.js`](../group03-smartschedule-baseline/web/app.js) (`handleGridDrop`) | Trả về `"proposed_block"` (clone `ScheduleBlock` cập nhật slot/giờ/ISO và `state="PINNED"`) khi hợp lệ; API đọc thống nhất `blocks`, `current_blocks` và `schedule.blocks`; Frontend gửi đầy đủ `algorithm`, `blocks` và `current_blocks`. |
| **Opt-out buffer từng task (`buffer_mode="NONE"`)** | [`src/models.py`](../group03-smartschedule-baseline/src/models.py), [`src/estimate_buffer.py`](../group03-smartschedule-baseline/src/estimate_buffer.py), [`src/controller.py`](../group03-smartschedule-baseline/src/controller.py), [`web/app.js`](../group03-smartschedule-baseline/web/app.js) | Hỗ trợ `"NONE"`/`"OFF"`/`"DISABLED"`/`"NO_BUFFER"` ở validator & `planned_duration_for_task_mode()`; `apply_estimate_buffer()` giữ `multiplier = 1.0` khi task chọn `buffer_mode="NONE"`; `saveStudentTask()` gán `buffer_mode = "NONE"` khi người dùng bỏ chọn buffer. |
| **Chống băm nhỏ quá mức trong `SHORTEN_TASK`** | [`src/overload_triage.py`](../group03-smartschedule-baseline/src/overload_triage.py) (`apply_triage_option`) | Khi thời lượng rút gọn `new_dur <= 90`, giữ `max_chunk_min = max(45, new_dur)` để bảo toàn tính nguyên khối (không xé vụn `T03-UNSPLITTABLE`); khi `new_dur > 90` (như `T06`), giữ chunk `15p` để vừa khe hẹp `1365m` của bài kiểm tra khả thi `100%`. |
| **Bảo vệ block `PINNED`/`DONE` khi Overrun** | [`src/solvers/local_repair.py`](../group03-smartschedule-baseline/src/solvers/local_repair.py) (`repair_overrun`) | Khóa trước `locked_other_blocks` (`PINNED`/`DONE`) lên lưới trước khi cấp slot mở rộng, chỉ nới/dịch `flexible_other_blocks`, và thêm cơ chế rollback + báo cáo `OVERRUN_OVERLOAD` nếu thiếu slot hợp lệ. |
| **Mở rộng `PersonalHabit` trước Overload Preview** | [`src/controller.py`](../group03-smartschedule-baseline/src/controller.py) (`preview_overload_resolution`) | Mở rộng `expand_personal_habits(profile, tasks)` từ đầu và dùng `preview_profile` với `personal_habits=[]` để tránh mở rộng trùng lặp/sai lệch thói quen khi mô phỏng Triage. |
| **Trùng mã sự kiện gián đoạn & Đồng bộ CLI/Benchmark/Docs** | [`web/app.js`](../group03-smartschedule-baseline/web/app.js) (`applyStudentDisruption`), [`main.py`](../group03-smartschedule-baseline/main.py), [`benchmark_runner.py`](../group03-smartschedule-baseline/benchmark_runner.py), `README.md`, `docs/`, `agents/` | Sinh `eventId` `DIS_xxxx` 1 lần trước `/api/repair`; bổ sung `--solver SCORED_GREEDY`, in `Experience Rating` / `Crunch Tier` và `REST` trong `672-Slot Breakdown` ở `main.py`; thêm `SCORED_GREEDY` vào Bảng 2 `benchmark_runner.py`; thêm regression test trong `test_sync_algorithm_fixes.py` (`14/14` pass) và sửa liên kết/số liệu ở toàn bộ `README.md`, `docs/`, `agents/`. |

---

## 3. Kết quả kiểm thử, Benchmark & Calibration sau chỉnh sửa cuối cùng

### 3.1. Bộ kiểm thử tự động (`verification_tests/clean_runner.py` & `pytest -v`)
* `python -B verification_tests/clean_runner.py --pass`: **`107 Passed | 0 Failed | Total: 107 Tests`** (`12.09s`, `ALL PASSED`):
  * Phase 1 UI (`ui_tests`): `test_ui_contract_improve_plan.py` (`1/1`), `test_ui_endpoints.py` (`5/5`).
  * Phase 2 Architecture (`architecture_tests`): `test_memory_leaks.py` (`2/2`), `test_production_failures.py` (`3/3`), `test_system_architecture.py` (`4/4`).
  * Phase 3 Logical (`logical_tests`): `test_circular_dependencies.py` (`4/4`), `test_estimate_buffer.py` (`34/34`), `test_generation.py` (`4/4`), `test_overload_triage.py` (`9/9`), `test_scheduling_edge_cases.py` (`3/3`), `test_sync_algorithm_fixes.py` (`14/14`), `test_undefined_behaviors.py` (`4/4`).
  * Phase 4 Benchmark (`benchmark_tests`): `test_constraints.py` (`3/3`), `test_edf_solver.py` (`2/2`), `test_feasibility_benchmarks.py` (`5/5`), `test_scenarios_t01_t10.py` (`7/7`), `test_time_grid.py` (`3/3`).
* `python -B verification_tests/clean_runner.py --gaps`: **`5 Passed | 0 Failed | Total: 5 Tests`** (`1.64s`, `ALL PASSED`).
* `python -B verification_tests/clean_runner.py --all`: **`112 Passed | 1 Failed | Total: 113 Tests`** (`12.59s`, `Status: 1 ISSUES/GAPS DETECTED`).
* `python -B -m pytest -v`: **`1 failed, 112 passed, 1 warning in 12.31s`**.
  * Bài test duy nhất fail (`test_fail_edge_sprint_mode_compression_recovery` trong `verification_tests/logical_tests/test_scheduling_edge_cases.py`) được giữ trung thực theo **`Q9`**: hệ thống từ chối tự ý nén tác vụ nguyên khối `90p` xuống `75p` khi thiếu slot rảnh trước deadline, thay bằng `INFEASIBLE_CAPACITY` + `Early Extension Alert`.

### 3.2. Kết quả Benchmark & CLI (`python -B benchmark_runner.py` & `python -B main.py`)
* **Kịch bản chuẩn `T01–T10`:** `C_hard = 0` trên toàn bộ 10 kịch bản, `3x Determ = PASS` (latency `0.54 ms – 2.45 ms`). `T03` chẩn đoán `CAPACITY_SHORTAGE (shortage=90m)` (`R_dl = 50.0%`), `T06` chẩn đoán `CAPACITY_SHORTAGE (shortage=105m)` (`R_dl = 66.7%`); 8 kịch bản còn lại đạt `R_dl = 100.0%`.
* **Bảng 2 — Đối sánh 5 Thuật toán trên `T01`:**
  * `GREEDY_EDF_FIRST_FIT`: `C_hard=0`, `R_dl=100.0%`, `Blocks=7`, `FragIdx=0.000`, `1.38 ms` (`SHA-256: 394e7b2ea28a3a11...`)
  * `GREEDY_LST_BEST_FIT`: `C_hard=0`, `R_dl=100.0%`, `Blocks=7`, `FragIdx=0.290`, `2.05 ms` (`SHA-256: e2f849322f364331...`)
  * `GREEDY_WSPT_SMITH_RULE`: `C_hard=0`, `R_dl=100.0%`, `Blocks=7`, `FragIdx=0.000`, `1.39 ms` (`SHA-256: 6fb72da16b1cb058...`)
  * `BACKTRACKING_BRANCH_AND_BOUND`: `C_hard=0`, `R_dl=100.0%`, `Blocks=7`, `FragIdx=0.290`, `89.26 ms` (`SHA-256: 9129eb0b8fcf2ec0...`)
  * `SCORED_GREEDY`: `C_hard=0`, `R_dl=100.0%`, `Blocks=7`, `FragIdx=0.290`, `7.70 ms` (`SHA-256: b2260750a83e5730...`)
* **Độ ổn định sự cố (`T04`) & Trượt thời lượng (`T05`):**
  * `LOCAL_INSERTION (Targeted M4)`: **Stability = `100.00%`**, `Moved = 2 blocks`, `C_hard = 0`, `R_dl = 100.0%`, `1.54 ms`.
  * `FULL_REBUILD (Scratch EDF)`: **Stability = `0.00%`**, `Moved = 12 blocks`, `C_hard = 0`, `R_dl = 100.0%`, `2.89 ms`.
  * `T05 Overrun (90m -> 135m)`: `Shifted Downstream Blocks = 2`, `C_hard = 0`, `R_dl = 100.0%`.
* **Khả năng mở rộng (`Scalability`):** `N=10` (`1.75 ms`), `N=25` (`3.93 ms`, đạt `<= 50 ms`), `N=50` (`7.89 ms`, đạt `<= 200 ms`), đều `100% placed`, `C_hard = 0`, `[PASS]`.
* **Kiểm chứng CLI `main.py --preset minh` (sau chỉnh sửa cuối cùng):**
  * `--solver SCORED_GREEDY`: `100.00% (9/9 tasks, 14/14 chunks)`, `C_hard=0`, `FragIdx=0.3600`, `Experience Rating: 2.48/5 (2 - Manageable) | Crunch Tier=0`, `672-Slot Breakdown: SLEEP=196 | OCCUPIED=132 | BLOCK=57 | REST=8 | FREE=279` (tổng = `672`), `SHA-256: 55c47d51a1f753eb`.
  * `--solver EDF`: `100.00% (9/9 tasks, 14/14 chunks)`, `C_hard=0`, `FragIdx=0.3600`, `Experience Rating: 2.08/5 (2 - Manageable) | Crunch Tier=0`, `672-Slot Breakdown: SLEEP=196 | OCCUPIED=132 | BLOCK=57 | REST=10 | FREE=277` (tổng = `672`), `SHA-256: a091f3a5e8385c70`.

### 3.3. Kết quả 1D Alpha Grid Search & Stress Test (Dữ liệu hiệu chỉnh lưu tại [`data/alpha_grid_calibration.json`](../group03-smartschedule-baseline/data/alpha_grid_calibration.json))
Kết quả hiệu chỉnh trước đợt vá cuối trên `7` kịch bản (`MinhWeek`, `LanWeek`, `T01_Normal`, `T02_Overlap`, `T05_Overrun`, `T08_Unclear`, `T09_Circadian`) với `SCORED_GREEDY` và sốc overrun `+25%`, `+50%` (ghi nhận tại [`data/alpha_grid_calibration.json`](../group03-smartschedule-baseline/data/alpha_grid_calibration.json)):

* `α = 1.00 / 1.00`: `R_dl = 100.00%`, **`+25%NoRep = 0.0%`**, `+25%Rdl = 100.00%`, `Frag = 0.20`, `Exp = 1.58`, **`Score = 79.61`** (không có đệm thì hầu như mọi task overrun `+25%` đều phải sửa lịch).
* `α = 1.20 / 1.20`: `+25%NoRep = 97.1%`, `Frag = 0.15`, `Exp = 1.90`, **`Score = 99.13`**.
* `α = 1.25 / 1.25` – `1.50 / 1.50`: hấp thụ không cần sửa **`+25%NoRep = 100.0%`**, đạt **điểm tối ưu 1D tại `α = 1.40 / 1.40`** (`Frag = 0.05`, `Exp = 1.80`, **`Score = 99.90`**).
* `α = 1.55 / 1.55` – `1.60 / 1.60`: `Frag` tăng lên `0.27 – 0.33`, `Exp` tăng lên `2.02 – 2.03`, `Score` giảm còn `99.36 – 99.23`.
* **Cấu hình bất đối xứng đề xuất (`α_light = 1.20`, `α_heavy = 1.35`):** `C_hard = 0`, `R_dl = 100.0%`, `+25%NoRep = 97.1%`, `+25%Rdl = 100.0%`, `+50%Rdl = 100.0%`, `Frag = 0.04`, `Exp = 1.96`, **`Score = 99.34`**.

---

## 4. Những hạn chế / khoảng trống còn lại chưa thể tự quyết định (Honest Remaining Gaps)

1. **Test #113 `test_fail_edge_sprint_mode_compression_recovery` (`1 Failed` trong `--all`/`pytest -v`):** Vẫn FAIL có chủ đích do không tự nén tác vụ `90p -> 75p` khi thiếu slot, cần cả nhóm chốt ở **`Q9`**.
2. **`M1 NL Parser` (`src/nl_parser.py`) chưa nối LLM API thật:** Đang chạy thuần `HYBRID_DETERMINISTIC` regex/rule-based offline (giữ nguyên toàn văn prompt làm `title`, mặc định `"Monday"` nếu không truyền `now`) theo hướng ưu tiên tính tất định **`Q5`**.
3. **Thiếu form nhập liệu trên UI (`web/index.html`) cho một số trường nâng cao:** `PersonalHabit`, `horizon_days` (chỉ định 7 hoặc 14 ngày) và `planning_week_start` đã hoạt động ở Pydantic model / API / solver, nhưng chưa mở ô nhập trực quan trong Student/Lab UI.
4. **Chưa có kịch bản stress tải cực hẹp cho `α >= 1.7` & chưa có log thực nghiệm `1-week peer study`:** 7 kịch bản của `benchmark_alpha_grid.py` đều còn quỹ rảnh lớn (`~5250–5595` phút rảnh/tuần) nên chưa chạm ngưỡng gãy deadline ở `α = 1.70`, và nhóm chưa thu thập log `actual_duration_min` thực tế ngoài đời (`Q1`, `Q7`).
5. **Khác biệt `T09`, mặc định UI solver & `FULL_REBUILD` (`Q10`):** `EDF` và `SCORED_GREEDY` đang cho lịch giống nhau trên `T09` (do `should_prefer_energy_placement()` bật chung để pass `--gaps`); Web UI mặc định vẫn chọn `GREEDY_EDF_FIRST_FIT`; và `LocalRepairEngine._repair_full_rebuild()` hiện vẫn gọi `GreedyEDFSolver`.
6. **File thuyết trình `Proposal/Presentation2.pdf` chưa chỉnh sửa:** Toàn bộ ký hiệu `(Unverified)`, `(Planned)`, `≥ X%`, `γ`, `M1: LLM`, và số liệu benchmark mới trên slide chỉ cập nhật sau khi cả nhóm thống nhất xong `Q1–Q10` (`Q8`).

---

## 5. Tổng hợp ĐẦY ĐỦ 10 hạng mục cần nhóm thảo luận & quyết định (`Q1–Q10`)

Toàn bộ nhóm cần họp biểu quyết `10` điểm sau (chi tiết lập luận & phương án xem thêm tại [`Proposal/Open_Decisions_For_Team.md`](Open_Decisions_For_Team.md)). Mặc định tạm thời hiện nay đang được gom trong [`src/config.py`](../group03-smartschedule-baseline/src/config.py) để hệ thống chạy ổn định:

| Mã | Hạng mục cần nhóm quyết định | Nguồn phát sinh | Mức độ ảnh hưởng | Tạm dùng hiện tại & phương án cần biểu quyết |
| :--- | :--- | :--- | :--- | :--- |
| **`Q1`** | Hệ số buffer **`α`**, chế độ **Habit vs Cognitive Load**, quy tắc làm tròn & kế hoạch `1-week peer study` | `Presentation2.pdf` Slide 7, 17 vs `src/estimate_buffer.py` | **Cao** | Tạm giữ song song `HABIT` + `COGNITIVE_LOAD` (`α_light=1.20`, `α_heavy=1.35`, `Score=99.34`). Nhóm cần chốt: giữ `1.20/1.35` hay nâng lên `1.40` (`Score=99.90`), `RoundUp_15` vs `Nearest_15`, và bổ sung stress-test `α >= 1.7` + thu log M7 1 tuần. |
| **`Q2`** | Hằng số suy giảm **`γ`** & giá trị biên `Urgency` cho `Habit` / `Overdue` | `Presentation2.pdf` Slide 8 (`exp(-slack / γ)`) | **Cao** | Tạm chốt `γ = 24.0` giờ, `OVERDUE_URGENCY_CAP = 1.50`, `HABIT_BASE_URGENCY = 0.20` (đã thay chỗ bỏ trống `γ` trên Slide 8). Nhóm cần xác nhận chính thức `3` hằng số này. |
| **`Q3`** | **Pattern 3 (Circadian Matching):** Cứng (`strictly`) hay Mềm (`Soft`)? | Slide 7 (*strictly*) vs Slide 9 (*Soft*) | **Cao** | Đang chạy cơ chế mềm 2 tầng (ưu tiên Level-3, fallback Level-2 trước deadline, hạ Level-1 khi Crunch). Nhóm chốt giữ mềm để tránh rớt deadline oan hay khóa cứng theo Slide 7. |
| **`Q4`** | Ngưỡng ổn định **`X%`** khi sửa lịch (`Schedule Stability` — Pattern 8) | Slide 5 & Slide 8 (`≥ X%`) | **Trung bình** | Tạm chốt **`X = 90%`** (khớp `Proposal_Report.pdf`; `T04 LOCAL_INSERTION` đạt `100.00%`). Nhóm duyệt chốt số `90%` để thay `≥ X%` trên slide. |
| **`Q5`** | **M1 NL Parser:** Dùng LLM API thật hay giữ Deterministic Parser (offline)? | Slide 10 (`M1: LLM`) vs `src/nl_parser.py` | **Trung bình** | Hiện dùng **Deterministic Parser** offline (`HYBRID_DETERMINISTIC`, không tốn quota/mạng, giữ SHA-256 tất định). Nhóm chốt giữ Hybrid (offline mặc định + hook LLM tùy chọn khi có key) hay tích hợp LLM bắt buộc. |
| **`Q6`** | Biên kỹ thuật **Pattern 2 (`15m REST`)**, **Pattern 5 (`< 30m` Dead-zone)** & **auto-split `> 90m`** | Slide 6, 7, 8, 13, 16 vs `src/models.py` | **Cao** | Tạm dùng: nghỉ `15p` sau phiên `>= 90p` hoặc `Load == 3` (trừ khi sát `SLEEP`/`OCCUPIED`), dead-zone cấm deep work, task `> 90m` auto-split nếu không truyền `is_splittable=False`. Nhóm chốt 3 ranh giới này (tránh ảnh hưởng ngược `T03`/`T06`). |
| **`Q7`** | Công thức **`Experience Rating (1–5)`**, trọng số **`Category Batching`** & UI `PersonalHabit` | Slide 6, 7 vs `src/metrics.py` | **Trung bình** | Đã cài hàm 4 thành phần chuẩn hóa `[1.0..5.0]`, `CATEGORY_BATCH_BONUS=0.35`, `CONTEXT_SWITCH_PENALTY=0.25`. Nhóm duyệt trọng số các thành phần và quyết định có mở form `PersonalHabit`/`horizon_days` trên Web UI hay không. |
| **`Q8`** | Quy trình hợp nhất nhánh `origin/hmanh` & lộ trình sửa `Presentation2.pdf` | Git `main` (`4c0a85a`) vs `origin/hmanh` (`5d8a30d`) | **Rất cao** | Dùng `ltbinh/sync-proposal` (port chọn lọc `overload_triage` + giữ `estimate_buffer` & Student UI) để tránh xung đột 47 file; sau khi duyệt `Q1–Q10`, xóa `(Unverified)` / `(Planned)` trên `Presentation2.pdf`. |
| **`Q9`** | **Sprint Mode Tier 1** có tự nén thời lượng task gốc (`90m -> 75m`) không? (`#113` fail) | `test_scheduling_edge_cases.py` (`test_fail_edge_sprint_mode_compression_recovery`) | **Cao** | **Phương án A (đề xuất):** Giữ nguyên tắc không tự cắt xén task người dùng, chuyển Sprint Mode sang gợi ý `SHORTEN_TASK` + `Early Extension Alert` và cập nhật spec bài test #113. **Phương án B:** Cho phép tự nén tối đa `X%` khi sát deadline. |
| **`Q10`** | Tách rạch ròi **`EDF` V0 (Energy-Blind)** vs **`SCORED_GREEDY`** trên `T09` & Solver mặc định Web UI | `base_solver.py` vs `web/index.html`, `web/app.js`, `local_repair.py` | **Cao** | Chốt (1) Có tách `EDF` thành thuần Energy-Blind trên `T09` & sửa `--gaps` sang `SCORED_GREEDY` để đối chứng R&D rõ ràng không; (2) Chốt mặc định Web UI dùng `SCORED_GREEDY` hay giữ `GREEDY_EDF_FIRST_FIT`, và `FULL_REBUILD` có giữ nguyên solver đang chọn thay vì hardcode `EDF` không. |

