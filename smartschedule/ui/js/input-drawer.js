/**
 * Unified 3-Tab Input Modal ("Thiết lập & Dữ liệu đầu vào"):
 *  - Tab 1 (Tasks): Parallel Manual Full Form + Optional Quick NL Fill (/api/tasks/natural-add)
 *  - Tab 2 (Commitments): Sleep Schedule + Fixed Events CRUD + Quick 3 Meals + .ics Import (/api/import/ics)
 *  - Tab 3 (Profile & Habits): Circadian Focus + Personal Habits CRUD + Horizon/Buffer + M7 Calibration
 */

import { api } from "./api.js";
import { invalidateSolverCaches, state } from "./state.js";
import {
  CATEGORY_LABELS,
  FOCUS_PROFILES,
  LOAD_LABELS,
  PRIORITY_LABELS,
  USER_LOAD_LABELS,
  WEEKDAYS_EN,
  WEEKDAYS_VI_SHORT,
  WINDOW_LABELS,
  addDays,
  computeBufferPreview,
  computeSleepHours,
  dateAndTimeToDeadlineDay,
  esc,
  fmtISODate,
  humanizeWeekdaysVi,
  parseWeekStartDate,
} from "./utils.js";

let icsPreviewData = null;

export function renderInputModal(modalRoot, callbacks) {
  const tab = state.inputTab || "tasks";
  const bodyEl = modalRoot.querySelector("#inputModalBody");
  const countTasks = state.tasks.length;
  const countFixed = (state.commitments.fixed_events || []).length;
  const countHabits = (state.commitments.personal_habits || []).length;

  modalRoot.querySelectorAll(".modal-tab").forEach((btn) => {
    const t = btn.getAttribute("data-input-tab");
    btn.classList.toggle("active", t === tab);
    if (t === "tasks") btn.textContent = `1. Công việc (${countTasks})`;
    if (t === "commitments") btn.textContent = `2. Lịch cố định & Ngủ (${countFixed})`;
    if (t === "profile") btn.textContent = `3. Nhịp sinh học & Thói quen (${countHabits})`;
  });

  if (tab === "tasks") {
    renderTasksTab(bodyEl, modalRoot, callbacks);
  } else if (tab === "commitments") {
    renderCommitmentsTab(bodyEl, modalRoot, callbacks);
  } else {
    renderProfileTab(bodyEl, modalRoot, callbacks);
  }
}

function renderTasksTab(bodyEl, modalRoot, callbacks) {
  const wsDate = parseWeekStartDate(state.commitments.planning_week_start);
  const horizonDays = Number(state.commitments.horizon_days || 7);
  const minDate = fmtISODate(wsDate);
  const maxDate = fmtISODate(addDays(wsDate, horizonDays - 1));
  const defaultDueDate = fmtISODate(addDays(wsDate, Math.min(3, horizonDays - 1)));

  const editing = state.editingTaskId ? state.tasks.find((t) => t.task_id === state.editingTaskId) : null;

  // Resolve editing date for Date Picker
  let editDateVal = defaultDueDate;
  let editTimeVal = "23:59";
  let editNoDeadline = false;
  if (editing) {
    if (!editing.deadline_day && !editing.due) {
      editNoDeadline = true;
    } else if (editing.due) {
      const m = String(editing.due).match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
      if (m) {
        editDateVal = m[1];
        editTimeVal = m[2];
      }
    } else if (editing.deadline_day) {
      const isNext = String(editing.deadline_day).toLowerCase().startsWith("next ");
      const dayClean = String(editing.deadline_day).replace(/^next\s+/i, "").trim();
      const dIdx = WEEKDAYS_EN.findIndex((w) => w.toLowerCase() === dayClean.toLowerCase());
      if (dIdx >= 0) editDateVal = fmtISODate(addDays(wsDate, dIdx + (isNext ? 7 : 0)));
      editTimeVal = editing.deadline_time || "23:59";
    }
  }

  let editStartDate = "";
  let editStartTime = "";
  if (editing?.start_after) {
    const mIso = String(editing.start_after).match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
    if (mIso) {
      editStartDate = mIso[1];
      editStartTime = mIso[2];
    }
  }

  const initDur = editing?.duration_min || 60;
  const initLoad = editing?.cognitive_load || 2;
  const initSplit = editing ? Boolean(editing.is_splittable) : true;
  const initRhythm = editing?.work_rhythm || "BALANCED";
  const initUseBuffer = editing ? String(editing.buffer_mode || "HABIT").toUpperCase() !== "NONE" : true;
  const prev = computeBufferPreview(initDur, initLoad, state.commitments);

  const otherTasks = state.tasks.filter((t) => !editing || t.task_id !== editing.task_id);
  const existingDeps = new Set(editing?.depends_on || []);

  const taskSummaryRows = state.tasks
    .map(
      (t) => `
      <div class="summary-row">
        <div style="min-width:0;">
          <strong>${esc(t.title)}</strong>
          <div class="mono" style="font-size:11px;color:var(--p-muted);">
            ${
              state.developerMode
                ? `${esc(t.task_id)} · ${t.duration_min}p · P${t.priority} · L${t.cognitive_load || 2} · ${esc(CATEGORY_LABELS[t.category] || t.category)}${
                    t.deadline_day ? ` · Hạn ${esc(t.deadline_day)} ${esc(t.deadline_time || "")}` : " · Linh hoạt"
                  }`
                : `${t.duration_min}p · Ưu tiên ${t.priority}/5 · ${esc(USER_LOAD_LABELS[t.cognitive_load || 2] || "Mức vừa")} · ${esc(
                    CATEGORY_LABELS[t.category] || t.category
                  )}${t.deadline_day ? ` · Hạn ${esc(humanizeWeekdaysVi(t.deadline_day))} ${esc(t.deadline_time || "")}` : " · Linh hoạt"}`
            }
          </div>
        </div>
        <div style="display:flex;gap:6px;flex-shrink:0;">
          <button type="button" class="btn btn-sm" data-edit-task="${esc(t.task_id)}">✏️ Sửa</button>
          <button type="button" class="btn btn-sm btn-danger" data-del-task="${esc(t.task_id)}">🗑️</button>
        </div>
      </div>`
    )
    .join("");

  bodyEl.innerHTML = `
    <!-- Cách B: Nhập nhanh AI (tùy chọn) -->
    <div class="nl-quick-box">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
        <strong style="font-size:12.5px;color:var(--p-accent);">Nhập nhanh bằng câu tự nhiên (tùy chọn — điền sẵn xuống biểu mẫu)</strong>
        <span style="font-size:11.5px;color:var(--p-muted);">Hoặc bỏ qua và tự điền thẳng bên dưới</span>
      </div>
      <div class="nl-quick-row">
        <input type="text" class="input" id="inpNlQuickPrompt" placeholder='VD: "Ôn Toán rời rạc 2 tiếng trước 21:00 thứ 5, ưu tiên cao, tập trung sâu"' />
        <button type="button" class="btn btn-primary" id="btnNlQuickFill">Điền vào biểu mẫu</button>
      </div>
      <div id="nlQuickFeedback" style="font-size:12px;color:var(--p-muted);display:none;"></div>
    </div>

    <!-- Cách A: Biểu mẫu đầy đủ mặc định mở sẵn -->
    <form id="frmTaskV3" style="display:flex;flex-direction:column;gap:14px;">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
        <h3>${editing ? `Đang sửa: ${esc(editing.title)}` : "Thêm công việc mới (4 trường cốt lõi)"}</h3>
        ${editing ? `<button type="button" class="btn btn-sm" id="btnCancelEditTask">Hủy sửa</button>` : ""}
      </div>

      <div class="form-grid-2">
        <div class="field">
          <label for="inpTaskTitle">Tên công việc *</label>
          <input type="text" id="inpTaskTitle" class="input" required placeholder="VD: Làm Lab 04 Cấu trúc dữ liệu" value="${esc(editing?.title || "")}" />
        </div>
        <div class="field">
          <label for="inpTaskDuration">Thời lượng dự kiến (phút, bội số 15p) *</label>
          <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
            <input type="number" id="inpTaskDuration" class="input mono" min="15" step="15" value="${initDur}" style="width:96px;" />
            <div class="pill-choices">
              ${[30, 45, 60, 90, 120]
                .map((m) => `<button type="button" class="pill-choice mono ${initDur === m ? "active" : ""}" data-dur-pill="${m}">${m}p</button>`)
                .join("")}
            </div>
          </div>
        </div>
      </div>

      <div class="form-grid-3">
        <div class="field">
          <label for="inpTaskDueDate">Ngày hạn chót (DD/MM/YYYY)</label>
          <input type="date" id="inpTaskDueDate" class="input mono" min="${minDate}" max="${maxDate}" value="${editDateVal}" ${editNoDeadline ? "disabled" : ""} />
          <label class="toggle-label" style="margin-top:4px;font-weight:400;">
            <input type="checkbox" id="chkTaskNoDeadline" ${editNoDeadline ? "checked" : ""} />
            <span>Không có hạn chót (việc linh hoạt)</span>
          </label>
        </div>
        <div class="field">
          <label for="inpTaskDueTime">Giờ hạn chót (HH:MM)</label>
          <input type="time" id="inpTaskDueTime" class="input mono" value="${editTimeVal}" ${editNoDeadline ? "disabled" : ""} />
        </div>
        <div class="field">
          <label for="inpTaskPriority">Độ ưu tiên & Phân loại</label>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
            <select id="inpTaskPriority" class="select">
              ${[5, 4, 3, 2, 1]
                .map((p) => `<option value="${p}" ${(editing?.priority || 3) === p ? "selected" : ""}>${PRIORITY_LABELS[p]}</option>`)
                .join("")}
            </select>
            <select id="inpTaskCategory" class="select">
              ${["EXAM", "PROJECT", "ASSIGNMENT", "LAB", "READING", "HABIT"]
                .map((c) => `<option value="${c}" ${(editing?.category || "ASSIGNMENT") === c ? "selected" : ""}>${CATEGORY_LABELS[c]}</option>`)
                .join("")}
            </select>
          </div>
        </div>
      </div>

      <!-- Tùy chọn nâng cao (đóng gọn mặc định) -->
      <details class="adv-details" ${editing ? "open" : ""}>
        <summary>Tùy chọn nâng cao (Độ nặng não, Khung giờ, Chia buổi, Phụ thuộc & Bộ đệm)</summary>
        <div style="display:flex;flex-direction:column;gap:12px;">
          <div class="form-grid-2">
            <div class="field">
              <label for="inpTaskLoad">${state.developerMode ? "Độ nặng đầu óc (cognitive_load)" : "Mức tập trung cần thiết"}</label>
              <select id="inpTaskLoad" class="select">
                ${[1, 2, 3]
                  .map((l) => `<option value="${l}" ${initLoad === l ? "selected" : ""}>${state.developerMode ? LOAD_LABELS[l] : USER_LOAD_LABELS[l]}</option>`)
                  .join("")}
              </select>
            </div>
            <div class="field">
              <label for="inpTaskWindow">${state.developerMode ? "Khung giờ muốn làm (preferred_window)" : "Khung giờ bạn muốn làm"}</label>
              <select id="inpTaskWindow" class="select">
                ${Object.entries(WINDOW_LABELS)
                  .map(([k, lbl]) => `<option value="${k}" ${(editing?.preferred_window || "ANYTIME") === k ? "selected" : ""}>${lbl}</option>`)
                  .join("")}
              </select>
            </div>
          </div>

          <div class="field">
            <label>${state.developerMode ? "Cách chia buổi học (Gộp gọn is_splittable + work_rhythm)" : "Cách chia buổi học"}</label>
            <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center;">
              <label class="toggle-label"><input type="radio" name="radSplitMode" value="single" ${!initSplit ? "checked" : ""} /> 🔒 Làm liền 1 buổi</label>
              <label class="toggle-label"><input type="radio" name="radSplitMode" value="split" ${initSplit ? "checked" : ""} /> ✂️ Chia nhiều phiên</label>
              <select id="inpTaskRhythm" class="select" style="width:auto;min-height:32px;${!initSplit ? "display:none;" : ""}">
                <option value="LIGHT" ${initRhythm === "LIGHT" ? "selected" : ""}>Nhẹ (30–45p)</option>
                <option value="BALANCED" ${initRhythm === "BALANCED" ? "selected" : ""}>Vừa (45–90p)</option>
                <option value="FLOW" ${initRhythm === "FLOW" ? "selected" : ""}>Sâu (60–120p)</option>
                <option value="CUSTOM" ${initRhythm === "CUSTOM" ? "selected" : ""}>Tùy chỉnh min–max</option>
              </select>
              <div id="customChunkInputs" style="display:${initSplit && initRhythm === "CUSTOM" ? "inline-flex" : "none"};gap:6px;align-items:center;">
                <input type="number" id="inpMinChunk" class="input mono" min="15" step="15" value="${editing?.min_chunk_min || 45}" style="width:72px;min-height:32px;" title="Min phút" />
                <span>–</span>
                <input type="number" id="inpMaxChunk" class="input mono" min="15" step="15" value="${editing?.max_chunk_min || 90}" style="width:72px;min-height:32px;" title="Max phút" />
                <span>p</span>
              </div>
            </div>
          </div>

          <div class="form-grid-2">
            <div class="field">
              <label>${state.developerMode ? "Không làm trước (start_after — Ngày & Giờ)" : "Thời điểm sớm nhất có thể bắt đầu"}</label>
              <div style="display:grid;grid-template-columns:1fr 110px;gap:6px;">
                <input type="date" id="inpStartAfterDate" class="input mono" min="${minDate}" max="${maxDate}" value="${editStartDate}" />
                <input type="time" id="inpStartAfterTime" class="input mono" value="${editStartTime}" />
              </div>
            </div>
            <div class="field">
              <label>Đệm phòng phát sinh cho riêng việc này</label>
              <label class="toggle-label" style="margin-top:6px;">
                <input type="checkbox" id="chkTaskBuffer" ${initUseBuffer ? "checked" : ""} />
                <span id="txtBufferPreview" class="mono" style="font-size:12px;">
                  ${initUseBuffer ? `${prev.raw}p gốc → ${prev.planned}p dự phòng (×${prev.mult})` : `${prev.raw}p gốc (Tắt đệm)`}
                </span>
              </label>
            </div>
          </div>

          <div class="field">
            <label>${state.developerMode ? "Phải làm sau công việc (depends_on — chọn theo tên)" : "Phải làm sau công việc khác"}</label>
            <div class="pill-choices" id="dependsOnChoices">
              ${
                otherTasks.length > 0
                  ? otherTasks
                      .map(
                        (ot) =>
                          `<label class="pill-choice" style="display:inline-flex;align-items:center;gap:5px;cursor:pointer;">
                            <input type="checkbox" name="chkDependsOn" value="${esc(ot.task_id)}" ${existingDeps.has(ot.task_id) ? "checked" : ""} />
                            <span>${esc(ot.title)}</span>
                          </label>`
                      )
                      .join("")
                  : `<span style="font-size:12px;color:var(--p-muted);">Chưa có công việc khác để chọn phụ thuộc.</span>`
              }
            </div>
          </div>
        </div>
      </details>

      <div style="display:flex;justify-content:flex-end;gap:8px;">
        <button type="submit" class="btn btn-primary">${editing ? "💾 Lưu thay đổi công việc" : "➕ Thêm công việc vào lịch"}</button>
      </div>
    </form>

    <!-- Tóm tắt danh sách đã nhập -->
    <div style="display:flex;flex-direction:column;gap:8px;padding-top:10px;border-top:1px solid var(--p-line);">
      <div style="display:flex;align-items:center;justify-content:space-between;">
        <strong>Danh sách công việc hiện hành (${state.tasks.length})</strong>
        <span class="mono" style="font-size:12px;color:var(--p-muted);">Tổng gốc: ${state.tasks.reduce((a, t) => a + Number(t.duration_min || 0), 0)}p</span>
      </div>
      <div class="summary-list">
        ${taskSummaryRows || `<div style="color:var(--p-muted);font-size:12.5px;padding:10px;">Chưa có công việc nào.</div>`}
      </div>
    </div>
  `;

  // Wire duration pills & buffer preview
  const durInput = bodyEl.querySelector("#inpTaskDuration");
  const loadSel = bodyEl.querySelector("#inpTaskLoad");
  const bufChk = bodyEl.querySelector("#chkTaskBuffer");
  const bufPreview = bodyEl.querySelector("#txtBufferPreview");

  const updatePreview = () => {
    const p = computeBufferPreview(durInput.value, loadSel.value, state.commitments);
    bufPreview.textContent = bufChk.checked
      ? `${p.raw}p gốc → ${p.planned}p dự phòng (×${p.mult})`
      : `${p.raw}p gốc (Tắt đệm)`;
  };
  durInput.addEventListener("input", updatePreview);
  loadSel.addEventListener("change", updatePreview);
  bufChk.addEventListener("change", updatePreview);

  bodyEl.querySelectorAll("[data-dur-pill]").forEach((pill) => {
    pill.addEventListener("click", () => {
      durInput.value = pill.getAttribute("data-dur-pill");
      bodyEl.querySelectorAll("[data-dur-pill]").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      updatePreview();
    });
  });

  // No deadline toggle
  bodyEl.querySelector("#chkTaskNoDeadline").addEventListener("change", (e) => {
    bodyEl.querySelector("#inpTaskDueDate").disabled = e.target.checked;
    bodyEl.querySelector("#inpTaskDueTime").disabled = e.target.checked;
  });

  // Split mode & rhythm
  const rhythmSel = bodyEl.querySelector("#inpTaskRhythm");
  const customChunkDiv = bodyEl.querySelector("#customChunkInputs");
  bodyEl.querySelectorAll('input[name="radSplitMode"]').forEach((rad) => {
    rad.addEventListener("change", () => {
      const isSplit = bodyEl.querySelector('input[name="radSplitMode"]:checked').value === "split";
      rhythmSel.style.display = isSplit ? "" : "none";
      customChunkDiv.style.display = isSplit && rhythmSel.value === "CUSTOM" ? "inline-flex" : "none";
    });
  });
  rhythmSel.addEventListener("change", () => {
    const isSplit = bodyEl.querySelector('input[name="radSplitMode"]:checked').value === "split";
    customChunkDiv.style.display = isSplit && rhythmSel.value === "CUSTOM" ? "inline-flex" : "none";
  });

  // Quick AI Fill (POST /api/tasks/natural-add, engine="auto")
  bodyEl.querySelector("#btnNlQuickFill").addEventListener("click", async () => {
    const prompt = bodyEl.querySelector("#inpNlQuickPrompt").value.trim();
    const fb = bodyEl.querySelector("#nlQuickFeedback");
    if (!prompt) return;
    fb.style.display = "block";
    fb.textContent = "Đang phân tích câu tự nhiên...";
    try {
      const res = await api.naturalAdd({
        prompt,
        now: state.commitments.now,
        existing_count: state.tasks.length,
        engine: "auto",
      });
      const draft = res.draft || res;
      if (draft.title) bodyEl.querySelector("#inpTaskTitle").value = draft.title;
      if (draft.duration_min) durInput.value = draft.duration_min;
      if (draft.priority) bodyEl.querySelector("#inpTaskPriority").value = String(draft.priority);
      if (draft.category && ["EXAM", "PROJECT", "ASSIGNMENT", "LAB", "READING", "HABIT"].includes(draft.category)) {
        bodyEl.querySelector("#inpTaskCategory").value = draft.category;
      }
      if (draft.cognitive_load) loadSel.value = String(draft.cognitive_load);
      if (draft.preferred_window) bodyEl.querySelector("#inpTaskWindow").value = draft.preferred_window;
      if (draft.deadline_day) {
        bodyEl.querySelector("#chkTaskNoDeadline").checked = false;
        bodyEl.querySelector("#inpTaskDueDate").disabled = false;
        bodyEl.querySelector("#inpTaskDueTime").disabled = false;
        const isNext = String(draft.deadline_day).toLowerCase().startsWith("next ");
        const cleanDay = String(draft.deadline_day).replace(/^next\s+/i, "").trim();
        const dIdx = WEEKDAYS_EN.findIndex((w) => w.toLowerCase() === cleanDay.toLowerCase());
        if (dIdx >= 0) bodyEl.querySelector("#inpTaskDueDate").value = fmtISODate(addDays(wsDate, dIdx + (isNext ? 7 : 0)));
        if (draft.deadline_time) bodyEl.querySelector("#inpTaskDueTime").value = draft.deadline_time;
      }
      updatePreview();
      fb.style.color = "var(--st-ok)";
      fb.textContent = `✔️ Đã điền tự động từ câu nhập (${res.engine_used || "auto"}). Bạn kiểm tra lại các ô bên dưới rồi bấm Thêm/Lưu.`;
    } catch (err) {
      fb.style.color = "var(--st-danger)";
      fb.textContent = `Không thể phân tích tự động: ${err.message}`;
    }
  });

  // Cancel editing
  bodyEl.querySelector("#btnCancelEditTask")?.addEventListener("click", () => {
    state.editingTaskId = null;
    renderInputModal(modalRoot, callbacks);
  });

  // Submit Task form
  bodyEl.querySelector("#frmTaskV3").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const title = bodyEl.querySelector("#inpTaskTitle").value.trim();
    if (!title) return;

    const rawDur = Math.max(15, Math.ceil((Number(durInput.value) || 60) / 15) * 15);
    const noDl = bodyEl.querySelector("#chkTaskNoDeadline").checked;
    const dueDate = bodyEl.querySelector("#inpTaskDueDate").value;
    const dueTime = bodyEl.querySelector("#inpTaskDueTime").value || "23:59";
    const isSplit = bodyEl.querySelector('input[name="radSplitMode"]:checked').value === "split";
    const rhythm = rhythmSel.value;
    const rhythmMap = { LIGHT: [30, 45], BALANCED: [45, 90], FLOW: [60, 120] };
    const [minC, maxC] =
      rhythm === "CUSTOM"
        ? [Math.max(15, Number(bodyEl.querySelector("#inpMinChunk").value) || 45), Math.max(15, Number(bodyEl.querySelector("#inpMaxChunk").value) || 90)]
        : rhythmMap[rhythm] || [45, 90];

    const saDate = bodyEl.querySelector("#inpStartAfterDate").value;
    const saTime = bodyEl.querySelector("#inpStartAfterTime").value || "00:00";
    const startAfter = saDate ? `${saDate}T${saTime}:00+07:00` : null;

    const deps = Array.from(bodyEl.querySelectorAll('input[name="chkDependsOn"]:checked')).map((el) => el.value);
    const taskId = editing ? editing.task_id : `T${Date.now().toString().slice(-5)}`;

    const newTask = {
      task_id: taskId,
      title,
      duration_min: rawDur,
      deadline_day: noDl ? null : dateAndTimeToDeadlineDay(dueDate, state.commitments.planning_week_start),
      deadline_time: noDl ? null : dueTime,
      due: noDl || !dueDate ? null : `${dueDate}T${dueTime}:00+07:00`,
      priority: Number(bodyEl.querySelector("#inpTaskPriority").value) || 3,
      category: bodyEl.querySelector("#inpTaskCategory").value || "ASSIGNMENT",
      cognitive_load: Number(loadSel.value) || 2,
      preferred_window: bodyEl.querySelector("#inpTaskWindow").value || "ANYTIME",
      is_splittable: isSplit,
      work_rhythm: isSplit ? rhythm : null,
      min_chunk_min: Math.min(minC, maxC),
      max_chunk_min: Math.max(minC, maxC),
      start_after: startAfter,
      depends_on: deps,
      buffer_mode: bufChk.checked ? state.commitments.buffer_mode || "HABIT" : "NONE",
    };

    if (editing) {
      const idx = state.tasks.findIndex((t) => t.task_id === editing.task_id);
      if (idx >= 0) state.tasks[idx] = newTask;
      state.editingTaskId = null;
    } else {
      state.tasks.push(newTask);
    }

    invalidateSolverCaches();
    renderInputModal(modalRoot, callbacks);
    callbacks.onDataMutated("Đã lưu công việc và cập nhật lịch.");
  });

  // Inline edit/delete
  bodyEl.querySelectorAll("[data-edit-task]").forEach((btn) =>
    btn.addEventListener("click", () => {
      state.editingTaskId = btn.getAttribute("data-edit-task");
      renderInputModal(modalRoot, callbacks);
    })
  );
  bodyEl.querySelectorAll("[data-del-task]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-del-task");
      state.tasks = state.tasks.filter((t) => t.task_id !== id);
      if (state.editingTaskId === id) state.editingTaskId = null;
      invalidateSolverCaches();
      renderInputModal(modalRoot, callbacks);
      callbacks.onDataMutated("Đã xóa công việc.");
    })
  );
}

function renderCommitmentsTab(bodyEl, modalRoot, callbacks) {
  const sleep = state.commitments.sleep_schedule || { daily_start_time: "23:30", daily_end_time: "06:30" };
  const sleepHours = computeSleepHours(sleep.daily_start_time, sleep.daily_end_time);
  const fixedList = state.commitments.fixed_events || [];

  const fixedRowsHtml = fixedList
    .map((ev) => {
      const daysStr = Array.isArray(ev.day_of_week) ? ev.day_of_week.join(", ") : ev.day_of_week;
      return `
        <div class="summary-row">
          <div>
            <strong>${esc(ev.title)}</strong>
            <div class="mono" style="font-size:11px;color:var(--p-muted);">
              ${esc(CATEGORY_LABELS[ev.category] || ev.category)} · ${esc(daysStr)} · ${esc(ev.start_time)}–${esc(ev.end_time)}
            </div>
          </div>
          <button type="button" class="btn btn-sm btn-danger" data-del-fixed="${esc(ev.event_id)}">🗑️</button>
        </div>`;
    })
    .join("");

  let icsPreviewHtml = "";
  if (icsPreviewData) {
    icsPreviewHtml = `
      <div class="card" style="padding:12px;background:var(--p-accent-soft);border-color:var(--p-accent-border);display:flex;flex-direction:column;gap:8px;">
        <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
          <strong>Xem trước tệp .ics: ${icsPreviewData.fixed_events.length} lịch cố định & ${icsPreviewData.tasks.length} bài tập/deadline</strong>
          <div style="display:flex;gap:6px;">
            <button type="button" class="btn btn-primary btn-sm" id="btnApplyIcsImport">✔️ Nạp tất cả vào lịch</button>
            <button type="button" class="btn btn-sm" id="btnDiscardIcs">Hủy</button>
          </div>
        </div>
        <div style="font-size:12px;color:var(--p-ink-soft);max-height:130px;overflow-y:auto;">
          ${icsPreviewData.fixed_events.map((e) => `<div>• [Lịch cố định] ${esc(e.title)} (${esc(Array.isArray(e.day_of_week) ? e.day_of_week.join(",") : e.day_of_week)} ${esc(e.start_time)}–${esc(e.end_time)})</div>`).join("")}
          ${icsPreviewData.tasks.map((t) => `<div>• [Deadline] ${esc(t.title)} (Hạn ${esc(t.deadline_day)} ${esc(t.deadline_time)})</div>`).join("")}
        </div>
      </div>`;
  }

  bodyEl.innerHTML = `
    <!-- 1. Giờ ngủ cố định -->
    <div class="card" style="padding:14px;display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
        <h3>🌙 Giờ ngủ cố định (Luật cứng H2)</h3>
        <span id="sleepHoursBadge" class="badge ${sleepHours < 6 ? "badge-danger" : "badge-ok"} mono">
          ${sleepHours} giờ / đêm ${sleepHours < 6 ? "· ⚠️ Dưới chuẩn tối thiểu 6 giờ!" : "· Đạt chuẩn H2"}
        </span>
      </div>
      <div class="form-grid-2">
        <div class="field">
          <label for="inpSleepStart">Giờ đi ngủ</label>
          <input type="time" id="inpSleepStart" class="input mono" value="${esc(sleep.daily_start_time)}" />
        </div>
        <div class="field">
          <label for="inpSleepEnd">Giờ thức dậy</label>
          <input type="time" id="inpSleepEnd" class="input mono" value="${esc(sleep.daily_end_time)}" />
        </div>
      </div>
    </div>

    <!-- 2. Thêm sự kiện cố định -->
    <form id="frmFixedEvent" class="card" style="padding:14px;display:flex;flex-direction:column;gap:12px;">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
        <h3>🏫 Thêm lịch cố định (Lớp học, Bữa ăn, Làm thêm, CLB)</h3>
        <button type="button" class="btn btn-sm" id="btnAddQuickMeals">+ Tạo nhanh 3 bữa ăn mẫu (Sáng / Trưa / Tối)</button>
      </div>
      <div class="form-grid-2">
        <div class="field">
          <label for="inpFixedTitle">Tên sự kiện *</label>
          <input type="text" id="inpFixedTitle" class="input" required placeholder="VD: Lý thuyết CTDL & Giải thuật" />
        </div>
        <div class="field">
          <label for="inpFixedCat">Phân loại</label>
          <select id="inpFixedCat" class="select">
            <option value="ACADEMIC_CLASS">Lớp học (ACADEMIC_CLASS)</option>
            <option value="MEAL">Bữa ăn (MEAL)</option>
            <option value="WORK">Làm thêm (WORK)</option>
            <option value="MEETING">Họp / CLB (MEETING)</option>
          </select>
        </div>
      </div>
      <div class="field">
        <label>Chọn các thứ lặp trong tuần *</label>
        <div class="pill-choices">
          ${WEEKDAYS_EN.map(
            (en, i) => `
            <label class="pill-choice" style="display:inline-flex;align-items:center;gap:5px;cursor:pointer;">
              <input type="checkbox" name="chkFixedDay" value="${en}" ${i === 0 ? "checked" : ""} />
              <span>${WEEKDAYS_VI_SHORT[i]}</span>
            </label>`
          ).join("")}
        </div>
      </div>
      <div class="form-grid-3">
        <div class="field">
          <label for="inpFixedStart">Từ giờ</label>
          <input type="time" id="inpFixedStart" class="input mono" value="08:00" required />
        </div>
        <div class="field">
          <label for="inpFixedEnd">Đến giờ</label>
          <input type="time" id="inpFixedEnd" class="input mono" value="10:30" required />
        </div>
        <div class="field" style="justify-content:flex-end;">
          <button type="submit" class="btn btn-primary" style="margin-top:auto;">➕ Thêm sự kiện cố định</button>
        </div>
      </div>
    </form>

    <!-- 3. Import .ics -->
    <div class="card" style="padding:14px;display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
        <div>
          <h3>📥 Nhập nhanh Thời khóa biểu / Moodle–Canvas từ tệp <code>.ics</code></h3>
          <p style="font-size:12px;color:var(--p-muted);margin-top:2px;">Chọn tệp <code>.ics</code> từ cổng sinh viên hoặc Google Calendar để xem trước và nạp trong 1 click.</p>
        </div>
        <label class="btn btn-sm" style="cursor:pointer;">
          <span>📂 Chọn tệp .ics</span>
          <input type="file" id="inpIcsFile" accept=".ics,text/calendar" style="display:none;" />
        </label>
      </div>
      ${icsPreviewHtml}
    </div>

    <!-- Danh sách sự kiện cố định hiện hành -->
    <div style="display:flex;flex-direction:column;gap:8px;">
      <strong>Danh sách lịch cố định hiện hành (${fixedList.length})</strong>
      <div class="summary-list">
        ${fixedRowsHtml || `<div style="color:var(--p-muted);font-size:12.5px;padding:10px;">Chưa có lịch cố định nào.</div>`}
      </div>
    </div>
  `;

  // Sleep change
  const updateSleep = () => {
    const s = bodyEl.querySelector("#inpSleepStart").value || "23:30";
    const e = bodyEl.querySelector("#inpSleepEnd").value || "06:30";
    state.commitments.sleep_schedule = { daily_start_time: s, daily_end_time: e, is_hard_lock: true };
    const hrs = computeSleepHours(s, e);
    const badge = bodyEl.querySelector("#sleepHoursBadge");
    badge.className = `badge ${hrs < 6 ? "badge-danger" : "badge-ok"} mono`;
    badge.textContent = `${hrs} giờ / đêm ${hrs < 6 ? "· ⚠️ Dưới chuẩn tối thiểu 6 giờ!" : "· Đạt chuẩn H2"}`;
    invalidateSolverCaches();
    callbacks.onDataMutated("Đã cập nhật giờ ngủ.");
  };
  bodyEl.querySelector("#inpSleepStart").addEventListener("change", updateSleep);
  bodyEl.querySelector("#inpSleepEnd").addEventListener("change", updateSleep);

  // Add fixed event
  bodyEl.querySelector("#frmFixedEvent").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const title = bodyEl.querySelector("#inpFixedTitle").value.trim();
    const days = Array.from(bodyEl.querySelectorAll('input[name="chkFixedDay"]:checked')).map((c) => c.value);
    const start_time = bodyEl.querySelector("#inpFixedStart").value;
    const end_time = bodyEl.querySelector("#inpFixedEnd").value;
    const category = bodyEl.querySelector("#inpFixedCat").value;
    if (!title || days.length === 0 || end_time <= start_time) {
      callbacks.onToast("Vui lòng nhập tên, chọn ít nhất 1 thứ và đảm bảo giờ kết thúc sau giờ bắt đầu.", "warn");
      return;
    }
    state.commitments.fixed_events = state.commitments.fixed_events || [];
    state.commitments.fixed_events.push({
      event_id: `FE_${Date.now().toString().slice(-5)}`,
      title,
      day_of_week: days.length === 1 ? days[0] : days,
      start_time,
      end_time,
      category,
    });
    invalidateSolverCaches();
    renderInputModal(modalRoot, callbacks);
    callbacks.onDataMutated("Đã thêm lịch cố định.");
  });

  // Quick 3 meals
  bodyEl.querySelector("#btnAddQuickMeals").addEventListener("click", () => {
    state.commitments.fixed_events = state.commitments.fixed_events || [];
    const existingIds = new Set(state.commitments.fixed_events.map((e) => e.event_id));
    const meals = [
      { event_id: "MEAL_BREAKFAST", title: "Bữa sáng", day_of_week: "ALL", start_time: "07:15", end_time: "07:45", category: "MEAL" },
      { event_id: "MEAL_LUNCH", title: "Bữa trưa", day_of_week: "ALL", start_time: "12:00", end_time: "12:45", category: "MEAL" },
      { event_id: "MEAL_DINNER", title: "Bữa tối", day_of_week: "ALL", start_time: "18:30", end_time: "19:15", category: "MEAL" },
    ];
    let added = 0;
    for (const m of meals) {
      if (!existingIds.has(m.event_id)) {
        state.commitments.fixed_events.push(m);
        added++;
      }
    }
    if (added > 0) {
      invalidateSolverCaches();
      renderInputModal(modalRoot, callbacks);
      callbacks.onDataMutated(`Đã thêm ${added} khung bữa ăn mẫu hằng ngày.`);
    } else {
      callbacks.onToast("3 bữa ăn mẫu đã có sẵn trong danh sách.", "info");
    }
  });

  // Delete fixed event
  bodyEl.querySelectorAll("[data-del-fixed]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-del-fixed");
      state.commitments.fixed_events = (state.commitments.fixed_events || []).filter((e) => e.event_id !== id);
      invalidateSolverCaches();
      renderInputModal(modalRoot, callbacks);
      callbacks.onDataMutated("Đã xóa sự kiện cố định.");
    })
  );

  // ICS File upload
  bodyEl.querySelector("#inpIcsFile").addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      icsPreviewData = await api.importIcs(text);
      renderInputModal(modalRoot, callbacks);
    } catch (err) {
      callbacks.onToast(`Lỗi đọc tệp .ics: ${err.message}`, "danger");
    }
  });

  bodyEl.querySelector("#btnApplyIcsImport")?.addEventListener("click", () => {
    if (!icsPreviewData) return;
    state.commitments.fixed_events = [...(state.commitments.fixed_events || []), ...(icsPreviewData.fixed_events || [])];
    state.tasks = [...state.tasks, ...(icsPreviewData.tasks || [])];
    icsPreviewData = null;
    invalidateSolverCaches();
    renderInputModal(modalRoot, callbacks);
    callbacks.onDataMutated("Đã nạp dữ liệu từ tệp .ics vào lịch.");
  });
  bodyEl.querySelector("#btnDiscardIcs")?.addEventListener("click", () => {
    icsPreviewData = null;
    renderInputModal(modalRoot, callbacks);
  });
}

function renderProfileTab(bodyEl, modalRoot, callbacks) {
  const focus = String(state.commitments.focus_preference || "BALANCED").toUpperCase();
  const bufMode = String(state.commitments.buffer_mode || "HABIT").toUpperCase();
  const estHabit = state.commitments.estimate_habit || "";
  const horizon = Number(state.commitments.horizon_days || 7);
  const wsDate = fmtISODate(parseWeekStartDate(state.commitments.planning_week_start));
  const nowMatch = String(state.commitments.now || "").match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
  const nowDateVal = nowMatch ? nowMatch[1] : wsDate;
  const nowTimeVal = nowMatch ? nowMatch[2] : "08:00";

  const habits = state.commitments.personal_habits || [];
  const cal = state.calibration;

  const habitRowsHtml = habits
    .map(
      (h) => `
      <div class="summary-row">
        <div>
          <strong>${esc(h.name)}</strong>
          <div class="mono" style="font-size:11px;color:var(--p-muted);">
            ${esc(WINDOW_LABELS[h.preferred_window] || h.preferred_window)} · ${h.frequency_per_week} buổi/tuần · ${h.duration_min}p/buổi
          </div>
        </div>
        <button type="button" class="btn btn-sm btn-danger" data-del-habit="${esc(h.habit_id)}">🗑️</button>
      </div>`
    )
    .join("");

  bodyEl.innerHTML = `
    <!-- 1. Nhịp sinh học -->
    <div class="card" style="padding:14px;display:flex;flex-direction:column;gap:10px;">
      <h3>🧠 Nhịp tỉnh táo cá nhân (focus_preference)</h3>
      <div class="form-grid-2">
        ${Object.entries(FOCUS_PROFILES)
          .map(
            ([k, info]) => `
            <label class="card interactive-card" style="padding:10px 12px;cursor:pointer;display:flex;align-items:flex-start;gap:10px;border-color:${focus === k ? "var(--p-accent)" : "var(--p-line)"};background:${focus === k ? "var(--p-accent-soft)" : "var(--p-card)"};">
              <input type="radio" name="radFocusPref" value="${k}" ${focus === k ? "checked" : ""} style="margin-top:3px;accent-color:var(--p-accent);" />
              <div>
                <strong>${esc(info.label)}</strong>
                <div style="font-size:12px;color:var(--p-muted);">${esc(info.peak)}</div>
              </div>
            </label>`
          )
          .join("")}
      </div>
    </div>

    <!-- 2. Cửa sổ & Bộ đệm -->
    <div class="card" style="padding:14px;display:flex;flex-direction:column;gap:12px;">
      <h3>📆 Cửa sổ lập lịch & Bộ đệm sai lệch thời gian</h3>
      <div class="form-grid-3">
        <div class="field">
          <label for="inpProfileHorizon">Độ dài lịch</label>
          <select id="inpProfileHorizon" class="select">
            <option value="7" ${horizon === 7 ? "selected" : ""}>7 ngày (1 tuần)</option>
            <option value="14" ${horizon === 14 ? "selected" : ""}>14 ngày (2 tuần)</option>
          </select>
        </div>
        <div class="field">
          <label for="inpProfileWeekStart">Ngày Thứ Hai đầu tuần</label>
          <input type="date" id="inpProfileWeekStart" class="input mono" value="${wsDate}" />
        </div>
        <div class="field">
          <label>Mốc hiện tại (NOW)</label>
          <div style="display:grid;grid-template-columns:1fr 94px;gap:6px;">
            <input type="date" id="inpProfileNowDate" class="input mono" value="${nowDateVal}" />
            <input type="time" id="inpProfileNowTime" class="input mono" value="${nowTimeVal}" />
          </div>
        </div>
      </div>

      <div class="form-grid-2">
        <div class="field">
          <label for="inpBufferStrategy">Chiến lược đệm phòng phát sinh</label>
          <select id="inpBufferStrategy" class="select">
            <option value="COGNITIVE_LOAD" ${bufMode === "COGNITIVE_LOAD" ? "selected" : ""}>Tự động theo độ nặng não (1.20x nhẹ / 1.35x nặng)</option>
            <option value="HABIT_OFTEN" ${bufMode === "HABIT" && estHabit === "OFTEN" ? "selected" : ""}>Theo thói quen: Hay ước lượng thiếu (+30%)</option>
            <option value="HABIT_SOMETIMES" ${bufMode === "HABIT" && estHabit === "SOMETIMES" ? "selected" : ""}>Theo thói quen: Thỉnh thoảng lố giờ (+15%)</option>
            <option value="HABIT_NONE" ${bufMode === "HABIT" && (!estHabit || estHabit === "RARELY") ? "selected" : ""}>Không dùng đệm (1.00x gốc)</option>
          </select>
        </div>
        <div class="field">
          <label>Hiệu chỉnh tự động từ lịch sử Check-in M7 (EWMA)</label>
          <div style="font-size:12px;padding:8px 10px;border-radius:var(--r-sm);background:var(--p-bg);border:1px solid var(--p-line);">
            ${
              cal && cal.ready_for_calibration
                ? `Đã ghi nhận <strong>${cal.sample_count}</strong> phiên · Tỷ lệ EWMA: <strong class="mono">${cal.ewma_ratio}x</strong> → Gợi ý <strong>α=${cal.recommended_alpha}</strong> (${cal.recommended_habit}).`
                : `Hiện có <strong>${cal?.sample_count || 0}/5</strong> phiên Check-in M7. Đạt ≥ 5 phiên sẽ tự đề xuất hệ số đệm α cá nhân.`
            }
          </div>
        </div>
      </div>
    </div>

    <!-- 3. Thói quen lặp (duy nhất 1 chỗ quản lý) -->
    <form id="frmAddHabit" class="card" style="padding:14px;display:flex;flex-direction:column;gap:10px;">
      <h3>🌱 Thói quen lặp hằng tuần (PersonalHabit)</h3>
      <div class="form-grid-3">
        <div class="field">
          <label for="inpHabitName">Tên thói quen *</label>
          <input type="text" id="inpHabitName" class="input" required placeholder="VD: Chạy bộ / Đọc sách" />
        </div>
        <div class="field">
          <label for="inpHabitWindow">Buổi ưu tiên</label>
          <select id="inpHabitWindow" class="select">
            <option value="MORNING">Sáng (06–12h)</option>
            <option value="AFTERNOON">Chiều (12–18h)</option>
            <option value="EVENING">Tối (18–23h)</option>
            <option value="ANYTIME">Linh hoạt</option>
          </select>
        </div>
        <div class="field">
          <label>Tần suất & Thời lượng</label>
          <div style="display:grid;grid-template-columns:1fr 1fr auto;gap:6px;">
            <input type="number" id="inpHabitFreq" class="input mono" min="1" max="7" value="3" title="Buổi/tuần" />
            <input type="number" id="inpHabitDur" class="input mono" min="15" step="15" value="30" title="Phút/buổi" />
            <button type="submit" class="btn btn-primary">➕</button>
          </div>
        </div>
      </div>
      <div class="summary-list">
        ${habitRowsHtml || `<div style="color:var(--p-muted);font-size:12.5px;padding:6px;">Chưa có thói quen lặp nào.</div>`}
      </div>
    </form>
  `;

  // Focus preference
  bodyEl.querySelectorAll('input[name="radFocusPref"]').forEach((rad) => {
    rad.addEventListener("change", () => {
      state.commitments.focus_preference = rad.value;
      invalidateSolverCaches();
      renderInputModal(modalRoot, callbacks);
      callbacks.onDataMutated(`Đã đổi nhịp sinh học sang ${FOCUS_PROFILES[rad.value].label}.`);
    });
  });

  // Horizon / Week start / Now / Buffer
  const saveTemporalAndBuffer = () => {
    state.commitments.horizon_days = Number(bodyEl.querySelector("#inpProfileHorizon").value) || 7;
    const ws = bodyEl.querySelector("#inpProfileWeekStart").value;
    if (ws) state.commitments.planning_week_start = `${ws}T00:00:00+07:00`;
    const nd = bodyEl.querySelector("#inpProfileNowDate").value;
    const nt = bodyEl.querySelector("#inpProfileNowTime").value || "08:00";
    if (nd) state.commitments.now = `${nd}T${nt}:00+07:00`;

    const strat = bodyEl.querySelector("#inpBufferStrategy").value;
    if (strat === "COGNITIVE_LOAD") {
      state.commitments.buffer_mode = "COGNITIVE_LOAD";
    } else if (strat === "HABIT_OFTEN") {
      state.commitments.buffer_mode = "HABIT";
      state.commitments.estimate_habit = "OFTEN";
    } else if (strat === "HABIT_SOMETIMES") {
      state.commitments.buffer_mode = "HABIT";
      state.commitments.estimate_habit = "SOMETIMES";
    } else {
      state.commitments.buffer_mode = "HABIT";
      state.commitments.estimate_habit = null;
    }
    invalidateSolverCaches();
    callbacks.onDataMutated("Đã cập nhật cấu hình cửa sổ & bộ đệm.");
  };

  ["#inpProfileHorizon", "#inpProfileWeekStart", "#inpProfileNowDate", "#inpProfileNowTime", "#inpBufferStrategy"].forEach((sel) =>
    bodyEl.querySelector(sel).addEventListener("change", saveTemporalAndBuffer)
  );

  // Add habit
  bodyEl.querySelector("#frmAddHabit").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const name = bodyEl.querySelector("#inpHabitName").value.trim();
    if (!name) return;
    state.commitments.personal_habits = state.commitments.personal_habits || [];
    state.commitments.personal_habits.push({
      habit_id: `HABIT_${Date.now().toString().slice(-4)}`,
      name,
      preferred_window: bodyEl.querySelector("#inpHabitWindow").value,
      frequency_per_week: Math.max(1, Math.min(7, Number(bodyEl.querySelector("#inpHabitFreq").value) || 3)),
      duration_min: Math.max(15, Math.ceil((Number(bodyEl.querySelector("#inpHabitDur").value) || 30) / 15) * 15),
      category: "HABIT",
      cognitive_load: 1,
    });
    invalidateSolverCaches();
    renderInputModal(modalRoot, callbacks);
    callbacks.onDataMutated("Đã thêm thói quen hằng tuần.");
  });

  bodyEl.querySelectorAll("[data-del-habit]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-del-habit");
      state.commitments.personal_habits = (state.commitments.personal_habits || []).filter((h) => h.habit_id !== id);
      invalidateSolverCaches();
      renderInputModal(modalRoot, callbacks);
      callbacks.onDataMutated("Đã xóa thói quen.");
    })
  );
}
