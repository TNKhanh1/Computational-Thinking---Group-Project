# SmartSchedule — Danh Mục Thư Viện, Ràng Buộc Kiến Trúc & Quy Định Môi Trường (`docs/requirements.md`)

**Dự án:** SmartSchedule (`v1.0-alpha`)  
**Tệp cấu hình môi trường:** [`environments/requirements.txt`](../environments/requirements.txt) & [`environments/requirements-nllb.txt`](../environments/requirements-nllb.txt) (nằm gọn trong [`environments/`](../environments/) cùng [`environments/pyproject.toml`](../environments/pyproject.toml))  
**Đối tượng:** Toàn bộ thành viên Nhóm 03 & Các AI Agent hỗ trợ code

> [!IMPORTANT]
> **QUY ĐỊNH CẬP NHẬT MỚI NHẤT (`v1.0-alpha`):**
> 1. **Đọc tài liệu trung tâm trước khi code:** Thành viên xem [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md); AI Agent bắt buộc đọc [`agents/README.md`](../agents/README.md) và [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md).
> 2. **Tiết kiệm Token & Giữ Gốc Repo Sạch Sẽ:** Ngoài gốc repo chỉ giữ `.gitignore` và `README.md`; mọi file môi trường nằm trong [`environments/`](../environments/), còn bản thảo/proposal cũ nằm trong [`Project_Drafts/`](../Project_Drafts/). Agent tra cứu nhanh qua [`environments/CODEBASE_INDEX.md`](../environments/CODEBASE_INDEX.md) và bỏ qua file nặng theo [`environments/.agentignore`](../environments/.agentignore).
> 3. **Thư mục chuẩn mới:** Không dùng lại `group03-smartschedule-baseline/`, `src/`, `web/`, `verification_tests/`. Toàn bộ mã nguồn nay nằm tại `smartschedule/`, `data/`, `tests/`, và `tools/`.
> 4. **Quy tắc đồng bộ bắt buộc:** Bất kỳ khi nào thêm, sửa, xóa thư viện trong [`environments/requirements.txt`](../environments/requirements.txt), phải cập nhật **đồng thời cả [`docs/requirements.md`](requirements.md) và [`agents/requirements.md`](../agents/requirements.md)**.

---

## 1. Thư Viện Vận Hành Chính ([`environments/requirements.txt`](../environments/requirements.txt))

| Thư Viện | Phiên Bản | Tầng Kiến Trúc | Mục Đích & Phạm Vi Cho Phép |
| :--- | :---: | :--- | :--- |
| **`fastapi`** | `>=0.115.0` | **Tầng 4 (`smartschedule/api/`, `tools/member_eval/`)** | Khung REST API, phục vụ UI và tài liệu Swagger. **Cấm import trong `smartschedule/core/` (`INV-1`).** |
| **`uvicorn[standard]`** | `>=0.30.0` | **Tầng 4 (Server Web)** | Máy chủ ASGI chạy ứng dụng qua `python -B -m smartschedule.main --serve`. |
| **`pydantic`** | `>=2.8.0` | **Tầng 1 & 4** | Kiểm soát dữ liệu đầu vào/ra chặt chẽ tại [`smartschedule/core/models.py`](../smartschedule/core/models.py) và schema JSON cho AI đọc ngữ cảnh ở `smartschedule/nlp/`. |
| **`httpx`** | `>=0.27.0` | **Tầng 4 & 5 (`tests/`, `smartschedule/nlp/`)** | Kiểm thử API tự động (`TestClient`) và gọi API mô hình ngôn ngữ online tùy chọn (`CONTEXT_MODEL_URL`). **Cấm dùng trong `smartschedule/core/`.** |
| **`python-dateutil`** | `>=2.9.0` | **Tầng 1 / 3 / 4** | Tính toán thời gian chuẩn ISO-8601 và múi giờ. |
| **`pytest`** | `>=8.0.0` | **Tầng 5 (`tests/`, `v1.0-alpha-plan/Testing_System/tests/`)** | Bộ chạy kiểm thử tự động đi kèm [`tests/clean_runner.py`](../tests/clean_runner.py). |
| **`PyYAML`** | `>=6.0` | **Tầng 4 & 5** | Đọc bộ 200 ca kiểm thử song ngữ trong `tests/fixtures/nl_cases/`. |
| **`google-genai`** | `>=1.0.0` | **Tầng 4 (`smartschedule/nlp/` duy nhất)** | Kết nối Google Gemini (`GEMINI_API_KEY`) cho **M1 NL Parser (`gemini-3-flash-preview`)** và **Mô hình AI Đọc Ngữ Cảnh Online Siêu Nhẹ `v1.0-alpha` (`gemini-2.5-flash-lite` / `gemini-2.5-flash`, tốn `0 MB` RAM máy)**. Tuyệt đối không gọi trong `smartschedule/core/`. |
| **`python-dotenv`** | `>=1.0.0` | **Tầng 4 (`smartschedule/nlp/parser_controller.py`)** | Tự động nạp tệp `environments/.env` để đọc `GEMINI_API_KEY` an toàn (đã được `.gitignore` bảo vệ). |

---

## 2. Thư Viện Dịch Offline Tùy Chọn ([`environments/requirements-nllb.txt`](../environments/requirements-nllb.txt))

Chỉ cài nếu muốn chạy dịch thuật neural offline bằng CTranslate2 (`backend="nllb"`). Đã tách riêng khỏi `requirements.txt` để máy các bạn không phải tải ~2 GB khi cài đặt.

- **`ctranslate2>=4.5.0`**, **`sentencepiece>=0.2.0`**, **`huggingface-hub>=0.25.0`** (Chỉ import lười trong `smartschedule/nlp/hybrid_pipeline/translator.py`).

---

## 3. Lõi Thuần Thư Viện Chuẩn Python (Không Tốn Thư Viện Ngoài)

Toàn bộ hạt nhân [`smartschedule/core/`](../smartschedule/core/) tuân thủ `INV-1` và `INV-5`, chỉ dùng thư viện có sẵn của Python 3.10+:
- **`sqlite3`** (`smartschedule/core/storage.py` $\to$ `data/runtime/local_state.db`)
- **`hashlib`** (`smartschedule/core/task_tracer.py` truy vết từ khóa SHA-256 & mã kiểm chứng tất định)
- **`ast`, `tracemalloc`, `threading`, `tkinter`** (kiểm tra biên kiến trúc, rò rỉ bộ nhớ `< 350 KB` và Test Studio)

---

## 4. Cài Đặt Môi Trường Nhanh (Trên Windows)

```powershell
# Chạy từ thư mục gốc repo:
.\tools\scripts\setup_env.bat                           # Tự tạo .venv và cài đặt environments/requirements.txt
Copy-Item environments/.env.example environments/.env   # Tùy chọn: điền GEMINI_API_KEY cho mô hình đọc ngữ cảnh online
.\tools\scripts\run_app.bat                             # Mở Web App tại http://127.0.0.1:8000
```
