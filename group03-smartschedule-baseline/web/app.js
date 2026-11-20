/**
 * SmartSchedule Baseline (V0) — Technical Benchmark Workbench Frontend Controller
 * Matches every DOM element in `web/index.html` and REST endpoint in `web/api.py`.
 */

const DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const DAYS_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"];

// Feature 001 — Estimate buffer. Mirrors src/estimate_buffer.py (spec 001 FR2/FR3).
const ESTIMATE_HABIT_MULTIPLIER = { RARELY: 1.0, SOMETIMES: 1.1, OFTEN: 1.25 };

function currentBufferMultiplier() {
  const habit = (state.commitments && state.commitments.estimate_habit) || "";
  return ESTIMATE_HABIT_MULTIPLIER[habit] || 1.0;
}

function plannedMinutesFor(estimateMin, multiplier) {
  const est = Math.max(0, parseInt(estimateMin || 0, 10));
  if (est <= 0) return 0;
  const floorMin = Math.ceil(est / 15) * 15;
  const pct = Math.round(multiplier * 100);
  if (pct <= 100) return floorMin;
  const nearestSlots = Math.floor((est * pct + 750) / 1500);
  return Math.max(floorMin, nearestSlots * 15);
}

const state = {
  commitments: {
    student_id: "MINH_YEAR2_CS",
    planning_week_start: "2026-11-02T00:00:00+07:00",
    horizon_days: 7,
    buffer_mode: "COGNITIVE_LOAD",
    alpha_light: 1.2,
    alpha_heavy: 1.35,
    sleep_schedule: {
      daily_start_time: "23:30",
      daily_end_time: "06:30",
      is_hard_lock: true,
    },
    fixed_events: [],
    personal_habits: [],
  },
  tasks: [],
  currentSchedule: null,
  repairedMovedIds: new Set(),
  editingTaskId: null,
  activeScenario: null,
  workbenchMode: "SINGLE", // 'SINGLE' | 'COMPARE'
  appMode: "STUDENT", // 'STUDENT' (Clean) | 'LAB' (Benchmark)
  studentView: "WEEK", // 'WEEK' | 'TODAY' | 'TASKS'
  todayDay: "Monday",
  viewWeekOffset: 0, // 0 = Week 1 (days 0..6), 1 = Week 2 (days 7..13)
  useRealTimeNow: false,
  pinnedBlocks: new Map(), // block_id -> ScheduleBlock
  doneBlocks: new Set(), // block_id
  taskBufferMap: new Map(), // task_id -> { raw_min, buffered_min }
  actualDurations: new Map(), // block_id -> actual_min
  previewState: null, // { option_id, option_code, target_task_id, resolved_tasks, before_schedule }
  undoSnapshot: null, // { commitments, tasks, schedule, pinnedBlocks }
  nlEngineMode: "auto", // 'auto' | 'offline'
  nlSuggestedFixedEvent: null, // Suggested FixedEvent payload from M1 parser
  nlTransBackend: "rule", // 'rule' | 'nllb'
  nlSession: "splittable", // 'splittable' | 'single'
  nlPacing: "BALANCED", // 'LIGHT' | 'BALANCED' | 'FLOW' | 'CUSTOM'
  nlUrgency: null, // null | 1 | 2 | 3 | 4 (1=Urgent..4=Low)
  nlAttachments: [], // [{ name, size_mb }]
  nlMinChunk: 30,
  nlMaxChunk: 60,
  stModalDraft: null,
  lastAnalyzedHybrid: null,
  lastAnalyzedTranslation: null,
  lastComparison: null,
  studentTasksSubtab: "TASKS",
  observedRange: { startIdx: 0, endIdx: 6 },
  miniCalendarMonth: null,
};

const WORKSPACE_STORAGE_KEY = "smartschedule_workspace_v2";
let _serverStateSaveTimer = null;

function getCurrentMondayIso() {
  const now = new Date();
  const day = now.getDay();
  const diffToMon = day === 0 ? -6 : 1 - day;
  const mon = new Date(now.getFullYear(), now.getMonth(), now.getDate() + diffToMon);
  const pad = (n) => String(n).padStart(2, "0");
  return `${mon.getFullYear()}-${pad(mon.getMonth() + 1)}-${pad(mon.getDate())}T00:00:00+07:00`;
}

function getCurrentLocalIso() {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:00+07:00`;
}

function _storageKey() {
  const sid = state.commitments?.student_id || "DEFAULT";
  return `smartschedule_state_${sid}_v1`;
}

function savePersistedStudentState() {
  try {
    const algorithm = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";
    localStorage.setItem(
      _storageKey(),
      JSON.stringify({
        doneBlocks: Array.from(state.doneBlocks),
        actualDurations: Array.from(state.actualDurations.entries()),
        pinnedBlocks: Array.from(state.pinnedBlocks.entries()),
        focus_preference: state.commitments?.focus_preference || "BALANCED",
        buffer_mode: state.commitments?.buffer_mode || "COGNITIVE_LOAD",
        alpha_light: state.commitments?.alpha_light ?? 1.2,
        alpha_heavy: state.commitments?.alpha_heavy ?? 1.35,
      })
    );
    if (state.activeScenario) return;
    const workspacePayload = {
      version: 2,
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm,
      pinned_blocks: Array.from(state.pinnedBlocks.entries()),
      done_blocks: Array.from(state.doneBlocks),
      actual_durations: Array.from(state.actualDurations.entries()),
      viewWeekOffset: state.viewWeekOffset || 0,
      useRealTimeNow: Boolean(state.useRealTimeNow),
    };
    localStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(workspacePayload));
    clearTimeout(_serverStateSaveTimer);
    _serverStateSaveTimer = setTimeout(() => {
      fetch("/api/state", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_id: "default", state: workspacePayload }),
      }).catch(() => {});
    }, 150);
  } catch (_) {}
}

function loadPersistedStudentState() {
  try {
    const raw = localStorage.getItem(_storageKey());
    if (!raw) return;
    const saved = JSON.parse(raw);
    if (Array.isArray(saved.doneBlocks)) state.doneBlocks = new Set(saved.doneBlocks);
    if (Array.isArray(saved.actualDurations)) state.actualDurations = new Map(saved.actualDurations);
    if (Array.isArray(saved.pinnedBlocks)) state.pinnedBlocks = new Map(saved.pinnedBlocks);
  } catch (_) {}
}

async function restorePersistedWorkspace() {
  let saved = null;
  try {
    const res = await fetch("/api/state?workspace_id=default");
    if (res.ok) {
      const d = await res.json();
      if (d && d.exists && d.state && typeof d.state === "object") {
        saved = d.state;
      }
    }
  } catch (_) {}

  if (!saved) {
    try {
      const raw = localStorage.getItem(WORKSPACE_STORAGE_KEY);
      if (raw) saved = JSON.parse(raw);
    } catch (_) {}
  }

  if (!saved || !saved.commitments) return false;
  state.commitments = {
    horizon_days: 7,
    personal_habits: [],
    ...saved.commitments,
  };
  state.tasks = Array.isArray(saved.tasks) ? saved.tasks : [];
  state.activeScenario = null;
  state.pinnedBlocks = new Map(Array.isArray(saved.pinned_blocks) ? saved.pinned_blocks : []);
  state.doneBlocks = new Set(Array.isArray(saved.done_blocks) ? saved.done_blocks : []);
  state.actualDurations = new Map(Array.isArray(saved.actual_durations) ? saved.actual_durations : []);
  state.viewWeekOffset = Number(saved.viewWeekOffset || 0) === 1 && (state.commitments.horizon_days || 7) >= 14 ? 1 : 0;
  state.useRealTimeNow = Boolean(saved.useRealTimeNow);
  if (state.useRealTimeNow) {
    state.commitments.now = getCurrentLocalIso();
  }
  const solverEl = document.getElementById("solverSelect");
  if (solverEl && saved.algorithm) solverEl.value = saved.algorithm;
  syncAllLeftPanels();
  await solveSchedule();
  return true;
}

// ============================================================================
// TEMPORAL ENGINE (DD/MM/YYYY, PAST / TODAY+NOW / FUTURE, DEMO VS REALTIME)
// ============================================================================

function pad2(n) {
  return String(n).padStart(2, "0");
}

function slotOffsetToTime(slotOffset) {
  const totalMin = slotOffset * 15;
  const hh = Math.floor(totalMin / 60);
  const mm = totalMin % 60;
  return `${pad2(hh)}:${pad2(mm)}`;
}

function parseIsoDateLocal(isoStr, fallbackIso = "2026-11-02T00:00:00") {
  const raw = String(isoStr || "").trim();
  const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2}))?/);
  if (m) {
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4] || 0), Number(m[5] || 0), 0, 0);
  }
  const fm = fallbackIso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (fm) return new Date(Number(fm[1]), Number(fm[2]) - 1, Number(fm[3]), 0, 0, 0, 0);
  return new Date();
}

function formatDateDDMMYYYY(d) {
  return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}`;
}

function formatDateShort(d) {
  return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}`;
}

function formatTimeHHMM(d) {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

function getYmdNumber(d) {
  return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
}

function getWeekBaseDate() {
  return parseIsoDateLocal(state.commitments?.planning_week_start || getCurrentMondayIso(), "2026-11-02T00:00:00");
}

function getDayDate(globalDayIdx) {
  const base = getWeekBaseDate();
  return new Date(base.getFullYear(), base.getMonth(), base.getDate() + globalDayIdx, 0, 0, 0, 0);
}

function getActiveNowDate() {
  if (state.useRealTimeNow) return new Date();
  if (state.commitments?.now) return parseIsoDateLocal(state.commitments.now);
  const realToday = new Date();
  const baseYmd = getYmdNumber(getWeekBaseDate());
  const curMon = parseIsoDateLocal(getCurrentMondayIso());
  if (baseYmd === getYmdNumber(curMon)) return realToday;
  return getWeekBaseDate();
}

function getDayTemporalState(dayDate, nowRef = getActiveNowDate()) {
  const ymd = getYmdNumber(dayDate);
  const nowYmd = getYmdNumber(nowRef);
  if (ymd < nowYmd) return "PAST";
  if (ymd === nowYmd) return "TODAY";
  return "FUTURE";
}

function parseHHMMToDate(dayDate, timeStr) {
  const [hh, mm] = String(timeStr || "00:00").split(":").map(Number);
  if (hh === 24 && (!mm || mm === 0)) {
    return new Date(dayDate.getFullYear(), dayDate.getMonth(), dayDate.getDate() + 1, 0, 0, 0, 0);
  }
  return new Date(dayDate.getFullYear(), dayDate.getMonth(), dayDate.getDate(), hh || 0, mm || 0, 0, 0);
}

function getBlockTemporalState(dayDate, startTime, endTime, nowRef = getActiveNowDate()) {
  const sDt = parseHHMMToDate(dayDate, startTime);
  const eDt = parseHHMMToDate(dayDate, endTime);
  const nowMs = nowRef.getTime();
  if (nowMs >= sDt.getTime() && nowMs < eDt.getTime()) {
    return { status: "ACTIVE", label: "ĐANG DIỄN RA", deltaMin: Math.round((eDt.getTime() - nowMs) / 60000) };
  }
  if (eDt.getTime() <= nowMs) {
    return { status: "PAST", label: "Đã qua", deltaMin: Math.round((nowMs - eDt.getTime()) / 60000) };
  }
  return { status: "FUTURE", label: "Sắp tới", deltaMin: Math.round((sDt.getTime() - nowMs) / 60000) };
}

function formatCountdownMin(mins) {
  const m = Math.max(0, Math.round(mins));
  if (m >= 1440) {
    const d = Math.floor(m / 1440);
    const h = Math.floor((m % 1440) / 60);
    return h > 0 ? `${d}d ${h}h` : `${d} ngày`;
  }
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const rem = m % 60;
    return rem > 0 ? `${h}h ${rem}p` : `${h}h`;
  }
  return `${m}p`;
}

function resolveDeadlineDisplay(item, nowRef = getActiveNowDate()) {
  let targetDate = null;
  if (item.due) {
    targetDate = parseIsoDateLocal(item.due);
  } else if (item.deadline_day) {
    const rawDay = String(item.deadline_day).trim();
    const isNext = rawDay.toLowerCase().startsWith("next ");
    const cleanDay = isNext ? rawDay.slice(5).trim() : rawDay;
    const foundIdx = DAYS_EN.findIndex((en) => en.toLowerCase().startsWith(cleanDay.toLowerCase().slice(0, 3)));
    if (foundIdx >= 0) {
      const dayIdx = foundIdx + (isNext ? 7 : 0);
      targetDate = parseHHMMToDate(getDayDate(dayIdx), item.deadline_time || "23:59");
    }
  } else if (typeof item.deadline_slot === "number" && item.deadline_slot >= 0) {
    const base = getWeekBaseDate();
    targetDate = new Date(base.getTime() + item.deadline_slot * 15 * 60000);
  } else if (item.deadline_str && item.deadline_str !== "No deadline (Flexible / Habit)") {
    const parts = String(item.deadline_str).split(" ");
    const tStr = parts[parts.length - 1];
    const dName = parts.slice(0, -1).join(" ");
    const isNext = dName.toLowerCase().startsWith("next ");
    const cleanDay = isNext ? dName.slice(5).trim() : dName;
    const foundIdx = DAYS_EN.findIndex((en) => en.toLowerCase().startsWith(cleanDay.toLowerCase().slice(0, 3)));
    if (foundIdx >= 0) {
      targetDate = parseHHMMToDate(getDayDate(foundIdx + (isNext ? 7 : 0)), tStr);
    }
  }

  if (!targetDate || Number.isNaN(targetDate.getTime())) {
    return { dateObj: null, dateText: "Linh hoạt (Habit)", isOverdue: false, badgeHtml: `<span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px]">Habit</span>` };
  }

  const jsDay = targetDate.getDay();
  const viShort = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"][jsDay];
  const hhmm = formatTimeHHMM(targetDate);
  const displayTime = (item.deadline_time === "23:59" || (hhmm === "00:00" && String(item.deadline_time) === "23:59")) ? "23:59" : hhmm;
  const dateText = `${viShort} · ${formatDateDDMMYYYY(targetDate)} ${displayTime}`;
  const diffMin = Math.round((targetDate.getTime() - nowRef.getTime()) / 60000);

  if (diffMin < 0) {
    return {
      dateObj: targetDate,
      dateText,
      isOverdue: true,
      badgeHtml: `<span class="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 font-bold text-[10px]">Quá hạn ${formatCountdownMin(-diffMin)}</span>`,
    };
  }
  if (diffMin <= 24 * 60) {
    return {
      dateObj: targetDate,
      dateText,
      isOverdue: false,
      badgeHtml: `<span class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-bold text-[10px]">Còn ${formatCountdownMin(diffMin)}</span>`,
    };
  }
  return {
    dateObj: targetDate,
    dateText,
    isOverdue: false,
    badgeHtml: `<span class="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-semibold text-[10px]">Còn ${formatCountdownMin(diffMin)}</span>`,
  };
}

function updateTemporalContextUI() {
  const realNow = new Date();
  const realMondayDate = parseIsoDateLocal(getCurrentMondayIso());
  const viDaysFull = ["Chủ Nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
  const clockEl = document.getElementById("topClockLiveLabel");
  if (clockEl) {
    clockEl.textContent = `Đồng hồ thực: ${viDaysFull[realNow.getDay()]}, ${formatDateDDMMYYYY(realNow)} ${formatTimeHHMM(realNow)}`;
  }

  const weekOff = state.viewWeekOffset || 0;
  const viewStart = getDayDate(weekOff * 7);
  const viewEnd = getDayDate(weekOff * 7 + 6);
  const rangeStr = `${formatDateDDMMYYYY(viewStart)} – ${formatDateDDMMYYYY(viewEnd)}`;
  const pillEl = document.getElementById("topWeekRangePill");
  if (pillEl) {
    const span = pillEl.querySelector("span") || pillEl;
    span.textContent = rangeStr;
  }
  const labPillEl = document.getElementById("labObservedRangePill");
  if (labPillEl) {
    labPillEl.textContent = `Chuỗi xem: ${rangeStr}`;
  }

  const base = getWeekBaseDate();
  const dateInp = document.getElementById("inpWeekStartDate");
  if (dateInp) {
    dateInp.value = `${base.getFullYear()}-${pad2(base.getMonth() + 1)}-${pad2(base.getDate())}`;
  }

  const banner = document.getElementById("temporalContextBanner");
  const bannerTxt = document.getElementById("temporalContextText");
  if (banner && bannerTxt) {
    const isHistoricalOrSim = getYmdNumber(base) !== getYmdNumber(realMondayDate) || !state.useRealTimeNow;
    if (isHistoricalOrSim) {
      const activeNow = getActiveNowDate();
      banner.classList.remove("hidden");
      bannerTxt.innerHTML = state.activeScenario
        ? `<span>🧪 <strong>Đang chạy kịch bản Benchmark ${_escHtml(state.activeScenario.scenario_id || "")}:</strong> Tuần cố định <span class="mono">${formatDateDDMMYYYY(getDayDate(0))} – ${formatDateDDMMYYYY(getDayDate(6))}</span> (Mốc giả lập: <span class="mono">${formatDateDDMMYYYY(activeNow)} ${formatTimeHHMM(activeNow)}</span>).</span>`
        : `<span>📌 <strong>Đang xem lịch tuần khác với tuần thực tế:</strong> <span class="mono">${formatDateDDMMYYYY(getDayDate(0))} – ${formatDateDDMMYYYY(getDayDate(6))}</span> (Hôm nay là <span class="mono">${formatDateDDMMYYYY(realNow)}</span>).</span>`;
    } else {
      banner.classList.add("hidden");
    }
  }

  const pop = document.getElementById("observedRangeCalendarPopover");
  if (pop && !pop.classList.contains("hidden")) {
    renderObservedRangeCalendar();
  }
}

function toggleStudentToolsMenu() {
  document.getElementById("studentToolsMenu")?.classList.toggle("hidden");
}

function closeStudentToolsMenu() {
  document.getElementById("studentToolsMenu")?.classList.add("hidden");
}

// ============================================================================
// MONTH RANGE CALENDAR POPOVER & HORIZONTAL TIMELINE SCRUBBER
// ============================================================================

function toggleObservedRangeCalendar(forceOpen = null) {
  const pop = document.getElementById("observedRangeCalendarPopover");
  if (!pop) return;
  const shouldOpen = forceOpen === null ? pop.classList.contains("hidden") : Boolean(forceOpen);
  if (shouldOpen) {
    const visStart = state.appMode === "STUDENT" && state.studentView === "WEEK"
      ? (state.observedRange?.startIdx ?? 0)
      : (state.viewWeekOffset || 0) * 7;
    const anchor = getDayDate(visStart);
    state.miniCalendarMonth = { year: anchor.getFullYear(), month: anchor.getMonth() };
    pop.classList.remove("hidden");
    renderObservedRangeCalendar();
  } else {
    pop.classList.add("hidden");
  }
}

function closeObservedRangeCalendar() {
  document.getElementById("observedRangeCalendarPopover")?.classList.add("hidden");
}

function shiftMiniCalendarMonth(delta) {
  if (!state.miniCalendarMonth) {
    const base = getWeekBaseDate();
    state.miniCalendarMonth = { year: base.getFullYear(), month: base.getMonth() };
  }
  const dt = new Date(state.miniCalendarMonth.year, state.miniCalendarMonth.month + delta, 1);
  state.miniCalendarMonth = { year: dt.getFullYear(), month: dt.getMonth() };
  renderObservedRangeCalendar();
}

function renderObservedRangeCalendar() {
  const grid = document.getElementById("calPopoverGrid");
  const titleEl = document.getElementById("calPopoverMonthTitle");
  const rangeEl = document.getElementById("calPopoverRangeText");
  const horizonEl = document.getElementById("calPopoverHorizonText");
  if (!grid) return;

  const base = getWeekBaseDate();
  if (!state.miniCalendarMonth) {
    state.miniCalendarMonth = { year: base.getFullYear(), month: base.getMonth() };
  }
  const { year, month } = state.miniCalendarMonth;
  if (titleEl) titleEl.textContent = `Tháng ${pad2(month + 1)} / ${year}`;

  const horizonDays = Number(state.commitments?.horizon_days || 7) >= 14 ? 14 : 7;
  const isContinuousWeek = state.appMode === "STUDENT" && state.studentView === "WEEK";
  const visStartIdx = isContinuousWeek ? Math.max(0, state.observedRange?.startIdx ?? 0) : (state.viewWeekOffset || 0) * 7;
  const visEndIdx = isContinuousWeek
    ? Math.min(horizonDays - 1, Math.max(visStartIdx, state.observedRange?.endIdx ?? Math.min(6, horizonDays - 1)))
    : Math.min(horizonDays - 1, visStartIdx + 6);

  const visStartDt = getDayDate(visStartIdx);
  const visEndDt = getDayDate(visEndIdx);
  if (rangeEl) {
    rangeEl.textContent = `${formatDateDDMMYYYY(visStartDt)} → ${formatDateDDMMYYYY(visEndDt)} (${visEndIdx - visStartIdx + 1} ngày)`;
  }
  if (horizonEl) {
    horizonEl.textContent = `Cửa sổ lập lịch: ${formatDateDDMMYYYY(getDayDate(0))} – ${formatDateDDMMYYYY(getDayDate(horizonDays - 1))} (${horizonDays} ngày)`;
  }

  const firstOfMonth = new Date(year, month, 1);
  const startJsDay = firstOfMonth.getDay(); // 0=Sun..6=Sat
  const padMon = startJsDay === 0 ? 6 : startJsDay - 1;
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const totalCells = Math.ceil((padMon + daysInMonth) / 7) * 7;

  const realNow = new Date();
  const realTodayYmd = getYmdNumber(realNow);
  const weekBaseMs = new Date(base.getFullYear(), base.getMonth(), base.getDate()).getTime();
  const visStartYmd = getYmdNumber(visStartDt);
  const visEndYmd = getYmdNumber(visEndDt);

  let html = "";
  for (let c = 0; c < totalCells; c++) {
    const cellDate = new Date(year, month, 1 - padMon + c);
    const inCurrentMonth = cellDate.getMonth() === month;
    const cellYmd = getYmdNumber(cellDate);
    const isoStr = `${cellDate.getFullYear()}-${pad2(cellDate.getMonth() + 1)}-${pad2(cellDate.getDate())}`;
    const dayIdx = Math.round((cellDate.getTime() - weekBaseMs) / 86400000);
    const inHorizon = dayIdx >= 0 && dayIdx < horizonDays;
    const inVisible = cellYmd >= visStartYmd && cellYmd <= visEndYmd;
    const isRealToday = cellYmd === realTodayYmd;

    let cls = "py-1.5 text-[11px] mono cursor-pointer transition relative select-none ";
    if (inVisible) {
      cls += "bg-indigo-600 text-white font-bold shadow-sm hover:bg-indigo-500 ";
      if (cellYmd === visStartYmd) cls += "rounded-l-lg ";
      if (cellYmd === visEndYmd) cls += "rounded-r-lg ";
    } else if (inHorizon) {
      cls += "bg-indigo-100 text-indigo-900 font-semibold hover:bg-indigo-200 ";
      if (dayIdx === 0) cls += "rounded-l-lg ";
      if (dayIdx === horizonDays - 1) cls += "rounded-r-lg ";
    } else {
      cls += inCurrentMonth
        ? "text-slate-700 hover:bg-slate-100 rounded-lg font-medium "
        : "text-slate-300 hover:bg-slate-50 rounded-lg ";
    }

    const todayRing = isRealToday ? "ring-2 ring-rose-500 ring-inset" : "";
    const todayDot = isRealToday
      ? `<span class="w-1 h-1 rounded-full ${inVisible ? "bg-rose-300" : "bg-rose-500"} mx-auto block mt-0.5"></span>`
      : "";

    html += `
      <button type="button" onclick="onMiniCalendarDateClick('${isoStr}', ${inHorizon ? dayIdx : -1})" class="${cls} ${todayRing}" title="${formatDateDDMMYYYY(cellDate)}${inVisible ? " (Đang xem)" : inHorizon ? " (Bấm để cuộn tới)" : " (Bấm để nhảy tới tuần này)"}">
        <span>${cellDate.getDate()}</span>${todayDot}
      </button>`;
  }
  grid.innerHTML = html;
}

async function onMiniCalendarDateClick(isoStr, horizonDayIdx) {
  if (horizonDayIdx >= 0) {
    if (state.appMode === "STUDENT") {
      if (state.studentView !== "WEEK") {
        switchStudentView("WEEK");
      }
      scrollToCalendarDay(horizonDayIdx);
    } else {
      const targetWeekOff = horizonDayIdx >= 7 ? 1 : 0;
      if ((state.viewWeekOffset || 0) !== targetWeekOff) {
        state.viewWeekOffset = targetWeekOff;
        savePersistedStudentState();
        updateTemporalContextUI();
        renderStudentViews();
        renderMainGrid();
      }
    }
    renderObservedRangeCalendar();
    return;
  }
  closeObservedRangeCalendar();
  await setPlanningWeekFromDate(isoStr);
}

function _applySliderToScroll(containerId, sliderVal) {
  const sc = document.getElementById(containerId);
  if (!sc) return;
  const maxScroll = Math.max(0, sc.scrollWidth - sc.clientWidth);
  sc.style.scrollBehavior = "auto";
  sc.scrollLeft = (Number(sliderVal) / 1000) * maxScroll;
}

function _restoreSmoothScroll(containerId) {
  const sc = document.getElementById(containerId);
  if (sc) sc.style.scrollBehavior = "";
}

function _syncRangeSliderFromScroll(containerId, sliderId) {
  const sc = document.getElementById(containerId);
  const sl = document.getElementById(sliderId);
  if (!sc || !sl) return;
  const maxScroll = Math.max(0, sc.scrollWidth - sc.clientWidth);
  if (maxScroll <= 2) {
    sl.value = "0";
    sl.disabled = true;
    sl.classList.add("opacity-40");
  } else {
    sl.disabled = false;
    sl.classList.remove("opacity-40");
    sl.value = String(Math.round((sc.scrollLeft / maxScroll) * 1000));
  }
}

function onStHorizontalSliderInput(val) {
  _applySliderToScroll("stCalendarScrollContainer", val);
  updateObservedViewportRange();
}

function restoreCalendarSmoothScroll() {
  _restoreSmoothScroll("stCalendarScrollContainer");
}

function onLabHorizontalSliderInput(val) {
  _applySliderToScroll("labGridScrollContainer", val);
}

function restoreLabSmoothScroll() {
  _restoreSmoothScroll("labGridScrollContainer");
}

function syncLabSliderFromScroll() {
  _syncRangeSliderFromScroll("labGridScrollContainer", "labGridHorizontalSlider");
}

function syncSliderFromCalendarScroll() {
  _syncRangeSliderFromScroll("stCalendarScrollContainer", "stCalendarHorizontalSlider");
  updateObservedViewportRange();
}

function scrollToCalendarDay(globalDayIdx) {
  const sc = document.getElementById("stCalendarScrollContainer");
  const col = document.getElementById(`stDayColWrapper_${globalDayIdx}`);
  if (!sc || !col) return;
  sc.style.scrollBehavior = "";
  const targetLeft = Math.max(0, col.offsetLeft - sc.offsetLeft - 8);
  sc.scrollTo({ left: targetLeft, behavior: "smooth" });
}

function panCalendarByDays(deltaDays) {
  const totalDays = Number(state.commitments?.horizon_days || 7) >= 14 ? 14 : 7;
  const curStart = state.observedRange?.startIdx ?? 0;
  const nextIdx = Math.max(0, Math.min(totalDays - 1, curStart + deltaDays));
  scrollToCalendarDay(nextIdx);
}

function scrollToTodayColumn() {
  const totalDays = Number(state.commitments?.horizon_days || 7) >= 14 ? 14 : 7;
  const activeNow = getActiveNowDate();
  for (let i = 0; i < totalDays; i++) {
    if (getDayTemporalState(getDayDate(i), activeNow) === "TODAY") {
      scrollToCalendarDay(i);
      return;
    }
  }
  scrollToCalendarDay(0);
}

function updateObservedViewportRange() {
  const sc = document.getElementById("stCalendarScrollContainer");
  const rangeEl = document.getElementById("stObservedRangeLabel");
  const countEl = document.getElementById("stObservedWindowCount");
  const stripEl = document.getElementById("stObservedDaysStrip");
  if (!sc) return;

  _syncRangeSliderFromScroll("stCalendarScrollContainer", "stCalendarHorizontalSlider");

  const totalDays = Number(state.commitments?.horizon_days || 7) >= 14 ? 14 : 7;
  const viewLeft = sc.scrollLeft;
  const viewRight = viewLeft + sc.clientWidth;

  let visStart = -1;
  let visEnd = -1;
  if (sc.clientWidth > 0) {
    for (let i = 0; i < totalDays; i++) {
      const col = document.getElementById(`stDayColWrapper_${i}`);
      if (!col) continue;
      const colLeft = col.offsetLeft - sc.offsetLeft;
      const colRight = colLeft + col.offsetWidth;
      // Consider a day "observed" when at least 60px (or half) is visible inside viewport
      const overlap = Math.min(viewRight, colRight) - Math.max(viewLeft, colLeft);
      if (overlap >= Math.min(70, col.offsetWidth * 0.35)) {
        if (visStart === -1) visStart = i;
        visEnd = i;
      }
    }
  }
  if (visStart === -1) {
    visStart = 0;
    visEnd = Math.min(6, totalDays - 1);
  }
  state.observedRange = { startIdx: visStart, endIdx: visEnd };

  const sDate = getDayDate(visStart);
  const eDate = getDayDate(visEnd);
  const shortVi = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
  if (rangeEl) {
    rangeEl.textContent = `${shortVi[visStart % 7]} ${formatDateDDMMYYYY(sDate)} → ${shortVi[visEnd % 7]} ${formatDateDDMMYYYY(eDate)}`;
  }
  if (countEl) {
    countEl.textContent = `${visEnd - visStart + 1}/${totalDays} ngày đang hiện`;
  }

  if (stripEl) {
    const activeNow = getActiveNowDate();
    let stripHtml = "";
    for (let i = 0; i < totalDays; i++) {
      const dObj = getDayDate(i);
      const tState = getDayTemporalState(dObj, activeNow);
      const isVis = i >= visStart && i <= visEnd;
      const dot = tState === "TODAY" ? `<span class="inline-block w-1.5 h-1.5 rounded-full ${isVis ? "bg-rose-300" : "bg-rose-500"} mr-1"></span>` : "";
      const pillCls = isVis
        ? "bg-indigo-600 text-white border-indigo-700 font-bold shadow-sm"
        : tState === "TODAY"
          ? "bg-indigo-50 text-indigo-800 border-indigo-300 font-semibold hover:bg-indigo-100"
          : tState === "PAST"
            ? "bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200"
            : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100";

      stripHtml += `
        <button type="button" onclick="scrollToCalendarDay(${i})" class="px-2 py-1 rounded-lg border text-[11px] mono transition ${pillCls}" title="Bấm để cuộn tới ${DAYS_VI[i % 7]} (${formatDateDDMMYYYY(dObj)})">
          ${dot}${shortVi[i % 7]} ${formatDateShort(dObj)}
        </button>`;
    }
    stripEl.innerHTML = stripHtml;
  }

  const pop = document.getElementById("observedRangeCalendarPopover");
  if (pop && !pop.classList.contains("hidden")) {
    renderObservedRangeCalendar();
  }
}

// ============================================================================
// INITIALIZATION & PRESET / SCENARIO LOADERS
// ============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  await loadScenariosDropdown();
  const restored = await restorePersistedWorkspace();
  if (!restored) {
    await loadPresetIntoCurrentWeek("minh");
  }
  const realJsDay = new Date().getDay();
  const realMonIdx = realJsDay === 0 ? 6 : realJsDay - 1;
  if (state.useRealTimeNow) {
    state.todayDay = DAYS_EN[realMonIdx];
  }
  switchAppMode("STUDENT");
  updateTemporalContextUI();
  requestAnimationFrame(() => {
    updateObservedViewportRange();
    syncLabSliderFromScroll();
  });

  window.addEventListener("resize", () => {
    updateObservedViewportRange();
    syncLabSliderFromScroll();
  });

  setInterval(() => {
    if (state.useRealTimeNow && state.commitments) {
      state.commitments.now = getCurrentLocalIso();
    }
    updateTemporalContextUI();
    if (state.currentSchedule) {
      if (state.appMode === "STUDENT") renderStudentViews();
      else renderMainGrid();
    }
  }, 60000);

  document.addEventListener("click", (e) => {
    const menu = document.getElementById("studentToolsMenu");
    const btn = document.getElementById("btnStudentToolsMenu");
    if (menu && !menu.classList.contains("hidden") && !menu.contains(e.target) && !btn?.contains(e.target)) {
      closeStudentToolsMenu();
    }
    const calPop = document.getElementById("observedRangeCalendarPopover");
    if (
      calPop &&
      !calPop.classList.contains("hidden") &&
      !e.target.closest("#observedRangeCalendarPopover, #topWeekRangePill, #btnToggleObservedCalendar, #labObservedRangePill, #btnStOpenMonthCal")
    ) {
      closeObservedRangeCalendar();
    }
  });

  const modal = document.getElementById("stTaskModal");
  if (modal) {
    modal.addEventListener("input", () => saveStudentModalDraft());
    modal.addEventListener("change", () => saveStudentModalDraft());
  }
  // Prevent Chrome, Edge, Firefox & Safari from opening dragged files in a new tab anywhere on window/document;
  // route drops inside open #stTaskModal cleanly into the NL Link Box.
  const clearDropHighlights = () => {
    const promptBox = document.getElementById("stNlPromptBox");
    const linkBox = document.getElementById("stNlFileLinkBox");
    if (promptBox) promptBox.classList.remove("border-indigo-500", "bg-indigo-50/30");
    if (linkBox) linkBox.classList.remove("border-indigo-500", "bg-indigo-50/40");
  };
  ["dragenter", "dragover"].forEach((evtName) => {
    window.addEventListener(evtName, (e) => {
      e.preventDefault();
      if (e.dataTransfer) {
        const stModal = document.getElementById("stTaskModal");
        try {
          e.dataTransfer.dropEffect = (stModal && !stModal.classList.contains("hidden")) ? "copy" : "none";
        } catch (_) {}
      }
    }, false);
    document.addEventListener(evtName, (e) => {
      e.preventDefault();
    }, false);
  });
  window.addEventListener("dragend", clearDropHighlights, false);
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    clearDropHighlights();
    const stModal = document.getElementById("stTaskModal");
    if (stModal && !stModal.classList.contains("hidden")) {
      handleStNlFileDrop(e, "linkbox");
    }
  }, false);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeStudentToolsMenu();
      closeObservedRangeCalendar();
      const stModal = document.getElementById("stTaskModal");
      if (stModal && !stModal.classList.contains("hidden")) {
        closeStudentTaskModal();
      }
    }
  });
});

async function loadScenariosDropdown() {
  try {
    const res = await fetch("/api/scenarios");
    if (!res.ok) return;
    const data = await res.json();
    const sel = document.getElementById("scenarioSelect");
    if (!sel) return;
    sel.innerHTML = `<option value="">-- Chọn Kịch Bản T01 - T10 --</option>`;
    for (const sc of data.scenarios || []) {
      const opt = document.createElement("option");
      opt.value = sc.scenario_id;
      opt.textContent = `${sc.scenario_id}: ${sc.name} (${sc.task_count} tasks)`;
      sel.appendChild(opt);
    }
  } catch (err) {
    console.error("Error loading scenarios:", err);
  }
}

async function loadPresetIntoCurrentWeek(presetId = "minh") {
  await loadPreset(presetId, { rebaseToCurrentWeek: true });
}

async function rebaseScheduleToCurrentWeek() {
  if (!state.commitments) return;
  state.activeScenario = null;
  const sel = document.getElementById("scenarioSelect");
  if (sel) sel.value = "";
  document.getElementById("scenarioBanner")?.classList.add("hidden");

  state.commitments.planning_week_start = getCurrentMondayIso();
  state.commitments.now = getCurrentLocalIso();
  state.useRealTimeNow = true;
  state.viewWeekOffset = 0;

  for (const t of state.tasks || []) {
    if (t.due && t.deadline_day) delete t.due;
  }
  const realJsDay = new Date().getDay();
  state.todayDay = DAYS_EN[realJsDay === 0 ? 6 : realJsDay - 1];

  syncAllLeftPanels();
  updateTemporalContextUI();
  await solveSchedule();
  savePersistedStudentState();
}

async function setPlanningWeekFromDate(dateStr) {
  if (!dateStr) return;
  const picked = parseIsoDateLocal(dateStr);
  const day = picked.getDay();
  const diffToMon = day === 0 ? -6 : 1 - day;
  const mon = new Date(picked.getFullYear(), picked.getMonth(), picked.getDate() + diffToMon);
  const monIso = `${mon.getFullYear()}-${pad2(mon.getMonth() + 1)}-${pad2(mon.getDate())}T00:00:00+07:00`;
  const isCurrentWeek = monIso === getCurrentMondayIso();

  state.commitments.planning_week_start = monIso;
  state.useRealTimeNow = isCurrentWeek;
  if (isCurrentWeek) {
    state.commitments.now = getCurrentLocalIso();
    const realJsDay = new Date().getDay();
    state.todayDay = DAYS_EN[realJsDay === 0 ? 6 : realJsDay - 1];
  } else {
    delete state.commitments.now;
    state.todayDay = "Monday";
  }
  state.viewWeekOffset = 0;
  syncAllLeftPanels();
  updateTemporalContextUI();
  await solveSchedule();
  if (!state.activeScenario) savePersistedStudentState();
}

async function loadPreset(presetId, options = {}) {
  try {
    const res = await fetch("/api/presets");
    if (!res.ok) throw new Error("Failed to fetch /api/presets");
    const data = await res.json();
    const presets = data.presets || data;
    const chosen = presets[presetId] || presets.minh;
    if (!chosen) return;

    state.commitments = {
      horizon_days: 7,
      personal_habits: [],
      ...chosen.commitments,
    };
    const shouldRebase = Boolean(options.rebaseToCurrentWeek) || presetId === "empty";
    if (shouldRebase) {
      state.commitments.planning_week_start = getCurrentMondayIso();
      state.commitments.now = getCurrentLocalIso();
      state.commitments.buffer_mode = presetId === "empty" ? "COGNITIVE_LOAD" : (state.commitments.buffer_mode || "COGNITIVE_LOAD");
      state.commitments.alpha_light = state.commitments.alpha_light ?? 1.2;
      state.commitments.alpha_heavy = state.commitments.alpha_heavy ?? 1.35;
      state.useRealTimeNow = true;
      const realJsDay = new Date().getDay();
      state.todayDay = DAYS_EN[realJsDay === 0 ? 6 : realJsDay - 1];
    } else {
      state.useRealTimeNow = false;
      state.todayDay = "Monday";
    }
    state.viewWeekOffset = 0;
    state.tasks = Array.isArray(chosen.tasks) ? chosen.tasks : chosen.tasks.tasks || [];
    state.activeScenario = null;
    state.repairedMovedIds.clear();
    state.pinnedBlocks.clear();
    state.doneBlocks.clear();
    state.taskBufferMap.clear();
    state.actualDurations.clear();
    state.previewState = null;

    const sel = document.getElementById("scenarioSelect");
    if (sel) sel.value = "";
    document.getElementById("scenarioBanner")?.classList.add("hidden");
    document.getElementById("determinismBanner")?.classList.add("hidden");
    document.getElementById("repairLogPanel")?.classList.add("hidden");

    syncAllLeftPanels();
    updateTemporalContextUI();
    await solveSchedule();
    savePersistedStudentState();
  } catch (err) {
    console.error("Failed to load preset:", err);
  }
}

async function onScenarioSelectChange(scenarioId) {
  if (!scenarioId) return;
  try {
    const res = await fetch(`/api/scenarios/${scenarioId}`);
    if (!res.ok) throw new Error(`Failed to fetch scenario ${scenarioId}`);
    const sc = await res.json();

    state.commitments = {
      horizon_days: 7,
      personal_habits: [],
      ...sc.commitments,
    };
    state.tasks = sc.tasks || [];
    state.activeScenario = sc;
    state.useRealTimeNow = false;
    state.viewWeekOffset = 0;
    state.todayDay = "Monday";
    state.repairedMovedIds.clear();
    state.pinnedBlocks.clear();
    state.doneBlocks.clear();
    state.taskBufferMap.clear();
    state.actualDurations.clear();
    state.previewState = null;

    // Show scenario banner
    const banner = document.getElementById("scenarioBanner");
    if (banner) {
      document.getElementById("scenarioBannerTitle").textContent = `${sc.scenario_id} — ${sc.name}`;
      document.getElementById("scenarioBannerDesc").textContent = sc.description || "";
      document.getElementById("scenarioBannerExpected").textContent = `Expected: ${sc.expected_status || "SUCCESS"}`;
      banner.classList.remove("hidden");
    }

    // Pre-fill disruption or overrun inputs if present in scenario
    const dis = sc.disruption || sc.disruption_event;
    if (dis) {
      document.getElementById("inpDisruptTitle").value = dis.title || dis.label || "Sự kiện khẩn cấp";
      document.getElementById("inpDisruptDay").value = dis.day_of_week || dis.day || "Monday";
      document.getElementById("inpDisruptStart").value = dis.start_time || dis.start || "07:30";
      document.getElementById("inpDisruptEnd").value = dis.end_time || dis.end || "09:30";
    }

    syncAllLeftPanels();
    updateTemporalContextUI();
    await solveSchedule();
  } catch (err) {
    console.error("Error loading scenario:", err);
  }
}

function clearAllData() {
  state.tasks = [];
  state.commitments.fixed_events = [];
  state.commitments.personal_habits = [];
  state.commitments.planning_week_start = getCurrentMondayIso();
  state.commitments.now = getCurrentLocalIso();
  state.useRealTimeNow = true;
  state.viewWeekOffset = 0;
  state.activeScenario = null;
  state.repairedMovedIds.clear();
  state.pinnedBlocks.clear();
  state.doneBlocks.clear();
  state.taskBufferMap.clear();
  state.actualDurations.clear();
  try {
    localStorage.removeItem(WORKSPACE_STORAGE_KEY);
    localStorage.removeItem(_storageKey());
  } catch (_) {}
  fetch("/api/state?workspace_id=default", { method: "DELETE" }).catch(() => {});
  syncAllLeftPanels();
  updateTemporalContextUI();
  solveSchedule();
}

// ============================================================================
// LAB CONTROL RAIL & UNIFIED TASK INPUT
// ============================================================================

function syncLabParamsUI() {
  const focusSel = document.getElementById("labFocusPrefSelect");
  const bufSel = document.getElementById("labBufferModeSelect");
  const aLight = document.getElementById("labAlphaLight");
  const aHeavy = document.getElementById("labAlphaHeavy");
  const nowInp = document.getElementById("labNowInput");
  const habitRow = document.getElementById("labHabitRow");
  const alphaRow = document.getElementById("labAlphaRow");

  const mode = state.commitments?.buffer_mode || "HABIT";
  if (focusSel) focusSel.value = state.commitments?.focus_preference || "BALANCED";
  if (bufSel) bufSel.value = mode;
  if (aLight) aLight.value = String(state.commitments?.alpha_light ?? 1.2);
  if (aHeavy) aHeavy.value = String(state.commitments?.alpha_heavy ?? 1.35);
  if (nowInp) nowInp.value = state.commitments?.now || "";
  if (habitRow) habitRow.classList.toggle("hidden", mode === "COGNITIVE_LOAD");
  if (alphaRow) alphaRow.classList.toggle("hidden", mode !== "COGNITIVE_LOAD");
}

async function onLabParamChange() {
  state.commitments.focus_preference = document.getElementById("labFocusPrefSelect")?.value || "BALANCED";
  state.commitments.buffer_mode = document.getElementById("labBufferModeSelect")?.value || "COGNITIVE_LOAD";
  state.commitments.alpha_light = parseFloat(document.getElementById("labAlphaLight")?.value || "1.2");
  state.commitments.alpha_heavy = parseFloat(document.getElementById("labAlphaHeavy")?.value || "1.35");
  const rawNow = (document.getElementById("labNowInput")?.value || "").trim();
  if (rawNow) {
    state.commitments.now = rawNow;
    state.useRealTimeNow = false;
  } else {
    delete state.commitments.now;
  }
  syncLabParamsUI();
  updateTemporalContextUI();
  await solveSchedule();
}

async function setLabNowCurrent() {
  const curIso = getCurrentLocalIso();
  state.commitments.now = curIso;
  state.useRealTimeNow = false;
  const nowInp = document.getElementById("labNowInput");
  if (nowInp) nowInp.value = curIso;
  updateTemporalContextUI();
  await solveSchedule();
}

function syncAllLeftPanels() {
  syncEstimateHabitUI();
  syncLabParamsUI();
  renderTaskQueue();
  renderFixedEventsList();
  syncSleepUI();
  populateOverrunSelect();
}

function updateSlotEquivalent() {}

function syncEstimateHabitUI() {
  const sel = document.getElementById("inpEstimateHabit");
  if (!sel || !state.commitments) return;
  if (state.commitments.estimate_habit) {
    sel.value = String(state.commitments.estimate_habit).toUpperCase();
  } else if (sel.value) {
    state.commitments.estimate_habit = sel.value;
  }
}

async function onEstimateHabitChange() {
  const sel = document.getElementById("inpEstimateHabit");
  if (!sel) return;
  if (sel.value) state.commitments.estimate_habit = sel.value;
  else delete state.commitments.estimate_habit;
  renderTaskQueue();
  await solveSchedule();
}

// Quick-Add Regex Parser (supports Vietnamese & English shorthand)
function parseQuickAdd(text) {
  const raw = (text || "").trim();
  if (!raw) return null;

  let durationMin = 120;
  const durMatch = raw.match(/\b(\d+)\s*(?:m|min|phut|p)\b/i);
  const hrMatch = raw.match(/\b(\d+(?:\.\d+)?)\s*(?:h|hr|gio)\b/i);
  if (durMatch) durationMin = parseInt(durMatch[1], 10);
  else if (hrMatch) durationMin = Math.round(parseFloat(hrMatch[1]) * 60);
  durationMin = Math.max(15, Math.ceil(durationMin / 15) * 15);

  // Day mapping: t2..t7, cn, mon..sun
  const dayMap = {
    t2: "Monday", mon: "Monday", monday: "Monday",
    t3: "Tuesday", tue: "Tuesday", tuesday: "Tuesday",
    t4: "Wednesday", wed: "Wednesday", wednesday: "Wednesday",
    t5: "Thursday", thu: "Thursday", thursday: "Thursday",
    t6: "Friday", fri: "Friday", friday: "Friday",
    t7: "Saturday", sat: "Saturday", saturday: "Saturday",
    cn: "Sunday", sun: "Sunday", sunday: "Sunday",
  };
  let deadlineDay = "Wednesday";
  const dayToken = raw.match(/\b(t[2-7]|cn|mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b/i);
  if (dayToken) {
    deadlineDay = dayMap[dayToken[1].toLowerCase()] || "Wednesday";
  }

  let deadlineTime = "23:59";
  const timeMatch = raw.match(/\b([01]?\d|2[0-3]):([0-5]\d)\b/);
  if (timeMatch) {
    deadlineTime = `${pad2(timeMatch[1])}:${timeMatch[2]}`;
  }

  let priority = 3;
  const pMatch = raw.match(/\bp([1-5])\b/i);
  if (pMatch) priority = parseInt(pMatch[1], 10);

  let minChunkMin = 45;
  let isSplittable = durationMin > 60;
  const splitMatch = raw.match(/~(\d+)/);
  if (splitMatch) {
    isSplittable = true;
    minChunkMin = Math.max(15, parseInt(splitMatch[1], 10));
  }

  let dependsOn = [];
  const afterMatch = raw.match(/after:([A-Za-z0-9_,-]+)/i);
  if (afterMatch) {
    dependsOn = afterMatch[1].split(",").map((s) => s.trim()).filter(Boolean);
  }

  const title = raw
    .replace(/\b(\d+)\s*(?:m|min|phut|p)\b/gi, "")
    .replace(/\b(\d+(?:\.\d+)?)\s*(?:h|hr|gio)\b/gi, "")
    .replace(/\b(t[2-7]|cn|mon(?:day)?|tue(?:sday)?|wed(?:nesday)?|thu(?:rsday)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)\b/gi, "")
    .replace(/\b([01]?\d|2[0-3]):([0-5]\d)\b/g, "")
    .replace(/\bp[1-5]\b/gi, "")
    .replace(/~\d+/g, "")
    .replace(/after:[A-Za-z0-9_,-]+/gi, "")
    .replace(/\s+/g, " ")
    .trim() || "Bài tập mới";

  return {
    title,
    duration_min: durationMin,
    deadline_day: deadlineDay,
    deadline_time: deadlineTime,
    priority,
    is_splittable: isSplittable,
    min_chunk_min: minChunkMin,
    depends_on: dependsOn,
  };
}

function previewQuickAdd(val) {
  const box = document.getElementById("quickAddChips");
  if (!box) return;
  const parsed = parseQuickAdd(val);
  if (!parsed) {
    box.innerHTML = "";
    return;
  }
  box.innerHTML = `
    <span class="px-1.5 py-0.5 bg-indigo-100 text-indigo-800 rounded text-[10px] font-semibold">📌 ${parsed.title}</span>
    <span class="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 rounded text-[10px] mono">⏱ ${parsed.duration_min}p</span>
    <span class="px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded text-[10px] mono">📅 ${parsed.deadline_day} ${parsed.deadline_time}</span>
    <span class="px-1.5 py-0.5 bg-purple-100 text-purple-800 rounded text-[10px] mono">★ P${parsed.priority}</span>
  `;
}

async function applyQuickAdd() {
  const inp = document.getElementById("quickAddInput");
  const parsed = parseQuickAdd(inp?.value || "");
  if (!parsed) return;

  const newTask = {
    task_id: `TASK-${state.tasks.length + 1}`,
    title: parsed.title,
    duration_min: parsed.duration_min,
    deadline_day: parsed.deadline_day,
    deadline_time: parsed.deadline_time,
    priority: parsed.priority,
    category: parsed.deadline_day ? "ASSIGNMENT" : "HABIT",
    is_splittable: parsed.is_splittable,
    min_chunk_min: parsed.min_chunk_min,
    max_chunk_min: 90,
    depends_on: parsed.depends_on,
  };
  state.tasks.push(newTask);
  if (inp) inp.value = "";
  const chips = document.getElementById("quickAddChips");
  if (chips) chips.innerHTML = "";
  const diagBox = document.getElementById("quickAddHybridDiag");
  if (diagBox) diagBox.innerHTML = "";

  syncAllLeftPanels();
  await solveSchedule();
}

function openQuickHybridDraftInModal() {
  const d = state.lastQuickHybridDraft;
  if (!d) {
    openStudentTaskModal();
    return;
  }
  openStudentTaskModal();
  if (document.getElementById("stInpTaskId")) document.getElementById("stInpTaskId").value = d.task_id || "";
  if (document.getElementById("stInpTitle")) document.getElementById("stInpTitle").value = d.title || "";
  if (document.getElementById("stInpDuration")) document.getElementById("stInpDuration").value = String(d.duration_min || 60);
  if (document.getElementById("stInpDeadlineDay")) document.getElementById("stInpDeadlineDay").value = d.deadline_day || "";
  if (document.getElementById("stInpDeadlineTime")) document.getElementById("stInpDeadlineTime").value = d.deadline_time || "23:59";
  if (document.getElementById("stInpDependsOn")) document.getElementById("stInpDependsOn").value = (d.depends_on || []).join(", ");
  if (document.getElementById("stInpStartAfter") && d.start_after) document.getElementById("stInpStartAfter").value = d.start_after;
  setStNlUrgency(d.user_priority || _mapSolverToUserUrgency(d.priority || 3));
  setStNlPacing(d.work_rhythm || "BALANCED");
  setStNlSession(d.is_splittable === false ? "single" : "splittable");
  updateStBufferPreview();
}

async function commitQuickHybridDraft() {
  const d = state.lastQuickHybridDraft;
  if (!d) return;
  const tid = d.task_id || `TASK_${state.tasks.length + 1}`;
  state.tasks.push({
    task_id: tid,
    title: d.title || "Bài tập mới",
    duration_min: d.duration_min || 60,
    deadline_day: d.deadline_day || null,
    deadline_time: d.deadline_time || "23:59",
    priority: d.priority || 3,
    category: d.category || (d.deadline_day ? "ASSIGNMENT" : "HABIT"),
    is_splittable: d.is_splittable !== false,
    min_chunk_min: d.min_chunk_min || 30,
    max_chunk_min: d.max_chunk_min || 60,
    work_rhythm: d.work_rhythm || "BALANCED",
    start_after: d.start_after || null,
    depends_on: d.depends_on || [],
    cognitive_load: d.cognitive_load || 2,
  });
  state.lastQuickHybridDraft = null;
  const inp = document.getElementById("quickAddInput");
  if (inp) inp.value = "";
  const chips = document.getElementById("quickAddChips");
  if (chips) chips.innerHTML = "";
  const diagBox = document.getElementById("quickAddHybridDiag");
  if (diagBox) diagBox.innerHTML = "";
  syncAllLeftPanels();
  await solveSchedule();
}

async function analyzeQuickAddHybrid() {
  const inp = document.getElementById("quickAddInput");
  const diagBox = document.getElementById("quickAddHybridDiag");
  const chipsBox = document.getElementById("quickAddChips");
  const prompt = (inp?.value || "").trim();
  if (!prompt) return;

  if (diagBox) {
    diagBox.innerHTML = `<div class="text-[10px] text-indigo-600 font-medium">⏳ Đang phân tích Hybrid 6-Stage...</div>`;
  }

  try {
    const res = await fetch("/api/tasks/natural-add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        now: state.commitments?.now || null,
        existing_count: state.tasks.length,
        engine: document.getElementById("quickAddNlBackend")?.value || "hybrid",
        translation_backend: state.nlTransBackend || "rule",
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    if (data.status === "NO_TASK" || data.status === "INVALID") {
      if (diagBox) {
        renderHybridDiagnostics(diagBox, data.hybrid, data.translation, data.rejection_reason);
      }
      return;
    }

    const d = data.draft || {};
    state.lastQuickHybridDraft = d;

    if (chipsBox) {
      chipsBox.innerHTML = `
        <span class="px-1.5 py-0.5 bg-indigo-100 text-indigo-800 rounded text-[10px] font-semibold">📌 ${_escHtml(d.title || prompt)}</span>
        <span class="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 rounded text-[10px] mono">⏱ ${d.duration_min || 60}p</span>
        <span class="px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded text-[10px] mono">📅 ${_escHtml(d.deadline_day || "Habit")} ${_escHtml(d.deadline_time || "")}</span>
        <span class="px-1.5 py-0.5 bg-purple-100 text-purple-800 rounded text-[10px] mono">★ P${d.priority || 3} (${_escHtml(d.work_rhythm || "BALANCED")})</span>
        <div class="w-full flex gap-1.5 pt-1">
          <button type="button" onclick="commitQuickHybridDraft()" class="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-[10px] font-bold">➕ Xếp vào lịch ngay</button>
          <button type="button" onclick="openQuickHybridDraftInModal()" class="px-2 py-1 bg-slate-200 hover:bg-slate-300 text-slate-800 rounded text-[10px] font-semibold">✏️ Mở trong Modal Lab</button>
        </div>
      `;
    }
    if (diagBox) {
      renderHybridDiagnostics(diagBox, data.hybrid, data.translation);
    }
  } catch (err) {
    if (diagBox) {
      diagBox.innerHTML = `<div class="text-[10px] text-rose-600 font-medium">Lỗi Hybrid: ${_escHtml(err.message)}</div>`;
    }
  }
}

function resetTaskForm() {
  state.editingTaskId = null;
}

function editTask(taskId) {
  editStudentTask(taskId);
}

async function deleteTask(taskId) {
  state.tasks = state.tasks.filter((t) => (t.task_id || t.id) !== taskId);
  savePersistedStudentState();
  syncAllLeftPanels();
  await solveSchedule();
}

function renderTaskQueue() {
  const container = document.getElementById("taskQueueContainer");
  const countBadge = document.getElementById("taskCountBadge");
  const totalSummary = document.getElementById("queueTotalSummary");
  if (!container) return;

  const totalMin = state.tasks.reduce((s, t) => s + (t.duration_min || t.estimate_min || 0), 0);
  if (countBadge) countBadge.textContent = String(state.tasks.length);
  if (totalSummary) {
    totalSummary.textContent = `${state.tasks.length} tasks · ${totalMin} phút (${(totalMin / 60).toFixed(1)}h)`;
  }

  if (state.tasks.length === 0) {
    container.innerHTML = `<div class="text-xs text-slate-400 text-center py-4 italic">Chưa có task nào trong hàng đợi.</div>`;
    return;
  }

  const unplacedIds = new Set(
    ((state.currentSchedule && state.currentSchedule.unplaced_tasks) || []).map((u) => u.task_id)
  );
  const activeNow = getActiveNowDate();

  container.innerHTML = state.tasks
    .map((t) => {
      const tid = t.task_id || t.id;
      const dur = t.duration_min || t.estimate_min || 60;
      const plannedDur = plannedMinutesFor(dur, currentBufferMultiplier());
      const dlInfo = resolveDeadlineDisplay(t, activeNow);
      const isUnplaced = unplacedIds.has(tid);
      const deps = t.depends_on || t.after || [];
      const rhythmBadge = t.work_rhythm === "DEEP_FLOW" ? "🔥" : t.work_rhythm === "LIGHT_PACE" ? "🐢" : "";

      return `
      <div class="p-2.5 rounded-lg border ${isUnplaced ? "border-rose-400 bg-rose-50" : "border-slate-200 bg-slate-50/70"} hover:border-indigo-300 transition flex items-start justify-between gap-2">
        <div class="space-y-0.5 min-w-0">
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="px-1.5 py-0.5 text-[10px] font-bold mono rounded bg-slate-800 text-white">${_escHtml(tid)}</span>
            <span class="text-xs font-bold text-slate-800 truncate">${_escHtml(t.title)}</span>
            ${rhythmBadge ? `<span title="${_escHtml(t.work_rhythm)}">${rhythmBadge}</span>` : ""}
            ${isUnplaced ? `<span class="px-1.5 py-0.5 text-[10px] font-bold bg-rose-600 text-white rounded mono">UNPLACED</span>` : ""}
          </div>
          <div class="text-[11px] text-slate-600 mono flex flex-wrap items-center gap-1.5">
            <span>⏱ ${dur}p${plannedDur > Math.ceil(dur / 15) * 15 ? ` <span class="text-amber-700 font-semibold">→ ${plannedDur}p</span>` : ""}</span>
            <span>📅 ${_escHtml(dlInfo.dateText)}</span>
            ${dlInfo.badgeHtml}
            <span>★ P${t.priority || 3}</span>
            <span>${t.is_splittable || t.splittable ? `✂️ Cắt (≥${t.min_chunk_min || 45}p)` : "🧱 Khối"}</span>
            ${deps.length ? `<span class="text-indigo-700 font-semibold">🔗 sau: ${_escHtml(deps.join(","))}</span>` : ""}
          </div>
        </div>
        <div class="flex items-center gap-1 shrink-0">
          <button onclick="editTask('${_escHtml(tid)}')" class="px-1.5 py-1 text-xs text-slate-600 hover:text-indigo-600 rounded hover:bg-slate-200" title="Sửa Task trong Modal Lab">✏️</button>
          <button onclick="deleteTask('${_escHtml(tid)}')" class="px-1.5 py-1 text-xs text-slate-600 hover:text-rose-600 rounded hover:bg-rose-100" title="Xóa Task">🗑️</button>
        </div>
      </div>`;
    })
    .join("");
}

// ============================================================================
// TAB 2: SLEEP & FIXED COMMITMENTS
// ============================================================================

function syncSleepUI() {
  const sleep = (state.commitments && state.commitments.sleep_schedule) || {};
  const start = sleep.daily_start_time || sleep.start || "23:30";
  const end = sleep.daily_end_time || sleep.end || "06:30";
  const sEl = document.getElementById("inpSleepStart");
  const eEl = document.getElementById("inpSleepEnd");
  if (sEl) sEl.value = start;
  if (eEl) eEl.value = end;
  document.querySelectorAll(".st-sleep-window-label").forEach((el) => {
    el.textContent = `🌙 ${start} – ${end} (Ngủ)`;
  });
}

async function updateSleepFromUI() {
  if (!state.commitments.sleep_schedule) state.commitments.sleep_schedule = {};
  state.commitments.sleep_schedule.daily_start_time = document.getElementById("inpSleepStart").value || "23:30";
  state.commitments.sleep_schedule.daily_end_time = document.getElementById("inpSleepEnd").value || "06:30";
  state.commitments.sleep_schedule.is_hard_lock = true;
  syncSleepUI();
  await solveSchedule();
}

function renderFixedEventsList() {
  const container = document.getElementById("fixedEventsContainer");
  const badge = document.getElementById("fixedEventCountBadge");
  if (!container) return;

  const events = (state.commitments && state.commitments.fixed_events) || [];
  if (badge) badge.textContent = String(events.length);

  if (events.length === 0) {
    container.innerHTML = `<div class="text-xs text-slate-400 text-center py-3 italic">Không có sự kiện cố định.</div>`;
    return;
  }

  container.innerHTML = events
    .map((ev, idx) => {
      const id = ev.event_id || ev.id || `EV_${idx + 1}`;
      const dayStr = Array.isArray(ev.day_of_week) ? ev.day_of_week.join(", ") : ev.day_of_week || ev.days;
      const start = ev.start_time || ev.start;
      const end = ev.end_time || ev.end;
      return `
      <div class="p-2 rounded border border-slate-200 bg-slate-50 flex items-center justify-between gap-2 text-xs">
        <div>
          <div class="font-bold text-slate-800">${ev.title} <span class="text-[10px] font-normal text-slate-500 mono">(${id})</span></div>
          <div class="text-[11px] text-slate-600 mono">${dayStr} · ${start}–${end} · ${ev.category || "CLASS"}</div>
        </div>
        <button onclick="deleteFixedEvent(${idx})" class="text-slate-400 hover:text-rose-600 px-1.5 py-0.5 font-bold">✕</button>
      </div>`;
    })
    .join("");
}

async function addFixedEventFromForm() {
  const eventId = document.getElementById("inpEvId").value.trim().toUpperCase() || `FIXED_${Date.now().toString().slice(-3)}`;
  const title = document.getElementById("inpEvTitle").value.trim() || "Lịch bận cố định";
  const dayRaw = document.getElementById("inpEvDay").value || "Monday";
  const dayOfWeek = dayRaw.includes(",") ? dayRaw.split(",").map((s) => s.trim()) : dayRaw;
  const category = document.getElementById("inpEvCategory").value || "ACADEMIC_CLASS";
  const startTime = document.getElementById("inpEvStart").value || "13:00";
  const endTime = document.getElementById("inpEvEnd").value || "17:00";

  if (!state.commitments.fixed_events) state.commitments.fixed_events = [];
  state.commitments.fixed_events.push({
    event_id: eventId,
    title,
    day_of_week: dayOfWeek,
    start_time: startTime,
    end_time: endTime,
    category,
  });

  document.getElementById("inpEvId").value = "";
  document.getElementById("inpEvTitle").value = "";
  renderFixedEventsList();
  await solveSchedule();
}

async function deleteFixedEvent(idx) {
  state.commitments.fixed_events.splice(idx, 1);
  renderFixedEventsList();
  await solveSchedule();
}

function populateOverrunSelect() {
  const sel = document.getElementById("inpOverrunTaskSelect");
  if (!sel) return;
  sel.innerHTML = state.tasks
    .map((t) => {
      const tid = t.task_id || t.id;
      const dur = t.duration_min || t.estimate_min || 60;
      return `<option value="${tid}">${tid} — ${t.title} (${dur}p)</option>`;
    })
    .join("");
}

// ============================================================================
// CORE SOLVER EXECUTION & KPI METRICS RENDERING
// ============================================================================

async function solveSchedule() {
  const algorithm = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";
  try {
    const res = await fetch("/api/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algorithm,
        pinned_blocks: Array.from(state.pinnedBlocks.values()),
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const schedule = await res.json();
    state.currentSchedule = schedule;

    updateTemporalContextUI();
    renderKpiCards(schedule);
    renderHealthV21Panels(schedule);
    renderOverloadBox(schedule);
    renderTaskQueue();
    populateOverrunSelect();
    renderMainGrid();
    renderPlacedBlocksTable(schedule);
    renderStudentViews();

    if (!state.activeScenario) {
      savePersistedStudentState();
    }

    if (state.workbenchMode === "COMPARE") {
      await runDualComparison();
    }
  } catch (err) {
    console.error("solveSchedule failed:", err);
  }
}

function renderKpiCards(schedule) {
  if (!schedule || !schedule.summary) return;
  const s = schedule.summary;
  const m = schedule.metrics || {};

  const hardEl = document.getElementById("kpiHardViolations");
  if (hardEl) {
    hardEl.textContent = String(s.hard_constraint_violations);
    hardEl.className =
      s.hard_constraint_violations === 0
        ? "text-xl font-bold mono text-emerald-600"
        : "text-xl font-bold mono text-rose-600";
  }

  const dlEl = document.getElementById("kpiDeadlineRate");
  if (dlEl) {
    dlEl.textContent = `${s.deadline_satisfaction_rate.toFixed(1)}%`;
    dlEl.className =
      s.deadline_satisfaction_rate >= 100
        ? "text-xl font-bold mono text-indigo-600"
        : "text-xl font-bold mono text-amber-600";
  }

  const placedEl = document.getElementById("kpiPlacedCount");
  if (placedEl) {
    placedEl.textContent = `${s.tasks_placed} / ${s.total_tasks_requested} tasks (${s.parts_placed}/${s.parts_total} phiên)`;
  }

  const deepPeak = m.deep_peak_match_pct ?? m.peak_match_rate_pct ?? 100.0;
  const peakEl = document.getElementById("kpiPeakMatch");
  if (peakEl) {
    peakEl.textContent = `${Number(deepPeak).toFixed(1)}%`;
    peakEl.className =
      deepPeak >= 70
        ? "text-xl font-bold mono text-emerald-600"
        : deepPeak >= 40
          ? "text-xl font-bold mono text-amber-600"
          : "text-xl font-bold mono text-rose-600";
  }
  const peakNoteEl = document.getElementById("kpiPeakMatchNote");
  if (peakNoteEl) {
    peakNoteEl.textContent = `Chung: ${Number(m.peak_match_rate_pct ?? 100).toFixed(0)}% · Avg E=${Number(m.avg_energy_level ?? 0).toFixed(2)}`;
  }

  const expRating = Number(s.experience_rating ?? 1.0);
  const expEl = document.getElementById("kpiExperienceVal");
  if (expEl) {
    expEl.textContent = expRating.toFixed(2);
    expEl.className =
      expRating >= 4.0
        ? "text-xl font-bold mono text-rose-600"
        : expRating >= 3.0
          ? "text-xl font-bold mono text-amber-600"
          : "text-xl font-bold mono text-violet-700";
  }
  const ctxEl = document.getElementById("kpiContextSwitches");
  if (ctxEl) {
    ctxEl.textContent = `Đổi môn: ${m.context_switches ?? 0} · Gộp: ${m.batched_pairs ?? 0} · Nghỉ: ${s.rest_slots ?? 0}`;
  }

  const execEl = document.getElementById("kpiExecTime");
  if (execEl) execEl.textContent = schedule.execution_time_ms.toFixed(2);
  const freeEl = document.getElementById("kpiFreeSlots");
  if (freeEl) freeEl.textContent = String(s.free_slots_remaining);
  const fragEl = document.getElementById("kpiFragmentation");
  if (fragEl) fragEl.textContent = `Phân mảnh: ${(s.fragmentation_index * 100).toFixed(1)}%`;

  const hashEl = document.getElementById("kpiDeterminismHash");
  if (hashEl) {
    hashEl.textContent = (schedule.determinism_hash || "--------").slice(0, 12) + "…";
    hashEl.title = schedule.determinism_hash || "";
  }
  const solverEl = document.getElementById("kpiSolverLabel");
  if (solverEl) solverEl.textContent = schedule.solver_used || "";
}

function renderHealthV21Panels(schedule) {
  const stPanel = document.getElementById("stHealthV21Panel");
  const labPanel = document.getElementById("labHealthV21Panel");
  const h = schedule && schedule.health_v21;
  if (!h || !h.available) {
    stPanel?.classList.add("hidden");
    labPanel?.classList.add("hidden");
    return;
  }

  const toneCls = {
    emerald: "bg-emerald-100 text-emerald-800 border-emerald-200",
    amber: "bg-amber-100 text-amber-900 border-amber-300",
    indigo: "bg-indigo-100 text-indigo-800 border-indigo-200",
    rose: "bg-rose-100 text-rose-800 border-rose-300",
  }[h.verdict_tone || "slate"] || "bg-slate-100 text-slate-800 border-slate-200";

  const g = h.gates || {};
  const p = h.pillars || {};
  const p1 = p.p1 || {};
  const p2 = p.p2 || {};
  const p3 = p.p3 || {};
  const p4 = p.p4 || {};
  const critiques = h.top_critiques || [];

  if (stPanel) {
    stPanel.classList.remove("hidden");
    const vBadge = document.getElementById("stHealthVerdictBadge");
    if (vBadge) {
      vBadge.className = `px-2.5 py-1 rounded-full text-[11px] font-bold mono border ${toneCls}`;
      vBadge.textContent = `${h.verdict_label_vi} (${h.verdict})`;
    }
    const sumEl = document.getElementById("stHealthSummaryText");
    if (sumEl) {
      sumEl.textContent = (h.verdict_reasons_vi && h.verdict_reasons_vi[0]) || "";
    }
    const rhoEl = document.getElementById("stHealthRhoBadge");
    if (rhoEl) {
      rhoEl.textContent = `G1=${g.g1_total_violations ?? 0} · ρ=${Number(g.rho_total ?? 0).toFixed(2)} · Crit=${h.critical_count ?? 0} · Warn=${h.warning_count ?? 0}`;
    }

    const p1Val = document.getElementById("stHealthP1Val");
    const p1Sub = document.getElementById("stHealthP1Sub");
    if (p1Val) p1Val.textContent = `${Number(p1.deadline_value_rate_pct ?? 100).toFixed(1)}%`;
    if (p1Sub) p1Sub.textContent = `Dồn <10h: ${Number(p1.unjustified_last_10h_crowding_pct ?? 0).toFixed(1)}% · Habit: ${p1.habit_value_rate_pct ?? "-"}%`;

    const p2Val = document.getElementById("stHealthP2Val");
    const p2Sub = document.getElementById("stHealthP2Sub");
    const apk = p2.achievable_heavy_peak_match_pct ?? p2.heavy_peak_match_pct;
    if (p2Val) p2Val.textContent = apk !== null && apk !== undefined ? `${Number(apk).toFixed(1)}% Peak` : "Không có L3";
    if (p2Sub) p2Sub.textContent = `Nghỉ >10p: ${p2.heavy_recovery_rate_pct ?? 100}% · OffP: ${p2.off_peak_heavy_mismatch_count ?? 0} · SJL: ${p2.sjl_minutes ?? "N/A"}p`;

    const p3Val = document.getElementById("stHealthP3Val");
    const p3Sub = document.getElementById("stHealthP3Sub");
    if (p3Val) p3Val.textContent = `Max ${p3.max_daily_total_min ?? 0}p (${((p3.max_daily_total_min ?? 0) / 60).toFixed(1)}h)`;
    if (p3Sub) p3Sub.textContent = `Std: ${Number(p3.total_daily_load_std_min ?? 0).toFixed(0)}p · Đổi môn: ${p3.focus_context_switches ?? 0}`;

    const p4Val = document.getElementById("stHealthP4Val");
    const p4Sub = document.getElementById("stHealthP4Sub");
    if (p4Val) p4Val.textContent = `${Number(p4.shock_25_pct ?? 100).toFixed(1)}% an toàn`;
    if (p4Sub) p4Sub.textContent = `Sốc +25% (+50%: ${Number(p4.shock_50_pct ?? 100).toFixed(0)}%) · Buffer: ${Number(p4.true_buffer_task_pct ?? 0).toFixed(0)}%`;

    const details = document.getElementById("stHealthIceeDetails");
    const list = document.getElementById("stHealthIceeList");
    const iceeSum = document.getElementById("stHealthIceeSummary");
    const actionable = critiques.filter((c) => c.severity !== "INFO").slice(0, 3);
    if (details && list) {
      if (actionable.length > 0) {
        details.classList.remove("hidden");
        if (iceeSum) iceeSum.textContent = `💡 Phát hiện ${actionable.length} điểm cần lưu ý trên lịch (Top ICEE)`;
        list.innerHTML = actionable
          .map(
            (c) => `
          <li class="p-2 rounded-lg bg-white border ${c.severity === "CRITICAL" ? "border-rose-300" : "border-amber-200"}">
            <div class="font-bold text-slate-900">[${_escHtml(c.severity)}][${_escHtml(c.pillar)}] ${_escHtml(c.summary_vi)}</div>
            <div class="text-slate-600 mt-0.5">→ ${_escHtml(c.suggested_action_vi)}</div>
          </li>`
          )
          .join("");
      } else {
        details.classList.add("hidden");
      }
    }
  }

  if (labPanel) {
    labPanel.classList.remove("hidden");
    const lv = document.getElementById("labHealthVerdictBadge");
    if (lv) {
      lv.className = `px-2 py-0.5 rounded-full text-[11px] font-bold mono border ${toneCls}`;
      lv.textContent = `${h.verdict} (Crit=${h.critical_count}, Warn=${h.warning_count})`;
    }
    const meta = document.getElementById("labHealthEvalMeta");
    if (meta) {
      meta.textContent = `G1=${g.g1_total_violations} · ρ_tot=${g.rho_total} · ρ_dl=${g.rho_deadline} · TStd=${p3.total_daily_load_std_min}/${p3.effective_daily_std_limit_min}p`;
    }
    const vecGrid = document.getElementById("labHealthVectorGrid");
    if (vecGrid) {
      const cells = [
        ["#1 QUALITY", h.verdict],
        ["#2 DEADLINE-VAL", `${p1.deadline_value_rate_pct ?? 100}%`],
        ["#3 SHOCK+25%", `${p4.shock_25_pct ?? 100}%`],
        ["#4 REC / STK", `${p2.heavy_recovery_rate_pct ?? "-"}% / ${p2.max_multi_block_streak_l2_min ?? 0}p`],
        ["#5 OFFP / APK%", `${p2.off_peak_heavy_mismatch_count ?? 0} / ${p2.achievable_heavy_peak_match_pct ?? "-"}%`],
        ["#6 NO-CRAM <10H", `${p1.unjustified_last_10h_crowding_pct ?? 0}%`],
        ["#7 MAX DAILY", `${p3.max_daily_total_min ?? 0}p`],
        ["#8 FOCUS CTX", `${p3.focus_context_switches ?? 0}`],
        ["#9 HABIT%", `${p1.habit_value_rate_pct ?? "-"}%`],
        ["#10 SJL / TSTD", `${p2.sjl_minutes ?? "N/A"}p / ${p3.total_daily_load_std_min ?? 0}p`],
        ["CORNE VEC", `[${(p3.corne_lexicographic_vector || [0, 0, 0]).join(",")}]`],
        ["POST-CLASS", `${p2.post_class_buffer_violations ?? 0}`],
      ];
      vecGrid.innerHTML = cells
        .map(
          ([k, v]) => `
        <div class="p-2 rounded-lg bg-slate-50 border border-slate-200">
          <div class="text-[9px] font-bold text-slate-500">${k}</div>
          <div class="font-bold text-slate-900 truncate">${_escHtml(String(v))}</div>
        </div>`
        )
        .join("");
    }
    const labIcee = document.getElementById("labHealthIceeList");
    if (labIcee) {
      labIcee.innerHTML = critiques.length
        ? critiques
            .map(
              (c) => `
          <div class="p-2 rounded-lg border ${c.severity === "CRITICAL" ? "bg-rose-50 border-rose-200" : c.severity === "WARNING" ? "bg-amber-50 border-amber-200" : "bg-slate-50 border-slate-200"}">
            <div class="font-bold">[${_escHtml(c.severity)}][${_escHtml(c.pillar)}] ${_escHtml(c.summary_vi)}</div>
            <div class="text-[11px] text-slate-600 mt-0.5">${_escHtml(c.rationale_vi)} · <strong>Gợi ý:</strong> ${_escHtml(c.suggested_action_vi)}</div>
          </div>`
            )
            .join("")
        : `<div class="text-emerald-700 font-semibold italic">✓ Không phát hiện cảnh báo ICEE — Lịch biểu đạt chuẩn HIGH_PRODUCTIVITY sạch.</div>`;
    }
  }
}

async function evaluateCurrentScheduleV21() {
  if (!state.currentSchedule || !state.commitments) return;
  try {
    const algorithm = document.getElementById("solverSelect")?.value || state.currentSchedule.solver_used || "SCORED_GREEDY";
    const res = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algorithm,
        pinned_blocks: Array.from(state.pinnedBlocks.values()),
        schedule: state.currentSchedule,
      }),
    });
    if (!res.ok) return;
    const h = await res.json();
    state.currentSchedule.health_v21 = h;
    renderHealthV21Panels(state.currentSchedule);
  } catch (_) {}
}

function renderOverloadBox(schedule) {
  const box = document.getElementById("overloadAlertBox");
  if (!box) return;

  const hasOverload =
    (schedule.unplaced_tasks && schedule.unplaced_tasks.length > 0) ||
    (schedule.overload_reports && schedule.overload_reports.length > 0);

  if (!hasOverload) {
    box.classList.add("hidden");
    return;
  }

  box.classList.remove("hidden");
  const ov = schedule.overload || (schedule.overload_reports && schedule.overload_reports[0]);

  if (ov) {
    document.getElementById("overloadTitle").textContent =
      ov.error_type === "FRAGMENTATION_FAILURE"
        ? "CẢNH BÁO LỖI PHÂN MẢNH KHE THỜI GIAN (FRAGMENTATION FAILURE)"
        : "CẢNH BÁO QUÁ TẢI DUNG LƯỢNG TOÁN HỌC (CAPACITY SHORTAGE)";
    document.getElementById("overloadSubtitle").textContent = ov.message;
    document.getElementById("overloadBadge").textContent = ov.error_type;

    document.getElementById("overloadStatsRow").innerHTML = `
      <div><span class="text-slate-500">Tổng giờ rảnh trước hạn:</span> <strong class="mono text-slate-900">${ov.total_free_minutes_available} phút</strong></div>
      <div><span class="text-slate-500">Tổng khối lượng yêu cầu:</span> <strong class="mono text-rose-700">${ov.total_planned_work_minutes} phút</strong></div>
      <div><span class="text-slate-500">Độ thiếu hụt (Shortage):</span> <strong class="mono text-rose-600">${ov.shortage_minutes} phút</strong></div>
    `;

    document.getElementById("overloadSuggestionsList").innerHTML = (ov.suggested_actions || [])
      .map((act) => `<li>${act}</li>`)
      .join("");
  }

  document.getElementById("unplacedTasksList").innerHTML = (schedule.unplaced_tasks || [])
    .map(
      (u) =>
        `<li><strong>[${u.task_id}] ${u.title}</strong> (${u.duration_min}p — Hạn: ${u.deadline || "N/A"}): ${u.reason}</li>`
    )
    .join("");
}

// ============================================================================
// 672-SLOT INTERACTIVE GRID RENDERING
// ============================================================================

function energyLevelBadgeHtml(energyLevel) {
  if (energyLevel === null || energyLevel === undefined || Number.isNaN(Number(energyLevel))) {
    return `<span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 mono text-[10px]">E=--</span>`;
  }
  const e = Number(energyLevel);
  if (e >= 2.5) {
    return `<span class="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold mono text-[10px]">⚡ E=${e.toFixed(1)} Peak</span>`;
  }
  if (e >= 1.5) {
    return `<span class="px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 font-semibold mono text-[10px]">⚖️ E=${e.toFixed(1)} Mid</span>`;
  }
  return `<span class="px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 mono text-[10px]">Low E=${e.toFixed(1)}</span>`;
}

function formatBlockDateTimeText(b) {
  const gDay = typeof b.start_slot === "number" ? Math.floor(b.start_slot / 96) : 0;
  const dObj = getDayDate(gDay);
  const viShort = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][gDay % 7];
  return `${viShort} · ${formatDateDDMMYYYY(dObj)} ${b.start_time}–${b.end_time}`;
}

function updateLabGridDateHeaders() {
  const weekOff = state.viewWeekOffset || 0;
  const activeNow = getActiveNowDate();
  const shortDays = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];

  for (let d = 0; d < 7; d++) {
    const colDate = getDayDate(weekOff * 7 + d);
    const fullStr = formatDateDDMMYYYY(colDate);
    const shortStr = formatDateShort(colDate);
    const tState = getDayTemporalState(colDate, activeNow);

    const badge =
      tState === "TODAY"
        ? `<span class="px-1 py-0.2 rounded bg-indigo-600 text-white text-[9px] font-bold">NAY</span>`
        : tState === "PAST"
          ? `<span class="px-1 py-0.2 rounded bg-slate-200 text-slate-600 text-[9px]">Qua</span>`
          : `<span class="px-1 py-0.2 rounded bg-emerald-50 text-emerald-700 text-[9px]">Tới</span>`;

    const labTh = document.getElementById(`labGridHeader_${d}`);
    if (labTh) {
      labTh.className = `py-1.5 px-1 text-center font-bold border-r border-slate-200 ${
        tState === "TODAY" ? "bg-indigo-100 text-indigo-950" : tState === "PAST" ? "bg-slate-200/70 text-slate-500" : ""
      }`;
      labTh.innerHTML = `<div class="flex items-center justify-center gap-1">${DAYS_VI[d]} ${badge}</div><div class="text-[10px] font-semibold mono ${tState === "TODAY" ? "text-indigo-700" : "text-slate-500"}">${fullStr}</div>`;
    }

    document.querySelectorAll(`.compare-day-hdr-${d}`).forEach((el) => {
      el.innerHTML = `<div>${shortDays[d]}</div><div class="text-[9px] font-normal mono">${shortStr}</div>`;
    });
  }
}

function renderMainGrid() {
  const tbody = document.getElementById("mainGridTbody");
  if (!tbody || !state.currentSchedule) return;

  updateLabGridDateHeaders();
  const foldSleep = document.getElementById("chkFoldNightSleep")?.checked ?? true;
  const stepSlots = parseInt(document.getElementById("gridResolutionSelect")?.value || "1", 10);

  tbody.innerHTML = buildScheduleRowsHTML(state.currentSchedule, {
    foldSleep,
    stepSlots,
    diffOtherSchedule: null,
  });
  requestAnimationFrame(() => syncLabSliderFromScroll());
}

function buildScheduleRowsHTML(schedule, { foldSleep = true, stepSlots = 1, diffOtherSchedule = null } = {}) {
  const gridStates = schedule.grid_states || [];
  const otherGridStates = (diffOtherSchedule && diffOtherSchedule.grid_states) || null;

  // Map slot -> placed block object
  const blockBySlot = {};
  for (const b of schedule.blocks || []) {
    for (let s = b.start_slot; s < b.end_slot; s++) {
      blockBySlot[s] = b;
    }
  }

  // Map fixed event metadata for labels
  const fixedLabelBySlot = {};
  const fixedCatBySlot = {};
  for (const ev of (state.commitments && state.commitments.fixed_events) || []) {
    const days = Array.isArray(ev.day_of_week)
      ? ev.day_of_week
      : String(ev.day_of_week || "Monday")
          .split(",")
          .map((d) => d.trim());
    const [sh, sm] = String(ev.start_time || "08:00").split(":").map(Number);
    const [eh, em] = String(ev.end_time || "10:00").split(":").map(Number);
    const sOff = Math.floor((sh * 60 + sm) / 15);
    const eOff = Math.ceil((eh * 60 + em) / 15);

    const dayIndices =
      days.includes("ALL") || days.includes("all")
        ? [0, 1, 2, 3, 4, 5, 6]
        : days.map((d) => DAYS_EN.findIndex((en) => en.toLowerCase().startsWith(d.toLowerCase().slice(0, 3)))).filter((i) => i >= 0);

    for (const dIdx of dayIndices) {
      for (let off = sOff; off < eOff; off++) {
        for (const wIdx of [0, 1]) {
          const slotIdx = (wIdx * 7 + dIdx) * 96 + off;
          fixedLabelBySlot[slotIdx] = ev.title;
          fixedCatBySlot[slotIdx] = ev.category || "ACADEMIC_CLASS";
        }
      }
    }
  }

  let html = "";
  const weekOff = state.viewWeekOffset || 0;
  const activeNow = getActiveNowDate();
  const nowSlotOffset = Math.floor((activeNow.getHours() * 60 + activeNow.getMinutes()) / 15);
  const colMeta = [];
  let hasTodayCol = false;
  for (let d = 0; d < 7; d++) {
    const dDate = getDayDate(weekOff * 7 + d);
    const tState = getDayTemporalState(dDate, activeNow);
    if (tState === "TODAY") hasTodayCol = true;
    colMeta.push({ dDate, dateStr: formatDateDDMMYYYY(dDate), tState });
  }

  const sleepCfg = state.commitments?.sleep_schedule || {};
  const sleepStartStr = sleepCfg.daily_start_time || sleepCfg.start || "23:30";
  const sleepEndStr = sleepCfg.daily_end_time || sleepCfg.end || "06:30";
  const [eH, eM] = String(sleepEndStr).split(":").map(Number);
  const startOffset = foldSleep ? Math.max(0, Math.min(48, Math.floor(((eH || 6) * 60 + (eM || 30)) / 15))) : 0;

  if (foldSleep && startOffset > 0) {
    html += `
      <tr class="slot-sleep text-[11px]">
        <td class="py-1.5 px-2 font-bold mono border-r border-slate-600">00:00 - ${sleepEndStr}</td>
        <td colspan="7" class="py-1.5 px-3 text-center font-medium">
          🌙 Khung giờ ngủ đêm được khóa cứng bảo vệ sức khỏe (${sleepStartStr} – ${sleepEndStr}, ≥ 6h tối thiểu)
        </td>
      </tr>`;
  }

  for (let offset = startOffset; offset < 96; offset += stepSlots) {
    const startTime = slotOffsetToTime(offset);
    const endTime = slotOffsetToTime(offset + stepSlots);
    const isFullHour = offset % 4 === 0;
    const isNowRow = hasTodayCol && nowSlotOffset >= offset && nowSlotOffset < offset + stepSlots;

    html += `<tr class="${isFullHour ? "border-t border-slate-300" : ""} ${isNowRow ? "border-t-2 border-t-rose-500" : ""}">`;
    html += `<td class="py-1 px-2 mono text-[11px] ${isNowRow ? "bg-rose-50 text-rose-700 font-bold" : isFullHour ? "font-bold text-slate-800 bg-slate-100" : "text-slate-500 bg-slate-50"} border-r border-slate-300">${isNowRow ? `🔴 ${startTime}` : startTime}</td>`;

    for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
      const slotIdx = (weekOff * 7 + dayIdx) * 96 + offset;
      const rawState = gridStates[slotIdx] || "FREE";
      const block = blockBySlot[slotIdx];
      const meta = colMeta[dayIdx];
      const isCellPast = meta.tState === "PAST" || (meta.tState === "TODAY" && offset + stepSlots <= nowSlotOffset);
      const isCellNow = meta.tState === "TODAY" && isNowRow;

      let cellClass = "slot-free";
      let cellText = "";
      let dragAttrs = `ondragover="event.preventDefault()" ondrop="handleGridDrop(event, ${dayIdx}, '${startTime}')"`;

      if (rawState === "SLEEP") {
        cellClass = "slot-sleep";
        cellText = startTime === sleepStartStr ? `🌙 Ngủ (${sleepStartStr})` : "";
      } else if (rawState === "REST") {
        cellClass = "slot-rest";
        const prevRest = offset > startOffset ? gridStates[slotIdx - stepSlots] === "REST" : false;
        cellText = prevRest ? "〃" : "☕ Nghỉ";
      } else if (rawState.startsWith("OCCUPIED")) {
        const cat = fixedCatBySlot[slotIdx] || "ACADEMIC_CLASS";
        if (cat === "MEAL") cellClass = "slot-occupied-meal";
        else if (cat === "DISRUPTION") cellClass = "slot-occupied-disruption";
        else cellClass = "slot-occupied-class";
        const prevSlotState = offset > startOffset ? gridStates[slotIdx - stepSlots] : "";
        cellText = prevSlotState !== rawState ? fixedLabelBySlot[slotIdx] || rawState.split(":")[1] : "〃";
      } else if (rawState.startsWith("BLOCK") && block) {
        const isMoved = state.repairedMovedIds.has(block.block_id);
        const isProposed = block.state === "PROPOSED";
        const isDiff = otherGridStates && otherGridStates[slotIdx] !== rawState;
        if (isProposed) cellClass = "slot-block-proposed";
        else if (isDiff) cellClass = "slot-block-diff";
        else if (isMoved) cellClass = "slot-block-moved";
        else cellClass = "slot-block";

        const isBlockStart = slotIdx === block.start_slot || offset === startOffset;
        const partBadge = block.total_chunks > 1 ? ` (${block.chunk_index}/${block.total_chunks})` : "";
        cellText = isBlockStart ? `[${block.task_id}] ${block.title}${partBadge}` : `↳ ${block.task_id}`;
        dragAttrs += ` draggable="true" ondragstart="handleGridDragStart(event, '${block.block_id}')"`;
      }

      if (isCellPast && !cellClass.includes("diff") && !cellClass.includes("moved")) {
        cellClass += " opacity-75";
      }
      if (isCellNow) {
        cellClass += " ring-2 ring-rose-500 ring-inset";
      }

      const inspectData = encodeURIComponent(
        JSON.stringify({
          slotIdx,
          dayName: DAYS_VI[dayIdx],
          dateStr: meta.dateStr,
          dayTemporal: meta.tState,
          timeRange: `${startTime}–${endTime}`,
          rawState,
          fixedLabel: fixedLabelBySlot[slotIdx] || null,
          block: block || null,
        })
      );

      html += `
        <td
          ${dragAttrs}
          onmouseenter="inspectSlot('${inspectData}', false)"
          onclick="inspectSlot('${inspectData}', true)"
          class="grid-cell py-1 px-1.5 border-r border-slate-200 truncate cursor-pointer text-[11px] font-medium ${cellClass}"
          title="Slot #${slotIdx} (${DAYS_VI[dayIdx]} ${meta.dateStr} ${startTime}-${endTime})">
          ${_escHtml(cellText)}
        </td>`;
    }

    html += `</tr>`;
  }

  return html;
}

function inspectSlot(encoded, pinPanel = false) {
  try {
    const info = JSON.parse(decodeURIComponent(encoded));
    const contentEl = document.getElementById("inspectorContent");
    const badgeEl = document.getElementById("inspectorSlotBadge");
    const tLabel = info.dayTemporal === "TODAY" ? "HÔM NAY" : info.dayTemporal === "PAST" ? "Đã qua" : "Sắp tới";
    if (badgeEl) {
      badgeEl.textContent = `Slot #${info.slotIdx} (${info.dayName} · ${info.dateStr || ""} ${info.timeRange} · ${tLabel})`;
    }

    if (contentEl) {
      if (info.block) {
        const b = info.block;
        contentEl.innerHTML = `
          <span class="px-1.5 py-0.5 bg-emerald-600 text-white rounded font-bold mono text-[10px]">${_escHtml(b.block_id)}</span>
          <strong class="text-white">${_escHtml(b.title)}</strong>
          <span class="text-slate-300 mono">(${_escHtml(info.dateStr || "")} ${b.start_time}–${b.end_time}, ${b.duration_min}p, P${b.priority})</span>
          <span class="text-amber-300 font-medium">→ ${_escHtml(b.reason || "")}</span>
        `;
      } else if (info.rawState === "SLEEP") {
        contentEl.innerHTML = `<span class="text-indigo-300 font-semibold">🌙 Slot Ngủ Bảo Vệ Cứng (SLEEP - H2):</span> <span>Hệ thống khóa cứng không cho phép xếp bài tập vào giờ ngủ.</span>`;
      } else if (info.rawState.startsWith("OCCUPIED")) {
        contentEl.innerHTML = `<span class="text-rose-400 font-semibold">🟥 Lịch Bận Cố Định (OCCUPIED - H1):</span> <span>${_escHtml(info.fixedLabel || info.rawState)}</span>`;
      } else if (info.rawState === "REST") {
        contentEl.innerHTML = `<span class="text-emerald-300 font-semibold">☕ Nghỉ Phục Hồi 15 Phút (REST - R3):</span> <span>Khoảng nghỉ tự động giữa các phiên học liên tục để tránh quá tải nhận thức.</span>`;
      } else {
        contentEl.innerHTML = `<span class="text-emerald-400 font-semibold">⬜ Khe Thời Gian Trống (FREE):</span> <span>Sẵn sàng tiếp nhận công việc mới (khu ${tLabel}).</span>`;
      }
    }

    if (pinPanel) {
      const panel = document.getElementById("labFixedInspectorPanel");
      if (panel) {
        panel.classList.remove("hidden");
        if (info.block) {
          const b = info.block;
          const dl = resolveDeadlineDisplay(b, getActiveNowDate());
          const codes = (b.reasons || [])
            .map((r) => `<span class="px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800 font-bold mono text-[10px]">${_escHtml(r.code || "RULE")}</span>`)
            .join(" ");
          panel.innerHTML = `
            <div class="flex flex-wrap items-start justify-between gap-2">
              <div class="space-y-1">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="font-bold text-indigo-950">🔬 Phân Tích Toán Học Slot #${info.slotIdx} · ${_escHtml(b.block_id)}</span>
                  ${energyLevelBadgeHtml(b.energy_level)}
                  <span class="px-1.5 py-0.5 rounded bg-slate-800 text-white mono text-[10px]">Load L${b.cognitive_load ?? 2}</span>
                  <span class="px-1.5 py-0.5 rounded bg-white border border-slate-200 mono text-[10px]">P${b.priority}</span>
                </div>
                <div class="text-slate-800"><strong>${_escHtml(b.title)}</strong> · ${formatBlockDateTimeText(b)} (${b.duration_min}p) · Hạn: <span class="mono">${_escHtml(dl.dateText)}</span> ${dl.badgeHtml}</div>
                <div class="flex flex-wrap items-center gap-1 pt-0.5">${codes} <span class="text-slate-700">${_escHtml(b.reason || "")}</span></div>
              </div>
              <button type="button" onclick="document.getElementById('labFixedInspectorPanel').classList.add('hidden')" class="px-2 py-0.5 rounded bg-white border border-slate-300 text-slate-600 hover:text-slate-900 font-bold">✕ Đóng</button>
            </div>`;
        } else {
          panel.innerHTML = `
            <div class="flex items-center justify-between gap-2">
              <div><strong>Slot #${info.slotIdx}</strong> (${_escHtml(info.dayName)} · ${_escHtml(info.dateStr || "")} ${info.timeRange}) · Trạng thái: <strong class="mono">${_escHtml(info.rawState)}</strong> · ${_escHtml(info.fixedLabel || tLabel)}</div>
              <button type="button" onclick="document.getElementById('labFixedInspectorPanel').classList.add('hidden')" class="px-2 py-0.5 rounded bg-white border border-slate-300 text-slate-600 hover:text-slate-900 font-bold">✕ Đóng</button>
            </div>`;
        }
      }
    }
  } catch (e) {
    // ignore
  }
}

function findBufferReason(b) {
  return ((b && b.reasons) || []).find((r) => r && r.code === "ESTIMATE_BUFFER") || null;
}

function formatBlockDuration(b) {
  const r = findBufferReason(b);
  if (!r) return `${b.duration_min}p`;
  if (b.total_chunks > 1) {
    return `${b.duration_min}p <span class="text-amber-700 font-semibold">(task: ${r.estimate_min}p → ${r.planned_min}p)</span>`;
  }
  return `<span class="line-through text-slate-400">${r.estimate_min}p</span> → <span class="text-amber-700 font-bold">${r.planned_min}p</span> <span class="text-[10px] text-amber-700">×${r.multiplier}</span>`;
}

function bufferReasonText(b) {
  const r = findBufferReason(b);
  return r ? `<div class="text-[10px] text-amber-800 font-semibold mt-0.5">⏳ ${_escHtml(r.text)}</div>` : "";
}

function renderPlacedBlocksTable(schedule) {
  const tbody = document.getElementById("placedBlocksTableBody");
  if (!tbody) return;
  const blocks = (schedule && schedule.blocks) || [];

  if (blocks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="py-4 text-center text-slate-400 italic">Chưa có khối công việc nào được xếp.</td></tr>`;
    return;
  }

  const activeNow = getActiveNowDate();
  tbody.innerHTML = blocks
    .map((b) => {
      const gDay = typeof b.start_slot === "number" ? Math.floor(b.start_slot / 96) : 0;
      const dObj = getDayDate(gDay);
      const bTemp = getBlockTemporalState(dObj, b.start_time, b.end_time, activeNow);
      const tBadge =
        bTemp.status === "ACTIVE"
          ? `<span class="px-1 py-0.2 rounded bg-emerald-600 text-white text-[9px] font-bold">▶ LIVE</span>`
          : bTemp.status === "PAST"
            ? `<span class="px-1 py-0.2 rounded bg-slate-200 text-slate-600 text-[9px]">Qua</span>`
            : "";
      const dlInfo = resolveDeadlineDisplay(b, activeNow);
      const reasonTags = (b.reasons || [])
        .filter((r) => r && r.code && r.code !== "ESTIMATE_BUFFER")
        .map((r) => `<span class="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 mono text-[9px] font-bold">${_escHtml(r.code)}</span>`)
        .join(" ");

      return `
      <tr class="hover:bg-slate-50 ${bTemp.status === "PAST" ? "opacity-75" : ""}">
        <td class="py-1.5 px-2.5 font-bold mono text-indigo-700">${_escHtml(b.block_id)}</td>
        <td class="py-1.5 px-2.5 font-semibold text-slate-800">${_escHtml(b.title)}</td>
        <td class="py-1.5 px-2.5 mono text-slate-600">${b.chunk_index}/${b.total_chunks}</td>
        <td class="py-1.5 px-2.5 font-semibold text-emerald-700 mono whitespace-nowrap">${_escHtml(formatBlockDateTimeText(b))} ${tBadge}</td>
        <td class="py-1.5 px-2.5 whitespace-nowrap">${energyLevelBadgeHtml(b.energy_level)}</td>
        <td class="py-1.5 px-2.5 mono">${formatBlockDuration(b)}</td>
        <td class="py-1.5 px-2.5 mono text-slate-600 whitespace-nowrap">${_escHtml(dlInfo.dateText)} ${dlInfo.badgeHtml}</td>
        <td class="py-1.5 px-2.5 text-slate-600"><div class="flex flex-wrap gap-1 mb-0.5">${reasonTags}</div>${_escHtml(b.reason || "")}${bufferReasonText(b)}</td>
      </tr>`;
    })
    .join("");
}

// ============================================================================
// LAB ANALYTICAL WORKSPACES: SINGLE / COMPARE A-B / RESILIENCE & DETERMINISM
// ============================================================================

async function switchWorkbenchMode(mode) {
  state.workbenchMode = mode;
  const tabMap = {
    SINGLE: { btn: "btnLabTabSingle", panel: "singleGridPanel" },
    COMPARE: { btn: "btnLabTabCompare", panel: "compareGridPanel" },
    RESILIENCE: { btn: "btnLabTabResilience", panel: "labPanelResilience" },
  };
  for (const [k, cfg] of Object.entries(tabMap)) {
    const btn = document.getElementById(cfg.btn);
    const panel = document.getElementById(cfg.panel);
    const active = k === mode;
    if (btn) {
      btn.className = active
        ? "px-3.5 py-1.5 text-xs font-bold rounded-md bg-white text-indigo-700 shadow-sm transition flex items-center gap-1.5"
        : "px-3.5 py-1.5 text-xs font-semibold rounded-md text-slate-600 hover:text-slate-900 transition flex items-center gap-1.5";
    }
    panel?.classList.toggle("hidden", !active);
  }

  if (mode === "COMPARE") {
    await runDualComparison();
  } else if (mode === "RESILIENCE") {
    populateOverrunSelect();
  } else {
    renderMainGrid();
  }
}

async function runComparisonPreset(leftAlgo, rightAlgo) {
  const selL = document.getElementById("compareAlgoLeft");
  const selR = document.getElementById("compareAlgoRight");
  if (selL) selL.value = leftAlgo;
  if (selR) selR.value = rightAlgo;
  if (state.workbenchMode !== "COMPARE") {
    await switchWorkbenchMode("COMPARE");
  } else {
    await runDualComparison();
  }
}

function _formatDeltaChip(diff, unit = "", higherIsBetter = true, decimals = 1) {
  const num = Number(diff || 0);
  if (Math.abs(num) < 0.05) {
    return `<span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 mono text-[10px]">0${unit} (Hòa)</span>`;
  }
  const good = higherIsBetter ? num > 0 : num < 0;
  const sign = num > 0 ? "+" : "";
  const cls = good ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800";
  return `<span class="px-1.5 py-0.5 rounded ${cls} font-bold mono text-[10px]">${sign}${num.toFixed(decimals)}${unit} ${good ? "✓ Tốt hơn" : ""}</span>`;
}

function _formatDiffPlacementCell(slot, timeRange, energy, slotDateFallback = null) {
  if (slot === null || slot === undefined || timeRange === "UNPLACED") {
    return `<span class="px-1.5 py-0.5 rounded bg-rose-100 text-rose-800 font-bold mono text-[10px]">UNPLACED</span>`;
  }
  const gDay = Math.floor(Number(slot) / 96);
  const viShort = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"][gDay % 7];
  const dObj = getDayDate(gDay);
  return `
    <div class="font-semibold text-slate-800 mono">${viShort} · ${formatDateDDMMYYYY(dObj)}</div>
    <div class="flex items-center gap-1.5 mt-0.5">
      <span class="text-[11px] text-slate-600 mono">${_escHtml(timeRange)}</span>
      ${energyLevelBadgeHtml(energy)}
    </div>`;
}

function renderLastComparisonDiffTable() {
  const tbody = document.getElementById("compareDiffTableBody");
  if (!tbody) return;
  const c = state.lastComparison?.comparison;
  const diffs = c?.block_diffs || [];
  const onlyChanged = document.getElementById("chkOnlyChangedDiff")?.checked ?? true;
  const filtered = onlyChanged ? diffs.filter((d) => d.changed) : diffs;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="py-5 text-center text-slate-500 italic">${
      diffs.length === 0
        ? "Chưa có dữ liệu so sánh."
        : "Không có phiên nào khác vị trí giữa 2 thuật toán (bỏ chọn bộ lọc ở trên để xem toàn bộ)."
    }</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered
    .map((d) => {
      const chunkSuffix = d.total_chunks > 1 ? ` (${d.chunk_index}/${d.total_chunks})` : "";
      const eDelta =
        d.right_energy !== null && d.left_energy !== null && d.right_energy !== undefined && d.left_energy !== undefined
          ? Number(d.right_energy) - Number(d.left_energy)
          : null;
      let deltaHtml = `<span class="text-slate-400 text-[11px]">Giữ nguyên</span>`;
      if (d.changed) {
        const slotDiffH = d.delta_slots !== null && d.delta_slots !== undefined ? (d.delta_slots * 15) / 60 : null;
        const moveText =
          slotDiffH === null
            ? "Trạng thái xếp khác"
            : slotDiffH === 0
              ? "Đổi độ dài"
              : slotDiffH < 0
                ? `Sớm hơn ${Math.abs(slotDiffH).toFixed(1)}h`
                : `Chuyển tới +${slotDiffH.toFixed(1)}h`;
        const eBadge =
          eDelta !== null && Math.abs(eDelta) >= 0.1
            ? `<div class="mt-0.5 text-[10px] font-bold mono ${eDelta > 0 ? "text-emerald-700" : "text-amber-700"}">${eDelta > 0 ? "↑" : "↓"} E ${eDelta > 0 ? "+" : ""}${eDelta.toFixed(1)}</div>`
            : "";
        deltaHtml = `<span class="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-800 font-semibold text-[10px] inline-block">${moveText}</span>${eBadge}`;
      }
      const rCodes = (d.right_reasons || [])
        .map((code) => `<span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 mono text-[9px] font-bold">${_escHtml(code)}</span>`)
        .join(" ");

      return `
        <tr class="hover:bg-slate-50 ${d.changed ? "bg-indigo-50/20" : ""}">
          <td class="py-2 px-3">
            <div class="font-bold text-slate-900">${_escHtml(d.title)}${chunkSuffix}</div>
            <div class="text-[10px] text-slate-500 mono">${_escHtml(d.task_id)} · Load L${d.cognitive_load ?? 2} · P${d.priority ?? 3}</div>
          </td>
          <td class="py-2 px-3">${_formatDiffPlacementCell(d.left_slot, d.left_time, d.left_energy)}</td>
          <td class="py-2 px-3">${_formatDiffPlacementCell(d.right_slot, d.right_time, d.right_energy)}</td>
          <td class="py-2 px-3">${deltaHtml}</td>
          <td class="py-2 px-3"><div class="flex flex-wrap gap-1">${rCodes || `<span class="text-slate-400">--</span>`}</div></td>
        </tr>`;
    })
    .join("");
}

async function runDualComparison() {
  const algoLeft = document.getElementById("compareAlgoLeft")?.value || "GREEDY_EDF_FIRST_FIT";
  const algoRight = document.getElementById("compareAlgoRight")?.value || "SCORED_GREEDY";

  try {
    updateLabGridDateHeaders();
    const res = await fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algo_left: algoLeft,
        algo_right: algoRight,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    state.lastComparison = data;

    const left = data.left;
    const right = data.right;
    const c = data.comparison;
    const lm = left.metrics || {};
    const rm = right.metrics || {};

    document.getElementById("compareLeftHeader").textContent =
      `Trái (A): ${left.solver_used} (${left.execution_time_ms.toFixed(2)} ms | Phân mảnh: ${(left.summary.fragmentation_index * 100).toFixed(1)}%)`;
    document.getElementById("compareRightHeader").textContent =
      `Phải (B): ${right.solver_used} (${right.execution_time_ms.toFixed(2)} ms | Phân mảnh: ${(right.summary.fragmentation_index * 100).toFixed(1)}%)`;

    // Layer 1: Executive Verdict Card
    const verdictEl = document.getElementById("compareVerdictBanner");
    if (verdictEl) {
      const winner = c.verdict_winner || "TIE";
      const winnerBadge =
        winner === "RIGHT"
          ? `<span class="px-2.5 py-1 rounded-full bg-emerald-600 text-white font-bold mono text-[11px]">🏆 KHUYẾN NGHỊ: ${_escHtml(c.algo_right)} (B)</span>`
          : winner === "LEFT"
            ? `<span class="px-2.5 py-1 rounded-full bg-indigo-600 text-white font-bold mono text-[11px]">🏆 KHUYẾN NGHỊ: ${_escHtml(c.algo_left)} (A)</span>`
            : `<span class="px-2.5 py-1 rounded-full bg-slate-700 text-white font-bold mono text-[11px]">🤝 TƯƠNG ĐƯƠNG TRÊN BỘ DỮ LIỆU NÀY</span>`;

      const highlightsHtml = (c.verdict_highlights || [])
        .map((h) => `<li class="text-slate-700">• ${_escHtml(h)}</li>`)
        .join("");

      verdictEl.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div class="font-bold text-slate-900 text-xs uppercase tracking-wide">📌 Đúc Kết Thực Nghiệm (Executive Verdict)</div>
          <div class="flex items-center gap-2">
            <span class="px-2 py-0.5 rounded bg-white border border-slate-200 mono text-[11px] text-slate-700">${c.different_block_placements}/${c.total_chunks_compared} phiên đổi vị trí</span>
            ${winnerBadge}
          </div>
        </div>
        <ul class="space-y-1 text-xs">${highlightsHtml}</ul>`;
    }

    // Layer 2: 9-Metric Scorecard Table
    const rowsSpec = [
      ["Vi phạm cứng H1–H5", `${c.left_hard_violations ?? left.summary.hard_constraint_violations}`, `${c.right_hard_violations ?? right.summary.hard_constraint_violations}`, _formatDeltaChip((c.right_hard_violations ?? 0) - (c.left_hard_violations ?? 0), "", false, 0)],
      ["Tỷ lệ đạt Deadline", `${Number(c.left_deadline_rate).toFixed(1)}%`, `${Number(c.right_deadline_rate).toFixed(1)}%`, _formatDeltaChip(c.right_deadline_rate - c.left_deadline_rate, "%", true, 1)],
      ["Task đã xếp hoàn chỉnh", `${c.left_placed_tasks ?? left.summary.tasks_placed}/${c.total_tasks ?? left.summary.total_tasks_requested}`, `${c.right_placed_tasks ?? right.summary.tasks_placed}/${c.total_tasks ?? right.summary.total_tasks_requested}`, _formatDeltaChip((c.right_placed_tasks ?? 0) - (c.left_placed_tasks ?? 0), " task", true, 0)],
      ["Khớp Peak Circadian (Load≥2)", `${Number(c.left_deep_peak_match_pct ?? lm.deep_peak_match_pct ?? 100).toFixed(1)}%`, `${Number(c.right_deep_peak_match_pct ?? rm.deep_peak_match_pct ?? 100).toFixed(1)}%`, _formatDeltaChip((c.right_deep_peak_match_pct ?? 100) - (c.left_deep_peak_match_pct ?? 100), "%", true, 1)],
      ["Khớp Peak Chung (Tất cả block)", `${Number(c.left_peak_match_pct ?? 100).toFixed(1)}%`, `${Number(c.right_peak_match_pct ?? 100).toFixed(1)}%`, _formatDeltaChip((c.right_peak_match_pct ?? 100) - (c.left_peak_match_pct ?? 100), "%", true, 1)],
      ["Trung bình Mức Năng Lượng", `${Number(c.left_avg_energy ?? 0).toFixed(2)}`, `${Number(c.right_avg_energy ?? 0).toFixed(2)}`, _formatDeltaChip((c.right_avg_energy ?? 0) - (c.left_avg_energy ?? 0), "", true, 2)],
      ["Experience Rating (1=Thoải mái→5)", `${Number(c.left_experience_rating ?? left.summary.experience_rating).toFixed(2)}`, `${Number(c.right_experience_rating ?? right.summary.experience_rating).toFixed(2)}`, _formatDeltaChip((c.right_experience_rating ?? 1) - (c.left_experience_rating ?? 1), "", false, 2)],
      ["Chuyển ngữ cảnh (Ít hơn = đỡ mệt)", `${c.left_context_switches ?? 0} lần (${c.left_batched_pairs ?? 0} gộp)`, `${c.right_context_switches ?? 0} lần (${c.right_batched_pairs ?? 0} gộp)`, _formatDeltaChip((c.right_context_switches ?? 0) - (c.left_context_switches ?? 0), " lần", false, 0)],
      ["Độ phân mảnh & Thời gian giải", `${(c.left_fragmentation * 100).toFixed(1)}% · ${c.left_exec_ms.toFixed(2)}ms`, `${(c.right_fragmentation * 100).toFixed(1)}% · ${c.right_exec_ms.toFixed(2)}ms`, _formatDeltaChip((c.right_fragmentation - c.left_fragmentation) * 100, "% mảnh", false, 1)],
    ];

    if (left.health_v21?.available && right.health_v21?.available) {
      const lh = left.health_v21;
      const rh = right.health_v21;
      const lApk = lh.pillars?.p2?.achievable_heavy_peak_match_pct ?? 100;
      const rApk = rh.pillars?.p2?.achievable_heavy_peak_match_pct ?? 100;
      const lShk = lh.pillars?.p4?.shock_25_pct ?? 100;
      const rShk = rh.pillars?.p4?.shock_25_pct ?? 100;
      const lMaxD = lh.pillars?.p3?.max_daily_total_min ?? 0;
      const rMaxD = rh.pillars?.p3?.max_daily_total_min ?? 0;
      rowsSpec.push(
        ["Phán quyết Máy `v2.1` (Verdict)", _escHtml(lh.verdict), _escHtml(rh.verdict), _formatDeltaChip((rh.critical_count ?? 0) - (lh.critical_count ?? 0), " crit", false, 0)],
        ["Chịu Sốc +25% giờ (`Shock@+25%`)", `${Number(lShk).toFixed(1)}%`, `${Number(rShk).toFixed(1)}%`, _formatDeltaChip(rShk - lShk, "%", true, 1)],
        ["Khớp Peak khả thi (`APk%`)", `${Number(lApk).toFixed(1)}%`, `${Number(rApk).toFixed(1)}%`, _formatDeltaChip(rApk - lApk, "%", true, 1)],
        ["Đỉnh tổng tải ngày (`MaxD` lớp+tự học)", `${lMaxD}p`, `${rMaxD}p`, _formatDeltaChip(rMaxD - lMaxD, "p", false, 0)]
      );
    }

    document.getElementById("compareMetricsBox").innerHTML = `
      <table class="w-full text-left text-xs">
        <thead class="bg-slate-50 text-slate-600 border-b border-slate-200">
          <tr>
            <th class="py-2 px-3">Chỉ Số Đánh Giá Khoa Học</th>
            <th class="py-2 px-3">Trái (A): ${_escHtml(left.solver_used)}</th>
            <th class="py-2 px-3 text-indigo-900">Phải (B): ${_escHtml(right.solver_used)}</th>
            <th class="py-2 px-3">Chênh Lệch (B − A)</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          ${rowsSpec
            .map(
              ([lbl, lv, rv, delta]) => `
            <tr class="hover:bg-slate-50">
              <td class="py-1.5 px-3 font-semibold text-slate-700">${lbl}</td>
              <td class="py-1.5 px-3 mono text-slate-600">${lv}</td>
              <td class="py-1.5 px-3 mono font-bold text-indigo-900">${rv}</td>
              <td class="py-1.5 px-3">${delta}</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;

    // Layer 3: Task-by-Task Placement Diff Table
    renderLastComparisonDiffTable();

    // Layer 4: Full Grids inside collapsible section
    document.getElementById("compareLeftTbody").innerHTML = buildScheduleRowsHTML(left, {
      foldSleep: true,
      stepSlots: 2,
      diffOtherSchedule: right,
    });
    document.getElementById("compareRightTbody").innerHTML = buildScheduleRowsHTML(right, {
      foldSleep: true,
      stepSlots: 2,
      diffOtherSchedule: left,
    });
  } catch (err) {
    console.error("Dual comparison failed:", err);
  }
}

// ============================================================================
// LAB TAB 3: RESILIENCE LAB (T04/T05) & 3X DETERMINISM LEDGER
// ============================================================================

async function runDisruptionRepair(mode) {
  const title = document.getElementById("inpDisruptTitle")?.value.trim() || "Sự kiện đột xuất";
  const day = document.getElementById("inpDisruptDay")?.value || "Monday";
  const start = document.getElementById("inpDisruptStart")?.value || "07:30";
  const end = document.getElementById("inpDisruptEnd")?.value || "09:30";
  const algorithm = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";

  try {
    const res = await fetch("/api/repair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algorithm,
        schedule: state.currentSchedule,
        mode,
        disruption: {
          event_id: `DISRUPT_${Date.now().toString().slice(-3)}`,
          title,
          day_of_week: day,
          start_time: start,
          end_time: end,
        },
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const rep = await res.json();

    state.currentSchedule = rep.schedule;
    state.repairedMovedIds = new Set(
      (rep.changes || []).filter((ch) => ch.status === "MOVED").map((ch) => ch.block_id)
    );

    state.commitments.fixed_events.push({
      event_id: "DISRUPTION",
      title: `⚡ ${title}`,
      day_of_week: day,
      start_time: start,
      end_time: end,
      category: "DISRUPTION",
    });
    renderFixedEventsList();

    renderKpiCards(state.currentSchedule);
    renderHealthV21Panels(state.currentSchedule);
    renderOverloadBox(state.currentSchedule);
    renderMainGrid();
    renderPlacedBlocksTable(state.currentSchedule);
    renderStudentViews();
    evaluateCurrentScheduleV21();

    const logBox = document.getElementById("repairLogPanel");
    if (logBox) {
      logBox.classList.remove("hidden");
      const movedRows = (rep.changes || [])
        .filter((c) => c.status !== "UNCHANGED")
        .map(
          (c) =>
            `<div class="text-slate-700 py-0.5">• <strong class="mono">${_escHtml(c.block_id)}</strong>: ${_escHtml(c.old_day)} ${c.old_start_time}–${c.old_end_time} ➔ <strong class="text-blue-700">${_escHtml(c.new_day || "UNPLACED")} ${c.new_start_time || ""}–${c.new_end_time || ""}</strong></div>`
        )
        .join("");

      logBox.innerHTML = `
        <div class="flex items-center justify-between">
          <div class="font-bold text-indigo-900">🛠️ Kết Quả Tái Lập Lịch (${_escHtml(rep.repair_mode)})</div>
          <span class="px-2 py-0.5 rounded font-bold mono ${rep.stability_score >= 90 ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-900"}">Độ ổn định: ${rep.stability_score.toFixed(1)}%</span>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs bg-slate-50 p-2.5 rounded-lg border border-slate-200">
          <div>S_stability: <strong class="mono text-emerald-700">${rep.stability_score.toFixed(1)}%</strong></div>
          <div>Phiên dời chỗ: <strong class="mono text-indigo-700">${rep.moved_blocks_count} phiên</strong></div>
          <div>Đè trực tiếp: <strong class="mono">${rep.directly_hit_blocks}</strong></div>
          <div>Xử lý: <strong class="mono">${rep.execution_time_ms.toFixed(2)} ms</strong></div>
        </div>
        <div class="space-y-0.5 text-xs">${movedRows || `<div class="text-emerald-700 italic">Không có phiên học nào bị dời vị trí.</div>`}</div>
      `;
    }
  } catch (err) {
    console.error("Disruption repair error:", err);
  }
}

async function runDisruptionComparison() {
  const title = document.getElementById("inpDisruptTitle")?.value.trim() || "Sự kiện đột xuất";
  const day = document.getElementById("inpDisruptDay")?.value || "Monday";
  const start = document.getElementById("inpDisruptStart")?.value || "07:30";
  const end = document.getElementById("inpDisruptEnd")?.value || "09:30";
  const algorithm = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";

  try {
    const res = await fetch("/api/repair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algorithm,
        schedule: state.currentSchedule,
        mode: "COMPARE_BOTH",
        disruption: {
          event_id: "DISRUPT_CMP",
          title,
          day_of_week: day,
          start_time: start,
          end_time: end,
        },
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const cmp = data.comparison;
    const savedBlocks = Math.max(0, (cmp.rebuild_moved_blocks || 0) - (cmp.local_moved_blocks || 0));

    const logBox = document.getElementById("repairLogPanel");
    if (logBox) {
      logBox.classList.remove("hidden");
      logBox.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="font-bold text-indigo-900">⚖️ Đối Chứng T04: Local Repair (M4) vs Full Rebuild — Sự cố "${_escHtml(title)}"</div>
          <span class="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-bold text-[11px]">Local Repair giữ ổn định hơn +${(cmp.local_stability_pct - cmp.rebuild_stability_pct).toFixed(1)}% (bảo toàn ${savedBlocks} phiên)</span>
        </div>
        <div class="space-y-2.5 pt-1">
          <div>
            <div class="flex justify-between text-xs font-semibold text-emerald-800 mb-1">
              <span>1. Local Insertion (M4) — Chỉ dời block bị đè</span>
              <span class="mono">${cmp.local_stability_pct.toFixed(1)}% ổn định (${cmp.local_moved_blocks} block dời)</span>
            </div>
            <div class="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
              <div class="h-full bg-emerald-500 rounded-full" style="width: ${Math.min(100, Math.max(0, cmp.local_stability_pct))}%"></div>
            </div>
          </div>
          <div>
            <div class="flex justify-between text-xs font-semibold text-rose-800 mb-1">
              <span>2. Full Greedy Rebuild — Xếp lại từ đầu (Domino Effect)</span>
              <span class="mono">${cmp.rebuild_stability_pct.toFixed(1)}% ổn định (${cmp.rebuild_moved_blocks} block xáo trộn)</span>
            </div>
            <div class="w-full h-3 bg-slate-100 rounded-full overflow-hidden">
              <div class="h-full bg-rose-500 rounded-full" style="width: ${Math.min(100, Math.max(0, cmp.rebuild_stability_pct))}%"></div>
            </div>
          </div>
        </div>
      `;
    }
  } catch (err) {
    console.error("Disruption comparison error:", err);
  }
}

async function runTaskOverrunSimulation() {
  const taskId = document.getElementById("inpOverrunTaskSelect")?.value;
  const extraMin = parseInt(document.getElementById("inpOverrunExtraMin")?.value || "45", 10);
  if (!taskId) return;

  try {
    const res = await fetch("/api/progress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        task_id: taskId,
        extra_min: extraMin,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    const tObj = state.tasks.find((t) => (t.task_id || t.id) === taskId);
    const oldEstimate = tObj ? tObj.duration_min || tObj.estimate_min : null;
    if (tObj) tObj.duration_min = data.new_estimate_min ?? data.new_duration_min;
    const estimateLine =
      data.new_estimate_min && data.new_estimate_min !== data.new_duration_min
        ? `<div>• Ước lượng gốc: <span class="mono">${oldEstimate}p ➔ <strong>${data.new_estimate_min}p</strong></span> · bộ đệm tự tính lại</div>`
        : "";

    state.currentSchedule = data.after_schedule;
    syncAllLeftPanels();
    renderKpiCards(state.currentSchedule);
    renderHealthV21Panels(state.currentSchedule);
    renderOverloadBox(state.currentSchedule);
    renderMainGrid();
    renderPlacedBlocksTable(state.currentSchedule);
    renderStudentViews();
    evaluateCurrentScheduleV21();

    const logBox = document.getElementById("repairLogPanel");
    if (logBox) {
      logBox.classList.remove("hidden");
      logBox.innerHTML = `
        <div class="font-bold text-slate-900">⏱️ Kết Quả Mô Phỏng Lố Giờ (T05 / UC9)</div>
        <div class="text-xs text-slate-700 space-y-1 bg-slate-50 p-3 rounded-lg border border-slate-200">
          ${estimateLine}
          <div>• Task <strong class="mono">${_escHtml(data.task_id)}</strong> tăng thời lượng: <span class="mono">${data.old_duration_min}p ➔ <strong>${data.new_duration_min}p</strong> (+${extraMin}p)</span></div>
          <div>• Hiệu ứng dây chuyền: <strong class="mono text-indigo-700">${data.shifted_blocks_count} phiên học phía sau bị dịch chuyển</strong></div>
        </div>
      `;
    }
  } catch (err) {
    console.error("Overrun simulation error:", err);
  }
}

function _buildDeterminismRowHtml(algo, data) {
  const statusBadge = data.is_deterministic
    ? `<span class="px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full font-bold mono text-[10px]">✓ 3x IDENTICAL PASS</span>`
    : `<span class="px-2 py-0.5 bg-rose-100 text-rose-800 rounded-full font-bold mono text-[10px]">✕ FAILED</span>`;
  return `
    <tr class="hover:bg-slate-50">
      <td class="py-2 px-3 font-bold text-slate-800 mono">${_escHtml(algo)}</td>
      <td class="py-2 px-3">${statusBadge}</td>
      <td class="py-2 px-3 mono text-slate-600 text-[11px]">${_escHtml(data.unique_hash || "")}</td>
      <td class="py-2 px-3 mono text-slate-700">[${(data.latencies_ms || []).map((x) => Number(x).toFixed(2) + "ms").join(", ")}]</td>
    </tr>`;
}

async function runDeterminismCheck() {
  const algorithm = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";
  try {
    const res = await fetch("/api/determinism-check", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algorithm,
        runs: 3,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    const banner = document.getElementById("determinismBanner");
    const textEl = document.getElementById("determinismBannerText");
    if (banner && textEl) {
      banner.classList.remove("hidden");
      textEl.innerHTML = `
        <strong>🔒 ${_escHtml(algorithm)} (${data.runs}x Runs):</strong>
        <span class="px-1.5 py-0.5 bg-emerald-600 text-white rounded font-bold mono">${data.is_deterministic ? "100% IDENTICAL PASS" : "FAILED"}</span> |
        SHA-256 = <span class="mono text-amber-300">${_escHtml(data.unique_hash)}</span>
      `;
    }
    const ledgerBody = document.getElementById("determinismLedgerBody");
    if (ledgerBody) {
      ledgerBody.innerHTML = _buildDeterminismRowHtml(algorithm, data);
    }
  } catch (err) {
    console.error("Determinism check error:", err);
  }
}

async function runAllSolversDeterminismLedger() {
  const ledgerBody = document.getElementById("determinismLedgerBody");
  if (!ledgerBody) return;
  const algos = [
    "GREEDY_EDF_FIRST_FIT",
    "GREEDY_LST_BEST_FIT",
    "GREEDY_WSPT_SMITH_RULE",
    "BACKTRACKING_BRANCH_AND_BOUND",
    "SCORED_GREEDY",
    "HYBRID_ALNS",
  ];
  ledgerBody.innerHTML = `<tr><td colspan="4" class="py-4 text-center text-indigo-700 font-semibold">⏳ Đang chạy kiểm chứng SHA-256 (3x runs × 6 solvers)...</td></tr>`;

  try {
    const rows = [];
    for (const algo of algos) {
      const res = await fetch("/api/determinism-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          commitments: state.commitments,
          tasks: state.tasks,
          algorithm: algo,
          runs: 3,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      rows.push(_buildDeterminismRowHtml(algo, data));
    }
    ledgerBody.innerHTML = rows.join("");
  } catch (err) {
    ledgerBody.innerHTML = `<tr><td colspan="4" class="py-4 text-center text-rose-600 font-semibold">Lỗi kiểm chứng: ${_escHtml(err.message)}</td></tr>`;
  }
}

async function exportSchedule(fmt) {
  try {
    const res = await fetch(`/api/export/${fmt}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        schedule: state.currentSchedule,
      }),
    });
    if (!res.ok) throw new Error(`Export ${fmt} failed`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fmt === "json" ? "schedule_output.json" : `smartschedule_baseline.${fmt}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    console.error("Export failed:", err);
  }
}

async function importJsonFile(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const raw = JSON.parse(text);
    if (raw.commitments && raw.tasks) {
      state.commitments = raw.commitments;
      state.tasks = raw.tasks;
    } else if (Array.isArray(raw)) {
      state.tasks = raw;
    } else if (raw.fixed_events || raw.sleep_schedule) {
      state.commitments = raw;
    }
    syncAllLeftPanels();
    await solveSchedule();
  } catch (err) {
    console.error("Import JSON error:", err);
  } finally {
    event.target.value = "";
  }
}

// ============================================================================
// STUDENT APP MODE CONTROLLER (CLEAN, MINIMALIST, USER-FACING)
// ============================================================================

function syncTaskModalModeVisibility() {
  const isStudent = state.appMode === "STUDENT";
  document.body.classList.toggle("app-mode-student", isStudent);
  const advDet = document.getElementById("stTaskAdvDetails");
  if (advDet) {
    if (!isStudent) {
      advDet.open = true;
    } else if (!state.editingTaskId) {
      advDet.open = false;
    }
  }
}

function switchAppMode(mode) {
  state.appMode = mode;
  document.body.classList.toggle("app-mode-student", mode === "STUDENT");
  const btnStudent = document.getElementById("btnAppModeStudent");
  const btnLab = document.getElementById("btnAppModeLab");
  const studentLayout = document.getElementById("studentAppLayout");
  const labLayout = document.getElementById("labWorkbenchLayout");
  const studentActions = document.getElementById("studentHeaderActions");
  const labActions = document.getElementById("labHeaderActions");
  const modeBadge = document.getElementById("headerModeBadge");

  if (mode === "STUDENT") {
    if (btnStudent) btnStudent.className = "px-3 py-1 text-xs font-bold rounded-lg bg-indigo-600 text-white shadow transition flex items-center gap-1";
    if (btnLab) btnLab.className = "px-3 py-1 text-xs font-semibold rounded-lg text-slate-300 hover:text-white transition flex items-center gap-1";
    studentLayout?.classList.remove("hidden");
    labLayout?.classList.add("hidden");
    studentActions?.classList.remove("hidden");
    labActions?.classList.add("hidden");
    if (modeBadge) {
      modeBadge.textContent = "STUDENT APP";
      modeBadge.className = "px-2 py-0.5 text-[10px] font-bold bg-indigo-500/30 text-indigo-300 border border-indigo-400/30 rounded-full mono uppercase";
    }
    syncTaskModalModeVisibility();
    updateTemporalContextUI();
    renderStudentViews();
    requestAnimationFrame(() => updateObservedViewportRange());
  } else {
    if (btnLab) btnLab.className = "px-3 py-1 text-xs font-bold rounded-lg bg-emerald-600 text-white shadow transition flex items-center gap-1";
    if (btnStudent) btnStudent.className = "px-3 py-1 text-xs font-semibold rounded-lg text-slate-300 hover:text-white transition flex items-center gap-1";
    labLayout?.classList.remove("hidden");
    studentLayout?.classList.add("hidden");
    labActions?.classList.remove("hidden");
    studentActions?.classList.add("hidden");
    if (modeBadge) {
      modeBadge.textContent = "LAB BENCHMARK";
      modeBadge.className = "px-2 py-0.5 text-[10px] font-bold bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 rounded-full mono uppercase";
    }
    syncTaskModalModeVisibility();
    syncLabParamsUI();
    populateOverrunSelect();
    updateTemporalContextUI();
    renderMainGrid();
  }
}

function switchStudentView(view) {
  state.studentView = view;
  const tabs = {
    WEEK: { btn: "btnStTabWeek", view: "stViewWeek" },
    TODAY: { btn: "btnStTabToday", view: "stViewToday" },
    TASKS: { btn: "btnStTabTasks", view: "stViewTasks" },
  };

  for (const [k, cfg] of Object.entries(tabs)) {
    const btn = document.getElementById(cfg.btn);
    const viewEl = document.getElementById(cfg.view);
    if (k === view) {
      if (btn) btn.className = "px-3.5 py-1.5 text-xs font-bold rounded-lg bg-white text-indigo-700 shadow-sm transition flex items-center gap-1.5";
      viewEl?.classList.remove("hidden");
    } else {
      if (btn) btn.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg text-slate-600 hover:text-slate-900 transition flex items-center gap-1.5";
      viewEl?.classList.add("hidden");
    }
  }

  renderStudentViews();
  if (view === "WEEK") {
    requestAnimationFrame(() => updateObservedViewportRange());
  }
}

function renderStudentViews() {
  updateTemporalContextUI();
  renderStudentSummary();
  renderHealthV21Panels(state.currentSchedule);
  renderStudentOverloadBanner();
  if (state.studentView === "WEEK") {
    renderStudentWeekCalendar();
  } else if (state.studentView === "TODAY") {
    renderStudentTodayView();
  } else if (state.studentView === "TASKS") {
    renderStudentTaskQueue();
    renderStudentMainHabits();
  }
}

async function shiftStudentCalendarWeek(delta) {
  const nextOffset = Math.max(0, Math.min(1, (state.viewWeekOffset || 0) + delta));
  if (nextOffset === 1 && Number(state.commitments?.horizon_days || 7) < 14) {
    state.commitments.horizon_days = 14;
    state.viewWeekOffset = 1;
    savePersistedStudentState();
    await solveSchedule();
    requestAnimationFrame(() => scrollToCalendarDay(7));
    return;
  }
  state.viewWeekOffset = nextOffset;
  savePersistedStudentState();
  updateTemporalContextUI();
  renderStudentViews();
  renderMainGrid();
  requestAnimationFrame(() => scrollToCalendarDay(nextOffset * 7));
}

async function changeStudentHorizonDays(val) {
  const days = parseInt(val, 10) >= 14 ? 14 : 7;
  state.commitments.horizon_days = days;
  if (days < 14 && state.viewWeekOffset > 0) {
    state.viewWeekOffset = 0;
  }
  savePersistedStudentState();
  await solveSchedule();
}

async function jumpToCurrentWeek() {
  state.commitments.planning_week_start = getCurrentMondayIso();
  state.commitments.now = getCurrentLocalIso();
  state.useRealTimeNow = true;
  state.viewWeekOffset = 0;
  const activeNow = getActiveNowDate();
  const jsDay = activeNow.getDay();
  state.todayDay = DAYS_EN[jsDay === 0 ? 6 : jsDay - 1];
  savePersistedStudentState();
  syncAllLeftPanels();
  await solveSchedule();
  requestAnimationFrame(() => scrollToTodayColumn());
}

function _dayColWrapperClass(tState) {
  const base = "flex-shrink-0 w-[265px] sm:w-[280px] rounded-2xl shadow-sm overflow-hidden flex flex-col ";
  if (tState === "TODAY") {
    return base + "bg-white border-2 border-indigo-500 ring-2 ring-indigo-100";
  }
  if (tState === "PAST") {
    return base + "bg-slate-50/70 border border-slate-200 opacity-85";
  }
  return base + "bg-white border border-slate-200";
}

function _ensureWeek2DayColumns(showWeek2) {
  const holder = document.getElementById("stExtraWeek2Columns");
  if (!holder) return;
  if (!showWeek2) {
    if (holder.childElementCount > 0) holder.innerHTML = "";
    return;
  }
  if (holder.childElementCount === 7) return;
  const sleepCfg = state.commitments?.sleep_schedule || {};
  const sStart = sleepCfg.daily_start_time || sleepCfg.start || "23:30";
  const sEnd = sleepCfg.daily_end_time || sleepCfg.end || "06:30";
  let html = "";
  for (let i = 7; i < 14; i++) {
    html += `
      <div id="stDayColWrapper_${i}" class="${_dayColWrapperClass("FUTURE")}">
        <div class="p-3 bg-indigo-50/40 border-b border-slate-200 flex items-center justify-between gap-1">
          <div>
            <div class="flex items-center gap-1.5">
              <span class="text-xs font-bold text-slate-900">${DAYS_VI[i % 7]}</span>
              <span class="px-1 py-0.2 rounded bg-indigo-100 text-indigo-800 text-[9px] font-bold">T2</span>
              <span id="stDayTemporal_${i}" class="px-1.5 py-0.5 rounded text-[9px] font-bold"></span>
            </div>
            <div id="stDayDate_${i}" class="text-[11px] font-semibold text-slate-600 mono">--/--/----</div>
          </div>
          <span id="stDayHours_${i}" class="text-[11px] font-semibold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full whitespace-nowrap">0h</span>
        </div>
        <div class="bg-slate-800 text-slate-300 text-[10px] px-2.5 py-1 border-b border-slate-700 flex items-center justify-between">
          <span class="st-sleep-window-label">🌙 ${sStart} – ${sEnd} (Ngủ)</span>
          <span class="text-indigo-300 font-medium">Ngủ</span>
        </div>
        <div id="stDayCards_${i}" class="p-2 space-y-2 flex-1 min-h-[360px] bg-slate-50/30"></div>
      </div>`;
  }
  holder.innerHTML = html;
}

function updateDynamicWeekDates() {
  const weekOffset = state.viewWeekOffset || 0;
  const horizonDays = Number(state.commitments?.horizon_days || 7) >= 14 ? 14 : 7;
  _ensureWeek2DayColumns(horizonDays >= 14);

  const horizonStartDate = getDayDate(0);
  const horizonEndDate = getDayDate(horizonDays - 1);
  const activeNow = getActiveNowDate();

  const titleEl = document.getElementById("stWeekHeaderTitle");
  if (titleEl) {
    titleEl.textContent = `Chuỗi Lịch (${horizonDays} ngày): ${formatDateDDMMYYYY(horizonStartDate)} – ${formatDateDDMMYYYY(horizonEndDate)}`;
  }
  const weekLblEl = document.getElementById("stWeekViewLabel");
  if (weekLblEl) weekLblEl.textContent = weekOffset === 1 ? "Tuần 2" : "Tuần 1";
  const horizonSel = document.getElementById("stHorizonDaysSelect");
  if (horizonSel) horizonSel.value = String(horizonDays);

  for (let i = 0; i < horizonDays; i++) {
    const cur = getDayDate(i);
    const tState = getDayTemporalState(cur, activeNow);
    const dEl = document.getElementById(`stDayDate_${i}`);
    if (dEl) dEl.textContent = formatDateDDMMYYYY(cur);

    const tagEl = document.getElementById(`stDayTemporal_${i}`);
    if (tagEl) {
      if (tState === "TODAY") {
        tagEl.textContent = "HÔM NAY";
        tagEl.className = "px-1.5 py-0.5 rounded bg-indigo-600 text-white text-[9px] font-bold";
      } else if (tState === "PAST") {
        tagEl.textContent = "Đã qua";
        tagEl.className = "px-1.5 py-0.5 rounded bg-slate-200 text-slate-600 text-[9px] font-semibold";
      } else {
        tagEl.textContent = "Sắp tới";
        tagEl.className = "px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 text-[9px] font-semibold";
      }
    }

    const wrapEl = document.getElementById(`stDayColWrapper_${i}`);
    if (wrapEl) {
      wrapEl.className = _dayColWrapperClass(tState);
    }
  }
}

function renderStudentSummary() {
  updateDynamicWeekDates();
  syncSleepUI();

  const summary = state.currentSchedule?.summary;
  const tasksCount = state.tasks?.length || 0;
  const blocksCount = state.currentSchedule?.blocks?.length || 0;
  const totalMin = (state.currentSchedule?.blocks || []).reduce((acc, b) => acc + (b.duration_min || 0), 0);
  const totalHours = (totalMin / 60).toFixed(1);

  const elTasks = document.getElementById("stSummaryTasks");
  const elHours = document.getElementById("stSummaryHours");
  const elDeadline = document.getElementById("stSummaryDeadline");
  const elExp = document.getElementById("stSummaryExperience");
  const elViolations = document.getElementById("stSummaryViolations");

  if (elTasks) elTasks.textContent = `${tasksCount} bài tập (${blocksCount} phiên)`;
  if (elHours) elHours.textContent = `${totalHours}h học`;

  if (summary) {
    if (elDeadline) {
      const rate = summary.deadline_satisfaction_rate ?? 100;
      elDeadline.textContent = `✓ ${rate.toFixed(0)}% đúng hạn`;
      elDeadline.className = rate >= 100
        ? "px-2.5 py-1 text-xs font-semibold bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200"
        : "px-2.5 py-1 text-xs font-semibold bg-rose-50 text-rose-700 rounded-full border border-rose-200";
    }
    if (elExp) {
      const rating = summary.experience_rating ?? 1.0;
      const lbl = summary.experience_label || "1 - Comfortable";
      elExp.textContent = `⭐ ${Number(rating).toFixed(1)} (${lbl.split(" - ")[1] || lbl})`;
      elExp.className = rating >= 4.0
        ? "px-2.5 py-1 text-xs font-semibold bg-rose-50 text-rose-700 rounded-full border border-rose-200"
        : rating >= 3.0
          ? "px-2.5 py-1 text-xs font-semibold bg-amber-50 text-amber-800 rounded-full border border-amber-200"
          : "px-2.5 py-1 text-xs font-semibold bg-violet-50 text-violet-700 rounded-full border border-violet-200";
    }
    if (elViolations) {
      const v = summary.hard_constraint_violations ?? 0;
      elViolations.textContent = v === 0 ? "🛡️ 0 vi phạm (H1–H5)" : `⚠️ ${v} vi phạm`;
      elViolations.className = v === 0
        ? "px-2.5 py-1 text-xs font-semibold bg-slate-100 text-slate-700 rounded-full border border-slate-200"
        : "px-2.5 py-1 text-xs font-semibold bg-rose-100 text-rose-800 rounded-full border border-rose-300";
    }
  }

  // Render Early Extension Alert 24-48h Banner
  const alertBox = document.getElementById("stEarlyExtensionAlertBox");
  const alerts = state.currentSchedule?.early_extension_alerts || summary?.early_extension_alerts || [];
  if (alertBox) {
    if (alerts.length > 0) {
      alertBox.classList.remove("hidden");
      alertBox.innerHTML = `
        <div class="flex items-center gap-2">
          <span class="text-base">⏳</span>
          <div>
            <div class="font-bold text-amber-950">Cảnh báo Sớm 24–48h (Early Extension Alert)</div>
            <div class="text-[11px] text-amber-900">${alerts.map((a) => `${a.title || a.task_id}: còn ${a.hours_remaining}h, thiếu ~${a.missing_minutes}p`).join(" · ")}</div>
          </div>
        </div>
        <span class="px-2 py-0.5 bg-amber-200 text-amber-950 rounded-full font-bold text-[10px]">${alerts.length} cảnh báo</span>
      `;
    } else {
      alertBox.classList.add("hidden");
    }
  }
}

function renderStudentOverloadBanner() {
  const banner = document.getElementById("stOverloadBanner");
  if (!banner) return;

  if (state.previewState) {
    banner.classList.remove("hidden");
    const afterS = state.previewState.after_summary || {};
    banner.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span class="font-bold text-indigo-900">👁️ Đang Xem Trước Phương Án (${state.previewState.option_code}):</span>
          <span>Đúng hạn ${afterS.deadline_satisfaction_rate ?? 100}% · Đã xếp ${afterS.tasks_placed ?? "?"}/${afterS.total_tasks_requested ?? "?"} tasks (0 vi phạm cứng).</span>
        </div>
        <div class="flex items-center gap-2">
          <button onclick="applyStudentOverloadPreview()" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-bold">✓ Áp Dụng Phương Án</button>
          <button onclick="undoStudentChange()" class="px-3 py-1 bg-slate-200 hover:bg-slate-300 text-slate-800 rounded-lg font-bold">↩️ Hoàn Tác</button>
        </div>
      </div>`;
    return;
  }

  const ov = state.currentSchedule?.overload;
  const options = ov?.options || [];
  if (!ov || options.length === 0) {
    if (state.undoSnapshot) {
      banner.classList.remove("hidden");
      banner.className = "bg-indigo-50 border border-indigo-200 rounded-2xl p-3 text-xs text-indigo-950 shadow-sm flex items-center justify-between";
      banner.innerHTML = `
        <span>⚡ Đã cập nhật lịch (ổn định). Bạn có thể hoàn tác nếu muốn quay lại trạng thái trước.</span>
        <button onclick="undoStudentChange()" class="px-3 py-1 bg-white border border-indigo-300 hover:bg-indigo-100 text-indigo-900 rounded-lg font-bold">↩️ Hoàn Tác (Undo)</button>`;
    } else {
      banner.classList.add("hidden");
    }
    return;
  }

  banner.className = "bg-rose-50 border-2 border-rose-300 rounded-2xl p-4 text-xs text-rose-950 shadow-sm space-y-2.5";
  banner.classList.remove("hidden");
  banner.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <div class="font-bold text-rose-900">⚠️ Quá tải lịch học (${ov.error_type}) — Thiếu ${ov.shortage_minutes || 0} phút</div>
        <div class="text-[11px] text-rose-800 mt-0.5">${ov.message || ""}</div>
      </div>
      ${state.undoSnapshot ? `<button onclick="undoStudentChange()" class="px-2.5 py-1 bg-white border border-rose-300 rounded-lg font-bold">↩️ Hoàn Tác</button>` : ""}
    </div>
    <div class="flex flex-wrap gap-2">
      ${options
        .slice(0, 4)
        .map(
          (opt) => `
        <button onclick="previewStudentOverloadOption('${opt.option_id || "O1"}', '${opt.code || ""}', '${opt.task || ""}')"
          class="px-3 py-1.5 bg-white hover:bg-indigo-50 border border-rose-200 hover:border-indigo-400 rounded-xl font-semibold text-slate-800 transition flex items-center gap-1.5">
          <span>👁️</span>
          <span>[${opt.code}] ${opt.label || opt.task || opt.option_id}</span>
        </button>`
        )
        .join("")}
    </div>`;
}

function _buildNowDividerHtml(timeStr) {
  return `
    <div class="flex items-center gap-1.5 my-1">
      <span class="h-0.5 flex-1 bg-rose-500"></span>
      <span class="px-1.5 py-0.5 rounded-full bg-rose-600 text-white text-[9px] font-bold mono shadow-sm">🔴 BÂY GIỜ (${timeStr})</span>
      <span class="h-0.5 flex-1 bg-rose-500"></span>
    </div>`;
}

function renderStudentWeekCalendar() {
  if (!state.currentSchedule) return;
  const horizonDays = Number(state.commitments?.horizon_days || 7) >= 14 ? 14 : 7;
  const activeNow = getActiveNowDate();
  const nowSlotExact = (activeNow.getHours() * 60 + activeNow.getMinutes()) / 15;

  for (let globalDayIdx = 0; globalDayIdx < horizonDays; globalDayIdx++) {
    const d = globalDayIdx % 7;
    const isWeek2 = globalDayIdx >= 7;
    const dayName = DAYS_EN[d];
    const targetDayLabel = isWeek2 ? `Next ${dayName}` : dayName;
    const colDate = getDayDate(globalDayIdx);
    const dayTemporal = getDayTemporalState(colDate, activeNow);
    const container = document.getElementById(`stDayCards_${globalDayIdx}`);
    const hoursEl = document.getElementById(`stDayHours_${globalDayIdx}`);
    if (!container) continue;

    // 1. Collect fixed events (fixed commitments recur weekly)
    const dayFixed = [];
    for (const ev of state.commitments?.fixed_events || []) {
      const days = Array.isArray(ev.day_of_week) ? ev.day_of_week : String(ev.day_of_week).split(",").map((s) => s.trim());
      const matches = days.includes("ALL") || days.includes("all") || days.some((x) => x.toLowerCase().startsWith(dayName.toLowerCase().slice(0, 3)));
      if (matches) {
        dayFixed.push({
          type: "FIXED",
          category: ev.category || "ACADEMIC_CLASS",
          title: ev.title,
          start_time: ev.start_time,
          end_time: ev.end_time,
          start_slot: globalDayIdx * 96 + Math.floor((parseInt(ev.start_time.split(":")[0]) * 60 + parseInt(ev.start_time.split(":")[1])) / 15),
        });
      }
    }

    // 2. Collect scheduled blocks for this specific day (Days 0..13)
    const dayBlocks = [];
    let dayStudyMin = 0;
    for (const b of state.currentSchedule.blocks || []) {
      const bDayIdx = typeof b.start_slot === "number" ? Math.floor(b.start_slot / 96) : -1;
      if (b.day === targetDayLabel || bDayIdx === globalDayIdx) {
        dayBlocks.push({
          type: "BLOCK",
          block: b,
          start_time: b.start_time,
          end_time: b.end_time,
          start_slot: b.start_slot,
          duration_min: b.duration_min,
        });
        dayStudyMin += b.duration_min;
      }
    }

    if (hoursEl) {
      hoursEl.textContent = `${(dayStudyMin / 60).toFixed(1)}h học`;
    }

    // Combine chronologically and inject NOW divider if TODAY
    const allEvents = [...dayFixed, ...dayBlocks];
    if (dayTemporal === "TODAY") {
      allEvents.push({
        type: "NOW_MARKER",
        start_slot: globalDayIdx * 96 + nowSlotExact,
        timeStr: formatTimeHHMM(activeNow),
      });
    }
    allEvents.sort((a, b) => a.start_slot - b.start_slot);

    if (allEvents.length === 0) {
      container.innerHTML = `
        <div class="h-full flex flex-col items-center justify-center py-10 text-center text-slate-400">
          <span class="text-2xl mb-1">🌿</span>
          <span class="text-[11px] font-medium">Trống lịch ngày ${formatDateShort(colDate)}</span>
          <span class="text-[10px] text-slate-400">Nghỉ ngơi hoặc tự ôn tập</span>
        </div>`;
      continue;
    }

    let html = "";
    for (const ev of allEvents) {
      if (ev.type === "NOW_MARKER") {
        html += _buildNowDividerHtml(ev.timeStr);
        continue;
      }

      const bTemp = getBlockTemporalState(colDate, ev.start_time, ev.end_time, activeNow);
      const isEvPast = dayTemporal === "PAST" || (dayTemporal === "TODAY" && bTemp.status === "PAST");
      const isEvActive = dayTemporal === "TODAY" && bTemp.status === "ACTIVE";

      if (ev.type === "FIXED") {
        const pastOp = isEvPast ? "opacity-65" : "";
        const activeRing = isEvActive ? "ring-2 ring-emerald-500" : "";
        if (ev.category === "MEAL") {
          html += `
            <div class="p-2 rounded-xl bg-amber-50 border border-amber-200/70 text-amber-900 shadow-sm transition hover:shadow ${pastOp} ${activeRing}">
              <div class="flex items-center justify-between text-[10px] text-amber-700 font-semibold mb-0.5">
                <span>${isEvActive ? "▶ ĐANG DIỄN RA" : "🍽️ ĂN & NGHỈ"}</span>
                <span class="mono">${ev.start_time} - ${ev.end_time}</span>
              </div>
              <div class="font-bold text-xs text-amber-950">${_escHtml(ev.title)}</div>
            </div>`;
        } else {
          html += `
            <div class="p-2.5 rounded-xl bg-slate-100 border border-slate-200 text-slate-800 shadow-sm transition hover:shadow ${pastOp} ${activeRing}">
              <div class="flex items-center justify-between text-[10px] text-slate-500 font-semibold mb-1">
                <span class="flex items-center gap-1">${isEvActive ? "▶ ĐANG DIỄN RA" : isEvPast ? "✓ Đã qua" : "🔒 CỐ ĐỊNH"}</span>
                <span class="mono font-bold text-slate-700">${ev.start_time} - ${ev.end_time}</span>
              </div>
              <div class="font-bold text-xs text-slate-900">${_escHtml(ev.title)}</div>
            </div>`;
        }
      } else {
        const b = ev.block;
        const isPinned = state.pinnedBlocks.has(b.block_id);
        const isDone = state.doneBlocks.has(b.block_id);
        const dlInfo = resolveDeadlineDisplay(b, activeNow);

        let cardClass = "bg-indigo-50/90 border border-indigo-200/90 text-indigo-950";
        if (isEvActive && !isDone) cardClass = "bg-emerald-50 border-2 border-emerald-500 ring-2 ring-emerald-100 text-emerald-950";
        else if (isPinned) cardClass = "bg-amber-50 border-2 border-amber-400 text-amber-950";
        if (isDone) cardClass = "bg-slate-50 border border-slate-200 text-slate-400 line-through opacity-60";
        else if (isEvPast) cardClass += " opacity-75";

        const statusBadge = isEvActive && !isDone
          ? `<span class="px-1.5 py-0.2 rounded bg-emerald-600 text-white text-[9px] font-bold">▶ LIVE</span>`
          : isEvPast && !isDone
            ? `<span class="px-1 py-0.2 rounded bg-slate-200 text-slate-600 text-[9px]">Qua</span>`
            : "";

        html += `
          <div class="p-2.5 rounded-xl ${cardClass} shadow-sm transition hover:shadow-md flex flex-col justify-between group">
            <div>
              <div class="flex items-center justify-between text-[10px] font-semibold mb-1 gap-1">
                <span class="mono px-1.5 py-0.5 bg-white/80 rounded text-indigo-800 font-bold">${b.start_time}–${b.end_time} (${b.duration_min}p)</span>
                <div class="flex items-center gap-1">
                  ${statusBadge}
                  <span class="px-1.5 py-0.5 rounded font-bold ${b.priority >= 4 ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700'}">P${b.priority}</span>
                </div>
              </div>
              <div class="font-bold text-xs leading-snug mb-1 text-slate-900">
                ${isPinned ? '📌 ' : ''}${isDone ? '✓ ' : ''}${_escHtml(b.title)}
                ${b.total_chunks > 1 ? `<span class="text-[10px] text-indigo-600 font-normal">(${b.chunk_index}/${b.total_chunks})</span>` : ''}
              </div>
              <div class="text-[10px] text-slate-500 mb-1.5 flex flex-wrap items-center gap-1">
                <span>🎯 ${_escHtml(dlInfo.dateText)}</span>
              </div>
            </div>

            <div class="flex items-center justify-between pt-1 border-t border-slate-200/50 text-[10px] gap-1">
              <button onclick="togglePinBlock('${b.block_id}')" class="px-1.5 py-0.5 rounded ${isPinned ? 'bg-amber-500 text-white font-bold' : 'bg-white hover:bg-amber-100 text-amber-800 border border-amber-200'} transition flex items-center gap-0.5" title="${isPinned ? 'Bỏ ghim' : 'Ghim cố định không cho dời'}">
                <span>📌</span> ${isPinned ? 'Ghim' : 'Ghim'}
              </button>
              <button onclick="toggleDoneBlock('${b.block_id}')" class="px-1.5 py-0.5 rounded ${isDone ? 'bg-emerald-600 text-white font-bold' : 'bg-white hover:bg-emerald-100 text-emerald-800 border border-emerald-200'} transition flex items-center gap-0.5" title="${isDone ? 'Đánh dấu chưa xong' : 'Đánh dấu đã xong'}">
                <span>✓</span> ${isDone ? 'Xong' : 'Xong'}
              </button>
              <button onclick="openWhyHereModal('${b.block_id}')" class="px-1.5 py-0.5 rounded bg-white hover:bg-indigo-100 text-indigo-800 border border-indigo-200 transition font-medium" title="Xem lý do thuật toán chọn khung giờ này">
                💡 Lý do
              </button>
            </div>
          </div>`;
      }
    }

    container.innerHTML = html;
  }

  requestAnimationFrame(() => updateObservedViewportRange());
}

function renderStudentTodayView() {
  const container = document.getElementById("stTodayTimelineContainer");
  const heroContainer = document.getElementById("stTodayHeroContainer");
  const pillsContainer = document.getElementById("stTodayDayPills");
  if (!container || !state.currentSchedule) return;

  const weekOff = state.viewWeekOffset || 0;
  const activeNow = getActiveNowDate();
  const nowSlotExact = (activeNow.getHours() * 60 + activeNow.getMinutes()) / 15;
  const dayIndex = Math.max(0, DAYS_EN.indexOf(state.todayDay));
  const globalDayIdx = weekOff * 7 + dayIndex;
  const selectedDate = getDayDate(globalDayIdx);
  const selectedDayTemporal = getDayTemporalState(selectedDate, activeNow);
  const targetDayLabel = weekOff === 1 ? `Next ${state.todayDay}` : state.todayDay;

  const titleEl = document.getElementById("stTodayActiveDateTitle");
  if (titleEl) {
    const tLabel = selectedDayTemporal === "TODAY" ? "HÔM NAY" : selectedDayTemporal === "PAST" ? "Đã qua" : "Sắp tới";
    titleEl.textContent = `${DAYS_VI[dayIndex]} · ${formatDateDDMMYYYY(selectedDate)} (${tLabel})`;
  }
  const nowBadgeEl = document.getElementById("stTodayNowBadge");
  if (nowBadgeEl) {
    nowBadgeEl.textContent = `Mốc hiện tại: ${formatDateDDMMYYYY(activeNow)} ${formatTimeHHMM(activeNow)}`;
  }

  // Render Day Pills with DD/MM and Today indicator
  if (pillsContainer) {
    pillsContainer.innerHTML = DAYS_EN.map((day, idx) => {
      const dDate = getDayDate(weekOff * 7 + idx);
      const tState = getDayTemporalState(dDate, activeNow);
      const isAct = day === state.todayDay;
      const dot = tState === "TODAY" ? `<span class="inline-block w-1.5 h-1.5 rounded-full bg-rose-400 mr-1"></span>` : "";
      return `
        <button onclick="setTodayDay('${day}')" class="px-2.5 py-1 text-xs font-bold rounded-lg transition ${
          isAct ? 'bg-indigo-600 text-white shadow' : tState === 'TODAY' ? 'bg-indigo-50 text-indigo-800 border border-indigo-300' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
        }">
          ${dot}${DAYS_VI[idx]} (${formatDateShort(dDate)})
        </button>`;
    }).join("");
  }

  // Collect today fixed events
  const todayFixed = [];
  for (const ev of state.commitments?.fixed_events || []) {
    const days = Array.isArray(ev.day_of_week) ? ev.day_of_week : String(ev.day_of_week).split(",").map((s) => s.trim());
    const matches = days.includes("ALL") || days.includes("all") || days.some((x) => x.toLowerCase().startsWith(state.todayDay.toLowerCase().slice(0, 3)));
    if (matches) {
      todayFixed.push({
        type: "FIXED",
        category: ev.category || "ACADEMIC_CLASS",
        title: ev.title,
        start_time: ev.start_time,
        end_time: ev.end_time,
        start_slot: globalDayIdx * 96 + Math.floor((parseInt(ev.start_time.split(":")[0]) * 60 + parseInt(ev.start_time.split(":")[1])) / 15),
      });
    }
  }

  const todayBlocks = [];
  for (const b of state.currentSchedule.blocks || []) {
    const bDayIdx = typeof b.start_slot === "number" ? Math.floor(b.start_slot / 96) : -1;
    if (b.day === targetDayLabel || bDayIdx === globalDayIdx) {
      todayBlocks.push({
        type: "BLOCK",
        block: b,
        start_time: b.start_time,
        end_time: b.end_time,
        start_slot: b.start_slot,
        duration_min: b.duration_min,
      });
    }
  }

  const allEvents = [...todayFixed, ...todayBlocks];
  if (selectedDayTemporal === "TODAY") {
    allEvents.push({
      type: "NOW_MARKER",
      start_slot: globalDayIdx * 96 + nowSlotExact,
      timeStr: formatTimeHHMM(activeNow),
    });
  }
  allEvents.sort((a, b) => a.start_slot - b.start_slot);

  // Pick next active/upcoming pending study block for Hero card
  const nextStudy =
    todayBlocks.find((x) => !state.doneBlocks.has(x.block.block_id) && getBlockTemporalState(selectedDate, x.start_time, x.end_time, activeNow).status === "ACTIVE") ||
    todayBlocks.find((x) => !state.doneBlocks.has(x.block.block_id) && getBlockTemporalState(selectedDate, x.start_time, x.end_time, activeNow).status === "FUTURE") ||
    todayBlocks.find((x) => !state.doneBlocks.has(x.block.block_id)) ||
    todayBlocks[0];

  if (heroContainer) {
    if (nextStudy) {
      const b = nextStudy.block;
      const isDone = state.doneBlocks.has(b.block_id);
      const isPinned = state.pinnedBlocks.has(b.block_id);
      const bTemp = getBlockTemporalState(selectedDate, b.start_time, b.end_time, activeNow);
      const dlInfo = resolveDeadlineDisplay(b, activeNow);
      const heroBadge = bTemp.status === "ACTIVE"
        ? `▶ ĐANG DIỄN RA (còn ${bTemp.deltaMin}p)`
        : selectedDayTemporal === "PAST" || bTemp.status === "PAST"
          ? "✓ ĐÃ QUA THEO MỐC THỜI GIAN"
          : "🎯 VIỆC CẦN TẬP TRUNG TIẾP THEO";

      heroContainer.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div class="flex flex-wrap items-center gap-2 mb-2">
              <span class="px-2.5 py-0.5 rounded-full ${bTemp.status === "ACTIVE" ? "bg-emerald-500 text-slate-950" : "bg-emerald-500/20 text-emerald-300 border border-emerald-400/30"} text-xs font-bold uppercase tracking-wider">${heroBadge}</span>
              <span class="text-xs text-indigo-200 mono font-semibold">${DAYS_VI[dayIndex]} · ${formatDateDDMMYYYY(selectedDate)} (${b.start_time} – ${b.end_time} · ${b.duration_min} phút)</span>
            </div>
            <h2 class="text-xl sm:text-2xl font-bold text-white tracking-tight mb-1.5 flex items-center gap-2">
              ${isPinned ? '📌 ' : ''}${isDone ? '✓ ' : ''}${_escHtml(b.title)}
              ${b.total_chunks > 1 ? `<span class="text-sm font-normal text-indigo-300">(Phiên ${b.chunk_index}/${b.total_chunks})</span>` : ''}
            </h2>
            <p class="text-xs text-indigo-200 max-w-2xl leading-relaxed">
              Hạn: <strong>${_escHtml(dlInfo.dateText)}</strong> · Ưu tiên P${b.priority} · ${_escHtml(b.reason || 'Được xếp tự động vào khung giờ tối ưu.')}
            </p>
            <div class="mt-3 flex flex-wrap items-center gap-2 text-xs">
              <span class="text-indigo-200">Check-in thực tế (M7):</span>
              <input id="stHeroActualMin" type="number" min="15" max="480" step="15" value="${state.actualDurations.get(b.block_id) || b.duration_min}" class="w-20 px-2 py-1 rounded-lg bg-slate-900/70 border border-indigo-400/50 text-white mono text-center" />
              <span class="text-indigo-300">phút</span>
              <button type="button" onclick="submitBlockCheckIn('${b.block_id}', 'stHeroActualMin')" class="px-3 py-1 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold transition">Lưu kết quả</button>
              <span id="stHeroCheckInFeedback" class="hidden text-emerald-300 font-semibold"></span>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <button onclick="toggleDoneBlock('${b.block_id}')" class="px-4 py-2 rounded-xl ${isDone ? 'bg-slate-700 text-slate-300' : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold'} shadow-md transition flex items-center gap-1.5 text-xs">
              <span>✓</span> ${isDone ? 'Đánh dấu chưa xong' : 'Hoàn Thành Phiên'}
            </button>
            <button onclick="togglePinBlock('${b.block_id}')" class="px-3.5 py-2 rounded-xl ${isPinned ? 'bg-amber-500 text-white font-bold' : 'bg-indigo-700/80 hover:bg-indigo-600 text-white'} border border-indigo-500/50 transition flex items-center gap-1.5 text-xs">
              <span>📌</span> ${isPinned ? 'Đã Ghim' : 'Ghim Lịch'}
            </button>
            <button onclick="openWhyHereModal('${b.block_id}')" class="px-3.5 py-2 rounded-xl bg-indigo-900/80 hover:bg-indigo-800 text-indigo-200 border border-indigo-700 transition flex items-center gap-1.5 text-xs">
              <span>💡</span> Tại Sao?
            </button>
          </div>
        </div>`;
    } else {
      heroContainer.innerHTML = `
        <div class="py-2 text-center text-indigo-200">
          <h2 class="text-lg font-bold text-white mb-1">🎉 Không còn bài tập nào trong ngày ${DAYS_VI[dayIndex]} (${formatDateDDMMYYYY(selectedDate)})!</h2>
          <p class="text-xs text-indigo-300">Hãy nghỉ ngơi hoặc chuyển sang ngày khác bằng các nút ở trên.</p>
        </div>`;
    }
  }

  // Render vertical timeline
  if (allEvents.length === 0) {
    container.innerHTML = `<div class="py-8 text-center text-slate-400 text-xs">Không có lịch trình nào trong ngày ${DAYS_VI[dayIndex]} (${formatDateDDMMYYYY(selectedDate)}).</div>`;
    return;
  }

  container.innerHTML = allEvents.map((ev) => {
    if (ev.type === "NOW_MARKER") {
      return _buildNowDividerHtml(ev.timeStr);
    }
    const bTemp = getBlockTemporalState(selectedDate, ev.start_time, ev.end_time, activeNow);
    const isPast = selectedDayTemporal === "PAST" || (selectedDayTemporal === "TODAY" && bTemp.status === "PAST");
    const isActive = selectedDayTemporal === "TODAY" && bTemp.status === "ACTIVE";
    const statusChip = isActive
      ? `<span class="px-2 py-0.5 rounded bg-emerald-600 text-white font-bold text-[10px]">▶ ĐANG DIỄN RA</span>`
      : isPast
        ? `<span class="px-2 py-0.5 rounded bg-slate-200 text-slate-600 text-[10px]">Đã qua</span>`
        : `<span class="px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 text-[10px]">Sắp tới</span>`;

    if (ev.type === "FIXED") {
      const isMeal = ev.category === "MEAL";
      return `
        <div class="flex items-start gap-3 p-3 rounded-xl ${isMeal ? 'bg-amber-50/70 border border-amber-200' : 'bg-slate-50 border border-slate-200'} ${isPast ? 'opacity-65' : ''} ${isActive ? 'ring-2 ring-emerald-500' : ''}">
          <div class="w-16 text-xs font-bold ${isMeal ? 'text-amber-800' : 'text-slate-600'} mono pt-0.5">${ev.start_time}</div>
          <div class="flex-1">
            <span class="text-[10px] font-bold uppercase tracking-wider ${isMeal ? 'text-amber-700' : 'text-slate-500'}">${isMeal ? '🍽️ Nghỉ & Ăn' : '🎓 Lịch Cố Định'}</span>
            <div class="text-xs font-bold text-slate-900">${_escHtml(ev.title)} (${ev.start_time} – ${ev.end_time})</div>
          </div>
          ${statusChip}
        </div>`;
    } else {
      const b = ev.block;
      const isDone = state.doneBlocks.has(b.block_id);
      const isPinned = state.pinnedBlocks.has(b.block_id);
      const dlInfo = resolveDeadlineDisplay(b, activeNow);

      return `
        <div class="flex items-start gap-3 p-3.5 rounded-xl border transition ${
          isDone ? 'bg-slate-50 border-slate-200 opacity-60' : isActive ? 'bg-emerald-50 border-2 border-emerald-500' : isPinned ? 'bg-amber-50/70 border-amber-300' : 'bg-indigo-50/60 border-indigo-200'
        } ${isPast && !isDone ? 'opacity-75' : ''}">
          <div class="w-16 text-xs font-bold text-indigo-900 mono pt-0.5">${b.start_time}</div>
          <input type="checkbox" ${isDone ? 'checked' : ''} onchange="toggleDoneBlock('${b.block_id}')" class="mt-1 w-4 h-4 text-indigo-600 rounded cursor-pointer" />
          <div class="flex-1">
            <div class="flex flex-wrap items-center gap-2 mb-0.5">
              <span class="text-xs font-bold text-slate-900 ${isDone ? 'line-through text-slate-500' : ''}">${_escHtml(b.title)}</span>
              ${b.total_chunks > 1 ? `<span class="text-[10px] font-medium text-indigo-600">(Phiên ${b.chunk_index}/${b.total_chunks})</span>` : ''}
              ${isPinned ? '<span class="text-[10px] px-1.5 py-0.2 bg-amber-200 text-amber-900 rounded font-bold">📌 ĐÃ GHIM</span>' : ''}
              ${statusChip}
            </div>
            <div class="text-[11px] text-slate-500 flex flex-wrap items-center gap-2">
              <span>⏱️ ${b.duration_min} phút</span>
              <span>·</span>
              <span>🎯 ${_escHtml(dlInfo.dateText)}</span>
              ${dlInfo.badgeHtml}
              <span class="text-indigo-700 font-medium">P${b.priority}</span>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <button onclick="togglePinBlock('${b.block_id}')" class="p-1.5 rounded hover:bg-white text-slate-600" title="Ghim/Bỏ ghim">📌</button>
            <button onclick="openWhyHereModal('${b.block_id}')" class="p-1.5 rounded hover:bg-white text-indigo-600" title="Xem lý do xếp">💡</button>
          </div>
        </div>`;
    }
  }).join("");
}

function setTodayDay(day) {
  state.todayDay = day;
  renderStudentTodayView();
}

function switchStudentTasksSubtab(subtab) {
  state.studentTasksSubtab = subtab;
  const btnT = document.getElementById("btnStSubTasks");
  const btnH = document.getElementById("btnStSubHabits");
  const paneT = document.getElementById("stSubTasksPane");
  const paneH = document.getElementById("stSubHabitsPane");
  const isHabits = subtab === "HABITS";
  if (btnT) {
    btnT.className = !isHabits
      ? "px-3 py-1.5 rounded-lg bg-white text-indigo-700 font-bold shadow-sm transition"
      : "px-3 py-1.5 rounded-lg text-slate-600 font-semibold hover:text-slate-900 transition";
  }
  if (btnH) {
    btnH.className = isHabits
      ? "px-3 py-1.5 rounded-lg bg-white text-indigo-700 font-bold shadow-sm transition"
      : "px-3 py-1.5 rounded-lg text-slate-600 font-semibold hover:text-slate-900 transition";
  }
  paneT?.classList.toggle("hidden", isHabits);
  paneH?.classList.toggle("hidden", !isHabits);
  if (isHabits) renderStudentMainHabits();
  else renderStudentTaskQueue();
}

function _renderHabitCardsInto(containerEl, autoSolveOnDelete = false) {
  if (!containerEl) return;
  const habits = Array.isArray(state.commitments?.personal_habits) ? state.commitments.personal_habits : [];
  if (habits.length === 0) {
    containerEl.innerHTML = `<div class="text-xs text-slate-400 italic py-2">Chưa có thói quen cố định theo tuần nào.</div>`;
    return;
  }
  const winLabels = { MORNING: "Sáng (06–12h)", AFTERNOON: "Chiều (12–18h)", EVENING: "Tối (18–23h)", ANYTIME: "Linh hoạt" };
  containerEl.innerHTML = habits
    .map((h, idx) => `
      <div class="flex items-center justify-between bg-white border border-slate-200 rounded-lg px-3 py-2 text-xs">
        <div class="font-medium text-slate-800">
          🏃 <strong>${_escHtml(h.name)}</strong> · ${winLabels[h.preferred_window] || h.preferred_window} · <span class="mono">${h.frequency_per_week}x/tuần × ${h.duration_min}p</span>
        </div>
        <button type="button" onclick="removeStudentPersonalHabit(${idx}, ${autoSolveOnDelete ? "true" : "false"})" class="text-slate-400 hover:text-rose-600 font-bold px-2 py-0.5 rounded hover:bg-rose-50" title="Xóa thói quen">✕ Xóa</button>
      </div>
    `)
    .join("");
}

function renderStudentMainHabits() {
  _renderHabitCardsInto(document.getElementById("stMainHabitsList"), true);
}

function _addHabitFromInputs(prefix) {
  const nameEl = document.getElementById(`${prefix}Name`);
  const name = nameEl?.value.trim();
  if (!name) return false;
  const win = document.getElementById(`${prefix}Window`)?.value || "EVENING";
  const freq = Math.max(1, Math.min(7, parseInt(document.getElementById(`${prefix}Freq`)?.value || "3", 10)));
  const dur = Math.max(15, Math.min(240, parseInt(document.getElementById(`${prefix}Dur`)?.value || "60", 10)));
  state.commitments.personal_habits = state.commitments.personal_habits || [];
  state.commitments.personal_habits.push({
    habit_id: `HABIT_${Date.now().toString().slice(-4)}`,
    name,
    preferred_window: win,
    frequency_per_week: freq,
    duration_min: dur,
    category: "HABIT",
    cognitive_load: 1,
  });
  if (nameEl) nameEl.value = "";
  renderStudentSettingsHabits();
  savePersistedStudentState();
  return true;
}

async function addStudentHabitFromMainTab() {
  if (_addHabitFromInputs("stMainHabitNew")) {
    await solveSchedule();
  }
}

function renderStudentTaskQueue() {
  const tbody = document.getElementById("stTasksTableBody");
  if (!tbody) return;

  if (!state.tasks || state.tasks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400">Chưa có công việc nào. Bấm nút "+ Thêm Việc" để bắt đầu!</td></tr>`;
    return;
  }

  const activeNow = getActiveNowDate();
  const placedIds = new Set((state.currentSchedule?.blocks || []).map((b) => b.task_id));

  tbody.innerHTML = state.tasks.map((t) => {
    const tid = t.task_id || t.id;
    const isPlaced = placedIds.has(tid);
    const bufferInfo = state.taskBufferMap.get(tid);
    const dlInfo = resolveDeadlineDisplay(t, activeNow);
    const rhythmBadge = t.work_rhythm === "DEEP_FLOW" ? "🔥 Sâu" : t.work_rhythm === "LIGHT_PACE" ? "🐢 Nhẹ" : "";

    return `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-2.5 px-3 font-semibold text-slate-900 mono">${_escHtml(tid)}</td>
        <td class="py-2.5 px-3 font-bold text-slate-900">
          ${_escHtml(t.title)}
          ${rhythmBadge ? `<span class="ml-1 text-[10px] font-semibold text-indigo-700 bg-indigo-50 px-1.5 py-0.5 rounded">${rhythmBadge}</span>` : ""}
        </td>
        <td class="py-2.5 px-3">
          <span class="font-semibold mono">${t.duration_min}p</span>
          ${bufferInfo ? `<span class="ml-1 text-[10px] text-indigo-600 font-semibold bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200">🛡️ +Buffer</span>` : ''}
        </td>
        <td class="py-2.5 px-3 text-slate-700 mono">
          <div class="flex flex-wrap items-center gap-1.5">
            <span>${_escHtml(dlInfo.dateText)}</span>
            ${dlInfo.badgeHtml}
          </div>
        </td>
        <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${t.priority >= 4 ? 'bg-indigo-100 text-indigo-800' : 'bg-slate-100 text-slate-700'}">P${t.priority}</span></td>
        <td class="py-2.5 px-3">
          ${isPlaced
            ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">✓ ĐÃ XẾP LỊCH</span>`
            : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">⚠️ CHƯA XẾP ĐƯỢC</span>`
          }
        </td>
        <td class="py-2.5 px-3 text-right whitespace-nowrap space-x-1">
          <button onclick="editStudentTask('${_escHtml(tid)}')" class="text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50 px-2 py-1 rounded font-bold text-xs" title="Sửa công việc">✏️ Sửa</button>
          <button onclick="deleteStudentTask('${_escHtml(tid)}')" class="text-slate-400 hover:text-rose-600 hover:bg-rose-50 px-2 py-1 rounded font-bold text-xs" title="Xóa task">✕ Xóa</button>
        </td>
      </tr>`;
  }).join("");
}

// Student Task Modal controls
function _escHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const HYBRID_DIAG_LABELS = {
  E_DEADLINE_IN_THE_PAST: "Hạn chót nằm trong quá khứ",
  E_DEADLINE_CONTRADICTION: "Xung đột nhiều hạn chót / sai thứ-ngày",
  E_START_AFTER_DEADLINE: "Thời điểm bắt đầu muộn hơn hạn chót",
  E_SUBTASK_DEADLINE_AFTER_PARENT: "Bước con có hạn muộn hơn task chính",
  E_CYCLIC_DEPENDENCY: "Phát hiện chu trình phụ thuộc A→B→A",
  E_DURATION_CONTRADICTION: "Tổng thời lượng mâu thuẫn với tổng bước con",
  E_SESSION_CONTRADICTION: "Mâu thuẫn chế độ Chia nhỏ vs 1 Buổi liền",
  E_SEMANTIC_CONTRADICTION: "Mâu thuẫn ngữ nghĩa nội tại (vd: nghỉ ngơi vs cường độ cao)",
  E_CUSTOM_RANGE_INVALID: "Khoảng Tùy chỉnh Min > Max không hợp lệ",
  E_ATTACHMENT_TOO_LARGE: "Tệp đính kèm vượt giới hạn 20MB",
  E_ATTACHMENT_TYPE: "Định dạng tệp không hỗ trợ (.pdf,.txt,.md,.html)",
  E_INVALID_CITATION_FORMAT: "Sai cú pháp dấu ngoặc vuông kép [[tên tệp]] hoặc tên tệp chứa ký tự không hợp lệ",
  E_INFEASIBLE_WORKLOAD: "Tổng thời lượng vượt quỹ thời gian tới hạn chót",
  E_NO_ACTIONABLE_TASK: "Thiếu hành động/đầu việc cụ thể",
  E_NONSENSE_INPUT: "Đầu vào không hợp lệ / ngoài phạm vi lập lịch",
  W_DOC_MENTIONED_NOT_ATTACHED: "Trích dẫn / nhắc tới tài liệu nhưng CHƯA đính kèm tệp tương ứng",
  W_ATTACHMENT_UNREFERENCED: "Có tệp đính kèm nhưng chưa được trích dẫn bằng [[tên tệp]] trong prompt",
  W_BREAKDOWN_RECOMMENDED: "Task phức tạp/đa miền — nên chia bước nhỏ",
  W_UNREALISTIC_LOAD: "Khối lượng 1 buổi liền quá nặng (≥6h)",
  W_TIGHT_SCHEDULE: "Quỹ thời gian sát — nên ưu tiên sớm",
  W_SESSION_CONFLICT: "Chế độ phiên xung đột với yêu cầu trong câu (tự ưu tiên theo câu)",
  W_PRIORITY_CONFLICT: "Độ ưu tiên nút chọn khác với thẻ [p1..p4] trong câu",
  W_CHUNK_CONFLICT: "Cỡ block mâu thuẫn với ràng buộc trong câu",
  W_OPEN_LOOP: "Đầu việc có vòng lặp mở chưa rõ điểm dừng",
  W_EXTERNAL_DEPENDENCY: "Phụ thuộc bên ngoài / chờ phản hồi người khác",
  W_NO_DURATION: "Chưa nêu rõ thời lượng thực hiện (hãy chọn chip hoặc nhập thời lượng gốc bên dưới)",
  W_NO_DEADLINE: "Chưa nêu rõ ngày/giờ hạn chót (tạm suy luận mặc định hoặc chọn Không hạn chót)",
  W_VAGUE_DURATION: "Thời lượng còn ước lượng mơ hồ (nên xác nhận lại số phút)",
  W_VAGUE_DEADLINE: "Hạn chót diễn đạt mơ hồ (vd: sớm / đầu tuần tới)",
  W_AMBIGUOUS_DATE: "Ngày/tháng có thể gây hiểu nhầm (nên viết rõ thứ và ngày)",
  W_MULTIPLE_GOALS: "Câu chứa nhiều mục tiêu độc lập (cân nhắc tách thành nhiều task)",
  W_DEPENDENCY_UNCLEAR: "Thứ tự phụ thuộc giữa các phần chưa rõ ràng",
  W_MIXED_LANGUAGE: "Phát hiện trộn lẫn Tiếng Việt & Tiếng Anh",
  W_STATUS_INFERRED: "Một số bước có dấu hiệu đã xong hoặc đang thực hiện",
  W_TYPO_CORRECTED: "Đã tự động sửa một số lỗi chính tả phổ biến",
  W_SELF_CORRECTION: "Phát hiện tự sửa ý giữa câu — đã lấy mốc điều chỉnh mới nhất",
  W_RECURRING_NO_END: "Lịch lặp lại định kỳ chưa có ngày kết thúc",
  W_RECURRING_NO_DURATION: "Lịch lặp lại chưa nêu thời lượng mỗi phiên",
  W_PROMPT_INJECTION: "Phát hiện mẫu Prompt/SQL Injection — đã kích hoạt lá chắn an toàn",
};

const CRITICAL_CITATION_CODES = new Set([
  "W_DOC_MENTIONED_NOT_ATTACHED",
  "W_ATTACHMENT_UNREFERENCED",
]);

function setStudentNlEngine(mode) {
  state.nlEngineMode = mode === "offline" ? "offline" : "auto";
  const btnAuto = document.getElementById("btnNlEngineAuto");
  const btnOff = document.getElementById("btnNlEngineOffline");
  const activeCls = "px-2 py-0.5 rounded-md bg-white text-indigo-700 shadow-sm transition";
  const idleCls = "px-2 py-0.5 rounded-md text-slate-600 hover:text-slate-900 transition";
  if (btnAuto) btnAuto.className = state.nlEngineMode === "auto" ? activeCls : idleCls;
  if (btnOff) btnOff.className = state.nlEngineMode === "offline" ? activeCls : idleCls;
}

function setStNlTransBackend(backend) {
  state.nlTransBackend = backend === "nllb" ? "nllb" : "rule";
}

function _refreshStNlChunkUI() {
  const paceGrp = document.getElementById("stNlPacingGroup");
  if (paceGrp) {
    if (state.nlSession === "single") {
      paceGrp.classList.add("opacity-45");
    } else {
      paceGrp.classList.remove("opacity-45");
    }
  }
  const advSum = document.getElementById("stAdvSyncedSummary");
  if (advSum) {
    const urgText = state.nlUrgency ? `P${state.nlUrgency} (Solver P${_mapUserUrgencyToSolver(state.nlUrgency)})` : "Tự động theo ngữ cảnh";
    const splitText = state.nlSession === "single"
      ? "Làm liền 1 buổi (Không cắt)"
      : `Cho phép cắt nhỏ (${state.nlMinChunk}–${state.nlMaxChunk}p · ${state.nlPacing})`;
    advSum.innerHTML = `Đồng bộ từ mục trên: <strong>Khẩn cấp ${_escHtml(urgText)}</strong> · <strong>${_escHtml(splitText)}</strong>`;
  }
}

function setStNlSession(mode) {
  state.nlSession = mode === "single" ? "single" : "splittable";
  const bSplit = document.getElementById("stNlSessionSplit");
  const bSingle = document.getElementById("stNlSessionSingle");
  const onCls = "px-2.5 py-1 rounded-md font-semibold bg-indigo-600 text-white transition";
  const offCls = "px-2.5 py-1 rounded-md font-semibold bg-white border border-slate-300 text-slate-600 transition";
  if (bSplit) bSplit.className = state.nlSession === "splittable" ? onCls : offCls;
  if (bSingle) bSingle.className = state.nlSession === "single" ? onCls : offCls;
  const chk = document.getElementById("stInpSplittable");
  if (chk) chk.checked = state.nlSession === "splittable";
  _refreshStNlChunkUI();
}

function syncStSessionFromSplittableCheckbox(checked) {
  setStNlSession(checked ? "splittable" : "single");
}

function setStNlPacing(pacing) {
  state.nlPacing = pacing || "BALANCED";
  if (state.nlPacing === "LIGHT") {
    state.nlMinChunk = 15;
    state.nlMaxChunk = 30;
  } else if (state.nlPacing === "FLOW") {
    state.nlMinChunk = 45;
    state.nlMaxChunk = 120;
  } else if (state.nlPacing === "CUSTOM") {
    const cMin = parseInt(document.getElementById("stNlCustomMin")?.value || "20", 10);
    const cMax = parseInt(document.getElementById("stNlCustomMax")?.value || "45", 10);
    state.nlMinChunk = Math.max(15, cMin);
    state.nlMaxChunk = Math.max(state.nlMinChunk, cMax);
  } else {
    state.nlMinChunk = 15;
    state.nlMaxChunk = 60;
  }

  const paceMap = {
    LIGHT: "stNlPaceLight",
    BALANCED: "stNlPaceBalanced",
    FLOW: "stNlPaceFlow",
    CUSTOM: "stNlPaceCustom",
  };
  const onCls = "px-2.5 py-1 rounded-md font-semibold bg-indigo-100 border border-indigo-400 text-indigo-800 transition";
  const offCls = "px-2.5 py-1 rounded-md font-semibold bg-white border border-slate-300 text-slate-600 transition";
  Object.entries(paceMap).forEach(([key, elId]) => {
    const el = document.getElementById(elId);
    if (el) el.className = state.nlPacing === key ? onCls : offCls;
  });

  const customWrap = document.getElementById("stNlCustomWrap");
  if (customWrap) customWrap.classList.toggle("hidden", state.nlPacing !== "CUSTOM");
  const rhythmSel = document.getElementById("stInpWorkRhythm");
  if (rhythmSel && rhythmSel.value !== state.nlPacing) rhythmSel.value = state.nlPacing;
  if (state.nlSession === "single") setStNlSession("splittable");
  _refreshStNlChunkUI();
}

function syncWorkRhythmFromAdv(rhythm) {
  setStNlPacing(rhythm || "BALANCED");
  saveStudentModalDraft();
}

function syncPriorityFromCore(val) {
  if (val === "auto" || val === "" || val === null || val === undefined) {
    setStNlUrgency(null);
    const priSel = document.getElementById("stInpPriority");
    if (priSel) priSel.value = "3";
  } else {
    setStNlUrgency(Number(val));
  }
  saveStudentModalDraft();
}

function _mapUserUrgencyToSolver(urg) {
  const u = Number(urg);
  if (u === 1) return 5;
  if (u === 2) return 4;
  if (u === 3) return 3;
  if (u === 4) return 1;
  return 3;
}

function _mapSolverToUserUrgency(solverVal) {
  const s = Number(solverVal);
  if (s >= 5) return 1;
  if (s === 4) return 2;
  if (s === 3) return 3;
  return 4;
}

function _renderUrgencyPills(activeUrg) {
  const urgIds = [
    [null, "stNlUrgAuto", "text-indigo-800"],
    [1, "stNlUrg1", "text-rose-700"],
    [2, "stNlUrg2", "text-amber-700"],
    [3, "stNlUrg3", "text-slate-700"],
    [4, "stNlUrg4", "text-emerald-700"],
  ];
  urgIds.forEach(([val, id, txtCls]) => {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.className = activeUrg === val
      ? `px-2 py-0.5 rounded font-bold bg-indigo-100 border border-indigo-400 ${txtCls} transition`
      : `px-2 py-0.5 rounded font-semibold bg-white border border-slate-300 ${txtCls} transition`;
  });
}

function setStNlUrgency(urgency) {
  state.nlUrgency = urgency === null || urgency === undefined ? null : Number(urgency);
  _renderUrgencyPills(state.nlUrgency);
  const priSel = document.getElementById("stInpPriority");
  if (priSel && state.nlUrgency !== null) {
    priSel.value = String(_mapUserUrgencyToSolver(state.nlUrgency));
  }
  const coreSel = document.getElementById("stInpPriorityCore");
  if (coreSel) {
    coreSel.value = state.nlUrgency === null ? "auto" : String(state.nlUrgency);
  }
  _refreshStNlChunkUI();
  // Keep live diagnostic urgency badge synchronized immediately if already analyzed
  if (state.lastAnalyzedHybrid && state.nlUrgency !== null) {
    state.lastAnalyzedHybrid.priority = state.nlUrgency;
    state.lastAnalyzedHybrid.solver_priority = _mapUserUrgencyToSolver(state.nlUrgency);
    const diagEl = document.getElementById("stNlDiagnostics");
    if (diagEl && !diagEl.classList.contains("hidden")) {
      renderHybridDiagnostics(diagEl, state.lastAnalyzedHybrid, state.lastAnalyzedTranslation);
    }
  }
}

function syncStUrgencyFromSolverSelect(solverVal) {
  const mappedUrg = _mapSolverToUserUrgency(solverVal);
  state.nlUrgency = mappedUrg;
  _renderUrgencyPills(mappedUrg);
  _refreshStNlChunkUI();
}

function _setPromptRedState(hasErrorOrMissingCitation) {
  const box = document.getElementById("stNlPromptBox") || document.getElementById("stNlPrompt");
  if (!box) return;
  if (hasErrorOrMissingCitation) {
    box.className = "flex-1 rounded-lg border-2 border-rose-500 ring-2 ring-rose-200 bg-rose-50/40 focus-within:border-rose-600 px-2.5 py-1.5 space-y-1.5 transition";
  } else {
    box.className = "flex-1 rounded-lg border border-slate-300 bg-white focus-within:border-indigo-600 focus-within:ring-1 focus-within:ring-indigo-500 px-2.5 py-1.5 space-y-1.5 transition";
  }
}

function extractBracketedCitations(text) {
  const src = String(text || "");
  const valid = [];
  let hasMalformed = false;
  const reDbl = /\[\[([^\[\]\n]*?)\]\]/g;
  let m;
  while ((m = reDbl.exec(src)) !== null) {
    const inner = m[1].trim();
    if (!inner || /[<>:"/\\|?*]/.test(inner)) {
      hasMalformed = true;
    } else if (!valid.some((v) => v.toLowerCase() === inner.toLowerCase())) {
      valid.push(inner);
    }
  }
  // Also recognize @[path/to/filename] chat-style file mentions
  const reAt = /@\[([^\[\]\n]+?)\]/g;
  while ((m = reAt.exec(src)) !== null) {
    const rawPath = m[1].trim();
    const baseFn = rawPath.split(/[/\\]/).pop().trim();
    if (baseFn && !valid.some((v) => v.toLowerCase() === baseFn.toLowerCase())) {
      valid.push(baseFn);
    }
  }
  const remainder = src.replace(/\[\[[^\[\]\n]*?\]\]/g, " ").replace(/@\[[^\[\]\n]+?\]/g, " ");
  if (/\[\[|\]\]/.test(remainder)) {
    hasMalformed = true;
  }
  return { valid, hasMalformed };
}

function parseLinkedFileEntry(rawInput) {
  let clean = String(rawInput || "").trim();
  if (!clean) return null;
  if ((clean.startsWith("@[") && clean.endsWith("]")) || (clean.startsWith("[[") && clean.endsWith("]]"))) {
    clean = clean.slice(2, -2).trim();
  }
  clean = clean.replace(/^["']|["']$/g, "").trim();
  if (!clean) return null;
  let normalized = clean.replace(/^file:\/\/\/+/i, "");
  try {
    normalized = decodeURIComponent(normalized);
  } catch (_) {}
  const name = normalized.split(/[?#]/)[0].split(/[/\\]/).pop().trim();
  if (!name) return null;
  return {
    name,
    path_or_uri: clean,
    size_mb: 0,
    source: normalized !== name ? "path" : "manual",
  };
}

function _upsertLinkedAttachment(entry) {
  if (!entry || !entry.name) return;
  if (!Array.isArray(state.nlAttachments)) state.nlAttachments = [];
  const lowName = entry.name.toLowerCase();
  const idx = state.nlAttachments.findIndex((a) => String(a.name || "").toLowerCase() === lowName);
  if (idx >= 0) {
    state.nlAttachments[idx] = { ...state.nlAttachments[idx], ...entry };
  } else {
    state.nlAttachments.push(entry);
  }
}

function onStNlPromptLiveCheck(val) {
  const { valid, hasMalformed } = extractBracketedCitations(val);
  const statusEl = document.getElementById("stNlBracketLiveStatus");
  const chipsEl = document.getElementById("stNlCitationBlockChips");
  const attLow = new Set((state.nlAttachments || []).map((a) => String(a.name || "").trim().toLowerCase()));

  if (statusEl) {
    if (hasMalformed) {
      statusEl.className = "text-[10px] font-bold text-rose-600";
      statusEl.textContent = "⛔ Lỗi ngoặc kép [[...]] chưa đóng hoặc rỗng!";
    } else if (valid.length > 0) {
      const missingCount = valid.filter((f) => !attLow.has(f.toLowerCase())).length;
      if (missingCount > 0) {
        statusEl.className = "text-[10px] font-bold text-rose-600";
        statusEl.textContent = `⚠️ ${missingCount} tệp trích dẫn chưa có trong Link Box`;
      } else {
        statusEl.className = "text-[10px] font-bold text-emerald-700";
        statusEl.textContent = `✓ Khớp ${valid.length} tệp`;
      }
    } else {
      statusEl.textContent = "";
    }
  }

  if (chipsEl) {
    if (valid.length === 0) {
      chipsEl.classList.add("hidden");
      chipsEl.innerHTML = "";
    } else {
      chipsEl.innerHTML = valid.map((fname) => {
        const isMatched = attLow.has(fname.toLowerCase());
        const badgeCls = isMatched
          ? "bg-indigo-50 border-2 border-indigo-400 text-indigo-900 shadow-xs"
          : "bg-rose-50 border-2 border-rose-400 text-rose-900 font-semibold";
        const icon = isMatched ? "✓" : "✕ Thiếu Link Box";
        return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md ${badgeCls} mono">
          <span>📄 ${_escHtml(fname)}</span>
          <span class="font-sans text-[9px] px-1 rounded bg-white/70">${icon}</span>
          <button type="button" onclick="removeCitationBlock('${_escHtml(fname).replace(/'/g, "\\'")}')" title="Gỡ hộp tệp khỏi ô nhập" class="hover:text-rose-700 font-bold ml-0.5">×</button>
        </span>`;
      }).join("");
      chipsEl.classList.remove("hidden");
    }
  }

  _setPromptRedState(hasMalformed);
}

function insertNamedCitationBlock(filename, skipReanalyze = false) {
  const clean = String(filename || "").replace(/^\[\[|\]\]$/g, "").trim();
  if (!clean) return;
  const promptEl = document.getElementById("stNlPrompt");
  if (!promptEl) return;
  const block = `[[${clean}]]`;
  if (!promptEl.value.toLowerCase().includes(block.toLowerCase()) && !promptEl.value.toLowerCase().includes(clean.toLowerCase() + "]")) {
    const cur = promptEl.value.trim();
    promptEl.value = cur ? `${cur} ${block}` : block;
  }
  onStNlPromptLiveCheck(promptEl.value);
  saveStudentModalDraft();
  if (!skipReanalyze && state.lastAnalyzedHybrid) {
    analyzeStudentNlPrompt();
  }
}

function promptInsertCitationBox() {
  const promptEl = document.getElementById("stNlPrompt");
  if (!promptEl) return;
  const val = promptEl.value || "";
  const start = promptEl.selectionStart ?? val.length;
  const end = promptEl.selectionEnd ?? val.length;
  const selected = val.slice(start, end).trim();
  const inner = selected || "Ten_tai_lieu.pdf";
  const prefix = start > 0 && !/\s$/.test(val.slice(0, start)) ? " " : "";
  const suffix = end < val.length && !/^\s/.test(val.slice(end)) ? " " : "";
  const inserted = `${prefix}[[${inner}]]${suffix}`;
  promptEl.value = val.slice(0, start) + inserted + val.slice(end);
  promptEl.focus();
  const selStart = start + prefix.length + 2;
  promptEl.setSelectionRange(selStart, selStart + inner.length);
  onStNlPromptLiveCheck(promptEl.value);
  saveStudentModalDraft();
}

function handleStNlFileDrop(event, dropZone) {
  event.preventDefault();
  event.stopPropagation();
  const promptBox = document.getElementById("stNlPromptBox");
  const linkBox = document.getElementById("stNlFileLinkBox");
  if (promptBox) promptBox.classList.remove("border-indigo-500", "bg-indigo-50/30");
  if (linkBox) linkBox.classList.remove("border-indigo-500", "bg-indigo-50/40");

  const dt = event.dataTransfer;
  if (!dt) return;
  const droppedNames = [];

  if (dt.files && dt.files.length > 0) {
    Array.from(dt.files).forEach((f) => {
      const entry = {
        name: f.name,
        path_or_uri: `dragged://${f.name}`,
        size_mb: Number((f.size / (1024 * 1024)).toFixed(2)),
        source: "drop",
      };
      _upsertLinkedAttachment(entry);
      droppedNames.push(entry.name);
    });
  } else if (dt.items && dt.items.length > 0) {
    Array.from(dt.items).forEach((item) => {
      if (item.kind === "file" && typeof item.getAsFile === "function") {
        const f = item.getAsFile();
        if (f && f.name) {
          _upsertLinkedAttachment({
            name: f.name,
            path_or_uri: `dragged://${f.name}`,
            size_mb: Number((f.size / (1024 * 1024)).toFixed(2)),
            source: "drop",
          });
          droppedNames.push(f.name);
        }
      }
    });
  }
  if (droppedNames.length === 0) {
    let rawDropText = "";
    try {
      rawDropText = (dt.getData("text/uri-list") || dt.getData("text/plain") || "").trim();
    } catch (_) {}
    if (rawDropText) {
      rawDropText.split(/\r?\n/).forEach((line) => {
        if (line && !line.startsWith("#")) {
          const parsed = parseLinkedFileEntry(line);
          if (parsed) {
            _upsertLinkedAttachment(parsed);
            droppedNames.push(parsed.name);
          }
        }
      });
    }
  }

  if (droppedNames.length === 0) return;
  renderStNlAttachmentChips();

  const shouldInsert = dropZone === "prompt" || (document.getElementById("stNlOptInsertBoxedToPrompt")?.checked ?? true);
  if (shouldInsert) {
    droppedNames.forEach((fn) => insertNamedCitationBlock(fn, true));
  } else {
    onStNlPromptLiveCheck(document.getElementById("stNlPrompt")?.value || "");
    saveStudentModalDraft();
  }
  if ((document.getElementById("stNlPrompt")?.value || "").trim()) {
    analyzeStudentNlPrompt();
  }
}

function wrapUnbracketedCitation(filename) {
  const promptEl = document.getElementById("stNlPrompt");
  if (!promptEl || !filename) return;
  const cur = promptEl.value;
  const escaped = filename.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const replaced = cur.replace(new RegExp(`["']?${escaped}["']?`, "gi"), `[[${filename}]]`);
  promptEl.value = replaced;
  onStNlPromptLiveCheck(promptEl.value);
  saveStudentModalDraft();
  analyzeStudentNlPrompt();
}

function removeCitationBlock(filename) {
  const promptEl = document.getElementById("stNlPrompt");
  if (!promptEl || !filename) return;
  const escaped = filename.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  promptEl.value = promptEl.value
    .replace(new RegExp(`\\s*\\[\\[\\s*${escaped}\\s*\\]\\]`, "gi"), "")
    .replace(new RegExp(`\\s*@\\[[^\\]\\n]*?${escaped}\\s*\\]`, "gi"), "")
    .trim();
  onStNlPromptLiveCheck(promptEl.value);
  saveStudentModalDraft();
  if (state.lastAnalyzedHybrid && promptEl.value) {
    analyzeStudentNlPrompt();
  }
}

function onStNlAttachmentsChange(inputEl) {
  const files = Array.from(inputEl?.files || []);
  const addedNames = [];
  files.forEach((f) => {
    const entry = {
      name: f.name,
      path_or_uri: `local://${f.name}`,
      size_mb: Number((f.size / (1024 * 1024)).toFixed(2)),
      source: "picker",
    };
    _upsertLinkedAttachment(entry);
    addedNames.push(f.name);
  });
  renderStNlAttachmentChips();
  const shouldInsert = document.getElementById("stNlOptInsertBoxedToPrompt")?.checked ?? true;
  if (shouldInsert) {
    addedNames.forEach((fn) => insertNamedCitationBlock(fn, true));
  } else {
    onStNlPromptLiveCheck(document.getElementById("stNlPrompt")?.value || "");
    saveStudentModalDraft();
  }
  if (inputEl) inputEl.value = "";
  if ((document.getElementById("stNlPrompt")?.value || "").trim()) {
    analyzeStudentNlPrompt();
  }
}

function renderStNlAttachmentChips() {
  const box = document.getElementById("stNlAttachChips");
  if (!box) return;
  if (!state.nlAttachments || state.nlAttachments.length === 0) {
    box.classList.add("hidden");
    box.innerHTML = "";
    return;
  }
  box.innerHTML = `<span class="text-slate-500 font-semibold mr-0.5">Trong Link Box (${state.nlAttachments.length}):</span>` + state.nlAttachments.map((a, idx) => {
    const tooBig = (a.size_mb || 0) > 20;
    const sizeLabel = a.size_mb > 0 ? `${a.size_mb} MB${tooBig ? " >20MB!" : ""}` : "Link";
    const cls = tooBig
      ? "bg-rose-50 border-rose-400 text-rose-800 font-semibold"
      : "bg-emerald-50 border-emerald-200 text-emerald-800";
    const pathTitle = a.path_or_uri ? ` title="${_escHtml(a.path_or_uri)}"` : "";
    return `<span${pathTitle} class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md border ${cls}">
      <span>📄 ${_escHtml(a.name)} (${sizeLabel})</span>
      <button type="button" onclick="insertNamedCitationBlock('${_escHtml(a.name).replace(/'/g, "\\'")}')" title="Chèn hộp [[${_escHtml(a.name)}]] vào ô nhập" class="px-1 rounded bg-white border border-indigo-200 text-indigo-700 hover:bg-indigo-50 text-[9px] font-bold">+ 📦 Hộp</button>
      <button type="button" onclick="removeStNlAttachment(${idx})" title="Gỡ khỏi Link Box" class="hover:text-rose-700 font-bold">×</button>
    </span>`;
  }).join("");
  box.classList.remove("hidden");
}

function removeStNlAttachment(idx) {
  state.nlAttachments.splice(idx, 1);
  renderStNlAttachmentChips();
  onStNlPromptLiveCheck(document.getElementById("stNlPrompt")?.value || "");
  saveStudentModalDraft();
  if (state.lastAnalyzedHybrid && (document.getElementById("stNlPrompt")?.value || "").trim()) {
    analyzeStudentNlPrompt();
  }
}

function renderHybridDiagnostics(containerEl, hybridData, translationData, fallbackReason = "") {
  if (!containerEl) return;
  if (!hybridData) {
    containerEl.classList.add("hidden");
    containerEl.innerHTML = "";
    _setPromptRedState(false);
    return;
  }

  const errors = hybridData.errors || [];
  const rawWarns = hybridData.warnings || [];
  const quietDefaults = new Set(["W_SESSION_DEFAULTED", "W_PACING_DEFAULTED", "W_PRIORITY_DEFAULTED"]);
  const shownWarns = rawWarns.filter((w) => !quietDefaults.has(w));
  const criticalWarns = shownWarns.filter((w) => CRITICAL_CITATION_CODES.has(w));
  const softWarns = shownWarns.filter((w) => !CRITICAL_CITATION_CODES.has(w));
  const subtasks = hybridData.subtasks || [];
  const cits = hybridData.citations || {};
  const missingCits = cits.missing_attachments || [];
  const extraAtts = cits.extra_attachments || [];
  const unbracketedCits = cits.unbracketed || [];
  const malformedCits = cits.malformed_brackets || [];

  const hasRedAlert = errors.length > 0 || criticalWarns.length > 0 || missingCits.length > 0 || malformedCits.length > 0;
  if (containerEl.id === "stNlDiagnostics") {
    _setPromptRedState(hasRedAlert);
  }

  const blocks = [];

  // Summary ribbon
  const st = hybridData.status || "OK";
  const stBadgeCls =
    hasRedAlert && (errors.length > 0 || missingCits.length > 0)
      ? "bg-rose-100 text-rose-800 border-rose-400"
      : st === "OK" ? "bg-emerald-100 text-emerald-800 border-emerald-300"
      : st === "OK_WITH_WARNINGS" ? "bg-amber-100 text-amber-800 border-amber-300"
      : "bg-rose-100 text-rose-800 border-rose-400";
  const pUrg = hybridData.priority ? `UI P${hybridData.priority} (Solver P${hybridData.solver_priority || "?"})` : "Tự động";
  const splitTxt = hybridData.splitting
    ? `${hybridData.splitting.min}–${hybridData.splitting.max}p (gợi ý ${hybridData.splitting.pref}p)`
    : (hybridData.is_task_splittable === false ? "1 Buổi liền" : "Mặc định");
  const saTxt = hybridData.start_after ? ` · ⏱ Bắt đầu sau: ${_escHtml(hybridData.start_after)}` : "";
  blocks.push(
    `<div class="flex flex-wrap items-center gap-1.5 text-[10px]">
      <span class="px-1.5 py-0.5 rounded border font-bold ${stBadgeCls}">Hybrid: ${_escHtml(st)}</span>
      <span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 font-medium">${_escHtml(hybridData.work_rhythm || "BALANCED")} · ${_escHtml(splitTxt)}</span>
      <span class="px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-800 border border-indigo-200 font-medium">${_escHtml(pUrg)}${saTxt}</span>
    </div>`
  );

  if (translationData?.applied && translationData?.translated_prompt) {
    const transBox = document.getElementById("stNlTransBadge");
    if (transBox && containerEl.id === "stNlDiagnostics") {
      transBox.innerHTML = `<strong>🌐 VI→EN (${_escHtml(translationData.backend || "rule")}):</strong> ${_escHtml(translationData.translated_prompt)}`;
      transBox.classList.remove("hidden");
    } else {
      blocks.push(
        `<div class="text-[10px] px-2 py-1 rounded bg-sky-50 border border-sky-200 text-sky-900">
          <strong>🌐 VI→EN (${_escHtml(translationData.backend || "rule")}):</strong> ${_escHtml(translationData.translated_prompt)}
        </div>`
      );
    }
  }

  // RED CRITICAL BLOCKS: Formatting/Logic Errors (E_*) & Missing/Mismatched Citations
  if (errors.length > 0 || criticalWarns.length > 0) {
    const redItems = [];
    errors.forEach((e) => {
      const desc = HYBRID_DIAG_LABELS[e] || fallbackReason || e;
      redItems.push(`<li><span class="px-1 py-0.2 rounded bg-rose-200/70 font-bold mono">${_escHtml(e)}</span>: ${_escHtml(desc)}</li>`);
    });
    criticalWarns.forEach((w) => {
      const desc = HYBRID_DIAG_LABELS[w] || w;
      redItems.push(`<li><span class="px-1 py-0.2 rounded bg-rose-200/70 font-bold mono">${_escHtml(w)}</span>: ${_escHtml(desc)}</li>`);
    });
    blocks.push(
      `<div class="p-2.5 rounded-lg bg-rose-50 border-2 border-rose-400 text-[10px] text-rose-950 shadow-sm">
        <div class="font-bold mb-1 flex items-center gap-1 text-rose-800">
          <span>🛑</span>
          <span>Lỗi định dạng / Thiếu tài liệu trích dẫn (${redItems.length}):</span>
        </div>
        <ul class="list-disc pl-4 space-y-1">${redItems.join("")}</ul>
      </div>`
    );
  }

  // CITATION CROSS-COMPARISON MATRIX (Cited [[...]] / Quoted vs Attached Files)
  if ((cits.cited_files && cits.cited_files.length > 0) || (cits.attached_files && cits.attached_files.length > 0)) {
    const cmpRows = [];
    (cits.matched || []).forEach((fn) => {
      cmpRows.push(
        `<div class="flex items-center justify-between gap-2 px-2 py-1 rounded bg-emerald-50 border border-emerald-300 text-emerald-900">
          <span class="mono font-semibold">✓ [[${_escHtml(fn)}]]</span>
          <span class="text-[9px] font-bold">Đã khớp tệp đính kèm</span>
        </div>`
      );
    });
    missingCits.forEach((fn) => {
      const needsWrap = unbracketedCits.includes(fn);
      cmpRows.push(
        `<div class="flex flex-wrap items-center justify-between gap-2 px-2 py-1.5 rounded bg-rose-100 border border-rose-400 text-rose-950">
          <span class="mono font-bold">✕ ${_escHtml(needsWrap ? `"${fn}"` : `[[${fn}]]`)} — Thiếu tệp đính kèm!</span>
          <span class="flex items-center gap-1">
            ${needsWrap ? `<button type="button" onclick="wrapUnbracketedCitation('${_escHtml(fn).replace(/'/g, "\\'")}')" class="px-1.5 py-0.5 rounded bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-[9px]">🔒 Bọc [[...]]</button>` : ""}
            <label for="stNlAttachments" class="cursor-pointer px-1.5 py-0.5 rounded bg-rose-700 hover:bg-rose-800 text-white font-bold text-[9px]">📎 Đính kèm ngay</label>
          </span>
        </div>`
      );
    });
    extraAtts.forEach((fn) => {
      cmpRows.push(
        `<div class="flex items-center justify-between gap-2 px-2 py-1 rounded bg-rose-50 border border-rose-300 text-rose-900">
          <span class="mono">⚠️ Đính kèm <strong>${_escHtml(fn)}</strong> nhưng chưa trích dẫn [[${_escHtml(fn)}]]</span>
          <button type="button" onclick="insertNamedCitationBlock('${_escHtml(fn).replace(/'/g, "\\'")}')" class="px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-white font-bold text-[9px] whitespace-nowrap">➕ Chèn [[file]]</button>
        </div>`
      );
    });
    if (cmpRows.length > 0) {
      blocks.push(
        `<div class="p-2 rounded-lg bg-slate-50 border border-slate-300 text-[10px] space-y-1">
          <div class="font-bold text-slate-800">📊 Đối chiếu Trích dẫn trong ô nhập ↔ Link Box Tệp:</div>
          ${cmpRows.join("")}
        </div>`
      );
    }
  }

  if (softWarns.length > 0) {
    const warnItems = softWarns.map((w) => {
      const desc = HYBRID_DIAG_LABELS[w] || w;
      return `<li><code class="font-semibold">${_escHtml(w)}</code>: ${_escHtml(desc)}</li>`;
    }).join("");
    blocks.push(
      `<div class="p-2 rounded-lg bg-amber-50 border border-amber-200 text-[10px] text-amber-900">
        <div class="font-bold mb-0.5">⚠️ Gợi ý chuẩn hóa (${softWarns.length}):</div>
        <ul class="list-disc pl-4 space-y-0.5">${warnItems}</ul>
      </div>`
    );
  }

  if (hybridData.breakdown_required || subtasks.length > 0) {
    const bdBanner = hybridData.breakdown_required
      ? `<div class="font-bold text-purple-900 mb-1">📐 Đề xuất chia nhỏ (Breakdown Recommended) — ${subtasks.length} bước phát hiện:</div>`
      : `<div class="font-bold text-purple-900 mb-1">🧩 Danh sách bước con trích xuất (${subtasks.length}):</div>`;
    const subRows = subtasks.map((stItem, i) => {
      const minTag = stItem.work_minutes != null ? `${stItem.work_minutes}p` : "?p";
      const priTag = stItem.priority != null ? `P${stItem.priority}` : "";
      const stIcon = stItem.status === "DONE" ? "✅" : (stItem.status === "IN_PROGRESS" ? "⏳" : "⬜");
      return `<li class="flex items-center justify-between gap-2">
        <span>${stIcon} <strong>${i + 1}.</strong> ${_escHtml(stItem.title || stItem.id)}</span>
        <span class="mono text-[9px] text-purple-700 whitespace-nowrap">${_escHtml(minTag)} ${_escHtml(priTag)}</span>
      </li>`;
    }).join("");
    blocks.push(
      `<div class="p-2 rounded-lg bg-purple-50 border border-purple-200 text-[10px] text-purple-950">
        ${bdBanner}
        ${subtasks.length > 0 ? `<ul class="space-y-0.5">${subRows}</ul>` : ""}
      </div>`
    );
  }

  containerEl.innerHTML = blocks.join("");
  containerEl.classList.remove("hidden");
}

const ST_MODAL_DRAFT_KEY = "smartschedule_st_modal_draft_v1";

function saveStudentModalDraft() {
  const prompt = document.getElementById("stNlPrompt")?.value || "";
  const taskId = document.getElementById("stInpTaskId")?.value || "";
  const title = document.getElementById("stInpTitle")?.value || "";
  const duration = document.getElementById("stInpDuration")?.value || "60";
  const deadlineDay = document.getElementById("stInpDeadlineDay")?.value ?? "Wednesday";
  const deadlineTime = document.getElementById("stInpDeadlineTime")?.value || "23:59";
  const category = document.getElementById("stInpCategory")?.value || "ASSIGNMENT";
  const cognitiveLoad = document.getElementById("stInpCognitiveLoad")?.value || "2";
  const priority = document.getElementById("stInpPriority")?.value || "5";
  const splittable = document.getElementById("stInpSplittable")?.checked ?? true;
  const buffer = document.getElementById("stInpBuffer")?.checked ?? true;
  const dependsOn = document.getElementById("stInpDependsOn")?.value || "";
  const startAfter = document.getElementById("stInpStartAfter")?.value || "";
  const workRhythm = document.getElementById("stInpWorkRhythm")?.value || "BALANCED";
  const customMin = document.getElementById("stNlCustomMin")?.value || "20";
  const customMax = document.getElementById("stNlCustomMax")?.value || "45";

  // Check if anything meaningful has been entered or modified
  const hasContent = Boolean(
    prompt.trim() ||
    taskId.trim() ||
    title.trim() ||
    duration !== "60" ||
    deadlineDay !== "Wednesday" ||
    deadlineTime !== "23:59" ||
    category !== "ASSIGNMENT" ||
    priority !== "5" ||
    dependsOn.trim() ||
    startAfter.trim() ||
    (state.nlAttachments && state.nlAttachments.length > 0) ||
    state.lastAnalyzedHybrid
  );

  const badge = document.getElementById("stModalDraftBadge");
  const btnClear = document.getElementById("btnStClearDraft");

  if (!hasContent) {
    try {
      localStorage.removeItem(ST_MODAL_DRAFT_KEY);
    } catch (e) {}
    state.stModalDraft = null;
    if (badge) badge.classList.add("hidden");
    if (btnClear) btnClear.classList.add("hidden");
    return;
  }

  const draftData = {
    prompt,
    taskId,
    title,
    duration,
    deadlineDay,
    deadlineTime,
    category,
    cognitiveLoad,
    priority,
    splittable,
    buffer,
    dependsOn,
    startAfter,
    workRhythm,
    customMin,
    customMax,
    nlEngineMode: state.nlEngineMode,
    nlTransBackend: state.nlTransBackend,
    nlSession: state.nlSession,
    nlPacing: state.nlPacing,
    nlUrgency: state.nlUrgency,
    nlAttachments: state.nlAttachments || [],
    insertBoxedToPrompt: document.getElementById("stNlOptInsertBoxedToPrompt")?.checked ?? true,
    nlMinChunk: state.nlMinChunk,
    nlMaxChunk: state.nlMaxChunk,
    hybrid: state.lastAnalyzedHybrid || null,
    translation: state.lastAnalyzedTranslation || null,
    suggestedFixedEvent: state.nlSuggestedFixedEvent || null,
    updatedAt: Date.now(),
  };

  try {
    localStorage.setItem(ST_MODAL_DRAFT_KEY, JSON.stringify(draftData));
    state.stModalDraft = draftData;
    if (badge) badge.classList.remove("hidden");
    if (btnClear) btnClear.classList.remove("hidden");
  } catch (e) {
    console.warn("Could not save modal draft:", e);
  }
}

function restoreStudentModalDraft() {
  let draftData = null;
  try {
    const raw = localStorage.getItem(ST_MODAL_DRAFT_KEY);
    if (raw) draftData = JSON.parse(raw);
  } catch (e) {
    console.warn("Could not parse modal draft:", e);
  }

  const badge = document.getElementById("stModalDraftBadge");
  const btnClear = document.getElementById("btnStClearDraft");

  if (!draftData) {
    if (badge) badge.classList.add("hidden");
    if (btnClear) btnClear.classList.add("hidden");
    return false;
  }

  if (document.getElementById("stNlPrompt")) document.getElementById("stNlPrompt").value = draftData.prompt || "";
  if (document.getElementById("stInpTaskId")) document.getElementById("stInpTaskId").value = draftData.taskId || "";
  if (document.getElementById("stInpTitle")) document.getElementById("stInpTitle").value = draftData.title || "";
  if (document.getElementById("stInpDuration")) document.getElementById("stInpDuration").value = draftData.duration || "60";
  if (document.getElementById("stInpDeadlineDay")) document.getElementById("stInpDeadlineDay").value = draftData.deadlineDay ?? "Wednesday";
  if (document.getElementById("stInpDeadlineTime")) document.getElementById("stInpDeadlineTime").value = draftData.deadlineTime || "23:59";
  if (document.getElementById("stInpStartAfter")) document.getElementById("stInpStartAfter").value = draftData.startAfter || "";
  if (document.getElementById("stInpWorkRhythm")) document.getElementById("stInpWorkRhythm").value = draftData.workRhythm || "BALANCED";
  if (document.getElementById("stInpPriorityCore")) {
    document.getElementById("stInpPriorityCore").value =
      draftData.nlUrgency === null || draftData.nlUrgency === undefined ? "auto" : String(draftData.nlUrgency);
  }
  if (document.getElementById("stInpCategory")) document.getElementById("stInpCategory").value = draftData.category || "ASSIGNMENT";
  if (document.getElementById("stInpCognitiveLoad")) document.getElementById("stInpCognitiveLoad").value = String(draftData.cognitiveLoad || 2);
  if (document.getElementById("stInpPriority")) document.getElementById("stInpPriority").value = String(draftData.priority || 5);
  if (document.getElementById("stInpSplittable")) document.getElementById("stInpSplittable").checked = draftData.splittable !== false;
  if (document.getElementById("stInpBuffer")) document.getElementById("stInpBuffer").checked = draftData.buffer !== false;
  if (document.getElementById("stInpDependsOn")) document.getElementById("stInpDependsOn").value = draftData.dependsOn || "";
  if (document.getElementById("stNlCustomMin")) document.getElementById("stNlCustomMin").value = draftData.customMin || "20";
  if (document.getElementById("stNlCustomMax")) document.getElementById("stNlCustomMax").value = draftData.customMax || "45";
  if (document.getElementById("stNlOptInsertBoxedToPrompt")) {
    document.getElementById("stNlOptInsertBoxedToPrompt").checked = draftData.insertBoxedToPrompt !== false;
  }

  if (draftData.nlEngineMode) setStudentNlEngine(draftData.nlEngineMode);
  if (draftData.nlTransBackend) {
    setStNlTransBackend(draftData.nlTransBackend);
    const sel = document.getElementById("stNlTransBackend");
    if (sel) sel.value = draftData.nlTransBackend;
  }
  if (draftData.nlSession) setStNlSession(draftData.nlSession);
  if (draftData.nlPacing) setStNlPacing(draftData.nlPacing);
  if (draftData.nlUrgency !== undefined) setStNlUrgency(draftData.nlUrgency);

  state.nlAttachments = draftData.nlAttachments || [];
  renderStNlAttachmentChips();
  onStNlPromptLiveCheck(draftData.prompt || "");

  if (draftData.hybrid) {
    state.lastAnalyzedHybrid = draftData.hybrid;
    state.lastAnalyzedTranslation = draftData.translation;
    const diagEl = document.getElementById("stNlDiagnostics");
    renderHybridDiagnostics(diagEl, draftData.hybrid, draftData.translation);
  }

  if (draftData.suggestedFixedEvent) {
    state.nlSuggestedFixedEvent = draftData.suggestedFixedEvent;
    const banner = document.getElementById("stNlFixedBanner");
    const desc = document.getElementById("stNlFixedDesc");
    if (banner && desc) {
      const fe = draftData.suggestedFixedEvent;
      desc.textContent = `${fe.day_of_week} ${fe.start_time}–${fe.end_time} (${fe.category})`;
      banner.classList.remove("hidden");
    }
  }

  if (badge) badge.classList.remove("hidden");
  if (btnClear) btnClear.classList.remove("hidden");
  updateStBufferPreview();
  return true;
}

function clearStudentModalDraft(confirmFirst = false) {
  if (confirmFirst && !confirm("Bạn có chắc chắn muốn xóa bản nháp và nhập lại từ đầu?")) {
    return;
  }
  try {
    localStorage.removeItem(ST_MODAL_DRAFT_KEY);
  } catch (e) {}
  state.stModalDraft = null;
  state.lastAnalyzedHybrid = null;
  state.lastAnalyzedTranslation = null;
  state.nlSuggestedFixedEvent = null;
  state.nlAttachments = [];

  if (document.getElementById("stNlPrompt")) document.getElementById("stNlPrompt").value = "";
  if (document.getElementById("stInpTaskId")) document.getElementById("stInpTaskId").value = "";
  if (document.getElementById("stInpTitle")) document.getElementById("stInpTitle").value = "";
  if (document.getElementById("stInpDuration")) document.getElementById("stInpDuration").value = "60";
  if (document.getElementById("stInpDeadlineDay")) document.getElementById("stInpDeadlineDay").value = "Wednesday";
  if (document.getElementById("stInpDeadlineTime")) document.getElementById("stInpDeadlineTime").value = "23:59";
  if (document.getElementById("stInpCategory")) document.getElementById("stInpCategory").value = "ASSIGNMENT";
  if (document.getElementById("stInpCognitiveLoad")) document.getElementById("stInpCognitiveLoad").value = "2";
  if (document.getElementById("stInpPriority")) document.getElementById("stInpPriority").value = "5";
  if (document.getElementById("stInpSplittable")) document.getElementById("stInpSplittable").checked = true;
  if (document.getElementById("stInpBuffer")) document.getElementById("stInpBuffer").checked = true;
  if (document.getElementById("stInpDependsOn")) document.getElementById("stInpDependsOn").value = "";
  if (document.getElementById("stInpStartAfter")) document.getElementById("stInpStartAfter").value = "";
  if (document.getElementById("stInpWorkRhythm")) document.getElementById("stInpWorkRhythm").value = "BALANCED";
  if (document.getElementById("stInpPriorityCore")) document.getElementById("stInpPriorityCore").value = "auto";

  setStNlSession("splittable");
  setStNlPacing("BALANCED");
  setStNlUrgency(null);
  renderStNlAttachmentChips();
  onStNlPromptLiveCheck("");
  resetStudentNlFeedback();
  updateStBufferPreview();

  const badge = document.getElementById("stModalDraftBadge");
  if (badge) badge.classList.add("hidden");
  const btnClear = document.getElementById("btnStClearDraft");
  if (btnClear) btnClear.classList.add("hidden");
}

function resetStudentNlFeedback() {
  state.nlSuggestedFixedEvent = null;
  _setPromptRedState(false);
  const nlSt = document.getElementById("stNlStatus");
  if (nlSt) {
    nlSt.className = "text-[10px] text-slate-500 hidden";
    nlSt.textContent = "";
  }
  const badge = document.getElementById("stNlEngineBadge");
  if (badge) {
    badge.className = "hidden px-1.5 py-0.5 rounded text-[9px] font-bold";
    badge.textContent = "";
  }
  const transBadge = document.getElementById("stNlTransBadge");
  if (transBadge) {
    transBadge.classList.add("hidden");
    transBadge.innerHTML = "";
  }
  const chips = document.getElementById("stNlChips");
  if (chips) {
    chips.classList.add("hidden");
    chips.innerHTML = "";
  }
  const diagEl = document.getElementById("stNlDiagnostics");
  if (diagEl) {
    diagEl.classList.add("hidden");
    diagEl.innerHTML = "";
  }
  const fixedBanner = document.getElementById("stNlFixedBanner");
  if (fixedBanner) fixedBanner.classList.add("hidden");
}

function renderStDependsOnCandidates() {
  const box = document.getElementById("stExistingTaskIdChips");
  if (!box) return;
  const tasks = state.tasks || [];
  if (tasks.length === 0) {
    box.innerHTML = `<span class="text-slate-400">Chưa có task nào trong hàng đợi để tham chiếu.</span>`;
    return;
  }
  const curIds = new Set(
    (document.getElementById("stInpDependsOn")?.value || "")
      .split(",")
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean)
  );
  box.innerHTML = `<span class="text-slate-500 font-semibold mr-0.5">Chọn nhanh Task ID hiện có:</span>` + tasks.map((t) => {
    const tid = String(t.task_id || t.id || "").trim();
    const active = curIds.has(tid.toUpperCase());
    const cls = active
      ? "bg-indigo-100 border-indigo-400 text-indigo-900 font-bold"
      : "bg-slate-100 border-slate-300 text-slate-700 hover:bg-slate-200";
    return `<button type="button" onclick="toggleStDependsOnId('${_escHtml(tid).replace(/'/g, "\\'")}')"
      class="px-2 py-0.5 rounded border ${cls} mono transition">
      ${active ? "✓" : "+"} ${_escHtml(tid)} <span class="font-sans text-slate-500">(${_escHtml((t.title || "").slice(0, 18))})</span>
    </button>`;
  }).join("");
}

function toggleStDependsOnId(tid) {
  const inp = document.getElementById("stInpDependsOn");
  if (!inp || !tid) return;
  const items = inp.value.split(",").map((s) => s.trim()).filter(Boolean);
  const idx = items.findIndex((s) => s.toUpperCase() === tid.toUpperCase());
  if (idx >= 0) {
    items.splice(idx, 1);
  } else {
    items.push(tid);
  }
  inp.value = items.join(", ");
  renderStDependsOnCandidates();
  saveStudentModalDraft();
}

function openStudentTaskModal() {
  state.editingTaskId = null;
  const btnSave = document.getElementById("btnSaveStTask");
  if (btnSave) btnSave.innerHTML = `<span>➕</span> Thêm & Lên Lịch Ngay`;
  const restored = restoreStudentModalDraft();
  if (!restored) {
    clearStudentModalDraft(false);
  }
  const tidInp = document.getElementById("stInpTaskId");
  if (tidInp) {
    tidInp.placeholder = `VD: TASK-${state.tasks.length + 1} (tự tạo)`;
  }
  syncTaskModalModeVisibility();
  renderStDependsOnCandidates();
  document.getElementById("stTaskModal")?.classList.remove("hidden");
  const targetFocus = (document.getElementById("stNlPrompt")?.value)
    ? document.getElementById("stInpTitle")
    : (document.getElementById("stNlPrompt") || document.getElementById("stInpTitle"));
  targetFocus?.focus();
  updateStBufferPreview();
}

function editStudentTask(tid) {
  const t = state.tasks.find((x) => (x.task_id || x.id) === tid);
  if (!t) return;
  clearStudentModalDraft(false);
  state.editingTaskId = tid;
  const btnSave = document.getElementById("btnSaveStTask");
  if (btnSave) btnSave.innerHTML = `<span>💾</span> Lưu Cập Nhật`;

  if (document.getElementById("stInpTaskId")) document.getElementById("stInpTaskId").value = t.task_id || t.id || "";
  if (document.getElementById("stInpTitle")) document.getElementById("stInpTitle").value = t.title || "";
  if (document.getElementById("stInpDuration")) document.getElementById("stInpDuration").value = String(t.duration_min || t.estimate_min || 60);
  if (document.getElementById("stInpDeadlineDay")) document.getElementById("stInpDeadlineDay").value = t.deadline_day || "";
  if (document.getElementById("stInpDeadlineTime")) document.getElementById("stInpDeadlineTime").value = t.deadline_time || "23:59";
  if (document.getElementById("stInpCategory")) document.getElementById("stInpCategory").value = t.category || (t.deadline_day ? "ASSIGNMENT" : "HABIT");
  if (document.getElementById("stInpCognitiveLoad")) document.getElementById("stInpCognitiveLoad").value = String(t.cognitive_load || 2);
  if (document.getElementById("stInpPriority")) document.getElementById("stInpPriority").value = String(t.priority || 3);
  if (document.getElementById("stInpStartAfter")) document.getElementById("stInpStartAfter").value = t.start_after || "";
  if (document.getElementById("stInpDependsOn")) document.getElementById("stInpDependsOn").value = (t.depends_on || t.after || []).join(", ");
  if (document.getElementById("stInpBuffer")) document.getElementById("stInpBuffer").checked = t.buffer_mode !== "NONE";

  const userUrg = _mapSolverToUserUrgency(t.priority || 3);
  setStNlUrgency(userUrg);
  setStNlPacing(t.work_rhythm || "BALANCED");
  setStNlSession(t.is_splittable === false ? "single" : "splittable");
  if (document.getElementById("stInpWorkRhythm")) {
    document.getElementById("stInpWorkRhythm").value = t.work_rhythm || "BALANCED";
  }

  syncTaskModalModeVisibility();
  const advDet = document.getElementById("stTaskAdvDetails");
  if (advDet && (t.start_after || (t.depends_on && t.depends_on.length > 0))) {
    advDet.open = true;
  }
  renderStDependsOnCandidates();
  document.getElementById("stTaskModal")?.classList.remove("hidden");
  updateStBufferPreview();
  document.getElementById("stInpTitle")?.focus();
}

function closeStudentTaskModal() {
  saveStudentModalDraft();
  document.getElementById("stTaskModal")?.classList.add("hidden");
}

function setStDuration(val) {
  const inp = document.getElementById("stInpDuration");
  if (inp) inp.value = val;
  updateStBufferPreview();
}

function updateStBufferPreview() {
  const raw = Math.max(15, parseInt(document.getElementById("stInpDuration")?.value || "60", 10));
  const isBuffer = document.getElementById("stInpBuffer")?.checked ?? true;
  const load = parseInt(document.getElementById("stInpCognitiveLoad")?.value || "2", 10);
  const durPreview = document.getElementById("stDurationPreview");
  const txtPreview = document.getElementById("stBufferPreviewText");

  if (durPreview) durPreview.textContent = `${raw} phút`;

  if (!isBuffer) {
    if (txtPreview) {
      txtPreview.innerHTML = `Thời lượng xếp lịch: <strong>${raw}p</strong> (Không thêm thời gian đệm).`;
    }
    return;
  }

  const mode = state.commitments?.buffer_mode || "HABIT";
  if (mode === "COGNITIVE_LOAD") {
    const aLight = Number(state.commitments?.alpha_light || 1.2);
    const aHeavy = Number(state.commitments?.alpha_heavy || 1.35);
    const alpha = load >= 3 ? aHeavy : aLight;
    const planned = Math.ceil((raw * alpha) / 15) * 15;
    if (txtPreview) {
      txtPreview.innerHTML = `Chế độ <strong>COGNITIVE_LOAD (α=${alpha.toFixed(2)})</strong>: <strong>${raw}p → ${planned}p</strong> (tính 1 lần ở backend, chống trễ hạn).`;
    }
  } else {
    const mult = currentBufferMultiplier();
    const planned = plannedMinutesFor(raw, mult);
    const habitLabel = state.commitments?.estimate_habit || "V0 (×1.00)";
    if (txtPreview) {
      txtPreview.innerHTML = mult > 1
        ? `Chế độ <strong>Habit (${habitLabel}, ×${mult})</strong>: <strong>${raw}p → ${planned}p</strong> (backend tự tính, không nhân trùng).`
        : `Đang đặt <strong>${habitLabel}</strong>: thời lượng giữ <strong>${planned}p</strong> (bạn có thể bật Habit / Cognitive Load trong ⚙️ Cài Đặt).`;
    }
  }
}

function applyNlChipSuggestion(field, value) {
  if (field === "duration_min") {
    setStDuration(parseInt(value, 10) || 60);
  } else if (field === "deadline_day") {
    const daySel = document.getElementById("stInpDeadlineDay");
    if (daySel) daySel.value = String(value ?? "");
    if (!value) {
      const catSel = document.getElementById("stInpCategory");
      if (catSel) catSel.value = "HABIT";
    }
    updateStBufferPreview();
  }
}

function renderStudentNlChips(suggestions) {
  const box = document.getElementById("stNlChips");
  if (!box) return;
  box.innerHTML = "";
  if (!Array.isArray(suggestions) || suggestions.length === 0) {
    box.classList.add("hidden");
    return;
  }
  const hint = document.createElement("span");
  hint.className = "text-[10px] font-semibold text-slate-600";
  hint.textContent = "Chọn nhanh:";
  box.appendChild(hint);

  suggestions.forEach((chip) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "px-2 py-0.5 rounded-full bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 text-indigo-800 text-[10px] font-semibold transition";
    btn.textContent = chip.label || String(chip.value);
    btn.onclick = () => applyNlChipSuggestion(chip.field, chip.value);
    box.appendChild(btn);
  });
  box.classList.remove("hidden");
}

async function lockNlFixedEvent() {
  const fe = state.nlSuggestedFixedEvent;
  if (!fe) return;
  if (!state.commitments.fixed_events) state.commitments.fixed_events = [];
  state.commitments.fixed_events.push({
    event_id: fe.event_id || `FIXED_NL_${Date.now().toString().slice(-4)}`,
    title: document.getElementById("stInpTitle")?.value.trim() || fe.title || "Lịch cố định",
    day_of_week: fe.day_of_week,
    start_time: fe.start_time,
    end_time: fe.end_time,
    category: fe.category || "MEETING",
  });
  const inpNl = document.getElementById("stNlPrompt");
  if (inpNl) inpNl.value = "";
  const inpT = document.getElementById("stInpTitle");
  if (inpT) inpT.value = "";
  closeStudentTaskModal();
  syncAllLeftPanels();
  await solveSchedule();
}

async function analyzeStudentNlPrompt() {
  const inp = document.getElementById("stNlPrompt");
  const statusEl = document.getElementById("stNlStatus");
  const badgeEl = document.getElementById("stNlEngineBadge");
  const diagEl = document.getElementById("stNlDiagnostics");
  const fixedBannerEl = document.getElementById("stNlFixedBanner");
  const fixedDescEl = document.getElementById("stNlFixedDesc");
  const prompt = (inp?.value || "").trim();
  if (!prompt) return;

  resetStudentNlFeedback();
  if (statusEl) {
    statusEl.className = "text-[10px] text-indigo-600 font-medium";
    statusEl.textContent = "⏳ Đang phân tích ngôn ngữ tự nhiên (Hybrid Pipeline)...";
  }

  // Gather UI WorkRhythm + 1=Urgent..4=Low + Attachments context
  const uiCustom = state.nlPacing === "CUSTOM"
    ? {
        min: parseInt(document.getElementById("stNlCustomMin")?.value || "20", 10),
        max: parseInt(document.getElementById("stNlCustomMax")?.value || "45", 10),
      }
    : null;
  const uiContext = {
    session: state.nlSession || "splittable",
    pacing: state.nlPacing || "BALANCED",
    custom: uiCustom,
    priority: state.nlUrgency,
    attachments: state.nlAttachments || [],
  };

  try {
    const res = await fetch("/api/tasks/natural-add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        now: state.commitments?.now || null,
        existing_count: state.tasks.length,
        engine: state.nlEngineMode || "auto",
        translation_backend: state.nlTransBackend || "rule",
        ui: uiContext,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    if (badgeEl) {
      const isAi = data.engine_used === "AI_GEMINI";
      badgeEl.textContent = isAi ? "✨ Gemini AI + Hybrid" : "⚡ Offline Hybrid";
      badgeEl.className = isAi
        ? "px-1.5 py-0.5 rounded text-[9px] font-bold bg-indigo-100 text-indigo-700"
        : "px-1.5 py-0.5 rounded text-[9px] font-bold bg-slate-200 text-slate-700";
    }

    if (data.status === "NO_TASK" || data.status === "INVALID") {
      if (statusEl) {
        statusEl.className = "text-[10px] text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-2 py-1.5 font-medium";
        statusEl.textContent = `🚫 ${data.rejection_reason || "Câu nhập không phải công việc cần xếp lịch."}`;
      }
      renderHybridDiagnostics(diagEl, data.hybrid, data.translation, data.rejection_reason);
      return;
    }

    const d = data.draft || {};
    if (document.getElementById("stInpTitle")) document.getElementById("stInpTitle").value = d.title || prompt;
    if (document.getElementById("stInpDuration")) document.getElementById("stInpDuration").value = d.duration_min || 60;
    if (document.getElementById("stInpDeadlineDay")) document.getElementById("stInpDeadlineDay").value = d.deadline_day || "";
    if (document.getElementById("stInpDeadlineTime")) document.getElementById("stInpDeadlineTime").value = d.deadline_time || "23:59";
    if (document.getElementById("stInpPriority")) document.getElementById("stInpPriority").value = String(d.priority || 3);
    const derivedUrg = d.user_priority || _mapSolverToUserUrgency(d.priority || 3);
    _renderUrgencyPills(derivedUrg);
    if (document.getElementById("stInpPriorityCore")) document.getElementById("stInpPriorityCore").value = String(derivedUrg);
    if (document.getElementById("stInpStartAfter") && d.start_after) document.getElementById("stInpStartAfter").value = d.start_after;
    if (d.work_rhythm) {
      setStNlPacing(d.work_rhythm);
    }

    const catEl = document.getElementById("stInpCategory");
    if (catEl) {
      const targetCat = d.category || "ASSIGNMENT";
      const hasOption = Array.from(catEl.options).some((opt) => opt.value === targetCat);
      catEl.value = hasOption ? targetCat : "ASSIGNMENT";
    }
    if (document.getElementById("stInpCognitiveLoad")) document.getElementById("stInpCognitiveLoad").value = String(d.cognitive_load || 2);
    if (document.getElementById("stInpSplittable")) document.getElementById("stInpSplittable").checked = d.is_splittable !== false;

    state.nlMinChunk = d.min_chunk_min || 30;
    state.nlMaxChunk = d.max_chunk_min || 60;
    state.nlSession = d.is_splittable === false ? "single" : "splittable";
    _refreshStNlChunkUI();
    updateStBufferPreview();

    renderStudentNlChips(data.suggestions || []);
    renderHybridDiagnostics(diagEl, data.hybrid, data.translation);

    if (data.suggested_fixed_event && fixedBannerEl && fixedDescEl) {
      const fe = data.suggested_fixed_event;
      state.nlSuggestedFixedEvent = fe;
      const locStr = data.location ? ` · 📍 ${data.location}` : "";
      fixedDescEl.textContent = `${fe.day_of_week} ${fe.start_time}–${fe.end_time} (${fe.category})${locStr}`;
      fixedBannerEl.classList.remove("hidden");
    }

    if (statusEl) {
      const warns = data.validation?.warnings || [];
      const locBadge = data.location ? ` · 📍 ${data.location}` : "";
      const dlText = d.deadline_day ? `${d.deadline_day} ${d.deadline_time}` : "Habit (Không hạn chót)";
      statusEl.className = warns.length > 0
        ? "text-[10px] text-amber-700 font-medium"
        : "text-[10px] text-emerald-700 font-medium";
      statusEl.textContent = warns.length > 0
        ? `⚠️ Đã điền (${dlText}${locBadge}): ${warns.join(" ")}`
        : `✓ Đã phân tích Hybrid: ${d.category} · Solver P${d.priority} (UI P${d.user_priority || "?"}) · ${d.work_rhythm || "BALANCED"} · ${dlText}${locBadge}`;
    }
    state.lastAnalyzedHybrid = data.hybrid;
    state.lastAnalyzedTranslation = data.translation;
    saveStudentModalDraft();
  } catch (err) {
    if (statusEl) {
      statusEl.className = "text-[10px] text-rose-600 font-medium";
      statusEl.textContent = `Lỗi phân tích M1: ${err.message}`;
    }
  }
}

async function saveStudentTask() {
  const rawTid = (document.getElementById("stInpTaskId")?.value || "").trim().toUpperCase().replace(/\s+/g, "_");
  const title = document.getElementById("stInpTitle")?.value.trim() || "Bài tập mới";
  const rawDur = Math.max(15, parseInt(document.getElementById("stInpDuration")?.value || "60", 10));
  const isBuffer = document.getElementById("stInpBuffer")?.checked ?? true;
  const deadlineDay = document.getElementById("stInpDeadlineDay")?.value || null;
  const deadlineTime = document.getElementById("stInpDeadlineTime")?.value || "23:59";
  const priority = parseInt(document.getElementById("stInpPriority")?.value || "3", 10);
  const category = document.getElementById("stInpCategory")?.value || (deadlineDay ? "ASSIGNMENT" : "HABIT");
  const cognitiveLoad = parseInt(document.getElementById("stInpCognitiveLoad")?.value || "2", 10);
  const isSplittable = document.getElementById("stInpSplittable")?.checked ?? true;
  const dependsOnStr = document.getElementById("stInpDependsOn")?.value.trim() || "";
  const startAfter = document.getElementById("stInpStartAfter")?.value.trim() || null;
  const workRhythm = document.getElementById("stInpWorkRhythm")?.value || state.nlPacing || "BALANCED";

  const isEditing = Boolean(state.editingTaskId);
  let tid = rawTid || (isEditing ? state.editingTaskId : `TASK_${state.tasks.length + 1}`);
  const existingIds = new Set(
    state.tasks
      .filter((t) => !isEditing || (t.task_id || t.id) !== state.editingTaskId)
      .map((t) => String(t.task_id || t.id || "").toUpperCase())
  );
  if (existingIds.has(tid.toUpperCase())) {
    tid = `${tid}_${Date.now().toString().slice(-3)}`;
  }
  const dependsOn = dependsOnStr ? dependsOnStr.split(",").map((s) => s.trim()).filter(Boolean) : [];
  const effMinChunk = isSplittable ? Math.max(15, parseInt(state.nlMinChunk || 30, 10)) : rawDur;
  const effMaxChunk = isSplittable ? Math.max(effMinChunk, parseInt(state.nlMaxChunk || 60, 10)) : rawDur;

  // Send raw duration_min cleanly — backend applies Planning Fallacy buffer ONCE (zero double-buffering)
  const taskPayload = {
    task_id: tid,
    title,
    duration_min: rawDur,
    deadline_day: deadlineDay,
    deadline_time: deadlineTime,
    priority,
    is_splittable: isSplittable,
    min_chunk_min: effMinChunk,
    max_chunk_min: effMaxChunk,
    work_rhythm: workRhythm,
    start_after: startAfter,
    depends_on: dependsOn,
    category: deadlineDay ? category : "HABIT",
    cognitive_load: cognitiveLoad,
  };
  if (!isBuffer) {
    taskPayload.buffer_mode = "NONE";
    taskPayload.buffer_multiplier = 1.0;
  }

  if (isEditing) {
    const idx = state.tasks.findIndex((t) => (t.task_id || t.id) === state.editingTaskId);
    if (idx >= 0) state.tasks[idx] = taskPayload;
    else state.tasks.push(taskPayload);
  } else {
    state.tasks.push(taskPayload);
  }
  state.editingTaskId = null;
  clearStudentModalDraft(false);
  document.getElementById("stTaskModal")?.classList.add("hidden");

  syncAllLeftPanels();
  savePersistedStudentState();
  await solveSchedule();
}

async function deleteStudentTask(tid) {
  state.tasks = state.tasks.filter((t) => (t.task_id || t.id) !== tid);
  state.taskBufferMap.delete(tid);
  savePersistedStudentState();
  syncAllLeftPanels();
  await solveSchedule();
}

// Pin & Done Block Handlers (with localStorage persistence + M7 feedback)
async function togglePinBlock(blockId) {
  if (state.pinnedBlocks.has(blockId)) {
    state.pinnedBlocks.delete(blockId);
  } else {
    const block = (state.currentSchedule?.blocks || []).find((b) => b.block_id === blockId);
    if (block) {
      state.pinnedBlocks.set(blockId, block);
    }
  }
  savePersistedStudentState();
  await solveSchedule();
}

function toggleDoneBlock(blockId) {
  if (state.doneBlocks.has(blockId)) {
    state.doneBlocks.delete(blockId);
  } else {
    state.doneBlocks.add(blockId);
  }
  savePersistedStudentState();
  renderStudentViews();
}

async function submitBlockCheckIn(blockId, inputId = "stActualMinInput") {
  const block = (state.currentSchedule?.blocks || []).find((b) => b.block_id === blockId);
  if (!block) return;
  const actInp = document.getElementById(inputId) || document.getElementById("stActualMinInput");
  const actualMin = Math.max(15, parseInt(actInp?.value || String(block.duration_min), 10));
  state.actualDurations.set(blockId, actualMin);
  state.doneBlocks.add(blockId);
  savePersistedStudentState();

  let msg = "";
  try {
    const res = await fetch("/api/tasks/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: block.task_id,
        estimated_min: block.duration_min,
        actual_duration_min: actualMin,
        completed: true,
      }),
    });
    const data = await res.json();
    msg = `✓ Đã ghi nhận ${actualMin}p (tỷ lệ ×${data.overrun_ratio}). Gợi ý hệ số cá nhân tiếp theo: ${data.recommended_estimate_habit} (α≈${data.recommended_alpha}).`;
  } catch (_) {}

  renderStudentViews();
  if (msg) {
    for (const fid of ["stCheckInFeedback", "stHeroCheckInFeedback"]) {
      const fEl = document.getElementById(fid);
      if (fEl) {
        fEl.classList.remove("hidden");
        fEl.textContent = msg;
      }
    }
  }
}

function openWhyHereModal(blockId) {
  const block = (state.currentSchedule?.blocks || []).find((b) => b.block_id === blockId);
  if (!block) return;

  const modal = document.getElementById("stWhyHereModal");
  const body = document.getElementById("stWhyHereBody");
  const actions = document.getElementById("stWhyHereActions");
  if (!modal || !body) return;

  const isPinned = state.pinnedBlocks.has(blockId);
  const isDone = state.doneBlocks.has(blockId);
  const sleepCfg = state.commitments?.sleep_schedule || {};
  const sleepWin = `${sleepCfg.daily_start_time || "23:30"}–${sleepCfg.daily_end_time || "06:30"}`;
  const solverUsed = state.currentSchedule?.solver_used || "EDF";
  const structuredReasons = Array.isArray(block.reasons) ? block.reasons : [];
  const savedActual = state.actualDurations.get(blockId) || block.duration_min;

  body.innerHTML = `
    <div class="p-3 bg-indigo-50 border border-indigo-200 rounded-xl space-y-1">
      <div class="font-bold text-sm text-indigo-950">${block.title} ${block.total_chunks > 1 ? `(Phiên ${block.chunk_index}/${block.total_chunks})` : ''}</div>
      <div class="text-xs text-indigo-800 font-semibold mono">📅 ${block.day}, ${block.start_time} – ${block.end_time} (${block.duration_min} phút)</div>
    </div>

    <div class="space-y-2 pt-1">
      <div class="font-bold text-slate-800 text-xs">Cơ sở toán học thuật toán chọn vị trí này:</div>
      <ul class="space-y-1.5 list-disc list-inside text-slate-600 text-xs">
        <li><strong>Thuật toán:</strong> <span class="mono">${solverUsed}</span>.</li>
        <li><strong>Hạn chót:</strong> ${block.deadline_str || 'Linh hoạt'} (Độ ưu tiên: P${block.priority}, Load-${block.cognitive_load || 2}).</li>
        <li><strong>Bảo toàn ràng buộc cứng H1 & H2:</strong> Không xâm phạm giờ ngủ (<span class="mono">${sleepWin}</span>) hay lớp học.</li>
        ${block.total_chunks > 1 ? `<li><strong>Cắt nhỏ thông minh (Chunking):</strong> Chia thành phiên ${block.duration_min}p (tối đa 90p Deep Work) kèm nghỉ ngắn 15p.</li>` : ''}
        <li><strong>Lý do tổng hợp:</strong> ${block.reason || 'Đặt vào khe tối ưu trước hạn chót.'}</li>
      </ul>
      ${
        structuredReasons.length > 0
          ? `<div class="flex flex-wrap gap-1 pt-1">
              ${structuredReasons.map((r) => `<span class="px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 text-[10px] font-semibold text-slate-700" title="${r.text || ""}">#${r.code}</span>`).join("")}
            </div>`
          : ""
      }
      <div class="mt-2 p-2.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1.5">
        <div class="font-bold text-[11px] text-slate-700">⏱️ Ghi nhận thời gian thực tế (M7 Feedback Loop):</div>
        <div class="flex items-center gap-2">
          <input id="stActualMinInput" type="number" min="15" step="15" value="${savedActual}" class="w-20 px-2 py-1 text-xs rounded border border-slate-300 mono" />
          <span class="text-[11px] text-slate-500">phút thực tế</span>
          <button onclick="submitBlockCheckIn('${blockId}')" class="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[11px] font-bold">Lưu & Done</button>
        </div>
        <div id="stCheckInFeedback" class="hidden text-[10px] text-emerald-700 font-medium"></div>
      </div>
    </div>`;

  actions.innerHTML = `
    <div class="flex items-center gap-2">
      <button onclick="togglePinBlock('${blockId}'); closeWhyHereModal();" class="px-3 py-1.5 rounded-lg ${isPinned ? 'bg-amber-500 text-white font-bold' : 'bg-slate-100 hover:bg-slate-200 text-slate-800'} text-xs font-semibold transition">
        <span>📌</span> ${isPinned ? 'Bỏ Ghim' : 'Ghim Phiên Này'}
      </button>
      <button onclick="toggleDoneBlock('${blockId}'); closeWhyHereModal();" class="px-3 py-1.5 rounded-lg ${isDone ? 'bg-emerald-600 text-white font-bold' : 'bg-slate-100 hover:bg-slate-200 text-slate-800'} text-xs font-semibold transition">
        <span>✓</span> ${isDone ? 'Chưa Xong' : 'Đã Hoàn Thành'}
      </button>
    </div>
    <button onclick="closeWhyHereModal()" class="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-bold transition">Đóng</button>
  `;

  modal.classList.remove("hidden");
}

function closeWhyHereModal() {
  document.getElementById("stWhyHereModal")?.classList.add("hidden");
}

// ============================================================================
// STUDENT SETTINGS MODAL, M5 DISRUPTION, M6 OVERLOAD PREVIEW & UNDO, DRAG/DROP
// ============================================================================

function toggleAlphaInputsInSettings() {
  const mode = document.getElementById("stSetBufferMode")?.value || "COGNITIVE_LOAD";
  document.getElementById("stSetHabitRow")?.classList.toggle("hidden", mode === "COGNITIVE_LOAD");
  document.getElementById("stSetAlphaRow")?.classList.toggle("hidden", mode !== "COGNITIVE_LOAD");
}

function renderStudentSettingsHabits() {
  _renderHabitCardsInto(document.getElementById("stSetHabitsList"), false);
  renderStudentMainHabits();
}

function addStudentPersonalHabit() {
  _addHabitFromInputs("stHabitNew");
}

async function removeStudentPersonalHabit(idx, autoSolve = false) {
  const habits = state.commitments?.personal_habits || [];
  habits.splice(idx, 1);
  renderStudentSettingsHabits();
  savePersistedStudentState();
  if (autoSolve) {
    await solveSchedule();
  }
}

function openStudentSettingsModal() {
  const sleep = state.commitments?.sleep_schedule || {};
  document.getElementById("stSetSleepStart").value = sleep.daily_start_time || "23:30";
  document.getElementById("stSetSleepEnd").value = sleep.daily_end_time || "06:30";
  document.getElementById("stSetFocusPref").value = state.commitments?.focus_preference || "BALANCED";
  document.getElementById("stSetBufferMode").value = state.commitments?.buffer_mode || (state.appMode === "STUDENT" ? "COGNITIVE_LOAD" : "HABIT");
  document.getElementById("stSetEstimateHabit").value = state.commitments?.estimate_habit || "";
  document.getElementById("stSetAlphaLight").value = String(state.commitments?.alpha_light ?? 1.2);
  document.getElementById("stSetAlphaHeavy").value = String(state.commitments?.alpha_heavy ?? 1.35);
  document.getElementById("stSetSolver").value = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";
  if (document.getElementById("stSetHorizonDays")) {
    document.getElementById("stSetHorizonDays").value = String(Number(state.commitments?.horizon_days || 7) >= 14 ? 14 : 7);
  }
  if (document.getElementById("stSetNowMode")) {
    document.getElementById("stSetNowMode").value = state.useRealTimeNow ? "REALTIME" : "KEEP";
  }
  document.getElementById("stSetSleepWarning")?.classList.add("hidden");
  renderStudentSettingsHabits();
  toggleAlphaInputsInSettings();
  document.getElementById("stSettingsModal")?.classList.remove("hidden");
}

function closeStudentSettingsModal() {
  document.getElementById("stSettingsModal")?.classList.add("hidden");
}

async function saveStudentSettings() {
  const sStart = document.getElementById("stSetSleepStart")?.value || "23:30";
  const sEnd = document.getElementById("stSetSleepEnd")?.value || "06:30";
  const [sh, sm] = sStart.split(":").map(Number);
  const [eh, em] = sEnd.split(":").map(Number);
  const startMin = (sh || 0) * 60 + (sm || 0);
  const endMin = (eh || 0) * 60 + (em || 0);
  const sleepDurMin = endMin > startMin ? endMin - startMin : (1440 - startMin + endMin);

  if (sleepDurMin < 360) {
    const warnEl = document.getElementById("stSetSleepWarning");
    if (warnEl) {
      warnEl.classList.remove("hidden");
      warnEl.textContent = "⚠️ Pattern 6: Ngủ tối thiểu phải ≥ 6 tiếng/đêm. Hệ thống sẽ tự động khóa đủ 6h nếu thấp hơn.";
    }
  }

  state.commitments.sleep_schedule = {
    daily_start_time: sStart,
    daily_end_time: sEnd,
    is_hard_lock: true,
  };
  state.commitments.focus_preference = document.getElementById("stSetFocusPref")?.value || "BALANCED";
  state.commitments.buffer_mode = document.getElementById("stSetBufferMode")?.value || "COGNITIVE_LOAD";
  const habitVal = document.getElementById("stSetEstimateHabit")?.value || "";
  if (habitVal) state.commitments.estimate_habit = habitVal;
  else delete state.commitments.estimate_habit;
  state.commitments.alpha_light = parseFloat(document.getElementById("stSetAlphaLight")?.value || "1.2");
  state.commitments.alpha_heavy = parseFloat(document.getElementById("stSetAlphaHeavy")?.value || "1.35");

  const horizonDays = parseInt(document.getElementById("stSetHorizonDays")?.value || "7", 10) >= 14 ? 14 : 7;
  state.commitments.horizon_days = horizonDays;
  if (horizonDays < 14 && state.viewWeekOffset > 0) state.viewWeekOffset = 0;

  const nowMode = document.getElementById("stSetNowMode")?.value || "KEEP";
  if (nowMode === "REALTIME") {
    state.commitments.planning_week_start = getCurrentMondayIso();
    state.commitments.now = getCurrentLocalIso();
    state.useRealTimeNow = true;
  } else if (nowMode === "WEEK_START") {
    delete state.commitments.now;
    state.useRealTimeNow = false;
  }

  const solverEl = document.getElementById("solverSelect");
  const stSolver = document.getElementById("stSetSolver")?.value;
  if (solverEl && stSolver) solverEl.value = stSolver;

  syncAllLeftPanels();
  savePersistedStudentState();
  closeStudentSettingsModal();
  await solveSchedule();
}

function openStudentDisruptionModal() {
  document.getElementById("stDisruptionModal")?.classList.remove("hidden");
}

function closeStudentDisruptionModal() {
  document.getElementById("stDisruptionModal")?.classList.add("hidden");
}

async function applyStudentDisruption() {
  if (!state.currentSchedule) return;
  state.undoSnapshot = {
    commitments: JSON.parse(JSON.stringify(state.commitments)),
    tasks: JSON.parse(JSON.stringify(state.tasks)),
    schedule: JSON.parse(JSON.stringify(state.currentSchedule)),
    pinnedBlocks: new Map(state.pinnedBlocks),
  };

  const title = document.getElementById("stDisTitle")?.value.trim() || "Sự cố đột xuất";
  const day = document.getElementById("stDisDay")?.value || "Monday";
  const start = document.getElementById("stDisStart")?.value || "08:00";
  const end = document.getElementById("stDisEnd")?.value || "10:00";
  const algorithm = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";

  const eventId = `DIS_${Date.now().toString().slice(-4)}`;

  try {
    const res = await fetch("/api/repair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algorithm,
        schedule: state.currentSchedule,
        mode: "LOCAL_INSERTION",
        disruption: {
          event_id: eventId,
          title,
          day_of_week: day,
          start_time: start,
          end_time: end,
        },
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const rep = await res.json();
    state.commitments.fixed_events = state.commitments.fixed_events || [];
    state.commitments.fixed_events.push({
      event_id: eventId,
      title,
      day_of_week: day,
      start_time: start,
      end_time: end,
      category: "DISRUPTION",
      is_movable: false,
    });
    state.currentSchedule = rep.schedule;
    state.repairedMovedIds = new Set((rep.changes || []).filter((c) => c.status === "MOVED").map((c) => c.block_id));
    closeStudentDisruptionModal();
    syncAllLeftPanels();
    renderKpiCards(state.currentSchedule);
    renderMainGrid();
    renderStudentViews();
    evaluateCurrentScheduleV21();
  } catch (err) {
    alert(`Lỗi tái lập lịch M5: ${err.message}`);
  }
}

async function previewStudentOverloadOption(optionId, optionCode, targetTaskId) {
  const algorithm = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";
  try {
    const res = await fetch("/api/overload/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algorithm,
        option_id: optionId,
        option_code: optionCode,
        target_task_id: targetTaskId,
        schedule: state.currentSchedule,
      }),
    });
    if (!res.ok) throw new Error(await res.text());
    const prev = await res.json();

    state.undoSnapshot = {
      commitments: JSON.parse(JSON.stringify(state.commitments)),
      tasks: JSON.parse(JSON.stringify(state.tasks)),
      schedule: JSON.parse(JSON.stringify(state.currentSchedule)),
      pinnedBlocks: new Map(state.pinnedBlocks),
    };
    state.previewState = {
      option_id: prev.option_id,
      option_code: prev.option_code,
      target_task_id: prev.target_task_id,
      resolved_tasks: prev.resolved_tasks,
      after_summary: prev.after_summary,
    };
    if (prev.schedule) {
      state.currentSchedule = prev.schedule;
    }
    renderKpiCards(state.currentSchedule);
    renderMainGrid();
    renderStudentViews();
  } catch (err) {
    alert(`Không thể xem trước phương án: ${err.message}`);
  }
}

async function applyStudentOverloadPreview() {
  if (!state.previewState) return;
  if (Array.isArray(state.previewState.resolved_tasks)) {
    state.tasks = state.previewState.resolved_tasks;
  }
  state.previewState = null;
  syncAllLeftPanels();
  await solveSchedule();
}

function undoStudentChange() {
  if (!state.undoSnapshot) return;
  state.commitments = state.undoSnapshot.commitments;
  state.tasks = state.undoSnapshot.tasks;
  state.currentSchedule = state.undoSnapshot.schedule;
  state.pinnedBlocks = state.undoSnapshot.pinnedBlocks || new Map();
  state.undoSnapshot = null;
  state.previewState = null;
  state.repairedMovedIds.clear();
  syncAllLeftPanels();
  renderKpiCards(state.currentSchedule);
  renderMainGrid();
  renderStudentViews();
  evaluateCurrentScheduleV21();
}

let draggedBlockId = null;
function handleGridDragStart(event, blockId) {
  draggedBlockId = blockId;
  event.dataTransfer?.setData("text/plain", blockId);
}

async function handleGridDrop(event, dayIdx, newTime) {
  event.preventDefault();
  const blockId = draggedBlockId || event.dataTransfer?.getData("text/plain");
  draggedBlockId = null;
  if (!blockId || !state.currentSchedule) return;

  const newDay = DAYS_EN[dayIdx];
  const algorithm = document.getElementById("solverSelect")?.value || "SCORED_GREEDY";
  try {
    const res = await fetch("/api/validate-move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
        algorithm,
        blocks: state.currentSchedule.blocks || [],
        current_blocks: state.currentSchedule.blocks || [],
        block_id: blockId,
        new_day: newDay,
        new_time: newTime,
      }),
    });
    const val = await res.json();
    if (!val.ok) {
      alert(`❌ Không thể kéo block sang ${newDay} ${newTime}:\n` + (val.violations || []).map((v) => `• ${v.message}`).join("\n"));
      return;
    }
    if (val.proposed_block) {
      state.pinnedBlocks.set(blockId, val.proposed_block);
      savePersistedStudentState();
      await solveSchedule();
    }
  } catch (err) {
    console.error("Drag/drop validate error:", err);
  }
}

// ============================================================================
// P3.3: Focus Timer (Pomodoro -> M7), EWMA Alpha Calibration & Notifications
// ============================================================================

const focusTimerState = {
  targetSec: 25 * 60,
  remainingSec: 25 * 60,
  elapsedSec: 0,
  intervalId: null,
  running: false,
  notifyEnabled: false,
  notifyIntervalId: null,
  notifiedBlockKeys: new Set(),
  lastCalibration: null,
};

function _formatMmSs(totalSec) {
  const safe = Math.max(0, Math.floor(totalSec));
  const mm = String(Math.floor(safe / 60)).padStart(2, "0");
  const ss = String(safe % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function _renderFocusTimerUI() {
  const disp = document.getElementById("stFocusTimerDisplay");
  const st = document.getElementById("stFocusTimerStatus");
  if (disp) disp.textContent = _formatMmSs(focusTimerState.remainingSec);
  if (st) {
    const elapsedMin = Math.max(0, Math.round(focusTimerState.elapsedSec / 60));
    if (focusTimerState.running) {
      st.textContent = `Đang tập trung... (đã chạy ~${elapsedMin} phút)`;
    } else if (focusTimerState.elapsedSec > 0) {
      st.textContent = `Đã tạm dừng · Thời gian thực đo: ${elapsedMin} phút`;
    } else {
      st.textContent = "Sẵn sàng bắt đầu phiên tập trung";
    }
  }
}

function changeFocusTimerPreset() {
  const sel = document.getElementById("stFocusPresetSelect");
  const mins = Math.max(5, parseInt(sel ? sel.value : "25", 10) || 25);
  pauseFocusTimer();
  focusTimerState.targetSec = mins * 60;
  focusTimerState.remainingSec = mins * 60;
  focusTimerState.elapsedSec = 0;
  _renderFocusTimerUI();
}

function startFocusTimer() {
  if (focusTimerState.running) return;
  focusTimerState.running = true;
  _renderFocusTimerUI();
  focusTimerState.intervalId = setInterval(() => {
    focusTimerState.elapsedSec += 1;
    if (focusTimerState.remainingSec > 0) {
      focusTimerState.remainingSec -= 1;
    }
    _renderFocusTimerUI();
    if (focusTimerState.remainingSec <= 0) {
      pauseFocusTimer();
      _sendDesktopNotification("SmartSchedule Focus Timer", "Hết phiên tập trung! Bấm 'Lưu M7' để ghi nhận thời lượng thực tế.");
    }
  }, 1000);
}

function pauseFocusTimer() {
  focusTimerState.running = false;
  if (focusTimerState.intervalId) {
    clearInterval(focusTimerState.intervalId);
    focusTimerState.intervalId = null;
  }
  _renderFocusTimerUI();
}

function resetFocusTimer() {
  pauseFocusTimer();
  focusTimerState.remainingSec = focusTimerState.targetSec;
  focusTimerState.elapsedSec = 0;
  _renderFocusTimerUI();
}

async function completeFocusTimerToM7() {
  pauseFocusTimer();
  const measuredMin = Math.max(1, Math.round((focusTimerState.elapsedSec || focusTimerState.targetSec) / 60));
  const heroInp = document.getElementById("stHeroActualMin");
  if (heroInp) heroInp.value = String(measuredMin);

  const activeBlock = (state.currentSchedule && Array.isArray(state.currentSchedule.blocks))
    ? state.currentSchedule.blocks.find((b) => !state.doneBlocks.has(b.block_id))
    : null;
  const taskId = activeBlock ? (activeBlock.task_id || "FOCUS-SESSION") : "FOCUS-SESSION";
  const category = activeBlock ? (activeBlock.category || "STUDY") : "STUDY";
  const estimatedMin = activeBlock ? (activeBlock.duration_min || Math.round(focusTimerState.targetSec / 60)) : Math.round(focusTimerState.targetSec / 60);

  try {
    const res = await fetch("/api/tasks/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task_id: taskId,
        category,
        estimated_duration_min: estimatedMin,
        actual_duration_min: measuredMin,
        completed: true,
      }),
    });
    if (res.ok) {
      const st = document.getElementById("stFocusTimerStatus");
      if (st) st.textContent = `✔️ Đã lưu M7 (${measuredMin}p / ước lượng ${estimatedMin}p) cho ${taskId}`;
      focusTimerState.elapsedSec = 0;
      focusTimerState.remainingSec = focusTimerState.targetSec;
      await refreshCalibrationAdvisory();
    }
  } catch (err) {
    console.error("Focus Timer M7 check-in error:", err);
  }
}

async function refreshCalibrationAdvisory() {
  const metricsEl = document.getElementById("stCalibrationMetrics");
  const noteEl = document.getElementById("stCalibrationNote");
  const applyBtn = document.getElementById("btnApplyCalibrationAlpha");
  try {
    const res = await fetch("/api/tasks/calibration?min_samples=5&lambda_ewma=0.25");
    if (!res.ok) return;
    const data = await res.json();
    const cal = data.calibration;
    if (!cal) return;
    focusTimerState.lastCalibration = cal;
    if (metricsEl) {
      const ratioTxt = cal.mean_ratio != null ? ` · TB Act/Est=${cal.mean_ratio}` : "";
      metricsEl.textContent = `Mẫu M7: ${cal.sample_count}/${cal.min_samples_required}${ratioTxt} · Đề xuất: α ${Number(cal.recommended_alpha_light).toFixed(2)} / ${Number(cal.recommended_alpha_heavy).toFixed(2)}`;
    }
    if (noteEl && cal.advisory_note) {
      noteEl.textContent = cal.advisory_note;
    }
    if (applyBtn) {
      applyBtn.disabled = !cal.ready_to_apply;
    }
  } catch (err) {
    console.error("Calibration fetch error:", err);
  }
}

async function applyRecommendedCalibrationAlpha() {
  const cal = focusTimerState.lastCalibration;
  if (!cal || !cal.ready_to_apply) return;
  if (state.commitments) {
    state.commitments.buffer_mode = "COGNITIVE_LOAD";
    state.commitments.alpha_light = Number(cal.recommended_alpha_light);
    state.commitments.alpha_heavy = Number(cal.recommended_alpha_heavy);
    if (typeof savePersistedStudentState === "function") savePersistedStudentState();
    if (typeof solveSchedule === "function") await solveSchedule();
  }
}

function _sendDesktopNotification(title, body) {
  if (typeof Notification === "undefined") return;
  if (Notification.permission === "granted") {
    try {
      new Notification(title, { body });
    } catch (_err) {
      // Ignore browser notification restrictions in headless/iframe contexts
    }
  }
}

function _checkUpcomingBlockReminders() {
  if (!focusTimerState.notifyEnabled || !state.currentSchedule || !Array.isArray(state.currentSchedule.blocks)) return;
  const now = new Date();
  const jsDay = now.getDay();
  const mondayIdx = (jsDay + 6) % 7;
  const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const todayName = dayNames[mondayIdx];
  const nowMin = now.getHours() * 60 + now.getMinutes();

  for (const blk of state.currentSchedule.blocks) {
    if (blk.day !== todayName || state.doneBlocks.has(blk.block_id)) continue;
    const parts = String(blk.start_time || "").split(":");
    if (parts.length !== 2) continue;
    const startMin = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
    const diff = startMin - nowMin;
    const key = `${blk.block_id}_${todayName}_${blk.start_time}`;
    if (diff >= 1 && diff <= 10 && !focusTimerState.notifiedBlockKeys.has(key)) {
      focusTimerState.notifiedBlockKeys.add(key);
      _sendDesktopNotification(
        `Sắp tới phiên học (${diff} phút nữa)`,
        `${blk.title || blk.task_id} (${blk.start_time} – ${blk.end_time})`
      );
    }
  }
}

async function toggleScheduleNotifications() {
  const btn = document.getElementById("btnStNotifyToggle");
  if (focusTimerState.notifyEnabled) {
    focusTimerState.notifyEnabled = false;
    if (focusTimerState.notifyIntervalId) {
      clearInterval(focusTimerState.notifyIntervalId);
      focusTimerState.notifyIntervalId = null;
    }
    if (btn) btn.textContent = "🔔 Nhắc giờ: Tắt";
    return;
  }
  if (typeof Notification !== "undefined" && Notification.permission === "default") {
    try {
      await Notification.requestPermission();
    } catch (_err) {
      // Ignore permission prompt failure
    }
  }
  focusTimerState.notifyEnabled = true;
  if (btn) btn.textContent = "🔔 Nhắc giờ: Bật";
  _checkUpcomingBlockReminders();
  focusTimerState.notifyIntervalId = setInterval(_checkUpcomingBlockReminders, 60000);
}
