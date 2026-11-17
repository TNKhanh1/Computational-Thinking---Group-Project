# ⚡ SmartSchedule — Trợ Lý Cá Nhân Tự Động Hóa Xếp Lịch Học Tập & Tối Ưu Năng Suất
### Personal Productivity Assistant for Automated Task & Timetable Scheduling

> **Môn học:** Tư duy Tính toán (CS252) — Khoa Công nghệ Thông tin, Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM (FIT-HCMUS)  
> **Nhóm thực hiện:** Group 03 (*The Seven Dwarfs*)  
> **Phiên bản:** Baseline System (V0) + Proposal & Presentation2 Sync (8 Behavioral Patterns, `SCORED_GREEDY`, Dual-Mode UI, Hybrid 6-Stage EN/VI NL Parser + Cross-Browser Modal UX, Overload Triage `Q9` Option A, 142 `pytest` Tests + 200 YAML NL Cases)

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
├── group03-smartschedule-baseline/         # ⭐ MÃ NGUỒN CHÍNH THỨC CỦA HỆ THỐNG
│   ├── README.md                          # Sổ tay kỹ thuật chi tiết hướng dẫn cài đặt, Gemini .env, chạy & REST API
│   ├── requirements.txt                   # Thư viện Python (FastAPI, Pydantic, Pytest, google-genai, PyYAML, CTranslate2...)
│   ├── .env.example                       # Mẫu cấu hình API Key Google Gemini (copy thành .env cục bộ, đã ignore trên Git)
│   ├── setup_env.bat                      # Script 1-click tạo .venv và cài thư viện trên Windows
│   ├── run_app.bat                        # File khởi chạy nhanh Web Workbench (1-click)
│   ├── main.py                            # CLI Runner cho lập lịch nhanh
│   ├── benchmark_runner.py                # Runner thực nghiệm tự động 10 kịch bản T01–T10
│   ├── benchmark_alpha_grid.py            # Grid Search 1D cho α ∈ [1.00, 1.60] & stress test +25%/+50%
│   ├── NL_Parser_Package/                 # Gói Hybrid EN/VI NL Parser 6 tầng (tokenizer, regex, translator, schema, parser)
│   ├── src/                               # Động cơ cốt lõi (TimeGrid, Solvers, Buffer, OverloadTriage, NL Parser, Metrics)
│   ├── web/                               # Giao diện Web Workbench Dual-Mode (HTML5/Tailwind/FastAPI + Drag-Drop Citations)
│   ├── data/                              # Dữ liệu tuần mẫu (Minh, Lan) & 10 kịch bản T01–T10
│   └── verification_tests/                # Hệ thống kiểm thử 142 pytest tests, 200 YAML NL cases & Test Studio
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

3. **Giao Diện Dual-Mode Đột Phá (Web Workbench):**
   - **Chế độ Sinh viên (Student Mode):** Thiết kế thân thiện, hỗ trợ 3 góc nhìn (Ngày / 3 Ngày / Tuần), tính năng thu gọn khung giờ ngủ, ghim lịch cố định (📌 Pinning), đánh dấu hoàn thành (✔️ Check-in), và pop-up giải thích vị trí xếp lịch (*"Tại sao ở đây? 💡"*).
   - **Chế độ Thí nghiệm (Lab Mode):** Dành cho nghiên cứu và kiểm thử thuật toán, nạp nhanh 10 kịch bản benchmark `T01–T10`, so sánh solver (EDF vs. LLF vs. Energy-First), và xem JSON I/O trực tiếp.

4. **Bộ Phân Tích Ngôn Ngữ Tự Nhiên Hybrid EN/VI & UX Modal Hiện Đại:**
   - Kết hợp pipeline offline 6 tầng (`NL_Parser_Package/` + M1 `src/nl_parser.py`) hỗ trợ song ngữ EN/VI (`rule`, `nllb`, `opus_mt`), thang khẩn cấp `1=Khẩn..4=Thấp` tự động ánh xạ Solver `5..1`, và `WorkRhythm` (Pomodoro / Balanced / Deep Focus).
   - Modal Thêm Công Việc (`#stTaskModal`) hỗ trợ **tự động lưu nháp (`localStorage`)**, chọn **cắt nhỏ / làm liền 1 buổi** ngay trong vùng nhập tự nhiên, nhập/chọn **`Task ID` phụ thuộc**, **kéo-thả tệp an toàn trên Edge/Chrome/Firefox/Safari**, và đối chiếu **trích dẫn không mất dữ liệu `[[filename]]` / `@[path]`** với cảnh báo đỏ khi sai định dạng hoặc thiếu tệp đính kèm.

5. **Bộ Đệm Thời Gian & Xử Lý Quá Tải (`Q9` Phương án A):**
   - Tự động áp dụng hệ số an toàn $1.25\times$ cho các tác vụ lớn, làm tròn số nguyên theo bước 15 phút và bảo toàn tác vụ ngắn $\le 15$ phút.
   - Chế độ Sprint Mode áp dụng **Phương án A (`Q9`)**: phát hiện quá tải không mất dữ liệu (`INFEASIBLE_CAPACITY`), bật cảnh báo gia hạn sớm (`Early Extension Alert`), và giải cứu có xác nhận qua `SHORTEN_TASK` / Tier-1 `Cut breaks`.

6. **Hệ Thống Kiểm Thử 142 `pytest` Tests + 200 Ca YAML Hybrid NL:**
   - `136` bài kiểm thử vận hành (`--pass`, 100% đạt) + `5/5` bài kiểm thử Improve Plan (`--gaps`, 100% đạt) + `1` bài kiểm thử `Q9` Sprint Mode Option A (`--all`: **`142/142` xanh 100%**).
   - Kèm bộ **200 ca benchmark EN/VI** (`verification_tests/NL_Parser_test_cases/`, đạt `200/200` / `100.0%` trên engine `rule`) và giao diện **Test Studio**.

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

### 4. Khởi Chạy Giao Diện Web Workbench
- **Cách 1 (1-Click trên Windows — khi dùng Python global hoặc đã activate `.venv`):** Nhấp đúp vào file [`group03-smartschedule-baseline/run_app.bat`](group03-smartschedule-baseline/run_app.bat).
- **Cách 2 (Dòng lệnh):**
  ```powershell
  cd group03-smartschedule-baseline
  python -m uvicorn web.api:app --host 127.0.0.1 --port 8000
  ```
👉 Truy cập trình duyệt tại địa chỉ: **`http://127.0.0.1:8000`**

### 5. Chạy Kiểm Thử Toàn Diện (Verification Tests & Studio)
- **Chạy toàn bộ 136 bài kiểm thử vận hành (`--pass`):**
  ```powershell
  cd group03-smartschedule-baseline
  python -B verification_tests/clean_runner.py --pass
  ```
- **Kiểm tra 5 bài mục tiêu Improve Plan (`--gaps`):**
  ```powershell
  cd group03-smartschedule-baseline
  python -B verification_tests/clean_runner.py --gaps
  ```
- **Chạy đầy đủ cả 142 tests (`--all` — `142 Passed | 0 Failed`, gồm ca `Q9` Option A):**
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
