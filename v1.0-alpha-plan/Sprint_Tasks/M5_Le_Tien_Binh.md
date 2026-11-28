# M5 — Lê Tiến Bình (`25125007`) · Builder 1 (Core Engineering & Idea Lead)
**Vai trò theo `work_division.pdf` & Sprint Nâng Cấp:** Builder 1 · Lead **§7 System Architecture**, Support **§6 Algorithmic Design** · **Core Technical Lead (cùng `M7` Gia Bảo & `M4` Trọng Tiến)**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m5-cross-week-adaptation-and-repair`  
**Đợt thực hiện (Wave):** **Wave 1A — Ưu tiên Merge đầu tiên** (Tạo PR trước **22:00 Thứ Sáu, 27/11/2026**)

---

## 1. Trọng Tâm Của Bạn Trong Kế Hoạch Nâng Cấp Điểm Tối Đa
Cùng với Gia Bảo (`M7`) và Trọng Tiến (`M4`), bạn đảm nhận phần **động cơ học thích nghi xuyên tuần & sửa lịch cục bộ** để giải quyết trọn vẹn câu hỏi cốt lõi của dự án mà không cần chạm vào 6 bộ giải tĩnh (`smartschedule/core/solvers/*`):

1. **Động cơ Học Thích Nghi Fallacy Buffer & Sở Thích Cho Tuần Kế Tiếp (`smartschedule/core/cross_week_adapter.py` — Pattern `P13`, hiện thực hóa `Proposal §7.8.3 & §7.8.4`):**
   - Hiện tại `calibration.py` mới chỉ tính 2 con số EWMA chung (`alpha_light`, `alpha_heavy`) và chưa có cơ chế **tự điều chỉnh hệ số đệm & sở thích công việc cho tuần kế tiếp dựa trên hành vi thực thi đã ghi nhận ở các tuần trước**!
   - Bạn xây dựng `cross_week_adapter.py` (Pure Layer 1) để từ nhật ký thực thi tuần trước (`timeline_logs` + `completion_logs`) tự động suy ra cho tuần kế tiếp (theo chuẩn LoA-4 có giải thích rõ):
     1) **Hệ số đệm Co rút Bayes–EWMA theo từng Nhóm môn & Độ nặng ($\hat{\alpha}^{(t+1)}_{c,\ell}$):** Ví dụ sinh viên làm `CODING` luôn lố `×1.42` nhưng `READING` chỉ `×1.08` $\to$ công thức co rút $\hat{\alpha}_{c,\ell} = \text{clip}\big(\frac{n_c}{n_c+\kappa}\text{EWMA}_c + \frac{\kappa}{n_c+\kappa}\alpha_0(\ell),\, 1.00,\, 1.60\big)$ ($\kappa=3$) học chính xác ngay từ tuần đầu ($n_c=1..4$) mà không bị vọt quá vách đá $\alpha \ge 1.70$, rồi gán thẳng vào `Task.alpha_light` / `Task.alpha_heavy` của tuần mới!
     2) **Học Sở thích Khung giờ Thực tế (*Stated vs. Revealed Chronotype*):** Tính điểm hiệu quả bám lịch theo buổi (`MORNING`, `AFTERNOON`, `EVENING`). Nếu sinh viên tự nhận là người dậy sớm (`MORNING`) nhưng tuần trước toàn bỏ/lố giờ ca sáng và hoàn thành xuất sắc ca tối $\to$ đề xuất đổi `focus_preference` / `CircadianEnergyProfile.hourly_levels` và `Task.preferred_window` cho tuần tới!
     3) **Điều nhịp Phục hồi sau Tuần Căng & Khoanh Vùng Sự Cố Lặp Lại (`§7.8.4`):** Nếu tuần trước mệt mỏi cao / dính Crunch hoặc các ca `90p FLOW` bị đứt gãy $\to$ hạ `work_rhythm` sang `BALANCED` (`45–60p`); nếu một khung giờ (vd: tối Thứ 5 `19:30–21:00`) bị sự cố đột xuất $\ge 2$ lần $\to$ đánh dấu `chronic_disruption_zones` để né xếp việc nặng vào khung đó!
2. **Xử lý Sự cố Đột xuất qua Chat bằng `LocalRepairEngine` (`disruption_chat.py` — Pattern `P8`, giữ ổn định $\ge 90\%$)** + **API Khởi tạo Tuần Hiện Tại, Xóa/Sửa Lẻ & Chạy Thực Nghiệm Thích Nghi Đa Tuần (`controller.py` & `app.py`).**

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (`0%` Merge Conflict Guarantee)
- **CREATE:**
  - `smartschedule/core/cross_week_adapter.py` *(Pure Layer 1: Python stdlib + `smartschedule.core.{calibration,config,models,utils}` ONLY!)*
  - `smartschedule/api/chat/disruption_chat.py`
  - `tests/logical/test_disruption_and_cross_week_adapter.py`
- **MODIFY (Wave 1A ONLY):**
  - `smartschedule/core/controller.py` *(SOLE OWNER in this sprint!)*
  - `smartschedule/api/app.py` *(SOLE OWNER in this sprint!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*` *(keep all 6 solvers 100% bit-identical!)*, `smartschedule/core/models.py` *(already has `Task.alpha_light`, `Task.alpha_heavy`, `CircadianEnergyProfile.hourly_levels`!)*, `smartschedule/api/chat/handlers.py` (`M4`), or `smartschedule/ui/*`.

### Engineering Requirements
1. **Cross-Week Fallacy Buffer & Preference Adaptation Engine (`smartschedule/core/cross_week_adapter.py`):**
   - Implement `adapt_preferences_for_next_week(profile: CommitmentsProfile, next_tasks: list[Task], timeline_logs: list[dict], kappa: float = 3.0) -> dict[str, Any]`:
     - **Shrinkage Category Fallacy Buffers:** Group `timeline_logs` by `category` (and `cognitive_load >= 3`). Clip each ratio $r_k = \text{clip}(d_{\text{act}} / d_{\text{est}}, 0.50, 2.50)$, compute chronological EWMA ($\lambda = 0.30$), and apply empirical Bayes shrinkage toward prior $\alpha_0(\ell) \in \{1.20, 1.35\}$:
       $$\hat{\alpha}_{c,\ell} = \text{clip}\!\left(\frac{n_c}{n_c + \kappa}\text{EWMA}_c + \frac{\kappa}{n_c + \kappa}\alpha_0(\ell),\; 1.00,\; 1.60\right)$$
       Apply $\hat{\alpha}_{c,\ell}$ onto copies of `next_tasks` (`t.buffer_mode = "COGNITIVE_LOAD"`, `t.alpha_light = alpha_c_light`, `t.alpha_heavy = alpha_c_heavy`, `t.buffer_multiplier = alpha_c`) — **never double-buffering already-buffered durations!**
     - **Revealed Chronotype & Window Preference Shift:** For each window $w \in \{\texttt{MORNING}, \texttt{AFTERNOON}, \texttt{EVENING}\}$, compute $\text{Eff}(w) = \text{AdherenceRate}(w) \times \text{clip}(\overline{d_{\text{est}}/d_{\text{act}}}, 0.60, 1.25)$ when $n_w \ge 2$. If the best revealed window exceeds the stated `focus_preference` window by $\ge 0.22$, update `adapted_profile.focus_preference` (and `hourly_levels`) and set `preferred_window` on deep tasks (`load == 3`) lacking explicit user window locks.
     - **Pacing & Chronic Disruption Zones (`Proposal §7.8.4`):** If mean fatigue $> 0.65$ or overrun rate on `> 60m` blocks $\ge 50\%$, adapt splittable deep tasks to `work_rhythm="BALANCED"` (`45–75m`); if `disruption_slot_window` repeats $\ge 2$ times on the same `(day, hour_band)`, emit `chronic_disruption_zones` and lower `hourly_levels` on that band (or add an advisory reserve event).
     - Return structured diff explanation `preference_shifts` (Vietnamese & formal rule trace for `Pattern P13`).
2. **Conversational Disruption Repair (`smartschedule/api/chat/disruption_chat.py` — Pattern `P8`):**
   - Expose `handle_disruption_chat_turn(...)`: parse weekday + `start_time`–`end_time`, invoke `LocalRepairEngine.repair_disruption(..., mode="LOCAL_INSERTION")`, append the new `FixedEvent`, and return standard `/api/chat/turn` dict highlighting `stability_score` ($\ge 90\%$) + `Pattern P8` trace in `thinking_summary`.
3. **Controller Helpers & FastAPI Endpoints (`smartschedule/core/controller.py` & `smartschedule/api/app.py`):**
   - `ScheduleController.build_empty_current_week_profile(...)` (computes real local Monday `00:00:00+07:00` without touching `data/presets/*`!).
   - `POST /api/workspace/init-real-week`, `POST /api/tasks/delete`, `POST /api/fixed-events/upsert`, `POST /api/fixed-events/delete`.
   - `POST /api/workspace/adapt-next-week`: Runs `adapt_preferences_for_next_week(...)` using stored `completion_logs` + optional `timeline_logs`, solves next week's schedule, and saves if `apply=True`.
   - `POST /api/simulation/multi-week`: Dynamically imports `InSilicoStudentSimulator` from `smartschedule.core.student_simulator` (`try/except ImportError` safe!) and runs a seeded `K`-week (`default=4`) closed-loop simulation (`Solve Week k -> Simulate Student -> Adapt Preferences for Week k+1`), returning week-by-week convergence metrics + deterministic `SHA-256` hash in `< 500 ms`!

### Verification Commands (Must Pass 100% Before PR)
```powershell
python -B -m pytest tests/logical/test_disruption_and_cross_week_adapter.py tests/logical/test_p2_alpha_calibration.py -q
python -B tests/clean_runner.py --pass
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [x] Xây dựng `smartschedule/core/cross_week_adapter.py` (học hệ số đệm Bayes–EWMA theo môn $\in [1.00, 1.60]$ + học lại nhịp sinh học/nhịp tách phiên từ hành vi tuần trước — gửi `M4` Trọng Tiến kiểm định bằng Claude Plan).
- [x] Tạo `smartschedule/api/chat/disruption_chat.py` nối câu báo bận đột xuất vào `LocalRepairEngine` (`LOCAL_INSERTION`, giữ ổn định $\ge 90\%$).
- [x] Bổ sung `build_empty_current_week_profile()` trong `controller.py` và mở đủ các API (`init-real-week`, CRUD lẻ, `adapt-next-week`, `simulation/multi-week`) trong `app.py`.
- [x] Viết test `tests/logical/test_disruption_and_cross_week_adapter.py` và chạy xanh `clean_runner.py --pass` + `Testing_System/tests`.
