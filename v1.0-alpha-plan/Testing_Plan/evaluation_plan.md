# Kế Hoạch Xây Dựng Chương Trình Trung Gian Đánh Giá Lịch Cuối Cùng (`Member-in-the-Loop Evaluation Plan`)

> [!NOTE]
> Tài liệu này lập kế hoạch xây dựng **chương trình trung gian độc lập cho cả 7 thành viên Nhóm 03 (*The Seven Dwarfs*)** trực tiếp đánh giá thời khóa biểu đầu ra của **6 lựa chọn thuật toán** dựa trên đối chiếu hai tầng: **Chuẩn máy `Testing_System v2.1`** ([Problem_Statement_And_Checker_Spec.md](Problem_Statement_And_Checker_Spec.md)) và **Trải nghiệm người dùng thật (`UX-1..UX-6`)**, nhằm tìm ra điểm lệch giữa thuật toán và thực tế sinh viên trước khi chốt cấu hình mặc định.

---

## I. Bối Cảnh & Lý Do Cần Chương Trình Trung Gian

1. **Những gì bộ chấm tự động `v2.1` đã chứng minh:**
   * Trên **220 kịch bản** (`120` Regimes + `50` Fuzz `1001..1050` + `50` Unseen Fuzz `5001..5050` = `1.320` lượt chạy), bản nâng cấp V3 ([ultimate_plan.md](ultimate_plan.md), [Solver_Benchmark_Report.md](Solver_Benchmark_Report.md)) đã triệt tiêu `INVALID → 0`, `SUBOPT → 0`, đưa nhóm `LOOSE` từ `0/24` lên **`22–23/24` (`91.7%–95.8%`) `HIGH_PRODUCTIVITY`** trên Fuzz và **`25/25` (`100.0%`)** trên tập ẩn (`5001..5050`), giữ thời gian giải `<= 774.8 ms`.
2. **Khoảng trống còn thiếu (*Metric–Reality Gap*):**
   * Bộ chấm `Testing_System v2.1` đánh giá qua **kịch bản giả lập** (`InputGenerator` & `FuzzGenerator v2`) và **hàm mục tiêu proxy** (`TStd`, `Ctx`, `APk%`, `Shock@+25%`).
   * **Câu hỏi mở của người dùng & nhóm:** Một thời khóa biểu đạt `HIGH_PRODUCTIVITY` trên giấy có thật sự **hiệu quả cho đúng bộ task thực tế của từng thành viên** và **cho cảm giác dễ làm theo nhất** không (vd: kích thước tách mảnh có bị vụn, chuỗi chuyển môn giữa ngày có mệt, khung giờ chọn có khớp thói quen sinh hoạt ngoài đời)?
3. **Vai trò của Chương trình Trung gian:**
   * Đặt giữa **Solver Engine (`src/solvers/`)** và **Quyết định tinh chỉnh cuối cùng** một vòng lặp **Chấm Mù A/B có Cấu Trúc (*Blind Multi-Solver Human Evaluation*)**, nối trực tiếp phản hồi của **7 thành viên** vào việc hiệu chỉnh tie-breaker hoặc chọn thuật toán mặc định.

---

## II. Khối Lựa Chọn Thuật Toán Đem Ra Đánh Giá (`src/solvers/registry.py`)

Chương trình sử dụng nguyên bản **6 solver thật** đang đăng ký trong [`SOLVER_REGISTRY`](../group03-smartschedule-baseline/src/solvers/registry.py) *(truy xuất qua [`ScheduleController.solve_schedule()`](../group03-smartschedule-baseline/src/controller.py#L85-L98))*:

| Mã Solver | Tên lớp & Nhãn thực nghiệm | Nhóm sinh học (`Q10`) | Tốc độ thực đo (`Avg / Max ms`) | Vai trò trong chương trình đánh giá mù |
| :--- | :--- | :---: | :---: | :--- |
| **`EDF`** | `GreedyEDFSolver` *(V0 untouched)* | Energy-Blind V0 | `12.4–36.5` / `140.8 ms` | **Mốc đối chứng V0:** giúp thành viên tự cảm nhận sự khác biệt giữa "chỉ xếp kịp hạn" (`0/120 HIGH`) và lịch có nhịp sinh học. |
| **`SCORED_GREEDY`** | `ScoredGreedySolver` *(V3 Default)* | Energy-Aware | `263.1–442.3` / `739.2 ms` | **Ứng viên mặc định Web UI:** hạng TB dẫn đầu Regimes (`2.22`) & Unseen (`2.48`), nhanh nhất trong nhóm có nhịp sinh học. |
| **`HYBRID_ALNS`** | `HybridALNSSolver` *(V3 thứ 6, `ALNS`/`ULTIMATE`)* | Energy-Aware + ALNS | `539.4–625.7` / `774.8 ms` | **Ứng viên chất lượng cao nhất:** nhiều `HIGH_PRODUCTIVITY` nhất (`79/120` Regimes [`19/20 R1`], `22/24` Fuzz, `25/25` Unseen). |
| **`BACKTRACK`** | `BacktrackingSolver` *(V3 Live-State B&B)* | Energy-Aware + DFS | `331.3–478.9` / `680.8 ms` | **Đối chứng Nhánh–Cận:** mạnh nhất ở Fuzz (`23/24 HIGH`, `AvgRk 2.30`), so trực tiếp chất lượng cắt tỉa với `HYBRID_ALNS`. |
| **`WSPT`** | `GreedyWSPTSolver` *(V3 Smith Rule)* | Energy-Blind V3 | `101.8–268.8` / `582.5 ms` | **Đối chứng mù năng lượng (giữ ưu tiên):** kiểm tra riêng bài toán quá tải `OVERLOAD` (`R5: 74.1%`) khi không dùng đường cong năng lượng. |
| **`LST`** | `GreedyLSTSolver` *(V3 Least-Slack)* | Energy-Blind V3 | `96.3–237.1` / `464.3 ms` | **Đối chứng mù năng lượng (chống dồn hạn):** so cảm nhận thực tế về lịch dàn đều `TStd` (`109–129p`) khi không ưu tiên giờ đỉnh `Peak`. |

### Hai chế độ chọn bộ solver khi mở phiên đánh giá:
1. **Chế độ Đánh giá Chuẩn (`3 Blind Candidates` — khuyến nghị cho 100% thành viên):**
   * Chạy song song **`EDF`** + **`SCORED_GREEDY`** + **`HYBRID_ALNS`** *(tùy chọn thay/thêm `BACKTRACK` thành 4 lịch)*, tự động **ẩn tên thuật toán** và tráo thứ tự ngẫu nhiên theo `hash(seed, member_id)` thành **`Phương án #A` / `#B` / `#C`**.
   * *Lý do:* Mù tên giúp thành viên không thiên vị cái tên `"HYBRID_ALNS"` hay `"SCORED_GREEDY"`, chỉ đánh giá dựa trên lịch thật.
2. **Chế độ Phân tích Sâu (`All 6 Solvers`):**
   * Dành cho các ca khó (`TIGHT`, `OVERLOAD`, `Q10 MORNING vs EVENING`) để đội Algorithmic Design so sánh trọn vẹn cả 6 thuật toán cùng lúc.

---

## III. Bộ Tiêu Chí Đánh Giá Kép (`Machine v2.1` × `Human UX Scorecard`)

Chương trình đánh giá từng lịch hoàn chỉnh qua **2 tầng tách bạch** *(tuân thủ triết lý không quy về 100đ mù ở [CT_Rationale_Log.md](CT_Rationale_Log.md))*:

### 1. Tầng A — Chấm Tự Động Chuẩn `Testing_System v2.1` *(Khóa ẩn khi chấm mù, chỉ mở sau khi bấm Nộp)*
Gọi nguyên hàm `ScheduleEvaluator.evaluate()` từ [`Testing_System/evaluator`](../Testing_System/evaluator/schedule_evaluator.py) *(không chỉnh sửa checker)* để thu vector đầy đủ:
* **Cổng `#0` (`HARD-RULE`):** `G1 == 0` *(bảo toàn `H1–H5`, `PINNED`, `start_after`, `now_slot`, chia mảnh đúng luật, đủ phút)* và `exec_ms <= 1000 ms`.
* **10 Cấp Từ Điển `v2.1` & `Verdict`:**
  1. `#1 QUALITY-TIER` (`HIGH_PRODUCTIVITY` / `FEASIBLE_BUT_LOW_PRODUCTIVITY` / `OVERLOAD_TRIAGE` / `SUBOPTIMAL_ALGORITHM_FAILURE` / `INVALID`)
  2. `#2 DEADLINE-VAL` (`P1.1%` điểm `priority` kịp hạn)
  3. `#3 SHOCK-SAFE` (`Shk25%` sống sót dưới sốc `+25%`)
  4. `#4 BREAK-SAFE` (`Rec%` nghỉ `>10p` sau `load=3`, chuỗi `Stk` `load>=2`, đệm sau lớp dài `PCl`)
  5. `#5 BIO-SYNC` (`OffP` đặt `load=3` vào `energy=1`, `APk%` khớp giờ đỉnh khả thi)
  6. `#6 NO-CRAM` (`<10h%` dồn vô lý và trễ khởi phát `heavy_onset_delay`)
  7. `#7 DAILY-CAP` (`Crn` quá `2` nặng/ngày / cặp sát / kẹp bữa ăn `load>=2`, đỉnh `MxD <= 540/600p`)
  8. `#8 FOCUS-FLOW` (`Ctx` chuyển ngữ cảnh sát nhau `<= 2` slots)
  9. `#9 USER-PREF` (`Hab%` giữ thói quen & `Prf%` khung giờ riêng khi $\rho \le 0.85$)
  10. `#10 PACE-BALANCE` (`SJL` lệch pha lớp/nghỉ & `TStd` đều tải ngày)
* **Đi kèm Top 5 cảnh báo `ICEE`** giải thích lỗi bằng Tiếng Việt dễ hiểu.

### 2. Tầng B — Phiếu Chấm Trải Nghiệm Con Người (`UX-1..UX-6`) *(Thành viên chấm trên giao diện mù)*
Với mỗi phương án ẩn (`#A`, `#B`, `#C`), thành viên chấm **5 điểm thành phần (`1–5`)**, **1 lựa chọn thắng cuộc**, và **đánh dấu trực tiếp lên block lỗi**:

| Mã tiêu chí | Tên tiêu chí UX | Câu hỏi hướng dẫn cho thành viên khi soi lịch | Thang đo & Đối tượng liên hệ `v2.1` |
| :---: | :--- | :--- | :--- |
| **`UX-1`** | **Hiệu quả xử lý task (`Task Efficiency`)** | Thuật toán có xếp xong đủ các bài quan trọng/gấp đúng hạn, giữ đúng độ dài `duration_min` (sau buffer) và thứ tự tiên quyết `depends_on` mà bạn mong đợi không? | `1–5` · Đối chiếu `P1.1%`, `Verdict`, `unplaced_tasks` |
| **`UX-2`** | **Độ hợp nhịp năng lượng (`Energy & Window Fit`)** | Các phiên học nặng não (`load=3`) có rơi đúng khung giờ bạn thật sự tỉnh táo (`MORNING`/`AFTERNOON`/`EVENING`), còn thói quen cá nhân có nằm đúng khung giờ riêng không? | `1–5` · Đối chiếu `APk%`, `OffP`, `Prf%`, `Hab%` |
| **`UX-3`** | **Sức bền & Nhịp nghỉ (`Fatigue & Break Naturalness`)** | Lịch ngày có ngày nào bị nhồi quá sức, thiếu khoảng thở giữa ca lớp/bữa ăn, hoặc học liên tiếp quá mệt không? | `1–5` · Đối chiếu `MxD`, `Rec%`, `Stk`, `PCl`, `Crn` |
| **`UX-4`** | **Độ mượt chia mảnh & Chuyển môn (`Split & Flow`)** | Việc cắt nhỏ task (nếu có) và cách xen kẽ giữa các môn học trong cùng ngày có hợp lý với mạch tập trung của bạn ngoài đời hay bị vụn/nhảy cóc? | `1–5` · Đối chiếu `Ctx`, số chunk/ngày, `<10h%` |
| **`UX-5`** | **Tính khả thi & Chịu biến cố (`Real-World Resilience`)** | Nếu ngoài đời một việc bị lố giờ `30–45p` hoặc phát sinh việc đột xuất, bạn thấy tuần này có đủ khe đệm để tự cứu không? | `1–5` · Đối chiếu `Shk25%`, `TStd`, khoảng trống cuối ngày |
| **`UX-6`** | **Bỏ phiếu Mù & Gắn nhãn Block (`Blind Winner + Tags`)** | **1)** Chọn đúng 1 phương án bạn **thật sự muốn dùng làm lịch tuần này** (`#A / #B / #C`). **2)** Click trực tiếp vào các block gây khó chịu để gắn nhãn nguyên nhân. | Winner ID + Tags: `AWKWARD_SPLIT`, `BAD_TIME_OF_DAY`, `TOO_TIGHT_GAP`, `CONTEXT_JUMP`, `DAY_OVERLOAD`, `HABIT_MISPLACED`, `WRONG_PRIORITY` |

> [!IMPORTANT]
> **Nguyên tắc chống quy về điểm 100 mù:** Phiếu chấm giữ rời 5 điểm `UX-1..UX-5` + phiếu chọn mù `UX-6`. Điểm `Mean UX` chỉ dùng làm bộ lọc tổng quan; mọi quyết định sửa thuật toán phải đi từ **phương án thắng mù** và **cụm Block Tags bị gắn nhiều nhất**.

---

## IV. Kiến Trúc Chương Trình Trung Gian Đề Xuất (`member_eval/`)

Thiết kế thành một gói **hoàn toàn độc lập** tại `group03-smartschedule-baseline/member_eval/` để:
- **Giữ bất biến 100% `Testing_System/`** (chỉ import hàm đọc `ScheduleEvaluator`, `InputGenerator`, `FuzzGenerator`, `compare_solvers`).
- **Giữ bất biến `INV-1..INV-6`** (`src/solvers/` và `src/models.py` không import web hay module đánh giá này).

### 1. Sơ đồ luồng dữ liệu 3 bước
```text
[1. Bộ Kịch Bản Input]
   (a) Tuần thật của thành viên (JSON / NL Parser / Form)
   (b) Regimes đối chứng (R1, R2, R3, R5, R6)
   (c) FuzzGenerator v2 (LOOSE / TIGHT / OVERLOAD, 7/14 ngày)
          │
          ▼  (chạy qua ScheduleController.solve_schedule cho từng solver đã chọn)
[2. Blind Packet Builder]  ───(chấm ngầm & lưu riêng)──▶ [v2.1 Oracle Cache (Ẩn)]
   • Gán mã ẩn ngẫu nhiên (#A/#B/#C)
   • Xuất packet chỉ chứa lưới block + thông tin task (không lộ tên solver)
          │
          ▼
[3. Giao Diện Chấm Mù cho Thành Viên (Local Web Viewer / CLI Export)]
   • Xem lịch tuần (#A / #B / #C) song song + bộ lọc theo ngày/độ nặng
   • Click từng block để gắn Tags lỗi (UX-6) + chấm UX-1..UX-5 + ghi chú
   • Nút [Nộp & Mở Kết Quả] ──▶ Mở lộ tên thật + Bảng 11 tiêu chí v2.1 + Top ICEE
   • Lưu JSON chuẩn hóa vào `member_eval/reviews/<member_id>_<scenario>.json`
          │
          ▼
[4. Aggregator & Calibration Analyzer]
   • Tổng hợp toàn bộ file review của 7 thành viên
   • Lập Ma trận Đồng Thuận vs. Bất Đồng (`Human Vote` vs. `v2.1 Lex Rank`)
   • Sinh báo cáo `Calibration_Report.md` chỉ rõ cần chỉnh gì ở `ergonomic_engine.py`
```

### 2. Cấu trúc module đã triển khai (`group03-smartschedule-baseline/member_eval/`)
1. **[`member_eval/__init__.py`](../group03-smartschedule-baseline/member_eval/__init__.py) & [`member_eval/evaluate_schedule.py`](../group03-smartschedule-baseline/member_eval/evaluate_schedule.py):**
   * **Kho kịch bản chuẩn & tự nhập (`SCENARIO_CATALOG` + Custom JSON):** Gồm `PERSONAL_MINH`, `PERSONAL_LAN`, `REGIME_1_LOOSE..REGIME_5_OVERLOAD`, `FUZZ_LOOSE_14D (seed=1041)`, `FUZZ_TIGHT_7D (seed=1001)`, `FUZZ_OVERLOAD_14D (seed=1049)`, và lịch tự nhập `custom_payload`.
   * **`generate_blind_packet()`:** Chạy bộ solver (`BLIND_3`, `BLIND_4`, hoặc `ALL_6`), ẩn tên thuật toán thành `#A/#B/#C...`, xóa nhãn thuật toán trong chuỗi lý do block, tính trước bảng chấm `v2.1` + `Top ICEE` đưa vào `oracle_reveal`.
   * **`save_member_review()` & `aggregate_reviews()`:** Lưu từng phiếu chấm vào `member_eval/reviews/<member_id>_<scenario_id>.json` và tự động tổng hợp tỷ lệ thắng mù, `Mean UX`, tỷ lệ đồng thuận với `v2.1 #1`, các ca bất đồng, và tần suất `Block Issue Tags` ra `member_eval/Calibration_Report.md`.
   * **3 chế độ chạy (`--mode serve|cli|aggregate`):** Server HTTP thuần stdlib (`ThreadingHTTPServer` — tách khỏi `fastapi` để bảo vệ `INV-1`), CLI tương tác/tóm tắt, và lệnh tổng hợp báo cáo.
2. **[`member_eval/viewer.html`](../group03-smartschedule-baseline/member_eval/viewer.html):** Giao diện web nhẹ (`http://127.0.0.1:8010`) hiển thị thời khóa biểu theo cột ngày (`7/14 ngày`), cho phép click block để gắn nhãn `UX-6`, chấm điểm `UX-1..UX-5`, bỏ phiếu thắng mù, và mở khóa bảng 11 tiêu chí `v2.1` + `ICEE` ngay sau khi nộp.
3. **[`run_member_eval.bat`](../group03-smartschedule-baseline/run_member_eval.bat) & [`test_member_eval_program.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_member_eval_program.py):** File chạy 1 chạm cho mọi thành viên trên Windows và bộ test kiểm định tự động.

---

## V. Quy Trình Thực Nghiệm Cho 7 Thành Viên Nhóm 03 & Hành Động Cải Tiến

Theo phân công trong [`Proposal/work_division.pdf`](../Proposal/work_division.pdf):

### 1. Bài chấm tối thiểu cho mỗi thành viên (`7` người × `3` kịch bản = `21` phiên chấm mù)
Mỗi thành viên thực hiện độc lập theo 3 bước:
1. **Ca 1 — Lịch thật tuần này của chính bạn (`Personal Week`):** Nhập đúng lịch lớp, giấc ngủ, thói quen và `5–10` task thật trong tuần hiện tại → chấm mù `3` phương án `#A/#B/#C` (`EDF`, `SCORED_GREEDY`, `HYBRID_ALNS`).
2. **Ca 2 — Kịch bản Tải vừa (`LOOSE`):** Chấm mù 1 kịch bản có nhịp sinh học rõ (vd `R3` Cú đêm/Chim sớm hoặc `Fuzz LOOSE 14 ngày seed=1041`).
3. **Ca 3 — Kịch bản Nước rút / Quá tải (`TIGHT` hoặc `OVERLOAD`):** Chấm mù `Fuzz TIGHT seed=1001` hoặc `R5 OVERLOAD` (`6` solvers hoặc `EDF` vs `SCORED_GREEDY` vs `BACKTRACK` vs `HYBRID_ALNS`) để đánh giá thuật toán nào bỏ/xếp task thông minh nhất khi thiếu giờ.

### 2. Trách nhiệm phối hợp theo vai trò nhóm
| Thành viên | Vai trò ([`work_division.pdf`](../Proposal/work_division.pdf)) | Nhiệm vụ cụ thể trong vòng đánh giá trung gian |
| :--- | :--- | :--- |
| **Phạm Đức Minh** | Leader · Lead §9 *Evaluation Plan* | Phát packet chuẩn cho nhóm, kiểm tra đủ 21+ file review JSON, chủ trì chạy `aggregator.py` và tổng hợp bảng đối chiếu Máy vs. Người cho §9. |
| **Trần Nguyên Khánh** | Thinker 1 · Lead §6 *Algorithmic Design* | Phân tích các ca *Disagreement* giữa `SCORED_GREEDY` vs `HYBRID_ALNS` vs `BACKTRACK` để quyết định chỉnh tie-breaker hay heuristic xếp khe. |
| **Lê Tiến Bình** | Builder 1 · Lead §7 *System Architecture* | Bảo đảm `member_eval/` tách lớp sạch theo `INV-1..6` và thực thi chỉnh sửa trực tiếp vào [`ergonomic_engine.py`](../group03-smartschedule-baseline/src/solvers/ergonomic_engine.py) / [`registry.py`](../group03-smartschedule-baseline/src/solvers/registry.py). |
| **Nguyễn Trọng Tiến** | Thinker 3 · Lead §5 *Abstraction* | Kiểm tra xem có ràng buộc thực tế nào của sinh viên đang bị thiếu trong mô hình hóa (`Task`, `CommitmentsProfile`, `energy_profile`) từ tag `BAD_TIME_OF_DAY` / `HABIT_MISPLACED`. |
| **Nguyễn Nguyễn Gia Bảo** | Builder 3 · Lead §8 *Edge Cases & Trade-offs* | Gom toàn bộ ca biên phát sinh từ lịch thật của nhóm (trùng giờ đột xuất, `TIGHT`, `OVERLOAD`, chia mảnh bất hợp lý) để ghi nhận trade-off vào §8 và test hồi quy. |
| **Lê Minh Nhật** | Builder 2 · Lead §10 *From Design to Action* | Thiết kế/ráo soát UX phần hiển thị lịch chấm mù và đối chiếu xem lý do `ICEE` có đủ dễ hiểu với sinh viên bình thường hay cần viết lại rõ hơn. |
| **Hoàng Minh Anh** | Thinker 2 · Lead §11 *Conclusion* | Tổng kết bằng chứng thực nghiệm hai chiều (Máy `v2.1` + Người thật Nhóm 03) để chốt kết luận đánh giá hiệu năng & trải nghiệm người dùng cho báo cáo cuối kỳ. |

---

## VI. Luật Chốt Thuật Toán & Vòng Lặp Cải Tiến Sau Khi Thu Review

Sau khi chạy `aggregator.py` trên dữ liệu của cả 7 thành viên, nhóm áp dụng **3 quy tắc quyết định rõ ràng**:

1. **Khi Người & Máy Đồng Thuận (`SCORED_GREEDY` / `HYBRID_ALNS` thắng mù `>= 70%` và `Mean UX >= 4.0/5` trên tuần thật + `LOOSE`):**
   * Giữ **`SCORED_GREEDY`** làm mặc định cho chế độ tương tác nhanh trên Web (`~263–442 ms` TB) và cung cấp **`HYBRID_ALNS`** (tùy chọn *"Tối ưu sâu / Deep Optimize"*, `max <= 774.8 ms`) trên giao diện.
2. **Khi có Cụm Phàn Nàn Thực Tế (*Friction Cluster* — cùng một `Block Tag` chiếm `>= 25%` số lượt đánh dấu):**
   * `AWKWARD_SPLIT`: điều chỉnh ưu tiên `opts[0]` (ít tách mảnh hơn) và phạt phân mảnh trong `score_candidate_unit` của [`ergonomic_engine.py`](../group03-smartschedule-baseline/src/solvers/ergonomic_engine.py).
   * `CONTEXT_JUMP`: tăng nhẹ trọng số phạt chuyển môn liên tiếp trong `score_candidate_unit` (hiện `Ctx` đứng ở cấp `#8`, sau `#7 DAILY-CAP`).
   * `BAD_TIME_OF_DAY` / `HABIT_MISPLACED`: rà soát lại cách chia cửa sổ `MORNING`/`AFTERNOON`/`EVENING` hoặc phạt `preferred_window` ở bước xây dựng lịch ban đầu.
3. **Khi Có Xung Đột Giữa Người Thật và Thước Đo `v2.1` (`Disagreement > 20%`):**
   * Chỉ cập nhật trọng số/thứ tự tie-breaker bên trong `group03-smartschedule-baseline/src/solvers/` rồi chạy lại đủ bộ kiểm định (`clean_runner.py --all`, `pytest Testing_System/tests -v`, và benchmark 220 kịch bản) để bảo đảm **trải nghiệm tốt hơn nhưng không làm vỡ chuẩn an toàn `G1 = 0`, `0 SUBOPT`, `<= 1000 ms`**.

---

## VII. Hướng Dẫn Chạy Nhanh Chương Trình Trung Gian

* **Cách 1 — Giao diện Web 1 chạm cho mọi thành viên (`http://127.0.0.1:8010`):**
  * Chạy [`run_member_eval.bat`](../group03-smartschedule-baseline/run_member_eval.bat) *(hoặc `python -B group03-smartschedule-baseline/member_eval/evaluate_schedule.py --mode serve --port 8010`)*.
* **Cách 2 — Chế độ dòng lệnh (CLI) cho từng kịch bản / tổng hợp báo cáo nhóm:**
  * Chấm & đối chiếu 1 kịch bản trên terminal: `python -B group03-smartschedule-baseline/member_eval/evaluate_schedule.py --mode cli --scenario PERSONAL_MINH --member 25125028 --interactive`
  * Tổng hợp toàn bộ phiếu chấm đã thu: `python -B group03-smartschedule-baseline/member_eval/evaluate_schedule.py --mode aggregate`
