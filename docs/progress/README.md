# Danh Mục Tài Liệu Kỹ Thuật Đang Hoạt Động (`docs/progress/`)

> [!IMPORTANT]
> **Muốn nắm kế hoạch và danh sách việc hiện hành của `v1.0-alpha`?** Hãy đọc [`docs/README.md`](../README.md) và [`v1.0-alpha-plan/README.md`](../../v1.0-alpha-plan/README.md). Các tài liệu cũ không còn dùng đã được lưu riêng tại [`docs/archive/`](../archive/).

---

## Các Tài Liệu Tham Khảo Đang Hiệu Lực (`docs/progress/`)

1. **[`v1.0-alpha-plan/README.md`](../../v1.0-alpha-plan/README.md)** — **Tài Liệu Tổng Hợp Chính Thức `v1.0-alpha`**
   - Giải thích chi tiết cấu trúc thư mục mới (`smartschedule/`, `environments/`, `Project_Drafts/`), giao diện Chat-First, thuật toán tối ưu + cắt tỉa tập trội, mô hình AI đọc ngữ cảnh online, và **bảng việc cần làm `[x]`/`[ ]`** cho cả nhóm.
2. **[`kien_truc_he_thong.md`](kien_truc_he_thong.md)**
   - Mô hình kiến trúc 5 tầng phân tách sạch sẽ (`smartschedule/core/`, `nlp/`, `api/`, `ui/`, `tests/`) và 6 quy tắc bất biến `INV-1` đến `INV-6`.
3. **[`kiem_thu_va_benchmark.md`](kiem_thu_va_benchmark.md)**
   - Hướng dẫn chạy kiểm thử tự động (`tests/clean_runner.py`), Test Studio, `Testing_System v2.1` và 10 kịch bản `T01–T10`.
4. **[`tinh_nang_dem_thoi_gian.md`](tinh_nang_dem_thoi_gian.md)**
   - Giải thích toán học cho bộ đệm thời gian chống ảo tưởng lập kế hoạch (`smartschedule/core/estimate_buffer.py`).
5. **[`bo_phan_tich_ngon_ngu_hybrid.md`](bo_phan_tich_ngon_ngu_hybrid.md)**
   - Kiến trúc bộ đọc hiểu ngôn ngữ tự nhiên Anh/Việt 6 tầng (`smartschedule/nlp/hybrid_pipeline/`), hợp nhất với tầng tách mệnh đề & mô hình Gemini online siêu nhẹ ở `v1.0-alpha`.
