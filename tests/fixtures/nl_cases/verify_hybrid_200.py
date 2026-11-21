"""
verify_hybrid_200.py
Ultimate 200-Case Content Parsing Verification Suite for the Unified Hybrid NL Parser.

Executes `hybrid_parser.parse_hybrid_case()` across all 200 YAML test cases in `test_cases/*.yaml`
with exact category proportions:
  - A  ( 5%):  10 cases (Fully Expressed EN & VI Workflows)
  - B  (60%): 120 cases (General Natural Speech with Missing/Uncertain Info: B1=60, B2=60)
  - C1 (10%):  20 cases (Contradictions: Duration, Temporal, DAG Cycle, Session, Semantic, Feasibility)
  - C2 (15%):  30 cases (Insufficient Specifics: Dangling Pronouns, Generic Scope, Non-Actionable)
  - C3 ( 5%):  10 cases (Trolling, Nonsense, Past Narrative Chatter & Adversarial Injection)
  - D  ( 5%):  10 cases (Overloaded Tasks Requiring Breakdown Recommendations)

Verifies parsed content against expected contract fields:
  - status (`OK`, `OK_WITH_WARNINGS`, `NEEDS_FIX`, `REJECTED`)
  - errors (`E_*` diagnostic codes)
  - total_work_minutes & work_minutes_lower_bound
  - deadline & start_after
  - priority (User 1=Urgent..4=Low & Solver 5=Highest..1=Lowest adapter)
  - is_task_splittable & breakdown_required
"""

from __future__ import annotations

import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[2]
for _p in (str(REPO_ROOT), str(THIS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from smartschedule.nlp.hybrid_pipeline.hybrid_parser import parse_hybrid_case
from validate_cases import BASE_TIME, FILES


def verify_single_case(case: Dict[str, Any], backend: str = "rule") -> Tuple[bool, List[str], Dict[str, Any]]:
    inp = case["input"]
    exp = case["expected"]
    got = parse_hybrid_case(
        inp["prompt"],
        inp.get("ui"),
        base_time=BASE_TIME,
        enable_translation=True,
        translation_backend=backend,
    )

    mismatches: List[str] = []

    if got["status"] != exp["status"]:
        mismatches.append(f"status: exp={exp['status']} got={got['status']} (errs={got['errors']}, warns={got['warnings']})")

    exp_errs = set(exp.get("errors") or [])
    got_errs = set(got.get("errors") or [])
    if got_errs != exp_errs:
        mismatches.append(f"errors: exp={sorted(exp_errs)} got={sorted(got_errs)}")

    if "contract" in exp and exp["contract"] is None:
        return (len(mismatches) == 0), mismatches, got

    if got["total_work_minutes"] != exp.get("total_work_minutes"):
        mismatches.append(f"total_work_minutes: exp={exp.get('total_work_minutes')} got={got['total_work_minutes']}")

    if got.get("work_minutes_lower_bound") != exp.get("work_minutes_lower_bound"):
        mismatches.append(f"work_minutes_lower_bound: exp={exp.get('work_minutes_lower_bound')} got={got.get('work_minutes_lower_bound')}")

    if got.get("start_after") != exp.get("start_after"):
        mismatches.append(f"start_after: exp={exp.get('start_after')} got={got.get('start_after')}")

    if got["deadline"] != exp.get("deadline"):
        mismatches.append(f"deadline: exp={exp.get('deadline')} got={got['deadline']}")

    if got["priority"] != exp.get("priority"):
        mismatches.append(f"priority: exp={exp.get('priority')} got={got['priority']}")

    if "priority_uncertain" in exp and got.get("priority_uncertain") != exp.get("priority_uncertain"):
        mismatches.append(f"priority_uncertain: exp={exp.get('priority_uncertain')} got={got.get('priority_uncertain')}")

    if got["is_task_splittable"] != exp.get("is_task_splittable"):
        mismatches.append(f"is_task_splittable: exp={exp.get('is_task_splittable')} got={got['is_task_splittable']}")

    if exp.get("splitting") is not None and got.get("splitting") != exp.get("splitting"):
        mismatches.append(f"splitting: exp={exp.get('splitting')} got={got.get('splitting')}")

    exp_warns = set(exp.get("warnings") or [])
    got_warns = set(got.get("warnings") or [])
    if got_warns != exp_warns:
        mismatches.append(f"warnings: exp={sorted(exp_warns)} got={sorted(got_warns)}")

    if bool(got["breakdown_required"]) != bool(exp.get("breakdown_required")):
        mismatches.append(f"breakdown_required: exp={bool(exp.get('breakdown_required'))} got={bool(got['breakdown_required'])}")

    return (len(mismatches) == 0), mismatches, got


def run_200_verification(backend: str = "rule", verbose_failures: bool = True) -> Tuple[int, int, Dict[str, Tuple[int, int]]]:
    passed = 0
    total = 0
    cat_stats: Dict[str, List[int]] = {}
    failures: List[Tuple[str, str, List[str]]] = []

    t0 = time.perf_counter()
    for fname, (cat, _) in FILES.items():
        data = yaml.safe_load((THIS_DIR / fname).read_text(encoding="utf-8"))
        cat_stats.setdefault(cat, [0, 0])
        for case in data["cases"]:
            total += 1
            cat_stats[cat][1] += 1
            ok, diffs, _ = verify_single_case(case, backend=backend)
            if ok:
                passed += 1
                cat_stats[cat][0] += 1
            else:
                failures.append((case["id"], cat, diffs))
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    print("=" * 82)
    print(f"HYBRID NL PARSER — 200-CASE CONTENT VERIFICATION SUITE (backend={backend})")
    print("=" * 82)
    for cat in ("A", "B", "C1", "C2", "C3", "D"):
        p_cnt, t_cnt = cat_stats.get(cat, [0, 0])
        pct = (p_cnt / t_cnt * 100.0) if t_cnt else 0.0
        share = (t_cnt / total * 100.0) if total else 0.0
        print(f"  Category {cat:<2} ({share:4.1f}% of suite): {p_cnt:3d}/{t_cnt:3d} passed ({pct:5.1f}%)")
    print("-" * 82)
    print(f"  TOTAL PASS RATE: {passed}/{total} ({passed/total*100.0:.1f}%) | Total Time: {elapsed_ms:.1f} ms ({elapsed_ms/max(1,total):.2f} ms/case)")
    print("=" * 82)

    if failures and verbose_failures:
        print(f"\nFailures ({len(failures)}):")
        for cid, cat, diffs in failures:
            print(f"  [{cid}] ({cat}): " + " | ".join(diffs))

    return passed, total, {k: (v[0], v[1]) for k, v in cat_stats.items()}


if __name__ == "__main__":
    p, t, _ = run_200_verification()
    sys.exit(0 if p == t else 1)
