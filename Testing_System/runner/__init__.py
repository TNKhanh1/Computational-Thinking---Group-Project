"""End-to-End Pipeline Runner Package (`Gen Input -> Run Project -> Evaluate Output`)."""

from Testing_System.runner.pipeline_runner import (
    format_vietnamese_summary,
    run_full_benchmark_suite,
    run_single_regime_case,
)
from Testing_System.runner.project_runner import (
    execute_project_direct,
    execute_project_http_e2e,
)

__all__ = [
    "execute_project_direct",
    "execute_project_http_e2e",
    "format_vietnamese_summary",
    "run_full_benchmark_suite",
    "run_single_regime_case",
]

