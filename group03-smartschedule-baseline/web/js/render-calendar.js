/**
 * View 1: Clean User-First Daily / Weekly Timeline Calendar (1 / 3 / 5 / 7 days),
 * Smooth Live Transitions when edited by the Right Copilot,
 * Yellow Dense-Schedule Warnings & Red Deadlock Alerts,
 * and Hidden Parameter Debug Badges when Developer Mode is active.
 */

import { state } from "./state.js";
import {
  CATEGORY_LABELS,
  WEEKDAYS_EN,
  WEEKDAYS_VI_FULL,
  WEEKDAYS_VI_SHORT,
  addDays,
  computeBufferPreview,
  esc,
  expandFixedEventsForDay,
  fmtDDMM,
  formatDeadlineCountdown,
  getEnergyForHour,
  getSleepSegmentsForDay,
  minToHHMM,
  parseWeekStartDate,
  resolveNowSlot,
  slotToDayIndex,
  slotToMinuteInDay,
} from "./utils.js";

const HOUR_HEIGHT = 58; // px per hour (matches .cal-hour-slot)

export function renderCalendarView(container, callbacks) {
  if (!container) return;
  const horizonDays = Math.max(7, Math.min(14, Number(state.commitments.horizon_days) || 7));
  const wsDate = parseWeekStartDate(state.commitments.planning_week_start);
  const nowSlot = resolveNowSlot(state.commitments);
  const todayDayIdx = Math.min(horizonDays - 1, Math.max(0, slotToDayIndex(nowSlot)));
  const nowMinInDay = slotToMinuteInDay(nowSlot);

  const isNarrow = window.innerWidth < 768;
  const requestedDays = Number(state.visibleDaysCount) || 7;
  const visibleCount = isNarrow ? Math.min(requestedDays, requestedDays === 1 ? 1 : 3) : requestedDays;

  const maxStart = horizonDays - 1;
  if (state.scrubberStartDay > maxStart) state.scrubberStartDay = maxStart;
  if (state.scrubberStartDay < 0) state.scrubberStartDay = 0;

  const viewWeekOffset = Number(state.viewWeekOffset) || 0;
  const startDay = viewWeekOffset !== 0 ? viewWeekOffset * 7 : state.scrubberStartDay;
  const inPlan = (d) => d >= 0 && d < horizonDays;
  const wd = (d) => ((d % 7) + 7) % 7;
  const dayIndices = [];
  for (let i = 0; i < visibleCount; i++) {
    dayIndices.push(startDay + i);
  }
  const endDay = dayIndices[dayIndices.length - 1];

  const schedule = state.currentSchedule;
  const blocks = state.overloadPreview?.blocks || schedule?.blocks || [];
  const unplaced = schedule?.unplaced_tasks || [];
  const pinnedIds = new Set((state.pinnedBlocks || []).map((b) => b.block_id));
  const taskById = new Map((state.tasks || []).map((t) => [t.task_id, t]));

  const diffAddedSet = new Set(state.lastScheduleDiff?.added || []);
  const diffMovedSet = new Set(state.lastScheduleDiff?.moved || []);
  const diffFresh = state.lastScheduleDiff?.finalizedAt && Date.now() - state.lastScheduleDiff.finalizedAt < 8000;

  const startHour = state.hideSleepHours ? 6 : 0;
  const endHour = 24;
  const hours = [];
  for (let h = startHour; h < endHour; h++) hours.push(h);

  // Quick day chips across the horizon
  const dayChipsHtml = Array.from({ length: horizonDays }, (_, d) => {
    const dt = addDays(wsDate, d);
    const inView = d >= startDay && d <= endDay;
    const isToday = d === todayDayIdx;
    const isPast = d < todayDayIdx;
    return `<button type="button" class="day-chip ${inView ? "in-view" : ""} ${isToday ? "is-today" : ""} ${isPast ? "is-past" : ""}" data-jump-day="${d}" title="Bắt đầu từ ${WEEKDAYS_VI_FULL[wd(d)]} ${fmtDDMM(dt)}">
      ${WEEKDAYS_VI_SHORT[wd(d)]} <span class="mono">${fmtDDMM(dt)}</span>
    </button>`;
  }).join("");

  // Finalized live transition banner when updated via Copilot/Chat
  let finalizedBannerHtml = "";
  if (diffFresh && state.lastScheduleDiff?.finalizedMessage) {
    finalizedBannerHtml = `
      <div class="alert-banner ok cal-finalized-banner" id="calendarFinalizedBanner">
        <div>
          <strong>${esc(state.lastScheduleDiff.finalizedMessage)}</strong>
          ${
            diffAddedSet.size + diffMovedSet.size > 0
              ? `<span style="margin-left:8px;color:var(--p-muted);font-size:12.5px;">(${diffAddedSet.size} khối mới · ${diffMovedSet.size} khối đã chuyển chỗ)</span>`
              : ""
          }
        </div>
        <button type="button" class="btn btn-sm btn-ghost" id="btnDismissFinalized">Đã hiểu</button>
      </div>`;
  }

  // Edge Case Banner (Yellow Density Warning or Red Deadlock Banner)
  let edgeBannerHtml = "";
  if (state.edgeCaseBanner) {
    const isDeadlock = state.edgeCaseBanner.type === "DEADLOCK";
    edgeBannerHtml = `
      <div class="alert-banner ${isDeadlock ? "danger" : "warn"}">
        <div>
          <strong>${isDeadlock ? "🚨 Lịch bị kẹt / Trùng hạn chót:" : "⚠️ Cảnh báo lịch trình dày đặc:"}</strong>
          <span>${esc(state.edgeCaseBanner.message_vi)}</span>
        </div>
        ${isDeadlock ? `<button type="button" class="btn btn-sm btn-primary" id="btnOpenOverloadRescueFromBanner">Xem hướng gỡ rối</button>` : ""}
      </div>`;
  }

  // Overload preview notice
  let previewBannerHtml = "";
  if (state.overloadPreview) {
    previewBannerHtml = `
      <div class="alert-banner info">
        <div>
          <strong>Đang xem thử phương án gỡ rối:</strong>
          Các khối nét đứt là lịch đề xuất. Bạn có thể áp dụng hoặc hoàn tác.
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button type="button" class="btn btn-primary btn-sm" id="btnApplyOverloadPreview">Áp dụng phương án</button>
          <button type="button" class="btn btn-sm" id="btnCancelOverloadPreview">Hoàn tác</button>
        </div>
      </div>`;
  }

  // Out-of-plan week notice
  let outOfPlanHtml = "";
  if (dayIndices.some((d) => !inPlan(d))) {
    const viewStart = addDays(wsDate, startDay);
    const planEnd = addDays(wsDate, horizonDays - 1);
    outOfPlanHtml = `
      <div class="alert-banner info out-of-plan-banner">
        <div>
          <strong>Đang xem tuần ${fmtDDMM(viewStart)} – ${fmtDDMM(addDays(viewStart, 6))}, ngoài kỳ đang lập lịch (${fmtDDMM(wsDate)} – ${fmtDDMM(planEnd)}).</strong>
          Lớp học & thói quen lặp hằng tuần vẫn hiển thị.
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button type="button" class="btn btn-sm" id="btnBackToPlanWeek">← Về tuần đang lập lịch</button>
          <button type="button" class="btn btn-primary btn-sm" id="btnPlanViewedWeek">Lập kế hoạch cho tuần này</button>
        </div>
      </div>`;
  }

  const isPastDue = (u) =>
    u.reason_code === "PAST_DUE" || u.reason_code === "DEADLINE_IN_PAST" || String(u.reason || "").includes("DEADLINE_IN_PAST");
  const pastDue = unplaced.filter(isPastDue);
  const genuineUnplaced = unplaced.filter((u) => !isPastDue(u));
  const dueOf = (u) => {
    const m = String(taskById.get(u.task_id)?.due || "").match(/^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/);
    return m ? { date: new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])), time: m[4] ? `${m[4]}:${m[5]}` : "" } : null;
  };

  let pastDueHtml = "";
  if (pastDue.length > 0) {
    const dues = pastDue.map(dueOf).filter(Boolean);
    const latest = dues.length ? new Date(Math.max(...dues.map((d) => d.date.getTime()))) : null;
    const weeksBack = latest ? Math.floor((latest.getTime() - wsDate.getTime()) / (7 * 86400000)) : 0;
    const targetWs = addDays(wsDate, weeksBack * 7);
    const chips = pastDue
      .map((u) => {
        const d = dueOf(u);
        return `<div class="unplaced-chip past-due-chip">
          <strong>${esc(u.title || u.task_id)}</strong>
          <span class="mono">${u.duration_min}p</span>
          <span style="color:var(--p-muted)">· hạn ${d ? `${fmtDDMM(d.date)}${d.time ? ` ${d.time}` : ""}` : esc(u.deadline || "trước tuần này")}</span>
        </div>`;
      })
      .join("");
    pastDueHtml = `
      <div class="card unplaced-strip past-due-strip">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0;">
            <span class="badge badge-info">Đã quá hạn trước tuần này (${pastDue.length})</span>
            <span style="font-size:12.5px;color:var(--p-muted)">
              Hạn chót của các việc này nằm trước ${fmtDDMM(wsDate)} nên không xếp vào tuần đang xem.
            </span>
          </div>
          ${
            latest && weeksBack < 0
              ? `<button type="button" class="btn btn-sm" id="btnJumpToDueWeek" data-week-shift="${weeksBack * 7}">← Về tuần có hạn (${fmtDDMM(targetWs)} – ${fmtDDMM(addDays(targetWs, 6))})</button>`
              : ""
          }
        </div>
        <div class="unplaced-list">${chips}</div>
      </div>`;
  }

  let unplacedHtml = "";
  if (genuineUnplaced.length > 0) {
    const chips = genuineUnplaced
      .map(
        (u) => `<div class="unplaced-chip">
          <strong>${esc(u.title || u.task_id)}</strong>
          <span class="mono">${u.duration_min}p</span>
          <span style="color:var(--p-muted)">· ${esc(u.reason || "Chưa đủ giờ trống")}</span>
        </div>`
      )
      .join("");
    unplacedHtml = `
      <div class="card unplaced-strip">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="badge badge-danger">Chưa xếp được (${genuineUnplaced.length})</span>
            <span style="font-size:12.5px;color:var(--p-muted)">Quỹ thời gian trống trước hạn chót đang bị kẹt.</span>
          </div>
          <button type="button" class="btn btn-sm btn-primary" id="btnOpenOverloadRescue">Gợi ý gỡ kẹt nhẹ nhàng</button>
        </div>
        <div class="unplaced-list">${chips}</div>
      </div>`;
  }

  const dayHeadsHtml = dayIndices
    .map((d) => {
      const dt = addDays(wsDate, d);
      const isToday = d === todayDayIdx;
      const isPast = d < todayDayIdx;
      const fixedEvs = expandFixedEventsForDay(state.commitments.fixed_events, wd(d));
      const classMin = fixedEvs
        .filter((e) => String(e.category || "").toUpperCase() === "ACADEMIC_CLASS")
        .reduce((acc, e) => acc + e.durationMin, 0);
      const dayBlocks = blocks.filter((b) => slotToDayIndex(b.start_slot) === d);
      const studyMin = dayBlocks.reduce((acc, b) => acc + Number(b.duration_min || 0), 0);
      const totalLoad = classMin + studyMin;
      const isDayDense = totalLoad >= 420;
      const pct = Math.min(100, Math.round((totalLoad / 540) * 100));
      const barCls = totalLoad > 600 ? "danger" : totalLoad >= 420 ? "warn" : "";

      const statusBadge = isToday
        ? `<span class="badge badge-info">Hôm nay</span>`
        : isPast
          ? `<span class="cal-day-sub">Đã qua</span>`
          : isDayDense
            ? `<span class="badge badge-warn">Khá dày</span>`
            : "";

      const devLoadMeter = state.developerMode
        ? `<div class="load-meter" title="Tổng Lớp (${classMin}p) + Tự học (${studyMin}p) / 540p">
             <div class="load-meter-label">
               <span>${visibleCount >= 7 ? "" : "Tải ngày"}</span>
               <span class="mono">${totalLoad} / 540p</span>
             </div>
             <div class="load-bar"><div class="load-bar-fill ${barCls}" style="width:${pct}%"></div></div>
           </div>`
        : isDayDense
          ? `<div class="user-dense-dot" title="Ngày này có lịch khá dày (~${(totalLoad / 60).toFixed(1)} tiếng)"></div>`
          : "";

      return `
        <div class="cal-day-head ${isToday ? "is-today" : ""} ${isPast ? "is-past" : ""} ${inPlan(d) ? "" : "out-of-plan"} ${isDayDense ? "is-dense-day" : ""}">
          <div class="cal-day-title-row">
            <div class="cal-day-identity">
              <span class="cal-date-circle mono">${String(dt.getDate()).padStart(2, "0")}</span>
              <div class="cal-day-name">${visibleCount >= 7 ? WEEKDAYS_VI_SHORT[wd(d)] : WEEKDAYS_VI_FULL[wd(d)]}</div>
            </div>
            ${statusBadge}
          </div>
          ${devLoadMeter}
        </div>`;
    })
    .join("");

  const timeLabelsHtml = hours
    .map((h) => `<div class="cal-hour-label mono">${String(h).padStart(2, "0")}:00</div>`)
    .join("");

  const dayColsHtml = dayIndices
    .map((d) => {
      const isToday = d === todayDayIdx;
      const isPast = d < todayDayIdx;
      const totalVisibleMin = (endHour - startHour) * 60;
      const pxPerMin = HOUR_HEIGHT / 60;

      const slotsHtml = hours
        .map((h) => {
          const eLevel = getEnergyForHour(state.commitments.focus_preference, h);
          const eCls = state.showEnergyBackdrop ? `energy-${eLevel}` : "";
          return inPlan(d)
            ? `<div class="cal-hour-slot ${eCls}" data-drop-day="${d}" data-drop-hour="${h}"></div>`
            : `<div class="cal-hour-slot ${eCls}"></div>`;
        })
        .join("");

      const eventsLayer = [];

      if (!state.hideSleepHours) {
        for (const seg of getSleepSegmentsForDay(state.commitments.sleep_schedule)) {
          const s = Math.max(startHour * 60, seg.startMin);
          const e = Math.min(endHour * 60, seg.endMin);
          if (e <= s) continue;
          const top = (s - startHour * 60) * pxPerMin;
          const height = Math.max(18, (e - s) * pxPerMin - 2);
          eventsLayer.push(`
            <div class="cal-event sleep" style="top:${top}px;height:${height}px;">
              <span style="font-weight:500;font-size:11px;">${esc(seg.label)}</span>
            </div>`);
        }
      }

      for (const ev of expandFixedEventsForDay(state.commitments.fixed_events, wd(d))) {
        const s = Math.max(startHour * 60, ev.startMin);
        const e = Math.min(endHour * 60, ev.endMin);
        if (e <= s) continue;
        const top = (s - startHour * 60) * pxPerMin;
        const height = Math.max(22, (e - s) * pxPerMin - 2);
        const cat = String(ev.category || "ACADEMIC_CLASS").toUpperCase();
        const evCls = cat === "ACADEMIC_CLASS" ? "fixed-class" : cat === "MEAL" ? "fixed-meal" : "fixed-other";
        eventsLayer.push(`
          <div class="cal-event ${evCls}" style="top:${top}px;height:${height}px;" title="${esc(ev.title)} (${ev.start_time}–${ev.end_time})">
            <div class="cal-ev-top">
              <span class="cal-ev-title">${esc(ev.title)}</span>
              ${visibleCount <= 5 ? `<span class="mono" style="font-size:10px;opacity:.75;">${esc(CATEGORY_LABELS[cat] || cat)}</span>` : ""}
            </div>
            ${height >= 36 ? `<div class="cal-ev-meta mono">${esc(ev.start_time)}–${esc(ev.end_time)}</div>` : ""}
          </div>`);
      }

      const dayBlocks = blocks.filter((b) => slotToDayIndex(b.start_slot) === d);
      for (const b of dayBlocks) {
        const bStartMin = slotToMinuteInDay(b.start_slot);
        const bEndMin = bStartMin + Number(b.duration_min || (b.end_slot - b.start_slot) * 15);
        const s = Math.max(startHour * 60, bStartMin);
        const e = Math.min(endHour * 60, bEndMin);
        if (e <= s) continue;
        const top = (s - startHour * 60) * pxPerMin;
        const height = Math.max(28, (e - s) * pxPerMin - 2);

        const isPastBlock = b.end_slot <= nowSlot;
        const isNowBlock = b.start_slot <= nowSlot && nowSlot < b.end_slot;
        const isPinned = pinnedIds.has(b.block_id) || b.state === "PINNED";
        const isProposed = b.state === "PROPOSED";
        const doneInfo = state.completedBlocks[b.block_id];
        const load = Number(b.cognitive_load || 2);
        const energy = b.energy_level || getEnergyForHour(state.commitments.focus_preference, Math.floor(bStartMin / 60));
        const countdown = !isPastBlock ? formatDeadlineCountdown(b.deadline_slot, nowSlot) : "Đã qua";

        const isEnter = diffFresh && diffAddedSet.has(b.block_id);
        const isMoved = diffFresh && diffMovedSet.has(b.block_id);

        const stateCls = [
          `load-${load}`,
          isPastBlock ? "state-past" : "",
          isNowBlock ? "state-now" : "",
          isPinned ? "state-pinned" : "",
          isProposed ? "state-proposed" : "",
          isEnter ? "cal-block-enter" : "",
          isMoved ? "cal-block-moved" : "",
        ]
          .filter(Boolean)
          .join(" ");

        const tagChips = [];
        if (isEnter) tagChips.push(`<span class="badge badge-ok" style="padding:1px 6px;font-size:9.5px;">Mới thêm</span>`);
        if (isMoved) tagChips.push(`<span class="badge badge-info" style="padding:1px 6px;font-size:9.5px;">Đã dời</span>`);
        if (isNowBlock) tagChips.push(`<span class="badge badge-danger" style="padding:1px 6px;font-size:9.5px;">Đang làm</span>`);
        if (doneInfo) tagChips.push(`<span class="badge badge-ok" style="padding:1px 6px;font-size:9.5px;">Xong</span>`);
        if (isPinned) tagChips.push(`<span class="badge badge-info" style="padding:1px 6px;font-size:9.5px;">Ghim</span>`);

        // User mode stays 100% clean & abstract; Developer Mode exposes hidden parameters right on the block
        const srcTask = taskById.get(b.task_id);
        let devHiddenLine = "";
        if (state.developerMode || state.showTechMetaOnBlocks) {
          const hash6 = srcTask?.trace_hash ? String(srcTask.trace_hash).slice(0, 6) : "—";
          const bufPrev = srcTask ? computeBufferPreview(srcTask.duration_min, load, state.commitments) : null;
          const mult = srcTask?.buffer_mode === "NONE" ? 1.0 : Number(srcTask?.buffer_multiplier > 1 ? srcTask.buffer_multiplier : bufPrev?.mult || 1.2);
          const splitTag = srcTask?.is_splittable ? `Split ${b.part || 1}/${b.parts || 1}` : "Atomic";
          devHiddenLine = `<div class="dev-hidden-param-badge mono">#${esc(hash6)} · L${load} · E${energy} · ×${mult.toFixed(2)} · ${esc(splitTag)} · ${esc(countdown)}</div>`;
        }

        eventsLayer.push(`
          <div class="cal-event task-block ${stateCls}"
               draggable="${!isPastBlock}"
               data-block-id="${esc(b.block_id)}"
               style="top:${top}px;height:${height}px;"
               title="${esc(b.title)} (${b.start_time}–${b.end_time}) — Nhấp để xem chi tiết hoặc kéo thả để dời giờ">
            <div class="cal-ev-top">
              <span class="cal-ev-title">${esc(b.title)}</span>
              <span style="display:inline-flex;gap:3px;align-items:center;">${tagChips.join("")}</span>
            </div>
            ${
              height >= 40
                ? `<div class="cal-ev-meta">
                    <span class="mono">${esc(b.start_time)}–${esc(b.end_time)}</span>
                  </div>`
                : ""
            }
            ${height >= 54 ? devHiddenLine : ""}
          </div>`);
      }

      let nowLineHtml = "";
      if (isToday && nowMinInDay >= startHour * 60 && nowMinInDay <= endHour * 60) {
        const nowTop = (nowMinInDay - startHour * 60) * pxPerMin;
        nowLineHtml = `
          <div class="now-line" style="top:${nowTop}px;">
            <span class="now-line-pill mono">${minToHHMM(nowMinInDay)}</span>
          </div>`;
      }

      return `
        <div class="cal-day-col ${isToday ? "is-today" : ""} ${isPast ? "is-past" : ""} ${inPlan(d) ? "" : "out-of-plan"}" style="height:${totalVisibleMin * pxPerMin}px;">
          ${slotsHtml}
          ${eventsLayer.join("")}
          ${nowLineHtml}
        </div>`;
    })
    .join("");

  const minColPx = visibleCount === 1 ? "1fr" : visibleCount >= 7 ? "minmax(108px, 1fr)" : "minmax(136px, 1fr)";
  const gridColsCss = `56px ${visibleCount === 1 ? "1fr" : `repeat(${dayIndices.length}, ${minColPx})`}`;

  container.innerHTML = `
    ${finalizedBannerHtml}
    ${edgeBannerHtml}
    ${outOfPlanHtml}
    ${previewBannerHtml}
    ${unplacedHtml}
    ${pastDueHtml}

    <div class="calendar-sheet">
      <div class="scrubber-bar">
        <div class="scrubber-left">
          <button type="button" class="btn btn-sm btn-icon" id="btnScrubPrev" ${state.scrubberStartDay <= 0 && viewWeekOffset === 0 ? "disabled" : ""} title="Lùi 1 ngày" aria-label="Lùi 1 ngày">
            <svg class="icon" viewBox="0 0 24 24"><path d="m15 18-6-6 6-6"/></svg>
          </button>
          <input type="range" class="scrubber-range" id="calScrubberRange" min="0" max="${maxStart}" value="${state.scrubberStartDay}" aria-label="Thanh kéo trượt ngày" />
          <button type="button" class="btn btn-sm btn-icon" id="btnScrubNext" ${state.scrubberStartDay >= maxStart && viewWeekOffset === 0 ? "disabled" : ""} title="Tiến 1 ngày" aria-label="Tiến 1 ngày">
            <svg class="icon" viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg>
          </button>
          <div class="day-chips">${dayChipsHtml}</div>
        </div>
        <div class="scrubber-controls">
          <button type="button" class="btn btn-sm btn-ghost" id="btnJumpToday" title="Về ngày hôm nay">Về hôm nay</button>
          <input type="checkbox" id="chkEnergyBackdrop" ${state.showEnergyBackdrop ? "checked" : ""} class="sr-only" aria-hidden="true" tabindex="-1" />
        </div>
      </div>

      <div class="calendar-shell">
        <div class="calendar-grid" style="grid-template-columns:${gridColsCss};${visibleCount === 1 ? "min-width:100%;" : ""}">
          <div class="cal-header-row">
            <div class="cal-corner mono">GMT+7</div>
            ${dayHeadsHtml}
          </div>
          <div class="cal-time-col">${timeLabelsHtml}</div>
          ${dayColsHtml}
        </div>
      </div>

      <div class="calendar-legend">
        <div class="legend-items">
          <span class="legend-dot"><span class="legend-swatch" style="background:#d46256"></span>Việc tập trung cao</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#d4952a"></span>Việc vừa</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#359464"></span>Việc nhẹ</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#3b7ddd"></span>Lịch cố định</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#3a8d8d"></span>Bữa ăn</span>
        </div>
        <span>Kéo thả khối để dời giờ · Hoặc nhắn trợ lý bên phải để sửa lịch tự động</span>
      </div>
    </div>
  `;

  container.querySelector("#btnDismissFinalized")?.addEventListener("click", () => {
    state.lastScheduleDiff = { added: [], moved: [], finalizedAt: null, finalizedMessage: "" };
    renderCalendarView(container, callbacks);
  });

  container.querySelector("#btnBackToPlanWeek")?.addEventListener("click", () => callbacks.onSetViewWeek?.(0));
  container.querySelector("#btnPlanViewedWeek")?.addEventListener("click", () => callbacks.onShiftWeek?.(viewWeekOffset * 7));

  container.querySelector("#btnScrubPrev")?.addEventListener("click", () => {
    state.viewWeekOffset = 0;
    state.scrubberStartDay = Math.max(0, state.scrubberStartDay - 1);
    renderCalendarView(container, callbacks);
    callbacks.onSyncRangeLabel?.();
  });
  container.querySelector("#btnScrubNext")?.addEventListener("click", () => {
    state.viewWeekOffset = 0;
    state.scrubberStartDay = Math.min(maxStart, state.scrubberStartDay + 1);
    renderCalendarView(container, callbacks);
    callbacks.onSyncRangeLabel?.();
  });
  container.querySelector("#calScrubberRange")?.addEventListener("input", (e) => {
    state.viewWeekOffset = 0;
    state.scrubberStartDay = Number(e.target.value);
    renderCalendarView(container, callbacks);
    callbacks.onSyncRangeLabel?.();
  });
  container.querySelector("#btnJumpToday")?.addEventListener("click", () => {
    state.viewWeekOffset = 0;
    state.scrubberStartDay = Math.min(maxStart, todayDayIdx);
    renderCalendarView(container, callbacks);
    callbacks.onSyncRangeLabel?.();
  });

  container.querySelectorAll("[data-jump-day]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = Number(btn.getAttribute("data-jump-day"));
      state.viewWeekOffset = 0;
      state.scrubberStartDay = Math.min(maxStart, Math.max(0, target));
      renderCalendarView(container, callbacks);
      callbacks.onSyncRangeLabel?.();
    });
  });

  container.querySelector("#btnOpenOverloadRescue")?.addEventListener("click", () => callbacks.onOpenOverloadRescue());
  container.querySelector("#btnOpenOverloadRescueFromBanner")?.addEventListener("click", () => callbacks.onOpenOverloadRescue());
  container.querySelector("#btnJumpToDueWeek")?.addEventListener("click", (e) => {
    callbacks.onShiftWeek?.(Number(e.currentTarget.getAttribute("data-week-shift")));
  });
  container.querySelector("#btnApplyOverloadPreview")?.addEventListener("click", () => callbacks.onApplyOverloadPreview());
  container.querySelector("#btnCancelOverloadPreview")?.addEventListener("click", () => callbacks.onCancelOverloadPreview());

  // Wire block clicks & drag-drop
  let draggedBlockId = null;
  container.querySelectorAll(".task-block[data-block-id]").forEach((el) => {
    const blockId = el.getAttribute("data-block-id");
    el.addEventListener("click", () => callbacks.onInspectBlock(blockId));
    el.addEventListener("dragstart", (ev) => {
      draggedBlockId = blockId;
      ev.dataTransfer.setData("text/plain", blockId);
      ev.dataTransfer.effectAllowed = "move";
    });
  });

  // Smooth scroll to newly animated block if present
  const firstChanged = container.querySelector(".cal-block-enter, .cal-block-moved");
  if (firstChanged) {
    firstChanged.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }

  container.querySelectorAll(".cal-hour-slot[data-drop-day]").forEach((slotEl) => {
    slotEl.addEventListener("dragover", (ev) => {
      ev.preventDefault();
      slotEl.classList.add("drop-over");
    });
    slotEl.addEventListener("dragleave", () => {
      slotEl.classList.remove("drop-over");
    });
    slotEl.addEventListener("drop", (ev) => {
      ev.preventDefault();
      slotEl.classList.remove("drop-over");
      const bid = draggedBlockId || ev.dataTransfer.getData("text/plain");
      if (!bid) return;
      const targetDay = Number(slotEl.getAttribute("data-drop-day"));
      const targetHour = Number(slotEl.getAttribute("data-drop-hour"));
      const newStartSlot = targetDay * 96 + targetHour * 4;
      const dayLabel = (targetDay >= 7 ? "Next " : "") + WEEKDAYS_EN[targetDay % 7];
      const timeLabel = `${String(targetHour).padStart(2, "0")}:00`;
      callbacks.onDropMoveBlock(bid, newStartSlot, dayLabel, timeLabel);
    });
  });
}
