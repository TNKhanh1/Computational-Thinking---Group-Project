/**
 * SmartSchedule UI v3 — Main ES Module Coordinator.
 * Wires Top Bar, Solver Switcher (with 0ms benchmark cache, including HYBRID_ALNS),
 * 4 Workspace Views, Unified 3-Tab Input Modal, Drag-and-Drop PINNED validation,
 * M7 Check-in & EWMA Calibration, Focus Timer, Local Repair, Overload Rescue,
 * and SQLite State Persistence.
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
      await refreshCalibrationAdvisory();
      return;
    }
  } catch {
    await loadSuite("preset", "minh", 42, false);
    await refreshCalibrationAdvisory();
    return;
  }

  await solveActiveSolver();
  await refreshCalibrationAdvisory();
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

async function evaluateCurrentScheduleV21(scheduleObj = state.currentSchedule) {
  if (!scheduleObj) return null;
  try {
    // Delegates to POST /api/evaluate via api.evaluate
    const evalReport = await api.evaluate({
      commitments: state.commitments,
      tasks: state.tasks,
      pinned_blocks: state.pinnedBlocks,
      algorithm: state.activeSolver,
      schedule: scheduleObj,
    });
    state.currentEvaluation = evalReport;
    scheduleObj.evaluation = evalReport;
    renderHealthV21Panels(scheduleObj, evalReport);
    return evalReport;
  } catch {
    return null;
  }
}

async function solveActiveSolver(forceFresh = false) {
  const key = state.activeSolver;
  if (!forceFresh && state.schedulesBySolver[key]) {
    state.currentSchedule = state.schedulesBySolver[key];
    state.currentEvaluation =
      state.schedulesBySolver[key].evaluation ||
      state.schedulesBySolver[key].health_v21 ||
      null;
    renderAll();
    return;
  }

  setBusyState(true);
  try {
    const payload = buildApiPayload(key);
    const sched = await api.plan(payload);
    let evalReport = sched.health_v21 || null;
    try {
      evalReport = await api.evaluate({
        commitments: state.commitments,
        tasks: state.tasks,
        pinned_blocks: state.pinnedBlocks,
        algorithm: key,
        schedule: sched,
      });
    } catch {
      evalReport = sched.health_v21 || null;
    }
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
      state.currentEvaluation =
        state.currentSchedule.evaluation || state.currentSchedule.health_v21 || null;
    }
    if (switchToView) {
      setActiveView("benchmark");
    } else {
      renderAll();
    }
    const top = res.ranking?.[0];
    if (top) {
      showToast(
        `Hoàn tất chấm ${res.ranking.length} thuật toán! Hạng #1: ${top.solver_key} (${top.verdict}).`,
        "ok"
      );
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

async function loadSuite(source, id, seed = 42, notify = true) {
  closeAllPopovers();
  setBusyState(true);
  try {
    const res = await api.loadSuite(source, id, seed);
    state.commitments = res.commitments || state.commitments;
    state.tasks = res.tasks || [];
    state.pinnedBlocks = res.pinned_blocks || [];
    state.completedBlocks = {};
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

async function handleDropMoveBlock(blockId, newStartSlot, dayLabel, timeLabel) {
  const blocks = state.currentSchedule?.blocks || [];
  const blk = blocks.find((b) => b.block_id === blockId);
  if (!blk) return;

  setBusyState(true);
  try {
    const val = await api.validateMove({
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm: state.activeSolver,
      blocks,
      current_blocks: blocks,
      block_id: blockId,
      new_start_slot: newStartSlot,
      new_day: dayLabel,
      new_time: timeLabel,
    });
    if (!val.ok) {
      const msg = (val.violations || []).map((v) => v.message).join(" · ") || "Vi phạm ràng buộc cứng H1–H5";
      showToast(`Không thể dời "${blk.title}" sang ${dayLabel} ${timeLabel}: ${msg}`, "danger");
      return;
    }

    const durSlots = Math.max(1, blk.end_slot - blk.start_slot);
    const updatedBlock = val.proposed_block || {
      ...blk,
      start_slot: newStartSlot,
      end_slot: newStartSlot + durSlots,
      day: dayLabel,
      start_time: timeLabel,
      state: "PINNED",
    };
    updatedBlock.state = "PINNED";

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
  } finally {
    setBusyState(false);
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
  setBusyState(true);
  try {
    const res = await api.completeTask({
      task_id: block.task_id,
      category: block.category || "OTHER",
      estimated_duration_min: block.duration_min || 60,
      actual_duration_min: actualMin,
      completed: true,
      workspace_id: state.workspaceId,
    });
    state.completedBlocks[block.block_id] = {
      actual_min: actualMin,
      completed_at: new Date().toISOString(),
    };
    state.calibration = await api.getCalibration(state.workspaceId).catch(() => state.calibration);
    await refreshCalibrationAdvisory();
    closeModal("blockModal");
    await persistWorkspace(true);
    renderAll();
    showToast(
      `✔️ Đã ghi nhận ${actualMin}p (tỷ lệ ×${res.overrun_ratio ?? "?"}). Gợi ý hệ số cá nhân: α≈${res.recommended_alpha ?? "1.20"}.`,
      "ok"
    );
  } catch (err) {
    showToast(`Lỗi Check-in M7: ${err.message}`, "danger");
  } finally {
    setBusyState(false);
  }
}

async function handleOverrunBlock(block, extraMin) {
  setBusyState(true);
  try {
    const rep = await api.overrun({
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm: state.activeSolver,
      task_id: block.task_id,
      extra_min: extraMin,
    });
    const nextSched = rep.after_schedule || rep.schedule;
    if (nextSched) {
      state.currentSchedule = nextSched;
      await evaluateCurrentScheduleV21(nextSched);
    }
    const taskObj = state.tasks.find((t) => t.task_id === block.task_id);
    if (taskObj && rep.new_duration_min) {
      taskObj.duration_min = rep.new_duration_min;
    }
    closeModal("blockModal");
    invalidateSolverCaches();
    renderAll();
    await persistWorkspace(true);
    showToast(
      `⏱️ Đã cập nhật tràn +${extraMin}p cho "${block.title}" (${rep.shifted_blocks_count ?? 0} phiên dịch chuyển).`,
      "warn"
    );
  } catch (err) {
    showToast(`Lỗi xử lý tràn giờ: ${err.message}`, "danger");
  } finally {
    setBusyState(false);
  }
}

async function handleRunRepair({ new_event, mode }) {
  setBusyState(true);
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
    const stab = res.stability_score ?? res.stability_pct ?? res.summary?.stability_pct;
    showToast(
      `Đã chèn sự cố "${new_event.title}" (${mode})${stab != null ? ` · Độ ổn định: ${Number(stab).toFixed(1)}%` : ""}.`,
      "ok"
    );
  } catch (err) {
    showToast(`Lỗi chạy Local Repair: ${err.message}`, "danger");
  } finally {
    setBusyState(false);
  }
}

async function handlePreviewOverload(optionId, optionCode, targetTaskId) {
  setBusyState(true);
  try {
    const prev = await api.overloadPreview({
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm: state.activeSolver,
      option_id: optionId,
      option_code: optionCode,
      target_task_id: targetTaskId,
      schedule: state.currentSchedule,
    });
    state.overloadPreview = {
      option_id: prev.option_id || optionId,
      option_code: prev.option_code || optionCode,
      target_task_id: prev.target_task_id || targetTaskId,
      resolved_tasks: prev.resolved_tasks || null,
      blocks: prev.blocks || prev.schedule?.blocks || [],
    };
    closeModal("overloadModal");
    renderAll();
    showToast(`Đang xem thử phương án ${state.overloadPreview.option_id} (nét đứt trên lịch).`, "ok");
  } catch (err) {
    showToast(`Lỗi xem thử giải cứu quá tải: ${err.message}`, "danger");
  } finally {
    setBusyState(false);
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

function handleCancelOverloadPreview() {
  state.overloadPreview = null;
  renderAll();
  showToast("Đã hoàn tác xem thử quá tải.", "ok");
}

async function handleExport(fmt) {
  closeAllPopovers();
  setBusyState(true);
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
  } finally {
    setBusyState(false);
  }
}

async function handleResetState() {
  closeAllPopovers();
  setBusyState(true);
  try {
    await api.deleteState(state.workspaceId).catch(() => null);
    await loadSuite("preset", "minh", 42, true);
  } finally {
    setBusyState(false);
  }
}

// ============================================================================
// REAL-TIME V2.1 4-PILLAR PANELS + P3.3 FOCUS TIMER / CALIBRATION
// ============================================================================

function renderHealthV21Panels(scheduleObj = state.currentSchedule, evalReport = state.currentEvaluation) {
  const hv = evalReport || scheduleObj?.health_v21 || null;
  const stBadge = document.getElementById("stHealthVerdictBadge");
  const stRho = document.getElementById("stHealthRhoBadge");
  const stSum = document.getElementById("stHealthSummaryText");
  const stIceeList = document.getElementById("stHealthIceeList");
  const labBadge = document.getElementById("labHealthVerdictBadge");
  const labGrid = document.getElementById("labHealthVectorGrid");
  const labIcee = document.getElementById("labHealthIceeList");

  if (!hv || hv.available === false) {
    if (stBadge) {
      stBadge.textContent = "Chưa chấm";
      stBadge.className = "badge badge-neutral mono";
    }
    if (labBadge) labBadge.textContent = "—";
    return;
  }

  const vb = getVerdictBadge(hv.verdict);
  if (stBadge) {
    stBadge.textContent = vb.label;
    stBadge.className = `badge ${vb.cls} mono`;
  }
  if (labBadge) {
    labBadge.textContent = vb.short;
    labBadge.className = `badge ${vb.cls} mono`;
  }
  const rho = hv.gates?.rho_deadline;
  if (stRho) {
    stRho.textContent = rho !== undefined ? `ρ=${(rho * 100).toFixed(0)}%` : "";
  }
  if (stSum) {
    stSum.textContent =
      (hv.verdict_reasons_vi && hv.verdict_reasons_vi[0]) ||
      (hv.verdict === "HIGH_PRODUCTIVITY"
        ? "Đạt chuẩn năng suất & nhịp sinh học."
        : "Xem các gợi ý ICEE để tối ưu lịch học.");
  }

  const p1Rate = hv.pillars?.p1?.deadline_value_rate_pct ?? hv.p1_value_timeliness?.deadline_value_rate_pct ?? 100;
  const p2Peak = hv.pillars?.p2?.heavy_peak_match_pct ?? hv.p2_cognitive_biology?.heavy_peak_match_pct ?? 100;
  const p3Max = hv.pillars?.p3?.max_daily_total_min ?? 0;
  const p4Shk = hv.pillars?.p4?.shock_25_pct ?? hv.p4_robustness_stability?.shock_results?.[0]?.survived_priority_pct ?? 100;
  const g1 = hv.gates?.g1_total_violations ?? 0;
  const sjl = hv.pillars?.p2?.sjl_minutes ?? hv.p2_cognitive_biology?.sjl_minutes;

  if (labGrid) {
    labGrid.innerHTML = `
      <div class="dev-stat"><span>G1 Cứng</span><strong>${g1}</strong></div>
      <div class="dev-stat"><span>P1 Kịp hạn</span><strong>${Number(p1Rate).toFixed(1)}%</strong></div>
      <div class="dev-stat"><span>P2 Peak nặng</span><strong>${Number(p2Peak).toFixed(1)}%</strong></div>
      <div class="dev-stat"><span>P4 Sốc +25%</span><strong>${Number(p4Shk).toFixed(1)}%</strong></div>
      <div class="dev-stat"><span>P3 Max ngày</span><strong>${p3Max}p</strong></div>
      <div class="dev-stat"><span>P2 SJL</span><strong>${sjl != null ? `${Number(sjl).toFixed(0)}p` : "—"}</strong></div>
    `;
  }

  const critiques = hv.top_critiques || hv.d1_icee_critiques || [];
  const critHtml = critiques.length
    ? critiques
        .slice(0, 3)
        .map((c) => `<li><strong>${esc(c.severity || "INFO")}:</strong> ${esc(c.summary_vi || "")}</li>`)
        .join("")
    : `<li>Không có cảnh báo ICEE.</li>`;
  if (stIceeList) stIceeList.innerHTML = critHtml;
  if (labIcee) labIcee.innerHTML = `<ul style="margin:0;padding-left:16px;">${critHtml}</ul>`;
}

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
      st.textContent = `Đang tập trung... (~${elapsedMin}p)`;
    } else if (focusTimerState.elapsedSec > 0) {
      st.textContent = `Đã tạm dừng · ${elapsedMin}p`;
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
      _sendDesktopNotification(
        "SmartSchedule Focus Timer",
        "Hết phiên tập trung! Bấm 'Lưu M7' để ghi nhận thời lượng thực tế."
      );
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
  const activeBlock = Array.isArray(state.currentSchedule?.blocks)
    ? state.currentSchedule.blocks.find((b) => !state.completedBlocks[b.block_id])
    : null;
  const taskId = activeBlock ? activeBlock.task_id || "FOCUS-SESSION" : "FOCUS-SESSION";
  const category = activeBlock ? activeBlock.category || "STUDY" : "STUDY";
  const estimatedMin = activeBlock
    ? activeBlock.duration_min || Math.round(focusTimerState.targetSec / 60)
    : Math.round(focusTimerState.targetSec / 60);

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
        workspace_id: state.workspaceId,
      }),
    });
    if (res.ok) {
      const st = document.getElementById("stFocusTimerStatus");
      if (st) st.textContent = `✔️ Đã lưu M7 (${measuredMin}p / ${estimatedMin}p) cho ${taskId}`;
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
    const res = await fetch(`/api/tasks/calibration?workspace_id=${encodeURIComponent(state.workspaceId)}&min_samples=5&lambda_ewma=0.25`);
    if (!res.ok) return;
    const data = await res.json();
    const cal = data.calibration;
    if (!cal) return;
    state.calibration = data;
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
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
    showToast(`✨ Đã áp dụng α_light=${cal.recommended_alpha_light}, α_heavy=${cal.recommended_alpha_heavy}.`, "ok");
  }
}

function _sendDesktopNotification(title, body) {
  if (typeof Notification === "undefined") return;
  if (Notification.permission === "granted") {
    try {
      new Notification(title, { body });
    } catch {
      // Ignore restricted notification environments
    }
  }
}

function _checkUpcomingBlockReminders() {
  if (!focusTimerState.notifyEnabled || !Array.isArray(state.currentSchedule?.blocks)) return;
  const now = new Date();
  const jsDay = now.getDay();
  const mondayIdx = (jsDay + 6) % 7;
  const dayNames = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  const todayName = dayNames[mondayIdx];
  const nowMin = now.getHours() * 60 + now.getMinutes();

  for (const blk of state.currentSchedule.blocks) {
    if (blk.day !== todayName || state.completedBlocks[blk.block_id]) continue;
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
    } catch {
      // Ignore permission failure
    }
  }
  focusTimerState.notifyEnabled = true;
  if (btn) btn.textContent = "🔔 Nhắc giờ: Bật";
  _checkUpcomingBlockReminders();
  focusTimerState.notifyIntervalId = setInterval(_checkUpcomingBlockReminders, 60000);
}

// ============================================================================
// RENDERING ORCHESTRATION
// ============================================================================

function applyTheme(themeName, persist = true) {
  const clean = ["botanical", "light", "dark"].includes(themeName) ? themeName : "botanical";
  state.theme = clean;
  document.documentElement.setAttribute("data-theme", clean);
  if (persist) {
    try {
      localStorage.setItem("smartschedule_theme", clean);
    } catch {
      // Ignore storage errors
    }
  }
  document.querySelectorAll("#themePopover [data-set-theme]").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-set-theme") === clean);
  });
}

function setActiveView(viewName) {
  const clean = ["calendar", "list", "weights", "benchmark"].includes(viewName) ? viewName : "calendar";
  state.activeView = clean;

  document.querySelectorAll(".view-tab[data-view-tab]").forEach((btn) => {
    const active = btn.getAttribute("data-view-tab") === clean;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", String(active));
  });

  const panelMap = {
    calendar: "viewCalendar",
    list: "viewList",
    weights: "viewWeights",
    benchmark: "viewBenchmark",
  };
  for (const [key, domId] of Object.entries(panelMap)) {
    document.getElementById(domId)?.classList.toggle("active", key === clean);
  }

  renderAll();
}

function renderAll() {
  renderTopBar();
  renderCalendarRangeLabel();
  renderSolverRibbon();
  renderTelemetryStrip();
  renderHealthV21Panels(state.currentSchedule, state.currentEvaluation);

  const view = state.activeView || "calendar";
  if (view === "calendar") {
    const el = document.getElementById("viewCalendar");
    if (el) {
      renderCalendarView(el, {
        onSyncRangeLabel: () => renderCalendarRangeLabel(),
        onOpenOverloadRescue: () => openOverloadModal(),
        onApplyOverloadPreview: () => handleApplyOverloadPreview(),
        onCancelOverloadPreview: () => handleCancelOverloadPreview(),
        onInspectBlock: (blockId, focusSection = null) => openBlockModal(blockId, focusSection),
        onDropMoveBlock: (bid, newSlot, dayLbl, timeLbl) => handleDropMoveBlock(bid, newSlot, dayLbl, timeLbl),
      });
    }
  } else if (view === "list") {
    const el = document.getElementById("viewList");
    if (el) {
      renderListView(el, {
        onInspectBlock: (blockId, focusSection = null) => openBlockModal(blockId, focusSection),
        onTogglePin: (bid) => handleTogglePin(bid),
      });
    }
  } else if (view === "weights") {
    const el = document.getElementById("viewWeights");
    if (el) {
      renderWeightsView(el, {
        onBackToCalendar: () => setActiveView("calendar"),
        onRefreshWeights: () => fetchSolverWeights(false),
      });
    }
  } else if (view === "benchmark") {
    const el = document.getElementById("viewBenchmark");
    if (el) {
      renderBenchmarkView(el, {
        onBackToCalendar: () => setActiveView("calendar"),
        onRunBenchmarkAll: () => runBenchmarkAll(true),
        onSelectSolver: async (solverKey, backToCalendar = false) => {
          state.activeSolver = solverKey;
          await solveActiveSolver(false);
          if (backToCalendar) setActiveView("calendar");
        },
      });
    }
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
  const badgeEl = document.getElementById("activeSuiteBadge");
  if (badgeEl) badgeEl.textContent = state.suiteLabel;
  const devLbl = document.getElementById("devSuiteLabel");
  if (devLbl) devLbl.textContent = state.suiteLabel;
  const cntEl = document.getElementById("txtInputTaskCount");
  if (cntEl) cntEl.textContent = String(state.tasks.length);

  const horizon = Number(state.commitments.horizon_days || 7);
  const ws = parseWeekStartDate(state.commitments.planning_week_start);
  const we = addDays(ws, horizon - 1);
  const rangeEl = document.getElementById("txtWeekRange");
  if (rangeEl) rangeEl.textContent = `${fmtDDMM(ws)} – ${fmtDDMM(we)}/${we.getFullYear()}`;
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
  if (!bar) return;
  const solversList = state.solvers.some((s) => s.key === "HYBRID_ALNS")
    ? state.solvers
    : [...state.solvers, { key: "HYBRID_ALNS", label: "HYBRID_ALNS", full_name: "Hybrid Adaptive Large Neighborhood Search" }];

  const activeMeta = solversList.find((s) => s.key === state.activeSolver) || {
    key: state.activeSolver,
    label: state.activeSolver,
    full_name: "",
  };
  const activeCached = state.schedulesBySolver[state.activeSolver];
  const activeVb = getVerdictBadge(activeCached?.evaluation?.verdict || activeCached?.health_v21?.verdict);
  const activeMs = activeCached ? `${Number(activeCached.execution_time_ms || 0).toFixed(0)}ms` : "";

  const optionsHtml = solversList
    .map((s) => {
      const isSelected = s.key === state.activeSolver;
      const cached = state.schedulesBySolver[s.key];
      const evalRep = cached?.evaluation || cached?.health_v21;
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
  trigger?.addEventListener("click", (e) => {
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
  if (!el || !actionsEl) return;

  const sched = state.currentSchedule;
  const rep = state.currentEvaluation || sched?.health_v21 || null;

  if (!sched) {
    el.innerHTML = `<span class="badge badge-neutral">Chưa có lịch</span>`;
    actionsEl.innerHTML = "";
    return;
  }

  const vb = getVerdictBadge(rep?.verdict);
  if (devDot) devDot.className = `status-dot ${vb.dot}`;

  const p1 =
    rep?.p1_value_timeliness?.deadline_value_rate_pct ??
    rep?.pillars?.p1?.deadline_value_rate_pct ??
    sched.metrics?.deadline_satisfaction_pct ??
    100;
  const shk25 =
    rep?.p4_robustness_stability?.shock_results?.[0]?.survived_priority_pct ??
    rep?.pillars?.p4?.shock_25_pct;
  const g1 = rep?.gates?.g1_total_violations ?? sched.metrics?.hard_violations ?? 0;
  const rho = rep?.gates?.rho_deadline;
  const ms = Number(sched.execution_time_ms || 0).toFixed(1);
  const topCrit = rep?.d1_icee_critiques?.[0] ?? rep?.top_critiques?.[0];
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
  if (!modal) return;
  const hint = modal.querySelector("#inputModalLoadHint");
  const rho = state.currentEvaluation?.gates?.rho_deadline;
  if (hint) {
    hint.textContent =
      rho !== undefined
        ? `Mật độ tải hạn chót hiện tại: ρ = ${(rho * 100).toFixed(0)}% ${rho > 1 ? "(Quá tải)" : "(Ổn định)"}`
        : `${state.tasks.length} việc · ${(state.commitments.fixed_events || []).length} lịch cố định`;
  }

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
  if (!modal) return;
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
  if (!modal) return;
  renderDisruptionModal(modal, {
    onRunRepair: (payload) => handleRunRepair(payload),
    onClose: () => closeModal("disruptionModal"),
  });
  openModal("disruptionModal");
}

function openOverloadModal() {
  const modal = document.getElementById("overloadModal");
  if (!modal) return;
  renderOverloadModal(modal, {
    onPreviewOption: (optId, code, tid) => handlePreviewOverload(optId, code, tid),
  });
  openModal("overloadModal");
}

function wireStaticListeners() {
  // Week navigation
  document.getElementById("btnWeekPrev")?.addEventListener("click", async () => {
    const step = Number(state.visibleDaysCount) || 7;
    if (state.scrubberStartDay > 0) {
      state.scrubberStartDay = Math.max(0, state.scrubberStartDay - step);
      renderAll();
    } else {
      const ws = parseWeekStartDate(state.commitments.planning_week_start);
      const prevWs = addDays(ws, -7);
      state.commitments.planning_week_start = `${fmtISODate(prevWs)}T00:00:00+07:00`;
      invalidateSolverCaches();
      await solveActiveSolver(true);
      await persistWorkspace(true);
    }
  });

  document.getElementById("btnWeekNext")?.addEventListener("click", async () => {
    const horizon = Math.max(7, Math.min(14, Number(state.commitments.horizon_days) || 7));
    const step = Number(state.visibleDaysCount) || 7;
    const maxStart = Math.max(0, horizon - 1);
    if (state.scrubberStartDay < maxStart && step < horizon) {
      state.scrubberStartDay = Math.min(maxStart, state.scrubberStartDay + step);
      renderAll();
    } else {
      const ws = parseWeekStartDate(state.commitments.planning_week_start);
      const nextWs = addDays(ws, 7);
      state.commitments.planning_week_start = `${fmtISODate(nextWs)}T00:00:00+07:00`;
      state.scrubberStartDay = 0;
      invalidateSolverCaches();
      await solveActiveSolver(true);
      await persistWorkspace(true);
    }
  });

  document.getElementById("btnWeekToday")?.addEventListener("click", () => {
    const horizon = Math.max(7, Math.min(14, Number(state.commitments.horizon_days) || 7));
    const todayIdx = Math.min(horizon - 1, Math.max(0, slotToDayIndex(resolveNowSlot(state.commitments))));
    state.scrubberStartDay = todayIdx;
    setActiveView("calendar");
  });

  // View tabs
  document.querySelectorAll(".view-tab[data-view-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-view-tab");
      setActiveView(target);
    });
  });

  // Primary input drawer
  document.getElementById("btnOpenInputModal")?.addEventListener("click", () => openInputModal());
  document.querySelectorAll("#inputModal .modal-tab[data-input-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.inputTab = btn.getAttribute("data-input-tab") || "tasks";
      openInputModal(state.inputTab);
    });
  });

  // Calendar Range Popover
  document.getElementById("btnToggleCalendarRange")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = document.getElementById("calendarRangePopover");
    const trig = document.getElementById("btnToggleCalendarRange");
    const willOpen = pop && !pop.classList.contains("open");
    closeAllPopovers();
    if (willOpen && pop) {
      renderCalendarRangePopover();
      pop.classList.add("open");
      trig?.setAttribute("aria-expanded", "true");
    }
  });

  // Theme Popover
  document.getElementById("btnToggleTheme")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = document.getElementById("themePopover");
    const trig = document.getElementById("btnToggleTheme");
    const willOpen = pop && !pop.classList.contains("open");
    closeAllPopovers();
    if (willOpen && pop) {
      pop.classList.add("open");
      trig?.setAttribute("aria-expanded", "true");
    }
  });
  document.querySelectorAll("#themePopover [data-set-theme]").forEach((btn) => {
    btn.addEventListener("click", () => {
      applyTheme(btn.getAttribute("data-set-theme"), true);
      closeAllPopovers();
    });
  });

  // Settings & Export Popover
  document.getElementById("btnToggleSettings")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = document.getElementById("settingsPopover");
    const trig = document.getElementById("btnToggleSettings");
    const willOpen = pop && !pop.classList.contains("open");
    closeAllPopovers();
    if (willOpen && pop) {
      pop.classList.add("open");
      trig?.setAttribute("aria-expanded", "true");
    }
  });

  document.getElementById("btnHorizon7")?.addEventListener("click", async () => {
    state.commitments.horizon_days = 7;
    state.scrubberStartDay = Math.min(state.scrubberStartDay, 6);
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
  });
  document.getElementById("btnHorizon14")?.addEventListener("click", async () => {
    state.commitments.horizon_days = 14;
    invalidateSolverCaches();
    await solveActiveSolver(true);
    await persistWorkspace(true);
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

  document.getElementById("btnOpenDisruption")?.addEventListener("click", () => openDisruptionModal());
  document.getElementById("btnSaveSqlState")?.addEventListener("click", async () => {
    closeAllPopovers();
    await persistWorkspace(false);
  });
  document.getElementById("btnExportIcs")?.addEventListener("click", () => handleExport("ics"));
  document.getElementById("btnExportCsv")?.addEventListener("click", () => handleExport("csv"));
  document.getElementById("btnExportJson")?.addEventListener("click", () => handleExport("json"));
  document.getElementById("btnResetState")?.addEventListener("click", () => handleResetState());

  // Dev Side Panel & Suites Popover
  document.getElementById("btnToggleDevPanel")?.addEventListener("click", () => setDevPanelOpen(!state.devPanelOpen));
  document.getElementById("btnCloseDevPanel")?.addEventListener("click", () => setDevPanelOpen(false));
  document.getElementById("btnToggleSuites")?.addEventListener("click", (e) => {
    e.stopPropagation();
    const pop = document.getElementById("suitesPopover");
    const trig = document.getElementById("btnToggleSuites");
    const willOpen = pop && !pop.classList.contains("open");
    closeAllPopovers();
    if (willOpen && pop) {
      renderTestSuitePopover(pop, {
        onLoadSuite: (source, id, seed) => loadSuite(source, id, seed, true),
      });
      pop.classList.add("open");
      trig?.setAttribute("aria-expanded", "true");
    }
  });

  document.getElementById("btnTopBenchmark")?.addEventListener("click", () => runBenchmarkAll(true));
  document.getElementById("btnTopWeights")?.addEventListener("click", () => fetchSolverWeights(true));

  // P3.3 Focus Timer & EWMA Calibration controls
  document.getElementById("stFocusPresetSelect")?.addEventListener("change", () => changeFocusTimerPreset());
  document.getElementById("btnFocusStart")?.addEventListener("click", () => startFocusTimer());
  document.getElementById("btnFocusPause")?.addEventListener("click", () => pauseFocusTimer());
  document.getElementById("btnFocusReset")?.addEventListener("click", () => resetFocusTimer());
  document.getElementById("btnFocusCompleteM7")?.addEventListener("click", () => completeFocusTimerToM7());
  document.getElementById("btnRefreshCalibration")?.addEventListener("click", () => refreshCalibrationAdvisory());
  document.getElementById("btnApplyCalibrationAlpha")?.addEventListener("click", () => applyRecommendedCalibrationAlpha());
  document.getElementById("btnStNotifyToggle")?.addEventListener("click", () => toggleScheduleNotifications());

  // Modal close buttons & backdrop dismissal
  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => closeModal(btn.getAttribute("data-close-modal")));
  });
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.classList.remove("open");
    });
  });

  // Global outside click & Escape key
  document.addEventListener("click", (e) => {
    if (!e.target.closest?.(".popover-anchor")) {
      closeAllPopovers();
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAllPopovers();
      document.querySelectorAll(".modal-backdrop.open").forEach((m) => m.classList.remove("open"));
    }
  });
}

if (typeof document !== "undefined") {
  bootstrap();
}
