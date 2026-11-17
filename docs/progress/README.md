# SmartSchedule — Mục Lục Tài Liệu Tiến Độ Dự Án (Dành Cho Thành Viên Nhóm)

**Thư mục:** `docs/progress/`  
**Ngôn ngữ:** Tiếng Việt  
**Đối tượng sử dụng:** Tất cả thành viên Nhóm 03 (*The Seven Dwarfs*) & Các AI Agent hỗ trợ  

---

## Danh Mục Tài Liệu Hướng Dẫn

1. **[`kien_truc_he_thong.md`](kien_truc_he_thong.md)**
   - Giải thích kiến trúc 5 tầng của hệ thống (Model, Solver, Controller, Web API, Test Suite).
   - 6 quy tắc bất biến sống còn (INV-1 đến INV-6) mà mọi thành viên và AI Agent không được vi phạm khi viết code.

2. **[`ke_hoach_baseline.md`](ke_hoach_baseline.md)**
   - Tóm lược bản mốc chuẩn Baseline V0.
   - Cơ chế lưới 672 ô (15 phút/ô), 5 ràng buộc cứng $H_1$–$H_5$.
   - 3 thuật toán tham lam (EDF, LST, WSPT) và 10 kịch bản kiểm thử T01–T10.

3. **[`ke_hoach_cai_tien.md`](ke_hoach_cai_tien.md)**
   - Tóm lược kế hoạch nâng cấp ứng dụng thân thiện với sinh viên theo `Improve_Plan`.
   - 7 khoảnh khắc sử dụng ($M_1$–$M_7$).
   - Các nâng cấp tâm lý học & nhịp sinh học (khớp giờ năng lượng, nghỉ 15p, đệm $1.25\times$, hủy thói quen trước).
   - 5 bài test mục tiêu đang chờ cài đặt mã nguồn.

4. **[`kiem_thu_va_benchmark.md`](kiem_thu_va_benchmark.md)**
   - Hướng dẫn chạy và theo dõi hệ thống kiểm thử tự động (đã mở rộng lên **142 bài test `pytest` đạt 100%**, gồm `136 --pass`, `5 --gaps`, `1` ca `Q9` Phương án A, và **200 ca YAML Hybrid NL Parser**).
   - Hướng dẫn dùng ứng dụng đồ họa Test Studio (`run_test_studio.bat`) và dòng lệnh batch.
   - Cách đọc màn hình console chẩn đoán lỗi mới (rõ ràng, không rác terminal).

5. **[`requirements.md`](../requirements.md)**
   - Giải thích chi tiết mục đích các thư viện (`fastapi`, `uvicorn`, `pydantic`, `pytest`, `httpx`, `python-dateutil`, `google-genai`, `python-dotenv`, `PyYAML`, `ctranslate2`, `sentencepiece`, `huggingface-hub`).
   - Phân định tầng kiến trúc được phép dùng và hướng dẫn cài đặt tự động 1-click bằng `setup_env.bat`.
   - Quy định bắt buộc đồng bộ đồng thời khi thêm thư viện mới.

6. **[`tinh_nang_dem_thoi_gian.md`](tinh_nang_dem_thoi_gian.md)**
   - Giải thích đơn giản thói quen ước lượng (Hiếm khi $\times 1.00$, Thỉnh thoảng $\times 1.10$, Thường xuyên $\times 1.25$).
   - Quy tắc làm tròn ô 15 phút thông minh không làm đội giờ việc nhỏ và 34 bài test đã chạy xanh.

7. **[`giao_dien_sinh_vien.md`](giao_dien_sinh_vien.md)**
   - Hướng dẫn dùng Chế độ Sinh Viên mới: Nút chuyển Dual-Mode, 3 góc nhìn (Tuần, Hôm nay, Hàng đợi), ghim việc (📌), điểm danh (✔️), và xem lý do (💡).

8. **[`bo_phan_tich_ngon_ngu_hybrid.md`](bo_phan_tich_ngon_ngu_hybrid.md)**
   - Kiến trúc pipeline Hybrid EN/VI 6 tầng (`NL_Parser_Package/` + M1), ánh xạ khẩn cấp `1=Khẩn..4=Thấp -> 5..1`, và backend dịch VI→EN (`rule`, `nllb`, `opus_mt`).
   - Hướng dẫn Modal Công Việc nâng cấp (tự động lưu nháp, trích dẫn `[[filename]]` không mất dữ liệu, kéo-thả đa trình duyệt, `Task ID` phụ thuộc và nút cắt nhỏ).

---

## Nhật Ký Cập Nhật Mã Nguồn & Quy Định Cho AI Agent
Để xem lịch sử các thay đổi và quy định bắt buộc đối với AI Agent khi hỗ trợ thành viên, vui lòng xem:
👉 **[`docs/commit_changes.md`](../commit_changes.md)**
