# Bộ Phân Tích Ngôn Ngữ Tự Nhiên Hybrid EN/VI & UX Modal Công Việc

> **Thành phần:** `smartschedule/nlp/hybrid_pipeline/` + `smartschedule/nlp/parser_controller.py` (M1) + `smartschedule/nlp/{clause_condenser,context_router}.py` + `smartschedule/api/` + `smartschedule/ui/`  
> **Trạng thái:** Đang vận hành ổn định — `200/200` ca YAML (`rule`), kiểm thử tích hợp & tổng quát hóa đạt `100%`, đã hợp nhất với tầng **Mô Hình AI Đọc Ngữ Cảnh Online (`gemini-2.5-flash-lite`)** trong `v1.0-alpha`.

---

## 1. Kiến Trúc Đường Ống Hybrid 6 Tầng

Bộ phân tích Hybrid EN/VI kết hợp pipeline offline 6 tầng ([`smartschedule/nlp/hybrid_pipeline/hybrid_parser.py`](../../smartschedule/nlp/hybrid_pipeline/hybrid_parser.py)) với tầng tiếp hợp M1 ([`parser_controller.py`](../../smartschedule/nlp/parser_controller.py)), định tuyến ngữ cảnh chat (`context_router.py` + `clause_condenser.py`) và giao diện Chat-First (`smartschedule/ui/`).

```text
Câu nhập (Tiếng Việt / Tiếng Anh) + Dữ liệu UI (Khẩn cấp 1-4, Nhịp học, Tệp đính kèm)
   │
   ▼
[1] Tách & Kiểm tra Trích dẫn (`[[filename]]`, `@[path/file]`)
   │   └─ Bật cảnh báo ĐỎ nếu thiếu ngoặc kép đôi hoặc chưa đính kèm tệp
   ▼
[2] Nhận diện Ngôn ngữ & Dịch VI→EN (`translator.py`: rule | nllb | opus_mt)
   │
   ▼
[3] Trích xuất Khung Công Việc (`parser.py` + `regex_parser.py` + `tokenizer.py`)
   │   └─ Thời lượng, Thứ/Giờ hạn chót, Phân loại (`QUIZ`, `EXAM`, `LAB`, `READING`, ...)
   ▼
[4] Ánh xạ Phân loại & Khẩn cấp (`1=Khẩn..4=Thấp -> 5..1` cho Solver)
   │   └─ Đồng bộ nhất quán `draft.priority` & `hybrid.urgency`
   ▼
[5] Tổng hợp Nhịp học & Khả năng Cắt nhỏ (`pomodoro`, `balanced`, `deep_focus`)
   │   └─ Tôn trọng lựa chọn `Cho phép cắt nhỏ` / `Làm liền 1 buổi` ngay trên thanh nhập
   ▼
[6] Chuẩn hóa & Chẩn đoán (`E_INVALID_CITATION_FORMAT`, cảnh báo thiếu dữ liệu)
```

---

## 2. Cấu Trúc Gói `smartschedule/nlp/hybrid_pipeline/` Đang Triển Khai

Thư mục [`smartschedule/nlp/hybrid_pipeline/`](../../smartschedule/nlp/hybrid_pipeline/) lưu trữ **7 module cốt lõi** phục vụ runtime (đi kèm `context_router.py` và `clause_condenser.py` trong [`smartschedule/nlp/`](../../smartschedule/nlp/) cho luồng hội thoại `v1.0-alpha`):

| Tệp tin | Vai trò |
| :--- | :--- |
| `__init__.py` | Khai báo export cho `hybrid_parser` và schema dùng chung |
| `hybrid_parser.py` | Bộ điều phối 6 tầng, kiểm tra cú pháp `[[...]]`, đối chiếu `ui.linked_files` |
| `parser.py` | Bộ phân tích ngữ nghĩa học vụ dựa trên luật cấu trúc |
| `regex_parser.py` | Nhận diện thời lượng, ngày/giờ hạn chót, loại bài tập song ngữ EN/VI |
| `schema.py` | Định nghĩa kiểu dữ liệu bản nháp, mã chẩn đoán và kết quả trả về |
| `tokenizer.py` | Bộ tách từ bảo toàn trích dẫn và dấu ngoặc |
| `translator.py` | Bộ định tuyến dịch VI→EN (`rule` siêu nhanh + tùy chọn CTranslate2 `nllb` / `opus_mt`) |

---

## 3. Giao Diện Chat-First `"Trợ Lý Xếp Lịch"` & Đọc Ngữ Cảnh Đa Ngày (`smartschedule/nlp/` & `ui/`)

- **Khung Hội Thoại Mặc Định Thoáng Sạch (`smartschedule/ui/index.html`, `js/chat-assistant.js`):** Mở ứng dụng vào thẳng `#viewChat` không còn nút chỉnh nhanh rối mắt hay tự chèn tiền tố; hỗ trợ trích dẫn tệp `[[filename]]` / `@[path]` kèm 1 nút duy nhất **`🗓️ Kiểm tra lịch trình`**.
- **Đọc Ngữ Cảnh 3 Tầng (`clause_condenser.py` + `context_router.py`):** Nhận diện chính xác 1 công việc xuyên nhiều ngày (`start_after` + `deadline` + `liên tục`), dùng `gemini-2.5-flash-lite` online (`0 MB` RAM máy) hoặc bộ rút gọn ngoại tuyến để cho ra tiêu đề súc tích (VD: `"Làm bài tập Computational Thinking"`), và nối với `task_tracer.py` SHA-256 để chỉnh thông số ngầm bằng câu chat.
- **An Toàn Kéo-Thả Đa Trình Duyệt:** Chặn sự kiện `dragenter`/`dragover`/`drop`/`dragend` trên cả `window` và `document` để Chrome, Edge, Firefox, Safari không mở nhầm tệp sang tab mới.

---

## 4. Kết Quả Kiểm Chứng

| Bộ kiểm thử | Lệnh chạy | Kết quả thực tế |
| :--- | :--- | :--- |
| **Kiểm tra Schema YAML** | `python -B tests/fixtures/nl_cases/validate_cases.py` | `200` ca — `All checks passed` |
| **Benchmark 200 ca Hybrid** | `python -B tests/fixtures/nl_cases/verify_hybrid_200.py` | `200/200 (100.0%)` |
| **Kiểm thử tích hợp Hybrid** | `pytest tests/logical/test_hybrid_nl_integration.py` | Đạt 100% (`12` tests) |
| **Kiểm thử tổng quát hóa khách quan** | `pytest tests/logical/test_hybrid_unbiased_generalization.py` | Đạt 100% (`9` tests) |
