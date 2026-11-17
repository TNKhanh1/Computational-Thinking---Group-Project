"""
Centralized Configurable Constants & Behavioral Parameters (Pure Layer 1).
All open parameters flagged in `Proposal/Open_Decisions_For_Team.md` are isolated here
so the team can adjust defaults without modifying solver or grid logic.
"""

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

# Step 5: Early Extension Alert horizon (hours before deadline)
EARLY_EXTENSION_ALERT_MIN_HOURS: float = 0.0
EARLY_EXTENSION_ALERT_MAX_HOURS: float = 48.0

