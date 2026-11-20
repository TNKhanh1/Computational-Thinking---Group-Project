# Tài Liệu Bàn Giao Toàn Diện: `member_eval/` (Chấm Mù 7 Thành Viên) & `P1` Web UI/API (`HYBRID_ALNS` + `v2.1` Thời Gian Thực)

> **Nhánh Git:** `feat/v3-solvers-and-member-eval`  
> **Ngày cập nhật:** `2026-11-20`  
> **Mục tiêu tài liệu:** Bàn giao **độc lập, trọn vẹn 100% bối cảnh** để bất kỳ thành viên nào chỉ cần đọc **duy nhất file này** là nắm toàn bộ hiện trạng codebase, những gì đã làm & kiểm chứng xong, cách chạy thử ngay cả 2 Web App (`8000` & `8010`), và lộ trình tiếp theo đưa SmartSchedule tới thương mại hóa cho học sinh/sinh viên (không cần đọc lại lịch sử chat).  
> **Lưu ý tên tài liệu:** Trong repo trên GitHub **không tồn tại** file `Testing_Plan/summary_plan.md`; tài liệu tổng kết bàn giao trước đó là [`HANDOFF_SUMMARY_AND_NEXT_TASKS.md`](HANDOFF_SUMMARY_AND_NEXT_TASKS.md) kết hợp với [`evaluation_plan.md`](evaluation_plan.md) và [`ultimate_plan.md`](ultimate_plan.md).

---

## I. Toàn Cảnh Dự Án Tính Đến Hiện Tại (`20/11/2026`)

| Pha / Hạng mục | Trạng thái | Tóm tắt kỹ thuật cốt lõi |
| :--- | :---: | :--- |
| **Lõi Baseline & Improve Plan (V1/V2)** | **Hoàn tất** | Lưới `672`/`1344` slots (`horizon_days = 7..14`), bảo toàn cứng $H_1\text{–}H_5$, ngủ `>= 6h`, Dual Estimate Buffer (`COGNITIVE_LOAD 1.20/1.35` + `HABIT` + opt-out `NONE`), `PersonalHabit`, `LocalRepairEngine`, `OverloadTriageEngine`, Hybrid EN/VI NL Parser + Live Gemini, SQLite persistence. |
| **Máy chấm & Sinh đề (`Testing_System v2.1 + Fuzz v2`)** | **Đóng băng (`39/39`)** | Cổng `#0 HARD-RULE` (`G1`, SLA `<= 1000 ms`) + 10 cấp Từ Điển có dung sai bắt đầu từ `QUALITY-TIER (Verdict)`, Top 5 `ICEE` tiếng Việt, và `FuzzGenerator v2` (*Plant-a-Witness* hỗ trợ `7/14 ngày`, `LOOSE`/`TIGHT`/`OVERLOAD`). |
| **`P0` — Bộ 6 Thuật Toán V3 (`src/solvers/`)** | **Hoàn tất** | [`ergonomic_engine.py`](../group03-smartschedule-baseline/src/solvers/ergonomic_engine.py) (`O(1)` prefix-sum, SJL vòng Smarr & Schirmer, tách mảnh chuẩn `G1`, cứu hạn Kempe + First-Fit) nâng cấp `WSPT`/`LST` (Blind `Q10`), `SCORED_GREEDY` (mặc định UI), `BACKTRACK`, giữ `EDF` V0 đối chứng, và thêm thuật toán thứ 6 [`HYBRID_ALNS`](../group03-smartschedule-baseline/src/solvers/hybrid_alns.py). Xóa sạch `SUBOPT -> 0/220` và đạt `25/25 (100%)` `LOOSE HIGH_PRODUCTIVITY` trên tập ẩn `5001..5050` (`max <= 774.8 ms`). |
| **Chương trình Chấm Mù (`member_eval/`)** | **MỚI — Hoàn tất** | Triển khai đầy đủ [`evaluation_plan.md`](evaluation_plan.md) tại `group03-smartschedule-baseline/member_eval/` (Web Portal riêng Port `8010` + CLI `blind_runner` + `aggregator`). |
| **`P1` — Web App Thương Mại (`HYBRID_ALNS` + `v2.1` UI/API)** | **MỚI — Hoàn tất** | Đưa `HYBRID_ALNS` + chẩn đoán **4 Trụ Cột `Testing_System v2.1`** & **`ICEE` tiếng Việt** thời gian thực lên Student Mode & Lab Mode (Port `8000`) kèm endpoint `POST /api/evaluate`. |
| **`P2–P3` (Pilot 7 ngày, 21+ phiên chấm mù, SaaS)** | **Kế tiếp** | Thu dữ liệu người thật từ 7 thành viên & sinh viên, hiệu chuẩn `ergonomic_engine.py` / `α`, và hoàn thiện hạ tầng đa người dùng (Auth, Calendar/LMS Sync, Focus Timer). |

---

## II. Chi Tiết Những Gì Đã Thực Hiện Trong Đợt Cập Nhật Này

### 1. Chương Trình Chấm Mù Đa Thành Viên (`group03-smartschedule-baseline/member_eval/` — Port `8010`)

Thiết kế tách lớp độc lập hoàn toàn với lõi giải thuật (`INV-1..6`):
- **[`member_eval/__init__.py`](../group03-smartschedule-baseline/member_eval/__init__.py):** Định nghĩa danh sách 7 thành viên Nhóm 03 + `guest_student`, 5 tiêu chí rời `UX-1..UX-5`, 3 cấu hình ứng viên (`standard_3`: `EDF`, `SCORED_GREEDY`, `HYBRID_ALNS`; `standard_4`: + `BACKTRACK`; `all_6`), và 7 nhãn block `OFFICIAL_BLOCK_TAGS` (`AWKWARD_SPLIT`, `BAD_TIME_OF_DAY`, `TOO_TIGHT_GAP`, `CONTEXT_JUMP`, `DAY_OVERLOAD`, `HABIT_MISPLACED`, `WRONG_PRIORITY`).
- **[`member_eval/scenarios.py`](../group03-smartschedule-baseline/member_eval/scenarios.py):** Cung cấp `PERSONAL_WEEK` (tuần thật chỉnh sửa được + thêm việc bằng NL tiếng Việt/Anh) và 7 kịch bản khóa seed (`R1_LOOSE_S1`, `R2_TIGHT_S42`, `R3_CIRCADIAN_S5`, `R5_OVERLOAD_S1`, `FUZZ_LOOSE_14D_S1041`, `FUZZ_TIGHT_S1001`, `FUZZ_OVERLOAD_S1049`).
  - *Điểm kỹ thuật quan trọng đã xử lý:* Truyền `fuzz_tier=None` cho các seed khóa (`1041`, `1001`, `1049`) khi gọi `FuzzGenerator.generate(seed, tier=...)` để không làm lệch trạng thái RNG khiến `seed=1041` bị rút từ `14` ngày xuống `7` ngày.
- **[`member_eval/blind_runner.py`](../group03-smartschedule-baseline/member_eval/blind_runner.py):**
  - `deterministic_blind_order()` dùng `SHA-256(seed:member_id:scenario_id)` tráo thứ tự thành `#A, #B, #C...`.
  - `build_blind_packet()` chạy song song các solver + chấm ngầm bằng `ScheduleEvaluator.evaluate()` & `rank_cross_solver_reports()`, rồi tách làm 2 phần:
    - `blind_view` (trả về UI qua `strip_oracle_for_blind_client()`): lọc sạch `solver_used` và mọi `algo_tag` trong `reason`/`reasons`, **không lộ bất kỳ tên thuật toán hay điểm `v2.1` nào**.
    - `revealed_oracle`: chỉ mở khóa sau khi người dùng nộp đủ `UX-1..UX-6`.
- **[`member_eval/app.py`](../group03-smartschedule-baseline/member_eval/app.py) & [`viewer.html`](../group03-smartschedule-baseline/member_eval/viewer.html) & [`run_member_eval.bat`](../group03-smartschedule-baseline/run_member_eval.bat):**
  - Server FastAPI độc lập tại `http://127.0.0.1:8010` (hỗ trợ biến môi trường `SMARTSCHEDULE_EVAL_DIR` để test cô lập):
    - `GET /`, `GET /api/eval/meta`, `POST /api/eval/nl-parse`
    - `POST /api/eval/session` (sinh packet mù, chỉ trả `blind_view`)
    - `POST /api/eval/submit` (validate điểm `1..5` cho mọi ứng viên + winner + tags hợp lệ, lưu `reviews/<member_id>_<scenario_id>.json`, mở khóa `revealed_oracle` + `machine_vs_human`)
    - `POST /api/eval/confirm-agreement` (ghi nhận `revealed_diff_agree`)
    - `GET /api/eval/report` (trả summary JSON + Markdown; truyền `?write_md=true` để xuất `Calibration_Report.md`).
- **[`member_eval/aggregator.py`](../group03-smartschedule-baseline/member_eval/aggregator.py):** Tính *Blind Human Win-Rate* theo từng loại tải, trung bình rời `UX-1..UX-5`, tỷ lệ đồng thuận `Exact Rank #1` & `Top-2`, liệt kê `disagreement_cases`, gắn cờ cụm phàn nàn `>= 25%` kèm hướng dẫn sửa cụ thể trong `ergonomic_engine.py`, và chạy 3 Quy tắc Quyết định (`§VI evaluation_plan.md`).

### 2. Nâng Cấp `P1` Lên Web Workbench Chính (`group03-smartschedule-baseline/web/` — Port `8000`)

- **[`web/health_v21.py`](../group03-smartschedule-baseline/web/health_v21.py) & [`web/api.py`](../group03-smartschedule-baseline/web/api.py):**
  - Cầu nối Tầng 4 `evaluate_schedule_v21()` gọi `ScheduleEvaluator` với cơ chế fallback an toàn nếu thiếu `Testing_System`.
  - `_enrich_response()` tự động đính kèm `"health_v21"` cho `POST /api/plan`, `POST /api/solve`, `POST /api/compare` bằng **`raw_tasks` chưa qua buffer** (`_extract_raw_tasks(payload)`) để tránh nhân buffer 2 lần bên trong `ScheduleEvaluator` (`preprocess_tasks`).
  - Bổ sung endpoint **`POST /api/evaluate`** chấm lại trực tiếp cả `ScheduleOutput` đầy đủ lẫn danh sách `blocks` rời (phục vụ sau khi sửa tay/kéo-thả/tái lập lịch). *Lưu ý:* khi truyền `pinned_blocks` kèm `schedule`, block tương ứng trong `schedule.blocks` phải mang `state="PINNED"` (đúng chuẩn `G1_PIN_VIOLATED` của `gates.py`).
- **[`web/index.html`](../group03-smartschedule-baseline/web/index.html) & [`web/app.js`](../group03-smartschedule-baseline/web/app.js):**
  - Mở lựa chọn **`HYBRID_ALNS`** (*Tối ưu sâu V3*) ở `#stSetSolver`, `#solverSelect`, `#compareAlgoLeft`/`#compareAlgoRight`, thêm nút đối chứng nhanh `SCORED_GREEDY vs HYBRID_ALNS`, và nâng Determinism Proof Ledger lên **tất cả 6 thuật toán**.
  - Thêm dải **4 Thẻ Sức Khỏe Sinh Viên (`#stHealthV21Panel`)** trong `#stViewWeek` hiển thị `Verdict` tiếng Việt, 4 trụ cột (`P1` Kịp hạn & `<10h%`; `P2` Nhịp sinh học `APk%` / nghỉ `>10p` / `SJL`; `P3` Đỉnh tải ngày `MaxD` / `TStd` / chuyển môn; `P4` Chịu sốc `+25%`) và `<details id="stHealthIceeDetails">` Top 3 gợi ý `ICEE`.
  - Thêm **`#labHealthV21Panel`** (12 ô vector `v2.1` + Top 5 `ICEE`) ở Lab Tab 1 và **4 hàng đối chiếu `v2.1`** (`Verdict`, `Shock@+25%`, `APk%`, `MaxD`) trong bảng so sánh A/B ở Lab Tab 2.

---

## III. Ranh Giới Kiến Trúc & Kết Quả Kiểm Chứng Xác Nhận

### 1. Ranh giới bất biến được bảo vệ tuyệt đối (`0` vi phạm)
- **`Testing_System/`**, **`src/solvers/`**, **`src/models.py`**, **`requirements.txt`**: **`0` file bị sửa đổi** (`git diff` chỉ chạm `web/api.py`, `web/app.js`, `web/index.html`, `README.md`, `agents/commit_changes.md`, `docs/commit_changes.md` và các file mới thêm).
- Kiểm tra AST tự động xác nhận `src/` và `Testing_System/` không hề import `member_eval/` hay `web/`.

### 2. Bảng kết quả kiểm thử chạy sau lần sửa code cuối
| Bộ kiểm thử | Lệnh thực thi | Kết quả thực đo |
| :--- | :--- | :--- |
| **Máy chấm `v2.1` & `Fuzz v2`** | `python -B -m pytest Testing_System/tests -v` | **`39 passed in 13.54s`** (`0 failed`) |
| **Toàn bộ Ma trận App (`--all`)** | `cd group03-smartschedule-baseline; python -B verification_tests/clean_runner.py --all` | **`167 Passed \| 0 Failed`** (`7.54s`, gồm `3/3` `test_member_eval_system.py` & `3/3` `test_p1_v21_ui_and_api.py`) |
| **Course Benchmark `T01–T10`** | `cd group03-smartschedule-baseline; python -B benchmark_runner.py` | **`EXIT=0`** (`T01–T10 C_hard=0`, `3x Determ PASS`, `T04 LOCAL_INSERTION=100.00%`, `T09 Ablation=PASS`, `Scale N=50=4.65 ms`) |
| **Cú pháp Frontend & So sánh ALNS** | `node --check web/app.js`, kiểm tra inline JS `viewer.html`, `POST /api/compare` (`SCORED_GREEDY` vs `HYBRID_ALNS`) | JS exit **`0`**; `/api/compare` trả **`200 OK`**, cả 2 đều đạt `HIGH_PRODUCTIVITY` |

---

## IV. Hướng Dẫn Khởi Chạy Nhanh Trong 3 Phút Cho Thành Viên Tiếp Theo

```powershell
# 1. Lấy nhánh mới nhất
git fetch --all --prune
git checkout feat/v3-solvers-and-member-eval
git pull --ff-only origin feat/v3-solvers-and-member-eval

# 2. Chạy toàn bộ test (Windows UTF-8)
$env:PYTHONIOENCODING = "utf-8"
python -B -m pytest Testing_System/tests -v
cd group03-smartschedule-baseline
python -B verification_tests/clean_runner.py --all
python -B benchmark_runner.py

# 3. Chạy Web App Sản Phẩm (Student + Lab Mode v2.1) tại http://127.0.0.1:8000
python -B -m uvicorn web.api:app --host 127.0.0.1 --port 8000

# 4. Chạy Cổng Chấm Mù 7 Thành Viên tại http://127.0.0.1:8010 (mở terminal thứ 2)
python -B -m uvicorn member_eval.app:app --host 127.0.0.1 --port 8010

# 5. (Tùy chọn CLI) Sinh packet hàng loạt hoặc xuất Calibration_Report.md
python -B -m member_eval.blind_runner --member duc_minh --scenario all --mode standard_3
python -B -m member_eval.aggregator
```

---

## V. Danh Sách Việc Cần Làm Tiếp Theo (Theo Thứ Tự Ưu Tiên)

1. **Hoàn thiện đợt Chấm Mù Nhóm (`evaluation_plan.md §V–VI`):**
   - Mỗi thành viên trong 7 người vào `http://127.0.0.1:8010` chấm tối thiểu **3 ca** (`Ca 1: PERSONAL_WEEK` tuần thật của mình + `Ca 2: LOOSE` + `Ca 3: TIGHT/OVERLOAD`) để thu đủ `>= 21` file JSON trong `member_eval/reviews/`.
   - Chạy `python -B -m member_eval.aggregator` sinh `member_eval/Calibration_Report.md`. Nếu có cụm nhãn lỗi `>= 25%` hoặc bất đồng Máy–Người `> 20%`, tinh chỉnh tie-breaker trong `src/solvers/ergonomic_engine.py` rồi chạy lại đủ `167` app tests + `39` Testing_System tests + benchmark `220` đề.
2. **Đồng bộ `P1.3` & Triển khai `P2` (Pilot 7 ngày & Hiệu chuẩn $\alpha$):**
   - Cập nhật [`Testing_System/README.md`](../Testing_System/README.md) phản ánh thêm `--mode fuzz`, `v2.1` và `39/39` tests.
   - Chạy Pilot 7 ngày dùng thật tại `http://127.0.0.1:8000`, bấm Check-in `actual_duration_min` (M7) sau mỗi block để thu dữ liệu `Actual / Estimated` thật; mở rộng [`benchmark_alpha_grid.py`](../group03-smartschedule-baseline/benchmark_alpha_grid.py) thêm ca tải cực hẹp `α >= 1.7` và cập nhật `Proposal/Presentation2.pdf`.
3. **Thương mại hóa `P3` (Multi-Tenant SaaS Cho Học Sinh / Sinh Viên):**
   - Bổ sung Auth (OAuth2 / Google Login) + tách dữ liệu DB theo `user_id` (thay `workspace_id="default"` và siết `CORS`);
   - Tích hợp import/đồng bộ 2 chiều Google Calendar / `.ics` thời khóa biểu trường / Moodle–Canvas LMS;
   - Thêm Focus Timer (Pomodoro) nối tự động vào check-in M7, EWMA tự học `α` cá nhân, thông báo nhắc giờ và Docker + GitHub Actions CI.
