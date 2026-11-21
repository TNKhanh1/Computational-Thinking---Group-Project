"""
M7 Completion Telemetry Calibration & EWMA Personal Alpha Estimator (Pure Layer 1).

Computes empirical Actual / Estimated duration ratios and Exponentially Weighted
Moving Average (EWMA) buffer recommendations from M7 completion logs stored in SQLite.

Architectural compliance (INV-1, INV-2):
  - Pure leaf module: imports only Python standard library and `src.config`.
  - LoA Level 4 advisory output: never mutates user profiles or solvers automatically.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Optional

from smartschedule.core.config import (
    ALPHA_GRID_MAX,
    ALPHA_GRID_MIN,
    ALPHA_HEAVY_DEFAULT,
    ALPHA_LIGHT_DEFAULT,
)

HEAVY_CATEGORIES = frozenset(
    {"CODING", "EXAM_PREP", "PROJECT", "DEEP_WORK", "LAB", "ASSIGNMENT", "THESIS"}
)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _is_heavy_log(entry: Dict[str, Any]) -> bool:
    raw_load = entry.get("cognitive_load")
    if raw_load is not None:
        try:
            return int(raw_load) >= 3
        except (TypeError, ValueError):
            pass
    cat = str(entry.get("category") or "OTHER").strip().upper()
    return cat in HEAVY_CATEGORIES


def _sort_chronological(logs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [dict(row) for row in logs if isinstance(row, dict)]
    if not items:
        return []
    # `list_completion_logs` returns newest-first (ORDER BY id DESC);
    # sort oldest-first so EWMA weights the most recent completions highest.
    return sorted(
        items,
        key=lambda r: (
            str(r.get("completed_at") or ""),
            int(r.get("id") or 0),
        ),
    )


def compute_ewma_calibration(
    logs: Iterable[Dict[str, Any]],
    lambda_ewma: float = 0.25,
    min_samples: int = 5,
    default_alpha_light: float = ALPHA_LIGHT_DEFAULT,
    default_alpha_heavy: float = ALPHA_HEAVY_DEFAULT,
    ratio_clip_min: float = 0.50,
    ratio_clip_max: float = 2.50,
    alpha_floor: float = ALPHA_GRID_MIN,
    alpha_ceil: float = ALPHA_GRID_MAX,
) -> Dict[str, Any]:
    """
    Calculate empirical Actual/Estimated ratios and EWMA-calibrated alpha values.

    Formula (oldest -> newest):
        r_t = clip(actual_t / estimated_t, ratio_clip_min, ratio_clip_max)
        alpha_t = lambda_ewma * r_t + (1 - lambda_ewma) * alpha_{t-1}

    Recommendations are gated by `min_samples` and clamped to `[alpha_floor, alpha_ceil]`
    to prevent over-buffering cliffs (`alpha >= 1.70`) under tight weekly loads.
    """
    lam = _clip(float(lambda_ewma), 0.05, 0.95)
    min_n = max(1, int(min_samples))
    ordered = _sort_chronological(logs)

    ratios_all: List[float] = []
    ratios_light: List[float] = []
    ratios_heavy: List[float] = []
    per_category_ratios: Dict[str, List[float]] = {}

    ewma_all = 0.5 * (default_alpha_light + default_alpha_heavy)
    ewma_light = float(default_alpha_light)
    ewma_heavy = float(default_alpha_heavy)
    per_category_ewma: Dict[str, float] = {}

    for row in ordered:
        try:
            est = float(row.get("estimated_duration_min") or 0)
            act = float(row.get("actual_duration_min") or 0)
        except (TypeError, ValueError):
            continue
        if est <= 0 or act <= 0:
            continue

        r = _clip(act / est, ratio_clip_min, ratio_clip_max)
        ratios_all.append(r)
        ewma_all = lam * r + (1.0 - lam) * ewma_all

        cat = str(row.get("category") or "OTHER").strip().upper() or "OTHER"
        if cat not in per_category_ratios:
            per_category_ratios[cat] = []
            per_category_ewma[cat] = (
                float(default_alpha_heavy)
                if cat in HEAVY_CATEGORIES
                else float(default_alpha_light)
            )
        per_category_ratios[cat].append(r)
        per_category_ewma[cat] = lam * r + (1.0 - lam) * per_category_ewma[cat]

        if _is_heavy_log(row):
            ratios_heavy.append(r)
            ewma_heavy = lam * r + (1.0 - lam) * ewma_heavy
        else:
            ratios_light.append(r)
            ewma_light = lam * r + (1.0 - lam) * ewma_light

    n_total = len(ratios_all)
    n_light = len(ratios_light)
    n_heavy = len(ratios_heavy)
    ready_overall = n_total >= min_n

    # When overall sample count meets threshold, calibrate each bucket if it has >= 2 logs,
    # otherwise gently anchor toward the overall EWMA while preserving heavy >= light.
    if ready_overall:
        raw_rec_light = ewma_light if n_light >= 2 else ewma_all
        raw_rec_heavy = ewma_heavy if n_heavy >= 2 else max(ewma_all, raw_rec_light)
        rec_light = round(_clip(raw_rec_light, alpha_floor, alpha_ceil), 2)
        rec_heavy = round(_clip(max(raw_rec_heavy, rec_light), alpha_floor, alpha_ceil), 2)
        advisory_note = (
            f"Đã thu đủ {n_total} phiên hoàn thành (ngưỡng >= {min_n}). "
            f"Đề xuất hiệu chuẩn LoA-4: α_light={rec_light:.2f}, α_heavy={rec_heavy:.2f} "
            f"(kẹp an toàn trong [{alpha_floor:.2f}, {alpha_ceil:.2f}])."
        )
    else:
        rec_light = round(float(default_alpha_light), 2)
        rec_heavy = round(float(default_alpha_heavy), 2)
        advisory_note = (
            f"Mới có {n_total}/{min_n} phiên hoàn thành — giữ nguyên mặc định "
            f"α_light={rec_light:.2f}, α_heavy={rec_heavy:.2f} cho đến khi đủ dữ liệu Pilot."
        )

    category_stats: Dict[str, Dict[str, Any]] = {}
    for cat in sorted(per_category_ratios.keys()):
        vals = per_category_ratios[cat]
        category_stats[cat] = {
            "count": len(vals),
            "mean_ratio": round(statistics.mean(vals), 3),
            "median_ratio": round(statistics.median(vals), 3),
            "ewma_alpha": round(_clip(per_category_ewma[cat], alpha_floor, alpha_ceil), 2),
        }

    return {
        "sample_count": n_total,
        "light_sample_count": n_light,
        "heavy_sample_count": n_heavy,
        "min_samples_required": min_n,
        "lambda_ewma": round(lam, 3),
        "ready_to_apply": ready_overall,
        "mean_ratio": round(statistics.mean(ratios_all), 3) if n_total else None,
        "median_ratio": round(statistics.median(ratios_all), 3) if n_total else None,
        "ewma_overall": round(ewma_all, 3) if n_total else None,
        "ewma_alpha_light": round(ewma_light, 3),
        "ewma_alpha_heavy": round(ewma_heavy, 3),
        "recommended_alpha_light": rec_light,
        "recommended_alpha_heavy": rec_heavy,
        "safe_bounds": [round(alpha_floor, 2), round(alpha_ceil, 2)],
        "by_category": category_stats,
        "advisory_note": advisory_note,
    }


def format_pilot_markdown_report(
    calibration: Dict[str, Any],
    workspace_id: str = "default",
) -> str:
    """Format a calibration dictionary into a clean Markdown summary for Pilot reports / Presentation2."""
    lines = [
        f"## M7 Empirical Alpha Calibration Summary (`workspace={workspace_id}`)",
        "",
        f"- **Completed Sessions (`n`):** `{calibration.get('sample_count', 0)}` "
        f"(Light: `{calibration.get('light_sample_count', 0)}`, Heavy: `{calibration.get('heavy_sample_count', 0)}`)",
        f"- **Empirical `Actual / Estimated`:** Mean = `{calibration.get('mean_ratio')}`, "
        f"Median = `{calibration.get('median_ratio')}`",
        f"- **EWMA (`λ={calibration.get('lambda_ewma')}`):** "
        f"Light = `{calibration.get('ewma_alpha_light')}`, Heavy = `{calibration.get('ewma_alpha_heavy')}`",
        f"- **Recommended α (LoA-4):** `α_light = {calibration.get('recommended_alpha_light')}`, "
        f"`α_heavy = {calibration.get('recommended_alpha_heavy')}` "
        f"(Ready: `{calibration.get('ready_to_apply')}`)",
        f"- **Note:** {calibration.get('advisory_note', '')}",
        "",
    ]
    by_cat: Optional[Dict[str, Dict[str, Any]]] = calibration.get("by_category")
    if by_cat:
        lines.extend(
            [
                "| Category | Sessions | Mean `Act/Est` | Median `Act/Est` | EWMA `α` |",
                "| :--- | :---: | :---: | :---: | :---: |",
            ]
        )
        for cat, st in by_cat.items():
            lines.append(
                f"| `{cat}` | {st['count']} | {st['mean_ratio']:.3f} | "
                f"{st['median_ratio']:.3f} | {st['ewma_alpha']:.2f} |"
            )
        lines.append("")
    return "\n".join(lines)
