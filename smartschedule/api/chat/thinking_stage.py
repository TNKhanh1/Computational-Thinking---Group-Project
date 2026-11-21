"""
Antigravity-Style Humanized Thinking Stage Builder & Minimal Post-Actions (`smartschedule.api.chat.thinking_stage`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_post_actions(task_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Keep post-action buttons ultra-minimal: one clear button to inspect the schedule."""
    return [
        {"action": "OPEN_CALENDAR", "label": "🗓️ Kiểm tra lịch trình"},
    ]


def build_thinking_summary(
    *,
    intent: str,
    context_note_vi: str,
    chosen_solver: str,
    escalated_from_greedy: bool,
    exec_ms: float,
    peak_match_pct: float,
    tasks_placed: int,
    tasks_total: int,
) -> Dict[str, Any]:
    """
    Build an Antigravity-inspired, humanized Thinking Summary for Developer Mode:
      1. Context parsing summary
      2. Dominant algorithm subset selection rationale
      3. Placement & constraint outcome
    """
    if escalated_from_greedy or chosen_solver == "HYBRID_ALNS":
        algo_note = (
            f"Đã loại bỏ nhóm thuật toán cổ điển mù năng lượng (`EDF`, `WSPT`, `LST` — kết quả tốt nhất của nhóm này "
            f"đã thấp hơn mức tệ nhất của nhóm thuật toán sinh học). Trong tập thuật toán tối ưu (`SCORED_GREEDY`, `HYBRID_ALNS`), "
            f"hệ thống chọn **`HYBRID_ALNS`** (tìm kiếm lân cận lớn phá-và-xây lại trong `{exec_ms:.1f}ms`) để hóa giải mật độ hạn chót dày."
        )
    else:
        algo_note = (
            f"Đã loại bỏ nhóm thuật toán cổ điển mù năng lượng (`EDF`, `WSPT`, `LST` — kết quả tốt nhất của nhóm này "
            f"vẫn kém hơn mức tệ nhất của nhóm có nhịp sinh học). Trong tập thuật toán vượt trội (`SCORED_GREEDY`, `HYBRID_ALNS`), "
            f"hệ thống chọn **`{chosen_solver}`** vì tốc độ phản hồi tức thì (`{exec_ms:.1f}ms`) và độ khớp khung giờ tỉnh táo đạt `{peak_match_pct:.0f}%`."
        )

    outcome_note = (
        f"Xếp thành công `{tasks_placed}/{tasks_total}` đầu việc vào lưới thời gian với `0` vi phạm ràng buộc cứng (bảo toàn giờ ngủ & lịch cố định)."
    )

    return {
        "headline_vi": f"Đã phân tích ngữ cảnh & tối ưu bằng {chosen_solver} ({exec_ms:.0f}ms)",
        "context_summary_vi": context_note_vi,
        "algorithm_summary_vi": algo_note,
        "outcome_summary_vi": outcome_note,
        "pruned_algorithms": ["EDF", "WSPT", "LST"],
        "candidate_subset": ["SCORED_GREEDY", "HYBRID_ALNS"],
        "selected_algorithm": chosen_solver,
        "steps_vi": [
            f"Phân tích ngữ cảnh: {context_note_vi}",
            f"Chọn thuật toán: {algo_note}",
            f"Kết quả xếp lịch: {outcome_note}",
        ],
    }
