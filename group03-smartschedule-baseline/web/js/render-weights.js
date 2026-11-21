/**
 * View 3: Solver Input Weights & Formula Glossary (POST /api/solver-weights).
 */

import { state } from "./state.js";
import { CATEGORY_LABELS, WINDOW_LABELS, esc } from "./utils.js";

export function renderWeightsView(container, callbacks) {
  const data = state.weightsData;
  if (!data) {
    container.innerHTML = `
      <div class="card" style="padding:28px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
        <div>
          <h3>Đang sẵn sàng tính trọng số thuật toán</h3>
          <p style="color:var(--p-muted);margin-top:4px;">Bấm nút bên cạnh để đọc toàn bộ trọng số quy đổi từ input hiện tại và <code>src/config.py</code>.</p>
        </div>
        <button type="button" class="btn btn-primary" id="btnFetchWeights">🎛️ Tính trọng số hiện tại</button>
      </div>`;
    container.querySelector("#btnFetchWeights")?.addEventListener("click", () => callbacks.onRefreshWeights());
    return;
  }

  const pw = data.profile_weights;
  const cfg = data.config_constants;
  const tasks = data.per_task_weights || [];
  const glossary = data.weights_glossary || [];
  const q = (state.weightsGlossaryFilter || "").trim().toLowerCase();
  const filteredGlossary = q
    ? glossary.filter((g) => `${g.name} ${g.formula} ${g.definition_vi} ${g.decision_impact_vi}`.toLowerCase().includes(q))
    : glossary;

  const taskRowsHtml = tasks
    .map(
      (t) => `
      <tr>
        <td>
          <strong>${esc(t.title)}</strong>
          <div class="mono" style="font-size:11px;color:var(--p-muted);">${esc(t.task_id)} · ${esc(CATEGORY_LABELS[t.category] || t.category)}</div>
        </td>
        <td class="mono">${t.duration_min}p × <strong>${t.buffer_multiplier}</strong> → <strong>${t.planned_duration_min}p</strong> <span style="color:var(--p-muted)">(${t.planned_slots} sl)</span></td>
        <td class="mono">P${t.priority} · L${t.cognitive_load ?? "—"}</td>
        <td class="mono">${esc(t.deadline_label)}<div style="font-size:11px;color:var(--p-muted)">slack: ${t.slack_hours !== null ? `${t.slack_hours}h` : "∞"} · DAG↓ ${t.descendant_count}</div></td>
        <td class="mono" style="font-weight:700;color:var(--p-accent);">${t.urgency_score}</td>
        <td class="mono">${t.smith_ratio}</td>
        <td class="mono">${t.dynamic_slack_slots !== null ? `${t.dynamic_slack_slots} sl` : "∞"}</td>
        <td class="mono" style="font-size:11.5px;">${esc(t.edf_key)}</td>
        <td style="font-size:12px;">
          <div>${esc(WINDOW_LABELS[t.preferred_window] || t.preferred_window)}</div>
          <div class="mono" style="font-size:11px;color:var(--p-muted)">${t.is_splittable ? `${t.min_chunk_min}–${t.max_chunk_min}p` : "Liền khối"}</div>
        </td>
      </tr>`
    )
    .join("");

  const curve = pw.circadian_curve || {};
  const levelLabel = (lv) => (lv === 3 ? "3 · Peak" : lv === 2 ? "2 · Vừa" : "1 · Thấp");
  const levelCls = (lv) => (lv === 3 ? "badge-info" : lv === 2 ? "badge-ok" : "badge-neutral");

  const configRowsHtml = Object.entries(cfg)
    .map(
      ([k, v]) => `
      <tr>
        <td class="mono" style="font-weight:600;">${esc(k)}</td>
        <td class="mono">${esc(v)}</td>
      </tr>`
    )
    .join("");

  const glossaryRowsHtml = filteredGlossary
    .map(
      (g) => `
      <tr>
        <td class="mono" style="font-weight:700;white-space:nowrap;">${esc(g.name)}</td>
        <td class="mono" style="font-size:11.5px;">${esc(g.formula)}</td>
        <td>${esc(g.definition_vi)}</td>
        <td>${esc(g.decision_impact_vi)}</td>
      </tr>`
    )
    .join("");

  container.innerHTML = `
    <div class="section-head">
      <div>
        <h2>Trọng Số Đầu Vào Của Thuật Toán & Hệ Số Hệ Thống</h2>
        <p>Hiển thị trực tiếp các giá trị quy đổi từ input hiện tại và <code>src/config.py</code> — minh bạch lý do thuật toán xếp thứ tự & chọn khe giờ.</p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button type="button" class="btn btn-sm" id="btnWeightsBack">← Quay lại lịch</button>
        <button type="button" class="btn btn-sm btn-primary" id="btnRefreshWeights">Làm mới trọng số</button>
      </div>
    </div>

    <div class="kpi-grid">
      <div class="card kpi-card">
        <span class="kpi-label">Mật độ tải hạn chót (ρ_deadline)</span>
        <span class="kpi-val mono" style="color:${pw.rho_deadline > 1 ? "var(--st-danger)" : pw.rho_deadline > 0.8 ? "var(--st-warn)" : "var(--p-accent)"}">${(pw.rho_deadline * 100).toFixed(1)}%</span>
        <span class="kpi-sub mono">${pw.deadline_planned_slots} / ${pw.usable_free_slots} slot khả dụng</span>
      </div>
      <div class="card kpi-card">
        <span class="kpi-label">Mật độ tải toàn bộ (ρ_total)</span>
        <span class="kpi-val mono">${(pw.rho_total * 100).toFixed(1)}%</span>
        <span class="kpi-sub mono">${pw.total_planned_slots} slot nhu cầu (${pw.total_tasks_expanded} việc gồm habit)</span>
      </div>
      <div class="card kpi-card">
        <span class="kpi-label">Chế độ đệm phòng vệ (Buffer)</span>
        <span class="kpi-val" style="font-size:17px;">${esc(pw.buffer_mode)}</span>
        <span class="kpi-sub mono">α_light=${pw.alpha_light} · α_heavy=${pw.alpha_heavy} · habit=${esc(pw.estimate_habit || "NONE")}</span>
      </div>
      <div class="card kpi-card">
        <span class="kpi-label">Cửa sổ lập lịch</span>
        <span class="kpi-val mono">${pw.horizon_days} ngày (${pw.horizon_slots} sl)</span>
        <span class="kpi-sub mono">now_slot=${pw.now_slot} · free_raw=${pw.free_slots} sl</span>
      </div>
    </div>

    <div class="card" style="padding:14px 16px;display:flex;flex-direction:column;gap:10px;">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
        <strong>Bảng 2A — Đường cong Năng lượng Sinh học (CircadianEnergyProfile: ${esc(pw.focus_preference)})</strong>
        <span class="badge badge-neutral">15 phút = 1 slot · 96 slot/ngày</span>
      </div>
      <div class="circadian-bars">
        <div class="circ-slot">
          <span>Sáng (06:00–12:00)</span>
          <strong style="margin-top:4px;"><span class="badge ${levelCls(curve.morning_06_12)}">${levelLabel(curve.morning_06_12)}</span></strong>
        </div>
        <div class="circ-slot">
          <span>Chiều (12:00–18:00)</span>
          <strong style="margin-top:4px;"><span class="badge ${levelCls(curve.afternoon_12_18)}">${levelLabel(curve.afternoon_12_18)}</span></strong>
        </div>
        <div class="circ-slot">
          <span>Tối (18:00–24:00)</span>
          <strong style="margin-top:4px;"><span class="badge ${levelCls(curve.evening_18_24)}">${levelLabel(curve.evening_18_24)}</span></strong>
        </div>
        <div class="circ-slot">
          <span>Đêm (00:00–06:00)</span>
          <strong style="margin-top:4px;"><span class="badge ${levelCls(curve.night_00_06)}">${levelLabel(curve.night_00_06)}</span></strong>
        </div>
      </div>
    </div>

    <div>
      <h3 style="margin-bottom:8px;">Bảng 1 — Trọng Số Từng Công Việc Mà Các Thuật Toán Nhìn Thấy (${tasks.length} mục)</h3>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>Công việc</th>
              <th>Gốc × α → Planned</th>
              <th>P / Load</th>
              <th>Hạn chót · Slack · DAG</th>
              <th>Urgency (SCORED)</th>
              <th>Smith (WSPT)</th>
              <th>Dyn. Slack (LST)</th>
              <th>EDF Key</th>
              <th>Khung giờ / Chia phiên</th>
            </tr>
          </thead>
          <tbody>
            ${taskRowsHtml || `<tr><td colspan="9" style="text-align:center;color:var(--p-muted);padding:20px;">Chưa có công việc nào trong input hiện tại.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>

    <div class="form-grid-2">
      <div>
        <h3 style="margin-bottom:8px;">Bảng 2B — Hằng Số Đang Đọc Từ <code>src/config.py</code></h3>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr><th>Hằng số</th><th>Giá trị hiện hành</th></tr>
            </thead>
            <tbody>${configRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div style="display:flex;flex-direction:column;gap:8px;">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;">
          <h3>Phụ Lục — Định Nghĩa Trọng Số & Tác Động</h3>
          <input type="search" class="input" id="inpWeightsGlossaryFilter" placeholder="Lọc biến trọng số..." value="${esc(state.weightsGlossaryFilter)}" style="width:200px;min-height:30px;" />
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Tên trọng số / Biến</th>
                <th>Giá trị / Công thức</th>
                <th>Định nghĩa dễ hiểu</th>
                <th>Thuật toán dùng để quyết định gì?</th>
              </tr>
            </thead>
            <tbody>${glossaryRowsHtml}</tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  container.querySelector("#btnWeightsBack")?.addEventListener("click", () => callbacks.onBackToCalendar?.());
  container.querySelector("#btnRefreshWeights")?.addEventListener("click", () => callbacks.onRefreshWeights());
  container.querySelector("#inpWeightsGlossaryFilter")?.addEventListener("input", (e) => {
    state.weightsGlossaryFilter = e.target.value;
    renderWeightsView(container, callbacks);
  });
}
