# M5_00 — Master Execution Index & Agent Handoff Protocol (`M5` Lê Tiến Bình)
**Thành viên:** `M5` — Lê Tiến Bình (`25125007` · Builder 1 — Core Engineering & Idea Lead)  
**Nhánh Git bắt buộc:** `v1.0-alpha/ltbinh-m5-cross-week-adaptation-and-repair` *(đã khởi tạo từ `main` `8f334b1`)*  
**Đợt Merge:** **Wave 1A — Ưu tiên Merge đầu tiên**  
**Tài liệu gốc tham chiếu:** [`M5_Le_Tien_Binh.md`](./M5_Le_Tien_Binh.md) · [`M5_Plan_Verification_And_Audit.md`](./M5_Plan_Verification_And_Audit.md) · [`../README_agents.md`](../README_agents.md)

---

## 1. GIAO THỨC BÀN GIAO CHO AI AGENT MỚI (TOKEN-EXHAUSTION HANDOFF PROTOCOL)

> [!IMPORTANT]
> **Nếu bạn là một AI Agent mới tiếp nhận dở dang công việc (do phiên trước hết token/context), hãy thực hiện ĐÚNG 5 bước sau (mất < 60 giây, KHÔNG cần đọc lại toàn bộ repo):**
> 1. Chạy lệnh kiểm tra nhánh & trạng thái hiện tại:
>    ```powershell
>    git branch --show-current; git status -sb
>    ```
>    Đảm bảo đang đứng ở nhánh **`v1.0-alpha/m5-cross-week-adaptation-and-repair`**. Nếu chưa, chạy `git checkout v1.0-alpha/m5-cross-week-adaptation-and-repair`.
> 2. Nhìn vào **Bảng Theo Dõi Tiến Độ 4 Giai Đoạn (Mục 3 bên dưới)**: tìm **Giai đoạn đầu tiên còn đánh dấu `[ ] PENDING` hoặc `[~] IN_PROGRESS`**.
> 3. Chỉ mở và đọc đúng file kế hoạch chi tiết của giai đoạn đó (`M5_01_...md`, `M5_02_...md`, `M5_03_...md`, hoặc `M5_04_...md`) — mỗi file đã ghi sẵn **đầy đủ chữ ký hàm, công thức toán, mã giả chi tiết, ca biên và lệnh kiểm thử độc lập**.
> 4. Tuyệt đối tuân thủ **Ma Trận Khóa File `0%` Xung Đột (Mục 2)** dưới đây.
> 5. Ngay khi code & chạy pass 100% lệnh kiểm thử của giai đoạn đó, hãy cập nhật trạng thái thành `[x] DONE` trong file giai đoạn đó VÀ trong Bảng Mục 3 của file `M5_00_Master_Index.md` này trước khi chuyển sang giai đoạn kế tiếp!

---

## 2. MA TRẬN KHÓA FILE TUYỆT ĐỐI (`0%` MERGE CONFLICT GUARANTEE)

### ✅ CÁC FILE `M5` ĐƯỢC PHÉP TẠO MỚI HOẶC CHỈNH SỬA (DUY NHẤT)
| Hành động | Đường dẫn File | Giai đoạn thực hiện | Ghi chú kiến trúc bắt buộc |
| :---: | :--- | :---: | :--- |
| **CREATE** | `smartschedule/core/cross_week_adapter.py` | **Stage 1 (`M5_01`)** | **Pure Layer 1 (`INV-1`):** CHỈ import Python stdlib + `smartschedule.core.{config, estimate_buffer, models, utils}`. CẤM import `api`, `nlp`, `fastapi`, `storage`, `solvers`. |
| **MODIFY** | `smartschedule/core/controller.py` | **Stage 1 (`M5_01`)** | `M5` độc quyền sở hữu. Giữ nguyên hành vi mặc định `solve_schedule(..., algorithm="EDF")` cho `Testing_System`. |
| **CREATE** | `smartschedule/api/chat/disruption_chat.py` | **Stage 2 (`M5_02`)** | Module xử lý sự cố đột xuất qua Chat (`Pattern P8`), tương thích kép cho cả `app.py` và `M4` (`handlers.py`). |
| **MODIFY** | `smartschedule/api/app.py` | **Stage 3 (`M5_03`)** | `M5` độc quyền sở hữu. Mở 6 API mới + cầu nối telemetry người dùng thật + điều hướng an toàn `disruption_chat`. |
| **CREATE** | `tests/logical/test_disruption_and_cross_week_adapter.py` | **Stage 4 (`M5_04`)** | Bộ kiểm thử toàn diện đơn vị + tích hợp FastAPI + 5 bất biến toán học của `M4`. |
| **MODIFY** | `v1.0-alpha-plan/Sprint_Tasks/M5_Le_Tien_Binh.md` | **Stage 4 (`M5_04`)** | Tick `[x]` vào 4 ô checklist cuối file sau khi toàn bộ test xanh 100%. |
| **PLAN** | `v1.0-alpha-plan/Sprint_Tasks/M5_00..04_*.md` | **Pre-Build / Tracking** | Bộ tài liệu kế hoạch & theo dõi tiến độ riêng của `M5` (không đụng bất kỳ file `M1..M4, M6..M7` nào). |

### ⛔ CÁC FILE CẤM ĐỤNG CHẠM TUYỆT ĐỐI (`DO NOT TOUCH` — TRÁNH XUNG ĐỘT GIT & VỠ BẤT BIẾN)
- **CẤM SỬA BỘ GIẢI & DỮ LIỆU GỐC:** `smartschedule/core/solvers/*` (tất cả 6 solvers + `local_repair.py` + `ergonomic_engine.py`), `smartschedule/core/models.py`, `smartschedule/core/storage.py`, `smartschedule/core/calibration.py`, `data/presets/*`, `v1.0-alpha-plan/Testing_System/*`.
- **CẤM SỬA FILE CỦA ĐỒNG ĐỘI:**
  - `smartschedule/api/chat/handlers.py`, `lifecycle_intents.py`, `smartschedule/nlp/intent_classifier.py` (của **`M4` Trọng Tiến**)
  - `smartschedule/nlp/context_router.py`, `free_context_engine.py`, `smartschedule/api/chat/thinking_stage.py` (của **`M2` Nguyên Khánh**)
  - `smartschedule/api/chat/profile_habit_chat.py`, `tools/member_eval/*` (của **`M3` Minh Anh**)
  - `smartschedule/core/student_simulator.py`, `smartschedule/nlp/doc_attachment_parser.py`, `tests/architecture/*`, `smartschedule/ui/css/*` (của **`M7` Gia Bảo**)
  - `smartschedule/ui/*` (của **`M6` Minh Nhật** & **`M1` Đức Minh**)
  - `agents/commit_changes.md`, `v1.0-alpha-plan/README.md`, `v1.0-alpha-plan/README_agents.md`, `environments/requirements.txt` (`0` thư viện ngoài mới!).

---

## 3. BẢNG THEO DÕI TIẾN ĐỘ 4 GIAI ĐOẠN BUILD (STAGE PROGRESS TRACKER)

| Giai đoạn | File Kế Hoạch Chi Tiết | Phạm Vi Build Chính | Điểm Modify Đã Tích Hợp (`Audit M-1..M-8`) | Trạng Thái |
| :---: | :--- | :--- | :---: | :---: |
| **Stage 1** | [`M5_01_Stage1_CrossWeekAdapter_And_Controller.md`](./M5_01_Stage1_CrossWeekAdapter_And_Controller.md) | Tạo `cross_week_adapter.py` (`Pattern P13`) + Nâng cấp `controller.py` (`apply_estimate_buffer` giữ alpha từng môn, `build_empty_current_week_profile`, `solve_adaptive`) | `M-1`, `M-2`, `M-3`, `M-4`, `M-5 (core)`, `M-7` | `[x] DONE` |
| **Stage 2** | [`M5_02_Stage2_Disruption_Chat_LocalRepair.md`](./M5_02_Stage2_Disruption_Chat_LocalRepair.md) | Tạo `disruption_chat.py` (`Pattern P8` `LOCAL_INSERTION` $\ge 90\%$ ổn định, hỏi lại khi thiếu giờ, hậu kiểm công thái học `load=3`, tương thích kép cho `M4` & `app.py`) | `M-5 (log)`, `M-6 (filter)`, `M-8` | `[x] DONE` |
| **Stage 3** | [`M5_03_Stage3_FastAPI_Endpoints_And_MultiWeekSim.md`](./M5_03_Stage3_FastAPI_Endpoints_And_MultiWeekSim.md) | Nâng cấp `app.py`: mở 6 API (`init-real-week`, `tasks/delete`, `fixed-events/upsert`, `fixed-events/delete`, `adapt-next-week`, `simulation/multi-week` kèm fallback simulator `< 500ms`) + nối `disruption_chat` | `M-5 (API)`, `M-6 (SLA)`, `M-7 (API)` | `[x] DONE` |
| **Stage 4** | [`M5_04_Stage4_TestSuite_AuditGate_And_PR.md`](./M5_04_Stage4_TestSuite_AuditGate_And_PR.md) | Viết `tests/logical/test_disruption_and_cross_week_adapter.py` (18+ ca kiểm thử), chạy cổng kiểm định 5 bất biến `M4`, chạy full `clean_runner` + `Testing_System`, kiểm tra `git diff` sạch & tick checklist `M5` | Toàn bộ `M-1` $\to$ `M-8` + `INV-1..6` | `[x] DONE` |

---

## 4. TÓM TẮT 8 ĐIỂM HIỆU CHỈNH KỸ THUẬT BẮT BUỘC PHẢI TUÂN THỦ KHI CODE

1. **`M-1` (Chống ghi đè xóa hệ số $\hat{\alpha}_{c,\ell}$ trong `controller.py`):** Khi `Task` có `buffer_mode == "COGNITIVE_LOAD"` và `alpha_light` / `alpha_heavy` riêng từng môn đã được gán, `ScheduleController.apply_estimate_buffer()` phải giữ nguyên `t.alpha_light`, `t.alpha_heavy` của task đó và `annotate_estimate_buffer()` vẫn gắn nhãn giải thích `ESTIMATE_BUFFER`.
2. **`M-2` (Chống co rút kép EWMA + Bayes):** Khởi tạo $\text{EWMA}_c^{(1)} = r_1$ tại mẫu đầu tiên của môn $c$, cập nhật $\text{EWMA}_c^{(k)} = 0.30 r_k + 0.70 \text{EWMA}_c^{(k-1)}$ cho $k \ge 2$, rồi mới co rút Bayes 1 lần duy nhất với $\kappa = 3.0$ và kẹp trong $[1.00, 1.60]$.
3. **`M-3` (Bảo vệ `hourly_levels` 7 ngày):** Sự cố lặp lại $\ge 2$ lần ở 1 ngày cụ thể `(day, hour_band)` phải dùng `FixedEvent(..., category="ADVISORY_BUFFER")` đúng ngày đó (khi tải $\rho \le 0.90$), **TUYỆT ĐỐI KHÔNG** hạ `hourly_levels` (vốn lặp lại cho cả 7 ngày).
4. **`M-4` (Vượt giới hạn validator Pydantic v2 khi đổi nhịp):** Khi hạ nhịp sau tuần căng thẳng, truyền tường minh `work_rhythm="BALANCED", min_chunk_min=45, max_chunk_min=75, is_splittable=True` vào `model_copy(update=...)`.
5. **`M-5` (Hỗ trợ cả Người dùng thật SQLite lẫn `InSilicoStudentSimulator`):** Tự suy luận `window` từ giờ hoàn thành / khối lịch `completedBlocks`, đo tỷ lệ bám lịch từ `workspace_state`, và lưu `disruption_logs` nhẹ trong `workspace_state`; mặc định `apply=False` (`LoA-4`).
6. **`M-6` (Đảm bảo SLA `< 500 ms` & Lọc câu lệnh chuẩn):** `/api/simulation/multi-week` mặc định `n_students=1, weeks=4` (`< 500 ms` với `SCORED_GREEDY`), vẫn hỗ trợ `n_students > 1` cho thống kê lô và có `try/except ImportError` fallback; `disruption_chat.py` không bắt nhầm câu thêm lịch lặp lại hàng tuần.
7. **`M-7` (Đồng bộ điều phối thuật toán `solve_adaptive`):** Mọi endpoint mới của `M5` chạy `SCORED_GREEDY` và tự leo thang sang `HYBRID_ALNS` nếu còn rớt việc khả thi; loại bỏ gọi lặp thừa `apply_estimate_buffer`.
8. **`M-8` (Hậu kiểm công thái học sau `LOCAL_INSERTION`):** Cảnh báo minh bạch + gợi ý chip tối ưu lại nếu `LocalRepairEngine` đẩy ca nặng `load=3` vào đáy năng lượng `energy=1`.
