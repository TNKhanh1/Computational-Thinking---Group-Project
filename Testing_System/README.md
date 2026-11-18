# Hệ Thống Kiểm Thử 2 Phần & Đánh Giá Năng Suất Lịch Trình (`Testing_System`)

Thư mục độc lập triển khai trọn vẹn bản kế hoạch đã chốt trong `Testing_Plan/Testing_Plan.md` mà **không chỉnh sửa bất kỳ file nào của baseline**.

## Kiến trúc
- **Tầng 0–2 (`evaluator/`):** `ScheduleEvaluator` thuần miền nghiệp vụ (`INV-1..INV-6`):
  - **Tầng 0 (`gates.py`):** `G1` (H1–H5 + `start_after`, `now_slot`, splitting/order, `planned_duration_min`, `PINNED` integrity) & `G2` (tỷ lệ tải $\rho$ sau `expand_personal_habits -> apply_estimate_buffer`).
  - **Tầng 1 (`pillars.py`):** 4 Trụ cột Productivity `P1–P4`, gồm Circular SJL theo Smarr & Schirmer — trung vị pha tròn của block tự học, ngày có lớp − ngày không lớp (`P2.3`), nghỉ `> 10 phút` (≥1 slot không mang tải) sau block `load=3` (`P2.2`), vector Corne so sánh từ điển (`P3.2`), chống ép *Owl* học sáng `06:00–12:00` (`P2.1`), chống dồn `< 10h` có miễn trừ *strategic idling* (`P1.2`), mô phỏng sốc `+25% / +50%` trên **thời lượng ước lượng thô `raw duration_min`** (`P4.1`), và ổn định sửa lịch $D(\pi_0,\pi_1)$, `Eq 1st`, `Orig%`, `Diff%` (`P4.2`).
  - **Tầng 2 (`verdict_and_icee.py`):** Phán quyết Từ Điển (`HIGH_PRODUCTIVITY`, `FEASIBLE_BUT_LOW_PRODUCTIVITY`, `OVERLOAD_TRIAGE`, `SUBOPTIMAL_ALGORITHM_FAILURE`, `INVALID`), Top 3–5 cảnh báo `ICEE` và đối chiếu chéo 5 solver.
- **Phần 1 (`generator/`):** `InputGenerator` sinh input xác định theo `(regime, seed)` qua **6 Regimes** và kiểm tra khả thi trên lưới thật sau khi áp buffer.
- **Chạy Project & Phần 2 (`runner/`):** Chạy qua cả Direct Controller (5 solvers + Local/Ripple/FullRebuild/Overrun) và HTTP API E2E với SQLite cô lập.

## Cách chạy nhanh (từ thư mục gốc workspace)
```powershell
group03-smartschedule-baseline\.venv\Scripts\python.exe -m pytest Testing_System/tests -v
group03-smartschedule-baseline\.venv\Scripts\python.exe -m Testing_System.cli --mode full --seeds 42
group03-smartschedule-baseline\.venv\Scripts\python.exe -m Testing_System.cli --mode http --seeds 42
```
Trên Windows console nên đặt `PYTHONIOENCODING=utf-8` trước khi chạy CLI để in được tiếng Việt.

