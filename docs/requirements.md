# SmartSchedule — Hướng Dẫn Cài Đặt & Danh Mục Thư Viện (Requirements)

**Dự án:** SmartSchedule — Trợ Lý Tối Ưu Hóa & Tự Động Xếp Lịch Học Tập  
**Môn học:** CS252 — Tư Duy Tính Toán (2026) · FIT-HCMUS (Nhóm 03 — *The Seven Dwarfs*)  
**Vị trí:** `docs/requirements.md`  
**File gốc:** `group03-smartschedule-baseline/requirements.txt`  
**Đối tượng:** Mọi thành viên trong nhóm & Các AI Agent hỗ trợ  

---

> [!IMPORTANT]
> ## 🚨 QUY ĐỊNH BẮT BUỘC ĐỒNG BỘ THƯ VIỆN & TÀI LIỆU
> Khi bất kỳ thành viên nào hoặc AI Agent nào cần cài đặt thêm thư viện mới (ví dụ thư viện vẽ biểu đồ, thư viện xuất PDF sau này):
> 1. Thêm tên thư viện và phiên bản vào file: `group03-smartschedule-baseline/requirements.txt`.
> 2. **BẮT BUỘC ĐỒNG BỘ ĐỒNG THỜI CẢ 2 TÀI LIỆU:**
>    - `docs/requirements.md` (File này — Tiếng Việt cho thành viên).
>    - `agents/requirements.md` (Bản tiếng Anh cho các AI Agent).
> 3. Giải thích rõ: Thư viện này làm gì, thuộc tầng nào trong kiến trúc 5 tầng, và ghi nhận thay đổi vào `docs/commit_changes.md` & `agents/commit_changes.md`.

---

## 1. Yêu Cầu Về Môi Trường Máy Tính

| Thành phần | Yêu cầu tối thiểu | Khuyên dùng | Ghi chú |
| :--- | :--- | :--- | :--- |
| **Python** | `Python >= 3.10` | `Python 3.12+` (hoặc 3.14) | Đã kiểm thử chạy mượt trên CPython 3.12 và 3.14 (Windows / macOS / Linux). |
| **Hệ Điều Hành** | Mọi hệ điều hành | Windows 10/11, macOS, Ubuntu | Mã nguồn dùng `pathlib.Path` nên tương thích đa nền tảng. |
| **Giao Diện Đồ Họa** | Thư viện `tkinter` | Có sẵn trong Python chuẩn | Dùng để mở giao diện Test Studio (`test_studio.py`). Windows và macOS khi cài Python chính thức đã có sẵn Tkinter. |

---

## 2. Giải Thích Từng Thư Viện Cần Cài Đặt (`requirements.txt`)

Nội dung file [`requirements.txt`](file:///d:/Projects/Computational-Thinking---Group-Project/group03-smartschedule-baseline/requirements.txt) gồm có 6 thư viện:

```text
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
pytest>=7.4.0
httpx>=0.24.0
python-dateutil>=2.8.2
```

### Chi tiết vì sao nhóm cần từng thư viện:

#### 1. `fastapi>=0.100.0` (Khung Web Backend)
- **Dùng để làm gì:** Là framework backend hiện đại, siêu nhanh giúp xây dựng các cổng API cho ứng dụng.
- **Dùng ở tầng nào:** **Chỉ được dùng ở Tầng 4 (Web API)** trong `web/api.py`.
- **Cung cấp API gì:** Nhận danh sách việc từ giao diện gửi về để xếp lịch (`/api/solve`), trả về danh sách kịch bản mẫu (`/api/presets`), kiểm tra hợp lệ khi người dùng kéo thả (`/api/validate-move`), và xuất file lịch (`/api/export/{fmt}`).
- **⚠️ LƯU Ý SỐNG CÒN:** **Tuyệt đối không được import FastAPI vào tầng thuật toán (`src/solvers/`) hay tầng dữ liệu (`src/models.py`)**. Quy tắc bất biến `INV-1` sẽ chặn ngay lập tức nếu vi phạm!

#### 2. `uvicorn>=0.23.0` (Máy Chủ Chạy Web ASGI)
- **Dùng để làm gì:** Là máy chủ web siêu nhẹ đóng vai trò "host" để chạy mã nguồn FastAPI.
- **Dùng ở đâu:** Dùng để khởi động trang web làm việc Technical Workbench tại địa chỉ `http://127.0.0.1:8000`.
- **Lệnh chạy:** `python -m uvicorn web.api:app --host 127.0.0.1 --port 8000`.

#### 3. `pydantic>=2.0.0` (Định Kiểu & Kiểm Tra Dữ Liệu)
- **Dùng để làm gì:** Giúp định nghĩa các lớp dữ liệu có kiểm tra kiểu tự động (Type Hinting). Nếu người dùng nhập sai (ví dụ thời lượng âm, độ ưu tiên ngoài khoảng 1–5), Pydantic sẽ phát hiện và báo lỗi ngay.
- **Dùng ở tầng nào:** **Tầng 1 (Mô Hình Dữ Liệu)** trong `src/models.py`.
- **Định nghĩa các đối tượng:** `Task` (công việc), `FixedEvent` (lịch cố định), `SleepSchedule` (giờ ngủ), `ScheduleOutput` (lịch đã xếp). Giúp dữ liệu đồng nhất chuẩn ISO-8601 (§7.3 Improve Plan).

#### 4. `pytest>=7.4.0` (Bộ Khung Kiểm Thử Tự Động)
- **Dùng để làm gì:** Bộ công cụ kiểm thử chuẩn của Python giúp chạy tự động toàn bộ 56 bài test trong chớp mắt (chỉ mất ~2 giây).
- **Dùng ở tầng nào:** **Tầng 5 (Hệ Thống Kiểm Thử)** trong `verification_tests/`.
- **Chạy bằng cách nào:** Chạy qua bộ lọc console sạch `clean_runner.py` để không bị rác màn hình.

#### 5. `httpx>=0.24.0` (Thư Viện Gửi Yêu Cầu HTTP Độc Lập)
- **Dùng để làm gì:** Là thư viện HTTP client mạnh mẽ, được FastAPI sử dụng để kích hoạt `TestClient`.
- **Dùng ở đâu:** Trong các bài test kiểm thử API (`verification_tests/ui_tests/`). Nó giúp kiểm thử toàn bộ API web ngay trong bộ nhớ mà **không cần phải bật server uvicorn thủ công**.

#### 6. `python-dateutil>=2.8.2` (Xử Lý Ngày Giờ Mở Rộng)
- **Dùng để làm gì:** Bổ sung các tính năng tính toán ngày giờ mạnh mẽ mà thư viện chuẩn `datetime` của Python còn thiếu.
- **Dùng ở đâu:** Dùng để đọc và phân tích các chuỗi thời gian chuẩn quốc tế ISO-8601 (ví dụ `"2026-11-02T00:00:00+07:00"`), tính toán độ lệch múi giờ Việt Nam (`+07:00`), và tự động xác định ngày đầu tuần.

---

## 3. Các Thư Viện Có Sẵn Trong Python (Không Cần Cài Thêm)

Dự án tận dụng tối đa thư viện chuẩn của Python để hệ thống nhẹ nhất có thể:
- `ast`: Dùng để quét mã nguồn tự động, cấm việc import bừa bãi mã web vào thuật toán.
- `tracemalloc`: Đo chính xác từng Byte bộ nhớ heap để chống tràn RAM.
- `threading`: Giúp chạy test ngầm không bị đơ cửa sổ giao diện.
- `argparse`: Giúp nhận các tham số dòng lệnh (`--pass`, `--gaps`, `--all`).
- `pathlib`: Xử lý đường dẫn file tương thích cả Windows, macOS, Linux.
- `hashlib`: Băm mã SHA-256 để chứng minh thuật toán có tính tất định tuyệt đối.
- `tkinter`: Tạo cửa sổ ứng dụng đồ họa Test Studio.

---

## 4. Hướng Dẫn Cài Đặt Từng Bước Cho Thành Viên

### Cách 1: 1-Click Tự Động Bằng File Batch (Dành Cho Windows — Khuyên Dùng)
1. Mở thư mục `group03-smartschedule-baseline/`.
2. Nhấp đúp chuột vào file **`setup_env.bat`**.
3. File script sẽ tự động tạo môi trường ảo `.venv`, kích hoạt và cài toàn bộ 6 thư viện trên cho bạn trong 30 giây!

---

### Cách 2: Cài Đặt Thủ Công Bằng Dòng Lệnh (Windows / macOS / Linux)
Mở terminal tại thư mục `group03-smartschedule-baseline/` và chạy 3 lệnh sau:

```bash
# 1. Tạo môi trường ảo riêng biệt
python -m venv .venv

# 2. Kích hoạt môi trường ảo
# Trên Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Trên Windows (Command Prompt):
.venv\Scripts\activate.bat
# Trên macOS / Linux:
source .venv/bin/activate

# 3. Cập nhật pip và cài đặt toàn bộ thư viện
python -m pip install --upgrade pip
pip install -r requirements.txt
```
Sau khi cài xong, bạn có thể gõ `python -B verification_tests/clean_runner.py --pass` để kiểm tra, nếu màn hình báo `50 Passed | Status: ALL PASSED` là môi trường đã chuẩn 100%!

