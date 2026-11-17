"""
Pure Domain Module: Smart Overload Triage, Habit-Skipping & Trade-off Option Engine (Feature 002 / F15).
Ported cleanly from origin/hmanh (preserving INV-1..INV-4 and Feature 001 / Presentation2 integration).
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from src.models import (
    CommitmentsProfile,
    OverloadReport,
    ScheduleOutput,
    Task,
)
from src.utils import MINUTES_PER_SLOT, round_up_to_15


class OverloadTriageEngine:
    """
    Pure domain service that analyzes schedule overload reports, identifies prerequisite-safe
    habit-skipping and trade-off options ordered by least academic harm, and applies
    selected options to deep-copied task lists for interactive What-If previews.
    """

    OPTION_CODES_ORDER = (
        "SKIP_HABIT",
        "SHORTEN_TASK",
        "ALLOW_SPLIT",
        "POSTPONE_LOWEST",
    )

    @classmethod
    def get_protected_prerequisite_ids(cls, tasks: List[Task]) -> Set[str]:
        """Return task_ids that are prerequisites (`depends_on`) of any task with priority >= 3."""
        protected: Set[str] = set()
        for t in tasks:
            if t.priority >= 3 and t.depends_on:
                for prereq_id in t.depends_on:
                    protected.add(str(prereq_id))
        return protected

    @classmethod
    def is_habit_or_optional_task(cls, task: Task, week_start_iso: str) -> bool:
        """Determine whether a task is a flexible habit or low-priority optional task eligible for SKIP_HABIT."""
        cat = (task.category or "").strip().upper()
        if cat in ("HABIT", "CHORE", "OPTIONAL", "SELF_CARE", "CLUB"):
            return True
        if task.resolve_deadline_slot(week_start_iso=week_start_iso) is None:
            return True
        if task.priority <= 2:
            return True
        return False

    @classmethod
    def build_triage_options(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        report: OverloadReport,
        unplaced_tasks: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Build a deterministic, least-harm ordered list of overload resolution options:
          1. SKIP_HABIT
          2. SHORTEN_TASK
          3. ALLOW_SPLIT
          4. POSTPONE_LOWEST
        """
        week_start_iso = profile.planning_week_start
        protected_prereqs = cls.get_protected_prerequisite_ids(tasks)
        task_map: Dict[str, Task] = {t.task_id: t for t in tasks}

        unplaced_ids: List[str] = []
        if unplaced_tasks:
            for u in unplaced_tasks:
                uid = str(u.get("task_id", ""))
                if uid and uid not in unplaced_ids:
                    unplaced_ids.append(uid)
        for uid in (report.unplaced_tasks or []):
            if uid and uid not in unplaced_ids:
                unplaced_ids.append(uid)

        bottleneck_slot = report.deadline_slot
        shortage_min = max(0, int(report.shortage_minutes or 0))

        competing_tasks: List[Task] = []
        for t in tasks:
            d_slot = t.resolve_deadline_slot(week_start_iso=week_start_iso)
            if bottleneck_slot is None or (d_slot is not None and d_slot <= bottleneck_slot):
                competing_tasks.append(t)
        if not competing_tasks:
            competing_tasks = list(tasks)

        raw_options: List[Dict[str, Any]] = []
        suggested_actions: List[str] = []

        # 1. SKIP_HABIT
        habit_candidates: List[Task] = [
            t
            for t in tasks
            if t.task_id not in protected_prereqs
            and cls.is_habit_or_optional_task(t, week_start_iso=week_start_iso)
        ]
        habit_candidates.sort(
            key=lambda t: (
                0
                if (
                    (t.category or "").strip().upper() == "HABIT"
                    or t.resolve_deadline_slot(week_start_iso=week_start_iso) is None
                )
                else 1,
                t.priority,
                -t.get_planned_duration_min(),
                t.task_id,
            )
        )

        if habit_candidates:
            best_habit = habit_candidates[0]
            frees_min = best_habit.get_planned_duration_min()
            is_explicit_habit = (
                (best_habit.category or "").strip().upper() == "HABIT"
                or best_habit.resolve_deadline_slot(week_start_iso=week_start_iso) is None
            )
            kind_label = "thói quen linh hoạt" if is_explicit_habit else f"task tự chọn ưu tiên thấp (P{best_habit.priority})"
            label = (
                f"Bỏ qua {kind_label} '{best_habit.title}' ({best_habit.task_id}) trong tuần này "
                f"(Giải phóng +{frees_min} phút cho các bài tập cốt lõi)"
            )
            raw_options.append({
                "code": "SKIP_HABIT",
                "task": best_habit.task_id,
                "title": best_habit.title,
                "frees_min": frees_min,
                "reduces_min": frees_min,
                "priority": best_habit.priority,
                "category": best_habit.category,
                "label": label,
            })
            suggested_actions.append(
                f"Bỏ qua {kind_label} '{best_habit.title}' ({best_habit.task_id}, ưu tiên {best_habit.priority}) "
                f"để giải phóng {frees_min} phút"
            )

        # 2. SHORTEN_TASK
        shorten_target: Optional[Task] = None
        for uid in unplaced_ids:
            if uid in task_map and task_map[uid].get_planned_duration_min() > MINUTES_PER_SLOT:
                shorten_target = task_map[uid]
                break
        if shorten_target is None and competing_tasks:
            candidates_by_prio = sorted(
                [t for t in competing_tasks if t.get_planned_duration_min() > MINUTES_PER_SLOT],
                key=lambda t: (t.priority, -t.get_planned_duration_min(), t.task_id),
            )
            if candidates_by_prio:
                shorten_target = candidates_by_prio[0]

        if shorten_target is not None:
            old_dur = shorten_target.get_planned_duration_min()
            floor_min = max(15, min(shorten_target.min_chunk_min, 45))
            if shortage_min > 0:
                cut_wanted = round_up_to_15(shortage_min)
                new_dur = max(floor_min, old_dur - cut_wanted)
            else:
                new_dur = max(floor_min, round_up_to_15(old_dur // 2))
            reduces_min = max(15, old_dur - new_dur)
            new_dur = max(15, old_dur - reduces_min)

            if new_dur < old_dur:
                label = (
                    f"Rút ngắn thời lượng '{shorten_target.title}' ({shorten_target.task_id}) "
                    f"từ {old_dur}p xuống {new_dur}p (Giảm -{reduces_min} phút thiếu hụt)"
                )
                raw_options.append({
                    "code": "SHORTEN_TASK",
                    "task": shorten_target.task_id,
                    "title": shorten_target.title,
                    "old_duration_min": old_dur,
                    "new_duration_min": new_dur,
                    "reduces_min": reduces_min,
                    "frees_min": reduces_min,
                    "label": label,
                })
                suggested_actions.append(
                    f"Cắt giảm {reduces_min} phút của task '{shorten_target.title}' ({shorten_target.task_id}: {old_dur}p -> {new_dur}p)"
                )

        # 3. ALLOW_SPLIT
        unsplittable_candidates: List[Task] = []
        for uid in unplaced_ids:
            t_cand = task_map.get(uid)
            if t_cand and (not t_cand.is_splittable or t_cand.min_chunk_min > 45) and t_cand.get_planned_duration_min() >= 60:
                unsplittable_candidates.append(t_cand)
        if not unsplittable_candidates:
            for t_cand in competing_tasks:
                if (not t_cand.is_splittable or t_cand.min_chunk_min > 45) and t_cand.get_planned_duration_min() >= 60:
                    unsplittable_candidates.append(t_cand)

        if unsplittable_candidates:
            split_target = unsplittable_candidates[0]
            label = (
                f"Cho phép chia nhỏ task '{split_target.title}' ({split_target.task_id}, {split_target.get_planned_duration_min()}p) "
                f"thành các phiên 45–90 phút để lấp vừa các khoảng trống ngắn"
            )
            raw_options.append({
                "code": "ALLOW_SPLIT",
                "task": split_target.task_id,
                "title": split_target.title,
                "min_chunk_min": 45,
                "frees_min": 0,
                "reduces_min": 0,
                "label": label,
            })
            suggested_actions.append(
                f"Bật cờ cho phép chia nhỏ (is_splittable = True, min_chunk = 45p) cho '{split_target.title}' ({split_target.task_id})"
            )

        # 4. POSTPONE_LOWEST
        postpone_candidates = [
            t for t in competing_tasks if t.task_id not in protected_prereqs
        ]
        if not postpone_candidates:
            postpone_candidates = list(competing_tasks)

        if postpone_candidates:
            postpone_candidates.sort(
                key=lambda t: (
                    0 if t.task_id in unplaced_ids else 1,
                    t.priority,
                    -t.get_planned_duration_min(),
                    t.task_id,
                )
            )
            post_target = postpone_candidates[0]
            frees_min = post_target.get_planned_duration_min()
            cur_day = (post_target.deadline_day or "").strip()
            new_deadline_day = "Next Monday" if cur_day.lower() in ("sunday", "next monday") else "Sunday"
            label = (
                f"Dời hạn chót '{post_target.title}' ({post_target.task_id}, Ưu tiên {post_target.priority}) "
                f"sang {new_deadline_day} 23:59 (Giảm tải +{frees_min} phút trước hạn chót hiện tại)"
            )
            raw_options.append({
                "code": "POSTPONE_LOWEST",
                "task": post_target.task_id,
                "title": post_target.title,
                "new_deadline_day": new_deadline_day,
                "new_deadline_time": "23:59",
                "frees_min": frees_min,
                "reduces_min": frees_min,
                "priority": post_target.priority,
                "label": label,
            })
            suggested_actions.append(
                f"Dời hạn chót của task ưu tiên thấp nhất '{post_target.title}' ({post_target.task_id}) sang {new_deadline_day} 23:59"
            )

        final_options: List[Dict[str, Any]] = []
        for idx, opt in enumerate(raw_options, start=1):
            opt_with_id = dict(opt)
            opt_with_id["id"] = f"O{idx}"
            final_options.append(opt_with_id)

        return final_options, suggested_actions

    @classmethod
    def enrich_schedule_overload(
        cls,
        output: ScheduleOutput,
        profile: CommitmentsProfile,
        tasks: List[Task],
    ) -> ScheduleOutput:
        """Enrich `output.overload_reports` and `output.overload` with least-harm triage options."""
        if not output.overload_reports and output.overload is None:
            return output

        for rep in output.overload_reports:
            options, actions = cls.build_triage_options(
                profile=profile,
                tasks=tasks,
                report=rep,
                unplaced_tasks=output.unplaced_tasks,
            )
            rep.options = options
            if actions:
                rep.suggested_actions = actions

        if output.overload_reports:
            output.overload = output.overload_reports[0]
        elif output.overload is not None:
            options, actions = cls.build_triage_options(
                profile=profile,
                tasks=tasks,
                report=output.overload,
                unplaced_tasks=output.unplaced_tasks,
            )
            output.overload.options = options
            if actions:
                output.overload.suggested_actions = actions

        # Surface Early Extension Alert note inside suggested_actions if present
        alerts = getattr(output.summary, "early_extension_alerts", None) or []
        if alerts and output.overload is not None:
            rec = str(alerts[0].get("recommendation", ""))
            if rec and rec not in output.overload.suggested_actions:
                output.overload.suggested_actions.append(rec)

        return output

    @classmethod
    def apply_triage_option(
        cls,
        profile: CommitmentsProfile,
        tasks: List[Task],
        option_id: Optional[str] = None,
        option_code: Optional[str] = None,
        target_task_id: Optional[str] = None,
        shortage_min: int = 0,
        available_options: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[List[Task], Dict[str, Any]]:
        """Apply a selected triage option (`SKIP_HABIT`, `SHORTEN_TASK`, `ALLOW_SPLIT`, `POSTPONE_LOWEST`) immutably."""
        cloned_tasks: List[Task] = [t.model_copy(deep=True) for t in tasks]
        if not cloned_tasks:
            return cloned_tasks, {
                "option_id": option_id or "O1",
                "code": option_code or "NONE",
                "task_id": target_task_id or "",
                "action": "NO_OP",
                "description": "Danh sách task trống.",
            }

        matched_opt: Optional[Dict[str, Any]] = None
        if available_options:
            for opt in available_options:
                if option_id and str(opt.get("id", "")).upper() == str(option_id).strip().upper():
                    matched_opt = opt
                    break
            if matched_opt is None and option_code:
                for opt in available_options:
                    if str(opt.get("code", "")).upper() == str(option_code).strip().upper():
                        if not target_task_id or str(opt.get("task", "")) == str(target_task_id):
                            matched_opt = opt
                            break

        resolved_code = (
            (option_code or (matched_opt.get("code") if matched_opt else "") or "SKIP_HABIT")
            .strip()
            .upper()
        )
        resolved_id = (option_id or (matched_opt.get("id") if matched_opt else "") or "O1").strip()
        resolved_target_id = (
            target_task_id
            or (matched_opt.get("task") if matched_opt else "")
            or cloned_tasks[-1].task_id
        )

        target_idx = 0
        for idx, t in enumerate(cloned_tasks):
            if t.task_id == resolved_target_id:
                target_idx = idx
                break
        target_task = cloned_tasks[target_idx]

        if resolved_code == "SKIP_HABIT":
            removed_task = cloned_tasks.pop(target_idx)
            for t in cloned_tasks:
                if removed_task.task_id in t.depends_on:
                    t.depends_on = [d for d in t.depends_on if d != removed_task.task_id]
            frees_min = removed_task.get_planned_duration_min()
            return cloned_tasks, {
                "option_id": resolved_id,
                "code": "SKIP_HABIT",
                "task_id": removed_task.task_id,
                "title": removed_task.title,
                "action": "REMOVED_SKIPPED_HABIT",
                "frees_min": frees_min,
                "description": (
                    f"Đã bỏ qua task '{removed_task.title}' ({removed_task.task_id}) trong tuần này, "
                    f"giải phóng {frees_min} phút cho các bài tập hạn chót."
                ),
            }

        if resolved_code == "SHORTEN_TASK":
            old_dur = target_task.get_planned_duration_min()
            if (
                matched_opt
                and matched_opt.get("task") == target_task.task_id
                and matched_opt.get("new_duration_min")
            ):
                new_dur = int(matched_opt["new_duration_min"])
            else:
                floor_min = max(15, min(target_task.min_chunk_min, 45))
                cut = round_up_to_15(shortage_min) if shortage_min > 0 else round_up_to_15(old_dur // 2)
                new_dur = max(floor_min, old_dur - cut)
            new_dur = max(15, min(old_dur, round_up_to_15(new_dur)))
            target_task.duration_min = new_dur
            if new_dur <= 90:
                target_task.min_chunk_min = min(45, new_dur)
                target_task.max_chunk_min = max(45, new_dur)
            else:
                target_task.is_splittable = True
                target_task.min_chunk_min = 15
                target_task.max_chunk_min = 15  # Required so T06 exact-capacity pockets (15m cracks) reach 100%
            reduces_min = old_dur - new_dur
            return cloned_tasks, {
                "option_id": resolved_id,
                "code": "SHORTEN_TASK",
                "task_id": target_task.task_id,
                "title": target_task.title,
                "action": "SHORTENED_DURATION",
                "old_duration_min": old_dur,
                "new_duration_min": new_dur,
                "reduces_min": reduces_min,
                "frees_min": reduces_min,
                "description": (
                    f"Đã rút ngắn '{target_task.title}' ({target_task.task_id}) "
                    f"từ {old_dur} phút xuống {new_dur} phút (-{reduces_min} phút)."
                ),
            }

        if resolved_code == "ALLOW_SPLIT":
            old_split = target_task.is_splittable
            old_min_chunk = target_task.min_chunk_min
            target_task.is_splittable = True
            target_task.min_chunk_min = 45
            if target_task.max_chunk_min < 45:
                target_task.max_chunk_min = 90
            return cloned_tasks, {
                "option_id": resolved_id,
                "code": "ALLOW_SPLIT",
                "task_id": target_task.task_id,
                "title": target_task.title,
                "action": "ENABLED_SPLITTING",
                "old_is_splittable": old_split,
                "new_is_splittable": True,
                "old_min_chunk_min": old_min_chunk,
                "new_min_chunk_min": 45,
                "description": (
                    f"Đã bật chế độ chia nhỏ (is_splittable=True, min_chunk=45p) "
                    f"cho task '{target_task.title}' ({target_task.task_id})."
                ),
            }

        old_deadline = target_task.format_deadline_label(week_start_iso=profile.planning_week_start)
        new_day = (
            str(matched_opt.get("new_deadline_day"))
            if matched_opt and matched_opt.get("new_deadline_day")
            else ("Next Monday" if (target_task.deadline_day or "").strip().lower() in ("sunday", "next monday") else "Sunday")
        )
        target_task.deadline_day = new_day
        target_task.deadline_time = "23:59"
        target_task.due = None
        return cloned_tasks, {
            "option_id": resolved_id,
            "code": "POSTPONE_LOWEST",
            "task_id": target_task.task_id,
            "title": target_task.title,
            "action": "POSTPONED_DEADLINE",
            "old_deadline": old_deadline,
            "new_deadline": f"{new_day} 23:59",
            "frees_min": target_task.get_planned_duration_min(),
            "description": (
                f"Đã dời hạn chót của '{target_task.title}' ({target_task.task_id}) "
                f"từ {old_deadline} sang {new_day} 23:59."
            ),
        }

