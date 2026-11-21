"""
SmartSchedule Web Layer — curated "showcase" comparison tables for the 6 solvers.

Layer 4 only (imported by `web/api.py`; never imported by `src/` or `Testing_System/`).
The catalog of every generated family — Regimes R1..R6 × seed × horizon and FuzzGenerator v2
tiers × seed — lives in `web/v3_services.py` next to the other test suites.

A handful of generated cases where the solvers produce visibly different schedules are run and
ranked; each gets a data-driven Vietnamese explanation placed under its table (who won, at which
lexicographic level, and how wide the spread is).

All numbers come from `ScheduleEvaluator.evaluate()` + `rank_cross_solver_reports()`; the
explanation text is generated from those numbers only (no hand-written claims about results).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from smartschedule.core.controller import ScheduleController
from smartschedule.api.v3_services import (  # also puts the repo root on sys.path
    FUZZ_ARCHETYPE_VI,
    generate_testing_bundle,
    get_available_solvers,
)

from Testing_System.evaluator import ScheduleEvaluator
from Testing_System.evaluator.verdict_and_icee import VERDICT_TIER_ORDER, rank_cross_solver_reports
from Testing_System.generator.input_generator import GeneratedCaseBundle
from Testing_System.schemas import EvaluationConfig, EvaluationReport


def bundle_title(source: str, suite_id: str, bundle: GeneratedCaseBundle) -> str:
    m = bundle.metadata
    if source == "fuzz":
        arch = FUZZ_ARCHETYPE_VI.get(m.persona_archetype or "", m.persona_archetype or "?")
        return f"FUZZ[{m.fuzz_tier} · {arch}] seed={m.seed} · {m.horizon_days} ngày"
    return f"{suite_id.upper()} seed={m.seed} · {m.horizon_days} ngày · {m.chronotype}"


# ---------------------------------------------------------------------------
# 2. Lexicographic levels (mirror of verdict_and_icee.rank_cross_solver_reports)
# ---------------------------------------------------------------------------

LEX_LEVELS: List[Dict[str, str]] = [
    {"code": "G1", "name": "Cổng #0 · Luật cứng (G1)", "short": "lỗi luật cứng"},
    {"code": "SLA", "name": "Cổng #0 · Trần tốc độ 1000ms", "short": "vượt trần tốc độ"},
    {"code": "#1", "name": "#1 QUALITY-TIER (Verdict)", "short": "nhóm chất lượng (Verdict)"},
    {"code": "#2", "name": "#2 DEADLINE-VAL (P1.1%)", "short": "điểm việc kịp hạn P1.1"},
    {"code": "#3", "name": "#3 SHOCK-SAFE (Shk25, bậc 5%)", "short": "đệm chịu sốc +25%"},
    {"code": "#4", "name": "#4 BREAK-SAFE (nghỉ / chuỗi học / đệm lớp)", "short": "nghỉ phục hồi & chống học thông"},
    {"code": "#5", "name": "#5 BIO-SYNC (ngược nhịp / giờ đỉnh)", "short": "khớp nhịp sinh học"},
    {"code": "#6", "name": "#6 NO-CRAM (<10h%, bậc 5%)", "short": "chống dồn sát hạn <10h"},
    {"code": "#7", "name": "#7 DAILY-CAP (ca nặng / trần ngày)", "short": "trần tải ngày"},
    {"code": "#8", "name": "#8 FOCUS-FLOW (đổi ngữ cảnh)", "short": "số lần đổi ngữ cảnh"},
    {"code": "#9", "name": "#9 USER-PREF (thói quen / giờ riêng)", "short": "giữ thói quen & giờ riêng"},
    {"code": "#10", "name": "#10 PACE-BALANCE (SJL / độ lệch tải)", "short": "đều tải tuần & lệch pha"},
]


def _shock(rep: EvaluationReport, pct: float) -> float:
    for sr in rep.p4_robustness_stability.shock_results:
        if abs(sr.shock_pct - pct) < 1e-6:
            return float(sr.survived_priority_pct)
    return 100.0


def lexicographic_key(rep: EvaluationReport, cfg: Optional[EvaluationConfig] = None) -> Tuple:
    """
    Same 12-component key as `rank_cross_solver_reports` (verdict_and_icee.py `lex_key`).
    The checker does not expose its key, so it is mirrored here only to *explain* which level
    separated two neighbours; `test_showcase_lex_key_matches_official_ranking` guards drift.
    """
    c = cfg or EvaluationConfig()
    p1, p2, p3 = rep.p1_value_timeliness, rep.p2_cognitive_biology, rep.p3_sustainable_pacing
    rec = p2.heavy_recovery_rate_pct
    ach = p2.achievable_heavy_peak_match_pct
    sjl_eff = 90.0 if p2.sjl_neutral_unpaired else (p2.sjl_minutes if p2.sjl_minutes is not None else 0.0)
    hab = p1.habit_value_rate_pct
    pref = p2.preferred_window_match_pct
    return (
        rep.gates.g1_total_violations,
        1 if rep.diagnostics.execution_time_ms > c.max_exec_ms_sla else 0,
        VERDICT_TIER_ORDER.get(rep.verdict, 9),
        -p1.deadline_value_rate_pct,
        -int(_shock(rep, 25.0) // 5) * 5,
        (
            -int((rec if rec is not None else 100.0) // 5) * 5,
            max(0, p2.max_multi_block_streak_l2_min - 90) // 30,
            p2.post_class_buffer_violations,
        ),
        (p2.off_peak_heavy_mismatch_count, -int((ach if ach is not None else 100.0) // 10) * 10),
        int(p1.unjustified_last_10h_crowding_pct // 5) * 5,
        (
            p3.heavy_day_overload_days,
            max(0, p3.max_daily_total_min - c.moderate_max_daily_total_min) // 30,
            p3.adjacent_heavy_pairs,
            p3.meal_boundary_offenses_l2,
        ),
        p3.focus_context_switches,
        (-int((hab if hab is not None else 100.0) // 10) * 10, -int((pref if pref is not None else 100.0) // 10) * 10),
        (int(sjl_eff // 30) * 30, int(p3.total_daily_load_std_min // 30) * 30),
    )


# ---------------------------------------------------------------------------
# 3. Comparison table + data-driven explanation
# ---------------------------------------------------------------------------

VERDICT_SHORT = {
    "HIGH_PRODUCTIVITY": "HIGH",
    "FEASIBLE_BUT_LOW_PRODUCTIVITY": "LOW",
    "OVERLOAD_TRIAGE": "OVLD",
    "SUBOPTIMAL_ALGORITHM_FAILURE": "SUBOPT",
    "INVALID": "INV",
}


def _row(solver: str, rank: int, rep: EvaluationReport) -> Dict[str, Any]:
    p1, p2, p3 = rep.p1_value_timeliness, rep.p2_cognitive_biology, rep.p3_sustainable_pacing
    return {
        "solver_key": solver,
        "rank": rank,
        "verdict": rep.verdict.value,
        "g1": rep.gates.g1_total_violations,
        "p1_pct": round(p1.deadline_value_rate_pct, 1),
        "shock25_pct": round(_shock(rep, 25.0), 1),
        "recovery_pct": None if p2.heavy_recovery_rate_pct is None else round(p2.heavy_recovery_rate_pct, 1),
        "max_streak_min": p2.max_multi_block_streak_l2_min,
        "off_peak": p2.off_peak_heavy_mismatch_count,
        "peak_pct": None if p2.achievable_heavy_peak_match_pct is None else round(p2.achievable_heavy_peak_match_pct, 1),
        "cram_pct": round(p1.unjustified_last_10h_crowding_pct, 1),
        "max_day_min": p3.max_daily_total_min,
        "heavy_overload_days": p3.heavy_day_overload_days,
        "ctx": p3.focus_context_switches,
        "habit_pct": None if p1.habit_value_rate_pct is None else round(p1.habit_value_rate_pct, 1),
        "sjl_min": None if p2.sjl_minutes is None else round(p2.sjl_minutes),
        "std_min": round(p3.total_daily_load_std_min),
        "crit": len(rep.critical_breaches),
        "warn": len(rep.moderate_warnings),
        "critical_breaches": list(rep.critical_breaches),
        "exec_ms": round(rep.diagnostics.execution_time_ms, 1),
    }


def _v(x: Any, unit: str = "") -> str:
    return "—" if x is None else f"{x}{unit}"


def _fmt_level_values(level_idx: int, a: EvaluationReport, b: EvaluationReport) -> str:
    ra, rb = _row("a", 0, a), _row("b", 0, b)
    if level_idx == 0:
        return f"G1 {ra['g1']} vs {rb['g1']}"
    if level_idx == 1:
        return f"{ra['exec_ms']}ms vs {rb['exec_ms']}ms"
    if level_idx == 2:
        return f"{VERDICT_SHORT.get(ra['verdict'], ra['verdict'])} vs {VERDICT_SHORT.get(rb['verdict'], rb['verdict'])}"
    if level_idx == 3:
        return f"P1.1 {ra['p1_pct']}% vs {rb['p1_pct']}%"
    if level_idx == 4:
        return f"Shk25 {ra['shock25_pct']}% vs {rb['shock25_pct']}%"
    if level_idx == 5:
        return (
            f"nghỉ {_v(ra['recovery_pct'], '%')} / chuỗi {ra['max_streak_min']}p vs "
            f"{_v(rb['recovery_pct'], '%')} / {rb['max_streak_min']}p"
        )
    if level_idx == 6:
        return (
            f"ngược nhịp {ra['off_peak']} / đỉnh {_v(ra['peak_pct'], '%')} vs "
            f"{rb['off_peak']} / {_v(rb['peak_pct'], '%')}"
        )
    if level_idx == 7:
        return f"<10h {ra['cram_pct']}% vs {rb['cram_pct']}%"
    if level_idx == 8:
        return (
            f"ngày quá 2 ca nặng {ra['heavy_overload_days']} / max {ra['max_day_min']}p vs "
            f"{rb['heavy_overload_days']} / {rb['max_day_min']}p"
        )
    if level_idx == 9:
        return f"Ctx {ra['ctx']} vs {rb['ctx']}"
    if level_idx == 10:
        return f"thói quen {_v(ra['habit_pct'], '%')} vs {_v(rb['habit_pct'], '%')}"
    return (
        f"SJL {_v(ra['sjl_min'], 'p')} / Std {ra['std_min']}p vs "
        f"{_v(rb['sjl_min'], 'p')} / {rb['std_min']}p"
    )


def _first_diff_level(ka: Tuple, kb: Tuple) -> Optional[int]:
    for i, (x, y) in enumerate(zip(ka, kb)):
        if x != y:
            return i
    return None


def _spread_sentences(rows: List[Dict[str, Any]]) -> List[str]:
    """Metrics where solvers disagree, phrased as best vs worst with solver names."""
    specs = [
        ("p1_pct", "Điểm việc kịp hạn P1.1", "%", True),
        ("shock25_pct", "Đệm chịu sốc +25%", "%", True),
        ("recovery_pct", "Tỷ lệ nghỉ phục hồi sau việc nặng", "%", True),
        ("peak_pct", "Việc nặng rơi vào giờ đỉnh", "%", True),
        ("max_day_min", "Tải ngày cao nhất (lớp + tự học)", "p", False),
        ("ctx", "Số lần đổi ngữ cảnh", "", False),
        ("std_min", "Độ lệch tải giữa các ngày", "p", False),
    ]
    out: List[str] = []
    for key, label, unit, higher_better in specs:
        vals = [(r[key], r["solver_key"]) for r in rows if r[key] is not None]
        if len(vals) < 2:
            continue
        lo, hi = min(v for v, _ in vals), max(v for v, _ in vals)
        if lo == hi:
            continue
        best_v = hi if higher_better else lo
        worst_v = lo if higher_better else hi
        best = ", ".join(s for v, s in vals if v == best_v)
        worst = ", ".join(s for v, s in vals if v == worst_v)
        out.append(f"{label}: tốt nhất {best} ({best_v}{unit}), kém nhất {worst} ({worst_v}{unit}).")
    return out


def explain_case(
    order: List[str], reports: Dict[str, EvaluationReport], cfg: Optional[EvaluationConfig] = None
) -> Dict[str, Any]:
    keys = {s: lexicographic_key(reports[s], cfg) for s in order}
    rows = [_row(s, i + 1, reports[s]) for i, s in enumerate(order)]

    verdict_counts: Dict[str, List[str]] = {}
    for r in rows:
        verdict_counts.setdefault(VERDICT_SHORT.get(r["verdict"], r["verdict"]), []).append(r["solver_key"])
    verdict_line = " · ".join(f"{v}: {', '.join(ss)}" for v, ss in verdict_counts.items())

    pair_lines: List[Dict[str, Any]] = []
    for upper, lower in zip(order, order[1:]):
        lvl = _first_diff_level(keys[upper], keys[lower])
        if lvl is None:
            pair_lines.append({
                "upper": upper, "lower": lower, "level": None,
                "text": f"{upper} và {lower} hòa ở mọi cấp (sau khi làm tròn bậc dung sai) — thứ tự giữ theo danh sách thuật toán.",
            })
        else:
            pair_lines.append({
                "upper": upper, "lower": lower, "level": LEX_LEVELS[lvl]["code"],
                "text": (
                    f"{upper} xếp trên {lower} nhờ cấp {LEX_LEVELS[lvl]['name']}: "
                    f"{_fmt_level_values(lvl, reports[upper], reports[lower])}."
                ),
            })

    decisive = [p["level"] for p in pair_lines if p["level"]]
    top = rows[0]
    top_reason = pair_lines[0]["text"] if pair_lines else ""
    summary = (
        f"Hạng #1 là {top['solver_key']} ({VERDICT_SHORT.get(top['verdict'], top['verdict'])}, "
        f"P1.1 {top['p1_pct']}%, {top['crit']} thẻ đỏ / {top['warn']} thẻ vàng). {top_reason}"
    )
    distinct_verdicts = len(verdict_counts)
    return {
        "rows": rows,
        "summary": summary,
        "verdict_line": verdict_line,
        "pairs": pair_lines,
        "spread": _spread_sentences(rows),
        "decisive_levels": sorted(set(decisive), key=lambda c: [lv["code"] for lv in LEX_LEVELS].index(c)),
        "distinct_verdicts": distinct_verdicts,
    }


def run_case(
    source: str, suite_id: str, seed: int, horizon_days: Optional[int] = None, solvers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Generate → solve with every solver → evaluate (raw tasks) → official ranking → explanation."""
    bundle = generate_testing_bundle(source, suite_id, seed, horizon_days)
    keys = solvers or [s["key"] for s in get_available_solvers()]
    cfg = EvaluationConfig()
    reports: Dict[str, EvaluationReport] = {}
    for key in keys:
        out, _ = ScheduleController.solve_schedule(
            profile=bundle.profile.model_copy(deep=True),
            tasks=[t.model_copy(deep=True) for t in bundle.tasks],
            algorithm=key,
            pinned_blocks=[b.model_copy(deep=True) for b in bundle.pinned_blocks] or None,
        )
        reports[key] = ScheduleEvaluator.evaluate(
            profile=bundle.profile,
            tasks=bundle.tasks,
            schedule=out,
            input_pinned_blocks=bundle.pinned_blocks or None,
            config=cfg,
        )
    order = [e.solver_name for e in rank_cross_solver_reports(reports, cfg)]
    m = bundle.metadata
    return {
        "source": source,
        "id": suite_id.upper(),
        "seed": int(seed),
        "horizon_days": m.horizon_days,
        "title": bundle_title(source, suite_id, bundle),
        "metadata": {
            "chronotype": m.chronotype,
            "persona_archetype": m.persona_archetype,
            "fuzz_tier": m.fuzz_tier,
            "tightness_rho": m.tightness_rho,
            "tightness_rho_deadline": m.tightness_rho_deadline,
            "task_count": m.task_count,
            "habit_count": m.habit_count,
            "pinned_count": m.pinned_count,
            "notes": m.notes,
        },
        **explain_case(order, reports, cfg),
    }


# ---------------------------------------------------------------------------
# 4. Curated showcase list (chosen from a 6-solver sweep where outputs diverge)
# ---------------------------------------------------------------------------

# Selected from a 6-solver sweep (R1..R6 × seeds 1,2,3,42,101 and Fuzz RANDOM 1001..1030) for
# *different* kinds of divergence. Only 7-day cases whose slowest solver stays well under the
# 1000ms SLA gate. `focus`/`why` only state what the generator family is designed to stress —
# never an outcome: SCORED_GREEDY / BACKTRACK / HYBRID_ALNS run wall-clock-budgeted polish, so
# their numbers can shift when the CPU is busy. Every result sentence is generated from the data.
SHOWCASE_CASES: List[Dict[str, Any]] = [
    {
        "source": "regime", "id": "R1", "seed": 3,
        "focus": "Tải nhẹ: thuật toán có hiểu nhịp sinh học hay không",
        "why": "R1 dư sức chứa (ρ < 0.55) nên ai cũng có chỗ kịp hạn; khác biệt nằm ở cách đặt việc nặng vào giờ đỉnh, chèn nghỉ và giữ trần tải ngày.",
    },
    {
        "source": "regime", "id": "R3", "seed": 1,
        "focus": "Cú đêm & lệch pha: tôn trọng chronotype",
        "why": "R3 dùng hồ sơ Owl và lịch lớp lệch T2-T4-T6 để kiểm tra việc tránh đẩy sớm pha ngủ và đặt việc nặng đúng khung năng lượng.",
    },
    {
        "source": "regime", "id": "R2", "seed": 101,
        "focus": "Sát hạn dồn cụm: phân hạng bằng đệm sốc & nghỉ phục hồi",
        "why": "R2 có nhiều hạn chót chồng cụm với độ chặt cao (ρ ≈ 0.75–0.92): thử sức chống rớt hạn, đệm +25% và nghỉ giữa các ca nặng.",
    },
    {
        "source": "regime", "id": "R5", "seed": 42,
        "focus": "Quá tải cấu trúc: so khả năng triage",
        "why": "R5 có tổng nhu cầu vượt sức chứa nên không thể kịp hết; cột P1.1 cho biết thuật toán giữ lại được bao nhiêu điểm priority.",
    },
    {
        "source": "fuzz", "id": "RANDOM", "seed": 1001,
        "focus": "Fuzz TIGHT: giữ hạn & đệm chịu sốc khi lịch rất chật",
        "why": "Đề FuzzGenerator v2 mức TIGHT (ρ ≈ 0.65–0.90, có lời giải mẫu Witness nên chắc chắn khả thi): đo việc giữ hạn và đệm chịu sốc trong điều kiện chật.",
    },
    {
        "source": "fuzz", "id": "RANDOM", "seed": 1007,
        "focus": "Fuzz OVERLOAD: so khả năng cứu điểm priority (triage)",
        "why": "Đề FuzzGenerator v2 quá tải thật (ρ_deadline ≈ 1.22–1.55): thứ hạng trước hết theo P1.1 — tỷ lệ điểm priority cứu được.",
    },
    {
        "source": "fuzz", "id": "RANDOM", "seed": 1015,
        "focus": "Fuzz LOOSE: tách hạng khi nhiều thuật toán cùng đạt chuẩn",
        "why": "Đề FuzzGenerator v2 dư sức chứa: khi nhiều thuật toán cùng đạt chuẩn, thứ hạng phải tách bằng các cấp sau như chống dồn <10h, đổi ngữ cảnh, đều tải tuần.",
    },
]

_cache_lock = threading.Lock()
_case_cache: Dict[int, Dict[str, Any]] = {}


def list_showcase() -> Dict[str, Any]:
    """Cheap listing (no solving) so the UI can render placeholders immediately."""
    return {
        "cases": [
            {"index": i, "source": c["source"], "id": c["id"], "seed": c["seed"], "focus": c["focus"], "why": c["why"]}
            for i, c in enumerate(SHOWCASE_CASES)
        ],
        "levels": LEX_LEVELS,
    }


def get_showcase_case(index: int, force: bool = False) -> Dict[str, Any]:
    """Run one showcase case (cached in-process: seeded inputs give deterministic schedules)."""
    if index < 0 or index >= len(SHOWCASE_CASES):
        raise ValueError(f"Showcase index {index} out of range 0..{len(SHOWCASE_CASES) - 1}.")
    with _cache_lock:
        if index in _case_cache and not force:
            return _case_cache[index]
    spec = SHOWCASE_CASES[index]
    t0 = time.perf_counter()
    res = run_case(spec["source"], spec["id"], spec["seed"], spec.get("horizon_days"))
    res.update({
        "index": index,
        "focus": spec["focus"],
        "why": spec["why"],
        "generated_ms": round((time.perf_counter() - t0) * 1000),
    })
    with _cache_lock:
        _case_cache[index] = res
    return res


__all__ = [
    "LEX_LEVELS",
    "SHOWCASE_CASES",
    "explain_case",
    "get_showcase_case",
    "lexicographic_key",
    "list_showcase",
    "run_case",
]
