/**
 * View 4: All-Solvers Benchmark Table & Full Dev Glossary (POST /api/benchmark-all).
 * Mirrors Solver_Benchmark_Report.md + Testing_System lexicographic ranking & ICEE critiques.
 */

import { state } from "./state.js";
import { esc, getVerdictBadge } from "./utils.js";

function fmtPct(v) {
  return v === null || v === undefined ? "—" : `${Number(v).toFixed(1)}%`;
}

function fmtNum(v, suffix = "") {
  return v === null || v === undefined ? "—" : `${Number(v).toFixed(1)}${suffix}`;
}

export function renderBenchmarkView(container, callbacks) {
  const data = state.benchmarkData;
  if (!data) {
    container.innerHTML = `
      <div class="card" style="padding:32px;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;">
        <div>
          <h2>📊 Chấm Điểm & Đối Chiếu Tất Cả Thuật Toán</h2>
          <p style="color:var(--p-muted);margin-top:6px;">
            Chạy cùng lúc mọi thuật toán hiện có trên cùng input, chấm bằng <code>Testing_System.ScheduleEvaluator</code>,
            xếp hạng theo Thứ tự Từ Điển và nạp cache để bạn chuyển đổi lịch giữa các thuật trong <strong>0ms</strong>.
          </p>
        </div>
        <button type="button" class="btn btn-primary" id="btnRunBenchmarkNow">📊 Chạy Chấm Điểm Ngay</button>
      </div>`;
    container.querySelector("#btnRunBenchmarkNow")?.addEventListener("click", () => callbacks.onRunBenchmarkAll());
    return;
  }

  const ranking = data.ranking || [];
  const glossaryCols = data.column_glossary || [];
  const lexOrder = data.lexicographic_order || [];
  const verdictDefs = data.verdict_definitions || [];
  const q = (state.glossaryFilter || "").trim().toLowerCase();
  const filteredCols = q
    ? glossaryCols.filter((c) =>
        `${c.symbol} ${(c.json_fields || []).join(" ")} ${c.dev_meaning} ${c.student_impact}`.toLowerCase().includes(q)
      )
    : glossaryCols;

  const rowsHtml = ranking
    .map((r) => {
      const vb = getVerdictBadge(r.verdict);
      const isExpanded = Boolean(state.expandedIceeSolvers[r.solver_key]);
      const g1Cls = r.g1_violations > 0 ? "cell-crit" : "cell-ok";
      const p1Cls = r.p1_value_rate_pct < 100 ? (r.is_structurally_overloaded ? "cell-warn" : "cell-crit") : "cell-ok";
      const shkCls = r.p4_shock25_survived_pct < 70 ? "cell-crit" : r.p4_shock25_survived_pct < 85 ? "cell-warn" : "cell-ok";
      const recCls = r.p2_recovery_rate_pct !== null && r.p2_recovery_rate_pct < 100 ? "cell-warn" : "cell-ok";
      const pkCls =
        r.p2_forced_phase_advance > 0 || (r.p2_heavy_peak_pct !== null && r.p2_heavy_peak_pct < 25)
          ? "cell-crit"
          : r.p2_heavy_peak_pct !== null && r.p2_heavy_peak_pct < 50
            ? "cell-warn"
            : "cell-ok";
      const l10Cls =
        r.p1_unjustified_last10h_pct > 50 ? "cell-crit" : r.p1_unjustified_last10h_pct > 25 ? "cell-warn" : "cell-ok";
      const corne = r.p3_corne_vector || [0, 0, 0];
      const crnCls = corne[0] > 0 ? "cell-warn" : corne[1] > 0 || corne[2] > 0 ? "cell-warn" : "";
      const sjlCls = r.p2_sjl_minutes !== null && r.p2_sjl_minutes > 30 ? "cell-warn" : "";
      const msCls = r.exec_ms > 2000 ? "cell-crit" : r.exec_ms > 1000 ? "cell-warn" : "";

      const critiques = r.d1_icee_critiques || [];
      const iceeRow = isExpanded
        ? `<tr class="icee-row">
            <td colspan="14">
              <div style="display:flex;flex-direction:column;gap:8px;">
                <div style="font-size:12.5px;">
                  <strong>Lý do kết luận (${esc(r.solver_key)}):</strong>
                  ${(r.verdict_reasons_vi || []).map((x) => esc(x)).join(" · ") || "Không có ghi chú."}
                </div>
                ${
                  critiques.length > 0
                    ? `<div class="icee-list">
                        ${critiques
                          .map(
                            (c) => `<div class="icee-item">
                              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
                                <span class="badge ${c.severity === "CRITICAL" ? "badge-danger" : c.severity === "WARNING" ? "badge-warn" : "badge-info"}">${esc(c.severity)} · ${esc(c.pillar)}</span>
                                <strong>${esc(c.summary_vi)}</strong>
                              </div>
                              <div style="font-size:12px;color:var(--p-ink-soft);">${esc(c.rationale_vi)}</div>
                              <div style="font-size:12px;color:var(--p-accent);"><strong>Gợi ý sửa:</strong> ${esc(c.suggested_action_vi)}</div>
                              <div style="font-size:11px;color:var(--p-muted);">Nguồn học thuật: ${esc(c.paper_reference)}</div>
                            </div>`
                          )
                          .join("")}
                      </div>`
                    : `<div style="font-size:12.5px;color:var(--st-ok);font-weight:600;">✔️ Không có cảnh báo ICEE nào — đạt chuẩn sạch trên mọi trụ cột.</div>`
                }
              </div>
            </td>
          </tr>`
        : "";

      return `
        <tr>
          <td class="mono" style="font-weight:700;">#${r.lexicographic_rank}</td>
          <td>
            <button type="button" class="solver-link-btn mono" data-jump-solver="${esc(r.solver_key)}" title="Xem lịch chi tiết của ${esc(r.solver_key)} (0ms từ cache)">
              ${esc(r.solver_key)}
            </button>
          </td>
          <td><span class="badge ${vb.cls}" title="${esc(vb.label)}">${vb.short}</span></td>
          <td class="mono ${g1Cls}">${r.g1_violations}</td>
          <td class="mono ${p1Cls}">${fmtPct(r.p1_value_rate_pct)}</td>
          <td class="mono ${shkCls}">${fmtPct(r.p4_shock25_survived_pct)}</td>
          <td class="mono ${recCls}">${fmtPct(r.p2_recovery_rate_pct)} <div style="font-size:10.5px;color:var(--p-muted)">max ${r.p2_max_uninterrupted_min}p</div></td>
          <td class="mono ${pkCls}">${r.p2_forced_phase_advance} / ${fmtPct(r.p2_heavy_peak_pct)}</td>
          <td class="mono ${l10Cls}">${fmtPct(r.p1_unjustified_last10h_pct)}</td>
          <td class="mono ${crnCls}">${corne.join("/")} <div style="font-size:10.5px;color:var(--p-muted)">max ${r.p3_max_daily_study_min}p</div></td>
          <td class="mono">${r.p3_context_switches} / ${r.p3_batched_pairs}</td>
          <td class="mono">${fmtPct(r.p1_habit_rate_pct)} / ${fmtPct(r.p2_preferred_window_pct)}</td>
          <td class="mono ${sjlCls}">${fmtNum(r.p2_sjl_minutes, "p")} / ${fmtNum(r.p3_daily_load_std_min, "p")}</td>
          <td class="mono ${msCls}">
            <div>${Number(r.exec_ms).toFixed(1)}ms</div>
            <button type="button" class="btn btn-sm" style="margin-top:4px;min-height:24px;font-size:11px;padding:0 7px;" data-toggle-icee="${esc(r.solver_key)}">
              ${isExpanded ? "Ẩn ICEE" : `ICEE (${critiques.length})`}
            </button>
          </td>
        </tr>
        ${iceeRow}`;
    })
    .join("");

  const lexHtml = lexOrder
    .map(
      (item) => `
      <div class="card" style="padding:10px 12px;display:flex;gap:10px;align-items:flex-start;">
        <span class="badge badge-dark mono">#${item.rank}</span>
        <div>
          <strong style="font-size:12.5px;">${esc(item.key)}</strong>
          <div style="font-size:12px;color:var(--p-muted);margin-top:2px;">${esc(item.note)}</div>
        </div>
      </div>`
    )
    .join("");

  const glossaryRowsHtml = filteredCols
    .map(
      (c) => `
      <tr>
        <td class="mono" style="font-weight:700;white-space:nowrap;">${esc(c.symbol)}</td>
        <td class="mono" style="font-size:11.5px;color:var(--p-ink-soft);">${(c.json_fields || []).map((f) => `<div>${esc(f)}</div>`).join("")}</td>
        <td style="font-size:12px;">
          <div><strong style="color:var(--st-danger);">CRIT:</strong> ${esc(c.critical_threshold)}</div>
          <div><strong style="color:var(--st-warn);">WARN:</strong> ${esc(c.warning_threshold)}</div>
        </td>
        <td style="font-size:12.5px;">${esc(c.dev_meaning)}</td>
        <td style="font-size:12.5px;color:var(--p-ink-soft);">${esc(c.student_impact)}</td>
      </tr>`
    )
    .join("");

  const verdictHtml = verdictDefs
    .map((v) => {
      const cls =
        v.tone === "success"
          ? "badge-ok"
          : v.tone === "warning"
            ? "badge-warn"
            : v.tone === "info"
              ? "badge-info"
              : "badge-danger";
      return `
        <div class="card" style="padding:12px 14px;display:flex;flex-direction:column;gap:6px;">
          <div style="display:flex;align-items:center;gap:8px;">
            <span class="badge ${cls}">${esc(v.short)}</span>
            <strong class="mono" style="font-size:12px;">${esc(v.label)}</strong>
          </div>
          <p style="font-size:12.5px;color:var(--p-ink-soft);">${esc(v.meaning)}</p>
        </div>`;
    })
    .join("");

  container.innerHTML = `
    <div class="section-head">
      <div>
        <h2>Bảng Chấm Điểm & Xếp Hạng Thuật Toán (${ranking.length} thuật toán)</h2>
        <p>Xếp hạng từ #1 đến #${ranking.length} theo <strong>Thứ tự Từ Điển</strong> của <code>Testing_System</code>. Click vào tên thuật toán để xem lịch chi tiết tức thì (0ms).</p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button type="button" class="btn btn-sm" id="btnBenchBack">← Quay lại lịch</button>
        <button type="button" class="btn btn-primary btn-sm" id="btnRerunBenchmark">Chấm lại tất cả</button>
      </div>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>Hạng</th>
            <th>Thuật toán</th>
            <th>Verdict</th>
            <th title="Hard constraint violations">(G1)</th>
            <th title="Deadline priority satisfaction %">P1.1%</th>
            <th title="Priority survival under +25% duration shock">Shk25%</th>
            <th title="Heavy recovery >10m / max uninterrupted streak">Rec%</th>
            <th title="Forced phase advance / Heavy peak match %">Adv / Pk%</th>
            <th title="Unjustified <10h deadline crowding %">&lt;10h%</th>
            <th title="Corne vector [>2/day, adjacent, meal] / max daily study">Crn (d/a/m)</th>
            <th title="Context switches / batched pairs">Ctx / Bch</th>
            <th title="Habit completion / preferred window match">Hab / Prf%</th>
            <th title="Social Jetlag |SJL| / Daily load std">SJL / Std</th>
            <th>ms & ICEE</th>
          </tr>
        </thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>

    <!-- PHẦN B: PHỤ LỤC CHO DEV -->
    <section style="display:flex;flex-direction:column;gap:14px;margin-top:6px;">
      <div class="section-head">
        <div>
          <h2>Phụ Lục So Sánh Dành Cho Dev (Chuẩn Solver Benchmark Report)</h2>
          <p>Giải thích đầy đủ thứ tự ưu tiên phân thắng-bại, tên biến JSON gốc, ngưỡng thẻ đỏ/thẻ vàng và ý nghĩa từng cột.</p>
        </div>
      </div>

      <div>
        <h3 style="margin-bottom:8px;">1. Thứ Tự Ưu Tiên Xếp Hạng Từ Điển (Cổng #0 → Tiêu Chí #11)</h3>
        <div class="glossary-grid">${lexHtml}</div>
      </div>

      <div>
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;margin-bottom:8px;">
          <h3>2. Từ Điển Biến & Ý Nghĩa Con Số Cho Dev (${filteredCols.length}/${glossaryCols.length} nhóm cột)</h3>
          <input type="search" class="input" id="inpGlossaryFilter" placeholder="Lọc ký hiệu cột hoặc tên biến JSON..." value="${esc(state.glossaryFilter)}" style="width:260px;min-height:32px;" />
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Ký hiệu cột</th>
                <th>Tên biến gốc JSON (schemas.py)</th>
                <th>Ngưỡng CRITICAL / WARNING</th>
                <th>Ý nghĩa con số để Dev so sánh thuật toán</th>
                <th>Tác dụng thực tế với sinh viên</th>
              </tr>
            </thead>
            <tbody>${glossaryRowsHtml}</tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 style="margin-bottom:8px;">3. Giải Thích 5 Nhãn Kết Luận (Verdict)</h3>
        <div class="glossary-grid">${verdictHtml}</div>
      </div>
    </section>
  `;

  container.querySelector("#btnBenchBack")?.addEventListener("click", () => callbacks.onBackToCalendar?.());
  container.querySelector("#btnRerunBenchmark")?.addEventListener("click", () => callbacks.onRunBenchmarkAll());
  container.querySelector("#inpGlossaryFilter")?.addEventListener("input", (e) => {
    state.glossaryFilter = e.target.value;
    renderBenchmarkView(container, callbacks);
  });

  container.querySelectorAll("[data-jump-solver]").forEach((btn) => {
    btn.addEventListener("click", () => {
      callbacks.onSelectSolver(btn.getAttribute("data-jump-solver"), true);
    });
  });

  container.querySelectorAll("[data-toggle-icee]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const k = btn.getAttribute("data-toggle-icee");
      state.expandedIceeSolvers[k] = !state.expandedIceeSolvers[k];
      renderBenchmarkView(container, callbacks);
    });
  });
}
