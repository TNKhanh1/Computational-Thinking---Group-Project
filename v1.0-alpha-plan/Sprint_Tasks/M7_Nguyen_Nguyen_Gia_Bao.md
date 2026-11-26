# M7 — Nguyễn Nguyễn Gia Bảo (`25125006`) · Builder 3
**Vai trò theo `work_division.pdf`:** Builder 3 · Lead **§8 Edge Cases & Trade-offs**, Support **§7 System Architecture**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m7-mobile-guardrails-and-e2e`  
**Đợt thực hiện (Wave):** **Wave 2B** (CSS & Architecture Tests trước **22:30 Thứ Bảy, 28/11/2026**) & **Wave 3** (Cổng Kiểm định Cuối cùng trước **09:30 Sáng Chủ Nhật, 29/11/2026**)

---

## 1. Dành cho Thành Viên (Giải thích dễ hiểu)
Khi cả nhóm ghép đủ tính năng mới (Onboarding, Xóa/Hoàn thành qua Chat, Sửa lịch đột xuất, Nhập `.ics`, Hoàn tác, và Mô hình NLP miễn phí), có **3 rủi ro thực tế quyết định ứng dụng dùng có mượt hay bị lỗi vặt** (đúng trọng tâm Mục §8 *Edge Cases & Trade-offs* và §7 *Architecture* bạn phụ trách):
1. **Trải nghiệm trên màn hình nhỏ / điện thoại & chia nửa màn hình laptop:** Thanh điều hướng trái và khung trợ lý phải nếu không trượt mượt dạng ngăn kéo (overlay drawer) trên màn hình hẹp sẽ làm bảng lịch bị ép nhỏ xíu, tràn chữ hoặc lệch nút.
2. **Bảo vệ tốc độ & RAM (`INV-1..6`):** Đảm bảo các thư viện đọc ngữ cảnh / đọc tài liệu mới ở Tầng 4 không bao giờ bị nạp nhầm vào Tầng lõi làm chậm thuật toán hoặc gây rò rỉ bộ nhớ (`< 350 KB`).
3. **Kiểm thử Hành trình Người dùng từ đầu tới cuối (End-to-End User Journeys):** Chốt chặn mọi ca biên (nhập rỗng, trùng giờ ngủ, quá tải cực đoan, xóa việc không tồn tại, hoàn tác liên tiếp) để bản `v1.0-alpha` chạy mượt 100% khi demo và sử dụng thật.

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (Conflict-Free Guarantee)
- **CREATE:**
  - `tests/ui/test_v1_alpha_user_journeys.py`
- **MODIFY (Wave 2B & Wave 3 ONLY):**
  - `smartschedule/ui/css/shell.css` *(SOLE OWNER in this sprint!)*
  - `smartschedule/ui/css/calendar.css` *(SOLE OWNER in this sprint!)*
  - `smartschedule/ui/css/chat.css` *(SOLE OWNER in this sprint!)*
  - `tests/architecture/test_system_architecture.py` *(SOLE OWNER!)*
  - `tests/architecture/test_memory_leaks.py` *(SOLE OWNER!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*`, `smartschedule/ui/app.js`, or `smartschedule/ui/index.html`.

### Engineering Requirements
1. **Responsive Layout, Auto-Expanding Composer & Smooth Transitions (`shell.css`, `calendar.css`, `chat.css`):**
   - At viewports `< 900px` / `< 768px`, style `#leftNavSidebar` (when open) and `#calendarCopilotDrawer` (when open) as clean slide-over drawers with subtle backdrop/shadow so `#calendarMainStage` never crushes day columns below readable width (`zero` unintended horizontal page overflow from `375px` to `1920px`).
   - Polish `.chat-input` (`max-height: 132px; overflow-y: auto; resize: none;`), `.chat-quick-chip` touch targets (`min-height: 34px`), Undo toast button styling, and `.cal-block-enter` / `.cal-block-moved` keyframe transitions (`prefers-reduced-motion` safe!).
   - Preserve `.calendar-with-copilot-layout:not(.copilot-collapsed) .copilot-expand-fab { display: none !important; }` and `.left-nav-sidebar.collapsed { display: none !important; }` contracts!
2. **Expanded `INV-1..6` & Lazy-Import Memory Guardrails (`tests/architecture/`):**
   - Extend `test_system_architecture.py` to scan ALL `.py` files in `smartschedule/core/` verifying zero imports of `smartschedule.api`, `smartschedule.nlp`, `spacy`, `transformers`, `docling`, `fastapi`, or `google`.
   - Extend `test_memory_leaks.py` to assert that importing `smartschedule.api.app` does NOT eagerly load heavy optional NLP models (`"torch" not in sys.modules`, `"transformers" not in sys.modules`) and 50 consecutive solves stay strictly `< 350 KB` heap growth and `< 10 MB` peak.
3. **End-to-End `v1.0-alpha` User-Journey Test Suite (`tests/ui/test_v1_alpha_user_journeys.py`):**
   - Write comprehensive FastAPI `TestClient` E2E tests covering:
     1) Fresh Real-Week Onboarding $\to$ `.ics` timetable import $\to$ Add multi-day atomic task $\to$ Verify `0` hard violations.
     2) Conversational Emergency Disruption $\to$ Verify `LocalRepairEngine` stability $\ge 90\%$.
     3) Conversational Delete / Complete / Profile Sleep validation ($< 6\text{h}$ sleep gracefully rejected without 500 error) + Deadlock/Dense-Schedule edge cases (`< 10,000 ms` turn SLA).

### Verification Commands (Final `v1.0-alpha` Release Gate — Sunday Morning 29/11)
```powershell
node --check smartschedule/ui/app.js
Get-ChildItem smartschedule/ui/js/*.js | ForEach-Object { node --check $_.FullName }
python -B tests/clean_runner.py --pass
python -B tests/clean_runner.py --edge
python -B -m pytest -c environments/pyproject.toml v1.0-alpha-plan/Testing_System/tests -q
python -B tests/fixtures/nl_cases/verify_hybrid_200.py
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [ ] Tinh chỉnh responsive mobile/tablet & animation mượt trong `shell.css`, `calendar.css`, `chat.css` (không tràn khung từ `375px` đến `1920px`).
- [ ] Mở rộng `test_system_architecture.py` & `test_memory_leaks.py` khóa chặt `INV-1..6` và kiểm soát lazy-load cho các module NLP mới.
- [ ] Viết bộ kiểm thử hành trình người dùng đầu-cuối `tests/ui/test_v1_alpha_user_journeys.py`.
- [ ] **(Sáng Chủ Nhật 29/11 — 08:30–09:30)** Chạy toàn bộ cổng kiểm định cuối cùng (App Tests + `Testing_System` + 200 NL Cases + `.bat` scripts) xác nhận xanh 100% trước khi Leader đóng gói `v1.0-alpha`.
