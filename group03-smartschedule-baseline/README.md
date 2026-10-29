# ⚡ SmartSchedule Baseline (V0) — Hệ Thống Tự Động Xếp Lịch Học Tập & Công Việc Cá Nhân

**Môn học:** Tư duy Tính toán (CSC10014) — Khoa Công nghệ Thông tin, Trường ĐH Khoa học Tự nhiên, ĐHQG-HCM (FIT-HCMUS)  
**Nhóm thực hiện:** Group 03 (*The Seven Dwarfs*)  
**Phiên bản:** **Baseline System (V0)** — Hệ thống Tham chiếu Tất định trên Lưới Thời gian Rời rạc 672 Slots

---

## 📌 Mục Lục
1. [Tổng Quan & Triết Lý Thiết Kế Baseline (V0)](#1-tổng-quan--triết-lý-thiết-kế-baseline-v0)
2. [Cấu Trúc Thư Mục Dự Án](#2-cấu-trúc-thư-mục-dự-án)
3. [Hướng Dẫn Cài Đặt & Khởi Chạy Nhanh (3 Cách)](#3-hướng-dẫn-cài-đặt--khởi-chạy-nhanh-3-cách)
4. [Hướng Dẫn Chi Tiết Về Dữ Liệu Đầu Vào (INPUT)](#4-hướng-dẫn-chi-tiết-về-dữ-liệu-đầu-vào-input)
5. [Hướng Dẫn Chi Tiết Về Kết Quả Đầu Ra (OUTPUT) & Cách Đọc Thông Số](#5-hướng-dẫn-chi-tiết-về-kết-quả-đầu-ra-output--cách-đọc-thông-số)
6. [Hướng Dẫn Sử Dụng Giao Diện Web Workbench Từng Bước](#6-hướng-dẫn-sử-dụng-giao-diện-web-workbench-từng-bước)
7. [Danh Sách 10 Kịch Bản Kiểm Thử Chuẩn (T01 – T10)](#7-danh-sách-10-kịch-bản-kiểm-thử-chuẩn-t01--t10)
8. [Giải Thích Chi Tiết: Khi Chạy Kiểm Thử (Test) Thì Hệ Thống Làm Gì Bên Dưới?](#8-giải-thích-chi-tiết-khi-chạy-kiểm-thử-test-thì-hệ-thống-làm-gì-bên-dưới)
9. [Tài Liệu REST API Endpoints](#9-tài-liệu-rest-api-endpoints)

---

## 1. Tổng Quan & Triết Lý Thiết Kế Baseline (V0)

**SmartSchedule Baseline (V0)** là hệ thống lập lịch tự động giải quyết bài toán phân bổ các công việc học tập (`tasks`) vào các khoảng thời gian trống trong tuần của sinh viên sao cho **không bao giờ vi phạm bất kỳ ràng buộc cứng nào** ($C_{\text{hard}} = 0$) và **tối đa hóa tỷ lệ hoàn thành đúng hạn chót** ($R_{\text{deadline}}$).

### 3 Nguyên Tắc Cốt Lõi Của Bản Baseline (V0):
1. **Rời rạc hóa thời gian 672 Slots (`1 slot = 15 phút`):**
   - 1 tuần = $7 \text{ ngày} \times 24 \text{ giờ} \times 4 \text{ slots/giờ} = \mathbf{672\text{ slots}}$ (đánh số từ `0` đến `671`).
   - Công thức ánh xạ tọa độ thời gian sang chỉ số mảng 1 chiều:
     $$\text{Slot Index} = \text{day} \times 96 + \text{hour} \times 4 + \lfloor \text{minute} / 15 \rfloor$$
     *(Trong đó `day = 0` là Thứ Hai, ..., `day = 6` là Chủ Nhật. Hỗ trợ mở rộng tự động lên `1,344 slots` cho các hạn chót sang tuần kế tiếp như kịch bản `T10`).*
2. **Bảo toàn tuyệt đối 5 Ràng buộc cứng ($H_1 \dots H_5$):**
   - **$H_1$ (Không đè lịch cố định):** Không xếp việc trùng vào giờ học trên trường, giờ làm thêm, giờ ăn uống (`OCCUPIED`).
   - **$H_2$ (Bảo vệ giấc ngủ sinh học):** Khóa cứng khung giờ ngủ đêm (mặc định `23:30 – 06:30`, tương ứng `196 slots/tuần` ở trạng thái `SLEEP`).
   - **$H_3$ (Chỉ đặt vào khe trống hợp lệ & giới hạn độ dài phiên):** Chỉ đặt vào các slot `FREE` liên tiếp; các tác vụ lớn có `is_splittable = true` được cắt thành các phiên học từ `45` đến `90` phút.
   - **$H_4$ (Tuân thủ hạn chót nghiêm ngặt):** Mọi phiên học phải kết thúc trước hoặc ngay tại thời điểm hạn chót (`end_slot <= deadline_slot`).
   - **$H_5$ (Thứ tự phụ thuộc `depends_on`):** Nếu công việc B phụ thuộc công việc A (`depends_on: ["A"]`), toàn bộ các phiên của A phải hoàn tất trước khi phiên đầu tiên của B bắt đầu.
3. **Tính tất định toán học 100% (Pure Determinism):**
   - Cùng một bộ dữ liệu đầu vào (`commitments` + `tasks`), chạy 3 lần hay 100 lần đều cho ra **cùng một lịch trình duy nhất** với mã băm kiểm chứng `SHA-256` giống hệt nhau 100%.

---

## 2. Cấu Trúc Thư Mục Dự Án

```text
group03-smartschedule-baseline/
├── README.md                              # Tài liệu hướng dẫn toàn diện (file này)
├── requirements.txt                       # Danh sách thư viện Python cần thiết
├── main.py                                # Công cụ chạy bằng dòng lệnh (CLI Runner)
├── benchmark_runner.py                    # Script chạy thực nghiệm tự động 10 kịch bản T01–T10
├── run_app.bat                            # File chạy nhanh Web Workbench trên Windows (1-click)
├── run_tests.bat                          # File chạy nhanh bộ kiểm thử Pytest + Benchmark (1-click)
│
├── data/                                  # Dữ liệu mẫu & 10 kịch bản kiểm thử chuẩn
│   ├── sample_week_commitments.json       # Lịch cố định & giờ ngủ chuẩn: Tuần của Minh (672 slots)
│   ├── sample_week_tasks.json             # 9 công việc mẫu trong tuần của Minh
│   ├── lan_week_commitments.json          # Lịch cố định mẫu: Tuần bận rộn của Lan
│   ├── lan_week_tasks.json                # Danh sách công việc tuần của Lan
│   └── test_scenarios/                    # 10 kịch bản kiểm thử chuẩn từ T01 đến T10
│       ├── t01_normal_feasible.json
│       ├── t02_overlapping_deadlines.json
│       ├── t03_large_unsplittable.json
│       ├── t04_event_disruption.json
│       ├── t05_duration_overrun.json
│       ├── t06_overload_capacity.json
│       ├── t07_incomplete_metadata.json
│       ├── t08_unclear_priority.json
│       ├── t09_circadian_comparison.json
│       └── t10_cross_week_deadline.json
│
├── src/                                   # Mã nguồn lõi (Core Scheduling Engine)
│   ├── utils.py                           # Chuyển đổi tọa độ 672-slot, Thứ/Giờ và ISO-8601
│   ├── models.py                          # Schema dữ liệu đầu vào / đầu ra (Pydantic v2)
│   ├── grid_manager.py                    # Quản lý lưới 672 slots & kiểm tra ràng buộc cứng H1–H5
│   ├── metrics.py                         # Tính toán KPI (C_hard, R_deadline, S_stability, FragIndex, SHA-256)
│   ├── exporter.py                        # Xuất lịch sang chuẩn .json, .csv và .ics (Google/Apple Calendar)
│   ├── controller.py                      # Bộ điều phối trung tâm (ScheduleController)
│   └── solvers/                           # Các thuật toán xếp lịch và tái lập lịch
│       ├── base_solver.py                 # Cắt nhỏ tác vụ (Chunking), sắp xếp Topo, chẩn đoán quá tải
│       ├── greedy_edf.py                  # 1. Tham lam Earliest Deadline First (EDF + First-Fit) [Chuẩn V0]
│       ├── greedy_lst.py                  # 2. Tham lam Least Slack Time (LST + Best-Fit)
│       ├── greedy_wspt.py                 # 3. Tham lam Weighted Shortest Processing Time (WSPT - Luật Smith)
│       ├── backtracking.py                # 4. Vét cạn Quay lui Nhánh-Cận (Backtracking Ground-Truth)
│       └── local_repair.py                # Động cơ Vá lịch cục bộ (Local Insertion) vs Xếp lại toàn bộ (Rebuild)
│
├── web/                                   # Giao diện Web Bàn Thử Nghiệm Kỹ Thuật (2-Column Workbench)
│   ├── api.py                             # FastAPI Backend Server
│   ├── index.html                         # Giao diện chính (Tailwind CSS + Bảng lưới 672 slots)
│   └── app.js                             # Logic tương tác Frontend
│
└── tests/                                 # Bộ kiểm thử tự động (Pytest Suite - 15 bài test)
    ├── test_time_grid.py                  # Kiểm thử toán học lưới 672 slots (196 SLEEP + 132 OCCUPIED + 344 FREE)
    ├── test_constraints.py                # Kiểm thử ràng buộc cứng H1–H5 & chặn thao tác kéo thả sai
    ├── test_edf_solver.py                 # Kiểm thử tính tất định 3x SHA-256 & độ ổn định Local Repair
    └── test_scenarios_t01_t10.py          # Kiểm thử tích hợp toàn bộ T01–T10 & REST API
```

---

## 3. Hướng Dẫn Cài Đặt & Khởi Chạy Nhanh (3 Cách)

### Bước 0: Cài đặt thư viện (Chỉ cần chạy 1 lần đầu)
Mở Terminal / PowerShell và di chuyển vào thư mục `group03-smartschedule-baseline`:
```powershell
cd d:\Git\test\Computational_Thinking\Computational-Thinking---Group-Project\group03-smartschedule-baseline
pip install -r requirements.txt
```

---

### Cách 1: Chạy Giao Diện Web Trực Quan (Khuyên dùng để Demo & Thử nghiệm)
Bạn có thể nhấp đúp chuột vào file **`run_app.bat`** hoặc chạy lệnh sau trong Terminal:
```powershell
python -m uvicorn web.api:app --host 127.0.0.1 --port 8000
```
👉 Sau đó mở trình duyệt web tại địa chỉ: **`http://127.0.0.1:8000`**

---

### Cách 2: Chạy Bằng Dòng Lệnh (CLI — `main.py`)
Dành cho việc kiểm tra nhanh trên Terminal hoặc xuất thẳng ra file `.json`, `.csv`, `.ics`:

```powershell
# 1. Giải lịch "Tuần của Minh" bằng thuật toán chuẩn EDF và kiểm chứng tất định 3 lần (3x SHA-256)
python main.py --preset minh --solver EDF --check-determinism

# 2. Giải lịch "Tuần bận rộn của Lan" bằng thuật toán Least Slack Time (LST + Best-Fit)
python main.py --preset lan --solver LST

# 3. Khởi tạo "Lịch Trống Hoàn Toàn" (0 Lịch bận cố định, 0 Task — chỉ khóa 196 slots ngủ, còn 476 slots FREE)
python main.py --preset empty

# 4. Chạy thử một kịch bản bất kỳ trong bộ T01..T10 (Ví dụ: T06 - Quá tải dung lượng)
python main.py --scenario T06

# 5. Giải lịch và xuất đồng thời ra cả 3 định dạng (.json, .csv, .ics)
python main.py --preset minh --export-json out_schedule.json --export-csv out_schedule.csv --export-ics out_schedule.ics
```

**Các tham số dòng lệnh của `main.py`:**
- `--preset {minh,lan,empty}`: Chọn bộ dữ liệu khởi tạo:
  - `minh` *(mặc định)*: Tuần chuẩn của Minh (9 tasks, `196 SLEEP + 132 OCCUPIED + 344 FREE = 672 slots`).
  - `lan`: Tuần bận rộn của Lan (học + làm thêm + CLB + bài tập sang tuần sau).
  - `empty`: Lịch trống hoàn toàn (`0` sự kiện cố định, `0` task, chỉ khóa giờ ngủ `23:30–06:30`).
- `--scenario T01..T10`: Chạy trực tiếp 1 trong 10 kịch bản test chuẩn (`T01`, `T02`, ..., `T10`).
- `--solver {EDF,LST,WSPT,BACKTRACK}`: Chọn thuật toán giải.
- `--check-determinism`: Chạy thuật toán 3 lần liên tiếp và kiểm tra mã băm `SHA-256`.
- `--export-json <đường_dẫn>`, `--export-csv <đường_dẫn>`, `--export-ics <đường_dẫn>`: Xuất kết quả ra tệp.

---

### Cách 3: Chạy Bộ Kiểm Thử Tự Động & Thực Nghiệm (`pytest` & `benchmark_runner.py`)
Bạn có thể nhấp đúp vào **`run_tests.bat`** hoặc chạy:
```powershell
# Chạy 15 bài kiểm thử đơn vị & tích hợp (Unit & E2E Tests)
python -m pytest -v

# Chạy báo cáo thực nghiệm tổng hợp (T01–T10, So sánh 4 thuật toán, Local Repair vs Rebuild, Test tải 10-25-50 tasks)
python benchmark_runner.py
```

---

## 4. Hướng Dẫn Chi Tiết Về Dữ Liệu Đầu Vào (INPUT)

Hệ thống nhận **2 nguồn dữ liệu đầu vào chính**:
1. **Hồ sơ Lịch cố định & Giấc ngủ (`commitments.json`)**
2. **Danh sách Công việc cần xếp lịch (`tasks.json`)**

Ngoài ra, bạn có thể nhập liệu trực tiếp trên giao diện Web thông qua **Biểu mẫu (Form)**, **Thanh gõ tắt (Quick-Add Regex)**, hoặc bấm nút **📥 Nhập JSON**.

### 4.1. Cấu trúc File Lịch Cố Định & Giấc Ngủ (`commitments.json`)
Xem ví dụ mẫu tại [`data/sample_week_commitments.json`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/group03-smartschedule-baseline/data/sample_week_commitments.json):

```json
{
  "student_id": "MINH_FIT_HCMUS",
  "planning_week_start": "2026-11-02T00:00:00+07:00",
  "sleep_schedule": {
    "daily_start_time": "23:30",
    "daily_end_time": "06:30",
    "is_hard_lock": true
  },
  "fixed_events": [
    {
      "event_id": "LUNCH_DAILY",
      "title": "Nghỉ trưa & Ăn trưa",
      "day_of_week": "ALL",
      "start_time": "11:30",
      "end_time": "12:45",
      "category": "MEAL"
    },
    {
      "event_id": "CLASS_MON_AFT",
      "title": "Học trên lớp chiều Thứ Hai",
      "day_of_week": "Monday",
      "start_time": "13:00",
      "end_time": "17:00",
      "category": "ACADEMIC_CLASS"
    }
  ]
}
```

**Ý nghĩa các trường trong `commitments.json`:**
| Trường (Field) | Kiểu dữ liệu | Ý nghĩa & Quy tắc sử dụng |
| :--- | :---: | :--- |
| `student_id` | `string` | Mã định danh sinh viên hoặc tên hồ sơ lịch. |
| `planning_week_start` | `string` | Ngày bắt đầu tuần lập lịch (Thứ Hai lúc `00:00:00+07:00` chuẩn ISO-8601). |
| `now` *(Tùy chọn)* | `string` | Thời điểm hiện tại (VD `"2026-11-02T06:30:00+07:00"`). Thuật toán sẽ không đặt task vào quá khứ trước thời điểm `now`. |
| `sleep_schedule.daily_start_time` | `string` | Giờ bắt đầu đi ngủ mỗi đêm (`HH:MM`, VD `"23:30"`). |
| `sleep_schedule.daily_end_time` | `string` | Giờ thức dậy mỗi sáng (`HH:MM`, VD `"06:30"`). |
| `fixed_events[].day_of_week` | `string` hoặc `list` | Nhận `"ALL"` (mỗi ngày), tên thứ tiếng Anh (`"Monday"`..`"Sunday"`), viết tắt (`"Mon"`, `"T2"`..`"CN"`), hoặc mảng nhiều thứ `["Monday", "Wednesday"]`. |
| `fixed_events[].start_time`, `end_time` | `string` | Giờ bắt đầu và kết thúc sự kiện cố định (`HH:MM`, bội số của 15 phút). |
| `fixed_events[].category` | `string` | Phân loại để tô màu trên lưới: `"ACADEMIC_CLASS"` (Đỏ hồng), `"MEAL"` (Vàng cam), `"WORK"`, `"MEETING"`. |

---

### 4.2. Cấu trúc File Danh Sách Công Việc (`tasks.json`)
Xem ví dụ mẫu tại [`data/sample_week_tasks.json`](file:///d:/Git/test/Computational_Thinking/Computational-Thinking---Group-Project/group03-smartschedule-baseline/data/sample_week_tasks.json):

```json
[
  {
    "task_id": "MATH-1",
    "title": "Ôn tập Quiz Toán giữa kỳ",
    "duration_min": 120,
    "deadline_day": "Wednesday",
    "deadline_time": "13:00",
    "priority": 5,
    "category": "EXAM",
    "is_splittable": true,
    "min_chunk_min": 45,
    "max_chunk_min": 90,
    "depends_on": []
  },
  {
    "task_id": "PRJ-2",
    "title": "Đồ án: Lập trình tính năng B",
    "duration_min": 120,
    "deadline_day": "Thursday",
    "deadline_time": "21:00",
    "priority": 4,
    "category": "PROJECT",
    "is_splittable": true,
    "min_chunk_min": 45,
    "max_chunk_min": 90,
    "depends_on": ["PRJ-1"]
  }
]
```

**Ý nghĩa các trường trong `tasks.json`:**
| Trường (Field) | Kiểu dữ liệu | Ý nghĩa & Quy tắc sử dụng |
| :--- | :---: | :--- |
| `task_id` (hoặc `id`) | `string` | Mã công việc duy nhất (VD `"MATH-1"`, `"PRJ-1"`). Dùng để tham chiếu trong `depends_on`. |
| `title` | `string` | Tên công việc hiển thị trên lưới lịch và bảng kê. |
| `duration_min` (hoặc `estimate_min`) | `int` | Thời lượng ước tính tính bằng **phút** (hệ thống tự động làm tròn lên bội số 15 phút gần nhất, không tự ý nhân hệ số đệm ở bản V0). |
| `deadline_day` | `string` / `null` | Thứ hạn chót: `"Monday"`..`"Sunday"`, hoặc `"Next Monday"`..`"Next Sunday"` (cho tuần sau), hoặc `null` / `""` nếu là việc linh hoạt không có hạn chót (`HABIT`). |
| `deadline_time` | `string` | Giờ hạn chót (`"HH:MM"`, mặc định `"23:59"`). |
| `due` *(Tùy chọn)* | `string` | Chuỗi hạn chót chuẩn ISO-8601 (VD `"2026-11-04T13:00:00+07:00"` — tương thích với Improve Plan §7). |
| `priority` | `int` (`1..5`) | Độ ưu tiên từ `1` (Thấp nhất) đến `5` (Cao nhất / Quan trọng nhất). Nếu truyền `grade_weight` (`"30+"`, `"20-29"`, `"10-19"`, `"<10"`), hệ thống tự quy đổi sang `priority`. |
| `is_splittable` (hoặc `splittable`) | `bool` | `true`: Cho phép cắt nhỏ tác vụ dài thành nhiều phiên học (`45–90` phút). `false`: Bắt buộc xếp nguyên 1 khối liên tục không ngắt quãng. |
| `min_chunk_min` | `int` | Thời lượng tối thiểu của 1 phiên sau khi cắt (mặc định `45` phút). |
| `depends_on` (hoặc `after`) | `list[str]` | Danh sách mã `task_id` tiên quyết phải hoàn thành xong trước khi công việc này được phép bắt đầu. |

---

### 4.3. Cú Pháp Nhập Nhanh Bằng Dòng Text (`Quick-Add Regex`) trên Web
Tại ô **"⚡ Nhập Nhanh Cú Pháp Rút Gọn"** ở cột bên trái giao diện Web, bạn có thể gõ nhanh 1 dòng văn bản tự nhiên, hệ thống sẽ tự động bóc tách thành các thẻ thông số:
- **Cú pháp mẫu:** `<Tên bài tập> <Thời lượng: 120m hoặc 2h> <Thứ hạn chót: t2..t7, cn, mon..sun> <Giờ hạn chót: HH:MM> <Ưu tiên: p1..p5> <Cắt nhỏ: ~45> <Phụ thuộc: after: MÃ_TASK>`
- **Ví dụ thực tế:**
  - `On tap Toan 120m t4 13:00 p5 ~45` ➔ Tạo task *"On tap Toan"*, thời lượng `120 phút`, hạn chót `Wednesday 13:00`, ưu tiên `5`, cho phép cắt nhỏ tối thiểu `45 phút`.
  - `Code tinh nang B 2h thu 5 21:00 p4 after:PRJ-1` ➔ Tạo task `120 phút`, hạn `Thursday 21:00`, ưu tiên `4`, chỉ bắt đầu sau khi `PRJ-1` hoàn tất.

---

### 4.4. So Sánh Chi Tiết Giữa "Mẫu Của Minh" và "Mẫu Của Lan" (Tại Sao Cần Cả 2 Mẫu Để Đối Chứng?)

Hai bộ dữ liệu mẫu **`minh`** và **`lan`** không phải là 2 bộ dữ liệu ngẫu nhiên, mà đại diện cho **2 hình mẫu sinh viên (Personas) và 2 giai đoạn thiết kế của nhóm**:

| Tiêu chí so sánh | 📂 Mẫu 1: Tuần Của Minh (`--preset minh`) | 📂 Mẫu 2: Tuần Của Lan (`--preset lan`) |
| :--- | :--- | :--- |
| **1. Nguồn gốc tài liệu** | Trích xuất nguyên bản 100% từ **`Proposal_Report.pdf` (§2.8, §5.5, §6.7)** và **`baseline_plan.md` (§2, §6.1)**. | Trích xuất từ **`improve_plan.md` (§6.1, §7.3)** — bộ dữ liệu chuẩn của giai đoạn nâng cấp. |
| **2. Chân dung sinh viên (Persona)** | Sinh viên CNTT năm 2 điển hình: Chỉ có lịch học trên trường + ăn trưa/tối cố định, buổi tối rảnh để tự học và làm đồ án. | Sinh viên cực kỳ bận rộn: Vừa học lý thuyết (T2/T4/T6), học Lab (T3/T5), vừa **đi làm thêm Part-time 3 buổi tối (T3/T5/T7 từ 18:00–22:00)** và **sinh hoạt CLB tối T4**. |
| **3. Phân bổ 672 Slots ban đầu** | • `SLEEP`: **196 slots** (`2,940p`)<br>• `OCCUPIED`: **132 slots** (`1,980p` — 33 giờ)<br>• `FREE` ban đầu: **344 slots** (`5,160p` — 86 giờ) | • `SLEEP`: **196 slots** (`2,940p`)<br>• `OCCUPIED`: **155 slots** (`2,325p` — 38.75 giờ, **bận hơn Minh 23 slots = 345p**)<br>• `FREE` ban đầu: **321 slots** (`4,815p`) |
| **4. Đặc trưng danh sách Task** | • **9 tasks** (tổng **855 phút** = **57 slots**, chia thành **14 phiên học**).<br>• Có **chuỗi phụ thuộc 5 mắt xích liên hoàn**: `PRJ-1` $\rightarrow$ `PRJ-2` $\rightarrow$ `PRJ-3` $\rightarrow$ `PRJ-4` $\rightarrow$ `PRJ-5`.<br>• Có **2 việc vặt không có hạn chót (`deadline = null`)**: Dọn phòng (`CLEAN`) & Giặt đồ (`LAUNDRY`). | • **5 tasks** (tổng **330 phút** = **22 slots**, giữ nguyên **5 phiên học**).<br>• Có các task **nguyên khối không cho cắt nhỏ (`is_splittable = false`)** dài tới 90p (`DSA-CODE`).<br>• Có bài tập **hạn chót vắt sang tuần kế tiếp (`Next Monday 09:00` — Cross-week `CALC-1`)**. |
| **5. Chuẩn Schema kiểm thử** | Kiểm thử chuẩn Schema Baseline §6 (`deadline_day`, `deadline_time`, `priority` trực tiếp). | Kiểm thử chuẩn Schema mở rộng của Improve Plan §7 (`due` ISO-8601, quy đổi tự động `grade_weight: "30+"` $\rightarrow$ `P5`, `cognitive_load`). |
| **6. Ý nghĩa khi đem ra Demo / So sánh** | Dùng để **kiểm chứng số liệu toán học gốc trong Báo cáo Proposal** (`196 + 132 + 344 = 672`), kiểm tra khả năng cắt nhỏ tác vụ lớn (Chunking) và giải chuỗi phụ thuộc Topo dài ($H_5$). | Dùng để **kiểm chứng sinh viên đi làm thêm bị khóa kín buổi tối**, cách thuật toán tìm khe trống ban ngày cho các task nguyên khối (`is_splittable=false`) và xử lý hạn chót tuần kế tiếp (`Next Monday`). |

---

## 5. Hướng Dẫn Chi Tiết Về Kết Quả Đầu Ra (OUTPUT) & Cách Đọc Thông Số

Sau khi bấm nút **"🚀 CHẠY THUẬT TOÁN XẾP LỊCH (SOLVE)"** (hoặc chạy `main.py` / gọi API `/api/plan`), hệ thống trả về cấu trúc JSON `ScheduleOutput` và hiển thị trực quan trên màn hình gồm **4 phần chính**:

### 5.1. Cách Đọc 5 Thẻ Chỉ Số Đo Lường (Benchmark KPI Cards)
Ở phía trên cùng bên phải màn hình là 5 thẻ KPI định lượng:
1. **Vi Phạm Cứng (H1–H5) (`hard_constraint_violations`):**
   - **Ý nghĩa:** Số lượng slot bị xếp đè lên giờ ngủ (`SLEEP`), đè lên lịch học cố định (`OCCUPIED`), trễ hạn chót, hoặc sai thứ tự phụ thuộc.
   - **Cách đọc:** Con số này **BẮT BUỘC LUÔN BẰNG `0`** (màu xanh lá). Nếu một công việc không thể xếp được mà không vi phạm ràng buộc cứng, hệ thống sẽ từ chối xếp và đưa vào danh sách `UNPLACED` chứ tuyệt đối không bao giờ ăn lẹm vào giờ ngủ hay giờ lên lớp.
2. **Đạt Hạn Chót (`deadline_satisfaction_rate`):**
   - **Ý nghĩa:** Phần trăm công việc được xếp hoàn tất trước hạn chót:
     $$R_{\text{deadline}} = \frac{\text{Số công việc được xếp thành công}}{\text{Tổng số công việc yêu cầu}} \times 100\%$$
   - **Cách đọc:** `100.0%` nghĩa là toàn bộ bài tập trong tuần đều được giải quyết trọn vẹn trước hạn. Nếu `< 100%`, sẽ có bảng **Cảnh báo Quá tải** màu đỏ xuất hiện ngay bên dưới để giải thích lý do toán học.
3. **Thời Gian Giải Thực Đo (`execution_time_ms`):**
   - **Ý nghĩa:** Thời gian CPU thực tế để thuật toán chạy xong (tính bằng mili-giây `ms`).
   - **Cách đọc:** Các thuật toán Tham lam (`EDF`, `LST`, `WSPT`) thường giải xong chỉ trong **`0.5 ms – 6.0 ms`** (nhanh hơn rất nhiều so với ngưỡng mục tiêu `< 2000 ms`).
4. **Slot Trống Còn Lại & Độ Phân Mảnh (`free_slots_remaining` & `fragmentation_index`):**
   - **Ý nghĩa:**
     - Cho biết trong tổng số `672 slots` của tuần còn bao nhiêu slot rảnh (`FREE`) sau khi đã trừ đi giờ ngủ (`196 slots`), lịch cố định (`132 slots`) và các bài tập vừa xếp.
     - **Độ phân mảnh (`Phân mảnh: X%`):** Tỷ lệ các khe thời gian trống bị vụn vặt (ngắn dưới 45 phút = 3 slots, khó tận dụng để học sâu) so với tổng thời gian trống. Chỉ số này càng thấp thì lịch học càng liền mạch.
5. **Mã Tất Định SHA-256 (`determinism_hash`):**
   - **Ý nghĩa:** Chữ ký băm mật mã học được tính từ toàn bộ tọa độ các phiên học đã xếp.
   - **Cách đọc:** Khi bấm nút **"🔒 Kiểm Chứng Tất Định (3x)"**, hệ thống chạy lại thuật toán 3 lần độc lập. Nếu cả 3 lần đều sinh ra đúng một mã `SHA-256` (VD `4a66f4e24c5251fa`), hệ thống xác nhận **`100% IDENTICAL PASS`**.

---

### 5.2. Cách Đọc Lưới Thời Gian 672 Slots & Thanh Giải Thích Thuật Toán ("Why Here?")
- **Ý nghĩa màu sắc trên lưới 7 ngày:**
  - ⬛ **Màu Xám Đậm sọc chéo (`SLEEP`):** Khung giờ ngủ bảo vệ cứng (`23:30 – 06:30`). Có thể bật/tắt nút **"🌙 Thu gọn ngủ đêm (00:00–06:30)"** để bảng gọn dễ nhìn hơn.
  - 🟥 **Màu Đỏ Hồng (`OCCUPIED - CLASS`):** Giờ học cố định trên trường, giờ làm thêm, họp CLB.
  - 🟧 **Màu Vàng Cam (`OCCUPIED - MEAL`):** Giờ ăn trưa, ăn tối, sinh hoạt cá nhân cố định.
  - 🟩 **Màu Xanh Lá (`BLOCK`):** Các phiên học tập/làm bài tập đã được thuật toán xếp thành công. Hiển thị rõ `[Mã_Task] Tên_Task (Phiên k/n)`.
  - 🟦 **Màu Xanh Dương (`REPAIRED`):** Các phiên học vừa được **Dời chỗ tự động** sau khi chạy mô phỏng Sự kiện đột xuất (`T04`).
  - ⬜ **Màu Trắng Sáng (`FREE`):** Khe thời gian rảnh rỗi hoàn toàn.
- **Thanh Giải Thích Thuật Toán (`💡 Giải thích thuật toán - Why here?`):**
  - Khi bạn **rê chuột (hover)** hoặc **click** vào bất kỳ ô nào trên lưới lịch, thanh màu đen ngay phía trên lưới sẽ hiển thị:
    1. Chỉ số **Slot tuyệt đối** (từ `Slot #0` đến `Slot #671`), Thứ và Khung giờ.
    2. **Lý do thuật toán chọn vị trí đó (`reason`):** Ví dụ: *"EDF (Hạn chót: Wednesday 13:00, Ưu tiên P5) — Đặt vào khe trống khả dụng sớm nhất (First-Fit) tại Slot 34..38"*, hoặc *"Đặt sau khi hoàn tất task tiên quyết [PRJ-1] tại Slot 72"*.

---

### 5.3. Cách Đọc Hộp Cảnh Báo Quá Tải & Chẩn Đoán Bất Khả Thi (`overloadAlertBox`)
Khi một kịch bản không thể xếp đủ 100% công việc (ví dụ **Kịch bản T03** hoặc **Kịch bản T06**), hộp cảnh báo màu đỏ sẽ xuất hiện và chỉ rõ **1 trong 2 chẩn đoán toán học**:
1. **`CAPACITY_SHORTAGE` (Quá tải dung lượng toán học — Kịch bản T06):**
   - **Ý nghĩa:** Tổng số phút rảnh rỗi thực tế từ hiện tại đến hạn chót **nhỏ hơn** tổng số phút bài tập yêu cầu.
   - **Ví dụ ở T06:** Từ sáng Thứ Hai đến hạn chót tối Thứ Ba `23:59` chỉ có tổng cộng **`1,365 phút` rảnh**, nhưng tổng khối lượng bài tập cần làm trước hạn đó lên tới **`1,470 phút`** $\rightarrow$ Hệ thống chứng minh thiếu hụt đúng **`105 phút` (`shortage_minutes = 105`)** và đưa ra gợi ý xử lý (giảm thời lượng hoặc dời hạn chót).
2. **`FRAGMENTATION_FAILURE` (Lỗi phân mảnh khe thời gian — Kịch bản T03):**
   - **Ý nghĩa:** Tổng thời gian rảnh cộng lại thì đủ, nhưng bị lịch cố định cắt vụn thành các khoảng ngắn hơn kích thước tối thiểu của một bài tập nguyên khối (`is_splittable = false`).
   - **Ví dụ ở T03:** Bài thi thử trực tuyến dài `180 phút` yêu cầu làm liên tục không ngắt quãng (`is_splittable = false`), nhưng các khe trống trong ngày chỉ dài tối đa `90 phút` $\rightarrow$ Hệ thống báo lỗi phân mảnh và đề xuất bật chế độ cho phép cắt nhỏ (`is_splittable = true`).

---

### 5.4. Cấu Trúc JSON Đầu Ra (`schedule_output.json`) & Các File Xuất (`.ics`, `.csv`)
Khi bấm các nút **💾 .JSON**, **📊 .CSV**, hoặc **📅 Xuất .ICS** trên thanh công cụ:
- **File `.JSON` (`schedule_output.json`):** Chứa đầy đủ `status`, `solver_used`, `execution_time_ms`, `determinism_hash`, `summary`, mảng `blocks` (từng phiên đã xếp kèm `start_slot`, `end_slot`, `start_iso`, `end_iso`, `reason`), `unplaced_tasks`, và `overload`.
- **File `.CSV` (`smartschedule_baseline.csv`):** Mở trực tiếp bằng Microsoft Excel hoặc Google Sheets để xem danh sách các phiên học theo dạng bảng biểu.
- **File `.ICS` (`smartschedule_baseline.ics`):** Chuẩn lịch quốc tế RFC 5545 — bạn có thể **Import trực tiếp vào Google Calendar, Apple Calendar hoặc Microsoft Outlook** để nhận thông báo nhắc lịch học trên điện thoại/máy tính.

---

## 6. Hướng Dẫn Sử Dụng Giao Diện Web Workbench Từng Bước

Giao diện Web được thiết kế theo bố cục **2 Cột Kỹ Thuật**:
- **Cột Trái (35%):** Gồm 3 Tab điều khiển đầu vào (`1. Hàng Đợi Task`, `2. Lịch Cố Định & Ngủ`, `3. Test Sự Cố T04/T05`) và nút chọn thuật toán ở dưới cùng.
- **Cột Phải (65%):** Hiển thị 5 thẻ KPI, Cảnh báo quá tải, Lưới 672 slots và Bảng kê chi tiết.

### Kịch bản thao tác 0: Chọn Chế Độ Khởi Tạo Lịch (Mẫu Minh / Mẫu Lan / Lịch Trống Hoàn Toàn)
Ngay trên thanh Header trên cùng của trang Web có **4 tùy chọn nạp dữ liệu khởi đầu**:
1. **`📂 Mẫu: Tuần Của Minh`**: Nạp bộ dữ liệu chuẩn trong Báo cáo đề xuất (`196 SLEEP + 132 OCCUPIED + 344 FREE = 672 slots` và 9 công việc học tập/đồ án).
2. **`📂 Mẫu: Tuần Của Lan`**: Nạp bộ dữ liệu sinh viên bận rộn (vừa học trên trường, vừa đi làm thêm, sinh hoạt CLB và có bài tập kéo dài sang tuần sau).
3. **`📄 Lịch Trống Hoàn Toàn`**: Khởi tạo một tuần mới tinh (**0 sự kiện cố định, 0 bài tập**, chỉ giữ lại khung giờ ngủ bảo vệ sức khỏe `23:30 – 06:30`) để bạn tự thêm từng lớp học và từng bài tập của riêng mình từ con số 0.
4. **`🔄 Xóa Sạch`**: Xóa toàn bộ danh sách Task và sự kiện cố định đang có trên màn hình về trạng thái rỗng tức thì.

### Kịch bản thao tác 1: Thử nghiệm các kịch bản chuẩn `T01 – T10`
1. Nhìn lên thanh Header trên cùng, tại mục **`🧪 Kịch bản Test`**, chọn bất kỳ kịch bản nào từ **`T01` đến `T10`**.
2. Ngay lập tức, dữ liệu của kịch bản đó được nạp vào hệ thống, giải lịch tự động và hiển thị thanh mô tả kỳ vọng màu tím ở đầu trang.

### Kịch bản thao tác 2: So sánh đối chứng song song 2 thuật toán (`Dual-Algorithm Comparative View`)
1. Trên thanh Header, bấm nút **`⚖️ So Sánh Song Song 2 Lịch`**.
2. Chọn Thuật toán bên trái (VD: `EDF + First-Fit`) và Thuật toán bên phải (VD: `LST + Best-Fit` hoặc `WSPT`), sau đó bấm **`🚀 Chạy So Sánh`**.
3. Màn hình sẽ hiển thị 2 lưới lịch đặt cạnh nhau; các ô có **viền nét đứt màu vàng** là những vị trí mà 2 thuật toán đưa ra quyết định đặt lịch khác nhau, kèm bảng đối sánh thời gian giải và độ phân mảnh.

### Kịch bản thao tác 3: Mô phỏng Sự kiện đột xuất (`T04`) & Làm lố giờ (`T05`)
1. Ở cột bên trái, chuyển sang Tab **`⚡ 3. Test Sự Cố (T04/T05)`**.
2. Trong khung **Mô phỏng Sự kiện đột xuất (Kịch bản T04)**:
   - Chọn Thứ, Giờ bắt đầu, Giờ kết thúc của sự kiện bất ngờ chèn vào lịch.
   - Bấm **`🛠️ Vá Cục Bộ (Local Repair)`**: Chỉ những phiên học bị sự kiện đột xuất đè trực tiếp mới bị nhấc lên và tìm khe trống mới (hiển thị màu **Xanh Dương** trên lưới), giữ nguyên 100% các phiên học khác ($S_{\text{stability}} = 100\%$).
   - Hoặc bấm **`⚖️ So Sánh Đối Chứng: Local Repair vs Full Rebuild (T04)`** để xem bảng so sánh trực tiếp độ ổn định lịch trình giữa 2 phương pháp.
3. Trong khung **Mô phỏng Làm lố giờ (Kịch bản T05)**:
   - Chọn 1 Task trong danh sách và chọn thời gian phát sinh thêm (`+30p`, `+45p`, `+60p`), sau đó bấm **`⏱️ Chạy Mô Phỏng Task Lố Giờ`** để quan sát hệ thống tự động đẩy lùi các phiên học phía sau mà không vi phạm ràng buộc cứng.

---

## 7. Danh Sách 10 Kịch Bản Kiểm Thử Chuẩn (T01 – T10)

| Mã | File JSON trong `data/test_scenarios/` | Mục tiêu kiểm thử | Kết quả chuẩn trên Baseline V0 |
| :---: | :--- | :--- | :--- |
| **T01** | `t01_normal_feasible.json` | 5 task bình thường trong tuần có đủ thời gian rảnh. | `SUCCESS` ($C_{\text{hard}}=0, R_{\text{dl}}=100\%$) |
| **T02** | `t02_overlapping_deadlines.json` | Nhiều bài tập lớn có cùng hạn chót chiều Thứ Tư. | `SUCCESS` — Tự động xếp nối tiếp từ Thứ Hai đến Thứ Tư. |
| **T03** | `t03_large_unsplittable.json` | Task 180p cho cắt nhỏ vs Task 180p nguyên khối trên các khe trống 90p. | Đặt thành công task cắt nhỏ (`90p+90p`); báo `UNPLACED` an toàn cho task nguyên khối. |
| **T04** | `t04_event_disruption.json` | Chèn sự kiện họp khẩn cấp 2 tiếng (`Thứ Hai 07:30–09:30`) đè lên lịch đã xếp. | `LOCAL_INSERTION` đạt $S_{\text{stability}} = 100\%$ (chỉ dời 2 block bị đè) so với `FULL_REBUILD` ($0\%$, xáo trộn 12 blocks). |
| **T05** | `t05_duration_overrun.json` | Task đầu tiên tốn nhiều hơn 45 phút (+50%) so với dự kiến. | Tự động dịch chuyển 3 phiên học phía sau, bảo toàn $C_{\text{hard}}=0$. |
| **T06** | `t06_overload_capacity.json` | Tổng khối lượng việc (`1,470p`) vượt quá tổng thời gian rảnh (`1,365p`) trước hạn Thứ Ba `23:59`. | Phát hiện chính xác `CAPACITY_SHORTAGE` với độ thiếu hụt `shortage_minutes = 105p`. |
| **T07** | `t07_incomplete_metadata.json` | Dữ liệu đầu vào bị bỏ trống hạn chót (`deadline_day`), thiếu `min_chunk_min`. | Tự động chuẩn hóa thành `HABIT` / giá trị mặc định an toàn và xếp lịch `100%`. |
| **T08** | `t08_unclear_priority.json` | Nhiều task có cùng hạn chót và cùng mức độ ưu tiên. | Quy tắc phá hòa (Tie-breaking) tất định 100% theo thời lượng và mã `task_id`. |
| **T09** | `t09_circadian_comparison.json` | Kiểm tra khóa cứng khung giờ ngủ khác nhau của sinh viên. | Bảo vệ tuyệt đối 100% khung giờ ngủ riêng ($C_{\text{hard}} = 0$). |
| **T10** | `t10_cross_week_deadline.json` | Bài tập có hạn chót rơi vào tuần kế tiếp (`Next Monday`, `Next Wednesday`). | Mở rộng lưới sang tuần 2 (`1,344 slots`), ưu tiên giải quyết việc tuần hiện tại trước. |

---

## 8. Giải Thích Chi Tiết: Khi Chạy Kiểm Thử (Test) Thì Hệ Thống Làm Gì Bên Dưới?

Hệ thống đi kèm 2 công cụ kiểm thử tự động độc lập: **Bộ kiểm thử đơn vị & tích hợp (`pytest`)** và **Bộ chạy thực nghiệm chuẩn (`benchmark_runner.py`)**. Dưới đây là giải thích chi tiết từng bước hệ thống thực hiện khi bạn bấm chạy kiểm thử:

---

### 8.1. Khi chạy `python -m pytest -v` (15 Bài Kiểm Thử Tự Động trong `tests/`)

Lệnh `pytest` sẽ quét toàn bộ thư mục `tests/` và thực thi **4 nhóm kiểm thử nghiêm ngặt** (tổng cộng 15 bài test):

#### Nhóm 1: Kiểm thử Toán học Lưới 672 Slots (`tests/test_time_grid.py` — 3 bài test)
1. **`test_slot_conversion_math`**:
   - Kiểm tra công thức chuyển đổi qua lại giữa `(Thứ, Giờ:Phút)` $\leftrightarrow$ `Slot Index (0..671)`.
   - Xác minh các mốc biên: `Monday 00:00` $\rightarrow$ `Slot 0`, `Monday 06:30` $\rightarrow$ `Slot 26`, `Sunday 23:45` $\rightarrow$ `Slot 671`, và mốc đóng cuối tuần `Sunday 23:59` $\rightarrow$ `Slot 672`.
2. **`test_minh_week_exact_672_slot_accounting`**:
   - Nạp file `data/sample_week_commitments.json` (Tuần của Minh) vào `TimeGridManager`.
   - Đếm từng slot trên mảng 672 phần tử và **kiểm chứng khớp tuyệt đối từng con số trong Báo cáo đề xuất (§2.8 & §5.5)**:
     - Tổng số slot = `672` (`10,080 phút`)
     - Số slot ngủ (`SLEEP`) = **`196 slots`** (`2,940 phút`)
     - Số slot bận cố định (`OCCUPIED`) = **`132 slots`** (`1,980 phút`)
     - Số slot rảnh thực sự (`FREE`) = **`344 slots`** (`5,160 phút`)
3. **`test_sleep_and_fixed_event_locking`**:
   - Thử đặt một công việc giả định đè vào lúc `01:00 sáng Thứ Hai` (`Slot 4` - đang ngủ) và `13:00 chiều Thứ Hai` (`Slot 52` - đang học trên lớp).
   - Xác minh `TimeGridManager` lập tức **từ chối (`False`)** và trả về đúng mã lỗi vi phạm `H2_SLEEP_VIOLATION` / `H1_COMMITMENT_OVERLAP`.

#### Nhóm 2: Kiểm thử 5 Ràng buộc cứng $H_1 \dots H_5$ (`tests/test_constraints.py` — 3 bài test)
4. **`test_hard_constraints_zero_violation_on_presets`**:
   - Chạy lần lượt cả 3 thuật toán (`EDF`, `LST`, `WSPT`) trên cả **Tuần của Minh** và **Tuần của Lan**.
   - Dùng bộ kiểm toán độc lập (`src/metrics.py`) quét lại toàn bộ lịch đầu ra để khẳng định: `hard_constraint_violations == 0` và `deadline_satisfaction_rate == 100.0%`.
5. **`test_manual_move_validation_rejects_sleep_and_class_overlap`**:
   - Mô phỏng hành vi người dùng cố tình kéo/di chuyển một phiên học đã xếp vào khung giờ ngủ (`01:00`) hoặc khung giờ học cố định (`13:00`).
   - Kiểm chứng hàm `validate_manual_move` chặn đứng thao tác sai và trả về lời giải thích tiếng Việt rõ ràng.
6. **`test_dependency_chain_strict_ordering` (Kiểm tra ràng buộc $H_5$):**
   - Tạo 2 công việc ngược thứ tự ưu tiên: `DEP-B` có độ ưu tiên cao nhất (`P5`, hạn Thứ Tư) nhưng phụ thuộc vào `DEP-A` (`depends_on: ["DEP-A"]`, ưu tiên thấp `P2`, hạn Thứ Năm).
   - Kiểm chứng bộ sắp xếp Topo buộc thuật toán phải xếp **toàn bộ các phiên của `DEP-A` hoàn tất trước** rồi mới được phép bắt đầu phiên đầu tiên của `DEP-B` (`min_start_B >= max_end_A`).

#### Nhóm 3: Kiểm thử Tính Tất định 3x & Độ Ổn định Vá lịch (`tests/test_edf_solver.py` — 2 bài test)
7. **`test_3x_determinism_hash_equality`**:
   - Với mỗi thuật toán trong 4 bộ giải (`EDF`, `LST`, `WSPT`, `BACKTRACK`), chạy giải lịch **3 lần liên tiếp độc lập** trên cùng đầu vào.
   - Tính mã băm `SHA-256` của toàn bộ tọa độ các phiên học ở cả 3 lần chạy và kiểm chứng 3 mã băm giống hệt nhau 100% (`is_deterministic == True`).
8. **`test_local_repair_vs_full_rebuild_stability`**:
   - Nạp kịch bản `T04` (chèn sự kiện họp khẩn cấp 2 tiếng vào sáng Thứ Hai đè lên lịch đã xếp).
   - Chạy đối chứng `LOCAL_INSERTION` (Vá lịch cục bộ) và `FULL_REBUILD` (Xếp lại từ đầu).
   - Kiểm chứng `LOCAL_INSERTION` giữ nguyên $\ge 90\%$ (thực tế đạt **100%**) các phiên học không bị sự kiện đột xuất đè trúng, cao vượt trội so với `FULL_REBUILD`.

#### Nhóm 4: Kiểm thử Tích hợp 10 Kịch bản `T01–T10` & REST API (`tests/test_scenarios_t01_t10.py` — 7 bài test)
9. **`test_t01_normal_feasible` & `test_t02_tight_cluster`**: Kiểm chứng các kịch bản khả thi đạt 100% hạn chót và 0 vi phạm cứng.
10. **`test_t03_fragmented_slots`**: Kiểm chứng trên các khe trống phân mảnh 90p, công việc 180p cho phép cắt nhỏ (`T03-SPLITTABLE`) được cắt thành `90p + 90p` và xếp thành công; trong khi công việc 180p nguyên khối (`T03-UNSPLITTABLE`) được phát hiện không đủ khe liên tục và đưa vào `unplaced_tasks`.
11. **`test_t06_overload_capacity_exact_shortage`**: Kiểm chứng bài toán chứng minh quá tải dung lượng toán học trong Báo cáo (§6.7): Quỹ thời gian rảnh trước hạn Thứ Ba `23:59` là `1,365 phút`, tổng khối lượng việc yêu cầu là `1,470 phút` $\rightarrow$ Hệ thống xuất báo cáo `CAPACITY_SHORTAGE` với độ thiếu hụt chính xác tuyệt đối **`shortage_minutes == 105`**.
12. **`test_t07_incomplete_metadata_normalization`**: Kiểm chứng khi người dùng nhập thiếu hạn chót hoặc thiếu thông số cắt nhỏ, hệ thống tự động chuẩn hóa an toàn mà không bị crash.
13. **`test_t08_t09_t10_edge_cases`**: Kiểm chứng phá hòa tất định (`T08`), bảo vệ giờ ngủ cá nhân (`T09`), và mở rộng lưới sang tuần kế tiếp (`T10`).
14. **`test_fastapi_endpoints_e2e`**: Giả lập trình duyệt gọi trực tiếp vào các REST API (`/api/presets`, `/api/scenarios`, `/api/plan`, `/api/compare`, `/api/export/ics`) và kiểm tra mã phản hồi `HTTP 200 OK` cùng nội dung file lịch `.ics`.

---

### 8.2. Khi chạy `python benchmark_runner.py` Thì Hệ Thống Làm Gì?

Khi bạn chạy `python benchmark_runner.py` (hoặc bấm `run_tests.bat`), script sẽ thực hiện **4 bài đo kiểm thực nghiệm tự động** và in ra 4 bảng báo cáo định lượng trên Terminal:

1. **Bảng 1 — Quét toàn bộ 10 Kịch bản chuẩn (`T01` $\rightarrow$ `T10`):**
   - Nạp từng file JSON trong `data/test_scenarios/`, chạy thuật toán chuẩn `EDF`, đo thời gian giải (`Latency ms`), kiểm tra số lỗi cứng (`C_hard`), tỷ lệ đạt hạn chót (`R_dl %`), độ phân mảnh (`FragIdx`), và chạy lặp 3 lần mỗi kịch bản để xác nhận cột `3x Determ = PASS`.
2. **Bảng 2 — Đối sánh 4 Thuật toán trên cùng Tuần chuẩn (`T01`):**
   - Chạy lần lượt `GREEDY_EDF_FIRST_FIT`, `GREEDY_LST_BEST_FIT`, `GREEDY_WSPT_SMITH_RULE`, và `BACKTRACKING_BRANCH_AND_BOUND` trên cùng đầu vào để so sánh tốc độ giải (`~0.8 ms` đến `~7.5 ms`), độ phân mảnh và mã băm `SHA-256`.
3. **Bảng 3 — Thực nghiệm Độ ổn định khi có Sự cố (`T04`) & Làm lố giờ (`T05`):**
   - Đo lường và in ra sự khác biệt giữa **Local Insertion** (`Stability = 100.00%`, chỉ dời đúng `2 blocks` bị đè, mất `0.84 ms`) và **Full Rebuild** (`Stability = 0.00%`, xáo trộn `12 blocks` do hiệu ứng Domino, mất `4.90 ms`).
   - Mô phỏng Task `T05-A` bị làm lố giờ từ `90p` lên `135p` (`+45p`) và đếm số phiên học phía sau bị đẩy lùi dây chuyền (`Shifted Downstream Blocks = 3`).
4. **Bảng 4 — Kiểm thử Khả năng Mở rộng & Tốc độ theo Quy mô (`Scalability N = 10, 25, 50 Tasks`):**
   - Tự động sinh ngẫu nhiên có kiểm soát `10`, `25`, và `50` công việc học tập trong tuần.
   - Đo thời gian giải thực tế (`~2.7 ms` cho 10 tasks, `~6.5 ms` cho 25 tasks, `~12.8 ms` cho 50 tasks) và đối chiếu với ngưỡng yêu cầu kỹ thuật (`<= 50 ms` cho 25 tasks, `<= 200 ms` cho 50 tasks).

---

## 9. Tài Liệu REST API Endpoints

Khi chạy server FastAPI (`web/api.py`), bạn cũng có thể truy cập tài liệu Swagger UI tự động tại **`http://127.0.0.1:8000/docs`**. Các endpoint chính bao gồm:

| Phương thức | Endpoint | Mô tả chức năng |
| :---: | :--- | :--- |
| `GET` | `/api/presets` | Lấy dữ liệu mẫu chuẩn (**Tuần của Minh** và **Tuần của Lan**). |
| `GET` | `/api/scenarios` | Liệt kê danh sách 10 kịch bản kiểm thử chuẩn `T01 – T10`. |
| `GET` | `/api/scenarios/{scenario_id}` | Lấy chi tiết dữ liệu đầu vào của một kịch bản (VD: `/api/scenarios/T06`). |
| `POST` | `/api/plan` *(hoặc `/api/solve`)* | Giải bài toán xếp lịch tuần với thuật toán tùy chọn (`EDF`, `LST`, `WSPT`, `BACKTRACK`). |
| `POST` | `/api/compare` | Chạy song song 2 thuật toán trên cùng đầu vào và trả về bảng đối sánh sai khác. |
| `POST` | `/api/repair` | Tái lập lịch khi có sự kiện đột xuất (`LOCAL_INSERTION`, `FULL_REBUILD`, `RIPPLE_SHIFT`, `COMPARE_BOTH`). |
| `POST` | `/api/progress` *(hoặc `/api/overrun`)* | Mô phỏng task làm lố giờ (`T05`) và tính toán số phiên học bị trượt dây chuyền. |
| `POST` | `/api/validate-move` | Kiểm tra một thao tác đổi giờ thủ công có vi phạm ràng buộc cứng $H_1 \dots H_5$ hay không. |
| `POST` | `/api/determinism-check` | Chạy thuật toán $N$ lần liên tiếp (mặc định 3 lần) và đối chiếu mã băm `SHA-256`. |
| `POST` | `/api/export/{fmt}` | Xuất lịch trình ra tệp tải về với `fmt` là `json`, `csv`, hoặc `ics`. |
