# Bộ Phân Tích Ngôn Ngữ Tự Nhiên Hybrid EN/VI & UX Modal Công Việc

> **Thành phần:** `NL_Parser_Package/` + `src/nl_parser.py` (M1) + `web/api.py` + `web/index.html` + `web/app.js`  
> **Trạng thái:** Đang vận hành ổn định — `200/200` ca YAML (`rule`, `458.1 ms`), `17/17` bài test tích hợp & tổng quát hóa khách quan đạt 100%.

---

## 1. Kiến Trúc Đường Ống Hybrid 6 Tầng

Bộ phân tích Hybrid EN/VI kết hợp pipeline offline 6 tầng (`NL_Parser_Package/hybrid_parser.py`) với tầng tiếp hợp M1 (`src/nl_parser.py`) và hộp thoại Thêm Công Việc (`web/index.html`, `web/app.js`).

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

## 2. Cấu Trúc Gói `NL_Parser_Package/` Đang Triển Khai

Thư mục `group03-smartschedule-baseline/NL_Parser_Package/` chỉ lưu trữ **7 module cốt lõi** phục vụ runtime (các file thừa, tài liệu `.md` nội bộ và cache đã được dọn sạch):

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

## 3. Nâng Cấp Giao Diện Modal & Kéo-Thả Tệp Đa Trình Duyệt

- **Mở rộng Modal & Tự động Lưu Nháp:** `#stTaskModal` rộng thoáng hơn (`max-w-3xl lg:max-w-4xl`, `max-h-[90vh]`, cuộn nội dung mượt), có nút đóng `✕` nổi bật ở góc phải trên + Esc/click nền, tự động lưu nháp vào `localStorage` (`#stModalDraftBadge`, `#btnStClearDraft`).
- **Hộp Liên Kết Tệp & Cảnh Báo Trích Dẫn Đỏ:** Gộp khung nhập `#stNlPromptBox` và `#stNlFileLinkBox` theo kiểu ô chat, cho phép kéo tệp vào hoặc bấm chèn `[[filename]]` để bảo toàn tên tệp không mất dữ liệu, đồng thời tô đỏ và liệt kê chi tiết khi sai định dạng hoặc thiếu tệp đính kèm (`CRITICAL_CITATION_CODES`, `HYBRID_DIAG_LABELS`).
- **Task ID Phụ Thuộc & Cắt Nhỏ Ngay Trên Prompt:** Bổ sung ô nhập `Task ID` (`#stInpTaskId`) và danh sách chip bấm chọn `#stExistingTaskIdChips` cho mục **"Task cần phải làm trước đó (Task ID)"**; đưa nút `✂️ Cho phép cắt nhỏ` | `🔒 Làm liền 1 buổi` lên thẳng vùng nhập tự nhiên và ẩn mục `"Ưu tiên Solver"` trùng lặp.
- **Khắc Phục Mở Tab Mới Khi Kéo-Thả Trên Edge/Chrome/Firefox/Safari:** Chặn đồng bộ `dragenter`/`dragover`/`drop`/`dragend` ở cả `window` và `document`, bọc `try { dropEffect = ... }`, fallback `dt.items`, xử lý `decodeURIComponent`, và lọc `dragleave` với `!this.contains(event.relatedTarget)`.

---

## 4. Kết Quả Kiểm Chứng

| Bộ kiểm thử | Lệnh chạy | Kết quả thực tế |
| :--- | :--- | :--- |
| **Kiểm tra Schema YAML** | `python -B verification_tests/NL_Parser_test_cases/validate_cases.py` | `200` ca — `All checks passed` |
| **Benchmark 200 ca Hybrid** | `python -B verification_tests/NL_Parser_test_cases/verify_hybrid_200.py` | `200/200 (100.0%)` trong `458.1 ms` |
| **Kiểm thử tích hợp Hybrid** | `pytest verification_tests/logical_tests/test_hybrid_nl_integration.py` | Nằm trong `142/142` (`8` tests) |
| **Kiểm thử tổng quát hóa khách quan** | `pytest verification_tests/logical_tests/test_hybrid_unbiased_generalization.py` | Nằm trong `142/142` (`9` tests) |
