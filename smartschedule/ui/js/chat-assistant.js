/**
 * Conversational Scheduling Assistant (Main Spacious Chat View + Right Calendar Copilot).
 * Synchronizes state across #viewChat and #calendarCopilotDrawer in real time, supports
 * multi-turn slot filling, SHA-256 task keyword traceability, hidden criteria tuning,
 * remaining-time + habit buffer re-estimation, Deadlock/Dense-Schedule edge cases,
 * 📎 .ics / syllabus (.pdf/.md/.txt) attachments, F5 chat persistence (30 msgs),
 * 🧹 Clear Chat, and Developer Mode Pattern -> Deterministic Logic Rule & DAG badges.
 */

import { api } from "./api.js";
import { showToast } from "./modals.js";
import {
  clearChatHistoryStorage,
  invalidateSolverCaches,
  saveChatHistoryToStorage,
  serializeWorkspaceState,
  state,
  trimChatMessages,
} from "./state.js";
import { popUndoSnapshot, pushUndoSnapshot } from "./undo-history.js";
import { CATEGORY_LABELS, WINDOW_LABELS, computeBufferPreview, esc } from "./utils.js";

export const MAX_CHAT_ATTACHMENT_BYTES = 20 * 1024 * 1024; // 20 MB cap (matches backend P14a)
const SUPPORTED_ATTACHMENT_EXTS = [".ics", ".txt", ".md", ".pdf"];
const VALID_SOLVER_KEYS = new Set(["EDF", "WSPT", "LST", "SCORED_GREEDY", "BACKTRACK", "HYBRID_ALNS"]);

function _getFileExt(filename) {
  const lower = String(filename || "").toLowerCase().trim();
  const idx = lower.lastIndexOf(".");
  return idx >= 0 ? lower.slice(idx) : "";
}

function _formatFileSize(bytes) {
  const n = Number(bytes || 0);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function _readFileAsText(file) {
  if (typeof file?.text === "function") return file.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`Không đọc được tệp ${file?.name || ""}`));
    reader.readAsText(file, "utf-8");
  });
}

function _readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error(`Không đọc được tệp ${file?.name || ""}`));
    reader.readAsDataURL(file);
  });
}

function _renderPatternRulesBlock(patternRules) {
  if (!Array.isArray(patternRules) || patternRules.length === 0) return "";
  const itemsHtml = patternRules
    .map((rule) => {
      const pid = esc(rule?.pattern_id || "P?");
      const pname = esc(rule?.pattern_name || "");
      const linkVi = rule?.causal_link_vi ? `<div style="font-size:11px;color:var(--p-muted);">${esc(rule.causal_link_vi)}</div>` : "";
      const detRule = rule?.deterministic_rule
        ? `<code class="mono" style="font-size:11px;display:inline-block;margin-top:2px;padding:1px 6px;border-radius:4px;background:var(--p-card);border:1px solid var(--p-line);">${esc(rule.deterministic_rule)}</code>`
        : "";
      return `
        <div class="chat-pattern-rule-item" style="padding:5px 8px;border-radius:6px;background:var(--p-card-glass);border:1px solid var(--p-line);display:flex;flex-direction:column;gap:2px;">
          <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
            <span class="badge badge-info mono">${pid}</span>
            <strong style="font-size:11.5px;">${pname}</strong>
          </div>
          ${linkVi}
          ${detRule}
        </div>`;
    })
    .join("");

  return `
    <div class="chat-thinking-step chat-pattern-rules-box" style="margin-top:4px;gap:5px;">
      <strong>🔗 Pattern → Quy tắc Logic Tất định:</strong>
      <div style="display:flex;flex-direction:column;gap:5px;">${itemsHtml}</div>
    </div>`;
}

function _renderThinkingStage(thinkingSummary) {
  if (!state.developerMode || !thinkingSummary) return "";
  const pruned = Array.isArray(thinkingSummary.pruned_algorithms)
    ? thinkingSummary.pruned_algorithms.map((p) => (typeof p === "string" ? p : p?.key || "")).filter(Boolean).join(", ")
    : "EDF, WSPT, LST";
  const selected = thinkingSummary.selected_algorithm || state.activeSolver || "SCORED_GREEDY";
  const patternRulesHtml = _renderPatternRulesBlock(thinkingSummary.pattern_rules);

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
        ${patternRulesHtml}
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
  const dagLabel = Array.isArray(task.depends_on) && task.depends_on.length > 0 ? task.depends_on.join(", ") : "Độc lập";
  const avoidHtml =
    Array.isArray(task.avoid_windows) && task.avoid_windows.length > 0
      ? `<span>Khung né: <strong>${esc(task.avoid_windows.map((w) => WINDOW_LABELS[w] || w).join(", "))}</strong></span>`
      : "";

  return `
    <div class="dev-hidden-card">
      <div class="dev-hidden-title">🛠️ Thông số ẩn của công việc</div>
      <div class="dev-hidden-grid mono">
        <span>SHA-256: <strong>${esc(hashShort)}</strong></span>
        <span>Nhịp sinh học: <strong>${esc(WINDOW_LABELS[task.preferred_window || "ANYTIME"] || task.preferred_window || "ANYTIME")}</strong></span>
        <span>Cường độ: <strong>L${task.cognitive_load || 2} · P${task.priority || 3}</strong></span>
        <span>Fallacy Buffer: <strong>${task.duration_min}p → ${plannedMin}p (×${effectiveMult.toFixed(2)})</strong></span>
        <span>Tách task: <strong>${esc(splitTxt)}</strong></span>
        <span>Phụ thuộc DAG: <strong>${esc(dagLabel)}</strong></span>
        ${avoidHtml}
      </div>
    </div>`;
}

function _renderEdgeCaseCard(edgeCase) {
  if (!edgeCase) return "";
  const isDeadlock = edgeCase.type === "DEADLOCK";
  const isPostDisruption = edgeCase.code === "POST_DISRUPTION_OVERLOAD";
  const cls = isDeadlock ? "chat-alert-danger" : "chat-alert-warn";
  const title = isDeadlock
    ? "🚨 Lịch bị kẹt / Trùng hạn chót"
    : isPostDisruption
      ? "⚠️ Quá tải sau khi chèn sự cố đột xuất"
      : "⚠️ Cảnh báo lịch trình dày đặc";

  const suggestions = Array.isArray(edgeCase.suggestions) ? edgeCase.suggestions : [];
  let buttons = suggestions
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

  if (!buttons && isPostDisruption) {
    buttons = `<button type="button" class="btn btn-sm btn-primary" data-edge-action="OPEN_OVERLOAD_RESCUE">🛟 Mở phương án gỡ quá tải</button>`;
  }

  return `
    <div class="chat-alert-card ${cls}">
      <strong>${title}</strong>
      <p>${esc(edgeCase.message_vi)}</p>
      ${buttons ? `<div class="chat-chip-row">${buttons}</div>` : ""}
    </div>`;
}

function _renderIcsImportCard(msg) {
  const ics = msg?.icsImport;
  if (!ics) return "";
  const fixedList = Array.isArray(ics.fixed_events) ? ics.fixed_events : [];
  const taskList = Array.isArray(ics.tasks) ? ics.tasks : [];
  const previewFixed = fixedList
    .slice(0, 4)
    .map((e) => `<li><strong>${esc(e.title)}</strong> <span class="mono">(${esc(Array.isArray(e.day_of_week) ? e.day_of_week.join(", ") : e.day_of_week)} ${esc(e.start_time)}–${esc(e.end_time)})</span></li>`)
    .join("");
  const previewTasks = taskList
    .slice(0, 4)
    .map((t) => `<li><strong>${esc(t.title)}</strong> <span class="mono">(hạn ${esc(t.deadline_day || "?")} ${esc(t.deadline_time || "23:59")} · ${esc(t.duration_min || 60)}p)</span></li>`)
    .join("");

  const statusFooter = ics.applied
    ? `<div class="chat-finalized-pill">✅ Đã áp dụng lịch từ ${esc(ics.filename)} vào tuần hiện tại</div>`
    : ics.dismissed
      ? `<div style="font-size:12px;color:var(--p-muted);">Đã bỏ qua bản nhập từ ${esc(ics.filename)}.</div>`
      : `<div class="chat-chip-row">
           <button type="button" class="btn btn-primary btn-sm" data-apply-ics-import="${esc(msg.id)}">✅ Áp dụng vào lịch</button>
           <button type="button" class="btn btn-sm btn-ghost" data-dismiss-ics-import="${esc(msg.id)}">✕ Bỏ qua</button>
         </div>`;

  return `
    <div class="card chat-ics-card" style="padding:10px 12px;display:flex;flex-direction:column;gap:7px;background:var(--p-card-subtle);border:1px solid var(--p-accent-border);">
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
        <strong>📅 Xem trước lịch .ics: ${esc(ics.filename || "timetable.ics")}</strong>
        <span class="badge badge-info mono">${fixedList.length} lớp cố định · ${taskList.length} hạn chót</span>
      </div>
      ${previewFixed ? `<ul style="margin:0;padding-left:18px;font-size:12px;display:flex;flex-direction:column;gap:2px;">${previewFixed}${fixedList.length > 4 ? `<li>… và ${fixedList.length - 4} lớp cố định khác</li>` : ""}</ul>` : ""}
      ${previewTasks ? `<ul style="margin:0;padding-left:18px;font-size:12px;display:flex;flex-direction:column;gap:2px;">${previewTasks}${taskList.length > 4 ? `<li>… và ${taskList.length - 4} deadline khác</li>` : ""}</ul>` : ""}
      ${statusFooter}
    </div>`;
}

function _renderAttachmentDigestCard(digest, conflict) {
  if (!digest || !Array.isArray(digest.milestones) || digest.milestones.length === 0) return "";
  const rows = digest.milestones
    .slice(0, 5)
    .map(
      (ms, idx) =>
        `<li><strong>${idx + 1}. ${esc(ms.title)}</strong> <span class="mono">(${esc(ms.estimated_min)}p · L${esc(ms.cognitive_load || 2)}${ms.depends_on_prev ? " · nối tiếp" : ""})</span></li>`
    )
    .join("");
  return `
    <div class="chat-rem-box" data-attachment-digest>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;flex-wrap:wrap;">
        <strong>📑 Phân tích đề bài: ${esc(digest.filename || "Tài liệu")}</strong>
        <span class="badge ${conflict === "USER_VS_DOC_UNDERESTIMATE" ? "badge-warn" : "badge-info"} mono">${digest.milestones.length} mốc · ~${esc(digest.suggested_total_min)}p</span>
      </div>
      <ul style="margin:4px 0 0;padding-left:18px;font-size:12px;display:flex;flex-direction:column;gap:2px;">
        ${rows}
        ${digest.milestones.length > 5 ? `<li>… và ${digest.milestones.length - 5} mốc khác</li>` : ""}
      </ul>
    </div>`;
}

function _renderMessageBubble(msg) {
  if (msg.role === "user") {
    const attChips = Array.isArray(msg.attachments) && msg.attachments.length
      ? `<div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:4px;">${msg.attachments
          .map((a) => `<span class="badge badge-neutral" style="background:rgba(255,255,255,0.2);color:inherit;border-color:rgba(255,255,255,0.35);">📎 ${esc(a.filename)}</span>`)
          .join("")}</div>`
      : "";
    return `
      <div class="chat-msg chat-msg-user">
        <div class="chat-bubble user">
          <div>${esc(msg.text)}</div>
          ${attChips}
        </div>
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
        ${_renderIcsImportCard(msg)}
        ${_renderAttachmentDigestCard(msg.attachmentDigest, msg.conflict)}
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

function _renderPendingAttachmentsBar() {
  const list = Array.isArray(state.pendingAttachments) ? state.pendingAttachments : [];
  if (list.length === 0) return "";
  return `
    <div class="chat-status-pills chat-attachment-pills" data-pending-attachments>
      ${list
        .map(
          (att, idx) => `
        <div class="chat-mode-pill" style="background:var(--st-info-bg);color:var(--st-info);border:1px solid var(--st-info-border);">
          <span>📎 <strong>${esc(att.filename)}</strong> <small style="opacity:0.8;">(${esc(_formatFileSize(att.size))})</small></span>
          <button type="button" data-remove-attachment="${idx}" aria-label="Bỏ tệp ${esc(att.filename)}">✕</button>
        </div>`
        )
        .join("")}
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
    AUTO: "VD: Làm bài tập môn Computational Thinking, từ 19h ngày thứ 3, tới 21h ngày thứ 5, cần thực hiện trong 2 tiếng... (hoặc kéo thả .ics / đề bài .pdf)",
    ADD_RECURRING: "Nhập tên lịch lặp & khung giờ (VD: Tập gym từ 17:30 đến 18:30 thứ 2, 4, 6)...",
    ADD_TASK: "Nhập việc cần làm, khung giờ hoặc thời lượng & hạn chót (VD: Làm bài tập Giải tích 2 tiếng trước 21h thứ 5)...",
  };

  const fullHeaderHtml = !compact && hasMessages
    ? `
      <div class="chat-full-toolbar" style="display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 4px 0;">
        <span style="font-size:12px;color:var(--p-muted);">Trợ lý xếp lịch · Lưu tự động ${state.chatMessages.length}/30 tin gần nhất</span>
        <button type="button" class="btn btn-sm btn-ghost" data-clear-chat-history title="Làm mới khung chat (không xóa công việc đã xếp)">🧹 Làm mới chat</button>
      </div>`
    : "";

  const heroHtml = !hasMessages && !compact
    ? `
      <div class="chat-empty-hero">
        <div class="chat-hero-badge">Trợ lý xếp lịch</div>
        <h1>Hôm nay bạn muốn sắp xếp lịch trình thế nào?</h1>
        <p>Nhắn tự nhiên việc cần làm cùng khung giờ (hoặc kéo thả tệp <code>.ics</code> / đề bài <code>.pdf, .md</code> vào ô chat).</p>
        ${_renderSuggestionCards(false)}
      </div>`
    : "";

  const copilotHeaderHtml = compact
    ? `
      <div class="copilot-head">
        <div>
          <strong>Trợ lý tinh chỉnh trực tiếp</strong>
          <div style="font-size:11.5px;color:var(--p-muted);">Nhắn hoặc thả file .ics / đề bài ngay bên dưới</div>
        </div>
        <div style="display:inline-flex;align-items:center;gap:4px;">
          ${hasMessages ? `<button type="button" class="btn btn-sm btn-ghost" data-clear-chat-history title="Làm mới lịch sử chat (không xóa lịch học)" aria-label="Làm mới chat">🧹</button>` : ""}
          <button type="button" class="btn btn-sm btn-ghost" id="btnToggleCopilotDrawer" title="Thu gọn trợ lý để mở rộng lịch trình" aria-label="Thu gọn trợ lý">⇥</button>
        </div>
      </div>
      ${!hasMessages ? _renderSuggestionCards(true) : ""}`
    : "";

  const streamHtml = hasMessages
    ? `<div class="chat-messages-stream" data-chat-stream>${state.chatMessages.map(_renderMessageBubble).join("")}</div>`
    : compact
      ? `<div class="chat-messages-stream is-empty-compact" data-chat-stream>
           <div class="chat-compact-hint">Chọn một gợi ý ở trên, bấm 📎 đính kèm .ics/đề bài, hoặc gõ yêu cầu vào ô bên dưới nhé.</div>
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

  const attachmentsBar = _renderPendingAttachmentsBar();

  container.innerHTML = `
    <div class="chat-surface ${compact ? "is-copilot" : "is-full"}">
      ${copilotHeaderHtml}
      ${fullHeaderHtml}
      <div class="chat-scroll-area" data-chat-scroll>
        ${heroHtml}
        ${streamHtml}
      </div>
      <div class="chat-composer-wrap" data-chat-dropzone>
        ${activeModeBadge || pendingBadge ? `<div class="chat-status-pills">${activeModeBadge}${pendingBadge}</div>` : ""}
        ${attachmentsBar}
        <form class="chat-composer-form" data-chat-form>
          <input type="file"
                 data-chat-file-input
                 accept=".ics,.txt,.md,.pdf"
                 multiple
                 hidden />
          <button type="button"
                  class="btn btn-sm btn-ghost chat-attach-btn"
                  data-chat-attach-btn
                  title="Đính kèm lịch .ics hoặc đề bài (.pdf, .md, .txt)"
                  aria-label="Đính kèm tệp .ics hoặc tài liệu"
                  style="height:36px;min-width:34px;padding:0 8px;font-size:15px;"
                  ${state.chatBusy ? "disabled" : ""}>📎</button>
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

export function clearChatTranscript(callbacks = {}) {
  state.chatMessages = [];
  state.pendingChatDraft = null;
  state.pendingAttachments = [];
  state.pendingIcsImport = null;
  clearChatHistoryStorage(state.workspaceId);
  api.saveState(serializeWorkspaceState(state), state.workspaceId).catch(() => null);
  callbacks.onClearChat?.();
  renderChatWorkspaces(callbacks);
  showToast("🧹 Đã làm mới lịch sử chat (lịch trình của bạn vẫn được giữ nguyên).", "ok");
}

export async function applyIcsImportToWorkspace(icsData, callbacks = {}, sourceMsg = null) {
  if (!icsData) return;
  const fixedToAdd = Array.isArray(icsData.fixed_events) ? icsData.fixed_events : [];
  const tasksToAdd = Array.isArray(icsData.tasks) ? icsData.tasks : [];
  if (fixedToAdd.length === 0 && tasksToAdd.length === 0) {
    showToast("Tệp .ics không có sự kiện hoặc hạn chót nào để áp dụng.", "warn");
    return;
  }

  pushUndoSnapshot(state, `Nhập lịch từ ${icsData.filename || "tệp .ics"}`);

  const existingFixed = Array.isArray(state.commitments.fixed_events) ? [...state.commitments.fixed_events] : [];
  const fixedSig = new Set(
    existingFixed.map((e) => `${String(e.title || "").toLowerCase()}|${JSON.stringify(e.day_of_week)}|${e.start_time}|${e.end_time}`)
  );
  let addedFixedCount = 0;
  for (const ev of fixedToAdd) {
    const sig = `${String(ev.title || "").toLowerCase()}|${JSON.stringify(ev.day_of_week)}|${ev.start_time}|${ev.end_time}`;
    if (!fixedSig.has(sig)) {
      fixedSig.add(sig);
      existingFixed.push(ev);
      addedFixedCount += 1;
    }
  }
  state.commitments.fixed_events = existingFixed;

  const existingTasks = Array.isArray(state.tasks) ? [...state.tasks] : [];
  const taskIds = new Set(existingTasks.map((t) => t.task_id));
  let addedTaskCount = 0;
  for (const t of tasksToAdd) {
    if (!taskIds.has(t.task_id)) {
      taskIds.add(t.task_id);
      existingTasks.push(t);
      addedTaskCount += 1;
    }
  }
  state.tasks = existingTasks;

  if (sourceMsg?.icsImport) {
    sourceMsg.icsImport.applied = true;
    sourceMsg.icsImport.dismissed = false;
  }
  state.pendingIcsImport = null;

  invalidateSolverCaches();
  try {
    const sched = await api.plan({
      commitments: state.commitments,
      tasks: state.tasks,
      algorithm: state.activeSolver || "SCORED_GREEDY",
      pinned_blocks: state.pinnedBlocks,
    });
    state.currentSchedule = sched;
    state.schedulesBySolver[state.activeSolver] = sched;
  } catch (err) {
    showToast(`Đã nhập .ics nhưng gặp lỗi xếp lịch: ${err.message}`, "warn");
  }

  await api.saveState(serializeWorkspaceState(state), state.workspaceId).catch(() => null);
  renderChatWorkspaces(callbacks);
  callbacks.onSelectSolver?.(state.activeSolver, false);

  showToast(`✅ Đã nạp ${addedFixedCount} lịch cố định & ${addedTaskCount} deadline từ ${icsData.filename || ".ics"}.`, "ok", {
    onUndo: async () => {
      const restored = popUndoSnapshot(state);
      if (!restored) return;
      if (sourceMsg?.icsImport) sourceMsg.icsImport.applied = false;
      await api.saveState(serializeWorkspaceState(state), state.workspaceId).catch(() => null);
      renderChatWorkspaces(callbacks);
      callbacks.onSelectSolver?.(state.activeSolver, false);
      showToast(`↩ Đã hoàn tác: ${restored.actionLabel}`, "ok");
    },
  });
}

async function _sendAttachmentChatTurn(promptText, modeHint, attachments, callbacks) {
  const cleanPrompt = String(promptText || "").trim() || "Phân tích tài liệu đính kèm và đề xuất xếp lịch giúp mình.";
  state.chatMessages.push({
    id: `u_${Date.now()}`,
    role: "user",
    text: cleanPrompt,
    attachments: attachments.map((a) => ({ filename: a.filename, size: a.size })),
  });
  state.chatMessages = trimChatMessages(state.chatMessages);
  state.chatBusy = true;
  renderChatWorkspaces(callbacks);

  const preSnapshot = {
    commitments: state.commitments,
    tasks: state.tasks,
    pinnedBlocks: state.pinnedBlocks,
    completedBlocks: state.completedBlocks,
    currentSchedule: state.currentSchedule,
  };

  try {
    const res = await api.sendChatTurn({
      prompt: cleanPrompt,
      mode_hint: modeHint || state.chatModeHint || "AUTO",
      pending_draft: state.pendingChatDraft,
      commitments: state.commitments,
      tasks: state.tasks,
      pinned_blocks: state.pinnedBlocks,
      completed_blocks: state.completedBlocks,
      last_task_id: state.lastMutatedTaskId,
      algorithm: state.activeSolver || "SCORED_GREEDY",
      workspace_id: state.workspaceId,
      auto_save: true,
      attachments: attachments.map(({ filename, content }) => ({ filename, content })),
    });

    if (res.status === "APPLIED") {
      pushUndoSnapshot(preSnapshot, `Xếp lịch từ tệp đính kèm (${attachments.map((a) => a.filename).join(", ")})`);
    }

    state.pendingChatDraft = res.pending_draft || null;
    if (res.status === "CANCELLED" || res.status === "APPLIED") {
      state.chatModeHint = "AUTO";
    }
    if (res.updated_commitments) state.commitments = res.updated_commitments;
    if (Array.isArray(res.updated_tasks)) state.tasks = res.updated_tasks;
    if (Array.isArray(res.updated_pinned_blocks)) state.pinnedBlocks = res.updated_pinned_blocks;
    if (res.mutated_task_id) state.lastMutatedTaskId = res.mutated_task_id;

    const selectedAlgo = res.thinking_summary?.selected_algorithm;
    if (selectedAlgo && VALID_SOLVER_KEYS.has(selectedAlgo)) {
      state.activeSolver = selectedAlgo;
    }

    if (res.schedule) {
      invalidateSolverCaches();
      state.schedulesBySolver[state.activeSolver] = res.schedule;
      state.currentSchedule = res.schedule;
      state.edgeCaseBanner = res.edge_case || null;
    }

    const defaultPostActions =
      Array.isArray(res.post_actions) && res.post_actions.length
        ? res.post_actions
        : [{ action: "OPEN_CALENDAR", label: "🗓️ Kiểm tra lịch trình" }];

    state.chatMessages.push({
      id: `a_${Date.now()}`,
      role: "assistant",
      text: res.reply_vi || "Đã phân tích tài liệu đính kèm của bạn.",
      quickChips: res.quick_chips || [],
      postActions: defaultPostActions,
      edgeCase: res.edge_case || null,
      remainingEstimation: res.remaining_estimation || null,
      thinkingSummary: res.thinking_summary || null,
      finalizedMessage: res.status === "APPLIED" ? res.finalized_message_vi || "" : "",
      tracedTaskId: res.traced_task?.task_id || res.mutated_task_id || null,
      conflict: res.conflict || null,
      attachmentDigest: res.attachment_digest || null,
      adaptation: res.adaptation || null,
    });
    state.chatMessages = trimChatMessages(state.chatMessages);
    await api.saveState(serializeWorkspaceState(state), state.workspaceId).catch(() => null);

    if (res.status === "APPLIED") {
      callbacks.onSelectSolver?.(state.activeSolver, false);
      showToast("✅ Đã cập nhật lịch trình từ tệp đính kèm.", "ok", {
        onUndo: async () => {
          const restored = popUndoSnapshot(state);
          if (!restored) return;
          await api.saveState(serializeWorkspaceState(state), state.workspaceId).catch(() => null);
          callbacks.onSelectSolver?.(state.activeSolver, false);
          renderChatWorkspaces(callbacks);
          showToast(`↩ Đã hoàn tác: ${restored.actionLabel}`, "ok");
        },
      });
    }
  } catch (err) {
    state.chatMessages.push({
      id: `e_${Date.now()}`,
      role: "assistant",
      text: `Mình gặp trục trặc khi đọc tệp đính kèm: ${err.message}. Bạn thử lại với file .ics, .pdf, .md hoặc .txt nhỏ hơn 20 MB nhé.`,
    });
    showToast(`Lỗi xử lý tệp đính kèm: ${err.message}`, "danger");
  } finally {
    state.chatBusy = false;
    renderChatWorkspaces(callbacks);
  }
}

export async function handleChatFilesSelected(fileList, callbacks = {}) {
  const files = Array.from(fileList || []);
  if (files.length === 0) return;

  for (const file of files) {
    const ext = _getFileExt(file.name);
    if (!SUPPORTED_ATTACHMENT_EXTS.includes(ext)) {
      showToast(`Định dạng "${file.name}" chưa hỗ trợ. Vui lòng chọn .ics, .pdf, .md hoặc .txt.`, "warn");
      continue;
    }
    if (Number(file.size || 0) > MAX_CHAT_ATTACHMENT_BYTES) {
      showToast(`Tệp "${file.name}" vượt quá giới hạn 20 MB.`, "danger");
      continue;
    }

    if (ext === ".ics") {
      try {
        const icsText = await _readFileAsText(file);
        const parsed = await api.importIcs(icsText);
        const fixedEvents = Array.isArray(parsed?.fixed_events) ? parsed.fixed_events : [];
        const tasks = Array.isArray(parsed?.tasks) ? parsed.tasks : [];
        const icsPayload = {
          filename: file.name,
          fixed_events: fixedEvents,
          tasks,
          warnings: parsed?.warnings || [],
          applied: false,
          dismissed: false,
        };
        state.pendingIcsImport = icsPayload;
        state.chatMessages.push({
          id: `u_ics_${Date.now()}`,
          role: "user",
          text: `📎 Đã tải lên thời khóa biểu: ${file.name}`,
          attachments: [{ filename: file.name, size: file.size }],
        });
        state.chatMessages.push({
          id: `a_ics_${Date.now() + 1}`,
          role: "assistant",
          text:
            fixedEvents.length + tasks.length > 0
              ? `Mình đã đọc xong tệp **${file.name}**: tìm thấy **${fixedEvents.length} lịch học cố định** và **${tasks.length} hạn chót bài tập**. Bạn kiểm tra nhanh và bấm áp dụng vào lịch nhé!`
              : `Mình đã đọc tệp **${file.name}** nhưng chưa thấy sự kiện lịch học hay hạn nộp hợp lệ nào bên trong.`,
          icsImport: icsPayload,
          postActions: [{ action: "OPEN_CALENDAR", label: "🗓️ Kiểm tra lịch trình" }],
        });
        state.chatMessages = trimChatMessages(state.chatMessages);
        renderChatWorkspaces(callbacks);
      } catch (err) {
        showToast(`Không đọc được tệp .ics "${file.name}": ${err.message}`, "danger");
      }
    } else {
      try {
        const content = ext === ".pdf" ? await _readFileAsDataUrl(file) : await _readFileAsText(file);
        const nextList = Array.isArray(state.pendingAttachments)
          ? state.pendingAttachments.filter((a) => a.filename !== file.name)
          : [];
        nextList.push({ filename: file.name, content, size: Number(file.size || content.length) });
        state.pendingAttachments = nextList;
        renderChatWorkspaces(callbacks);
        showToast(`📎 Đã đính kèm "${file.name}". Nhấn Gửi để trợ lý phân tích đề bài.`, "ok");
      } catch (err) {
        showToast(`Không đọc được tệp "${file.name}": ${err.message}`, "danger");
      }
    }
  }
}

function _wireChatContainer(container, callbacks) {
  if (!container) return;
  const inputEl = container.querySelector("[data-chat-input]");
  const formEl = container.querySelector("[data-chat-form]");
  const fileInput = container.querySelector("[data-chat-file-input]");
  const attachBtn = container.querySelector("[data-chat-attach-btn]");
  const dropZone = container.querySelector("[data-chat-dropzone]");

  container.querySelector("#btnToggleCopilotDrawer")?.addEventListener("click", () => {
    callbacks.onToggleCopilotDrawer?.();
  });

  container.querySelectorAll("[data-clear-chat-history]").forEach((btn) => {
    btn.addEventListener("click", () => clearChatTranscript(callbacks));
  });

  attachBtn?.addEventListener("click", () => {
    if (state.chatBusy) return;
    fileInput?.click();
  });

  fileInput?.addEventListener("change", async (e) => {
    const selected = e.target.files;
    if (selected && selected.length > 0) {
      await handleChatFilesSelected(selected, callbacks);
    }
    e.target.value = "";
  });

  if (dropZone) {
    const setDragActive = (active) => {
      dropZone.classList.toggle("is-drag-over", active);
      dropZone.style.outline = active ? "2px dashed var(--p-accent)" : "";
    };
    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      if (!state.chatBusy) setDragActive(true);
    });
    dropZone.addEventListener("dragleave", () => setDragActive(false));
    dropZone.addEventListener("drop", async (e) => {
      e.preventDefault();
      setDragActive(false);
      if (state.chatBusy) return;
      const dropped = e.dataTransfer?.files;
      if (dropped && dropped.length > 0) {
        await handleChatFilesSelected(dropped, callbacks);
      }
    });
  }

  container.querySelectorAll("[data-remove-attachment]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.getAttribute("data-remove-attachment"));
      if (Number.isInteger(idx) && Array.isArray(state.pendingAttachments)) {
        state.pendingAttachments.splice(idx, 1);
        renderChatWorkspaces(callbacks);
      }
    });
  });

  container.querySelectorAll("[data-apply-ics-import]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const msgId = btn.getAttribute("data-apply-ics-import");
      const msg = (state.chatMessages || []).find((m) => m.id === msgId);
      if (!msg?.icsImport || msg.icsImport.applied) return;
      if (typeof callbacks?.onApplyIcsImport === "function") {
        await callbacks.onApplyIcsImport(msg.icsImport, msg);
        return;
      }
      await applyIcsImportToWorkspace(msg.icsImport, callbacks, msg);
    });
  });

  container.querySelectorAll("[data-dismiss-ics-import]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const msgId = btn.getAttribute("data-dismiss-ics-import");
      const msg = (state.chatMessages || []).find((m) => m.id === msgId);
      if (msg?.icsImport) {
        msg.icsImport.dismissed = true;
        renderChatWorkspaces(callbacks);
      }
    });
  });

  formEl?.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (state.chatBusy) return;
    const val = inputEl?.value.trim() || "";
    const staged = Array.isArray(state.pendingAttachments) ? [...state.pendingAttachments] : [];
    if (!val && staged.length === 0) return;

    if (inputEl) inputEl.value = "";

    if (staged.length > 0) {
      state.pendingAttachments = [];
      const promptToSend = val || "Phân tích tài liệu đính kèm và đề xuất xếp lịch giúp mình.";
      if (typeof callbacks?.onSendChatWithAttachments === "function") {
        await callbacks.onSendChatWithAttachments(promptToSend, state.chatModeHint, staged);
        return;
      }
      if (typeof callbacks?.onSendChatPrompt === "function" && callbacks.onSendChatPrompt.length >= 3) {
        await callbacks.onSendChatPrompt(promptToSend, state.chatModeHint, staged);
        return;
      }
      await _sendAttachmentChatTurn(promptToSend, state.chatModeHint, staged, callbacks);
      return;
    }

    callbacks.onSendChatPrompt(val, state.chatModeHint);
  });

  inputEl?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
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
      } else if (act === "OPEN_OVERLOAD_RESCUE") {
        callbacks.onOpenOverloadRescue?.();
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
  // Always keep latest 30 chat messages persisted across F5 refresh
  state.chatMessages = saveChatHistoryToStorage(state.chatMessages, state.workspaceId);

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
      const dagTxt = Array.isArray(t.depends_on) && t.depends_on.length ? ` · DAG: ${t.depends_on.join(", ")}` : "";
      const avoidTxt = Array.isArray(t.avoid_windows) && t.avoid_windows.length ? ` · Né: ${t.avoid_windows.join(", ")}` : "";
      return `
        <div class="dev-task-inspect-item">
          <div style="display:flex;justify-content:space-between;gap:6px;align-items:center;">
            <strong>${esc(t.title)}</strong>
            <span class="badge badge-neutral mono">#${esc(hashShort)}</span>
          </div>
          <div class="mono" style="font-size:11px;color:var(--p-muted);margin-top:3px;">
            ${esc(CATEGORY_LABELS[t.category] || t.category)} · L${t.cognitive_load || 2} · ${esc(t.preferred_window || "ANYTIME")} · ${t.duration_min}p→${planMin}p (×${mult.toFixed(2)}) · ${t.is_splittable ? `Split ${t.min_chunk_min || 45}–${t.max_chunk_min || 90}p` : "Atomic"}${esc(dagTxt)}${esc(avoidTxt)}
          </div>
        </div>`;
    })
    .join("");
}
