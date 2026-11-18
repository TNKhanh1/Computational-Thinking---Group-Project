"""
Command-Line Runner for the Schedule Testing System (`Gen Input -> Run Project -> Evaluate Output`).

Examples (run from workspace root with baseline venv):
  python -m Testing_System.cli --mode contrast
  python -m Testing_System.cli --mode full --seeds 42 101 --out Testing_System/reports/latest.json
  python -m Testing_System.cli --mode http --seeds 42
"""

from __future__ import annotations

import argparse
import sys

from Testing_System.evaluator import build_contrast_pairs
from Testing_System.runner import (
    format_vietnamese_summary,
    run_full_benchmark_suite,
    run_single_regime_case,
)
from Testing_System.schemas import RegimeName


def main() -> int:
    parser = argparse.ArgumentParser(description="Schedule 2-Part Testing & Productivity Evaluation CLI")
    parser.add_argument(
        "--mode",
        choices=["contrast", "regime", "full", "http"],
        default="full",
        help="contrast (evaluator self-test) | regime (one regime) | full (all 6 direct) | http (HTTP API E2E)",
    )
    parser.add_argument("--regime", type=int, choices=[1, 2, 3, 4, 5, 6], default=1, help="Regime index 1..6")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42], help="Deterministic seed list")
    parser.add_argument("--out", type=str, default=None, help="Optional output JSON report path")
    args = parser.parse_args()

    if args.mode == "contrast":
        res = build_contrast_pairs()
        print(f"=== CONTRAST PAIRS SELF-TEST: {'PASS' if res.passed else 'FAIL'} ===")
        for chk in res.assertions:
            print(f"  [{'PASS' if chk.passed else 'FAIL'}] {chk.name} :: {chk.detail}")
        return 0 if res.passed else 1

    if args.mode == "regime":
        reg_enum = list(RegimeName)[args.regime - 1]
        ok = True
        for s in args.seeds:
            r = run_single_regime_case(regime=reg_enum, seed=s, use_http_e2e=False)
            print(format_vietnamese_summary(r))
            print()
            ok = ok and r.all_invariants_passed
        return 0 if ok else 1

    use_http = args.mode == "http"
    summary = run_full_benchmark_suite(seeds=args.seeds, use_http_e2e=use_http, output_json_path=args.out)

    contrast = summary["contrast_pairs"]
    print(f"=== [SELF-TEST] Contrast Pairs (Gombolay §5.3): {'PASS' if contrast['passed'] else 'FAIL'} ===")
    for chk in contrast["assertions"]:
        print(f"  [{'PASS' if chk['passed'] else 'FAIL'}] {chk['name']}")
    print()

    from Testing_System.schemas import RegimeRunResult

    for raw_run in summary["regime_runs"]:
        rr = RegimeRunResult.model_validate(raw_run)
        print(format_vietnamese_summary(rr))
        print("-" * 92)

    print(f"\nOVERALL SUITE RESULT: {'ALL PASS' if summary['overall_passed'] else 'FAILED'}")
    return 0 if summary["overall_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

