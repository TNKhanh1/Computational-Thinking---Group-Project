"""
Centralized Configurable Constants, Behavioral Parameters & Workspace Paths (Pure Layer 1).
All open parameters and repository path resolvers are isolated here so modules never hardcode `parents[N]`.
"""

import os
from pathlib import Path

# Centralized Workspace Directory Resolution (INV-1 Pure Stdlib)
CORE_DIR: Path = Path(__file__).resolve().parent
SMARTSCHEDULE_DIR: Path = CORE_DIR.parent
REPO_ROOT: Path = SMARTSCHEDULE_DIR.parent
ENVIRONMENTS_DIR: Path = REPO_ROOT / "environments"
UI_DIR: Path = SMARTSCHEDULE_DIR / "ui"
NLP_DIR: Path = SMARTSCHEDULE_DIR / "nlp"
TESTS_DIR: Path = REPO_ROOT / "tests"
TOOLS_DIR: Path = REPO_ROOT / "tools"
PLAN_ROOT: Path = REPO_ROOT / "v1.0-alpha-plan"
TESTING_SYSTEM_DIR: Path = PLAN_ROOT / "Testing_System"

DATA_DIR: Path = Path(os.environ.get("SMARTSCHEDULE_DATA_DIR") or (REPO_ROOT / "data"))
PRESETS_DIR: Path = DATA_DIR / "presets"
SCENARIOS_DIR: Path = DATA_DIR / "scenarios"
CALIBRATION_DIR: Path = DATA_DIR / "calibration"
RUNTIME_DATA_DIR: Path = DATA_DIR / "runtime"
DEFAULT_DB_PATH: Path = RUNTIME_DATA_DIR / "local_state.db"

# Pattern 1: Planning Fallacy Duration Buffer (Presentation2.pdf Slide 7 & Slide 17)
ALPHA_LIGHT_DEFAULT: float = 1.20  # cognitive_load in {1, 2}
ALPHA_HEAVY_DEFAULT: float = 1.35  # cognitive_load == 3
ALPHA_GRID_MIN: float = 1.00
ALPHA_GRID_MAX: float = 1.60
ALPHA_GRID_STEP: float = 0.05

# Pattern 2: Cognitive Fatigue & Mandatory Rest
MAX_DEEP_WORK_MIN: int = 90
MIN_DEEP_WORK_BREAK_TRIGGER_MIN: int = 90  # >= 90m or cognitive_load == 3 triggers 15m rest break
MANDATORY_REST_SLOTS: int = 1  # 15 minutes

# Pattern 4: Context Switching & Category Batching
CATEGORY_BATCH_BONUS: float = 0.35
CONTEXT_SWITCH_PENALTY: float = 0.25

# Pattern 5: Dead-Zones (< 30 minutes)
DEAD_ZONE_MAX_SLOTS: int = 1  # Gaps < 2 slots (< 30 min) -> STATE_REST

# Pattern 6: Biological Sleep Recovery
MIN_SLEEP_HOURS: int = 6
MIN_SLEEP_SLOTS: int = 24  # 6h * 4 slots/h

# Pattern 7: Procrastination & Hyperbolic Urgency (Presentation2.pdf Slide 8)
GAMMA_URGENCY_HOURS: float = 24.0
OVERDUE_URGENCY_CAP: float = 1.50
HABIT_BASE_URGENCY: float = 0.20

# Pattern 8: Schedule Stability Target (Presentation2.pdf Slide 5 & Slide 8)
STABILITY_TARGET_PCT: float = 90.0

# Backtracking Optimization Limits (Slide 15 < 2s latency bound)
BACKTRACK_MAX_CANDIDATES_PER_TASK: int = 12
BACKTRACK_MAX_NODES: int = 3000
BACKTRACK_TIME_BUDGET_SEC: float = 0.55

# Step 5: Early Extension Alert horizon (hours before deadline)
EARLY_EXTENSION_ALERT_MIN_HOURS: float = 0.0
EARLY_EXTENSION_ALERT_MAX_HOURS: float = 48.0

# Ergonomic Engine Guardrails (aligned with Student Ergonomics & Testing_System v2.1)
ERGONOMIC_DAILY_HEAVY_CAP: int = 2                # max load==3 blocks per day
ERGONOMIC_DAILY_TOTAL_SOFT_SLOTS: int = 36        # 540 min (study + class)
ERGONOMIC_DAILY_TOTAL_HARD_SLOTS: int = 40        # 600 min (study + class)
ERGONOMIC_L2_STREAK_SOFT_SLOTS: int = 8           # 120 min contiguous load>=2 chain
ERGONOMIC_L2_STREAK_HARD_SLOTS: int = 12          # 180 min contiguous load>=2 chain
ERGONOMIC_HEAVY_MIN_GAP_SLOTS: int = 2            # >= 30 min separation between load==3 blocks
ERGONOMIC_CRAM_WINDOW_SLOTS: int = 40             # last 10h before deadline
ERGONOMIC_DAILY_STD_BASE_TOL_MIN: float = 45.0    # base_class_std + 45 tolerance
ERGONOMIC_DAILY_STD_FLOOR_MIN: float = 180.0      # floor for daily std warning threshold

# Hybrid ALNS & Greedy Polish Budgets (iteration-first determinism; time is safety guard only)
GREEDY_POLISH_MAX_PASSES: int = 2
GREEDY_TIME_BUDGET_SEC: float = 0.35
ALNS_MAX_ITERS: int = 80
ALNS_POLISH_MAX_PASSES: int = 3
ALNS_TIME_BUDGET_SEC: float = 0.65


