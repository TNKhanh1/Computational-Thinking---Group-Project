# SmartSchedule v1.0-alpha — Improved Minimalist Chat-First UI & Developer Thinking Plan (Revision 2)

**Branch:** `v1.0-alpha/ui-ux-chat`  
**Directory:** `v1.0-alpha-plan/UI_Rebuild_Plan/`  
**Purpose:** Incorporates user UX review feedback to achieve radical visual minimalism, accurate cross-day natural-language context parsing, collapsible calendar copilot ergonomics, and an Antigravity-inspired humanized **Thinking Stage** in Developer Mode.

---

## 1. Visual Minimalism & Navigation Refinements

### 1.1. Brand Header & Left Vertical Taskbar (`#leftNavSidebar`)
1. **Clickable Brand Home (`SS SmartSchedule`):**
   - Clicking the `SS SmartSchedule` brand group in the top-left header always returns directly to the main conversational workspace (`#viewChat`).
2. **Renamed Primary Navigation:**
   - Rename `"Khung Chatbot"` to **`"Trợ lý xếp lịch"`**.
3. **Complete Hide on Sidebar Close (Zero Misaligned Footer):**
   - Since the top-left hamburger toggle (`#btnToggleLeftSidebar`) remains permanently accessible in the top bar, closing the left taskbar collapses `#leftNavSidebar` completely (`display: none`) rather than shrinking to a cramped 66px strip with a misaligned Developer Mode box.
4. **Remove Redundant `"Chuyển nhanh tuần"` from Sidebar:**
   - Week switching belongs exclusively in the Calendar view header, keeping the left taskbar strictly focused on workspace switching (`Trợ lý xếp lịch`, `Lịch Trình Tuần`, `Danh Sách Việc`) and the bottom `Developer Mode` toggle.

### 1.2. Upper-Right Settings Menu (`#settingsPopover`) Cleanup
- **Remove `"Nền năng lượng sinh học"`:** Circadian energy alignment is an internal hidden criterion managed automatically by the scheduling engine, not a manual user toggle.
- **Remove `"Tiện ích nhanh"` (`"Báo sự cố đột xuất & Sửa lịch"`):** Urgent schedule disruptions and fixes are handled directly through natural conversation in the chatbot.

### 1.3. Ultra-Clean Chat Composer & Bot Responses
1. **Remove `"Chỉnh nhanh việc đã lưu"` Strip:**
   - Eliminates the row of saved-task pills above the input box so the chat composer remains as clean and spacious as Antigravity.
2. **No Forced Input Text Prefixes on Suggestion Cards:**
   - Clicking **`🔁 Thêm / Đổi lịch lặp hằng ngày`** or **`📌 Thêm / Chỉnh 1 công việc riêng biệt`** sets the mode indicator pill above the composer (`Chế độ: 🔁 Lịch lặp hằng ngày` / `📌 Công việc riêng`) and focuses the input without injecting `"Thêm công việc: "` text into the textarea.
3. **Single Clean Post-Action CTA (`"🗓️ Kiểm tra lịch trình"`):**
   - Every completed schedule/task response displays a single clear button: **`[🗓️ Kiểm tra lịch trình]`** to transition to the weekly calendar, removing cluttered secondary buttons (`"Chỉnh độ nặng / nhẹ công việc"`, `"Mở lịch trình mới"`, etc.).

### 1.4. Collapsible Right Calendar Copilot (`"Trợ lý chỉnh lịch trực tiếp"`)
- In the Weekly Calendar view (`#viewCalendar`), clicking the arrow button (`⇥` / `Thu gọn`) on the right-hand `"Trợ lý chỉnh lịch trực tiếp"` drawer **collapses the copilot panel to the right edge**, expanding the weekly calendar grid to 100% width.
- When collapsed, a sleek floating pill (`💬 Trợ lý xếp lịch`) appears on the top-right of the calendar to slide the copilot drawer back open in place (never jumping out of the calendar view).

---

## 2. Context-Aware Natural Language Parsing Fix (Cross-Day Window + Single-Task Integrity)

### 2.1. Root Cause of the 3-Task Misinterpretation
When the user prompted:
> *"Làm bài tập môn Computational Thinking, từ 19h ngày thứ 3, tới 21h ngày thứ 5, cần thực hiện trong 2 tiếng"*

Three compounding parser issues occurred in Revision 1:
1. **Accent-Stripped `"tới"` Collision:** `strip_accents("tới")` produced `"toi"`, which collided with the regex `\btoi\b` for `"buổi tối"` (`EVENING`), falsely flagging the prompt as a hidden-parameter modification (`MODIFY_HIDDEN`) on existing preset tasks.
2. **Stop-Word Leakage in Keyword Matcher:** Words like `"thực"`, `"hiện"`, `"trong"`, `"môn"` were not in `_STOP_WORDS`, causing `resolve_target_task_from_prompt` to partially match 3 pre-loaded tasks from Minh's preset.
3. **Cross-Day Window `[start_after, deadline]` & Auto-Splitting:** The parser did not separate `"từ 19h ngày thứ 3"` (`start_after` release time) from `"tới 21h ngày thứ 5"` (`deadline`), and defaulted `is_splittable = True` (`max_chunk_min = 90`), which split a single 2-hour (`120m`, buffered to `150m`) task into 3 separate calendar chunks (`#1/3`, `#2/3`, `#3/3`).

### 2.2. Revision 2 Context Parser Rules (`web/chat_service.py` & `src/task_tracer.py`)
1. **Cross-Day Window Extraction (`_extract_cross_day_window`):**
   - Recognizes `từ <time1>? <day1> (?:tới|đến|trước) <time2>? <day2>` (and `<day> <time>` variants).
   - Maps `<day1> <time1>` to `start_after` (`Tuesday 19:00`) and `<day2> <time2>` to `deadline_day` + `deadline_time` (`Thursday 21:00`).
   - Extracts `"cần thực hiện trong 2 tiếng"` -> `duration_min = 120` and strips the entire temporal clause from the task title, yielding the clean title: **`"Làm bài tập môn Computational Thinking"`**.
2. **Single-Task Contiguous Integrity:**
   - A newly prompted task defaults to **1 contiguous session (`is_splittable = False`)** whenever `duration_min <= 180` minutes unless the user explicitly asks to split it (`"chia nhỏ"`, `"nhiều buổi"`).
3. **Strict Intent Guard:**
   - Prompts specifying a new task with duration and time bounds are always routed to `ADD_TASK`.
   - `"tối"` only matches circadian `EVENING` when preceded/followed by time-of-day cues (`buổi tối`, `tối nay`, `tối mai`, `tối thứ`, `<hour>h tối`, `ban đêm`, `khuya`).

---

## 3. Developer Mode: Antigravity-Style Humanized "Thinking Stage"

When **Developer Mode** is toggled ON (`#chkDeveloperMode`), the assistant displays a concise, humanized **Thinking Summary (`💭 Tóm tắt suy nghĩ & Chọn thuật toán`)** at the top of its response bubble:

1. **Context & Hidden Criteria Parsing Summary:**
   - Summarizes in plain language how many tasks were detected, the extracted title, time window (`Bắt đầu sớm nhất` → `Hạn chót`), raw vs. buffered duration, and inferred hidden parameters (`Cường độ`, `Tách/Gộp buổi`, `Nhịp sinh học`, `Mã truy vết SHA-256`).
2. **Dominant Algorithm Subset Selection Rationale:**
   - Benchmark evaluations in `Testing_System v2.1` prove that classical energy-blind heuristics (`EDF`, `WSPT`, `LST`) have a best-case ergonomic/productivity outcome worse than the worst-case outcome of circadian-aware solvers.
   - Therefore, the bot explicitly notes that it **prunes the dominated baseline group (`EDF`, `WSPT`, `LST`)** and selects from the **Dominant Ergonomic Portfolio (`SCORED_GREEDY`, `HYBRID_ALNS`)**:
     - Uses **`SCORED_GREEDY`** for fast, high-energy-match scheduling under normal/moderate weekly load (`< 30ms`).
     - Automatically escalates to **`HYBRID_ALNS`** (Adaptive Large Neighborhood Search with ruin-and-recreate) when deadline density is tight or greedy placement leaves unplaced work.
