"""
validate_cases.py
Structural + consistency checker for the NLP parser evaluation dataset.

Checks:
  * schema / enums / unique ids / known diagnostic codes
  * status <-> errors/warnings consistency
  * single session => splitting null
  * subtask sums vs total_work_minutes (remaining work only)
  * dependency references exist and graph is acyclic (unless E_CYCLIC_DEPENDENCY)
  * attachments: size <= 20MB and allowed types (unless the matching error is expected)
  * prompt length > 500 <=> E_PROMPT_TOO_LONG
  * breakdown_required <=> W_BREAKDOWN_RECOMMENDED
  * feasibility rule (W_TIGHT_SCHEDULE / E_INFEASIBLE_WORKLOAD)
  * category distribution & domain coverage report

Usage:  python test_cases/validate_cases.py
"""

from __future__ import annotations

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

BASE_TIME = datetime(2026, 11, 6, 9, 0)
ROOT = Path(__file__).parent

FILES = {
    "A_fully_expressed.yaml": ("A", 0.05),
    "B1_general_missing_info.yaml": ("B", 0.30),
    "B2_general_missing_info.yaml": ("B", 0.30),
    "C1_contradictions.yaml": ("C1", 0.10),
    "C2_insufficient_specifics.yaml": ("C2", 0.15),
    "C3_trolling_nonsense.yaml": ("C3", 0.05),
    "D_overload_breakdown.yaml": ("D", 0.05),
}

DOMAINS = {"office", "housework", "exercise", "lifestyle", "study", "mixed", "none"}
SESSIONS = {"splittable", "single", "not_sure", None}
PACINGS = {"LIGHT", "BALANCED", "FLOW", "CUSTOM", "NOT_SURE", None}
PRIORITIES = {1, 2, 3, 4, "NOT_SURE", None}
STATUSES = {"OK", "OK_WITH_WARNINGS", "NEEDS_FIX", "REJECTED"}
SUB_STATUSES = {"TODO", "IN_PROGRESS", "DONE", "WAITING"}
ALLOWED_EXT = {"txt", "pdf", "html", "md"}
MAX_MB = 20

ERRORS = {
    "E_PROMPT_TOO_LONG", "E_NO_ACTIONABLE_TASK", "E_NONSENSE_INPUT",
    "E_DEADLINE_CONTRADICTION", "E_DURATION_CONTRADICTION", "E_SESSION_CONTRADICTION",
    "E_SEMANTIC_CONTRADICTION", "E_START_AFTER_DEADLINE", "E_SUBTASK_DEADLINE_AFTER_PARENT",
    "E_CYCLIC_DEPENDENCY", "E_INFEASIBLE_WORKLOAD", "E_ATTACHMENT_TOO_LARGE",
    "E_ATTACHMENT_TYPE", "E_CUSTOM_RANGE_INVALID",
}
WARNINGS = {
    "W_NO_DEADLINE", "W_VAGUE_DEADLINE", "W_AMBIGUOUS_DATE",
    "W_NO_DURATION", "W_VAGUE_DURATION", "W_PARTIAL_DURATION",
    "W_PRIORITY_DEFAULTED", "W_PRIORITY_UNCERTAIN", "W_PRIORITY_INFERRED", "W_PRIORITY_CONFLICT",
    "W_SESSION_DEFAULTED", "W_PACING_DEFAULTED", "W_SESSION_CONFLICT", "W_CHUNK_CONFLICT",
    "W_SUBTASK_DEFAULTS_INHERITED", "W_STATUS_INFERRED", "W_DEPENDENCY_UNCLEAR", "W_OPEN_LOOP",
    "W_EXTERNAL_DEPENDENCY", "W_DOC_MENTIONED_NOT_ATTACHED", "W_ATTACHMENT_UNREFERENCED",
    "W_SCOPE_MISMATCH", "W_RECURRING_NO_END", "W_VAGUE_TASK", "W_UNRESOLVED_REFERENCE",
    "W_MULTIPLE_GOALS", "W_BREAKDOWN_RECOMMENDED", "W_TIGHT_SCHEDULE", "W_UNREALISTIC_LOAD",
    "W_SELF_CORRECTION", "W_TYPO_CORRECTED", "W_MIXED_LANGUAGE", "W_NON_TASK_CONTENT",
    "W_PROMPT_INJECTION",
}
CONTRACT_REQUIRED = ["title", "total_work_minutes", "deadline", "priority", "is_task_splittable", "splitting"]


def dt(value):
    return datetime.fromisoformat(value) if value else None


class Checker:
    def __init__(self):
        self.problems: list[str] = []

    def fail(self, cid: str, msg: str):
        self.problems.append(f"[{cid}] {msg}")

    # ------------------------------------------------------------------
    def check_case(self, case: dict):
        cid = case.get("id", "<no id>")
        for key in ("id", "domain", "group", "covers", "input", "expected", "rationale"):
            if key not in case:
                self.fail(cid, f"missing key '{key}'")
        if case.get("domain") not in DOMAINS:
            self.fail(cid, f"bad domain {case.get('domain')!r}")

        inp = case.get("input", {})
        ui = inp.get("ui", {})
        prompt = inp.get("prompt", "")
        if ui.get("session") not in SESSIONS:
            self.fail(cid, f"bad ui.session {ui.get('session')!r}")
        if ui.get("pacing") not in PACINGS:
            self.fail(cid, f"bad ui.pacing {ui.get('pacing')!r}")
        if ui.get("priority") not in PRIORITIES:
            self.fail(cid, f"bad ui.priority {ui.get('priority')!r}")

        exp = case.get("expected", {})
        errors = exp.get("errors", []) or []
        warnings = exp.get("warnings", []) or []
        for code in errors:
            if code not in ERRORS:
                self.fail(cid, f"unknown error code {code}")
        for code in warnings:
            if code not in WARNINGS:
                self.fail(cid, f"unknown warning code {code}")
        if len(set(warnings)) != len(warnings):
            self.fail(cid, "duplicate warning codes")

        # status consistency
        status = exp.get("status")
        if status not in STATUSES:
            self.fail(cid, f"bad status {status!r}")
        if status == "REJECTED" and "E_NONSENSE_INPUT" not in errors:
            self.fail(cid, "REJECTED requires E_NONSENSE_INPUT")
        if errors and status not in ("NEEDS_FIX", "REJECTED"):
            self.fail(cid, "errors present but status not NEEDS_FIX/REJECTED")
        if not errors and warnings and status != "OK_WITH_WARNINGS":
            self.fail(cid, "warnings only => OK_WITH_WARNINGS")
        if not errors and not warnings and status != "OK":
            self.fail(cid, "no diagnostics => OK")
        if errors and not exp.get("suggestions"):
            self.fail(cid, "errors must come with at least one suggestion")

        # prompt length rule (2000 chars cap)
        if (len(prompt) > 2000) != ("E_PROMPT_TOO_LONG" in errors):
            self.fail(cid, f"prompt length {len(prompt)} vs E_PROMPT_TOO_LONG mismatch")

        # attachment rules
        too_big = any(a.get("mb", 0) > MAX_MB for a in ui.get("attachments", []) or [])
        bad_type = any(a["name"].rsplit(".", 1)[-1].lower() not in ALLOWED_EXT for a in ui.get("attachments", []) or [])
        if too_big != ("E_ATTACHMENT_TOO_LARGE" in errors):
            self.fail(cid, "attachment size vs E_ATTACHMENT_TOO_LARGE mismatch")
        if bad_type != ("E_ATTACHMENT_TYPE" in errors):
            self.fail(cid, "attachment type vs E_ATTACHMENT_TYPE mismatch")

        # custom range rule
        custom = ui.get("custom")
        if custom and (custom[0] > custom[1]) != ("E_CUSTOM_RANGE_INVALID" in errors):
            self.fail(cid, "custom range vs E_CUSTOM_RANGE_INVALID mismatch")

        if bool(exp.get("breakdown_required")) != ("W_BREAKDOWN_RECOMMENDED" in warnings):
            self.fail(cid, "breakdown_required <=> W_BREAKDOWN_RECOMMENDED mismatch")
        if exp.get("breakdown_required") and len(exp.get("suggestions", [])) < 2:
            self.fail(cid, "breakdown must offer >= 2 suggestions")

        if "contract" in exp and exp["contract"] is None:
            if status not in ("NEEDS_FIX", "REJECTED"):
                self.fail(cid, "contract: null only allowed for NEEDS_FIX/REJECTED")
            return

        for key in CONTRACT_REQUIRED:
            if key not in exp:
                self.fail(cid, f"expected missing '{key}'")

        self.check_splitting(cid, exp, errors)
        self.check_priority(cid, exp)
        self.check_dates(cid, exp, errors)
        self.check_subtasks(cid, exp, errors)
        self.check_feasibility(cid, exp, errors, warnings)

    # ------------------------------------------------------------------
    def check_splitting(self, cid, exp, errors):
        split = exp.get("is_task_splittable")
        cfg = exp.get("splitting")
        if split is False and cfg is not None:
            self.fail(cid, "single session must have splitting: null")
        if split is True and cfg is None and "E_CUSTOM_RANGE_INVALID" not in errors:
            self.fail(cid, "splittable task needs a splitting config")
        if split is None and "E_SESSION_CONTRADICTION" not in errors:
            self.fail(cid, "is_task_splittable null only with E_SESSION_CONTRADICTION")
        if cfg:
            if not (cfg["min"] <= cfg["pref"] <= cfg["max"]):
                self.fail(cid, f"splitting not ordered: {cfg}")

    def check_priority(self, cid, exp):
        pri = exp.get("priority")
        if pri not in (1, 2, 3, 4, None):
            self.fail(cid, f"bad expected priority {pri!r}")
        if pri is None and not exp.get("priority_uncertain"):
            self.fail(cid, "priority null requires priority_uncertain: true")

    def check_dates(self, cid, exp, errors):
        try:
            dl, sa = dt(exp.get("deadline")), dt(exp.get("start_after"))
        except ValueError as exc:
            self.fail(cid, f"bad datetime: {exc}")
            return
        if dl and dl < BASE_TIME:
            self.fail(cid, "deadline in the past")
        if dl and sa and sa > dl and "E_START_AFTER_DEADLINE" not in errors:
            self.fail(cid, "start_after > deadline without E_START_AFTER_DEADLINE")
        for st in exp.get("subtasks", []) or []:
            sdl = dt(st.get("deadline"))
            if sdl and dl and sdl > dl and "E_SUBTASK_DEADLINE_AFTER_PARENT" not in errors:
                self.fail(cid, f"subtask {st['id']} deadline after parent")

    def check_subtasks(self, cid, exp, errors):
        subs = exp.get("subtasks", []) or []
        ids = [s["id"] for s in subs]
        if len(set(ids)) != len(ids):
            self.fail(cid, "duplicate subtask ids")
        graph = {}
        for s in subs:
            if s.get("status", "TODO") not in SUB_STATUSES:
                self.fail(cid, f"bad subtask status {s.get('status')}")
            if s.get("priority") not in (None, 1, 2, 3, 4):
                self.fail(cid, f"bad subtask priority {s.get('priority')}")
            for dep in s.get("depends_on", []) or []:
                if dep not in ids:
                    self.fail(cid, f"{s['id']} depends on unknown {dep}")
            graph[s["id"]] = s.get("depends_on", []) or []

        if self.has_cycle(graph) != ("E_CYCLIC_DEPENDENCY" in errors):
            self.fail(cid, "dependency cycle vs E_CYCLIC_DEPENDENCY mismatch")

        # remaining-work sum rule (if E_DURATION_CONTRADICTION, header total and subtask sum must genuinely disagree)
        if not subs or exp.get("repeat"):
            return
        if any(s.get("repeat") for s in subs):
            return
        known, unknown = 0, False
        for s in subs:
            if s.get("status") == "DONE" or s.get("external"):
                continue
            if "minutes" not in s or s["minutes"] is None:
                unknown = True
            else:
                known += s["minutes"]
        total = exp.get("total_work_minutes")
        if "E_DURATION_CONTRADICTION" in errors:
            if total == known:
                self.fail(cid, f"E_DURATION_CONTRADICTION requires header total ({total}) != subtask sum ({known})")
            return
        if unknown:
            if total is not None:
                self.fail(cid, "total must be null when a subtask duration is unknown")
            lb = exp.get("work_minutes_lower_bound")
            if known and lb != known:
                self.fail(cid, f"work_minutes_lower_bound should be {known}, got {lb}")
        elif total != known:
            self.fail(cid, f"total_work_minutes {total} != remaining subtask sum {known}")

    @staticmethod
    def has_cycle(graph):
        state = {}

        def visit(node):
            if state.get(node) == 1:
                return True
            if state.get(node) == 2:
                return False
            state[node] = 1
            if any(visit(n) for n in graph.get(node, []) if n in graph):
                return True
            state[node] = 2
            return False

        return any(visit(n) for n in graph)

    def check_feasibility(self, cid, exp, errors, warnings):
        total = exp.get("total_work_minutes") or exp.get("work_minutes_lower_bound")
        dl = dt(exp.get("deadline"))
        if not total or not dl or exp.get("repeat"):
            return
        sa = dt(exp.get("start_after"))
        start = max(BASE_TIME, sa) if sa else BASE_TIME
        window = (dl - start).total_seconds() / 60
        if window <= 0:
            return
        if sa and abs(window - total) < 1:  # fixed slot
            return
        capacity = window / 3 if window > 1440 else min(window / 2, 480)
        infeasible = total > window
        tight = (not infeasible) and total > capacity
        if infeasible != ("E_INFEASIBLE_WORKLOAD" in errors):
            self.fail(cid, f"infeasibility mismatch (total={total}, window={window:.0f})")
        if tight != ("W_TIGHT_SCHEDULE" in warnings):
            self.fail(cid, f"tight-schedule mismatch (total={total}, capacity={capacity:.0f})")


def main() -> int:
    checker = Checker()
    all_ids, per_cat, domains, covers = [], Counter(), Counter(), Counter()
    status_count = Counter()

    for fname, (cat, _) in FILES.items():
        path = ROOT / fname
        if not path.exists():
            checker.problems.append(f"missing file {fname}")
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for case in data["cases"]:
            checker.check_case(case)
            all_ids.append(case.get("id"))
            per_cat[cat] += 1
            domains[case.get("domain")] += 1
            covers.update(case.get("covers", []))
            status_count[case["expected"].get("status")] += 1

    dupes = [i for i, n in Counter(all_ids).items() if n > 1]
    if dupes:
        checker.problems.append(f"duplicate ids: {dupes}")

    total = sum(per_cat.values())
    print(f"Total cases: {total}")
    targets = {}
    for _, (cat, share) in FILES.items():
        targets[cat] = targets.get(cat, 0) + share
    for cat, share in targets.items():
        got = per_cat[cat] / total if total else 0
        flag = "OK " if abs(got - share) < 0.005 else "OFF"
        print(f"  [{flag}] {cat:<3} {per_cat[cat]:>3} cases  {got:6.1%}  (target {share:.0%})")
        if flag == "OFF":
            checker.problems.append(f"category {cat} share {got:.1%} != {share:.0%}")
    print("Domains:", dict(domains))
    print("Statuses:", dict(status_count))
    print(f"Distinct edge-case tags: {len(covers)}")

    if checker.problems:
        print(f"\n{len(checker.problems)} problem(s):")
        for p in checker.problems:
            print("  -", p)
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

