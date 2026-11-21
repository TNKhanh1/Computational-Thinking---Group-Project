# SmartSchedule `v1.0-alpha` — Kế Hoạch Tổng Thể & Bảng Theo Dõi Nhóm (`v1.0-alpha-plan/README.md`)

> [!IMPORTANT]
> **TÀI LIỆU TRỌNG TÂM CHO MỌI THÀNH VIÊN NHÓM 03 (*The Seven Dwarfs*):**
> File này là **bức tranh tổng hợp đầy đủ nhất của giai đoạn `v1.0-alpha`** (nhánh `v1.0-alpha/ui-ux-chat`), kết nối toàn bộ kế hoạch chia lại thư mục, tái thiết kế giao diện Chat-First, động cơ thuật toán & kiểm thử, và nâng cấp mô hình AI đọc ngữ cảnh online.
> - **Dành cho AI Agent hỗ trợ bạn:** Yêu cầu Agent đọc [`README_agents.md`](README_agents.md) (và [`agents/README.md`](../agents/README.md)).
> - **Quy tắc theo dõi & đóng góp ý tưởng:** Khi hoàn thành hạng mục nào, hãy **đánh dấu `[x]`** trực tiếp vào **Checklist Tiến Độ (Mục 4)** bên dưới. **Nếu thành viên nhóm hoặc AI Agent có ý tưởng tốt hơn để cải tiến kế hoạch `v1.0-alpha` (giao diện, thuật toán hay mô hình đọc ngữ cảnh), hãy tự do đề xuất và cập nhật trực tiếp vào tài liệu này!**

---

## 1. Bốn Trụ Cột Cốt Lõi Của `v1.0-alpha`

### Trụ cột 1: Tái Cấu Trúc & Phân Chia Thư Mục (`folder_division_plan.md`)
- **Mục tiêu:** Xóa bỏ thư mục cũ `group03-smartschedule-baseline/` dài dòng và gom dữ liệu nặng vào đúng chỗ để giảm mạnh lượng token AI Agent đọc thừa, giúp nhiều bạn code song song không đụng file nhau.
- **Kết quả triển khai:**
  - Tách gọn mã nguồn ứng dụng thành [`smartschedule/`](../smartschedule/) với 4 phần rõ rệt: `core/`, `nlp/`, `api/`, `ui/`.
  - Tách toàn bộ JSON dữ liệu mẫu, 10 kịch bản `T01–T10`, hiệu chỉnh và CSDL SQLite sang [`data/`](../data/) (được [`environments/.agentignore`](../environments/.agentignore) che bớt dữ liệu thô để tiết kiệm token).
  - Gom toàn bộ bài test về [`tests/`](../tests/) và công cụ đánh giá/Docker/batch script về [`tools/`](../tools/).
  - Nhóm các tài liệu bản thảo học phần cũ (`Proposal/`, `Baseline_Plan/`, `Improve_Plan/`) vào [`Project_Drafts/`](../Project_Drafts/) và toàn bộ tệp cấu hình môi trường/chỉ mục (`.agentignore`, `CODEBASE_INDEX.md`, `pyproject.toml`, `requirements*.txt`, `.env.example`) vào [`environments/`](../environments/) — chỉ giữ `.gitignore` và `README.md` ở gốc repo.
  - Chia nhỏ 2 tệp quá dài (`chat_service.py` 72 KB $\to$ [`smartschedule/nlp/clause_condenser.py`](../smartschedule/nlp/clause_condenser.py), [`context_router.py`](../smartschedule/nlp/context_router.py) và [`smartschedule/api/chat/`](../smartschedule/api/chat/); `app.css` 2082 dòng $\to$ `shell.css`, `dev-panel.css`, `calendar.css`, `chat.css`).
  - Xem chi tiết kiến trúc chia thư mục tại [`folder_division_plan.md`](folder_division_plan.md) và bản đồ tra cứu nhanh [`environments/CODEBASE_INDEX.md`](../environments/CODEBASE_INDEX.md).

### Trụ cột 2: Giao Diện Chat-First Tối Giản Tuyệt Đối ([`UI_Rebuild_Plan/proposal_pipeline.md`](UI_Rebuild_Plan/proposal_pipeline.md))
- **Mở app vào thẳng `"Trợ lý xếp lịch"` (`#viewChat`):** Không gian trống trải thân thiện giống Antigravity; bấm logo `SS SmartSchedule` ở góc trên trái luôn quay về khung chat.
- **Thanh điều hướng dọc bên trái (`#leftNavSidebar`):** Gồm 3 mục (`Trợ lý xếp lịch`, `Lịch Trình Tuần`, `Danh Sách Việc`) + công tắc `Developer Mode` ở đáy; khi bấm đóng sẽ **ẩn 100%** (đã xóa mục `"Chuyển nhanh tuần"` gây rối).
- **Menu Cài đặt gọn nhẹ & Khung gõ sạch:** Đã bỏ `"Nền năng lượng sinh học"` và `"Tiện ích nhanh"` khỏi Cài đặt; bỏ thanh `"Chỉnh nhanh việc đã lưu"`; bấm 2 thẻ gợi ý không tự chèn tiền tố thừa vào ô nhập; mỗi câu trả lời giữ 1 nút hành động duy nhất **`🗓️ Kiểm tra lịch trình`**.
- **Lịch Tuần + `"Trợ lý tinh chỉnh trực tiếp"` bên phải:** Đã sửa lệch nút/nhãn `"Hôm nay"`; bấm mũi tên **`⇥`** ở khung chat phải sẽ thu gọn ngay khung chat để mở rộng lịch tuần, và nút **`💬 Mở trợ lý`** tự ẩn hoàn toàn khi khung chat đang mở.
- **Chế độ `Developer Mode` (`💭 Quá trình suy nghĩ`):** Hiển thị hộp tóm tắt quá trình AI hiểu ngữ cảnh, **loại trừ tập thuật toán trội kém hơn** và giải thích thông số ẩn đang tinh chỉnh.

### Trụ cột 3: Thiết Kế Thuật Toán & Kiểm Định Chất Lượng (`smartschedule/core/solvers/` & [`Testing_Plan/`](Testing_Plan/))
- **Lưới rời rạc 672/1344 ô (15 phút/ô, 7–14 ngày)** kết hợp hạt nhân công thái học [`ergonomic_engine.py`](../smartschedule/core/solvers/ergonomic_engine.py) và **6 bộ giải** (`EDF` mốc V0, `LST` & `WSPT` mù năng lượng V3, `SCORED_GREEDY` mặc định nhanh theo nhịp sinh học, `BACKTRACK` nhánh-cận, và `HYBRID_ALNS` tối ưu sâu Ruin-and-Recreate).
- **Tập trung vào Tập Thuật Toán Trội (Dominant Subset Pruning):** Với lịch có tiêu chí nhịp sinh học/nặng nhẹ, bộ giải thông minh chứng minh nhánh mù năng lượng (`EDF`/`WSPT`/`LST`) luôn thua ở trường hợp tốt nhất so với nhóm nhịp sinh học (`SCORED_GREEDY`/`HYBRID_ALNS`) nên tự động lọc tập ứng viên phù hợp.
- **Bảo vệ Hành vi Người học:** Bộ đệm Planning Fallacy (`RARELY`/`SOMETIMES`/`OFTEN` + `COGNITIVE_LOAD` $\alpha=1.20/1.35$), tính lại thời gian làm tiếp kết hợp lịch sử M7 EWMA, **truy vết công việc bằng mã vân tay `SHA-256`** (`task_tracer.py`) để chỉnh tiêu chí ngầm bằng câu chat, và xử lý 2 ca biên kẹt lịch (`DEADLOCK` báo đỏ + `DENSE_WARNING` báo vàng).
- **Máy chấm tự động `Testing_System v2.1` + Chương trình Chấm Mù [`tools/member_eval/`](../tools/member_eval/):** Đánh giá 4 trụ cột + `ICEE` trên `Regimes R1–R6` và `Fuzz v2`.

### Trụ cột 4: Nâng Cấp Mô Hình Đọc Ngữ Cảnh Hiệu Quả & Miễn Phí (`smartschedule/nlp/`)
- **Hiện trạng đang chạy (`v1.0-alpha`):** Hợp nhất bộ tách vế & xuyên ngày [`clause_condenser.py`](../smartschedule/nlp/clause_condenser.py) (`< 2 ms`, xử lý chuẩn câu phức thành **1 công việc duy nhất** như **`"Làm bài tập Computational Thinking"`**) + mô hình Gemini qua `GEMINI_API_KEY` (`context_router.py`) và bộ rút gọn ngoại tuyến.
- **Định hướng nâng cấp bằng các mô hình miễn phí, tối ưu RAM & tốc độ (thuộc Tầng 4 `smartschedule/nlp/`, không ảnh hưởng `INV-5` của Solver):**
  - **Transformer Encoders (Hugging Face):** `DeBERTa`, `RoBERTa`, `BERT`, `StructBERT` cho bài toán trích xuất thực thể (`NER`), hỏi-đáp (`QA`), phân loại ngữ cảnh & sắc thái/phủ định (như `cardiffnlp/twitter-roberta-base-sentiment-latest`).
  - **spaCy Pipelines (giấy phép MIT miễn phí):** Tách phụ thuộc cú pháp (dependency parsing), gán nhãn từ loại (`POS`), nhận diện thực thể (`NER`) hỗ trợ >75 ngôn ngữ rất nhẹ và nhanh cho tách tên việc khỏi cụm thời gian.
  - **Stanza & Stanford CoreNLP:** Phân tích cú pháp phụ thuộc, cú pháp cấu thành và ngôn ngữ học đa ngôn ngữ mã nguồn mở.
  - **Vision-Language & Document Parsers (`Qwen2-VL`, `Docling`):** Trích xuất cấu trúc tài liệu nhiều trang / file PDF đề bài, đề cương đính kèm mà không cần phụ thuộc API trả phí.

---

## 2. Bản Đồ Thư Mục & Tệp Cốt Lõi Trong Dự Án Mới

| Khu vực | Đường dẫn chính xác | Vai trò & Khi nào cần đụng tới |
| :--- | :--- | :--- |
| **Lõi Dữ liệu & Thuật toán (Layer 1–3)** | [`smartschedule/core/`](../smartschedule/core/)<br>├── `config.py`, `models.py`, `utils.py`<br>├── `task_tracer.py`, `estimate_buffer.py`, `calibration.py`<br>├── `controller.py`, `overload_triage.py`, `storage.py`, `ics_importer.py`<br>└── `solvers/` (`edf`, `lst`, `wspt`, `scored_greedy`, `backtracking`, `hybrid_alns`, `ergonomic_engine`, `local_repair`, `registry`) | Sửa dữ liệu, quy tắc đệm, truy vết SHA-256 hoặc nghiên cứu thuật toán.<br>**Lưu ý:** Giữ nguyên `INV-1..6` (không import `api`/`nlp` vào `core/`). |
| **Xử lý Ngôn ngữ & Ngữ cảnh (Layer 4A)** | [`smartschedule/nlp/`](../smartschedule/nlp/)<br>├── `context_router.py` (gọi `gemini-2.5-flash-lite`)<br>├── `clause_condenser.py` (cô đọng tiêu đề & tách vế)<br>├── `parser_controller.py` (M1 Gemini + Offline)<br>└── `hybrid_pipeline/` (7 module pipeline 6 tầng) | Tinh chỉnh câu chat tiếng Việt/Anh, rút gọn tiêu đề, hoặc nâng cấp mô hình đọc ngữ cảnh online. |
| **API Web & Trợ lý Chat (Layer 4B)** | [`smartschedule/api/`](../smartschedule/api/)<br>├── `app.py` (FastAPI entrypoint)<br>├── `chat/` (`handlers.py`, `thinking_stage.py`, `edge_cases.py`)<br>└── `auth.py`, `health_v21.py`, `v3_services.py`, `test_showcase.py` | Thêm/sửa API, luồng hỏi lại khi thiếu giờ, hộp Suy nghĩ Developer Mode, hoặc xử lý ca biên `DEADLOCK`/`DENSE_WARNING`. |
| **Giao diện Người dùng (Layer 4B)** | [`smartschedule/ui/`](../smartschedule/ui/)<br>├── `index.html`, `app.js`<br>├── `js/` (`chat-assistant.js`, `render-calendar.js`, `render-list.js`, `modals.js`, `state.js`, `api.js`, ...)<br>└── `css/` (`tokens.css`, `shell.css`, `dev-panel.css`, `calendar.css`, `chat.css`, `app.css`) | Tinh chỉnh màn hình Trợ lý xếp lịch, Lịch tuần, Trợ lý bên phải, giao diện di động/responsive. |
| **Dữ liệu & CSDL** | [`data/`](../data/)<br>├── `presets/` (`sample_week_*`, `lan_week_*`)<br>├── `scenarios/` (`t01_*` .. `t10_*`)<br>├── `calibration/` (`alpha_grid_calibration.json`)<br>└── `runtime/` (`local_state.db` — đã gitignore) | Thêm kịch bản test hoặc xem dữ liệu mẫu (AI Agent tránh đọc hàng loạt file trong đây). |
| **Kiểm thử Tự động (Layer 5)** | [`tests/`](../tests/)<br>├── `clean_runner.py`, `test_studio.py`, `conftest.py`<br>├── `ui/`, `architecture/`, `logical/`, `benchmark/`, `gaps/`<br>└── `fixtures/nl_cases/` (200 câu mẫu + `verify_hybrid_200.py`) | Chạy kiểm tra trước khi báo xong việc hoặc thêm unit test mới. |
| **Môi trường & Đề xuất cũ** | [`environments/`](../environments/) (`requirements*.txt`, `pyproject.toml`, `.env.example`, `.agentignore`, `CODEBASE_INDEX.md`)<br>[`Project_Drafts/`](../Project_Drafts/) (`Proposal/`, `Baseline_Plan/`, `Improve_Plan/`) | Cấu hình môi trường chạy app/test và lưu trữ hồ sơ đề xuất gốc. |
| **Công cụ & Kế hoạch** | [`tools/`](../tools/) (`member_eval/`, `benchmarks/`, `docker/`, `scripts/*.bat`)<br>[`v1.0-alpha-plan/`](./) (`UI_Rebuild_Plan/`, `Testing_Plan/`, `Testing_System/`, `folder_division_plan.md`) | Chạy chấm mù đa thành viên (`8010`), benchmark `T01–T10`, hoặc đọc báo cáo học thuật / máy chấm `v2.1`. |

---

## 3. Lệnh Chạy Nhanh Hàng Ngày (Từ Thư Mục Gốc Repo)

```powershell
# 1. Cài đặt môi trường & (tùy chọn) bật API Key cho mô hình đọc ngữ cảnh online
.\tools\scripts\setup_env.bat
Copy-Item environments/.env.example environments/.env    # Dán GEMINI_API_KEY=... vào environments/.env

# 2. Chạy Web App SmartSchedule (http://127.0.0.1:8000)
python -B -m smartschedule.main --serve

# 3. Chạy Chương trình Chấm Mù thành viên (http://127.0.0.1:8010)
.\tools\scripts\run_member_eval.bat

# 4. Chạy toàn bộ Kiểm thử (bắt buộc xanh trước khi hoàn thành task)
python -B tests/clean_runner.py --pass
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
python -B tests/fixtures/nl_cases/verify_hybrid_200.py
```

---

## 4. Bảng Checklist Tiến Độ `v1.0-alpha` (Thành Viên & AI Agent Tự Tích `[x]` Khi Xong)

> Hãy đánh dấu `[x]` ngay tại dòng bạn vừa hoàn thành (và cập nhật song song trong [`README_agents.md`](README_agents.md) nếu cần).

### A. Tái Cấu Trúc Thư Mục & Hạ Tầng (`folder_division_plan.md`)
- [x] Di chuyển toàn bộ mã nguồn khỏi `group03-smartschedule-baseline/` sang `smartschedule/`, `data/`, `tests/`, `tools/` (giữ toàn vẹn lịch sử Git & bảo toàn `.env`, `data/runtime/local_state.db`).
- [x] Chia nhỏ `chat_service.py` $\to$ `smartschedule/nlp/{clause_condenser,context_router}.py` + `smartschedule/api/chat/{thinking_stage,edge_cases,handlers}.py`.
- [x] Chia nhỏ `app.css` $\to$ `smartschedule/ui/css/{shell,dev-panel,calendar,chat}.css` và gom cấu hình môi trường (`pyproject.toml`, `.agentignore`, `CODEBASE_INDEX.md`, `requirements*.txt`, `.env.example`) vào [`environments/`](../environments/), gom bản thảo cũ vào [`Project_Drafts/`](../Project_Drafts/).
- [x] Cập nhật đường dẫn cho toàn bộ kiểm thử & xác nhận xanh 100%: `tests/clean_runner.py --pass` (`194/194`), `Testing_System/tests` (`39/39`), `verify_hybrid_200.py` (`200/200`), JS `node --check`.
- [x] Đóng gói các commit tái cấu trúc thư mục (`e56ab06`) & `Project_Drafts/` (`5a96211`); đồng bộ cổng tài liệu `agents/`, `docs/`, `v1.0-alpha-plan/`.
- [ ] Kiểm tra chéo toàn bộ nhánh `v1.0-alpha/ui-ux-chat` trước khi mở Pull Request gộp vào `main`.

### B. Giao Diện Chat-First & Trải Nghiệm Người Dùng (`UI_Rebuild_Plan/`)
- [x] Mặc định mở app vào `"Trợ lý xếp lịch"` (`#viewChat`); logo `SS SmartSchedule` quay thẳng về khung chat.
- [x] Thanh trượt dọc bên trái thu gọn 100% (ẩn luôn Developer Mode khi đóng, bỏ `"Chuyển nhanh tuần"`), gọn menu Cài đặt (bỏ `"Nền năng lượng sinh học"` & `"Tiện ích nhanh"`).
- [x] Xóa `"Chỉnh nhanh việc đã lưu"`, bỏ tự chèn tiền tố ở 2 thẻ gợi ý, giữ 1 nút phản hồi duy nhất **`🗓️ Kiểm tra lịch trình`**.
- [x] Sửa lệch hộp `"Hôm nay"` trên Lịch Tuần; nút mũi tên `⇥` thu gọn `"Trợ lý tinh chỉnh trực tiếp"` tại chỗ; ẩn triệt để `"💬 Mở trợ lý"` khi khung chat phải đang mở.
- [x] Hộp **💭 Quá trình suy nghĩ (Thinking Stage)** khi bật Developer Mode giải thích ngữ cảnh & lý do loại tập thuật toán kém.
- [ ] **Kiểm thử tương tác trực tiếp trên trình duyệt Chrome/Edge** bởi từng thành viên nhóm (xác nhận kéo-thả, thu gọn thanh trái/phải, responsive mobile).

### C. Nâng Cấp Mô Hình Đọc Ngữ Cảnh & Truy Vết SHA-256 (`smartschedule/nlp/`)
- [x] Truy vết từ khóa bằng mã vân tay `SHA-256` (`smartschedule/core/task_tracer.py`) cho câu lệnh chỉnh độ nặng, chia nhỏ, nhịp sinh học.
- [x] Fix lỗi câu 1 việc xuyên nhiều ngày (*"từ 19h thứ 3 tới 21h thứ 5, 2 tiếng liên tục"*) không bị tách nhầm thành 3 việc và rút gọn sạch tiêu đề (`"Làm bài tập Computational Thinking"`).
- [x] Bổ sung hộp thoại hỏi lại khi thiếu thông tin (Multi-turn Clarification) & tính lại thời gian làm tiếp có đệm thói quen/M7 EWMA.
- [ ] **Thử nghiệm & tích hợp mô hình đọc ngữ cảnh miễn phí tối ưu RAM/tốc độ:** So sánh thực nghiệm **Transformer Encoders** (`DeBERTa`, `RoBERTa`, `BERT`, `StructBERT`, `cardiffnlp/twitter-roberta-base-sentiment-latest`), **spaCy** (MIT), và **Stanza / CoreNLP** trên Tầng 4 để thay thế/nâng cấp lớp đọc ngữ cảnh mà vẫn giữ ngưỡng bộ nhớ `INV-5` (`< 350 KB` heap ở Solver).
- [ ] **Thử nghiệm phân tích tài liệu đính kèm cục bộ:** Đánh giá **`Docling`** / **`Qwen2-VL`** cho đề bài, lịch học PDF nhiều trang khi người dùng kéo thả tệp vào khung chat.
- [ ] **Đề xuất & đóng góp thêm ý tưởng:** Thành viên nhóm hoặc AI Agent có phương án gọn nhẹ hơn có thể ghi thêm thẳng vào mục này.

### D. Động Cơ Thuật Toán, Benchmark & Đánh Giá Thành Viên
- [x] Giữ nguyên 6 thuật toán (`EDF`, `LST`, `WSPT`, `SCORED_GREEDY`, `BACKTRACK`, `HYBRID_ALNS`), bất biến kiến trúc `INV-1..6`, và bộ đánh giá `Testing_System v2.1`.
- [x] Xử lý rõ ràng 2 ca biên trong Chat: `DEADLOCK` (báo lỗi đỏ + gợi ý giãn deadline/nhờ việc) và `DENSE_WARNING` (cảnh báo vàng ngày quá dày).
- [ ] Hoàn tất **đợt chấm mù đa thành viên** trên `tools/member_eval/` (cổng `8010`) để thu thập phiếu đánh giá thực tế của cả 7 thành viên cho báo cáo cuối kỳ (`Calibration_Report.md`).
- [ ] Tổng hợp số liệu Benchmark & biểu đồ mới nhất sau cùng đưa vào slide / báo cáo nộp môn `CS252`.
