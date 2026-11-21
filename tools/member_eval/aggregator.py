"""
Multi-Member Review Aggregator & Ergonomic Calibration Analyzer (`member_eval/aggregator.py`).

Implements Sections IV & VI of `Testing_Plan/evaluation_plan.md`:
  - Computes blind human win-rates (split by Personal / LOOSE / TIGHT / OVERLOAD)
  - Computes UX-1..UX-5 component means (anti-100-score collapse)
  - Computes Machine (v2.1 Lex Rank) vs. Human Agreement Rate and Disagreement ledger
  - Detects Friction Clusters (Block Tags >= 25%) and maps concrete `ergonomic_engine.py` tuning rules
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from tools.member_eval import ALL_6_SOLVERS, OFFICIAL_BLOCK_TAGS, OFFICIAL_BLOCK_TAGS_META


def load_reviews(reviews_dir: Path) -> List[Dict[str, Any]]:
    if not reviews_dir.exists():
        return []
    out: List[Dict[str, Any]] = []
    for path in sorted(reviews_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "blind_winner_id" in data and "blind_mapping" in data:
                out.append(data)
        except Exception:
            continue
    return out


def aggregate_reviews(reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_sessions = len(reviews)
    unique_members = sorted({str(r.get("member_id", "")) for r in reviews if r.get("member_id")})
    unique_scenarios = sorted({str(r.get("scenario_id", "")) for r in reviews if r.get("scenario_id")})

    sessions_by_category: Dict[str, int] = {"PERSONAL": 0, "LOOSE": 0, "TIGHT": 0, "OVERLOAD": 0}
    solver_acc: Dict[str, Dict[str, Any]] = {}

    def _ensure_solver(name: str) -> Dict[str, Any]:
        if name not in solver_acc:
            solver_acc[name] = {
                "solver_name": name,
                "appearances": 0,
                "blind_wins": 0,
                "wins_by_category": {"PERSONAL": 0, "LOOSE": 0, "TIGHT": 0, "OVERLOAD": 0},
                "appearances_by_category": {"PERSONAL": 0, "LOOSE": 0, "TIGHT": 0, "OVERLOAD": 0},
                "ux_sums": {f"UX-{i}": 0.0 for i in range(1, 6)},
                "ux_counts": {f"UX-{i}": 0 for i in range(1, 6)},
                "v21_high_count": 0,
                "v21_rank1_count": 0,
                "tag_counts": {tag: 0 for tag in OFFICIAL_BLOCK_TAGS},
            }
        return solver_acc[name]

    exact_rank1_agreed = 0
    top2_agreed = 0
    post_reveal_checked = 0
    post_reveal_agreed = 0
    disagreement_cases: List[Dict[str, Any]] = []

    overall_tag_counts: Dict[str, int] = {tag: 0 for tag in OFFICIAL_BLOCK_TAGS}
    total_tags_marked = 0

    for rev in reviews:
        cat = str(rev.get("scenario_category") or "PERSONAL").upper()
        if cat not in sessions_by_category:
            sessions_by_category[cat] = 0
        sessions_by_category[cat] += 1

        mapping: Dict[str, str] = rev.get("blind_mapping") or {}
        winner_blind_id = str(rev.get("blind_winner_id") or "")
        winner_solver = mapping.get(winner_blind_id, "")
        scores_by_blind = rev.get("scores_by_blind_id") or {}
        oracle_reports = rev.get("reports_by_blind_id") or {}

        v21_rank1_blind = None
        v21_rank1_solver = None
        for b_id, s_name in mapping.items():
            s_rec = _ensure_solver(s_name)
            s_rec["appearances"] += 1
            s_rec["appearances_by_category"][cat] = s_rec["appearances_by_category"].get(cat, 0) + 1
            if b_id == winner_blind_id:
                s_rec["blind_wins"] += 1
                s_rec["wins_by_category"][cat] = s_rec["wins_by_category"].get(cat, 0) + 1

            ux_map = scores_by_blind.get(b_id) or {}
            for i in range(1, 6):
                k = f"UX-{i}"
                if k in ux_map and ux_map[k] is not None:
                    s_rec["ux_sums"][k] += float(ux_map[k])
                    s_rec["ux_counts"][k] += 1

            rep = oracle_reports.get(b_id) or {}
            if rep.get("verdict") == "HIGH_PRODUCTIVITY":
                s_rec["v21_high_count"] += 1
            if rep.get("lexicographic_rank") == 1:
                s_rec["v21_rank1_count"] += 1
                v21_rank1_blind = b_id
                v21_rank1_solver = s_name

        winner_rep = oracle_reports.get(winner_blind_id) or {}
        winner_rank = winner_rep.get("lexicographic_rank")
        if winner_rank == 1:
            exact_rank1_agreed += 1
        if isinstance(winner_rank, int) and winner_rank <= 2:
            top2_agreed += 1

        if rev.get("revealed_diff_agree") is not None:
            post_reveal_checked += 1
            if rev.get("revealed_diff_agree") is True:
                post_reveal_agreed += 1

        tags_list = rev.get("block_tags") or []
        tags_on_rank1: List[str] = []
        for item in tags_list:
            tag_name = str(item.get("tag") or "").strip().upper()
            b_id = str(item.get("blind_id") or "")
            s_name = mapping.get(b_id, "")
            if tag_name in overall_tag_counts:
                overall_tag_counts[tag_name] += 1
                total_tags_marked += 1
                if s_name:
                    _ensure_solver(s_name)["tag_counts"][tag_name] += 1
            if b_id == v21_rank1_blind and tag_name:
                tags_on_rank1.append(tag_name)

        if v21_rank1_solver and winner_solver and winner_solver != v21_rank1_solver:
            disagreement_cases.append({
                "member_id": rev.get("member_id"),
                "scenario_id": rev.get("scenario_id"),
                "scenario_category": cat,
                "human_winner_solver": winner_solver,
                "human_winner_verdict": winner_rep.get("verdict"),
                "human_winner_v21_rank": winner_rank,
                "v21_rank1_solver": v21_rank1_solver,
                "tags_on_v21_rank1": tags_on_rank1,
                "free_text_notes": rev.get("free_text_notes", ""),
            })

    solver_stats: Dict[str, Dict[str, Any]] = {}
    ordered_solvers = [s for s in ALL_6_SOLVERS if s in solver_acc] + [
        s for s in sorted(solver_acc) if s not in ALL_6_SOLVERS
    ]
    for s_name in ordered_solvers:
        rec = solver_acc[s_name]
        app_cnt = max(1, rec["appearances"])
        ux_means: Dict[str, float] = {}
        ux_vals: List[float] = []
        for i in range(1, 6):
            k = f"UX-{i}"
            cnt = rec["ux_counts"][k]
            avg = round(rec["ux_sums"][k] / cnt, 2) if cnt > 0 else 0.0
            ux_means[k] = avg
            if cnt > 0:
                ux_vals.append(avg)
        win_rates_by_cat = {}
        for c_key, c_app in rec["appearances_by_category"].items():
            c_wins = rec["wins_by_category"].get(c_key, 0)
            win_rates_by_cat[c_key] = round(100.0 * c_wins / c_app, 1) if c_app > 0 else None

        solver_stats[s_name] = {
            "solver_name": s_name,
            "appearances": rec["appearances"],
            "blind_wins": rec["blind_wins"],
            "blind_win_rate_pct": round(100.0 * rec["blind_wins"] / app_cnt, 1),
            "wins_by_category": rec["wins_by_category"],
            "win_rate_by_category_pct": win_rates_by_cat,
            "ux_means": ux_means,
            "mean_ux": round(sum(ux_vals) / len(ux_vals), 2) if ux_vals else 0.0,
            "v21_high_rate_pct": round(100.0 * rec["v21_high_count"] / app_cnt, 1),
            "v21_rank1_rate_pct": round(100.0 * rec["v21_rank1_count"] / app_cnt, 1),
            "tag_counts": rec["tag_counts"],
        }

    meta_by_tag = {m["tag"]: m for m in OFFICIAL_BLOCK_TAGS_META}
    friction_clusters: List[Dict[str, Any]] = []
    for tag in OFFICIAL_BLOCK_TAGS:
        cnt = overall_tag_counts[tag]
        share_pct = round(100.0 * cnt / total_tags_marked, 1) if total_tags_marked > 0 else 0.0
        meta = meta_by_tag.get(tag, {})
        friction_clusters.append({
            "tag": tag,
            "label_vi": meta.get("label_vi", tag),
            "count": cnt,
            "share_pct": share_pct,
            "is_friction_cluster": total_tags_marked > 0 and share_pct >= 25.0,
            "calibration_hint": meta.get("calibration_hint", ""),
        })
    friction_clusters.sort(key=lambda x: (-x["count"], x["tag"]))

    top2_agree_pct = round(100.0 * top2_agreed / total_sessions, 1) if total_sessions > 0 else 0.0
    exact_rank1_pct = round(100.0 * exact_rank1_agreed / total_sessions, 1) if total_sessions > 0 else 0.0
    disagreement_pct = round(100.0 - top2_agree_pct, 1) if total_sessions > 0 else 0.0
    post_reveal_agree_pct = (
        round(100.0 * post_reveal_agreed / post_reveal_checked, 1) if post_reveal_checked > 0 else None
    )

    decision_rules = _evaluate_decision_rules(
        total_sessions=total_sessions,
        solver_stats=solver_stats,
        friction_clusters=friction_clusters,
        disagreement_pct=disagreement_pct,
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_sessions": total_sessions,
        "unique_members": unique_members,
        "unique_members_count": len(unique_members),
        "unique_scenarios": unique_scenarios,
        "sessions_by_category": sessions_by_category,
        "solver_stats": solver_stats,
        "agreement_metrics": {
            "exact_rank1_agreement_pct": exact_rank1_pct,
            "top2_agreement_pct": top2_agree_pct,
            "disagreement_rate_pct": disagreement_pct,
            "post_reveal_agree_pct": post_reveal_agree_pct,
            "disagreement_cases": disagreement_cases,
        },
        "total_tags_marked": total_tags_marked,
        "friction_clusters": friction_clusters,
        "decision_rules": decision_rules,
    }


def _evaluate_decision_rules(
    total_sessions: int,
    solver_stats: Dict[str, Dict[str, Any]],
    friction_clusters: List[Dict[str, Any]],
    disagreement_pct: float,
) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    if total_sessions == 0:
        rules.append({
            "rule": "NO_DATA",
            "status": "PENDING",
            "message_vi": "Chưa có phiên chấm mù nào được nộp. Cần tối thiểu 21 phiên (7 thành viên × 3 ca) để chốt cấu hình.",
        })
        return rules

    sg = solver_stats.get("SCORED_GREEDY", {})
    alns = solver_stats.get("HYBRID_ALNS", {})
    combined_win_pct = round(sg.get("blind_win_rate_pct", 0.0) + alns.get("blind_win_rate_pct", 0.0), 1)
    best_v3_ux = max(sg.get("mean_ux", 0.0), alns.get("mean_ux", 0.0))

    r1_ok = combined_win_pct >= 70.0 and best_v3_ux >= 4.0
    rules.append({
        "rule": "RULE_1_CONSENSUS",
        "status": "TRIGGERED" if r1_ok else "MONITORING",
        "message_vi": (
            f"Đồng thuận Người & Máy ĐẠT chuẩn (V3 SCORED_GREEDY + HYBRID_ALNS thắng mù {combined_win_pct}% >= 70%, Mean UX={best_v3_ux}/5 >= 4.0): "
            "Giữ SCORED_GREEDY làm mặc định Web tương tác nhanh & cung cấp HYBRID_ALNS cho chế độ Tối ưu sâu."
            if r1_ok
            else f"Tỷ lệ thắng mù V3 hiện đạt {combined_win_pct}%, Mean UX={best_v3_ux}/5 (ngưỡng chốt: >=70% thắng & >=4.0/5)."
        ),
    })

    active_clusters = [fc for fc in friction_clusters if fc["is_friction_cluster"]]
    if active_clusters:
        for fc in active_clusters:
            rules.append({
                "rule": f"RULE_2_FRICTION_{fc['tag']}",
                "status": "ACTION_REQUIRED",
                "message_vi": (
                    f"Cụm phàn nàn [{fc['tag']}] chiếm {fc['share_pct']}% (>=25% tổng nhãn): {fc['calibration_hint']}"
                ),
            })
    else:
        rules.append({
            "rule": "RULE_2_FRICTION",
            "status": "CLEAN",
            "message_vi": "Chưa phát hiện cụm nhãn lỗi nào vượt ngưỡng >=25% tổng số lượt gắn thẻ.",
        })

    if disagreement_pct > 20.0:
        rules.append({
            "rule": "RULE_3_DISAGREEMENT",
            "status": "ACTION_REQUIRED",
            "message_vi": (
                f"Tỷ lệ bất đồng Máy v2.1 vs Người thật là {disagreement_pct}% (>20%): rà soát các ca disagreement_cases "
                "và tinh chỉnh trọng số trong src/solvers/ergonomic_engine.py, sau đó chạy lại 220 kịch bản kiểm định."
            ),
        })
    else:
        rules.append({
            "rule": "RULE_3_DISAGREEMENT",
            "status": "ALIGNED",
            "message_vi": f"Độ lệch Top-2 Máy v2.1 vs Người thật ở mức an toàn ({disagreement_pct}% <= 20%).",
        })
    return rules


def render_calibration_report_md(summary: Dict[str, Any]) -> str:
    """Render clean Vietnamese Markdown calibration report matching `evaluation_plan.md`."""
    ag = summary["agreement_metrics"]
    lines: List[str] = [
        "# Báo Cáo Tổng Hợp Đánh Giá Mù & Hiệu Chuẩn Thuật Toán (`Member-in-the-Loop Calibration Report`)",
        "",
        f"- **Thời điểm tổng hợp:** `{summary['generated_at']}`",
        f"- **Tổng số phiên chấm mù:** `{summary['total_sessions']}` | **Thành viên tham gia:** `{summary['unique_members_count']}` ({', '.join(summary['unique_members']) or 'Chưa có'})",
        f"- **Phân bổ kịch bản:** Personal=`{summary['sessions_by_category'].get('PERSONAL', 0)}`, LOOSE=`{summary['sessions_by_category'].get('LOOSE', 0)}`, TIGHT=`{summary['sessions_by_category'].get('TIGHT', 0)}`, OVERLOAD=`{summary['sessions_by_category'].get('OVERLOAD', 0)}`",
        "",
        "## 1. Tỷ Lệ Thắng Mù & Điểm Trải Nghiệm `UX-1..UX-5` Theo Thuật Toán",
        "",
        "| Thuật toán | Lượt chấm | Thắng mù (`#1`) | `UX-1` (Hiệu quả) | `UX-2` (Sinh học) | `UX-3` (Nghỉ/Bền) | `UX-4` (Mượt/Mạch) | `UX-5` (Đệm/Sốc) | Mean UX | `v2.1 HIGH` |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for s_name, st in summary["solver_stats"].items():
        ux = st["ux_means"]
        lines.append(
            f"| **`{s_name}`** | {st['appearances']} | {st['blind_wins']} ({st['blind_win_rate_pct']}%) | "
            f"{ux['UX-1']} | {ux['UX-2']} | {ux['UX-3']} | {ux['UX-4']} | {ux['UX-5']} | **{st['mean_ux']}** | {st['v21_high_rate_pct']}% |"
        )
    if not summary["solver_stats"]:
        lines.append("| *(Chưa có dữ liệu)* | 0 | 0% | - | - | - | - | - | - | - |")

    lines.extend([
        "",
        "## 2. Độ Đồng Thuận Máy `v2.1` vs. Người Thật",
        "",
        f"- **Khớp chính xác Hạng #1 (`Exact Rank #1 Agreement`):** `{ag['exact_rank1_agreement_pct']}%`",
        f"- **Khớp trong Top-2 (`Rank #1 or #2 Agreement`):** `{ag['top2_agreement_pct']}%`",
        f"- **Tỷ lệ bất đồng (`Disagreement Rate`):** `{ag['disagreement_rate_pct']}%`",
        f"- **Đồng thuận sau khi mở khóa (`Post-Reveal Agreement`):** `{ag['post_reveal_agree_pct']}%`" if ag["post_reveal_agree_pct"] is not None else "- **Đồng thuận sau mở khóa:** *(Chưa đánh dấu)*",
        "",
        "## 3. Cụm Phàn Nàn Thực Tế (`Block Tags` — Ngưỡng Cụm >= 25%)",
        "",
        "| Tag Lỗi | Mô tả | Số lượt | Tỷ lệ | Cụm `>=25%` | Hướng hiệu chuẩn `ergonomic_engine.py` |",
        "| :--- | :--- | :---: | :---: | :---: | :--- |",
    ])
    for fc in summary["friction_clusters"]:
        flag = "CẦN CHỈNH" if fc["is_friction_cluster"] else "Ổn"
        lines.append(
            f"| `{fc['tag']}` | {fc['label_vi']} | {fc['count']} | {fc['share_pct']}% | **{flag}** | {fc['calibration_hint']} |"
        )

    lines.extend(["", "## 4. Khuyến Nghị Quyết Định (Theo Quy Tắc §VI `evaluation_plan.md`)", ""])
    for r in summary["decision_rules"]:
        lines.append(f"- **[{r['status']}] `{r['rule']}`:** {r['message_vi']}")

    if ag["disagreement_cases"]:
        lines.extend(["", "## 5. Danh Sách Các Ca Bất Đồng Chi Tiết", ""])
        for c in ag["disagreement_cases"]:
            lines.append(
                f"- `{c['member_id']}` · `{c['scenario_id']}` ({c['scenario_category']}): "
                f"Người chọn **`{c['human_winner_solver']}`** (rank `{c['human_winner_v21_rank']}`, `{c['human_winner_verdict']}`) "
                f"vs Máy `#1` **`{c['v21_rank1_solver']}`** | Tags trên `#1`: {c['tags_on_v21_rank1']} | Ghi chú: {c['free_text_notes']}"
            )
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    base_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Aggregate Member-in-the-Loop blind reviews into Calibration_Report.md.")
    parser.add_argument("--reviews-dir", default=str(base_dir / "reviews"), help="Directory of saved review JSON files")
    parser.add_argument("--out", default=str(base_dir / "Calibration_Report.md"), help="Output Markdown report path")
    args = parser.parse_args(argv)

    reviews = load_reviews(Path(args.reviews_dir))
    summary = aggregate_reviews(reviews)
    md = render_calibration_report_md(summary)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"[AGGREGATOR] Loaded {len(reviews)} review(s) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
