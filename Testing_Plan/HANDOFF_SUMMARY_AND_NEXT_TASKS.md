# Tổng Kết Thay Đổi (`main` → `v2.1 + Fuzz v2`) & Lộ Trình Bàn Giao Hoàn Thành SmartSchedule

> **Nhánh bàn giao:** `testing-system/v2.1-fuzz-handoff` *(tách từ `main` commit `e261e42` — PR #6 `testing-system/paper-alignment`; nhánh `main` được giữ nguyên vẹn)*.  
> **Ngày tổng kết:** `2026-11-20`  
> **Trọng tâm đợt thay đổi này:** Đóng băng bộ **Sinh đề vô hạn (`FuzzGenerator v2`)** + **Máy chấm hướng con người (`Checker v2.1`)** làm thước đo chuẩn xác, công bằng trước khi bắt tay vào xây lại toàn bộ 5 thuật toán lập lịch ở pha tiếp theo.

---

## I. Bối Cảnh Bàn Giao & Phạm Vi Thay Đổi So Với `main` (`e261e42`)

### 1. Ranh giới bất biến của đợt cập nhật
* **Thư mục app sản phẩm [`group03-smartschedule-baseline/`](group03-smartschedule-baseline/README.md) giữ nguyên `0` thay đổi:** Toàn bộ 5 solver (`greedy_edf.py`, `greedy_wspt.py`, `greedy_lst.py`, `scored_greedy.py`, `backtracking.py`), `base_solver.py`, `local_repair.py`, web UI và API đều chưa đụng tới để không trộn lẫn việc **chuẩn hóa thước đo** với việc **nâng cấp thuật toán**.
* Toàn bộ thay đổi nằm ở `Testing_System/`, `Testing_Plan/` và các file quy chuẩn dự án (`AGENTS.md`, `CLAUDE.md`, tài liệu này).

### 2. Bảng kiểm kê tệp thay đổi (`git diff main --stat`: `9` file sửa `+775 / -226` dòng + `8` file mới)

| Nhóm | Tệp | Vai trò thay đổi so với `main` (`e261e42`) |
| :--- | :--- | :--- |
| **Evaluator (`v2.1`)** | [`Testing_System/schemas.py`](Testing_System/schemas.py) | Mở rộng `EvaluationConfig` (ngưỡng hiệu chỉnh `v2.1`), `Pillar2CognitiveBiology` (`APk%`, `OffP`, `Stk_L2`, `PCl`, `sjl_neutral_unpaired`), `Pillar3SustainablePacing` (`meal_l2`, `MaxD` tổng lớp+tự học, `TStd`, `Ctx`), `CrossSolverEntry`, và metadata cho Fuzz/Witness (`is_fuzz`, `fuzz_tier`, `persona_archetype`, `witness_verified`). |
| **Evaluator (`v2.1`)** | [`Testing_System/evaluator/pillars.py`](Testing_System/evaluator/pillars.py) | Nâng cấp `evaluate_p2`, `evaluate_p3`; thêm `_has_contiguous_peak_slot`, `_has_better_energy_window` (nhịp sinh học 2 chiều); vá bất biến đơn điệu sốc tại `_simulate_shock_survival` (`#L867-L880`). |
| **Evaluator (`v2.1`)** | [`Testing_System/evaluator/verdict_and_icee.py`](Testing_System/evaluator/verdict_and_icee.py) | Áp dụng bộ luật `v2.1` (xem Mục II.1); làm lại `rank_cross_solver_reports` theo **Cổng `#0` + 10 cấp Từ Điển có dung sai**, đặt `QUALITY-TIER` (`Verdict`) lên cấp `#1`; chuẩn hóa `FOCUS-FLOW` theo `study_days` và tách `INFO` khi `0% buffer` vẫn đạt `Shock@+25% >= 85%`. |
| **Evaluator (`v2.1`)** | [`Testing_System/evaluator/schedule_evaluator.py`](Testing_System/evaluator/schedule_evaluator.py) | Truyền `config` xuống `evaluate_p2`, `evaluate_p3`, đồng thời tính `diagnostics` trước `evaluate_verdict_and_critiques` để Cổng `#0` kiểm được SLA tốc độ `exec_ms > 1000ms`. |
| **Generator (`v2`)** | [`Testing_System/generator/fuzz_generator.py`](Testing_System/generator/fuzz_generator.py) *(Mới)* | Bộ sinh đề ngẫu nhiên vô hạn `FuzzGenerator v2` theo phương pháp **Plant-a-Witness**, hỗ trợ `7/14 ngày`, 4 mẫu hồ sơ thực tế, 3 mức tải (`LOOSE`/`TIGHT`/`OVERLOAD`) và khắc lời giải chứng từ `witness_blocks`. |
| **Generator (`v2`)** | [`Testing_System/generator/input_generator.py`](Testing_System/generator/input_generator.py), [`__init__.py`](Testing_System/generator/__init__.py) | Thêm `witness_blocks: Optional[List[ScheduleBlock]] = None` vào `GeneratedCaseBundle` và export `FuzzGenerator` / `FuzzTier`. |
| **Runner & CLI** | [`Testing_System/runner/pipeline_runner.py`](Testing_System/runner/pipeline_runner.py), [`__init__.py`](Testing_System/runner/__init__.py), [`cli.py`](Testing_System/cli.py) | Thêm `_check_fuzz_invariants`, `run_fuzz_case`, `run_fuzz_benchmark`, tích hợp kiểm định Witness + đơn điệu sốc + CLI `--mode fuzz --count N --start-seed S --tier auto\|LOOSE\|TIGHT\|OVERLOAD`. |
| **Tests (`31 → 39`)** | [`Testing_System/tests/test_v21_and_fuzz.py`](Testing_System/tests/test_v21_and_fuzz.py) *(Mới)* | Thêm 8 test tự động khóa các bất biến `v2.1`, công bằng cho học sinh/sinh viên, đơn điệu sốc, scale-invariant `Ctx`, controllability `P4.1`, `14d TIGHT`, và `LOOSE` Witness đạt `HIGH_PRODUCTIVITY`. |
| **Tài liệu & Quy chuẩn** | [`Testing_Plan/Problem_Statement_And_Checker_Spec.md`](Testing_Plan/Problem_Statement_And_Checker_Spec.md), [`Solver_Benchmark_Report.md`](Testing_Plan/Solver_Benchmark_Report.md), [`CT_Rationale_Log.md`](Testing_Plan/CT_Rationale_Log.md) *(Mới)* | Đặc tả đầy đủ bài toán, cơ chế sinh đề, bảng luật `v2.1`, phụ lục giải thích tiêu chí cho học sinh/sinh viên, kết quả benchmark 50 Fuzz + 120 Regimes, và nhật ký 13 lập luận Tư duy Tính toán. |
| **Workspace Rules & Handoff** | [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md), [`HANDOFF_SUMMARY_AND_NEXT_TASKS.md`](HANDOFF_SUMMARY_AND_NEXT_TASKS.md) *(Mới)* | Quy định đối chiếu số liệu thật, ghi log CT, giữ đủ 5 mục khi xuất báo cáo Benchmark, và tài liệu bàn giao này. |

---

## II. So Sánh `main (v1)` vs Hiện Tại (`v2.1 + Fuzz v2`) & Lý Do Từng Quyết Định Lớn

### 1. Nâng cấp Máy chấm: `Checker v1` (trên `main`) → `Checker v2.1`

Trên `main`, máy chấm đã có khung 3 tầng (`G1`/`G2`/`P1–P4`), nhưng chạy thực nghiệm đa phiên đã lộ **nghịch lý xếp hạng**, **kẽ hở Goodhart** *(thuật toán có thể lách để đạt điểm cao dù lịch phi lý)*, và **phạt oan theo độ dài tuần / đặc thù học sinh**:

| Khía cạnh | Trên `main` (`v1`) | Hiện tại (`v2.1`) | Lý do quyết định & Tác động thực tế |
| :--- | :--- | :--- | :--- |
| **Xếp hạng 5 thuật toán** | Thứ tự từ điển 11 cấp cứng từ `G1 -> P1.1 -> Shk25 -> Rec -> ForceAdv -> Peak -> <10h -> SJL -> Corne -> Std -> ms`; **không** đặt `Verdict` lên đầu và **không** có bậc dung sai. | **Cổng `#0` (`G1`, `exec_ms > 1000ms`) + 10 cấp Từ Điển có bậc dung sai (*epsilon-bucketed*)**, bắt đầu ngay bằng `#1 QUALITY-TIER (Verdict)` (`verdict_and_icee.py#L538-L630`). Giữ nguyên nguyên tắc **không quy về thang 100**. | Xóa triệt để nghịch lý trên `Regime 3` nơi `BACKTRACK` (`LOW`) từng xếp `#1` trên `SCORED_GREEDY` (`HIGH`) chỉ vì hơn `4.5p` `SJL` (`184.5p` vs `189.0p`). Sau `v2.1`: **`0/170` nghịch lý** (`120` Regimes + `50` Fuzz). |
| **`P2.1` Nhịp sinh học (`BIO-SYNC`)** | Chỉ đếm `forced_phase_advance_count` (ép Owl học sáng `06:00–12:00`) và `heavy_peak_match_pct` thô trên tổng `load=3`. | **(a)** `off_peak_heavy_mismatch_count`: đo 2 chiều cho **mọi chronotype** khi `load=3` rơi vào `energy=1` dù lưới phản chứng còn khe `avg_energy >= 2.0`; **(b)** `achievable_heavy_peak_match_pct` (`APk%`): chỉ tính mẫu số trên task còn khe Peak khả dụng. | Bảo vệ công bằng cả *Chim sớm* lẫn *Cú đêm*; không phạt oan học sinh THPT phải học chính khóa kín buổi sáng nên ít khe Peak trống. |
| **`P2.2` Nghỉ & Thông mạch (`BREAK-SAFE`)** | Đo nghỉ sau `load=3`; dễ phạt nhầm block đơn dài hoặc bỏ lọt chuỗi nhồi nhiều block `load=2` thông mạch. | Tách `max_multi_block_streak_l2_min` (`>= 2` block `load>=2` liên tiếp: `>120p WARN`, `>180p CRIT`) và `post_class_buffer_violations` (chừa `15p` sau lớp dài `>= 90p` trước `load=3`). | Chặn kẽ hở xếp 5–8 tiếng `load=2` không nghỉ, đồng thời không phạt oan block đơn `135p` hợp lệ. |
| **`P2.3` `SJL` & `P3.1` Cân bằng tuần** | `SJL = None` rơi về `0.0` khi xếp hạng (lách bằng cách học rải kiểu không bắt cặp ngày); chưa tách lệch pha sớm/muộn; `Std` chỉ tính giờ tự học. | Phân biệt `PHASE_ADVANCE > 60p` vs `PHASE_DELAY > 180p`; thêm `sjl_neutral_unpaired` (miễn phạt khi làm xong sớm nghỉ cuối tuần nhưng gán `90p` trung tính khi xếp hạng); đổi sang `total_daily_load_std_min` (**lớp + tự học**) với ngưỡng `max(180p, base_class_daily_std_min + 45p)`. | Bịt lỗ hổng `SJL=None -> 0.0`, không phạt oan sinh viên học lệch T2/T4/T6 có phương sai lịch lớp sẵn cao. |
| **`P3.2` Trần ngày & Chuyển ngữ cảnh** | Đếm kẹp bữa ăn chung; chưa giới hạn tổng **lớp + tự học** theo ngày; `focus_context_switches` dùng ngưỡng cố định dễ quá tải khi mở sang `14 ngày`. | Thêm `max_daily_total_min` (`lớp + tự học > 540p WARN / > 600p CRIT`); giới hạn kẹp bữa ăn ở `load>=2` (`meal_boundary_offenses_l2`); chuẩn hóa `FOCUS-FLOW` (`Ctx`) thành **`>= max(4, study_days)`**. | Ngăn lịch ngày cày `11–13h` gây kiệt sức, không gán nhầm việc nhẹ trước bữa ăn, và chuẩn hóa công bằng cho cả lịch `7 ngày` lẫn `14 ngày`. |
| **`USER-PREF` (Thói quen & Giờ riêng)** | Chưa có rào phạt riêng đủ mạnh khi solver cố ý bỏ `HABIT` hoặc phớt lờ `preferred_window`. | Khi tải nhẹ–vừa (`rho_total <= 0.85`): phạt `habit_value_rate_pct` (`<50% CRIT`, `<80% WARN`) và `preferred_window_match_pct` (`<50% WARN`). | Bịt kẽ hở solver "gian lận" vứt 100% thói quen cá nhân để dọn chỗ lấy `HIGH`, nhưng vẫn linh hoạt nhường bài thi khi tuần quá tải. |
| **`P4.1` Sốc `+25%` (`SHOCK-SAFE`)** | *(1)* `_simulate_shock_survival` quét va chạm từ `eff_start` nên nếu đầu block gốc lố đẩy quá sang bên kia rào `MEAL`/`OCCUPIED`, `Shock@+50%` có thể cao hơn `Shock@+25%` (`seed=1011, 1031`). *(2)* Input đặt `estimate_habit="RARELY"` (`0% buffer`) khiến mọi lịch tốt vẫn dính `WARNING`. | *(1)* Vá `_simulate_shock_survival` (`pillars.py#L867-L880`) quét suốt `range(b.start_slot, eff_end)`; *(2)* Theo nguyên lý **Khả kiểm (*Controllability*)**, nếu `true_buffer_task_pct == 0.0%` nhưng `Shock@+25% >= 85%` thì chỉ phát `INFO` (`verdict_and_icee.py#L381`). | Đạt **`50/50` đơn điệu `P1.1 >= Shock@+25% >= Shock@+50%`** trên Fuzz v2, và không hạ oan `Verdict` của thuật toán vì tham số đề bài. |

---

### 2. Bổ sung Bộ Sinh Đề Ngẫu Nhiên Vô Hạn: `FuzzGenerator v2` (*Plant-a-Witness*)

* **Hạn chế trên `main`:** `InputGenerator` chỉ có 6 Regimes chuẩn đối chứng (`R3–R6` mang tính kịch bản mẫu bán cố định, chỉ `R2` có `extra_pool` ngẫu nhiên một phần), làm thuật toán dễ "học vẹt" theo 6 mẫu; và nếu lọc đề ngẫu nhiên bằng 1 lượt chạy `EDF` sẽ thiên vị cho `EDF`.
* **Quyết định thiết kế trong [`fuzz_generator.py`](Testing_System/generator/fuzz_generator.py):**
  1. **Đa dạng thực tế & vô hạn theo `seed`:** Sinh từ 4 mẫu hồ sơ (`HIGH_SCHOOL_STUDENT`, `UNI_ASYMMETRIC`, `UNI_BUSY_WEEK`, `EXAM_PREP_WEEK`), `75%` là `7 ngày` / `25%` là `14 ngày`, mặc định `45% LOOSE` / `35% TIGHT` / `20% OVERLOAD`, chống chồng lấn ngủ–ăn–lớp ngay từ lúc dựng hồ sơ.
  2. **Kiến trúc ngược *Plant-a-Witness* (chứng minh điều kiện đủ không thiên vị):** Đặt trước `PersonalHabit` → khắc lời giải chứng từ $\pi^*$ trực tiếp lên các khe rảnh → suy ngược `deadline`, cạnh DAG `depends_on` (`0%` chu trình), `start_after` và `PINNED` rồi mới xáo trộn danh sách `tasks`.
  3. **Khắc chuẩn công thái học cho `LOOSE` (`strict_ergonomic=True`):** Lời giải chứng từ nhóm `LOOSE` giữ đồng thời nghỉ `15p` sau `load=3` (kể cả sát lớp học), tránh `energy=1`, trần ngày, ngắt chuỗi `load>=2`, chừa đệm phòng sốc `+25%` và gom môn — chứng minh trên thực nghiệm **`22 / 24` (`91.7%`)** Witness `LOOSE` đạt hẳn **`HIGH_PRODUCTIVITY`**.
  4. **Đủ tải thật cho `14 ngày` & `OVERLOAD` chuẩn xác:** Tự co giãn số lượng/thời lượng task theo sức chứa `usable_free_init` (giúp `14 ngày TIGHT` đạt `ρ ∈ [0.7067, 0.7749]`, khắc phục tình trạng `0.1453` khi mở rộng thô ở bản nháp); nhóm `OVERLOAD` bơm task hạn sớm tới `rho_dl >= 1.22` và `has_shortage=True`.
  5. **Tự kiểm chứng ở Runner:** [`_check_fuzz_invariants`](Testing_System/runner/pipeline_runner.py#L342-L426) bắt buộc lời giải chứng từ (nếu là đề khả thi) phải qua `ScheduleEvaluator` với `G1 == 0`, `P1.1 == 100%`, `not is_structurally_overloaded`, tách bạch lỗi của solver khỏi chất lượng đề.

---

## III. Bức Tranh Thực Nghiệm Đóng Băng (Baseline Hiện Tại Trước Khi Làm Lại Solver)

Các kết quả kiểm chứng đóng băng được lưu chi tiết tại [`Testing_Plan/Solver_Benchmark_Report.md`](Testing_Plan/Solver_Benchmark_Report.md):

1. **Độ tin cậy của hệ thống test (`Testing_System v2.1 + Fuzz v2`):**
   * `python -B -m pytest Testing_System/tests -v`: **`39 passed in 37.97s`** (`0` failed, `0` skipped — tăng từ `31` test trên `main`).
   * **Kiểm định lệch tier độc lập (`50 seeds × 3 tiers`):** `LOOSE` `0/50`, `TIGHT` `0/50`, `OVERLOAD` `0/50`.
   * **50 đề `FuzzGenerator v2` (`seeds 1001..1050`):** **`50/50` ALL PASS**, `0/250 INVALID`, `50/50` đơn điệu sốc, **`42/42` Witness đạt `G1=0, P1.1=100%`**, `0/50` nghịch lý; **`22/24` (`91.7%`)** Witness `LOOSE` đạt `HIGH_PRODUCTIVITY`.
   * **120 đề `6 Regimes` (`20 seeds × 6`):** **`120/120` PASS**, `0/600 INVALID`, `0/120` nghịch lý.

2. **Chẩn đoán 5 thuật toán nền tảng hiện tại (trên `50` đề Fuzz v2 — lý do cần "đập đi xây lại"):**

| Thuật toán | Hạng TB | `#1` | `P1.1%` TB | `Shk25%` TB | Verdict (`HIGH`/`LOW`/`SUBOPT`/`OVLD`/`INV`) | Điểm yếu cốt lõi từ thẻ đỏ `ICEE` |
| :--- | :---: | :---: | :---: | :---: | :--- | :--- |
| **`SCORED_GREEDY`** | **`2.14`** | **`19/50`** | `95.52` | **`78.31`** | `0 / 32 / 10 / 8 / 0` | Mạnh ở `LOOSE` (`15/24 #1`) & `OVERLOAD` (`3/8 #1`), nhưng **gãy `10/18 SUBOPT` ở `TIGHT`** (`AvgRk 3.06`) và dính **`91` thẻ đỏ `DAILY-CAP`**. |
| **`BACKTRACK`** | `2.24` | `13/50` | `96.08` | `76.34` | `0 / 42 / 0 / 8 / 0` | **`0/42 SUBOPT`** trên toàn bộ đề khả thi và dẫn đầu `TIGHT` (`10/18 #1`), nhưng chạy chậm nhất (`280.5ms` TB), dính **`96` `DAILY-CAP`** & `49` `BREAK-SAFE`. |
| **`EDF`** | `2.40` | `13/50` | **`96.49`** | `73.64` | `0 / 42 / 0 / 8 / 0` | **`0/42 SUBOPT`**, nhanh (`11.7ms` TB), nhưng mù sinh học (`APk 29.8%`, `Prf 33.0%`), **`100` `DAILY-CAP`** & `50` `BREAK-SAFE`. |
| **`WSPT`** | `3.36` | `5/50` | `94.17` | `73.86` | `0 / 23 / 19 / 8 / 0` | Đạt chuẩn `HIGH` ở **`0/50`**; rớt **`16/18 SUBOPT`** ở `TIGHT`, `100` `DAILY-CAP`. |
| **`LST`** | `4.86` | `0/50` | `81.45` | `58.59` | `0 / 9 / 33 / 8 / 0` | Rớt **`16/24 SUBOPT`** ngay ở `LOOSE` và **`17/18 SUBOPT`** ở `TIGHT`, dính `<10h=11.35%`. |

> **Kết luận đối chứng quan trọng nhất:** Ở 24 đề `LOOSE` của Fuzz v2, chính lời giải chứng từ Witness đạt **`22/24 HIGH_PRODUCTIVITY`**, còn cả 5 thuật toán cũ chỉ đạt **`0/24 HIGH_PRODUCTIVITY`** (`0/50` trên toàn bộ Fuzz). Khoảng cách đó 100% đến từ thiết kế solver hiện tại.

---

## IV. Hiện Trạng Toàn Bộ App & Lộ Trình Nhiệm Vụ Tiếp Theo Cho Teammate

### A. Những phần của App ĐÃ HOÀN THÀNH trên `main` (Teammate KHÔNG cần làm lại)

Theo trạng thái thực tế trong [`Proposal/Production_Readiness_And_Decision_Analysis.md`](Proposal/Production_Readiness_And_Decision_Analysis.md) và [`Proposal/Sync_Completion_Report.md`](Proposal/Sync_Completion_Report.md):
* **Nền tảng lưới & mô hình hóa (`group03-smartschedule-baseline/src/`):** Lưới `672` / `1344` slots (`horizon_days = 7..14`), bảo toàn cứng $H_1\text{–}H_5$, ngủ `>= 6h/đêm`, Dual Estimate Buffer (`COGNITIVE_LOAD 1.20/1.35` + `HABIT` + opt-out `NONE`), `PersonalHabit`, `start_after`, `work_rhythm`, `LocalRepairEngine` (`T04` ổn định), `OverloadTriageEngine` (`Q9` Phương án A), Experience Rating `1–5`.
* **Hybrid EN/VI NL Parser:** Gói [`NL_Parser_Package/`](group03-smartschedule-baseline/NL_Parser_Package/__init__.py) + [`src/nl_parser.py`](group03-smartschedule-baseline/src/nl_parser.py) hỗ trợ cả `Offline Deterministic` (`200/200` YAML cases) lẫn `Live Gemini API` (`.env` với `GEMINI_API_KEY`).
* **Web Workbench Dual-Mode (`web/` + `src/storage.py`):** Chế độ `STUDENT` & `LAB`, hiển thị ngày thực `DD/MM/YYYY` & tuần hiện tại, SQLite + `localStorage` persistence qua F5, kéo-thả `PINNED` (`/api/validate-move`), sửa lịch sự cố/overrun, M7 Check-in (`/api/tasks/complete`).
* **Các quyết định nhóm `Q1–Q10`:** Đã chốt đầy đủ trong [`Proposal/Production_Readiness_And_Decision_Analysis.md`](Proposal/Production_Readiness_And_Decision_Analysis.md) *(trên đó ghi nhận bộ kiểm thử baseline `verification_tests/clean_runner.py --all` đạt `155/155` trước đợt đóng băng `Testing_System`)*.

---

### B. Nhiệm vụ tiếp theo để hoàn thành App (Thứ tự ưu tiên `P0 → P3`)

#### `P0` — TRỌNG TÂM SỐ 1: Xây lại / Nâng cấp 5 Thuật Toán Lập Lịch (`src/solvers/`)

* **Phạm vi mã nguồn đích (trong `group03-smartschedule-baseline/`):**
  * [`src/solvers/base_solver.py`](group03-smartschedule-baseline/src/solvers/base_solver.py) *(hạ tầng xếp khe, tách mảnh, theo dõi tải theo ngày, scoring đặt block & two-tier rescue)*
  * [`src/solvers/scored_greedy.py`](group03-smartschedule-baseline/src/solvers/scored_greedy.py) *(thuật toán mặc định của Web UI & `/api/plan`)*
  * [`src/solvers/backtracking.py`](group03-smartschedule-baseline/src/solvers/backtracking.py), [`greedy_edf.py`](group03-smartschedule-baseline/src/solvers/greedy_edf.py), [`greedy_lst.py`](group03-smartschedule-baseline/src/solvers/greedy_lst.py), [`greedy_wspt.py`](group03-smartschedule-baseline/src/solvers/greedy_wspt.py), [`local_repair.py`](group03-smartschedule-baseline/src/solvers/local_repair.py), [`src/solvers/registry.py`](group03-smartschedule-baseline/src/solvers/registry.py), [`src/config.py`](group03-smartschedule-baseline/src/config.py)
  * **Lưu ý hợp đồng `Q10`:** Trong [`greedy_edf.py`](group03-smartschedule-baseline/src/solvers/greedy_edf.py) và `BaseScheduler.should_prefer_energy_placement()` hiện tách `EDF` làm đối chứng *Energy-Blind V0* cho bài test `T09` trong `verification_tests`. Khi nâng cấp 5 thuật toán mới, hãy quyết định rõ có giữ một alias/chế độ đối chứng V0 cho `verification_tests` hay cập nhật test đối chứng tương ứng để không làm vỡ hợp đồng báo cáo.

* **4 năng lực kỹ thuật bắt buộc phải thiết kế vào bộ solver mới** *(dựa trên phân tích thẻ đỏ `ICEE` tại [`Solver_Benchmark_Report.md#L161-L162`](Testing_Plan/Solver_Benchmark_Report.md#L161-L162) và [`Problem_Statement_And_Checker_Spec.md#L190-L207`](Testing_Plan/Problem_Statement_And_Checker_Spec.md#L190-L207)):*
  1. **Bộ đếm trần tải ngày & phân bố đều (`DAILY-CAP` & `PACE-BALANCE`):**
     * Theo dõi theo từng ngày: số ca `load=3` tối đa `<= 2`, tổng phút **`lớp + tự học <= 540p`** (trần cứng `<= 600p`), cấm hai block `load=3` sát nhau (`<= 1 slot`), tránh kẹp ngay trước & sau bữa `MEAL` với `load>=2`, và giữ `total_daily_load_std_min <= max(180p, base_class_daily_std_min + 45p)` cùng `SJL` trong ngưỡng (`ADVANCE <= 60p`, `DELAY <= 180p`).
  2. **Quản lý nghỉ & chống thông mạch (`BREAK-SAFE`):**
     * Chừa nghỉ `>= 15p` sau mỗi block `load=3` (lưu ý: tiết lớp ngay sau **không** được tính là nghỉ); giới hạn chuỗi `>= 2` block `load>=2` liên tiếp không nghỉ `<= 120p` (tuyệt đối `<= 180p`); và chừa đệm `15p` sau ca lớp dài (`>= 90p`) trước khi đặt `load=3`.
  3. **Sinh học 2 chiều, chống dồn `<10h`, gom môn & đệm sốc `+25%` (`BIO-SYNC`, `NO-CRAM`, `FOCUS-FLOW`, `SHOCK-SAFE`, `USER-PREF`):**
     * Khóa không đặt `load=3` vào `energy=1` nếu trên lưới còn khe `avg_energy >= 2.0` (`OffP = 0`), ưu tiên khớp khe `Peak` khả thi (`APk% >= 50%`); khởi phát sớm các task cửa sổ rộng (`<10h <= 25%`); gom block cùng `category` để giữ `Ctx < max(4, study_days)`; khi `rho_total <= 0.85` phải giữ `HABIT >= 80%` và `preferred_window >= 50%`; và tránh dồn sát block để giữ `Shock@+25% >= 85%`.
  4. **Pha cứu hạn đa tầng cho vùng `TIGHT` & `OVERLOAD` (*Feasibility-First Rescue*):**
     * Giải quyết triệt để lỗ hổng `10/18 SUBOPT` của `SCORED_GREEDY` ở vùng tải `TIGHT`: kết hợp lượt đặt chuẩn công thái học trước → nếu vẫn còn deadline khả thi bị rơi thì chạy pha cứu hạn có thứ tự *(tái sắp theo laxity/slack thực + chia mảnh hợp lệ theo khe hẹp + chỉ nới từng nấc ràng buộc mềm khi thật sự cần thiết để giữ `P1.1 = 100%`)*, giữ thời gian giải `<= 1000ms`.

* **Tiêu chí nghiệm thu (`Definition of Done`) cho `P0`:**
  1. `cd group03-smartschedule-baseline; python -B verification_tests/clean_runner.py --all` và `python -B benchmark_runner.py` vẫn xanh 100%, `C_hard = 0`, `3x Determ PASS`.
  2. `python -B -m pytest Testing_System/tests -v` tiếp tục **`39/39` passed**.
  3. Chạy lại toàn bộ benchmark (`--mode full --seeds 1..20` và `--mode fuzz --count 50 --start-seed 1001`):
     * `0 INVALID`, **`0 SUBOPT`** trên bộ solver mục tiêu (đặc biệt `SCORED_GREEDY` và `BACKTRACK`).
     * Đưa tỷ lệ **`HIGH_PRODUCTIVITY`** nhóm `LOOSE` từ **`0/24`** hiện nay lên mục tiêu cao tiệm cận giới hạn chứng từ (`22/24 = 91.7%` của Witness).
     * Cập nhật bảng số liệu mới + 5 mục chuẩn vào [`Testing_Plan/Solver_Benchmark_Report.md`](Testing_Plan/Solver_Benchmark_Report.md) theo Rule 2 của [`AGENTS.md`](AGENTS.md).

---

#### `P1` — Đồng bộ App UI/API & Tài liệu Kỹ thuật theo chuẩn `v2.1`

1. **Hiển thị chẩn đoán sức khỏe `v2.1` lên Student / Lab UI:**
   * Nối các chỉ số mới (`tổng tải lớp+tự học/ngày`, cảnh báo chuỗi `load>=2`, nhịp sinh học 2 chiều `OffP`/`APk%`, khả năng chịu sốc `+25%`, `Ctx`) qua [`src/controller.py`](group03-smartschedule-baseline/src/controller.py) → [`web/api.py`](group03-smartschedule-baseline/web/api.py) → [`web/app.js`](group03-smartschedule-baseline/web/app.js) / [`web/index.html`](group03-smartschedule-baseline/web/index.html).
   * **Lưu ý kiến trúc `INV-1..INV-6`:** Nếu tái sử dụng hàm chấm ở `Testing_System/evaluator/` hoặc viết bản đồng bộ trong `src/metrics.py`, tuyệt đối giữ tầng evaluator độc lập — không import web/FastAPI vào evaluator.
2. **Kiểm thử tay E2E Web UI (`http://127.0.0.1:8000`):**
   * Xác minh trực tiếp các luồng chính sau khi đổi solver: Student Mode (`7/14 ngày`, thêm/sửa/xóa task, `PersonalHabit`, kéo-thả `PINNED`, check-in `actual_duration_min`), Lab Mode (so sánh A/B 5 solver mới), Overload Triage, Local Repair, và Live Gemini `.env`.
3. **Cập nhật tài liệu người dùng:**
   * Làm mới [`Testing_System/README.md`](Testing_System/README.md) và [`README.md`](README.md) để phản ánh `Checker v2.1`, `--mode fuzz`, `39` pytest tests của `Testing_System` và kết quả bộ solver mới.

---

#### `P2` — Hoàn thiện Thực nghiệm Nhóm, Pilot 1 tuần & Slide Bảo vệ Đồ án

1. **Pilot 1 tuần & Calibration `α >= 1.7`:** Theo mục mở ở [`Proposal/Sync_Completion_Report.md#L157`](Proposal/Sync_Completion_Report.md#L157), thu log `actual_duration_min` thực tế qua SQLite Check-in M7 và bổ sung kịch bản tải cực hẹp `α >= 1.7` vào [`benchmark_alpha_grid.py`](group03-smartschedule-baseline/benchmark_alpha_grid.py).
2. **Cập nhật Slide gốc & Export `Proposal/Presentation2.pdf`:** Gỡ các placeholder còn sót trong slide PDF gốc *(nếu có từ file nguồn `.pptx` của nhóm)* và đưa bảng đối chiếu `Baseline V0 → V1/V2 (v2.1 + Fuzz v2)` kèm 13 lập luận trong [`Testing_Plan/CT_Rationale_Log.md`](Testing_Plan/CT_Rationale_Log.md) vào báo cáo cuối kỳ.

---

#### `P3` — Mở rộng SaaS Đa Người Dùng *(Tùy chọn hậu-V1 / Gói C)*

* Auth/OAuth2 + tách dữ liệu theo `user_id` trong SQLite/DB; siết `CORS`, Rate-Limiting & Quota AI; đồng bộ 2 chiều Google Calendar / LMS; Focus Timer (Pomodoro) nối tự động vào M7 Check-in; tự điều chỉnh hệ số buffer `α` cá nhân theo EWMA; Docker & GitHub Actions CI chạy tự động cả `verification_tests` lẫn `Testing_System/tests`.

---

## V. Cẩm Nang Bắt Tay Ngay Cho Teammate (Onboarding 5 Phút)

### 1. Thứ tự đọc tài liệu nhanh nhất
1. File này (`HANDOFF_SUMMARY_AND_NEXT_TASKS.md`) — nắm toàn cảnh thay đổi và việc cần làm.
2. [`AGENTS.md`](AGENTS.md) — **bắt buộc đọc** trước khi sửa số liệu hay viết báo cáo (quy định CT Log & cấu trúc 5 mục Benchmark Report).
3. [`Testing_Plan/Problem_Statement_And_Checker_Spec.md`](Testing_Plan/Problem_Statement_And_Checker_Spec.md) — đọc **Mục VI (`Acceptance Checklist v2.1`)** ở cuối file để lấy tiêu chuẩn đầu ra cho solver mới.
4. [`Testing_Plan/Solver_Benchmark_Report.md`](Testing_Plan/Solver_Benchmark_Report.md) — xem chi tiết từng cột điểm và lỗi `ICEE` mà 5 thuật toán cũ đang mắc phải.
5. [`Proposal/Production_Readiness_And_Decision_Analysis.md`](Proposal/Production_Readiness_And_Decision_Analysis.md) — xem các quyết định `Q1–Q10` và phần UI/Backend đã hoàn thành.

### 2. Các lệnh PowerShell thiết lập & chạy kiểm thử ngay

```powershell
# 1. Lấy nhánh bàn giao (KHÔNG làm việc trực tiếp trên main trước khi sẵn sàng PR)
git fetch origin
git checkout testing-system/v2.1-fuzz-handoff

# 2. Chạy bộ kiểm thử máy chấm + bộ sinh Fuzz v2 (đóng băng chuẩn 39/39)
python -B -m pytest Testing_System/tests -v

# 3. Benchmark nhanh 6 Regimes & Fuzz ngẫu nhiên với UTF-8 trên Windows
$env:PYTHONIOENCODING = "utf-8"
python -B -m Testing_System.cli --mode full --seeds 42
python -B -m Testing_System.cli --mode fuzz --count 10 --start-seed 1001
python -B -m Testing_System.cli --mode fuzz --tier LOOSE --count 10 --start-seed 2001

# 4. Kiểm tra hồi quy bộ test & benchmark gốc của App (trong group03-smartschedule-baseline/)
cd group03-smartschedule-baseline
python -B verification_tests/clean_runner.py --all
python -B benchmark_runner.py

# 5. Khởi chạy Web App cục bộ để test UI tại http://127.0.0.1:8000
python -m uvicorn web.api:app --host 127.0.0.1 --port 8000
```

> **Nhắc nhở môi trường:** Nếu dùng `.venv` do `setup_env.bat` tạo, nhớ kích hoạt `group03-smartschedule-baseline\.venv\Scripts\Activate.ps1` trước khi chạy `python` / `uvicorn` / `pytest`, và chỉ copy `.env.example` thành `.env` cục bộ khi cần test Live Gemini (không commit `.env` hay `data/*.db`).
