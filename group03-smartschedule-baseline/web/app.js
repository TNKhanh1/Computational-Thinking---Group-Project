/**
 * SmartSchedule Baseline (V0) — Technical Benchmark Workbench Frontend Controller
 * Matches every DOM element in `web/index.html` and REST endpoint in `web/api.py`.
 */

const DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const DAYS_VI = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"];

const state = {
  commitments: {
    student_id: "MINH_YEAR2_CS",
    planning_week_start: "2026-11-02T00:00:00+07:00",
    sleep_schedule: {
      daily_start_time: "23:30",
      daily_end_time: "06:30",
      is_hard_lock: true,
    },
    fixed_events: [],
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
  pinnedBlocks: new Map(), // block_id -> ScheduleBlock
  doneBlocks: new Set(), // block_id
  taskBufferMap: new Map(), // task_id -> { raw_min, buffered_min }
};

// ============================================================================
// INITIALIZATION & PRESET / SCENARIO LOADERS
// ============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  updateSlotEquivalent();
  await loadScenariosDropdown();
  await loadPreset("minh");
  switchAppMode("STUDENT");
});

function pad2(n) {
  return String(n).padStart(2, "0");
}

function slotOffsetToTime(slotOffset) {
  const totalMin = slotOffset * 15;
  const hh = Math.floor(totalMin / 60);
  const mm = totalMin % 60;
  return `${pad2(hh)}:${pad2(mm)}`;
}

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

async function loadPreset(presetId) {
  try {
    const res = await fetch("/api/presets");
    if (!res.ok) throw new Error("Failed to fetch /api/presets");
    const data = await res.json();
    const presets = data.presets || data;
    const chosen = presets[presetId] || presets.minh;
    if (!chosen) return;

    state.commitments = chosen.commitments;
    state.tasks = Array.isArray(chosen.tasks) ? chosen.tasks : chosen.tasks.tasks || [];
    state.activeScenario = null;
    state.repairedMovedIds.clear();
    state.pinnedBlocks.clear();
    state.doneBlocks.clear();
    state.taskBufferMap.clear();

    const sel = document.getElementById("scenarioSelect");
    if (sel) sel.value = "";
    document.getElementById("scenarioBanner")?.classList.add("hidden");
    document.getElementById("determinismBanner")?.classList.add("hidden");
    document.getElementById("repairLogPanel")?.classList.add("hidden");

    syncAllLeftPanels();
    await solveSchedule();
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

    state.commitments = sc.commitments;
    state.tasks = sc.tasks || [];
    state.activeScenario = sc;
    state.repairedMovedIds.clear();

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
    await solveSchedule();
  } catch (err) {
    console.error("Error loading scenario:", err);
  }
}

function clearAllData() {
  state.tasks = [];
  state.commitments.fixed_events = [];
  state.repairedMovedIds.clear();
  state.pinnedBlocks.clear();
  state.doneBlocks.clear();
  state.taskBufferMap.clear();
  syncAllLeftPanels();
  solveSchedule();
}

// ============================================================================
// LEFT PANE TABS & INPUT FORMS
// ============================================================================

function switchLeftTab(tabName) {
  const map = {
    TASKS: { btn: "tabBtnTasks", panel: "tabPanelTasks" },
    COMMITMENTS: { btn: "tabBtnCommitments", panel: "tabPanelCommitments" },
    DISRUPTION: { btn: "tabBtnDisruption", panel: "tabPanelDisruption" },
  };
  for (const [k, cfg] of Object.entries(map)) {
    const btnEl = document.getElementById(cfg.btn);
    const panelEl = document.getElementById(cfg.panel);
    if (k === tabName) {
      btnEl.className = "py-2.5 px-2 border-b-2 border-indigo-600 text-indigo-700 bg-white";
      panelEl.classList.remove("hidden");
    } else {
      btnEl.className = "py-2.5 px-2 border-b-2 border-transparent text-slate-600 hover:text-slate-900";
      panelEl.classList.add("hidden");
    }
  }
  if (tabName === "DISRUPTION") {
    populateOverrunSelect();
  }
}

function syncAllLeftPanels() {
  renderTaskQueue();
  renderFixedEventsList();
  syncSleepUI();
  populateOverrunSelect();
}

function updateSlotEquivalent() {
  const dur = Math.max(15, parseInt(document.getElementById("inpTaskDuration")?.value || "120", 10));
  const slots = Math.ceil(dur / 15);
  const hours = (dur / 60).toFixed(1);
  const lbl = document.getElementById("slotEquivalentLabel");
  if (lbl) lbl.textContent = `= ${slots} slots (${hours} giờ)`;
}

function adjustDuration(delta) {
  const inp = document.getElementById("inpTaskDuration");
  if (!inp) return;
  const cur = parseInt(inp.value || "60", 10);
  inp.value = Math.max(15, cur + delta);
  updateSlotEquivalent();
}

function setPriority(prio) {
  document.getElementById("inpTaskPriority").value = String(prio);
  document.querySelectorAll(".prio-btn").forEach((btn) => {
    const bPrio = parseInt(btn.getAttribute("data-prio"), 10);
    if (bPrio === prio) {
      btn.className = "prio-btn flex-1 py-1 text-xs rounded border bg-indigo-600 text-white border-indigo-600 font-semibold";
    } else {
      btn.className = "prio-btn flex-1 py-1 text-xs rounded border border-slate-300 font-semibold";
    }
  });
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

function applyQuickAdd() {
  const inp = document.getElementById("quickAddInput");
  const parsed = parseQuickAdd(inp?.value || "");
  if (!parsed) return;

  document.getElementById("inpTaskId").value = `TASK-${state.tasks.length + 1}`;
  document.getElementById("inpTaskTitle").value = parsed.title;
  document.getElementById("inpTaskDuration").value = parsed.duration_min;
  document.getElementById("inpTaskDeadlineDay").value = parsed.deadline_day;
  document.getElementById("inpTaskDeadlineTime").value = parsed.deadline_time;
  setPriority(parsed.priority);
  document.getElementById("inpTaskSplittable").checked = parsed.is_splittable;
  document.getElementById("inpTaskMinChunk").value = parsed.min_chunk_min;
  document.getElementById("inpTaskDependsOn").value = parsed.depends_on.join(", ");
  updateSlotEquivalent();

  inp.value = "";
  document.getElementById("quickAddChips").innerHTML = "";
  saveTaskFromForm();
}

function resetTaskForm() {
  state.editingTaskId = null;
  document.getElementById("taskFormHeading").textContent = "📝 Biểu Mẫu Thông Số Task Chuẩn";
  document.getElementById("btnCancelEditTask").classList.add("hidden");
  document.getElementById("btnSaveTask").innerHTML = `<span>➕</span> Thêm Task Vào Hàng Đợi`;
  document.getElementById("inpTaskId").value = "";
  document.getElementById("inpTaskTitle").value = "";
  document.getElementById("inpTaskDuration").value = "120";
  document.getElementById("inpTaskDependsOn").value = "";
  setPriority(5);
  updateSlotEquivalent();
}

async function saveTaskFromForm() {
  const idRaw = document.getElementById("inpTaskId").value.trim().toUpperCase();
  const taskId = idRaw || `TASK-${state.tasks.length + 1}`;
  const title = document.getElementById("inpTaskTitle").value.trim() || taskId;
  const durationMin = Math.max(15, parseInt(document.getElementById("inpTaskDuration").value || "120", 10));
  const deadlineDay = document.getElementById("inpTaskDeadlineDay").value || null;
  const deadlineTime = document.getElementById("inpTaskDeadlineTime").value || "23:59";
  const priority = parseInt(document.getElementById("inpTaskPriority").value || "3", 10);
  const isSplittable = document.getElementById("inpTaskSplittable").checked;
  const minChunkMin = Math.max(15, parseInt(document.getElementById("inpTaskMinChunk").value || "45", 10));
  const depStr = document.getElementById("inpTaskDependsOn").value.trim();
  const dependsOn = depStr ? depStr.split(",").map((s) => s.trim()).filter(Boolean) : [];

  const taskObj = {
    task_id: taskId,
    title,
    duration_min: durationMin,
    deadline_day: deadlineDay,
    deadline_time: deadlineTime,
    priority,
    category: deadlineDay ? "DEADLINE" : "HABIT",
    is_splittable: isSplittable,
    min_chunk_min: minChunkMin,
    max_chunk_min: 90,
    depends_on: dependsOn,
  };

  if (state.editingTaskId) {
    const idx = state.tasks.findIndex((t) => (t.task_id || t.id) === state.editingTaskId);
    if (idx >= 0) state.tasks[idx] = taskObj;
    else state.tasks.push(taskObj);
  } else {
    state.tasks.push(taskObj);
  }

  resetTaskForm();
  syncAllLeftPanels();
  await solveSchedule();
}

function editTask(taskId) {
  const t = state.tasks.find((x) => (x.task_id || x.id) === taskId);
  if (!t) return;
  state.editingTaskId = taskId;
  document.getElementById("taskFormHeading").textContent = `✏️ Đang Sửa Task: ${taskId}`;
  document.getElementById("btnCancelEditTask").classList.remove("hidden");
  document.getElementById("btnSaveTask").innerHTML = `<span>💾</span> Lưu Cập Nhật Task`;

  document.getElementById("inpTaskId").value = t.task_id || t.id;
  document.getElementById("inpTaskTitle").value = t.title || "";
  document.getElementById("inpTaskDuration").value = t.duration_min || t.estimate_min || 60;
  document.getElementById("inpTaskDeadlineDay").value = t.deadline_day || "";
  document.getElementById("inpTaskDeadlineTime").value = t.deadline_time || "23:59";
  setPriority(t.priority || 3);
  document.getElementById("inpTaskSplittable").checked = Boolean(t.is_splittable ?? t.splittable);
  document.getElementById("inpTaskMinChunk").value = t.min_chunk_min || 45;
  document.getElementById("inpTaskDependsOn").value = (t.depends_on || t.after || []).join(", ");
  updateSlotEquivalent();
}

async function deleteTask(taskId) {
  state.tasks = state.tasks.filter((t) => (t.task_id || t.id) !== taskId);
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

  container.innerHTML = state.tasks
    .map((t) => {
      const tid = t.task_id || t.id;
      const dur = t.duration_min || t.estimate_min || 60;
      const dl = t.due ? t.due.slice(0, 16).replace("T", " ") : t.deadline_day ? `${t.deadline_day} ${t.deadline_time || "23:59"}` : "Linh hoạt";
      const isUnplaced = unplacedIds.has(tid);
      const deps = t.depends_on || t.after || [];

      return `
      <div class="p-2.5 rounded-lg border ${isUnplaced ? "border-rose-400 bg-rose-50" : "border-slate-200 bg-slate-50/70"} hover:border-indigo-300 transition flex items-start justify-between gap-2">
        <div class="space-y-0.5">
          <div class="flex items-center gap-1.5 flex-wrap">
            <span class="px-1.5 py-0.5 text-[10px] font-bold mono rounded bg-slate-800 text-white">${tid}</span>
            <span class="text-xs font-bold text-slate-800">${t.title}</span>
            ${isUnplaced ? `<span class="px-1.5 py-0.5 text-[10px] font-bold bg-rose-600 text-white rounded mono">UNPLACED</span>` : ""}
          </div>
          <div class="text-[11px] text-slate-600 mono flex flex-wrap items-center gap-2">
            <span>⏱ ${dur}p</span>
            <span>📅 ${dl}</span>
            <span>★ P${t.priority || 3}</span>
            <span>${t.is_splittable || t.splittable ? `✂️ Cắt (≥${t.min_chunk_min || 45}p)` : "🧱 Nguyên khối"}</span>
            ${deps.length ? `<span class="text-indigo-700 font-semibold">🔗 sau: ${deps.join(",")}</span>` : ""}
          </div>
        </div>
        <div class="flex items-center gap-1 shrink-0">
          <button onclick="editTask('${tid}')" class="px-1.5 py-1 text-xs text-slate-600 hover:text-indigo-600 rounded hover:bg-slate-200" title="Sửa Task">✏️</button>
          <button onclick="deleteTask('${tid}')" class="px-1.5 py-1 text-xs text-slate-600 hover:text-rose-600 rounded hover:bg-rose-100" title="Xóa Task">🗑️</button>
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
  const sEl = document.getElementById("inpSleepStart");
  const eEl = document.getElementById("inpSleepEnd");
  if (sEl) sEl.value = sleep.daily_start_time || sleep.start || "23:30";
  if (eEl) eEl.value = sleep.daily_end_time || sleep.end || "06:30";
}

async function updateSleepFromUI() {
  if (!state.commitments.sleep_schedule) state.commitments.sleep_schedule = {};
  state.commitments.sleep_schedule.daily_start_time = document.getElementById("inpSleepStart").value || "23:30";
  state.commitments.sleep_schedule.daily_end_time = document.getElementById("inpSleepEnd").value || "06:30";
  state.commitments.sleep_schedule.is_hard_lock = true;
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
  const algorithm = document.getElementById("solverSelect")?.value || "GREEDY_EDF_FIRST_FIT";
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

    renderKpiCards(schedule);
    renderOverloadBox(schedule);
    renderTaskQueue();
    renderMainGrid();
    renderPlacedBlocksTable(schedule);
    renderStudentViews();

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

  const hardEl = document.getElementById("kpiHardViolations");
  hardEl.textContent = String(s.hard_constraint_violations);
  hardEl.className =
    s.hard_constraint_violations === 0
      ? "text-2xl font-bold mono text-emerald-600"
      : "text-2xl font-bold mono text-rose-600";

  const dlEl = document.getElementById("kpiDeadlineRate");
  dlEl.textContent = `${s.deadline_satisfaction_rate.toFixed(1)}%`;
  dlEl.className =
    s.deadline_satisfaction_rate >= 100
      ? "text-2xl font-bold mono text-indigo-600"
      : "text-2xl font-bold mono text-amber-600";

  document.getElementById("kpiPlacedCount").textContent =
    `${s.tasks_placed} / ${s.total_tasks_requested} tasks (${s.parts_placed}/${s.parts_total} phiên)`;

  document.getElementById("kpiExecTime").textContent = schedule.execution_time_ms.toFixed(2);
  document.getElementById("kpiFreeSlots").textContent = String(s.free_slots_remaining);
  document.getElementById("kpiFragmentation").textContent =
    `Phân mảnh: ${(s.fragmentation_index * 100).toFixed(1)}%`;

  document.getElementById("kpiDeterminismHash").textContent =
    (schedule.determinism_hash || "--------").slice(0, 12) + "…";
  document.getElementById("kpiDeterminismHash").title = schedule.determinism_hash || "";
  document.getElementById("kpiSolverLabel").textContent = schedule.solver_used || "";
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

function renderMainGrid() {
  const tbody = document.getElementById("mainGridTbody");
  if (!tbody || !state.currentSchedule) return;

  const foldSleep = document.getElementById("chkFoldNightSleep")?.checked ?? true;
  const stepSlots = parseInt(document.getElementById("gridResolutionSelect")?.value || "1", 10);

  tbody.innerHTML = buildScheduleRowsHTML(state.currentSchedule, {
    foldSleep,
    stepSlots,
    diffOtherSchedule: null,
  });
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
        const slotIdx = dIdx * 96 + off;
        fixedLabelBySlot[slotIdx] = ev.title;
        fixedCatBySlot[slotIdx] = ev.category || "ACADEMIC_CLASS";
      }
    }
  }

  let html = "";
  const startOffset = foldSleep ? 26 : 0; // 26 * 15m = 06:30

  if (foldSleep) {
    html += `
      <tr class="slot-sleep text-[11px]">
        <td class="py-1.5 px-2 font-bold mono border-r border-slate-600">00:00 - 06:30</td>
        <td colspan="7" class="py-1.5 px-3 text-center font-medium">
          🌙 Khung giờ ngủ đêm được khóa cứng bảo vệ sức khỏe (26 slots/đêm × 7 ngày = 182 slots ban đêm + 14 slots sau 23:30 = 196 SLEEP slots)
        </td>
      </tr>`;
  }

  for (let offset = startOffset; offset < 96; offset += stepSlots) {
    const startTime = slotOffsetToTime(offset);
    const endTime = slotOffsetToTime(offset + stepSlots);
    const isFullHour = offset % 4 === 0;

    html += `<tr class="${isFullHour ? "border-t border-slate-300" : ""}">`;
    html += `<td class="py-1 px-2 mono text-[11px] ${isFullHour ? "font-bold text-slate-800 bg-slate-100" : "text-slate-500 bg-slate-50"} border-r border-slate-300">${startTime}</td>`;

    for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
      const slotIdx = dayIdx * 96 + offset;
      const rawState = gridStates[slotIdx] || "FREE";
      const block = blockBySlot[slotIdx];

      let cellClass = "slot-free";
      let cellText = "";

      if (rawState === "SLEEP") {
        cellClass = "slot-sleep";
        cellText = offset === 94 ? "🌙 Ngủ (23:30)" : "";
      } else if (rawState.startsWith("OCCUPIED")) {
        const cat = fixedCatBySlot[slotIdx] || "ACADEMIC_CLASS";
        if (cat === "MEAL") cellClass = "slot-occupied-meal";
        else if (cat === "DISRUPTION") cellClass = "slot-occupied-disruption";
        else cellClass = "slot-occupied-class";
        const prevSlotState = offset > startOffset ? gridStates[slotIdx - stepSlots] : "";
        cellText = prevSlotState !== rawState ? fixedLabelBySlot[slotIdx] || rawState.split(":")[1] : "〃";
      } else if (rawState.startsWith("BLOCK") && block) {
        const isMoved = state.repairedMovedIds.has(block.block_id);
        const isDiff = otherGridStates && otherGridStates[slotIdx] !== rawState;
        if (isDiff) cellClass = "slot-block-diff";
        else if (isMoved) cellClass = "slot-block-moved";
        else cellClass = "slot-block";

        const isBlockStart = slotIdx === block.start_slot || offset === startOffset;
        const partBadge = block.total_chunks > 1 ? ` (${block.chunk_index}/${block.total_chunks})` : "";
        cellText = isBlockStart ? `[${block.task_id}] ${block.title}${partBadge}` : `↳ ${block.task_id}`;
      }

      const inspectData = encodeURIComponent(
        JSON.stringify({
          slotIdx,
          dayName: DAYS_VI[dayIdx],
          timeRange: `${startTime}–${endTime}`,
          rawState,
          fixedLabel: fixedLabelBySlot[slotIdx] || null,
          block: block || null,
        })
      );

      html += `
        <td
          onmouseenter="inspectSlot('${inspectData}')"
          onclick="inspectSlot('${inspectData}')"
          class="grid-cell py-1 px-1.5 border-r border-slate-200 truncate cursor-pointer text-[11px] font-medium ${cellClass}"
          title="Slot #${slotIdx} (${DAYS_VI[dayIdx]} ${startTime}-${endTime})">
          ${cellText}
        </td>`;
    }

    html += `</tr>`;
  }

  return html;
}

function inspectSlot(encoded) {
  try {
    const info = JSON.parse(decodeURIComponent(encoded));
    const contentEl = document.getElementById("inspectorContent");
    const badgeEl = document.getElementById("inspectorSlotBadge");
    if (badgeEl) badgeEl.textContent = `Slot #${info.slotIdx} (${info.dayName} ${info.timeRange})`;

    if (!contentEl) return;
    if (info.block) {
      const b = info.block;
      contentEl.innerHTML = `
        <span class="px-1.5 py-0.5 bg-emerald-600 text-white rounded font-bold mono text-[10px]">${b.block_id}</span>
        <strong class="text-white">${b.title}</strong>
        <span class="text-slate-300 mono">(${b.day} ${b.start_time}–${b.end_time}, ${b.duration_min}p, P${b.priority})</span>
        <span class="text-amber-300 font-medium">→ ${b.reason}</span>
      `;
    } else if (info.rawState === "SLEEP") {
      contentEl.innerHTML = `<span class="text-indigo-300 font-semibold">🌙 Slot Ngủ Bảo Vệ Cứng (SLEEP - H2):</span> <span>Hệ thống khóa cứng không cho phép xếp bài tập vào giờ ngủ.</span>`;
    } else if (info.rawState.startsWith("OCCUPIED")) {
      contentEl.innerHTML = `<span class="text-rose-400 font-semibold">🟥 Lịch Bận Cố Định (OCCUPIED - H1):</span> <span>${info.fixedLabel || info.rawState}</span>`;
    } else {
      contentEl.innerHTML = `<span class="text-emerald-400 font-semibold">⬜ Khe Thời Gian Trống (FREE):</span> <span>Sẵn sàng tiếp nhận công việc mới.</span>`;
    }
  } catch (e) {
    // ignore
  }
}

function renderPlacedBlocksTable(schedule) {
  const tbody = document.getElementById("placedBlocksTableBody");
  if (!tbody) return;
  const blocks = (schedule && schedule.blocks) || [];

  if (blocks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="py-4 text-center text-slate-400 italic">Chưa có khối công việc nào được xếp.</td></tr>`;
    return;
  }

  tbody.innerHTML = blocks
    .map(
      (b) => `
      <tr class="hover:bg-slate-50">
        <td class="py-1.5 px-2.5 font-bold mono text-indigo-700">${b.block_id}</td>
        <td class="py-1.5 px-2.5 font-semibold text-slate-800">${b.title}</td>
        <td class="py-1.5 px-2.5 mono text-slate-600">${b.chunk_index}/${b.total_chunks}</td>
        <td class="py-1.5 px-2.5 font-semibold text-emerald-700 mono">${b.day} ${b.start_time}–${b.end_time}</td>
        <td class="py-1.5 px-2.5 mono text-slate-500">[${b.start_slot}..${b.end_slot})</td>
        <td class="py-1.5 px-2.5 mono">${b.duration_min}p</td>
        <td class="py-1.5 px-2.5 mono text-slate-600">${b.deadline_str}</td>
        <td class="py-1.5 px-2.5 text-slate-600">${b.reason}</td>
      </tr>`
    )
    .join("");
}

// ============================================================================
// DUAL-ALGORITHM COMPARATIVE VIEW (SINGLE vs COMPARE)
// ============================================================================

async function switchWorkbenchMode(mode) {
  state.workbenchMode = mode;
  const btnSingle = document.getElementById("btnModeSingle");
  const btnCompare = document.getElementById("btnModeCompare");
  const singlePanel = document.getElementById("singleGridPanel");
  const comparePanel = document.getElementById("compareGridPanel");

  if (mode === "COMPARE") {
    btnCompare.className = "px-2.5 py-1 text-xs font-semibold rounded bg-emerald-600 text-white transition";
    btnSingle.className = "px-2.5 py-1 text-xs font-semibold rounded text-slate-300 hover:text-white transition";
    singlePanel.classList.add("hidden");
    comparePanel.classList.remove("hidden");
    await runDualComparison();
  } else {
    btnSingle.className = "px-2.5 py-1 text-xs font-semibold rounded bg-emerald-600 text-white transition";
    btnCompare.className = "px-2.5 py-1 text-xs font-semibold rounded text-slate-300 hover:text-white transition";
    comparePanel.classList.add("hidden");
    singlePanel.classList.remove("hidden");
    renderMainGrid();
  }
}

async function runDualComparison() {
  const algoLeft = document.getElementById("compareAlgoLeft")?.value || "GREEDY_EDF_FIRST_FIT";
  const algoRight = document.getElementById("compareAlgoRight")?.value || "GREEDY_LST_BEST_FIT";

  try {
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
    const left = data.left;
    const right = data.right;
    const c = data.comparison;

    document.getElementById("compareLeftHeader").textContent =
      `Trái: ${left.solver_used} (${left.execution_time_ms.toFixed(2)} ms | Phân mảnh: ${(left.summary.fragmentation_index * 100).toFixed(1)}%)`;
    document.getElementById("compareRightHeader").textContent =
      `Phải: ${right.solver_used} (${right.execution_time_ms.toFixed(2)} ms | Phân mảnh: ${(right.summary.fragmentation_index * 100).toFixed(1)}%)`;

    document.getElementById("compareMetricsBox").innerHTML = `
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div><span class="text-slate-500">Số phiên đặt khác vị trí:</span> <strong class="mono text-indigo-700">${c.different_block_placements} / ${c.total_chunks_compared} phiên</strong></div>
        <div><span class="text-slate-500">Đạt Deadline (Trái vs Phải):</span> <strong class="mono">${c.left_deadline_rate}% vs ${c.right_deadline_rate}%</strong></div>
        <div><span class="text-slate-500">Độ phân mảnh (Trái vs Phải):</span> <strong class="mono">${(c.left_fragmentation * 100).toFixed(1)}% vs ${(c.right_fragmentation * 100).toFixed(1)}%</strong></div>
        <div><span class="text-slate-500">Thời gian giải (Trái vs Phải):</span> <strong class="mono">${c.left_exec_ms.toFixed(2)}ms vs ${c.right_exec_ms.toFixed(2)}ms</strong></div>
      </div>
    `;

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
// TAB 3: DISRUPTION REPAIR (T04) & TASK OVERRUN SIMULATOR (T05)
// ============================================================================

async function runDisruptionRepair(mode) {
  const title = document.getElementById("inpDisruptTitle").value.trim() || "Sự kiện đột xuất";
  const day = document.getElementById("inpDisruptDay").value || "Monday";
  const start = document.getElementById("inpDisruptStart").value || "07:30";
  const end = document.getElementById("inpDisruptEnd").value || "09:30";

  try {
    const res = await fetch("/api/repair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
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

    // Also add disruption to fixed events for visual display
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

    const logBox = document.getElementById("repairLogPanel");
    logBox.classList.remove("hidden");
    logBox.innerHTML = `
      <div class="font-bold text-indigo-800">🛠️ Kết Quả Tái Lập Lịch (${rep.repair_mode})</div>
      <div class="grid grid-cols-2 gap-2 text-[11px] bg-slate-50 p-2 rounded border border-slate-200">
        <div>Độ ổn định ($S_{\\text{stability}}$): <strong class="mono text-emerald-700">${rep.stability_score.toFixed(1)}%</strong></div>
        <div>Số phiên bị dời chỗ: <strong class="mono text-indigo-700">${rep.moved_blocks_count} phiên</strong></div>
        <div>Số phiên bị đè trực tiếp: <strong class="mono">${rep.directly_hit_blocks}</strong></div>
        <div>Thời gian xử lý: <strong class="mono">${rep.execution_time_ms.toFixed(2)} ms</strong></div>
      </div>
      <div class="space-y-1 text-[11px]">
        ${(rep.changes || [])
          .filter((c) => c.status !== "UNCHANGED")
          .map(
            (c) =>
              `<div class="text-slate-700">• <strong>${c.block_id}</strong>: ${c.old_day} ${c.old_start_time}–${c.old_end_time} ➔ <strong class="text-blue-700">${c.new_day || "UNPLACED"} ${c.new_start_time || ""}–${c.new_end_time || ""}</strong></div>`
          )
          .join("")}
      </div>
    `;
  } catch (err) {
    console.error("Disruption repair error:", err);
  }
}

async function runDisruptionComparison() {
  const title = document.getElementById("inpDisruptTitle").value.trim() || "Sự kiện đột xuất";
  const day = document.getElementById("inpDisruptDay").value || "Monday";
  const start = document.getElementById("inpDisruptStart").value || "07:30";
  const end = document.getElementById("inpDisruptEnd").value || "09:30";

  try {
    const res = await fetch("/api/repair", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commitments: state.commitments,
        tasks: state.tasks,
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

    const logBox = document.getElementById("repairLogPanel");
    logBox.classList.remove("hidden");
    logBox.innerHTML = `
      <div class="font-bold text-indigo-900">⚖️ Đối Chứng T04: Local Repair (M4) vs Full Rebuild</div>
      <table class="w-full text-[11px] border-collapse mt-1">
        <thead>
          <tr class="border-b border-slate-300 text-slate-600 text-left">
            <th class="py-1">Phương pháp</th>
            <th class="py-1">Độ ổn định ($S_{\\text{stability}}$)</th>
            <th class="py-1">Số Block bị xáo trộn</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-b border-slate-100 text-emerald-800 font-semibold">
            <td class="py-1">1. Local Insertion (M4)</td>
            <td class="py-1 mono">${cmp.local_stability_pct.toFixed(1)}%</td>
            <td class="py-1 mono">${cmp.local_moved_blocks} blocks (Chỉ dời đúng block bị đè)</td>
          </tr>
          <tr class="text-rose-800">
            <td class="py-1">2. Full Greedy Rebuild</td>
            <td class="py-1 mono">${cmp.rebuild_stability_pct.toFixed(1)}%</td>
            <td class="py-1 mono">${cmp.rebuild_moved_blocks} blocks (Hiệu ứng Domino)</td>
          </tr>
        </tbody>
      </table>
    `;
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

    // Update task duration in local state
    const tObj = state.tasks.find((t) => (t.task_id || t.id) === taskId);
    if (tObj) tObj.duration_min = data.new_duration_min;

    state.currentSchedule = data.after_schedule;
    syncAllLeftPanels();
    renderKpiCards(state.currentSchedule);
    renderOverloadBox(state.currentSchedule);
    renderMainGrid();
    renderPlacedBlocksTable(state.currentSchedule);

    const logBox = document.getElementById("repairLogPanel");
    logBox.classList.remove("hidden");
    logBox.innerHTML = `
      <div class="font-bold text-slate-800">⏱️ Kết Quả Mô Phỏng Lố Giờ (Kịch bản T05)</div>
      <div class="text-[11px] text-slate-700 space-y-1">
        <div>• Task <strong>${data.task_id}</strong> tăng thời lượng: <span class="mono">${data.old_duration_min}p ➔ <strong>${data.new_duration_min}p</strong> (+${extraMin}p)</span></div>
        <div>• Số phiên học phía sau bị trượt dây chuyền: <strong class="mono text-indigo-700">${data.shifted_blocks_count} phiên</strong></div>
      </div>
    `;
  } catch (err) {
    console.error("Overrun simulation error:", err);
  }
}

// ============================================================================
// 3X DETERMINISM CHECK & EXPORT / IMPORT
// ============================================================================

async function runDeterminismCheck() {
  const algorithm = document.getElementById("solverSelect")?.value || "GREEDY_EDF_FIRST_FIT";
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
    banner.classList.remove("hidden");
    textEl.innerHTML = `
      <strong>🔒 KIỂM CHỨNG TẤT ĐỊNH 3 LẦN LIÊN TIẾP (${data.runs}x Runs):</strong>
      Trạng thái = <span class="px-1.5 py-0.5 bg-emerald-600 text-white rounded font-bold mono">${data.is_deterministic ? "100% IDENTICAL PASS" : "FAILED"}</span> |
      SHA-256 = <span class="mono text-amber-300">${data.unique_hash}</span> |
      Thời gian 3 lần chạy = <span class="mono">[${data.latencies_ms.map((x) => x.toFixed(2) + "ms").join(", ")}]</span>
    `;
  } catch (err) {
    console.error("Determinism check error:", err);
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

function switchAppMode(mode) {
  state.appMode = mode;
  const btnStudent = document.getElementById("btnAppModeStudent");
  const btnLab = document.getElementById("btnAppModeLab");
  const studentLayout = document.getElementById("studentAppLayout");
  const labLayout = document.getElementById("labWorkbenchLayout");
  const studentActions = document.getElementById("studentHeaderActions");
  const labActions = document.getElementById("labHeaderActions");
  const modeBadge = document.getElementById("headerModeBadge");

  if (mode === "STUDENT") {
    if (btnStudent) btnStudent.className = "px-3.5 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 text-white shadow transition flex items-center gap-1.5";
    if (btnLab) btnLab.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg text-slate-300 hover:text-white transition flex items-center gap-1.5";
    studentLayout?.classList.remove("hidden");
    labLayout?.classList.add("hidden");
    studentActions?.classList.remove("hidden");
    labActions?.classList.add("hidden");
    if (modeBadge) {
      modeBadge.textContent = "STUDENT APP";
      modeBadge.className = "px-2 py-0.5 text-[10px] font-bold bg-indigo-500/30 text-indigo-300 border border-indigo-400/30 rounded-full mono uppercase";
    }
    renderStudentViews();
  } else {
    if (btnLab) btnLab.className = "px-3.5 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 text-white shadow transition flex items-center gap-1.5";
    if (btnStudent) btnStudent.className = "px-3.5 py-1.5 text-xs font-semibold rounded-lg text-slate-300 hover:text-white transition flex items-center gap-1.5";
    labLayout?.classList.remove("hidden");
    studentLayout?.classList.add("hidden");
    labActions?.classList.remove("hidden");
    studentActions?.classList.add("hidden");
    if (modeBadge) {
      modeBadge.textContent = "LAB BENCHMARK";
      modeBadge.className = "px-2 py-0.5 text-[10px] font-bold bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 rounded-full mono uppercase";
    }
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
}

function renderStudentViews() {
  renderStudentSummary();
  if (state.studentView === "WEEK") {
    renderStudentWeekCalendar();
  } else if (state.studentView === "TODAY") {
    renderStudentTodayView();
  } else if (state.studentView === "TASKS") {
    renderStudentTaskQueue();
  }
}

function renderStudentSummary() {
  const summary = state.currentSchedule?.summary;
  const tasksCount = state.tasks?.length || 0;
  const blocksCount = state.currentSchedule?.blocks?.length || 0;
  const totalMin = (state.currentSchedule?.blocks || []).reduce((acc, b) => acc + (b.duration_min || 0), 0);
  const totalHours = (totalMin / 60).toFixed(1);

  const elTasks = document.getElementById("stSummaryTasks");
  const elHours = document.getElementById("stSummaryHours");
  const elDeadline = document.getElementById("stSummaryDeadline");
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
    if (elViolations) {
      const v = summary.hard_constraint_violations ?? 0;
      elViolations.textContent = v === 0 ? "🛡️ 0 vi phạm (H1–H5)" : `⚠️ ${v} vi phạm`;
      elViolations.className = v === 0
        ? "px-2.5 py-1 text-xs font-semibold bg-slate-100 text-slate-700 rounded-full border border-slate-200"
        : "px-2.5 py-1 text-xs font-semibold bg-rose-100 text-rose-800 rounded-full border border-rose-300";
    }
  }
}

function renderStudentWeekCalendar() {
  if (!state.currentSchedule) return;

  for (let d = 0; d < 7; d++) {
    const dayName = DAYS_EN[d];
    const container = document.getElementById(`stDayCards_${d}`);
    const hoursEl = document.getElementById(`stDayHours_${d}`);
    if (!container) continue;

    // 1. Collect fixed events
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
          start_slot: d * 96 + Math.floor((parseInt(ev.start_time.split(":")[0]) * 60 + parseInt(ev.start_time.split(":")[1])) / 15),
        });
      }
    }

    // 2. Collect scheduled blocks
    const dayBlocks = [];
    let dayStudyMin = 0;
    for (const b of state.currentSchedule.blocks || []) {
      if (b.day === dayName) {
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

    // Combine and sort chronologically
    const allEvents = [...dayFixed, ...dayBlocks].sort((a, b) => a.start_slot - b.start_slot);

    if (allEvents.length === 0) {
      container.innerHTML = `
        <div class="h-full flex flex-col items-center justify-center py-10 text-center text-slate-400">
          <span class="text-2xl mb-1">🌿</span>
          <span class="text-[11px] font-medium">Trống lịch cả ngày</span>
          <span class="text-[10px] text-slate-400">Nghỉ ngơi hoặc tự ôn tập</span>
        </div>`;
      continue;
    }

    let html = "";
    for (const ev of allEvents) {
      if (ev.type === "FIXED") {
        if (ev.category === "MEAL") {
          html += `
            <div class="p-2 rounded-xl bg-amber-50 border border-amber-200/70 text-amber-900 shadow-sm transition hover:shadow">
              <div class="flex items-center justify-between text-[10px] text-amber-700 font-semibold mb-0.5">
                <span>🍽️ ĂN & NGHỈ</span>
                <span class="mono">${ev.start_time} - ${ev.end_time}</span>
              </div>
              <div class="font-bold text-xs text-amber-950">${ev.title}</div>
            </div>`;
        } else {
          html += `
            <div class="p-2.5 rounded-xl bg-slate-100 border border-slate-200 text-slate-800 shadow-sm transition hover:shadow">
              <div class="flex items-center justify-between text-[10px] text-slate-500 font-semibold mb-1">
                <span class="flex items-center gap-1">🔒 LỚP HỌC / CỐ ĐỊNH</span>
                <span class="mono font-bold text-slate-700">${ev.start_time} - ${ev.end_time}</span>
              </div>
              <div class="font-bold text-xs text-slate-900">${ev.title}</div>
            </div>`;
        }
      } else {
        const b = ev.block;
        const isPinned = state.pinnedBlocks.has(b.block_id);
        const isDone = state.doneBlocks.has(b.block_id);

        let cardClass = "bg-indigo-50/90 border border-indigo-200/90 text-indigo-950";
        if (isPinned) cardClass = "bg-amber-50 border-2 border-amber-400 text-amber-950";
        if (isDone) cardClass = "bg-slate-50 border border-slate-200 text-slate-400 line-through opacity-60";

        html += `
          <div class="p-2.5 rounded-xl ${cardClass} shadow-sm transition hover:shadow-md flex flex-col justify-between group">
            <div>
              <div class="flex items-center justify-between text-[10px] font-semibold mb-1">
                <span class="mono px-1.5 py-0.5 bg-white/70 rounded text-indigo-800 font-bold">${b.start_time} - ${b.end_time} (${b.duration_min}p)</span>
                <span class="px-1.5 py-0.5 rounded font-bold ${b.priority >= 4 ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700'}">P${b.priority}</span>
              </div>
              <div class="font-bold text-xs leading-snug mb-1 text-slate-900">
                ${isPinned ? '📌 ' : ''}${isDone ? '✓ ' : ''}${b.title}
                ${b.total_chunks > 1 ? `<span class="text-[10px] text-indigo-600 font-normal">(${b.chunk_index}/${b.total_chunks})</span>` : ''}
              </div>
              ${b.deadline_str ? `<div class="text-[10px] text-slate-500 mb-1.5 flex items-center gap-1"><span>🎯 Hạn:</span> <span class="font-medium">${b.deadline_str}</span></div>` : ''}
            </div>

            <!-- Action Buttons on card -->
            <div class="flex items-center justify-between pt-1 border-t border-slate-200/50 text-[10px] gap-1">
              <button onclick="togglePinBlock('${b.block_id}')" class="px-1.5 py-0.5 rounded ${isPinned ? 'bg-amber-500 text-white font-bold' : 'bg-white hover:bg-amber-100 text-amber-800 border border-amber-200'} transition flex items-center gap-0.5" title="${isPinned ? 'Bỏ ghim' : 'Ghim cố định không cho dời'}">
                <span>📌</span> ${isPinned ? 'Đã ghim' : 'Ghim'}
              </button>
              <button onclick="toggleDoneBlock('${b.block_id}')" class="px-1.5 py-0.5 rounded ${isDone ? 'bg-emerald-600 text-white font-bold' : 'bg-white hover:bg-emerald-100 text-emerald-800 border border-emerald-200'} transition flex items-center gap-0.5" title="${isDone ? 'Đánh dấu chưa xong' : 'Đánh dấu đã xong'}">
                <span>✓</span> ${isDone ? 'Xong' : 'Làm xong'}
              </button>
              <button onclick="openWhyHereModal('${b.block_id}')" class="px-1.5 py-0.5 rounded bg-white hover:bg-indigo-100 text-indigo-800 border border-indigo-200 transition font-medium" title="Xem lý do thuật toán chọn khung giờ này">
                💡 Tại sao?
              </button>
            </div>
          </div>`;
      }
    }

    container.innerHTML = html;
  }
}

function renderStudentTodayView() {
  const container = document.getElementById("stTodayTimelineContainer");
  const heroContainer = document.getElementById("stTodayHeroContainer");
  const pillsContainer = document.getElementById("stTodayDayPills");
  if (!container || !state.currentSchedule) return;

  // Render Day Pills
  if (pillsContainer) {
    pillsContainer.innerHTML = DAYS_EN.map((day, idx) => {
      const isAct = day === state.todayDay;
      return `
        <button onclick="setTodayDay('${day}')" class="px-3 py-1 text-xs font-bold rounded-lg transition ${
        isAct ? 'bg-indigo-600 text-white shadow' : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
      }">
          ${DAYS_VI[idx]} (${day.slice(0, 3)})
        </button>`;
    }).join("");
  }

  const dayIndex = DAYS_EN.indexOf(state.todayDay);

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
        start_slot: dayIndex * 96 + Math.floor((parseInt(ev.start_time.split(":")[0]) * 60 + parseInt(ev.start_time.split(":")[1])) / 15),
      });
    }
  }

  const todayBlocks = [];
  for (const b of state.currentSchedule.blocks || []) {
    if (b.day === state.todayDay) {
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

  const allEvents = [...todayFixed, ...todayBlocks].sort((a, b) => a.start_slot - b.start_slot);

  // Find next pending study block for hero card
  const nextStudy = todayBlocks.find((x) => !state.doneBlocks.has(x.block.block_id)) || todayBlocks[0];

  if (heroContainer) {
    if (nextStudy) {
      const b = nextStudy.block;
      const isDone = state.doneBlocks.has(b.block_id);
      const isPinned = state.pinnedBlocks.has(b.block_id);

      heroContainer.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div class="flex items-center gap-2 mb-2">
              <span class="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 text-xs font-bold uppercase tracking-wider">🎯 VIỆC CẦN TẬP TRUNG TIẾP THEO</span>
              <span class="text-xs text-indigo-200 mono font-semibold">${state.todayDay} Lúc ${b.start_time} – ${b.end_time} (${b.duration_min} phút)</span>
            </div>
            <h2 class="text-xl sm:text-2xl font-bold text-white tracking-tight mb-1.5 flex items-center gap-2">
              ${isPinned ? '📌 ' : ''}${isDone ? '✓ ' : ''}${b.title}
              ${b.total_chunks > 1 ? `<span class="text-sm font-normal text-indigo-300">(Phiên ${b.chunk_index}/${b.total_chunks})</span>` : ''}
            </h2>
            <p class="text-xs text-indigo-200 max-w-2xl leading-relaxed">
              ${b.deadline_str ? `Hạn chót: <strong>${b.deadline_str}</strong> · ` : ''}Ưu tiên P${b.priority} · ${b.reason || 'Được xếp tự động vào khoảng thời gian trống khả dụng sớm nhất.'}
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <button onclick="toggleDoneBlock('${b.block_id}')" class="px-4 py-2 rounded-xl ${isDone ? 'bg-slate-700 text-slate-300' : 'bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold'} shadow-md transition flex items-center gap-1.5 text-xs">
              <span>✓</span> ${isDone ? 'Đánh dấu chưa xong' : 'Hoàn Thành Phiên Này'}
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
          <h2 class="text-lg font-bold text-white mb-1">🎉 Bạn Đã Hoàn Thành Toàn Bộ Phiên Học Hôm Nay!</h2>
          <p class="text-xs text-indigo-300">Không còn bài tập nào chưa làm trong ngày ${state.todayDay}. Hãy nghỉ ngơi hoặc xem trước bài cho ngày mai.</p>
        </div>`;
    }
  }

  // Render vertical timeline
  if (allEvents.length === 0) {
    container.innerHTML = `<div class="py-8 text-center text-slate-400 text-xs">Không có lịch trình nào được xếp trong ngày ${state.todayDay}.</div>`;
    return;
  }

  container.innerHTML = allEvents.map((ev) => {
    if (ev.type === "FIXED") {
      const isMeal = ev.category === "MEAL";
      return `
        <div class="flex items-start gap-3 p-3 rounded-xl ${isMeal ? 'bg-amber-50/70 border border-amber-200' : 'bg-slate-50 border border-slate-200'}">
          <div class="w-16 text-xs font-bold ${isMeal ? 'text-amber-800' : 'text-slate-600'} mono pt-0.5">${ev.start_time}</div>
          <div class="flex-1">
            <span class="text-[10px] font-bold uppercase tracking-wider ${isMeal ? 'text-amber-700' : 'text-slate-500'}">${isMeal ? '🍽️ Nghỉ & Ăn Trưa/Tối' : '🎓 Lịch Học Cố Định Trên Trường'}</span>
            <div class="text-xs font-bold text-slate-900">${ev.title} (${ev.start_time} – ${ev.end_time})</div>
          </div>
          <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-white text-slate-600 border border-slate-200">KHÓA CỨNG</span>
        </div>`;
    } else {
      const b = ev.block;
      const isDone = state.doneBlocks.has(b.block_id);
      const isPinned = state.pinnedBlocks.has(b.block_id);

      return `
        <div class="flex items-start gap-3 p-3.5 rounded-xl border transition ${
          isDone ? 'bg-slate-50 border-slate-200 opacity-60' : isPinned ? 'bg-amber-50/70 border-amber-300' : 'bg-indigo-50/60 border-indigo-200'
        }">
          <div class="w-16 text-xs font-bold text-indigo-900 mono pt-0.5">${b.start_time}</div>
          <input type="checkbox" ${isDone ? 'checked' : ''} onchange="toggleDoneBlock('${b.block_id}')" class="mt-1 w-4 h-4 text-indigo-600 rounded cursor-pointer" />
          <div class="flex-1">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="text-xs font-bold text-slate-900 ${isDone ? 'line-through text-slate-500' : ''}">${b.title}</span>
              ${b.total_chunks > 1 ? `<span class="text-[10px] font-medium text-indigo-600">(Phiên ${b.chunk_index}/${b.total_chunks})</span>` : ''}
              ${isPinned ? '<span class="text-[10px] px-1.5 py-0.2 bg-amber-200 text-amber-900 rounded font-bold">📌 ĐÃ GHIM</span>' : ''}
            </div>
            <div class="text-[11px] text-slate-500 flex flex-wrap items-center gap-2">
              <span>⏱️ ${b.duration_min} phút</span>
              <span>·</span>
              <span>🎯 ${b.deadline_str ? `Hạn: ${b.deadline_str}` : 'Habit'}</span>
              <span>·</span>
              <span class="text-indigo-700 font-medium">Ưu tiên P${b.priority}</span>
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

function renderStudentTaskQueue() {
  const tbody = document.getElementById("stTasksTableBody");
  if (!tbody) return;

  if (!state.tasks || state.tasks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400">Chưa có công việc nào. Bấm nút "+ Thêm Việc" để bắt đầu!</td></tr>`;
    return;
  }

  const placedIds = new Set((state.currentSchedule?.blocks || []).map((b) => b.task_id));

  tbody.innerHTML = state.tasks.map((t) => {
    const tid = t.task_id || t.id;
    const isPlaced = placedIds.has(tid);
    const bufferInfo = state.taskBufferMap.get(tid);

    return `
      <tr class="hover:bg-slate-50 transition">
        <td class="py-2.5 px-3 font-semibold text-slate-900 mono">${tid}</td>
        <td class="py-2.5 px-3 font-bold text-slate-900">${t.title}</td>
        <td class="py-2.5 px-3">
          <span class="font-semibold mono">${t.duration_min}p</span>
          ${bufferInfo ? `<span class="ml-1 text-[10px] text-indigo-600 font-semibold bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200">🛡️ +20%</span>` : ''}
        </td>
        <td class="py-2.5 px-3 text-slate-600">${t.deadline_day ? `${t.deadline_day} ${t.deadline_time || ''}` : 'Không hạn chót'}</td>
        <td class="py-2.5 px-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold ${t.priority >= 4 ? 'bg-indigo-100 text-indigo-800' : 'bg-slate-100 text-slate-700'}">P${t.priority}</span></td>
        <td class="py-2.5 px-3">
          ${isPlaced
            ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">✓ ĐÃ XẾP LỊCH</span>`
            : `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">⚠️ CHƯA XẾP ĐƯỢC</span>`
          }
        </td>
        <td class="py-2.5 px-3 text-right">
          <button onclick="deleteStudentTask('${tid}')" class="text-slate-400 hover:text-rose-600 px-2 py-1 font-bold text-xs" title="Xóa task">✕ Xóa</button>
        </td>
      </tr>`;
  }).join("");
}

// Student Task Modal controls
function openStudentTaskModal() {
  document.getElementById("stTaskModal")?.classList.remove("hidden");
  document.getElementById("stInpTitle")?.focus();
  updateStBufferPreview();
}

function closeStudentTaskModal() {
  document.getElementById("stTaskModal")?.classList.add("hidden");
}

function setStDuration(val) {
  const inp = document.getElementById("stInpDuration");
  if (inp) inp.value = val;
  updateStBufferPreview();
}

function updateStBufferPreview() {
  const raw = parseInt(document.getElementById("stInpDuration")?.value || "60", 10);
  const isBuffer = document.getElementById("stInpBuffer")?.checked ?? true;
  const durPreview = document.getElementById("stDurationPreview");
  const txtPreview = document.getElementById("stBufferPreviewText");

  if (durPreview) durPreview.textContent = `${raw} phút`;

  if (isBuffer) {
    const rawBuffered = Math.ceil(raw * 1.2);
    const planned = Math.ceil(rawBuffered / 15) * 15;
    if (txtPreview) {
      txtPreview.innerHTML = `Thời lượng xếp lịch: <strong>${raw}p → ${rawBuffered}p (~${planned}p)</strong> (Thêm 20% đệm an toàn chống vỡ kế hoạch).`;
    }
  } else {
    if (txtPreview) {
      txtPreview.innerHTML = `Thời lượng xếp lịch: <strong>${raw}p</strong> (Không thêm thời gian đệm).`;
    }
  }
}

async function saveStudentTask() {
  const title = document.getElementById("stInpTitle")?.value.trim() || "Bài tập mới";
  const rawDur = parseInt(document.getElementById("stInpDuration")?.value || "60", 10);
  const isBuffer = document.getElementById("stInpBuffer")?.checked ?? true;
  const deadlineDay = document.getElementById("stInpDeadlineDay")?.value || null;
  const deadlineTime = document.getElementById("stInpDeadlineTime")?.value || "23:59";
  const priority = parseInt(document.getElementById("stInpPriority")?.value || "3", 10);
  const isSplittable = document.getElementById("stInpSplittable")?.checked ?? true;
  const dependsOnStr = document.getElementById("stInpDependsOn")?.value.trim() || "";

  // Compute final planned duration with buffer
  let finalDur = rawDur;
  if (isBuffer) {
    finalDur = Math.ceil(Math.ceil(rawDur * 1.2) / 15) * 15;
  }

  const tid = `TASK_${Date.now().toString().slice(-4)}`;
  const dependsOn = dependsOnStr ? dependsOnStr.split(",").map((s) => s.trim()).filter(Boolean) : [];

  const newTask = {
    task_id: tid,
    title,
    duration_min: finalDur,
    deadline_day: deadlineDay,
    deadline_time: deadlineTime,
    priority,
    is_splittable: isSplittable,
    min_chunk_min: 45,
    max_chunk_min: 90,
    depends_on: dependsOn,
    category: deadlineDay ? "DEADLINE" : "HABIT",
  };

  if (isBuffer) {
    state.taskBufferMap.set(tid, { raw_min: rawDur, buffered_min: finalDur });
  }

  state.tasks.push(newTask);
  closeStudentTaskModal();

  // Reset modal fields
  const inpT = document.getElementById("stInpTitle");
  if (inpT) inpT.value = "";
  const inpD = document.getElementById("stInpDuration");
  if (inpD) inpD.value = "60";
  const inpDep = document.getElementById("stInpDependsOn");
  if (inpDep) inpDep.value = "";

  syncAllLeftPanels();
  await solveSchedule();
}

async function deleteStudentTask(tid) {
  state.tasks = state.tasks.filter((t) => (t.task_id || t.id) !== tid);
  state.taskBufferMap.delete(tid);
  syncAllLeftPanels();
  await solveSchedule();
}

// Pin & Done Block Handlers
async function togglePinBlock(blockId) {
  if (state.pinnedBlocks.has(blockId)) {
    state.pinnedBlocks.delete(blockId);
  } else {
    const block = (state.currentSchedule?.blocks || []).find((b) => b.block_id === blockId);
    if (block) {
      state.pinnedBlocks.set(blockId, block);
    }
  }
  await solveSchedule();
}

function toggleDoneBlock(blockId) {
  if (state.doneBlocks.has(blockId)) {
    state.doneBlocks.delete(blockId);
  } else {
    state.doneBlocks.add(blockId);
  }
  renderStudentViews();
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

  body.innerHTML = `
    <div class="p-3 bg-indigo-50 border border-indigo-200 rounded-xl space-y-1">
      <div class="font-bold text-sm text-indigo-950">${block.title} ${block.total_chunks > 1 ? `(Phiên ${block.chunk_index}/${block.total_chunks})` : ''}</div>
      <div class="text-xs text-indigo-800 font-semibold mono">📅 ${block.day}, ${block.start_time} – ${block.end_time} (${block.duration_min} phút)</div>
    </div>

    <div class="space-y-2 pt-1">
      <div class="font-bold text-slate-800 text-xs">Cơ sở toán học thuật toán chọn vị trí này:</div>
      <ul class="space-y-1.5 list-disc list-inside text-slate-600 text-xs">
        <li><strong>Thuật toán:</strong> Earliest Deadline First (EDF) + First-Fit.</li>
        <li><strong>Hạn chót:</strong> ${block.deadline_str || 'Linh hoạt'} (Độ ưu tiên: P${block.priority}).</li>
        <li><strong>Bảo toàn ràng buộc cứng H1 & H2:</strong> Khe thời gian hoàn toàn tự do, không xâm phạm giờ ngủ (23:30–06:30) hay lớp học.</li>
        ${block.total_chunks > 1 ? `<li><strong>Cắt nhỏ thông minh (Chunking):</strong> Được cắt thành phiên ${block.duration_min}p để vừa khe trống liên tục.</li>` : ''}
        <li><strong>Lý do cụ thể:</strong> ${block.reason || 'Đặt vào khe trống sớm nhất khả dụng trước hạn chót.'}</li>
      </ul>
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
