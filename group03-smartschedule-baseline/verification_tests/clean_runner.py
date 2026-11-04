"""
Interpretable Console Test Runner for SmartSchedule
Author: Nguyen Nguyen Gia Bao (Builder 3 - System Architecture & Testing)

Formats test outputs into an interpretable log format:
  1. Running Signal: Clear notification of engine activity & target
  2. Running Phase: Grouped by functional directory / layer
  3. Files (and directories): PASSED or FAILED
     - If failed: Directly summarizes and points to the specific issue (discrepancy, gap, exception)
  4. Final Summary: Clear, uncluttered outcome statistics
"""

import argparse
from collections import defaultdict
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent
VERIFICATION_DIR = BASE_DIR / "verification_tests"

PHASE_TITLES = {
    "ui_tests": "UI & Frontend Contract Tests",
    "architecture_tests": "System Architecture & Invariant Tests",
    "logical_tests": "Logical, Math & Defensive Edge Case Tests",
    "benchmark_tests": "Baseline Scenarios T01–T10 & Feasibility Benchmarks",
    "development_gap_tests": "Improve Plan Target Feature Gaps (Expected Failures)",
}


class InterpretableConsolePlugin:
    """Pytest plugin that intercepts test outcomes and renders clean, human-readable logs."""

    def __init__(self, target_label: str = "All Tests"):
        self.target_label = target_label
        self.start_time = 0.0
        self.total_tests = 0
        self.passed_count = 0
        self.failed_count = 0
        self.skipped_count = 0

        # Grouping: phase_dir -> file_name -> list of test outcomes
        # Each outcome is dict(name=str, outcome=str, issue=str, diff=str)
        self.results: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))

    def pytest_sessionstart(self, session):
        self.start_time = time.perf_counter()
        print("=" * 72)
        print("[RUNNING] Verification Test Engine Active...")
        print(f"Target:   {self.target_label}")
        print(f"Time:     {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 72)
        print()

    def pytest_runtest_logreport(self, report):
        if report.when != "call" and not (report.when == "setup" and report.failed):
            return

        self.total_tests += 1
        node_parts = report.nodeid.split("::")
        file_path_str = node_parts[0].replace("\\", "/")
        test_func_name = node_parts[-1]

        # Determine phase directory and relative file name
        path_obj = Path(file_path_str)
        phase_dir = path_obj.parent.name if path_obj.parent.name in PHASE_TITLES else "tests"
        file_name = path_obj.name

        outcome_info = {
            "name": test_func_name,
            "outcome": report.outcome,
            "duration": report.duration,
            "issue": "",
            "discrepancy": "",
        }

        if report.passed:
            self.passed_count += 1
        elif report.failed:
            self.failed_count += 1
            issue_msg, diff_msg = self._extract_clean_issue(report)
            outcome_info["issue"] = issue_msg
            outcome_info["discrepancy"] = diff_msg
        elif report.skipped:
            self.skipped_count += 1

        self.results[phase_dir][file_name].append(outcome_info)

    def _extract_clean_issue(self, report) -> tuple[str, str]:
        """Extract a human-readable summary of the failure, stripping pytest internal noise."""
        raw_repr = str(report.longrepr or "")
        lines = [line.strip() for line in raw_repr.splitlines() if line.strip()]

        issue_summary = "Test assertion failed."
        discrepancy = ""

        # First pass: find explicit failure reasons or assertion text
        for line in lines:
            if "AssertionError:" in line:
                issue_summary = line.split("AssertionError:", 1)[1].strip()
                break
            elif line.startswith("E   ") and not line.startswith("E   assert"):
                candidate = line[4:].strip()
                if "Error:" in candidate or "Exception:" in candidate:
                    issue_summary = candidate
                    break
                elif not issue_summary or issue_summary == "Test assertion failed.":
                    issue_summary = candidate

        # Second pass: find the evaluated comparison discrepancy.
        # Pytest prefixes the evaluated failure expression with "E   assert "
        # We search from bottom up to get the exact evaluated comparison line.
        for line in reversed(lines):
            if re.match(r"^E\s+assert\s+", line):
                clean_assert = re.sub(r"^E\s+", "", line).strip()
                discrepancy = f"Discrepancy: {clean_assert}"
                break
            elif re.match(r"^E\s+where\s+", line) or re.match(r"^E\s+values:\s+", line):
                clean_where = re.sub(r"^E\s+", "", line).strip()
                if not discrepancy:
                    discrepancy = f"Discrepancy: {clean_where}"

        return issue_summary, discrepancy

    def pytest_sessionfinish(self, session, exitstatus):
        elapsed = time.perf_counter() - self.start_time

        # Render Phases and Files
        phase_keys = [k for k in PHASE_TITLES.keys() if k in self.results]
        # Include any custom phases
        for k in self.results.keys():
            if k not in phase_keys:
                phase_keys.append(k)

        total_phases = len(phase_keys)

        for idx, phase_key in enumerate(phase_keys, 1):
            phase_name = PHASE_TITLES.get(phase_key, phase_key.replace("_", " ").title())
            print(f"[PHASE {idx}/{total_phases}] {phase_name} (verification_tests/{phase_key})")

            files_map = self.results[phase_key]
            for file_name, tests_list in sorted(files_map.items()):
                file_failed = any(t["outcome"] == "failed" for t in tests_list)
                file_passed_count = sum(1 for t in tests_list if t["outcome"] == "passed")
                file_total_count = len(tests_list)

                dots = "." * max(2, 54 - len(file_name))

                if file_failed:
                    file_fail_count = sum(1 for t in tests_list if t["outcome"] == "failed")
                    print(f"  [FILE] {file_name} {dots} FAILED ({file_passed_count} passed, {file_fail_count} failed)")
                    # Print issues for failed tests in this file
                    for t in tests_list:
                        if t["outcome"] == "failed":
                            print(f"    -> [ISSUE] {t['name']}")
                            print(f"       Point to: {t['issue']}")
                            if t["discrepancy"]:
                                print(f"       Details:  {t['discrepancy']}")
                else:
                    print(f"  [FILE] {file_name} {dots} PASSED ({file_passed_count}/{file_total_count} tests)")

            print()

        # Render Final Summary
        print("=" * 72)
        status_label = "ALL PASSED" if self.failed_count == 0 else f"{self.failed_count} ISSUES/GAPS DETECTED"
        print(f"[FINAL SUMMARY] {self.passed_count} Passed | {self.failed_count} Failed | Total: {self.total_tests} Tests")
        print(f"Execution Time: {elapsed:.2f}s | Status: {status_label}")
        print("=" * 72)


def run_tests(args_list: List[str], target_label: str = "Verification Suite") -> int:
    """Run pytest with the InterpretableConsolePlugin."""
    # Ensure stdout handles UTF-8 cleanly on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    plugin = InterpretableConsolePlugin(target_label=target_label)
    # Disable pytest's built-in terminal plugin to eliminate raw dots/summaries
    pytest_args = [
        "-p", "no:terminal",
    ] + args_list

    return pytest.main(pytest_args, plugins=[plugin])


def main():
    parser = argparse.ArgumentParser(description="Interpretable Console Test Runner")
    parser.add_argument("--all", action="store_true", help="Run full 60/40 test matrix (including development gaps)")
    parser.add_argument("--pass", dest="pass_only", action="store_true", help="Run only passing operational tests")
    parser.add_argument("--edge", action="store_true", help="Run 40%% edge case and failure tests")
    parser.add_argument("--gaps", action="store_true", help="Run Improve Plan development gap failure tests")
    parser.add_argument("--ui", action="store_true", help="Run UI & contract tests")
    parser.add_argument("--arch", action="store_true", help="Run Architecture & invariant tests")
    parser.add_argument("--logic", action="store_true", help="Run Logical & boundary tests")
    parser.add_argument("--bench", action="store_true", help="Run Benchmark & feasibility tests")
    parser.add_argument("--target", type=str, default="", help="Run a specific test file or directory")

    parsed, unknown = parser.parse_known_args()

    os.chdir(str(BASE_DIR))

    if parsed.target:
        target_path = Path(parsed.target)
        label = f"Target: {target_path.name}"
        exit_code = run_tests([str(target_path)], target_label=label)
    elif parsed.gaps:
        label = "Improve Plan Target Feature Gaps"
        exit_code = run_tests(["verification_tests/development_gap_tests"], target_label=label)
    elif parsed.edge:
        label = "40% Edge Cases & Production Failure Scenarios"
        exit_code = run_tests([
            "verification_tests/logical_tests/test_scheduling_edge_cases.py",
            "verification_tests/architecture_tests/test_production_failures.py",
            "verification_tests/benchmark_tests/test_feasibility_benchmarks.py",
        ], target_label=label)
    elif parsed.ui:
        label = "UI & Delivery Tests"
        exit_code = run_tests(["verification_tests/ui_tests"], target_label=label)
    elif parsed.arch:
        label = "System Architecture Tests"
        exit_code = run_tests(["verification_tests/architecture_tests"], target_label=label)
    elif parsed.logic:
        label = "Logical Tests"
        exit_code = run_tests(["verification_tests/logical_tests"], target_label=label)
    elif parsed.bench:
        label = "Benchmark Scenarios T01–T10 & Feasibility"
        exit_code = run_tests(["verification_tests/benchmark_tests"], target_label=label)
    elif parsed.pass_only:
        label = "Operational Verification Suite (Passing Baseline Tests)"
        exit_code = run_tests([
            "-k", "not test_fail",
            "verification_tests/ui_tests",
            "verification_tests/architecture_tests",
            "verification_tests/logical_tests",
            "verification_tests/benchmark_tests",
        ], target_label=label)
    elif parsed.all:
        label = "Full 60/40 Matrix (All Verification Tests)"
        exit_code = run_tests(["verification_tests"], target_label=label)
    else:
        # Default: run all operational tests (UI, Arch, Logic, Benchmarks)
        label = "Operational Verification Suite (Passing Baseline Tests)"
        exit_code = run_tests([
            "-k", "not test_fail",
            "verification_tests/ui_tests",
            "verification_tests/architecture_tests",
            "verification_tests/logical_tests",
            "verification_tests/benchmark_tests",
        ], target_label=label)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
