/**
 * Central Application State for SmartSchedule UI (Chat-First + Developer Mode).
 */

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
  theme: localStorage.getItem("smartschedule_theme") || "botanical", // botanical | light | dark
  inputTab: "tasks", // tasks | commitments | profile
  editingTaskId: null,
  editingFixedEventId: null,

  // Chat-First Assistant & Synchronized Calendar Copilot State
  chatMessages: [], // shared transcript across #viewChat and #calendarCopilotDrawer
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

export function buildApiPayload(algorithmOverride = null) {
  return {
    commitments: state.commitments,
    tasks: state.tasks,
    algorithm: algorithmOverride || state.activeSolver,
    pinned_blocks: state.pinnedBlocks,
  };
}
