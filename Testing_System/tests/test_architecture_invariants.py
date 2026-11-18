"""Architectural Invariant Verification (INV-1..INV-6): Domain Purity, Immutability, & Thread-Safety."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import subprocess
import sys

from schedule_testing_system.evaluator import ScheduleEvaluator
from schedule_testing_system.generator import InputGenerator
from schedule_testing_system.schemas import RegimeName
from schedule_testing_system.sut_adapter import run_solver_direct


def test_inv1_domain_evaluator_has_no_web_imports():
    """Verify importing the domain evaluator never pulls FastAPI, Starlette, httpx, or web.api."""
    code = (
        "import sys; "
        "from schedule_testing_system.evaluator import ScheduleEvaluator, build_contrast_pairs; "
        "bad = [m for m in sys.modules if any(k in m for k in ('fastapi', 'starlette', 'uvicorn', 'web.api'))]; "
        "assert not bad, f'Domain evaluator imported web modules: {bad}'"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_inv3_inv4_evaluate_never_mutates_inputs():
    bundle = InputGenerator.generate(RegimeName.DISRUPTION_AND_OVERRUN_SERIES, seed=42)
    out, _ = run_solver_direct(bundle.profile, bundle.tasks, "SCORED_GREEDY", bundle.pinned_blocks)

    prof_before = bundle.profile.model_dump()
    tasks_before = [t.model_dump() for t in bundle.tasks]
    pins_before = [p.model_dump() for p in bundle.pinned_blocks]
    out_before = out.model_dump()

    _ = ScheduleEvaluator.evaluate(
        profile=bundle.profile,
        tasks=bundle.tasks,
        schedule=out,
        input_pinned_blocks=bundle.pinned_blocks,
    )

    assert bundle.profile.model_dump() == prof_before
    assert [t.model_dump() for t in bundle.tasks] == tasks_before
    assert [p.model_dump() for p in bundle.pinned_blocks] == pins_before
    assert out.model_dump() == out_before


def test_inv6_concurrent_evaluation_is_thread_safe_and_deterministic():
    bundle = InputGenerator.generate(RegimeName.CIRCADIAN_SJL_AND_RECOVERY, seed=42)
    out, _ = run_solver_direct(bundle.profile, bundle.tasks, "SCORED_GREEDY", bundle.pinned_blocks)

    def _run_one(_):
        return ScheduleEvaluator.evaluate(bundle.profile, bundle.tasks, out).model_dump()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_run_one, range(8)))

    first = results[0]
    for r in results[1:]:
        assert r == first

