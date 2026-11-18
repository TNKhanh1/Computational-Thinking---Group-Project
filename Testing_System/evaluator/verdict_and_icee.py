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


def evaluate_verdict_and_critiques(
    gates: GateContextMetrics,
    p1: Pillar1ValueTimeliness,
    p2: Pillar2CognitiveBiology,
    p3: Pillar3SustainablePacing,
    p4: Pillar4RobustnessStability,
    config: EvaluationConfig,
) -> Tuple[VerdictLabel, List[str], List[str], List[str], List[ICEECritique]]:
    """
    Determine Lexicographic Verdict + Top 3-5 non-noisy ICEE Critiques (Gombolay Conjecture 1).
    Returns `(verdict, verdict_reasons_vi, critical_breaches, moderate_warnings, top_critiques)`.
    """
    critiques: List[ICEECritique] = []
    critical_breaches: List[str] = []
    moderate_warnings: List[str] = []
    reasons_vi: List[str] = []

    shock25_pct = _get_shock_pct(p4, 25.0)
    shock25_failed_ids = p4.shock_results[0].failed_task_ids if p4.shock_results else []

    # Collect structured diagnostic issues for D1 ICEE regardless of gate pass/fail
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

    # Pillar P2.1: Forced Phase Advance on Owl or low heavy Peak alignment
    if p2.forced_phase_advance_count > 0:
        critical_breaches.append(
            f"P2.1: Ép Owl học nặng vào sáng 06:00–12:00 ({p2.forced_phase_advance_count} block)"
        )
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P2.1",
                impact_rank=88,
                task_ids=list(p2.forced_phase_advance_task_ids),
                block_ids=list(p2.forced_phase_advance_blocks),
                summary_vi=f"Ép {p2.forced_phase_advance_count} block nhận thức nặng (load=3) của cú đêm (Owl) vào sáng 06:00–12:00.",
                rationale_vi=(
                    "Khung sáng có energy_level=1 trong khi cùng cửa sổ hạn chót vẫn còn khung chiều/tối năng lượng cao hơn. "
                    "Smarr & Schirmer: sớm pha (advance) vào ngày học tương quan âm với GPA và nhóm Owl chịu bất lợi điểm số lớn nhất."
                ),
                suggested_action_vi="Dời các block nặng này sang khung PEAK chiều/tối của hồ sơ sinh học.",
                paper_reference="Smarr & Schirmer (2018) tr. 5–6; Schaerf (1999) Junginger / De Werra",
            )
        )
    elif p2.heavy_peak_match_pct is not None and p2.heavy_peak_match_pct < config.critical_heavy_peak_min_pct:
        critical_breaches.append(f"P2.1: Khớp Peak cho việc nặng (load=3) quá thấp ({p2.heavy_peak_match_pct}%)")
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P2.1",
                impact_rank=82,
                summary_vi=f"Chỉ {p2.heavy_peak_match_pct}% thời lượng việc nặng (load=3) nằm đúng khung đỉnh năng lượng.",
                rationale_vi="Đưa việc đòi hỏi nhận thức sâu vào khung năng lượng thấp làm giảm chất lượng đầu ra và tăng mệt mỏi.",
                suggested_action_vi="Hoán đổi vị trí với các việc nhẹ (load=1) đang chiếm khung Peak.",
                paper_reference="Schaerf (1999) Junginger; Smarr & Schirmer (2018) tr. 5",
            )
        )
    elif p2.heavy_peak_match_pct is not None and p2.heavy_peak_match_pct < config.moderate_heavy_peak_min_pct:
        moderate_warnings.append(f"P2.1: Khớp Peak việc nặng dưới mức kỳ vọng ({p2.heavy_peak_match_pct}%)")
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P2.1",
                impact_rank=55,
                summary_vi=f"Khớp Peak việc nặng mới đạt {p2.heavy_peak_match_pct}%.",
                rationale_vi="Còn dư địa chuyển việc sâu sang khung giờ tỉnh táo hơn để tăng hiệu suất.",
                suggested_action_vi="Ưu tiên dùng SCORED_GREEDY/BACKTRACK hoặc ghim việc nặng vào khung Peak.",
                paper_reference="Schaerf (1999) tr. 8, 16; Smarr & Schirmer (2018)",
            )
        )

    # Pillar P2.2: Albulescu > 10 min break after cognitively demanding work
    if p2.heavy_recovery_rate_pct is not None and p2.heavy_recovery_rate_pct < 100.0:
        missing = p2.heavy_sessions_total - p2.heavy_sessions_with_gt10m_break
        # Plan §4.3: missing breaks are critical unless the solver explicitly entered Crunch Tier 1
        # (break cutting to rescue unplaced deadline work), which is reported as a warning.
        if p2.crunch_tier_used == 0:
            critical_breaches.append(
                f"P2.2: Thiếu khoảng nghỉ >10p sau {missing}/{p2.heavy_sessions_total} phiên nặng ({p2.heavy_recovery_rate_pct}%)"
            )
            sev = "CRITICAL"
            rank = 86
        else:
            moderate_warnings.append(
                f"P2.2: Crunch Tier 1 cắt nghỉ >10p ở {missing}/{p2.heavy_sessions_total} phiên nặng"
            )
            sev = "WARNING"
            rank = 60
        critiques.append(
            ICEECritique(
                severity=sev,
                pillar="P2.2",
                impact_rank=rank,
                task_ids=[],
                block_ids=list(p2.missing_break_block_ids),
                summary_vi=f"Có {missing}/{p2.heavy_sessions_total} phiên nặng (load=3) không có khoảng nghỉ >10 phút (≥1 slot 15p) ngay sau đó.",
                rationale_vi=(
                    "Meta-analysis của Albulescu et al. (N=2335, k=22): sau tác vụ nhận thức, micro-break <=10p không cải thiện "
                    "hiệu năng (d=-.09, p=.541); thời lượng nghỉ dài hơn tăng hiệu năng (b=.07, p=.006), tác giả gợi ý cần nghỉ >10 phút. "
                    "Ngay sau block này là block học/lớp/sự kiện khác nên không có khoảng nghỉ."
                ),
                suggested_action_vi="Chèn ít nhất 1 slot trống 15p sau mỗi block load=3.",
                paper_reference="Albulescu et al. (2022) Abstract tr. 1; Results tr. 15; Table 5",
            )
        )

    # Pillar P3.2: Corne > 2 heavy blocks / day
    if p3.heavy_day_overload_days > 0:
        critical_breaches.append(f"P3.2: Dồn >2 phiên nặng trong cùng 1 ngày ({p3.heavy_day_overload_days} ngày)")
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P3.2",
                impact_rank=84,
                task_ids=[],
                block_ids=list(p3.overload_heavy_block_ids),
                summary_vi=f"Có {p3.heavy_day_overload_days} ngày phải gánh >2 phiên nhận thức nặng (load=3).",
                rationale_vi=(
                    "Corne et al. phạt nặng nhất trường hợp người học phải làm >2 bài nặng trong cùng một ngày "
                    "(xếp trên cả lỗi 2 bài liền kề và lỗi kẹp hai đầu bữa trưa)."
                ),
                suggested_action_vi="Tách bớt 1 phiên nặng sang ngày lân cận có tải nhẹ hơn.",
                paper_reference="Corne et al. (1993) trong Schaerf (1999) §4.2, tr. 25",
            )
        )
    elif p3.adjacent_heavy_pairs > 0 or p3.meal_boundary_offenses > 0:
        moderate_warnings.append(
            f"P3.2: Cụm phiên nặng sát nhau ({p3.adjacent_heavy_pairs}) hoặc kẹp sát bữa ăn ({p3.meal_boundary_offenses})"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P3.2",
                impact_rank=48,
                task_ids=[],
                block_ids=list(p3.adjacent_heavy_block_ids),
                summary_vi=(
                    f"Phát hiện {p3.adjacent_heavy_pairs} cặp phiên nặng gần nhau và {p3.meal_boundary_offenses} lần kẹp 2 đầu bữa ăn."
                ),
                rationale_vi=(
                    "Corne et al. phạt 2 bài liền kề và 2 bài sát trước + sát sau bữa trưa; Carter et al. coi hai đầu bữa trưa "
                    "là các kỳ 'liên tiếp'. Đây là 2 mức phạt thấp hơn lỗi >2 bài/ngày."
                ),
                suggested_action_vi="Chừa ít nhất 15p đệm trước/sau bữa ăn hoặc giãn khoảng cách giữa 2 phiên nặng.",
                paper_reference="Corne et al. (1993), Carter et al. (1994) trong Schaerf (1999) §4.2, tr. 25",
            )
        )

    # Pillar P4.1: Shock Survival Under +25% Duration Uncertainty
    if shock25_pct < config.critical_shock25_min_pct:
        critical_breaches.append(f"P4.1: Dưới sốc +25% chỉ còn {shock25_pct}% priority sống sót")
        critiques.append(
            ICEECritique(
                severity="CRITICAL",
                pillar="P4.1",
                impact_rank=89,
                task_ids=list(shock25_failed_ids[:5]),
                summary_vi=f"Lịch dễ vỡ dây chuyền: khi thời lượng tăng +25%, chỉ {shock25_pct}% giá trị priority còn kịp hạn.",
                rationale_vi=(
                    f"Tỷ lệ task có buffer phòng vệ thực sự mới đạt {p4.true_buffer_task_pct}% và có {p4.zero_slack_risk_blocks} "
                    "block nằm sát vách 0-slot slack, chỉ cần tràn nhẹ sẽ đâm vào block sau/lịch cứng/hạn chót."
                ),
                suggested_action_vi="Bật `buffer_mode=COGNITIVE_LOAD` hoặc chừa khe đệm 15p sau các block quan trọng.",
                paper_reference="Vieira et al. (2003) Mehta & Uzsoy tr. 53 / Daniels & Kouvelis tr. 45; Myers (2006) EMP",
            )
        )
    elif shock25_pct < config.moderate_shock25_min_pct or (p4.true_buffer_task_pct == 0.0 and p4.total_tasks_checked > 0):
        moderate_warnings.append(
            f"P4.1: Buffer thực={p4.true_buffer_task_pct}%, Shock@+25% còn {shock25_pct}%"
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P4.1",
                impact_rank=58,
                task_ids=list(shock25_failed_ids[:5]),
                summary_vi=f"Đệm phòng vệ còn mỏng (Buffer={p4.true_buffer_task_pct}%, Shock@+25%={shock25_pct}%).",
                rationale_vi=(
                    "Mehta & Uzsoy: chèn thời gian rảnh (inserted idle time) làm lịch dự đoán được hơn mà không giảm đáng kể "
                    "hiệu năng; thiếu đệm làm phần tràn đâm vào block sau/lịch cứng/hạn chót."
                ),
                suggested_action_vi="Cân nhắc bật estimate buffer theo cognitive load để tăng độ an toàn thực thi.",
                paper_reference="Mehta & Uzsoy (1998) trong Vieira tr. 53; Myers (2006) EMP tr. 6–7",
            )
        )

    # Pillar P1.2: Unjustified < 10h procrastination
    if p1.unjustified_last_10h_crowding_pct > config.critical_last10h_crowding_max_pct:
        critical_breaches.append(
            f"P1.2: Dồn {p1.unjustified_last_10h_crowding_pct}% khối lượng cửa sổ rộng vào <10h sát hạn dù có slot tốt sớm hơn"
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
            f"P1.2: Khởi phát muộn (heavy onset delay={p1.heavy_onset_delay_pct}%, <10h={p1.unjustified_last_10h_crowding_pct}%)"
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

    # Pillar P2.3: Social Jetlag > 30 min (Smarr & Schirmer: 60% of students exceed 30 min; larger SJL
    # correlates with lower GPA, advances on class days more strongly than delays)
    if p2.sjl_exceeds_30m is True:
        moderate_warnings.append(f"P2.3: SJL={p2.sjl_minutes}p ({p2.sjl_direction})")
        advance_note = (
            " Lệch theo hướng sớm pha (advance) vào ngày có lớp — hướng có tương quan âm mạnh nhất với GPA."
            if p2.sjl_direction == "PHASE_ADVANCE"
            else ""
        )
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P2.3",
                impact_rank=50,
                task_ids=[],
                block_ids=[],
                summary_vi=(
                    f"Pha tự học ngày có lớp lệch {p2.sjl_minutes}p so với ngày không có lớp ({p2.sjl_direction})."
                ),
                rationale_vi=(
                    "Smarr & Schirmer (N=14,894) đo SJL bằng hiệu trung vị pha tròn giữa ngày có lớp và ngày không lớp; "
                    "60% sinh viên có SJL >30 phút và SJL càng lớn GPA càng giảm." + advance_note
                ),
                suggested_action_vi="Giữ khung giờ tự học của ngày có lớp gần với khung giờ của ngày không có lớp.",
                paper_reference="Smarr & Schirmer (2018) tr. 4–6, Methods tr. 8",
            )
        )

    # Pillar P3.1: Weekly Load Dispersion
    if p3.active_days_count >= 3 and p3.daily_load_std_min > config.moderate_max_daily_load_std_min:
        moderate_warnings.append(f"P3.1: Phân bố tải giữa các ngày lệch cao (std={p3.daily_load_std_min}p)")
        critiques.append(
            ICEECritique(
                severity="WARNING",
                pillar="P3.1",
                impact_rank=42,
                summary_vi=f"Khối lượng tự học dồn cục theo ngày (độ lệch chuẩn {p3.daily_load_std_min} phút/ngày).",
                rationale_vi="Chênh lệch tải quá lớn giữa các ngày dễ gây kiệt sức cục bộ và mất nhịp duy trì đều đặn.",
                suggested_action_vi="San đều bớt giờ học từ ngày cao điểm sang các ngày nhẹ tải hơn.",
                paper_reference="Colorni et al. (1992) trong Schaerf tr. 8; Gombolay (2017) tr. 143",
            )
        )

    # Lexicographic Verdict Decision Tree (Plan §4.3 Bước 4)
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
            f"Đạt G1=0, P1.1={p1.deadline_value_rate_pct}%, Shock@+25%={shock25_pct}% và giữ vững các trụ cột P2–P4."
        )

    # Enforce Gombolay Conjecture 1 non-noise alert budget (Top max_icee_critiques by impact)
    critiques.sort(key=lambda c: (-c.impact_rank, c.pillar))
    top_critiques = critiques[: config.max_icee_critiques]

    return verdict, reasons_vi, critical_breaches, moderate_warnings, top_critiques


def rank_cross_solver_reports(reports: Dict[str, EvaluationReport]) -> List[CrossSolverEntry]:
    """
    D2 Cross-Solver Comparison using Lexicographic Preference (Schaerf §7.3-7.5; Colorni; Gombolay §5.3).
    Never collapses metrics into an opaque linear weighted score.
    """
    sortable: List[Tuple[Tuple, CrossSolverEntry]] = []

    for solver_name, rep in reports.items():
        shock25 = _get_shock_pct(rep.p4_robustness_stability, 25.0)
        rec = rep.p2_cognitive_biology.heavy_recovery_rate_pct
        peak = rep.p2_cognitive_biology.heavy_peak_match_pct
        sjl = rep.p2_cognitive_biology.sjl_minutes

        lex_key = (
            rep.gates.g1_total_violations,
            -rep.p1_value_timeliness.deadline_value_rate_pct,
            -shock25,
            -(rec if rec is not None else 100.0),
            rep.p2_cognitive_biology.forced_phase_advance_count,
            -(peak if peak is not None else 100.0),
            rep.p1_value_timeliness.unjustified_last_10h_crowding_pct,
            sjl if sjl is not None else 0.0,
            tuple(rep.p3_sustainable_pacing.corne_lexicographic_vector),
            rep.p3_sustainable_pacing.daily_load_std_min,
            rep.diagnostics.execution_time_ms,
        )

        entry = CrossSolverEntry(
            solver_name=solver_name,
            lexicographic_rank=1,
            verdict=rep.verdict,
            g1_violations=rep.gates.g1_total_violations,
            p1_value_rate_pct=rep.p1_value_timeliness.deadline_value_rate_pct,
            p4_shock25_survived_pct=shock25,
            p2_heavy_peak_pct=peak,
            p2_recovery_rate_pct=rec,
            p2_forced_phase_advance=rep.p2_cognitive_biology.forced_phase_advance_count,
            p1_unjustified_last10h_pct=rep.p1_value_timeliness.unjustified_last_10h_crowding_pct,
            p2_sjl_minutes=sjl,
            p3_corne_vector=list(rep.p3_sustainable_pacing.corne_lexicographic_vector),
            p3_daily_load_std_min=rep.p3_sustainable_pacing.daily_load_std_min,
            exec_ms=rep.diagnostics.execution_time_ms,
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

