# Đặc Tả Bài Toán, Cơ Chế Sinh Đề & Bộ Chấm Checker (`Testing_System v2.1 + Fuzzing`)

> **Tài liệu chuẩn hóa bài toán (Problem Statement, Generator & Checker Specification)** cho hệ thống [Testing_System](../Testing_System/README.md), đối chiếu trực tiếp từ [schemas.py](../Testing_System/schemas.py), [gates.py](../Testing_System/evaluator/gates.py), [pillars.py](../Testing_System/evaluator/pillars.py), [verdict_and_icee.py](../Testing_System/evaluator/verdict_and_icee.py), [input_generator.py](../Testing_System/generator/input_generator.py), [fuzz_generator.py](../Testing_System/generator/fuzz_generator.py) và [src/models.py](../group03-smartschedule-baseline/src/models.py).
>
> **Mục tiêu:** Chuyển từ bài toán *"xếp sao cho không trùng lịch (`H1–H5`)"* sang bài toán tối ưu **"Đúng cứng (`G1 = 0`) + Hiệu quả thực chất (`v2.1`: Cổng `#0` + 10 tiêu chí hướng con người — đúng việc quan trọng, hợp nhịp sinh học 2 chiều, có ngủ nghỉ phục hồi và chịu được sai số `+25%`) → Đạt `HIGH_PRODUCTIVITY` (`AC`)"**.

---

## I. Định Nghĩa Bài Toán & Cơ Chế Sinh Đề (Input & Output)

### 1. Không gian thời gian
* Thời gian được rời rạc hóa thành các **slot 15 phút**, kéo dài `horizon_days` = `7 ngày` (`672` slot) hoặc `14 ngày` (`1344` slot), bắt đầu lập lịch từ mốc `now_slot`.

### 2. Cấu trúc dữ liệu đầu vào (`CommitmentsProfile` + `List[Task]` + `pinned_blocks`)
1. **Hồ sơ ràng buộc của sinh viên (`CommitmentsProfile`, [src/models.py#L162-L192](../group03-smartschedule-baseline/src/models.py#L162-L192)):**
   * **Giấc ngủ (`sleep_schedule`):** Khóa cứng hằng đêm (`is_hard_lock=True`; mặc định `23:00–07:00` ở `InputGenerator`, biến thiên theo nhóm học sinh/cú đêm ở `FuzzGenerator`).
   * **Lịch cố định (`fixed_events`):** Luôn có **3 bữa ăn/ngày** (`category="MEAL"`) và các **ca học cố định** (`category="ACADEMIC_CLASS"`, dạng lệch ngày hoặc dày/đều).
   * **Nhịp sinh học (`focus_preference`):** Gồm **4 mức** `MORNING` (*Lark*), `AFTERNOON`, `EVENING` (*Owl*), hoặc `BALANCED` (*Finch*) — quy định mức năng lượng `energy_level` $\in \{1, 2, 3\}$ ở từng khung giờ.
   * **Chế độ đệm (`buffer_mode`):** `COGNITIVE_LOAD` ($\alpha_{\text{light}}=1.20$, $\alpha_{\text{heavy}}=1.35$) hoặc `HABIT` (`RARELY`/`SOMETIMES`/`OFTEN`).
   * **Thói quen cá nhân (`personal_habits`):** Việc lặp theo tuần (`frequency_per_week`, `duration_min`, `preferred_window`, không hạn chót; `expand_personal_habits` trải đều vào tuần đầu tại [src/controller.py#L40-L82](../group03-smartschedule-baseline/src/controller.py#L40-L82)).
2. **Các dạng Task đầu vào (`List[Task]`):**
   * Chia 2 loại: **có hạn chót (`DEADLINE` — category `EXAM`, `PROJECT`, `ASSIGNMENT`, `DEADLINE`)** và **không hạn chót (`HABIT`)**.
   * Thuộc tính chính: thời lượng gốc `duration_min` (sau tiền xử lý buffer thành `planned_duration_min`), hạn chót (`deadline_day`, `deadline_time`), độ quan trọng `priority` (`1..5`), độ nặng não `cognitive_load` (`1=nhẹ`, `2=vừa`, `3=nặng/sâu`), khung giờ ưa thích `preferred_window`, nhịp làm việc `work_rhythm` (`LIGHT`/`BALANCED`/`FLOW`), quyền cắt nhỏ (`is_splittable`, `min_chunk_min`, `max_chunk_min`), mốc sớm nhất được làm (`start_after`), và đồ thị phụ thuộc 1 chiều (`depends_on`).
3. **Các block đã ghim (`pinned_blocks`)** và *(riêng Regime 6)* **Sự kiện đột xuất (`DisruptionEvent`) / Làm lố giờ (`Overrun +50%`)**.

### 3. Output cần chấm (`ScheduleOutput`)
* Tập các khối đã xếp `blocks`: `(task_id, chunk_index, start_slot, end_slot, duration_min, state)` và danh sách việc bỏ lại `unplaced_tasks`.

### 4. Cơ Chế Sinh Đề (2 Bộ Sinh Độc Lập)

#### Bộ 1 — `InputGenerator`: 6 Regimes chuẩn đối chứng ([input_generator.py](../Testing_System/generator/input_generator.py))
* Sinh tập kịch bản kiểm định có kiểm soát theo `seed` để cô lập từng nhóm lỗi của thuật toán:
  * **`R1` (Tải nhẹ, $\rho \approx 0.36\text{–}0.55$):** Thử độ sạch khi quỹ giờ rộng.
  * **`R2` (Deadline dồn sát, $\rho \approx 0.80\text{–}0.95$):** Có `extra_pool` ngẫu nhiên thử sức bền tránh rớt hạn.
  * **`R3` (Cú đêm & SJL):** Nhịp `EVENING` + lớp lệch ngày T2/T4/T6 thử ép sáng & phục hồi.
  * **`R4` (DAG & Hạn xa `<10h`):** Đồ thị phụ thuộc kết hợp cửa sổ rộng thử trì hoãn phút chót.
  * **`R5` (Quá tải thật, $\rho > 1$):** Bắt buộc rơi task để đo khả năng *triage* giữ `priority` cao.
  * **`R6` (Chuỗi sự cố A/B/C):** Thử sửa cục bộ (`LOCAL_INSERTION`, `RIPPLE_REPAIR`, `FULL_REBUILD`) và overrun `+50%`.
* Cố định 3 bữa ăn (`_build_meals` `#L62-L89`), lớp học (`_build_classes` `#L92-L136`), và tự kiểm chứng sức chứa sau khi bung thói quen & cộng đệm (`_verify_grid_feasibility` `#L139-L239`).

#### Bộ 2 — `FuzzGenerator v2`: Bộ sinh đề ngẫu nhiên vô hạn theo lời giải chứng từ ([fuzz_generator.py](../Testing_System/generator/fuzz_generator.py))
Chống học vẹt trên 6 kịch bản mẫu bằng cách sinh đề hoàn toàn thủ tục từ mọi số nguyên `seed` (`random.Random(seed)`), nâng cấp lên **quy trình ngược *Plant-a-Witness* + mở rộng tỷ lệ `14 ngày`**:

1. **Bước 1 — Bốc mức tải & dựng hồ sơ chống chồng lấn (`_build_archetype_profile` `#L188-L358`, `FuzzGenerator.generate` `#L898`):**
   * Nếu không ép `--tier`, máy bốc ngẫu nhiên theo trọng số **`45% LOOSE` / `35% TIGHT` / `20% OVERLOAD`**.
   * Bốc 1 trong **4 mẫu hồ sơ thực tế (`ARCHETYPES`, `#L61-L66`)**: `HIGH_SCHOOL_STUDENT`, `UNI_ASYMMETRIC`, `UNI_BUSY_WEEK`, `EXAM_PREP_WEEK` *(ưu tiên `35%` khi `OVERLOAD`)*.
   * Bốc `focus_preference`, `horizon_days` (`75%` là `7 ngày`, `25%` là `14 ngày`), `buffer_mode` (`COGNITIVE_LOAD`/`HABIT`), `0–2` `PersonalHabit`, đồng thời khóa bữa sáng $\ge \text{wake\_slot} + 1$, trưa/tối và lớp sáng tránh chồng lấn ngủ–ăn–lớp từ gốc.
2. **Bước 2 — Đặt trước `PersonalHabit` & Khắc Lời Giải Chứng Từ $\pi^*$ (`_place_habits_on_witness` `#L439-L523`, `_try_carve_task_on_witness` `#L595-L787`):**
   * Đặt trước các `PersonalHabit` (bỏ thói quen nào không đủ khe nếu có).
   * Với mỗi ứng viên task (`_make_candidate_task` `#L526-L592`), trần số lượng task và thời lượng tự thích nghi theo `usable_free_init` (`7d`: tối đa `16–24` tasks; `14d`: tối đa `22–34` tasks kèm các task dài `150–240p` tách mảnh `60–90p`).
   * Lấy đúng số lượng & độ dài chunk qua `apply_estimate_buffer -> split_task_into_chunks`, chọn ngẫu nhiên vị trí đa dạng trong khe trống (`_sample_interval_positions`).
   * **Ở mức `LOOSE` (`strict_ergonomic=True`):** bắt buộc giữ nghỉ `15p` sau `load=3` (kể cả so với block & ca lớp đã đặt), đệm sau lớp dài, không đặt `load=3` vào `energy=1`, trần `<= 2` ca nặng & `<= 540p`/ngày, không cặp nặng sát nhau, không chuỗi ghép `load>=2`, không kẹp bữa ăn `load>=2`, giữ khe phòng sốc `+25%` (`_chunk_shock25_extra` `#L135`), và gom ngữ cảnh tránh `Ctx` cao → giúp chính lời giải chứng từ đạt chuẩn `HIGH_PRODUCTIVITY`.
   * **Ở mức `TIGHT`:** giữ điểm ưu tiên sinh học mềm với fallback đóng khít tới $\rho \in [0.65, 0.90]$ (kèm vòng top-up `L1/L2` tách mảnh).
3. **Bước 3 — Suy ngược ràng buộc đề bài từ $\pi^*$ (`_derive_constraints_from_witness` `#L790-L891`):**
   * **`deadline_day` / `deadline_time`:** Gán sau `last_end` của task trên $\pi^*$ (ở `LOOSE` tính kèm phần dư `+25%` shock tail) cộng thêm `slack` ngẫu nhiên (`2–4 ngày` cho `LOOSE`, `0–2 ngày` cho `TIGHT`).
   * **DAG `depends_on` (`24%`) & `start_after` (`20%`):** Chỉ nối cạnh `parent -> child` khi `witness_end(parent) <= witness_start(child)` và `parent_dl <= child_dl` → **chắc chắn `0%` chu trình và `100%` khả thi đồng thời cả DAG lẫn đóng thùng**.
   * **`PINNED` (`35%`):** Nâng cấp trực tiếp 1 block đơn hợp lệ trên $\pi^*$ (không tách mảnh, không DAG, không `start_after`) thành `PINNED`. Sau cùng xáo trộn `tasks` để tránh lộ thứ tự $\pi^*$ cho solver.
4. **Bước 4 — Nhánh `OVERLOAD` & Hậu kiểm `_compute_rho` (`#L361-L425`):**
   * Riêng `OVERLOAD` dùng lõi khả thi đã khắc rồi bơm thêm task hạn sớm (`1–6 ngày đầu`, `priority` phân cực `1,2,4,5`) đến khi `_compute_rho(..., require_chunk_fit=False)` xác nhận `rho_dl >= 1.22` **và** `has_shortage=True` (bỏ `witness_blocks`, `witness_verified=False`).
   * Đề `LOOSE`/`TIGHT` luôn giữ `witness_blocks` kèm cờ `witness_verified=True`.
5. **Bước 5 — Tự kiểm chứng Witness + Chấm 5 solver (`_check_fuzz_invariants` trong [pipeline_runner.py#L342-L426](../Testing_System/runner/pipeline_runner.py#L342-L426)):**
   * Với mọi đề có `witness_blocks`, runner tự đưa $\pi^*$ vào `ScheduleEvaluator` bắt buộc chứng minh `G1 == 0`, `P1.1 == 100%`, `not is_structurally_overloaded` — tách bạch hoàn toàn lỗi của thuật toán (`SUBOPT`) khỏi chất lượng đề; đồng thời kiểm tra bất biến đơn điệu sốc `P1.1 >= Shock@+25% >= Shock@+50%`.

> [!TIP]
> **Bộ sinh `FuzzGenerator v2` & Checker `v2.1` đã được kiểm chứng đóng băng (`50 seeds 1001..1050`: `50/50 ALL PASS`):**
> 1. **Đúng 100% tỷ lệ tải:** `0/50` lệch tier ở cả 3 mức (`LOOSE`, `TIGHT`, `OVERLOAD`); toàn bộ `14 ngày TIGHT` đạt $\rho \in [0.7067, 0.7749]$.
> 2. **Chứng minh Điều kiện Đủ lẫn Khả thi `HIGH`:** `42/42` đề khả thi có `witness_blocks` chứng minh `G1=0, P1.1=100%`; riêng nhóm `LOOSE` có **`22/24` (`91.7%`)** lời giải chứng từ đạt hẳn **`HIGH_PRODUCTIVITY`**, và `_simulate_shock_survival` ([pillars.py#L867-L880](../Testing_System/evaluator/pillars.py#L867-L880)) giữ `50/50` đơn điệu sốc.

---

## II. Luật Chấm Của Checker `v2.1` (Tách Bạch "Đúng Cứng" vs "Hiệu Quả Thật")

### Tầng 0 — Luật Cứng `G1` (Bắt buộc = `0` lỗi, sai 1 lỗi là loại ngay)
Định nghĩa trong [gates.py](../Testing_System/evaluator/gates.py) và [metrics.py](../group03-smartschedule-baseline/src/metrics.py):

1. **`H1`:** Không chồng lên `OCCUPIED` (lớp học, bữa ăn, sự cố cố định).
2. **`H2`:** Không chồng lên `SLEEP` (bảo vệ giờ ngủ).
3. **`H3`:** Không xếp 2 block công việc trùng nhau trong cùng 1 slot 15 phút.
4. **`H4`:** Không có block kết thúc sau `deadline_slot` và không tràn khỏi `[0, horizon_slots)`.
5. **`H5`:** Đúng thứ tự `depends_on` (task con không chạy trước khi task cha xong; không xếp task con nếu task cha chưa được xếp).
6. **`start_after`:** Không xếp trước mốc `start_after` (trừ block `DONE`/`PINNED`).
7. **`now_slot`:** Không xếp lùi vào quá khứ trước `now_slot` (trừ `DONE`/`PINNED`).
8. **Tách mảnh đúng luật:** Không cắt task `is_splittable=False`; các chunk phải đúng thứ tự tăng dần, không chồng nhau, và tuân thủ `min_chunk_min` / `max_chunk_min`.
9. **Đủ thời lượng:** Tổng phút các block của task đã xếp phải bằng đúng `planned_duration_min` (sau buffer).
10. **Bảo toàn `PINNED`:** Mọi block `PINNED` hợp lệ ở đầu vào phải nằm nguyên tại đúng `(task_id, start_slot, end_slot)`.

*(Song song với `G1`, cổng **`G2`** tính $\rho = \frac{\text{slot cần xếp (đã trừ PINNED)}}{\text{slot FREE khả dụng (đã trừ SLEEP, OCCUPIED, PINNED)}}$ + kiểm tra sức chứa theo từng mốc hạn để phân biệt: rơi task là do **đề quá tải thật** ($\rho > 1$) hay do **thuật toán dở** ($\rho \le 1$)).*

---

### Tầng 1 — Luật Hiệu Quả & Sức Khỏe (`v2.1`: `HARD-SLA` + 10 Tiêu Chí `P1–P4`)
Checker không dừng ở "không xếp trùng" mà chấm chất lượng sống–học bằng **`CRITICAL` (1 thẻ đỏ)** và **`WARNING` (1 thẻ vàng)** theo [schemas.py#L55-L85](../Testing_System/schemas.py#L55-L85), [pillars.py](../Testing_System/evaluator/pillars.py) và [verdict_and_icee.py#L41-L490](../Testing_System/evaluator/verdict_and_icee.py#L41-L490):

| Mã / Trụ cột | Checker `v2.1` đang đo cái gì? | Điều kiện bị phạt **`CRITICAL`** (thẻ đỏ) | Điều kiện bị phạt **`WARNING`** (thẻ vàng) |
| :--- | :--- | :--- | :--- |
| **`HARD-SLA`** *(Tốc độ)* | Thời gian giải `execution_time_ms` của thuật toán | *(Không gắn CRITICAL; đưa vào Cổng `#0` nếu > trần)* | `exec_ms > 1000ms` |
| **`P1.1` (`DEADLINE-VAL`)** | `%` tổng `priority` các task có hạn kịp deadline | Rơi $\ge 1$ task có hạn khi `G2` xác nhận $\rho \le 1$ | *(Nếu $\rho > 1$ hoặc thiếu slot hạn, chuyển sang nhãn `OVERLOAD_TRIAGE`)* |
| **`P1.1 / P2.1` (`USER-PREF`)** | `%` hoàn thành `HABIT` và `%` khớp `preferred_window` *(chỉ xét khi tải nhẹ–vừa $\rho_{\text{total}} \le 0.85$)* | `habit_value_rate_pct < 50%` *(khi $\rho_{\text{total}} \le 0.85$)* | `habit_value_rate_pct < 80%` **HOẶC** `preferred_window_match_pct < 50%` *(khi $\rho_{\text{total}} \le 0.85$)* |
| **`P1.2` (`NO-CRAM`)** | `%` khối lượng cửa sổ rộng (`>10h`) bị dồn vào `<10h` sát hạn dù có khe năng lượng $\ge$ trước đó *(miễn nếu chờ Peak/DAG)* | Dồn vô lý **`> 50%`** | Dồn vô lý **`> 25%`** **HOẶC** độ trễ khởi phát việc nặng **`> 60%`** |
| **`P2.1` (`BIO-SYNC`)** | **(a) 2-way Synchrony:** số block `load=3` bị đặt vào `energy=1` dù lưới phản chứng còn khe `avg_energy >= 2.0` *(mọi chronotype)*; **(b) Achievable Peak (`APk%`):** `%` `load=3` khớp `energy=3` *chỉ tính trên task còn khe Peak khả dụng* | `off_peak_heavy_mismatch_count >= 1` **HOẶC** `APk% < 25%` | `APk% < 50%` |
| **`P2.2` (`BREAK-SAFE`)** | **(a)** Nghỉ `>= 15p` sau `load=3` *(lớp ngay sau không tính là nghỉ)*; **(b)** Chuỗi $\ge 2$ block `load>=2` liên tiếp không nghỉ (`Stk`); **(c)** Đặt `load=3` sát ngay sau lớp dài $\ge 90\text{p}$ (`PCl`) | Thiếu nghỉ sau `load=3` (`crunch_tier_used == 0`), **HOẶC** `Stk > 180p`, **HOẶC** `PCl >= 2` | Thiếu nghỉ ở `Crunch Tier 1`, **HOẶC** `Stk > 120p`, **HOẶC** `PCl == 1` |
| **`P2.3` (`PACE-BALANCE` SJL)** | Độ lệch trung vị pha tròn giờ tự học giữa ngày có lớp và ngày không lớp *(nếu làm xong sớm nghỉ cuối tuần `sjl_neutral_unpaired=True`, miễn phạt & gán `90p` khi xếp hạng)* | *(Không gắn CRITICAL)* | `PHASE_ADVANCE > 60p` **HOẶC** `PHASE_DELAY > 180p` |
| **`P3.1` (`PACE-BALANCE` TStd)** | Độ lệch chuẩn **tổng tải ngày (`lớp + tự học`)** giữa các ngày có lớp/khe trống (`>= 3` ngày) | *(Không gắn CRITICAL)* | `total_daily_load_std_min > max(180p, base_class_daily_std_min + 45p)` |
| **`P3.2` (`DAILY-CAP` & `FOCUS-FLOW`)** | **(a)** Số ngày `>2` ca `load=3`; **(b)** Ngày tổng giờ **lớp + tự học** cao nhất (`MxD`); **(c)** Cặp `load=3` sát nhau (`<=1` slot) / kẹp 2 đầu `MEAL` với **`load>=2`**; **(d)** Đổi `category` & khác `task_id` cách `<=2` slots (`Ctx`) | `heavy_day_overload_days >= 1` **HOẶC** `max_daily_total_min > 600p` (`10h`) | `adjacent_heavy_pairs >= 1` / `meal_l2 >= 1`, **HOẶC** `MxD > 540p` (`9h`), **HOẶC** `Ctx >= max(4, study_days)` |
| **`P4.1` (`SHOCK-SAFE`)** | Giả lập mọi task tăng thời lượng `+25%` (trên `duration_min` gốc) xem còn bao nhiêu `%` `priority` kịp hạn không đụng `SLEEP`/`OCCUPIED`/block sau | Sống sót dưới sốc `+25%` **`< 70%`** | Sống sót **`< 85%`** *(trường hợp `0% buffer` ở đầu vào nhưng vẫn sống `>= 85%` chỉ ghi mức `INFO`, không phạt `WARNING`)* |
| **`P4.2` (`Ổn định sau sửa`)** *(Regime 6)* | Đo $D(\pi_0,\pi_1)$, giữ block đầu `Eq 1st`, `Orig%`, `Diff%`, độ dịch trung bình $\Delta t$, số đảo thứ tự | *(Chấm theo bất biến Regime 6: `LOCAL_INSERTION` phải giữ ổn định tốt hơn `FULL_REBUILD` ở cấp nhẹ)* | — |

---

## III. Hai Cơ Chế Chấm Điểm Độc Lập (`v2.1` — Không Quy Về Thang 100)

> [!IMPORTANT]
> **Tại sao checker KHÔNG quy về thang điểm 100?**
> Theo [verdict_and_icee.py#L540-L546](../Testing_System/evaluator/verdict_and_icee.py#L540-L546) và *Schaerf (1999) §5.1, tr. 29*, bộ chấm tuyệt đối không cộng dồn kiểu `0.3*A + 0.4*B + 0.3*C = 85/100` vì điểm đẹp ở 1 cột sẽ **che giấu lỗi chí mạng** ở cột khác (nhồi 4 ca nặng không nghỉ vẫn được 85/100 dù khiến người học kiệt sức).

### 1. Cơ Chế A — Chấm Đậu / Rớt Độc Lập Từng Lịch (`Verdict` — như "Thi Bằng Lái Xe")
Không so với thuật toán khác. Cây quyết định tại [verdict_and_icee.py#L507-L535](../Testing_System/evaluator/verdict_and_icee.py#L507-L535) và `VerdictLabel` tại [schemas.py#L24-L29](../Testing_System/schemas.py#L24-L29):

| Nhãn checker trả về | Định nghĩa & Điều kiện kích hoạt | Tác dụng thực tế của nhãn | Khi thấy nhãn này cần làm gì? |
| :--- | :--- | :--- | :--- |
| **`INVALID`** *(không phải `UNVALID`)* | `g1_total_violations > 0` — vi phạm ít nhất 1 trong 10 luật cứng Tầng 0 (`G1`). | **Cổng chặn tuyệt đối (WA cứng):** loại ngay mọi lịch bất khả thi ngoài đời thực. | Mở `g1_violation_details` để sửa triệt để lỗi vi phạm ràng buộc cứng / mất `PINNED`. |
| **`OVERLOAD_TRIAGE`** | `G1 == 0`, có task hạn chót bị rơi (`unplaced_deadline_count > 0`), **và** `G2` xác nhận quá tải cấu trúc ($\rho > 1$ hoặc thiếu sức chứa). | **Tránh kết tội oan thuật toán:** chuyển sang đo năng lực *triage* (giữ được bao nhiêu `%` `priority` cao). | Kiểm tra `P1.1%` và `rank` so với `WSPT`/`SCORED_GREEDY`. |
| **`SUBOPTIMAL_ALGORITHM_FAILURE`** | `G1 == 0`, rơi task có hạn, **nhưng** `G2` xác nhận lý thuyết đủ sức chứa ($\rho \le 1$). | **Bắt đích danh thuật toán yếu (WA mềm):** rơi việc do phân mảnh khe trống hoặc tham lam thiển cận. | Rà soát thứ tự duyệt task, cơ chế tách mảnh (`splitting`), hoặc chọn khe sớm. |
| **`FEASIBLE_BUT_LOW_PRODUCTIVITY`** | `G1 == 0`, đủ `100%` task có hạn, **nhưng** dính **`>= 1` `CRITICAL`** **HOẶC** **`>= 2` `WARNING`** theo bộ tiêu chí `v2.1`. | **Chặn bệnh "xếp không trùng là xong":** cảnh báo lịch hại nhịp sinh học, nhồi ngày, bỏ thói quen hoặc mong manh khi trễ giờ. | Đọc **`Top Cảnh Báo ICEE`** đi kèm để biết đích danh thẻ đỏ/vàng ở tiêu chí nào và sửa solver. |
| **`HIGH_PRODUCTIVITY`** | `G1 == 0`, đủ `100%` task có hạn, **`0` `CRITICAL`** và **tối đa `1` `WARNING`**. | **Đạt chuẩn `AC` thật:** an toàn sinh học, tôn trọng thói quen, đủ nghỉ & chịu được sốc `+25%`. | Đạt chuẩn ở kịch bản đang test; tiếp tục kiểm chứng chéo trên Regimes & Fuzz. |

---

### 2. Cơ Chế B — Xếp Hạng Nhiều Thuật Toán (`v2.1`: Cổng `#0` + 10 Cấp Từ Điển Có Dung Sai)
Tại [verdict_and_icee.py#L538-L630](../Testing_System/evaluator/verdict_and_icee.py#L538-L630) (`lex_key` dòng `#L563-L594`), các tiêu chí không trọng số hóa thành 100 mà xếp theo **bảng tổng sắp huy chương có bậc dung sai (*epsilon-bucketed*)** để xóa nghịch lý hơn nhau vài phút lẻ ở cấp dưới mà đè cấp trên:

* **Cổng `#0` — `HARD-RULE` (Luật cứng & Trần tốc độ):** `(G1 nhỏ hơn thắng -> exec_ms > 1000ms: False thắng)`.
1. **`#1` `QUALITY-TIER` (Nhóm Đạt Chuẩn `Verdict`):** `HIGH_PRODUCTIVITY` (`0`) < `LOW` (`1`) < `OVLD` (`2`) < `SUBOPT` (`3`) < `INVALID` (`4`).
2. **`#2` `DEADLINE-VAL` (`P1.1%`):** `%` tổng `priority` deadline kịp hạn *(cao hơn thắng)*.
3. **`#3` `SHOCK-SAFE` (`Shk25%`):** `%` `priority` sống sót dưới sốc `+25%`, chia bậc **`5%`** *(cao hơn thắng)*.
4. **`#4` `BREAK-SAFE` (Nghỉ & Chống Thông Mạch):** Tuple 3 tầng `(Rec% chia bậc 5% ↑, bậc 30p của max_multi_block_streak_l2 vượt 90p ↓, post_class_buffer_violations ↓)`.
5. **`#5` `BIO-SYNC` (Nhịp Sinh Học 2 Chiều):** `(off_peak_heavy_mismatch_count ↓, achievable_heavy_peak_match_pct chia bậc 10% ↑)`.
6. **`#6` `NO-CRAM` (`<10h%`):** `%` khối lượng cửa sổ rộng dồn vô lý `<10h`, chia bậc **`5%`** *(thấp hơn thắng)*.
7. **`#7` `DAILY-CAP` (Giới Hạn Ngày):** `(số ngày >2 ca load=3 ↓, bậc 30p của max_daily_total vượt 540p ↓, cặp nặng sát nhau ↓, kẹp bữa ăn load>=2 ↓)`.
8. **`#8` `FOCUS-FLOW` (`Ctx`):** Số lần đổi `category` & khác `task_id` cách `<= 2` slots trong ngày *(thấp hơn thắng)*.
9. **`#9` `USER-PREF` (Thói Quen & Khung Giờ):** `(% giữ HABIT chia bậc 10% ↑, % khớp preferred_window chia bậc 10% ↑)`.
10. **`#10` `PACE-BALANCE` (Đều Tuần & Lệch Pha):** `(SJL hiệu dụng chia bậc 30p ↓ [unpaired nhận 90p], Tổng Std lớp+tự học chia bậc 30p ↓)`.

---

## IV. App Chạy Thật vs Phòng Chấm Thi & Ví Dụ Thực Tế (`REGIME_1, seed=42`)

### 1. Hai hiểu nhầm cần tách bạch
1. **App sản phẩm (`group03-smartschedule-baseline`) KHÔNG phải "chạy 5 thuật rồi chọn thuật thắng":** Khi sinh viên sử dụng, app chạy thuật toán thiết kế chính là `SCORED_GREEDY`. Việc `Testing_System` chạy song song 5 solvers (`EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`) là **thí nghiệm đối chứng khoa học** trong phòng chấm thi.
2. **`Rank #1` KHÔNG đồng nghĩa với `HIGH_PRODUCTIVITY`:** `Rank #1` chỉ nói rằng thuật toán đó *"ít tệ nhất trong 5 thuật toán đang so"*.

### 2. Kết quả chạy thật trên `REGIME_1_LOOSE_FEASIBLE` (`seed=42`) dưới chuẩn `v2.1`
Lệnh kiểm chứng: `python -B -m Testing_System.cli --mode regime --regime 1 --seeds 42` (`Tải ρ=0.3623 = 121/334 slots`, `Chronotype=BALANCED`, `Horizon=7 ngày`, `Buffer=COGNITIVE_LOAD`):

| Rank | Solver | Verdict (Độc lập) | `G1` | `P1.1%` | `Shk25` | `Rec/Stk/PCl` | `OffP/APk%` | `<10h` | `Crn/MaxD` | `Ctx` | `Hab/Prf` | `SJL/TStd` | `ms` |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `#1` | **`SCORED_GREEDY`** | `FEASIBLE_BUT_LOW_PRODUCTIVITY` | 0 | 100.0 | 100.0 | `100/150/0` | `0/80` | 0.0 | `1/3/0/705m` | 4 | `100/87` | `390/219` | 29.6 |
| `#2` | **`EDF`** | `FEASIBLE_BUT_LOW_PRODUCTIVITY` | 0 | 100.0 | 100.0 | `100/150/0` | `0/20` | 0.0 | `3/2/1/735m` | 9 | `100/34` | `285/309` | 4.7 |
| `#3` | **`WSPT`** | `FEASIBLE_BUT_LOW_PRODUCTIVITY` | 0 | 100.0 | 100.0 | `100/150/1` | `0/20` | 0.0 | `2/5/1/765m` | 4 | `100/36` | `308/307` | 5.1 |
| `#4` | **`BACKTRACK`** | `FEASIBLE_BUT_LOW_PRODUCTIVITY` | 0 | 100.0 | 100.0 | `100/225/0` | `0/80` | 0.0 | `1/4/0/765m` | 5 | `100/87` | `405/231` | 166.9 |
| `#5` | **`LST`** | `FEASIBLE_BUT_LOW_PRODUCTIVITY` | 0 | 100.0 | 100.0 | `100/225/2` | `0/0` | 7.8 | `0/3/1/750m` | 7 | `100/7` | `75/241` | 18.1 |

**Cách đọc bảng đúng theo `v2.1`:**
* **Theo Cơ chế B (Xếp hạng):**
  * `SCORED_GREEDY` (`Rec=100%, Stk=150p [bậc 2], PCl=0`) hòa với `EDF` đến hết `#4 BREAK-SAFE`, rồi thắng dứt điểm ở **`#5 BIO-SYNC` (`OffP=0`, `APk=80% > 20%`)**.
  * `SCORED_GREEDY` thắng `BACKTRACK` ngay ở **`#4 BREAK-SAFE`** vì `Stk=150p` (`(150-90)//30 = 2`) nhỏ hơn hẳn `BACKTRACK` `Stk=225p` (`(225-90)//30 = 4`).
* **Theo Cơ chế A (Chất lượng độc lập) — Lý do `#1 SCORED_GREEDY` vẫn là `LOW`:** Bộ chẩn đoán `ICEE` trả Top 5 cảnh báo theo `impact_rank`:
  1. **`[CRITICAL][P3.2]`** *(rank 84)*: Có 1 ngày phải gánh `>2` phiên nhận thức nặng (`load=3`).
  2. **`[CRITICAL][P3.2]`** *(rank 81)*: Có ngày tổng giờ học trên lớp + tự học lên tới `705 phút (>10 tiếng)`.
  3. **`[WARNING][P2.2]`** *(rank 54)*: Chuỗi học ghép nhiều block (`load>=2`) thông mạch `150 phút`.
  4. **`[WARNING][P2.3]`** *(rank 50)*: Pha tự học ngày có lớp lệch `390.0p` so với ngày không có lớp (`PHASE_DELAY > 180p`).
  5. **`[WARNING][P1.2]`** *(rank 45)*: Xu hướng trì hoãn khởi phát với tác vụ nhận thức nặng.

> [!NOTE]
> **Phân biệt `[Invariants]: PASS` vs `Verdict == HIGH_PRODUCTIVITY`:** Dòng `[Invariants]: PASS` ở CLI chỉ kiểm tra mức sàn tự động của test suite (không lỗi `G1`, đủ `100%` dưới tải nhẹ, `SCORED_GREEDY` giữ Peak/Window không thua `EDF`, không nghịch lý xếp hạng). Để đưa sản phẩm lên `HIGH_PRODUCTIVITY`, nhóm dùng Top cảnh báo `ICEE` để nâng cấp hàm mục tiêu của `SCORED_GREEDY` theo vòng lặp khép kín.

---

## V. Nhật Ký Lập Luận Tư Duy Tính Toán & Báo Cáo Thực Nghiệm (`v2.1 + Fuzzing`)

> [!IMPORTANT]
> Toàn bộ bảng **Nhật ký Lập luận Tư duy Tính toán (CT Log)** được lưu gọn tại [CT_Rationale_Log.md](CT_Rationale_Log.md) *(đồng bộ bắt buộc theo [AGENTS.md](../AGENTS.md))*. Số liệu benchmark thực nghiệm của 5 thuật toán trên **120 đề Regimes + 50 đề Fuzz** xem tại [Solver_Benchmark_Report.md](Solver_Benchmark_Report.md).

---

## VI. Mẫu Prompt / Spec Bàn Giao Cho Thành Viên & AI (`Acceptance Checklist v2.1`)

> *Có thể copy trực tiếp khung dưới đây để giao việc hoặc làm task spec cho AI khi sửa/viết thuật toán sắp lịch:*

```markdown
### Mục tiêu nghiệm thu Solver / Thuật toán Lập lịch SmartSchedule (Chuẩn v2.1)
Mọi lời giải sinh ra trên lưới 15 phút (672/1344 slots) KHÔNG ĐƯỢC chỉ dừng ở "không xếp trùng". Để đạt chuẩn **AC (`HIGH_PRODUCTIVITY`)** khi chấm qua `Testing_System`, đầu ra phải thỏa mãn đầy đủ 3 lớp sau:

1. **Điều kiện cần (`G1 = 0` & `exec_ms <= 1000ms` — Cổng `#0 HARD-RULE`):**
   - Thỏa mãn `H1–H5` (không đè `OCCUPIED`/`SLEEP`, không đè block khác, không quá deadline, đúng thứ tự `depends_on`).
   - Tuân thủ `start_after`, `now_slot`, quy tắc tách mảnh (`is_splittable`, `min_chunk_min`, `max_chunk_min`), đủ `planned_duration_min` (sau buffer), và giữ nguyên 100% block `PINNED`.

2. **Điều kiện đủ (`0 CRITICAL` và `<= 1 WARNING` trên 10 tiêu chí `v2.1`):**
   - **`P1` (`DEADLINE-VAL`, `NO-CRAM`, `USER-PREF`):** Xếp đủ 100% task có hạn khi tải $\rho \le 1$; dồn vô lý vào `<10h` $\le 25\%$ và `heavy_onset_delay <= 60%`; khi $\rho_{\text{total}} \le 0.85$ phải giữ `HABIT >= 80%` và `preferred_window >= 50%`.
   - **`P2` (`BIO-SYNC`, `BREAK-SAFE`, `SJL`):** Tuyệt đối không đặt `load=3` vào khung `energy=1` nếu lưới còn khe `avg_energy >= 2.0` (`off_peak_heavy_mismatch_count == 0`, áp dụng mọi chronotype); khớp Peak khả thi `achievable_heavy_peak_match_pct >= 50%`; luôn chừa `>= 15p` nghỉ sau mỗi block `load=3`; chuỗi ghép `>= 2` block `load>=2` thông mạch $\le 120\text{p}$ (tối đa `180p`); chừa `15p` đệm sau ca lớp dài ($\ge 90\text{p}$) trước khi xếp `load=3`; giữ `SJL`: `PHASE_ADVANCE <= 60p`, `PHASE_DELAY <= 180p`.
   - **`P3` (`DAILY-CAP`, `FOCUS-FLOW`, `PACE-BALANCE`):** Tối đa `<= 2` phiên `load=3`/ngày; tổng tải ngày **lớp + tự học** `<= 540p` (`9h`, trần cứng `600p`); không đặt 2 phiên `load=3` sát nhau (`<= 1 slot`) hoặc kẹp 2 đầu bữa ăn với `load>=2`; đổi loại việc sát nhau `focus_context_switches < max(4, study_days)`; độ lệch chuẩn tổng tải ngày `total_daily_load_std_min <= max(180p, base_class_daily_std_min + 45p)`.
   - **`P4` (`SHOCK-SAFE` & `P4.2`):** Chừa khe đệm / bật buffer sao cho khi sốc thời lượng `+25%`, tối thiểu `>= 85%` `priority` kịp hạn; khi có sự cố/overrun, ưu tiên sửa cục bộ giảm tối đa $D(\pi_0, \pi_1)$ và giữ `Eq 1st`.

3. **Lệnh tự kiểm định trước khi nộp PR:**
   - `python -B -m pytest Testing_System/tests -v` (`39/39` passed — gồm bộ test `v2.1`, đơn điệu sốc, scale-invariant `Ctx`/`P4.1` & `FuzzGenerator v2`)
   - `python -B -m Testing_System.cli --mode full --seeds 42` (`OVERALL SUITE RESULT: ALL PASS`)
   - `python -B -m Testing_System.cli --mode fuzz --count 5 --start-seed 1001` (`OVERALL FUZZ RESULT: ALL PASS`)
```
