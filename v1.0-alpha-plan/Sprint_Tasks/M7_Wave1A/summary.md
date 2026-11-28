# M7 Wave 1A Summary — Virtual Student Twin & Smart Assignment Reader

> **Why this file is here (instead of editing `docs/` or `agents/`):**
> Under our team's sprint rules (`agents/README.md` and `v1.0-alpha-plan/README_agents.md`), shared changelog files (`agents/commit_changes.md` and `docs/commit_changes.md`) are locked during feature branches so all 7 members never collide, and `requirements.md` files only change when Python dependencies change (none were added here). To respect those rules while keeping everything crystal clear, this standalone summary documents the Wave 1A work on branch `v1.0-alpha/m7-simulator-and-doc-parser`.

---

## 1. Core Ideas

In Wave 1A, we built two missing pieces that make SmartSchedule genuinely smart rather than a basic calendar app:

1. **A Virtual Student Twin (`smartschedule/core/student_simulator.py`):**
   - **The real-world problem:** Our scheduler is supposed to learn a student's real habits from week to week—such as which subjects they underestimate or when they actually focus best. However, in a short university semester, we cannot ethically test stressful schedules on real students for 6 to 8 weeks.
   - **The core idea:** Instead of waiting months, we built a lightweight, repeatable "digital student" that acts out a planned week block-by-block using 5 well-known psychology rules (body clock rhythm, optimism bias on hard tasks, procrastination near vs. far deadlines, choice under distraction, and mental tiredness with rest recovery). Running a 4-week learning loop with this virtual twin takes under half a second on a normal laptop.

2. **A Smart Assignment Reader (`smartschedule/nlp/doc_attachment_parser.py`):**
   - **The real-world problem:** Students often attach a lab sheet or syllabus (`.pdf`, `.md`, or `.txt`) and say *"finish this in 30 minutes"*, when the actual document asks for 3 heavy coding and testing parts that take 3+ hours.
   - **The core idea:** We built a fast document reader that breaks an attached assignment into clear steps, spots grade weights (like `40%`), judges how mentally demanding each step is, detects when one step depends on the previous one, and calculates a realistic total time so the chat assistant can warn the student before they under-plan.

---

## 2. Pipeline Used

### A. Closed-Loop Multi-Week Learning Pipeline
1. **Plan the week:** SmartSchedule generates a weekly study timetable for a student profile and task list.
2. **Simulate student behavior:** The Virtual Student Twin walks through every scheduled block in chronological order:
   - Checks whether the time matches the student's *true* biological peak hour (even if the student claimed a different preference in settings).
   - Tracks mental tiredness across the day, restoring 40% of fatigue whenever there is at least a 15-minute real break, and checking for recurring disruptions (like a Thursday evening clash).
   - Decides whether the student actually sticks to the block or gets distracted/procrastinates.
   - If the student does the work, simulates how long it *actually* took based on the subject's optimism bias (for example, coding tends to run longer than reading).
3. **Output clean weekly logs:** Produces a standardized timeline log (`timeline_logs`) showing planned vs. actual minutes, whether each block was followed, overrun minutes, fatigue level, and any disruption window.
4. **Adapt next week:** Feeds those logs into the Cross-Week Adapter (`M5`), which adjusts time buffers and preferred study hours for the next week, repeating from Week 1 to Week 4.

### B. Attachment-to-Schedule Pipeline
1. **Safety check & text extraction:** Verifies the file is within the 20 MB limit, decodes plain text/Markdown directly, or extracts text from PDFs (trying lightweight PDF helpers only if installed, and falling back to built-in Python text extraction with zero extra memory cost).
2. **Step breakdown:** Splits the document into numbered parts, questions, or phases while ignoring administrative headers like *"Overview"* or *"References"*.
3. **Effort & order tagging:** Estimates minutes per step (rounded to 15-minute calendar slots), tags mental effort (`1` = light, `2` = medium, `3` = deep), reads `%` grade weights to suggest priority, and marks `depends_on_prev` when a step relies on an earlier one.
4. **Reality check:** Exposes a helper (`detect_user_underestimate`) so the chat handler (`M4`) can warn the student if their typed time estimate is less than half of what the assignment actually requires.

---

## 3. Thinking Process & Key Design Decisions

- **Why 5 math/psychology rules instead of a giant AI language model per time slot?**
  Calling a massive AI model on hundreds of 15-minute slots across 4 weeks would be slow, expensive, unpredictable, and violate our strict memory limit (`< 350 KB` heap growth). Five grounded behavioral equations give us realistic, peer-reviewed human patterns in milliseconds—and using an isolated random seed guarantees the exact same experiment can be re-run bit-for-bit by any grader or teammate.
- **Avoiding the "Double-Buffering Trap":**
  The planner already pads a 60-minute coding task up to 90 minutes (`planned_duration_min`). If the simulator multiplied `90` by the coding optimism bias again, it would unfairly punish the buffered schedule! Instead, the simulator always traces back to the student's *raw* unbuffered estimate (`60` minutes) to simulate real work time, then measures overrun against the *planned* `90` minutes. That way, better planning genuinely reduces overruns across Weeks 1 to 4.
- **Distinguishing chained projects from independent exam questions:**
  In a programming lab (*Part 1: Build solver -> Part 2: Test Part 1 -> Part 3: Final report*), later steps clearly depend on earlier ones. In an exam sheet (*Question 1 -> Question 2*), they usually do not. We combined explicit dependency phrases (*"based on"*, *"after"*, *"sau khi"*) with build-then-test structure detection so independent questions stay parallel while real project chains form proper order links.
- **Zero-bloat PDF handling:**
  Heavy PDF/AI packages can use hundreds of megabytes of RAM just by being imported. By loading optional PDF libraries only inside the PDF function—and keeping a pure-Python fallback ready—our base system stays fast, self-contained, and completely within memory guardrails.
