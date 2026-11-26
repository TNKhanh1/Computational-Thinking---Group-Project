# M2 — Trần Nguyên Khánh (`25125019`) · Thinker 1
**Vai trò theo `work_division.pdf`:** Thinker 1 · Lead **§6 Pillar 4: Algorithmic Design**, Support **§8 Edge Cases**, **§10 Design to Action**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m2-free-context-nlp`  
**Đợt thực hiện (Wave):** **Wave 1** (Tạo PR trước **23:00 Thứ Sáu, 27/11/2026** · Hạn trễ nhất **12:00 Trưa Thứ Bảy, 28/11/2026**)

---

## 1. Dành cho Thành Viên (Giải thích dễ hiểu)
Hiện nay tầng đọc ngữ cảnh (`context_router.py`) mới chỉ gọi Gemini khi có `GEMINI_API_KEY` hoặc rơi về bộ cắt vế câu cơ bản. Nếu người dùng không có API key mà gõ các câu có **ý phủ định / né khung giờ / sang tuần sau** (ví dụ: *"Làm bài tập Giải tích 2 tiếng trước thứ 6, nhưng tránh buổi tối nhé"*, *"Không làm sáng thứ 4"*), hệ thống dễ hiểu ngược thành *"xếp vào buổi tối"*!

**Nhiệm vụ của bạn trong `v1.0-alpha` (Đã tinh gọn nhẹ nhàng — phần nối đồ thị & đọc đề do `M4` và `M7` gánh):**
1. **Bộ hỗ trợ bắt Phủ định Tiếng Việt & Gợi ý Thứ tự nhẹ RAM (`free_context_engine.py` + `context_router.py`):** Bọc `try / except ImportError` nạp lười `spaCy` (tùy chọn, nếu chưa cài vẫn chạy mượt bằng bộ luật `< 2 ms`!), bắt từ khóa **phủ định tiếng Việt** (*"không"*, *"đừng"*, *"tránh"*, *"né"* $\to$ `avoid_windows`) và cụm từ thứ tự cơ bản (*"sau khi xong X"* $\to$ `prerequisite_hint`).
2. **Format hộp "💭 Quá trình suy nghĩ" hiển thị `14 Patterns -> Deterministic Logic Rule` (`thinking_stage.py`):** Bổ sung danh sách `pattern_rules` gọn đẹp đối chiếu sẵn từ bảng trong [`../Testing_Plan/Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md) (`P1`..`P14`) để phục vụ Mục §4 & §6 khi demo.

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
2. **Negation, Next-Week & Prerequisite DAG Cue Awareness (`free_context_engine.py` + `context_router.py`):**
   - Detect Vietnamese/English negation cues (`không`, `đừng`, `tránh`, `né`, `trừ`, `avoid`, `not in`) before time-of-day windows (`buổi sáng`, `buổi chiều`, `buổi tối`) so *"không làm buổi tối"* NEVER sets `preferred_window = "EVENING"` — instead populate `avoid_windows: list[str]` (e.g. `["EVENING"]`, Pattern `P12b`).
   - Detect prerequisite ordering cues (`sau khi (?:làm )?xong <X>`, `hoàn thành <X> trước rồi mới`, `xong <X> (?:rồi )?mới`, `after finishing <X>`, `depends on <X>`) and expose `prerequisite_hint: Optional[str]` in `ChatContextExtractionSchema` so `M4` (`handlers.py`) can link `Task.depends_on` (Pattern `P10`).
   - Detect relative next-week cues (`tuần sau`, `đầu tuần tới`, `next week`) and expose `week_offset_hint: int` (`0` or `1`).
   - Routing priority in `parse_context_with_online_model()` (keep function name backward-compatible for `handlers.py`!):
     1) Free local lightweight engine (`spaCy` / HF encoder if installed & enabled via `NL_CONTEXT_BACKEND=free|auto`),
     2) Cloud `gemini-2.5-flash-lite` (if `GEMINI_API_KEY` present),
     3) Deterministic syntactic + negation/prerequisite-aware condenser fallback (`< 2 ms`, **also active offline & in unit tests when negation/prerequisite cues appear** so `M4`/E2E tests get `avoid_windows` & `prerequisite_hint` deterministically without needing cloud keys!).
3. **Explicit `12-Pattern -> Deterministic Logic Rule` Trace in `thinking_stage.py`:**
   - Preserve all existing keyword parameters of `build_thinking_summary(...)` and add optional defaulted kwargs:
     `pattern_rules: Optional[List[Dict[str, str]]] = None`, `has_dag: bool = False`, `avoided_windows: Optional[List[str]] = None`, `repair_stability_pct: Optional[float] = None`, `overload_triage: bool = False`, `parser_engine_used: Optional[str] = None`, `parse_ms: Optional[float] = None`.
   - Auto-populate `"pattern_rules"` (list of `{"pattern_id", "pattern_name", "causal_link_vi", "deterministic_rule"}` matching [`../Testing_Plan/Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md) §4) based on active features (`P1` Fallacy Buffer `RoundUp_15(d*α)`, `P2` Ultradian `90m` Cap + `15m` Rest, `P3` Counterfactual Bio-Sync, plus `P10` DAG `max(end_u) <= min(start_v)` when `has_dag=True`, `P12b` Negation Mask when `avoided_windows`, `P8` Local Insertion Freeze when `repair_stability_pct is not None`, and `P11` `HYBRID_ALNS` Regret-2 / Kempe Eject or Knapsack Triage when `escalated_from_greedy` / `overload_triage`).
   - Include `parser_engine_used` and `parse_ms` cleanly in `context_summary_vi` and sharpen `algorithm_summary_vi`.

### Verification Commands (Must Pass 100% Before PR)
```powershell
python -B -m pytest tests/logical/test_free_context_engine.py tests/architecture/test_memory_leaks.py -q
python -B tests/clean_runner.py --pass
python -B tests/fixtures/nl_cases/verify_hybrid_200.py
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [ ] Xây dựng `smartschedule/nlp/free_context_engine.py` (hỗ trợ `spaCy` / HF encoder nạp lười + bắt phủ định `avoid_windows` `P12b` + bắt tiền điều kiện `prerequisite_hint` `P10`).
- [ ] Tích hợp luồng chọn mô hình thông minh vào `context_router.py` (giữ tương thích ngược 100% cho `handlers.py`).
- [ ] Nâng cấp `thinking_stage.py` xuất mảng `pattern_rules` nối rõ **Pattern $\to$ Cơ chế nhân quả $\to$ Deterministic Logic Rule** (khớp bảng 12 Patterns trong [`Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md)).
- [ ] Tạo `environments/requirements-nlp-extra.txt` và viết test `tests/logical/test_free_context_engine.py`, đảm bảo `test_memory_leaks.py` (`< 350 KB`) xanh 100%.
