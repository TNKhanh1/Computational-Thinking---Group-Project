/**
 * SmartSchedule UI v3 — Main ES Module Coordinator.
 * Wires Top Bar, Solver Switcher (with 0ms benchmark cache; solvers come from /api/solvers,
 * currently 6 incl. HYBRID_ALNS), 4 Workspace Views, Unified 3-Tab Input Modal,
 * Drag-and-Drop PINNED validation, M7 Check-in, Local Repair, Overload Rescue,
 * Testing_System v2.1 4-pillar health panel, Focus Timer (Pomodoro → M7) with EWMA α
 * calibration & block reminders, and SQLite State Persistence.
 */

import { api } from "./js/api.js";
import { renderInputModal } from "./js/input-drawer.js";
import {
  renderBlockInspectorModal,
  renderDisruptionModal,
  renderOverloadModal,
  renderTestSuitePopover,
  showToast,
} from "./js/modals.js";
import { renderBenchmarkView } from "./js/render-benchmark.js";
import { renderCalendarView } from "./js/render-calendar.js";
import { renderListView } from "./js/render-list.js";
import { renderShowcaseView } from "./js/render-showcase.js";
import { renderWeightsView } from "./js/render-weights.js";
import { buildApiPayload, invalidateSolverCaches, state } from "./js/state.js";
import {
  WEEKDAYS_VI_FULL,
  WEEKDAYS_VI_SHORT,
  addDays,
  esc,
  fmtDDMM,
  fmtISODate,
  getVerdictBadge,
  normalizeEvaluation,
  parseWeekStartDate,
  resolveNowSlot,
  slotToDayIndex,
} from "./js/utils.js";

// ============================================================================
// BOOTSTRAP & PERSISTENCE
// ============================================================================

async function bootstrap() {
  applyTheme(state.theme, false);
  wireStaticListeners();

  try {
    const [solversRes, catalogRes, calRes] = await Promise.all([
      api.getSolvers(),
      api.getCatalog(),
      api.getCalibration(state.workspaceId).catch(() => null),
    ]);
    if (solversRes?.solvers?.length) state.solvers = solversRes.solvers;
    state.catalog = catalogRes;
    state.calibration = calRes;
    renderCalibrationAdvisory();
  } catch (err) {
    showToast(`Không tải được danh mục khởi tạo: ${err.message}`, "danger");
  }

  // Try restoring SQLite workspace state; fall back to Minh's Week preset
  try {
    const saved = await api.loadState(state.workspaceId);
    if (saved?.exists && saved.state?.commitments && Array.isArray(saved.state?.tasks)) {
      applyLoadedState(saved.state, saved.state.suiteLabel || "Workspace đã lưu (SQLite)");
    } else {
      await loadSuite("preset", "minh", 42, false);
      return;
    }
  } catch {
    await loadSuite("preset", "minh", 42, false);
    return;
  }

  await solveActiveSolver();
}

function applyLoadedState(savedObj, label) {
  state.commitments = savedObj.commitments;
  state.tasks = savedObj.tasks || [];
  state.pinnedBlocks = savedObj.pinnedBlocks || savedObj.pinned_blocks || [];
  state.completedBlocks = savedObj.completedBlocks || {};
  state.activeSolver = savedObj.activeSolver || savedObj.algorithm || "SCORED_GREEDY";
  state.suiteLabel = label || "Tùy chỉnh";
  state.disruptionPreset = savedObj.disruption || null;
  state.overrunPreset = savedObj.overrun_config || null;
  invalidateSolverCaches();
}

async function persistWorkspace(silent = true) {
  try {
    await api.saveState(
      {
        suiteLabel: state.suiteLabel,
        commitments: state.commitments,
        tasks: state.tasks,
        pinnedBlocks: state.pinnedBlocks,
        completedBlocks: state.completedBlocks,
        activeSolver: state.activeSolver,
      },
      state.workspaceId
    );
    if (!silent) showToast("Đã lưu trạng thái workspace vào SQLite.", "ok");
  } catch (err) {
    if (!silent) showToast(`Lỗi lưu trạng thái: ${err.message}`, "danger");
  }
}

// ============================================================================
// SOLVING, EVALUATING, BENCHMARKING & WEIGHTS
// ============================================================================

/**
 * Testing_System v2.1 evaluation (G1/G2 + P1–P4 + ICEE) for one schedule.
 * Backend v3 already evaluates inside /api/plan → `health_v21`, so reuse it and skip a second
 * full evaluation round-trip; only fall back to POST /api/evaluate when it is missing.
 */
async function evaluateCurrentScheduleV21(sched = state.currentSchedule, algorithm = state.activeSolver) {
  if (!sched) return null;
  const inline = normalizeEvaluation(sched.health_v21);
  if (inline) return inline;
  try {
    return normalizeEvaluation(
      await api.evaluate({
        commitments: state.commitments,
        tasks: state.tasks,
        pinned_blocks: state.pinnedBlocks,
        algorithm,
        schedule: sched,
      })
    );
  } catch {
    return null;
  }
}

async function solveActiveSolver(forceFresh = false) {
  const key = state.activeSolver;
  if (!forceFresh && state.schedulesBySolver[key]) {
    state.currentSchedule = state.schedulesBySolver[key];
    state.currentEvaluation = normalizeEvaluation(state.schedulesBySolver[key].evaluation);
    renderAll();
    return;
  }

  setBusyState(true);
  try {
    const payload = buildApiPayload(key);
    const sched = await api.plan(payload);
    const evalReport = await evaluateCurrentScheduleV21(sched, key);
    sched.evaluation = evalReport;
    state.schedulesBySolver[key] = sched;
    state.currentSchedule = sched;
    state.currentEvaluation = evalReport;
  } catch (err) {
    showToast(`Lỗi chạy thuật toán ${key}: ${err.message}`, "danger");
  } finally {
    setBusyState(false);
    renderAll();
  }
}

async function runBenchmarkAll(switchToView = true) {
  setBusyState(true);
  showToast("Đang chạy & chấm điểm tất cả thuật toán trên cùng input...", "ok");
  try {
    const res = await api.benchmarkAll({
      commitments: state.commitments,
      tasks: state.tasks,
      pinned_blocks: state.pinnedBlocks,
    });
    state.benchmarkData = res;
    state.schedulesBySolver = res.schedules_by_solver || {};
    if (state.schedulesBySolver[state.activeSolver]) {
      state.currentSchedule = state.schedulesBySolver[state.activeSolver];
      state.currentEvaluation = normalizeEvaluation(state.currentSchedule.evaluation);
    }
    if (switchToView) {
      setActiveView("benchmark");
    } else {
      renderAll();
    }
    const top = res.ranking?.[0];
    if (top) {
      showToast(`Hoàn tất chấm ${res.ranking.length} thuật toán! Hạng #1: ${top.solver_key} (${top.verdict}).`, "ok");
    }
  } catch (err) {
    showToast(`Lỗi chấm điểm thuật toán: ${err.message}`, "danger");
  } finally {
    setBusyState(false);
    renderAll();
  }
}

async function fetchSolverWeights(switchToView = false) {
  setBusyState(true);
  try {
    state.weightsData = await api.solverWeights({
      commitments: state.commitments,
      tasks: state.tasks,
      pinned_blocks: state.pinnedBlocks,
    });
    if (switchToView) {
      setActiveView("weights");
    } else {
      renderAll();
    }
  } catch (err) {
    showToast(`Lỗi đọc trọng số thuật toán: ${err.message}`, "danger");
  } finally {
    setBusyState(false);
    renderAll();
  }
}

async function loadSuite(source, id, seed = 42, notify = true, horizonDays = null) {
  closeAllPopovers();
  setBusyState(true);
  try {
    const res = await api.loadSuite(source, id, seed, horizonDays);
    state.commitments = res.commitments || state.commitments;
    state.tasks = res.tasks || [];
    state.pinnedBlocks = res.pinned_blocks || [];
    state.completedBlocks = {};
    state.viewWeekOffset = 0;
    state.suiteLabel = res.name || id;
    state.suiteMeta = res.metadata || null;
    state.disruptionPreset = res.disruption || null;
    state.overrunPreset = res.overrun_config || null;
    state.scrubberStartDay = Math.min(
      Math.max(0, (Number(state.commitments.horizon_days) || 7) - state.visibleDaysCount),
      slotToDayIndex(resolveNowSlot(state.commitments))
    );
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
    if (notify) showToast(`Đã nạp bộ test: ${state.suiteLabel}`, "ok");
  } catch (err) {
    showToast(`Không nạp được bộ test: ${err.message}`, "danger");
  } finally {
    setBusyState(false);
  }
}

// ============================================================================
// INTERACTIVE ACTIONS (Drag/Drop, Pin, Check-in, Overrun, Repair, Overload, Export)
// ============================================================================

/** Move the planning week (and simulated NOW) by `deltaDays`; task deadlines keep their absolute dates. */
async function shiftWeek(deltaDays) {
  const ws = parseWeekStartDate(state.commitments.planning_week_start);
  const nextWs = addDays(ws, deltaDays);
  state.commitments.planning_week_start = `${fmtISODate(nextWs)}T00:00:00+07:00`;
  state.commitments.now = `${fmtISODate(nextWs)}T08:00:00+07:00`;
  state.scrubberStartDay = 0;
  state.viewWeekOffset = 0;
  invalidateSolverCaches();
  await solveActiveSolver(true);
  await persistWorkspace(true);
}

/** Browse another week without re-planning: only the viewed week changes. */
function setViewWeek(offsetWeeks) {
  state.viewWeekOffset = offsetWeeks;
  if (offsetWeeks === 0) state.scrubberStartDay = 0;
  setActiveView("calendar");
}

/** "Xóa tất cả lịch": empties tasks, pins, check-ins (+ optionally fixed events & habits), then saves. */
async function clearAllSchedule({ includeFixed = false } = {}) {
  const counts = {
    tasks: state.tasks.length,
    fixed: (state.commitments.fixed_events || []).length,
    habits: (state.commitments.personal_habits || []).length,
  };
  state.tasks = [];
  state.pinnedBlocks = [];
  state.completedBlocks = {};
  state.overloadPreview = null;
  state.disruptionPreset = null;
  state.overrunPreset = null;
  if (includeFixed) {
    state.commitments.fixed_events = [];
    state.commitments.personal_habits = [];
  }
  state.suiteLabel = "Lịch trống";
  state.suiteMeta = null;
  state.viewWeekOffset = 0;
  state.scrubberStartDay = 0;
  invalidateSolverCaches();
  closeModal("clearAllModal");
  await solveActiveSolver(true);
  await persistWorkspace(true);
  showToast(
    includeFixed
      ? `Đã xóa ${counts.tasks} việc, ${counts.fixed} lịch cố định và ${counts.habits} thói quen.`
      : `Đã xóa ${counts.tasks} việc (giữ lại lịch cố định & thói quen).`,
    "ok"
  );
}

async function handleDropMoveBlock(blockId, newStartSlot, dayLabel, timeLabel) {
  const blocks = state.currentSchedule?.blocks || [];
  const blk = blocks.find((b) => b.block_id === blockId);
  if (!blk) return;

  try {
    const val = await api.validateMove({
      commitments: state.commitments,
      tasks: state.tasks,
      current_blocks: blocks,
      block_id: blockId,
      new_start_slot: newStartSlot,
      new_day: dayLabel,
      new_time: timeLabel,
    });
    if (!val.ok) {
      const msg = (val.violations || []).join(" · ") || "Vi phạm ràng buộc cứng H1–H5.";
      showToast(`Không thể dời block: ${msg}`, "danger");
      return;
    }

    const durSlots = Math.max(1, blk.end_slot - blk.start_slot);
    const updatedBlock = {
      ...blk,
      start_slot: newStartSlot,
      end_slot: newStartSlot + durSlots,
      day: dayLabel,
      start_time: timeLabel,
      state: "PINNED",
    };

    state.pinnedBlocks = [
      ...state.pinnedBlocks.filter((p) => p.block_id !== blockId),
      updatedBlock,
    ];
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
    showToast(`📌 Đã dời & ghim "${blk.title}" sang ${dayLabel} ${timeLabel}.`, "ok");
  } catch (err) {
    showToast(`Lỗi kiểm tra di chuyển: ${err.message}`, "danger");
  }
}

async function handleTogglePin(blockId) {
  const exists = state.pinnedBlocks.some((p) => p.block_id === blockId);
  if (exists) {
    state.pinnedBlocks = state.pinnedBlocks.filter((p) => p.block_id !== blockId);
    showToast("Đã bỏ ghim cố định block.", "ok");
  } else {
    const blk = (state.currentSchedule?.blocks || []).find((b) => b.block_id === blockId);
    if (!blk) return;
    state.pinnedBlocks.push({ ...blk, state: "PINNED" });
    showToast(`📌 Đã ghim cố định "${blk.title}".`, "ok");
  }
  closeModal("blockModal");
  invalidateSolverCaches();
  await solveActiveSolver(true);
  await persistWorkspace(true);
}

async function handleCheckinBlock(block, actualMin) {
  try {
    const res = await api.completeTask({
      task_id: block.task_id,
      category: block.category,
      workspace_id: state.workspaceId,
      estimated_min: block.duration_min,
      actual_duration_min: actualMin,
      completed: true,
    });
    state.completedBlocks[block.block_id] = {
      actual_min: actualMin,
      completed_at: new Date().toISOString(),
    };
    await refreshCalibrationAdvisory();
    closeModal("blockModal");
    await persistWorkspace(true);
    renderAll();
    showToast(
      `✔️ Đã ghi nhận M7 (${actualMin}p vs ${block.duration_min}p, tỷ lệ ${res.overrun_ratio}x). Gợi ý α=${res.recommended_alpha}.`,
      "ok"
    );
  } catch (err) {
    showToast(`Lỗi Check-in M7: ${err.message}`, "danger");
  }
}

async function handleOverrunBlock(block, extraMin) {
  try {
    const res = await api.overrun({
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm: state.activeSolver,
      task_id: block.task_id,
      extra_min: extraMin,
    });
    // Update task duration in workspace to reflect overrun
    const task = state.tasks.find((t) => t.task_id === block.task_id);
    if (task) task.duration_min = res.new_duration_min;
    closeModal("blockModal");
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
    showToast(
      `Đã xử lý tràn +${extraMin}p cho "${block.title}" (${res.shifted_blocks_count} block bị dịch chuyển).`,
      "warn"
    );
  } catch (err) {
    showToast(`Lỗi xử lý tràn giờ: ${err.message}`, "danger");
  }
}

async function handleRunRepair({ new_event, mode }) {
  try {
    const res = await api.repair({
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm: state.activeSolver,
      schedule: state.currentSchedule,
      new_event,
      mode,
    });
    // Persist new urgent fixed event into commitments so subsequent views stay consistent
    state.commitments.fixed_events = [
      ...(state.commitments.fixed_events || []),
      { ...new_event, category: "MEETING" },
    ];
    closeModal("disruptionModal");
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
    const stab = res.stability_pct ?? res.summary?.stability_pct;
    showToast(
      `Đã chèn sự cố "${new_event.title}" (${mode})${stab != null ? ` · Độ ổn định: ${stab}%` : ""}.`,
      "ok"
    );
  } catch (err) {
    showToast(`Lỗi chạy Local Repair: ${err.message}`, "danger");
  }
}

async function handlePreviewOverload(optionId, optionCode, targetTaskId) {
  try {
    const res = await api.overloadPreview({
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm: state.activeSolver,
      schedule: state.currentSchedule,
      option_id: optionId,
      option_code: optionCode,
      target_task_id: targetTaskId,
    });
    state.overloadPreview = res;
    closeModal("overloadModal");
    setActiveView("calendar");
    showToast(`👁️ Đang xem thử phương án ${optionId}. Kiểm tra các khối nét đứt trên lịch.`, "ok");
  } catch (err) {
    showToast(`Lỗi xem thử giải cứu quá tải: ${err.message}`, "danger");
  }
}

async function handleApplyOverloadPreview() {
  if (!state.overloadPreview) return;
  if (Array.isArray(state.overloadPreview.resolved_tasks)) {
    state.tasks = state.overloadPreview.resolved_tasks;
  }
  state.overloadPreview = null;
  invalidateSolverCaches();
  await solveActiveSolver(true);
  await persistWorkspace(true);
  showToast("✔️ Đã áp dụng phương án giải cứu quá tải.", "ok");
}

async function handleExport(fmt) {
  closeAllPopovers();
  try {
    const blob = await api.exportFile(fmt, {
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm: state.activeSolver,
      schedule: state.currentSchedule,
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `smartschedule_${state.activeSolver.toLowerCase()}.${fmt}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showToast(`Đã xuất tệp .${fmt} thành công.`, "ok");
  } catch (err) {
    showToast(`Lỗi xuất .${fmt}: ${err.message}`, "danger");
  }
}

// ============================================================================
// RENDERING ORCHESTRATION
// ============================================================================

function setActiveView(viewName) {
  state.activeView = viewName;
  document.querySelectorAll("[data-view-tab]").forEach((btn) => {
    const active = btn.getAttribute("data-view-tab") === viewName;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
  });
  const map = {
    calendar: "viewCalendar",
    list: "viewList",
    weights: "viewWeights",
    benchmark: "viewBenchmark",
    showcase: "viewShowcase",
  };
  Object.entries(map).forEach(([k, id]) => {
    document.getElementById(id)?.classList.toggle("active", k === viewName);
  });

  if (viewName === "weights" && !state.weightsData) {
    fetchSolverWeights(false);
    return;
  }
  renderAll();
}

function renderAll() {
  renderTopBar();
  renderSolverRibbon();
  renderCalendarRangeLabel();
  renderTelemetryStrip();
  renderHealthV21Panels();

  const sharedCallbacks = {
    onInspectBlock: (blockId, focusSection = null) => openBlockModal(blockId, focusSection),
    onTogglePin: (blockId) => handleTogglePin(blockId),
    onDropMoveBlock: (bid, slot, day, time) => handleDropMoveBlock(bid, slot, day, time),
    onOpenOverloadRescue: () => openOverloadModal(),
    onApplyOverloadPreview: () => handleApplyOverloadPreview(),
    onCancelOverloadPreview: () => {
      state.overloadPreview = null;
      renderAll();
    },
    onRefreshWeights: () => fetchSolverWeights(false),
    onRunBenchmarkAll: () => runBenchmarkAll(true),
    onSelectSolver: async (solverKey, jumpToCalendar = false) => {
      state.activeSolver = solverKey;
      if (jumpToCalendar) setActiveView("calendar");
      await solveActiveSolver(false);
    },
    onSyncRangeLabel: () => renderCalendarRangeLabel(),
    onBackToCalendar: () => setActiveView("calendar"),
    onShiftWeek: (deltaDays) => shiftWeek(deltaDays),
    onSetViewWeek: (offsetWeeks) => setViewWeek(offsetWeeks),
    onLoadSuite: async (src, id, seed, horizon = null) => {
      await loadSuite(src, id, seed, true, horizon);
      setActiveView("calendar");
    },
  };

  if (state.activeView === "calendar") {
    renderCalendarView(document.getElementById("viewCalendar"), sharedCallbacks);
  } else if (state.activeView === "list") {
    renderListView(document.getElementById("viewList"), sharedCallbacks);
  } else if (state.activeView === "weights") {
    renderWeightsView(document.getElementById("viewWeights"), sharedCallbacks);
  } else if (state.activeView === "benchmark") {
    renderBenchmarkView(document.getElementById("viewBenchmark"), sharedCallbacks);
  } else if (state.activeView === "showcase") {
    renderShowcaseView(document.getElementById("viewShowcase"), sharedCallbacks);
  }
}

function applyTheme(themeKey, notify = false) {
  const valid = ["botanical", "light", "dark"].includes(themeKey) ? themeKey : "botanical";
  state.theme = valid;
  document.documentElement.setAttribute("data-theme", valid);
  try {
    localStorage.setItem("smartschedule_theme", valid);
  } catch {}
  document.querySelectorAll("[data-set-theme]").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-set-theme") === valid);
  });
  if (notify) {
    const names = { botanical: "Rừng cây (Botanical)", light: "Sáng tối giản", dark: "Rừng đêm (Dark)" };
    showToast(`Đã chuyển sang giao diện ${names[valid]}.`, "ok");
  }
}

function setDevPanelOpen(open) {
  state.devPanelOpen = Boolean(open);
  const panel = document.getElementById("devSidePanel");
  const btn = document.getElementById("btnToggleDevPanel");
  panel?.classList.toggle("open", state.devPanelOpen);
  btn?.classList.toggle("active", state.devPanelOpen);
  btn?.setAttribute("aria-expanded", String(state.devPanelOpen));
}

function renderTopBar() {
  document.getElementById("activeSuiteBadge").textContent = state.suiteLabel;
  const devLbl = document.getElementById("devSuiteLabel");
  if (devLbl) devLbl.textContent = state.suiteLabel;
  document.getElementById("txtInputTaskCount").textContent = String(state.tasks.length);

  const horizon = Number(state.commitments.horizon_days || 7);
  const planWs = parseWeekStartDate(state.commitments.planning_week_start);
  const offset = Number(state.viewWeekOffset) || 0;
  const ws = addDays(planWs, offset * 7);
  const we = addDays(ws, offset === 0 ? horizon - 1 : 6);
  document.getElementById("txtWeekRange").textContent = `${fmtDDMM(ws)} – ${fmtDDMM(we)}/${we.getFullYear()}`;
  document.getElementById("btnHorizon7")?.classList.toggle("active", horizon === 7);
  document.getElementById("btnHorizon14")?.classList.toggle("active", horizon === 14);

  const chkSleep = document.getElementById("chkSettingHideSleep");
  const chkEnergy = document.getElementById("chkSettingEnergy");
  const chkTech = document.getElementById("chkSettingTechMeta");
  if (chkSleep) chkSleep.checked = Boolean(state.hideSleepHours);
  if (chkEnergy) chkEnergy.checked = Boolean(state.showEnergyBackdrop);
  if (chkTech) chkTech.checked = Boolean(state.showTechMetaOnBlocks);
}

function renderCalendarRangeLabel() {
  const lbl = document.getElementById("txtCalendarRangeLabel");
  if (!lbl) return;
  const count = Number(state.visibleDaysCount) || 7;
  const ws = parseWeekStartDate(state.commitments.planning_week_start);
  if (Number(state.viewWeekOffset)) {
    lbl.textContent = `Tuần · từ T2 ${fmtDDMM(addDays(ws, Number(state.viewWeekOffset) * 7))}`;
    return;
  }
  const startDt = addDays(ws, state.scrubberStartDay);
  const dayShort = WEEKDAYS_VI_SHORT[state.scrubberStartDay % 7];
  if (count === 1) {
    lbl.textContent = `Theo ngày · ${dayShort} ${fmtDDMM(startDt)}`;
  } else if (count === 7) {
    lbl.textContent = state.scrubberStartDay === 0 ? "Tuần (7 ngày)" : `7 ngày · từ ${dayShort} ${fmtDDMM(startDt)}`;
  } else {
    lbl.textContent = `${count} ngày · từ ${dayShort} ${fmtDDMM(startDt)}`;
  }
}

function renderCalendarRangePopover() {
  const pop = document.getElementById("calendarRangePopover");
  if (!pop) return;
  const count = Number(state.visibleDaysCount) || 7;
  const horizon = Math.max(7, Math.min(14, Number(state.commitments.horizon_days) || 7));
  const ws = parseWeekStartDate(state.commitments.planning_week_start);
  const wsIso = fmtISODate(ws);

  const modes = [
    { days: 1, label: "Theo ngày (1 ngày)", sub: "Tập trung chi tiết từng ngày" },
    { days: 3, label: "3 ngày", sub: "Gọn, dễ đọc trên màn nhỏ" },
    { days: 5, label: "5 ngày", sub: "Cân bằng giữa rộng và chi tiết" },
    { days: 7, label: "Cả tuần (7 ngày)", sub: "Toàn cảnh 7 ngày liên tiếp" },
  ];

  const startDayChips = Array.from({ length: horizon }, (_, d) => {
    const dt = addDays(ws, d);
    const active = d === state.scrubberStartDay;
    return `<button type="button" class="day-chip ${active ? "is-today" : ""}" data-range-start-day="${d}" title="Bắt đầu từ ${WEEKDAYS_VI_FULL[d % 7]} ${fmtDDMM(dt)}">
      ${WEEKDAYS_VI_SHORT[d % 7]} <span class="mono">${fmtDDMM(dt)}</span>
    </button>`;
  }).join("");

  pop.innerHTML = `
    <div class="settings-section">
      <div class="popover-section-title">Chế độ hiển thị lịch</div>
      <div style="display:flex;flex-direction:column;gap:2px;">
        ${modes
          .map(
            (m) => `
          <button type="button" class="range-option ${count === m.days ? "active" : ""}" data-range-days="${m.days}">
            <div>
              <div>${m.label}</div>
              <div style="font-size:11px;color:var(--p-muted);font-weight:400;">${m.sub}</div>
            </div>
            ${count === m.days ? `<span class="badge badge-info">Đang chọn</span>` : ""}
          </button>`
          )
          .join("")}
      </div>
    </div>

    <div class="settings-section">
      <div class="popover-section-title">Chọn ngày bắt đầu hiển thị</div>
      <div class="day-chips">${startDayChips}</div>
      <div class="field" style="margin-top:6px;">
        <label for="inpRangeWeekStart" style="font-size:11.5px;color:var(--p-muted);">Hoặc dời ngày mốc đầu tuần (DD/MM/YYYY)</label>
        <input type="date" id="inpRangeWeekStart" class="input mono" value="${wsIso}" style="min-height:34px;font-size:12.5px;" />
      </div>
    </div>
  `;

  pop.querySelectorAll("[data-range-days]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.visibleDaysCount = Number(btn.getAttribute("data-range-days"));
      closeAllPopovers();
      setActiveView("calendar");
    });
  });

  pop.querySelectorAll("[data-range-start-day]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.scrubberStartDay = Number(btn.getAttribute("data-range-start-day"));
      closeAllPopovers();
      setActiveView("calendar");
    });
  });

  pop.querySelector("#inpRangeWeekStart")?.addEventListener("change", async (e) => {
    const val = e.target.value;
    if (!val) return;
    state.commitments.planning_week_start = `${val}T00:00:00+07:00`;
    state.commitments.now = `${val}T08:00:00+07:00`;
    state.scrubberStartDay = 0;
    closeAllPopovers();
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
    setActiveView("calendar");
  });
}

function renderSolverRibbon() {
  const bar = document.getElementById("solverSwitcherBar");
  const activeMeta = state.solvers.find((s) => s.key === state.activeSolver) || {
    key: state.activeSolver,
    label: state.activeSolver,
    full_name: "",
  };
  const activeCached = state.schedulesBySolver[state.activeSolver];
  const activeVb = getVerdictBadge(activeCached?.evaluation?.verdict);
  const activeMs = activeCached ? `${Number(activeCached.execution_time_ms || 0).toFixed(0)}ms` : "";

  const optionsHtml = state.solvers
    .map((s) => {
      const isSelected = s.key === state.activeSolver;
      const cached = state.schedulesBySolver[s.key];
      const evalRep = cached?.evaluation;
      const vb = getVerdictBadge(evalRep?.verdict);
      const msText = cached ? `${Number(cached.execution_time_ms || 0).toFixed(0)}ms` : "";
      return `
        <button type="button" class="solver-option ${isSelected ? "active" : ""}" data-solver-key="${esc(s.key)}">
          <div style="display:flex;align-items:center;gap:9px;min-width:0;">
            <span class="status-dot ${vb.dot}"></span>
            <div style="min-width:0;">
              <div style="font-weight:600;font-size:13px;color:var(--p-ink);">${esc(s.label)}</div>
              <div style="font-size:11.5px;color:var(--p-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px;">${esc(s.full_name)}</div>
            </div>
          </div>
          <div style="display:inline-flex;align-items:center;gap:6px;flex-shrink:0;">
            ${evalRep ? `<span class="badge ${vb.cls}">${vb.short}</span>` : ""}
            ${msText ? `<span class="mono" style="font-size:11.5px;color:var(--p-muted);">${msText}</span>` : ""}
          </div>
        </button>`;
    })
    .join("");

  bar.innerHTML = `
    <button type="button" class="solver-select-trigger" id="btnToggleSolverMenu" aria-expanded="false" aria-controls="solverDropdownMenu" title="Chuyển đổi thuật toán trên cùng dữ liệu đầu vào">
      <span class="status-dot ${activeVb.dot}"></span>
      <span style="color:var(--p-muted);font-weight:500;">Thuật toán:</span>
      <span>${esc(activeMeta.label)}</span>
      ${activeMs ? `<span class="mono" style="font-size:11.5px;color:var(--p-muted);font-weight:500;">${activeMs}</span>` : ""}
      <svg class="icon" viewBox="0 0 24 24" style="width:14px;height:14px;color:var(--p-muted);"><path d="m6 9 6 6 6-6"/></svg>
    </button>
    <div class="popover-menu solver-dropdown-menu" id="solverDropdownMenu" role="listbox" aria-label="Danh sách thuật toán">
      <div class="popover-section-title" style="padding:4px 8px 2px;">Chọn thuật toán (cùng input)</div>
      ${optionsHtml}
    </div>
  `;

  const trigger = bar.querySelector("#btnToggleSolverMenu");
  const menu = bar.querySelector("#solverDropdownMenu");
  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    const willOpen = !menu.classList.contains("open");
    closeAllPopovers();
    if (willOpen) {
      menu.classList.add("open");
      trigger.setAttribute("aria-expanded", "true");
    }
  });

  bar.querySelectorAll("[data-solver-key]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      closeAllPopovers();
      state.activeSolver = btn.getAttribute("data-solver-key");
      await solveActiveSolver(false);
    });
  });
}

function renderTelemetryStrip() {
  const el = document.getElementById("telemetryMetrics");
  const actionsEl = document.getElementById("telemetryActions");
  const devDot = document.getElementById("devToggleDot");
  const sched = state.currentSchedule;
  const rep = state.currentEvaluation;

  if (!sched) {
    el.innerHTML = `<span class="badge badge-neutral">Chưa có lịch</span>`;
    actionsEl.innerHTML = "";
    return;
  }

  const vb = getVerdictBadge(rep?.verdict);
  if (devDot) devDot.className = `status-dot ${vb.dot}`;

  const p1 = rep?.p1_value_timeliness?.deadline_value_rate_pct ?? sched.metrics?.deadline_satisfaction_pct ?? 100;
  const shk25 = rep?.p4_robustness_stability?.shock_results?.[0]?.survived_priority_pct;
  const g1 = rep?.gates?.g1_total_violations ?? sched.metrics?.hard_violations ?? 0;
  const rho = rep?.gates?.rho_deadline;
  const ms = Number(sched.execution_time_ms || 0).toFixed(1);
  const topCrit = rep?.d1_icee_critiques?.[0];
  const cachedTag = state.benchmarkData ? `<span class="badge badge-info">Cache 0ms</span>` : "";

  el.innerHTML = `
    <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;margin-bottom:8px;">
      <span class="badge ${vb.cls}" title="${esc(vb.label)}">${esc(vb.label)}</span>
      ${cachedTag}
    </div>
    <div class="dev-metric-grid">
      <div class="dev-stat"><span>Vi phạm cứng (G1)</span><strong class="mono">${g1}</strong></div>
      <div class="dev-stat"><span>Kịp hạn (P1.1)</span><strong class="mono">${Number(p1).toFixed(1)}%</strong></div>
      <div class="dev-stat"><span>Chịu sốc +25%</span><strong class="mono">${shk25 !== undefined ? `${Number(shk25).toFixed(1)}%` : "—"}</strong></div>
      <div class="dev-stat"><span>Mật độ ρ · Tốc độ</span><strong class="mono">${rho !== undefined ? `${(rho * 100).toFixed(0)}%` : "—"} · ${ms}ms</strong></div>
    </div>
  `;

  actionsEl.innerHTML = topCrit
    ? `<button type="button" class="settings-action" id="btnViewTopIcee" title="${esc(topCrit.rationale_vi)}">
        <div style="min-width:0;">
          <div style="font-size:11px;font-weight:700;color:var(--st-warn);text-transform:uppercase;">Top cảnh báo ICEE</div>
          <div style="font-size:12px;color:var(--p-ink);margin-top:2px;">${esc(topCrit.summary_vi)}</div>
        </div>
        <svg class="icon" viewBox="0 0 24 24"><path d="m9 18 6-6-6-6"/></svg>
      </button>`
    : `<div style="font-size:12px;color:var(--st-ok);font-weight:600;padding:4px 2px;">Đạt chuẩn sạch — không có cảnh báo ICEE.</div>`;

  actionsEl.querySelector("#btnViewTopIcee")?.addEventListener("click", () => {
    if (!state.benchmarkData) {
      runBenchmarkAll(true);
    } else {
      state.expandedIceeSolvers[state.activeSolver] = true;
      setActiveView("benchmark");
    }
  });
}

// ============================================================================
// TESTING_SYSTEM v2.1 4-PILLAR HEALTH PANEL (complements the quick telemetry strip)
// ============================================================================

function renderHealthV21Panels(rep = state.currentEvaluation) {
  const badge = document.getElementById("stHealthVerdictBadge");
  const rhoEl = document.getElementById("stHealthRhoBadge");
  const sumEl = document.getElementById("stHealthSummaryText");
  const iceeSum = document.getElementById("stHealthIceeSummary");
  const grid = document.getElementById("labHealthVectorGrid");
  const iceeList = document.getElementById("labHealthIceeList");
  if (!badge || !grid) return;

  if (!rep) {
    badge.textContent = "Chưa chấm";
    badge.className = "badge badge-neutral mono";
    if (rhoEl) rhoEl.textContent = "";
    if (sumEl) sumEl.textContent = "Đang chờ chấm điểm lịch hiện tại...";
    if (iceeSum) iceeSum.textContent = "Cảnh báo ICEE";
    grid.innerHTML = "";
    if (iceeList) iceeList.innerHTML = "";
    return;
  }

  const vb = getVerdictBadge(rep.verdict);
  badge.textContent = rep.verdict_label_vi || vb.label;
  badge.className = `badge ${vb.cls} mono`;
  const rho = rep.gates?.rho_deadline;
  if (rhoEl) rhoEl.textContent = rho !== undefined ? `ρ_deadline = ${(rho * 100).toFixed(0)}%` : "";
  if (sumEl) {
    sumEl.textContent =
      rep.verdict_reasons_vi?.[0] ||
      (rep.verdict === "HIGH_PRODUCTIVITY" ? "Đạt chuẩn năng suất & nhịp sinh học." : "Xem gợi ý ICEE để tối ưu lịch.");
  }

  const p2 = rep.p2_cognitive_biology || {};
  const p3 = rep.p3_sustainable_pacing || {};
  const p4 = rep.p4_robustness_stability || {};
  const shock50 = p4.shock_results?.find((s) => Number(s.shock_pct) === 50)?.survived_priority_pct;
  const p3MaxDay = p3.max_daily_total_min ?? (Array.isArray(p3.daily_load_minutes) ? Math.max(0, ...p3.daily_load_minutes) : undefined);
  const fmtPct = (v) => (v != null ? `${Number(v).toFixed(1)}%` : "—");
  grid.innerHTML = `
    <div class="dev-stat"><span>P2 Việc nặng đúng giờ vàng</span><strong class="mono">${fmtPct(p2.achievable_heavy_peak_match_pct ?? p2.heavy_peak_match_pct)}</strong></div>
    <div class="dev-stat"><span>P2 Lệch nhịp ngủ (SJL)</span><strong class="mono">${p2.sjl_minutes != null ? `${Number(p2.sjl_minutes).toFixed(0)}p` : "—"}</strong></div>
    <div class="dev-stat"><span>P3 Tải ngày cao nhất</span><strong class="mono">${p3MaxDay != null ? `${p3MaxDay}p` : "—"}</strong></div>
    <div class="dev-stat"><span>P4 Chịu sốc +50%</span><strong class="mono">${fmtPct(shock50)}</strong></div>
  `;

  const crits = rep.d1_icee_critiques || [];
  if (iceeSum) iceeSum.textContent = `Cảnh báo ICEE (${crits.length})`;
  if (iceeList) {
    iceeList.innerHTML = crits.length
      ? crits
          .slice(0, 5)
          .map(
            (c) =>
              `<li title="${esc(c.rationale_vi || "")}"><span class="mono">${esc(c.pillar || c.severity || "")}</span> · ${esc(
                c.summary_vi || ""
              )}${c.suggested_action_vi ? `<div class="health-icee-action">→ ${esc(c.suggested_action_vi)}</div>` : ""}</li>`
          )
          .join("")
      : `<li>Không có cảnh báo ICEE.</li>`;
  }
}

// ============================================================================
// P3.3 FOCUS TIMER (Pomodoro → M7) · EWMA α CALIBRATION · BLOCK REMINDERS
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
};

function _formatMmSs(totalSec) {
  const safe = Math.max(0, Math.floor(totalSec));
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function _renderFocusTimerUI() {
  const disp = document.getElementById("stFocusTimerDisplay");
  const st = document.getElementById("stFocusTimerStatus");
  if (disp) disp.textContent = _formatMmSs(focusTimerState.remainingSec);
  if (st) {
    const elapsedMin = Math.round(focusTimerState.elapsedSec / 60);
    st.textContent = focusTimerState.running
      ? `Đang tập trung… (~${elapsedMin}p)`
      : focusTimerState.elapsedSec > 0
        ? `Đã tạm dừng · ${elapsedMin}p`
        : "Sẵn sàng";
  }
  const startBtn = document.getElementById("btnFocusStart");
  if (startBtn) startBtn.disabled = focusTimerState.running;
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
  focusTimerState.intervalId = setInterval(() => {
    focusTimerState.elapsedSec += 1;
    if (focusTimerState.remainingSec > 0) focusTimerState.remainingSec -= 1;
    if (focusTimerState.remainingSec <= 0) {
      pauseFocusTimer();
      _sendDesktopNotification("SmartSchedule Focus Timer", "Hết phiên tập trung! Bấm 'Lưu M7' để ghi nhận thời lượng thực tế.");
      showToast("⏱️ Hết phiên tập trung — bấm “Lưu M7” để ghi nhận.", "ok");
      return;
    }
    _renderFocusTimerUI();
  }, 1000);
  _renderFocusTimerUI();
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

/** Logs the measured focus session as an M7 actual-duration check-in for the next unfinished study block. */
async function completeFocusTimerToM7() {
  pauseFocusTimer();
  if (focusTimerState.elapsedSec < 60) {
    showToast("Phiên tập trung chưa đủ 1 phút để ghi nhận M7.", "warn");
    return;
  }
  const measuredMin = Math.round(focusTimerState.elapsedSec / 60);
  const nowSlot = resolveNowSlot(state.commitments);
  const studyBlocks = (state.currentSchedule?.blocks || []).filter(
    (b) => !state.completedBlocks[b.block_id] && b.category !== "FIXED" && b.category !== "SLEEP"
  );
  const activeBlock =
    studyBlocks.find((b) => b.start_slot <= nowSlot && nowSlot < b.end_slot) ||
    studyBlocks.find((b) => b.end_slot > nowSlot) ||
    null;
  const estimatedMin = activeBlock?.duration_min || Math.round(focusTimerState.targetSec / 60);

  try {
    const res = await api.completeTask({
      task_id: activeBlock?.task_id || "FOCUS-SESSION",
      category: activeBlock?.category || "STUDY",
      workspace_id: state.workspaceId,
      estimated_duration_min: estimatedMin,
      actual_duration_min: measuredMin,
      completed: true,
    });
    if (activeBlock) {
      state.completedBlocks[activeBlock.block_id] = { actual_min: measuredMin, completed_at: new Date().toISOString() };
      await persistWorkspace(true);
    }
    focusTimerState.elapsedSec = 0;
    focusTimerState.remainingSec = focusTimerState.targetSec;
    await refreshCalibrationAdvisory();
    renderAll();
    showToast(
      `✔️ Đã lưu M7 ${measuredMin}p / ${estimatedMin}p${activeBlock ? ` cho “${activeBlock.title}”` : ""} (tỷ lệ ${res.overrun_ratio}x).`,
      "ok"
    );
  } catch (err) {
    showToast(`Lỗi lưu M7 từ Focus Timer: ${err.message}`, "danger");
  }
}

function renderCalibrationAdvisory() {
  const metricsEl = document.getElementById("stCalibrationMetrics");
  const noteEl = document.getElementById("stCalibrationNote");
  const applyBtn = document.getElementById("btnApplyCalibrationAlpha");
  const cal = state.calibration?.calibration;
  if (!metricsEl) return;
  if (!cal) {
    metricsEl.textContent = `Mẫu M7: ${state.calibration?.sample_count ?? 0}/5`;
    if (applyBtn) applyBtn.disabled = true;
    return;
  }
  const ratioTxt = cal.mean_ratio != null ? ` · TB thực/ước = ${cal.mean_ratio}x` : "";
  metricsEl.textContent = `Mẫu M7: ${cal.sample_count}/${cal.min_samples_required}${ratioTxt} · Đề xuất α ${Number(
    cal.recommended_alpha_light
  ).toFixed(2)} / ${Number(cal.recommended_alpha_heavy).toFixed(2)}`;
  if (noteEl && cal.advisory_note) noteEl.textContent = cal.advisory_note;
  if (applyBtn) applyBtn.disabled = !cal.ready_to_apply;
}

/** GET /api/tasks/calibration (EWMA λ=0.25, ≥5 samples) — shared by the Dev card and Input tab 3. */
async function refreshCalibrationAdvisory() {
  state.calibration = await api.getCalibration(state.workspaceId).catch(() => state.calibration);
  renderCalibrationAdvisory();
}

async function applyRecommendedCalibrationAlpha() {
  const cal = state.calibration?.calibration;
  if (!cal?.ready_to_apply || !state.commitments) return;
  state.commitments.buffer_mode = "COGNITIVE_LOAD";
  state.commitments.alpha_light = Number(cal.recommended_alpha_light);
  state.commitments.alpha_heavy = Number(cal.recommended_alpha_heavy);
  invalidateSolverCaches();
  await solveActiveSolver(true);
  await persistWorkspace(true);
  showToast(`✨ Đã áp dụng α_light=${cal.recommended_alpha_light}, α_heavy=${cal.recommended_alpha_heavy}.`, "ok");
}

function _sendDesktopNotification(title, body) {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  try {
    new Notification(title, { body });
  } catch {
    // Restricted notification environments
  }
}

function _checkUpcomingBlockReminders() {
  if (!focusTimerState.notifyEnabled) return;
  const nowMs = Date.now();
  for (const blk of state.currentSchedule?.blocks || []) {
    if (state.completedBlocks[blk.block_id] || !blk.start_iso) continue;
    const startMs = Date.parse(blk.start_iso);
    if (Number.isNaN(startMs)) continue;
    const diffMin = Math.round((startMs - nowMs) / 60000);
    const key = `${blk.block_id}@${blk.start_iso}`;
    if (diffMin >= 1 && diffMin <= 10 && !focusTimerState.notifiedBlockKeys.has(key)) {
      focusTimerState.notifiedBlockKeys.add(key);
      _sendDesktopNotification(`Sắp tới phiên học (${diffMin} phút nữa)`, `${blk.title || blk.task_id} (${blk.start_time} – ${blk.end_time})`);
    }
  }
}

async function toggleScheduleNotifications() {
  const btn = document.getElementById("btnStNotifyToggle");
  if (focusTimerState.notifyEnabled) {
    focusTimerState.notifyEnabled = false;
    clearInterval(focusTimerState.notifyIntervalId);
    focusTimerState.notifyIntervalId = null;
    if (btn) btn.textContent = "🔔 Nhắc giờ: Tắt";
    return;
  }
  if (typeof Notification === "undefined") {
    showToast("Trình duyệt này không hỗ trợ thông báo.", "warn");
    return;
  }
  if (Notification.permission === "default") {
    try {
      await Notification.requestPermission();
    } catch {
      // ignore
    }
  }
  if (Notification.permission !== "granted") {
    showToast("Chưa được cấp quyền thông báo — hãy cho phép trong trình duyệt.", "warn");
    return;
  }
  focusTimerState.notifyEnabled = true;
  if (btn) btn.textContent = "🔔 Nhắc giờ: Bật";
  _checkUpcomingBlockReminders();
  focusTimerState.notifyIntervalId = setInterval(_checkUpcomingBlockReminders, 60000);
}

function setBusyState(busy) {
  document.body.style.cursor = busy ? "progress" : "";
}

// ============================================================================
// MODALS & STATIC EVENT LISTENERS
// ============================================================================

function openModal(id) {
  closeAllPopovers();
  document.getElementById(id)?.classList.add("open");
}

function closeModal(id) {
  document.getElementById(id)?.classList.remove("open");
}

function closeAllPopovers() {
  document.querySelectorAll(".popover-menu.open").forEach((p) => p.classList.remove("open"));
  document.getElementById("btnToggleSuites")?.setAttribute("aria-expanded", "false");
  document.getElementById("btnToggleSettings")?.setAttribute("aria-expanded", "false");
  document.getElementById("btnToggleTheme")?.setAttribute("aria-expanded", "false");
  document.getElementById("btnToggleCalendarRange")?.setAttribute("aria-expanded", "false");
  document.getElementById("btnToggleSolverMenu")?.setAttribute("aria-expanded", "false");
}

function openInputModal(tab = null) {
  if (tab) state.inputTab = tab;
  const modal = document.getElementById("inputModal");
  const hint = modal.querySelector("#inputModalLoadHint");
  const rho = state.currentEvaluation?.gates?.rho_deadline;
  hint.textContent =
    rho !== undefined
      ? `Mật độ tải hạn chót hiện tại: ρ = ${(rho * 100).toFixed(0)}% ${rho > 1 ? "(Quá tải)" : "(Ổn định)"}`
      : `${state.tasks.length} việc · ${(state.commitments.fixed_events || []).length} lịch cố định`;

  renderInputModal(modal, {
    onDataMutated: async (msg) => {
      await solveActiveSolver(true);
      await persistWorkspace(true);
      if (state.activeView === "weights") fetchSolverWeights(false);
      showToast(msg, "ok");
    },
    onToast: (msg, tone) => showToast(msg, tone),
  });
  openModal("inputModal");
}

function openBlockModal(blockId, focusSection = null) {
  const blocks = state.currentSchedule?.blocks || [];
  const block = blocks.find((b) => b.block_id === blockId);
  if (!block) return;
  const modal = document.getElementById("blockModal");
  renderBlockInspectorModal(modal, block, focusSection, {
    onTogglePin: (bid) => handleTogglePin(bid),
    onCheckinBlock: (blk, mins) => handleCheckinBlock(blk, mins),
    onOverrunBlock: (blk, extra) => handleOverrunBlock(blk, extra),
    onClose: () => closeModal("blockModal"),
  });
  openModal("blockModal");
}

function openDisruptionModal() {
  const modal = document.getElementById("disruptionModal");
  renderDisruptionModal(modal, {
    onRunRepair: (payload) => handleRunRepair(payload),
    onClose: () => closeModal("disruptionModal"),
  });
  openModal("disruptionModal");
}

function openOverloadModal() {
  const modal = document.getElementById("overloadModal");
  renderOverloadModal(modal, {
    onPreviewOption: (optId, code, tid) => handlePreviewOverload(optId, code, tid),
  });
  openModal("overloadModal");
}

function wireStaticListeners() {
  // Focus Timer · Calibration · Reminders (Dev panel)
  document.getElementById("stFocusPresetSelect")?.addEventListener("change", changeFocusTimerPreset);
  document.getElementById("btnFocusStart")?.addEventListener("click", startFocusTimer);
  document.getElementById("btnFocusPause")?.addEventListener("click", pauseFocusTimer);
  document.getElementById("btnFocusReset")?.addEventListener("click", resetFocusTimer);
  document.getElementById("btnFocusCompleteM7")?.addEventListener("click", completeFocusTimerToM7);
  document.getElementById("btnRefreshCalibration")?.addEventListener("click", refreshCalibrationAdvisory);
  document.getElementById("btnApplyCalibrationAlpha")?.addEventListener("click", applyRecommendedCalibrationAlpha);
  document.getElementById("btnStNotifyToggle")?.addEventListener("click", toggleScheduleNotifications);

  // View tabs
  document.querySelectorAll("[data-view-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-view-tab");
      if (target === "benchmark" && !state.benchmarkData) {
        runBenchmarkAll(true);
      } else if (target === "weights" && !state.weightsData) {
        fetchSolverWeights(true);
      } else {
        setActiveView(target);
      }
    });
  });

  // Top bar & Settings buttons
  document.getElementById("btnOpenInputModal").addEventListener("click", () => openInputModal());
  document.getElementById("btnTopWeights").addEventListener("click", () => {
    closeAllPopovers();
    fetchSolverWeights(true);
  });
  document.getElementById("btnTopBenchmark").addEventListener("click", () => {
    closeAllPopovers();
    runBenchmarkAll(true);
  });
  document.getElementById("btnTopShowcase")?.addEventListener("click", () => {
    closeAllPopovers();
    setActiveView("showcase");
  });
  document.getElementById("btnOpenDisruption").addEventListener("click", () => openDisruptionModal());

  // Week navigation & 7d/14d horizon
  // ‹ › only change the viewed week; re-planning another week is the banner's explicit button.
  document.getElementById("btnWeekPrev").addEventListener("click", () => setViewWeek((Number(state.viewWeekOffset) || 0) - 1));
  document.getElementById("btnWeekNext").addEventListener("click", () => setViewWeek((Number(state.viewWeekOffset) || 0) + 1));
  document.getElementById("btnWeekToday").addEventListener("click", () => {
    const nowSlot = resolveNowSlot(state.commitments);
    state.viewWeekOffset = 0;
    state.scrubberStartDay = Math.max(0, slotToDayIndex(nowSlot));
    setActiveView("calendar");
  });

  const setHorizon = async (days) => {
    state.commitments.horizon_days = days;
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
  };
  document.getElementById("btnHorizon7").addEventListener("click", () => setHorizon(7));
  document.getElementById("btnHorizon14").addEventListener("click", () => setHorizon(14));

  // Test Suites Popover
  document.getElementById("btnToggleSuites").addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = document.getElementById("suitesPopover");
    const willOpen = !pop.classList.contains("open");
    closeAllPopovers();
    if (willOpen) {
      renderTestSuitePopover(pop, {
        onLoadSuite: (src, id, seed, horizon = null) => loadSuite(src, id, seed, true, horizon),
        onOpenShowcase: () => {
          closeAllPopovers();
          setActiveView("showcase");
        },
      });
      pop.classList.add("open");
      e.currentTarget.setAttribute("aria-expanded", "true");
    }
  });

  // Theme Switcher Popover (Botanical Green / Light / Dark Forest)
  document.getElementById("btnToggleTheme")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = document.getElementById("themePopover");
    const willOpen = !pop.classList.contains("open");
    closeAllPopovers();
    if (willOpen) {
      pop.classList.add("open");
      e.currentTarget.setAttribute("aria-expanded", "true");
    }
  });
  document.querySelectorAll("[data-set-theme]").forEach((btn) => {
    btn.addEventListener("click", () => {
      applyTheme(btn.getAttribute("data-set-theme"), true);
      closeAllPopovers();
    });
  });

  // Collapsible Dev Side Panel
  document.getElementById("btnToggleDevPanel")?.addEventListener("click", () => {
    setDevPanelOpen(!state.devPanelOpen);
  });
  document.getElementById("btnCloseDevPanel")?.addEventListener("click", () => {
    setDevPanelOpen(false);
  });

  // Calendar Range & Start Day Popover
  document.getElementById("btnToggleCalendarRange").addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = document.getElementById("calendarRangePopover");
    const willOpen = !pop.classList.contains("open");
    closeAllPopovers();
    if (willOpen) {
      renderCalendarRangePopover();
      pop.classList.add("open");
      e.currentTarget.setAttribute("aria-expanded", "true");
    }
  });

  // Unified Settings & Tools Gear Popover
  document.getElementById("btnToggleSettings").addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = document.getElementById("settingsPopover");
    const willOpen = !pop.classList.contains("open");
    closeAllPopovers();
    if (willOpen) {
      pop.classList.add("open");
      e.currentTarget.setAttribute("aria-expanded", "true");
    }
  });

  document.getElementById("chkSettingHideSleep")?.addEventListener("change", (e) => {
    state.hideSleepHours = e.target.checked;
    renderAll();
  });
  document.getElementById("chkSettingEnergy")?.addEventListener("change", (e) => {
    state.showEnergyBackdrop = e.target.checked;
    renderAll();
  });
  document.getElementById("chkSettingTechMeta")?.addEventListener("change", (e) => {
    state.showTechMetaOnBlocks = e.target.checked;
    renderAll();
  });

  document.getElementById("btnSaveSqlState").addEventListener("click", () => {
    closeAllPopovers();
    persistWorkspace(false);
  });
  document.getElementById("btnExportIcs").addEventListener("click", () => handleExport("ics"));
  document.getElementById("btnExportCsv").addEventListener("click", () => handleExport("csv"));
  document.getElementById("btnExportJson").addEventListener("click", () => handleExport("json"));
  document.getElementById("btnClearAllSchedule")?.addEventListener("click", () => {
    closeAllPopovers();
    const chk = document.getElementById("chkClearIncludeFixed");
    if (chk) chk.checked = false;
    const sum = document.getElementById("clearAllSummary");
    if (sum) {
      sum.textContent = `${state.tasks.length} việc · ${(state.pinnedBlocks || []).length} khối ghim · ${
        Object.keys(state.completedBlocks || {}).length
      } check-in · ${(state.commitments.fixed_events || []).length} lịch cố định · ${(state.commitments.personal_habits || []).length} thói quen`;
    }
    openModal("clearAllModal");
  });
  document.getElementById("btnConfirmClearAll")?.addEventListener("click", () =>
    clearAllSchedule({ includeFixed: Boolean(document.getElementById("chkClearIncludeFixed")?.checked) })
  );

  document.getElementById("btnResetState").addEventListener("click", async () => {
    closeAllPopovers();
    await api.deleteState(state.workspaceId).catch(() => {});
    await loadSuite("preset", "minh", 42, true);
  });

  // Input modal tabs
  document.querySelectorAll("[data-input-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.inputTab = btn.getAttribute("data-input-tab");
      openInputModal(state.inputTab);
    });
  });

  // Close modals & popovers on backdrop/button/Escape
  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => closeModal(btn.getAttribute("data-close-modal")));
  });
  document.querySelectorAll(".modal-backdrop").forEach((bg) => {
    bg.addEventListener("click", (e) => {
      if (e.target === bg) bg.classList.remove("open");
    });
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".popover-anchor")) closeAllPopovers();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllPopovers();
      document.querySelectorAll(".modal-backdrop.open").forEach((m) => m.classList.remove("open"));
    }
  });
}

bootstrap();
