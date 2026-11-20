"""
Shared solver registry and lookup helpers for the Scheduling Domain layer.
Allows ScheduleController and LocalRepairEngine to resolve algorithms identically
without circular imports.
"""

from typing import Dict, Optional, Type

from src.solvers.backtracking import BacktrackingSolver
from src.solvers.base_solver import BaseScheduler
from src.solvers.greedy_edf import GreedyEDFSolver
from src.solvers.greedy_lst import GreedyLSTSolver
from src.solvers.greedy_wspt import GreedyWSPTSolver
from src.solvers.scored_greedy import ScoredGreedySolver

from src.solvers.hybrid_alns import HybridALNSSolver

SOLVER_REGISTRY: Dict[str, Type[BaseScheduler]] = {
    "EDF": GreedyEDFSolver,
    "GREEDY_EDF": GreedyEDFSolver,
    "GREEDY_EDF_FIRST_FIT": GreedyEDFSolver,
    "SCORED_GREEDY": ScoredGreedySolver,
    "URGENCY": ScoredGreedySolver,
    "LST": GreedyLSTSolver,
    "GREEDY_LST": GreedyLSTSolver,
    "GREEDY_LST_BEST_FIT": GreedyLSTSolver,
    "WSPT": GreedyWSPTSolver,
    "GREEDY_WSPT": GreedyWSPTSolver,
    "GREEDY_WSPT_SMITH_RULE": GreedyWSPTSolver,
    "BACKTRACK": BacktrackingSolver,
    "BACKTRACKING": BacktrackingSolver,
    "BACKTRACKING_BRANCH_AND_BOUND": BacktrackingSolver,
    "HYBRID_ALNS": HybridALNSSolver,
    "ALNS": HybridALNSSolver,
    "ULTIMATE": HybridALNSSolver,
}


def resolve_solver(algorithm: Optional[str] = "EDF") -> BaseScheduler:
    """Instantiate the solver class matching `algorithm`, defaulting to GreedyEDFSolver."""
    key = (algorithm or "EDF").strip().upper()
    solver_cls = SOLVER_REGISTRY.get(key, GreedyEDFSolver)
    return solver_cls()
