"""
SmartSchedule UI v3 Backend Services (Web Presentation Adapter Layer).

Preserves Architectural Invariants INV-1..INV-6:
  - One-way dependency: `web` -> `src` and `web` -> `Testing_System`.
  - Never mutates input profiles/tasks/schedules.
  - Passes raw (unbuffered) tasks to `ScheduleEvaluator.evaluate()` so P4.1 never double-buffers.
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import config as app_config
from src.controller import ScheduleController
from src.grid_manager import TimeGridManager
from src.models import CommitmentsProfile, ScheduleBlock, ScheduleOutput, Task
from src.solvers.base_solver import BaseScheduler
from src.solvers.greedy_edf import GreedyEDFSolver
from src.solvers.greedy_wspt import GreedyWSPTSolver
from src.solvers.registry import SOLVER_REGISTRY
from src.solvers.scored_greedy import ScoredGreedySolver
from src.storage import list_completion_logs
from src.utils import MINUTES_PER_SLOT

from Testing_System.evaluator import ScheduleEvaluator
from Testing_System.evaluator.verdict_and_icee import rank_cross_solver_reports
from Testing_System.generator import InputGenerator
from Testing_System.schemas import EvaluationConfig, EvaluationReport, RegimeName


CANONICAL_SOLVERS_ORDER: List[Dict[str, str]] = [
    {"key": "EDF", "label": "EDF", "full_name": "Earliest Deadline First + First-Fit"},
    {"key": "WSPT", "label": "WSPT", "full_name": "Weighted Shortest Processing Time (Smith's Rule)"},
    {"key": "LST", "label": "LST", "full_name": "Dynamic Least Slack Time + Best-Fit"},
    {"key": "SCORED_GREEDY", "label": "SCORED_GREEDY", "full_name": "Hyperbolic Urgency × Priority + Circadian & Batching"},
    {"key": "BACKTRACK", "label": "BACKTRACK", "full_name": "Bounded Backtracking Branch & Bound"},
    {"key": "HYBRID_ALNS", "label": "HYBRID_ALNS", "full_name": "Hybrid Adaptive Large Neighborhood Search"},
]

REGIME_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "R1",
        "regime": RegimeName.LOOSE_FEASIBLE.value,
        "name": "R1 · Loose Feasible (Dễ / Dư sức chứa)",
        "tag": "LOOSE",
        "description": "Độ chặt thấp (ρ < 0.55), kiểm tra chuẩn nền G1=0, P1.1=100% và căn chỉnh sinh học.",
    },
    {
        "id": "R2",
        "regime": RegimeName.TIGHT_DEADLINE_CLUSTER.value,
        "name": "R2 · Tight Deadline Cluster (Sát hạn dồn cụm)",
        "tag": "TIGHT",
        "description": "Nhiều hạn chót chồng cụm với độ chặt cao (ρ ≈ 0.75–0.92), thử sức chống rớt hạn & Shock +25%.",
    },
    {
        "id": "R3",
        "regime": RegimeName.CIRCADIAN_SJL_AND_RECOVERY.value,
        "name": "R3 · Circadian SJL & Recovery (Cú đêm / Phục hồi)",
        "tag": "BIOLOGY",
        "description": "Hồ sơ sinh học Owl + lịch học bất đối xứng T2-T4-T6, kiểm tra tránh sớm pha & nghỉ >10p.",
    },
    {
        "id": "R4",
        "regime": RegimeName.PROCRASTINATION_ONSET_AND_DAG.value,
        "name": "R4 · Procrastination Onset & DAG (Chuỗi phụ thuộc)",
        "tag": "DAG",
        "description": "Các chuỗi depends_on đa tầng + cửa sổ rộng, kiểm tra chống dồn việc <10h sát hạn.",
    },
    {
        "id": "R5",
        "regime": RegimeName.OVERLOAD_INFEASIBLE.value,
        "name": "R5 · Overload Infeasible (Quá tải cấu trúc)",
        "tag": "OVERLOAD",
        "description": "Tổng nhu cầu vượt sức chứa khả dụng (ρ > 1.0), kiểm tra khả năng triage giữ điểm Priority cao.",
    },
    {
        "id": "R6",
        "regime": RegimeName.DISRUPTION_AND_OVERRUN_SERIES.value,
        "name": "R6 · Disruption & Overrun Series (Biến cố & Tràn giờ)",
        "tag": "RESILIENCE",
        "description": "Kèm sự cố đột xuất & tràn thời lượng (A/B/C), kiểm tra ổn định sửa lịch & bảo toàn PINNED.",
    },
]


def get_available_solvers() -> List[Dict[str, str]]:
    """Return canonical solvers actually registered in SOLVER_REGISTRY."""
    available: List[Dict[str, str]] = []
    for item in CANONICAL_SOLVERS_ORDER:
        if item["key"] in SOLVER_REGISTRY:
            available.append(dict(item))
    return available


def build_benchmark_glossary(cfg: Optional[EvaluationConfig] = None) -> Dict[str, Any]:
    """Structured Dev Glossary matching Testing_System schemas & lexicographic ranking."""
    c = cfg or EvaluationConfig()
    columns = [
        {
            "symbol": "Hạng (#1..#N)",
            "json_fields": ["lexicographic_rank"],
            "critical_threshold": "—",
            "warning_threshold": "—",
            "dev_meaning": "Thứ hạng tổng thể theo Thứ tự Từ Điển (Lexicographic Tuple), không trộn điểm tuyến tính mơ hồ.",
            "student_impact": "Cho biết thuật toán nào tạo ra lịch thực tế an toàn và bền vững nhất trên cùng input.",
        },
        {
            "symbol": "Verdict",
            "json_fields": ["verdict", "critical_breaches", "moderate_warnings"],
            "critical_threshold": "INVALID / SUBOPTIMAL_ALGORITHM_FAILURE",
            "warning_threshold": "FEASIBLE_BUT_LOW_PRODUCTIVITY / OVERLOAD_TRIAGE",
            "dev_meaning": "Kết luận cuối cùng từ cây quyết định Từ điển: >=1 lỗi CRITICAL hoặc >=2 WARNING sẽ hạ xuống LOW_PRODUCTIVITY.",
            "student_impact": "Tóm tắt nhanh lịch có sẵn sàng để sinh viên dùng ngay mà không quá tải hay bỏ sót deadline.",
        },
        {
            "symbol": "(G1)",
            "json_fields": ["gates.g1_total_violations", "gates.g1_violation_details"],
            "critical_threshold": "> 0 (Thẻ đỏ ngay lập tức -> INVALID)",
            "warning_threshold": "0",
            "dev_meaning": "Tổng vi phạm ràng buộc cứng H1–H5, start_after, trước NOW, sai thứ tự chunk hoặc xê dịch block PINNED.",
            "student_impact": "Bằng 0 nghĩa là lịch không đè giờ ngủ, không đè lớp học và không làm mất lịch đã ghim.",
        },
        {
            "symbol": "P1.1%",
            "json_fields": ["p1_value_timeliness.deadline_value_rate_pct", "p1_value_timeliness.unplaced_deadline_count"],
            "critical_threshold": "< 100% khi ρ_deadline <= 1.0 (SUBOPTIMAL)",
            "warning_threshold": "< 100% khi quá tải cấu trúc (OVERLOAD_TRIAGE)",
            "dev_meaning": "Phần trăm tổng điểm Priority của các task có deadline hoàn thành kịp hạn. Khi quá tải, thuật giữ P1.1% cao hơn sẽ thắng triage.",
            "student_impact": "Đảm bảo các bài tập/đồ án/kỳ thi quan trọng nhất đều kịp nộp trước hạn.",
        },
        {
            "symbol": "Shk25%",
            "json_fields": ["p4_robustness_stability.shock_results[0].survived_priority_pct", "p4_robustness_stability.true_buffer_task_pct"],
            "critical_threshold": f"< {c.critical_shock25_min_pct:.0f}%",
            "warning_threshold": f"< {c.moderate_shock25_min_pct:.0f}%",
            "dev_meaning": "Tỷ lệ điểm Priority còn kịp hạn nếu MỌI task đều làm lố +25% thời lượng thực tế (mô phỏng Planning Fallacy). Nếu thấp nghĩa là lịch xếp quá sát nhau hoặc thiếu đệm.",
            "student_impact": "Lịch có sức chống chịu tốt khi bài tập bất ngờ khó hơn dự tính mà không gây hiệu ứng domino trễ hạn.",
        },
        {
            "symbol": "Rec%",
            "json_fields": ["p2_cognitive_biology.heavy_recovery_rate_pct", "p2_cognitive_biology.max_uninterrupted_work_min"],
            "critical_threshold": "Thiếu nghỉ >10p (1 slot 15p) sau ca nặng (load=3)",
            "warning_threshold": "< 100% (chỉ dùng crunch tier khi sát hạn)",
            "dev_meaning": "Tỷ lệ các phiên nhận thức nặng (cognitive_load=3) có ít nhất 15 phút nghỉ phục hồi ngay sau đó (Albulescu et al. 2022).",
            "student_impact": "Giúp não bộ hồi phục sau ca học nặng, tránh kiệt sức và giảm hiệu suất các ca sau.",
        },
        {
            "symbol": "Adv / Pk%",
            "json_fields": ["p2_cognitive_biology.forced_phase_advance_count", "p2_cognitive_biology.heavy_peak_match_pct"],
            "critical_threshold": f"Adv > 0 hoặc Pk% < {c.critical_heavy_peak_min_pct:.0f}%",
            "warning_threshold": f"Pk% < {c.moderate_heavy_peak_min_pct:.0f}%",
            "dev_meaning": "Adv = số block nặng của cú đêm (Owl) bị ép học sáng 06–12h (energy=1) dù còn khe chiều/tối; Pk% = % thời lượng việc nặng nằm đúng giờ Peak (energy=3).",
            "student_impact": "Tránh học môn khó lúc buồn ngủ; đưa việc đòi hỏi tập trung sâu vào giờ tỉnh táo nhất.",
        },
        {
            "symbol": "<10h%",
            "json_fields": ["p1_value_timeliness.unjustified_last_10h_crowding_pct", "p1_value_timeliness.heavy_onset_delay_pct"],
            "critical_threshold": f"> {c.critical_last10h_crowding_max_pct:.0f}%",
            "warning_threshold": f"> {c.moderate_last10h_crowding_max_pct:.0f}%",
            "dev_meaning": "% khối lượng các task cửa sổ rộng bị dồn vào <10 giờ cuối trước hạn dù trước đó có khe trống năng lượng tương đương/cao hơn (Svartdal / Howell).",
            "student_impact": "Chống thói quen nước đến chân mới nhảy, chừa biên độ sửa bài nếu gặp lỗi phút chót.",
        },
        {
            "symbol": "Crn (d/a/m)",
            "json_fields": [
                "p3_sustainable_pacing.corne_lexicographic_vector",
                "p3_sustainable_pacing.heavy_day_overload_days",
                "p3_sustainable_pacing.adjacent_heavy_pairs",
                "p3_sustainable_pacing.meal_boundary_offenses",
            ],
            "critical_threshold": "So sánh từ điển 3 phần tử [d, a, m] càng nhỏ càng tốt",
            "warning_threshold": "d > 0 (>2 ca nặng/ngày) hoặc a > 0 (2 ca nặng sát nhau) hoặc m > 0 (kẹp bữa ăn)",
            "dev_meaning": "Vector phạt Corne et al. (1993): d = số ngày có >2 block nặng; a = số cặp block nặng liên tiếp; m = số lần kẹp bữa ăn giữa 2 block nặng.",
            "student_impact": "Tránh lịch học dồn nặng bất hợp lý trong 1 ngày hoặc ép học nặng ngay sát giờ ăn.",
        },
        {
            "symbol": "Ctx / Bch",
            "json_fields": ["p3_sustainable_pacing.context_switches", "p3_sustainable_pacing.batched_pairs"],
            "critical_threshold": "—",
            "warning_threshold": "Ctx cao làm tăng chi phí chuyển mạch ngữ cảnh",
            "dev_meaning": "Ctx = số lần đổi phân loại môn/category giữa 2 block gần nhau; Bch = số cặp block cùng loại được gom cụm (batching).",
            "student_impact": "Giữ mạch tư duy liền mạch, đỡ mất thời gian làm nóng lại đầu óc khi đổi môn liên tục.",
        },
        {
            "symbol": "Hab / Prf%",
            "json_fields": ["p1_value_timeliness.habit_value_rate_pct", "p2_cognitive_biology.preferred_window_match_pct"],
            "critical_threshold": "—",
            "warning_threshold": "Thấp khi thuật bỏ rơi thói quen hoặc phớt lờ preferred_window",
            "dev_meaning": "Hab% = tỷ lệ phiên thói quen (PersonalHabit) xếp được; Prf% = % thời lượng task có preferred_window nằm đúng buổi mong muốn.",
            "student_impact": "Tôn trọng thói quen sống (thể thao, đọc sách) và khung giờ học mong muốn của từng môn.",
        },
        {
            "symbol": "SJL / Std",
            "json_fields": ["p2_cognitive_biology.sjl_minutes", "p3_sustainable_pacing.daily_load_std_min"],
            "critical_threshold": "—",
            "warning_threshold": f"SJL > 30p (lệch pha ngày học/nghỉ) hoặc Std > {c.moderate_max_daily_load_std_min:.0f}p",
            "dev_meaning": "SJL = lệch pha tròn trung vị giờ tự học giữa ngày có lớp và ngày không lớp (Smarr & Schirmer 2018); Std = độ lệch chuẩn phút tự học giữa các ngày.",
            "student_impact": "Giữ đồng hồ sinh học ổn định cả tuần và phân bổ tải đều thay vì ngày quá nhàn, ngày quá nặng.",
        },
        {
            "symbol": "ms",
            "json_fields": ["diagnostics.execution_time_ms"],
            "critical_threshold": "> 2000ms (vượt SLA tương tác)",
            "warning_threshold": "> 1000ms",
            "dev_meaning": "Thời gian chạy thực tế của thuật toán trên lưới slot 15 phút (tie-breaker cuối cùng).",
            "student_impact": "Phản hồi gần như tức thì khi sinh viên thêm việc hoặc kéo thả chỉnh lịch.",
        },
    ]

    lexicographic_order = [
        {"rank": 1, "key": "G1 Violations (tăng dần)", "note": "Cổng #0 bắt buộc: G1 = 0 luôn thắng mọi lịch có lỗi cứng."},
        {"rank": 2, "key": "P1.1 Deadline Value Rate % (giảm dần)", "note": "Tối đa hóa tổng điểm Priority các việc có hạn chót hoàn thành kịp giờ."},
        {"rank": 3, "key": "P4.1 Shock@+25% Survived % (giảm dần)", "note": "Khả năng sống sót của lịch khi mọi công việc bị lố +25% thời lượng."},
        {"rank": 4, "key": "P2.2 Heavy Recovery Rate % (giảm dần)", "note": "Tỷ lệ phiên nhận thức nặng (load=3) có khoảng nghỉ phục hồi >= 15p."},
        {"rank": 5, "key": "P2.1 Forced Phase Advance Count (tăng dần)", "note": "Tránh ép cú đêm học nặng vào khung sáng energy=1 khi còn khe tốt hơn."},
        {"rank": 6, "key": "P2.1 Heavy Peak Match % (giảm dần)", "note": "Tỷ lệ việc nặng được đặt vào đúng khung giờ Peak (energy=3)."},
        {"rank": 7, "key": "P1.2 Unjustified <10h Crowding % (tăng dần)", "note": "Chống trì hoãn dồn việc vào <10 giờ cuối trước deadline."},
        {"rank": 8, "key": "P2.3 Social Jetlag |SJL| phút (tăng dần)", "note": "Giảm lệch pha giữa ngày có lớp và ngày không lớp."},
        {"rank": 9, "key": "P3.2 Corne Vector [>2/ngày, kề nhau, kẹp bữa] (tăng dần)", "note": "So sánh từ điển tránh dồn nặng cục bộ và kẹp giờ ăn."},
        {"rank": 10, "key": "P3.1 Daily Load Std phút (tăng dần)", "note": "San đều khối lượng học tập giữa các ngày hoạt động."},
        {"rank": 11, "key": "Execution Time ms (tăng dần)", "note": "Tiêu chí phân định cuối cùng khi mọi tiêu chí trên ngang nhau."},
    ]

    verdict_definitions = [
        {
            "label": "HIGH_PRODUCTIVITY",
            "short": "HIGH",
            "tone": "success",
            "meaning": "Đạt G1=0, không rơi deadline (khi khả thi), 0 lỗi CRITICAL và tối đa 1 cảnh báo WARNING — lịch tối ưu sẵn sàng sử dụng.",
        },
        {
            "label": "FEASIBLE_BUT_LOW_PRODUCTIVITY",
            "short": "LOW",
            "tone": "warning",
            "meaning": "Hợp lệ và đủ hạn (G1=0, P1.1=100%), nhưng vi phạm >=1 ngưỡng CRITICAL sức khỏe/sinh học hoặc >=2 WARNING.",
        },
        {
            "label": "OVERLOAD_TRIAGE",
            "short": "OVLD",
            "tone": "info",
            "meaning": "Đầu vào quá tải cấu trúc (ρ > 1.0) nên không thể xếp hết mọi việc; đánh giá thuật qua khả năng ưu tiên giữ P1.1% cao nhất.",
        },
        {
            "label": "SUBOPTIMAL_ALGORITHM_FAILURE",
            "short": "SUBOPT",
            "tone": "danger",
            "meaning": "Tổng giờ rảnh lý thuyết vẫn đủ (ρ <= 1.0) nhưng thuật toán vẫn làm rơi việc có hạn chót.",
        },
        {
            "label": "INVALID",
            "short": "INV",
            "tone": "danger",
            "meaning": "Vi phạm ràng buộc cứng G1 (trùng ngủ/lớp, quá hạn, gãy DAG hoặc làm mất block PINNED).",
        },
    ]

    return {
        "columns": columns,
        "lexicographic_order": lexicographic_order,
        "verdict_definitions": verdict_definitions,
    }


def evaluate_single_schedule(
    profile: CommitmentsProfile,
    raw_tasks: List[Task],
    schedule: ScheduleOutput,
    pinned_blocks: Optional[List[ScheduleBlock]] = None,
) -> Dict[str, Any]:
    """Run Tier 0 -> Tier 2 ScheduleEvaluator on raw tasks (never double-buffering)."""
    report = ScheduleEvaluator.evaluate(
        profile=profile,
        tasks=raw_tasks,
        schedule=schedule,
        input_pinned_blocks=pinned_blocks or None,
    )
    return report.model_dump()


def _extract_shock25(rep: EvaluationReport) -> float:
    for sr in rep.p4_robustness_stability.shock_results:
        if abs(sr.shock_pct - 25.0) < 1e-6:
            return sr.survived_priority_pct
    return rep.p4_robustness_stability.shock_results[0].survived_priority_pct if rep.p4_robustness_stability.shock_results else 100.0


def run_benchmark_all(
    profile: CommitmentsProfile,
    raw_tasks: List[Task],
    pinned_blocks: Optional[List[ScheduleBlock]],
    enrich_fn: Callable[[ScheduleOutput, Optional[CommitmentsProfile]], Dict[str, Any]],
) -> Dict[str, Any]:
    """Run and evaluate every available canonical solver on the same raw input."""
    solvers = get_available_solvers()
    reports: Dict[str, EvaluationReport] = {}
    schedules_by_solver: Dict[str, Dict[str, Any]] = {}

    for s_meta in solvers:
        key = s_meta["key"]
        out, _ = ScheduleController.solve_schedule(
            profile=profile.model_copy(deep=True),
            tasks=[t.model_copy(deep=True) for t in raw_tasks],
            algorithm=key,
            pinned_blocks=[b.model_copy(deep=True) for b in (pinned_blocks or [])] or None,
        )
        rep = ScheduleEvaluator.evaluate(
            profile=profile,
            tasks=raw_tasks,
            schedule=out,
            input_pinned_blocks=pinned_blocks or None,
        )
        reports[key] = rep
        enriched = enrich_fn(out, profile)
        enriched["evaluation"] = rep.model_dump()
        schedules_by_solver[key] = enriched

    ranked_entries = rank_cross_solver_reports(reports)
    ranking_rows: List[Dict[str, Any]] = []
    for entry in ranked_entries:
        rep = reports[entry.solver_name]
        daily_loads = rep.p3_sustainable_pacing.daily_load_minutes or [0]
        row = entry.model_dump()
        row.update(
            {
                "solver_key": entry.solver_name,
                "p1_unplaced_deadline_count": rep.p1_value_timeliness.unplaced_deadline_count,
                "p1_habit_rate_pct": rep.p1_value_timeliness.habit_value_rate_pct,
                "p2_preferred_window_pct": rep.p2_cognitive_biology.preferred_window_match_pct,
                "p2_max_uninterrupted_min": rep.p2_cognitive_biology.max_uninterrupted_work_min,
                "p2_sjl_direction": rep.p2_cognitive_biology.sjl_direction,
                "p3_context_switches": rep.p3_sustainable_pacing.context_switches,
                "p3_batched_pairs": rep.p3_sustainable_pacing.batched_pairs,
                "p3_max_daily_study_min": max(daily_loads) if daily_loads else 0,
                "p4_true_buffer_pct": rep.p4_robustness_stability.true_buffer_task_pct,
                "rho_total": rep.gates.rho_total,
                "rho_deadline": rep.gates.rho_deadline,
                "is_structurally_overloaded": rep.gates.is_structurally_overloaded,
                "verdict_reasons_vi": list(rep.verdict_reasons_vi),
                "critical_breaches": list(rep.critical_breaches),
                "moderate_warnings": list(rep.moderate_warnings),
                "d1_icee_critiques": [c.model_dump() for c in rep.d1_icee_critiques],
                "diagnostics": rep.diagnostics.model_dump(),
            }
        )
        ranking_rows.append(row)

    glossary = build_benchmark_glossary()
    return {
        "solvers": solvers,
        "ranking": ranking_rows,
        "schedules_by_solver": schedules_by_solver,
        "column_glossary": glossary["columns"],
        "lexicographic_order": glossary["lexicographic_order"],
        "verdict_definitions": glossary["verdict_definitions"],
    }


def _compute_descendant_counts(tasks: List[Task]) -> Dict[str, int]:
    """Count transitive downstream dependents for each task in the depends_on DAG."""
    children: Dict[str, List[str]] = defaultdict(list)
    ids = {t.task_id for t in tasks}
    for t in tasks:
        for dep in t.depends_on or []:
            if dep in ids:
                children[dep].append(t.task_id)

    counts: Dict[str, int] = {}
    for t in tasks:
        visited = set()
        q = deque(children.get(t.task_id, []))
        while q:
            cur = q.popleft()
            if cur in visited or cur == t.task_id:
                continue
            visited.add(cur)
            for nxt in children.get(cur, []):
                if nxt not in visited:
                    q.append(nxt)
        counts[t.task_id] = len(visited)
    return counts


def compute_solver_weights(
    profile: CommitmentsProfile,
    raw_tasks: List[Task],
    pinned_blocks: Optional[List[ScheduleBlock]] = None,
) -> Dict[str, Any]:
    """Inspect all effective per-task weights, grid density, circadian profile, and config constants."""
    all_tasks = ScheduleController.expand_personal_habits(profile, raw_tasks)
    buffered_tasks = ScheduleController.apply_estimate_buffer(profile, all_tasks)
    week_start_iso = profile.planning_week_start
    now_slot = BaseScheduler.resolve_now_slot(profile)
    horizon_slots = BaseScheduler.resolve_horizon_slots(
        buffered_tasks,
        week_start_iso=week_start_iso,
        horizon_days=getattr(profile, "horizon_days", 7),
    )

    grid = TimeGridManager(total_slots=horizon_slots)
    grid.initialize_from_profile(profile)
    # Count free and usable free slots from now_slot onward
    free_slots = sum(1 for s in range(now_slot, horizon_slots) if grid.is_slot_free(s))
    usable_grid = grid.clone()
    usable_grid.mark_dead_zones_as_rest()
    usable_free_slots = sum(1 for s in range(now_slot, horizon_slots) if usable_grid.is_slot_free(s))

    total_planned_slots = sum(t.get_planned_slots() for t in buffered_tasks)
    deadline_planned_slots = sum(
        t.get_planned_slots()
        for t in buffered_tasks
        if t.resolve_deadline_slot(week_start_iso=week_start_iso) is not None
    )
    rho_total = round(total_planned_slots / float(max(1, usable_free_slots)), 3)
    rho_deadline = round(deadline_planned_slots / float(max(1, usable_free_slots)), 3)

    descendants = _compute_descendant_counts(buffered_tasks)
    per_task_weights: List[Dict[str, Any]] = []
    for idx, t in enumerate(buffered_tasks):
        planned_min = t.get_planned_duration_min()
        planned_slots = t.get_planned_slots()
        d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
        s_after_slot = t.resolve_start_after_slot(week_start_iso=week_start_iso)
        eff_earliest = max(now_slot, s_after_slot) if s_after_slot is not None else now_slot

        slack_hours: Optional[float] = None
        dynamic_slack_slots: Optional[int] = None
        if d_slot is not None:
            slack_min = (d_slot - now_slot) * MINUTES_PER_SLOT - planned_min
            slack_hours = round(slack_min / 60.0, 2)
            dynamic_slack_slots = d_slot - eff_earliest - planned_slots

        urgency_score, _ = ScoredGreedySolver.compute_task_score(t, now_slot, week_start_iso)
        smith_ratio = round(float(t.priority) / float(max(MINUTES_PER_SLOT, planned_min)), 4)
        edf_has_dl, edf_d_slot, edf_neg_p, _ = GreedyEDFSolver._edf_sort_key(idx, t, now_slot, week_start_iso)

        per_task_weights.append(
            {
                "task_id": t.task_id,
                "title": t.title or t.task_id,
                "category": t.category,
                "duration_min": t.duration_min,
                "buffer_multiplier": round(float(t.buffer_multiplier), 2),
                "planned_duration_min": planned_min,
                "planned_slots": planned_slots,
                "priority": t.priority,
                "cognitive_load": t.cognitive_load,
                "preferred_window": t.preferred_window or "ANYTIME",
                "is_splittable": t.is_splittable,
                "work_rhythm": t.work_rhythm or "CUSTOM",
                "min_chunk_min": t.min_chunk_min,
                "max_chunk_min": t.max_chunk_min,
                "deadline_label": t.format_deadline_label(week_start_iso=week_start_iso),
                "deadline_slot": d_slot,
                "slack_hours": slack_hours,
                "descendant_count": descendants.get(t.task_id, 0),
                "urgency_score": round(float(urgency_score), 4),
                "smith_ratio": smith_ratio,
                "dynamic_slack_slots": dynamic_slack_slots,
                "edf_key": f"({edf_has_dl}, {edf_d_slot if d_slot is not None else '∞'}, {edf_neg_p})",
            }
        )

    energy_prof = profile.get_energy_profile()
    profile_weights = {
        "now_slot": now_slot,
        "horizon_days": profile.horizon_days,
        "horizon_slots": horizon_slots,
        "total_tasks_expanded": len(buffered_tasks),
        "total_planned_slots": total_planned_slots,
        "deadline_planned_slots": deadline_planned_slots,
        "free_slots": free_slots,
        "usable_free_slots": usable_free_slots,
        "rho_total": rho_total,
        "rho_deadline": rho_deadline,
        "is_structurally_overloaded": rho_deadline > 1.0 or rho_total > 1.0,
        "focus_preference": energy_prof.focus_preference,
        "circadian_curve": {
            "morning_06_12": energy_prof.morning_level,
            "afternoon_12_18": energy_prof.afternoon_level,
            "evening_18_24": energy_prof.evening_level,
            "night_00_06": energy_prof.night_level,
        },
        "buffer_mode": profile.buffer_mode,
        "estimate_habit": profile.estimate_habit,
        "alpha_light": profile.alpha_light,
        "alpha_heavy": profile.alpha_heavy,
    }

    config_constants = {
        "ALPHA_LIGHT_DEFAULT": app_config.ALPHA_LIGHT_DEFAULT,
        "ALPHA_HEAVY_DEFAULT": app_config.ALPHA_HEAVY_DEFAULT,
        "ALPHA_GRID_RANGE": f"{app_config.ALPHA_GRID_MIN:.2f} .. {app_config.ALPHA_GRID_MAX:.2f} (step {app_config.ALPHA_GRID_STEP:.2f})",
        "MAX_DEEP_WORK_MIN": app_config.MAX_DEEP_WORK_MIN,
        "MIN_DEEP_WORK_BREAK_TRIGGER_MIN": app_config.MIN_DEEP_WORK_BREAK_TRIGGER_MIN,
        "MANDATORY_REST_SLOTS": app_config.MANDATORY_REST_SLOTS,
        "CATEGORY_BATCH_BONUS": app_config.CATEGORY_BATCH_BONUS,
        "CONTEXT_SWITCH_PENALTY": app_config.CONTEXT_SWITCH_PENALTY,
        "DEAD_ZONE_MAX_SLOTS": app_config.DEAD_ZONE_MAX_SLOTS,
        "MIN_SLEEP_HOURS": app_config.MIN_SLEEP_HOURS,
        "GAMMA_URGENCY_HOURS": app_config.GAMMA_URGENCY_HOURS,
        "OVERDUE_URGENCY_CAP": app_config.OVERDUE_URGENCY_CAP,
        "HABIT_BASE_URGENCY": app_config.HABIT_BASE_URGENCY,
        "STABILITY_TARGET_PCT": app_config.STABILITY_TARGET_PCT,
        "BACKTRACK_MAX_CANDIDATES_PER_TASK": app_config.BACKTRACK_MAX_CANDIDATES_PER_TASK,
        "BACKTRACK_MAX_NODES": app_config.BACKTRACK_MAX_NODES,
        "EARLY_EXTENSION_ALERT_MAX_HOURS": app_config.EARLY_EXTENSION_ALERT_MAX_HOURS,
    }

    weights_glossary = [
        {
            "name": "buffer_multiplier (α)",
            "formula": f"COGNITIVE_LOAD: {app_config.ALPHA_LIGHT_DEFAULT} (L1/2), {app_config.ALPHA_HEAVY_DEFAULT} (L3) | HABIT: 1.0 / 1.15 / 1.30",
            "definition_vi": "Hệ số nhân phòng vệ Planning Fallacy để tính planned_duration_min = RoundUp_15(duration_min × α).",
            "decision_impact_vi": "Dự trữ thêm thời gian trực tiếp trong block giúp chống tràn giờ khi làm bài thực tế (tăng Shock@+25%).",
        },
        {
            "name": "Urgency Score (SCORED_GREEDY)",
            "formula": f"exp(-max(0, slack_hours) / {app_config.GAMMA_URGENCY_HOURS}) × priority (quá hạn trần {app_config.OVERDUE_URGENCY_CAP}; habit = {app_config.HABIT_BASE_URGENCY})",
            "definition_vi": "Điểm khẩn cấp hàm mũ nhân tầm quan trọng. Còn 48h -> e^-2 ≈ 0.135; còn 24h -> 0.368; còn 0h -> 1.00.",
            "decision_impact_vi": "Cân bằng giữa bài sắp đến hạn và bài điểm cao còn xa hạn để quyết định thứ tự đưa lên lịch.",
        },
        {
            "name": "Smith Ratio (WSPT)",
            "formula": "priority / planned_duration_min",
            "definition_vi": "Mật độ giá trị ưu tiên trên mỗi phút thực hiện theo quy tắc Smith.",
            "decision_impact_vi": "WSPT xếp việc ngắn mà điểm cao lên trước để tối đa hóa tổng giá trị hoàn thành sớm khi bị quá tải.",
        },
        {
            "name": "Dynamic Slack (LST)",
            "formula": "deadline_slot − max(now_slot, start_after_slot) − planned_slots",
            "definition_vi": "Số slot 15 phút dư ra tối đa mà công việc có thể trì hoãn trước khi chắc chắn trễ hạn.",
            "decision_impact_vi": "LST luôn chọn công việc có độ dư nhỏ nhất tại thời điểm hiện tại để tránh bỏ sót deadline gấp.",
        },
        {
            "name": "EDF Key (EDF)",
            "formula": "(has_no_deadline, deadline_slot, -priority, idx)",
            "definition_vi": "Khóa sắp xếp cổ điển: việc có hạn chót sớm nhất đứng trước, hòa thì ưu tiên priority cao hơn.",
            "decision_impact_vi": "Đảm bảo tốc độ cực nhanh và tối ưu cho trường hợp 1 tài nguyên không có trọng số sinh học.",
        },
        {
            "name": "rho_total / rho_deadline (G2)",
            "formula": "planned_slots / usable_free_slots",
            "definition_vi": "Tỷ lệ tải giữa tổng nhu cầu học và tổng slot trống khả dụng (đã trừ ngủ, lớp cố định và dead-zone <30p).",
            "decision_impact_vi": "Khi ρ > 1.0 hệ thống nhận diện quá tải cấu trúc (OVERLOAD_TRIAGE) và kích hoạt gợi ý giải cứu O1–O4.",
        },
        {
            "name": "CircadianEnergyProfile (E1..E3)",
            "formula": "MORNING(3,2,1,1) · AFTERNOON(2,3,1,1) · EVENING(1,2,3,2) · BALANCED(3,2,2,1)",
            "definition_vi": "Mức tỉnh táo theo 4 buổi (Sáng 06–12h, Chiều 12–18h, Tối 18–24h, Đêm 00–06h): 3=Peak, 2=Vừa, 1=Thấp.",
            "decision_impact_vi": "SCORED_GREEDY & BACKTRACK ưu tiên đặt task load=3 vào khung E3 và tránh khung E1.",
        },
        {
            "name": "MANDATORY_REST_SLOTS & DEAD_ZONE",
            "formula": f"Rest = {app_config.MANDATORY_REST_SLOTS} slot (15p) sau >= {app_config.MIN_DEEP_WORK_BREAK_TRIGGER_MIN}p / load=3; Dead-zone <= {app_config.DEAD_ZONE_MAX_SLOTS} slot (<30p)",
            "definition_vi": "Khoảng nghỉ phục hồi bắt buộc và quy tắc chuyển khe vụn <30p thành REST.",
            "decision_impact_vi": "Ngăn phân mảnh lịch vụn vặt và bảo toàn tỷ lệ phục hồi nhận thức (P2.2).",
        },
        {
            "name": "CATEGORY_BATCH_BONUS / CONTEXT_SWITCH_PENALTY",
            "formula": f"+{app_config.CATEGORY_BATCH_BONUS} thưởng cùng nhóm / −{app_config.CONTEXT_SWITCH_PENALTY} phạt đổi nhóm",
            "definition_vi": "Trọng số gom cụm môn cùng phân loại và phạt khi nhảy liên tục giữa các môn khác nhau.",
            "decision_impact_vi": "Giảm số lần chuyển ngữ cảnh (context_switches) trên thanh lịch hằng ngày.",
        },
        {
            "name": "BACKTRACK_MAX_NODES / CANDIDATES",
            "formula": f"max_nodes = {app_config.BACKTRACK_MAX_NODES}, max_candidates/task = {app_config.BACKTRACK_MAX_CANDIDATES_PER_TASK}",
            "definition_vi": "Ngân sách nhánh tìm kiếm của thuật toán Backtracking Branch & Bound.",
            "decision_impact_vi": "Giữ thời gian tìm kiếm nằm dưới ngưỡng tương tác < 2s ngay cả khi tuần dày task.",
        },
    ]

    return {
        "per_task_weights": per_task_weights,
        "profile_weights": profile_weights,
        "config_constants": config_constants,
        "weights_glossary": weights_glossary,
    }


def get_test_suites_catalog(presets_dict: Dict[str, Any], scenarios_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return unified catalog across Presets, Scenarios T01-T10, and Testing_System Regimes R1-R6."""
    presets = [
        {
            "id": pid,
            "name": p["name"],
            "task_count": len(p.get("tasks") or []),
            "fixed_count": len((p.get("commitments") or {}).get("fixed_events") or []),
        }
        for pid, p in presets_dict.items()
    ]
    return {
        "presets": presets,
        "scenarios": scenarios_list,
        "regimes": REGIME_CATALOG,
    }


def load_test_suite(
    source: str,
    suite_id: str,
    seed: int,
    presets_dict: Dict[str, Any],
    scenarios_dir: Path,
) -> Dict[str, Any]:
    """Load any test suite from Preset, Scenario T01-T10, or Testing_System Regime R1-R6."""
    src_clean = (source or "preset").strip().lower()
    sid = (suite_id or "").strip()

    if src_clean == "preset":
        key = sid.lower()
        if key not in presets_dict:
            raise ValueError(f"Preset '{suite_id}' not found.")
        p = presets_dict[key]
        return {
            "source": "preset",
            "id": key,
            "name": p["name"],
            "description": f"Preset mẫu sẵn ({len(p['tasks'])} tasks).",
            "commitments": p["commitments"],
            "tasks": p["tasks"],
            "pinned_blocks": [],
            "disruption": None,
            "overrun_config": None,
            "metadata": {"source": "preset", "preset_id": key},
        }

    if src_clean == "scenario":
        key = sid.lower()
        if scenarios_dir.exists():
            for path in sorted(scenarios_dir.glob("*.json")):
                raw = json.loads(path.read_text(encoding="utf-8"))
                raw_sid = str(raw.get("scenario_id", "")).strip().lower()
                if key in (raw_sid, path.stem.lower(), path.name.lower()):
                    return {
                        "source": "scenario",
                        "id": raw.get("scenario_id", path.stem.upper()),
                        "name": f"{raw.get('scenario_id', path.stem.upper())} — {raw.get('name', path.stem)}",
                        "description": raw.get("description", ""),
                        "commitments": raw.get("commitments", {}),
                        "tasks": raw.get("tasks", []),
                        "pinned_blocks": raw.get("pinned_blocks", []),
                        "disruption": raw.get("disruption"),
                        "overrun_config": raw.get("overrun_config"),
                        "metadata": {
                            "source": "scenario",
                            "scenario_id": raw.get("scenario_id"),
                            "expected_status": raw.get("expected_status"),
                        },
                    }
        raise ValueError(f"Scenario '{suite_id}' not found.")

    if src_clean == "regime":
        # Match R1..R6 or full RegimeName value
        regime_enum: Optional[RegimeName] = None
        for entry in REGIME_CATALOG:
            if sid.upper() in (entry["id"], entry["regime"]):
                regime_enum = RegimeName(entry["regime"])
                break
        if regime_enum is None:
            raise ValueError(f"Unknown regime '{suite_id}'. Use R1..R6.")

        bundle = InputGenerator.generate(regime_enum, seed=int(seed))
        disruption_dict = None
        overrun_dict = None
        if bundle.regime6_suite is not None:
            disruption_dict = bundle.regime6_suite.level_a_single_disruption.model_dump()
            overrun_dict = {
                "task_id": bundle.regime6_suite.level_b_overrun_task_id,
                "overrun_pct": bundle.regime6_suite.level_b_overrun_pct,
            }
        return {
            "source": "regime",
            "id": sid.upper(),
            "name": f"{sid.upper()} (seed={seed}) · {bundle.metadata.chronotype}",
            "description": bundle.metadata.notes or f"Sinh tự động từ Testing_System InputGenerator ({regime_enum.value}).",
            "commitments": bundle.profile.model_dump(),
            "tasks": [t.model_dump() for t in bundle.tasks],
            "pinned_blocks": [b.model_dump() for b in bundle.pinned_blocks],
            "disruption": disruption_dict,
            "overrun_config": overrun_dict,
            "metadata": bundle.metadata.model_dump(),
        }

    raise ValueError(f"Unsupported test suite source '{source}'.")


def _parse_ics_dt(raw: str) -> Optional[datetime]:
    cleaned = raw.strip().upper().rstrip("Z")
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M", "%Y%m%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def parse_ics_content(ics_text: str) -> Dict[str, Any]:
    """Parse standard iCalendar (.ics) VEVENT entries into previewable FixedEvents & Tasks."""
    if not ics_text or "BEGIN:VEVENT" not in ics_text:
        raise ValueError("Tệp .ics không chứa sự kiện VEVENT hợp lệ.")

    # Unfold folded iCal lines (RFC 5545)
    unfolded = re.sub(r"\r?\n[ \t]", "", ics_text)
    events_raw = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", unfolded, flags=re.DOTALL)
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    rrule_map = {"MO": "Monday", "TU": "Tuesday", "WE": "Wednesday", "TH": "Thursday", "FR": "Friday", "SA": "Saturday", "SU": "Sunday"}

    fixed_events: List[Dict[str, Any]] = []
    tasks: List[Dict[str, Any]] = []

    for idx, block in enumerate(events_raw, start=1):
        fields: Dict[str, str] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            key_base = k.split(";", 1)[0].strip().upper()
            fields[key_base] = v.strip()

        summary = fields.get("SUMMARY", f"Sự kiện #{idx}").replace("\\,", ",").replace("\\n", " ")
        dtstart = _parse_ics_dt(fields.get("DTSTART", ""))
        dtend = _parse_ics_dt(fields.get("DTEND", "")) if fields.get("DTEND") else None
        if dtstart is None:
            continue

        rrule = fields.get("RRULE", "")
        is_deadline_like = (dtend is None) or (dtend <= dtstart) or any(
            kw in summary.lower() for kw in ("due", "deadline", "nộp", "bài tập", "assignment", "quiz", "exam", "thi")
        )

        if is_deadline_like and not rrule:
            due_dt = dtend or dtstart
            tasks.append(
                {
                    "task_id": f"ICS_T{idx:02d}",
                    "title": summary,
                    "duration_min": 90,
                    "deadline_day": weekday_names[due_dt.weekday()],
                    "deadline_time": due_dt.strftime("%H:%M") if (due_dt.hour or due_dt.minute) else "23:59",
                    "due": due_dt.strftime("%Y-%m-%dT%H:%M:00+07:00"),
                    "priority": 4 if any(w in summary.lower() for w in ("exam", "thi", "final", "midterm")) else 3,
                    "category": "EXAM" if any(w in summary.lower() for w in ("exam", "thi")) else "ASSIGNMENT",
                    "cognitive_load": 2,
                    "is_splittable": True,
                    "min_chunk_min": 45,
                    "max_chunk_min": 90,
                }
            )
        else:
            end_dt = dtend if (dtend and dtend > dtstart) else (dtstart + timedelta(hours=1))
            days: Any = weekday_names[dtstart.weekday()]
            byday_match = re.search(r"BYDAY=([A-Z,]+)", rrule)
            if byday_match:
                parsed_days = [rrule_map[d] for d in byday_match.group(1).split(",") if d in rrule_map]
                if parsed_days:
                    days = parsed_days if len(parsed_days) > 1 else parsed_days[0]

            low_title = summary.lower()
            cat = "ACADEMIC_CLASS"
            if any(w in low_title for w in ("meal", "lunch", "dinner", "breakfast", "ăn")):
                cat = "MEAL"
            elif any(w in low_title for w in ("work", "shift", "làm thêm", "part-time")):
                cat = "WORK"
            elif any(w in low_title for w in ("meeting", "clb", "họp", "club")):
                cat = "MEETING"

            fixed_events.append(
                {
                    "event_id": f"ICS_EV{idx:02d}",
                    "title": summary,
                    "day_of_week": days,
                    "start_time": dtstart.strftime("%H:%M"),
                    "end_time": end_dt.strftime("%H:%M"),
                    "category": cat,
                }
            )

    return {
        "total_parsed": len(fixed_events) + len(tasks),
        "fixed_events": fixed_events,
        "tasks": tasks,
    }


def compute_calibration_summary(workspace_id: str = "default") -> Dict[str, Any]:
    """Summarize historical M7 actual-vs-estimated completion logs for EWMA alpha calibration."""
    rows = list_completion_logs(workspace_id=workspace_id, limit=200)
    count = len(rows)
    if count == 0:
        return {
            "workspace_id": workspace_id,
            "sample_count": 0,
            "ready_for_calibration": False,
            "ewma_ratio": None,
            "mean_ratio": None,
            "recommended_alpha": None,
            "recommended_habit": None,
        }

    ratios = [
        float(r.get("actual_duration_min", 60)) / float(max(1, int(r.get("estimated_duration_min", 60))))
        for r in rows
    ]
    # Compute EWMA (oldest -> newest)
    ewma = ratios[-1]
    for r in reversed(ratios[:-1]):
        ewma = 0.35 * r + 0.65 * ewma
    mean_r = sum(ratios) / float(count)
    rec_alpha = round(max(1.0, min(1.6, ewma)), 2)
    rec_habit = "OFTEN" if rec_alpha >= 1.25 else ("SOMETIMES" if rec_alpha >= 1.10 else "RARELY")

    return {
        "workspace_id": workspace_id,
        "sample_count": count,
        "ready_for_calibration": count >= 5,
        "ewma_ratio": round(ewma, 3),
        "mean_ratio": round(mean_r, 3),
        "recommended_alpha": rec_alpha,
        "recommended_habit": rec_habit,
    }
