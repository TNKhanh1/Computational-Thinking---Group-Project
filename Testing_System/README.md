# Hệ Thống Kiểm Thử 2 Phần & Đánh Giá Năng Suất Lịch Trình (`Testing_System v2.1 + Fuzz v2`)

Thư mục độc lập triển khai trọn vẹn bản kế hoạch đã chốt trong `Testing_Plan/Testing_Plan.md` và đặc tả `v2.1` (`Testing_Plan/Problem_Statement_And_Checker_Spec.md`) mà **không chỉnh sửa bất kỳ file nào của baseline**.

## Kiến trúc
- **Tầng 0–2 (`evaluator/`):** `ScheduleEvaluator` thuần miền nghiệp vụ (`INV-1..INV-6`):
  - **Cổng `#0 HARD-RULE` (`gates.py`):** `G1` (`H1–H5` + `start_after`, `now_slot`, splitting/order, `planned_duration_min`, `PINNED` integrity) + SLA thực thi `<= 1000 ms`, và `G2` (tỷ lệ tải $\rho$ sau `expand_personal_habits -> apply_estimate_buffer`).
  - **Tầng 1 (`pillars.py`):** 4 Trụ cột Productivity `P1–P4`, gồm Circular SJL theo Smarr & Schirmer — trung vị pha tròn của block tự học, ngày có lớp − ngày không lớp (`P2.3`), nghỉ `> 10 phút` (≥1 slot không mang tải) sau block `load=3` (`P2.2`), vector Corne so sánh từ điển (`P3.2`), chống ép *Owl* học sáng `06:00–12:00` (`P2.1`), chống dồn `< 10h` có miễn trừ *strategic idling* (`P1.2`), mô phỏng sốc `+25% / +50%` trên **thời lượng ước lượng thô `raw duration_min`** (`P4.1`), và ổn định sửa lịch $D(\pi_0,\pi_1)$, `Eq 1st`, `Orig%`, `Diff%` (`P4.2`).
  - **Tầng 2 (`verdict_and_icee.py`):** Xếp hạng **10 cấp Từ Điển có dung sai (`v2.1`)** bắt đầu từ `#1 QUALITY-TIER` (`HIGH_PRODUCTIVITY`, `FEASIBLE_BUT_LOW_PRODUCTIVITY`, `OVERLOAD_TRIAGE`, `SUBOPTIMAL_ALGORITHM_FAILURE`, `INVALID`) → `#2 DEADLINE-VAL` → `#3 SHOCK-SAFE` → `#4 BREAK-SAFE` → `#5 BIO-SYNC` → `#6 NO-CRAM` → `#7 DAILY-CAP` → `#8 FOCUS-FLOW` → `#9 USER-PREF` → `#10 PACE-BALANCE`; kèm **Top 5 cảnh báo `ICEE`** tiếng Việt và đối chiếu chéo đa solver (`5` hoặc `6` solvers gồm `HYBRID_ALNS`).
- **Phần 1 (`generator/`):**
  - `InputGenerator`: Sinh input xác định theo `(regime, seed)` qua **6 Regimes** và kiểm tra khả thi trên lưới thật sau khi áp buffer.
  - `FuzzGenerator v2` (*Plant-a-Witness*): Sinh đề ngẫu nhiên vô hạn có kiểm soát hỗ trợ **`7/14 ngày`** và 3 mức tải **`LOOSE` / `TIGHT` / `OVERLOAD`** kèm lịch chứng nhân (*Witness*) đảm bảo tính khả thi toán học.
- **Chạy Project & Phần 2 (`runner/`):** Chạy qua cả Direct Controller (các solver + Local/Ripple/FullRebuild/Overrun) và HTTP API E2E với SQLite cô lập.

## Bộ kiểm thử (`39/39` pytest tests)
Bao gồm kiểm định bất biến kiến trúc (`INV-1..6`), cặp đối chứng tự kiểm tra (`Contrast Pairs` — Gombolay §5.3), toàn bộ 6 Regimes, và `FuzzGenerator v2` + Checker `v2.1`.

## Cách chạy nhanh (từ thư mục gốc workspace)
```powershell
$env:PYTHONIOENCODING = "utf-8"

# 1. Chạy toàn bộ 39 bài kiểm thử tự động của Testing_System v2.1 + Fuzz v2
group03-smartschedule-baseline\.venv\Scripts\python.exe -B -m pytest Testing_System/tests -v

# 2. Chạy Contrast Pairs Self-Test
group03-smartschedule-baseline\.venv\Scripts\python.exe -B -m Testing_System.cli --mode contrast

# 3. Chạy 6 Regimes (Direct Controller hoặc HTTP API E2E)
group03-smartschedule-baseline\.venv\Scripts\python.exe -B -m Testing_System.cli --mode full --seeds 42
group03-smartschedule-baseline\.venv\Scripts\python.exe -B -m Testing_System.cli --mode http --seeds 42

# 4. Chạy FuzzGenerator v2 (ngẫu nhiên có kiểm soát theo tier)
group03-smartschedule-baseline\.venv\Scripts\python.exe -B -m Testing_System.cli --mode fuzz --count 10 --start-seed 1001 --tier auto
group03-smartschedule-baseline\.venv\Scripts\python.exe -B -m Testing_System.cli --mode fuzz --seeds 1041 1001 1049 --tier auto
```
Trên Windows console nên đặt `$env:PYTHONIOENCODING="utf-8"` trước khi chạy CLI để in được tiếng Việt.
