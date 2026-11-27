"""
Logical & Behavioral Verification:
  - `smartschedule/core/student_simulator.py` (Pattern P14b — 5-Equation In-Silico Student Twin)
  - `smartschedule/nlp/doc_attachment_parser.py` (Pattern P14a — Logical Syllabus/Assignment Compiler)
"""

from __future__ import annotations

import ast
import base64
from pathlib import Path
import random
import statistics
import time
import pytest

from smartschedule.core.config import CORE_DIR
from smartschedule.core.controller import ScheduleController
from smartschedule.core.models import CommitmentsProfile, FixedEvent, SleepSchedule, Task
from smartschedule.core.student_simulator import (
    InSilicoStudentSimulator,
    compute_timeline_hash,
    summarize_week_execution,
)
from smartschedule.nlp.doc_attachment_parser import (
    MAX_ATTACHMENT_BYTES,
    detect_user_underestimate,
    parse_document_constraint_digest,
)

REQUIRED_LOG_KEYS = {
    "task_id",
    "block_id",
    "category",
    "cognitive_load",
    "day",
    "window",
    "start_hour",
    "estimated_duration_min",
    "planned_duration_min",
    "actual_duration_min",
    "adhered",
    "overrun_min",
    "fatigue_after",
    "disruption_slot_window",
}


def _make_standard_profile(
    *,
    focus_preference: str = "MORNING",
    sleep_start: str = "23:30",
    sleep_end: str = "06:30",
    alpha_light: float = 1.20,
    alpha_heavy: float = 1.35,
    buffer_mode: str = "COGNITIVE_LOAD",
) -> CommitmentsProfile:
    return CommitmentsProfile(
        student_id="TEST_SIM_STUDENT",
        planning_week_start="2026-11-02T00:00:00+07:00",
        now="2026-11-02T06:30:00+07:00",
        sleep_schedule=SleepSchedule(daily_start_time=sleep_start, daily_end_time=sleep_end, is_hard_lock=True),
        fixed_events=[
            FixedEvent(
                event_id="CLASS_MWF",
                title="Morning Class",
                day_of_week=["Monday", "Wednesday", "Friday"],
                start_time="13:00",
                end_time="15:00",
                category="ACADEMIC_CLASS",
            ),
            FixedEvent(
                event_id="MEAL_LUNCH",
                title="Lunch",
                day_of_week="ALL",
                start_time="12:00",
                end_time="12:45",
                category="MEAL",
            ),
        ],
        focus_preference=focus_preference,
        buffer_mode=buffer_mode,
        alpha_light=alpha_light,
        alpha_heavy=alpha_heavy,
    )


def _make_mixed_week_tasks() -> list[Task]:
    return [
        Task(
            task_id="CODE_01",
            title="Implement graph solver",
            duration_min=90,
            deadline_day="Wednesday",
            deadline_time="22:00",
            priority=5,
            category="CODING",
            cognitive_load=3,
            is_splittable=True,
        ),
        Task(
            task_id="CODE_02",
            title="Build backtracking validator",
            duration_min=90,
            deadline_day="Friday",
            deadline_time="22:00",
            priority=5,
            category="CODING",
            cognitive_load=3,
            is_splittable=True,
        ),
        Task(
            task_id="CODE_03",
            title="Optimize ALNS operators",
            duration_min=90,
            deadline_day="Sunday",
            deadline_time="22:00",
            priority=4,
            category="CODING",
            cognitive_load=3,
            is_splittable=True,
        ),
        Task(
            task_id="CODE_04",
            title="Write dynamic repair engine",
            duration_min=90,
            deadline_day="Sunday",
            deadline_time="22:00",
            priority=4,
            category="CODING",
            cognitive_load=3,
            is_splittable=True,
        ),
        Task(
            task_id="READ_01",
            title="Read research paper notes",
            duration_min=60,
            deadline_day="Thursday",
            deadline_time="23:59",
            priority=3,
            category="READING",
            cognitive_load=1,
            is_splittable=False,
        ),
        Task(
            task_id="READ_02",
            title="Summarize chapter 4",
            duration_min=60,
            deadline_day="Saturday",
            deadline_time="23:59",
            priority=3,
            category="READING",
            cognitive_load=1,
            is_splittable=False,
        ),
        Task(
            task_id="READ_03",
            title="Review lecture slides",
            duration_min=60,
            deadline_day="Sunday",
            deadline_time="23:59",
            priority=2,
            category="READING",
            cognitive_load=1,
            is_splittable=False,
            preferred_window="EVENING",
        ),
        Task(
            task_id="CODE_05",
            title="Debug evening lab exercise",
            duration_min=60,
            deadline_day="Sunday",
            deadline_time="23:59",
            priority=4,
            category="CODING",
            cognitive_load=3,
            is_splittable=False,
            preferred_window="EVENING",
        ),
    ]


def test_student_simulator_layer1_purity_and_rng_isolation():
    """Verify Layer-1 import purity, RNG isolation, input immutability, and 3-run hash determinism."""
    sim_path = CORE_DIR / "student_simulator.py"
    tree = ast.parse(sim_path.read_text(encoding="utf-8"), filename=str(sim_path))
    allowed_core_prefixes = (
        "smartschedule.core.config",
        "smartschedule.core.models",
        "smartschedule.core.utils",
    )
    forbidden_prefixes = (
        "smartschedule.nlp",
        "smartschedule.api",
        "smartschedule.core.controller",
        "smartschedule.core.solvers",
        "fastapi",
        "httpx",
        "spacy",
        "pypdf",
        "docling",
        "google",
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith(forbidden_prefixes), f"Layer violation: {alias.name}"
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith(forbidden_prefixes), f"Layer violation: {node.module}"
            if node.module.startswith("smartschedule"):
                assert node.module.startswith(allowed_core_prefixes), (
                    f"Non-allowed smartschedule import in Layer 1 simulator: {node.module}"
                )

    profile = _make_standard_profile()
    tasks = _make_mixed_week_tasks()
    schedule, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="SCORED_GREEDY")

    prof_snap = profile.model_dump()
    tasks_snap = [t.model_dump() for t in tasks]
    sched_snap = schedule.model_dump()

    random.seed(99999)
    global_rng_before = random.getstate()

    hashes = []
    logs_runs = []
    for _ in range(3):
        sim = InSilicoStudentSimulator(
            student_id="DETERMINISTIC_CHECK",
            seed=42,
            latent_profile={"true_peak_hour": 20.5, "recurring_disruption": "Thursday 19:30-21:00"},
        )
        logs = sim.simulate_week_execution(profile, tasks, schedule)
        logs_runs.append(logs)
        hashes.append(compute_timeline_hash(logs))

    assert random.getstate() == global_rng_before, "Simulator mutated global random module state!"
    assert profile.model_dump() == prof_snap
    assert [t.model_dump() for t in tasks] == tasks_snap
    assert schedule.model_dump() == sched_snap

    assert len(set(hashes)) == 1
    assert logs_runs[0] == logs_runs[1] == logs_runs[2]
    assert len(logs_runs[0]) == len(schedule.blocks)
    for entry in logs_runs[0]:
        assert REQUIRED_LOG_KEYS.issubset(entry.keys())
        assert entry["window"] in {"MORNING", "AFTERNOON", "EVENING"}


def test_psychometric_equations_exact_properties():
    """Verify Equations 1..5 mathematical invariants, anti-double-buffering, and recurring disruptions."""
    # Eq 1: MCTQ circular fit (wraparound across midnight within valid [7.0, 23.0] peak domain)
    sim_owl = InSilicoStudentSimulator("OWL", seed=7, latent_profile={"true_peak_hour": 23.0, "poisson_disruption_rate": 0.0})
    assert sim_owl.circadian_fit(23.0) == pytest.approx(1.0)
    assert sim_owl.circadian_fit(1.0) == pytest.approx(1.0 - 2.0 / 8.0)  # 2h circular wraparound distance
    assert sim_owl.circadian_fit(11.0) == pytest.approx(0.0)

    # Eq 2: Buehler category Log-Normal fallacy & 15m quantization
    coding_samples = [sim_owl.sample_actual_duration_min(60, "CODING") for _ in range(40)]
    reading_samples = [sim_owl.sample_actual_duration_min(60, "READING") for _ in range(40)]
    assert all(d > 0 and d % 15 == 0 for d in coding_samples + reading_samples)
    assert statistics.mean(coding_samples) > statistics.mean(reading_samples)

    # Eq 3 & 4: Steel (2007) TMT with Gamma denominator & McFadden RUM logit
    sim_proc = InSilicoStudentSimulator("PROC", seed=11, latent_profile={"true_peak_hour": 20.0, "gamma": 0.5})
    u_near = sim_proc.compute_tmt_utility(circ_fit=0.9, fatigue=0.1, priority=5, slack_hours=4.0)
    u_far = sim_proc.compute_tmt_utility(circ_fit=0.9, fatigue=0.1, priority=5, slack_hours=96.0)
    u_low_p = sim_proc.compute_tmt_utility(circ_fit=0.9, fatigue=0.1, priority=1, slack_hours=4.0)
    assert u_near > u_far, "Near-deadline TMT utility must exceed far-deadline utility (Gamma denominator)"
    assert u_near > u_low_p, "Higher priority task must have higher TMT utility"

    p_fresh = sim_proc.adherence_probability(u_near, fatigue=0.0)
    p_tired = sim_proc.adherence_probability(u_near, fatigue=0.9)
    assert p_fresh > p_tired

    # Eq 5a: 40% fatigue recovery after >=15m break, 0% recovery if <15m
    assert InSilicoStudentSimulator.apply_rest_break(0.80, 15) == pytest.approx(0.48)
    assert InSilicoStudentSimulator.apply_rest_break(0.80, 10) == pytest.approx(0.80)

    # Eq 5b & Anti-double-buffering: verify planned_duration_min > estimated_duration_min == raw Task.duration_min
    profile = _make_standard_profile(alpha_light=1.20, alpha_heavy=1.35)
    atomic_task = Task(
        task_id="CODE_ATOMIC",
        title="Atomic coding task",
        duration_min=60,
        deadline_day="Thursday",
        deadline_time="23:59",
        priority=5,
        category="CODING",
        cognitive_load=3,
        is_splittable=False,
    )
    sched, _ = ScheduleController.solve_schedule(profile, [atomic_task], algorithm="SCORED_GREEDY")
    assert len(sched.blocks) == 1
    assert sched.blocks[0].duration_min == 90  # ceil(60 * 1.35 / 15)*15 = 90m buffered

    logs_ok = sim_owl.simulate_week_execution(profile, [atomic_task], sched)
    assert logs_ok[0]["estimated_duration_min"] == 60  # raw unbuffered estimate, NOT 90!
    assert logs_ok[0]["planned_duration_min"] == 90

    # Recurring disruption window collision -> adhered=False & non-null canonical disruption_slot_window
    pinned_thu_eve = sched.blocks[0].model_copy(
        update={
            "day": "Thursday",
            "start_slot": 3 * 96 + 19 * 4 + 2,  # Thu 19:30
            "end_slot": 3 * 96 + 21 * 4,        # Thu 21:00
            "start_time": "19:30",
            "end_time": "21:00",
            "duration_min": 90,
        }
    )
    sched_disrupt = sched.model_copy(update={"blocks": [pinned_thu_eve]})
    sim_disrupt = InSilicoStudentSimulator(
        "DISRUPT_TEST",
        seed=42,
        latent_profile={"recurring_disruption": {"day": "Thursday", "start_time": "19:30", "end_time": "21:00"}},
    )
    dis_logs = sim_disrupt.simulate_week_execution(profile, [atomic_task], sched_disrupt)
    assert dis_logs[0]["adhered"] is False
    assert dis_logs[0]["actual_duration_min"] == 0
    assert dis_logs[0]["disruption_slot_window"] == "Thursday 19:30–21:00"

    # Sleep < 7h leaves residual morning fatigue higher than >= 7h sleep
    short_sleep_prof = _make_standard_profile(sleep_start="01:30", sleep_end="06:30")  # 5h sleep
    sched_short, _ = ScheduleController.solve_schedule(short_sleep_prof, [atomic_task], algorithm="SCORED_GREEDY")
    sim_a = InSilicoStudentSimulator("SLEEP_A", seed=5, latent_profile={"poisson_disruption_rate": 0.0, "u_distract": -5.0})
    sim_b = InSilicoStudentSimulator("SLEEP_B", seed=5, latent_profile={"poisson_disruption_rate": 0.0, "u_distract": -5.0})
    log_norm = sim_a.simulate_week_execution(profile, [atomic_task], sched)
    log_short = sim_b.simulate_week_execution(short_sleep_prof, [atomic_task], sched_short)
    assert log_short[0]["fatigue_after"] > log_norm[0]["fatigue_after"]


def _local_p13_adapt_fallback(
    profile: CommitmentsProfile,
    tasks: list[Task],
    history_logs: list[dict],
    kappa: float = 3.0,
) -> tuple[CommitmentsProfile, list[Task]]:
    """Compact P13 Bayesian-shrinkage + revealed-window adapter used when M5's module is not yet merged."""
    # Shrinkage category buffer
    cat_ratios: dict[str, list[float]] = {}
    win_scores: dict[str, list[float]] = {"MORNING": [], "AFTERNOON": [], "EVENING": []}
    for row in history_logs:
        est = float(row.get("estimated_duration_min") or 0)
        act = float(row.get("actual_duration_min") or 0)
        cat = str(row.get("category") or "OTHER").upper()
        win = str(row.get("window") or "MORNING").upper()
        if row.get("adhered") and est > 0 and act > 0:
            ratio = max(0.5, min(2.5, act / est))
            cat_ratios.setdefault(cat, []).append(ratio)
            if win in win_scores:
                win_scores[win].append(min(1.25, est / act))
        elif win in win_scores:
            win_scores[win].append(0.0)

    best_win = profile.focus_preference or "MORNING"
    best_eff = -1.0
    for win, vals in win_scores.items():
        if len(vals) >= 2:
            eff = sum(vals) / len(vals)
            if eff > best_eff:
                best_eff = eff
                best_win = win

    new_profile = profile.model_copy(update={"focus_preference": best_win, "energy_profile": None}, deep=True)
    adapted_tasks: list[Task] = []
    learned_light: list[float] = []
    learned_heavy: list[float] = []
    for t in tasks:
        cat = str(t.category or "OTHER").upper()
        is_heavy = (t.cognitive_load or 2) >= 3
        prior = 1.35 if is_heavy else 1.20
        vals = cat_ratios.get(cat, [])
        if vals:
            ewma = prior
            for r in vals:
                ewma = 0.30 * r + 0.70 * ewma
            n_c = len(vals)
            alpha = (n_c * ewma + kappa * prior) / (n_c + kappa)
            alpha = round(max(1.00, min(1.60, alpha)), 2)
        else:
            alpha = prior
        if is_heavy:
            learned_heavy.append(alpha)
        else:
            learned_light.append(alpha)
        adapted_tasks.append(
            t.model_copy(
                update={
                    "buffer_mode": "COGNITIVE_LOAD",
                    "alpha_light": alpha if not is_heavy else t.alpha_light,
                    "alpha_heavy": alpha if is_heavy else t.alpha_heavy,
                    "preferred_window": best_win if is_heavy else t.preferred_window,
                },
                deep=True,
            )
        )
    new_profile = new_profile.model_copy(
        update={
            "alpha_light": round(sum(learned_light) / len(learned_light), 2) if learned_light else new_profile.alpha_light,
            "alpha_heavy": round(sum(learned_heavy) / len(learned_heavy), 2) if learned_heavy else new_profile.alpha_heavy,
        },
        deep=True,
    )
    return new_profile, adapted_tasks


def test_closed_loop_4_week_adaptation_convergence_and_latency():
    """
    Closed-loop Week 1 -> Week 4 simulation on a miscalibrated Night-Owl + Coding-Underestimator
    student (`true_peak_hour=20.5`, `CODING=1.42`, misreported `MORNING` & `alpha_heavy=1.00`).
    Must keep simulation+adaptation well under 500 ms and strictly improve Week 4 vs Week 1.
    """
    try:
        from smartschedule.core.cross_week_adapter import adapt_preferences_for_next_week
    except ImportError:
        adapt_preferences_for_next_week = None

    latent = {
        "true_peak_hour": 20.5,
        "category_bias": {"CODING": 1.42, "READING": 1.05},
        "lognormal_sigma": 0.03,
        "gamma": 0.25,
        "u_distract": 0.12,
        "logit_beta": 8.0,
        "poisson_disruption_rate": 0.0,
    }

    # Initial miscalibrated profile (claims MORNING, zero initial buffer alpha=1.00)
    profile = _make_standard_profile(focus_preference="MORNING", alpha_light=1.00, alpha_heavy=1.00)
    base_tasks = _make_mixed_week_tasks()
    tasks = [
        t.model_copy(update={"alpha_light": 1.00, "alpha_heavy": 1.00, "buffer_mode": "COGNITIVE_LOAD"}, deep=True)
        for t in base_tasks
    ]

    sim = InSilicoStudentSimulator("NIGHT_OWL_CODER", seed=42, latent_profile=latent)
    all_history: list[dict] = []
    weekly_metrics: list[dict] = []

    sim_adapt_ms = 0.0
    t_start = time.perf_counter()
    for wk in range(1, 5):
        sched, _ = ScheduleController.solve_schedule(profile, tasks, algorithm="SCORED_GREEDY")
        t_sim = time.perf_counter()
        logs = sim.simulate_week_execution(profile, tasks, sched)
        summary = summarize_week_execution(tasks, sched, logs, profile.planning_week_start)
        weekly_metrics.append(summary)
        all_history.extend(logs)

        fresh_tasks = [t.model_copy(deep=True) for t in base_tasks]
        if adapt_preferences_for_next_week is not None:
            adapted = adapt_preferences_for_next_week(profile, fresh_tasks, all_history)
            profile = adapted["adapted_commitments"]
            tasks = adapted["adapted_tasks"]
        else:
            profile, tasks = _local_p13_adapt_fallback(profile, fresh_tasks, all_history)
        sim_adapt_ms += (time.perf_counter() - t_sim) * 1000.0

    elapsed_ms = (time.perf_counter() - t_start) * 1000.0
    assert sim_adapt_ms < 500.0, f"4-week simulator+adapter took {sim_adapt_ms:.1f} ms (>= 500 ms SLA)"
    assert elapsed_ms < 3000.0, f"Full 4-week solve+sim loop took {elapsed_ms:.1f} ms (>= 3000 ms)"

    w1 = weekly_metrics[0]
    w4 = weekly_metrics[-1]
    assert w4["adherence_pct"] > w1["adherence_pct"], f"Expected Week 4 adherence > Week 1 ({w4} vs {w1})"
    assert w4["on_time_value_pct"] > w1["on_time_value_pct"], f"Expected Week 4 on-time value > Week 1 ({w4} vs {w1})"
    assert w4["mean_overrun_min"] < w1["mean_overrun_min"], f"Expected Week 4 mean overrun < Week 1 ({w4} vs {w1})"


def test_doc_attachment_parser_bilingual_milestones_and_dag():
    """Verify milestone extraction, weights, cognitive loads, DAG cues, and underestimate detection."""
    lab_spec = """
# Lab 03: Graph Shortest Path & Verification
Worth 30% of final grade.

## Overview
Read the instructions carefully before coding.

## Part 1 (40%): Implement Dijkstra Solver in Python
Write `dijkstra.py` to compute shortest paths and optimize the priority queue. (2 hours)

## Part 2 (30%): Write Unit Tests Based on Part 1
Test edge cases and benchmark runtime using the output from Part 1. (1 hour)

## Part 3 (30%): Final Report Summarizing Test Results
Write a concise report comparing theoretical vs measured runtime.
"""
    digest = parse_document_constraint_digest("Lab03_Spec.md", lab_spec)
    assert digest["filename"] == "Lab03_Spec.md"
    assert len(digest["milestones"]) == 3

    m1, m2, m3 = digest["milestones"]
    assert m1["weight_pct"] == 40
    assert m1["cognitive_load"] == 3
    assert m1["estimated_min"] == 120
    assert m1["depends_on_prev"] is False

    assert m2["weight_pct"] == 30
    assert m2["cognitive_load"] == 2
    assert m2["estimated_min"] == 60
    assert m2["depends_on_prev"] is True

    assert m3["weight_pct"] == 30
    assert m3["cognitive_load"] == 2
    assert m3["depends_on_prev"] is True

    assert digest["suggested_total_min"] >= 180
    assert digest["suggested_total_min"] % 15 == 0
    assert digest["suggested_load"] == 3
    assert digest["suggested_priority"] == 5

    # Underestimate detection: 30m user estimate vs >= 180m doc estimate (< 0.5x)
    conflict = detect_user_underestimate(30, digest)
    assert conflict["is_underestimate"] is True
    assert conflict["conflict_code"] == "USER_VS_DOC_UNDERESTIMATE"

    ok_check = detect_user_underestimate(180, digest)
    assert ok_check["is_underestimate"] is False
    assert ok_check["conflict_code"] is None

    # Independent Vietnamese exam problems should NOT artificially chain depends_on_prev
    vn_exam = """
Câu 1 (20%): Cài đặt hàm đọc đồ thị từ file txt.
Câu 2 (30%): Cài đặt thuật toán tìm đường đi ngắn nhất.
"""
    vn_digest = parse_document_constraint_digest("De_Thi_Thu.txt", vn_exam)
    assert len(vn_digest["milestones"]) == 2
    assert vn_digest["milestones"][0]["weight_pct"] == 20
    assert vn_digest["milestones"][1]["weight_pct"] == 30
    assert vn_digest["milestones"][0]["depends_on_prev"] is False
    assert vn_digest["milestones"][1]["depends_on_prev"] is False
    assert vn_digest["suggested_priority"] == 5


def test_doc_attachment_parser_pdf_base64_and_size_guardrails():
    """Verify stdlib PDF stream fallback, data-URI base64 decoding, >20 MB rejection, and empty input."""
    minimal_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog >> endobj\n"
        b"2 0 obj << /Length 138 >> stream\n"
        b"BT /F1 12 Tf 72 720 Td (Part 1: Implement Graph Parser (50%)) Tj "
        b"0 -20 Td (Part 2: Write Integration Tests after Part 1 (50%)) Tj ET\n"
        b"endstream\nendobj\n%%EOF\n"
    )
    pdf_digest = parse_document_constraint_digest("assignment.pdf", minimal_pdf)
    assert len(pdf_digest["milestones"]) == 2
    assert pdf_digest["milestones"][0]["weight_pct"] == 50
    assert pdf_digest["milestones"][0]["cognitive_load"] == 3
    assert pdf_digest["milestones"][1]["depends_on_prev"] is True

    # Data-URI base64 payload
    b64_uri = "data:application/pdf;base64," + base64.b64encode(minimal_pdf).decode("ascii")
    b64_digest = parse_document_constraint_digest("assignment_b64.pdf", b64_uri)
    assert len(b64_digest["milestones"]) == 2
    assert b64_digest["suggested_total_min"] == pdf_digest["suggested_total_min"]

    # > 20 MB cap enforcement
    oversized = b"A" * (MAX_ATTACHMENT_BYTES + 1)
    with pytest.raises(ValueError, match="20 MB"):
        parse_document_constraint_digest("huge.txt", oversized)

    # Empty attachment returns valid safe digest
    empty_digest = parse_document_constraint_digest("empty.md", "   \n  ")
    assert empty_digest["milestones"] == []
    assert empty_digest["suggested_total_min"] == 0
    assert empty_digest["suggested_priority"] == 3
    assert empty_digest["suggested_load"] == 2
