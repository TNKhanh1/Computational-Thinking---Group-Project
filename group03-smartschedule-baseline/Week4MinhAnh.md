# BÁO CÁO PHÁT TRIỂN (DEVELOPMENT REPORT) — LAB 04: FROM SPEC TO CODE (PHASED VIBE-CODING WITH AI)

| Thông tin | Chi tiết |
|---|---|
| **Môn học** | Tư duy Tính toán (CSC10014) — Khoa Công nghệ Thông tin, Trường ĐH Khoa học Tự nhiên, ĐHQG-HCM (FIT-HCMUS) |
| **Nhóm thực hiện** | Group 03 (*The Seven Dwarfs*) |
| **Sinh viên thực hiện** | **Hoàng Minh Anh** (`hmanh0201` / `minhanhbmt07@gmail.com`) — *Thinker 2 (Perspective 4: Overload & Alerts / UI-UX Review Flow)* |
| **Nhánh Git (Branch)** | `hmanh` |
| **Tính năng phát triển** | **Feature 002 (F15): Smart Overload Triage, Habit-Skipping & Interactive Trade-off Preview Engine (`002-overload-triage-preview`)** |
| **Hồ sơ Đặc tả (Spec Kit)** | [`../specs/002-overload-triage-preview/`](../specs/002-overload-triage-preview/) (`spec.md`, `plan.md`, `tasks.md`, `diagrams.md`) |

---

## 1. Khảo Sát Nhánh Nhóm & Lý Do Chọn Tính Năng (Feature Selection & Justification)

### 1.1. Tóm tắt khảo sát các nhánh thành viên trong nhóm (`git branch -r`)
Trước khi bắt đầu thiết kế và viết mã, quá trình khảo sát toàn bộ nhánh trên kho lưu trữ Git của nhóm được thực hiện để đảm bảo không trùng lặp phạm vi và không gây xung đột hợp nhất (merge conflict):

| Nhánh Remote | Thành viên phụ trách | Phạm vi công việc đã thực hiện | Các file tác động |
|---|---|---|---|
| `origin/main` | Toàn nhóm | Hệ thống **Baseline (V0)** trên lưới thời gian rời rạc 672 slots, 4 thuật toán (`EDF`, `LST`, `WSPT`, `Backtracking`), `LocalRepairEngine`, 10 kịch bản `T01–T10`. | `group03-smartschedule-baseline/*` |
| `origin/dminh` | Phạm Đức Minh (*Leader*) | Giao diện **Student-Facing Minimalist UI Mode** (`#studentAppLayout`) và tính toán buffer $\times 1.2$ phía client. | `web/index.html`, `web/app.js`, `Week4DucMinh.md`, `AIWeek4.md` |
| `origin/verification_tests_ver1` | Nguyễn Nguyễn Gia Bảo (*Builder 3*) | Bộ kiểm thử tự động 56 tests (`verification_tests/`), ứng dụng GUI `test_studio.py`, `clean_runner.py`, và **5 bài test mục tiêu (Development Gap Tests)** trong `test_improve_plan_gaps.py`. | `verification_tests/*`, `agents/*`, `docs/*`, `web/api.py` |
| `origin/feature/estimate-buffer` | Nguyễn Trọng Tiến (*Thinker 3*) | **Feature 001 — Estimate Buffer (Planning-Fallacy Correction)** (`001-estimate-buffer`): giải quyết **Gap Test #3** (`test_fail_planning_fallacy_buffer_multiplier`). | `specs/001-estimate-buffer/*`, `src/estimate_buffer.py`, `src/models.py`, `src/controller.py` |

### 1.2. Quyết định lựa chọn tính năng: Feature 002 (F15) — `002-overload-triage-preview`
Tôi lựa chọn triển khai **Feature 002 (F15): Smart Overload Triage, Habit-Skipping & Interactive Trade-off Preview Engine** vì 4 lý do kỹ thuật cốt lõi:
1. **Đúng phân công chuyên môn trong nhóm:** Trong Báo cáo Đề xuất (`Proposal_Report.pdf`, trang 42–43), Hoàng Minh Anh (*Thinker 2*) phụ trách **Perspective 4 (Overload & Alerts)** và **UI/UX Review Flow**.
2. **Giải quyết trực tiếp Development Gap Test #5:** Trong bộ kiểm thử `verification_tests/development_gap_tests/test_improve_plan_gaps.py`, bài kiểm thử `test_fail_overload_habit_skipping_recommendation` đang báo đỏ (`FAILED`) vì bản V0 chưa phân biệt được thói quen linh hoạt (`HABIT` / task tự chọn ưu tiên thấp) với bài tập cốt lõi để gợi ý mã `SKIP_HABIT`.
3. **Hiện thực hóa đặc tả `Improve_Plan/improve_plan.md` (§5.1 F15, §6.7, §7.2, §7.3):** Cung cấp bộ phân loại giải pháp giảm thiểu thiệt hại học tập (`SKIP_HABIT` $\to$ `SHORTEN_TASK` $\to$ `ALLOW_SPLIT` $\to$ `POSTPONE_LOWEST`), nâng cấp endpoint `POST /api/overload/preview` từ stub sang mô phỏng thực tế trên bản sao độc lập (stateless deep-copy), đánh dấu các phiên đề xuất bằng trạng thái `state = "PROPOSED"` (viền nét đứt trên lưới 672 slots), và bổ sung thanh **Hoàn Tác 1-Click (Undo)**.
4. **Độc lập kiến trúc tuyệt đối (Zero Solver Conflict):** Toàn bộ thuật toán phân loại quá tải được đóng gói trong module thuần `src/overload_triage.py` và kết nối qua `src/controller.py`, giữ nguyên 100% thư mục `src/solvers/*` và `requirements.txt`.

---

## 2. Đặc Tả Kỹ Thuật (Specification) & Thiết Kế Trực Quan (Diagrams as Code)

### 2.1. Ba Sơ Đồ Thiết Kế Hệ Thống (Mã Nguồn Mermaid Plain-Text)

#### Sơ đồ 1: Use Case Diagram — Luồng Phát Hiện Quá Tải, Phân Loại & Xem Trước Tương Tác

```mermaid
flowchart LR
    Student(["👩‍🎓 Sinh viên (Student)"])
    Lecturer(["👨‍🏫 Giảng viên / Người chấm (Lab Evaluator)"])

    subgraph SmartSchedule_Overload_System ["SmartSchedule — Overload Triage & Interactive Preview System (Feature F15)"]
        UC1("UC1: Phát hiện Quá tải & Tính toán Thiếu hụt<br/>(Detect Capacity / Fragmentation Overload)")
        UC2("UC2: Phân loại Giải pháp Tối thiểu Thiệt hại<br/>(Generate Least-Harm Options: SKIP_HABIT, SHORTEN, SPLIT, POSTPONE)")
        UC3("UC3: Bảo vệ Ràng buộc Cứng & Thứ tự Tiên quyết<br/>(Guard SLEEP, OCCUPIED & depends_on DAG)")
        UC4("UC4: Xem trước Phương án trên Lưới 672 Slots<br/>(Interactive What-If Preview with Dashed PROPOSED Blocks)")
        UC5("UC5: Áp dụng Phương án & Cập nhật Lịch Tuần<br/>(Apply Selected Resolution Option)")
        UC6("UC6: Hoàn tác 1-Click về Lịch Gốc<br/>(1-Click Undo to Pre-Resolution State)")
    end

    Student --> UC1
    Student --> UC4
    Student --> UC5
    Student --> UC6
    Lecturer --> UC1
    Lecturer --> UC2
    Lecturer --> UC4

    UC1 -->|"<<include>>"| UC2
    UC2 -->|"<<include>>"| UC3
    UC4 -->|"<<extend>>"| UC5
    UC5 -->|"<<extend>>"| UC6
```

#### Sơ đồ 2: Sequence Diagram — Luồng Xử Lý End-to-End Từ Phát Hiện Quá Tải Đến Xem Trước, Áp Dụng & Hoàn Tác

```mermaid
sequenceDiagram
    autonumber
    actor User as 👩‍🎓 Student / Evaluator
    participant UI as 🖥️ Web Workbench (index.html / app.js)
    participant API as ⚡ FastAPI (web/api.py)
    participant Ctrl as 🎛️ ScheduleController (src/controller.py)
    participant Triage as 🧠 OverloadTriageEngine (src/overload_triage.py)
    participant Solver as ⚙️ BaseScheduler / GreedyEDFSolver

    User->>UI: Nạp Kịch bản Quá tải (T06 / T03) & Bấm "Chạy Xếp Lịch"
    UI->>API: POST /api/plan {commitments, tasks, algorithm}
    API->>Ctrl: solve_schedule(profile, tasks, algorithm)
    Ctrl->>Solver: solve(profile, tasks)
    Solver-->>Ctrl: ScheduleOutput (status=INFEASIBLE_CAPACITY, raw overload_reports)
    Ctrl->>Triage: enrich_schedule_overload(output, profile, tasks)
    Triage->>Triage: Quét Habits (category=HABIT / priority<=2) & kiểm tra depends_on DAG
    Triage->>Triage: Sinh danh sách options [O1: SKIP_HABIT, O2: SHORTEN_TASK, O3: ALLOW_SPLIT, O4: POSTPONE_LOWEST]
    Triage-->>Ctrl: Enriched ScheduleOutput (overload.options[])
    Ctrl-->>API: (ScheduleOutput, TimeGridManager)
    API-->>UI: HTTP 200 JSON (blocks, unplaced, overload.options[])
    UI-->>User: Hiển thị Hộp Cảnh Báo Quá Tải + Các Thẻ Giải Pháp (Preview / Apply)

    User->>UI: Bấm nút "👁️ Xem Trước (Preview)" trên Option O1/O2
    UI->>API: POST /api/overload/preview {commitments, tasks, option_id, option_code, target_task_id}
    API->>Ctrl: preview_overload_resolution(profile, tasks, option_id, option_code, target_task_id)
    Ctrl->>Triage: apply_triage_option(profile, tasks_copy, option_id, option_code, target_task_id)
    Triage-->>Ctrl: (resolved_tasks_copy, change_record)
    Ctrl->>Solver: solve(profile, resolved_tasks_copy)
    Solver-->>Ctrl: preview_schedule (status=SUCCESS, 0 unplaced)
    Ctrl->>Ctrl: Đánh dấu các block mới/thay đổi state="PROPOSED" & tính before/after summary
    Ctrl-->>API: PreviewResult {preview_mode: true, blocks, before_summary, after_summary, resolved_tasks}
    API-->>UI: HTTP 200 JSON PreviewResult
    UI-->>User: Vẽ các block PROPOSED (viền nét đứt) trên lưới 672 slots + Thanh trạng thái Xem Trước

    alt Người dùng bấm "✅ Áp Dụng Phương Án Này (Apply)"
        User->>UI: Bấm "✅ Áp Dụng (Apply)"
        UI->>UI: Lưu deep-copy (state.tasks, state.lastSchedule) vào overloadUndoStack
        UI->>UI: Cập nhật state.tasks = resolved_tasks & gọi solveSchedule()
        UI-->>User: Lịch tuần đạt 100% Feasible (state="ACCEPTED") + Hiển thị nút "↩️ Hoàn Tác (Undo)"
    else Người dùng bấm "✖ Hủy Xem Trước (Cancel Preview)" hoặc "↩️ Hoàn Tác (Undo)"
        User->>UI: Bấm "Hủy Xem Trước" / "Hoàn Tác"
        UI->>UI: Khôi phục state.tasks & state.currentSchedule từ bản gốc
        UI-->>User: Trả lại trạng thái lưới lịch ban đầu
    end
```

#### Sơ đồ 3: State Machine Diagram — Vòng Đời Trạng Thái Của Lịch Biểu & Chế Độ Xem Trước Quá Tải

```mermaid
stateDiagram-v2
    [*] --> Idle_Unplanned : Khởi tạo / Nạp Preset hoặc Scenario (T01..T10)

    Idle_Unplanned --> Solving_Schedule : POST /api/plan (Chạy thuật toán xếp lịch)

    state Solving_Schedule {
        [*] --> Running_Solver
        Running_Solver --> Check_Feasibility : Kiểm tra unplaced_tasks & overload_reports
    }

    Check_Feasibility --> Feasible_Schedule : unplaced == 0 (status = SUCCESS)
    Check_Feasibility --> Overloaded_Detected : unplaced > 0 (INFEASIBLE_CAPACITY / NO_SCHEDULE_FOUND)

    state Overloaded_Detected {
        [*] --> Triage_Enrichment : OverloadTriageEngine.enrich_schedule_overload()
        Triage_Enrichment --> Options_Presented : Hiển thị thẻ SKIP_HABIT / SHORTEN_TASK / ALLOW_SPLIT / POSTPONE_LOWEST
    }

    Options_Presented --> Previewing_Option : Bấm "Xem Trước (Preview)" (POST /api/overload/preview)

    state Previewing_Option {
        [*] --> Simulated_On_Cloned_Tasks : Clone tasks (INV-3 Stateless) & áp dụng Option
        Simulated_On_Cloned_Tasks --> Render_Proposed_Blocks : Các block mới/dời chỗ mang state = "PROPOSED" (viền nét đứt)
    }

    Previewing_Option --> Options_Presented : Bấm "Hủy Xem Trước (Cancel Preview)"
    Previewing_Option --> Previewing_Option : Chọn "Xem Trước" một Option khác (O1 <-> O2 <-> O3)
    Previewing_Option --> Resolution_Applied : Bấm "Áp Dụng (Apply)"
    Options_Presented --> Resolution_Applied : Bấm "Áp Dụng (Apply)" trực tiếp trên thẻ Option

    state Resolution_Applied {
        [*] --> Push_Undo_Snapshot : Lưu snapshot vào overloadUndoStack
        Push_Undo_Snapshot --> ReSolve_Committed : Cập nhật state.tasks & giải lại lịch (state = "ACCEPTED")
    }

    Resolution_Applied --> Overloaded_Detected : Bấm "Hoàn Tác (Undo)" (Khôi phục snapshot gốc)
    Resolution_Applied --> Feasible_Schedule : Xác nhận giữ lịch mới (100% Deadline Satisfaction)
    Feasible_Schedule --> [*]
```

---

## 3. Kết Quả Kiểm Thử (`pytest` & `clean_runner.py`)

* **`tests/test_overload_triage.py`:** `9 / 9 PASSED`
* **`verification_tests/development_gap_tests/test_improve_plan_gaps.py::test_fail_overload_habit_skipping_recommendation`:** `PASSED (100%)`
* **`verification_tests/clean_runner.py --pass`:** `59 / 59 PASSED (0 Failed)`
* **6 ảnh chụp màn hình minh chứng:** Lưu tại [`../screenshots/`](../screenshots/).
