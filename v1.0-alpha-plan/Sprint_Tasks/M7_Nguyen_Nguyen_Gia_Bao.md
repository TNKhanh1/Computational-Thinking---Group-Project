# M7 — Nguyễn Nguyễn Gia Bảo (`25125006`) · Builder 3 (Core Engineering & Idea Lead)
**Vai trò theo `work_division.pdf` & Sprint Nâng Cấp:** Builder 3 · Lead **§8 Edge Cases & Trade-offs**, Support **§7 Architecture** · **Core Technical Lead (cùng `M5` Lê Tiến Bình & `M4` Nguyễn Trọng Tiến)**  
**Nhánh Git riêng (Branch):**
- **Wave 1A (Core & NLP):** `v1.0-alpha/m7-simulator-and-doc-parser` *(Tạo PR trước **23:00 Thứ Sáu, 27/11/2026**)*
- **Wave 2B & 3 (CSS & Final Gate):** `v1.0-alpha/m7-mobile-guardrails-and-e2e` *(Trước **22:30 Thứ Bảy, 28/11** & Gate **09:30 Sáng CN, 29/11/2026**)*

---

## 1. Trọng Tâm Của Bạn Trong Kế Hoạch Nâng Cấp Điểm Tối Đa
Cùng với Tiến Bình (`M5`) và Trọng Tiến (`M4`), bạn gánh **2 mảnh ghép tư duy khó nhất** để trả lời trực tiếp nhận xét của giảng viên (*"cần tính năng khó hơn về mặt tư duy"* + *"làm sao kiểm chứng học thích nghi nhiều tuần khi học kỳ quá ngắn?"* + *"xử lý logic file đính kèm"*), đồng thời giảm tải kỹ thuật cho các thành viên còn lại (`M1, M2, M3, M6`):

1. **Tác tử Mô phỏng Hành vi Sinh viên Đa tuần (`smartschedule/core/student_simulator.py` — Pattern `P14b`, hoàn thiện `Proposal §9.7`):**
   - Giải quyết triệt để vấn đề **không đủ thời gian khảo sát người thật suốt 6–8 tuần**: đối chiếu các nghiên cứu mô phỏng hành vi người độ chính xác cao (`Park et al., 2024 — StanfordHCI/genagents`, 85% độ chính xác lặp lại hành vi; `Binz et al., 2025 Nature — Centaur`, `marcelbinz.github.io/Centaur`) và cài đặt **Mô hình Cơ chế Tâm lý 5 Phương trình Tất định** (`MCTQ` nhịp sinh học ngầm + `Buehler 1994` lệch Log-Normal theo môn + `Steel 2007 TMT` sửa chuẩn mẫu số $1+\Gamma D$ + `McFadden 1974 RUM` xác suất bám lịch + `Albulescu 2022` tích lũy/phục hồi mệt mỏi).
   - Chạy thực nghiệm khép kín `Tuần 1 -> Tuần 4` cùng `cross_week_adapter.py` của Bình (`M5`) trong `< 500 ms` để chứng minh thuật toán tự học đúng hệ số đệm $\alpha$ và nhịp sinh học thật của sinh viên!
2. **Bộ Biên dịch Đề cương / Bài tập Đính kèm thành Ràng buộc (`smartschedule/nlp/doc_attachment_parser.py` — Pattern `P14a`):**
   - *(Chuyển từ `M6` sang bạn để Nhật chỉ làm thuần UI JS)* Đọc `.pdf`/`.md`/`.txt` đề cương bài tập, bóc tách các phần/câu hỏi (`Part 1..K`, trọng số điểm `%`, từ khóa độ khó, quan hệ thứ tự trước–sau) thành `DocumentConstraintDigest` để bắt lỗi sinh viên ước lượng quá thấp so với đề bài thật (`USER_VS_DOC_UNDERESTIMATE`).
3. **Responsive Mobile/Tablet CSS, Chốt chặn `INV-1..6` (`< 350 KB` RAM) & Bộ Test Hành trình E2E Cuối (`Wave 2B & 3`).**

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (`0%` Merge Conflict Guarantee Across All Waves)
- **CREATE (Wave 1A):**
  - `smartschedule/core/student_simulator.py` *(Pure Layer 1: Python stdlib + `smartschedule.core.{config,models,utils}` ONLY — zero web/NLP imports!)*
  - `smartschedule/nlp/doc_attachment_parser.py` *(Layer 4: lazy-imports `pypdf`/`docling` inside function scope with pure-Python UTF-8/regex fallback)*
  - `tests/logical/test_student_simulator_and_doc_parser.py`
- **CREATE / MODIFY (Wave 2B & Wave 3):**
  - `tests/ui/test_v1_alpha_user_journeys.py` *(CREATE)*
  - `smartschedule/ui/css/shell.css`, `smartschedule/ui/css/calendar.css`, `smartschedule/ui/css/chat.css` *(SOLE OWNER!)*
  - `tests/architecture/test_system_architecture.py`, `tests/architecture/test_memory_leaks.py` *(SOLE OWNER!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*`, `smartschedule/core/controller.py` (`M5`), `smartschedule/api/*` (`M4`/`M5`), or `smartschedule/ui/app.js` & `index.html` (`M1`).

### Engineering Requirements
1. **5-Equation Mechanistic Behavioral Simulator (`smartschedule/core/student_simulator.py`):**
   - Implement `InSilicoStudentSimulator(student_id: str, seed: int = 42, latent_profile: dict | None = None)` using an isolated `random.Random(seed)` instance (never mutate global `random` state!):
     1) **Latent Chronotype (`MCTQ` / `Smarr & Schirmer 2018`):** `true_peak_hour` $\in [7.0, 23.0]$ (supports deliberate mismatch against stated `profile.focus_preference`, e.g., stated `"MORNING"` vs latent Night Owl `20.5h`, to test revealed-preference learning!). Circular distance fit: $\text{CircFit}(h) = \max(0, 1 - \min(|h - H^*|, 24 - |h - H^*|)/8.0)$.
     2) **Category-Specific Asymmetric Log-Normal Fallacy (`Buehler et al. 1994`):** `category_bias[cat]` (e.g., `CODING=1.42`, `PROJECT=1.35`, `READING=1.08`), computing $d_{\text{actual}} = 15 \cdot \lceil d_{\text{est}} \cdot b_{\text{cat}} \cdot \exp(\mathcal{N}(0, 0.08^2)) / 15 \rceil$.
     3) **Corrected Temporal Motivation Theory (`Steel 2007, Eq. 3`):** $U_{\text{task}} = \frac{\text{Expectancy}(\text{CircFit}, F_t) \cdot (p_i / 5.0)}{1.0 + \Gamma \cdot \max(0.05, s_h / 24.0)}$, with $\Gamma \sim \text{Beta}(2, 5)$.
     4) **Discrete Adherence Choice (`McFadden 1974 RUM`):** Logistic probability $P(\text{adhere}) = \sigma(4.0 \cdot (U_{\text{task}} - U_{\text{distract}} - 0.25 F_t))$.
     5) **Ultradian Fatigue & Poisson Disruptions (`Albulescu 2022`):** Track `current_fatigue` $\in [0, 1]$, restoring $40\%$ after $\ge 15\text{m}$ rest break, plus optional recurring weekly disruption slot (e.g., Thursday `19:30–21:00`) to test `M5`'s chronic disruption detector.
   - Expose `simulate_week_execution(profile: CommitmentsProfile, tasks: list[Task], schedule: ScheduleOutput) -> list[dict]` returning structured `timeline_logs`:
     `[{"task_id", "block_id", "category", "cognitive_load", "day", "window", "start_hour", "estimated_duration_min", "planned_duration_min", "actual_duration_min", "adhered": bool, "overrun_min": int, "fatigue_after": float, "disruption_slot_window": str | None}]`.
2. **Logical Syllabus / Assignment Attachment Compiler (`smartschedule/nlp/doc_attachment_parser.py`):**
   - Expose `parse_document_constraint_digest(filename: str, raw_bytes_or_text: bytes | str) -> dict`:
     - Enforce `<= 20 MB` cap; lazily try `pypdf` / `docling` for `.pdf`, falling back cleanly to UTF-8 decoding for `.md`/`.txt`.
     - Extract numbered/bulleted milestones (`Part 1..N`, `Bài 1..N`, `Task 1..N`, `Câu 1..N`), grade weights (`(\d{1,2})%` mapped via `GRADE_WEIGHT_TO_PRIORITY`), coding/math/report complexity signals (`cognitive_load` $\in \{1,2,3\}$), sequential ordering cues (`depends_on_prev: bool`), and `suggested_total_min` (rounded to 15m).
3. **Mobile Slide-Over CSS, `INV-1..6` Lazy-Import Guardrails & Full E2E Suite (`Wave 2B & 3`):**
   - Responsive slide-over drawers at `< 900px` / `< 768px` in `shell.css`, `calendar.css`, `chat.css` + `.thinking-pattern-rules` badge styling (preserving `.copilot-expand-fab` and `.left-nav-sidebar.collapsed` contracts).
   - Extend `test_system_architecture.py` (scanning all `smartschedule/core/*.py`, including `student_simulator.py` & `cross_week_adapter.py`, for zero `nlp`/`api`/`fastapi`/`spacy`/`transformers`/`docling` imports) and `test_memory_leaks.py` (`< 350 KB` heap delta).
   - Build `tests/ui/test_v1_alpha_user_journeys.py` covering Onboarding, `.ics`, Document-to-DAG + Underestimate Alert, Emergency `LOCAL_INSERTION` ($\ge 90\%$), and **4-Week Closed-Loop Adaptation (`POST /api/simulation/multi-week`: Week 4 adherence & on-time value $>$ Week 1)**.

### Verification Commands (Must Pass 100% Before PR)
```powershell
python -B -m pytest tests/logical/test_student_simulator_and_doc_parser.py tests/architecture/ -q
python -B tests/clean_runner.py --pass
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [x] **(Wave 1A)** Xây dựng `smartschedule/core/student_simulator.py` (5 phương trình tâm lý tất định theo `seed`, trả `timeline_logs` chuẩn cho `M5`).
- [x] **(Wave 1A)** Xây dựng `smartschedule/nlp/doc_attachment_parser.py` biên dịch đề bài `.pdf/.md/.txt` thành `DocumentConstraintDigest` + viết `test_student_simulator_and_doc_parser.py` (gửi `M4` Trọng Tiến kiểm định bằng Claude Plan).
- [ ] **(Wave 2B)** Hoàn thiện responsive CSS (`shell.css`, `calendar.css`, `chat.css`) + khóa `INV-1..6` trong `tests/architecture/*`.
- [ ] **(Wave 2B & Wave 3)** Viết `tests/ui/test_v1_alpha_user_journeys.py` và chạy cổng kiểm định cuối cùng sáng Chủ Nhật trước khi `M1` gắn tag `v1.0-alpha`.
