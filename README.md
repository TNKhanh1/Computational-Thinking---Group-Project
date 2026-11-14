# ⚡ SmartSchedule — Trợ Lý Cá Nhân Tự Động Hóa Xếp Lịch Học Tập & Tối Ưu Năng Suất
### Personal Productivity Assistant for Automated Task & Timetable Scheduling

> **Môn học:** Tư duy Tính toán (CS252) — Khoa Công nghệ Thông tin, Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM (FIT-HCMUS)  
> **Nhóm thực hiện:** Group 03 (*The Seven Dwarfs*)  
> **Phiên bản:** Baseline System (V0) + Week 4 Extended Features (Dual-Mode UI, Planning Fallacy Buffer, Verification Test Studio)

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
├── Proposal/                              # Hồ sơ đề xuất dự án ban đầu
│   ├── Proposal_Report.pdf                # Báo cáo đề xuất hoàn chỉnh (45 trang)
│   ├── Presentation.pdf                   # Slide báo cáo đề xuất (53 trang)
│   └── Task_Assignment.md                 # Bảng phân công công việc thành viên
│
├── Baseline_Plan/                         # Đặc tả kỹ thuật hệ sinh thái Baseline (V0)
│   └── baseline_plan.md                   # Đặc tả toán học, 672 slots, 5 ràng buộc cứng H1-H5
│
├── Improve_Plan/                          # Kế hoạch cải tiến và mở rộng hệ thống
│   ├── improve_plan.md                    # Lộ trình nâng cấp thuật toán (V1/V2, nhịp sinh học, ML)
│   └── improve_plan_summary.pdf           # Bản tóm tắt cải tiến hệ thống
│
├── group03-smartschedule-baseline/         # ⭐ MÃ NGUỒN CHÍNH THỨC CỦA HỆ THỐNG
│   ├── README.md                          # Sổ tay kỹ thuật chi tiết hướng dẫn chạy & REST API
│   ├── requirements.txt                   # Danh sách thư viện Python phụ thuộc
│   ├── run_app.bat                        # File khởi chạy nhanh Web Workbench (1-click)
│   ├── run_tests.bat                      # File khởi chạy nhanh toàn bộ Test Suite (1-click)
│   ├── main.py                            # CLI Runner cho lập lịch nhanh
│   ├── benchmark_runner.py                # Runner thực nghiệm tự động 10 kịch bản T01–T10
│   ├── src/                               # Động cơ cốt lõi (TimeGrid, Solvers, Buffer, Metrics)
│   ├── web/                               # Giao diện Web Workbench Dual-Mode (HTML5/Tailwind/FastAPI)
│   ├── data/                              # Dữ liệu tuần mẫu (Minh, Lan) & 10 kịch bản T01–T10
│   └── verification_tests/                # Hệ thống kiểm thử chuyên sâu 89 tests & Test Studio
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

4. **Bộ Đệm Thời Gian Ngăn Ngừa Ảo Tưởng Lập Kế Hoạch (Planning Fallacy Buffer — Feature 001):**
   - Tự động áp dụng hệ số an toàn $1.25\times$ cho các tác vụ lớn, làm tròn số nguyên theo bước 15 phút.
   - Bảo toàn nguyên vẹn thời lượng các tác vụ ngắn $\le 15$ phút, chống lãng phí thời gian biểu.

5. **Hệ Thống Kiểm Thử 89 Tests & Test Studio:**
   - 84 bài kiểm thử vận hành đạt chuẩn (Pass 100%), bao phủ tính toàn vẹn kiến trúc, tính logic, và giao diện.
   - Giao diện **Test Studio** và công cụ **Interpretable Console Runner** xuất báo cáo trực quan cho từng commit.

---

## 🚀 Hướng Dẫn Cài Đặt & Khởi Chạy Nhanh

### 1. Yêu Cầu Tiên Quyết
- **Python:** Phiên bản 3.10 trở lên.
- **Hệ điều hành:** Windows 10/11, macOS, hoặc Linux.

### 2. Cài Đặt Môi Trường
Mở terminal tại thư mục gốc và di chuyển vào thư mục ứng dụng:
```powershell
cd group03-smartschedule-baseline
pip install -r requirements.txt
```

### 3. Khởi Chạy Giao Diện Web Workbench
- **Cách 1 (1-Click trên Windows):** Nhấp đúp vào file [`group03-smartschedule-baseline/run_app.bat`](group03-smartschedule-baseline/run_app.bat).
- **Cách 2 (Dòng lệnh):**
  ```powershell
  cd group03-smartschedule-baseline
  python -m uvicorn web.api:app --host 127.0.0.1 --port 8000
  ```
👉 Truy cập trình duyệt tại địa chỉ: **`http://127.0.0.1:8000`**

### 4. Chạy Kiểm Thử Toàn Diện (Verification Tests & Studio)
- **Chạy toàn bộ 84 bài kiểm thử vận hành:**
  ```powershell
  cd group03-smartschedule-baseline
  python verification_tests/clean_runner.py --pass
  ```
- **Kiểm tra các kịch bản đang mở rộng (Gap Analysis):**
  ```powershell
  cd group03-smartschedule-baseline
  python verification_tests/clean_runner.py --gaps
  ```
- **Khởi chạy Test Studio trực quan:**
  ```powershell
  cd group03-smartschedule-baseline
  python verification_tests/test_studio.py
  ```
- **Chạy thực nghiệm Benchmark 10 kịch bản chuẩn (T01–T10):**
  ```powershell
  cd group03-smartschedule-baseline
  python benchmark_runner.py
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
