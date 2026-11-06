# Feature 002 — Visual Design Diagrams (Diagrams as Code — Mermaid)

This document contains the plain-text **Mermaid** source code for the 3 visual design diagrams of **Feature 002 (F15): Smart Overload Triage, Habit-Skipping & Interactive Trade-off Preview Engine (`002-overload-triage-preview`)**.

---

## 1. Use Case Diagram — Overload Detection, Triage & Interactive Resolution Flow

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

---

## 2. Sequence Diagram — End-to-End Overload Triage, What-If Preview, Apply & Undo

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
    Solver-->>Ctrl: ScheduleOutput (status=PARTIAL_OVERLOAD, raw overload_reports)
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
        UI->>UI: Cập nhật state.tasks = resolved_tasks & gọi solveCurrentSchedule()
        UI-->>User: Lịch tuần đạt 100% Feasible (state="ACCEPTED") + Hiển thị nút "↩️ Hoàn Tác (Undo)"
    else Người dùng bấm "✖ Hủy Xem Trước (Cancel Preview)" hoặc "↩️ Hoàn Tác (Undo)"
        User->>UI: Bấm "Hủy Xem Trước" / "Hoàn Tác"
        UI->>UI: Khôi phục state.tasks & state.lastSchedule từ bản gốc
        UI-->>User: Trả lại trạng thái lưới lịch ban đầu
    end
```

---

## 3. State Machine Diagram — Schedule & Overload Resolution Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Idle_Unplanned : Khởi tạo / Nạp Preset hoặc Scenario (T01..T10)

    Idle_Unplanned --> Solving_Schedule : POST /api/plan (Chạy thuật toán xếp lịch)

    state Solving_Schedule {
        [*] --> Running_Solver
        Running_Solver --> Check_Feasibility : Kiểm tra unplaced_tasks & overload_reports
    }

    Check_Feasibility --> Feasible_Schedule : unplaced == 0 (status = SUCCESS)
    Check_Feasibility --> Overloaded_Detected : unplaced > 0 (PARTIAL_OVERLOAD / NO_SCHEDULE_FOUND)

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
    Previewing_Option -->Previewing_Option : Chọn "Xem Trước" một Option khác (O1 <-> O2 <-> O3)
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
