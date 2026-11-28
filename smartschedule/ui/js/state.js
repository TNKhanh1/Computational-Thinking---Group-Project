/**
 * Central Application State for SmartSchedule UI (Chat-First + Developer Mode).
 */

export const MAX_PERSISTED_CHAT_MESSAGES = 30;

function _chatStorageKey(workspaceId = "default") {
  return `smartschedule_chat_history_v1_${String(workspaceId || "default")}`;
}

function _safeLocalStorageGet(key) {
  try {
    if (typeof localStorage === "undefined") return null;
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function _safeLocalStorageSet(key, value) {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(key, value);
  } catch {
    // Ignore storage quota or private browsing errors
  }
}

function _safeLocalStorageRemove(key) {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.removeItem(key);
  } catch {
    // Ignore restricted storage errors
  }
}

/**
 * Trim and sanitize chat messages for workspace & F5 persistence (max 30 latest messages).
 */
export function trimChatMessages(messages, maxCount = MAX_PERSISTED_CHAT_MESSAGES) {
  if (!Array.isArray(messages)) return [];
  const limit = Math.max(1, Number(maxCount) || MAX_PERSISTED_CHAT_MESSAGES);
  return messages.slice(-limit).map((m) => {
    const clean = {
      id: String(m?.id || `msg_${Date.now()}`),
      role: m?.role === "user" ? "user" : "assistant",
      text: String(m?.text || ""),
    };
    if (Array.isArray(m?.quickChips) && m.quickChips.length) clean.quickChips = m.quickChips;
    if (Array.isArray(m?.postActions) && m.postActions.length) clean.postActions = m.postActions;
    if (m?.edgeCase) clean.edgeCase = m.edgeCase;
    if (m?.remainingEstimation) clean.remainingEstimation = m.remainingEstimation;
    if (m?.thinkingSummary) clean.thinkingSummary = m.thinkingSummary;
    if (m?.finalizedMessage) clean.finalizedMessage = String(m.finalizedMessage);
    if (m?.tracedTaskId) clean.tracedTaskId = m.tracedTaskId;
    if (Array.isArray(m?.attachments) && m.attachments.length) {
      clean.attachments = m.attachments.map((a) => ({
        filename: String(a?.filename || "file"),
        size: Number(a?.size || 0),
      }));
    }
    if (m?.icsImport) clean.icsImport = m.icsImport;
    if (m?.conflict) clean.conflict = m.conflict;
    if (m?.attachmentDigest) clean.attachmentDigest = m.attachmentDigest;
    if (m?.adaptation) clean.adaptation = m.adaptation;
    return clean;
  });
}

export function loadChatHistoryFromStorage(workspaceId = "default") {
  const raw = _safeLocalStorageGet(_chatStorageKey(workspaceId));
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return trimChatMessages(parsed, MAX_PERSISTED_CHAT_MESSAGES);
  } catch {
    return [];
  }
}

export function saveChatHistoryToStorage(messages, workspaceId = "default") {
  const trimmed = trimChatMessages(messages, MAX_PERSISTED_CHAT_MESSAGES);
  _safeLocalStorageSet(_chatStorageKey(workspaceId), JSON.stringify(trimmed));
  return trimmed;
}

export function clearChatHistoryStorage(workspaceId = "default") {
  _safeLocalStorageRemove(_chatStorageKey(workspaceId));
}

export const state = {
  // Active workspace data
  workspaceId: "default",
  suiteLabel: "Lịch trình của bạn",
  suiteMeta: null,
  commitments: {
    student_id: "STUDENT_01",
    planning_week_start: "2026-11-02T00:00:00+07:00",
    now: "2026-11-02T08:00:00+07:00",
    sleep_schedule: { daily_start_time: "23:30", daily_end_time: "06:30", is_hard_lock: true },
    fixed_events: [],
    estimate_habit: "SOMETIMES",
    focus_preference: "BALANCED",
    buffer_mode: "COGNITIVE_LOAD",
    alpha_light: 1.2,
    alpha_heavy: 1.35,
    horizon_days: 7,
    personal_habits: [],
  },
  tasks: [],
  pinnedBlocks: [],
  completedBlocks: {}, // block_id -> { actual_min, completed_at }
  disruptionPreset: null,
  overrunPreset: null,

  // Solvers & cached outputs (enables 0ms switching after benchmark-all)
  solvers: [
    { key: "EDF", label: "EDF", full_name: "Earliest Deadline First + First-Fit" },
    { key: "WSPT", label: "WSPT", full_name: "Weighted Shortest Processing Time" },
    { key: "LST", label: "LST", full_name: "Dynamic Least Slack Time" },
    { key: "SCORED_GREEDY", label: "SCORED_GREEDY", full_name: "Hyperbolic Urgency + Circadian" },
    { key: "BACKTRACK", label: "BACKTRACK", full_name: "Backtracking Branch & Bound" },
  ],
  activeSolver: "SCORED_GREEDY",
  schedulesBySolver: {}, // solver_key -> enriched schedule + evaluation
  currentSchedule: null,
  currentEvaluation: null,
  benchmarkData: null, // response from /api/benchmark-all
  weightsData: null, // response from /api/solver-weights
  catalog: null, // response from /api/test-suites/catalog
  calibration: null,

  // UI view, Left Taskbar Slider & Developer Mode
  activeView: "chat", // chat (default entry) | calendar | list | weights | benchmark | showcase
  leftSidebarOpen: true,
  copilotCollapsed: false,
  developerMode: false,
  devPanelOpen: false,
  theme: _safeLocalStorageGet("smartschedule_theme") || "botanical", // botanical | light | dark
  inputTab: "tasks", // tasks | commitments | profile
  editingTaskId: null,
  editingFixedEventId: null,

  // Chat-First Assistant & Synchronized Calendar Copilot State
  chatMessages: loadChatHistoryFromStorage("default"), // persisted across F5 (latest 30 msgs)
  pendingAttachments: [], // staged .txt/.md/.pdf files [{ filename, content, size }]
  pendingIcsImport: null, // latest parsed .ics preview awaiting apply
  chatModeHint: "AUTO", // AUTO | ADD_RECURRING | ADD_TASK | MODIFY_HIDDEN | ADJUST_DEADLINE
  pendingChatDraft: null,
  lastMutatedTaskId: null,
  chatBusy: false,
  lastScheduleDiff: {
    added: [],
    moved: [],
    finalizedAt: null,
    finalizedMessage: "",
  },
  edgeCaseBanner: null,

  // Test-suite picker inputs
  suitePicker: { regimeSeed: 42, regimeHorizon: "", fuzzSeed: 1001 },
  showcase: { list: null, cases: {}, errors: {}, rerunning: {}, loading: false, listError: null },

  // Calendar Scrubber & Display controls
  scrubberStartDay: 0,
  viewWeekOffset: 0, // weeks from planning_week_start being *viewed* (week nav never re-plans)
  visibleDaysCount: 7, // 1 | 3 | 5 | 7
  hideSleepHours: true,
  showEnergyBackdrop: true,
  showTechMetaOnBlocks: false,

  // List view controls
  listFilter: "all", // all | study | past | today | future | warning
  listSearch: "",
  listShowSleep: false,

  // Benchmark & Weights UI state
  expandedIceeSolvers: {},
  glossaryFilter: "",
  weightsGlossaryFilter: "",
  overloadPreview: null,

  // Focus timer state
  timer: {
    blockId: null,
    totalSec: 25 * 60,
    remainingSec: 25 * 60,
    running: false,
    intervalId: null,
  },
};

export function invalidateSolverCaches() {
  state.schedulesBySolver = {};
  state.benchmarkData = null;
  state.weightsData = null;
  state.overloadPreview = null;
}

export function serializeWorkspaceState(targetState = state) {
  const trimmedChat = trimChatMessages(targetState.chatMessages, MAX_PERSISTED_CHAT_MESSAGES);
  saveChatHistoryToStorage(trimmedChat, targetState.workspaceId);
  return {
    suiteLabel: targetState.suiteLabel,
    commitments: targetState.commitments,
    tasks: targetState.tasks,
    pinnedBlocks: targetState.pinnedBlocks,
    completedBlocks: targetState.completedBlocks,
    activeSolver: targetState.activeSolver,
    chatMessages: trimmedChat,
  };
}

export function hydrateWorkspaceState(savedObj, targetState = state) {
  if (!savedObj || typeof savedObj !== "object") return targetState;
  if (savedObj.commitments) targetState.commitments = savedObj.commitments;
  if (Array.isArray(savedObj.tasks)) targetState.tasks = savedObj.tasks;
  targetState.pinnedBlocks = savedObj.pinnedBlocks || savedObj.pinned_blocks || [];
  targetState.completedBlocks = savedObj.completedBlocks || {};
  targetState.activeSolver = savedObj.activeSolver || savedObj.algorithm || "SCORED_GREEDY";
  if (savedObj.suiteLabel) targetState.suiteLabel = savedObj.suiteLabel;

  if (Array.isArray(savedObj.chatMessages) && savedObj.chatMessages.length > 0) {
    targetState.chatMessages = trimChatMessages(savedObj.chatMessages, MAX_PERSISTED_CHAT_MESSAGES);
    saveChatHistoryToStorage(targetState.chatMessages, targetState.workspaceId);
  } else {
    const cached = loadChatHistoryFromStorage(targetState.workspaceId);
    if (cached.length > 0) {
      targetState.chatMessages = cached;
    }
  }
  return targetState;
}

export function buildApiPayload(algorithmOverride = null) {
  return {
    commitments: state.commitments,
    tasks: state.tasks,
    algorithm: algorithmOverride || state.activeSolver,
    pinned_blocks: state.pinnedBlocks,
  };
}
