# AI Usage Declaration — Lab 04: From Spec to Code (Phased Vibe-Coding with AI)

- **Course:** CS252 — Computational Thinking (2026) · FIT-HCMUS
- **Team:** Group 03 — *The Seven Dwarfs*
- **Student:** Hoàng Minh Anh (`hmanh0201` — `minhanhbmt07@gmail.com`)
- **Role:** Thinker 2 — System Analysis & Interactive Trade-off Resolution
- **Feature:** Feature 002 (`F15`) — Smart Overload Triage, Habit-Skipping & Interactive Trade-off Preview Engine (`002-overload-triage-preview`)
- **Branch:** `hmanh`

---

## 1. AI Tools & Models Used

| Tool / Platform | Model / Engine | Purpose in Lab 04 Workflow |
| :--- | :--- | :--- |
| **Google Antigravity IDE** | Agentic Coding Assistant | Multi-branch Git survey, Spec-Driven Design (`spec.md`, `plan.md`, `tasks.md`), Mermaid diagram generation (`diagrams.md`), phased code implementation across Layer 3–5, and automated pytest verification |

---

## 2. Phased Vibe-Coding Workflow & Verbatim Prompts

### Phase 1 — Branch Survey, Specification, Diagrams & Planning (Zero-Code Gate)
- **Objective:** Survey all teammate remote branches (`origin/dminh`, `origin/feature/estimate-buffer`, `origin/verification_tests_ver1`), identify an orthogonal single feature with zero file collisions in `src/solvers/*`, and produce a complete Master Plan & Specification with 3 Mermaid diagrams before writing any code.
- **Prompt Used:**
  > *"Tôi đã tải lên file đề bài Lab 04: 'Lab04-From Spec to Code: Phased Vibe-coding with AI'. Bạn hãy đóng vai trò là kỹ sư phần mềm phụ trách chính, đọc kỹ tài liệu này kết hợp khảo sát trực tiếp toàn bộ workspace và các nhánh Git của nhóm để lập kế hoạch triển khai. Mục tiêu giai đoạn này: Tuyệt đối KHÔNG viết mã nguồn, không chỉnh sửa file hay cài đặt bất cứ thư viện nào trong workspace. Nhiệm vụ duy nhất của bạn lúc này là khảo sát, đọc hiểu, phân tích và xuất ra một Bản kế hoạch & Đặc tả kỹ thuật chi tiết (Master Plan & Spec) để tôi duyệt trước khi thực thi..."*
- **Human Review & Decision:**
  - Verified that `origin/dminh` implemented `F12` (Circadian Energy Matching) and `origin/feature/estimate-buffer` implemented `F14` (Estimate Buffer Multiplier) inside `src/solvers/*`.
  - Approved **Feature 002 (F15): Smart Overload Triage, Habit-Skipping & Interactive Trade-off Preview Engine** (`002-overload-triage-preview`) operating strictly in Layer 3 (`src/overload_triage.py`, `src/controller.py`), Layer 4 (`web/api.py`), and Layer 5 (`web/index.html`, `web/app.js`).

### Phase 2 — Sequential Task Execution, Testing & Verification (Tasks 1–7)
- **Objective:** Create branch `hmanh` from `origin/verification_tests_ver1` and execute Tasks 1 through 7 with one atomic Git commit per task, preserving 100% of existing tests and turning Developmental Gap Test #5 green.
- **Prompt Used:**
  > *"Tôi chính thức phê duyệt Bản kế hoạch & Đặc tả kỹ thuật cho Feature 002 (F15): Smart Overload Triage, Habit-Skipping & Interactive Trade-off Preview Engine (002-overload-triage-preview). Bây giờ, hãy chuyển sang Pha Thực Thi (Implementation & Verification Phase) và tự động chạy các lệnh trên terminal cũng như chỉnh sửa file để hoàn thành tuần tự từ Task 1 đến Task 7... TUYỆT ĐỐI KHÔNG gộp nhiều Task vào một commit. Bạn phải chạy lệnh git add và git commit trực tiếp trên nhánh hmanh ngay sau khi hoàn thành và kiểm thử xong từng Task..."*

---

## 3. Division of Responsibility & Human Verification

| Artifact / Component | AI Role | Student (Hoàng Minh Anh) Role & Verification |
| :--- | :--- | :--- |
| `specs/002-overload-triage-preview/*` | Drafted `spec.md`, `plan.md`, `tasks.md`, and 3 Mermaid diagrams (`diagrams.md`). | Reviewed acceptance criteria `AC1–AC6`, prerequisite protection rules (`H4`), and Mermaid syntax accuracy. |
| `src/overload_triage.py` | Generated `OverloadTriageEngine` methods (`get_protected_prerequisite_ids`, `is_habit_or_optional_task`, `build_triage_options`, `enrich_schedule_overload`, `apply_triage_option`). | Verified AST purity (`INV-1`–`INV-6`), ensured `output.unplaced_tasks` is prioritized over `report.unplaced_tasks` so `T06-EXTRA-3` is targeted in Scenario `T06`, and verified 15-minute chunk splitting for `SHORTEN_TASK`. |
| `src/controller.py` & `web/api.py` | Integrated `enrich_schedule_overload` and `preview_overload_resolution`; upgraded `POST /api/overload/preview`. | Verified deep-copy isolation (`copy.deepcopy`) so What-If previews never mutate baseline tasks, and confirmed backward compatibility with `test_ui_contracts.py`. |
| `web/index.html` & `web/app.js` | Added `.slot-block-proposed` CSS, interactive triage cards, preview status banner, and 1-click Undo banner. | Inspected visual layout and verified `Preview -> Apply -> Undo` state transitions against the State Machine diagram. |
| `tests/test_overload_triage.py` | Authored 9 unit and API integration tests covering `AC1–AC6`. | Executed `clean_runner.py --pass` (`59/59 PASSED`), `test_overload_triage.py` (`9/9 PASSED`), and Gap Test #5 (`PASSED`). |

---

## 4. Academic Integrity Statement

I, **Hoàng Minh Anh** (`hmanh0201`), declare that:
1. I used AI coding tools transparently following the **Spec-Driven Phased Vibe-Coding** methodology required by Lab 04.
2. Every specification, Mermaid diagram, code module, and unit test generated with AI assistance was reviewed, understood, and verified by me against the project's formal constraints ($H_1$–$H_5$, `INV-1`–`INV-6`, and 3x SHA-256 determinism).
3. No unverified code was committed, and all architectural invariants and team synchronization logs (`agents/commit_changes.md`, `docs/commit_changes.md`) were faithfully maintained.
