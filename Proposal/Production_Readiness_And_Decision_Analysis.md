# Báo Cáo Hợp Nhất: Đánh Giá Sẵn Sàng Thực Chiến & Khuyến Nghị Chốt Quyết Định (`Q1–Q10`)

> **Cập nhật lần cuối:** 17/11/2026 *(Đã hoàn tất cả **Cột mốc 1**, **`Q10` Nhịp 1–2**, **Cột mốc 2 (`Gói A.0`, `Gói A.1–A.3`, `Gói B`)** và **Tái thiết lập UI/Lab (`Lần cập nhật 013`)** trên nhánh `M1-NL-Parser`, bảng quyết định **`☑ Q1–Q10`** đã chốt xong 100%.)*  
> **Cơ sở đối chiếu:** `PR4_Review_Report.pdf`, [`Proposal/Open_Decisions_For_Team.md`](Open_Decisions_For_Team.md), [`Proposal/Sync_Completion_Report.md`](Sync_Completion_Report.md), và mã nguồn thực tế trên nhánh `M1-NL-Parser` (sau Cột mốc 1 + `Q10` Nhịp 2).  
> **Ghi chú:** Tài liệu này tách bạch rõ 2 cột mốc: (1) **Đủ chuẩn Merge PR #4 & Bảo vệ đồ án** và (2) **Đem app ra xài thực tế hằng ngày**.
>
> **Cơ sở kiểm chứng thực nghiệm mới nhất trên `M1-NL-Parser` (sau Cột mốc 2 & Tái thiết lập UI/Lab):**
> * `python -B verification_tests/clean_runner.py --pass`: **149 Passed | 0 Failed** (`ALL PASSED`)
> * `python -B verification_tests/clean_runner.py --gaps`: **5 Passed | 0 Failed** (`ALL PASSED`)
> * `python -B verification_tests/clean_runner.py --all` & `python -B -m pytest -q`: **155 Passed | 0 Failed** (`ALL PASSED` — gồm `149` `--pass` + `5` `--gaps` + `1` `Q9` Phương án A)
> * `python -B verification_tests/NL_Parser_test_cases/validate_cases.py`: **`200` cases — `All checks passed`**
> * `python -B verification_tests/NL_Parser_test_cases/verify_hybrid_200.py`: **200/200 (`100.0%`)** (`backend=rule`, `620.6 ms`, `3.10 ms/case`)
> * `node --check group03-smartschedule-baseline/web/app.js`: **exit `0`**
> * `python -B benchmark_runner.py`: **T01–T10 `C_hard = 0`**, `3x Determ PASS`, `T04 LOCAL_INSERTION Stability = 100.00%` vs `FULL_REBUILD` (`0.00%`), `Scalability N=50 = 7.29 ms`, **Bảng 5 Controlled Ablation (`T09`)**: `EDF V0` Energy-Blind giữ nguyên `Monday 06:30-08:00` (`hash 4268107a006d` cho cả `MORNING` & `EVENING`) còn `SCORED_GREEDY` dịch chuyển linh hoạt `06:30-08:00` (`f65266353eff`) $\leftrightarrow$ `18:00-19:30` (`ac905601e5bf`).
> * **Live Gemini API (`.env` + `google-genai` + `python-dotenv`, `gemini-3-flash-preview`):** **ĐÃ XÁC MINH CHẠY THẬT THÀNH CÔNG (`200 OK`, `engine_used="AI_GEMINI"`, `ai_status="ACTIVE"`)** qua cả `parse_natural_language_task(..., engine="auto")` lẫn `POST /api/tasks/natural-add` + `POST /api/plan` (`SCORED_GREEDY` mặc định). Chi tiết xem **Mục 2.2**.

---

## 1. Tóm Tắt Điều Hành: Demo Tốt vs Xài Thực Tế Được Ngay Chưa?

| Góc độ đánh giá | Trạng thái hiện tại | Kết luận thẳng thắn |
| :--- | :---: | :--- |
| **Lõi Thuật toán & Kiểm thử (`M2–M6`, Tests)** | **Vững & Đạt chuẩn Demo** | Toàn bộ 12 bản vá (`A1–A12`), 8 Behavioral Patterns, `SCORED_GREEDY`, `EDF V0` thuần Energy-Blind (`Q10` Nhịp 1 & 2 xong), `OverloadTriageEngine`, `LocalRepairEngine`, `start_after`/`work_rhythm`/`PersonalHabit`, và Hybrid NL Offline (`200/200`) đều chạy nhanh (`0.61–9.77 ms`), `C_hard = 0`, và tất định SHA-256 ở tầng Solver. |
| **Điều kiện Merge PR #4 (`M1-NL-Parser -> main`)** | **SẴN SÀNG MERGE PR #4** | Toàn bộ Cột mốc 1, Cột mốc 2 & Tái thiết lập UI/Lab đã hoàn chỉnh với **`155/155` tests xanh**, Live Gemini OK, **`Q1–Q10` đã chốt hết `☑`**, và UI hiển thị ngày cụ thể `DD/MM/YYYY` + Lab 3 workspace trực quan. |
| **Đem ra Xài Thực Tế Cá Nhân Hằng Ngày (Local App)** | **SẴN SÀNG XÀI HẰNG NGÀY** | Đã hoàn tất **Gói A.0–A.3 + Gói B + UI Redesign**: SQLite + `localStorage` persistence qua F5, đồng hồ thực (`DD/MM/YYYY` + vạch `BÂY GIỜ` + tuần hiện tại khi mở lần đầu), `PersonalHabit` tab trực tiếp, Student UI gọn một luồng thao tác, và Lab Mode A/B Verdict + Diff Table + Ledger SHA-256. |
| **Thương Mại Hóa Đa Người Dùng (Multi-Tenant SaaS)** | **Cần Gói C (Post-V1)** | Muốn mở dịch vụ SaaS công khai đa người dùng vẫn cần Auth/OAuth2 tách `user_id`, siết CORS/Rate-Limit/Quota AI, đồng bộ Google Calendar 2 chiều & đóng gói Docker/Monitoring (**Gói C**). |

---

## 2. Kiểm Toán Toàn Bộ Features Chính & 4 Rào Cản Thực Chiến

### 2.1. Hiện trạng từng Feature chính trên `M1-NL-Parser`

| # | Feature / Phân hệ | Cho Demo / Môn học | Cho Xài Thật Hằng Ngày | Đánh giá cụ thể trong mã nguồn |
| :---: | :--- | :---: | :---: | :--- |
| **1** | **Lưới 672 Slots, $H_1\text{–}H_5$ & Cross-Week (`1344`)** | **Đạt** | **Đạt** | Xử lý chuẩn $C_{\text{hard}}=0$, DAG $H_5$, ngủ `>= 6h`, sự kiện qua đêm `22:00–02:00`, `d_slot == 0`, deadline quá khứ. Đã thêm `horizon_days` (`7..14`) vào [`CommitmentsProfile`](../group03-smartschedule-baseline/src/models.py), nối `resolve_horizon_slots()` & `grid_states` (`1344`), và thêm nút `🕒 Tuần này` + `◀ Tuần 1 / Tuần 2 ▶` trên Web UI. |
| **2** | **5 Solvers (`EDF`, `LST`, `WSPT`, `BACKTRACK`, `SCORED_GREEDY`)** | **Đạt 100%** *(Q10 xong 2 nhịp)* | **Đạt** | Đủ 5 bộ giải (`Backtracking` trần `12` ứng viên/`3000` nodes trong [`src/config.py`](../group03-smartschedule-baseline/src/config.py#L39-L40), timeout `1.75s`). **Đã hoàn tất cả `Q10` Nhịp 1 & Nhịp 2:** UI (`#solverSelect`, `#stSetSolver`, `#kpiSolverLabel`, `app.js`) và `/api/plan` mặc định **`SCORED_GREEDY`**; `BaseScheduler.should_prefer_energy_placement()` trả `False` để `EDF`/`LST`/`WSPT` trở về thuần **Energy-Blind V0** (chứng minh rõ trên `T09`), còn `SCORED_GREEDY` & `BacktrackingSolver` giữ tối ưu Circadian + Batching; [`src/solvers/registry.py`](../group03-smartschedule-baseline/src/solvers/registry.py) dùng chung cho `_repair_full_rebuild()` & `POST /api/repair`. |
| **3** | **8 Behavioral Patterns (`Presentation2.pdf`)** | **Đạt** | **Đạt** | Pattern 1 (`1.20/1.35` + bỏ nhân đôi JS), Pattern 2 (`90p` cap + `15p REST`), Pattern 5 (`< 30p` Dead-zone `REST`), Pattern 6 (`>= 6h` ngủ + Early Alert `24–48h`), Pattern 7 (`exp(-slack/24) × Importance`), Pattern 8 (`LocalRepair 100%`) đều chạy đúng. Đã đặt mặc định **Student UI / Settings / `"empty"` preset** dùng `"COGNITIVE_LOAD"` (`CommitmentsProfile` Pydantic fallback giữ `"HABIT"` để bảo toàn V0 `T01–T10`). |
| **4** | **Personal Habits (`Slide 6`, `Q7.3 = A3`)** | **Đạt** | **Đạt** | Đã mở UI quản lý `PersonalHabit` (`1 preferred_window + frequency_per_week + duration_min`) trong Cài đặt Sinh viên (`#stSettingsModal`); [`expand_personal_habits()`](../group03-smartschedule-baseline/src/controller.py) phân bổ các buổi rải đều qua từng thứ (`start_after`) và `score_candidate_slot()` ưu tiên đúng khung `MORNING`/`AFTERNOON`/`EVENING`. |
| **5** | **Two-Tier Crunch & Overload Triage (Feature 002 / Step 5)** | **Đạt** | **Đạt** | Tier 1 (`Cut breaks`) tự mở nghỉ 15p & dead-zone nếu cứu được lịch; Tier 2 (`OverloadTriageEngine`) có `SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST` kèm Preview/Apply/Undo và bảo vệ tiên quyết. |
| **6** | **M1 Hybrid EN/VI NL Parser (`src/nl_parser.py` + `NL_Parser_Package/`)** | **Đạt (AI + Offline)** | **Đạt** | Đã xong Cột mốc 1 lẫn **Cột mốc 2**: nối `Task.start_after` + `Task.work_rhythm` vào `BaseScheduler`/`BacktrackingSolver`, gỡ `engine: "offline"` cứng ở Lab Mode `analyzeQuickAddHybrid()`, và sửa [`OfflineNLParser.extract_duration_min()`](../group03-smartschedule-baseline/src/nl_parser.py) tách bỏ khoảng giờ (`14h00 - 16h00`) / giờ 24h (`19h30`) trước khi trích xuất phút (`"19h30 khoảng 90p"` $\rightarrow$ `90` thay vì `1170`). |
| **7** | **M7 Check-in & Calibration (`benchmark_alpha_grid.py`)** | **Đạt** | **Đạt** *(lịch sử SQLite)* | `/api/tasks/complete` ghi nhận `overrun_ratio`, `recommended_estimate_habit`, `recommended_alpha` vào SQLite (`completion_logs` qua [`src/storage.py`](../group03-smartschedule-baseline/src/storage.py)) và đọc lại tại `GET /api/tasks/completions`. Còn bổ sung thêm kịch bản stress `α >= 1.7` & log pilot 1 tuần thật khi chạy thực nghiệm nhóm. |
| **8** | **Giao diện Web Student / Lab & Xuất Lịch** | **Đạt 100%** | **Đạt (Single-User)** | Hiển thị 672/1344 slots, Why Here?, Kéo-thả `validate-move`, Undo, So sánh 2 thuật toán, xuất `.ics/.csv/.json`. Đã triển khai **Gói A.0–A.3**: Progressive Disclosure `#stTaskModal` gọn ở `STUDENT` Mode (`LAB` Mode bung full), **lưu bền vững SQLite + `localStorage` qua F5** (`GET/PUT/DELETE /api/state`), Sửa/Xóa Task trong Student Mode (`editStudentTask`). Còn Sync Google Calendar & Auth đa user thuộc Gói C. |
| **9** | **Scripts `.bat`, Deps & Tài liệu** | **Đã đồng bộ** | **Đạt** | 3 file `.bat` (`run_app.bat`, `run_verification_tests.bat`, `run_test_studio.bat`) tự ưu tiên `.venv\Scripts\python.exe`; đã tách NLLB sang [`requirements-nllb.txt`](../group03-smartschedule-baseline/requirements-nllb.txt) và đồng bộ `agents/` & `docs/`. |

### 2.2. Kết Quả Kiểm Chứng Trực Tiếp `.env` & Gemini Live API (`17/11/2026`)

Quá trình chạy thử trực tiếp với `.env` (`GEMINI_API_KEY` thật, `NL_PARSER_ENGINE=auto`, `GEMINI_MODEL=gemini-3-flash-preview`, giá trị key được bảo mật không đọc/in ra log) đã phát hiện và khắc phục các điểm sau:

1. **Bẫy môi trường (`silent fallback`) -> Đã vá bằng `validation["ai_status"]`:**
   - Khi thử ở môi trường thiếu `google-genai` hoặc `python-dotenv`, `engine="auto"` trước đây âm thầm rơi về `OFFLINE_DETERMINISTIC` với `assumptions: []`. Nay [`NLParserController.parse()`](../group03-smartschedule-baseline/src/nl_parser.py) gán rõ `validation["ai_status"]` (`"ACTIVE"`, `"OFFLINE_REQUESTED"`, `"MISSING_GOOGLE_GENAI_PACKAGE"`, `"MISSING_API_KEY"`, `"FALLBACK_AFTER_ERROR"`) và ghi cảnh báo vào `assumptions`.
2. **Đối chứng thực tế `OFFLINE_DETERMINISTIC` vs `AI_GEMINI` (chứng minh trực tiếp cho `Q5`):**

   | Kịch bản đầu vào (`now="Monday"`) | `OFFLINE_DETERMINISTIC` | `AI_GEMINI` (`gemini-3-flash-preview`, chạy thật `17/11/2026`) | Kết luận sau vá Cột mốc 1 |
   | :--- | :--- | :--- | :--- |
   | **VI chuẩn:** *"Nộp báo cáo Tư duy tính toán thứ 6 lúc 23h, mất khoảng 2 tiếng"* | — | `2740.3 ms` \| `dur=120`, `Friday 23:00`, `ASSIGNMENT`, `prio=5` (`user=1`), `work_rhythm="FLOW"` | Trích xuất chuẩn 100%, giữ trọn đồng bộ `WorkRhythm` + `user_priority`. |
   | **Trích dẫn tệp:** *"Làm lab [[Ch1. Logic_apcs.pdf]] tối thứ 5 19h30 khoảng 90p"* | — *(chú ý: câu tương tự ở offline nếu thiếu Gemini có thể hiểu nhầm `19h30` vào `duration_min`)* | `2353.5 ms` \| `title="Làm lab Ch1. Logic_apcs.pdf"`, `dur=90`, `Thursday 19:30`, `LAB`, `prio=4`, `hybrid_errors=[]` | Hoạt động tốt với cả `attachments` dạng `dict` lẫn `list[str]` sau bản vá. |
   | **EN khẩu ngữ:** *"Urgently need to cram Linear Algebra midterm prep before Thursday 5pm for two and a half hours"* | `dur=60` *(bỏ sót `"two and a half hours"`)*, `title` còn nguyên cụm thời gian | `dur=150`, `Thursday 17:00`, `EXAM`, `prio=5`; lặp lại cho `dur=150` nhất quán nhưng `title` đổi ngữ điệu giữa lần gọi | Gemini vượt trội regex ở cụm số viết bằng chữ; nhưng tiêu đề thay đổi giữa các phiên -> **xác nhận LoA Level 4 (`Q5`)** cho phép user duyệt trước khi vào Solver SHA-256. |
   | **VI khẩu ngữ + Coarse Window:** *"Chiều mốt làm gấp slide thuyết trình nhóm CT khoảng tiếng rưỡi [[Slide_Draft.pptx]]"* | `dur=60`, `Wednesday 17:00`, `matched=['Slide_Draft.pptx']` | **Trước vá:** rơi giờ `"chiều"` về `23:59`. **Sau vá (`POST /api/tasks/natural-add` -> `/api/plan`):** `AI_GEMINI` (`4345.8 ms`), **`Wednesday 17:00`, `dur=90`, `prio=5`, `matched=['Slide_Draft.pptx']`**, xếp được **1 block (`SCORED_GREEDY`, `R_dl=100.0%`)**. | Bản vá `OfflineNLParser.extract_coarse_window_time()` (`sáng->11:00`, `trưa->12:00`, `chiều->17:00`, `tối->21:30`) đã cứu trọn mốc `"chiều"` khi Gemini trả `deadline_time=None`. |
   | **Câu phiếm quá khứ:** *"Hôm qua đi uống trà sữa..."* & *"Chủ nhật vừa đi đá banh với lớp hết 2 tiếng mệt quá"* | `status="NO_TASK"` | `status="NO_TASK"` (`1522.6 ms` câu trà sữa; giải thích tự nhiên câu đá banh) | Cả hai tầng đều chặn rác an toàn. |

3. **Vá xong bug `ui.attachments: list[str]` tại `hybrid_parser.py`:**
   - Lỗi `AttributeError: 'str' object has no attribute 'get'` khi truyền `ui={"attachments": ["Ch1. Logic_apcs.pdf"]}` đã được xử lý triệt để bằng helper `_normalize_attachment_items()` (chấp nhận đồng thời `str`, `dict`, hoặc danh sách pha trộn) và có unit + API test bảo vệ trong [`test_hybrid_nl_integration.py`](../group03-smartschedule-baseline/verification_tests/logical_tests/test_hybrid_nl_integration.py).

### 2.3. Thẩm định 4 điểm kỹ thuật từ `PR4_Review_Report.pdf` & phản hồi của Bảo
1. **Import tuyệt đối phụ thuộc `sys.path` trong [`NL_Parser_Package/__init__.py`](../group03-smartschedule-baseline/NL_Parser_Package/__init__.py):**
   * *Trạng thái:* **ĐÃ SỬA.** Toàn bộ 5 file trong `NL_Parser_Package/` (`__init__.py`, `hybrid_parser.py`, `parser.py`, `regex_parser.py`, `tokenizer.py`), `src/nl_parser.py` và 2 file test caller đã chuyển sang package/relative import sạch, không còn chèn thư mục con `NL_Parser_Package/` vào `sys.path`.
2. **Bảng quy đổi mức gấp `{1: 5, 2: 4, 3: 3, 4: 1}` trong [`NL_Parser_Package/hybrid_parser.py`](../group03-smartschedule-baseline/NL_Parser_Package/hybrid_parser.py):**
   * *Trạng thái:* **ĐÃ BỔ SUNG DOCSTRING & KIỂM CHỨNG ẨN THANG NGƯỢC.** Giữ nguyên `{1:5, 2:4, 3:3, 4:1}` để mức Thấp (`4 -> 1`) nhường hẳn cho `P3` và `Habit`, bổ sung docstring giải thích ngay tại `map_user_urgency_to_solver_priority()`, và giữ `#stInpPriority` ở chế độ ẩn (`type="hidden"`) trên Student UI.
3. **200 ca YAML dễ "học thuộc" & gói cài đặt nặng (`ctranslate2`, `huggingface-hub`):**
   * *Trạng thái:* **ĐÃ BỔ SUNG 16 CÂU TỰ SOẠN MỚI (EN/VI)** trong `test_hybrid_nl_integration.py` (`test_fresh_student_prompts_beyond_200_yaml_and_default_scored_greedy_plan`) để kiểm tra khả năng tổng quát hóa độc lập ngoài 200 ca YAML. Việc tách `ctranslate2`/`sentencepiece`/`huggingface-hub` sang `requirements-nllb.txt` chuyển sang Mốc 2 dọn repo.
4. **Tính chính xác về ghi công PR #4 & "3 file report trong `Proposal/`":**
   * Commit `4a9d0b5` xây sẵn nền Dual-Engine M1 (`src/nl_parser.py`, `.env.example`, `.gitignore`, 12 test tích hợp, README Gemini); các commit `c3010fd..a24dc26` mở rộng `NL_Parser_Package/` 6 bước, kéo-thả `[[file]]`, 200 ca YAML và `Q9` Phương án A.
   * Trong `Proposal/`, 2 file hậu đồng bộ ([`Sync_Completion_Report.md`](Sync_Completion_Report.md) và [`Open_Decisions_For_Team.md`](Open_Decisions_For_Team.md)) và báo cáo hợp nhất này đã được cập nhật số liệu mới; [`Sync_Audit_And_Fix_Guide.md`](Sync_Audit_And_Fix_Guide.md) được gắn nhãn *Archived / Tham khảo lịch sử tiền đồng bộ*.

---

## 3. Phân Tích Quyết Định `Q1 → Q10` (Hợp Nhất Khuyến Nghị & Cơ Sở Khoa Học)

> Dưới đây là bảng chốt nhanh `Q1–Q10` kèm phân tích chuyên sâu kết hợp **số liệu thực nghiệm trên repo** và **nghiên cứu khoa học bình duyệt**.

### Bảng Tóm Tắt Quyết Định Đã Chốt (`☑ Q1–Q10`)

| Mã | Hạng mục | Quyết định ĐÃ CHỐT thống nhất (`17/11/2026`) | Trạng thái |
| :---: | :--- | :--- | :---: |
| **Q1** | Hệ số buffer `α`, chế độ & làm tròn | **Giữ Dual-Mode; mặc định Student UI dùng `COGNITIVE_LOAD` (`α_light=1.20 / α_heavy=1.35`, `RoundUp_15`), giữ `HABIT` (`nearest_15`) & opt-out `NONE`; `Q1.3` dùng hàm `composite` sẵn có + pilot 7 ngày + stress-test `α >= 1.7`.** | ☑ Đã chốt |
| **Q2** | Hằng số `γ`, trần quá hạn, Habit | **Chốt cứng `γ = 24.0h`, `OVERDUE_URGENCY_CAP = 1.50`, `HABIT_BASE_URGENCY = 0.20`; sửa nhãn Slide 8 thành *Exponential Urgency*.** | ☑ Đã chốt |
| **Q3** | Pattern 3 Circadian Matching | **Chốt cơ chế MỀM đa tầng (Peak Level-3 → Level-2 → Level-1 khi Crunch); bỏ chữ *"strictly"* trên Slide 7.** | ☑ Đã chốt |
| **Q4** | Ngưỡng ổn định sửa lịch `X%` | **Chốt `X = 90%` (`STABILITY_TARGET_PCT = 90.0`).** | ☑ Đã chốt |
| **Q5** | M1 NL Parser & Determinism Slide 12 | **Chốt Hybrid Dual-Engine (`Offline` 6 bước tất định làm lõi bảo đảm + Gemini AI xem trước `#stTaskModal` có User xác nhận — LoA Level 4, tách khỏi Solver SHA-256); ĐÃ xác minh Gemini thật & vá `ai_status`/coarse window; Mốc 2 thêm Progressive Disclosure tối giản `#stTaskModal` ở `STUDENT` Mode (`Gói A.0`).** | ☑ Đã chốt & vá lõi |
| **Q6** | Nghỉ `15p`, dead-zone `< 30p`, auto-split `> 90p` | **Chốt giữ nguyên cả 3 ranh giới hiện tại (`>= 90p` hoặc `load >= 3` chỉ lấy ô `FREE`; khóa mọi dead-zone `<= 1 slot` kể cả `Load-1` ở lượt thường [`Q6.2 = A2`], chỉ mở ở Tier-1 Crunch; auto-split `> 90p` trừ khi user khóa `False`).** | ☑ Đã chốt |
| **Q7** | Experience Rating, Batching & Habits | **Chốt công thức 4 thành phần `[1..5]` & trọng số Batching `+0.35 / -0.25` cho v1.0; chốt mô hình Habit gọn `1 preferred_window + frequency_per_week` (`Q7.3 = A3`) để mở UI + nối Solver ở Mốc 2.** | ☑ Đã chốt |
| **Q8** | Quy trình merge PR #4 & sửa tài liệu | **Hoàn tất toàn bộ Cổng Pre-Merge trên `M1-NL-Parser` (bao gồm `Q10` Nhịp 1+2, chốt `☑ Q1–Q10`, test tay UI & cập nhật `Proposal/`) -> sẵn sàng Merge `main`; sau đó sửa `Presentation2.pdf`.** | ☑ Đã đóng cổng |
| **Q9** | Sprint Mode nén task (`90p → 75p`) | **Chính thức phê chuẩn Phương án A (Tier-1 chỉ cắt nghỉ/dead-zone, KHÔNG tự nén thời lượng gốc; rút ngắn phải qua Triage `SHORTEN_TASK` xác nhận + `Early Extension Alert`).** | ☑ Đã áp dụng |
| **Q10** | Tách `EDF` V0 vs `SCORED_GREEDY` & Default UI | **Đã hoàn tất cả 2 nhịp (`17/11/2026`):** (1) Web UI & `/api/plan` mặc định `SCORED_GREEDY`; (2) `EDF`/`LST`/`WSPT` thuần Energy-Blind (`T09`), `--gaps` dùng `SCORED_GREEDY`, `_repair_full_rebuild()` giữ đúng solver qua `src/solvers/registry.py`. | ☑ Xong cả 2 nhịp |

---

### Chi Tiết Khuyến Nghị & Luận Cứ Khoa Học Từng Mục

#### Q1. Hệ số Planning Fallacy `α`, `HABIT` vs `COGNITIVE_LOAD` & `RoundUp_15` vs `Nearest_15`
* **Khuyến nghị (và hiện trạng `Q1.3`):** Giữ cả `HABIT` (`nearest_15`, bảo toàn `34/34` unit tests Feature 001) và `COGNITIVE_LOAD` (`α_light=1.20 / α_heavy=1.35`, `RoundUp_15`), đặt mặc định **ở tầng Student UI / Preset (`web/app.js` & `#stSettingsModal`)** sang **`COGNITIVE_LOAD`** (kèm nút opt-out `NONE` từng task). **Cảnh báo kỹ thuật quan trọng:** KHÔNG sửa trực tiếp `default="HABIT"` trong [`CommitmentsProfile`](../group03-smartschedule-baseline/src/models.py#L172-L175) nếu chưa gắn tường minh `"buffer_mode": "HABIT"` vào toàn bộ `T01–T10` & V0 fixtures, vì [`apply_estimate_buffer()`](../group03-smartschedule-baseline/src/controller.py#L114-L138) sẽ tự nhân `1.20x–1.35x` lên mọi task V0 và làm sai số liệu `shortage_minutes` của `T03`/`T06`. Riêng **`Q1.3` (hàm mục tiêu 1D Grid Search)** đã có sẵn hàm `composite` chuẩn hóa trong [`benchmark_alpha_grid.py`](../group03-smartschedule-baseline/benchmark_alpha_grid.py#L189-L197):
  `composite = 0.35*avg_dl + 0.25*avg_s25_dl + 0.20*avg_s50_dl + 0.20*avg_s25_zero - 4.0*max(0, avg_rating-2.0) - 2.0*avg_frag - 100.0*hard_violations`.
  Chưa nâng toàn bộ lên `1.40` cho tới khi hoàn thành 7 ngày log `actual_duration_min` thật + bổ sung kịch bản tải hẹp `α >= 1.7` trong `benchmark_alpha_grid.py`.
* **Luận cứ Khoa học & Thực nghiệm:**
  * **Tâm lý học nhận thức — Buehler, Griffin & Ross (1994, *JPSP*):** Nghiên cứu gốc về *Planning Fallacy* đo trên sinh viên đại học cho thấy thời gian dự đoán "thực tế nhất" trung bình là `33.9 ngày` nhưng thời gian hoàn thành thực tế là **`55.5 ngày`** (`Actual / Estimated ≈ 1.64`, chỉ `~30%` hoàn thành đúng hạn, tệ hơn cả ước lượng bi quan `48.6 ngày`). Nguyên nhân là thiên kiến *"inside view"* (Kahneman & Tversky, 1979): người làm chỉ hình dung luồng làm việc lý tưởng của bài hiện tại mà phớt lờ độ trễ thống kê ở quá khứ.
  * **Thực nghiệm trực tiếp trên repo ([`alpha_grid_calibration.json`](../group03-smartschedule-baseline/data/alpha_grid_calibration.json)):**
    * Nếu không đệm (`α = 1.00`), khả năng hấp thụ sốc `+25%` mà không phải xáo lịch (`+25%NoRep`) bằng **`0.0%`** (`Score = 79.61`) — cứ làm lố 25% là hỏng lịch dây chuyền.
    * Cặp đối xứng **`(1.40, 1.40)`** đạt điểm tổng hợp `99.90` (`Frag = 0.05`, `5374.0 phút` rảnh/tuần), nhưng ép cộng `+40%` lên cả việc nhẹ/quen gây thừa giờ giả khi tuần bận.
    * Cặp bất đối xứng **`(1.20, 1.35)`** đạt **`Score = 99.34`**, hấp thụ **`97.1%`** sốc `+25%` và `100%` `+50%Rdl`, đạt **độ phân mảnh thấp nhất toàn bảng (`0.04`)**, và giữ được **`5456.0` phút rảnh/tuần** — **tiết kiệm `+82 phút/tuần`** so với `(1.40, 1.40)`.
  * **Tại sao `COGNITIVE_LOAD` dùng `RoundUp_15`:** Trên lưới 15 phút/slot, `Nearest_15` làm biến mất đệm của task ngắn (`15p × 1.25 = 18.75p → 15p`), nên `RoundUp_15` đảm bảo ít nhất `+1 slot` bảo hiểm đúng như toán học Slide 7 & 17; còn `HABIT` giữ `Nearest_15` để bảo toàn hợp đồng V0.

#### Q2. Hằng số `γ`, Trần quá hạn `1.50` & Trọng số Habit `0.20`
* **Khuyến nghị:** Chốt **`γ = 24.0 giờ`**, **`OVERDUE_URGENCY_CAP = 1.50`**, **`HABIT_BASE_URGENCY = 0.20`**, và sửa tên trên Slide 8 thành **"Exponential Urgency" (`exp(-slack / γ)`)** cho khớp toán học.
* **Luận cứ Khoa học & Toán học:**
  * **Temporal Motivation Theory (Steel & König, 2006; Steel, 2007):** Công thức $U = \frac{E \times V}{1 + I \times D}$ giải thích sự trì hoãn sinh ra vì con người chiết khấu giá trị tương lai khi hạn chót (`Delay`) còn xa, rồi hoảng loạn dồn việc khi `Delay → 0`. Bộ lập lịch phải mô phỏng sự leo thang độ khẩn cấp từ sớm hơn điểm hoảng loạn đó.
  * **Định lượng ngay trong [`scored_greedy.py`](../group03-smartschedule-baseline/src/solvers/scored_greedy.py#L34-L52):**
    * Với `γ = 24h`, đường `exp(-slack / 24)` leo đều trước hạn 1–2 ngày (`72h → 0.05`, `48h → 0.135`, `24h → 0.368`, `0h → 1.00`) — vừa đủ sớm để xếp việc lớn không dồn sát giờ nộp, vừa không đánh đồng việc ngày mai với việc tuần sau.
    * Trần `1.50` (cộng tối đa `+0.50` tie-breaker theo độ trễ) tránh tràn số và chặn 1 bài đã quá hạn lâu đè chết các bài hôm nay vẫn còn kịp nộp.
    * Habit (`deadline = None`) được gắn nền `0.20 * priority` (`[0.20..1.00]`, riêng habit `P1` là `0.20`), không bị liệt ở `Score = 0` (`exp(-∞)`), nhưng luôn nhường slot cho bài học sắp hạn (ví dụ task `P5` còn `24h` đạt `5 × e^-1 ≈ 1.84 > 1.00`, ngay cả `P3` còn `24h` đạt `1.10 > 1.00`).

#### Q3. Pattern 3 (Circadian Energy Matching): Cứng (`strictly`) vs Mềm (`Soft`)
* **Khuyến nghị:** Chốt **cơ chế Mềm đa tầng** (ưu tiên cao Level-3 Peak → fallback Level-2 trước hạn → chỉ xuống Level-1 khi Crunch), sửa Slide 7 bỏ *"strictly"* cho thống nhất với Slide 9.
* **Luận cứ Khoa học:**
  * **Sinh học nhịp ngày đêm & Synchrony Effect (Schmidt et al., 2007; Roenneberg et al., 2003, 2007):** Hiệu suất xử lý nhận thức phức tạp đạt đỉnh khi khớp đồng hồ sinh học (*Morning Larks* vs *Evening Owls*); sinh viên đại học thường có dịch pha muộn (*late chronotype*) dễ mắc *Social Jetlag* khi bị ép học sáng sớm. Tuy nhiên, một sinh viên thường chỉ có ~3–4 giờ Peak/ngày; nếu khóa cứng, tuần nào có 6 giờ bài `Load-3`/ngày hệ thống sẽ **cố tình đánh rớt hạn $H_4$** (0 điểm học thuật) dù các buổi khác hoàn toàn rảnh. Ràng buộc mềm giữ đúng ưu tiên Peak khi còn chỗ, lùi sang Level-2 để cứu deadline, và báo lại độ lệch qua `Experience Rating`.

#### Q4. Ngưỡng ổn định `Schedule Stability >= X%` (Pattern 8)
* **Khuyến nghị:** Chốt **`X = 90%`** (`STABILITY_TARGET_PCT = 90.0`).
* **Luận cứ Khoa học & Thực nghiệm:**
  * **Minimal Perturbation Problem & Iterative Repair (Barták, Müller & Rudová; Zweben et al.):** Xáo trộn toàn lịch (*Full Rebuild*) khi có việc đột xuất gây chi phí tái thích nghi tâm lý rất lớn khiến người dùng mất niềm tin và bỏ app (*automation disuse*). Benchmark trên `T04` cho thấy `LOCAL_INSERTION` giữ **`100.00%`** stability (`Moved = 2` blocks bị đè trực tiếp) so với **`0.00%`** của `FULL_REBUILD` (`Moved = 12` blocks). Ngưỡng `90%` đủ nghiêm để chặn Rebuild bừa bãi, đồng thời chừa biên `10%` cho `Progressive Unfreezing` dịch chuyển vài block mềm khi thật sự cần.

#### Q5. M1 NL Parser: Gemini API vs Offline Deterministic & Tiêu chuẩn SHA-256 (Slide 12)
* **Khuyến nghị:** Chốt **Dual-Engine Hybrid (`Offline` 6 bước tất định làm lõi bảo đảm + Gemini AI làm trợ lý tùy chọn ở màn hình xem trước `#stTaskModal`, người dùng xác nhận trước khi lưu vào Solver)**; đồng bộ nút gạt này cho cả Lab Mode ở Mốc 2. *(Đã hoàn tất kiểm chứng Live Gemini thật ngày 17/11/2026 + sửa `NL_Parser_Package/` sang relative import + thêm `validation["ai_status"]` + giữ giờ buổi `sáng/trưa/chiều/tối`.)*
* **Luận cứ Khoa học:**
  * **Phân tách Neuro-Symbolic & Human-in-the-Loop (Parasuraman, Sheridan & Wickens, 2000 — Automation Level 4):** Ngôn ngữ tự nhiên giàu biến thể cần sức mạnh ngữ nghĩa của LLM (khi có mạng/key), trong khi bộ giải lịch `M2–M6` cần `100%` tất định `SHA-256`. Vì bước parse chỉ điền *bản nháp* để người dùng kiểm tra/chỉnh tay (LoA Level 4) trước khi bấm Lưu thành `TaskSheet` chuẩn, **toàn bộ tầng Solver `M2–M6` không bao giờ mất tính tất định `SHA-256`**. Khi offline, CI, hoặc gạt sang `⚡ Offline`, cả 2 tầng đều `100%` tất định (`200/200` trong `616.5 ms` = `3.08 ms/case`).

#### Q6. Ranh giới `15p REST`, Dead-Zone `< 30p`, Auto-Split `> 90p`
* **Khuyến nghị (đã chốt `Q6.2 = A2`):** Giữ nguyên cả 3 ranh giới như đang cài:
  1. Nghỉ `15p` sau block `>= 90p` **hoặc** `cognitive_load >= 3` (chỉ đặt lên ô `FREE` — tự miễn nếu liền sau đã là `SLEEP`/`MEAL`/`OCCUPIED`).
  2. Dead-zone `<= 1 slot` (`< 30p`) bị đánh dấu `STATE_REST:DEAD_ZONE` **ngay cả với tác vụ nhẹ `Load-1` ở lượt thường** (`allow_breaks=True`, phương án **`Q6.2 = A2`** nhằm chống phân mảnh lịch và giảm dư lượng chú ý khi chen việc lặt vặt 15p giữa 2 tiết học) và chỉ tự mở khóa ở `Tier-1 Crunch` (`allow_breaks=False`).
  3. Auto-split `duration_min > max_chunk_min` (`90p`) trừ khi người dùng chủ động khóa `"🔒 Làm liền 1 buổi"` (`is_splittable=False`).
* **Luận cứ Khoa học:**
  * **Kleitman (1963, 1982) BRAC (~90 phút) & Ericsson, Krampe & Tesch-Römer (1993) Deliberate Practice:** Phiên tập trung sâu hiệu quả nhất kéo dài khoảng `60–90 phút` kèm quãng nghỉ phục hồi giữa các phiên; quá `90 phút` không nghỉ gây suy giảm mạnh độ chính xác và mệt mỏi thần kinh.
  * **Leroy (2009) — *Attention Residue*:** Khi bắt đầu/chuyển việc, não mất thời gian chuyển trạng thái để xả dư lượng chú ý; một khe trống lẻ `15 phút` giữa 2 ca cố định không đủ vượt qua pha khởi động & thu dọn nên phải coi là khoảng thở *dead-zone* ở chế độ thường, chỉ tận dụng khi bật Crunch để kịp hạn.

#### Q7. Trọng số `Experience Rating (1–5)`, `Category Batching`, Pilot 1 Tuần & `PersonalHabit`
* **Khuyến nghị (đã chốt `Q7.3 = A3`):** Chốt công thức 4 thành phần hiện tại của `calculate_experience_rating()` (`density 0..2.2`, `streak 0..0.8`, `circadian 0..0.6`, `overload 0..1.0`) và trọng số `CATEGORY_BATCH_BONUS = 0.35`, `CONTEXT_SWITCH_PENALTY = 0.25` cho v1.0; tổ chức pilot 1 tuần lấy `actual_duration_min` + tự đánh giá mệt mỏi; và áp dụng phương án **`Q7.3 = A3`** cho `PersonalHabit` ở Mốc 2: giữ mô hình gọn **`1 preferred_window` (`MORNING | AFTERNOON | EVENING`) + `frequency_per_week`** (tự dàn đều giữa các ngày trong tuần khi nối vào `expand_personal_habits()` và mở form UI Student Mode), tránh làm phức tạp quá mức bảng nhập đa khung giờ lặp theo từng thứ.
* **Luận cứ Khoa học & Toán học:**
  * **Chi phí chuyển ngữ cảnh (Rubinstein, Meyer & Evans, 2001; Leroy, 2009):** Đổi môn liên tục ép não chạy lại quá trình *goal shifting* và *rule activation*, làm giảm hiệu suất và tăng cảm giác kiệt sức.
  * **Chứng minh biên độ trong [`base_solver.py`](../group03-smartschedule-baseline/src/solvers/base_solver.py#L462-L484):** Điểm Circadian cho `Load-3` là `(avg_energy - 1.5) * 4.0` nằm trong **`[-2.0, +6.0]`** (biên độ `8.0`), còn Category Batching chỉ nằm trong **`[-0.25, +0.35]`** (biên độ `0.60`, tỷ trọng ~7.5%–15%). Tỷ lệ toán học này đảm bảo gom môn chỉ làm **tie-breaker làm mượt lịch trong ngày**, tuyệt đối không phá giờ Peak hay đánh đổi deadline.

#### Q8. Quy trình Hợp nhất Nhánh, Sửa `Proposal/` & `Presentation2.pdf`
* **Khuyến nghị:** Thực hiện đúng thứ tự cổng kiểm soát ở **Phần IV** bên dưới trên `M1-NL-Parser` trước khi bấm Merge PR #4 vào `main`, ghi công rõ phần của cả `4a9d0b5` lẫn `c3010fd..a24dc26`, cập nhật 2 file báo cáo hậu đồng bộ trong `Proposal/` + lưu trữ `Sync_Audit_And_Fix_Guide.md`, rồi mới gỡ `(Unverified)`, `(Planned)`, `X%`, `γ` trên `Presentation2.pdf` sau cùng.

#### Q9. Sprint Mode Tier 1: Phương án A vs B (`90p → 75p`)
* **Khuyến nghị:** **Chính thức phê chuẩn Phương án A** (như test mới trong `c58e4fd`): Tier 1 chỉ tự cắt nghỉ 15p & dùng dead-zone (`Cut breaks`), **tuyệt đối không tự ý cắt ngắn thời lượng gốc của người dùng**; mọi việc rút ngắn phải qua đề xuất `SHORTEN_TASK` của Overload Triage để sinh viên xác nhận + cảnh báo `Early Extension Alert`.
* **Luận cứ Khoa học:**
  * **Parasuraman, Sheridan & Wickens (2000) — Levels of Automation:** Nếu phần mềm tự ý chặt task `90p` xuống `75p` không xin phép (tương đương LoA Level 7–8), sinh viên rơi vào *Out-of-the-Loop*: thấy lịch báo "Đã xếp" tưởng mình đủ thời gian nhưng thực chất bị thiếu 17–25% khối lượng ôn thi ngoài đời → phá hủy hoàn toàn niềm tin (*Automation Disuse*). Ở LoA Level 4, phần mềm giữ nguyên toàn vẹn dữ liệu gốc và trao quyền đánh đổi cho người dùng.
  * **Van Dongen, Maislin, Mullington & Dinges (2003 — *SLEEP*):** Sàn ngủ cứng **`>= 6 giờ/đêm`** trong Pattern 6 cũng mang tính khoa học bắt buộc (không nên cho Sprint Mode xâm phạm dưới 6h), vì thí nghiệm trên PVT chứng minh ngủ `6h/đêm` liên tục 14 ngày tạo ra suy giảm nhận thức **tương đương thức trắng 24 giờ**, dù người thiếu ngủ chủ quan tưởng mình đã thích nghi.

#### Q10. Tách `EDF` Baseline V0 vs `SCORED_GREEDY` & Mặc định Web UI / `FULL_REBUILD`
* **Trạng thái (✅ ĐÃ HOÀN TẤT CẢ 2 NHỊP trên `M1-NL-Parser`):**
  * **Nhịp 1 (UI & API Default):** Chuyển lựa chọn mặc định Web UI (`#solverSelect`, `#stSetSolver`, `#kpiSolverLabel`, `web/app.js`) và `POST /api/plan` (`web/api.py#L67`) sang **`SCORED_GREEDY`** (`8.40 ms` trên `T01`, giữ `EDF` trong menu Lab).
  * **Nhịp 2 (Tách Energy-Blind V0 & Forward Solver):**
    1. Chuyển [`BaseScheduler.should_prefer_energy_placement()`](../group03-smartschedule-baseline/src/solvers/base_solver.py#L490-L497) về `False` để `EDF`/`LST`/`WSPT` thành **Energy-Blind V0** (chỉ `SCORED_GREEDY` và `BacktrackingSolver` tối ưu Circadian & Category Batching); `build_chunk_reasons()` chỉ phát `ENERGY_MATCH`/`ENERGY_FALLBACK`/`BATCHED_CATEGORY` khi solver là Energy-Aware. Kết quả `T09` Controlled Ablation: `EDF` trả cùng hash `4268107a006d` cho cả `MORNING` & `EVENING` (`Monday 06:30-08:00`), còn `SCORED_GREEDY` dịch từ `06:30-08:00` (`f65266353eff`) sang `18:00-19:30` (`ac905601e5bf`).
    2. Cập nhật `test_fail_circadian_energy_matching` và `test_fail_why_popover_structured_reason_codes` trong [`test_improve_plan_gaps.py`](../group03-smartschedule-baseline/verification_tests/development_gap_tests/test_improve_plan_gaps.py) sang `algorithm="SCORED_GREEDY"` (`5/5 PASS`).
    3. Tách [`src/solvers/registry.py`](../group03-smartschedule-baseline/src/solvers/registry.py) để [`LocalRepairEngine._repair_full_rebuild()`](../group03-smartschedule-baseline/src/solvers/local_repair.py#L578-L612), `ScheduleController.compare_repair_modes()`, `POST /api/repair` và `web/app.js` truyền đúng `algorithm` hiện hành thay vì gắn cứng `GreedyEDFSolver()`.
* **Luận cứ Khoa học:** Trong **Controlled Ablation Experiment** (Khoa học Máy tính), mô hình đối chứng nền (`EDF V0`) không được phép chứa cơ chế nâng cấp (`Circadian/Batching`) của mô hình mới (`SCORED_GREEDY`). Bảng 5 trong `benchmark_runner.py` và bộ `147/147` tests hiện chứng minh tách bạch hoàn toàn V0 vs V1/V2.

---

## 4. Lộ Trình Hành Động Chia 2 Cột Mốc Rõ Ràng

### Cột mốc 1 — Cổng Kiểm Soát Trước Khi Merge PR #4 (`M1-NL-Parser -> main`) — ✅ ĐÃ HOÀN TẤT
1. ✅ **Chốt xong bảng `Q1–Q10`:** Toàn bộ `Q1–Q10` đã được duyệt & đánh dấu **`☑`** trong Phụ lục A (chi tiết tại [`Open_Decisions_For_Team.md`](Open_Decisions_For_Team.md)).
2. ✅ **Kiểm thử sống E2E + Tự động:**
   * **Live Gemini API + FastAPI:** Đã kiểm chứng với `.env` (`GEMINI_API_KEY` thật, `gemini-3-flash-preview`, `"chiều mốt..." -> Wednesday 17:00, duration_min=90, matched=['Slide_Draft.pptx'] -> SCORED_GREEDY 1 block`).
   * **Automated Suites:** `141` `--pass`, `5` `--gaps`, **`147/147` `--all` / `pytest`** (bao gồm `16` câu EN/VI mới & regression test `Q10` Nhịp 2), **`200/200` YAML**, **`T01–T10` `C_hard=0`** + Bảng 5 Ablation `T09`.
   * **Test tay Web UI (`http://127.0.0.1:8000`):** Người dùng đã test trực tiếp giao diện hiển thị đúng và phản hồi đề xuất tối giản `#stTaskModal` ở User Mode (đưa vào Gói A.0 Cột mốc 2).
3. ✅ **Vá kỹ thuật & `Q10` Nhịp 1 + Nhịp 2:** Đã xong toàn bộ các bản vá NL Package, UI/API default `SCORED_GREEDY`, Energy-Blind V0, `_repair_full_rebuild()` forwarding và cập nhật đồng bộ tài liệu `Proposal/`, `agents/`, `docs/`.

### Cột mốc 2 — ĐÃ HOÀN THÀNH Gói A.0 + Gói A.1–A.3 + Gói B (Sẵn Sàng Xài Cá Nhân Hằng Ngày)
* ✅ **Gói A.0 — Progressive Disclosure Modal Thêm Việc (`#stTaskModal`: `STUDENT` Mode vs `LAB` Mode):**
  * **Thiết kế đã triển khai:** Áp dụng `.app-mode-student .st-lab-only-modal { display: none !important; }` kết hợp `syncTaskModalModeVisibility()` trong [`web/index.html`](../group03-smartschedule-baseline/web/index.html) & [`web/app.js`](../group03-smartschedule-baseline/web/app.js) — **giữ nguyên 100% DOM IDs & handlers** cho `LAB` Mode và `test_web_ui_serves_hybrid_controls_and_handlers()`.
  * Ở `STUDENT` Mode mặc định chỉ hiện thanh chat AI (`#stNlPrompt` + nút đính kèm gọn `📎` + `Phân tích`), **4 trường cốt lõi** (Tên việc `#stInpTitle`, Thời lượng `#stInpDuration`, Hạn chót `#stInpDeadlineDay`/`#stInpDeadlineTime`, Mức ưu tiên `#stInpPriorityCore` / Phân loại `#stInpCategory`), và ngăn `<details id="stTaskAdvDetails">` mặc định đóng chứa `Task ID`, `work_rhythm`, `start_after`, `cognitive_load`, `buffer`, `depends_on`. Ở `LAB` Mode tự động mở toàn bộ bảng kỹ thuật & chẩn đoán JSON.
* ✅ **Gói A.1–A.3 — Lưu trữ bền vững, Thời gian thực & Hoàn thiện Student/Solver:**
  1. **Lưu trữ bền vững (`src/storage.py` SQLite + `localStorage`):** Lưu đủ `commitments`, `tasks`, `pinned_blocks`, `done_blocks`, `actual_durations`, `algorithm` qua `GET/PUT/DELETE /api/state` và nhật ký hoàn thành M7 qua `POST /api/tasks/complete` & `GET /api/tasks/completions`; chỉ nạp `loadPreset("minh")` ở lần mở đầu tiên khi chưa có state lưu.
  2. **Thời gian thực & Đa tuần:** Bổ sung `CommitmentsProfile.horizon_days` (`7..14`), nối `BaseScheduler.resolve_horizon_slots()` & `grid_states` lên tới `1344` slot; thêm nút `◀ Tuần 1 / Tuần 2 ▶`, `7 ngày / 14 ngày`, và `🕒 Tuần này` (`getCurrentMondayIso()` + `now` thực tế) trên Student UI (vẫn giữ nguyên ngày cố định khi bấm preset Minh/Lan).
  3. **Hoàn thiện Student CRUD, `PersonalHabit` & Solver:** Mở **Sửa Task** (`editStudentTask` ngay trên `#stTaskModal`), form **`PersonalHabit`** (`1 preferred_window + frequency_per_week + duration_min`, `Q7.3 = A3`) và rải ngày thông minh + chấm điểm `preferred_window` ở `expand_personal_habits()` / `score_candidate_slot()`; nối `Task.start_after` & `Task.work_rhythm` vào `Task` / `BaseScheduler` / `BacktrackingSolver`; gỡ `engine: "offline"` trong `analyzeQuickAddHybrid()`; sửa `OfflineNLParser.extract_duration_min()` lọc chuẩn cụm giờ/khoảng giờ (`19h30`, `14h00 - 16h00`) không bị đọc nhầm sang `duration_min`.
* ✅ **Gói B — Tinh Gọn Kỹ Thuật (Đã xong phần code/scripts):**
  1. Đặt Student UI/Settings `buffer_mode` mặc định là `"COGNITIVE_LOAD"` (`1.20/1.35`) và preset `"empty"` dùng `"COGNITIVE_LOAD"` (giữ `CommitmentsProfile.buffer_mode` Pydantic fallback `"HABIT"` để bảo toàn `T01–T10`); cập nhật `run_app.bat`, `run_verification_tests.bat`, `run_test_studio.bat` ưu tiên `.venv\Scripts\python.exe`; tách `ctranslate2`/`sentencepiece`/`huggingface-hub` sang [`requirements-nllb.txt`](../group03-smartschedule-baseline/requirements-nllb.txt) và đồng bộ `agents/requirements.md` & `docs/requirements.md`.
  2. **Việc nhóm làm thêm trước/sau bảo vệ:** Chạy pilot 1 tuần thu log `actual_duration_min` thực tế + bổ sung kịch bản tải cực hẹp (`α >= 1.7`) vào `benchmark_alpha_grid.py`, và cập nhật văn bản trực tiếp trên file nguồn `.pptx` -> xuất [`Proposal/Presentation2.pdf`](Presentation2.pdf) (gỡ `(Unverified)`, `(Planned)`, `X%`, `γ`).
* ✅ **Gói A.4 — Tái Thiết Lập UI Ngày Cụ Thể (`DD/MM/YYYY`) & Lab Research Workbench (`Lần cập nhật 013`):**
  1. **Ngày `DD/MM/YYYY` & Trục Thời Gian Thực:** Mọi cột Lịch Tuần, pill Hôm Nay, hạn chót Task (kèm đếm ngược `Còn Xd Yh` / `Quá hạn`), Lưới & Bảng Lab đều hiển thị rõ `DD/MM/YYYY`, phân tách `Đã qua / HÔM NAY / Sắp tới`, chèn vạch `🔴 BÂY GIỜ`, thẻ `▶ ĐANG DIỄN RA`, và banner `#temporalContextBanner` khi xem dữ liệu lịch sử (`02/11/2026`).
  2. **Student UI Một Nguồn Thao Tác & `PersonalHabit` Trực Tiếp:** Hợp nhất action bar + dropdown `#studentToolsMenu`, mở tab `🏃 Thói Quen Tuần` đồng bộ `#stSettingsModal`, và gắn Check-in M7 inline ngay trên Hero card.
  3. **Lab Mode 3 Workspace Có Đúc Kết Định Lượng:** Loại bỏ form `#inpTask*` trùng lặp; bổ sung 6 KPI (gồm `Khớp Peak Circadian` & `Experience/Context Switches`), `#labFixedInspectorPanel`, Phòng So Sánh A/B (`#compareVerdictBanner`, bảng 9 chỉ số, bảng Diff từng task/phiên, lưới 672 slot thu gọn) và Tab Độ Bền T04/T05 + Ledger 3x SHA-256 5 solvers.
* ⏳ **Gói C — Thương Mại Hóa & Nâng Cấp SaaS (Post-V1):** Auth/OAuth2 + tách dữ liệu đa người dùng (`user_id`), siết `CORS` + Rate Limiting & Quota AI theo gói Free/Pro, đồng bộ 2 chiều Google Calendar / LMS, Focus Timer/Pomodoro gắn Check-in M7, tự hiệu chỉnh `α` cá nhân theo EWMA, đóng gói Docker + Monitoring + Billing.

---

## Phụ Lục A — Bảng Tổng Hợp Quyết Định Đã Chốt (`☑ Q1–Q10`)

| Mã | Quyết định đã chốt thống nhất (`17/11/2026`) | Trạng thái | Người phụ trách |
| :---: | :--- | :---: | :--- |
| **Q1** | Mặc định **Student UI** dùng `COGNITIVE_LOAD` (`1.20/1.35`, `RoundUp_15`), giữ `"HABIT"` làm V0 fallback ở `CommitmentsProfile`; dùng hàm `composite` sẵn có ở `benchmark_alpha_grid.py` (`Q1.3`) + pilot 7 ngày + stress-test `α >= 1.7`. | ☑ | Backend + Frontend |
| **Q2** | Chốt `γ = 24.0h`, trần `1.50`, `Habit = 0.20`; đổi nhãn Slide 8 thành **Exponential Urgency**. | ☑ | Presentation2 |
| **Q3** | Chốt Circadian Matching **Mềm đa tầng**; bỏ *"strictly"* trên Slide 7. | ☑ | Presentation2 |
| **Q4** | Chốt ngưỡng ổn định sửa lịch `X = 90%`. | ☑ | Presentation2 |
| **Q5** | Chốt Hybrid Dual-Engine (`Offline` tất định + `Gemini` LoA Level 4, đã test live & thêm `ai_status`); mở chọn engine cho Lab Mode + tách UX đơn giản ở Student Mode (`Gói A.0`). | ☑ | M1 + Web UI |
| **Q6** | Giữ `>= 90p` / `load >= 3` nghỉ `15p` ô `FREE`, auto-split `> 90p` trừ khóa `False`; **Chốt `Q6.2 = A2`:** khóa mọi dead-zone `<= 1 slot` kể cả `Load-1` ở lượt thường, mở ở Tier-1 Crunch. | ☑ | Docs / Presentation2 |
| **Q7** | Chốt Experience Rating 4 thành phần, Batching (`+0.35/-0.25`), pilot 1 tuần; **Chốt `Q7.3 = A3`:** `PersonalHabit` dùng `1 preferred_window + frequency_per_week` mở UI & nối Solver ở Mốc 2. | ☑ | Frontend + Controller |
| **Q8** | Hoàn tất Cổng Pre-Merge trên `M1-NL-Parser` (sẵn sàng Merge PR #4 vào `main`), sau đó triển khai Mốc 2 & cập nhật `Presentation2.pdf`. | ☑ | Cả nhóm |
| **Q9** | Chính thức phê chuẩn **Phương án A** (Tier-1 chỉ cắt nghỉ/dead-zone, không tự cắt task gốc; rút ngắn phải qua Triage xác nhận). | ☑ | Cả nhóm |
| **Q10** | **Đã xong cả 2 nhịp:** (1) Web UI & `/api/plan` mặc định `SCORED_GREEDY`; (2) Tách `EDF`/`LST`/`WSPT` về thuần Energy-Blind V0 (`T09`), `--gaps` dùng `SCORED_GREEDY`, `_repair_full_rebuild()` giữ đúng solver qua `src/solvers/registry.py`. | ☑ | Solvers + UI + Tests |

---

## Phụ Lục B — Nguồn Khoa Học Tham Chiếu
1. **Buehler, R., Griffin, D., & Ross, M. (1994).** *Exploring the "planning fallacy": Why people underestimate their task completion times.* Journal of Personality and Social Psychology, 67(3), 366–381.
2. **Steel, P. (2007); Steel, P., & König, C. J. (2006).** *Temporal Motivation Theory* — Psychological Bulletin / Academy of Management Review.
3. **Kleitman, N. (1963/1982); Ericsson, K. A., Krampe, R. T., & Tesch-Römer, C. (1993).** *Basic Rest-Activity Cycle (~90m)* & *Deliberate Practice.* Psychological Review.
4. **Leroy, S. (2009); Rubinstein, J. S., Meyer, D. E., & Evans, J. E. (2001).** *Attention Residue* (OBHDP) & *Task-Switching Costs* (JEP:HPP).
5. **Schmidt, C., Collette, F., Cajochen, C., & Peigneux, P. (2007); Roenneberg, T. et al. (2003, 2007).** *Circadian Synchrony Effect* & *Social Jetlag.*
6. **Van Dongen, H. P. A., Maislin, G., Mullington, J. M., & Dinges, D. F. (2003).** *The cumulative cost of additional wakefulness (6h sleep restriction vs 24h deprivation).* SLEEP, 26(2), 117–126.
7. **Barták, R., Müller, T., & Rudová, H.; Zweben, M. et al.** *The Minimal Perturbation Problem in Constraint Programming / Iterative Repair Scheduling.*
8. **Parasuraman, R., Sheridan, T. B., & Wickens, C. D. (2000).** *A model for types and levels of human interaction with automation.* IEEE Trans. SMC-A, 30(3), 286–297.
