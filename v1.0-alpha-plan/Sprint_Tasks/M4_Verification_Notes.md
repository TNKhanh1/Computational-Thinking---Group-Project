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
| **Sau khi sửa B1–B3** (kèm router M4) — toàn bộ `tests/` | `270 passed, 1 xfailed` (xfail = B5) |
| **Sau khi sửa B1–B3** — `clean_runner.py --pass` | `264/265`, `0 Failed` |
| **Sau khi sửa B4, B5, B8** — toàn bộ `tests/` | `274 passed` (không còn xfail) |
| **Sau khi sửa B4, B5, B8** — `clean_runner.py --pass` | `268/268` |

## 3. Cổng kiểm định 5 bất biến

| # | Bất biến | Kết quả | Bằng chứng |
|---|---|---|---|
| 1 | Không nhân đệm hai lần, α ∈ [1.00, 1.60] | ✅ | Adapter chỉ đặt `alpha_*`/`buffer_multiplier`, giữ nguyên `duration_min`; simulator tính `est_min` từ `Task.duration_min` thô |
| 2 | Cold-start `n=0 → α₀`; 1 ngoại lai 5.0 → clip 2.50 | ✅ | `0.25·2.5 + 0.75·1.35 = 1.6375 → 1.60`; `0.25·2.5 + 0.75·1.20 = 1.525` |
| 3 | RNG cô lập, Γ ở mẫu số TMT, hồi mệt khi nghỉ ≥ 15' | ✅ | 3 lần `seed=42` → cùng SHA-256; `denom = 1 + Γ·max(0.05, s_h/24)`; `apply_rest_break` ≥ 15' → `×0.60` |
| 4 | Tuần 4 tốt hơn Tuần 1 (Night-Owl + Coding) | ✅ **Đạt trên nhóm** (sau khi sửa B1–B3) | Simulator thật, có sự cố Thứ 5. Quét seed `40..49`, `weeks=4`: `n_students=1` hội tụ `1/5` (seed 42–46); `n_students=5` hội tụ `8/10`; `n_students=10` hội tụ `9/10` (seed 42: adherence `60.0 → 68.33`, on-time `46.55 → 59.58`). Từ W5 trở đi không còn block nào rơi vào Thứ 5 19:30–21:00 |
| 5 | Không hồi quy `Testing_System` | ✅ | `39/39` |

---

## 4. Lỗi Backend (cần M5/M7 sửa; riêng B1–B5 và B8 M4 đã sửa ngày 28/11 theo yêu cầu của Tiến)

**B1 — [Nghiêm trọng] Sai tên khóa sự cố lặp giữa M5 ↔ M7.** `app.py` (`_build_default_multiweek_benchmark_scenario`) truyền `chronic_disruption_window`, nhưng `InSilicoStudentSimulator` chỉ đọc `recurring_disruptions` / `recurring_disruption` / `chronic_disruption` → sự cố Thứ 5 19:30–21:00 **bị bỏ qua im lặng**. Hiện `converged=True` chỉ vì không có sự cố. Khi sửa khóa (seed 42): W1 `83.8` → W4 `75.8` on-time value → `converged=False`. Nguyên nhân phụ: vùng đệm cần ≥ 2 lần va chạm, lần đầu xảy ra ở W3, nên vùng đệm chỉ thêm sau W4 — không kịp trong 4 tuần. *Sửa:* M7 nhận thêm khóa `chronic_disruption_window`; M5 xem lại ngưỡng `CHRONIC_DISRUPTION_MIN_COUNT` hoặc số tuần mô phỏng.

> ✅ **Đã sửa (M4, 28/11, theo yêu cầu Tiến):** `student_simulator.py` đọc thêm khóa `chronic_disruption_window`. **Không** đổi ngưỡng `≥ 2` của M5: chẩn đoán 7 tuần (seed 42) cho thấy vùng bận được học sau W4 và W5–W7 không còn block nào đụng Thứ 5 19:30–21:00, nên thuật toán đúng. W4 < W1 trên 1 sinh viên là do **cách đo**, không phải do thuật toán: W1 xếp buổi sáng nên chưa bao giờ đụng sự cố; W3 dời sang tối (đúng giờ vàng 20:30) thì bắt đầu đụng; W4 nằm giữa giai đoạn đang học. Thêm vào đó mỗi tuần chỉ có 6–9 block, nên 1 block lệch làm adherence đổi 11–17 điểm.

**B2 — [Test đỏ] `test_closed_loop_4_week_adaptation_convergence_and_latency` (M7).** Test dùng `adapted["adapted_commitments"]` (là `dict` từ `model_dump()`) làm `profile` → `AttributeError: 'dict' object has no attribute 'planning_week_start'`. Đúng ra phải dùng `adapted["adapted_profile"]`. Hợp đồng `README_agents.md §2.5` chỉ ghi `-> dict` nên cần bổ sung tên khóa trả về.

> ✅ **Đã sửa:** đổi sang `adapted["adapted_profile"]`; test pass với adapter thật của M5.

**Vì sao test riêng pass mà gộp lại fail (B1–B3):** mỗi nhánh khi chạy một mình thì module của bên kia chưa có, nên `try/except ImportError` dùng **bản giả do chính mình viết** (M7 dùng `_local_p13_adapt_fallback` trong test; M5 dùng `_DeterministicFallbackStudentSimulator` trong `app.py`). Bản giả khớp với giả định của người viết, nên không thể phát hiện chỗ lệch tên khóa. Khi gộp, `import` thành công và module thật được dùng, nên lệch hợp đồng mới lộ ra.

**B3 — [Test đỏ] `test_api_multi_week_simulation_determinism_convergence_and_sla` (M5).** Test viết theo simulator dự phòng của M5; với simulator thật của M7, W1 và W4 đều `adherence=100.0` → `assert 100.0 > 100.0` sai. Nên dùng `>=` cho adherence và giữ `>` cho on-time value.

> ✅ **Đã sửa (cách khác với đề xuất ở trên):** nới `>` thành `>=` vẫn chỉ là may rủi trên 1 sinh viên. Test được tách làm hai: lệnh gọi `n_students=1` chỉ kiểm tra tính tất định (hash SHA-256) và SLA `< 1000 ms`; phần hội tụ dùng nhóm `n_students=10, seed=42` và giữ nguyên các phép so sánh `>` chặt, kèm kiểm tra `simulator_backend == "InSilicoStudentSimulator"` để không thể pass trên bản giả nữa.

**B4 — [Trung bình] Sự cố "một lần" bị lưu thành lịch cố định hằng tuần.** `handle_disruption_chat_turn` thêm `FixedEvent(category="DISRUPTION", day_of_week="Thursday")`. `FixedEvent` lặp mỗi tuần, và `adapt_preferences_for_next_week` chỉ xóa `ADVISORY_BUFFER` → sự cố đột xuất bị khóa mãi sang các tuần sau, đồng thời chặn luôn vùng đệm (B1) vì slot đã bị chiếm.

> ✅ **Đã sửa (M4, 28/11):** `cross_week_adapter.py` thêm hằng `ONE_WEEK_FIXED_EVENT_CATEGORIES = {ADVISORY_BUFFER, DISRUPTION}` và bỏ cả hai loại khi sang tuần mới. Trong tuần hiện tại sự cố vẫn khóa slot như cũ. Tín hiệu lặp lại vẫn còn trong `disruption_logs`, nên vùng bận mãn tính vẫn được học, và vùng đệm không còn bị chặn bởi sự cố cũ nằm trên cùng slot. Test: `test_b4_one_off_disruption_is_not_carried_into_next_week`.

**B5 — [Trung bình] Chặn nhầm lệnh xóa.** `is_disruption_intent("Hủy lịch họp CLB thứ 5") == True` → thay vì xóa lịch, hệ thống **thêm** một khung bận. `_LIFECYCLE_EXCLUSION_RE` chỉ có `huy bai|huy cong viec`, thiếu `huy lich`, và chỉ khớp ở đầu câu (`^`). Vì `app.py` chặn trước `handlers.py` nên router M4 không thể sửa được (M5 sở hữu `app.py`).

> ✅ **Đã sửa (M4, 28/11):** `_LIFECYCLE_EXCLUSION_RE` nhận cả lời dẫn ("mình muốn / giúp mình …") và `huy bo` / `huy|bo + đối tượng` (`lich, buoi, cuoc hop, bai, viec, task, su kien, cong viec, deadline, mon`). Thêm `_DELETE_ANYWHERE_RE` để bắt cụm xóa ở giữa câu ("Thứ 5 hủy lịch họp CLB nhé"), trừ khi có tín hiệu khẩn cấp mạnh. `huy` đứng một mình **không** đủ vì đó cũng là tên người ("Huy rủ mình họp khẩn…" vẫn là báo bận). Test `xfail` cũ đã gỡ đánh dấu và pass qua HTTP: `/api/chat/turn` trả `DELETE_ITEM`.

**B6 — [Thấp] α riêng từng task "dính" sau khi serialize.** `_has_custom_task_cognitive_buffer` coi `"alpha_light" in model_fields_set` là α tùy chỉnh. Mọi task đi qua `model_dump()` → `model_validate()` (M5 tự lưu `tasks` kiểu này) đều có field này → với task `COGNITIVE_LOAD`, hiệu chỉnh α cấp hồ sơ (P2 `calibration.py`) bị bỏ qua.

**B7 — [Thấp] Đọc đề nhầm thời lượng.** `_EXPLICIT_HOURS/MINUTES_RE` cộng mọi cụm "N phút/giờ" trong đoạn: "thuyết trình **10 phút**" → mốc Báo cáo ước tính `15` phút. File `.pdf` hỏng vẫn trả `suggested_total_min=60` (từ text rác) → có thể bật cảnh báo `USER_VS_DOC_UNDERESTIMATE` sai.

**B8 — [Thấp] "Tối nay bận…" vẫn hỏi lại ngày.** `extract_disruption_fields("Tối nay mình bận đột xuất họp nhóm 19h-21h")` không nhận "tối nay" là hôm nay → `NEEDS_CLARIFICATION` hỏi "ngày nào"; tiêu đề giữ nguyên cả câu ("Tối nay mình bận đột xuất họp nhóm").

> ✅ **Đã sửa (M4, 28/11):** thêm `_SAME_DAY_PERIOD_RE` (`sáng|trưa|chiều|tối|đêm nay`, `tonight`, `this morning/afternoon/evening`) → ngày hôm nay theo `profile.now`, đứng sau ngày ghi rõ ("tối mai" vẫn là ngày mai). Tiêu đề bỏ cụm "tối nay" và đảo "bận đột xuất họp nhóm" → "Họp nhóm đột xuất". Không sửa `clause_condenser.py` (M2). Test: `test_b8_same_day_period_resolves_to_today_and_title_is_clean`.

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

**Cập nhật 28/11:** B1–B3 đã sửa (xem từng mục), nên **cả 5 bất biến đều đạt** và toàn bộ test xanh. Còn mở: B4–B8 và U1–U6. Lưu ý cho thuyết trình: chỉ nên trình bày "Tuần 4 tốt hơn Tuần 1" như một kết quả **trên nhóm sinh viên** (`n_students ≥ 10`); với 1 sinh viên, kết quả phụ thuộc vào seed.

**Cập nhật 28/11 (lần 2):** đã sửa thêm B4, B5, B8 (file M5: `disruption_chat.py`, `cross_week_adapter.py`). Backend còn mở: B6 (M5), B7 (M7). UI: U1–U6.

## 7. Phần việc M4 đã làm trên nhánh này

- `smartschedule/nlp/intent_classifier.py` — danh sách quyết định tất định (`~0.06 ms`/lượt): xóa luôn thắng báo bận, chuỗi "xong A rồi mới B" không bị hiểu là "đã xong A".
- `smartschedule/api/chat/lifecycle_intents.py` — `DELETE_ITEM`, `COMPLETE_TASK` (ghi A/E vào `completion_logs`), `QUERY_SCHEDULE`, `ADAPT_NEXT_WEEK` (xem trước → áp dụng, LoA-4), `BATCH_ADD_TASKS`, `LINK_DEPENDENCY` (DFS 3 màu dạng lặp, chặn vòng lặp), đối chiếu đề bài `USER_VS_DOC_UNDERESTIMATE`.
- `smartschedule/api/chat/handlers.py` — import an toàn M5/M7/M3 (`try/except ImportError` + `inspect.signature`), chuẩn hóa `selected_algorithm` khi chuyển sang M5 (chặn U1 trên luồng của router), thêm `pattern_rules` P10/P13/P14 vào `thinking_summary`.
- `tests/logical/test_chat_lifecycle_and_grounding.py` — `40` test, tính cả tham số (test B5 qua HTTP đã hết `xfail` sau khi sửa B5) — trước đó `xfail(strict)` (tự báo đỏ khi M5 sửa xong để gỡ đánh dấu).
- **Giới hạn:** qua HTTP, câu "hủy lịch …" vẫn bị `app.py` chặn trước router (B5) — chỉ M5 sửa được.
