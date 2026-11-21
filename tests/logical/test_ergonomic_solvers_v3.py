"""
Verification Tests (V3): Ergonomic Solvers, Q10 Energy-Blind Invariants, Hybrid ALNS,
Adaptive Legal Splitting, Multi-Week 14-Day Horizon, Partial Pinned Stability, and Speed Bounds.
"""

import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from smartschedule.core.models import CommitmentsProfile, FixedEvent, ScheduleBlock, SleepSchedule, Task
from smartschedule.core.solvers.registry import resolve_solver


def _build_realistic_profile(focus: str = "MORNING", horizon_days: int = 7) -> CommitmentsProfile:
    return CommitmentsProfile(
        student_id="TEST_V3_STUDENT",
        focus_preference=focus,
        horizon_days=horizon_days,
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
        fixed_events=[
            FixedEvent(
                event_id="CLASS_MON",
                title="Data Structures Class",
                day_of_week=["Monday", "Wednesday", "Friday"],
                start_time="08:00",
                end_time="09:30",
                category="ACADEMIC_CLASS",
            ),
            FixedEvent(
                event_id="LUNCH",
                title="Lunch Break",
                day_of_week=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                start_time="12:00",
                end_time="13:00",
                category="MEAL",
            ),
        ],
    )


def _build_mixed_tasks() -> list:
    return [
        Task(
            task_id="T_HEAVY_1",
            title="Algorithms Assignment",
            duration_min=90,
            deadline_day="Wednesday",
            deadline_time="20:00",
            priority=5,
            cognitive_load=3,
            category="HOMEWORK",
        ),
        Task(
            task_id="T_HEAVY_2",
            title="Systems Project",
            duration_min=180,
            deadline_day="Thursday",
            deadline_time="22:00",
            priority=4,
            cognitive_load=3,
            is_splittable=True,
            category="PROJECT",
        ),
        Task(
            task_id="T_DEP",
            title="Algorithms Report",
            duration_min=60,
            deadline_day="Friday",
            deadline_time="18:00",
            priority=4,
            cognitive_load=2,
            depends_on=["T_HEAVY_1"],
            category="REPORT",
        ),
        Task(
            task_id="T_HABIT",
            title="Morning Review",
            duration_min=30,
            priority=2,
            cognitive_load=1,
            preferred_window="MORNING",
            category="HABIT",
        ),
    ]


def test_determinism_and_statelessness_all_six_solvers() -> None:
    """Every solver (including HYBRID_ALNS) must be 3x deterministic and stateless."""
    profile = _build_realistic_profile("MORNING")
    tasks = _build_mixed_tasks()
    for name in ["EDF", "WSPT", "LST", "SCORED_GREEDY", "BACKTRACK", "HYBRID_ALNS"]:
        solver = resolve_solver(name)
        hashes = []
        for _ in range(3):
            out, _grid = solver.solve(profile, tasks)
            hashes.append(out.determinism_hash)
            assert out.summary.hard_constraint_violations == 0, f"{name} had hard violations"
        assert len(set(hashes)) == 1, f"{name} failed 3x determinism: {hashes}"


def test_q10_energy_blind_wspt_and_lst_invariant() -> None:
    """Q10 invariant: WSPT and LST must produce identical blocks under MORNING vs EVENING."""
    tasks = _build_mixed_tasks()
    prof_m = _build_realistic_profile("MORNING")
    prof_e = _build_realistic_profile("EVENING")

    for blind_name in ["WSPT", "LST"]:
        out_m, _ = resolve_solver(blind_name).solve(prof_m, tasks)
        out_e, _ = resolve_solver(blind_name).solve(prof_e, tasks)
        spans_m = [(b.task_id, b.chunk_index, b.start_slot, b.end_slot) for b in out_m.blocks]
        spans_e = [(b.task_id, b.chunk_index, b.start_slot, b.end_slot) for b in out_e.blocks]
        assert spans_m == spans_e, f"{blind_name} drifted with energy profile!"


def test_energy_aware_solvers_separate_morning_vs_evening() -> None:
    """Energy-aware solvers should place load=3 tasks differently between MORNING and EVENING."""
    tasks = [
        Task(
            task_id="DEEP_FOCUS",
            title="Deep Proof Writing",
            duration_min=90,
            deadline_day="Wednesday",
            deadline_time="23:30",
            priority=5,
            cognitive_load=3,
            category="EXAM",
        )
    ]
    prof_m = CommitmentsProfile(
        focus_preference="MORNING",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
    )
    prof_e = CommitmentsProfile(
        focus_preference="EVENING",
        sleep_schedule=SleepSchedule(daily_start_time="23:30", daily_end_time="06:30"),
    )

    for aware_name in ["SCORED_GREEDY", "BACKTRACK", "HYBRID_ALNS"]:
        solver = resolve_solver(aware_name)
        out_m, _ = solver.solve(prof_m, tasks)
        out_e, _ = solver.solve(prof_e, tasks)
        assert out_m.blocks and out_e.blocks
        assert out_m.blocks[0].start_slot != out_e.blocks[0].start_slot, (
            f"{aware_name} ignored circadian energy peak shift!"
        )


def test_tight_deadline_rescue_zero_subopt() -> None:
    """All 5 upgraded solvers must solve tight colliding deadlines with zero unplaced tasks."""
    profile = CommitmentsProfile(
        focus_preference="MORNING",
        sleep_schedule=SleepSchedule(daily_start_time="23:00", daily_end_time="07:00"),
        fixed_events=[
            FixedEvent(
                event_id="CLASS_M",
                title="Morning Lecture",
                day_of_week="Monday",
                start_time="08:00",
                end_time="12:00",
                category="ACADEMIC_CLASS",
            ),
            FixedEvent(
                event_id="CLASS_A",
                title="Afternoon Lab",
                day_of_week="Monday",
                start_time="13:00",
                end_time="17:00",
                category="ACADEMIC_CLASS",
            ),
        ],
    )
    tasks = [
        Task(
            task_id="T_LATE_DL",
            title="Flexible Review",
            duration_min=180,
            deadline_day="Wednesday",
            deadline_time="20:00",
            priority=3,
            cognitive_load=2,
            is_splittable=True,
        ),
        Task(
            task_id="T_TIGHT",
            title="Monday Tight Task",
            duration_min=240,
            deadline_day="Monday",
            deadline_time="23:00",
            priority=5,
            cognitive_load=3,
            is_splittable=True,
        ),
    ]
    for name in ["WSPT", "LST", "SCORED_GREEDY", "BACKTRACK", "HYBRID_ALNS"]:
        out, _ = resolve_solver(name).solve(profile, tasks)
        assert out.summary.tasks_unplaced == 0, f"{name} left tight task unplaced: {out.unplaced_tasks}"
        assert out.summary.hard_constraint_violations == 0


def test_partial_pinned_and_14day_horizon() -> None:
    """Partial PINNED chunks & 14-day cross-week horizon must stay valid and intact."""
    profile = _build_realistic_profile("BALANCED", horizon_days=14)
    tasks = [
        Task(
            task_id="LONG_TERM",
            title="Capstone Phase 1",
            duration_min=180,
            deadline_day="Next Friday",
            deadline_time="18:00",
            priority=5,
            cognitive_load=3,
            is_splittable=True,
        )
    ]
    pinned = [
        ScheduleBlock(
            task_id="LONG_TERM",
            title="Capstone Phase 1",
            day="Monday",
            start_time="14:00",
            end_time="15:30",
            start_slot=56,
            end_slot=62,
            duration_min=90,
            chunk_index=1,
            total_chunks=2,
            state="PINNED",
        )
    ]
    for name in ["WSPT", "LST", "SCORED_GREEDY", "BACKTRACK", "HYBRID_ALNS"]:
        out, _ = resolve_solver(name).solve(profile, tasks, pinned_blocks=pinned)
        assert out.summary.tasks_unplaced == 0, f"{name} failed partial pinned 14d test"
        p1 = [b for b in out.blocks if b.task_id == "LONG_TERM" and b.chunk_index == 1]
        assert len(p1) == 1 and p1[0].start_slot == 56 and p1[0].state == "PINNED"


def test_n50_scalability_under_1000ms() -> None:
    """Even N=50 tasks must complete well under 1000 ms on SCORED_GREEDY and HYBRID_ALNS."""
    profile = _build_realistic_profile("BALANCED", horizon_days=14)
    tasks = [
        Task(
            task_id=f"N50_{i}",
            title=f"Task {i}",
            duration_min=45 if i % 2 == 0 else 60,
            deadline_day="Next Sunday",
            deadline_time="20:00",
            priority=(i % 5) + 1,
            cognitive_load=(i % 3) + 1,
            category="STUDY" if i % 2 == 0 else "HOMEWORK",
        )
        for i in range(50)
    ]
    for name in ["WSPT", "LST", "SCORED_GREEDY", "BACKTRACK", "HYBRID_ALNS"]:
        t0 = time.perf_counter()
        out, _ = resolve_solver(name).solve(profile, tasks)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert elapsed_ms <= 1000.0, f"{name} exceeded 1000ms at N=50: {elapsed_ms:.1f}ms"
        assert out.summary.hard_constraint_violations == 0
