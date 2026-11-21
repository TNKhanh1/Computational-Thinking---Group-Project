# ⚡ SmartSchedule (`v1.0-alpha`) — Trợ Lý Xếp Lịch Học Tập Thông Minh (Chat-First AI Scheduler)

> **Môn học:** Tư duy Tính toán (CS252) — Khoa Công nghệ Thông tin, Trường Đại học Khoa học Tự nhiên, ĐHQG-HCM (FIT-HCMUS)  
> **Nhóm thực hiện:** Group 03 (*The Seven Dwarfs*)  
> **Nhánh hiện tại:** **`v1.0-alpha/ui-ux-chat`** — Kiến trúc mô-đun sạch (`smartschedule/`, `data/`, `tests/`, `tools/`), Giao diện **Chat-First Tối Giản**, Bộ 6 Solvers Công Thái Học, Mô hình AI Đọc Ngữ Cảnh Online Siêu Nhẹ (`gemini-2.5-flash-lite` + `clause_condenser`), **`194/194`** Verification Tests, **`39/39`** `Testing_System v2.1 + Fuzz v2` Tests, và **`200/200`** NL Benchmark Cases.

---

## 📌 Điểm Bắt Đầu Nhanh

- **Thành viên nhóm:** Đọc [`v1.0-alpha-plan/README.md`](v1.0-alpha-plan/README.md) (bản tóm tắt toàn bộ kế hoạch `v1.0-alpha`, bản đồ thư mục mới & **checklist `[x]` / `[ ]`** theo dõi tiến độ).
- **AI Coding Agents:** Chỉ cần đọc [`agents/README.md`](agents/README.md) và [`v1.0-alpha-plan/README_agents.md`](v1.0-alpha-plan/README_agents.md) (cấu hình môi trường & chỉ mục token nằm trong [`environments/`](environments/)).

---

## 📂 Cấu Trúc Kho Lưu Trữ (Repository Structure)

```text
Computational-Thinking---Group-Project/
├── .gitignore                             # Quy tắc bỏ qua .env, CSDL SQLite, cache
├── README.md                              # Tổng quan dự án (tệp này)
│
├── environments/                          # ⚙️ CẤU HÌNH MÔI TRƯỜNG & CHỈ MỤC AI AGENT
│   ├── README.md                          # Giải thích từng thành phần môi trường
│   ├── requirements.txt & requirements-nllb.txt
│   ├── pyproject.toml                     # Cấu hình gói smartschedule* & pytest pythonpath
│   ├── .env.example                       # Mẫu GEMINI_API_KEY (copy thành environments/.env)
│   └── .agentignore & CODEBASE_INDEX.md   # Tối ưu token & bản đồ mã nguồn cho AI
│
├── smartschedule/                         # ⭐ MÃ NGUỒN ỨNG DỤNG CHÍNH (Installable Package)
│   ├── main.py                            # CLI & launcher server FastAPI
│   ├── core/                              # Tầng 1–3: models, config, utils, estimate_buffer, calibration,
│   │                                      #          task_tracer (SHA-256), storage, ics_importer, controller,
│   │                                      #          overload_triage & solvers/ (6 thuật toán V3 + ALNS)
│   ├── nlp/                               # Tầng 4A: context_router (Online Model), clause_condenser,
│   │                                      #          parser_controller (M1), hybrid_pipeline/ (7 modules)
│   ├── api/                               # Tầng 4B: FastAPI (app.py), chat/ (handlers, thinking_stage,
│   │                                      #          edge_cases), auth, health_v21, v3_services, test_showcase
│   └── ui/                                # Giao diện Chat-First Tối giản (index.html, app.js, js/, css/)
│
├── data/                                  # Bộ dữ liệu mẫu (presets/), kịch bản T01–T10 (scenarios/),
│                                          # calibration/ & SQLite runtime/ (đã gitignore)
├── tests/                                 # Tầng 5: Kiểm thử sạch (clean_runner.py, test_studio.py,
│                                          #         ui/, architecture/, logical/, benchmark/, gaps/, fixtures/)
├── tools/                                 # Cổng chấm mù member_eval/, benchmarks/, docker/, scripts/*.bat
│
├── v1.0-alpha-plan/                       # 🎯 KẾ HOẠCH TRUNG TÂM v1.0-alpha
│   ├── README.md & README_agents.md       # Tổng hợp + Checklist theo dõi cho thành viên & AI Agents
│   ├── folder_division_plan.md            # Bản thiết kế chia thư mục giảm tải token
│   ├── UI_Rebuild_Plan/                   # Đặc tả Chat-First UI/UX & Merged Context-Parsing Model
│   ├── Testing_Plan/                      # Báo cáo Benchmark, CT_Rationale_Log, Evaluation Plan & papers/
│   └── Testing_System/                    # Máy chấm tự động 4 Trụ Cột v2.1 + Fuzz v2 (39/39 tests)
│
├── agents/                                # 🤖 Cổng Tài Liệu Cho AI Agent (agents/README.md entrypoint)
├── docs/                                  # 📘 Trung Tâm Tài Liệu Tiếng Việt (docs/README.md & progress/)
└── Project_Drafts/                        # 📚 Bản thảo & đề xuất học phần cũ (Proposal, Baseline_Plan, Improve_Plan)
```

---

## 🌟 Tính Năng Nổi Bật Trong `v1.0-alpha`

1. **Giao Diện Chat-First Tối Giản (`"Trợ lý xếp lịch"`):** Mở app vào thẳng khung hội thoại thoáng mắt; thanh trượt dọc bên trái thu gọn 100%; Lịch Tuần có `"Trợ lý tinh chỉnh trực tiếp"` bên phải co giãn mượt mà; nút **`🗓️ Kiểm tra lịch trình`** chuẩn hóa.
2. **Developer Mode (`💭 Quá trình suy nghĩ`):** Hiển thị tóm tắt phân tích ngữ cảnh, lý do loại trừ các thuật toán mù năng lượng kém hơn (`EDF`/`LST`/`WSPT`) và theo dõi các thông số ngầm truy vết qua mã băm **`SHA-256`**.
3. **Bộ Phân Tích Ngữ Cảnh 3 Tầng Siêu Nhẹ:** Hợp nhất bộ tách mệnh đề/xuyên ngày (`< 2 ms`) + mô hình AI đọc ngữ cảnh online (`gemini-2.5-flash-lite`, `0 MB` RAM máy) + bộ cô đọng tiêu đề tiếng Việt offline (`clause_condenser.py`).
4. **Mô Hình Lưới 672/1344 Slots & 6 Bộ Giải Công Thái Học:** Tuân thủ tuyệt đối $H_1$–$H_5$, bảo vệ $\ge 6\text{h}$ ngủ, đệm Planning Fallacy ($\alpha_{\text{light}}=1.20 / \alpha_{\text{heavy}}=1.35$), hiệu chuẩn EWMA từ check-in thực tế M7, và cảnh báo rõ `DEADLOCK` / `DENSE_WARNING`.

---

## 🚀 Cài Đặt, Chạy Ứng Dụng & Kiểm Thử (Từ Thư Mục Gốc)

```powershell
# 1. Cài đặt môi trường .venv (Windows 1-click) hoặc thủ công:
.\tools\scripts\setup_env.bat
# (Hoặc: pip install -r environments/requirements.txt)

# 2. (Tùy chọn) Bật mô hình AI đọc ngữ cảnh online bằng Gemini API Key miễn phí:
Copy-Item environments/.env.example environments/.env    # Dán GEMINI_API_KEY=... vào environments/.env

# 3. Khởi chạy Web App chính (http://127.0.0.1:8000):
python -B -m smartschedule.main --serve

# 4. Khởi chạy Cổng Chấm Mù Đa Thành Viên (http://127.0.0.1:8010):
python -B -m uvicorn tools.member_eval.app:app --host 127.0.0.1 --port 8010

# 5. Chạy toàn bộ Kiểm thử & Benchmark:
python -B tests/clean_runner.py --pass
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
python -B tests/fixtures/nl_cases/verify_hybrid_200.py
python -B tools/benchmarks/benchmark_runner.py
```

---

## 📚 Tài Liệu Chi Tiết

| Đối Tượng | Điểm Bắt Đầu | Nội Dung |
| :--- | :--- | :--- |
| **Thành viên Nhóm 03** | [`v1.0-alpha-plan/README.md`](v1.0-alpha-plan/README.md) & [`docs/README.md`](docs/README.md) | Kế hoạch `v1.0-alpha`, checklist tiến độ `[x]`/`[ ]`, giải thích dễ hiểu bằng tiếng Việt. |
| **AI Agents & Developers** | [`agents/README.md`](agents/README.md) & [`v1.0-alpha-plan/README_agents.md`](v1.0-alpha-plan/README_agents.md) | Quy tắc bất biến `INV-1..6`, cấu trúc tầng `smartschedule/`, lệnh test & checklist kỹ thuật. |
| **Kỹ sư API & Học thuật** | [`docs/technical_handbook.md`](docs/technical_handbook.md) & [`v1.0-alpha-plan/Testing_Plan/`](v1.0-alpha-plan/Testing_Plan/) | Hợp đồng JSON API, báo cáo `220` đề × `6` thuật, nhật ký Tư duy Tính toán `CT_Rationale_Log.md`. |

---

## 📝 Lịch Sử Commit Tái Cấu Trúc (`v1.0-alpha/ui-ux-chat`)

| Commit | Phạm Vi | Nội Dung Tóm Tắt |
| :--- | :--- | :--- |
| **`e56ab06`** | Chia thư mục & `environments/` | Chuyển đổi `group03-smartschedule-baseline/` thành `smartschedule/`, `data/`, `tests/`, `tools/` và gom toàn bộ cấu hình môi trường vào `environments/`. |
| **`5a96211`** | `Project_Drafts/` | Gom nhóm các tài liệu đề xuất học phần ban đầu (`Baseline_Plan/`, `Improve_Plan/`, `Proposal/`) vào `Project_Drafts/`. |
| **`7a76ef3`** | `agents/`, `docs/`, `v1.0-alpha-plan/` | Làm mới cổng hướng dẫn `v1.0-alpha`, dọn sạch các mục/link lỗi thời khỏi `README.md` & `progress/`, cập nhật `requirements.md` và lưu trữ nhật ký cũ `001–015`. |

---
*Dự án học phần Tư duy Tính toán (CS252) — Nhóm 03 The Seven Dwarfs, FIT-HCMUS.*
