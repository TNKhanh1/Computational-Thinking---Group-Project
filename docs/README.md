# SmartSchedule — Cổng Thông Tin Dành Cho Thành Viên Nhóm (`docs/README.md`)

> [!IMPORTANT]
> **ĐIỂM BẮT ĐẦU CHO ĐỢT NƯỚC RÚT HOÀN THIỆN `v1.0-alpha` (HẠN CHÓT: ĐÊM THỨ BẢY 28/11 – SÁNG CN 29/11/2026):**
> - **Thành viên nhóm:** Đọc ngay [`v1.0-alpha-plan/README.md`](../v1.0-alpha-plan/README.md) để xem lộ trình phối hợp 4 đợt không xung đột Git, sau đó mở **phiếu nhiệm vụ cá nhân của riêng bạn trong [`v1.0-alpha-plan/Sprint_Tasks/`](../v1.0-alpha-plan/Sprint_Tasks/)** (`M1` đến `M7`).
> - **AI Agent hỗ trợ bạn:** Yêu cầu Agent đọc [`agents/README.md`](../agents/README.md), [`v1.0-alpha-plan/README_agents.md`](../v1.0-alpha-plan/README_agents.md) và đúng phiếu `Sprint_Tasks/M<k>_...md` của bạn trước khi sửa mã nguồn.
> - *Lưu ý:* Các tài liệu cũ không còn sử dụng ở `v1.0-alpha` và nhật ký `001–015` đã được cất riêng tại [`docs/archive/`](archive/).

**Dự án:** SmartSchedule — Trợ Lý Xếp Lịch Học Tập Thông Minh (`CS252`, Nhóm 03 *The Seven Dwarfs*, FIT-HCMUS)  
**Giai đoạn hiện tại:** Nước rút hoàn thiện `v1.0-alpha` trên `main` (7 nhánh cá nhân độc lập file)

---

## 1. Cấu Trúc Thư Mục Mới (Thay Cho `group03-smartschedule-baseline/`)

Toàn bộ dự án đã được tách gọn ở gốc repo để chạy trực tiếp và tiết kiệm token cho AI Agent:

- [`smartschedule/`](../smartschedule/) — Mã nguồn ứng dụng (`core/`, `nlp/`, `api/`, `ui/`).
- [`data/`](../data/) — Dữ liệu mẫu (`presets/`), 10 kịch bản `T01–T10` (`scenarios/`), hiệu chỉnh `calibration/`, và SQLite `runtime/` (đã gitignore).
- [`tests/`](../tests/) — Hệ thống kiểm thử (`ui/`, `architecture/`, `logical/`, `benchmark/`, `gaps/`, `fixtures/nl_cases/`) + bộ chạy sạch `tests/clean_runner.py`.
- [`tools/`](../tools/) — Công cụ đánh giá mù `member_eval/`, benchmark `benchmarks/`, `docker/`, và file `.bat` chạy nhanh trong `tools/scripts/`.
- [`environments/`](../environments/) — Cấu hình môi trường (`requirements*.txt`, `pyproject.toml`, `.env.example`, `.agentignore`, `CODEBASE_INDEX.md` — xem [`environments/README.md`](../environments/README.md)).
- [`Project_Drafts/`](../Project_Drafts/) — Tài liệu đề xuất & kế hoạch học phần gốc (`Proposal/`, `Baseline_Plan/`, `Improve_Plan/`).
- [`v1.0-alpha-plan/`](../v1.0-alpha-plan/) — **Kế hoạch tổng `v1.0-alpha`**, kế hoạch UI/UX, kế hoạch chia thư mục, bộ đề xuất học thuật `Testing_Plan/` và máy chấm `Testing_System/`.

---

## 2. Chạy Ứng Dụng & Kiểm Thử Nhanh

```powershell
# Từ thư mục gốc D:\Projects\Computational-Thinking---Group-Project
python -B -m smartschedule.main --serve          # Chạy Web App tại http://127.0.0.1:8000
python -B tests/clean_runner.py --pass           # Chạy toàn bộ kiểm thử vận hành
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q   # Máy chấm v2.1
```

---

## 3. Tài Liệu Còn Hiệu Lực Trong `docs/`

- [`docs/requirements.md`](requirements.md) — Danh mục thư viện tại `environments/requirements.txt` & khóa API Gemini.
- [`docs/progress/README.md`](progress/README.md) — Mục lục tài liệu kỹ thuật đang hoạt động (kiến trúc 5 tầng, NL Parser Hybrid, bộ đệm Planning Fallacy, kiểm thử).
- [`docs/commit_changes.md`](commit_changes.md) — Nhật ký thay đổi gần đây nhất (bản lưu trữ cũ ở [`docs/archive/`](archive/)).
- [`docs/technical_handbook.md`](technical_handbook.md) — Sổ tay kỹ thuật chuyên sâu (JSON API & kịch bản thực nghiệm).
