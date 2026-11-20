"""
Scenario Catalog & Personal Week Builder for Member-in-the-Loop Blind Evaluation (`member_eval/scenarios.py`).

Provides the locked-seed benchmark/fuzz scenarios specified in `Testing_Plan/evaluation_plan.md §IV.2`
plus a customizable real student `PERSONAL_WEEK` template.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional


def _ensure_paths() -> None:
    baseline_root = str(Path(__file__).resolve().parents[1])
    repo_root = str(Path(__file__).resolve().parents[2])
    for p in (repo_root, baseline_root):
        if p not in sys.path:
            sys.path.insert(0, p)


_ensure_paths()

from Testing_System.generator import FuzzGenerator, InputGenerator  # noqa: E402
from Testing_System.schemas import RegimeName  # noqa: E402
from src.models import CommitmentsProfile, ScheduleBlock, Task  # noqa: E402


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    title_vi: str
    category: str  # PERSONAL | LOOSE | TIGHT | OVERLOAD
    description_vi: str
    source: str  # personal | regime | fuzz
    horizon_days: int
    recommended_mode: str = "standard_3"
    seed: int = 0
    regime_name: Optional[str] = None
    fuzz_tier: Optional[str] = None


SCENARIO_CATALOG: List[ScenarioSpec] = [
    ScenarioSpec(
        scenario_id="PERSONAL_WEEK",
        title_vi="Ca 1 — Lịch thật tuần này của chính bạn (Personal Week)",
        category="PERSONAL",
        description_vi="Nhập đúng lịch học cố định, giờ ngủ, thói quen và 5–10 task thật trong tuần hiện tại (hỗ trợ nhập tiếng Việt tự nhiên).",
        source="personal",
        horizon_days=7,
        recommended_mode="standard_3",
    ),
    ScenarioSpec(
        scenario_id="R1_LOOSE_S1",
        title_vi="Ca 2a — Regime 1: Tuần tải vừa chuẩn (seed=1)",
        category="LOOSE",
        description_vi="Kịch bản tải vừa (LOOSE) kiểm tra nhịp sinh học, nghỉ 15p sau ca nặng và phân bổ đều.",
        source="regime",
        horizon_days=7,
        recommended_mode="standard_3",
        seed=1,
        regime_name=RegimeName.LOOSE_FEASIBLE.value,
    ),
    ScenarioSpec(
        scenario_id="R2_TIGHT_S42",
        title_vi="Ca 3a — Regime 2: Cụm hạn chót gấp (TIGHT seed=42)",
        category="TIGHT",
        description_vi="Nhiều hạn chót chồng chéo buộc thuật toán chia mảnh thông minh để giữ 100% đúng hạn.",
        source="regime",
        horizon_days=7,
        recommended_mode="standard_4",
        seed=42,
        regime_name=RegimeName.TIGHT_DEADLINE_CLUSTER.value,
    ),
    ScenarioSpec(
        scenario_id="R3_CIRCADIAN_S5",
        title_vi="Ca 2b — Regime 3: Nhịp sinh học & Lệch pha SJL (seed=5)",
        category="LOOSE",
        description_vi="Lịch học bất đối xứng T2/T4/T6 + bài nặng nhận thức kiểm tra khớp Peak & SJL.",
        source="regime",
        horizon_days=7,
        recommended_mode="standard_3",
        seed=5,
        regime_name=RegimeName.CIRCADIAN_SJL_AND_RECOVERY.value,
    ),
    ScenarioSpec(
        scenario_id="R5_OVERLOAD_S1",
        title_vi="Ca 3b — Regime 5: Tuần quá tải thực sự (OVERLOAD seed=1)",
        category="OVERLOAD",
        description_vi="Khối lượng vượt quỹ giờ rảnh: chấm xem thuật toán giữ bài ưu tiên cao và bỏ việc nào hợp lý nhất.",
        source="regime",
        horizon_days=7,
        recommended_mode="all_6",
        seed=1,
        regime_name=RegimeName.OVERLOAD_INFEASIBLE.value,
    ),
    ScenarioSpec(
        scenario_id="FUZZ_LOOSE_14D_S1041",
        title_vi="Ca 2c — Fuzz LOOSE 14 Ngày (seed=1041)",
        category="LOOSE",
        description_vi="Đề ngẫu nhiên Plant-a-Witness chu kỳ 2 tuần (14 ngày), độ dài & độ nặng đa dạng.",
        source="fuzz",
        horizon_days=14,
        recommended_mode="standard_3",
        seed=1041,
        fuzz_tier=None,
    ),
    ScenarioSpec(
        scenario_id="FUZZ_TIGHT_S1001",
        title_vi="Ca 3c — Fuzz Nước Rút TIGHT (seed=1001)",
        category="TIGHT",
        description_vi="Tuần nước rút áp lực cao: đánh giá khả năng cứu deadline mà vẫn giữ được sức bền.",
        source="fuzz",
        horizon_days=7,
        recommended_mode="standard_4",
        seed=1001,
        fuzz_tier=None,
    ),
    ScenarioSpec(
        scenario_id="FUZZ_OVERLOAD_S1049",
        title_vi="Ca 3d — Fuzz Quá Tải Lớn OVERLOAD (seed=1049)",
        category="OVERLOAD",
        description_vi="Bài toán quá tải lớn kiểm tra chiến lược Triage giữ giá trị priority cao nhất.",
        source="fuzz",
        horizon_days=14,
        recommended_mode="all_6",
        seed=1049,
        fuzz_tier=None,
    ),
]

SCENARIO_INDEX: Dict[str, ScenarioSpec] = {s.scenario_id: s for s in SCENARIO_CATALOG}


def list_scenarios() -> List[Dict[str, Any]]:
    """Return UI-ready catalog of all evaluation scenarios."""
    return [asdict(s) for s in SCENARIO_CATALOG]


def get_personal_week_template() -> Dict[str, Any]:
    """Default editable 7-day student week template for Ca 1 (Personal Week)."""
    commitments = {
        "student_id": "STUDENT_PERSONAL_WEEK",
        "planning_week_start": "2026-11-16T00:00:00+07:00",
        "horizon_days": 7,
        "focus_preference": "MORNING",
        "buffer_mode": "COGNITIVE_LOAD",
        "alpha_light": 1.2,
        "alpha_heavy": 1.35,
        "sleep_schedule": {
            "daily_start_time": "23:30",
            "daily_end_time": "06:30",
            "is_hard_lock": True,
        },
        "fixed_events": [
            {
                "event_id": "CLASS_MWF",
                "title": "Lý thuyết trên trường (T2-T4-T6)",
                "day_of_week": ["Monday", "Wednesday", "Friday"],
                "start_time": "07:30",
                "end_time": "11:00",
                "category": "ACADEMIC_CLASS",
            },
            {
                "event_id": "LUNCH_DAILY",
                "title": "Ăn trưa & Nghỉ trưa",
                "day_of_week": "ALL",
                "start_time": "12:00",
                "end_time": "13:00",
                "category": "MEAL",
            },
            {
                "event_id": "DINNER_DAILY",
                "title": "Ăn tối",
                "day_of_week": "ALL",
                "start_time": "18:30",
                "end_time": "19:15",
                "category": "MEAL",
            },
        ],
        "personal_habits": [
            {
                "habit_id": "HAB_SPORT",
                "name": "Chạy bộ / Gym",
                "preferred_window": "EVENING",
                "frequency_per_week": 3,
                "duration_min": 45,
                "category": "HABIT",
                "cognitive_load": 1,
            }
        ],
    }
    tasks = [
        {
            "task_id": "PW_ALG",
            "title": "Ôn tập Tư duy Tính toán & Giải thuật",
            "duration_min": 120,
            "deadline_day": "Wednesday",
            "deadline_time": "22:00",
            "priority": 5,
            "cognitive_load": 3,
            "category": "EXAM",
            "is_splittable": True,
            "min_chunk_min": 45,
            "max_chunk_min": 90,
        },
        {
            "task_id": "PW_LAB",
            "title": "Làm bài Lab Hệ điều hành",
            "duration_min": 90,
            "deadline_day": "Thursday",
            "deadline_time": "23:59",
            "priority": 4,
            "cognitive_load": 3,
            "category": "LAB",
            "is_splittable": True,
            "min_chunk_min": 45,
            "max_chunk_min": 90,
        },
        {
            "task_id": "PW_SLIDE",
            "title": "Làm slide báo cáo nhóm",
            "duration_min": 90,
            "deadline_day": "Friday",
            "deadline_time": "20:00",
            "priority": 4,
            "cognitive_load": 2,
            "category": "PROJECT",
            "depends_on": ["PW_ALG"],
            "is_splittable": True,
            "min_chunk_min": 30,
            "max_chunk_min": 60,
        },
        {
            "task_id": "PW_ENG",
            "title": "Luyện nghe đọc Tiếng Anh",
            "duration_min": 60,
            "deadline_day": "Saturday",
            "deadline_time": "21:00",
            "priority": 3,
            "cognitive_load": 2,
            "category": "ASSIGNMENT",
            "preferred_window": "EVENING",
            "is_splittable": False,
        },
        {
            "task_id": "PW_READ",
            "title": "Đọc tài liệu tuần mới",
            "duration_min": 60,
            "deadline_day": "Sunday",
            "deadline_time": "22:00",
            "priority": 2,
            "cognitive_load": 1,
            "category": "READING",
            "is_splittable": False,
        },
    ]
    return {"commitments": commitments, "tasks": tasks, "pinned_blocks": []}


def load_scenario_bundle(scenario_id: str) -> Dict[str, Any]:
    """Load `CommitmentsProfile`, `List[Task]`, `List[ScheduleBlock]`, and `ScenarioSpec` for an ID."""
    key = str(scenario_id or "").strip().upper()
    if key not in SCENARIO_INDEX:
        raise ValueError(f"Unknown scenario_id '{scenario_id}'. Valid IDs: {list(SCENARIO_INDEX.keys())}")
    spec = SCENARIO_INDEX[key]

    if spec.source == "personal":
        tpl = get_personal_week_template()
        return build_custom_personal_bundle(
            commitments_dict=tpl["commitments"],
            tasks_list=tpl["tasks"],
            pinned_list=tpl["pinned_blocks"],
            scenario_id=spec.scenario_id,
        )

    if spec.source == "regime":
        bundle = InputGenerator.generate(RegimeName(spec.regime_name), seed=spec.seed)
        return {
            "spec": spec,
            "profile": bundle.profile,
            "tasks": bundle.tasks,
            "pinned_blocks": bundle.pinned_blocks,
        }

    bundle = FuzzGenerator.generate(seed=spec.seed, tier=spec.fuzz_tier)
    return {
        "spec": spec,
        "profile": bundle.profile,
        "tasks": bundle.tasks,
        "pinned_blocks": bundle.pinned_blocks,
    }


def build_custom_personal_bundle(
    commitments_dict: Dict[str, Any],
    tasks_list: List[Dict[str, Any]],
    pinned_list: Optional[List[Dict[str, Any]]] = None,
    scenario_id: str = "PERSONAL_WEEK",
) -> Dict[str, Any]:
    """Validate and wrap custom user commitments & tasks for blind evaluation."""
    profile = CommitmentsProfile.model_validate(commitments_dict or {})
    tasks = [Task.model_validate(t) for t in (tasks_list or [])]
    pinned = [ScheduleBlock.model_validate(b) for b in (pinned_list or [])]
    spec = SCENARIO_INDEX.get(scenario_id) or ScenarioSpec(
        scenario_id=scenario_id,
        title_vi="Ca 1 — Lịch thật tuần này của chính bạn",
        category="PERSONAL",
        description_vi="Lịch cá nhân tùy chỉnh do thành viên / sinh viên tự nhập.",
        source="personal",
        horizon_days=int(getattr(profile, "horizon_days", 7) or 7),
        recommended_mode="standard_3",
    )
    return {
        "spec": spec,
        "profile": profile,
        "tasks": tasks,
        "pinned_blocks": pinned,
    }


__all__ = [
    "SCENARIO_CATALOG",
    "SCENARIO_INDEX",
    "ScenarioSpec",
    "build_custom_personal_bundle",
    "get_personal_week_template",
    "list_scenarios",
    "load_scenario_bundle",
]
