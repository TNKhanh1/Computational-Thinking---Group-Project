# Danh Sách Các Điểm & Thông Số Chưa Chốt — Cần Nhóm Thảo Luận & Quyết Định

> **Mục đích:** Tổng hợp toàn bộ các tham số thuật toán, xung đột giữa tài liệu thiết kế (`Presentation2.pdf`, `Proposal_Report.pdf`, `Improve_Plan`) với mã nguồn (`main` vs `origin/hmanh`) để trình bày và thống nhất với các thành viên Nhóm 03.
>
> **Nhánh đối chiếu & thử nghiệm:** `ltbinh/sync-proposal` (xuất phát từ `main` `4c0a85a`).

---

## Tóm tắt nhanh các hạng mục cần nhóm biểu quyết

| Mã | Hạng mục chưa chốt | Nguồn xuất hiện | Mức độ ảnh hưởng | Mặc định tạm thời đề xuất để chạy thử |
| :--- | :--- | :--- | :--- | :--- |
| **Q1** | Hệ số buffer **`α`** & tiêu chí chọn `α` theo **Habit** vs **Cognitive Load** | `Presentation2.pdf` Slide 7, 17 vs `src/estimate_buffer.py` | **Cao** (trực tiếp đổi thời lượng block & overload) | Chạy song song 2 chế độ: giữ `estimate_habit` khi bật, mặc định Load 1–2 = `1.20`, Load 3 = `1.35` + chạy 1D Grid Search |
| **Q2** | Hằng số suy giảm **`γ`** & giá trị biên `Urgency` cho `Habit` / `Overdue` | `Presentation2.pdf` Slide 8 (`exp(-slack / γ)`) vs `Proposal_Report.pdf` (`24`) | **Cao** (thứ tự ưu tiên trong `SCORED_GREEDY`) | `γ = 24.0` giờ; `slack <= 0` kẹp về trần `1.5`; Habit không deadline = `0.20` |
| **Q3** | **Pattern 3 (Circadian Matching):** Cứng (`strictly`) hay Mềm (`Soft`)? | `Presentation2.pdf` Slide 7 vs Slide 9 | **Cao** (có thể gây rớt deadline nếu khóa cứng) | Mô hình 2 tầng: bình thường ưu tiên Peak Energy (Level-3), fallback Level-2 trước khi trễ hạn; Crunch mới hạ xuống Level-1 |
| **Q4** | Ngưỡng ổn định **`X%`** khi sửa lịch (`Schedule Stability`) | `Presentation2.pdf` Slide 5 & 8 (`>= X%`) | **Trung bình** (tiêu chí PASS cho M4 Local Repair) | Chốt **`X = 90%`** (khớp `Proposal_Report.pdf` & `benchmark_runner.py` T04) |
| **Q5** | **M1 NL Parser:** Dùng LLM API hay Deterministic Parser (offline)? | `Presentation2.pdf` Slide 10 (`M1: LLM`) vs `web/app.js` & `web/api.py` | **Trung bình** (chạy offline khi demo/chấm tự động) | Hybrid: Backend Deterministic Parser làm lõi offline mặc định + hook LLM tùy chọn khi có API key |
| **Q6** | Điều kiện kích hoạt nghỉ **15p (`Pattern 2`)**, khe **dead-zone `< 30m` (`Pattern 5`)** & **auto-split `> 90m`** | `Presentation2.pdf` Slide 7, 8, 16 vs `src/models.py` & `t03` | **Cao** (ảnh hưởng capacity T01–T10 & trải nghiệm) | Nghỉ 15p giữa 2 task liên tiếp sau block `>= 90p` hoặc `Load == 3` (trừ khi liền sau là `SLEEP`/`OCCUPIED`); dead-zone cấm `Load >= 2`; task `> 90m` tự tách nếu user không khóa `False` |
| **Q7** | Công thức **`Experience Rating (1-5)`**, trọng số **`Category Batching`**, và **mẫu thử `1-week peer study`** | `Presentation2.pdf` Slide 6, 7, 17 | **Trung bình** (hiển thị đánh giá lịch & hiệu chỉnh thực tế) | Hàm fatigue tuyến tính 4 thành phần chuẩn hóa `[1.0..5.0]`; trọng số batching ~15% ưu tiên; bổ sung field `actual_duration_min` để team gom log |
| **Q8** | Hợp nhất 2 nhánh Feature 001 (`main`: `estimate_buffer`) & Feature 002 (`origin/hmanh`: `overload_triage`) | Git `main` (`4c0a85a`) vs `origin/hmanh` (`5d8a30d`) | **Rất cao** (xung đột 47 file nếu merge trực tiếp) | Không merge thẳng `origin/hmanh`; port chọn lọc `overload_triage` + giữ `estimate_buffer` & Student UI trên `ltbinh/sync-proposal` |
| **Q9** | **Sprint Mode Tier 1** có được phép tự nén thời lượng task gốc (`90m -> 75m`) hay giữ an toàn nguyên khối? | `verification_tests/logical_tests/test_scheduling_edge_cases.py` (`#113` `test_fail_edge_sprint_mode_compression_recovery`) | **Cao** (1 test `--all`/`pytest` còn fail có chủ đích) | Tạm giữ **không tự cắt xén** thời lượng task gốc khi chưa có xác nhận người dùng; chỉ mở đề xuất qua Overload Triage (`SHORTEN_TASK`) |
| **Q10** | Tách rạch ròi **`EDF` V0 (Energy-Blind)** vs **`SCORED_GREEDY` (Energy-Aware)** & chọn solver mặc định trên Web UI | `src/solvers/base_solver.py` (`should_prefer_energy_placement`) vs `web/index.html` (`L1073`), `web/app.js` (`L655`), `T09` | **Cao** (trên `T09`, `EDF` và `SCORED_GREEDY` đang ra cùng lịch; UI vẫn mặc định `GREEDY_EDF_FIRST_FIT`) | Tạm giữ nguyên `should_prefer_energy_placement` để bảo toàn pass `--gaps`, giữ UI mặc định `GREEDY_EDF_FIRST_FIT`, chờ nhóm chốt chuyển mặc định UI sang `SCORED_GREEDY` hay giữ `EDF` |

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
* **Cần nhóm chốt:**
  1. Chọn chuẩn cuối cùng cho Student UI là **theo Cognitive Load (`1.20 / 1.35`)**, **theo thói quen (`1.0 / 1.1 / 1.25`)**, hay **kết hợp cả hai**?
  2. Quy ước làm tròn dùng **`RoundUp_15`** (như Slide 7/17) hay **`Nearest_15`** (như `test_estimate_buffer.py`)?
  3. Chốt trọng số hàm mất mát `Loss(α)` cho 1D Grid Search và phân công từng thành viên log `actual_duration_min` trong 1 tuần thử nghiệm.

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
* **Thực tế:** Slide 10 gọi tên M1 là **LLM**, trong khi máy người dùng/môi trường chấm bài chạy cục bộ (FastAPI + Python offline) không có LLM key sẵn, và UI hiện tự parse bằng regex JS (`parseQuickAdd`) trong khi backend `/api/tasks/natural-add` là stub cứng Thứ Tư.
* **Cần nhóm chốt:** Nhóm có muốn gọi API LLM thật (như Gemini API nếu có key biến môi trường) làm lớp tùy chọn bên cạnh **Deterministic Backend Parser**, hay thống nhất **100% Rule-based Deterministic Parser** để đảm bảo tiêu chí **Pure Determinism (SHA-256)** ở Slide 12?

---

### Q6. Ranh giới kỹ thuật của Pattern 2, Pattern 5 & Cờ `is_splittable` (`Slide 6, 7, 8, 13, 16`)
1. **Pattern 2 (15m REST):** Áp dụng bắt buộc sau **mọi block**, sau block **`>= 60–90 phút`**, hay chỉ **`cognitive_load == 3`**? Nếu ngay sau phiên học đã là giờ `MEAL` / `CLASS` / `SLEEP` (`OCCUPIED`), có cần chèn thêm `15m REST` nữa không?
2. **Pattern 5 (`< 30m` Dead-zone `STATE_REST`):** Khe rảnh `15 phút` có chặn hoàn toàn cả task nhẹ `Load-1` (dài `15 phút`) ở chế độ thường, hay chỉ cấm deep focus `Load 2–3` (và mở lại cho `Load 1` khi Crunch)?
3. **Auto-split task `> 90 phút`:** Nếu người dùng tạo task `120–180 phút` mà không chỉ định `is_splittable`, hệ thống có mặc định bật `is_splittable = True` (theo Slide 16) hay giữ `False` như `models.py:107`?

---

### Q7. Công thức `Experience Rating (1-5)` (`Slide 6`) & Trọng số `Category Batching` (`Slide 7`)
* **`Experience Rating (1-5)`:** Slide 6 mô tả hàm mục tiêu chấm độ mệt mỏi từ `1 (Comfortable)` đến `5 (Exhausting)` nhưng chưa chốt công thức toán học. Nhóm cần duyệt 4 thành phần trọng số (tổng tải học/ngày, số lần thiếu nghỉ, tỷ lệ lệch Circadian, số lần chuyển môn `context_switches`).
* **`Category Batching`:** Cần chốt mức phạt chuyển môn `w_switch` vừa đủ gom môn cùng nhóm nhưng không làm task gấp bị xếp trễ.
* **`Personal Habits` (`Slide 6`):** Định dạng `(activity_name, time_intervals, priority_weights)` có nên cho phép gán nhiều khung giờ lặp trong tuần không?

---

### Q8. Quy trình chốt hợp nhất nhánh `origin/hmanh` và cập nhật lại `Presentation2.pdf`
* Sau khi đồng bộ xong code trên nhánh `ltbinh/sync-proposal`, nhóm cần duyệt danh sách quyết định `Q1–Q10` và đồng thời cập nhật lại các chữ **`(Unverified)`**, **`(Planned)`**, **`≥ X%`**, **`γ`**, cùng số liệu benchmark/solver trên `Presentation2.pdf` trước khi nộp/thuyết trình chính thức.

---

### Q9. Cơ chế nén thời lượng ở Tier-1 Sprint Mode (`test_fail_edge_sprint_mode_compression_recovery`)
* **Bối cảnh thực tế:** Bài test thứ #113 trong `clean_runner.py --all` và `pytest -v` (`verification_tests/logical_tests/test_scheduling_edge_cases.py::test_fail_edge_sprint_mode_compression_recovery`) kiểm tra tình huống một task nguyên khối `90 phút` chỉ còn khe rảnh `75 phút` trước deadline (không có buffer/nghỉ để cắt). Hiện hệ thống báo `INFEASIBLE_CAPACITY` (`75p < 90p`) và đề xuất `Early Extension Alert` thay vì tự ý thu ngắn task xuống `75p`, nên bài test này đang **FAIL (`112 Passed | 1 Failed | Total: 113`)**.
* **Phương án cần nhóm biểu quyết:**
  * **Phương án A (Bảo toàn khối lượng gốc — đề xuất giữ an toàn):** Không bao giờ tự co ngắn thời lượng thô của task người dùng; chỉ cho phép nén thông qua **Overload Triage (`SHORTEN_TASK`)** có sự đồng ý của sinh viên, đồng thời điều chỉnh đặc tả bài test `test_fail_edge_sprint_mode_compression_recovery` sang kiểm tra Tier-2 Triage / Early Extension Alert.
  * **Phương án B (Sprint Mode tự nén tối đa X%):** Cho phép Tier-1 Sprint Mode nén trực tiếp thời lượng tác vụ xuống tối đa (ví dụ `-15%` hoặc tối đa `15 phút`) khi sát deadline kèm cảnh báo trong lịch.

---

### Q10. Tách rạch ròi Baseline `EDF` vs `SCORED_GREEDY` (`T09`) & Solver mặc định Web UI
* **Bối cảnh thực tế:**
  1. Trên kịch bản `t09_circadian_comparison.json` (`T09`), cả `EDF` lẫn `SCORED_GREEDY` hiện cho kết quả đặt block giống hệt nhau (sáng `06:30–08:00` cho `T09-DEEP-MATH` ở chế độ Morning; chuyển `T09-DEEP-MATH` xuống `18:00–19:30` ở chế độ Evening), vì `BaseScheduler.should_prefer_energy_placement()` cũng kích hoạt lọc năng lượng cho `EDF` (hiện đang được test `--gaps` `test_fail_circadian_energy_matching` kiểm tra với `algorithm="EDF"`).
  2. Trên giao diện Web (`web/index.html` & `web/app.js`), tùy chọn solver mặc định đang vẫn là `GREEDY_EDF_FIRST_FIT`, dù Slide & `Improve_Plan` hướng tới `SCORED_GREEDY` (`E1–E4`).
  3. Ngoài ra, khi `LocalRepairEngine` chạy ở chế độ `FULL_REBUILD` (`src/solvers/local_repair.py`), bên trong hiện vẫn gọi `GreedyEDFSolver` thay vì giữ đúng solver người dùng đang chọn.
* **Phương án cần nhóm biểu quyết:**
  * **Ý 1 (So sánh thực nghiệm `T09` & `--gaps`):** Có tách rạch ròi `EDF` V0 thành **thuần Energy-Blind First-Fit** để `benchmark_runner.py` / `T09` chứng minh sự khác biệt giữa V0 (`EDF`) và V1/V2 (`SCORED_GREEDY`) hay giữ `EDF` hỗ trợ energy preference như hiện tại (nếu tách thì cần cập nhật test `--gaps` dùng `SCORED_GREEDY`)?
  * **Ý 2 (Mặc định Web UI & `FULL_REBUILD`):** Chuyển mặc định giao diện Student/Lab UI sang **`SCORED_GREEDY`** hay giữ `GREEDY_EDF_FIRST_FIT`, và `FULL_REBUILD` có tái sử dụng đúng solver của lịch hiện tại hay luôn fallback về `EDF`?

