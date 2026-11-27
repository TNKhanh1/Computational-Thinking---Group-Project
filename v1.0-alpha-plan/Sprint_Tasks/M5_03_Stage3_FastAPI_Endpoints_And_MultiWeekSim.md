# M5_03 — Stage 3 Plan: FastAPI Endpoints, Real-User Telemetry Bridge & Multi-Week Simulation (`app.py`)
**Trạng thái Stage 3:** `[x] DONE`  
**Nhánh Git:** `v1.0-alpha/m5-cross-week-adaptation-and-repair`  
**Điều kiện tiên quyết:** Stage 1 (`M5_01`) & Stage 2 (`M5_02`) đã `[x] DONE`  
**Phạm vi File của Stage 3 (DUY NHẤT 1 FILE):**
1. **MODIFY:** `smartschedule/api/app.py` *(M5 độc quyền sở hữu 100% trong toàn bộ Sprint!)*

---

## 1. MỤC TIÊU & NGUYÊN TẮC AN TOÀN KHI SỬA `smartschedule/api/app.py`

1. **Bảo toàn 100% các Endpoint hiện hữu:** Không đổi đường dẫn, mã HTTP, hay cấu trúc JSON của bất kỳ API cũ nào (`/api/solve`, `/api/plan`, `/api/repair`, `/api/overrun`, `/api/progress`, `/api/chat/turn`, `/api/tasks/complete`, `/api/state`, `/api/benchmark-all`, v.v.) để toàn bộ `Testing_System/tests` (`http` mode) và `tests/ui/*` giữ xanh tuyệt đối.
2. **Tối ưu gọi lặp `apply_estimate_buffer` (`Fix M-1` / `A3`):**
   - Trong `api_solve_schedule` (`/api/solve`), `api_compare_algorithms`, `api_task_overrun`: truyền `apply_buffer=False` vào `_extract_profile_and_tasks(payload, apply_buffer=False)` vì ngay dòng kế tiếp `ScheduleController.solve_schedule` / `compare_algorithms` / `handle_task_overrun` đã tự gọi `apply_estimate_buffer` bên trong! (Giữ nguyên `apply_buffer=True` cho `api_repair_schedule` vì `LocalRepairEngine.repair_disruption` nhận danh sách task đã qua buffer).
3. **Đồng bộ Hợp đồng API 100% với `README_agents.md §2.2`**, đồng thời linh hoạt chấp nhận cả tên trường viết tắt của Frontend (`M1` `onboarding.js` & `M6` `api.js`).

---

## 2. ĐẶC TẢ TỪNG ENDPOINT & CẦU NỐI TRONG `smartschedule/api/app.py`

### 2.1. Nối An Toàn `disruption_chat.py` Vào `POST /api/chat/turn` (`app.py` dòng ~725)
- `M5` không được sửa `handlers.py` (của `M4`), nhưng `POST /api/chat/turn` trong `app.py` thuộc quyền của `M5`!
- Để `POST /api/chat/turn` xử lý mượt câu báo sự cố đột xuất **ngay ở Wave 1A** (trước khi `M4` merge) VÀ **không bị gọi đúp** sau khi `M4` merge `handlers.py`:
  - Trong `api_chat_turn`:
    - Kiểm tra `prompt_str = str(enriched_payload.get("prompt") or enriched_payload.get("text") or "").strip()`
    - `mode_hint = str(enriched_payload.get("mode_hint") or "AUTO").strip().upper()`
    - `pending_draft = enriched_payload.get("pending_draft") if isinstance(enriched_payload.get("pending_draft"), dict) else None`
    - Nếu `is_disruption_intent(prompt_str, mode_hint=mode_hint, pending_draft=pending_draft)` là `True`:
      gọi trực tiếp `return handle_disruption_chat_turn(enriched_payload)`!
    - Ngược lại chuyển tiếp nguyên vẹn sang `return process_chat_turn(enriched_payload)`.
  - *Vì sao không bao giờ xung đột với `M4`?* Khi `is_disruption_intent` trả về `True`, `handle_disruption_chat_turn` trả về kết quả cuối cùng luôn và không đi vào `process_chat_turn`; còn nếu `M4` gọi `handle_disruption_chat_turn` từ bên trong `process_chat_turn` trong unit test riêng của `M4`, nó vẫn chạy đúng hàm đó 100%!

---

### 2.2. Ghi Vết Sự Cố & Buổi Học Thật Cho Người Dùng Thực Tế (`Fix M-5`)
1. **Helper nội bộ `_load_or_extract_workspace_bundle(payload, request)`:**
   - Giải quyết `ws_id = resolve_workspace_id(request, str(payload.get("workspace_id") or "default"))`.
   - Đọc `saved_record = load_workspace_state(workspace_id=ws_id)` (nếu có).
   - Nếu `payload` không gửi kèm `commitments` / `tasks`, tự động lấy từ `saved_record["state"]` (hỗ trợ cả khóa `commitments` lẫn `profile`, `pinned_blocks` lẫn `pinnedBlocks`).
2. **Trong `/api/repair` (`api_repair_schedule`):**
   - Nếu `payload.get("workspace_id")` được gửi kèm (hoặc workspace tồn tại trong SQLite) và `mode` không phải `COMPARE_BOTH`, tự động ghi nhẹ sự kiện đột xuất `{event_id, title, day_of_week, start_time, end_time, disruption_slot_window}` vào `state["disruption_logs"]` (tối đa 50 mục) nếu `payload.get("persist_log", False)` hoặc khi sửa lịch trên workspace đang lưu.
3. **Helper nội bộ `_synthesize_real_user_timeline_logs(ws_id, profile, provided_logs)` (Trái tim của `Fix M-5`):**
   - Nếu `provided_logs` (từ `payload.get("timeline_logs")`) đã có sẵn dữ liệu $\to$ bắt đầu từ bản sao của `provided_logs`.
   - Nếu `provided_logs` rỗng hoặc thiếu dữ liệu, tự động lấy `completion_rows = list_completion_logs(workspace_id=ws_id, limit=200)` kết hợp với `saved_state = (load_workspace_state(ws_id) or {}).get("state") or {}`:
     - Tra bảng ánh xạ `task_id -> block` từ `(saved_state.get("currentSchedule") or {}).get("blocks") or []` và `completed_blocks = saved_state.get("completedBlocks") or {}`:
       - Nếu một block trong lịch tuần trước có mặt trong `completed_blocks` $\to$ biết chính xác `start_time` (suy ra `window`), `cognitive_load`, `adhered = True`.
       - Nếu lịch tuần trước đã qua (`currentSchedule.blocks` có các ca thuộc các ngày trước `now`) mà block **không** nằm trong `completed_blocks` khi người dùng bấm tổng kết sang tuần mới (`include_uncompleted_scheduled_blocks=True` khi có ít nhất 1 `completedBlocks` được ghi nhận trong tuần!) $\to$ ghi nhận `adhered = False` ở đúng `window` đó để tính chính xác `AdherenceRate(w)`!
     - Nối thêm các mục trong `saved_state.get("disruption_logs") or []` dưới dạng các dòng log mang `disruption_slot_window` để Nhánh 3 (`chronic_disruption_zones`) hoạt động thật 100% trên dữ liệu người dùng!

---

### 2.3. Chi Tiết 6 Endpoint Mới Trong `smartschedule/api/app.py`

#### Endpoint 1: `POST /api/workspace/init-real-week` (`M5` $\leftrightarrow$ `M1` `onboarding.js` & `M6` `api.js`)
- **Input chấp nhận linh hoạt cả 2 bộ tên khóa** (vì `M1_Pham_Duc_Minh.md` dòng 35 viết `daily_start_time, daily_end_time`, còn `README_agents.md` dòng 62 viết `sleep_start, sleep_end`!):
  - `sleep_start = str(payload.get("sleep_start") or payload.get("daily_start_time") or "23:30")`
  - `sleep_end = str(payload.get("sleep_end") or payload.get("daily_end_time") or "06:30")`
  - `focus_preference = str(payload.get("focus_preference") or "BALANCED")`
  - `estimate_habit = payload.get("estimate_habit", "SOMETIMES")`
  - `student_id = str(payload.get("student_id") or "STUDENT_USER")`
  - `persist = bool(payload.get("save", True))`
- **Xử lý:**
  - Gọi `profile = ScheduleController.build_empty_current_week_profile(student_id=student_id, daily_start_time=sleep_start, daily_end_time=sleep_end, focus_preference=focus_preference, estimate_habit=estimate_habit)`.
  - Gọi `out, _, _ = ScheduleController.solve_adaptive(profile=profile, tasks=[], algorithm="SCORED_GREEDY", pinned_blocks=[])`.
  - `enriched = _enrich_response(out, profile=profile, raw_tasks=[], pinned_blocks=[])`.
  - Nếu `persist` là `True`: lưu state mới sạch sẽ vào SQLite (`save_workspace_state({"commitments": profile.model_dump(), "tasks": [], "pinnedBlocks": [], "completedBlocks": {}, "activeSolver": "SCORED_GREEDY", "currentSchedule": enriched, "chatMessages": [], "disruption_logs": []}, workspace_id=ws_id)`).
- **Output (khớp `README_agents.md §2.2`):**
  ```python
  {
      "workspace_id": ws_id,
      "commitments": profile.model_dump(),
      "tasks": [],
      "pinned_blocks": [],
      "schedule": enriched,
  }
  ```

---

#### Endpoint 2: `POST /api/tasks/delete` (`M5` $\leftrightarrow$ `M6` `modals.js` / `api.js`)
- **Input:** `workspace_id`, `task_id` (bắt buộc không rỗng, nếu rỗng raise `HTTPException(400)`), cùng tùy chọn `commitments`, `tasks`, `pinned_blocks`, `algorithm` (nếu thiếu thì nạp từ SQLite `workspace_state`).
- **Xử lý sạch ca biên DAG:**
  - Lọc bỏ task có `t.task_id == task_id` khỏi danh sách `raw_tasks`.
  - **Dọn sạch tham chiếu mồ côi (`depends_on`):** Với mọi task còn lại, nếu `task_id` nằm trong `t.depends_on`, loại bỏ `task_id` khỏi `t.depends_on` để không gây lỗi đồ thị mồ côi!
  - Lọc bỏ mọi block trong `pinned_blocks` có `pb.task_id == task_id`.
  - Gọi `out, _, _ = ScheduleController.solve_adaptive(profile=profile, tasks=kept_tasks, algorithm=algo, pinned_blocks=kept_pins)`.
  - Nếu workspace đang tồn tại trong SQLite (hoặc `payload.get("save") is True`), cập nhật lại `tasks`, `pinnedBlocks`, `currentSchedule` vào SQLite.
- **Output (khớp `README_agents.md §2.2`):**
  ```python
  {
      "deleted_task_id": task_id,
      "updated_tasks": [t.model_dump() for t in kept_tasks],
      "updated_pinned_blocks": [pb.model_dump() for pb in kept_pins],
      "schedule": _enrich_response(out, profile=profile, raw_tasks=kept_tasks, pinned_blocks=kept_pins),
  }
  ```

---

#### Endpoint 3 & 4: `POST /api/fixed-events/upsert` & `POST /api/fixed-events/delete` (`M5` $\leftrightarrow$ `M6` `render-list.js` / `api.js`)
- **Cho `upsert`:**
  - Nhận `event_raw = payload.get("event") or payload.get("fixed_event")`; nếu không phải dict $\to$ `HTTPException(400)`.
  - Nếu `event_raw` chưa có `event_id` / `id` $\to$ tự sinh `f"EVENT_{uuid.uuid4().hex[:6].upper()}"`.
  - Validate `ev = FixedEvent.model_validate(event_raw)` (kiểm tra `end_time` hợp lệ khác `start_time`).
  - Nếu trong `profile.fixed_events` đã có phần tử trùng `ev.event_id` $\to$ thay thế đúng vị trí đó; ngược lại `append(ev)`.
  - Giải lại lịch bằng `ScheduleController.solve_adaptive(...)`, lưu SQLite nếu workspace tồn tại hoặc `save=True`.
  - Trả về `{"event": ev.model_dump(), "updated_commitments": updated_profile.model_dump(), "schedule": enriched}`.
- **Cho `delete`:**
  - Nhận `event_id = str(payload.get("event_id") or "").strip()`; nếu rỗng $\to$ `HTTPException(400)`.
  - Lọc bỏ sự kiện có `fe.event_id == event_id` khỏi `profile.fixed_events`.
  - Giải lại lịch bằng `ScheduleController.solve_adaptive(...)`, lưu SQLite nếu workspace tồn tại hoặc `save=True`.
  - Trả về `{"deleted_event_id": event_id, "updated_commitments": updated_profile.model_dump(), "schedule": enriched}`.

---

#### Endpoint 5: `POST /api/workspace/adapt-next-week` (`Pattern P13`, Chuẩn `LoA-4` `apply=False` mặc định)
- **Input:**
  - `workspace_id`, `commitments` (tùy chọn — fallback sang SQLite state), `next_week_tasks` (hoặc `tasks` — fallback sang tasks trong SQLite state), `timeline_logs` (tùy chọn), `kappa` (mặc định `3.0`), `advance_week` (`bool`, mặc định `True`: tự tịnh tiến `planning_week_start` sang Thứ Hai tuần kế tiếp `+7 ngày` nếu đang lập cho tuần tới!), và **`apply: bool = False` (MẶC ĐỊNH `False` — chuẩn `LoA-4`!)**.
- **Xử lý:**
  - Tổng hợp `effective_logs = _synthesize_real_user_timeline_logs(ws_id, profile, payload.get("timeline_logs"))`.
  - Gọi `adapt_res = adapt_preferences_for_next_week(profile=base_profile, next_tasks=raw_next_tasks, timeline_logs=effective_logs, kappa=kappa)`.
  - Lấy `adapted_profile = adapt_res["adapted_profile"]`, `adapted_tasks = adapt_res["adapted_tasks"]`.
  - Chạy `out, _, _ = ScheduleController.solve_adaptive(profile=adapted_profile, tasks=adapted_tasks, algorithm=algo)`.
  - **Nếu và chỉ nếu `bool(payload.get("apply", False)) is True`:** lưu `adapted_commitments`, `adapted_tasks_dump`, `currentSchedule` vào SQLite `workspace_state`!
- **Output (khớp `README_agents.md §2.2`):**
  ```python
  {
      "workspace_id": ws_id,
      "applied": bool(payload.get("apply", False)),
      "adapted_commitments": adapt_res["adapted_commitments"],
      "adapted_tasks": adapt_res["adapted_tasks_dump"],
      "category_alphas": adapt_res["category_alphas"],
      "preference_shifts": adapt_res["preference_shifts"],
      "chronic_disruption_zones": adapt_res["chronic_disruption_zones"],
      "pattern_rules": adapt_res["pattern_rules"],
      "schedule": _enrich_response(out, profile=adapted_profile, raw_tasks=adapted_tasks),
  }
  ```

---

#### Endpoint 6: `POST /api/simulation/multi-week` (`Pattern P13 + P14b`, `< 500 ms` SLA & `SHA-256` Determinism — `Fix M-6`)
- **Input:**
  - `weeks: int = int(payload.get("weeks") or 4)` (kẹp an toàn `1..12`).
  - `n_students: int = int(payload.get("n_students") or 1)` (mặc định **`1`** để đạt tốc độ tương tác trực tiếp **`< 500 ms`** trên `SCORED_GREEDY`; kẹp tối đa `1..50` cho chế độ thống kê lô!).
  - `seed: int = int(payload.get("seed") if payload.get("seed") is not None else 42)`.
  - `algorithm: str = str(payload.get("algorithm") or "SCORED_GREEDY")`.
  - `commitments` & `tasks` (tùy chọn): **Nếu caller không gửi kèm `commitments` / `tasks`**, tự động tạo bộ đề chuẩn kiểm định đóng vòng (*Default Benchmark Persona*):
    - Sinh viên tự khai báo nhầm `"MORNING"` (nhưng đỉnh năng lượng tiềm ẩn thực tế là Cú Đêm `true_peak_hour = 20.5`),
    - Thường đánh giá thấp nhóm bài `CODING` (`×1.45`) và `PROJECT` (`×1.38`) trong khi `READING` chuẩn (`×1.05`),
    - Gồm 6–7 công việc học tập đa dạng (`CODING`, `PROJECT`, `ASSIGNMENT`, `READING` có cả `cognitive_load = 3` ở `MORNING` ban đầu để lộ rõ sự lột xác từ Tuần 1 sang Tuần 4!),
    - Kèm sự cố CLB lặp lại tối Thứ Năm `19:30–21:00`.
- **Tích hợp Động `M7` Kèm Nhánh Dự Phòng Tự Thân (`try / except ImportError`):**
  - Thử `from smartschedule.core.student_simulator import InSilicoStudentSimulator`.
  - Nếu `InSilicoStudentSimulator` chưa có trên nhánh (khi `M5` chạy test độc lập ở Wave 1A trước khi merge với `M7`), kích hoạt class nội bộ `_FallbackStudentSimulator` (~60 dòng Python thuần dùng riêng `random.Random(student_seed)` cô lập, cài đặt đúng 5 phương trình: `CircFit` tròn quanh `20.5h`, `LogNormal` theo môn, `Steel 2007 TMT` có mẫu số $1 + \Gamma \cdot s_h/24$, `McFadden RUM` logit, và tích lũy/phục hồi `fatigue` + sự cố tối Thứ Năm) trả về `timeline_logs` đúng hệt định dạng 14 khóa của `M7`!
  - *(Lưu ý kỹ thuật cực hay cho `n_students >= 10` để tốc độ luôn nhanh):* Khi `n_students == 1` (mặc định demo), chạy full `SCORED_GREEDY` (`4 lần giải ≈ 120–280 ms < 500 ms`!). Khi `n_students > 1` (chạy thống kê đoàn hệ `N=25`), vẫn chạy vòng lặp đóng `Week 1..K` cho từng `student_idx` với `seed_i = seed + student_idx * 9973` và gộp trung bình theo từng tuần `1..K`!
- **Vòng lặp đóng qua `w = 1 .. weeks` cho mỗi sinh viên:**
  1. Lưu bản sao công việc gốc chưa nhân đệm của mẫu tuần (`raw_template_tasks`), mỗi tuần truyền vào bộ giải cùng `cur_profile` và `cur_tasks` (từ Tuần 2 trở đi là kết quả của `adapt_preferences_for_next_week(cur_profile, raw_template_tasks, cumulative_logs)` — nhờ truyền `raw_template_tasks` gốc nên **không bao giờ nhân đệm chồng lên nhau qua nhiều tuần**, mà `cumulative_logs` tích lũy giúp $n_c$ tăng dần $1 \to 4 \to 8 \to 12$ làm $\hat{\alpha}_{c,\ell}$ hội tụ mượt mà!).
  2. Chạy giải lịch Tuần `w` $\to$ mô phỏng sinh viên thực thi Tuần `w` nhận `week_logs`.
  3. Tính chỉ số thực thi thực tế của Tuần `w`:
     - `adherence_pct`: `%` số phiên được xếp lịch mà sinh viên thực sự bám lịch hoàn thành (`adhered == True`).
     - `on_time_value_pct`: `%` tổng trọng số `priority` của các công việc hoàn thành trọn vẹn không bị bỏ dở/vượt hạn khi cộng cả `actual_duration_min` (tăng rõ rệt khi $\hat{\alpha}_{\text{CODING}}$ và `EVENING` được học đúng ở Tuần 2–4!).
- **Kiểm tra hội tụ & Băm tất định `SHA-256`:**
  - `converged = bool(len(weeks_summary) >= 2 and (weeks_summary[-1]["adherence_pct"] >= weeks_summary[0]["adherence_pct"]) and (weeks_summary[-1]["on_time_value_pct"] >= weeks_summary[0]["on_time_value_pct"]))`.
  - Tạo chuỗi JSON chuẩn hóa `json.dumps({"seed": seed, "weeks": weeks, "n_students": n_students, "weeks_summary": weeks_summary}, sort_keys=True)` (không chứa `execution_time_ms`!) và băm `hashlib.sha256(...).hexdigest()` $\to$ đảm bảo 3 lần gọi với cùng `seed=42` trả về **`determinism_hash` giống hệt nhau từng ký tự 100%**!
- **Output (khớp 100% `README_agents.md §2.2` dòng 75):**
  ```python
  {
      "weeks": weeks,
      "n_students": n_students,
      "seed": seed,
      "simulator_backend": "InSilicoStudentSimulator" | "DeterministicFallbackTwin",
      "weeks_summary": weeks_summary,  # [{"week": 1, "adherence_pct": ..., "on_time_value_pct": ..., "learned_alphas": {...}, "learned_focus": "..."}, ...]
      "converged": converged,
      "determinism_hash": det_hash,
      "execution_time_ms": exec_ms,
  }
  ```

---

## 3. LỆNH KIỂM THỬ ĐỘC LẬP KẾT THÚC STAGE 3

Sau khi cập nhật xong `smartschedule/api/app.py`, chạy ngay lệnh kiểm thử tích hợp nhanh qua `TestClient`:
```powershell
python -B -c "from fastapi.testclient import TestClient; from smartschedule.api.app import app; c = TestClient(app); r1 = c.post('/api/workspace/init-real-week', json={'workspace_id': 'test_m5_stage3', 'save': False}); assert r1.status_code == 200, r1.text; s1 = c.post('/api/simulation/multi-week', json={'weeks': 4, 'n_students': 1, 'seed': 42}).json(); s2 = c.post('/api/simulation/multi-week', json={'weeks': 4, 'n_students': 1, 'seed': 42}).json(); assert s1['determinism_hash'] == s2['determinism_hash']; assert s1['weeks_summary'][-1]['on_time_value_pct'] >= s1['weeks_summary'][0]['on_time_value_pct'], s1; print('STAGE 3 SMOKE OK:', s1['execution_time_ms'], 'ms | W1->W4:', s1['weeks_summary'][0]['on_time_value_pct'], '->', s1['weeks_summary'][-1]['on_time_value_pct'])"
python -B -m pytest tests/ui/test_ui_v3_endpoints.py -q
```
Nếu cả 2 lệnh đều PASS 100%, đánh dấu `[x] DONE` ở đầu file này và trong [`M5_00_Master_Index.md`](./M5_00_Master_Index.md), rồi chuyển sang giai đoạn khóa sổ [`M5_04_Stage4_TestSuite_AuditGate_And_PR.md`](./M5_04_Stage4_TestSuite_AuditGate_And_PR.md).
