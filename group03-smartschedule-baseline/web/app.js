/**
 * SmartSchedule UI v3 — Main ES Module Coordinator.
 * Wires Top Bar, Solver Switcher (with 0ms benchmark cache), 4 Workspace Views,
 * Unified 3-Tab Input Modal, Drag-and-Drop PINNED validation, M7 Check-in,
 * Local Repair, Overload Rescue, and SQLite State Persistence.
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

async function solveActiveSolver(forceFresh = false) {
  const key = state.activeSolver;
  if (!forceFresh && state.schedulesBySolver[key]) {
    state.currentSchedule = state.schedulesBySolver[key];
    state.currentEvaluation = state.schedulesBySolver[key].evaluation || null;
    renderAll();
    return;
  }

  setBusyState(true);
  try {
    const payload = buildApiPayload(key);
    const sched = await api.plan(payload);
    let evalReport = null;
    try {
      evalReport = await api.evaluate({
        commitments: state.commitments,
        tasks: state.tasks,
        pinned_blocks: state.pinnedBlocks,
        algorithm: key,
        schedule: sched,
      });
    } catch {
      evalReport = null;
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
      state.currentEvaluation = state.currentSchedule.evaluation || null;
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
    renderOverloadBox(state.currentSchedule);
    renderMainGrid();
    renderPlacedBlocksTable(state.currentSchedule);
    renderStudentViews();

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
    renderOverloadBox(state.currentSchedule);
    renderMainGrid();
    renderPlacedBlocksTable(state.currentSchedule);
    renderStudentViews();

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

async function runAllSolversDeterminismLedger() {
  const ledgerBody = document.getElementById("determinismLedgerBody");
  if (!ledgerBody) return;
  const algos = [
    "GREEDY_EDF_FIRST_FIT",
    "GREEDY_LST_BEST_FIT",
    "GREEDY_WSPT_SMITH_RULE",
    "BACKTRACKING_BRANCH_AND_BOUND",
    "SCORED_GREEDY",
  ];
  ledgerBody.innerHTML = `<tr><td colspan="4" class="py-4 text-center text-indigo-700 font-semibold">⏳ Đang chạy kiểm chứng SHA-256 (3x runs × 5 solvers)...</td></tr>`;

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
  const ws = parseWeekStartDate(state.commitments.planning_week_start);
  const we = addDays(ws, horizon - 1);
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
