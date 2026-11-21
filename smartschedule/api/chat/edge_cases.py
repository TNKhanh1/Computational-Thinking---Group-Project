"""
Conversational Edge-Case Analyzer & Remaining-Time Habit Buffering (`smartschedule.api.chat.edge_cases`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from smartschedule.core.calibration import compute_ewma_calibration
from smartschedule.core.estimate_buffer import multiplier_for_habit, multiplier_for_load
from smartschedule.core.models import CommitmentsProfile, ScheduleOutput, Task
from smartschedule.core.storage import list_completion_logs
from smartschedule.core.utils import SLOTS_PER_DAY, round_up_to_15
from smartschedule.nlp.clause_condenser import _WEEKDAY_VI_MAP, _extract_flexible_duration_min
from smartschedule.nlp.parser_controller import WEEKDAYS, _strip_accents


def analyze_schedule_edge_cases(
    profile: CommitmentsProfile,
    out: ScheduleOutput,
    tasks: List[Task],
) -> Optional[Dict[str, Any]]:
    """
    Detect:
      - DEADLOCK: genuine unplaced tasks due to overlapping deadlines or capacity shortage.
      - DENSE_WARNING: feasible (0 unplaced) but intense daily load (>= 420m) or crunch/high fatigue.
    """
    genuine_unplaced = [
        u
        for u in (out.unplaced_tasks or [])
        if str(u.get("reason_code") or "").upper() not in ("PAST_DUE", "DEADLINE_IN_PAST")
        and "DEADLINE_IN_PAST" not in str(u.get("reason") or "")
    ]

    if genuine_unplaced or out.status in ("INFEASIBLE_CAPACITY", "NO_SCHEDULE_FOUND"):
        titles = [str(u.get("title") or u.get("task_id") or "Công việc") for u in genuine_unplaced]
        shortage_min = int(out.overload.shortage_minutes) if out.overload else sum(
            int(u.get("duration_min") or 60) for u in genuine_unplaced
        )
        suggestions: List[Dict[str, Any]] = []
        if out.overload and out.overload.options:
            for opt in out.overload.options[:4]:
                code = str(opt.get("code") or "")
                friendly = {
                    "SKIP_HABIT": f"🌱 Tạm nghỉ thói quen '{opt.get('title', '')}' tuần này (+{opt.get('frees_min', 0)}p)",
                    "SHORTEN_TASK": f"✂️ Rút ngắn '{opt.get('title', '')}' xuống {opt.get('new_duration_min', 45)}p",
                    "ALLOW_SPLIT": f"🧩 Chia nhỏ '{opt.get('title', '')}' để lấp khe trống ngắn",
                    "POSTPONE_LOWEST": f"📅 Dời '{opt.get('title', '')}' sang cuối tuần",
                }.get(code, str(opt.get("label") or "Điều chỉnh lịch"))
                suggestions.append(
                    {
                        "action": "OVERLOAD_OPTION",
                        "option_id": opt.get("id", "O1"),
                        "option_code": code,
                        "target_task_id": opt.get("task", ""),
                        "label": friendly,
                    }
                )
        else:
            suggestions = [
                {"action": "PROMPT", "label": "✂️ Chia nhỏ bớt các công việc dài", "prompt": "Chia nhỏ các công việc dài để dễ xếp lịch hơn"},
                {"action": "PROMPT", "label": "📅 Dời hạn chót việc ít gấp", "prompt": "Dời deadline công việc ưu tiên thấp sang Chủ nhật"},
            ]

        return {
            "type": "DEADLOCK",
            "severity": "danger",
            "shortage_min": shortage_min,
            "unplaced_titles": titles,
            "message_vi": (
                f"Lịch trình đang bị kẹt hoặc chồng hạn chót ({len(titles)} việc chưa xếp được: "
                f"{', '.join(titles[:3])}, thiếu khoảng {max(15, shortage_min)} phút trống). "
                "Bạn chọn một hướng gỡ rối nhẹ nhàng bên dưới nhé:"
            ),
            "suggestions": suggestions,
        }

    horizon_days = max(7, min(14, int(getattr(profile, "horizon_days", 7) or 7)))
    day_load: Dict[int, int] = {d: 0 for d in range(horizon_days)}
    for ev in profile.fixed_events or []:
        raw_days = ev.day_of_week
        days_list = WEEKDAYS if str(raw_days).upper() == "ALL" else (raw_days if isinstance(raw_days, list) else [raw_days])
        try:
            sh, sm = map(int, ev.start_time.split(":"))
            eh, em = map(int, ev.end_time.split(":"))
            dur = max(0, (eh * 60 + em) - (sh * 60 + sm))
        except Exception:
            dur = 0
        if str(ev.category or "").upper() == "MEAL":
            continue
        for wd_name in days_list:
            if wd_name in WEEKDAYS:
                idx = WEEKDAYS.index(wd_name)
                if idx < horizon_days:
                    day_load[idx] = day_load.get(idx, 0) + dur

    for blk in out.blocks or []:
        d_idx = int(blk.start_slot) // SLOTS_PER_DAY
        if 0 <= d_idx < horizon_days:
            day_load[d_idx] = day_load.get(d_idx, 0) + int(blk.duration_min or 0)

    dense_days = [
        {
            "day_index": d,
            "day_vi": _WEEKDAY_VI_MAP.get(WEEKDAYS[d % 7], WEEKDAYS[d % 7]),
            "minutes": mins,
        }
        for d, mins in sorted(day_load.items())
        if mins >= 420
    ]
    max_day_min = max(day_load.values(), default=0)
    is_dense = bool(dense_days) or out.summary.crunch_tier_used > 0 or out.summary.experience_rating >= 2.2

    if is_dense:
        day_txt = ", ".join(f"{d['day_vi']} (~{round(d['minutes'] / 60, 1)} tiếng)" for d in dense_days[:3])
        if not day_txt:
            day_txt = f"một số ngày trong tuần (~{round(max_day_min / 60, 1)} tiếng/ngày)"
        return {
            "type": "DENSE_WARNING",
            "severity": "warn",
            "dense_days": dense_days,
            "max_daily_min": max_day_min,
            "message_vi": (
                f"Đã xếp đủ công việc trước hạn, nhưng lịch trình đang khá dày đặc ở {day_txt}. "
                "Bạn có thể giảm áp lực bằng cách chia nhỏ việc dài hoặc dời bớt sang ngày thoáng hơn:"
            ),
            "suggestions": [
                {
                    "action": "PROMPT",
                    "label": "🌬️ Chia nhỏ các việc nặng để giãn bớt",
                    "prompt": "Chia nhỏ các công việc nặng ra nhiều buổi ngắn hơn để lịch đỡ dày",
                },
                {
                    "action": "PROMPT",
                    "label": "📅 Dời bớt 1 việc nhẹ sang cuối tuần",
                    "prompt": "Dời hạn công việc ưu tiên thấp sang Chủ nhật cho thoáng lịch",
                },
                {"action": "DISMISS", "label": "👍 Giữ nguyên lịch này"},
            ],
        }

    return None


def compute_remaining_and_habit_buffer(
    *,
    prompt: str,
    task_dict: Dict[str, Any],
    profile: CommitmentsProfile,
    completed_blocks: Dict[str, Any],
    workspace_id: str,
) -> Dict[str, Any]:
    """Compute remaining raw minutes + habit/EWMA safety buffer."""
    norm = _strip_accents(prompt).lower()
    explicit_rem_min, dur_inferred = _extract_flexible_duration_min(norm)
    old_duration = int(task_dict.get("duration_min") or 60)

    if not dur_inferred and explicit_rem_min is not None:
        remaining_raw = round_up_to_15(explicit_rem_min)
        source_note = f"theo thời lượng bạn ước lượng cần làm tiếp ({remaining_raw} phút)"
    else:
        tid = str(task_dict.get("task_id") or "")
        done_min = 0
        for bid, info in (completed_blocks or {}).items():
            if tid and (str(bid).startswith(f"{tid}_") or str(bid) == tid):
                done_min += int((info or {}).get("actual_min") or 0)
        remaining_raw = max(15, round_up_to_15(max(15, old_duration - done_min)))
        source_note = (
            f"tính từ phần việc còn lại ({old_duration}p - {done_min}p đã làm)"
            if done_min > 0
            else f"giữ nguyên thời lượng ước tính hiện có ({remaining_raw} phút)"
        )

    logs = list_completion_logs(workspace_id=workspace_id, limit=100)
    cal = compute_ewma_calibration(logs)
    cog_load = int(task_dict.get("cognitive_load") or 2)

    base_load_mult = multiplier_for_load(
        cog_load,
        alpha_light=float(getattr(profile, "alpha_light", 1.20) or 1.20),
        alpha_heavy=float(getattr(profile, "alpha_heavy", 1.35) or 1.35),
    )
    habit_mult = multiplier_for_habit(getattr(profile, "estimate_habit", None))
    ewma_mult = float(cal.get("ewma_overall") or cal.get("mean_ratio") or 1.0)
    if cal.get("ready_to_apply"):
        ewma_mult = float(
            cal.get("recommended_alpha_heavy" if cog_load >= 3 else "recommended_alpha_light") or ewma_mult
        )

    eff_alpha = round(max(1.10, min(1.60, max(base_load_mult, habit_mult, ewma_mult))), 2)
    buffered_min = max(remaining_raw, round_up_to_15(int(round(remaining_raw * eff_alpha))))
    extra_buffer_min = max(0, buffered_min - remaining_raw)

    return {
        "old_duration_min": old_duration,
        "remaining_raw_min": remaining_raw,
        "applied_alpha": eff_alpha,
        "buffered_duration_min": buffered_min,
        "extra_buffer_min": extra_buffer_min,
        "calibration_samples": int(cal.get("sample_count") or 0),
        "explanation_vi": (
            f"Phần việc còn lại là {remaining_raw} phút ({source_note}). "
            f"Áp dụng hệ số nhịp độ & thói quen cá nhân (×{eff_alpha:.2f}), "
            f"hệ thống dự phòng thêm +{extra_buffer_min} phút thành tổng {buffered_min} phút."
        ),
    }
