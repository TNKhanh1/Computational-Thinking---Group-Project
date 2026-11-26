# Abstraction of Problem Definition into Formal Specification & 14-Pattern Algorithmic Bridge

> **Purpose:** Slide-ready academic specification, behavioral simulation reference guide, and Q&A defense blueprint for **Group 03 — SmartSchedule (`v1.0-alpha`)**, directly addressing every point of instructor feedback from the Feature/Proposal Presentation to maximize the Final Presentation score.
>
> **Core Technical & Verification Task Force (`v1.0-alpha` Deep-Thinking Upgrade):**
> - **Idea & Core Engineering Leads:** Nguyễn Nguyễn Gia Bảo (`M7` — `InSilicoStudentSimulator` §9.7 + `DocumentConstraintDigest` + E2E) & Lê Tiến Bình (`M5` — `CrossWeekPreferenceAdapter` §7.8.3–7.8.4 + `LocalRepairEngine` + APIs)
> - **Formal Spec, Grounded Chat Router & Claude-Plan Verification Lead:** Nguyễn Trọng Tiến (`M4` — §5 Abstraction, `handlers.py` DAG/Doc/Adaptation wiring, & independent mathematical/edge-case audit)
> - **Supporting Product & Evaluation Flows (Lightweight Scope):** Phạm Đức Minh (`M1`), Trần Nguyên Khánh (`M2`), Hoàng Minh Anh (`M3`), Lê Minh Nhật (`M6`)

---

## 1. Instructor Feedback Traceability Matrix

| # | Instructor Feedback Point | Root Cause in `Presentation2.pdf` | Exact Upgrade in `v1.0-alpha` & Final Slides |
| :-: | :--- | :--- | :--- |
| **1** | *"Problem Definition: Very good human-language description — Need sample input and corresponding sample output"* | Slide 4 only had prose; Slide 5 only listed conceptual bullets with no concrete instance. | Added **verified bit-exact Sample Input $\mathcal{I}_{\text{sample}} \to$ Sample Output $\mathcal{O}_{\text{sample}}$** (`SHA-256: 9157054420ae`, incl. DAG `PRJ-1, PRJ-2 -> PRJ-3` & `LOCAL_INSERTION` repair) in **Section 2.4** below + 1-click preset in Onboarding (`M1`). |
| **2** | *"Add more slides for Input and Output and **their types in Formal Spec**. Put these slides under the title **'Abstraction of Problem Definition into Formal Specification'**"* | Slide 5 & Slide 6 described inputs/outputs informally without mathematical domains, tuples, or invariant formulas. | Created **4 dedicated slides** in **Section 2** under the exact required title ***"Abstraction of Problem Definition into Formal Specification"***, including `DocumentConstraintDigest` ($\mathcal{D}_{\text{doc}}$) and Cross-Week Behavioral State ($\mathcal{H}^{(t-1)}_{\text{hist}} \to \mathcal{P}_t, \mathcal{T}'_t$). |
| **3** | *"Does any of your abstraction rely on some reasoning (such as any patterns)? Why did you do abstraction in that way but not other ways?"* | Slide 6 showed *what* was stripped vs. kept, but did not justify *why* alternatives (continuous time, float curves, `0..100` weighted sum, linear clock, 70B LLM simulation) were rejected. | Added **7-row Pattern-Driven Abstraction Trade-off Matrix** in **Section 3**, proving how each abstraction is forced by specific behavioral/computational patterns (`P2`, `P3`, `P5`, `P9`, `P14`, Goodhart's Law) and complexity bounds ($O(1)$ prefix sums). |
| **4** | *"The problem is too simple, need to add more difficult feature (in term of thinking)"* | Slide 16 only presented a basic 5-step single-week Greedy pipeline, omitting longitudinal learning, document structure, and DAG/ALNS math. | Added **Cross-Week Fallacy Buffer & Revealed-Preference Adaptation (`M5`)**, **Validated Multi-Week In-Silico Behavioral Simulation (`M7` — solving the short-semester field study bottleneck!)**, **Logical Attachment-to-DAG Parsing (`M7`+`M4`)**, plus exposed **Topological DAG (`P10`)** and **`HYBRID_ALNS` / Overload Triage (`P11`)**. |
| **5** | *"Excellent table of Pattern Recognition... However some need a clearer explanation of the linking between Pattern and Deterministic Logic Rule. Try to add more Pattern to get maximum score."* | Slides 7–8 had 8 patterns, some with qualitative links (e.g., `"stability >= X%"`) and missing cross-week adaptive & multimodal patterns. | Expanded **8 $\to$ 14 Patterns (`P1–P14`)** in **Section 4** with an explicit **Causal Bridge column (*Why this exact math rule?*)**, backed by peer-reviewed psychology citations & open-source references in **Section 5**. |

---

## 2. Slide Deck Section: *"Abstraction of Problem Definition into Formal Specification"*

> [!IMPORTANT]
> Use the exact section header ***"Abstraction of Problem Definition into Formal Specification"*** across the 4 slides below (`2.1` $\to$ `2.4`) in the Final Presentation deck.

### Slide 2.1 — Abstraction of Problem Definition into Formal Specification (1/4: Discrete Time & State Space)

* **Continuous-to-Discrete Horizon Mapping:**
  Given planning horizon $H \in \{7, 14\}$ days (`horizon_days`) anchored at Monday `00:00` ($t_0$) and quantum $\Delta t = 15\text{ min}$, continuous time is abstracted into a finite index set of $S = 96H \in \{672, 1344\}$ contiguous slots:

  $$
  \mathbb{T}_H = \{0, 1, \dots, S - 1\}, \qquad \text{slot}(d, h, m) = 96d + 4h + \left\lfloor \frac{m}{15} \right\rfloor \quad (d \in \mathbb{Z}_H,\; h \in \mathbb{Z}_{24},\; m \in \mathbb{Z}_{60})
  $$

* **Grid Cell State Domain & Circadian Energy Function ([`grid_manager.py`](../../smartschedule/core/grid_manager.py), [`models.py`](../../smartschedule/core/models.py)):**
  - **Slot State Map:** $\sigma : \mathbb{T}_H \to \Sigma$, where $\Sigma = \{\texttt{FREE},\; \texttt{SLEEP},\; \texttt{OCCUPIED},\; \texttt{BLOCK},\; \texttt{REST}\}$ (with sub-tags $\texttt{REST:BREAK}$ and $\texttt{REST:DEAD\_ZONE}$).
  - **Immutable Lock Mask:** $\Lambda : \mathbb{T}_H \to \{0, 1\}$, where $\Lambda(s) = 1 \iff \sigma(s) \in \{\texttt{SLEEP}, \texttt{OCCUPIED}\} \cup \text{slots}(\Pi_{\text{pin}} \cup \Pi_{\text{done}})$.
  - **24h Periodic Circadian Alertness Function:** $E : \mathbb{T}_H \to \{1, 2, 3\}$ (`1 = Low`, `2 = Medium`, `3 = Peak`), periodic modulo $96$ slots/day ($E(s) = E_{\text{band}}(\lfloor (s \bmod 96)/4 \rfloor)$).

---

### Slide 2.2 — Abstraction of Problem Definition into Formal Specification (2/4: Formal Input Types)

An instance of the SmartSchedule problem is a 5-tuple $\mathcal{I} = (\mathcal{P},\; \mathcal{T},\; \Pi_{\text{lock}},\; \Delta_{\text{disrupt}},\; s_{\text{now}})$:

| Formal Symbol | Mathematical Type & Domain | Code Schema (`models.py`) | Semantic Meaning & Domain Bounds |
| :--- | :--- | :--- | :--- |
| $s_{\text{now}}$ | $\mathbb{Z}_{S+1}$ (`0 .. 96H`) | `CommitmentsProfile.now` | Current cut-off slot; future blocks must satisfy $s \ge s_{\text{now}}$ |
| $\mathcal{S}_{\text{sleep}}$ | $\mathbb{Z}_{96} \times \mathbb{Z}_{96} \times \mathbb{B}$ | `SleepSchedule` | `(start_tod, end_tod, is_hard_lock=True)` with nightly span $\ge 24$ slots ($\ge 6\text{h}$) |
| $\mathcal{F} = \{F_k\}_{k=1}^m$ | $2^{\mathbb{Z}_7} \times \mathbb{Z}_{96} \times \mathbb{Z}_{96} \times \mathcal{C}_{\text{fix}}$ | `List[FixedEvent]` | Recurring non-negotiable intervals (classes, meals, shifts); $\mathcal{C}_{\text{fix}} = \{\texttt{CLASS}, \texttt{MEAL}, \texttt{MEETING}, \dots\}$ |
| $\mathcal{H}_{\text{hab}} = \{B_u\}$ | $\Sigma^* \times \mathcal{W} \times \{1..7\} \times 15\mathbb{N}^+$ | `List[PersonalHabit]` | Weekly routines `(name, window, freq_per_week, duration_min)` expanded into priority-`1` tasks |
| $\mathcal{P}$ | $(\mathbb{T}_H, \mathcal{S}_{\text{sleep}}, \mathcal{F}, E, \mu_{\text{buf}}, \alpha_L, \alpha_H, \mathcal{H}_{\text{hab}})$ | `CommitmentsProfile` | Student constraint & biological profile; $\alpha_L, \alpha_H \in [1.00, 1.60]$, $\mu_{\text{buf}} \in \{\texttt{COGNITIVE\_LOAD}, \texttt{HABIT}, \texttt{NONE}\}$ |
| $T_i \in \mathcal{T}$ | $(\text{id}_i, d_i, r_i, D_i, p_i, \ell_i, \text{sp}_i, [c^{\min}_i, c^{\max}_i], W_i, \overline{W}_i, \text{Pred}_i)$ | `Task` (`i = 1..n`) | $d_i \in \mathbb{N}^+$ (raw min), $r_i \in \mathbb{Z}_S \cup \{0\}$ (`start_after`), $D_i \in \{1..S\} \cup \{\infty\}$ (`deadline_slot`), $p_i \in \{1..5\}$ (`priority`), $\ell_i \in \{1,2,3\}$ (`cognitive_load`), $\text{sp}_i \in \mathbb{B}$ (`is_splittable`), $15 \le c^{\min}_i \le c^{\max}_i$, $W_i \in \{\texttt{MORNING}, \texttt{AFTERNOON}, \texttt{EVENING}, \texttt{ANYTIME}\}$, $\overline{W}_i \subseteq \mathcal{W}$ (`avoid_windows`), $\text{Pred}_i \subseteq \{\text{id}_1..\text{id}_n\}$ (`depends_on` forming DAG $G=(\mathcal{T}, E_{\text{prec}})$) |
| $\Pi_{\text{lock}}$ | $\mathcal{P}(\mathcal{T} \times \mathbb{N}^+ \times \mathbb{Z}_S \times \mathbb{Z}_S)$ | `List[ScheduleBlock]` | User-pinned (`PINNED`) or completed (`DONE`) immutable block intervals $[s, e)$ |
| $\Delta_{\text{disrupt}}$ | $(\mathbb{Z}_S \times \mathbb{Z}_S) \cup (\text{id}_i \times \mathbb{N}^+) \cup \{\varnothing\}$ | `DisruptionEvent` | Optional runtime emergency event $[s_{\text{dis}}, e_{\text{dis}})$ or task duration overrun $\Delta d_i$ |
| $\mathcal{D}_{\text{doc}}$ | $\Sigma^* \times \text{List}[\text{Milestone}] \times \mathbb{N}^+ \times \{1..5\}$ | `DocumentConstraintDigest` | Logical attachment abstraction (`.pdf/.md/.txt` $\to$ weighted subtasks, implicit `depends_on` edges, & effort lower-bound sanity check) |
| $\mathcal{H}_{\text{hist}}^{(t-1)}$ | $\text{List}\big[(\text{cat}, \ell, w_{\text{tod}}, d_{\text{est}}, d_{\text{act}}, \text{adhered}, \text{disrupted})\big]$ | `completion_logs` + timeline telemetry | Recorded execution behaviors from Week $t-1$ driving Cross-Week Fallacy Buffer $\hat{\alpha}^{(t)}_{c,\ell}$ & Revealed-Preference adaptation ($\mathcal{P}_t, \mathcal{T}'_t$) |

---

### Slide 2.3 — Abstraction of Problem Definition into Formal Specification (3/4: Formal Output, Hard Gates & Objective)

* **Formal Output Tuple (`ScheduleOutput` & `RepairOutput`):**

  $$
  \mathcal{O} = \big(\text{status},\; \Pi,\; \mathcal{U},\; \mathcal{R}_{\text{ovld}},\; h_{\text{det}}\big), \qquad \Pi = \big\{ B_{i,j} = (\text{id}_i, j, s_{i,j}, e_{i,j}, \text{st}_{i,j}) \;\big|\; s_{i,j}, e_{i,j} \in \mathbb{Z}_{S+1},\; s_{i,j} < e_{i,j} \big\}
  $$

  where $\text{status} \in \{\texttt{SUCCESS}, \texttt{PARTIAL\_OVERLOAD}, \texttt{INFEASIBLE\_CAPACITY}\}$, $\mathcal{U} \subseteq \mathcal{T}$ is the unplaced task set, $\mathcal{R}_{\text{ovld}}$ is the exact minute-deficit `OverloadReport`, and $h_{\text{det}} \in \{0..9,\text{a}..\text{f}\}^{64}$ is the SHA-256 determinism digest.

* **Hard Feasibility Gate $G_1(\mathcal{I}, \Pi) = 0$ (Zero Violations Across 10 Invariants in [`gates.py`](../Testing_System/evaluator/gates.py)):**
  1. **Non-Overlap with Fixed & Sleep ($H_1, H_2$):** $\forall B_{i,j} \in \Pi,\; \forall s \in [s_{i,j}, e_{i,j}):\; \sigma_0(s) \notin \{\texttt{OCCUPIED}, \texttt{SLEEP}\}$.
  2. **Pairwise Disjointness ($H_3$):** $\forall (i,j) \ne (i',j'):\; [s_{i,j}, e_{i,j}) \cap [s_{i',j'}, e_{i',j'}) = \varnothing$.
  3. **Release, Present & Deadline Bounds ($H_4$):** $\max(s_{\text{now}}, r_i) \le s_{i,j} < e_{i,j} \le \min(D_i, S)$ for all non-locked chunks.
  4. **Topological DAG Precedence ($H_5$):** $\forall u \in \text{Pred}_v:\; v \text{ placed} \implies u \text{ placed} \;\land\; \max_k e_{u,k} \le \min_j s_{v,j}$.
  5. **Buffered Duration Conservation & Legal Chunking:** $\sum_{j=1}^{k_i} 15(e_{i,j} - s_{i,j}) = d^{\text{plan}}_i = \lceil d_i \alpha_i / 15 \rceil \cdot 15$, with $\neg\text{sp}_i \implies k_i = 1$, and $\text{sp}_i \implies c^{\min}_i \le 15(e_{i,j}-s_{i,j}) \le c^{\max}_i$ (ordered $e_{i,j} \le s_{i,j+1}$).
  6. **Pin Preservation:** $\Pi_{\text{lock}} \subseteq \Pi$ at exact coordinates.

* **Non-Compensatory Optimization Objective ($\varepsilon$-Bucketed 10-Level Lexicographic Vector $\mathcal{L}_{10}$ in [`verdict_and_icee.py`](../Testing_System/evaluator/verdict_and_icee.py)):**

  $$
  \min_{\Pi:\; G_1(\mathcal{I}, \Pi)=0} \; \mathcal{L}_{10}(\Pi) = \Big\langle \text{SLA}_{>1\text{s}},\; \text{Tier}_{\text{v2.1}},\; -P_{1.1},\; -\lfloor \text{Shk}_{25}/5 \rfloor,\; \Phi_{\text{break}},\; \Phi_{\text{bio}},\; \lfloor \text{Cram}_{<10\text{h}}/5 \rfloor,\; \Phi_{\text{cap}},\; \text{Ctx},\; -\Phi_{\text{pref}},\; \Phi_{\text{pace}} \Big\rangle_{\text{lex}}
  $$

---

### Slide 2.4 — Abstraction of Problem Definition into Formal Specification (4/4: Verified Sample Input $\to$ Corresponding Sample Output)

> **Reproducible Command:** `ScheduleController.solve_schedule(sample_week_commitments, sample_week_tasks, algorithm="SCORED_GREEDY")` (`buffer_mode="COGNITIVE_LOAD"`, `focus_preference="MORNING"`).

| **Sample Input $\mathcal{I}_{\text{sample}}$ (`MINH_FIT_HCMUS`)** | **Corresponding Sample Output $\mathcal{O}_{\text{sample}}$ (`SHA-256: 9157054420ae`, `65.0 ms`)** |
| :--- | :--- |
| **1. Profile $\mathcal{P}$ ($H=7$, $S=672$, $s_{\text{now}}=26$ [Mon `06:30`]):**<br>• **Sleep $\mathcal{S}_{\text{sleep}}$:** `23:30–06:30` nightly (`28` slots = `7h` $\ge 6\text{h}$, locked)<br>• **Classes & Meals $\mathcal{F}$:**<br>  - `CLASS_MWF`: Mon/Wed/Fri `13:00–17:00` (`48` slots)<br>  - `CLASS_TTH`: Tue/Thu `08:00–11:00` (`24` slots)<br>  - `MEETING_THU`: Thu `19:30–20:30` (`4` slots)<br>  - `MEAL_*`: Daily `07:00–07:30`, `12:00–12:45`, `18:30–19:15`<br>• **Circadian & Buffer:** `MORNING` (`E=3` at `06:00–12:00`, `E=2` at `12:00–18:00`, `E=1` at `18:00–06:00`); $\alpha_L = 1.20, \alpha_H = 1.35$<br><br>**2. Task Set $\mathcal{T}$ (`9` tasks, incl. DAG `PRJ-1, PRJ-2 -> PRJ-3`):**<br>• `MATH-1`: $d=120\text{m} \xrightarrow{\times 1.35} 165\text{m}$, $D=\text{Wed 13:00}$, $p=5, \ell=3$, `split=T`<br>• `LAB-1`: $d=60\text{m} \xrightarrow{\times 1.20} 75\text{m}$, $D=\text{Tue 23:59}$, $p=3, \ell=2$, `split=F`<br>• `PRJ-1`: $d=120\text{m} \to 165\text{m}$, $D=\text{Sun 23:59}$, $p=5, \ell=3$, `Pred=[]`<br>• `PRJ-2`: $d=120\text{m} \to 165\text{m}$, $D=\text{Sun 23:59}$, $p=5, \ell=3$, `Pred=[]`<br>• **`PRJ-3`**: $d=120\text{m} \to 150\text{m}$, $D=\text{Sun 23:59}$, $p=5, \ell=2$, **`Pred=["PRJ-1","PRJ-2"]`**<br>• `PRJ-4`: $d=180\text{m} \to 245\to 240\text{m}$, $D=\text{Sun 23:59}$, $p=5, \ell=3$, `split=T`<br>• `PRJ-5`: $d=60\text{m} \to 75\text{m}$, $D=\text{Sun 23:59}$, $p=5, \ell=2$, `split=F`<br>• `LAUNDRY` ($45\text{m}\to 60\text{m}$), `CLEAN` ($30\text{m}\to 45\text{m}$): $D=\infty, p=1, \ell=1$ | **1. Primary Schedule $\Pi$ (`status="SUCCESS"`, `9/9` tasks = `15/15` chunks, $G_1=0$):**<br>• **Mon (`E=3` Peak):** `MATH-1_P1` `07:30–09:00` (`90m`) $\to$ *`30m` Break* $\to$ `MATH-1_P2` `09:30–10:45` (`75m`)<br>• **Tue (`E=2`):** `LAB-1_P1` `12:45–14:00` (`75m`, atomic) $\to$ `PRJ-5_P1` `14:30–15:45` (`75m`)<br>• **Wed (`E=3` Peak):** `PRJ-1_P1` `07:30–09:00` (`90m`) $\to$ *`30m` Break* $\to$ `PRJ-1_P2` `09:30–10:45` (`75m`, **PRJ-1 done @ slot `235`**)<br>• **Thu (`E=1` Low):** `CLEAN_P1` `20:30–21:15` (`45m` chore matched to low energy)<br>• **Fri (`E=3` Peak):** `PRJ-2_P1` `07:30–09:00` (`90m`)<br>• **Sat:** `PRJ-2_P2` `07:30–08:45` (**PRJ-2 done @ slot `515`**) $\to$ *Break* $\to$ `PRJ-4_P1` `09:15–10:45` (`E=3`) $\to$ **`PRJ-3_P1` `12:45–14:00` (starts @ slot `531 > 515`, honoring DAG $H_5$!)** $\to$ `LAUNDRY_P1` `19:15–20:15` (`E=1`)<br>• **Sun:** `PRJ-4_P2` `07:30–09:00` $\to$ *Break* $\to$ `PRJ-4_P3` `09:30–10:45` (`E=3`) $\to$ `PRJ-3_P2` `12:45–14:00` (`E=2`)<br><br>**2. Dynamic Disruption $\Delta_{\text{disrupt}}$ = Emergency Meeting `Mon 07:30–09:00` (`LOCAL_INSERTION`):**<br>• **Moved:** ONLY `MATH-1_P1` (`Mon 07:30–09:00` $\to$ `Mon 17:00–18:30`)<br>• **Stability:** **`14 / 14 = 100.0%` unaffected blocks unchanged** (`Experience Rating = 1.79 Comfortable`) |

---

## 3. Reasoning Behind Abstraction Choices (*"Why This Way and NOT Other Ways?"*)

> [!TIP]
> **Direct Answer to Instructor Question:** *"Does any of your abstraction rely on some reasoning (such as any patterns)? Why did you do abstraction in that way but not other ways?"*
> **Yes — every core abstraction in SmartSchedule is derived directly from empirical human patterns and computational complexity invariants.**

| Abstraction Decision | Chosen Formal Representation | Rejected Alternative A | Rejected Alternative B | Pattern & Algorithmic Reasoning (*Why Chosen Wins*) |
| :--- | :--- | :--- | :--- | :--- |
| **1. Temporal Representation** | **Discrete `15-min` Slot Array** $\mathbb{Z}_{96H}$ (`672` / `1344` slots) with bitmask & $O(1)$ prefix sums | **Continuous Real Intervals** $[t_s, t_e) \subset \mathbb{R}_{\ge 0}$ / Interval Tree | **1-min Grid** (`10,080` slots/wk) or **60-min Grid** (`168` slots/wk) | **Driven by Patterns `P2` (`15m` post-deep break) & `P5` (`<30m` dead-zone = `2` slots)** + university `:00/:15/:30/:45` GCD. Continuous intervals suffer float slivers (`13.7m`) and cannot precompute $O(1)$ range energy sums (`pref_energy_sum`); `1-min` inflates ALNS search $15\times$ with zero human meaning; `60-min` cannot represent `15m` breaks or `45m` chunks. |
| **2. Biological Alertness & Task Effort** | **3-Tier Ordinal Scale** $E(s) \in \{1, 2, 3\}$ & $\ell_i \in \{1, 2, 3\}$ | **Continuous Float Curve** $E(t) \in [0.0, 1.0]$ | **Binary Flag** (`Hard` vs `Easy`) | **Driven by Pattern `P3` (Circadian Synchrony: Peak / Intermediate / Trough phases, May & Hasher 1998)** and **User Input Noise Pattern**: students cannot self-report `"effort = 0.73 vs 0.68"`, whereas binary loses intermediate daytime slots (`E=2`). Ordinal `{1,2,3}` enables exact counterfactual logic (`forbid L=3 at E=1 iff E>=2 exists`). |
| **3. Multi-Criteria Objective** | **10-Level $\varepsilon$-Bucketed Lexicographic Tuple** $\mathcal{L}_{10}$ + Separate `G1/G2` Gates | **Weighted Linear Sum** $\sum w_k M_k \in [0, 100]$ | **Strict Unbucketed Lexicographic** ($\varepsilon = 0$) | **Driven by Goodhart's Law (`CT_Rationale_Log #1, #7, #8`):** A `0..100` linear sum lets `100%` Peak match mask `4` consecutive heavy sessions with zero rest (`85/100` burnout schedule!). Conversely, $\varepsilon=0$ lexicographic flips rank over trivial `4.5m` noise (`Regime 3`). $\varepsilon$-bucketing (`5%` / `30m` tiers) prevents both compensatory masking and noise fragility. |
| **4. Circadian Phase Drift (`Social Jetlag`)** | **Unit-Circle Projection** $\theta_s = \frac{2\pi(s \bmod 96)}{96} \in S^1$ (`sin/cos` sums) | **Linear Minute Mean** $\frac{1}{K}\sum m_k \in [0, 1440)$ | **Ignoring Day-to-Day Phase** (only counting daily hours) | **Driven by Pattern `P9` (Night-Owl Midnight Wraparound, Smarr & Schirmer 2018):** Linear arithmetic computes the midpoint of `23:30` (`1410m`) and `00:30` (`30m`) as **`12:00` noon** (`720m` — `12h` error!). Circular $S^1$ trigonometry yields the true `00:00` midnight phase in $O(1)$ incremental updates. |
| **5. Overload vs. Solver Failure** | **Structural Load Ratio Gate `G2` ($\rho$)** separating `SUBOPT` ($\rho \le 1$) vs `OVERLOAD_TRIAGE` ($\rho > 1$) | **Single Penalty Per Unplaced Task** | **Hard Exception / Reject Schedule** | **Driven by Pattern `P11` (Capacity Cliff & Triage):** Dropping a task when $\rho = 0.75$ is an *algorithmic fragmentation bug* (must trigger Kempe/ALNS rescue), whereas dropping low-priority habits when $\rho = 1.30$ is *mathematically unavoidable* (must trigger knapsack triage + interactive Pareto options). |
| **6. Conversational Task Identity & UX** | **SHA-256 Keyword Fingerprints** + **User Mode vs. `Developer Mode` Split** | **Requiring Manual Form IDs / Exposing Raw Solver Knobs** | **Stateful Black-Box LLM Memory** | **Driven by Cognitive Friction & Determinism:** Students refer to tasks by fuzzy subject phrases (*"bài Giải tích"*), not `T_04`, and get overwhelmed by `alpha`/`L3` forms (MVP Demo Feedback). SHA-256 unigram/bigram hashing resolves references deterministically in `<1 ms` with `0 MB` LLM state, while Progressive Disclosure hides solver internals from normal users. |
| **7. Longitudinal Behavioral Validation** | **5-Law Mechanistic Cognitive Agent (`InSilicoStudentSimulator`: TMT + McFadden RUM + LogNormal + MCTQ + Fatigue)** | **70B LLM Foundation Simulacra** (`Centaur` / `genagents` per slot) | **Unvalidated Static Heuristics** (waiting 8 real weeks with 0 test) | **Driven by Pattern `P14` & `INV-5` (`<350KB`, SHA-256 Determinism):** While LLM cognitive models (*Binz et al., Nature 2025*; *Park et al., 2024*) require heavy GPUs and non-deterministic sampling across $672 \times 4$ slots, abstracting student behavior into 5 peer-reviewed psychometric equations simulates `50–1,000` students $\times$ `4–6` closed-loop weeks in `<500 ms` on CPU with 100% seed reproducibility! |

---

## 4. Expanded 14-Pattern Recognition $\to$ Deterministic Logic Rule Table (`P1–P14`)

> [!IMPORTANT]
> This table upgrades the original 8 patterns (`P1–P8`) with an explicit **Causal Bridge (*Why this rule?*)** and adds **6 advanced Computational Thinking patterns (`P9–P14`)** covering Circular Social Jetlag, Topological DAGs, Non-Monotone Regime Escalation, Cross-Week Preference & Fallacy Buffer Learning, and Mechanistic In-Silico Behavioral Simulation.

| ID | Human / Computational Pattern | Failure Mode Without Rule | Causal Bridge (*Why Pattern $\implies$ Exact Rule*) | Deterministic Logic Rule & Code Module |
| :-: | :--- | :--- | :--- | :--- |
| **`P1`** | **Asymmetric Planning Fallacy & Over-Buffering Cliff** *(Buehler et al., 1994)* | Students underestimate durations by `25–40%` (cascading late tasks), yet inflating $\alpha \ge 1.70$ causes `20%` false capacity shortages. | Deep tasks incur higher variance than routine tasks, discrete grids require slot-ceiling alignment, and empirical grid sweep proves $\alpha > 1.60$ wastes prime slots. | $d^{\text{plan}}_i = \left\lceil \frac{d_i \cdot \alpha(\ell_i)}{15} \right\rceil \cdot 15$, with $\alpha(1,2)=1.20$, $\alpha(3)=1.35$, clamped to $[1.00, 1.60]$ ([`estimate_buffer.py`](../../smartschedule/core/estimate_buffer.py)). |
| **`P2`** | **Ultradian `90m` Focus Depletion & Post-Class Fatigue** | Continuous `3h` blocks or jumping into `L=3` study right after a `2h` lecture causes severe cognitive exhaustion. | Working memory saturates after `90m` (`6` slots) of `L=3` effort or $\ge 90\text{m}$ lectures, requiring at least `1` discrete `15m` recovery slot before another heavy load. | Split `split=True` tasks into $[45, 90]\text{m}$ chunks; enforce $\ge 1$ `REST` slot (`15m`) after every `L=3` block & after classes $\ge 90\text{m}$; cap `L>=2` streaks $\le 120\text{m}$ ([`ergonomic_engine.py`](../../smartschedule/core/solvers/ergonomic_engine.py)). |
| **`P3`** | **2-Way Circadian Synchrony (`Lark` / `Owl` / `Finch`)** *(May & Hasher, 1998)* | Scheduling `L=3` synthesis during circadian troughs (`E=1`, e.g. morning for Night Owls) slashes throughput and causes task abandonment. | A strict `"always E=3"` rule fails if deadlines precede the next peak; therefore the rule must be *counterfactual* over reachable pre-deadline slots. | **Counterfactual `BIO-SYNC`:** Forbid placing $\ell_i=3$ at $E(s)=1$ *iff* $\exists$ feasible $[s', e') \le D_i$ with $\bar{E} \ge 2.0$; reserve Peak ($E=3$) slots for $\ell_i=3$ (`APk% >= 50%`) ([`ergonomic_engine.py`](../../smartschedule/core/solvers/ergonomic_engine.py)). |
| **`P4`** | **Attention Residue & Meal-Boundary Disruption** | Rapidly alternating `MATH -> ESSAY -> CODE` within `15–30m` or sandwiching meals between heavy tasks wastes `15–25m` of re-orientation. | Context residue decays over `>30m` (`>2` slots); grouping identical `category` chunks amortizes mental setup cost. | Add batching bonus when `cat(B_a) == cat(B_b)` within the same day; penalize `cat` switches separated by $\le 2$ slots (`Ctx < max(4, study_days)`) and ban `L>=2` on both sides of `MEAL` ([`pillars.py`](../Testing_System/evaluator/pillars.py)). |
| **`P5`** | **Sub-`30m` Fragmentation ("Dead-Time Paradox")** | `15m` slivers between lectures look `"free"` on paper (`total_free_min` seems sufficient) but are unusable for real study. | Setup + teardown overhead exceeds `15m`, so `1`-slot isolated islands create a false illusion of capacity (`FRAGMENTATION_FAILURE`). | Scan grid post-masking: any isolated `FREE` run of length `< 2` slots (`< 30m`) is relabeled `REST:DEAD_ZONE` and excluded from `L>=2` chunk placement ([`grid_manager.py`](../../smartschedule/core/grid_manager.py)). |
| **`P6`** | **Non-Linear Cumulative Sleep Debt** | Cutting nightly sleep below `6h` to cram deadlines collapses next-day cognitive capacity across the entire week. | Because sleep deprivation degrades *all* subsequent slots non-linearly, sleep cannot be traded off as a soft penalty even during crunch weeks. | Hard invariant $H_2$: lock $\ge 24$ slots/night (`>= 6h`) in immutable `_locked_mask`; Tier-1 Crunch may relax `15m` breaks, **never** `SLEEP`, and Chat rejects `<6h` sleep edits (`M3`, [`models.py`](../../smartschedule/core/models.py)). |
| **`P7`** | **Hyperbolic Procrastination & `<10h` Panic Cramming** *(Steel & König, 2006)* | Pure LST/deadline sorting ignores tasks with wide windows until the final `<10h`, causing last-night workload spikes. | Perceived urgency rises exponentially as slack $s_h$ shrinks; combining exponential urgency with explicit anti-cramming prevents late crowding. | Rank via $\text{Score}(T_i) = p_i \cdot \exp(-s_h / 24.0)$ ($s_h > 0$) + `NO-CRAM` rule penalizing $>25\%$ of wide-window work (`>10h` span) placed inside $[D_i - 40, D_i)$ ([`scored_greedy.py`](../../smartschedule/core/solvers/scored_greedy.py)). |
| **`P8`** | **Schedule Whiplash & Plan Abandonment on Disruption** *(Vieira et al., 2003)* | Re-running global scratch scheduling after a `1h` club meeting reshuffles `70%+` of unrelated study blocks, breaking user trust. | Habitual adherence requires minimizing perturbation distance $D(\Pi_0, \Pi_1)$ by isolating repair strictly to collided slots unless mathematically deadlocked. | **`LOCAL_INSERTION` (`M5`):** Freeze `PINNED`/`DONE` + all non-colliding blocks; move only collided chunks minimizing $|\Delta s|$; progressively unfreeze lowest-$p_i$ future tasks 1-by-1 only if infeasible ($\text{Stability} \ge 90\%$, [`local_repair.py`](../../smartschedule/core/solvers/local_repair.py)). |
| **`P9`** *(New)* | **Asymmetric Timetable & Midnight-Wraparound Social Jetlag** *(Smarr & Schirmer, 2018)* | Students with Mon/Wed/Fri classes study at `08:00` on free days vs `21:00` on class days (or `23:30–01:00` for Owls), causing `>3h` circadian phase whiplash. | Clock time is modular (`00:00 == 24:00`); stabilizing study rhythm across class vs. non-class days requires circular median distance on unit circle $S^1$. | Maintain incremental $(\sum \sin\theta_s, \sum \cos\theta_s)$ per day; bound circular median shift $|\Delta\phi_{\text{circ}}|$ between class & non-class days (`Advance <= 60m`, `Delay <= 180m`, [`ergonomic_engine.py`](../../smartschedule/core/solvers/ergonomic_engine.py)). |
| **`P10`** *(New)* | **Prerequisite Chain Bottlenecks (*Topological DAG Cascade*)** | If `Code A` and `Test B` (`A -> B`) both have deadline `Sun 23:59`, naive greedy places `A` at `Sun 22:00`, leaving `0` slots for `B`! | Nominal deadlines ignore downstream chain duration; parent tasks must inherit tightened effective deadlines from descendants before slot selection. | **3-Color DFS Cycle Guard + Backward Deadline Tightening:** $D^{\text{eff}}_u = \min\big(D_u, \min_{(u,v)\in E}(D^{\text{eff}}_v - d^{\text{plan}}_v)\big)$ + hard constraint $\max_k e_{u,k} \le \min_j s_{v,j}$ ($H_5$), wired to NL chat (*"xong A mới làm B"*, `M2`+`M4`). |
| **`P11`** *(New)* | **Non-Monotone Greedy Trap & Structural Overload ($\rho > 1$) No-Free-Lunch** | Across `220` benchmarks, greedy placed an early flexible task into an urgent atomic task's bottleneck (`R2` fail `16/20`), while $\rho > 1$ (`R5`) caused arbitrary drops. | Single-pass heuristics get trapped in local optima when $0.8 \le \rho \le 1.0$, and feasibility search is ill-posed when $\rho > 1.0$; regime detection must switch algorithms deterministically. | **Gate `G2` + Regime Escalation:** If $\rho \le 1$ has unplaced tasks, run **Kempe `1/2-eject` + `HYBRID_ALNS` (`5` Ruin ops + Regret-2 Insertion)** (`0/220 SUBOPT`); if $\rho > 1$, switch to **`OVERLOAD_PACK` value-density knapsack + `OverloadTriageEngine` 4 Pareto options** ([`hybrid_alns.py`](../../smartschedule/core/solvers/hybrid_alns.py)). |
| **`P12`** *(New)* | **Personal Bias Drift & Conversational Negation Polarity** | Fixed $\alpha$ ignores real completion history (while raw averages blow up on 1 outlier), and keyword parsers misread *"không làm buổi tối"* as `EVENING`! | Human adaptation requires outlier-clipped exponential smoothing with user consent (`LoA-4`), and natural language requires syntactic scope inversion before window matching. | **(a) Bounded LoA-4 EWMA:** $r_t=\text{clip}(A_t/E_t, 0.5, 2.5)$, $\alpha_t = 0.25 r_t + 0.75\alpha_{t-1} \in [1.0, 1.6]$ ($n \ge 5$, [`calibration.py`](../../smartschedule/core/calibration.py)); **(b) Negation Mask (`M2`+`M4`):** `không/tránh/né + W` $\implies \overline{W}$ complement mapping ([`free_context_engine.py`](../../smartschedule/nlp/free_context_engine.py)). |
| **`P13`** *(New)* | **Cross-Week Category Fallacy & Stated-vs-Revealed Chronotype Drift** *(Proposal §7.8.3–7.8.4)* | Students underestimate `CODING` (`×1.45`) far more than `READING` (`×1.05`), and often claim `"MORNING"` peak while actually skipping `07:30` blocks and finishing `20:00` blocks (`Revealed Preference != Stated Preference`). | With small weekly sample sizes ($n_c \in [1, 6]$), raw averages overfit while waiting for $n \ge 20$ wastes weeks; empirical Bayesian shrinkage + window adherence scoring adapts safely from Week $t \to t+1$. | **`CrossWeekPreferenceAdapter` (`M5`):** **(i) Shrinkage Category Buffer:** $\hat{\alpha}^{(t+1)}_{c,\ell} = \text{clip}\!\big(\frac{n_c}{n_c+\kappa}\text{EWMA}_c + \frac{\kappa}{n_c+\kappa}\alpha_0(\ell),\, 1.00,\, 1.60\big)$ ($\kappa=3$); **(ii) Revealed Window Shift:** $\text{Eff}(w) = \text{Adhere}(w)\cdot\text{clip}(\bar{E}/\bar{A}, 0.6, 1.2) \implies$ shift `focus_preference` / `hourly_levels` & `work_rhythm` (`FLOW -> BALANCED` after Crunch) + reserve recurring disruption slots (`cross_week_adapter.py`). |
| **`P14`** *(New)* | **Document-to-Constraint Abstraction & Cold-Start Longitudinal Gap** *(Proposal §7.8.2 & §9.7)* | Syllabi/PDFs hide implicit subtask DAGs & grade weights (causing `30m` user underestimates on `3h` specs), and a 1-semester project cannot ethically overload real students for 6+ weeks to verify `P13`. | Unstructured attachments must compile into quantitative constraint bounds before solving, and longitudinal adaptation requires a mathematically grounded **In-Silico Human Behavioral Twin** (`SimulatedStudent`). | **(a) `DocumentConstraintDigest` (`M7`+`M4`):** Parse `.pdf/.md/.txt` rubrics $\to$ weighted subtasks + `depends_on` + `USER_VS_DOC_UNDERESTIMATE` alert (`doc_attachment_parser.py`); **(b) `InSilicoStudentSimulator` (`M7`):** Closed-loop 4-week Monte Carlo test (`TMT + McFadden RUM + LogNormal + MCTQ + Fatigue`, `student_simulator.py`). |

---

## 5. Scientific Citations & Open-Source Reference Guide for Behavioral Simulation (`§9.7` Completed)

> [!TIP]
> **Resolving the Missing Citations & Source Code Question:** During the Proposal phase (`Proposal_Report.pdf §9.7`), the team introduced programmatic simulation of human behavior (`SimulatedStudent`) and noted recent high-accuracy behavioral simulation research without having the exact repositories and closed-loop math wired in. Below are the **exact peer-reviewed citations, open-source repositories, and why SmartSchedule's Mechanistic Agent is the optimal CT abstraction**:

### 5.1. Recent High-Accuracy Computational Human Behavior Simulation Papers & Official Code
1. **Stanford / Google DeepMind — Generative Human Behavior Simulation (`85%` Normalized Accuracy):**
   - **Citation:** Park, J. S., Zou, C. Q., Shaw, A., Hill, B. M., Cai, C., Morris, M. R., Willer, R., Liang, P., & Bernstein, M. S. (2024). *"Generative Agent Simulations of 1,000 People."* `arXiv:2411.10109` *(building on Park et al., UIST 2023, "Generative Agents: Interactive Simulacra of Human Behavior")*.
   - **Key Result:** Programmatic agents replicated real participants' behavioral choices and responses **85% as accurately** as humans replicated their own answers 2 weeks later.
   - **Official Open-Source Code:** https://github.com/StanfordHCI/genagents and https://github.com/joonspk-research/generative_agents
2. **Nature (2025) — Foundation Model of Human Cognition (`Psych-101`):**
   - **Citation:** Binz, M., Akata, E., Bethge, M., et al. (2025). *"Centaur: a foundation model of human cognition."* *Nature* (`arXiv:2410.20268`).
   - **Key Result:** Trained on `10.6 million` human choices from `60,092` participants across `160` psychological experiments, accurately predicting held-out trial-by-trial human decision behavior.
   - **Official Project & Open-Source Code:** https://marcelbinz.github.io/Centaur/ (Weights & scripts on Hugging Face `marcelbinz/Llama-3.1-Centaur-70B`)
3. **Classical Cognitive Architecture Baseline (`ACT-R`):**
   - **Citation:** Anderson, J. R., Bothell, D., Byrne, M. D., Douglass, S., Lebiere, C., & Qin, Y. (2004). *"An integrated theory of the mind."* *Psychological Review*, 111(4), 1036–1060. **Official Source Code:** http://act-r.psy.cmu.edu/

### 5.2. Exact 5-Equation Mechanistic Model in `smartschedule/core/student_simulator.py` (`M7`)
Why we do **not** call a 70B LLM at every 15-minute slot (`INV-5`: `<350 KB` heap, `0` GPU cost, `SHA-256` determinism), and instead formalize the 5 domain-specific psychometric laws from `Proposal_Report.pdf §9.7` (with the `Steel 2007` $\Gamma$-denominator bug fixed!):

1. **Latent Chronotype Peak (`Roenneberg et al., 2003, J. Biol. Rhythms — MCTQ`; `Smarr & Schirmer, 2018`):**
   True latent peak hour $H^*_{\text{peak}} \in [7.0, 23.0]$ (which may differ from the student's initial *self-reported* `focus_preference`, testing revealed-preference discovery!):
   $$\text{CircFit}(t) = \max\!\left(0,\; 1 - \frac{\min(|t - H^*_{\text{peak}}|,\; 24 - |t - H^*_{\text{peak}}|)}{8.0}\right)$$
2. **Category-Asymmetric Log-Normal Planning Fallacy (`Buehler, Griffin & Ross, 1994, JPSP`; `Kahneman & Tversky, 1979`):**
   $$d_{\text{actual}}(i) = 15 \cdot \left\lceil \frac{d_{\text{est}}(i) \cdot b_{\text{cat}}(c_i) \cdot \exp(\mathcal{N}(0, \sigma_\varepsilon^2))}{15} \right\rceil, \qquad b_{\text{cat}}(c_i) = \exp(\mu_{c_i}) \in [0.95, 1.85]$$
3. **Temporal Motivation Theory — TMT (`Steel, 2007, Psychological Bulletin, Eq. 3`):**
   With individual impulsiveness / procrastination trait $\Gamma \sim \text{Beta}(2, 5)$ (mean $\approx 0.29$) and slack $s_h$ hours to deadline:
   $$U_{\text{task}}(b) = \frac{\text{Expectancy}(\text{CircFit}(b), F_t) \cdot \text{Value}(p_i / 5)}{1 + \Gamma \cdot (s_h / 24.0)}$$
4. **Random Utility Discrete Adherence Choice (`McFadden, 1974, Conditional Logit RUM`):**
   At each scheduled block $b$, the student adheres ($y_b = 1$) vs. procrastinates/skips ($y_b = 0$) with logistic probability:
   $$P(y_b = 1) = \frac{1}{1 + \exp\!\big(-\beta \cdot (U_{\text{task}}(b) - U_{\text{distract}} - \gamma_F F_t)\big)}$$
5. **Ultradian Fatigue & Recovery Restoration (`Albulescu et al., 2022, PLOS ONE`; `Kleitman BRAC`):**
   Deep blocks ($\ell=3$) accumulate fatigue $F_{t^+} = \min(1, F_t + \lambda_F \cdot \text{hours})$; a contiguous $\ge 15\text{m}$ `REST` break restores $40\%$ of accumulated fatigue ($F \leftarrow 0.60 F$), while sleep $< 7\text{h}$ leaves residual morning fatigue.

---

## 6. High-Impact 3.5-Minute Final Demo Script (Showcasing Deep CT Thinking Live)

1. **Step 1 — Formal Sample Input $\to$ Output (`30s`):**
   - Load `MINH_FIT_HCMUS` Sample Preset: point out `MATH-1` (`120m -> 165m` split `90m + 30m break + 75m` in Morning Peak `E=3`) and DAG chain `PRJ-1, PRJ-2 -> PRJ-3` (`SHA-256: 9157054420ae`).
2. **Step 2 — Logical Attachment Processing + Prerequisite DAG + `Pattern -> Rule` Trace (`60s`):**
   - Toggle **`Developer Mode` ON**. Attach a sample assignment `.md`/`.pdf` (`Lab03_Spec.md`: 3 milestones, `180m` total) and type *"Làm xong bài Lab này trong 30 phút trước Thứ 6, tránh buổi tối"*.
   - Show SmartSchedule catching the **`USER_VS_DOC_UNDERESTIMATE` conflict** (`30m` vs `180m` spec), building the 3-step `depends_on` DAG (`P10`, `P14a`), masking `EVENING` (`P12b`), and displaying the live **`🔗 Pattern → Deterministic Logic Rule`** badges!
3. **Step 3 — Mid-Week Emergency Disruption $\to$ Minimum-Perturbation Local Repair (`30s`):**
   - Type *"Chiều thứ 4 từ 14h đến 16h họp CLB đột xuất"* $\to$ `LOCAL_INSERTION` (`P8`) keeps **`>= 95%`** of unaffected blocks untouched.
4. **Step 4 — Closed-Loop 4-Week Behavioral Adaptation via `InSilicoStudentSimulator` (`60s` — The Showstopper!):**
   - Trigger **Multi-Week Adaptation Simulation (`Week 1 -> Week 4`)**: show a simulated Night-Owl student who misreports `"MORNING"` and underestimates `CODING` by `×1.42`. Watch `CrossWeekPreferenceAdapter` (`P13` + `P14b`) automatically learn $\hat{\alpha}_{\text{CODING}}: 1.20 \to 1.40$, flip `MORNING -> EVENING` from revealed block adherence, reserve chronic disruption slots, and raise real execution completion from **Week 1 (`~62%`) $\to$ Week 4 (`~95%+`)** in `< 500 ms`!
