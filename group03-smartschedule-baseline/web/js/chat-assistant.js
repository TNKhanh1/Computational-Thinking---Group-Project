/**
 * Conversational Scheduling Assistant (Main Spacious Chat View + Right Calendar Copilot).
 * Synchronizes state across #viewChat and #calendarCopilotDrawer in real time, supports
 * multi-turn slot filling, SHA-256 task keyword traceability, hidden criteria tuning,
 * remaining-time + habit buffer re-estimation, and Deadlock/Dense-Schedule edge cases.
 */

import { state } from "./state.js";
import { CATEGORY_LABELS, WINDOW_LABELS, computeBufferPreview, esc } from "./utils.js";

function _renderThinkingStage(thinkingSummary) {
  if (!state.developerMode || !thinkingSummary) return "";
  const pruned = Array.isArray(thinkingSummary.pruned_algorithms)
    ? thinkingSummary.pruned_algorithms.map((p) => (typeof p === "string" ? p : p?.key || "")).filter(Boolean).join(", ")
    : "EDF, WSPT, LST";
  const selected = thinkingSummary.selected_algorithm || state.activeSolver || "SCORED_GREEDY";

  return `
    <details class="chat-thinking-stage" open>
      <summary class="chat-thinking-summary">
        <span class="chat-thinking-title">💭 ${esc(thinkingSummary.headline_vi || "Quá trình suy nghĩ & chọn thuật toán")}</span>
        <span class="badge badge-info mono">${esc(selected)}</span>
      </summary>
      <div class="chat-thinking-body">
        <div class="chat-thinking-step">
          <strong>1. Đọc ngữ cảnh & tiêu chí ẩn:</strong>
          <span>${esc(thinkingSummary.context_summary_vi || "")}</span>
        </div>
        <div class="chat-thinking-step">
          <strong>2. Sàng lọc tập thuật toán:</strong>
          <span>${esc(thinkingSummary.algorithm_summary_vi || "")}</span>
        </div>
        <div class="chat-thinking-step">
          <strong>3. Kết quả thực thi:</strong>
          <span>${esc(thinkingSummary.outcome_summary_vi || "")}</span>
        </div>
        <div class="chat-thinking-pills mono">
          <span class="thinking-pill is-pruned" title="Trường hợp tốt nhất của nhóm này vẫn kém hơn trường hợp tệ nhất của nhóm có nhịp sinh học">Đã loại: ${esc(pruned)}</span>
          <span class="thinking-pill is-selected">Tối ưu: ${esc(selected)}</span>
        </div>
      </div>
    </details>`;
}

function _renderHiddenParamDebugCard(task) {
  if (!state.developerMode || !task) return "";
  const prev = computeBufferPreview(task.duration_min, task.cognitive_load || 2, state.commitments);
  const effectiveMult = task.buffer_mode === "NONE" ? 1.0 : Number(task.buffer_multiplier > 1 ? task.buffer_multiplier : prev.mult);
  const plannedMin = task.buffer_mode === "NONE" ? task.duration_min : Math.ceil((Number(task.duration_min || 60) * effectiveMult) / 15) * 15;
  const hashShort = task.trace_hash ? String(task.trace_hash).slice(0, 10) : "—";
  const splitTxt = task.is_splittable
    ? `Chia nhỏ (${task.work_rhythm || "BALANCED"}: ${task.min_chunk_min || 45}–${task.max_chunk_min || 90}p)`
    : "Giữ liền 1 khối (Atomic)";

  return `
    <div class="dev-hidden-card">
      <div class="dev-hidden-title">🛠️ Thông số ẩn của công việc</div>
      <div class="dev-hidden-grid mono">
        <span>SHA-256: <strong>${esc(hashShort)}</strong></span>
        <span>Nhịp sinh học: <strong>${esc(WINDOW_LABELS[task.preferred_window || "ANYTIME"] || task.preferred_window || "ANYTIME")}</strong></span>
        <span>Cường độ: <strong>L${task.cognitive_load || 2} · P${task.priority || 3}</strong></span>
        <span>Fallacy Buffer: <strong>${task.duration_min}p → ${plannedMin}p (×${effectiveMult.toFixed(2)})</strong></span>
        <span>Tách task: <strong>${esc(splitTxt)}</strong></span>
      </div>
    </div>`;
}

function _renderEdgeCaseCard(edgeCase) {
  if (!edgeCase) return "";
  const isDeadlock = edgeCase.type === "DEADLOCK";
  const cls = isDeadlock ? "chat-alert-danger" : "chat-alert-warn";
  const title = isDeadlock ? "🚨 Lịch bị kẹt / Trùng hạn chót" : "⚠️ Cảnh báo lịch trình dày đặc";
  const buttons = (edgeCase.suggestions || [])
    .map(
      (s, i) => `
      <button type="button"
              class="btn btn-sm ${i === 0 ? "btn-primary" : ""}"
              data-edge-action="${esc(s.action || "PROMPT")}"
              data-edge-prompt="${esc(s.prompt || "")}"
              data-edge-opt-id="${esc(s.option_id || "")}"
              data-edge-opt-code="${esc(s.option_code || "")}"
              data-edge-opt-task="${esc(s.target_task_id || "")}">
        ${esc(s.label)}
      </button>`
    )
    .join("");

  return `
    <div class="chat-alert-card ${cls}">
      <strong>${title}</strong>
      <p>${esc(edgeCase.message_vi)}</p>
      ${buttons ? `<div class="chat-chip-row">${buttons}</div>` : ""}
    </div>`;
}

function _renderMessageBubble(msg) {
  if (msg.role === "user") {
    return `
      <div class="chat-msg chat-msg-user">
        <div class="chat-bubble user">${esc(msg.text)}</div>
      </div>`;
  }

  const chipsHtml = (msg.quickChips || [])
    .map(
      (ch) => `
      <button type="button"
              class="chat-quick-chip"
              data-chat-chip-prompt="${esc(ch.prompt || ch.label)}"
              data-chat-chip-mode="${esc(ch.mode_hint || "")}">
        ${esc(ch.label)}
      </button>`
    )
    .join("");

  const postActionsHtml = (msg.postActions || [])
    .map((act) => {
      const isPrimary = act.action === "OPEN_CALENDAR";
      return `
        <button type="button"
                class="btn btn-sm ${isPrimary ? "btn-primary" : ""}"
                data-chat-post-action="${esc(act.action)}"
                data-chat-post-task="${esc(act.task_id || "")}">
          ${esc(act.label)}
        </button>`;
    })
    .join("");

  const remHtml = msg.remainingEstimation
    ? `<div class="chat-rem-box">
         <strong>⏳ Tính lại thời gian theo thói quen:</strong>
         <span>${esc(msg.remainingEstimation.remaining_raw_min)}p còn lại + ${esc(msg.remainingEstimation.extra_buffer_min)}p dự phòng (×${Number(msg.remainingEstimation.applied_alpha).toFixed(2)}) = <strong>${esc(msg.remainingEstimation.buffered_duration_min)}p</strong></span>
       </div>`
    : "";

  const finalizedHtml = msg.finalizedMessage
    ? `<div class="chat-finalized-pill">${esc(msg.finalizedMessage)}</div>`
    : "";

  const tracedTaskObj = msg.tracedTaskId
    ? (state.tasks || []).find((t) => t.task_id === msg.tracedTaskId)
    : null;

  return `
    <div class="chat-msg chat-msg-ai">
      <div class="chat-avatar" aria-hidden="true">AI</div>
      <div class="chat-bubble ai">
        ${_renderThinkingStage(msg.thinkingSummary)}
        ${finalizedHtml}
        <div class="chat-ai-text">${esc(msg.text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</div>
        ${remHtml}
        ${_renderEdgeCaseCard(msg.edgeCase)}
        ${_renderHiddenParamDebugCard(tracedTaskObj)}
        ${chipsHtml ? `<div class="chat-chip-row">${chipsHtml}</div>` : ""}
        ${postActionsHtml ? `<div class="chat-post-actions">${postActionsHtml}</div>` : ""}
      </div>
    </div>`;
}

function _renderSuggestionCards(compact = false) {
  return `
    <div class="chat-suggestions ${compact ? "is-compact" : ""}">
      <button type="button" class="chat-suggest-card ${state.chatModeHint === "ADD_RECURRING" ? "active" : ""}" data-suggest-mode="ADD_RECURRING">
        <div class="chat-suggest-icon">🔁</div>
        <div class="chat-suggest-copy">
          <strong>Thêm / Đổi lịch lặp hằng ngày</strong>
          <span>Lớp học, bữa ăn, giờ ngủ, tập thể dục lặp lại theo tuần</span>
        </div>
      </button>
      <button type="button" class="chat-suggest-card ${state.chatModeHint === "ADD_TASK" ? "active" : ""}" data-suggest-mode="ADD_TASK">
        <div class="chat-suggest-icon">📌</div>
        <div class="chat-suggest-copy">
          <strong>Thêm / Chỉnh 1 công việc riêng biệt</strong>
          <span>Bài tập, ôn thi, đồ án với thời gian bắt đầu – kết thúc hoặc hạn chót</span>
        </div>
      </button>
    </div>`;
}

function _renderChatSurface(container, { compact = false } = {}) {
  if (!container) return;
  const hasMessages = state.chatMessages.length > 0;
  const modeLabels = {
    AUTO: "Tự động hiểu",
    ADD_RECURRING: "🔁 Lịch lặp hằng ngày",
    ADD_TASK: "📌 Công việc riêng",
    MODIFY_HIDDEN: "🧠 Chỉnh tiêu chí ẩn",
    ADJUST_DEADLINE: "⏳ Đổi deadline",
  };
  const modePlaceholders = {
    AUTO: "VD: Làm bài tập môn Computational Thinking, từ 19h ngày thứ 3, tới 21h ngày thứ 5, cần thực hiện trong 2 tiếng...",
    ADD_RECURRING: "Nhập tên lịch lặp & khung giờ (VD: Tập gym từ 17:30 đến 18:30 thứ 2, 4, 6)...",
    ADD_TASK: "Nhập việc cần làm, khung giờ hoặc thời lượng & hạn chót (VD: Làm bài tập Giải tích 2 tiếng trước 21h thứ 5)...",
  };

  const heroHtml = !hasMessages && !compact
    ? `
      <div class="chat-empty-hero">
        <div class="chat-hero-badge">Trợ lý xếp lịch</div>
        <h1>Hôm nay bạn muốn sắp xếp lịch trình thế nào?</h1>
        <p>Nhắn tự nhiên việc cần làm cùng khung giờ (hoặc hạn chót). Nếu thiếu thông tin, mình sẽ hỏi lại ngắn gọn.</p>
        ${_renderSuggestionCards(false)}
      </div>`
    : "";

  const copilotHeaderHtml = compact
    ? `
      <div class="copilot-head">
        <div>
          <strong>Trợ lý tinh chỉnh trực tiếp</strong>
          <div style="font-size:11.5px;color:var(--p-muted);">Nhắn để dời, thêm hoặc gỡ kẹt ngay trên lịch</div>
        </div>
        <button type="button" class="btn btn-sm btn-ghost" id="btnToggleCopilotDrawer" title="Thu gọn trợ lý để mở rộng lịch trình" aria-label="Thu gọn trợ lý">⇥</button>
      </div>
      ${!hasMessages ? _renderSuggestionCards(true) : ""}`
    : "";

  const streamHtml = hasMessages
    ? `<div class="chat-messages-stream" data-chat-stream>${state.chatMessages.map(_renderMessageBubble).join("")}</div>`
    : compact
      ? `<div class="chat-messages-stream is-empty-compact" data-chat-stream>
           <div class="chat-compact-hint">Chọn một gợi ý ở trên hoặc gõ yêu cầu chỉnh sửa lịch vào ô bên dưới nhé.</div>
         </div>`
      : "";

  const activeModeBadge = state.chatModeHint !== "AUTO"
    ? `<div class="chat-mode-pill">
         <span>Chế độ: <strong>${esc(modeLabels[state.chatModeHint] || state.chatModeHint)}</strong></span>
         <button type="button" data-clear-chat-mode aria-label="Bỏ chế độ">✕</button>
       </div>`
    : "";

  const pendingBadge = state.pendingChatDraft
    ? `<div class="chat-mode-pill is-pending">
         <span>Đang bổ sung thông tin cho: <strong>${esc(state.pendingChatDraft.title || "lịch mới")}</strong></span>
         <button type="button" data-cancel-pending-draft aria-label="Hủy thao tác đang dở">✕ Hủy</button>
       </div>`
    : "";

  container.innerHTML = `
    <div class="chat-surface ${compact ? "is-copilot" : "is-full"}">
      ${copilotHeaderHtml}
      <div class="chat-scroll-area" data-chat-scroll>
        ${heroHtml}
        ${streamHtml}
      </div>
      <div class="chat-composer-wrap">
        ${activeModeBadge || pendingBadge ? `<div class="chat-status-pills">${activeModeBadge}${pendingBadge}</div>` : ""}
        <form class="chat-composer-form" data-chat-form>
          <textarea class="chat-input"
                    data-chat-input
                    rows="${compact ? 2 : 1}"
                    placeholder="${esc(modePlaceholders[state.chatModeHint] || modePlaceholders.AUTO)}"
                    ${state.chatBusy ? "disabled" : ""}></textarea>
          <button type="submit" class="btn btn-primary chat-send-btn" ${state.chatBusy ? "disabled" : ""}>
            ${state.chatBusy ? "Đang xếp..." : "Gửi"}
          </button>
        </form>
      </div>
    </div>`;

  const scrollBox = container.querySelector("[data-chat-scroll]");
  if (scrollBox) scrollBox.scrollTop = scrollBox.scrollHeight;
}

function _wireChatContainer(container, callbacks) {
  if (!container) return;
  const inputEl = container.querySelector("[data-chat-input]");
  const formEl = container.querySelector("[data-chat-form]");

  container.querySelector("#btnToggleCopilotDrawer")?.addEventListener("click", () => {
    callbacks.onToggleCopilotDrawer?.();
  });

  formEl?.addEventListener("submit", (e) => {
    e.preventDefault();
    const val = inputEl?.value.trim();
    if (!val || state.chatBusy) return;
    inputEl.value = "";
    callbacks.onSendChatPrompt(val, state.chatModeHint);
  });

  inputEl?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      formEl?.requestSubmit();
    }
  });

  container.querySelectorAll("[data-suggest-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-suggest-mode");
      state.chatModeHint = state.chatModeHint === mode ? "AUTO" : mode;
      state.pendingChatDraft = null;
      renderChatWorkspaces(callbacks);
      const nextInp = container.querySelector("[data-chat-input]");
      if (nextInp) {
        nextInp.focus();
      }
    });
  });

  container.querySelector("[data-clear-chat-mode]")?.addEventListener("click", () => {
    state.chatModeHint = "AUTO";
    renderChatWorkspaces(callbacks);
  });

  container.querySelector("[data-cancel-pending-draft]")?.addEventListener("click", () => {
    callbacks.onSendChatPrompt("hủy", state.chatModeHint);
  });

  container.querySelectorAll("[data-chat-chip-prompt]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = btn.getAttribute("data-chat-chip-prompt");
      const m = btn.getAttribute("data-chat-chip-mode") || state.chatModeHint;
      if (p) callbacks.onSendChatPrompt(p, m);
    });
  });

  container.querySelectorAll("[data-chat-post-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const act = btn.getAttribute("data-chat-post-action");
      if (act === "OPEN_CALENDAR") {
        callbacks.onOpenCalendarView?.();
      }
    });
  });

  container.querySelectorAll("[data-edge-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const act = btn.getAttribute("data-edge-action");
      if (act === "OVERLOAD_OPTION") {
        callbacks.onPreviewOverloadOption?.(
          btn.getAttribute("data-edge-opt-id"),
          btn.getAttribute("data-edge-opt-code"),
          btn.getAttribute("data-edge-opt-task")
        );
      } else if (act === "PROMPT") {
        const p = btn.getAttribute("data-edge-prompt");
        if (p) callbacks.onSendChatPrompt(p, "AUTO");
      } else if (act === "DISMISS") {
        state.edgeCaseBanner = null;
        renderChatWorkspaces(callbacks);
      }
    });
  });
}

export function renderChatWorkspaces(callbacks) {
  const mainChatEl = document.getElementById("viewChat");
  if (mainChatEl) {
    _renderChatSurface(mainChatEl, { compact: false });
    _wireChatContainer(mainChatEl, callbacks);
  }

  const copilotEl = document.getElementById("calendarCopilotDrawer");
  if (copilotEl) {
    _renderChatSurface(copilotEl, { compact: true });
    _wireChatContainer(copilotEl, callbacks);
  }
}

export function renderDevHiddenTaskInspector() {
  const box = document.getElementById("devTaskHiddenInspectorList");
  if (!box) return;
  if (!state.developerMode) {
    box.innerHTML = "";
    return;
  }
  const tasks = state.tasks || [];
  if (!tasks.length) {
    box.innerHTML = `<div style="font-size:11.5px;color:var(--p-muted);">Chưa có công việc nào để kiểm tra thông số ẩn.</div>`;
    return;
  }
  box.innerHTML = tasks
    .map((t) => {
      const hashShort = t.trace_hash ? String(t.trace_hash).slice(0, 8) : "—";
      const prev = computeBufferPreview(t.duration_min, t.cognitive_load || 2, state.commitments);
      const mult = t.buffer_mode === "NONE" ? 1.0 : Number(t.buffer_multiplier > 1 ? t.buffer_multiplier : prev.mult);
      const planMin = t.buffer_mode === "NONE" ? t.duration_min : Math.ceil((Number(t.duration_min || 60) * mult) / 15) * 15;
      return `
        <div class="dev-task-inspect-item">
          <div style="display:flex;justify-content:space-between;gap:6px;align-items:center;">
            <strong>${esc(t.title)}</strong>
            <span class="badge badge-neutral mono">#${esc(hashShort)}</span>
          </div>
          <div class="mono" style="font-size:11px;color:var(--p-muted);margin-top:3px;">
            ${esc(CATEGORY_LABELS[t.category] || t.category)} · L${t.cognitive_load || 2} · ${esc(t.preferred_window || "ANYTIME")} · ${t.duration_min}p→${planMin}p (×${mult.toFixed(2)}) · ${t.is_splittable ? `Split ${t.min_chunk_min || 45}–${t.max_chunk_min || 90}p` : "Atomic"}
          </div>
        </div>`;
    })
    .join("");
}
