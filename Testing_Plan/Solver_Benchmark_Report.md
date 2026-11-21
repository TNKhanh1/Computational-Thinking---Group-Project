# Báo Cáo Thống Kê & Đánh Giá 5 Thuật Toán Lập Lịch (`Testing_System v2.1 + Fuzzing v2`)

> [!NOTE]
> Báo cáo này tuân thủ **Rule 2** trong [AGENTS.md](../AGENTS.md), sử dụng máy chấm **phiên bản `v2.1` (Cổng `#0` + 10 cấp Từ Điển có dung sai & chống lách luật)** sau khi vá đơn điệu `_simulate_shock_survival` ([pillars.py#L867-L880](../Testing_System/evaluator/pillars.py#L867-L880)) và nâng cấp bộ sinh đề ngẫu nhiên vô hạn **`FuzzGenerator v2` (*Plant-a-Witness* + mở rộng `14 ngày`)** ([fuzz_generator.py](../Testing_System/generator/fuzz_generator.py)). Đặc tả chi tiết xem tại [Problem_Statement_And_Checker_Spec.md](Problem_Statement_And_Checker_Spec.md); các lập luận CT xem tại [CT_Rationale_Log.md](CT_Rationale_Log.md).

---

## I. Thông Tin Đợt Chạy & Phạm Vi Dữ Liệu

* **Ngày thực nghiệm:** `2026-11-20` *(bộ test đóng băng cho pha xây lại 5 thuật toán)* | **Chế độ:** `DIRECT_CONTROLLER` (`v2.1`) | **`pytest Testing_System/tests`:** **`39 / 39` passed (`18.46s`)**
* **Tập kiểm thử 1 — 6 Regimes chuẩn:** `20 seeds (1..20) × 6 Regimes = 120 đề` (`600 lượt chạy & chấm` trong `37.42s`)
  * Invariants PASS: **`120 / 120` (`20/20` ở cả 6 Regimes)** | Lỗi cứng `INVALID`: **`0 / 600`** | Nghịch lý xếp hạng (`LOW` thắng `#1` trên `HIGH`): **`0 / 120`**.
* **Tập kiểm thử 2 — Bộ sinh ngẫu nhiên vô hạn `FuzzGenerator v2` (`Plant-a-Witness`):** `50 seeds (1001..1050) = 50 đề` (`250 lượt chạy & chấm` + kiểm định 42 Witness trong `31.66s`)
  * Kiểm định lệch tier độc lập (`50 seeds × 3 tiers`): `LOOSE` **`0/50`**, `TIGHT` **`0/50`**, `OVERLOAD` **`0/50`**.
  * Cơ cấu ngẫu nhiên trên `50 seeds (1001..1050)`:
    * **4 mẫu hồ sơ thực tế:** `EXAM_PREP_WEEK` (`22`), `UNI_ASYMMETRIC` (`14`), `HIGH_SCHOOL_STUDENT` (`8`), `UNI_BUSY_WEEK` (`6`).
    * **Độ dài tuần:** `7 ngày` (`38` đề), `14 ngày` (`12` đề).
    * **3 mức độ tải:** `LOOSE` (`24`), `TIGHT` (`18`, gồm `3` đề `14 ngày TIGHT` đạt $\rho = [0.7067, 0.7472, 0.7749]$), `OVERLOAD` (`8`).
  * Kết quả Invariants & Witness Fuzz v2: **`50 / 50` ALL PASS** (`0/250 INVALID`, **`50 / 50` đơn điệu sốc `P1.1 >= Shock@+25% >= Shock@+50%`**, **`42 / 42` lời giải chứng từ Witness đạt `G1=0, P1.1=100%, not overloaded`**, `0 / 50` nghịch lý).
  * **Bằng chứng khả thi `HIGH_PRODUCTIVITY` trên Witness:**
    * Nhóm **`LOOSE` (`24` đề):** **`22 / 24` (`91.7%`)** lời giải chứng từ đạt hẳn **`HIGH_PRODUCTIVITY`** (`2` đề còn lại `LOW`) — khẳng định các đề `LOOSE` chắc chắn có nghiệm đạt chuẩn vàng con người.
    * Nhóm **`TIGHT` (`18` đề):** `18 / 18` Witness đạt `G1=0, P1.1=100%` (`LOW`) — dùng làm bài test chịu tải nước rút (vì $\rho \in [0.65, 0.83]$ đẩy tổng giờ/ngày lên `~11.3h > 10h` sinh học).

---

## II. Bảng Thống Kê 5 Thuật Toán Theo Tiêu Chí `v2.1` & Phân Bố `Verdict`

### 2.1. Tập 1 — Tổng hợp `120` test `Regimes 1–6` (`600 lượt chấm`, `paradox = 0`)

| Thuật toán | Hạng TB | `#1` | `(G1)` | `P1.1%` | `Shk25` | `Rec / Stk / PCl` | `OffP / APk%` | `<10h%` | `Corne (d/a/m) / MxD` | `Ctx` | `Hab / Prf%` | `SJL / TStd` | `ms` | Verdict (`HIGH`/`LOW`/`SUBOPT`/`OVLD`/`INV`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`SCORED_GREEDY`** | **1.89** | **71/120** | 0.00 | **94.69** | **90.09** | 91.4 / 114.8 / 0.58 | **0.01 / 84.5** | 1.12 | **0.92/1.79/0.78** / **584p** | **4.33** | 100 / **98.0** | 362 / **178** | 39.4 | **60** / 24 / **16** / 20 / 0 |
| **`BACKTRACK`** | 2.67 | 0/120 | 0.00 | 93.78 | 88.53 | **98.8** / 115.0 / **0.56** | 0.08 / 83.5 | 0.61 | 0.89/2.99/0.72 / 587p | 5.32 | 100 / **98.0** | 364 / 178 | **368.7** | **40** / 56 / **4** / 20 / 0 |
| **`EDF`** | 2.79 | 26/120 | 0.00 | 93.83 | 89.13 | 93.1 / 105.5 / 0.76 | 0.72 / 24.7 | 0.76 | 1.83/2.77/0.86 / 700p | 6.85 | 100 / 38.9 | 431 / 226 | **6.0** | **0** / 100 / 0 / 20 / 0 |
| **`WSPT`** | 3.94 | 14/120 | 0.00 | 93.49 | 89.80 | 98.0 / 116.0 / 1.06 | 0.90 / 24.7 | **0.15** | 1.38/2.64/0.78 / 703p | 5.19 | 100 / 23.5 | 393 / 253 | 8.0 | **0** / 80 / **20** / 20 / 0 |
| **`LST`** | 3.70 | 9/120 | 0.00 | **87.66** | **82.13** | **99.1 / 97.5** / 1.09 | 0.88 / 42.7 | **10.26** | 1.20/2.56/0.59 / 635p | 6.15 | 100 / 38.9 | **166** / 189 | 26.3 | **0** / 100 / 0 / 20 / 0 |

### 2.2. Tập 2 — Bộ test Ngẫu Nhiên Vô Hạn `FuzzGenerator v2` (`50 seeds: 1001..1050`, `250 lượt chấm`, `paradox = 0`)

#### 2.2a. Tổng hợp toàn bộ `50` đề Fuzz v2 (`LOOSE: 24`, `TIGHT: 18`, `OVERLOAD: 8`)

| Thuật toán | Hạng TB | `#1` | `(G1)` | `P1.1%` | `Shk25` | `Rec / Stk / PCl` | `OffP / APk%` | `<10h%` | `Corne (d/a/m) / MxD` | `Ctx` | `Hab / Prf%` | `SJL / TStd` | `ms` | Verdict (`HIGH`/`LOW`/`SUBOPT`/`OVLD`/`INV`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`SCORED_GREEDY`** | **2.14** | **19/50** | 0.00 | 95.52 | **78.31** | 83.4 / **200.7** / 0.28 | 1.60 / 43.6 | 0.37 | 2.00/5.12/0.60 / 728p | **10.84** | **100 / 88.7** | 230 / **153** | 119.2 | 0 / 32 / **10** / 8 / 0 |
| **`BACKTRACK`** | 2.24 | 13/50 | 0.00 | 96.08 | 76.34 | **97.4** / 227.4 / **0.22** | **1.52 / 45.1** | 0.30 | 2.12/5.28/0.94 / 764p | 13.16 | **100** / 88.1 | 211 / 168 | **280.5** | 0 / **42** / **0** / 8 / 0 |
| **`EDF`** | 2.40 | 13/50 | 0.00 | **96.49** | 73.64 | 89.9 / 235.8 / 0.34 | 2.22 / 29.8 | 0.05 | 2.64/5.58/1.38 / 801p | 13.08 | **100** / 33.0 | **196** / 234 | **11.7** | 0 / **42** / **0** / 8 / 0 |
| **`WSPT`** | 3.36 | 5/50 | 0.00 | 94.17 | 73.86 | 79.2 / 241.8 / 0.16 | 2.32 / 29.9 | **0.00** | 2.38/5.08/1.14 / 793p | 13.76 | **100** / 34.6 | 209 / 282 | 15.5 | 0 / 23 / **19** / 8 / 0 |
| **`LST`** | 4.86 | 0/50 | 0.00 | **81.45** | **58.59** | 75.9 / 200.1 / 0.34 | 3.46 / 25.3 | **11.35** | **1.50/3.46/0.50 / 688p** | 11.24 | 99.6 / 31.5 | 220 / 159 | 53.4 | 0 / 9 / **33** / 8 / 0 |

#### 2.2b. Bóc tách 3 mức độ khó của `FuzzGenerator v2`

| Nhóm tải Fuzz v2 | `SCORED_GREEDY` | `BACKTRACK` | `EDF` | `WSPT` | `LST` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`LOOSE`** *(`24` đề)* | **`#1` 15/24** (**`Rk 1.58`**) · P1.1 `100%` · Shk **`84.7%`** · Stk **`143p`** · Prf `95.3%` | `#1` 2/24 (`Rk 2.54`) · P1.1 `100%` · APk **`47.2%`** · `306ms` | `#1` 3/24 (`Rk 2.92`) · P1.1 `100%` · MxD `786p` · Prf `31.9%` | `#1` 4/24 (`Rk 3.12`) · **3/24 SUBOPT** · P1.1 `99.8%` | `#1` 0/24 (`Rk 4.83`) · **16/24 SUBOPT** · `<10h 15.6%` |
| **`TIGHT`** *(`18` đề)* | `#1` 1/18 (`Rk 3.06`) · **10/18 SUBOPT** · P1.1 `96.4%` · Shk **`74.7%`** | **`#1` 10/18** (**`Rk 1.50`**) · P1.1 **`100%`** · Rec **`97.6%`** · **`0` SUBOPT** | `#1` 7/18 (`Rk 1.78`) · P1.1 **`100%`** · **`0` SUBOPT** · MxD `806p` | `#1` 0/18 (`Rk 3.78`) · **16/18 SUBOPT** · P1.1 `95.4%` | `#1` 0/18 (`Rk 4.89`) · **17/18 SUBOPT** · P1.1 `72.6%` |
| **`OVERLOAD`** *(`8` đề)* | **`#1` 3/8** (**`Rk 1.75`**) · P1.1 **`80.1%`** · Prf **`69.5%`** | `#1` 1/8 (`Rk 3.00`) · P1.1 `75.5%` · Shk **`67.7%`** · Rec **`97.7%`** | `#1` 3/8 (`Rk 2.25`) · P1.1 `78.1%` · `HP 100%` · MxD `834p` | `#1` 1/8 (`Rk 3.12`) · P1.1 `74.5%` | `#1` 0/8 (`Rk 4.88`) · P1.1 `65.1%` · Shk `60.3%` |

### 2.3. Bóc tách từng `Regime 1..6` dưới chuẩn `v2.1` (`20 seeds` mỗi Regime)

| Regime (`20` đề) | `SCORED_GREEDY` | `BACKTRACK` | `EDF` | `WSPT` | `LST` |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **R1 — Tải nhẹ** | `#1` 5/20 · **0/20 HIGH** *(Stk `244m`, MxD `729m`)* | `#1` 0/20 · **0/20 HIGH** *(Stk `272m`, `502ms`)* | **`#1` 11/20** · Stk `176m`, OffP `2.15`, APk `29%` | `#1` 0/20 · OffP `1.95` | `#1` 4/20 · SJL `52m`, OffP `3.10` |
| **R2 — Deadline dồn sát** | `#1` 0/20 · **16/20 SUBOPT** · Rec `66.1%` | `#1` 0/20 · **4/20 SUBOPT** · P1.1 `99.7%` | **`#1` 15/20** · P1.1 `100%` · 20 LOW | `#1` 0/20 · **20/20 SUBOPT** · P1.1 `86.9%` | `#1` 5/20 · P1.1 `100%` · 20 LOW |
| **R3 — Cú đêm & SJL** | **`#1` 20/20** · **20/20 HIGH** · APk `100%` · Crn `0/0/0` | `#1` 0/20 · **0/20 HIGH** *(Crn `0/2/0`)* | `#1` 0/20 · OffP `1.20` · APk `45%` | `#1` 0/20 · PCl `1.00` · SJL `630m` | `#1` 0/20 · PCl `1.20` · Prf `33%` |
| **R4 — DAG & `<10h`** | **`#1` 20/20** · **20/20 HIGH** · Stk `0m` | **`#1` 0/20** · **20/20 HIGH** | `#1` 0/20 · APk `9.5%` · Crn `1/2/0` | `#1` 0/20 · APk `9.5%` · Prf `0%` | `#1` 0/20 · `<10h 30.0%` · 20 LOW |
| **R5 — Quá tải thật** | `#1` 6/20 · P1.1 `71.5%` · Prf `100%` · **20 OVLD** | `#1` 0/20 · P1.1 `63.0%` · **20 OVLD** | `#1` 0/20 · P1.1 `63.0%` · **20 OVLD** | **`#1` 14/20** · P1.1 **`74.1%`** · **20 OVLD** | `#1` 0/20 · P1.1 **`25.9%`** · **20 OVLD** |
| **R6 — Sự cố (nền)** | **`#1` 20/20** · **20/20 HIGH** · `5.7ms` | `#1` 0/20 · **20/20 HIGH** | `#1` 0/20 · APk `0%` · MxD `705m` | `#1` 0/20 · APk `0%` · MxD `705m` | `#1` 0/20 · Stk `150m` · APk `0%` |

### 2.4. Tần suất thẻ đỏ (`CRITICAL`) trên `50` đề Fuzz v2 & `120` đề Regimes

* **Trên `50` đề Fuzz v2 (`seeds 1001..1050`):**
  * **`SCORED_GREEDY`:** `CRIT={'DAILY-CAP': 91, 'BREAK-SAFE': 40, 'BIO-SYNC': 35, 'SHOCK-SAFE': 18, 'P1.1': 10}`
  * **`BACKTRACK`:** `CRIT={'DAILY-CAP': 96, 'BREAK-SAFE': 49, 'BIO-SYNC': 33, 'SHOCK-SAFE': 18}` *(0 thẻ P1.1)*
  * **`EDF`:** `CRIT={'DAILY-CAP': 100, 'BREAK-SAFE': 50, 'BIO-SYNC': 40, 'SHOCK-SAFE': 19}` *(0 thẻ P1.1)*
  * **`WSPT`:** `CRIT={'DAILY-CAP': 100, 'BREAK-SAFE': 52, 'BIO-SYNC': 40, 'SHOCK-SAFE': 22, 'P1.1': 19}`
  * **`LST`:** `CRIT={'DAILY-CAP': 73, 'BREAK-SAFE': 50, 'BIO-SYNC': 43, 'P1.1': 33, 'SHOCK-SAFE': 32}`
* **Trên `120` đề Regimes:** `SCORED_GREEDY` `DAILY-CAP(104) > BREAK-SAFE(79) > P1.1(16) > SHOCK-SAFE(14) > BIO-SYNC(12)` | `BACKTRACK` `DAILY-CAP(100) > BREAK-SAFE(81) > SHOCK-SAFE(23) > BIO-SYNC(13) > P1.1(4)` | `EDF` `DAILY-CAP(200) > BIO-SYNC(96) > BREAK-SAFE(81) > SHOCK-SAFE(20)`.

### 2.5. Minh họa 2 Đề Bài Ngẫu Nhiên `Fuzz v2` Cụ Thể & Kết Quả Chấm 5 Thuật Toán

#### Ví dụ 1 — `FUZZ[TIGHT | HIGH_SCHOOL_STUDENT]` (`seed=1001`)
* **Đề bài sinh ngẫu nhiên (`Plant-a-Witness`):** `FUZZ[TIGHT | HIGH_SCHOOL_STUDENT]`, nhịp **`AFTERNOON`**, `horizon=7 ngày`, `buffer=COGNITIVE_LOAD`, tải thực **$\rho = 0.7877$ (`230/292 slots`, $\rho_{\text{deadline}} = 0.7877$)**.
* **Lời giải & bảng chấm 5 thuật toán (`v2.1`):**
  * `#1 BACKTRACK` (`LOW`): `G1=0, P1.1=100.0%, Shk25=86.4%, Rec/Stk/PCl=100/270/0, OffP/APk%=1/53, <10h=0.0%, Crn/MaxD=1/5/1/840m, Ctx=12, Prf=85%` (`224.2ms`)
  * `#2 EDF` (`LOW`): `G1=0, P1.1=100.0%, Shk25=86.4%, Rec/Stk/PCl=91/270/1, OffP/APk%=3/41, <10h=0.0%, Crn/MaxD=3/2/1/870m, Ctx=13, Prf=36%` (`7.6ms`)
  * `#3 WSPT` (`SUBOPT`): rơi `1.7%` (`P1.1=98.3%`), `Shk25=88.1%`, `Rec/Stk/PCl=100/225/0`, `OffP/APk%=2/80`, `Crn/MaxD=1/4/1/900m`, `Ctx=12`, `Prf=46%` (`13.0ms`)
  * `#4 SCORED_GREEDY` (`SUBOPT`): rơi `18.6%` (`P1.1=81.4%`), `Shk25=66.1%`, `Rec/Stk/PCl=100/225/0`, `OffP/APk%=3/53`, `Crn/MaxD=1/5/0/795m`, `Ctx=8`, `Prf=96%` (`63.8ms`)
  * `#5 LST` (`SUBOPT`): rơi `20.3%` (`P1.1=79.7%`), `Shk25=72.9%`, `Rec=25%`, `OffP/APk%=8/0`, `<10h=9.0%`, `Crn/MaxD=1/4/1/870m`, `Ctx=6`, `Prf=20%` (`31.2ms`)

#### Ví dụ 2 — `FUZZ[TIGHT | EXAM_PREP_WEEK]` (`seed=1002`, `14 ngày` đã đủ tải thật)
* **Đề bài sinh ngẫu nhiên (`Plant-a-Witness`):** `FUZZ[TIGHT | EXAM_PREP_WEEK]`, nhịp **`AFTERNOON`**, `horizon=14 ngày`, `buffer=HABIT`, tải thực **$\rho = 0.7067$ (`530/750 slots`, $\rho_{\text{deadline}} = 0.7067$)** *(đạt ngưỡng `TIGHT` $\ge 0.65$ thay cho `0.1453` ở bản v1)*.
* **Lời giải & bảng chấm 5 thuật toán (`v2.1`):**
  * `#1 BACKTRACK` (`LOW`): `G1=0, P1.1=100.0%, Shk25=47.9%, Rec/Stk/PCl=100/315/0, OffP/APk%=5/81, <10h=0.8%, Crn/MaxD=4/14/0/720m, Ctx=23, Prf=94%` (`705.3ms`)
  * `#2 EDF` (`LOW`): `G1=0, P1.1=100.0%, Shk25=21.3%, Rec/Stk/PCl=100/345/0, OffP/APk%=5/48, <10h=0.0%, Crn/MaxD=6/14/1/765m, Ctx=18, Prf=30%` (`21.0ms`)
  * `#3 SCORED_GREEDY` (`SUBOPT`): rơi `1.1%` (`P1.1=98.9%`), `Shk25=56.4%`, `Rec/Stk/PCl=100/270/0`, `OffP/APk%=5/78`, `<10h=0.8%`, `Crn/MaxD=4/13/1/735m`, `Ctx=15`, `Prf=100%` (`581.2ms`)
  * `#4 WSPT` (`SUBOPT`): rơi `6.4%` (`P1.1=93.6%`), `Shk25=39.4%`, `Rec/Stk/PCl=33/345/0`, `OffP/APk%=5/46`, `<10h=0.0%`, `Crn/MaxD=4/12/5/810m`, `Ctx=15`, `Prf=35%` (`38.1ms`)
  * `#5 LST` (`SUBOPT`): rơi `42.5%` (`P1.1=57.5%`), `Shk25=23.4%`, `OffP/APk%=3/22`, `<10h=8.4%`, `Crn/MaxD=1/3/0/525m`, `Ctx=12`, `Prf=15%` (`121.8ms`)

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

## V. Đánh Giá Sơ Bộ Của AI (Hệ thống Test Đóng Băng `v2.1 + Fuzz v2`)

1. **Bộ sinh đề & Máy chấm đã đạt trạng thái "đóng băng" tin cậy để làm thước đo xây lại 5 thuật toán:**
   * **`39/39 pytest passed`**, **`120/120` Regimes PASS**, **`50/50` Fuzz v2 PASS**, **`0/170` nghịch lý xếp hạng**, **`0/150` lệch tier (`LOOSE`/`TIGHT`/`OVERLOAD`)**, **`14 ngày TIGHT` $\rho \in [0.7067, 0.7749]$**.
   * **Bằng chứng cứng cho thuật mới:** Ở **`LOOSE` (`24` đề)**, chính **`22 / 24` (`91.7%`)** lời giải chứng từ Witness đã đạt **`HIGH_PRODUCTIVITY`** → khẳng định đề hoàn toàn khả thi đạt chuẩn vàng; việc cả 5 thuật cũ chỉ đạt **`0 / 24 HIGH`** ở `LOOSE` 100% là lỗi thiết kế của 5 thuật toán cũ.
   * Ở **`TIGHT` (`18` đề, $\rho \in [0.65, 0.83]$)**, tải thực ~`11.3h/ngày` đóng vai trò *stress test nước rút* phân loại sức bền không rớt hạn (`P1.1=100%`) — `18/18` Witness chứng minh chắc chắn giải đủ 100% deadline.
2. **Bức tranh tổng kết 5 thuật toán baseline trước khi "đập đi xây lại":**
   * **`SCORED_GREEDY`:** Đứng **`#1` nhiều nhất (`19/50`, `AvgRk 2.14`)** nhờ thống trị **`LOOSE` (`15/24`, `AvgRk 1.58`, `Prf=95.3%`, `Stk=143p`)** và `OVERLOAD` (`3/8`, `80.1%`), nhưng **gãy ở `TIGHT` (`10/18 SUBOPT`, `AvgRk 3.06`)** và dính `91` thẻ đỏ `DAILY-CAP` do chưa tính tải tích lũy ngày.
   * **`BACKTRACK`:** **Không rơi bài khả thi nào (`0/42 SUBOPT`, `100%` ở cả `LOOSE` & `TIGHT`)**, dẫn đầu **`TIGHT` (`10/18`, `AvgRk 1.50`, `Rec=97.6%`)**, nhưng chậm nhất (`280.5ms`) và vẫn nhồi ngày (`96` thẻ đỏ `DAILY-CAP`).
   * **`EDF`:** **`0/42 SUBOPT`** (`11.7ms`, `#2` ở `TIGHT`), nhưng mù sinh học (`APk=29.8%`, `Prf=33.0%`, `MxD=801p`).
   * **`WSPT` & `LST`:** Sụp đổ ở `TIGHT` (`16/18` và `17/18 SUBOPT`; riêng `LST` rớt `16/24` ngay ở `LOOSE`, `AvgRk 4.86`).
3. **Kim chỉ nam khi xây lại 5 thuật toán mới (dựa trên dữ liệu thẻ đỏ `ICEE`):**
   * Muốn bứt phá từ `0%` lên mức cao `HIGH_PRODUCTIVITY` ở `LOOSE` và xóa sạch `SUBOPT` ở `TIGHT`, bộ thuật toán mới bắt buộc phải có: *(1)* Bộ đếm trần tải ngày (`<= 2` ca nặng, tổng `lớp+tự học <= 540p`), *(2)* Ngắt chuỗi ghép `load>=2 <= 120p` + đệm `15p` sau `load=3` & lớp dài, *(3)* Khóa tránh `energy=1` cho `load=3`, và *(4)* Pha cứu hạn (*feasibility-first rescue*) khi tải tiến gần $\rho \rightarrow 0.85$.
