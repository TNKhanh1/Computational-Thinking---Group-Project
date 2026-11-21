/**
 * View 1: Daily / Weekly Timeline Calendar (1 / 3 / 5 / 7 days with selectable start day),
 * Past / Now / Future differentiation, Drag-and-Drop rescheduling (/api/validate-move),
 * subtle Circadian backdrop, and clean card presentation (technical L1-L3/Peak labels hidden by default).
 */

import { state } from "./state.js";
import {
  CATEGORY_LABELS,
  WEEKDAYS_EN,
  WEEKDAYS_VI_FULL,
  WEEKDAYS_VI_SHORT,
  addDays,
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
  const horizonDays = Math.max(7, Math.min(14, Number(state.commitments.horizon_days) || 7));
  const wsDate = parseWeekStartDate(state.commitments.planning_week_start);
  const nowSlot = resolveNowSlot(state.commitments);
  const todayDayIdx = Math.min(horizonDays - 1, Math.max(0, slotToDayIndex(nowSlot)));
  const nowMinInDay = slotToMinuteInDay(nowSlot);

  const isNarrow = window.innerWidth < 768;
  const requestedDays = Number(state.visibleDaysCount) || 7;
  const visibleCount = isNarrow ? Math.min(requestedDays, requestedDays === 1 ? 1 : 3) : requestedDays;

  // Allow choosing ANY start day in the horizon (even in 7-day week mode, user can start from Tue/Wed/etc.)
  const maxStart = horizonDays - 1;
  if (state.scrubberStartDay > maxStart) state.scrubberStartDay = maxStart;
  if (state.scrubberStartDay < 0) state.scrubberStartDay = 0;

  const startDay = state.scrubberStartDay;
  const dayIndices = [];
  for (let i = 0; i < visibleCount; i++) {
    dayIndices.push(startDay + i);
  }
  const endDay = dayIndices[dayIndices.length - 1];

  const schedule = state.currentSchedule;
  const blocks = state.overloadPreview?.blocks || schedule?.blocks || [];
  const unplaced = schedule?.unplaced_tasks || [];
  const pinnedIds = new Set((state.pinnedBlocks || []).map((b) => b.block_id));

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
    return `<button type="button" class="day-chip ${inView ? "in-view" : ""} ${isToday ? "is-today" : ""} ${isPast ? "is-past" : ""}" data-jump-day="${d}" title="Bắt đầu từ ${WEEKDAYS_VI_FULL[d % 7]} ${fmtDDMM(dt)}">
      ${WEEKDAYS_VI_SHORT[d % 7]} <span class="mono">${fmtDDMM(dt)}</span>
    </button>`;
  }).join("");

  // Overload preview notice
  let previewBannerHtml = "";
  if (state.overloadPreview) {
    previewBannerHtml = `
      <div class="alert-banner info">
        <div>
          <strong>Đang xem thử phương án giải cứu (${esc(state.overloadPreview.option_id)}):</strong>
          Các khối nét đứt là lịch đề xuất. Bạn có thể áp dụng hoặc hoàn tác.
        </div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          <button type="button" class="btn btn-primary btn-sm" id="btnApplyOverloadPreview">Áp dụng phương án</button>
          <button type="button" class="btn btn-sm" id="btnCancelOverloadPreview">Hoàn tác</button>
        </div>
      </div>`;
  }

  // Unplaced strip
  let unplacedHtml = "";
  if (unplaced.length > 0) {
    const chips = unplaced
      .map(
        (u) => `<div class="unplaced-chip">
          <strong>${esc(u.title || u.task_id)}</strong>
          <span class="mono">${u.duration_min}p</span>
          <span style="color:var(--p-muted)">· ${esc(u.reason || u.reason_code || "Thiếu khe trống")}</span>
        </div>`
      )
      .join("");
    unplacedHtml = `
      <div class="card unplaced-strip">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="badge badge-danger">Chưa xếp được (${unplaced.length})</span>
            <span style="font-size:12.5px;color:var(--p-muted)">Không đủ khe trống hợp lệ trước hạn chót hoặc vi phạm phụ thuộc.</span>
          </div>
          <button type="button" class="btn btn-sm btn-primary" id="btnOpenOverloadRescue">Gợi ý giải cứu quá tải (O1–O4)</button>
        </div>
        <div class="unplaced-list">${chips}</div>
      </div>`;
  }

  const dayHeadsHtml = dayIndices
    .map((d) => {
      const dt = addDays(wsDate, d);
      const isToday = d === todayDayIdx;
      const isPast = d < todayDayIdx;
      const fixedEvs = expandFixedEventsForDay(state.commitments.fixed_events, d);
      const classMin = fixedEvs
        .filter((e) => String(e.category || "").toUpperCase() === "ACADEMIC_CLASS")
        .reduce((acc, e) => acc + e.durationMin, 0);
      const dayBlocks = blocks.filter((b) => slotToDayIndex(b.start_slot) === d);
      const studyMin = dayBlocks.reduce((acc, b) => acc + Number(b.duration_min || 0), 0);
      const totalLoad = classMin + studyMin;
      const pct = Math.min(100, Math.round((totalLoad / 540) * 100));
      const barCls = totalLoad > 600 ? "danger" : totalLoad > 540 ? "warn" : "";

      const statusBadge = isToday
        ? `<span class="badge badge-info">Hôm nay</span>`
        : isPast
          ? `<span class="cal-day-sub">Đã qua</span>`
          : "";

      return `
        <div class="cal-day-head ${isToday ? "is-today" : ""} ${isPast ? "is-past" : ""}">
          <div class="cal-day-title-row">
            <div class="cal-day-identity">
              <span class="cal-date-circle mono">${String(dt.getDate()).padStart(2, "0")}</span>
              <div class="cal-day-name">${visibleCount >= 7 ? WEEKDAYS_VI_SHORT[d % 7] : WEEKDAYS_VI_FULL[d % 7]}</div>
            </div>
            ${visibleCount < 7 ? statusBadge : ""}
          </div>
          <div class="load-meter" title="Tổng Lớp (${classMin}p) + Tự học (${studyMin}p) so với trần 540p/ngày">
            <div class="load-meter-label">
              <span>${visibleCount >= 7 ? "" : "Tải ngày"}</span>
              <span class="mono">${totalLoad} / 540p</span>
            </div>
            <div class="load-bar"><div class="load-bar-fill ${barCls}" style="width:${pct}%"></div></div>
          </div>
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
          return `<div class="cal-hour-slot ${eCls}" data-drop-day="${d}" data-drop-hour="${h}"></div>`;
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

      for (const ev of expandFixedEventsForDay(state.commitments.fixed_events, d)) {
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
        const height = Math.max(26, (e - s) * pxPerMin - 2);

        const isPastBlock = b.end_slot <= nowSlot;
        const isNowBlock = b.start_slot <= nowSlot && nowSlot < b.end_slot;
        const isPinned = pinnedIds.has(b.block_id) || b.state === "PINNED";
        const isProposed = b.state === "PROPOSED";
        const doneInfo = state.completedBlocks[b.block_id];
        const load = Number(b.cognitive_load || 2);
        const energy = b.energy_level || getEnergyForHour(state.commitments.focus_preference, Math.floor(bStartMin / 60));
        const countdown = !isPastBlock ? formatDeadlineCountdown(b.deadline_slot, nowSlot) : "Đã qua";

        const stateCls = [
          `load-${load}`,
          isPastBlock ? "state-past" : "",
          isNowBlock ? "state-now" : "",
          isPinned ? "state-pinned" : "",
          isProposed ? "state-proposed" : "",
        ]
          .filter(Boolean)
          .join(" ");

        const tagChips = [];
        if (isNowBlock) tagChips.push(`<span class="badge badge-danger" style="padding:1px 6px;font-size:9.5px;">Đang diễn ra</span>`);
        if (doneInfo) tagChips.push(`<span class="badge badge-ok" style="padding:1px 6px;font-size:9.5px;">Xong ${doneInfo.actual_min}p</span>`);
        if (isPinned) tagChips.push(`<span class="badge badge-info" style="padding:1px 6px;font-size:9.5px;">Ghim</span>`);

        // Clean default face: title + time only; technical L1-L3/Peak/countdown shown when enabled in Settings or in 1-day view tooltip
        const techBits = state.showTechMetaOnBlocks
          ? `<span>· L${load}</span>${energy === 3 ? `<span>· Peak</span>` : ""}<span>· ${esc(countdown)}</span>`
          : visibleCount === 1
            ? `<span>· ${esc(CATEGORY_LABELS[b.category] || b.category)}</span><span>· ${esc(countdown)}</span>`
            : "";

        eventsLayer.push(`
          <div class="cal-event task-block ${stateCls}"
               draggable="${!isPastBlock}"
               data-block-id="${esc(b.block_id)}"
               style="top:${top}px;height:${height}px;"
               title="${esc(b.title)} (${b.start_time}–${b.end_time}, ${b.duration_min}p · L${load} · ${energy === 3 ? "Peak E3" : `E${energy}`} · ${countdown}) — Click xem chi tiết hoặc kéo để dời giờ">
            <div class="cal-ev-top">
              <span class="cal-ev-title">${esc(b.title)}</span>
              <span style="display:inline-flex;gap:3px;align-items:center;">${tagChips.join("")}</span>
            </div>
            ${
              height >= 40
                ? `<div class="cal-ev-meta">
                    <span class="mono">${esc(b.start_time)}–${esc(b.end_time)}</span>
                    ${techBits}
                  </div>`
                : ""
            }
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
        <div class="cal-day-col ${isToday ? "is-today" : ""} ${isPast ? "is-past" : ""}" style="height:${totalVisibleMin * pxPerMin}px;">
          ${slotsHtml}
          ${eventsLayer.join("")}
          ${nowLineHtml}
        </div>`;
    })
    .join("");

  const minColPx = visibleCount === 1 ? "1fr" : visibleCount >= 7 ? "minmax(122px, 1fr)" : "minmax(150px, 1fr)";
  const gridColsCss = `60px ${visibleCount === 1 ? "1fr" : `repeat(${dayIndices.length}, ${minColPx})`}`;

  container.innerHTML = `
    ${previewBannerHtml}
    ${unplacedHtml}

    <div class="calendar-sheet">
      <div class="scrubber-bar">
        <div class="scrubber-left">
          <button type="button" class="btn btn-sm btn-icon" id="btnScrubPrev" ${startDay <= 0 ? "disabled" : ""} title="Lùi 1 ngày" aria-label="Lùi 1 ngày">
            <svg class="icon" viewBox="0 0 24 24"><path d="m15 18-6-6 6-6"/></svg>
          </button>
          <input type="range" class="scrubber-range" id="calScrubberRange" min="0" max="${maxStart}" value="${startDay}" aria-label="Thanh kéo trượt ngày" />
          <button type="button" class="btn btn-sm btn-icon" id="btnScrubNext" ${startDay >= maxStart ? "disabled" : ""} title="Tiến 1 ngày" aria-label="Tiến 1 ngày">
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
          <span class="legend-dot"><span class="legend-swatch" style="background:#d46256"></span>Tập trung sâu</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#d4952a"></span>Trung bình</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#359464"></span>Nhẹ</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#3b7ddd"></span>Lớp cố định</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#3a8d8d"></span>Bữa ăn</span>
          <span class="legend-dot"><span class="legend-swatch" style="background:#9aa4b4"></span>Đã qua</span>
        </div>
        <span>Kéo thả khối để dời & ghim giờ · Click vào khối để xem chi tiết</span>
      </div>
    </div>
  `;

  // Wire scrubber events
  container.querySelector("#btnScrubPrev")?.addEventListener("click", () => {
    state.scrubberStartDay = Math.max(0, state.scrubberStartDay - 1);
    renderCalendarView(container, callbacks);
    callbacks.onSyncRangeLabel?.();
  });
  container.querySelector("#btnScrubNext")?.addEventListener("click", () => {
    state.scrubberStartDay = Math.min(maxStart, state.scrubberStartDay + 1);
    renderCalendarView(container, callbacks);
    callbacks.onSyncRangeLabel?.();
  });
  container.querySelector("#calScrubberRange")?.addEventListener("input", (e) => {
    state.scrubberStartDay = Number(e.target.value);
    renderCalendarView(container, callbacks);
    callbacks.onSyncRangeLabel?.();
  });
  container.querySelector("#btnJumpToday")?.addEventListener("click", () => {
    state.scrubberStartDay = Math.min(maxStart, todayDayIdx);
    renderCalendarView(container, callbacks);
    callbacks.onSyncRangeLabel?.();
  });

  container.querySelectorAll("[data-jump-day]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = Number(btn.getAttribute("data-jump-day"));
      state.scrubberStartDay = Math.min(maxStart, Math.max(0, target));
      renderCalendarView(container, callbacks);
      callbacks.onSyncRangeLabel?.();
    });
  });

  container.querySelector("#btnOpenOverloadRescue")?.addEventListener("click", () => callbacks.onOpenOverloadRescue());
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
