# M4 — Verification Notes: M5 (`ltbinh-m5-cross-week-adaptation-and-repair`) + M7 (`m7-simulator-and-doc-parser`)

**Người kiểm định:** Nguyễn Trọng Tiến (`M4`) · **Ngày:** 28/11/2026 · **Nhánh:** `verification` (từ `main` @ `8f334b1`)
**Commit đã rà:** `7230af4`, `0234d69` (M5 · Lê Tiến Bình) · `c3a68bf` (M7 · Gia Bảo)
**Môi trường test:** `group03-smartschedule-baseline/.venv` (Python 3.14 + fastapi 0.162). *Python hệ thống không có `fastapi` → hàng loạt lỗi import giả.*

---

## 1. Thay đổi so với `main`

| Nhánh | File | Nội dung |
|---|---|---|
| M5 | `core/cross_week_adapter.py` *(mới)* | `adapt_preferences_for_next_week`: Bayes–EWMA α theo môn, dời khung giờ ưu tiên (chronotype), chia nhỏ phiên khi mệt, khoanh vùng đệm `ADVISORY_BUFFER` khi sự cố lặp ≥ 2 lần |
| M5 | `core/controller.py` | `solve_adaptive` (tự nâng `SCORED_GREEDY → HYBRID_ALNS`), `build_empty_current_week_profile`, `inspect_repair_ergonomics`; `apply_estimate_buffer` giữ α riêng từng task |
| M5 | `api/chat/disruption_chat.py` *(mới)* | Chat báo bận đột xuất → `LocalRepairEngine` `LOCAL_INSERTION` (P8) |
| M5 | `api/app.py` | 6 endpoint mới: `init-real-week`, `tasks/delete`, `fixed-events/upsert`, `fixed-events/delete`, `workspace/adapt-next-week`, `simulation/multi-week`; `/api/chat/turn` chặn ý định "bận đột xuất" **trước** `process_chat_turn` |
| M7 | `core/student_simulator.py` *(mới)* | `InSilicoStudentSimulator` 5 phương trình (MCTQ, LogNormal, TMT Steel, RUM McFadden, Fatigue) |
| M7 | `nlp/doc_attachment_parser.py` *(mới)* | `parse_document_constraint_digest` + `detect_user_underestimate` |

Không nhánh nào sửa `smartschedule/ui/*` hay `core/solvers/*`. Hai nhánh không đụng chung file → merge sạch.

## 2. Kết quả test

| Bộ test | Kết quả |
|---|---|
| M5 riêng (`test_disruption_and_cross_week_adapter.py`) | `25/25` PASS |
| M7 riêng (`test_student_simulator_and_doc_parser.py`) | `5/5` PASS |
| **Sau khi gộp** — toàn bộ `tests/` | `229 passed, 2 failed` |
| `Testing_System` v2.1 (frozen) | `39/39` PASS |
| `clean_runner.py --pass` | `223/225` (2 lỗi giống trên) |

## 3. Cổng kiểm định 5 bất biến

| # | Bất biến | Kết quả | Bằng chứng |
|---|---|---|---|
| 1 | Không nhân đệm hai lần, α ∈ [1.00, 1.60] | ✅ | Adapter chỉ đặt `alpha_*`/`buffer_multiplier`, giữ nguyên `duration_min`; simulator tính `est_min` từ `Task.duration_min` thô |
| 2 | Cold-start `n=0 → α₀`; 1 ngoại lai 5.0 → clip 2.50 | ✅ | `0.25·2.5 + 0.75·1.35 = 1.6375 → 1.60`; `0.25·2.5 + 0.75·1.20 = 1.525` |
| 3 | RNG cô lập, Γ ở mẫu số TMT, hồi mệt khi nghỉ ≥ 15' | ✅ | 3 lần `seed=42` → cùng SHA-256; `denom = 1 + Γ·max(0.05, s_h/24)`; `apply_rest_break` ≥ 15' → `×0.60` |
| 4 | Tuần 4 tốt hơn Tuần 1 (Night-Owl + Coding) | ❌ **Chưa đạt thật** | Xem B1, B2 |
| 5 | Không hồi quy `Testing_System` | ✅ | `39/39` |

---

## 4. Lỗi Backend (cần M5/M7 sửa — M4 **không** sửa file của người khác)

**B1 — [Nghiêm trọng] Sai tên khóa sự cố lặp giữa M5 ↔ M7.** `app.py` (`_build_default_multiweek_benchmark_scenario`) truyền `chronic_disruption_window`, nhưng `InSilicoStudentSimulator` chỉ đọc `recurring_disruptions` / `recurring_disruption` / `chronic_disruption` → sự cố Thứ 5 19:30–21:00 **bị bỏ qua im lặng**. Hiện `converged=True` chỉ vì không có sự cố. Khi sửa khóa (seed 42): W1 `83.8` → W4 `75.8` on-time value → `converged=False`. Nguyên nhân phụ: vùng đệm cần ≥ 2 lần va chạm, lần đầu xảy ra ở W3, nên vùng đệm chỉ thêm sau W4 — không kịp trong 4 tuần. *Sửa:* M7 nhận thêm khóa `chronic_disruption_window`; M5 xem lại ngưỡng `CHRONIC_DISRUPTION_MIN_COUNT` hoặc số tuần mô phỏng.

**B2 — [Test đỏ] `test_closed_loop_4_week_adaptation_convergence_and_latency` (M7).** Test dùng `adapted["adapted_commitments"]` (là `dict` từ `model_dump()`) làm `profile` → `AttributeError: 'dict' object has no attribute 'planning_week_start'`. Đúng ra phải dùng `adapted["adapted_profile"]`. Hợp đồng `README_agents.md §2.5` chỉ ghi `-> dict` nên cần bổ sung tên khóa trả về.

**B3 — [Test đỏ] `test_api_multi_week_simulation_determinism_convergence_and_sla` (M5).** Test viết theo simulator dự phòng của M5; với simulator thật của M7, W1 và W4 đều `adherence=100.0` → `assert 100.0 > 100.0` sai. Nên dùng `>=` cho adherence và giữ `>` cho on-time value.

**B4 — [Trung bình] Sự cố "một lần" bị lưu thành lịch cố định hằng tuần.** `handle_disruption_chat_turn` thêm `FixedEvent(category="DISRUPTION", day_of_week="Thursday")`. `FixedEvent` lặp mỗi tuần, và `adapt_preferences_for_next_week` chỉ xóa `ADVISORY_BUFFER` → sự cố đột xuất bị khóa mãi sang các tuần sau, đồng thời chặn luôn vùng đệm (B1) vì slot đã bị chiếm.

**B5 — [Trung bình] Chặn nhầm lệnh xóa.** `is_disruption_intent("Hủy lịch họp CLB thứ 5") == True` → thay vì xóa lịch, hệ thống **thêm** một khung bận. `_LIFECYCLE_EXCLUSION_RE` chỉ có `huy bai|huy cong viec`, thiếu `huy lich`, và chỉ khớp ở đầu câu (`^`). Vì `app.py` chặn trước `handlers.py` nên router M4 không thể sửa được (M5 sở hữu `app.py`).

**B6 — [Thấp] α riêng từng task "dính" sau khi serialize.** `_has_custom_task_cognitive_buffer` coi `"alpha_light" in model_fields_set` là α tùy chỉnh. Mọi task đi qua `model_dump()` → `model_validate()` (M5 tự lưu `tasks` kiểu này) đều có field này → với task `COGNITIVE_LOAD`, hiệu chỉnh α cấp hồ sơ (P2 `calibration.py`) bị bỏ qua.

**B7 — [Thấp] Đọc đề nhầm thời lượng.** `_EXPLICIT_HOURS/MINUTES_RE` cộng mọi cụm "N phút/giờ" trong đoạn: "thuyết trình **10 phút**" → mốc Báo cáo ước tính `15` phút. File `.pdf` hỏng vẫn trả `suggested_total_min=60` (từ text rác) → có thể bật cảnh báo `USER_VS_DOC_UNDERESTIMATE` sai.

**B8 — [Thấp] "Tối nay bận…" vẫn hỏi lại ngày.** `extract_disruption_fields("Tối nay mình bận đột xuất họp nhóm 19h-21h")` không nhận "tối nay" là hôm nay → `NEEDS_CLARIFICATION` hỏi "ngày nào"; tiêu đề giữ nguyên cả câu ("Tối nay mình bận đột xuất họp nhóm").

---

## 5. Lỗi UI ↔ API (để Tiến kiểm tra giao diện sau)

**U1 — Solver bị đổi thành `LOCAL_INSERTION` sau khi báo bận qua chat.** `disruption_chat` trả `thinking_summary.selected_algorithm = "LOCAL_INSERTION"`; `app.js:169-171` gán thẳng vào `state.activeSolver`. `LOCAL_INSERTION` không có trong `SOLVER_REGISTRY` → lần giải sau `resolve_solver` âm thầm rơi về `GreedyEDFSolver`, nhãn solver và cache `schedulesBySolver["LOCAL_INSERTION"]` hiển thị sai. *Kiểm tra:* chat "Tối nay bận họp CLB 19h–21h", rồi bấm giải lại / đổi tab Benchmark.

**U2 — Lịch gốc để sửa lấy từ SQLite, không phải từ UI.** UI gửi `tasks`/`commitments` nhưng **không gửi `schedule`**; `disruption_chat` lấy `currentSchedule` từ workspace đã lưu. Nếu autosave chưa kịp (vừa thêm task), lịch được sửa có thể thiếu task mới hoặc lệch với danh sách hiển thị. *Kiểm tra:* thêm 1 task rồi ngay lập tức báo bận.

**U3 — 6 endpoint mới chưa có lời gọi nào trong UI** (`init-real-week`, `tasks/delete`, `fixed-events/*`, `adapt-next-week`, `simulation/multi-week`). Đây là phần việc của M1/M6, không phải lỗi; ghi lại để đối chiếu khi họ nối.

**U5 — Thẻ cảnh báo sau khi sửa lịch đột xuất bị gắn nhãn sai.** `disruption_chat` trả `edge_case = {"has_edge_case", "severity": "WARNING", "code": "POST_DISRUPTION_OVERLOAD", "message_vi"}` — **không có `type`**. `chat-assistant.js:_renderEdgeCaseCard` chỉ phân biệt `type === "DEADLOCK"`, nên quá tải sau sự cố hiện tiêu đề *"⚠️ Cảnh báo lịch trình dày đặc"* và không có nút gỡ rối (`suggestions` rỗng). *Kiểm tra:* báo bận đột xuất vào một ngày đã kín lịch.

**U6 — Phản hồi mới của router M4 cần UI hiển thị (M6).** `status="INFO_ONLY"` (truy vấn lịch, xem trước thích nghi) trả `schedule=None` → `app.js` không vẽ lại lịch (đúng ý đồ). Các khóa mới `conflict` (`USER_VS_DOC_UNDERESTIMATE` / `CIRCULAR_DEPENDENCY`), `attachment_digest`, `adaptation`, `created_task_ids` hiện UI **chưa đọc**; chip vẫn hoạt động vì nằm trong `quick_chips`. *Kiểm tra:* đính kèm đề bài + gõ thời lượng quá ngắn → phải thấy 2 chip lựa chọn.

**U4 — Chip "Hủy báo bận" khi đang hỏi bổ sung.** Chip gửi `"Hủy thao tác"`, khớp `_CANCEL_DRAFT_RE` → trả `status="CANCELLED"`, `schedule=None`. `app.js` đã xử lý `CANCELLED` (reset `chatModeHint`) → **OK**, chỉ cần xác nhận bằng mắt rằng bong bóng chat hiển thị đúng.

---

## 6. Kết luận

Hai nhánh **đúng về logic toán học** (bất biến 1, 2, 3, 5 đạt). Đã gộp vào `verification` để M4 làm tiếp `handlers.py`. **Chưa đạt cổng kiểm định** cho tới khi M5/M7 xử lý B1–B3; B4, B5 nên sửa trước khi chấm mù Chủ Nhật.

## 7. Phần việc M4 đã làm trên nhánh này

- `smartschedule/nlp/intent_classifier.py` — danh sách quyết định tất định (`~0.06 ms`/lượt): xóa luôn thắng báo bận, chuỗi "xong A rồi mới B" không bị hiểu là "đã xong A".
- `smartschedule/api/chat/lifecycle_intents.py` — `DELETE_ITEM`, `COMPLETE_TASK` (ghi A/E vào `completion_logs`), `QUERY_SCHEDULE`, `ADAPT_NEXT_WEEK` (xem trước → áp dụng, LoA-4), `BATCH_ADD_TASKS`, `LINK_DEPENDENCY` (DFS 3 màu dạng lặp, chặn vòng lặp), đối chiếu đề bài `USER_VS_DOC_UNDERESTIMATE`.
- `smartschedule/api/chat/handlers.py` — import an toàn M5/M7/M3 (`try/except ImportError` + `inspect.signature`), chuẩn hóa `selected_algorithm` khi chuyển sang M5 (chặn U1 trên luồng của router), thêm `pattern_rules` P10/P13/P14 vào `thinking_summary`.
- `tests/logical/test_chat_lifecycle_and_grounding.py` — `36` test + `1` `xfail(strict)` ghi lại B5 (tự báo đỏ khi M5 sửa xong để gỡ đánh dấu).
- **Giới hạn:** qua HTTP, câu "hủy lịch …" vẫn bị `app.py` chặn trước router (B5) — chỉ M5 sửa được.
