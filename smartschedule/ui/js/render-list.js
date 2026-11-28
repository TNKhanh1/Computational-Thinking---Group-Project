/**
 * View 2: Chronological List View — linear day-by-day sequence merging
 * Fixed Events, ScheduleBlocks, 15m Recovery Rests, and optional Sleep.
 */

import { api } from "./api.js";
import { showToast } from "./modals.js";
import { invalidateSolverCaches, serializeWorkspaceState, state } from "./state.js";
import { popUndoSnapshot, pushUndoSnapshot } from "./undo-history.js";
import {
  CATEGORY_LABELS,
  WEEKDAYS_VI_FULL,
  addDays,
  esc,
  expandFixedEventsForDay,
  fmtDDMMYYYY,
  getEnergyForHour,
  getSleepSegmentsForDay,
  minToHHMM,
  parseWeekStartDate,
  resolveNowSlot,
  slotToDayIndex,
  slotToMinuteInDay,
} from "./utils.js";

let _inlineEditingFixedId = null;

export function renderListView(container, callbacks) {
  const horizonDays = Math.max(7, Math.min(14, Number(state.commitments.horizon_days) || 7));
  const wsDate = parseWeekStartDate(state.commitments.planning_week_start);
  const nowSlot = resolveNowSlot(state.commitments);
  const todayDayIdx = Math.min(horizonDays - 1, Math.max(0, slotToDayIndex(nowSlot)));

  const blocks = state.currentSchedule?.blocks || [];
  const pinnedIds = new Set((state.pinnedBlocks || []).map((b) => b.block_id));
  const warningBlockIds = new Set();
  for (const c of state.currentEvaluation?.d1_icee_critiques || []) {
    for (const bid of c.block_ids || []) warningBlockIds.add(bid);
  }

  const filter = state.listFilter || "all";
  const search = (state.listSearch || "").trim().toLowerCase();

  const dayGroupsHtml = [];

  for (let d = 0; d < horizonDays; d++) {
    const dt = addDays(wsDate, d);
    const isToday = d === todayDayIdx;
    const isPastDay = d < todayDayIdx;

    const items = [];

    // 1. Sleep (optional)
    if (state.listShowSleep) {
      for (const seg of getSleepSegmentsForDay(state.commitments.sleep_schedule)) {
        items.push({
          kind: "sleep",
          startMin: seg.startMin,
          endMin: seg.endMin,
          durationMin: seg.endMin - seg.startMin,
          title: seg.label,
          category: "SLEEP",
          temporal: d * 96 + Math.floor(seg.endMin / 15) <= nowSlot ? "past" : d * 96 + Math.floor(seg.startMin / 15) <= nowSlot ? "now" : "future",
          hasWarning: false,
        });
      }
    }

    // 2. Fixed events
    const fixedEvs = expandFixedEventsForDay(state.commitments.fixed_events, d);
    const classMin = fixedEvs
      .filter((e) => String(e.category || "").toUpperCase() === "ACADEMIC_CLASS")
      .reduce((acc, e) => acc + e.durationMin, 0);

    for (const ev of fixedEvs) {
      const sSlot = d * 96 + Math.floor(ev.startMin / 15);
      const eSlot = d * 96 + Math.floor(ev.endMin / 15);
      items.push({
        kind: "fixed",
        eventId: ev.event_id || ev.id || "",
        fixedEvent: ev,
        startMin: ev.startMin,
        endMin: ev.endMin,
        durationMin: ev.durationMin,
        title: ev.title,
        category: ev.category || "ACADEMIC_CLASS",
        temporal: eSlot <= nowSlot ? "past" : sSlot <= nowSlot ? "now" : "future",
        hasWarning: false,
      });
    }

    // 3. Study blocks + automatic 15m recovery rest rows after load=3 or >=90m sessions
    const dayBlocks = blocks
      .filter((b) => slotToDayIndex(b.start_slot) === d)
      .sort((a, b) => a.start_slot - b.start_slot);
    const studyMin = dayBlocks.reduce((acc, b) => acc + Number(b.duration_min || 0), 0);

    for (const b of dayBlocks) {
      const startMin = slotToMinuteInDay(b.start_slot);
      const dur = Number(b.duration_min || (b.end_slot - b.start_slot) * 15);
      const endMin = startMin + dur;
      const temporal = b.end_slot <= nowSlot ? "past" : b.start_slot <= nowSlot ? "now" : "future";
      const load = Number(b.cognitive_load || 2);
      const energy = b.energy_level || getEnergyForHour(state.commitments.focus_preference, Math.floor(startMin / 60));
      const firstReason = (b.reasons || [])[0];
      const reasonSummary = typeof firstReason === "string" ? firstReason : firstReason?.text || firstReason?.code || "";

      items.push({
        kind: "study",
        block: b,
        startMin,
        endMin,
        durationMin: dur,
        title: b.title,
        category: b.category || "DEADLINE",
        load,
        energy,
        isPinned: pinnedIds.has(b.block_id) || b.state === "PINNED",
        doneInfo: state.completedBlocks[b.block_id],
        reasonSummary,
        temporal,
        hasWarning: warningBlockIds.has(b.block_id) || (load === 3 && energy === 1),
      });

      const restEnd = endMin + 15;
      const overlapsFixed = fixedEvs.some((fe) => fe.startMin < restEnd && fe.endMin > endMin);
      if ((load === 3 || dur >= 90) && restEnd <= 1440 && !overlapsFixed) {
        items.push({
          kind: "rest",
          startMin: endMin,
          endMin: restEnd,
          durationMin: 15,
          title: "Nghỉ phục hồi nhận thức (Albulescu > 10p)",
          category: "REST",
          temporal: b.end_slot + 1 <= nowSlot ? "past" : "future",
          hasWarning: false,
        });
      }
    }

    items.sort((a, b) => a.startMin - b.startMin);

    // Filter items
    const filtered = items.filter((it) => {
      if (filter === "study" && it.kind !== "study") return false;
      if (filter === "past" && it.temporal !== "past") return false;
      if (filter === "today" && !isToday) return false;
      if (filter === "future" && it.temporal !== "future") return false;
      if (filter === "warning" && !it.hasWarning) return false;
      if (search) {
        const hay = `${it.title} ${it.category} ${it.reasonSummary || ""}`.toLowerCase();
        if (!hay.includes(search)) return false;
      }
      return true;
    });

    if (filtered.length === 0) continue;

    const totalLoad = classMin + studyMin;
    const rowsHtml = filtered
      .map((it) => {
        const temporalBadge =
          it.temporal === "now"
            ? `<span class="badge badge-danger">Đang diễn ra</span>`
            : it.temporal === "past"
              ? `<span class="badge badge-neutral">Đã qua</span>`
              : `<span class="badge badge-ok">Sắp tới</span>`;

        if (it.kind === "rest") {
          return `
            <div class="chrono-item is-rest">
              <div><span class="badge badge-teal">Nghỉ 15p</span></div>
              <div class="mono">${minToHHMM(it.startMin)} – ${minToHHMM(it.endMin)}</div>
              <div>${esc(it.title)}</div>
              <div></div>
            </div>`;
        }

        if (it.kind === "fixed" || it.kind === "sleep") {
          const catBadgeCls =
            it.category === "ACADEMIC_CLASS"
              ? "badge-info"
              : it.category === "MEAL"
                ? "badge-teal"
                : "badge-neutral";
          const isEditableFixed = it.kind === "fixed" && Boolean(it.eventId);
          const isEditingThis = isEditableFixed && _inlineEditingFixedId === it.eventId;

          if (isEditingThis) {
            const ev = it.fixedEvent || {};
            return `
              <div class="chrono-item is-editing-fixed">
                <div><span class="badge badge-info">Đang sửa</span></div>
                <div style="grid-column:span 2;">
                  <form class="inline-fixed-edit-form" data-inline-fixed-form="${esc(it.eventId)}" style="display:flex;flex-wrap:wrap;gap:6px;align-items:center;">
                    <input type="text" class="input" name="title" value="${esc(ev.title || it.title)}" required style="flex:1;min-width:150px;min-height:30px;padding:4px 8px;" aria-label="Tên lịch cố định" />
                    <input type="time" class="input mono" name="start_time" value="${esc(ev.start_time || minToHHMM(it.startMin))}" required style="width:105px;min-height:30px;padding:4px 6px;" aria-label="Giờ bắt đầu" />
                    <input type="time" class="input mono" name="end_time" value="${esc(ev.end_time || minToHHMM(it.endMin))}" required style="width:105px;min-height:30px;padding:4px 6px;" aria-label="Giờ kết thúc" />
                    <button type="submit" class="btn btn-primary btn-sm">💾 Lưu</button>
                    <button type="button" class="btn btn-sm btn-ghost" data-cancel-inline-fixed>Hủy</button>
                  </form>
                </div>
                <div class="chrono-item-actions"></div>
              </div>`;
          }

          return `
            <div class="chrono-item ${it.temporal === "past" ? "is-past" : ""} ${it.temporal === "now" ? "is-now" : ""}">
              <div>${temporalBadge}</div>
              <div class="mono" style="font-weight:600;">${minToHHMM(it.startMin)} – ${minToHHMM(it.endMin)} <span style="color:var(--p-muted);font-weight:400;">(${it.durationMin}p)</span></div>
              <div>
                <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                  <strong>${esc(it.title)}</strong>
                  <span class="badge ${catBadgeCls}">${esc(CATEGORY_LABELS[it.category] || it.category)}</span>
                </div>
              </div>
              <div class="chrono-item-actions" style="color:var(--p-muted);font-size:12px;">
                ${
                  isEditableFixed
                    ? `<button type="button" class="btn btn-sm" data-list-edit-fixed="${esc(it.eventId)}" title="Chỉnh sửa lịch cố định này">✏️ Sửa</button>
                       <button type="button" class="btn btn-sm btn-danger" data-list-delete-fixed="${esc(it.eventId)}" title="Xóa lịch cố định này">🗑️ Xóa</button>`
                    : "Cố định"
                }
              </div>
            </div>`;
        }

        const b = it.block;
        const loadCls = it.load === 3 ? "badge-danger" : it.load === 2 ? "badge-warn" : "badge-ok";
        return `
          <div class="chrono-item ${it.temporal === "past" ? "is-past" : ""} ${it.temporal === "now" ? "is-now" : ""}">
            <div>${temporalBadge}</div>
            <div class="mono" style="font-weight:600;">${minToHHMM(it.startMin)} – ${minToHHMM(it.endMin)} <span style="color:var(--p-muted);font-weight:400;">(${it.durationMin}p)</span></div>
            <div style="display:flex;flex-direction:column;gap:3px;">
              <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                <strong>${esc(it.title)}</strong>
                <span class="badge badge-neutral">${esc(CATEGORY_LABELS[it.category] || it.category)}</span>
                ${state.developerMode ? `<span class="badge ${loadCls}">L${it.load}</span><span class="badge ${it.energy === 3 ? "badge-info" : "badge-neutral"}">${it.energy === 3 ? "Peak E3" : `E${it.energy}`}</span>` : ""}
                ${it.isPinned ? `<span class="badge badge-dark">Ghim</span>` : ""}
                ${it.doneInfo ? `<span class="badge badge-ok">Xong ${it.doneInfo.actual_min}p</span>` : ""}
                ${it.hasWarning ? `<span class="badge badge-warn">Cần chú ý</span>` : ""}
              </div>
              ${state.developerMode && it.reasonSummary ? `<div style="font-size:12px;color:var(--p-muted);">${esc(it.reasonSummary)}</div>` : ""}
            </div>
            <div class="chrono-item-actions">
              <button type="button" class="btn btn-sm" data-list-pin="${esc(b.block_id)}">${it.isPinned ? "Bỏ ghim" : "Ghim"}</button>
              <button type="button" class="btn btn-sm" data-list-checkin="${esc(b.block_id)}">Hoàn thành</button>
              <button type="button" class="btn btn-sm btn-tonal" data-list-inspect="${esc(b.block_id)}">Chi tiết</button>
              <button type="button" class="btn btn-sm btn-danger" data-list-delete-task="${esc(b.task_id)}" title="Xóa công việc này" aria-label="Xóa công việc ${esc(it.title)}">🗑️</button>
            </div>
          </div>`;
      })
      .join("");

    dayGroupsHtml.push(`
      <section class="card chrono-day-group">
        <header class="chrono-day-head ${isToday ? "is-today" : ""}">
          <div style="display:flex;align-items:center;gap:8px;">
            <strong>${WEEKDAYS_VI_FULL[d % 7]}, <span class="mono">${fmtDDMMYYYY(dt)}</span></strong>
            ${isToday ? `<span class="badge badge-ok">HÔM NAY</span>` : isPastDay ? `<span class="badge badge-neutral">Quá khứ</span>` : ""}
          </div>
          ${
            state.developerMode
              ? `<div class="mono" style="font-size:12px;color:var(--p-ink-soft);">Tổng tải Lớp + Tự học: <strong>${totalLoad}p</strong> / 540p (Lớp ${classMin}p · Tự học ${studyMin}p)</div>`
              : `<div class="mono" style="font-size:12px;color:var(--p-muted);">${dayBlocks.length + fixedEvs.length} hoạt động</div>`
          }
        </header>
        <div>${rowsHtml}</div>
      </section>`);
  }

  container.innerHTML = `
    <div class="card list-toolbar">
      <div class="filter-pills">
        ${[
          ["all", "Tất cả"],
          ["study", "Chỉ việc tự học"],
          ["past", "Quá khứ"],
          ["today", "Hôm nay"],
          ["future", "Sắp tới"],
          ["warning", "Có cảnh báo"],
        ]
          .map(
            ([k, lbl]) =>
              `<button type="button" class="filter-pill ${filter === k ? "active" : ""}" data-list-filter="${k}">${lbl}</button>`
          )
          .join("")}
      </div>
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <label class="toggle-label">
          <input type="checkbox" id="chkListSleep" ${state.listShowSleep ? "checked" : ""} />
          <span>Hiện giờ ngủ</span>
        </label>
        <input type="search" class="input" id="inpListSearch" placeholder="Tìm tên việc, môn học..." value="${esc(state.listSearch)}" style="width:220px;min-height:32px;" />
      </div>
    </div>

    ${
      dayGroupsHtml.length > 0
        ? dayGroupsHtml.join("")
        : `<div class="card" style="padding:28px;text-align:center;color:var(--p-muted);">Không có mục nào khớp với bộ lọc hiện tại.</div>`
    }
  `;

  container.querySelectorAll("[data-list-filter]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.listFilter = btn.getAttribute("data-list-filter");
      renderListView(container, callbacks);
    });
  });
  container.querySelector("#chkListSleep")?.addEventListener("change", (e) => {
    state.listShowSleep = e.target.checked;
    renderListView(container, callbacks);
  });
  container.querySelector("#inpListSearch")?.addEventListener("input", (e) => {
    state.listSearch = e.target.value;
    renderListView(container, callbacks);
  });

  container.querySelectorAll("[data-list-inspect]").forEach((btn) =>
    btn.addEventListener("click", () => callbacks.onInspectBlock(btn.getAttribute("data-list-inspect")))
  );
  container.querySelectorAll("[data-list-pin]").forEach((btn) =>
    btn.addEventListener("click", () => callbacks.onTogglePin(btn.getAttribute("data-list-pin")))
  );
  container.querySelectorAll("[data-list-checkin]").forEach((btn) =>
    btn.addEventListener("click", () => callbacks.onInspectBlock(btn.getAttribute("data-list-checkin"), "checkin"))
  );

  const _syncAfterFallbackMutation = async (toastMsg) => {
    await api.saveState(serializeWorkspaceState(state), state.workspaceId).catch(() => null);
    renderListView(container, callbacks);
    showToast(toastMsg, "ok", {
      onUndo: async () => {
        const restored = popUndoSnapshot(state);
        if (!restored) return;
        await api.saveState(serializeWorkspaceState(state), state.workspaceId).catch(() => null);
        renderListView(container, callbacks);
        showToast(`↩ Đã hoàn tác: ${restored.actionLabel}`, "ok");
      },
    });
  };

  container.querySelectorAll("[data-list-delete-task]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const taskId = btn.getAttribute("data-list-delete-task");
      if (!taskId) return;
      if (typeof callbacks?.onDeleteTask === "function") {
        callbacks.onDeleteTask(taskId);
        return;
      }
      const taskObj = (state.tasks || []).find((t) => t.task_id === taskId);
      const label = `Xóa công việc "${taskObj?.title || taskId}"`;
      pushUndoSnapshot(state, label);
      try {
        const res = await api.deleteTask({
          workspace_id: state.workspaceId,
          commitments: state.commitments,
          tasks: state.tasks,
          pinned_blocks: state.pinnedBlocks,
          task_id: taskId,
          algorithm: state.activeSolver || "SCORED_GREEDY",
        });
        if (Array.isArray(res?.updated_tasks)) state.tasks = res.updated_tasks;
        if (Array.isArray(res?.updated_pinned_blocks)) state.pinnedBlocks = res.updated_pinned_blocks;
        invalidateSolverCaches();
        if (res?.schedule) {
          state.currentSchedule = res.schedule;
          state.schedulesBySolver[state.activeSolver] = res.schedule;
        }
        await _syncAfterFallbackMutation(`🗑️ Đã xóa "${taskObj?.title || taskId}".`);
      } catch (err) {
        popUndoSnapshot(state);
        showToast(`Lỗi xóa công việc: ${err.message}`, "danger");
      }
    });
  });

  container.querySelectorAll("[data-list-delete-fixed]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const eventId = btn.getAttribute("data-list-delete-fixed");
      if (!eventId) return;
      const evObj = (state.commitments.fixed_events || []).find((e) => (e.event_id || e.id) === eventId);
      if (typeof callbacks?.onDeleteFixedEvent === "function") {
        callbacks.onDeleteFixedEvent(eventId, evObj);
        return;
      }
      pushUndoSnapshot(state, `Xóa lịch cố định "${evObj?.title || eventId}"`);
      try {
        const res = await api.deleteFixedEvent({
          workspace_id: state.workspaceId,
          commitments: state.commitments,
          tasks: state.tasks,
          pinned_blocks: state.pinnedBlocks,
          event_id: eventId,
          algorithm: state.activeSolver || "SCORED_GREEDY",
        });
        if (res?.updated_commitments) state.commitments = res.updated_commitments;
        invalidateSolverCaches();
        if (res?.schedule) {
          state.currentSchedule = res.schedule;
          state.schedulesBySolver[state.activeSolver] = res.schedule;
        }
        if (_inlineEditingFixedId === eventId) _inlineEditingFixedId = null;
        await _syncAfterFallbackMutation(`🗑️ Đã xóa lịch cố định "${evObj?.title || eventId}".`);
      } catch (err) {
        popUndoSnapshot(state);
        showToast(`Lỗi xóa lịch cố định: ${err.message}`, "danger");
      }
    });
  });

  container.querySelectorAll("[data-list-edit-fixed]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const eventId = btn.getAttribute("data-list-edit-fixed");
      if (!eventId) return;
      const evObj = (state.commitments.fixed_events || []).find((e) => (e.event_id || e.id) === eventId);
      if (typeof callbacks?.onEditFixedEvent === "function") {
        callbacks.onEditFixedEvent(eventId, evObj);
        return;
      }
      _inlineEditingFixedId = eventId;
      renderListView(container, callbacks);
    });
  });

  container.querySelectorAll("[data-cancel-inline-fixed]").forEach((btn) => {
    btn.addEventListener("click", () => {
      _inlineEditingFixedId = null;
      renderListView(container, callbacks);
    });
  });

  container.querySelectorAll("[data-inline-fixed-form]").forEach((form) => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const eventId = form.getAttribute("data-inline-fixed-form");
      const existing = (state.commitments.fixed_events || []).find((ev) => (ev.event_id || ev.id) === eventId);
      if (!existing) return;
      const title = form.querySelector('[name="title"]')?.value.trim();
      const startTime = form.querySelector('[name="start_time"]')?.value;
      const endTime = form.querySelector('[name="end_time"]')?.value;
      if (!title || !startTime || !endTime || startTime >= endTime) {
        showToast("Giờ kết thúc phải lớn hơn giờ bắt đầu.", "danger");
        return;
      }
      const updatedEvent = {
        ...existing,
        event_id: existing.event_id || eventId,
        title,
        start_time: startTime,
        end_time: endTime,
      };
      if (typeof callbacks?.onUpsertFixedEvent === "function") {
        _inlineEditingFixedId = null;
        callbacks.onUpsertFixedEvent(updatedEvent);
        return;
      }
      pushUndoSnapshot(state, `Cập nhật lịch cố định "${title}"`);
      try {
        const res = await api.upsertFixedEvent({
          workspace_id: state.workspaceId,
          commitments: state.commitments,
          tasks: state.tasks,
          pinned_blocks: state.pinnedBlocks,
          event: updatedEvent,
          algorithm: state.activeSolver || "SCORED_GREEDY",
        });
        if (res?.updated_commitments) state.commitments = res.updated_commitments;
        invalidateSolverCaches();
        if (res?.schedule) {
          state.currentSchedule = res.schedule;
          state.schedulesBySolver[state.activeSolver] = res.schedule;
        }
        _inlineEditingFixedId = null;
        await _syncAfterFallbackMutation(`✏️ Đã cập nhật lịch cố định "${title}".`);
      } catch (err) {
        popUndoSnapshot(state);
        showToast(`Lỗi cập nhật lịch cố định: ${err.message}`, "danger");
      }
    });
  });
}
