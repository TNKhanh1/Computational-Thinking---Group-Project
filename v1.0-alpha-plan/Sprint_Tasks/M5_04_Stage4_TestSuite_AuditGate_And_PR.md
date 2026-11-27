# M5_04 — Stage 4 Plan: Comprehensive Test Suite, `M4` Audit Self-Gate, Full Regression & PR Ready
**Trạng thái Stage 4:** `[x] DONE`  
**Nhánh Git:** `v1.0-alpha/m5-cross-week-adaptation-and-repair`  
**Điều kiện tiên quyết:** Stage 1 (`M5_01`), Stage 2 (`M5_02`) & Stage 3 (`M5_03`) đều đã `[x] DONE`  
**Phạm vi File của Stage 4:**
1. **CREATE:** `tests/logical/test_disruption_and_cross_week_adapter.py`
2. **MODIFY (Sau khi mọi test đều PASS 100%):** Tick `[x]` vào 4 dòng checklist cuối file [`M5_Le_Tien_Binh.md`](./M5_Le_Tien_Binh.md)

---

## 1. MỤC TIÊU CỦA STAGE 4: VƯỢT QUA CỔNG KIỂM ĐỊNH CỦA `M4` (CLAUDE-PLAN AUDIT) NGAY TỪ LẦN ĐẦU

Trong [`M4_Nguyen_Trong_Tien.md`](./M4_Nguyen_Trong_Tien.md#L42-L49), Trọng Tiến (`M4`) sẽ chạy quy trình kiểm định độc lập trên PR của `M5` với **5 bất biến toán học & hệ thống**. Vì vậy bộ test `tests/logical/test_disruption_and_cross_week_adapter.py` của chúng ta phải kiểm tra và khóa cứng toàn bộ 5 bất biến này cộng với tất cả ca biên của `M-1` $\to$ `M-8`!

---

## 2. DANH SÁCH 18 BÀI TEST BẮT BUỘC TRONG `tests/logical/test_disruption_and_cross_week_adapter.py`

### Nhóm A — Kiểm định Toán học `CrossWeekPreferenceAdapter` (`Pattern P13` & `M4` Audit Invariants)
1. **`test_cold_start_zero_logs_preserves_priors` (`M4 Invariant #2a`):**
   - Khi `timeline_logs = []` ($n_c = 0$), kiểm tra $\hat{\alpha}_{c,\text{light}} == 1.20$, $\hat{\alpha}_{c,\text{heavy}} == 1.35$, không phát sinh `preference_shifts` ảo, `focus_preference` giữ nguyên.
2. **`test_single_extreme_outlier_clipped_and_shrunk_safely` (`M4 Invariant #2b` & `Fix M-2`):**
   - Đưa đúng $n_c = 1$ mẫu cực đoan $d_{\text{est}} = 60, d_{\text{act}} = 300$ ($A/E = 5.0$) cho `CODING` (`load=3`, $\alpha_0=1.35$, $\kappa=3.0$).
   - Kiểm tra tỷ số bị kẹp về `2.50`, **không bị co rút kép** ($\text{EWMA}_1 = 2.50$), và hệ số sau co rút Bayes bằng $\text{clip}(\frac{1}{4}(2.50) + \frac{3}{4}(1.35), 1.00, 1.60) = \text{clip}(1.6375, 1.00, 1.60) == \mathbf{1.60}$ (không bao giờ vượt trần vách đá $\alpha \ge 1.70$!).
3. **`test_no_double_shrinkage_sensitivity_at_small_sample` (`Fix M-2`):**
   - Với $n_c = 1$ mẫu vừa phải $r_1 = 1.52$ cho môn nhẹ ($\alpha_0 = 1.20, \kappa = 3.0$), kiểm tra $\hat{\alpha}_{c,\text{light}} == 0.25(1.52) + 0.75(1.20) = \mathbf{1.28}$ (chứng minh không bị bóp nghẹt về `1.224` do lỗi co rút kép).
4. **`test_multi_category_differentiation_and_no_double_buffering` (`M4 Invariant #1`):**
   - Truyền 4 mẫu `CODING` ($r \approx 1.45$) và 4 mẫu `READING` ($r \approx 1.02$).
   - Kiểm tra $\hat{\alpha}_{\text{CODING}} > 1.35 > \hat{\alpha}_{\text{READING}}$, tất cả nằm trong $[1.00, 1.60]$.
   - Gọi tiếp `adapt_preferences_for_next_week` lần thứ 2 trên `adapted_tasks` $\to$ kiểm tra `t.duration_min` gốc **không bao giờ bị nhân phình lên lần 2** (`t2.duration_min == raw_duration_min` và `t2.get_planned_duration_min() == t1.get_planned_duration_min()`!).
   - Task có `buffer_mode="NONE"` vẫn giữ nguyên `buffer_multiplier == 1.0`.
5. **`test_controller_preserves_per_category_task_alphas_during_solve` (`Fix M-1` — Critical Regression Test!):**
   - Tạo 2 task cùng `duration_min = 100, cognitive_load = 3` nhưng khác môn (`CODING` được adapter gán `alpha_heavy = 1.50` $\to$ `150m`; `READING` được gán `alpha_heavy = 1.05` $\to$ `105m`).
   - Chạy qua `ScheduleController.solve_schedule(adapted_profile, adapted_tasks, algorithm="SCORED_GREEDY")`.
   - Kiểm tra tổng thời lượng các block được xếp trên lịch của `CODING` đúng bằng `150m` và của `READING` đúng bằng `105m` (chứng minh `controller.apply_estimate_buffer` **không còn ghi đè xóa trắng** hệ số từng môn!), đồng thời block `CODING` có nhãn giải thích `ESTIMATE_BUFFER`.
6. **`test_revealed_chronotype_shift_lark_to_owl_and_guardrail` (`Fix M-6`):**
   - Sinh viên khai báo `focus_preference = "MORNING"`, nhưng 3 ca sáng bỏ lỡ 2 ca (`Adherence = 33%`), trong khi 3 ca tối hoàn thành đủ 3 ca đúng giờ (`Adherence = 100%`, $\Delta \text{Eff} \ge 0.22$).
   - Kiểm tra `adapted_profile.focus_preference == "EVENING"`, `hourly_levels[20] == 3`, và task `load == 3` chưa khóa cửa sổ được gợi ý `preferred_window == "EVENING"` (còn task đã khóa cứng `preferred_window == "AFTERNOON"` vẫn được tôn trọng giữ nguyên!).
   - Kiểm tra chiều ngược lại (Guardrail): nếu ca sáng vẫn đạt `Adherence = 100%` hiệu quả cao ngang ca tối ($\Delta \text{Eff} < 0.22$) $\to$ **không tự ý lật nhịp sinh học**.
7. **`test_pacing_adjustment_enforces_explicit_chunk_bounds_in_pydantic` (`Fix M-4`):**
   - Cho `timeline_logs` có `fatigue_after` trung bình `0.78` (hoặc 3/4 ca `90m` bị lố giờ) và 1 task `duration_min = 120, work_rhythm = "FLOW", max_chunk_min = 120`.
   - Kiểm tra task sau thích nghi có `max_chunk_min == 75`, `min_chunk_min == 45`, `is_splittable is True`, và khi đưa vào `SCORED_GREEDY` thì không có block đơn lẻ nào dài `120m`!
8. **`test_chronic_disruption_zone_adds_single_day_advisory_buffer_without_corrupting_other_days` (`Fix M-3`):**
   - Truyền 2 sự cố lặp lại `"Thursday 19:30-21:00"`.
   - Kiểm tra `chronic_disruption_zones` phát hiện đúng Thứ Năm `19:30–21:00`, thêm `FixedEvent(category="ADVISORY_BUFFER", day_of_week="Thursday")` vào `adapted_profile.fixed_events`, **VÀ kiểm tra năng lượng `adapted_profile.get_energy_profile().level_for_hour(20)` của các ngày khác trong tuần KHÔNG bị hạ xuống `1`**!

---

### Nhóm B — Kiểm định `disruption_chat.py` (`Pattern P8`, `Fix M-6` & `Fix M-8`)
9. **`test_disruption_intent_filtering_vs_recurring_and_tasks` (`Fix M-6`):**
   - Khẳng định `is_disruption_intent` trả `True` cho câu sự cố khẩn cấp/bận đột xuất, và trả `False` cho câu lịch học lặp lại hàng tuần (*"mỗi thứ 4"*, *"hằng ngày"*) hoặc thêm bài tập.
10. **`test_disruption_chat_missing_time_requests_clarification`:**
    - Gửi *"Chiều thứ 5 mình bận họp CLB đột xuất"* (thiếu giờ cụ thể) $\to$ nhận `status == "NEEDS_CLARIFICATION"`, có `pending_draft` và `quick_chips`; lượt 2 gửi tiếp *"Từ 14h đến 16h"* kèm `pending_draft` $\to$ nhận `status == "APPLIED"`!
11. **`test_disruption_chat_local_insertion_high_stability_and_p8_trace`:**
    - Trên lịch chuẩn `Minh's Week`, chèn sự cố đột xuất 90 phút đè lên 1 phiên học $\to$ kiểm tra `status == "APPLIED"`, `repair_summary["stability_score"] >= 90.0`, sự kiện mới nằm trong `updated_commitments["fixed_events"]`, và `thinking_summary["pattern_rules"]` chứa `pattern_id == "P8"`.
12. **`test_disruption_chat_dual_calling_convention_for_m4_compatibility`:**
    - Gọi `handle_disruption_chat_turn` theo **cả 2 kiểu** (truyền 1 `payload: dict` và truyền keyword arguments rời kiểu `M3`/`M4`) $\to$ cả hai đều chạy xanh không lỗi!

---

### Nhóm C — Kiểm định 6 FastAPI Endpoints, Người Dùng Thật SQLite & Mô Phỏng Đa Tuần (`Stage 3`)
*(Dùng `monkeypatch` trỏ `SMARTSCHEDULE_DB_PATH` hoặc `storage.DB_PATH` sang `tmp_path / "test_m5.db"` để không làm bẩn database thật của workspace!)*
13. **`test_api_init_real_week_computes_monday_and_keeps_presets_untouched`:**
    - Kiểm tra `POST /api/workspace/init-real-week` trả về đúng ngày Thứ Hai `00:00:00+07:00`, `tasks == []`, từ chối giờ ngủ `< 6h` (`400`), và file `data/presets/sample_week_commitments.json` không hề bị sửa đổi.
14. **`test_api_delete_task_cleans_dangling_dag_dependencies_and_pins`:**
    - Tạo 2 task `A -> B` (`B.depends_on = ["A"]`) và ghim 1 block của `A`. Gọi `POST /api/tasks/delete` xóa `A` $\to$ kiểm tra `A` biến mất, `B.depends_on == []` (sạch tham chiếu mồ côi!), block ghim của `A` bị gỡ, và `B` được xếp lịch thành công.
15. **`test_api_fixed_events_upsert_and_delete_roundtrip`:**
    - Gọi `POST /api/fixed-events/upsert` thêm mới $\to$ gọi lại `upsert` cập nhật giờ cùng `event_id` (không bị nhân đôi!) $\to$ gọi `POST /api/fixed-events/delete` xóa sạch.
16. **`test_api_adapt_next_week_from_real_sqlite_logs_loa4_preview_and_apply` (`Fix M-5`):**
    - Ghi 3 bản ghi thật qua `POST /api/tasks/complete` (`category="CODING"`, ước tính `60p`, thực tế `95p`).
    - Gọi `POST /api/workspace/adapt-next-week` với `apply=False` $\to$ trả về `category_alphas["CODING"]["alpha_heavy"] > 1.35`, nhưng đọc lại `GET /api/state` thấy state cũ chưa bị ghi đè (`LoA-4` an toàn!).
    - Gọi lại với `apply=True` $\to$ state trong SQLite được cập nhật sang tuần mới.
17. **`test_api_multi_week_simulation_determinism_convergence_and_sla` (`M4 Invariant #3 & #4`, `Fix M-6`):**
    - Gọi `POST /api/simulation/multi-week` (`{"weeks": 4, "n_students": 1, "seed": 42}`) **3 lần liên tiếp**:
      - Kiểm tra cả 3 mã `determinism_hash` giống hệt nhau 100%.
      - Kiểm tra `execution_time_ms < 1000.0` (mục tiêu `< 500 ms` trên máy bình thường).
      - Kiểm tra hội tụ đóng vòng: `weeks_summary[-1]["adherence_pct"] > weeks_summary[0]["adherence_pct"]` và `weeks_summary[-1]["on_time_value_pct"] > weeks_summary[0]["on_time_value_pct"]`!
    - Kiểm tra thêm chế độ đoàn hệ `{"weeks": 4, "n_students": 5, "seed": 42}` chạy mượt và trả về đúng 4 mốc tuần trung bình.
18. **`test_m5_layer_purity_and_memory_invariants` (`INV-1..5`):**
    - Kiểm tra AST của `smartschedule/core/cross_week_adapter.py` và `smartschedule/core/controller.py` tuyệt đối không chứa bất kỳ import cấm nào (`api`, `nlp`, `fastapi`, `spacy`, `transformers`, `docling`).

---

## 3. BỘ LỆNH KIỂM ĐỊNH CUỐI CÙNG TRƯỚC KHI CHỐT PR WAVE 1A (MANDATORY GATE)

Chạy tuần tự trọn bộ lệnh dưới đây từ thư mục gốc repository — **tất cả phải XANH 100% (`0` failed)**:

```powershell
# 1. Bộ test mới của M5 + Calibration + Kiến trúc & Bộ nhớ (< 350 KB)
python -B -m pytest tests/logical/test_disruption_and_cross_week_adapter.py tests/logical/test_p2_alpha_calibration.py tests/architecture/ -v

# 2. Toàn bộ bộ kiểm thử chuẩn của dự án
python -B tests/clean_runner.py --pass

# 3. Bộ kiểm thử bất biến Testing_System v2.1 (39/39 tests — xác nhận 0% hồi quy trên 6 solvers!)
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q

# 4. Kiểm tra danh sách file đã chạm so với nhánh main (Đảm bảo 0% đụng file cấm!)
git status -sb
git diff --name-only main
```

### Danh sách file hợp lệ duy nhất được phép xuất hiện trong `git diff --name-only main`:
- `smartschedule/core/cross_week_adapter.py`
- `smartschedule/core/controller.py`
- `smartschedule/api/chat/disruption_chat.py`
- `smartschedule/api/app.py`
- `tests/logical/test_disruption_and_cross_week_adapter.py`
- `v1.0-alpha-plan/Sprint_Tasks/M5_Le_Tien_Binh.md` *(tick `[x]` 4 dòng checklist)*
- *(Và các tài liệu kế hoạch/kiểm định `v1.0-alpha-plan/Sprint_Tasks/M5_*` của riêng `M5`)*

Sau khi tất cả lệnh trên đều xanh 100%, đánh dấu `[x] DONE` vào `M5_04`, `M5_00_Master_Index.md`, và 4 ô `[x]` trong `M5_Le_Tien_Binh.md` — sẵn sàng commit & mở PR Wave 1A!
