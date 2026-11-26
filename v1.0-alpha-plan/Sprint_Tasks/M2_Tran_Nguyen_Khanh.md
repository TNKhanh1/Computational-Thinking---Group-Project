# M2 — Trần Nguyên Khánh (`25125019`) · Thinker 1
**Vai trò theo `work_division.pdf`:** Thinker 1 · Lead **§6 Pillar 4: Algorithmic Design**, Support **§8 Edge Cases**, **§10 Design to Action**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m2-free-context-nlp`  
**Đợt thực hiện (Wave):** **Wave 1** (Tạo PR trước **23:00 Thứ Sáu, 27/11/2026** · Hạn trễ nhất **12:00 Trưa Thứ Bảy, 28/11/2026**)

---

## 1. Dành cho Thành Viên (Giải thích dễ hiểu)
Hiện nay tầng đọc ngữ cảnh (`context_router.py`) mới chỉ gọi Gemini khi có `GEMINI_API_KEY` hoặc rơi về bộ cắt vế câu cơ bản. Nếu người dùng không có API key mà gõ các câu có **ý phủ định / né khung giờ / sang tuần sau** (ví dụ: *"Làm bài tập Giải tích 2 tiếng trước thứ 6, nhưng tránh buổi tối nhé"*, *"Không làm sáng thứ 4"*), hệ thống dễ hiểu ngược thành *"xếp vào buổi tối"*!

**Nhiệm vụ của bạn trong `v1.0-alpha`:**
1. **Tích hợp bộ đọc ngữ cảnh miễn phí, nhẹ RAM & tốc độ cao (`free_context_engine.py`):** Đưa mô hình mã nguồn mở miễn phí (`spaCy` MIT pipeline và/hoặc encoder nhẹ trên Hugging Face như `DeBERTa` / `RoBERTa` nén nhẹ) vào tầng NLP theo cơ chế **chỉ nạp khi gọi (lazy-load)**, đi kèm bộ luật nhận diện phủ định tiếng Việt (*"không"*, *"đừng"*, *"tránh"*, *"né"*) để người dùng không cần khóa API trả phí vẫn tách tên công việc và ý muốn cực chuẩn.
2. **Nâng cấp hộp "💭 Quá trình suy nghĩ" (`thinking_stage.py`):** Ở chế độ `Developer Mode`, hiển thị rõ hệ thống vừa dùng bộ đọc ngữ cảnh nào, mất bao nhiêu mili-giây, và giải thích ngắn gọn vì sao thuật toán được chọn vượt trội hơn các thuật toán đã loại (đúng tinh thần Mục §6 bạn phụ trách).

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (Conflict-Free Guarantee)
- **CREATE:**
  - `smartschedule/nlp/free_context_engine.py`
  - `environments/requirements-nlp-extra.txt` *(for optional `spacy` / `onnxruntime` / `transformers` packages so core `environments/requirements.txt` stays instant & zero-conflict!)*
  - `tests/logical/test_free_context_engine.py`
- **MODIFY (Wave 1 ONLY):**
  - `smartschedule/nlp/context_router.py` *(SOLE OWNER in this sprint!)*
  - `smartschedule/api/chat/thinking_stage.py` *(SOLE OWNER in this sprint!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*`, `smartschedule/api/chat/handlers.py`, `smartschedule/ui/*`, or `agents/commit_changes.md`.

### Engineering Requirements
1. **Strict `INV-5` Memory Compliance (`< 350 KB` Solver Heap Delta):**
   - Never import `spacy`, `torch`, `transformers`, or `onnxruntime` at module top-level during solver imports. Load NLP pipelines lazily inside a singleton getter in `smartschedule/nlp/free_context_engine.py` ONLY when `extract_context_free_model(...)` is called, with clean `try / except ImportError` fallback when `requirements-nlp-extra.txt` is not installed.
2. **Negation & Exclusion Awareness (`free_context_engine.py` + `context_router.py`):**
   - Detect Vietnamese/English negation cues (`không`, `đừng`, `tránh`, `né`, `trừ`, `avoid`, `not in`) before time-of-day windows (`buổi sáng`, `buổi chiều`, `buổi tối`) so *"không làm buổi tối"* NEVER sets `preferred_window = "EVENING"` (instead maps to an alternative window or `avoid_windows` hint).
   - Detect relative next-week cues (`tuần sau`, `đầu tuần tới`, `next week`) and expose `week_offset_hint` / ISO deadline date cleanly in `ChatContextExtractionSchema`.
   - Routing priority in `parse_context_with_online_model()` (keep function name backward-compatible for `handlers.py`!):
     1) Free local lightweight engine (`spaCy` / HF encoder if installed & enabled via `NL_CONTEXT_BACKEND=free|auto`),
     2) Cloud `gemini-2.5-flash-lite` (if `GEMINI_API_KEY` present),
     3) Deterministic syntactic + negation-aware condenser fallback (`< 2 ms`).
3. **Richer Humanized Thinking Stage (`smartschedule/api/chat/thinking_stage.py`):**
   - Include `parser_engine_used` and `parse_ms` (when provided) cleanly in `context_summary_vi` and sharpen `algorithm_summary_vi` explaining dominant subset selection (`SCORED_GREEDY` / `HYBRID_ALNS` vs energy-blind `EDF`/`WSPT`/`LST`).

### Verification Commands (Must Pass 100% Before PR)
```powershell
python -B -m pytest tests/logical/test_free_context_engine.py tests/architecture/test_memory_leaks.py -q
python -B tests/clean_runner.py --pass
python -B tests/fixtures/nl_cases/verify_hybrid_200.py
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [ ] Xây dựng `smartschedule/nlp/free_context_engine.py` (hỗ trợ `spaCy` / HF encoder nạp lười + bắt phủ định tiếng Việt *"tránh/không làm buổi..."*).
- [ ] Tích hợp luồng chọn mô hình thông minh vào `context_router.py` (giữ tương thích ngược 100% cho `handlers.py`).
- [ ] Cải thiện lời giải thích chọn thuật toán tối ưu trong `thinking_stage.py`.
- [ ] Tạo `environments/requirements-nlp-extra.txt` và viết test `tests/logical/test_free_context_engine.py`, đảm bảo `test_memory_leaks.py` (`< 350 KB`) xanh 100%.
