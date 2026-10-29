"""
Solvers Strategy Package for SmartSchedule Baseline (V0).
Provides:
  - GreedyEDFSolver (3A: Earliest Deadline First + First-Fit - Default V0 Baseline B)
  - GreedyLSTSolver (3B: Least Slack Time + Best-Fit - Comparison Engine)
  - GreedyWSPTSolver (3C: Weighted Shortest Processing Time / Smith's Rule)
  - BacktrackingSolver (2: Branch-and-Bound Exact Ground-Truth Validator for N <= 8)
  - LocalRepairEngine (M4: Local Insertion vs Full Rebuild vs Ripple-Shift)
"""

