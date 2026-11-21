# Báo Cáo Thống Kê & Đánh Giá Bộ Thuật Toán Lập Lịch (`Testing_System v2.1 + Fuzzing v2`)

> [!NOTE]
> Báo cáo này tuân thủ **Rule 2** trong [AGENTS.md](../AGENTS.md), giữ nguyên đầy đủ **5 mục chuẩn** và sử dụng máy chấm bất biến **`Testing_System v2.1`** (*Cổng `#0` + 10 cấp Từ Điển có dung sai & chống lách luật*, [verdict_and_icee.py](../Testing_System/evaluator/verdict_and_icee.py), [pillars.py](../Testing_System/evaluator/pillars.py)) cùng bộ sinh đề **`FuzzGenerator v2`** ([fuzz_generator.py](../Testing_System/generator/fuzz_generator.py)). Không một file nào trong `Testing_System/` bị chỉnh sửa. Tài liệu kiến trúc nâng cấp xem tại [ultimate_plan.md](ultimate_plan.md); lập luận CT xem tại [CT_Rationale_Log.md](CT_Rationale_Log.md).

---

## I. Thông Tin Đợt Chạy & Phạm Vi Dữ Liệu

* **Ngày thực nghiệm sau nâng cấp V3:** `2026-11-20` *(đối chiếu trực tiếp với mốc baseline đóng băng cùng thước đo `v2.1`)* | **Chế độ:** `DIRECT_CONTROLLER` (`v2.1`)
* **Toàn bộ bộ kiểm thử tự động đều XANH 100% (`0` sửa đổi trong `Testing_System/`):**
  * **`pytest Testing_System/tests -v`:** **`39 / 39` passed (`40.25s`)**
  * **`clean_runner.py --all`:** **`161 / 161` Passed (`47.31s`)** *(gồm 6 test hồi quy V3 mới trong `test_ergonomic_solvers_v3.py`)*
  * **`benchmark_runner.py`:** **`EXIT=0`** (`T01–T10 C_hard=0`, `3x Determ PASS`, `T04 LOCAL_INSERTION Stability=100.00%`, `EDF N=50 = 4.97 ms`, `T09 Ablation`: `EDF` `4268107a006d` bất biến vs `SCORED_GREEDY` `6aa59bace73a -> 00c63b253dde`).
* **Quy mô benchmark 6 thuật toán (`EDF` [V0 untouched], `WSPT` [Blind], `LST` [Blind], `SCORED_GREEDY` [V3], `BACKTRACK` [V3], `HYBRID_ALNS` [V3 thứ 6]): `220` đề × `6` thuật toán = `1.320` lượt giải & chấm (`444.7s`):**
  1. **Tập 1 — `6 Regimes` chuẩn (`20 seeds: 1..20` × `6 Regimes` = `120` đề, `720` lượt chạy):**
     * Invariants PASS: **`120 / 120`** (`0` thất bại) | Lỗi cứng `INVALID`: **`0 / 720`** | Rớt hạn vô lý `SUBOPT`: **`0 / 720`** | Nghịch lý xếp hạng (6 & 5 solvers): **`0 / 120`**.
  2. **Tập 2 — `FuzzGenerator v2` (`50 seeds: 1001..1050`, `300` lượt chạy):** `EXAM_PREP_WEEK` (`22`), `UNI_ASYMMETRIC` (`14`), `HIGH_SCHOOL_STUDENT` (`8`), `UNI_BUSY_WEEK` (`6`); `7 ngày` (`38`), `14 ngày` (`12`); `LOOSE` (`24` — Witness đạt `22/24 HIGH`), `TIGHT` (`18`), `OVERLOAD` (`8`).
     * Invariants PASS: **`50 / 50`** | Lỗi cứng `INVALID`: **`0 / 300`** | `SUBOPT`: **`0 / 300`** | Nghịch lý xếp hạng: **`0 / 50`**.
  3. **Tập 3 — Tập kiểm chứng mù chưa từng chạm khi tinh chỉnh (`Held-Out Unseen Fuzz v2`, `50 seeds: 5001..5050`, `300` lượt chạy):** `EXAM_PREP_WEEK` (`14`), `HIGH_SCHOOL_STUDENT` (`14`), `UNI_BUSY_WEEK` (`11`), `UNI_ASYMMETRIC` (`11`); `7 ngày` (`34`), `14 ngày` (`16`); `LOOSE` (`25`), `TIGHT` (`15`), `OVERLOAD` (`10`); `witness_verified = 40/40`.
     * Invariants PASS: **`50 / 50`** | Lỗi cứng `INVALID`: **`0 / 300`** | `SUBOPT`: **`0 / 300`** | Nghịch lý xếp hạng: **`0 / 50`**.

* **Đợt chạy bổ sung `2026-11-21` — chọn đề cho tab *Bảng so sánh trên 7 bộ test nổi bật* (Web UI):** quét `60` đề (`R1–R6 × seeds 1,2,3,42,101` = `30` + Fuzz `RANDOM 1001..1030` = `30`) × `6` thuật toán = `360` lượt giải & chấm, chế độ `DIRECT_CONTROLLER` (`v2.1`), cùng `ScheduleEvaluator` + `rank_cross_solver_reports`; sau đó `verification_tests` **`190 / 190`** passed (gồm `4` test mới `test_showcase_and_fuzz_suites.py`). Kết quả chi tiết ở mục **2.6**.

---

## II. Bảng Thống Kê Bộ Thuật Toán Theo Tiêu Chí `v2.1` & Phân Bố `Verdict`

### 2.1. Tập 1 — Tổng hợp `120` test `Regimes 1–6` (`720` lượt chấm, `invariants_failed = 0`, `paradox = 0/0`)

| Thuật toán | Hạng TB | `#1` *(6 / 5)* | `(G1)` | `P1.1%` | `Shk25` | `Rec / Stk / PCl` | `OffP / APk%` | `<10h%` | `Corne (d/a/m) / MxD` | `Ctx` | `Hab / Prf%` | `SJL / TStd` | `ms` *(Max)* | Verdict (`HIGH`/`LOW`/`SUBO`/`OVLD`/`INV`) *(Baseline → V3)* |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`SCORED_GREEDY`** *(V3)* | **`2.22`** | **`57`** / **`73`** | 0.00 | **95.68** | 90.71 | 86.1 / 73.2 / 0.21 | 0.24 / 83.6 | 0.92 | 0.75/1.31/0.64 / 511p | 3.83 | 100 / 97.1 | 196 / 153 | 263.1 *(535.6)* | **77** / 23 / **0** / 20 / 0 *(từ 60/24/16/20/0)* |
| **`BACKTRACK`** *(V3)* | 2.58 | 4 / 9 | 0.00 | **95.68** | **91.90** | 91.5 / 65.5 / 0.18 | 0.32 / 82.7 | 1.39 | **0.72**/0.94/0.66 / **504p** | **3.34** | 100 / 96.2 | 186 / **143** | 331.3 *(550.3)* | **77** / 23 / **0** / 20 / 0 *(từ 40/56/4/20/0)* |
| **`HYBRID_ALNS`** *(V3 thứ 6)* | 2.85 | 21 / — | 0.00 | **95.68** | 91.69 | **93.1** / 61.1 / **0.17** | **0.15 / 84.1** | 1.26 | 0.73/**0.93**/0.64 / 507p | 3.67 | 100 / **97.4** | **180** / 144 | 590.6 *(774.8)* | **79** / 21 / **0** / 20 / 0 *(Thuật mới)* |
| **`WSPT`** *(Blind V3)* | 3.92 | 20 / — | 0.00 | **95.68** | 90.09 | 84.4 / 75.4 / 0.23 | 0.54 / 65.4 | **0.12** | 0.76/1.50/0.62 / 545p | 4.03 | 100 / 90.3 | 229 / 179 | 101.8 *(281.9)* | **50** / 50 / **0** / 20 / 0 *(từ 0/80/20/20/0)* |
| **`LST`** *(Blind V3)* | 4.25 | 0 / 20 | 0.00 | 94.44 | 88.90 | 87.8 / **55.4** / 0.23 | 0.49 / 61.1 | 3.84 | 0.76/1.52/**0.46** / 523p | 3.82 | 100 / 87.0 | 220 / 172 | 96.3 *(285.1)* | **60** / 40 / **0** / 20 / 0 *(từ 0/100/0/20/0)* |
| **`EDF`** *(Untouched V0)* | 5.18 | 18 / 18 | 0.00 | 93.83 | 89.13 | 93.1 / 105.5 / 0.76 | 0.72 / 24.7 | 0.76 | 1.83/2.77/0.86 / 700p | 6.85 | 100 / 38.9 | 374 / 226 | **12.4** *(52.1)* | **0** / 100 / 0 / 20 / 0 *(mốc V0 giữ nguyên)* |

### 2.2. Tập 2 & Tập 3 — `FuzzGenerator v2` (`1001..1050`) và Tập Ẩn Chống Học Vẹt (`5001..5050`)

#### 2.2a. Tổng hợp toàn bộ `50` đề Fuzz v2 (`seeds 1001..1050`, `LOOSE: 24`, `TIGHT: 18`, `OVERLOAD: 8`, `paradox = 0/0`)

| Thuật toán | Hạng TB | `#1` *(6 / 5)* | `(G1)` | `P1.1%` | `Shk25` | `Rec / Stk / PCl` | `OffP / APk%` | `<10h%` | `Corne (d/a/m) / MxD` | `Ctx` | `Hab / Prf%` | `SJL / TStd` | `ms` *(Max)* | Verdict (`HIGH`/`LOW`/`SUBO`/`OVLD`/`INV`) *(Baseline → V3)* |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`BACKTRACK`** *(V3)* | **`2.30`** | 12 / 12 | 0.00 | 96.00 | **87.77** | **94.2** / 78.6 / **0.02** | 0.56 / 75.2 | 1.88 | 1.10/**0.76**/0.38 / 589p | **7.54** | 91 / 51.1 | **105** / **58** | 425.4 *(557.1)* | **23** / 19 / **0** / 8 / 0 *(từ 0/42/0/8/0)* |
| **`SCORED_GREEDY`** *(V3)* | 2.50 | **`20`** / **`21`** | 0.00 | 95.96 | 86.64 | 91.2 / **74.1** / **0.02** | 0.60 / **75.7** | 1.82 | 1.02/1.18/0.42 / 589p | 8.06 | 92 / 51.8 | **105** / 70 | 396.5 *(658.8)* | **22** / 20 / **0** / 8 / 0 *(từ 0/32/10/8/0)* |
| **`HYBRID_ALNS`** *(V3 thứ 6)* | 2.82 | 1 / — | 0.00 | 96.09 | 87.59 | 92.8 / 75.3 / **0.02** | **0.54** / **75.7** | 1.67 | **0.98**/0.82/**0.30** / **587p** | 8.58 | 94 / 52.5 | 109 / 61 | 539.4 *(731.4)* | **22** / 20 / **0** / 8 / 0 *(Thuật mới)* |
| **`LST`** *(Blind V3)* | 4.06 | 6 / 6 | 0.00 | 95.77 | **88.35** | 89.1 / 90.9 / **0.00** | 1.82 / 29.2 | 1.35 | 1.04/1.26/0.58 / 632p | 8.72 | 84 / **63.0** | 127 / 109 | 225.4 *(454.1)* | **3** / 39 / **0** / 8 / 0 *(từ 0/9/33/8/0)* |
| **`WSPT`** *(Blind V3)* | 4.58 | 2 / 2 | 0.00 | 95.72 | 82.11 | 77.5 / 120.3 / **0.00** | 2.04 / 32.6 | 0.92 | 1.36/2.22/0.72 / 654p | 8.20 | **100** / 57.0 | 127 / 152 | 241.1 *(543.1)* | **2** / 40 / **0** / 8 / 0 *(từ 0/23/19/8/0)* |
| **`EDF`** *(Untouched V0)* | 4.74 | 9 / 9 | 0.00 | **96.49** | 73.64 | 89.9 / 235.8 / 0.34 | 2.22 / 29.8 | **0.05** | 2.64/5.58/1.38 / 801p | 13.08 | **100** / 33.0 | 196 / 233 | **33.7** *(140.8)* | **0** / 42 / 0 / 8 / 0 *(mốc V0 giữ nguyên)* |

#### 2.2b. Bóc tách 3 mức độ khó của `FuzzGenerator v2` (`1001..1050`)

| Nhóm tải (`1001..1050`) | `SCORED_GREEDY` *(V3)* | `BACKTRACK` *(V3)* | `HYBRID_ALNS` *(V3 thứ 6)* | `WSPT` *(Blind V3)* | `LST` *(Blind V3)* | `EDF` *(Untouched V0)* |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`LOOSE`** *(`24`, Witness=`22`)* | **`#1` 16/24** (**`Rk 1.50`**) · **`22/24 HIGH`** · P1.1 `100%` · Shk `98.5%` · APk `91.2%` · `0` SUBO | `#1` 6/24 (`Rk 2.00`) · **`23/24 HIGH`** · P1.1 `100%` · Shk **`98.7%`** · APk **`92.5%`** · `0` SUBO | `#1` 1/24 (`Rk 2.75`) · **`22/24 HIGH`** · P1.1 `100%` · Shk `98.6%` · TStd **`57p`** · `0` SUBO | `2/24 HIGH` · `Rk 4.50` · P1.1 `100%` · Shk `97.1%` · **`0` SUBO** *(was 3)* | `3/24 HIGH` · `Rk 4.33` · P1.1 `100%` · Shk **`100%`** · **`0` SUBO** *(was 16)* | `0/24 HIGH` · `Rk 5.92` · Shk `78.7%` · TStd `312p` |
| **`TIGHT`** *(`18` đề)* | `#1` 2/18 (`Rk 3.56`) · P1.1 **`100%`** · APk **`74.9%`** · Stk **`155p`** · **`0` SUBO** *(was 10)* | **`#1` 5/18** (**`Rk 2.56`**) · P1.1 **`100%`** · Shk **`80.0%`** · Rec **`86.0%`** · TStd **`60p`** · **`0` SUBO** | `#1` 0/18 (`Rk 3.00`) · P1.1 **`100%`** · Shk `79.9%` · Crn **`1.56/2.11`** · **`0` SUBO** | `#1` 2/18 (`Rk 4.44`) · P1.1 **`100%`** · **`0` SUBO** *(was 16)* | `#1` 5/18 (`Rk 3.39`) · P1.1 **`100%`** · Shk **`80.0%`** · **`0` SUBO** *(was 17)* | `#1` 4/18 (`Rk 4.06`) · P1.1 `100%` · Rec `97.1%` · MxD `806p` |
| **`OVERLOAD`** *(`8` đề)* | `#1` 2/8 (`Rk 3.12`) · P1.1 `74.7%` · Rec **`95.6%`** · `0` INV | `#1` 1/8 (**`Rk 2.62`**) · P1.1 `75.0%` · Shk **`72.4%`** · `0` INV | `#1` 0/8 (**`Rk 2.62`**) · P1.1 `75.5%` · Stk **`98p`** · `0` INV | `#1` 0/8 (`Rk 5.12`) · P1.1 `73.2%` · `0` INV | `#1` 0/8 (`Rk 4.75`) · P1.1 `73.6%` · `0` INV | **`#1` 5/8** (`Rk 2.75`) · P1.1 **`78.1%`** · Rec `52.1%` |

#### 2.2c. Tập 3 — Tập Ẩn Chống Học Vẹt (`Held-Out Unseen Fuzz v2`, `seeds 5001..5050`, `LOOSE: 25`, `TIGHT: 15`, `OVERLOAD: 10`, `paradox = 0/0`)

| Thuật toán | Hạng TB | `#1` *(6 / 5)* | `(G1)` | `P1.1%` | `Shk25` | `Rec / Stk / PCl` | `OffP / APk%` | `<10h%` | `Corne (d/a/m) / MxD` | `Ctx` | `Hab / Prf%` | `SJL / TStd` | `ms` *(Max)* | Verdict (`H`/`L`/`S`/`O`/`I`) | **`LOOSE` `HIGH` (`25`)** | **`TIGHT` `SUBO` (`15`)** |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- | :---: | :---: |
| **`SCORED_GREEDY`** | **`2.48`** | 10 / 16 | 0.00 | 94.92 | 87.12 | 90.2 / 83.1 / **0.04** | 1.10 / 71.0 | 2.56 | 1.18/1.16/0.50 / 619p | 7.52 | 96 / 49.4 | 114 / 74 | 442.3 *(739.2)* | **25** / 15 / **0** / 10 / 0 | **`25 / 25` (`100%`)** | **`0 / 15`** |
| **`BACKTRACK`** | 2.50 | **`15`** / **`18`** | 0.00 | 94.71 | **87.29** | **94.2** / 77.1 / 0.06 | **0.84** / 71.2 | 2.70 | 1.18/**0.80**/**0.28** / 616p | **6.84** | 95 / 49.8 | 119 / 64 | 478.9 *(680.8)* | **24** / 16 / **0** / 10 / 0 | **`24 / 25` (`96%`)** | **`0 / 15`** |
| **`HYBRID_ALNS`** | 2.62 | 9 / — | 0.00 | 95.06 | 87.02 | 92.2 / **75.3** / **0.04** | 1.06 / **71.9** | 2.77 | **1.12**/0.90/0.36 / **615p** | 7.92 | 96 / 48.8 | **107** / **61** | 625.7 *(743.8)* | **25** / 15 / **0** / 10 / 0 | **`25 / 25` (`100%`)** | **`0 / 15`** |
| **`LST`** *(Blind)* | 4.50 | 1 / 1 | 0.00 | 94.48 | 84.52 | 84.1 / 97.2 / 0.10 | 2.62 / 31.1 | 2.01 | 1.36/2.06/0.56 / 649p | 7.68 | 99 / **59.9** | 126 / 129 | 237.1 *(464.3)* | **4** / 36 / **0** / 10 / 0 | `4 / 25` | **`0 / 15`** |
| **`WSPT`** *(Blind)* | 4.56 | 1 / 1 | 0.00 | 94.52 | 84.42 | 80.1 / 113.4 / 0.12 | 2.64 / 28.6 | 2.18 | 1.54/2.42/0.68 / 662p | 7.96 | **100** / 56.5 | 122 / 143 | 268.8 *(582.5)* | **3** / 37 / **0** / 10 / 0 | `3 / 25` | **`0 / 15`** |
| **`EDF`** *(Untouched)* | 4.34 | 14 / 14 | 0.00 | **95.98** | 76.69 | 86.7 / 252.3 / 0.28 | 2.20 / 30.5 | **0.02** | 2.68/6.42/1.58 / 812p | 13.72 | 97 / 31.4 | 167 / 226 | **36.5** *(123.0)* | **0** / 40 / 0 / 10 / 0 | `0 / 25` | `0 / 15` |

### 2.3. Bóc tách từng `Regime 1..6` dưới chuẩn `v2.1` (`20 seeds` mỗi Regime)

| Regime (`20` đề) | `SCORED_GREEDY` *(V3)* | `BACKTRACK` *(V3)* | `HYBRID_ALNS` *(V3 thứ 6)* | `WSPT` *(Blind V3)* | `LST` *(Blind V3)* | `EDF` *(Untouched V0)* |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R1 — Tải nhẹ** | `#1` 7/20 · **17/20 HIGH** (`APk 81.7%`, `TStd 118p`, `Stk 0m`) | `#1` 2/20 · **17/20 HIGH** (`APk 79.2%`, `TStd 101p`, `MxD 493p`) | **`#1` 11/20** (`Rk 1.50`) · **`19/20 HIGH`** (`APk 83.7%`, `Stk 0m`) | `6/20 HIGH` (`APk 58.3%`, `Stk 0m`) | `4/20 HIGH` (`APk 49.7%`, `Stk 0m`) | `0/20 HIGH` (`Rk 6.00`, `Stk 176m`, `MxD 760p`) |
| **R2 — Deadline sát** | **`0/20 SUBO`** *(was 16)* · P1.1 `100%` · Shk `70.2%` | `#1` 2/20 (`Rk 2.40`) · **`0/20 SUBO`** · Shk `77.3%` · TStd `40p` | `Rk 2.60` · **`0/20 SUBO`** · APk **`32.1%`** · TStd `38p` | **`0/20 SUBO`** *(was 20)* · P1.1 `100%` | **`0/20 SUBO`** · P1.1 `100%` | **`#1` 18/20** (`Rk 1.10`) · P1.1 `100%` · Shk `79.2%` |
| **R3 — Cú đêm & SJL** | **`#1` 16/20** (`Rk 1.20`) · **20/20 HIGH** · APk `100%` | `Rk 2.20` · **20/20 HIGH** · APk `100%` | `#1` 4/20 (`Rk 2.60`) · **20/20 HIGH** · SJL **`38p`** | `4/20 HIGH` (`APk 70.0%`, `SJL 63p`) | **16/20 HIGH** (`APk 60.0%`, `SJL 46p`) | `0/20 HIGH` (`APk 45%`, `SJL 630p`, `OffP 1.20`) |
| **R4 — DAG & `<10h`** | **`#1` 20/20** (`Rk 1.00`) · **20/20 HIGH** · APk `100%` · `<10h 0%` | `Rk 2.00` · **20/20 HIGH** · APk `100%` | `Rk 3.00` · **20/20 HIGH** · APk `100%` | **20/20 HIGH** (`0` -> `20`, `Prf 100%`) | **20/20 HIGH** (`<10h 30%` -> `0%`) | `0/20 HIGH` (`APk 9.5%`, `Prf 16.7%`) |
| **R5 — Quá tải thật** | **`#1` 14/20** (`Rk 1.30`) · P1.1 **`74.1%`** · 20 OVLD | `Rk 2.30` · P1.1 **`74.1%`** *(was 63%)* · 20 OVLD | `#1` 6/20 (`Rk 2.40`) · P1.1 **`74.1%`** · Rec **`86%`** | P1.1 **`74.1%`** · `20 OVLD` | P1.1 **`66.7%`** *(was 25.9%)* · `20 OVLD` | P1.1 `63.0%` · PCl `2.00` · `20 OVLD` |
| **R6 — Sự cố (nền)** | **20/20 HIGH** · APk `100%` · MxD `330p` · SJL `22p` | **20/20 HIGH** · `116.9ms` | **20/20 HIGH** · SJL `22p` | **`#1` 20/20** · **20/20 HIGH** (`35.1ms`) | **20/20 HIGH** (`34.1ms`) | `0/20 HIGH` (`APk 0%`, `MxD 705p`) |

### 2.4. Tần suất thẻ đỏ (`CRITICAL`) trước vs sau nâng cấp V3

* **Tập `50` Fuzz v2 (`1001..1050`):**
  * `SCORED_GREEDY`: `DAILY-CAP: 91 -> 48`, `BREAK-SAFE: 40 -> 9`, `BIO-SYNC: 35 -> 13`, `SHOCK-SAFE: 18 -> 10`, **`P1.1: 10 -> 0`**.
  * `BACKTRACK`: `DAILY-CAP: 96 -> 48`, `BREAK-SAFE: 49 -> 10`, `BIO-SYNC: 33 -> 10`, `SHOCK-SAFE: 18 -> 9` (`P1.1 = 0`).
  * `HYBRID_ALNS`: `DAILY-CAP=48, BIO-SYNC=10, BREAK-SAFE=11, SHOCK-SAFE=8` (`P1.1 = 0`).
  * `WSPT`: `DAILY-CAP: 100 -> 55, P1.1: 19 -> 0`; `LST`: `DAILY-CAP: 73 -> 52, P1.1: 33 -> 0`.
  * *(Lưu ý: `48` thẻ `DAILY-CAP` còn lại tập trung chủ yếu ở `18` đề `TIGHT` + `8` đề `OVERLOAD`, nơi lịch lớp/đề ép tổng giờ `> 600p/ngày` — cả nhóm `LOOSE` chỉ còn 1–2 thẻ trên `seed=1027/1050`.)*
* **Tập `50` Unseen Fuzz (`5001..5050`):** `SCORED_GREEDY` `DAILY-CAP=46, BIO-SYNC=16, BREAK-SAFE=13, SHOCK-SAFE=11, USER-PREF=1`; `HYBRID_ALNS` `DAILY-CAP=46, BIO-SYNC=15, BREAK-SAFE=13, SHOCK-SAFE=11, USER-PREF=1` (`0` thẻ `P1.1`).
* **Tập `120` Regimes (`1..20`):** `DAILY-CAP: 104 -> 60` (đều nằm ở `20` R2 + `20` R5 vốn kín lịch lớp), `BREAK-SAFE: 79 -> 45` (`SCORED_GREEDY`) / `37` (`HYBRID_ALNS`), `P1.1: 16 -> 0`.

### 2.5. Minh họa 2 Đề Bài Ngẫu Nhiên `Fuzz v2` Cụ Thể Sau Nâng Cấp V3

#### Ví dụ 1 — `FUZZ[TIGHT | HIGH_SCHOOL_STUDENT]` (`seed=1001`, $\rho = 0.7877$, `230/292 slots`)
* `#1 LST (FEASIBLE_BUT_LOW_PRODUCTIVITY)`: `G1=0, P1.1=100.0%, Shk25=94.92%, Rec/Stk/PCl=91/135/0, OffP/APk%=3/31, <10h=1.74%, Crn/MaxD=1/1/0/810m, Ctx=15, Hab/Prf=-/42, SJL/TStd=105/29` (`181.7ms`)
* `#2 EDF (FEASIBLE_BUT_LOW_PRODUCTIVITY)`: `G1=0, P1.1=100.0%, Shk25=86.44%, Rec/Stk/PCl=91/270/1, OffP/APk%=3/41, <10h=0.0%, Crn/MaxD=3/2/1/870m, Ctx=13, Hab/Prf=-/36, SJL/TStd=435/148` (`23.8ms`)
* `#3 WSPT (FEASIBLE_BUT_LOW_PRODUCTIVITY)`: `G1=0, P1.1=100.0%, Shk25=71.19%, Rec/Stk/PCl=82/150/0, OffP/APk%=3/49, <10h=0.0%, Crn/MaxD=1/0/1/825m, Ctx=16, Hab/Prf=-/53, SJL/TStd=165/49` (`175.8ms`)
* `#4 SCORED_GREEDY`, `#5 BACKTRACK`, `#6 HYBRID_ALNS` *(hội tụ cùng nghiệm tối ưu `APk=100%`, `Crn=0/0/0`)*: `G1=0, P1.1=100.0%, Shk25=67.8%, Rec/Stk/PCl=91/105/0, OffP/APk%=0/100, <10h=2.61%, Crn/MaxD=0/0/0/840m, Ctx=15, Hab/Prf=-/48, SJL/TStd=172/55` (`420.2ms` / `481.4ms` / `652.0ms`) — **xóa sạch `18.6%` (`SCORED_GREEDY`) & `20.3%` (`LST`) `SUBOPT` ở baseline**.

#### Ví dụ 2 — `FUZZ[TIGHT | EXAM_PREP_WEEK]` (`seed=1002`, `14 ngày`, $\rho = 0.7067$, `530/750 slots`)
* `#1 BACKTRACK`: `G1=0, P1.1=100.0%, Shk25=27.66%, Rec/Stk/PCl=92/360/0, OffP/APk%=2/69, <10h=0.75%, Crn/MaxD=5/2/3/795m, Ctx=18, Hab/Prf=-/29, SJL/TStd=60/197` (`521.4ms`)
* `#2 HYBRID_ALNS`: `G1=0, P1.1=100.0%, Shk25=26.6%, Rec/Stk/PCl=67/360/0, OffP/APk%=4/62, <10h=0.75%, Crn/MaxD=5/5/2/795m, Ctx=19, Hab/Prf=-/31, SJL/TStd=105/243` (`676.3ms`)
* `#3 EDF`: `G1=0, P1.1=100.0%, Shk25=21.28%, Rec/Stk/PCl=100/345/0, OffP/APk%=5/48, <10h=0.0%, Crn/MaxD=6/14/1/765m, Ctx=18, Hab/Prf=-/30, SJL/TStd=82/259` (`64.9ms`)
* `#4 WSPT`, `#5 LST`, `#6 SCORED_GREEDY`: `G1=0, P1.1=100.0%, Shk25=12.77%, Rec/Stk/PCl=21/360/0, OffP/APk%=7/42, <10h=0.0%, Crn/MaxD=5/14/2/795m, Ctx=23, Hab/Prf=-/31, SJL/TStd=105/312` (`539.2ms` / `316.2ms` / `512.4ms`) — **toàn bộ `6/6` solver đạt `100%` deadline thay vì `42.5% SUBOPT` (`LST`) hay `1.1–6.4%` (`SCORED_GREEDY`/`WSPT`)**.


### 2.6. Bảy Bộ Test Nổi Bật Đưa Lên Web UI (`2026-11-21`, đợt quét đơn luồng)

Chọn từ đợt quét `60` đề theo **kiểu khác biệt** giữa các thuật toán (mỗi đề làm nổi một cấp khác nhau của thứ tự từ điển). Chỉ lấy đề `7 ngày` có thuật toán chậm nhất `< 700ms` để không chạm cổng trần `1000ms`. Trên UI, mỗi bảng được giải & chấm trực tiếp và có phần giải thích sinh tự động từ số liệu ([test_showcase.py](../group03-smartschedule-baseline/web/test_showcase.py)).

| # | Đề (`source / id / seed`) | Thông số đề | Thứ hạng `#1 → #6` *(Verdict)* | Cấp quyết định thứ hạng |
| :---: | :--- | :--- | :--- | :--- |
| 1 | `regime / R1 / 3` | `7 ngày`, `EVENING`, $
ho = 0.37$ | `HYBRID_ALNS`, `BACKTRACK`, `SCORED_GREEDY` *(HIGH)* → `WSPT`, `LST`, `EDF` *(LOW)* | `#1`, `#4`, `#5` |
| 2 | `regime / R3 / 1` | `7 ngày`, `EVENING`, $
ho = 0.11$ | `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`, `LST` *(HIGH)* → `WSPT`, `EDF` *(LOW)* | `#1`, `#5` |
| 3 | `regime / R2 / 101` | `7 ngày`, `MORNING`, $
ho = 0.77$ | `BACKTRACK`, `SCORED_GREEDY`, `EDF`, `HYBRID_ALNS`, `WSPT`, `LST` *(tất cả LOW)* | `#3`, `#4` |
| 4 | `regime / R5 / 42` | `7 ngày`, `EVENING`, quá tải | `HYBRID_ALNS`, `SCORED_GREEDY`, `BACKTRACK`, `WSPT` *(P1.1 `74.1%`)* → `LST` *(`66.7%`)* → `EDF` *(`63.0%`)*, tất cả `OVLD` | `#2`, `#4`, `#10` |
| 5 | `fuzz / RANDOM / 1001` | `TIGHT`, Học sinh cấp 3, $
ho = 0.79$ | `SCORED_GREEDY`, `HYBRID_ALNS`, `LST` *(Shk25 `94.9%`)* → `EDF` *(`86.4%`)* → `WSPT` *(`71.2%`)* → `BACKTRACK` *(`67.8%`)*, tất cả LOW | `#3`, `#5`, `#7` |
| 6 | `fuzz / RANDOM / 1007` | `OVERLOAD`, SV lịch lệch, $
ho = 1.23$ | `EDF` *(P1.1 `78.3%`)* → `HYBRID_ALNS` *(`75.3%`)* → `BACKTRACK`, `SCORED_GREEDY` *(`72.2%`)* → `WSPT`, `LST` *(`71.1%`)*, tất cả `OVLD` | `#2`, `#4` |
| 7 | `fuzz / RANDOM / 1015` | `LOOSE`, SV tuần bận, $
ho = 0.38$ | `SCORED_GREEDY`, `HYBRID_ALNS`, `BACKTRACK`, `LST`, `WSPT` *(HIGH)* → `EDF` *(LOW)* | `#1`, `#5`, `#6`, `#8`, `#10` |

* **Phát hiện về độ ổn định (đo lại cùng đề Fuzz `1001`):** trong đợt quét (đơn luồng) `BACKTRACK` đạt Shk25 `67.8%` như bảng trên, nhưng `3/3` lần đo lại đơn luồng sau đó `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`, `LST` đều đạt `94.9%` — tức kết quả V3 dao động ngay cả khi không chạy song song; khi có `2` luồng khác giải lịch song song trong cùng tiến trình, `SCORED_GREEDY`/`BACKTRACK`/`HYBRID_ALNS` tụt còn `67.8%` (`3/3` lần) và `WSPT` dao động `71.2–84.8%`, còn `LST` và `EDF` giữ nguyên. Nguyên nhân là bước tối ưu V3 bị giới hạn theo **thời gian thực** (`time_budget_sec` trong [backtracking.py](../group03-smartschedule-baseline/src/solvers/backtracking.py), `deadline_ts` trong [ergonomic_engine.py](../group03-smartschedule-baseline/src/solvers/ergonomic_engine.py)): khi CPU bị chia, số vòng tối ưu giảm. Đề `1001` ở bảng trên lệch vị trí `BACKTRACK` so với Ví dụ 1 (mục 2.5) cũng vì lý do này. Vì vậy chữ mô tả viết tay trên UI không khẳng định kết quả, và mỗi bảng có nút *Chạy lại*.

---

## III. Thứ Tự Ưu Tiên Xếp Hạng `v2.1` (Cổng `#0` + 10 Cấp Từ Điển Có Dung Sai)

Tại [verdict_and_icee.py#L538-L630](../Testing_System/evaluator/verdict_and_icee.py#L538-L630), checker so sánh các thuật toán theo **bảng tổng sắp huy chương có bậc dung sai** *(hòa trong cùng bậc dung sai ở cấp trên mới xét sang cấp dưới; không quy về thang 100)*:

* **Cổng `#0` — `HARD-RULE` (Luật cứng & Trần tốc độ):** Số lỗi cứng `G1` *(nhỏ hơn thắng)* $\rightarrow$ cờ vượt trần `exec_ms > 1000ms` *(`False` thắng)*.
1. **`#1` `QUALITY-TIER` (Nhóm Đạt Chuẩn Chung):** `HIGH_PRODUCTIVITY` (`0`) < `FEASIBLE_BUT_LOW_PRODUCTIVITY` (`1`) < `OVERLOAD_TRIAGE` (`2`) < `SUBOPTIMAL_ALGORITHM_FAILURE` (`3`) < `INVALID` (`4`).
2. **`#2` `DEADLINE-VAL` (`P1.1%`):** `%` tổng `priority` các bài có hạn kịp hạn *(cao hơn thắng)*.
3. **`#3` `SHOCK-SAFE` (`Shk25%`):** `%` `priority` sống sót dưới sốc `+25%`, làm tròn bậc **`5%`** *(cao hơn thắng)*.
4. **`#4` `BREAK-SAFE` (Nghỉ & Chống Thông Mạch):** `(tỷ lệ nghỉ >10p bậc 5% ↑, số bậc 30p chuỗi học ghép load>=2 vượt 90p ↓, số lần xếp nặng sát sau lớp ↓)`.
5. **`#5` `BIO-SYNC` (Nhịp Sinh Học 2 Chiều):** `(số block load=3 đặt vào khung energy=1 dù còn khung tốt hơn ↓, % khớp Peak khả thi bậc 10% ↑)`.
6. **`#6` `NO-CRAM` (`<10h%`):** `%` khối lượng cửa sổ rộng bị dồn vô lý `<10h`, bậc **`5%`** *(thấp hơn thắng)*.
7. **`#7` `DAILY-CAP` (Giới Hạn Sức Chịu Đựng Ngày):** `(số ngày >2 ca load=3 ↓, bậc 30p ngày tổng học vượt 540p ↓, cặp nặng sát nhau ↓, kẹp bữa ăn load>=2 ↓)`.
8. **`#8` `FOCUS-FLOW` (`Ctx`):** Số lần đổi `category` công việc khác nhau với khoảng cách $\le 2$ slots *(ít hơn thắng)*.
9. **`#9` `USER-PREF` (Thói Quen & Giờ Riêng):** `(% giữ HABIT bậc 10% ↑, % khớp preferred_window bậc 10% ↑)`.
10. **`#10` `PACE-BALANCE` (Đều Tuần & Ít Lệch Pha):** `(SJL hiệu dụng bậc 30p ↓ [unpaired làm xong sớm gán 90p trung tính], Tổng Std ngày bậc 30p ↓)`.

---

## IV. Phụ Lục: Tên Tiêu Chí, Ý Nghĩa & Tác Dụng Thực Tế Với Học Sinh / Sinh Viên

### 4.1. Chú thích các cột trong bảng thống kê `v2.1`

| Ký hiệu cột | Tên dễ hiểu (Tiếng Việt) | Cấp (`v2.1`) | Ý nghĩa & Ngưỡng phạt (`CRITICAL` / `WARNING`) | Tác dụng thực tế *(Vì sao cần cho học sinh / sinh viên?)* |
| :--- | :--- | :---: | :--- | :--- |
| **`AvgRk` / `#1`** | **Hạng TB / Số lần #1** | Bảng so | Thứ hạng trung bình & số lần đứng nhất theo Cổng 0 + 10 cấp Từ Điển. | Đánh giá độ ổn định của thuật toán qua hàng trăm đề đa dạng thay vì ăn may 1 đề. |
| **`(G1)`** | **Lỗi Luật Cứng & Lịch Ghim** | Cổng `0` | Vi phạm `H1–H5`, `now_slot`, `start_after`, tách mảnh sai, thiếu giờ, mất `PINNED`. `>= 1` $\rightarrow$ **`INVALID`**. | Bảo vệ lịch bất khả xâm phạm: **không đè giờ ngủ, giờ học lớp, bữa ăn, không trễ hạn, không xê dịch block tự ghim.** |
| **`P1.1%`** | **Điểm Việc Quan Trọng Kịp Hạn** | `#2` | `%` tổng `priority` các task có hạn kịp deadline. Rơi khi $\rho \le 1$ $\rightarrow$ **`SUBOPT`**; khi $\rho > 1$ $\rightarrow$ **`OVLD`**. | Chống bẫy làm nhiều việc vặt điểm 1 để "lấy `%`" nhưng **bỏ rơi bài thi/đồ án hệ số cao**. |
| **`Shk25`** | **Đệm An Toàn Khi Lố Giờ `+25%`** | `#3` | `%` `priority` còn kịp hạn khi mọi việc lố **`+25%`**. `CRIT` `<70%` · `WARN` `<85%` *(tắt buffer mà vẫn `>=85%` chỉ ghi `INFO`)*. | Chống **vỡ lịch domino**: ước lượng thiếu giờ là bình thường ở sinh viên, nhờ khe đệm hoặc buffer mà không sập dây chuyền. |
| **`Rec/Stk/PCl`** | **Nghỉ Phục Hồi / Thông Mạch / Đệm Lớp** | `#4` | `Rec%` nghỉ `15p` sau `load=3` (`<100%` `CRIT`); `Stk` chuỗi `>=2` block `load>=2` liên tiếp (`>180m` `CRIT`, `>120m` `WARN`); `PCl` đặt `load=3` sát sau lớp dài (`>=2` `CRIT`, `=1` `WARN`). | Ngăn **học thông 5 tiếng `load=2` không nghỉ**, bảo vệ khoảng thở 15p sau tiết học ở trường và sau mỗi ca nặng. |
| **`OffP/APk%`** | **Ngược Nhịp 2 Chiều / Giờ Đỉnh Khả Thi** | `#5` | `OffP` số block `load=3` đặt vào `energy=1` khi còn chỗ tốt (`>=1` `CRIT`); `APk%` khớp `energy=3` *chỉ tính trên các bài còn khe đỉnh khả dụng* (`<25%` `CRIT`, `<50%` `WARN`). | Bảo vệ cả **Cú đêm lẫn Chim sớm** khỏi giờ trái nhịp, đồng thời **không phạt oan học sinh cấp 3** phải học chính khóa suốt buổi sáng. |
| **`<10h%`** | **Chống "Nước Đến Chân Mới Nhảy"** | `#6` | `%` khối lượng cửa sổ rộng bị dồn vô lý `<10h` sát hạn *(miễn nếu chờ Peak/DAG)*. `CRIT` `>50%` · `WARN` `>25%`. | Giúp bắt đầu sớm để còn thời gian sửa sai trước hạn, không phạt oan việc chờ đúng khung tỉnh táo. |
| **`Crn / MxD`** | **Giới Hạn Ca Nặng & Trần Giờ/Ngày** | `#7` | `Crn`: `[>2 nặng/ngày (CRIT>=1), cặp nặng sát nhau (WARN), kẹp bữa ăn load>=2 (WARN)]`; `MxD`: tổng phút **lớp + tự học** ngày cao nhất (`>600p` `CRIT`, `>540p` `WARN`). | Ngăn **ngày cày 12–13 tiếng** (cộng cả giờ trên trường) gây kiệt sức; không gán nhầm việc nhẹ 15p trước bữa ăn là lỗi. |
| **`Ctx`** | **Đổi Môn / Ngữ Cảnh Sát Nhau** | `#8` | Số cặp việc khác `category` & khác `task_id` xếp cách nhau $\le 2$ slots trong cùng ngày (`>= max(4, study_days)` `WARN`). | Giảm **tàn dư chú ý (*Attention Residue*)** khi nhảy qua lại liên tục, chuẩn hóa công bằng cho cả lịch `7 ngày` lẫn `14 ngày`. |
| **`Hab/Prf%`** | **Giữ Thói Quen & Khung Giờ Riêng** | `#9` | Chỉ check khi $\rho_{\text{total}} \le 0.85$: `Hab%` (`<50%` `CRIT`, `<80%` `WARN`) và `Prf%` khớp `preferred_window` (`<50%` `WARN`). | Ngăn AI **"gian lận"** vứt bỏ hết thói quen cá nhân của sinh viên, nhưng vẫn linh hoạt nhường bài thi khi tuần quá tải. |
| **`SJL/TStd`** | **Lệch Pha & Đều Tải Tổng Theo Tuần** | `#10` | `SJL` (`ADVANCE >60p` `WARN`, `DELAY >180p` `WARN`, không phạt làm xong sớm nghỉ cuối tuần); `TStd` độ lệch chuẩn **lớp+tự học** vượt `max(180, base_cls_std + 45p)` (`WARN`). | Giữ nhịp sinh học giữa ngày đi học – ngày nghỉ, công bằng với lịch lớp vốn lệch sẵn mà vẫn chống dồn tuần. |
| **`ms`** | **Tốc độ Giải** | Cổng `0` | Thời gian chạy (mili-giây), trần phản hồi nhanh `<= 1000ms` (`>1000ms` `WARN`). | Đảm bảo web phản hồi mượt mà khi học sinh/sinh viên tạo hoặc kéo-thả sửa lịch. |

### 4.2. Giải thích 5 nhãn `Verdict` (Đánh giá Đậu / Rớt độc lập)

| Viết tắt | Nhãn đầy đủ | Điều kiện kích hoạt (`v2.1`) | Ý nghĩa & Hành động |
| :---: | :--- | :--- | :--- |
| **`HIGH`** | `HIGH_PRODUCTIVITY` | `G1 = 0`, đủ `100%` deadline, `0 CRITICAL`, tối đa `1 WARNING`. | **Đạt chuẩn `AC` thật:** an toàn sinh học, tôn trọng thói quen, đủ nghỉ & đệm `+25%`. |
| **`LOW`** | `FEASIBLE_BUT_LOW_PRODUCTIVITY` | `G1 = 0` và `100%` deadline, nhưng dính `>= 1 CRIT` hoặc `>= 2 WARN`. | **Lịch hại người / thiếu bền vững:** đọc ngay `Top ICEE` để biết sai ở cột nào và sửa thuật toán. |
| **`SUBOPT`** | `SUBOPTIMAL_ALGORITHM_FAILURE` | Đề đủ chỗ ($\rho \le 1$) nhưng thuật toán để rơi bài có hạn. | **Thuật toán yếu (`WA` mềm):** cải thiện chiến lược chọn khe / chia mảnh. |
| **`OVLD`** | `OVERLOAD_TRIAGE` | Đề quá tải thật ($\rho > 1$ hoặc thiếu sức chứa). | **Chuyển sang đo *triage*:** giữ được càng nhiều điểm `priority` quan trọng càng tốt. |
| **`INV`** | `INVALID` *(không phải `UNVALID`)* | `G1 > 0` (đè ngủ/lớp/hạn, sai DAG, mất `PINNED`...). | **Loại ngay (`WA` cứng):** lịch bất khả thi ngoài đời thực. |

---

## V. Đánh Giá Tổng Kết Của AI (Trước vs. Sau Nâng Cấp V3 & Lựa Chọn Thuật Toán)

1. **Bước nhảy vọt toàn diện trên cả 3 tập (`220` đề × `6` thuật toán = `1.320` lượt, `0` lỗi cứng, `0` nghịch lý):**
   * **`SUBOPT` giảm về `0 / 220`** cho **tất cả các thuật toán nâng cấp** (`WSPT: 19->0` Fuzz / `20->0` Regimes; `LST: 33->0` Fuzz; `SCORED_GREEDY: 10->0` Fuzz / `16->0` Regimes; `BACKTRACK: 4->0` Regimes; `HYBRID_ALNS: 0`) nhờ tách mảnh thích ứng chuẩn `G1`, cứu hạn Kempe `1/2-eject` và sàn khả thi `build_feasibility_first_fit_state`.
   * **Nhóm `LOOSE` bứt phá từ `0%` lên mức trần Witness & `100%` tập ẩn:** Trên Fuzz `1001..1050` (`LOOSE=24`, Witness=`22/24`), **`SCORED_GREEDY` (`22/24 = 91.7%`)**, **`HYBRID_ALNS` (`22/24`)** và **`BACKTRACK` (`23/24 = 95.8%`)** đạt ngang & vượt chứng từ Witness. Trên **50 đề ẩn chưa từng đụng (`5001..5050`, `LOOSE=25`)**, **`SCORED_GREEDY` và `HYBRID_ALNS` cùng đạt `25/25 (100.0%) HIGH_PRODUCTIVITY`** (`BACKTRACK 24/25`), bác bỏ hoàn toàn rủi ro học vẹt.
   * **Bảo toàn nghiêm ngặt `Q10` & `T09` Ablation:** `EDF` giữ nguyên bản chất V0 (`0/120 HIGH`), trong khi `WSPT` và `LST` đạt `50/120` & `60/120 HIGH` mà vẫn bất biến 100% theo chronotype (`MORNING == EVENING`, không đọc `energy_profile`).
2. **Đề xuất chọn thuật toán chính thức cho SmartSchedule:**
   * **Thuật toán mặc định cho Web UI & API thời gian thực (`<= 1000 ms`):** **`SCORED_GREEDY`** — giữ hạng TB tốt nhất trên Regimes (`2.22`, `#1` `57/120` và `73/120` ở mode 5 thuật) lẫn Unseen (`2.48`), nhanh nhất trong nhóm Energy-Aware (`263.1ms` Regimes, `396.5ms` Fuzz, `22.41ms` T01), giữ vững ngôi `#1` trên `Regime 3` & `T09 Ablation`, đạt `22/24` Fuzz `LOOSE` & `25/25` Unseen `LOOSE`.
   * **Thuật toán cao cấp thiên về chất lượng tối đa (`Higher-End Design`):** **`HYBRID_ALNS`** (thuật thứ 6, alias `ALNS`/`ULTIMATE`) — đứng đầu tổng số ca **`HIGH_PRODUCTIVITY` toàn bộ `220` đề (`79/120` Regimes gồm `19/20 R1`, `22/24` Fuzz `LOOSE`, `25/25` Unseen `LOOSE`)**, dẫn đầu `APk%` (`84.1%` / `71.9%`), giảm nhẹ `TStd` xuống `61p` trên tập ẩn và khống chế `max_ms <= 774.8ms`; song hành cùng **`BACKTRACK`** (`AvgRk 2.30` trên Fuzz, `23/24 LOOSE HIGH`) làm đối chứng nhánh-cận trạng thái sống.
3. **Lưu ý tái lập kết quả cho nhóm (`2026-11-21`):** số liệu của `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS` phụ thuộc lượng CPU rảnh trong ngân sách thời gian (mục 2.6: Shk25 `94.9% → 67.8%` khi có luồng giải song song). Khi chạy benchmark nên chạy đơn luồng trên máy rảnh; về lâu dài nên chuyển giới hạn của bước tối ưu sang số vòng/số node cố định để kết quả tất định bất kể tải máy.
