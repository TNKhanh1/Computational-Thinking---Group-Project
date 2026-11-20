# ⚡ SmartSchedule — Trợ Lý Cá Nhân Tự Động Hóa Xếp Lịch Học Tập & Tối Ưu Năng Suất
### Personal Productivity Assistant for Automated Task & Timetable Scheduling

> **Môn học:** Tư duy Tính toán (CS252) — Khoa Công nghệ Thông tin, Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM (FIT-HCMUS)  
> **Nhóm thực hiện:** Group 03 (*The Seven Dwarfs*)  
> **Phiên bản:** **V3 Commercial-Ready Build** — Bộ 6 Solvers Công Thái Học (gồm `SCORED_GREEDY` mặc định & `HYBRID_ALNS` tối ưu sâu), Kiểm thử `Testing_System v2.1 + Fuzz v2` (`39/39` passed), **`167/167`** Verification Tests, Web UI/API Chẩn Đoán 4 Trụ Cột Thời Gian Thực (`POST /api/evaluate`), và Chương trình Chấm Mù Đa Thành Viên (`member_eval/`, Port `8010`)

---

## 📌 Mục Lục
1. [Giới Thiệu Dự Án](#-giới-thiệu-dự-án)
2. [Cấu Trúc Kho Lưu Trữ (Repository Structure)](#-cấu-trúc-kho-lưu-trữ-repository-structure)
3. [Điểm Nổi Bật & Tính Năng Cốt Lõi](#-điểm-nổi-bật--tính-năng-cốt-lõi)
4. [Hướng Dẫn Cài Đặt & Khởi Chạy Nhanh](#-hướng-dẫn-cài-đặt--khởi-chạy-nhanh)
5. [Tài Liệu Hướng Dẫn Chi Tiết](#-tài-liệu-hướng-dẫn-chi-tiết)
6. [Thành Viên Nhóm Thực Hiện](#-thành-viên-nhóm-thực-hiện)

---

## 📖 Giới Thiệu Dự Án

**SmartSchedule** là dự án giải quyết bài toán tự động phân bổ lịch trình học tập và làm việc cá nhân cho sinh viên dựa trên nền tảng **Tư duy Tính toán (Computational Thinking)**. 

Hệ thống mô hình hóa tuần lễ sinh viên thành một **Lưới rời rạc 672 slots (mỗi slot = 15 phút)**, tiếp nhận các cam kết cố định (lịch học, ca làm, giờ ăn), bảo vệ giấc ngủ sinh học ($\ge 6$ giờ/đêm), và tự động sắp xếp các công việc linh hoạt (bài tập, đồ án, ôn thi) vào các khoảng thời gian trống tối ưu mà **tuyệt đối không xảy ra xung đột thời gian**, đồng thời tính đến bộ đệm sai lệch thời gian ước tính (Planning Fallacy) và sự đồng bộ nhịp sinh học năng lượng.

---

## 📂 Cấu Trúc Kho Lưu Trữ (Repository Structure)

```text
Computational-Thinking---Group-Project/
├── README.md                              # Tài liệu tổng quan dự án (file này)
│
├── Proposal/                              # Hồ sơ đề xuất & tài liệu đồng bộ dự án
│   ├── Proposal_Report.pdf                # Báo cáo đề xuất hoàn chỉnh (45 trang)
│   ├── Presentation.pdf                   # Slide báo cáo đề xuất (53 trang)
│   ├── Presentation2.pdf                  # Slide trình bày tham số & 8 Behavioral Patterns (18 trang)
│   ├── Sync_Audit_And_Fix_Guide.md        # Bản kiểm toán đối chiếu mã nguồn với Presentation2
│   ├── Open_Decisions_For_Team.md         # Danh sách Q1–Q10 cần nhóm thảo luận & biểu quyết
│   └── Sync_Completion_Report.md          # Báo cáo kết quả đồng bộ & các điểm tồn đọng
│
├── Baseline_Plan/                         # Đặc tả kỹ thuật hệ sinh thái Baseline (V0)
│   └── baseline_plan.md                   # Đặc tả toán học, 672 slots, 5 ràng buộc cứng H1-H5
│
├── Improve_Plan/                          # Kế hoạch cải tiến và mở rộng hệ thống
│   ├── improve_plan.md                    # Lộ trình nâng cấp thuật toán (V1/V2, nhịp sinh học, ML)
│   └── improve_plan_summary.pdf           # Bản tóm tắt cải tiến hệ thống
│
├── Testing_Plan/                          # 📚 Đặc tả Checker v2.1, Báo cáo Benchmark V3 & Kế hoạch chấm người thật
│   ├── HANDOFF_SUMMARY_AND_NEXT_TASKS.md  # Tổng kết bàn giao & lộ trình P0–P3
│   ├── evaluation_plan.md                 # Kế hoạch chương trình trung gian chấm mù 7 thành viên (UX-1..UX-6)
│   ├── ultimate_plan.md                   # Kiến trúc nâng cấp 6 solvers V3 & HYBRID_ALNS
│   ├── Solver_Benchmark_Report.md         # Báo cáo benchmark 220 đề × 6 thuật (1.320 lượt chạy)
│   └── CT_Rationale_Log.md                # Nhật ký 17 lập luận Tư duy Tính toán
│
├── Testing_System/                        # 🧪 Bộ sinh đề Fuzz v2 + Máy chấm 4 Trụ Cột v2.1 (39/39 tests)
│
├── group03-smartschedule-baseline/         # ⭐ MÃ NGUỒN CHÍNH THỨC CỦA HỆ THỐNG
│   ├── README.md                          # Sổ tay kỹ thuật chi tiết hướng dẫn cài đặt, Gemini .env, chạy & REST API
│   ├── requirements.txt                   # Thư viện Python (FastAPI, Pydantic, Pytest, google-genai, PyYAML...)
│   ├── .env.example                       # Mẫu cấu hình API Key Google Gemini (copy thành .env cục bộ, đã ignore trên Git)
│   ├── setup_env.bat                      # Script 1-click tạo .venv và cài thư viện trên Windows
│   ├── run_app.bat                        # File khởi chạy nhanh Web Workbench (http://127.0.0.1:8000)
│   ├── run_member_eval.bat                # File khởi chạy Cổng Chấm Mù Đa Thành Viên (http://127.0.0.1:8010)
│   ├── main.py                            # CLI Runner cho lập lịch nhanh
│   ├── benchmark_runner.py                # Runner thực nghiệm tự động 10 kịch bản T01–T10
│   ├── benchmark_alpha_grid.py            # Grid Search 1D cho α ∈ [1.00, 1.60] & stress test +25%/+50%
│   ├── NL_Parser_Package/                 # Gói Hybrid EN/VI NL Parser 6 tầng (tokenizer, regex, translator, schema, parser)
│   ├── member_eval/                       # 🎭 Chương trình Chấm Mù Human-in-the-Loop (blind_runner, aggregator, app, viewer)
│   ├── src/                               # Động cơ cốt lõi (TimeGrid, 6 Solvers V3 + ALNS, Buffer, OverloadTriage, NL Parser)
│   ├── web/                               # Giao diện Web Workbench Dual-Mode + health_v21.py (FastAPI/Tailwind/HTML5)
│   ├── data/                              # Dữ liệu tuần mẫu (Minh, Lan) & 10 kịch bản T01–T10
│   └── verification_tests/                # Hệ thống kiểm thử 167 pytest tests, 200 YAML NL cases & Test Studio
│
├── agents/                                # 🤖 AI AGENT & DEVELOPER KNOWLEDGE HUB (English)
│   ├── requirements.md                    # Môi trường, dependency và kiến trúc bất biến (INV-1..6)
│   ├── commit_changes.md                  # Nhật ký commit kỹ thuật và SHA-256 state tracking
│   └── progress/                          # Tài liệu kỹ thuật chuyên sâu (Architecture, Tests, Specs)
│
└── docs/                                  # 📘 TRUNG TÂM TÀI LIỆU TIẾNG VIỆT CHO NHÓM
    ├── requirements.md                    # Hướng dẫn thiết lập môi trường và cấu trúc thư mục
    ├── commit_changes.md                  # Lịch sử thay đổi hệ thống bằng tiếng Việt
    └── progress/                          # Hướng dẫn sử dụng trực quan, bộ đệm thời gian, giao diện
```

---

## 🌟 Điểm Nổi Bật & Tính Năng Cốt Lõi

1. **Mô hình hóa Lưới Rời Rạc 672 Slots (`1 slot = 15 phút`):**
   - Ánh xạ chính xác thời gian một tuần ($7 \text{ ngày} \times 24 \text{ giờ} \times 4 \text{ slots/giờ} = 672\text{ slots}$).
   - Đảm bảo tính tất định toán học (100% Determinism) — cùng dữ liệu đầu vào luôn cho ra lịch trình với mã băm `SHA-256` trùng khớp tuyệt đối.

2. **Bảo toàn 5 Ràng Buộc Cứng ($H_1 \dots H_5$):**
   - **$H_1$:** Tuyệt đối không đè lên lịch học trên lớp, ca làm việc cố định (`OCCUPIED`).
   - **$H_2$:** Khóa cứng và bảo vệ tối thiểu 6 giờ ngủ liên tục mỗi đêm (`SLEEP`).
   - **$H_3$:** Chỉ phân bổ vào các khe trống hợp lệ (`FREE`) với độ dài phiên học khoa học (45–90 phút).
   - **$H_4$:** Nghiêm ngặt hoàn thành trước hoặc đúng hạn chót (`end_slot <= deadline_slot`).
   - **$H_5$:** Tự động tuần tự hóa các nhiệm vụ có quan hệ phụ thuộc (`depends_on`).

3. **Giao Diện Dual-Mode, Bộ 6 Solvers V3 & Chẩn Đoán Sức Khỏe Lịch Trình `v2.1`:**
   - **Chế độ Sinh viên (Student Mode):** Trục thời gian 7/14 ngày `DD/MM/YYYY`, thanh kéo ngang + Lịch Tháng, ghim lịch cố định (`PINNED`), check-in thực tế (M7), pop-up giải thích (*"Tại sao ở đây?"*), và **4 Thẻ Sức Khỏe Năng Suất (`P1` Kịp hạn · `P2` Nhịp sinh học · `P3` Sức bền ngày · `P4` Chịu biến cố)** kèm Top 3 gợi ý `ICEE` tiếng Việt theo thời gian thực (`POST /api/evaluate`).
   - **Chế độ Thí nghiệm (Lab Mode):** Nạp nhanh `T01–T10`, chọn đủ **6 Thuật toán** (`SCORED_GREEDY` mặc định nhanh, `HYBRID_ALNS` tối ưu sâu V3, `BACKTRACK`, `WSPT`, `LST`, `EDF` V0 đối chứng), so sánh A/B kèm vector `v2.1`, và kiểm chứng SHA-256 3x cho cả 6 thuật toán.

4. **Chương Trình Chấm Mù Đa Thành Viên (`member_eval/` — Port `8010`):**
   - Ẩn danh ngẫu nhiên tất định (`#A/#B/#C`) đầu ra của các thuật toán trên tuần thật cá nhân, `6 Regimes` và `Fuzz v2` để thành viên/sinh viên chấm rời 5 chiều `UX-1..UX-5`, gắn nhãn lỗi trực tiếp lên từng block (`UX-6`), rồi mới mở khóa đối chiếu kết quả `Testing_System v2.1` và tổng hợp `Calibration_Report.md`.

5. **Bộ Phân Tích Ngôn Ngữ Tự Nhiên Hybrid EN/VI & UX Modal Hiện Đại:**
   - Kết hợp pipeline offline 6 tầng (`NL_Parser_Package/` + M1 `src/nl_parser.py`) và Live Gemini API hỗ trợ song ngữ EN/VI (`rule`, `nllb`), thang khẩn cấp `1=Khẩn..4=Thấp`, `WorkRhythm`, lưu nháp `localStorage`, SQLite persistence qua F5, và trích dẫn tệp `[[filename]]` / `@[path]`.

6. **Bộ Đệm Thời Gian & Xử Lý Quá Tải (`Q9` Phương án A):**
   - Tự động áp dụng bộ đệm `COGNITIVE_LOAD` (`1.20/1.35`, `RoundUp_15`) và `HABIT`, làm tròn 15 phút; Overload Triage sinh phương án `SKIP_HABIT`/`SHORTEN_TASK`/`MOVE_DEADLINE` kèm What-If Preview & Undo 1-click.

7. **Hệ Thống Kiểm Thử Toàn Diện (`167` App Tests + `39` Testing_System v2.1 Tests + `200` YAML Cases):**
   - `verification_tests/clean_runner.py --all`: **`167/167` PASSED** (bao gồm `T01–T10`, bất biến kiến trúc `INV-1..6`, bộ giải V3, `member_eval/`, và `P1` UI/API).
   - `pytest Testing_System/tests -v`: **`39/39` PASSED** (kiểm chứng `Checker v2.1` + `FuzzGenerator v2`).
   - Bộ **200 ca benchmark EN/VI** (`verification_tests/NL_Parser_test_cases/`, `200/200` trên engine `rule`) và giao diện **Test Studio**.

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy Nhanh

### 1. Yêu Cầu Tiên Quyết
- **Python:** Phiên bản 3.10 trở lên (đã kiểm thử trên Python 3.12).
- **Hệ điều hành:** Windows 10/11, macOS, hoặc Linux.

### 2. Cài Đặt Môi Trường
- **Cách 1 (Tự động tạo `.venv` trên Windows):** Chạy [`group03-smartschedule-baseline/setup_env.bat`](group03-smartschedule-baseline/setup_env.bat):
  ```powershell
  cd group03-smartschedule-baseline
  .\setup_env.bat
  ```
  > *Lưu ý:* `run_app.bat`, `run_verification_tests.bat` và `run_test_studio.bat` gọi `python` trực tiếp chưa tự activate `.venv`, nên nếu cài bằng `setup_env.bat` hãy kích hoạt `.venv\Scripts\Activate.ps1` (PowerShell) trước khi chạy `.bat` hoặc CLI.
- **Cách 2 (Cài thủ công vào venv hoặc Python hiện hành):**
  ```powershell
  cd group03-smartschedule-baseline
  pip install -r requirements.txt
  ```

### 3. Cấu Hình API Key Google Gemini (Cho M1 Hybrid NL Parser — Tùy Chọn)
Hệ thống vẫn chạy **100% offline** nếu không có key (chế độ `⚡ Offline` mặc định fallback tự động). Để bật AI Gemini cho ô **`✨ Nhập tự nhiên`** trong Student Modal:
1. Lấy API key miễn phí tại Google AI Studio (`https://aistudio.google.com/apikey`).
2. Tạo file `.env` trong `group03-smartschedule-baseline/` từ mẫu [`.env.example`](group03-smartschedule-baseline/.env.example):
   ```powershell
   cd group03-smartschedule-baseline
   Copy-Item .env.example .env
   ```
3. Dán key vào `group03-smartschedule-baseline/.env` (file `.gitignore` đã chặn `.env` để không bao giờ lộ key lên Git):
   ```dotenv
   GEMINI_API_KEY=AIzaSy...key_cua_ban...
   NL_PARSER_ENGINE=auto
   GEMINI_MODEL=gemini-3-flash-preview
   ```
   *(Xem thêm lưu ý chọn model và cách kiểm tra trên UI tại [`group03-smartschedule-baseline/README.md`](group03-smartschedule-baseline/README.md#bước-2-cách-lấy--cấu-hình-google-gemini-api-key-env-cho-m1-hybrid-nl-parser).)*

### 4. Khởi Chạy Giao Diện Web Workbench & Chương Trình Chấm Mù
- **Web App Chính (Student & Lab Modes — Port `8000`):**
  ```powershell
  cd group03-smartschedule-baseline
  python -B -m uvicorn web.api:app --host 127.0.0.1 --port 8000
  ```
  *(Hoặc nhấp đúp [`group03-smartschedule-baseline/run_app.bat`](group03-smartschedule-baseline/run_app.bat) → mở `http://127.0.0.1:8000`)*
- **Chương Trình Chấm Mù Đa Thành Viên (`member_eval` — Port `8010`):**
  ```powershell
  cd group03-smartschedule-baseline
  python -B -m uvicorn member_eval.app:app --host 127.0.0.1 --port 8010
  ```
  *(Hoặc nhấp đúp [`group03-smartschedule-baseline/run_member_eval.bat`](group03-smartschedule-baseline/run_member_eval.bat) → mở `http://127.0.0.1:8010`)*

### 5. Chạy Kiểm Thử Toàn Diện (Testing_System + Verification Tests)
- **Kiểm thử Máy Chấm `v2.1` & Bộ Sinh Đề `Fuzz v2` (`39/39` PASSED):**
  ```powershell
  $env:PYTHONIOENCODING = "utf-8"
  python -B -m pytest Testing_System/tests -v
  ```
- **Chạy đầy đủ toàn bộ `167` tests của App (`--all` — `167 Passed | 0 Failed`):**
  ```powershell
  cd group03-smartschedule-baseline
  python -B verification_tests/clean_runner.py --all
  ```
- **Kiểm tra 200 test case Hybrid EN/VI NL Parser:**
  ```powershell
  cd group03-smartschedule-baseline
  python -B verification_tests/NL_Parser_test_cases/validate_cases.py
  python -B verification_tests/NL_Parser_test_cases/verify_hybrid_200.py
  ```
- **Khởi chạy Test Studio trực quan:**
  ```powershell
  cd group03-smartschedule-baseline
  python verification_tests/test_studio.py
  ```
- **Chạy thực nghiệm Benchmark 10 kịch bản chuẩn (`T01–T10`) & Grid Search `α`:**
  ```powershell
  cd group03-smartschedule-baseline
  python benchmark_runner.py
  python benchmark_alpha_grid.py --save-json
  ```

---

## 📚 Tài Liệu Hướng Dẫn Chi Tiết

| Đối Tượng Đọc | Thư Mục Tài Liệu | Mô Tả Nội Dung |
| :--- | :--- | :--- |
| **Thành viên Nhóm** | [`docs/`](docs) | Hướng dẫn cài đặt tiếng Việt, giải thích trực quan về bộ đệm thời gian, hướng dẫn sử dụng giao diện sinh viên. |
| **AI Agents & Developers** | [`agents/`](agents) | Đặc tả kỹ thuật tiếng Anh chi tiết, ràng buộc bất biến kiến trúc (INV-1..6), nhật ký hash và quy chuẩn kiểm thử. |
| **Kỹ Sư Backend & Thuật Toán** | [`group03-smartschedule-baseline/README.md`](group03-smartschedule-baseline/README.md) | Sổ tay kỹ thuật chi tiết: Cấu trúc JSON Input/Output, REST API specs, phân tích 10 kịch bản thực nghiệm. |
| **Hội Đồng Đánh Giá Môn Học** | [`Proposal/`](Proposal) & [`Improve_Plan/`](Improve_Plan) | Báo cáo học thuật 45 trang, slide thuyết trình 53 trang, và bản đề xuất mở rộng thuật toán V1/V2. |

---

## 👥 Thành Viên Nhóm Thực Hiện

**Group 03 — *The Seven Dwarfs* (FIT-HCMUS — Khóa CS252):**
- **Đức Minh:** Kiến trúc hệ thống, Giao diện Chế độ Sinh viên (Student Mode UI & Dual-Mode Workbench).
- **Nguyễn Trọng Tiến:** Động cơ giải thuật, Bộ đệm thời gian Planning Fallacy (Feature 001).
- Cùng các thành viên Group 03 chịu trách nhiệm các phân hệ Kiểm thử, Tối ưu hóa Nhịp sinh học và Báo cáo.

---
*Dự án phục vụ học phần Tư duy Tính toán (CS252) — Khoa Công nghệ Thông tin, Đại học Khoa học Tự nhiên, ĐHQG-HCM.*
