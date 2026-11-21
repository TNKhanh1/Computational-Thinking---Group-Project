"""
Tier 2: Lexicographic Verdict Engine, D1 ICEE Root-Cause Critiques (Non-Noise Conjecture 1),
D2 Relative Cross-Solver Comparison, and Auxiliary Diagnostics.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from Testing_System.schemas import (
    AuxiliaryDiagnostics,
    CrossSolverEntry,
    EvaluationConfig,
    EvaluationReport,
    GateContextMetrics,
    ICEECritique,
    Pillar1ValueTimeliness,
    Pillar2CognitiveBiology,
    Pillar3SustainablePacing,
    Pillar4RobustnessStability,
    VerdictLabel,
)


def _get_shock_pct(p4: Pillar4RobustnessStability, target_shock: float) -> float:
    for sr in p4.shock_results:
        if abs(sr.shock_pct - target_shock) < 1e-6:
            return sr.survived_priority_pct
    return p4.shock_results[0].survived_priority_pct if p4.shock_results else 100.0


VERDICT_TIER_ORDER: Dict[VerdictLabel, int] = {
    VerdictLabel.HIGH_PRODUCTIVITY: 0,
    VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY: 1,
    VerdictLabel.OVERLOAD_TRIAGE: 2,
    VerdictLabel.SUBOPTIMAL_ALGORITHM_FAILURE: 3,
    VerdictLabel.INVALID: 4,
}


def evaluate_verdict_and_critiques(
    gates: GateContextMetrics,
    p1: Pillar1ValueTimeliness,
    p2: Pillar2CognitiveBiology,
    p3: Pillar3SustainablePacing,
    p4: Pillar4RobustnessStability,
    config: EvaluationConfig,
    exec_ms: Optional[float] = None,
) -> Tuple[VerdictLabel, List[str], List[str], List[str], List[ICEECritique]]:
    """
    Determine v2.1 Lexicographic Verdict + Top non-noisy ICEE Critiques (Gombolay Conjecture 1).
    Returns `(verdict, verdict_reasons_vi, critical_breaches, moderate_warnings, top_critiques)`.
    """
    critiques: List[ICEECritique] = []
    critical_breaches: List[str] = []
    moderate_warnings: List[str] = []
    reasons_vi: List[str] = []

    shock25_pct = _get_shock_pct(p4, 25.0)
    shock25_failed_ids = p4.shock_results[0].failed_task_ids if p4.shock_results else []

    if gates.g1_total_violations > 0:
        critical_breaches.append(f"G1: {gates.g1_total_violations} vi phạm ràng buộc cứng / bảo toàn PINNED")
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="G1",
                impact_rank=100,
                task_ids=[],
                block_ids=[],
                summary_vi=f"Vi phạm {gates.g1_total_violations} ràng buộc cứng hoặc làm mất block PINNED.",
                rationale_vi=(
                    "Lịch vi phạm ràng buộc cứng (trùng SLEEP/OCCUPIED/block khác, vượt hạn, "
                    "vi phạm depends_on/start_after, tách mảnh sai hoặc xê dịch PINNED) nên không thể thực thi."
                ),
                suggested_action_vi="Kiểm tra danh sách lỗi G1 chi tiết để giải phóng xung đột hoặc khôi phục block PINNED.",
                paper_reference="Schaerf (1999) §1.1–1.2; Myers (2006) SPARK; Gombolay (2017) §3.2.1",
            )
        )

    if exec_ms is not None and exec_ms > config.max_exec_ms_sla:
        moderate_warnings.append(f"HARD-SLA: Thời gian giải {exec_ms:.1f}ms vượt ngưỡng {config.max_exec_ms_sla:.0f}ms")
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="G1",
                impact_rank=40,
                summary_vi=f"Thời gian chạy thuật toán ({exec_ms:.1f}ms) vượt ngưỡng phản hồi nhanh ({config.max_exec_ms_sla:.0f}ms).",
                rationale_vi="Thời gian xử lý quá lâu gây trễ khi sinh viên thao tác tương tác trên giao diện.",
                suggested_action_vi="Giới hạn độ sâu tìm kiếm hoặc chuyển sang chế độ tham lam thích ứng.",
                paper_reference="Vieira et al. (2003) tr. 48",
            )
        )

    if p1.unplaced_deadline_count > 0:
        missed_ids_note = f"mất {p1.missed_deadline_priority} điểm ưu tiên ({p1.unplaced_deadline_count} task)"
        if gates.is_structurally_overloaded:
            reasons_vi.append(f"Đầu vào quá tải cấu trúc (ρ_deadline={gates.rho_deadline}), {missed_ids_note}.")
        else:
            critical_breaches.append(f"P1.1: Rơi {missed_ids_note} dù đầu vào không thiếu sức chứa")
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P1.1",
                impact_rank=95,
                task_ids=list(p1.missed_deadline_task_ids),
                block_ids=[],
                summary_vi=f"Bỏ lọt {p1.unplaced_deadline_count} việc có hạn chót ({p1.unplaced_deadline_min}p, {p1.missed_deadline_priority} điểm priority).",
                rationale_vi=(
                    f"Chỉ đạt {p1.deadline_value_rate_pct}% tổng giá trị ưu tiên. "
                    + (
                        "Nguyên nhân do quá tải cấu trúc (ρ > 1), cần triage cắt giảm việc ưu tiên thấp."
                        if gates.is_structurally_overloaded
                        else "Dù tổng giờ rảnh vẫn đủ (ρ <= 1), cách sắp xếp chưa bảo toàn được hết việc hạn chót."
                    )
                ),
                suggested_action_vi="Bật cho phép tách nhỏ task lớn, hoặc xin dời hạn việc priority thấp / tăng sức chứa.",
                paper_reference="Schaerf (1999) §1.2, §5.1; Vieira et al. (2003) Shafaei & Brunn / Portougal & Robb",
            )
        )

    # BIO-SYNC (P2.1): 2-way Synchrony Off-Peak Mismatch + Achievable Heavy Peak Alignment
    if p2.off_peak_heavy_mismatch_count > 0:
        critical_breaches.append(
            f"BIO-SYNC: Đặt {p2.off_peak_heavy_mismatch_count} block load=3 vào giờ năng lượng thấp (energy=1) dù còn khe tốt hơn"
        )
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P2.1",
                impact_rank=88,
                task_ids=list(p2.off_peak_heavy_mismatch_task_ids),
                block_ids=list(p2.off_peak_heavy_mismatch_blocks),
                summary_vi=f"Đặt {p2.off_peak_heavy_mismatch_count} block nhận thức nặng (load=3) trái nhịp sinh học (energy=1) dù vẫn còn khung giờ năng lượng cao hơn.",
                rationale_vi=(
                    "Theo Synchrony Effect (May & Hasher 1998) và Smarr & Schirmer (2018): làm việc nặng ở khung off-peak "
                    "làm giảm kiểm soát tập trung ở cả nhóm Sáng lẫn nhóm Tối."
                ),
                suggested_action_vi="Dời các block nặng này sang khung PEAK hoặc tối thiểu khung năng lượng trung bình.",
                paper_reference="May & Hasher (1998) Synchrony Effect; Smarr & Schirmer (2018) tr. 5–6; Schaerf (1999)",
            )
        )
    elif p2.achievable_heavy_peak_match_pct is not None and p2.achievable_heavy_peak_match_pct < config.critical_heavy_peak_min_pct:
        critical_breaches.append(
            f"BIO-SYNC: Khớp giờ đỉnh khả thi cho việc nặng quá thấp ({p2.achievable_heavy_peak_match_pct}%)"
        )
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P2.1",
                impact_rank=82,
                summary_vi=f"Chỉ {p2.achievable_heavy_peak_match_pct}% thời lượng việc nặng (có khe Peak khả dụng) được đặt đúng khung đỉnh năng lượng.",
                rationale_vi="Đưa việc đòi hỏi nhận thức sâu vào khung năng lượng thấp dù giờ Peak còn trống làm giảm chất lượng học.",
                suggested_action_vi="Hoán đổi vị trí với các việc nhẹ (load=1) đang chiếm khung Peak.",
                paper_reference="May & Hasher (1998); Schaerf (1999) Junginger; Smarr & Schirmer (2018) tr. 5",
            )
        )
    elif p2.achievable_heavy_peak_match_pct is not None and p2.achievable_heavy_peak_match_pct < config.moderate_heavy_peak_min_pct:
        moderate_warnings.append(
            f"BIO-SYNC: Khớp giờ đỉnh khả thi cho việc nặng dưới kỳ vọng ({p2.achievable_heavy_peak_match_pct}%)"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P2.1",
                impact_rank=55,
                summary_vi=f"Khớp Peak khả thi mới đạt {p2.achievable_heavy_peak_match_pct}%.",
                rationale_vi="Còn dư địa chuyển việc sâu sang khung giờ tỉnh táo hơn để tăng hiệu suất.",
                suggested_action_vi="Ưu tiên dùng SCORED_GREEDY hoặc ghim việc nặng vào khung Peak.",
                paper_reference="May & Hasher (1998); Schaerf (1999) tr. 8, 16; Smarr & Schirmer (2018)",
            )
        )

    # BREAK-SAFE (P2.2): Albulescu >10m break after load=3 + multi-block L>=2 streak cap + post-class transition buffer
    if p2.heavy_recovery_rate_pct is not None and p2.heavy_recovery_rate_pct < 100.0:
        missing = p2.heavy_sessions_total - p2.heavy_sessions_with_gt10m_break
        if p2.crunch_tier_used == 0:
            critical_breaches.append(
                f"BREAK-SAFE: Thiếu nghỉ >10p sau {missing}/{p2.heavy_sessions_total} phiên nặng ({p2.heavy_recovery_rate_pct}%)"
            )
            sev, rank = "CRITICAL", 86
        else:
            moderate_warnings.append(
                f"BREAK-SAFE: Crunch Tier 1 cắt nghỉ >10p ở {missing}/{p2.heavy_sessions_total} phiên nặng"
            )
            sev, rank = "WARNING", 60
        critiques.append(
            ICEECritique(
                severity=sev,
                pillar="P2.2",
                impact_rank=rank,
                task_ids=[],
                block_ids=list(p2.missing_break_block_ids),
                summary_vi=f"Có {missing}/{p2.heavy_sessions_total} phiên nặng (load=3) không có khoảng nghỉ >10 phút (≥1 slot 15p) ngay sau đó.",
                rationale_vi=(
                    "Meta-analysis của Albulescu et al. (2022, N=2335): sau tác vụ nhận thức nặng cần nghỉ >10 phút để phục hồi Vigor và giảm Fatigue. "
                    "Ngay sau block này là block học/lớp khác nên không có khoảng nghỉ."
                ),
                suggested_action_vi="Chèn ít nhất 1 slot trống 15p sau mỗi block load=3.",
                paper_reference="Albulescu et al. (2022) Abstract tr. 1; Results tr. 15; Table 5",
            )
        )

    if p2.max_multi_block_streak_l2_min > config.critical_multi_block_streak_min:
        critical_breaches.append(
            f"BREAK-SAFE: Chuỗi học liên tục load>=2 kéo dài {p2.max_multi_block_streak_l2_min}p (>{config.critical_multi_block_streak_min}p)"
        )
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P2.2",
                impact_rank=80,
                summary_vi=f"Xếp nhiều block liên hoàn (load>=2) thông mạch {p2.max_multi_block_streak_l2_min} phút không nghỉ.",
                rationale_vi="Học liên tục nhiều khối >3h gây mỏi não Time-on-Task và giảm mạnh độ tập trung.",
                suggested_action_vi="Ngắt quãng bằng ít nhất 15 phút nghỉ sau mỗi 90–120 phút học liên tiếp.",
                paper_reference="Albulescu et al. (2022); Ericsson, Krampe & Tesch-Römer (1993)",
            )
        )
    elif p2.max_multi_block_streak_l2_min > config.moderate_multi_block_streak_min:
        moderate_warnings.append(
            f"BREAK-SAFE: Chuỗi học liên tục load>=2 dài {p2.max_multi_block_streak_l2_min}p (>{config.moderate_multi_block_streak_min}p)"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P2.2",
                impact_rank=54,
                summary_vi=f"Chuỗi học ghép nhiều block (load>=2) thông mạch {p2.max_multi_block_streak_l2_min} phút.",
                rationale_vi="Các phiên tập trung bền vững nên dừng ở ngưỡng 60–120 phút rồi nghỉ ngắn trước khi nối tiếp.",
                suggested_action_vi="Chèn khe nghỉ 15p giữa 2 block học nối tiếp.",
                paper_reference="Albulescu et al. (2022); Ericsson et al. (1993)",
            )
        )

    if p2.post_class_buffer_violations >= config.critical_post_class_violations_min:
        critical_breaches.append(
            f"BREAK-SAFE: Xếp ngay việc nặng load=3 sát sau giờ lớp dài ({p2.post_class_buffer_violations} lần)"
        )
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P2.2",
                impact_rank=79,
                block_ids=list(p2.post_class_violation_block_ids),
                summary_vi=f"Có {p2.post_class_buffer_violations} lần xếp việc nặng load=3 ngay phút đầu tiên sau ca học dài trên trường.",
                rationale_vi="Giờ học trên lớp đã tiêu hao nhận thức và cần ít nhất 15p di chuyển/hồi sức trước khi học sâu.",
                suggested_action_vi="Chừa tối thiểu 1 slot 15p đệm sau ca học dài trước khi đặt việc nặng.",
                paper_reference="Albulescu et al. (2022)",
            )
        )
    elif p2.post_class_buffer_violations == 1:
        moderate_warnings.append("BREAK-SAFE: Có 1 block nặng load=3 đặt sát ngay sau giờ lớp dài không đệm nghỉ")
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P2.2",
                impact_rank=49,
                block_ids=list(p2.post_class_violation_block_ids),
                summary_vi="Đặt 1 block load=3 ngay sau giờ học trên trường không có đệm nghỉ 15p.",
                rationale_vi="Chưa có khoảng chuyển tiếp/nghỉ giữa giờ lớp và tự học nặng.",
                suggested_action_vi="Lùi giờ bắt đầu block nặng tối thiểu 15 phút sau giờ tan lớp.",
                paper_reference="Albulescu et al. (2022)",
            )
        )

    # DAILY-CAP (P3.2): Corne >2 heavy/day, total daily load cap (class+study), adj/meal-L2, Context switches
    if p3.heavy_day_overload_days > 0:
        critical_breaches.append(f"DAILY-CAP: Dồn >2 phiên nặng trong cùng 1 ngày ({p3.heavy_day_overload_days} ngày)")
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P3.2",
                impact_rank=84,
                task_ids=[],
                block_ids=list(p3.overload_heavy_block_ids),
                summary_vi=f"Có {p3.heavy_day_overload_days} ngày phải gánh >2 phiên nhận thức nặng (load=3).",
                rationale_vi="Corne et al. phạt nặng nhất việc gánh >2 bài nặng trong cùng một ngày.",
                suggested_action_vi="Tách bớt 1 phiên nặng sang ngày lân cận có tải nhẹ hơn.",
                paper_reference="Corne et al. (1993) trong Schaerf (1999) §4.2, tr. 25",
            )
        )
    elif p3.adjacent_heavy_pairs > 0 or p3.meal_boundary_offenses_l2 > 0:
        moderate_warnings.append(
            f"DAILY-CAP: Cụm nặng sát nhau ({p3.adjacent_heavy_pairs}) hoặc kẹp sát bữa ăn load>=2 ({p3.meal_boundary_offenses_l2})"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P3.2",
                impact_rank=48,
                task_ids=[],
                block_ids=list(p3.adjacent_heavy_block_ids),
                summary_vi=f"Có {p3.adjacent_heavy_pairs} cặp phiên nặng sát nhau và {p3.meal_boundary_offenses_l2} lần kẹp 2 đầu bữa ăn (load>=2).",
                rationale_vi="Xếp việc vừa/nặng sát hai đầu bữa ăn hoặc sát nhau dễ gây quá tải tiêu hóa và mệt mỏi.",
                suggested_action_vi="Chừa ít nhất 15p đệm trước/sau bữa ăn hoặc giãn 2 phiên nặng.",
                paper_reference="Corne et al. (1993), Carter et al. (1994) trong Schaerf (1999) §4.2, tr. 25",
            )
        )

    if p3.max_daily_total_min > config.critical_max_daily_total_min:
        critical_breaches.append(
            f"DAILY-CAP: Tổng tải ngày (lớp+tự học) đỉnh {p3.max_daily_total_min}p (>{config.critical_max_daily_total_min}p)"
        )
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P3.2",
                impact_rank=81,
                summary_vi=f"Có ngày tổng giờ học trên lớp + tự học lên tới {p3.max_daily_total_min} phút (>10 tiếng).",
                rationale_vi="Gombolay (2017 Ch. 6) và Ericsson et al. (1993): quá tải tổng giờ trong ngày làm giảm mạnh chất lượng học và dễ kiệt sức.",
                suggested_action_vi="Chuyển bớt giờ tự học sang các ngày ít lịch lớp cố định.",
                paper_reference="Gombolay (2017) Ch. 6 tr. 181; Ericsson, Krampe & Tesch-Römer (1993)",
            )
        )
    elif p3.max_daily_total_min > config.moderate_max_daily_total_min:
        moderate_warnings.append(
            f"DAILY-CAP: Tổng tải ngày đỉnh {p3.max_daily_total_min}p (>{config.moderate_max_daily_total_min}p)"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P3.2",
                impact_rank=52,
                summary_vi=f"Ngày cao điểm đạt {p3.max_daily_total_min} phút tổng học (lớp + tự học).",
                rationale_vi="Tải ngày >9h tiệm cận ngưỡng mệt mỏi đối với học sinh/sinh viên.",
                suggested_action_vi="San bớt 1–2 block tự học sang ngày rảnh hơn.",
                paper_reference="Gombolay (2017) tr. 181; Ericsson et al. (1993)",
            )
        )

    study_days = sum(1 for m in p3.daily_load_minutes if m > 0)
    ctx_limit = max(config.moderate_context_switches_max, study_days)
    if p3.focus_context_switches >= ctx_limit:
        moderate_warnings.append(
            f"FOCUS-FLOW: Đổi loại việc/môn liên tiếp {p3.focus_context_switches} lần (ngưỡng {ctx_limit})"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P3.2",
                impact_rank=44,
                summary_vi=f"Có {p3.focus_context_switches} lần nhảy qua lại giữa các loại công việc khác nhau với khoảng cách ngắn (ngưỡng {ctx_limit}).",
                rationale_vi="Leroy (2009): chuyển việc liên tục tạo Attention Residue khiến não không đạt độ sâu tập trung.",
                suggested_action_vi="Gom các task cùng category/môn học lại gần nhau (batching).",
                paper_reference="Leroy (2009) OBHDP 109(2):168–181; Vieira et al. (2003) tr. 48",
            )
        )

    # SHOCK-SAFE (P4.1)
    if shock25_pct < config.critical_shock25_min_pct:
        critical_breaches.append(f"SHOCK-SAFE: Dưới sốc +25% chỉ còn {shock25_pct}% priority sống sót")
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P4.1",
                impact_rank=89,
                task_ids=list(shock25_failed_ids[:5]),
                summary_vi=f"Lịch dễ vỡ dây chuyền: khi thời lượng tăng +25%, chỉ {shock25_pct}% giá trị priority còn kịp hạn.",
                rationale_vi=(
                    f"Tỷ lệ task có buffer phòng vệ thực sự mới đạt {p4.true_buffer_task_pct}% và có {p4.zero_slack_risk_blocks} "
                    "block nằm sát vách 0-slot slack."
                ),
                suggested_action_vi="Bật `buffer_mode=COGNITIVE_LOAD` hoặc chừa khe đệm 15p sau các block quan trọng.",
                paper_reference="Vieira et al. (2003) Mehta & Uzsoy tr. 53 / Daniels & Kouvelis tr. 45; Myers (2006) EMP",
            )
        )
    elif shock25_pct < config.moderate_shock25_min_pct:
        moderate_warnings.append(f"SHOCK-SAFE: Buffer={p4.true_buffer_task_pct}%, Shock@+25% còn {shock25_pct}%")
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P4.1",
                impact_rank=58,
                task_ids=list(shock25_failed_ids[:5]),
                summary_vi=f"Đệm phòng vệ còn mỏng (Buffer={p4.true_buffer_task_pct}%, Shock@+25%={shock25_pct}%).",
                rationale_vi="Thiếu đệm làm phần tràn đâm vào block sau/lịch cứng/hạn chót.",
                suggested_action_vi="Cân nhắc bật estimate buffer theo cognitive load để tăng độ an toàn thực thi.",
                paper_reference="Mehta & Uzsoy (1998) trong Vieira tr. 53; Myers (2006) EMP tr. 6–7",
            )
        )
    elif p4.true_buffer_task_pct == 0.0 and p4.total_tasks_checked > 0:
        critiques.append(
            ICEECritique(
                severity="INFO",
                pillar="P4.1",
                impact_rank=15,
                summary_vi=f"Đầu vào đang tắt buffer (Buffer=0.0%), nhưng lịch vẫn chừa khe trống đạt Shock@+25%={shock25_pct}%.",
                rationale_vi="Nhờ còn khe đệm rảnh sau các block nên lịch vẫn chịu được lố giờ +25% mà không đè block sau.",
                suggested_action_vi="Có thể cân nhắc bật `buffer_mode=COGNITIVE_LOAD` nếu muốn khóa đệm cứng ngay trong thời lượng block.",
                paper_reference="Mehta & Uzsoy (1998) trong Vieira tr. 53; Myers (2006) EMP tr. 6–7",
            )
        )

    # USER-PREF: Habit preservation + preferred window when load rho_total <= 0.85
    if gates.rho_total <= config.habit_check_max_rho:
        if p1.habit_value_rate_pct is not None:
            if p1.habit_value_rate_pct < config.critical_habit_rate_min_pct:
                critical_breaches.append(f"USER-PREF: Bỏ quá nhiều thói quen cá nhân (chỉ giữ {p1.habit_value_rate_pct}%)")
                critiques.append(
                    ICEECritique(
                        severity="CRITICAL",
                        pillar="P1.1",
                        impact_rank=77,
                        summary_vi=f"Tuần còn rảnh (ρ={gates.rho_total}) nhưng chỉ giữ được {p1.habit_value_rate_pct}% thói quen HABIT.",
                        rationale_vi="Gombolay (2017) & Myers (2006): lịch bỏ qua thói quen sinh hoạt khiến người dùng nhanh chóng từ bỏ hệ thống.",
                        suggested_action_vi="Xếp bổ sung các phiên PersonalHabit vào khe rảnh phù hợp.",
                        paper_reference="Gombolay (2017) §2.5.4; Myers et al. (2006) PExA tr. 9",
                    )
                )
            elif p1.habit_value_rate_pct < config.moderate_habit_rate_min_pct:
                moderate_warnings.append(f"USER-PREF: Tỷ lệ giữ thói quen HABIT thấp ({p1.habit_value_rate_pct}%)")
                critiques.append(
                    ICEECritique(
                        severity="WARNING",
                        pillar="P1.1",
                        impact_rank=51,
                        summary_vi=f"Tỷ lệ hoàn thành thói quen cá nhân mới đạt {p1.habit_value_rate_pct}%.",
                        rationale_vi="Vẫn còn quỹ giờ trống để duy trì đều thói quen cá nhân.",
                        suggested_action_vi="Đưa thêm thói quen vào các ngày nhẹ tải.",
                        paper_reference="Gombolay (2017) §2.5.4; Myers et al. (2006)",
                    )
                )
        if p2.preferred_window_match_pct is not None and p2.preferred_window_match_pct < config.moderate_preferred_window_min_pct:
            moderate_warnings.append(f"USER-PREF: Khớp khung giờ ưa thích thấp ({p2.preferred_window_match_pct}%)")
            critiques.append(
                ICEECritique(
                    severity="WARNING",
                    pillar="P2.1",
                    impact_rank=46,
                    summary_vi=f"Chỉ {p2.preferred_window_match_pct}% thời lượng rơi đúng khung giờ người dùng chọn (preferred_window).",
                    rationale_vi="Phớt lờ sở thích cá nhân làm giảm sự hài lòng và mức độ tuân thủ lịch.",
                    suggested_action_vi="Ưu tiên đặt task đúng preferred_window khi tải không căng.",
                    paper_reference="Gombolay (2017) Ch. 6; Myers et al. (2006) tr. 9",
                )
            )

    # NO-CRAM (P1.2)
    if p1.unjustified_last_10h_crowding_pct > config.critical_last10h_crowding_max_pct:
        critical_breaches.append(
            f"NO-CRAM: Dồn {p1.unjustified_last_10h_crowding_pct}% khối lượng cửa sổ rộng vào <10h sát hạn dù có slot tốt sớm hơn"
        )
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P1.2",
                impact_rank=78,
                task_ids=list(p1.unjustified_last_10h_task_ids),
                summary_vi=f"Trì hoãn bất hợp lý: {p1.unjustified_last_10h_crowding_pct}% khối lượng bị dồn vào <10h trước hạn chót.",
                rationale_vi="Trước đoạn <10h đã có khoảng trống hợp lệ đạt mức năng lượng tương đương/cao hơn nhưng không khởi phát.",
                suggested_action_vi="Kéo khối lượng của các task này lên sớm hơn để giảm rủi ro dồn hạn phút chót.",
                paper_reference="Svartdal et al. (2018) Howell (2006) Table 2 tr. 4",
            )
        )
    elif p1.unjustified_last_10h_crowding_pct > config.moderate_last10h_crowding_max_pct or (
        p1.heavy_onset_delay_pct is not None and p1.heavy_onset_delay_pct > config.moderate_onset_delay_max_pct
    ):
        moderate_warnings.append(
            f"NO-CRAM: Khởi phát muộn (heavy onset={p1.heavy_onset_delay_pct}%, <10h={p1.unjustified_last_10h_crowding_pct}%)"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P1.2",
                impact_rank=45,
                task_ids=list(p1.unjustified_last_10h_task_ids),
                summary_vi="Xu hướng trì hoãn khởi phát với tác vụ đòi hỏi nhận thức nặng.",
                rationale_vi="Khởi phát càng muộn càng thu hẹp biên độ sửa sai khi gặp khó khăn bất ngờ.",
                suggested_action_vi="Bắt đầu phiên tiền đề/khởi động ngay khung năng lượng phù hợp đầu tiên.",
                paper_reference="Svartdal et al. (2018) tr. 2–4, Studies 3a–3b",
            )
        )

    # PACE-BALANCE (P2.3 SJL calibrated + P3.1 Total Daily Std calibrated)
    if p2.sjl_minutes is not None:
        is_adv_warn = p2.sjl_direction == "PHASE_ADVANCE" and p2.sjl_minutes > config.moderate_sjl_advance_max_min
        is_del_warn = p2.sjl_minutes > config.moderate_sjl_delay_max_min
        if is_adv_warn or is_del_warn:
            moderate_warnings.append(f"PACE-BALANCE: SJL={p2.sjl_minutes}p ({p2.sjl_direction})")
            critiques.append(
                ICEECritique(
                    severity="WARNING",
                    pillar="P2.3",
                    impact_rank=50,
                    summary_vi=f"Pha tự học ngày có lớp lệch {p2.sjl_minutes}p so với ngày không có lớp ({p2.sjl_direction}).",
                    rationale_vi="Smarr & Schirmer (2018): lệch pha lớn (đặc biệt PHASE_ADVANCE ngày có lớp) ảnh hưởng bất lợi đến kết quả học tập.",
                    suggested_action_vi="Giữ khung giờ tự học giữa ngày có lớp và ngày nghỉ gần nhau hơn.",
                    paper_reference="Smarr & Schirmer (2018) tr. 4–6, Methods tr. 8",
                )
            )

    if len(p3.total_daily_load_minutes) >= 3 and p3.total_daily_load_std_min > p3.effective_daily_std_limit_min:
        moderate_warnings.append(
            f"PACE-BALANCE: Tổng tải ngày (lớp+tự học) lệch cao (std={p3.total_daily_load_std_min}p > {p3.effective_daily_std_limit_min}p)"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P3.1",
                impact_rank=42,
                summary_vi=f"Tổng tải giờ học/ngày mất cân bằng (std={p3.total_daily_load_std_min}p > ngưỡng hiệu chỉnh {p3.effective_daily_std_limit_min}p).",
                rationale_vi="Tập trung quá nhiều giờ học vào vài ngày cố định gây kiệt sức cục bộ.",
                suggested_action_vi="San bớt giờ tự học từ ngày có lớp nhiều sang ngày trống hơn.",
                paper_reference="Colorni et al. (1992) trong Schaerf tr. 8; Gombolay (2017) tr. 143",
            )
        )

    # Verdict Decision Tree
    if gates.g1_total_violations > 0:
        verdict = VerdictLabel.INVALID
        reasons_vi.append(f"Không hợp lệ: vi phạm {gates.g1_total_violations} điều kiện G1.")
    elif p1.unplaced_deadline_count > 0:
        if gates.is_structurally_overloaded:
            verdict = VerdictLabel.OVERLOAD_TRIAGE
            reasons_vi.append(
                f"Đầu vào quá tải (ρ_total={gates.rho_total}, ρ_deadline={gates.rho_deadline}); "
                f"giữ được {p1.deadline_value_rate_pct}% điểm ưu tiên."
            )
        else:
            verdict = VerdictLabel.SUBOPTIMAL_ALGORITHM_FAILURE
            reasons_vi.append(
                f"Sức chứa lý thuyết vẫn đủ (ρ_total={gates.rho_total}, ρ_deadline={gates.rho_deadline}) "
                f"nhưng bị rơi {p1.unplaced_deadline_count} việc có hạn."
            )
    elif len(critical_breaches) >= 1 or len(moderate_warnings) >= 2:
        verdict = VerdictLabel.FEASIBLE_BUT_LOW_PRODUCTIVITY
        reasons_vi.extend(critical_breaches or moderate_warnings[:2])
    else:
        verdict = VerdictLabel.HIGH_PRODUCTIVITY
        reasons_vi.append(
            f"Đạt G1=0, P1.1={p1.deadline_value_rate_pct}%, Shock@+25%={shock25_pct}% và vượt chuẩn v2.1 (Cổng 0 + 10 tiêu chí)."
        )

    critiques.sort(key=lambda c: (-c.impact_rank, c.pillar))
    top_critiques = critiques[: config.max_icee_critiques]
    return verdict, reasons_vi, critical_breaches, moderate_warnings, top_critiques


def rank_cross_solver_reports(
    reports: Dict[str, EvaluationReport], config: Optional[EvaluationConfig] = None
) -> List[CrossSolverEntry]:
    """
    v2.1 Human-Centric Cross-Solver Comparison:
      Gate 0 (HARD-RULE: G1, SLA) + 10-Level Epsilon-Bucketed Lexicographic Ranking starting with Verdict Tier.
    Never collapses heterogeneous metrics into an opaque linear weighted score.
    """
    cfg = config or EvaluationConfig()
    sortable: List[Tuple[Tuple, CrossSolverEntry]] = []

    for solver_name, rep in reports.items():
        p1 = rep.p1_value_timeliness
        p2 = rep.p2_cognitive_biology
        p3 = rep.p3_sustainable_pacing
        shock25 = _get_shock_pct(rep.p4_robustness_stability, 25.0)
        rec = p2.heavy_recovery_rate_pct
        ach_peak = p2.achievable_heavy_peak_match_pct
        raw_peak = p2.heavy_peak_match_pct
        sjl_raw = p2.sjl_minutes
        sjl_eff = 90.0 if p2.sjl_neutral_unpaired else (sjl_raw if sjl_raw is not None else 0.0)
        hab = p1.habit_value_rate_pct
        pref = p2.preferred_window_match_pct
        sla_exceeded = rep.diagnostics.execution_time_ms > cfg.max_exec_ms_sla

        lex_key = (
            rep.gates.g1_total_violations,                                                      # Gate 0a: HARD-RULE G1
            1 if sla_exceeded else 0,                                                           # Gate 0b: SLA <= 1000ms
            VERDICT_TIER_ORDER.get(rep.verdict, 9),                                             # #1 QUALITY-TIER
            -p1.deadline_value_rate_pct,                                                        # #2 DEADLINE-VAL
            -int(shock25 // 5) * 5,                                                             # #3 SHOCK-SAFE (5% bucket)
            (                                                                                   # #4 BREAK-SAFE
                -int((rec if rec is not None else 100.0) // 5) * 5,
                max(0, p2.max_multi_block_streak_l2_min - 90) // 30,
                p2.post_class_buffer_violations,
            ),
            (                                                                                   # #5 BIO-SYNC
                p2.off_peak_heavy_mismatch_count,
                -int((ach_peak if ach_peak is not None else 100.0) // 10) * 10,
            ),
            int(p1.unjustified_last_10h_crowding_pct // 5) * 5,                                 # #6 NO-CRAM (5% bucket)
            (                                                                                   # #7 DAILY-CAP
                p3.heavy_day_overload_days,
                max(0, p3.max_daily_total_min - cfg.moderate_max_daily_total_min) // 30,
                p3.adjacent_heavy_pairs,
                p3.meal_boundary_offenses_l2,
            ),
            p3.focus_context_switches,                                                          # #8 FOCUS-FLOW
            (                                                                                   # #9 USER-PREF
                -int((hab if hab is not None else 100.0) // 10) * 10,
                -int((pref if pref is not None else 100.0) // 10) * 10,
            ),
            (                                                                                   # #10 PACE-BALANCE
                int(sjl_eff // 30) * 30,
                int(p3.total_daily_load_std_min // 30) * 30,
            ),
        )

        entry = CrossSolverEntry(
            solver_name=solver_name,
            lexicographic_rank=1,
            verdict=rep.verdict,
            g1_violations=rep.gates.g1_total_violations,
            p1_value_rate_pct=p1.deadline_value_rate_pct,
            p4_shock25_survived_pct=shock25,
            p2_heavy_peak_pct=raw_peak,
            p2_recovery_rate_pct=rec,
            p2_forced_phase_advance=p2.forced_phase_advance_count,
            p1_unjustified_last10h_pct=p1.unjustified_last_10h_crowding_pct,
            p2_sjl_minutes=sjl_raw,
            p3_corne_vector=list(p3.corne_lexicographic_vector),
            p3_daily_load_std_min=p3.daily_load_std_min,
            exec_ms=rep.diagnostics.execution_time_ms,
            v2_achievable_peak_pct=ach_peak,
            v2_off_peak_mismatch=p2.off_peak_heavy_mismatch_count,
            v2_max_streak_l2_min=p2.max_multi_block_streak_l2_min,
            v2_post_class_violations=p2.post_class_buffer_violations,
            v2_max_daily_total_min=p3.max_daily_total_min,
            v2_total_daily_std_min=p3.total_daily_load_std_min,
            v2_meal_l2_offenses=p3.meal_boundary_offenses_l2,
            v2_context_switches=p3.focus_context_switches,
            v2_habit_rate_pct=hab,
            v2_preferred_window_pct=pref,
            v2_sjl_effective_min=sjl_eff,
            v2_sla_exceeded=sla_exceeded,
        )
        sortable.append((lex_key, entry))

    sortable.sort(key=lambda item: item[0])
    ranked: List[CrossSolverEntry] = []
    for idx, (_, entry) in enumerate(sortable, start=1):
        ranked.append(entry.model_copy(update={"lexicographic_rank": idx}))
    return ranked


def build_auxiliary_diagnostics(
    base_grid,
    blocks,
    prepared_tasks,
    schedule,
    p1: Pillar1ValueTimeliness,
    insights: Dict,
) -> AuxiliaryDiagnostics:
    """Populate D2 auxiliary technical diagnostics over full horizon_slots without 672 truncation."""
    from Testing_System.sut_adapter import calculate_fragmentation_index, round_up_to_15

    occ_grid = base_grid.clone()
    for b in blocks:
        length = b.end_slot - b.start_slot
        if length > 0 and b.start_slot >= 0 and b.end_slot <= occ_grid.total_slots and occ_grid.is_range_free(b.start_slot, length):
            occ_grid.place_block(b.start_slot, length, b.task_id, b.title)

    frag_pct = calculate_fragmentation_index(occ_grid, up_to=occ_grid.total_slots)

    # Check work_rhythm compliance over placed multi-chunk or single-chunk tasks
    task_map = {t.task_id: t for t in prepared_tasks}
    rhythm_checked = 0
    rhythm_ok = 0
    for b in blocks:
        t = task_map.get(b.task_id)
        if t and t.work_rhythm in ("LIGHT", "BALANCED", "FLOW"):
            rhythm_checked += 1
            min_b = max(15, round_up_to_15(t.min_chunk_min))
            max_b = max(min_b, round_up_to_15(t.max_chunk_min))
            if min_b <= b.duration_min <= max_b or b.duration_min <= max_b:
                rhythm_ok += 1
    rhythm_pct = round(100.0 * rhythm_ok / float(rhythm_checked), 2) if rhythm_checked > 0 else 100.0

    return AuxiliaryDiagnostics(
        fragmentation_index_pct=frag_pct,
        execution_time_ms=round(float(schedule.execution_time_ms), 3),
        work_rhythm_compliance_pct=rhythm_pct,
        habit_completion_pct=p1.habit_value_rate_pct,
        existing_deep_peak_match_pct=float(insights.get("deep_peak_match_pct", 100.0)),
        existing_experience_rating=float(schedule.summary.experience_rating),
    )

