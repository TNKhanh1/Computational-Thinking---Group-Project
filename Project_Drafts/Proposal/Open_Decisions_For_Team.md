# Danh Sách Các Điểm & Thông Số Chưa Chốt — Cần Nhóm Thảo Luận & Quyết Định

> **Mục đích:** Tổng hợp toàn bộ các tham số thuật toán, xung đột giữa tài liệu thiết kế (`Presentation2.pdf`, `Proposal_Report.pdf`, `Improve_Plan`) với mã nguồn (`main` → `ltbinh/sync-proposal` → `M1-NL-Parser`) để trình bày và thống nhất với các thành viên Nhóm 03.
>
> **Nhánh & Tài liệu hợp nhất:** `M1-NL-Parser` (**ĐÃ CHỐT TOÀN BỘ `☑ Q1–Q10`** và hoàn tất cả Cột mốc 1 lẫn `Q10` Nhịp 2). Phân tích chuyên sâu & lộ trình Mốc 2 (bao gồm kế hoạch tối giản Modal Thêm Việc ở `STUDENT` vs `LAB` Mode) xem tại [`Proposal/Production_Readiness_And_Decision_Analysis.md`](Production_Readiness_And_Decision_Analysis.md) và [`Proposal/Sync_Completion_Report.md`](Sync_Completion_Report.md).

---

## Tóm tắt nhanh các hạng mục quyết định (`Q1–Q10`) — Nhánh `M1-NL-Parser` (ĐÃ CHỐT)

| Mã | Hạng mục | Nguồn xuất hiện | Mức độ ảnh hưởng | Quyết định ĐÃ CHỐT (`17/11/2026`) |
| :--- | :--- | :--- | :--- | :--- |
| **Q1** | Hệ số buffer **`α`** & tiêu chí chọn `α` theo **Habit** vs **Cognitive Load** | `Presentation2.pdf` Slide 7, 17 vs `src/estimate_buffer.py` | **Cao** | **☑ ĐÃ CHỐT:** Giữ Dual-Mode; Student UI mặc định `COGNITIVE_LOAD` (`1.20/1.35`, `RoundUp_15`), giữ `"HABIT"` V0 fallback ở `CommitmentsProfile`; dùng hàm `composite` sẵn có trong `benchmark_alpha_grid.py` (`Q1.3`) + pilot 7 ngày + stress `α >= 1.7`. |
| **Q2** | Hằng số suy giảm **`γ`** & giá trị biên `Urgency` cho `Habit` / `Overdue` | `Presentation2.pdf` Slide 8 (`exp(-slack / γ)`) vs `Proposal_Report.pdf` (`24`) | **Cao** | **☑ ĐÃ CHỐT:** `γ = 24.0` giờ; `OVERDUE_URGENCY_CAP = 1.50` (+ tie-breaker); `HABIT_BASE_URGENCY = 0.20`; sửa nhãn Slide 8 thành *Exponential Urgency*. |
| **Q3** | **Pattern 3 (Circadian Matching):** Cứng (`strictly`) hay Mềm (`Soft`)? | `Presentation2.pdf` Slide 7 vs Slide 9 | **Cao** | **☑ ĐÃ CHỐT:** Cơ chế **MỀM đa tầng** (ưu tiên Level-3 Peak → fallback Level-2 trước hạn → Crunch Level-1), bỏ *"strictly"* trên Slide 7. |
| **Q4** | Ngưỡng ổn định **`X%`** khi sửa lịch (`Schedule Stability`) | `Presentation2.pdf` Slide 5 & 8 (`>= X%`) | **Trung bình** | **☑ ĐÃ CHỐT:** **`X = 90%`** (`STABILITY_TARGET_PCT = 90.0`, `T04` đạt `100.00%`). |
| **Q5** | **M1 NL Parser:** Dùng LLM API hay Deterministic Parser (offline)? | `Presentation2.pdf` Slide 10 (`M1: LLM`) vs `src/nl_parser.py` | **Trung bình** | **☑ ĐÃ CHỐT & KIỂM CHỨNG LIVE:** Hybrid Dual-Engine (`Offline` 6 tầng tất định làm lõi + Gemini AI xem trước `#stTaskModal` có User xác nhận — LoA Level 4, giữ Solver SHA-256). Đã thêm `ai_status`, `17:00`, relative import; Mốc 2 thêm Progressive Disclosure tối giản `#stTaskModal` ở `STUDENT` Mode. |
| **Q6** | Nghỉ **15p (`Pattern 2`)**, khe **dead-zone `< 30m` (`Pattern 5`)** & **auto-split `> 90m`** | `Presentation2.pdf` Slide 7, 8, 16 vs `src/models.py` & `t03` | **Cao** | **☑ ĐÃ CHỐT (`Q6.2 = A2`):** Giữ nghỉ `15p` sau block `>= 90p` hoặc `Load >= 3` trên ô `FREE`; khóa mọi dead-zone `<= 1 slot` kể cả `Load-1` ở lượt thường, chỉ mở ở Tier-1 Crunch; auto-split `> 90p` trừ `False`. |
| **Q7** | Công thức **`Experience Rating (1-5)`**, **`Category Batching`**, **`PersonalHabit`** & pilot 1 tuần | `Presentation2.pdf` Slide 6, 7, 17 | **Trung bình** | **☑ ĐÃ CHỐT (`Q7.3 = A3`):** Lock hàm 4 thành phần `[1..5]` & batching `+0.35/-0.25` cho v1.0; `PersonalHabit` dùng **`1 preferred_window + frequency_per_week`** (dàn đều theo tuần, mở UI ở Mốc 2) + pilot 1 tuần. |
| **Q8** | Quy trình hợp nhất nhánh, cập nhật `Proposal/` & `Presentation2.pdf` | Git `M1-NL-Parser` vs `main` | **Rất cao** | **☑ ĐÃ CHỐT:** Đã hoàn tất toàn bộ Cổng Pre-Merge (test tay UI, Live Gemini, `147/147` tests, cập nhật `Proposal/`) -> sẵn sàng Merge PR #4 vào `main`; sau đó cập nhật `Presentation2.pdf` và sang Mốc 2. |
| **Q9** | **Sprint Mode Tier 1** có tự nén thời lượng task gốc (`90m -> 75m`) không? | `test_scheduling_edge_cases.py` (`#113`) | **Cao** | **☑ ĐÃ CHỐT & ÁP DỤNG PHƯƠNG ÁN A:** Tier-1 chỉ cắt nghỉ/dead-zone (`allow_breaks=False`), không tự cắt task gốc; rút ngắn phải qua Triage `SHORTEN_TASK` xác nhận + `Early Extension Alert`. Suite `--all` đạt `147/147 PASS`. |
| **Q10** | Tách **`EDF` V0 (Energy-Blind)** vs **`SCORED_GREEDY`** & mặc định Web UI | `base_solver.py` vs `web/index.html`, `web/app.js`, `web/api.py`, `local_repair.py` | **Cao** | **☑ ĐÃ HOÀN TẤT CẢ 2 NHỊP:** (1) UI & `/api/plan` mặc định **`SCORED_GREEDY`**; (2) `EDF`/`LST`/`WSPT` thuần Energy-Blind trên `T09` (`4268107a006d` cố định vs `SCORED_GREEDY` dịch Peak), `--gaps` dùng `SCORED_GREEDY`, `_repair_full_rebuild()` giữ đúng solver qua `src/solvers/registry.py`. |

---

> **Ghi chú trạng thái đồng bộ & báo cáo đầy đủ:** Xem báo cáo kỹ thuật, các bản vá kiểm toán sau đồng bộ và kết quả chạy thực nghiệm tại [`Proposal/Sync_Completion_Report.md`](Sync_Completion_Report.md).

## Chi tiết từng vấn đề cần nhóm thảo luận

### Q1. Tham số Planning Fallacy Buffer `α` (Slide 7 & Slide 17)
* **Mâu thuẫn hiện tại:**
  * `Presentation2.pdf` Slide 7 & 17 định nghĩa `Planned_Duration = RoundUp_15(Estimated_Duration × α)` theo **độ nặng (`cognitive_load`)** với giá trị khởi tạo chưa kiểm chứng *(Unverified)*: `α_light/medium = 1.20`, `α_heavy = 1.35`.
  * Codebase trên `main` (`src/estimate_buffer.py`) lại tính theo **thói quen ước lượng (`estimate_habit`)**: `RARELY = 1.0`, `SOMETIMES = 1.1`, `OFTEN = 1.25` (mặc định `None = 1.0`) và làm tròn *gần nhất* 15p (`nearest_15`), đang được bảo vệ bởi bộ unit test `test_estimate_buffer.py`.
  * Ngoài ra `web/app.js` còn tự nhân thêm `1.2` ở frontend gây lỗi **nhân đôi buffer (Double-Buffering)**.
* **Slide 17 còn nêu 2 bước Planned chưa làm:**
  1. **1D Grid Search:** Quét `α ∈ [1.00, 1.60]` bước `0.05` trên các kịch bản tuần mô phỏng để cân bằng giữa phút trễ (`late minutes`) và buffer dư thừa (`wasted idle buffer time`).
  2. **Stress Test & Real Calibration:** Thử nghiệm với sốc overrun `+25%` và `+50%`, rồi đo tỷ lệ thật `Actual / Estimated` qua 1 tuần dùng thử của nhóm.
* **Trạng thái & Cần nhóm chốt:**
  1. **Mặc định Student UI vs V0 Fallback:** Khuyến nghị mặc định tầng Student UI sang **`COGNITIVE_LOAD` (`1.20 / 1.35`)**, giữ `"HABIT"` tại `CommitmentsProfile` V0 (`src/models.py`) + nút opt-out `NONE` từng task.
  2. **Làm tròn:** Dùng **`RoundUp_15`** trong `COGNITIVE_LOAD` (bảo đảm `+1 slot` cho micro-task), giữ `Nearest_15` cho `HABIT`.
  3. **`Q1.3` Hàm mục tiêu `Loss(α)`:** `benchmark_alpha_grid.py` đã cài sẵn hàm `composite = 0.35*avg_dl + 0.25*avg_s25_dl + 0.20*avg_s50_dl + 0.20*avg_s25_zero - 4.0*max(0, avg_rating-2.0) - 2.0*avg_frag - 100.0*hard_violations` (đã quét `1.00–1.60`). Nhóm chỉ cần xác nhận công thức này, bổ sung stress-test `α >= 1.7` và phân công log `actual_duration_min` trong 1 tuần thử nghiệm ở Mốc 2.

---

### Q2. Hằng số `γ` & Biên hàm ưu tiên trong Pattern 7 (`Slide 8 & 16`)
* **Chưa chốt trên Slide 8:** `Urgency = exp(-slack / γ) × Importance` để ẩn `γ` chưa ghi con số.
* **Điểm biên chưa định nghĩa:**
  * Nếu `slack <= 0` (sát hoặc trễ hạn): hàm `exp(-slack / γ)` tăng vọt nếu giữ số âm.
  * Nếu là **Personal Habit** (`deadline = None`, `slack = +∞`): `exp(-∞) = 0` → `Score = 0`, khiến mọi thói quen luôn bị xếp cuối hoặc không bao giờ vào lịch dù có `priority_weights`.
* **Cần nhóm chốt:** Xác nhận giá trị `γ` (đề xuất `24h` theo `Proposal_Report.pdf`), ngưỡng kẹp trần quá hạn (`1.5`), và điểm urgency cơ sở cho `Habit` (`0.20`).

---

### Q3. Pattern 3 (Circadian Energy Matching): Cứng (`strictly`) hay Mềm (`Soft`)? (`Slide 7` vs `Slide 9`)
* **Mâu thuẫn ngay trong `Presentation2.pdf`:**
  * Slide 7 ghi: *"Assign **Load-3 (Deep Work) strictly to Level-3 (Peak Energy) slots**; assign Load-1 tasks to Low-Energy slots."*
  * Slide 9 cột *1. Problem Nature* lại phân loại: *"Hard: Fixed slots & ≥6h sleep | **Soft: Circadian energy match**."*
* **Hệ quả kỹ thuật:** Nếu ép cứng 100%, sinh viên có 6 giờ bài nặng (`Load-3`) nhưng chỉ cài Peak Energy `3 giờ/tuần` thì 3 giờ bài tập kia **không được xếp lịch và rớt deadline**, dù các buổi khác vẫn rảnh hoàn toàn.
* **Cần nhóm chốt:** Đồng ý cơ chế **2 tầng (Soft ưu tiên cao → Fallback sang Level-2 trước deadline → chỉ xuống Level-1 khi Crunch Mode)** thay vì chặn cứng tuyệt đối.

---

### Q4. Ngưỡng Stability `X%` trong Pattern 8 (`Slide 5` & `Slide 8`)
* **Chưa chốt trên Slide:** Cả Slide 5 và Slide 8 viết *"keeping `X%` unchanged / stability `>= X%`"*.
* **Cần nhóm chốt:** Chốt số **`X = 90%`** để đồng bộ giữa `Presentation2.pdf`, `Proposal_Report.pdf` và test `test_local_repair_vs_full_rebuild_stability`.

---

### Q5. Module M1 (`Natural Language Parser (LLM)`) (`Slide 10`)
* **Trạng thái hiện tại:** Đã nâng cấp lên Dual-Engine Hybrid (`src/nl_parser.py` + `NL_Parser_Package/`): **Offline 6 tầng tất định** (`200/200` YAML trong `616.5 ms`) kết hợp **Gemini Live API** (`gemini-3-flash-preview`, đã kiểm chứng chạy thật `17/11/2026`, `200 OK`, `ai_status="ACTIVE"`). Ở bước Cột mốc 1 đã vá thêm relative import `__init__.py`, `ui.attachments: list[str]`, cảnh báo `validation["ai_status"]` rõ ràng và giữ mốc giờ buổi (`sáng/trưa/chiều/tối`).
* **Khuyến nghị chốt:** Duy trì kiến trúc **LoA Level 4** (AI/Hybrid chỉ điền nháp `#stTaskModal` cho người dùng xác nhận trước khi vào Solver để giữ **Pure Determinism SHA-256** Slide 12) và mở tùy chọn engine cho Lab Mode ở Mốc 2.

---

### Q6. Ranh giới kỹ thuật của Pattern 2, Pattern 5 & Cờ `is_splittable` (`Slide 6, 7, 8, 13, 16`)
1. **Pattern 2 (15m REST):** Áp dụng sau block `>= 90p` hoặc `cognitive_load >= 3`, chỉ chiếm ô `FREE` (tự miễn nếu liền sau đã là `SLEEP`/`MEAL`/`OCCUPIED`).
2. **Pattern 5 (`< 30m` Dead-zone `STATE_REST` — ĐÃ CHỐT `Q6.2 = A2`):** Khóa mọi khe hở `<= 1 slot` (`15p`) kể cả với tác vụ nhẹ `Load-1` trong lượt xếp thường (`allow_breaks=True`) để tránh phân mảnh và dư lượng chú ý; tự mở khóa ở Tier-1 Crunch (`allow_breaks=False`).
3. **Auto-split task `> 90 phút`:** Mặc định bật `is_splittable = True` khi `duration_min > 90p`, nhưng vẫn tôn trọng tuyệt đối nếu người dùng khóa `is_splittable = False`.

---

### Q7. Công thức `Experience Rating (1-5)` (`Slide 6`) & Trọng số `Category Batching` (`Slide 7`)
* **`Experience Rating (1-5)`:** Khóa công thức 4 thành phần chuẩn hóa `[1.0..5.0]` (`density 0..2.2`, `streak 0..0.8`, `circadian 0..0.6`, `overload 0..1.0`).
* **`Category Batching`:** Chốt `CATEGORY_BATCH_BONUS = 0.35`, `CONTEXT_SWITCH_PENALTY = 0.25` (~7.5–15% biên độ Circadian `Load-3`, chỉ làm mượt lịch chứ không đảo deadline).
* **`Personal Habits` (`Slide 6` — ĐÃ CHỐT `Q7.3 = A3`):** Giữ mô hình gọn **`1 preferred_window` (`MORNING | AFTERNOON | EVENING`) + `frequency_per_week`** (tự dàn đều giữa các ngày trong tuần khi nối `preferred_window` vào `expand_personal_habits()` và mở form UI Student Mode ở Mốc 2).

---

### Q8. Quy trình chốt hợp nhất nhánh và cập nhật `Proposal/` + `Presentation2.pdf`
* Nhánh tích hợp hiện tại là `M1-NL-Parser` (đã port `overload_triage` + tích hợp `NL_Parser_Package/` + hoàn tất vá kỹ thuật Pre-Merge và cập nhật bộ tài liệu `Proposal/`). Sau khi nhóm duyệt `Q1–Q10` và kiểm thử thủ công UI trình duyệt thật sẽ Merge PR #4 vào `main`, rồi dọn sạch `(Unverified)`, `(Planned)`, `≥ X%`, `γ` trên `Presentation2.pdf`.

---

### Q9. Cơ chế nén thời lượng ở Tier-1 Sprint Mode (`test_fail_edge_sprint_mode_compression_recovery`)
* **Quyết định ĐÃ CHỐT & ÁP DỤNG (Phương án A):** Không bao giờ tự co ngắn thời lượng thô (`90p -> 75p`) của task người dùng nếu chưa có xác nhận. Tier-1 Sprint Mode chỉ tự cắt nghỉ 15p / dead-zone (`Cut breaks`), còn thiếu chỗ buộc phải qua **Overload Triage (`SHORTEN_TASK`)** + `Early Extension Alert`. Bài test `test_fail_edge_sprint_mode_compression_recovery` đã được cập nhật đúng spec Phương án A và toàn bộ **`clean_runner.py --all` đạt `146 Passed | 0 Failed`**.

---

### Q10. Tách rạch ròi Baseline `EDF` vs `SCORED_GREEDY` (`T09`) & Solver mặc định Web UI
* **Trạng thái (✅ ĐÃ HOÀN TẤT CẢ 2 NHỊP):**
  * **Nhịp 1:** Đã chuyển mặc định `#solverSelect`, `#stSetSolver`, `#kpiSolverLabel` trên Web UI (`web/index.html`, `web/app.js`) và `POST /api/plan` (`web/api.py#L67`) sang **`SCORED_GREEDY`** (`solver_used == "SCORED_GREEDY"`).
  * **Nhịp 2:** Đã tách `EDF`/`LST`/`WSPT` về thuần **Energy-Blind V0** (`BaseScheduler.should_prefer_energy_placement -> False`, giữ `SCORED_GREEDY` & `BacktrackingSolver` tối ưu Circadian + Batching, kiểm chứng trên `benchmark_runner.py` Bảng 5 `T09`), cập nhật `test_improve_plan_gaps.py` dùng `SCORED_GREEDY`, và dùng [`src/solvers/registry.py`](../group03-smartschedule-baseline/src/solvers/registry.py) để `LocalRepairEngine._repair_full_rebuild()`, `compare_repair_modes()` và `POST /api/repair` giữ đúng solver hiện hành.

