# SmartSchedule — Hướng Dẫn Kiểm Thử & Chạy Benchmark (`docs/progress/kiem_thu_va_benchmark.md`)

**Phụ trách:** Builder 3 (Kiến Trúc Hệ Thống & Kiểm Thử Triển Khai)  
**Vị trí mã nguồn:** [`tests/`](../../tests/) · **Máy chấm v2.1:** [`v1.0-alpha-plan/Testing_System/`](../../v1.0-alpha-plan/Testing_System/README.md) · **Công cụ:** [`tools/benchmarks/`](../../tools/benchmarks/)  
**Xem thêm:** [`docs/README.md`](../README.md) · [`v1.0-alpha-plan/README.md`](../../v1.0-alpha-plan/README.md)

---

## 1. Cấu Trúc Thư Mục Kiểm Thử Mới (`tests/`)

Từ bản `v1.0-alpha`, toàn bộ bộ kiểm thử đã chuyển từ `group03-smartschedule-baseline/verification_tests/` ra thư mục [`tests/`](../../tests/) tại gốc repo với tên gọi ngắn gọn, sạch sẽ:

```text
tests/
├── clean_runner.py         # Trình chạy kiểm thử sạch, ẩn log nhiễu
├── test_studio.py          # Ứng dụng đồ họa Test Studio (Tkinter)
├── ui/                     # Kiểm tra giao diện Chat-First & REST API
├── architecture/           # Kiểm tra quy tắc INV-1..6, rò rỉ bộ nhớ (<350 KB), đa luồng
├── logical/                # Kiểm tra 6 solver V3, NL Parser, Chat-First, SHA-256 tracer, P1–P3
├── benchmark/              # Kiểm tra toán lưới 672 ô, Ràng buộc cứng H1–H5, T01–T10
├── gaps/                   # Bộ test theo dõi mục tiêu nâng cấp
└── fixtures/nl_cases/      # Bộ 200 ca tiếng Việt/Anh chuẩn hóa (verify_hybrid_200.py)
```

*(Dữ liệu mẫu & kịch bản `T01–T10` nay nằm ở [`data/presets/`](../../data/presets/) và [`data/scenarios/`](../../data/scenarios/).)*

---

## 2. Cách Chạy Kiểm Thử Nhanh Nhất

### Cách 1: Nhấp Đúp Script Windows (Trong `tools/scripts/`)
- Vào [`tools/scripts/`](../../tools/scripts/) và mở **`run_test_studio.bat`** để dùng giao diện đồ họa, hoặc chạy **`run_verification_tests.bat --pass`**.

### Cách 2: Chạy Bằng Dòng Lệnh Tại Thư Mục Gốc Repo

```powershell
# 1. Chạy toàn bộ bộ kiểm thử vận hành
python -B tests/clean_runner.py --pass

# 2. Chạy riêng từng tầng
python -B tests/clean_runner.py --ui      # Giao diện & API
python -B tests/clean_runner.py --arch    # Kiến trúc & rò rỉ bộ nhớ
python -B tests/clean_runner.py --logic   # Logic thuật toán, NL Parser & Chat-First
python -B tests/clean_runner.py --bench   # 10 kịch bản T01–T10 & lưới 672 ô
python -B tests/clean_runner.py --gaps    # Các bài test mục tiêu

# 3. Kiểm tra máy chấm tự động Testing_System v2.1 + Fuzz v2
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q

# 4. Kiểm tra 200 câu lệnh ngôn ngữ tự nhiên Anh/Việt
python -B tests/fixtures/nl_cases/validate_cases.py
python -B tests/fixtures/nl_cases/verify_hybrid_200.py

# 5. Chạy thực nghiệm Benchmark & Grid Search hệ số đệm alpha
python -B tools/benchmarks/benchmark_runner.py
python -B tools/benchmarks/benchmark_alpha_grid.py --include-extreme --save-json
```

---

## 3. Cách Đọc Kết Quả Từ `clean_runner.py`

Màn hình console sạch gồm 3 phần rõ ràng:
1. **Tín hiệu chạy (`[RUNNING]`):** Thời điểm bắt đầu và bộ test mục tiêu.
2. **Từng giai đoạn (`[PHASE]`):** Hiển thị tách bạch `tests/ui`, `tests/architecture`, `tests/logical`, `tests/benchmark`.
3. **Tổng kết (`[FINAL SUMMARY]`):** Thống kê tổng số bài `PASSED` / `FAILED`; nếu có lỗi sẽ chỉ thẳng tên hàm (`Point to:`) và sai lệch giá trị (`Details:`).
