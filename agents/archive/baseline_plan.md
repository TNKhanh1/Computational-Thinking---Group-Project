# SmartSchedule — Baseline Plan (V0 Specification)

**Project:** SmartSchedule — Personal Productivity Assistant  
**Document Ref:** Based on `Baseline_Plan/baseline_plan.md`  
**Purpose:** Technical Reference for V0 Baseline Engine & Benchmark Infrastructure  
**Target Audience:** AI Coding Assistants & Engine Developers  

---

## 1. Principles & Purpose of the Baseline (V0)

The **Baseline (V0)** represents the foundational scientific benchmark for Group 03's Computational Thinking project. It isolates classical algorithmic capabilities from behavioral heuristics and machine learning to establish a reproducible performance baseline.

### 1.1. Core Directives
1. **Pure Determinism:** 
   - Given the exact same inputs (commitments, tasks, solver configuration), the solver must produce the exact same schedule every single run.
   - Determinism is verified cryptographically via 3x consecutive SHA-256 schedule hash equality.
2. **Zero AI / Zero LLM:**
   - No Large Language Models or fuzzy natural-language parsers are used for core scheduling.
   - All inputs are strictly structured data (JSON, CSV, or typed web form payloads).
3. **Zero Behavioral Psychology (Heuristic-Blind):**
   - **No Planning Fallacy Buffers:** $T_{\text{planned}} = T_{\text{estimate}}$ (no $1.25\times$ expansion).
   - **No Cognitive Load Classification:** Tasks are not split into Deep / Medium / Shallow for time-of-day assignment.
   - **No Circadian Energy Matching:** All available free slots have identical utility weights.
   - **No Automatic Rest Breaks:** Tasks are packed back-to-back contiguously if capacity allows.
   - **No Context-Switching Penalties:** No clustering or batching bonuses.

---

## 2. Mathematical Time Representation: The 672-Slot Grid

To make time computable, the continuous 7-day week ($10,080$ minutes) is discretized into a 1-dimensional array of **672 slots**, each representing exactly **15 minutes**:

$$\text{Slot Index} = \text{DayIndex} \times 96 + \text{Hour} \times 4 + \lfloor \text{Minute} / 15 \rfloor$$

Where:
- $\text{DayIndex} \in \{0 = \text{Monday}, 1 = \text{Tuesday}, \dots, 6 = \text{Sunday}\}$.
- Each day has $24 \times 4 = 96$ slots.
- Total week size: $7 \times 96 = 672$ slots ($[0, 671]$).

```text
Slot 000: Monday 00:00 - 00:15 [SLEEP]
Slot 026: Monday 06:30 - 06:45 [FREE]
Slot 030: Monday 07:30 - 07:45 [OCCUPIED: Lecture]
...
Slot 671: Sunday 23:45 - 24:00 [SLEEP]
```

### Slot State Enums
- `0` (`FREE`): Open window available for placing student tasks.
- `1` (`OCCUPIED`): Hard commitment (university lectures, lab sessions, fixed job shifts).
- `2` (`SLEEP`): Inviolable biological recovery window (default: 23:30 to 06:30 daily).
- `100+` (`TASK`): Slot reserved by an assigned task ID.

---

## 3. Hard Constraints Formulation ($H_1$ to $H_5$)

The baseline solver treats scheduling as a **Classical Constraint Satisfaction Problem (CSP)** with 5 non-negotiable hard constraints:

| Constraint | Name | Mathematical Formulation | Failure Penalty |
| :-: | :--- | :--- | :--- |
| **$H_1$** | **Fixed Event Collision** | $\forall b \in \text{Blocks}, \forall f \in \text{FixedEvents}: [s_b, e_b) \cap [s_f, e_f) = \emptyset$ | Hard Invalidation ($C_{\text{hard}} = \infty$) |
| **$H_2$** | **Sleep Window Protection** | $\forall b \in \text{Blocks}, \forall \text{day}: [s_b, e_b) \cap \text{SleepWindow}_{\text{day}} = \emptyset$ | Hard Invalidation ($C_{\text{hard}} = \infty$) |
| **$H_3$** | **Free Slot Legality** | $\forall b \in \text{Blocks}, \forall t \in [s_b, e_b): \text{Grid}[t] = \text{FREE}$ | Overwrite Rejection |
| **$H_4$** | **Deadline Compliance** | $\forall b \in \text{Blocks}: e_b \le \text{DeadlineSlot}(\text{Task}_b)$ | Dropped to Unplaced |
| **$H_5$** | **DAG Prerequisite Order** | $\forall (u, v) \in \text{Dependencies}: e_u \le s_v$ | Dependency Error |

---

## 4. Baseline Scheduling Algorithms

The baseline system implements three classical greedy scheduling heuristics:

### 4.1. Earliest Deadline First (EDF) — Primary Baseline
- **Mechanism:**
  1. Topologically sorts tasks to respect dependency prerequisites ($H_5$).
  2. Sorts available tasks by deadline ascending ($d_i$). Ties are broken by priority descending ($p_i$), then duration ascending.
  3. Iterates over free contiguous blocks from Monday 00:00 forward (First-Fit).
  4. Places task into the first continuous free window of length $L \ge \lceil \text{duration} / 15 \rceil$ that completes before $d_i$.
  5. If no valid gap exists before the deadline, marks task as `unplaced` with diagnostic reason `CAPACITY_SHORTAGE` or `DEADLINE_PASSED`.

### 4.2. Least Slack Time (LST) — Heuristic Variant
- **Mechanism:**
  - Evaluates slack for each task at current time $t$: $\text{Slack}_i(t) = d_i - t - \text{duration}_i$.
  - Prioritizes tasks with minimum slack (highest urgency).

### 4.3. Weighted Shortest Processing Time (WSPT) — Heuristic Variant
- **Mechanism:**
  - Computes efficiency ratio: $R_i = p_i / \text{duration}_i$.
  - Maximizes immediate value density under unconstrained time grids.

---

## 5. Course Scenarios & Benchmarking Suite (T01–T10)

The baseline is evaluated across 10 standardized course scenarios defined in `Baseline_Plan/baseline_plan.md`:

- **T01 (Baseline Feasibility):** Standard student profile with 15 tasks; verifies complete feasibility without constraint violations.
- **T02 (Underload):** Low commitment load; tests compactness and unnecessary gap fragmentation.
- **T03 (Overload):** 35 hours of tasks competing for 20 hours of free time; asserts intelligent dropping of lowest-priority tasks without corrupting high-priority items.
- **T04 (Tight Deadline Cluster):** Multiple tasks due on the exact same afternoon; verifies priority preservation.
- **T05 (High Fixed Commitment Density):** Medical/engineering student schedule with 40+ hours of lab/lectures.
- **T06 (Long Atomic Task):** 4-hour unsplittable study session needing large continuous free blocks.
- **T07 (Prerequisite DAG Chain):** 4-stage project pipeline ($\text{Proposal} \to \text{Draft} \to \text{Code} \to \text{Slide}$).
- **T08 (Weekend Preference):** Tasks requested specifically for Saturday/Sunday execution.
- **T09 (Late Night Deadlines):** Tasks with 23:59 Sunday deadlines testing boundary slots.
- **T10 (Emergency Disruption):** Sudden insertion of an urgent 3-hour task causing minimal schedule ripple.

