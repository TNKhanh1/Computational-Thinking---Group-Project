# Feature 001 — Design Diagrams (Mermaid)

## 1. Activity diagram — computing the planned duration

```mermaid
flowchart TD
    A([Task with estimate E minutes]) --> B{Profile has estimate_habit?}
    B -- No --> R0[Multiplier m = 1.00]
    B -- RARELY --> R0
    B -- SOMETIMES --> R1[m = 1.10]
    B -- OFTEN --> R2[m = 1.25]
    R0 --> F[Floor = round_up_to_15 E]
    R1 --> C
    R2 --> C
    C[Buffered = E × m] --> N[Nearest = round Buffered to nearest 15 min, half up]
    N --> M{Nearest > Floor?}
    F --> P0([Planned = Floor — V0 behaviour])
    M -- No --> P1([Planned = Floor — buffer absorbed by grid slack, no extra slot])
    M -- Yes --> P2([Planned = Nearest, add reason ESTIMATE_BUFFER])
```

Worked values for OFTEN (×1.25):

| Estimate | ×1.25 | Naive round-up | **This rule** | V0 |
|---:|---:|---:|---:|---:|
| 5 | 6.25 | 15 | **15** | 15 |
| 10 | 12.5 | 15 | **15** | 15 |
| 15 | 18.75 | 30 | **15** | 15 |
| 25 | 31.25 | 45 | **30** | 30 |
| 45 | 56.25 | 60 | **60** | 45 |
| 60 | 75 | 75 | **75** | 60 |
| 90 | 112.5 | 120 | **120** | 90 |

## 2. Sequence diagram — planning a week with the buffer

```mermaid
sequenceDiagram
    actor S as Student
    participant UI as Workbench (app.js)
    participant API as FastAPI (web/api.py)
    participant C as ScheduleController
    participant EB as estimate_buffer.py
    participant SV as Solver (EDF / LST / WSPT / BT)

    S->>UI: Choose "Thói quen ước lượng = OFTEN"
    UI->>UI: Preview "planned 75 min" under the 60-min estimate
    S->>UI: Click Solve
    UI->>API: POST /api/plan {commitments.estimate_habit, tasks}
    API->>C: apply_estimate_buffer(profile, tasks)
    C->>EB: multiplier_for_habit("OFTEN")
    EB-->>C: 1.25
    C-->>API: task copies with buffer_multiplier = 1.25
    API->>C: solve_schedule(profile, buffered tasks)
    C->>SV: solve(...)
    SV->>EB: (via Task.get_planned_duration_min) planned_duration_min(60, 1.25)
    EB-->>SV: 75
    SV-->>C: ScheduleOutput (blocks of 75 min)
    C->>C: annotate blocks with ESTIMATE_BUFFER reason
    C-->>API: ScheduleOutput
    API-->>UI: JSON blocks + reasons
    UI-->>S: Grid + table "60p → 75p (×1.25)"
```

## 3. Component diagram — what changed (and what did not)

```mermaid
flowchart LR
    subgraph L4[Layer 4 — Web]
        UI[web/index.html + app.js<br/>habit selector, preview, column]:::changed
        API[web/api.py<br/>parse habit, new_estimate_min]:::changed
    end
    subgraph L3[Layer 3 — Orchestration]
        CTRL[src/controller.py<br/>apply_estimate_buffer, annotate]:::changed
    end
    subgraph L2[Layer 2 — Solvers]
        SOLV[src/solvers/*<br/>UNCHANGED]:::same
    end
    subgraph L1[Layer 1 — Models]
        MOD[src/models.py<br/>estimate_habit, buffer_multiplier]:::changed
        EB[src/estimate_buffer.py<br/>pure functions]:::new
    end
    UI --> API --> CTRL --> SOLV --> MOD --> EB
    CTRL --> EB
    classDef new fill:#d1fae5,stroke:#059669
    classDef changed fill:#fef3c7,stroke:#d97706
    classDef same fill:#f1f5f9,stroke:#94a3b8
```
