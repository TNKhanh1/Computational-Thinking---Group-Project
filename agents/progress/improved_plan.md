# SmartSchedule — Improved Plan (V1/V2 Roadmap & Feature Gaps)

**Project:** SmartSchedule — Personal Productivity Assistant  
**Document Ref:** Based on `Improve_Plan/improve_plan.md`  
**Purpose:** Specification of User-Facing Upgrades, Behavioral Heuristics, and Development Gaps  
**Target Audience:** AI Coding Assistants & Feature Builders  

---

## 1. Executive Summary & Design Vision

While the **Baseline Plan (V0)** establishes an algorithmic engine on a 672-slot grid, it treats time mechanically and exposes raw engine internals (slots, constraint IDs, solver names).

The **Improve Plan (V1/V2)** bridges the gap between the mathematical solver and the everyday life of a university student:
> *"The student sees a calm weekly planner, and the lecturer sees the algorithm in Lab mode. Both use the exact same engine."*

---

## 2. The 7 Student Moments ($M_1$–$M_7$)

The improved system is engineered around seven critical touchpoints in a student's weekly rhythm:

| Moment | Student Question / Intent | Required System Response | Target Milestone |
| :-: | :--- | :--- | :--- |
| **$M_1$** | *"Do I have to enter my timetable every week?"* | Master timetable profile configured once; recurring weekly inheritance. | Phase 1 |
| **$M_2$** | *"Let me jot this new homework down quickly."* | 10-second fast capture modal with intelligent defaults. | Phase 1 |
| **$M_3$** | *"When should I do all this work this week?"* | One-click full-week automated proposal generation. | Phase 1 |
| **$M_4$** | *"What should I focus on right now?"* | Minimalist Now / Next widget with clear visual priority. | Phase 2 |
| **$M_5$** | *"An unexpected meeting came up—don't wreck my week."* | Localized Ripple Repair: shifts only collided tasks while keeping $\ge 90\%$ of the week stable. | Phase 1 |
| **$M_6$** | *"I have too much work; is this week even possible?"* | Overload Assistant: explains shortage in exact minutes and recommends trade-offs (e.g. skip habit, shorten task). | Phase 1 |
| **$M_7$** | *"I didn't finish my study block today."* | 30-second daily evening check-in; automatically rolls unfinished duration into buffer slots. | Phase 2 |

---

## 3. Behavioral Psychology & Cognitive Enhancements

The Improve Plan introduces five critical behavioral mechanisms absent in Baseline V0:

### 3.1. Circadian Rhythm Energy Matching (Improve Plan §3.3 & Pillar 2)
- **Problem in V0:** Greedy First-Fit packs hard tasks into the earliest available window (e.g., placing complex math proofs at Monday 06:30 right after waking up).
- **V1 Solution:**
  - Tasks carry a cognitive classification: `DEEP` (high focus), `MEDIUM`, or `SHALLOW` (admin/chores).
  - Users define their chronotype preference: `MORNING` (08:00–11:30) or `EVENING` (18:00–21:00).
  - Solvers prioritize placing `DEEP` work into matching energy windows.

### 3.2. Mandatory Rest Breaks (Decision D2 & Table §3.3)
- **Problem in V0:** Solver packs tasks contiguously with 0-minute gaps between 90-minute blocks, causing cognitive fatigue.
- **V1 Solution:**
  - Every `DEEP` task with duration $\ge 90\text{ minutes}$ automatically reserves an inviolable 15-minute rest slot immediately following it before another task can be placed.

### 3.3. Planning Fallacy Buffer Multiplier (Feature F06)
- **Problem in V0:** Students routinely underestimate required study time by $20\text{--}40\%$ (Kahneman & Tversky's Planning Fallacy).
- **V1 Solution:**
  - Configurable behavioral buffer multiplier ($T_{\text{scheduled}} = T_{\text{estimate}} \times 1.25$).
  - For a 60-minute task, the engine allocates 75 minutes of grid space to absorb realistic overruns.

### 3.4. Overload Resolution & Habit Skipping (Feature F15)
- **Problem in V0:** When total task demand exceeds weekly free capacity, V0 blindly drops tasks based on raw priority numbers or deadline order.
- **V1 Solution:**
  - Classifies commitments into `ACADEMIC` vs `HABIT` (e.g., gym, reading).
  - Offers a tiered resolution dialog:
    1. `SKIP_HABIT`: Drop low-stake recurring habits first to preserve assignment deadlines.
    2. `SHORTEN_TASK`: Compress tasks with safety margins.
    3. `POSTPONE_LOWEST`: Explicitly defer low-priority items with clear confirmation.

### 3.5. Sprint Mode Compression Recovery (Features §4.1, §5.1)
- When a task misses a deadline by a tiny margin ($\le 15\text{ minutes}$), instead of failing and dropping the task, the solver temporarily compresses adjacent non-critical buffers (with user notification).

---

## 4. UI ↔ Engine Data Contract (Improve Plan §7.3)

The delivery layer communicates via a standardized ISO-8601 JSON schema:

```json
{
  "schedule_id": "SCH_2026_W45_001",
  "planning_week_start": "2026-11-02T00:00:00+07:00",
  "solver_used": "EDF_CIRCADIAN",
  "blocks": [
    {
      "task_id": "T_DEEP_ESSAY",
      "day": "Monday",
      "start_time": "18:00",
      "end_time": "19:30",
      "start_slot": 72,
      "end_slot": 78,
      "reasons": ["ENERGY_MATCH", "BEFORE_DEADLINE", "BREAK_AFTER"]
    }
  ],
  "unplaced_tasks": [],
  "metrics": {
    "total_tasks_placed": 1,
    "total_tasks_unplaced": 0,
    "hard_constraint_violations": 0,
    "energy_match_percentage": 100.0,
    "stability_score": 100.0
  }
}
```

---

## 5. Live Development Gaps Exposing V0 Limitations

The verification test suite maintains 5 intentional developmental target failure tests ([`test_improve_plan_gaps.py`](file:///d:/Projects/Computational-Thinking---Group-Project/group03-smartschedule-baseline/verification_tests/development_gap_tests/test_improve_plan_gaps.py)) tracking upcoming sprint work:

1. `test_fail_circadian_energy_matching`: Deep task placed at 06:30 instead of $\ge 18:00$.
2. `test_fail_rest_break_insertion_after_deep_work`: Gap between tasks is $0\text{m}$ instead of $\ge 15\text{m}$.
3. `test_fail_planning_fallacy_buffer_multiplier`: Scheduled duration is $60\text{m}$ instead of buffered $75\text{m}$.
4. `test_fail_why_popover_structured_reason_codes`: Reason code `'ENERGY_MATCH'` missing from block metadata.
5. `test_fail_overload_habit_skipping_recommendation`: Overload response fails to include `'SKIP_HABIT'` action.

