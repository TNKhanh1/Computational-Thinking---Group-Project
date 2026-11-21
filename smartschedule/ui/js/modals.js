/**
 * Interactive Popovers & Modals:
 *  - Test Suite Popover (Presets, Regimes R1-R6 + Seed + 7/14 ngày, Fuzz v2 tiers + Seed, Scenarios T01-T10)
 *  - Block Inspector Modal ("Tại sao xếp giờ này?", Pin, Focus Timer 25/45/90p, Check-in M7, Overrun)
 *  - Disruption / Local Repair Modal
 *  - Overload Rescue Modal (O1-O4 Preview & Apply)
 *  - Toast Notifications
 */

import { state } from "./state.js";
import { CATEGORY_LABELS, LOAD_LABELS, USER_LOAD_LABELS, WEEKDAYS_EN, esc, formatDeadlineCountdown, humanizeWeekdaysVi, resolveNowSlot } from "./utils.js";

export function showToast(message, tone = "ok") {
  const stack = document.getElementById("toastStack");
  if (!stack) return;
  const el = document.createElement("div");
  el.className = `toast ${tone}`;
  el.innerHTML = `<span>${esc(message)}</span>`;
  stack.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 220ms ease";
    setTimeout(() => el.remove(), 240);
  }, 3600);
}

export function renderTestSuitePopover(popoverEl, callbacks) {
  const cat = state.catalog;
  if (!cat) {
    popoverEl.innerHTML = `<div style="padding:12px;color:var(--p-muted);">Đang tải danh mục bộ test...</div>`;
    return;
  }

  const presetsHtml = (cat.presets || [])
    .map(
      (p) => `
      <button type="button" class="suite-item" data-load-source="preset" data-load-id="${esc(p.id)}">
        <div>
          <strong style="font-size:12.5px;">${esc(p.name)}</strong>
          <div style="font-size:11.5px;color:var(--p-muted);">${p.task_count} việc · ${p.fixed_count} lịch cố định</div>
        </div>
        <span class="badge badge-ok">Preset</span>
      </button>`
    )
    .join("");

  const scenariosHtml = (cat.scenarios || [])
    .map((s) => {
      const exp = String(s.expected_status || "SUCCESS");
      const bCls = exp.includes("OVERLOAD") ? "badge-warn" : s.has_disruption || s.has_overrun ? "badge-info" : "badge-neutral";
      return `
        <button type="button" class="suite-item" data-load-source="scenario" data-load-id="${esc(s.scenario_id)}">
          <div style="min-width:0;">
            <strong style="font-size:12.5px;">${esc(s.scenario_id)} · ${esc(s.name)}</strong>
            <div style="font-size:11.5px;color:var(--p-muted);">${esc(s.description)}</div>
          </div>
          <span class="badge ${bCls} mono">${s.task_count}t</span>
        </button>`;
    })
    .join("");

  const picker = state.suitePicker;
  const regimesHtml = (cat.regimes || [])
    .map(
      (r) => `
      <button type="button" class="suite-item" data-load-source="regime" data-load-id="${esc(r.id)}">
        <div style="min-width:0;">
          <strong style="font-size:12.5px;">${esc(r.name)}</strong>
          <div style="font-size:11.5px;color:var(--p-muted);">${esc(r.description)}</div>
        </div>
        <span class="badge badge-dark mono">${esc(r.tag)}</span>
      </button>`
    )
    .join("");

  const fuzzHtml = (cat.fuzz_tiers || [])
    .map(
      (f) => `
      <button type="button" class="suite-item" data-load-source="fuzz" data-load-id="${esc(f.id)}">
        <div style="min-width:0;">
          <strong style="font-size:12.5px;">${esc(f.name)}</strong>
          <div style="font-size:11.5px;color:var(--p-muted);">${esc(f.description)}</div>
          <div class="mono" style="font-size:11px;color:var(--p-muted);margin-top:2px;">${esc(f.rho_range)}</div>
        </div>
        <span class="badge ${f.id === "OVERLOAD" ? "badge-warn" : f.id === "TIGHT" ? "badge-info" : "badge-dark"} mono">${esc(f.tag)}</span>
      </button>`
    )
    .join("");

  const seedControls = (idPrefix, value) => `
    <div style="display:inline-flex;align-items:center;gap:6px;">
      <label for="${idPrefix}Seed" style="font-size:11.5px;color:var(--p-muted);">Seed:</label>
      <input type="number" id="${idPrefix}Seed" class="input mono" value="${esc(value)}" style="width:80px;min-height:28px;padding:3px 6px;" />
      <button type="button" class="btn btn-sm" data-random-seed="${idPrefix}Seed" title="Sinh seed ngẫu nhiên">🎲</button>
    </div>`;

  popoverEl.innerHTML = `
    <button type="button" class="suite-item suite-showcase" id="btnSuiteOpenShowcase">
      <div>
        <strong style="font-size:12.5px;">📊 Bảng so sánh 6 thuật toán trên 7 bộ test nổi bật</strong>
        <div style="font-size:11.5px;color:var(--p-muted);">Các đề Testing_System mà kết quả thuật toán khác nhau rõ — kèm giải thích dưới mỗi bảng.</div>
      </div>
      <span class="badge badge-ok">Xem</span>
    </button>

    <div>
      <div class="popover-section-title">1. Mẫu thực tế (Presets)</div>
      <div style="display:flex;flex-direction:column;gap:6px;">${presetsHtml}</div>
    </div>

    <div>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px;flex-wrap:wrap;">
        <div class="popover-section-title" style="margin:0;">2. 6 Regimes chuẩn (InputGenerator)</div>
        <div style="display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;">
          ${seedControls("inpRegime", picker.regimeSeed)}
          <select id="inpRegimeHorizon" class="select" style="width:auto;min-height:28px;padding:2px 8px;font-size:11.5px;" aria-label="Số ngày lập lịch">
            <option value="" ${picker.regimeHorizon === "" ? "selected" : ""}>Số ngày: mặc định</option>
            <option value="7" ${picker.regimeHorizon === "7" ? "selected" : ""}>7 ngày</option>
            <option value="14" ${picker.regimeHorizon === "14" ? "selected" : ""}>14 ngày</option>
          </select>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;">${regimesHtml}</div>
    </div>

    <div>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px;flex-wrap:wrap;">
        <div class="popover-section-title" style="margin:0;">3. Fuzz v2 — đề ngẫu nhiên vô hạn (FuzzGenerator)</div>
        ${seedControls("inpFuzz", picker.fuzzSeed)}
      </div>
      <div style="display:flex;flex-direction:column;gap:6px;">${fuzzHtml}</div>
    </div>

    <div>
      <div class="popover-section-title">4. Kịch bản đồ án (T01 – T10)</div>
      <div style="display:flex;flex-direction:column;gap:6px;">${scenariosHtml}</div>
    </div>
  `;

  const readSeed = (id, fallback) => {
    const v = parseInt(popoverEl.querySelector(`#${id}`)?.value ?? "", 10);
    return Number.isFinite(v) ? v : fallback;
  };
  const syncPicker = () => {
    picker.regimeSeed = readSeed("inpRegimeSeed", 42);
    picker.fuzzSeed = readSeed("inpFuzzSeed", 1001);
    picker.regimeHorizon = popoverEl.querySelector("#inpRegimeHorizon")?.value || "";
  };
  popoverEl.querySelectorAll("input, select").forEach((el) => el.addEventListener("change", syncPicker));

  popoverEl.querySelectorAll("[data-random-seed]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const inp = popoverEl.querySelector(`#${btn.getAttribute("data-random-seed")}`);
      if (inp) inp.value = String(Math.floor(Math.random() * 9000) + 100);
      syncPicker();
    });
  });

  popoverEl.querySelector("#btnSuiteOpenShowcase")?.addEventListener("click", () => callbacks.onOpenShowcase?.());

  popoverEl.querySelectorAll("[data-load-source]").forEach((btn) => {
    btn.addEventListener("click", () => {
      syncPicker();
      const source = btn.getAttribute("data-load-source");
      const id = btn.getAttribute("data-load-id");
      if (source === "fuzz") {
        callbacks.onLoadSuite(source, id, picker.fuzzSeed, null);
      } else if (source === "regime") {
        callbacks.onLoadSuite(source, id, picker.regimeSeed, picker.regimeHorizon ? Number(picker.regimeHorizon) : null);
      } else {
        callbacks.onLoadSuite(source, id, 42, null);
      }
    });
  });
}

function _humanizeBlockReason(reasonObj, block) {
  const code = typeof reasonObj === "string" ? "REASON" : String(reasonObj?.code || "INFO").toUpperCase();
  const rawText = typeof reasonObj === "string" ? reasonObj : String(reasonObj?.text || "");
  const load = Number(block?.cognitive_load || 2);
  const loadDesc = USER_LOAD_LABELS[load] || "Mức vừa";
  const energyVal = Number(reasonObj?.energy_level ?? block?.energy_level);
  const slotEnergyDesc = Number.isFinite(energyVal)
    ? energyVal >= 2.5
      ? "khung giờ tỉnh táo cao"
      : energyVal >= 1.7
        ? "khung giờ tập trung vừa"
        : "khung giờ trống phù hợp"
    : "khung giờ trống phù hợp";

  if (code === "BEFORE_DEADLINE") {
    const dueLabel = humanizeWeekdaysVi(reasonObj?.due || block?.deadline_str || "");
    return {
      tag: "Kịp hạn",
      text: dueLabel ? `Hoàn thành kịp trước hạn chót (${dueLabel}).` : "Hoàn thành kịp trước hạn chót.",
    };
  }
  if (code === "ENERGY_MATCH") {
    return {
      tag: "Nhịp sinh học",
      text: `Phù hợp với ${slotEnergyDesc} trong ngày của bạn.`,
    };
  }
  if (code === "ENERGY_FALLBACK") {
    return {
      tag: "Kịp tiến độ",
      text: "Giờ tỉnh táo nhất đã kín nên app xếp vào khung giờ trống sớm nhất để bạn kịp hạn.",
    };
  }
  if (code === "BREAK_AFTER") {
    const mins = Number(reasonObj?.rest_min || 15);
    return {
      tag: "Nghỉ ngơi",
      text: `Tự động chừa ${mins} phút nghỉ giải lao ngay sau phiên học dài để tránh mệt mỏi.`,
    };
  }
  if (code === "ESTIMATE_BUFFER") {
    const est = reasonObj?.estimate_min;
    const plan = reasonObj?.planned_min;
    return {
      tag: "Dự phòng giờ",
      text:
        est && plan
          ? `Đã tính sẵn thêm thời gian dự phòng (${est}p → ${plan}p) phòng khi làm lâu hơn dự kiến.`
          : "Đã cộng thêm thời gian dự phòng để hạn chế trễ dây chuyền.",
    };
  }
  if (code === "BATCHED_CATEGORY") {
    const cat = CATEGORY_LABELS[reasonObj?.category] || reasonObj?.category || "cùng nhóm";
    return {
      tag: "Học liền mạch",
      text: `Đặt gần công việc thuộc nhóm ${cat} để giữ mạch tập trung, đỡ phải chuyển qua lại nhiều chủ đề.`,
    };
  }
  if (code === "AFTER_PREREQ") {
    const depIds = Array.isArray(reasonObj?.depends_on) ? reasonObj.depends_on : [];
    const depNames = depIds
      .map((id) => state.tasks.find((t) => t.task_id === id)?.title || id)
      .filter(Boolean);
    return {
      tag: "Đúng thứ tự",
      text: depNames.length
        ? `Xếp sau khi bạn đã hoàn thành việc cần làm trước: ${depNames.join(", ")}.`
        : "Xếp đúng sau công việc cần hoàn thành trước đó.",
    };
  }
  if (code === "CRUNCH_RELAXED") {
    return {
      tag: "Lịch dày",
      text: "Tuần này nhiều việc sát hạn nên app rút bớt khoảng nghỉ đệm để bạn vẫn làm kịp.",
    };
  }
  if (code === "OVERRUN_EXTENSION" || code === "MOVED_BY_REPAIR") {
    return {
      tag: "Điều chỉnh lịch",
      text: "Đã tự động sắp xếp lại khung giờ sau khi cập nhật lịch trình hoặc thời lượng.",
    };
  }
  if (
    ["SCORED_GREEDY", "HYBRID_ALNS", "BACKTRACK", "WSPT", "LST", "EDF", "EARLIEST_FREE_GAP"].includes(code) ||
    rawText.trim().startsWith("[")
  ) {
    const prio = Number(reasonObj?.priority ?? block?.priority ?? 3);
    const prioText = prio >= 5 ? "rất cao" : prio === 4 ? "cao" : prio === 3 ? "trung bình" : "linh hoạt";
    return {
      tag: "Ưu tiên xếp lịch",
      text: `Việc này có mức ưu tiên ${prioText} (${loadDesc.toLowerCase()}) nên được xếp vào ${slotEnergyDesc}.`,
    };
  }

  return {
    tag: "Lý do xếp lịch",
    text: humanizeWeekdaysVi(rawText.replace(/^\[[^\]]+\]\s*/, "").trim() || "Phù hợp với quỹ thời gian trống hiện có của bạn."),
  };
}

export function renderBlockInspectorModal(modalEl, block, focusSection, callbacks) {
  const isDev = Boolean(state.developerMode);
  const nowSlot = resolveNowSlot(state.commitments);
  const pinnedIds = new Set((state.pinnedBlocks || []).map((b) => b.block_id));
  const isPinned = pinnedIds.has(block.block_id) || block.state === "PINNED";
  const doneInfo = state.completedBlocks[block.block_id];
  const srcTask = state.tasks.find((t) => t.task_id === block.task_id);
  const currentTaskDur = Math.max(15, Number(srcTask?.duration_min || block.duration_min || 60));
  const load = Number(block.cognitive_load || 2);
  const energyVal = Number(block.energy_level);
  const userEnergyLabel = Number.isFinite(energyVal)
    ? energyVal >= 2.5
      ? "Giờ tỉnh táo cao"
      : energyVal >= 1.7
        ? "Giờ tập trung vừa"
        : "Giờ năng lượng thấp"
    : "Khung giờ trong ngày";

  const reasonsHtml = (block.reasons || []).length
    ? (block.reasons || [])
        .map((r) => {
          if (isDev) {
            const code = typeof r === "string" ? "REASON" : r.code || "INFO";
            const text = typeof r === "string" ? r : r.text || JSON.stringify(r);
            return `<div class="summary-row" style="align-items:flex-start;">
              <span class="badge badge-neutral mono">${esc(code)}</span>
              <span style="flex:1;">${esc(text)}</span>
            </div>`;
          }
          const friendly = _humanizeBlockReason(r, block);
          return `<div class="summary-row" style="align-items:flex-start;">
            <span class="badge badge-neutral">${esc(friendly.tag)}</span>
            <span style="flex:1;">${esc(friendly.text)}</span>
          </div>`;
        })
        .join("")
    : `<div style="font-size:12.5px;color:var(--p-muted);">${
        isDev
          ? `Xếp theo thứ tự ưu tiên của thuật toán ${esc(state.activeSolver)}.`
          : "Được xếp vào khung giờ trống phù hợp nhất với độ ưu tiên và hạn hoàn thành của bạn."
      }</div>`;

  modalEl.querySelector("#blockModalTitle").textContent = block.title || block.task_id;
  const body = modalEl.querySelector("#blockModalBody");
  body.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
      <span class="badge badge-dark mono">${esc(isDev ? block.day : humanizeWeekdaysVi(block.day))} ${esc(block.start_time)}–${esc(block.end_time)} (${block.duration_min}p)</span>
      <span class="badge badge-neutral">${esc(CATEGORY_LABELS[block.category] || block.category)}</span>
      <span class="badge ${load === 3 ? "badge-danger" : load === 2 ? "badge-warn" : "badge-ok"}">${isDev ? LOAD_LABELS[load] || `L${load}` : USER_LOAD_LABELS[load] || "Mức vừa"}</span>
      <span class="badge badge-info">${isDev ? `Năng lượng E${block.energy_level || "?"}` : esc(userEnergyLabel)}</span>
      <span class="badge badge-neutral">${esc(formatDeadlineCountdown(block.deadline_slot, nowSlot))}</span>
      ${isPinned ? `<span class="badge badge-dark">📌 Đã ghim</span>` : ""}
    </div>

    <!-- Tại sao xếp giờ này? -->
    <div style="display:flex;flex-direction:column;gap:6px;">
      <h4>${isDev ? "Tại sao thuật toán xếp giờ này?" : "Vì sao ứng dụng chọn khung giờ này?"}</h4>
      <div style="display:flex;flex-direction:column;gap:6px;">${reasonsHtml}</div>
    </div>

    <!-- Check-in thực tế & Điều chỉnh thời lượng -->
    <div class="form-grid-2">
      <div class="card" style="padding:14px;display:flex;flex-direction:column;gap:8px;" id="secCheckinM7">
        <h4>${isDev ? "Check-in thời gian thực tế (M7)" : "Xác nhận hoàn thành"}</h4>
        <div class="field">
          <label for="inpActualMin">Số phút thực tế bạn đã làm</label>
          <input type="number" id="inpActualMin" class="input mono" min="5" step="5" value="${doneInfo?.actual_min || block.duration_min}" />
        </div>
        <button type="button" class="btn btn-primary btn-sm" id="btnSubmitCheckin">${isDev ? "Ghi nhận hoàn thành M7 (xóa khỏi lịch)" : "Đã làm xong &amp; xóa khỏi lịch"}</button>
        <span style="font-size:11px;color:var(--p-muted);">Lưu thời gian thực tế và giải phóng khung giờ cho việc khác.</span>
      </div>

      <div class="card" style="padding:14px;display:flex;flex-direction:column;gap:10px;">
        <h4>${isDev ? "Báo phát sinh / Đặt lại thời lượng" : "Thay đổi thời lượng việc này"}</h4>
        <div class="field">
          <label for="inpOverrunExtra">Cần thêm bao nhiêu phút phát sinh?</label>
          <div style="display:flex;gap:6px;align-items:center;">
            <input type="number" id="inpOverrunExtra" class="input mono" min="15" step="15" value="30" style="width:92px;" />
            <button type="button" class="btn btn-danger btn-sm" id="btnTriggerOverrun" style="flex:1;">Thêm giờ &amp; xếp lại</button>
          </div>
        </div>
        <div class="field" style="border-top:1px solid var(--p-line);padding-top:10px;">
          <label for="inpSetTaskDuration">Tự đặt lại tổng thời lượng (phút)</label>
          <div style="display:flex;gap:6px;align-items:center;">
            <input type="number" id="inpSetTaskDuration" class="input mono" min="15" step="15" value="${currentTaskDur}" style="width:92px;" />
            <button type="button" class="btn btn-sm" id="btnSetTaskDuration" style="flex:1;border-color:var(--p-accent);color:var(--p-accent);">Đặt thời lượng mới</button>
          </div>
          <span style="font-size:11px;color:var(--p-muted);">Đang đặt: ${currentTaskDur}p (làm tròn lên bội 15p &amp; tự xếp lại lịch).</span>
        </div>
      </div>
    </div>

    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;padding-top:8px;border-top:1px solid var(--p-line);">
      <button type="button" class="btn" id="btnModalTogglePin">${isPinned ? "Bỏ ghim cố định" : isDev ? "Ghim cố định giờ này (PINNED)" : "Ghim cố định khung giờ này"}</button>
      <button type="button" class="btn btn-ghost" id="btnCloseBlockModalFooter">Đóng</button>
    </div>
  `;

  body.querySelector("#btnModalTogglePin").addEventListener("click", () => callbacks.onTogglePin(block.block_id));
  body.querySelector("#btnSubmitCheckin").addEventListener("click", () => {
    const actualMin = Number(body.querySelector("#inpActualMin").value) || block.duration_min;
    callbacks.onCheckinBlock(block, actualMin);
  });
  body.querySelector("#btnTriggerOverrun").addEventListener("click", () => {
    const extraMin = Math.max(15, Number(body.querySelector("#inpOverrunExtra").value) || 30);
    callbacks.onOverrunBlock(block, extraMin);
  });
  body.querySelector("#btnSetTaskDuration").addEventListener("click", () => {
    const rawMin = Number(body.querySelector("#inpSetTaskDuration").value);
    if (!Number.isFinite(rawMin) || rawMin < 15) {
      showToast("Thời lượng mới phải tối thiểu 15 phút.", "danger");
      return;
    }
    const targetMin = Math.max(15, Math.ceil(rawMin / 15) * 15);
    callbacks.onSetTaskDuration?.(block, targetMin);
  });
  body.querySelector("#btnCloseBlockModalFooter").addEventListener("click", () => callbacks.onClose());

  if (focusSection === "checkin") {
    body.querySelector("#inpActualMin")?.focus();
  }
}

export function renderDisruptionModal(modalEl, callbacks) {
  const isDev = Boolean(state.developerMode);
  const preset = state.disruptionPreset || {
    title: "Họp nhóm đột xuất khẩn cấp",
    day_of_week: "Tuesday",
    start_time: "14:00",
    end_time: "16:00",
  };
  const body = modalEl.querySelector("#disruptionModalBody");
  body.innerHTML = `
    <p style="font-size:13px;color:var(--p-muted);">
      ${
        isDev
          ? "Chèn một sự kiện đột xuất vào lịch và chạy <strong>Local Repair (Sửa cục bộ giữ ổn định)</strong> hoặc <strong>Full Rebuild</strong> qua <code>POST /api/repair</code>."
          : "Thêm một việc đột xuất vào lịch và chọn cách sắp xếp lại các buổi bị trùng sao cho ít xáo trộn nhất."
      }
    </p>
    <form id="frmDisruption" style="display:flex;flex-direction:column;gap:12px;">
      <div class="field">
        <label for="inpDisTitle">Tên sự cố / Việc đột xuất</label>
        <input type="text" id="inpDisTitle" class="input" value="${esc(preset.title)}" required />
      </div>
      <div class="form-grid-3">
        <div class="field">
          <label for="inpDisDay">Thứ</label>
          <select id="inpDisDay" class="select">
            ${WEEKDAYS_EN.map((d) => `<option value="${d}" ${preset.day_of_week === d ? "selected" : ""}>${esc(isDev ? d : humanizeWeekdaysVi(d))}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="inpDisStart">Từ giờ</label>
          <input type="time" id="inpDisStart" class="input mono" value="${esc(preset.start_time || "14:00")}" required />
        </div>
        <div class="field">
          <label for="inpDisEnd">Đến giờ</label>
          <input type="time" id="inpDisEnd" class="input mono" value="${esc(preset.end_time || "16:00")}" required />
        </div>
      </div>
      <div class="field">
        <label for="inpDisMode">Chế độ sửa lịch</label>
        <select id="inpDisMode" class="select">
          <option value="LOCAL_INSERTION">${isDev ? "Local Repair (Ưu tiên giữ nguyên các block không bị đụng)" : "Sửa cục bộ (Giữ nguyên các buổi không bị trùng)"}</option>
          <option value="RIPPLE_SHIFT">${isDev ? "Ripple Shift (Đẩy tịnh tiến dây chuyền)" : "Dời dây chuyền (Đẩy nối tiếp các buổi phía sau)"}</option>
          <option value="FULL_REBUILD">${isDev ? "Full Rebuild (Xếp lại toàn bộ tuần)" : "Sắp xếp lại toàn bộ tuần"}</option>
        </select>
      </div>
      <div style="display:flex;justify-content:flex-end;gap:8px;">
        <button type="button" class="btn" id="btnCancelDisruption">Hủy</button>
        <button type="submit" class="btn btn-primary">Chạy sửa lịch</button>
      </div>
    </form>
  `;

  body.querySelector("#btnCancelDisruption").addEventListener("click", () => callbacks.onClose());
  body.querySelector("#frmDisruption").addEventListener("submit", (ev) => {
    ev.preventDefault();
    callbacks.onRunRepair({
      new_event: {
        event_id: `URG_${Date.now().toString().slice(-4)}`,
        title: body.querySelector("#inpDisTitle").value.trim(),
        day_of_week: body.querySelector("#inpDisDay").value,
        start_time: body.querySelector("#inpDisStart").value,
        end_time: body.querySelector("#inpDisEnd").value,
      },
      mode: body.querySelector("#inpDisMode").value,
    });
  });
}

export function renderOverloadModal(modalEl, callbacks) {
  const isDev = Boolean(state.developerMode);
  const sched = state.currentSchedule;
  const options = sched?.overload_options || [
    { option_id: "O1", code: "DEFER_LOW_PRIORITY", title: "Tạm hoãn việc ít quan trọng hơn", description: "Giữ lại các việc quan trọng để kịp hạn chót." },
    { option_id: "O2", code: "REDUCE_SCOPE", title: "Rút gọn thời lượng dự kiến", description: "Giảm thời lượng việc linh hoạt cho vừa quỹ thời gian." },
    { option_id: "O3", code: "SPLIT_CHUNKS", title: "Bật chia nhỏ thành nhiều buổi", description: "Cho phép cắt nhỏ các việc dài để lấp vừa khe trống." },
    { option_id: "O4", code: "RELAX_BUFFER", title: "Giảm bớt thời gian dự phòng", description: "Giải phóng thêm thời gian trống trong tuần quá tải." },
  ];

  const body = modalEl.querySelector("#overloadModalBody");
  body.innerHTML = `
    <p style="font-size:13px;color:var(--p-muted);">
      Chọn một phương án để <strong>xem thử trực tiếp bằng khối nét đứt</strong> trên lịch trước khi quyết định áp dụng${
        isDev ? " (<code>POST /api/overload/preview</code>)" : ""
      }.
    </p>
    <div style="display:flex;flex-direction:column;gap:8px;">
      ${options
        .map(
          (opt, idx) => `
          <div class="card interactive-card" style="padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;">
            <div style="flex:1;min-width:220px;">
              <strong>${esc(opt.title || opt.label || opt.option_id || `O${idx + 1}`)}</strong>
              <div style="font-size:12px;color:var(--p-muted);margin-top:2px;">${esc(opt.description || opt.summary || opt.rationale || "")}</div>
            </div>
            <button type="button" class="btn btn-primary btn-sm" data-preview-opt="${esc(opt.option_id || `O${idx + 1}`)}" data-preview-code="${esc(opt.code || opt.option_code || "")}" data-preview-task="${esc(opt.target_task_id || "")}">
              👁️ Xem thử
            </button>
          </div>`
        )
        .join("")}
    </div>
  `;

  body.querySelectorAll("[data-preview-opt]").forEach((btn) => {
    btn.addEventListener("click", () => {
      callbacks.onPreviewOption(
        btn.getAttribute("data-preview-opt"),
        btn.getAttribute("data-preview-code") || null,
        btn.getAttribute("data-preview-task") || null
      );
    });
  });
}
