/**
 * Typed Fetch API Client for SmartSchedule Backend (V0 + UI v3 endpoints).
 */

async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errJson = await res.json();
      if (errJson?.detail) detail = typeof errJson.detail === "string" ? errJson.detail : JSON.stringify(errJson.detail);
    } catch {
      const txt = await res.text();
      if (txt) detail = txt.slice(0, 220);
    }
    throw new Error(detail);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res.text();
}

export const api = {
  getSolvers: () => request("/api/solvers"),
  getCatalog: () => request("/api/test-suites/catalog"),
  loadSuite: (source, id, seed = 42, horizonDays = null) =>
    request("/api/test-suites/load", {
      method: "POST",
      body: JSON.stringify({ source, id, seed, horizon_days: horizonDays }),
    }),
  getShowcaseList: () => request("/api/test-showcase"),
  getShowcaseCase: (index, refresh = false) => request(`/api/test-showcase/${index}${refresh ? "?refresh=true" : ""}`),

  plan: (payload) =>
    request("/api/plan", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  evaluate: (payload) =>
    request("/api/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  benchmarkAll: (payload) =>
    request("/api/benchmark-all", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  solverWeights: (payload) =>
    request("/api/solver-weights", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  validateMove: (payload) =>
    request("/api/validate-move", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  repair: (payload) =>
    request("/api/repair", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  overrun: (payload) =>
    request("/api/overrun", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  overloadPreview: (payload) =>
    request("/api/overload/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  naturalAdd: (payload) =>
    request("/api/tasks/natural-add", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  chatTurn: (payload) =>
    request("/api/chat/turn", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  sendChatTurn: (payload) =>
    request("/api/chat/turn", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  completeTask: (payload) =>
    request("/api/tasks/complete", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  deleteTask: (payload) =>
    request("/api/tasks/delete", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  upsertFixedEvent: (payload) =>
    request("/api/fixed-events/upsert", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  deleteFixedEvent: (payload) =>
    request("/api/fixed-events/delete", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  initRealWeek: (payload = {}) =>
    request("/api/workspace/init-real-week", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  adaptNextWeek: (payload = {}) =>
    request("/api/workspace/adapt-next-week", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  simulateMultiWeek: (payload = {}) =>
    request("/api/simulation/multi-week", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getCalibration: (workspaceId = "default") =>
    request(`/api/tasks/calibration?workspace_id=${encodeURIComponent(workspaceId)}`),

  importIcs: (content) =>
    request("/api/import/ics", {
      method: "POST",
      body: JSON.stringify(typeof content === "string" ? { content } : content),
    }),

  exportFile: async (fmt, payload) => {
    const res = await fetch(`/api/export/${encodeURIComponent(fmt)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`Export failed (${res.status})`);
    return res.blob();
  },

  loadState: (workspaceId = "default") =>
    request(`/api/state?workspace_id=${encodeURIComponent(workspaceId)}`),

  saveState: (stateData, workspaceId = "default") =>
    request("/api/state", {
      method: "PUT",
      body: JSON.stringify({ workspace_id: workspaceId, state: stateData }),
    }),

  deleteState: (workspaceId = "default") =>
    request(`/api/state?workspace_id=${encodeURIComponent(workspaceId)}`, {
      method: "DELETE",
    }),
};
