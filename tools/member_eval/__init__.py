"""
Standalone Member-in-the-Loop Blind Evaluation Package (`member_eval/`).

Implements `Testing_Plan/evaluation_plan.md` while strictly honoring `INV-1..INV-6`:
  - Never mutates or modifies `Testing_System/`, `src/solvers/`, or `src/models.py`.
  - Runs strictly in isolation on dedicated FastAPI app/CLI (`127.0.0.1:8010`).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

BLIND_LABELS: Tuple[str, ...] = ("#A", "#B", "#C", "#D", "#E", "#F")

STANDARD_3_SOLVERS: Tuple[str, ...] = ("EDF", "SCORED_GREEDY", "HYBRID_ALNS")
STANDARD_4_SOLVERS: Tuple[str, ...] = ("EDF", "SCORED_GREEDY", "HYBRID_ALNS", "BACKTRACK")
ALL_6_SOLVERS: Tuple[str, ...] = ("EDF", "SCORED_GREEDY", "HYBRID_ALNS", "BACKTRACK", "WSPT", "LST")

OFFICIAL_BLOCK_TAGS: Tuple[str, ...] = (
    "AWKWARD_SPLIT",
    "BAD_TIME_OF_DAY",
    "TOO_TIGHT_GAP",
    "CONTEXT_JUMP",
    "DAY_OVERLOAD",
    "HABIT_MISPLACED",
    "WRONG_PRIORITY",
)

OFFICIAL_BLOCK_TAGS_META: List[Dict[str, str]] = [
    {
        "tag": "AWKWARD_SPLIT",
        "label_vi": "Cắt nhỏ vụn / khó làm",
        "calibration_hint": "Điều chỉnh ưu tiên opts[0] (ít tách mảnh hơn) và phạt phân mảnh trong score_candidate_unit.",
    },
    {
        "tag": "BAD_TIME_OF_DAY",
        "label_vi": "Sai buổi / trái nhịp tỉnh táo",
        "calibration_hint": "Rà soát lại chia cửa sổ MORNING/AFTERNOON/EVENING và điểm Peak năng lượng trong ergonomic_engine.py.",
    },
    {
        "tag": "TOO_TIGHT_GAP",
        "label_vi": "Quá sát lớp / bữa ăn / thiếu nghỉ",
        "calibration_hint": "Tăng phạt khoảng đệm sau lớp dài, bữa ăn và nghỉ >10p sau ca nặng trong ergonomic_engine.py.",
    },
    {
        "tag": "CONTEXT_JUMP",
        "label_vi": "Nhảy cóc môn học liên tục",
        "calibration_hint": "Tăng nhẹ trọng số phạt chuyển môn liên tiếp trong score_candidate_unit.",
    },
    {
        "tag": "DAY_OVERLOAD",
        "label_vi": "Ngày bị nhồi quá nặng / kiệt sức",
        "calibration_hint": "Siết nhẹ giới hạn tải ngày (MaxD / TStd) và ưu tiên san tải giữa các ngày trong tuần.",
    },
    {
        "tag": "HABIT_MISPLACED",
        "label_vi": "Thói quen đặt lệch khung giờ",
        "calibration_hint": "Tăng trọng số khớp preferred_window cho PersonalHabit và task HABIT.",
    },
    {
        "tag": "WRONG_PRIORITY",
        "label_vi": "Xếp sai thứ tự ưu tiên / bỏ nhầm bài",
        "calibration_hint": "Kiểm tra lại hàm ưu tiên urgency × priority và ba lô OVERLOAD_PACK khi quá tải.",
    },
]

UX_CRITERIA: List[Dict[str, str]] = [
    {
        "code": "UX-1",
        "name_vi": "Hiệu quả xử lý task (Task Efficiency)",
        "question_vi": "Thuật toán có xếp xong đủ các bài quan trọng/gấp đúng hạn, giữ đúng độ dài và thứ tự tiên quyết không?",
        "v21_link": "P1.1%, Verdict, unplaced_tasks",
    },
    {
        "code": "UX-2",
        "name_vi": "Độ hợp nhịp năng lượng (Energy & Window Fit)",
        "question_vi": "Các phiên học nặng (load=3) có rơi đúng khung giờ tỉnh táo và thói quen cá nhân đúng buổi mong muốn không?",
        "v21_link": "APk%, OffP, Prf%, Hab%",
    },
    {
        "code": "UX-3",
        "name_vi": "Sức bền & Nhịp nghỉ (Fatigue & Break Naturalness)",
        "question_vi": "Lịch ngày có bị nhồi quá sức, thiếu khoảng thở giữa ca lớp/bữa ăn, hoặc học liên tiếp quá mệt không?",
        "v21_link": "MxD, Rec%, Stk, PCl, Crn",
    },
    {
        "code": "UX-4",
        "name_vi": "Độ mượt chia mảnh & Chuyển môn (Split & Flow)",
        "question_vi": "Việc cắt nhỏ task (nếu có) và cách xen kẽ giữa các môn trong cùng ngày có hợp mạch tập trung ngoài đời không?",
        "v21_link": "Ctx, chunk/ngày, <10h%",
    },
    {
        "code": "UX-5",
        "name_vi": "Tính khả thi & Chịu biến cố (Real-World Resilience)",
        "question_vi": "Nếu ngoài đời bị lố giờ 30–45p hoặc phát sinh việc đột xuất, tuần này có đủ khe đệm để tự cứu không?",
        "v21_link": "Shk25%, TStd, khoảng trống cuối ngày",
    },
]

TEAM_MEMBERS: List[Dict[str, str]] = [
    {"member_id": "duc_minh", "name": "Phạm Đức Minh", "role": "Leader · Lead §9 Evaluation Plan"},
    {"member_id": "nguyen_khanh", "name": "Trần Nguyên Khánh", "role": "Thinker 1 · Lead §6 Algorithmic Design"},
    {"member_id": "tien_binh", "name": "Lê Tiến Bình", "role": "Builder 1 · Lead §7 System Architecture"},
    {"member_id": "trong_tien", "name": "Nguyễn Trọng Tiến", "role": "Thinker 3 · Lead §5 Abstraction"},
    {"member_id": "gia_bao", "name": "Nguyễn Nguyễn Gia Bảo", "role": "Builder 3 · Lead §8 Edge Cases & Trade-offs"},
    {"member_id": "minh_nhat", "name": "Lê Minh Nhật", "role": "Builder 2 · Lead §10 From Design to Action"},
    {"member_id": "minh_anh", "name": "Hoàng Minh Anh", "role": "Thinker 2 · Lead §11 Conclusion"},
    {"member_id": "guest_student", "name": "Sinh Viên Trải Nghiệm (Guest)", "role": "End-User Commercial Validation"},
]

__all__ = [
    "ALL_6_SOLVERS",
    "BLIND_LABELS",
    "OFFICIAL_BLOCK_TAGS",
    "OFFICIAL_BLOCK_TAGS_META",
    "STANDARD_3_SOLVERS",
    "STANDARD_4_SOLVERS",
    "TEAM_MEMBERS",
    "UX_CRITERIA",
]
