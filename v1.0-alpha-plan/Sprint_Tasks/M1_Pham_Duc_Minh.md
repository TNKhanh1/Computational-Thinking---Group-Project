# M1 — Phạm Đức Minh (`25125028`) · Leader
**Vai trò theo `work_division.pdf`:** Leader · Lead **§9 Evaluation Plan**, Support **§11 Conclusion**  
**Nhánh Git riêng (Branch):** `v1.0-alpha/m1-onboarding-and-release`  
**Đợt thực hiện (Wave):** **Wave 2B** (Code xong trước **22:00 Thứ Bảy, 28/11/2026**) & **Wave 3** (Gộp nhánh & chốt bản `v1.0-alpha` trước **10:00 Sáng Chủ Nhật, 29/11/2026**)

---

## 1. Dành cho Thành Viên (Giải thích dễ hiểu)
Hiện tại khi một người dùng mới mở ứng dụng lần đầu tiên, hệ thống đang tự động nạp sẵn lịch học và 5 bài tập mẫu của bạn "Minh" (từ tuần `02/11/2026`), đồng thời nút chỉnh Giờ ngủ / Nhịp sinh học lại đang bị giấu trong chế độ `Developer Mode`. Điều này khiến người dùng thật bối rối vì không biết làm sao bắt đầu với lịch trống của chính mình ở tuần hiện tại.

**Nhiệm vụ của bạn trong `v1.0-alpha`:**
1. **Màn hình Chào mừng 30 giây cho người mới (`onboarding.js`):** Khi mở web lần đầu (chưa có dữ liệu lưu), hiển thị hộp chào ngắn gọn cho chọn 1 trong 2 hướng:
   - **"🚀 Bắt đầu với lịch trống tuần này"**: Đặt lịch về đúng ngày Thứ Hai của tuần thực tế hiện tại, cho chọn nhanh Giờ ngủ (mặc định `23:30 – 06:30`) và Khung giờ tỉnh táo nhất (`Buổi sáng` / `Buổi chiều` / `Buổi tối` / `Cân bằng`).
   - **"👀 Xem thử lịch mẫu sinh viên (Sample Input $\to$ Output)"**: Nạp bộ lịch mẫu chuẩn `MINH_FIT_HCMUS` (`9` công việc gồm cả đồ thị phụ thuộc `PRJ-1, PRJ-2 -> PRJ-3` — dùng trực tiếp để demo Sample Input $\to$ Sample Output theo feedback giảng viên tại [`../Testing_Plan/Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md)).
2. **Nút chỉnh nhanh "Hồ sơ Giờ ngủ & Năng lượng" cho người dùng thường:** Đặt gọn trong nút Cài đặt góc trên bên phải (`#settingsPopover`) để sinh viên không cần bật `Developer Mode` vẫn đổi được giờ ngủ, nhịp sinh học và thói quen trừ hao thời gian.
3. **Ghép nối giao diện tổng (`index.html` & `app.js` — chỉ một mình bạn sửa 2 file này ở Wave 2B để 0% xung đột Git) & Điều phối Slide Cuối Kỳ:** Nối thêm phím tắt `Enter` để gửi tin nhắn (`Shift + Enter` xuống dòng) ở khung chat, gắn module Hoàn tác (`undo-history.js` của Nhật `M6`), điều phối gộp PR của cả nhóm và ráp bộ slide cuối kỳ theo đúng khung [`Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md).

---

## 2. Instructions for AI Coding Agent (Technical Spec & Boundaries)

### Exclusive File Ownership (Conflict-Free Guarantee)
- **CREATE:**
  - `smartschedule/ui/js/onboarding.js`
  - `smartschedule/ui/css/onboarding.css` (import via `@import url("./onboarding.css");` at the bottom of `smartschedule/ui/css/app.css`)
  - `tests/ui/test_onboarding_and_user_profile.py`
- **MODIFY (Wave 2B ONLY — after rebasing onto merged Wave 1 + Wave 2A `main`):**
  - `smartschedule/ui/index.html` *(SOLE OWNER in this sprint — preserve all contracted DOM IDs!)*
  - `smartschedule/ui/app.js` *(SOLE OWNER in this sprint!)*
- **DO NOT TOUCH:** `smartschedule/core/solvers/*`, `smartschedule/nlp/*`, `smartschedule/api/chat/handlers.py`, or `agents/commit_changes.md` (until final Sunday morning release consolidation).

### Engineering Requirements
1. **First-Visit Detection in `bootstrap()` (`smartschedule/ui/app.js`):**
   - When `api.loadState(state.workspaceId)` returns `exists === false`, instead of silently calling `loadSuite("preset", "minh")` right away, render the non-intrusive Welcome Modal/Overlay from `onboarding.js` (while keeping default fallback state valid so existing headless API/UI contract tests never fail!).
   - Calling **"Bắt đầu với lịch trống tuần này"** invokes Builder 1's (`M5`) `POST /api/workspace/init-real-week` (or client-side Monday ISO computation if offline) with selected `daily_start_time`, `daily_end_time`, `focus_preference`, and `estimate_habit`, saves state via `persistWorkspace()`, and lands cleanly on `#viewChat`.
2. **User-Mode Personal Preferences Section in `#settingsPopover` (`smartschedule/ui/index.html`):**
   - Add a concise `"Hồ sơ cá nhân"` section inside `#settingsPopover` with:
     - Sleep window inputs (`#inpUserSleepStart`, `#inpUserSleepEnd` — enforcing $\ge 6\text{h}$ sleep).
     - Peak energy selector (`#selUserFocusPref`: `MORNING`, `AFTERNOON`, `EVENING`, `BALANCED`).
     - Estimation habit selector (`#selUserEstimateHabit`: `RARELY`, `SOMETIMES`, `OFTEN`).
   - Keep `#chkSettingEnergy` and `#btnOpenDisruption` with `class="sr-only" hidden` so all legacy UI contract tests remain 100% green.
3. **Chat Keyboard Ergonomics & Wave 2A Hookup (`smartschedule/ui/app.js`):**
   - Wire `keydown` on `[data-chat-input]`: `Enter` (without `Shift` and `!event.isComposing` for Vietnamese IME!) submits the chat form; `Shift+Enter` inserts a newline and auto-adjusts textarea height (`1..5` rows).
   - Wire callbacks from `M6` (`undo-history.js` and `.ics` import trigger in `#settingsPopover`).

### Verification Commands (Must Pass 100% Before PR)
```powershell
node --check smartschedule/ui/app.js
node --check smartschedule/ui/js/onboarding.js
python -B tests/clean_runner.py --ui
python -B tests/clean_runner.py --pass
```

---

## 3. Checklist Cá Nhân (Tick `[x]` trên nhánh của bạn)
- [ ] Tạo `onboarding.js` + `onboarding.css` cho phép chọn **Lịch trống tuần hiện tại** hoặc **Lịch mẫu** khi mở lần đầu.
- [ ] Bổ sung mục chỉnh nhanh **Giờ ngủ & Khung giờ tỉnh táo** ngay trong menu Cài đặt cho người dùng thường.
- [ ] Nối phím `Enter` gửi chat (hỗ trợ gõ tiếng Việt Unikey/Telex `!e.isComposing`), `Shift+Enter` xuống dòng, và ghép nối nút Hoàn tác / Nhập `.ics` từ `M6`.
- [ ] Viết test `tests/ui/test_onboarding_and_user_profile.py` và chạy xanh `clean_runner.py --pass`.
- [ ] **(Sáng Chủ Nhật 29/11)** Duyệt & merge tuần tự các PR Wave 1 $\to$ Wave 2A $\to$ Wave 2B, tổng hợp `commit_changes.md`, gắn tag `v1.0-alpha`, và điều phối ráp slide thuyết trình từ [`Formal_Spec_And_Patterns.md`](../Testing_Plan/Formal_Spec_And_Patterns.md) (§9 Evaluation + Sample Input $\to$ Output).
