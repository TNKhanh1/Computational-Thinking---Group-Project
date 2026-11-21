/**
 * View 5: "Bộ test so sánh" — curated Testing_System cases where the 6 solvers diverge.
 * GET /api/test-showcase (instant list) → GET /api/test-showcase/{i} (solve + evaluate + rank, cached server-side).
 * Every table is followed by an explanation generated server-side from the evaluation numbers.
 */

import { state } from "./state.js";
import { esc, getVerdictBadge } from "./utils.js";
import { api } from "./api.js";

// Column spec: key, header, tooltip, unit, direction (+1 higher is better, -1 lower is better, 0 = no best/worst)
const COLUMNS = [
  { key: "p1_pct", head: "P1.1%", tip: "Điểm priority các việc có hạn được xếp kịp hạn", unit: "%", dir: 1 },
  { key: "shock25_pct", head: "Shk25%", tip: "Priority còn kịp hạn khi mọi việc lố +25% thời lượng", unit: "%", dir: 1 },
  { key: "recovery_pct", head: "Nghỉ%", tip: "Tỷ lệ việc nặng (load=3) có nghỉ >10 phút phía sau", unit: "%", dir: 1 },
  { key: "max_streak_min", head: "Chuỗi", tip: "Chuỗi học liên tục dài nhất gồm ≥2 khối load≥2 (phút)", unit: "p", dir: -1 },
  { key: "peak_pct", head: "Đỉnh%", tip: "Việc nặng rơi vào giờ năng lượng cao (chỉ tính khi còn khe đỉnh khả dụng)", unit: "%", dir: 1 },
  { key: "off_peak", head: "Ngược", tip: "Số khối nặng đặt vào giờ năng lượng thấp dù còn khe tốt hơn", unit: "", dir: -1 },
  { key: "cram_pct", head: "<10h%", tip: "Khối lượng bị dồn vô lý vào 10 giờ cuối trước hạn", unit: "%", dir: -1 },
  { key: "max_day_min", head: "MaxNgày", tip: "Tổng phút lớp + tự học của ngày nặng nhất", unit: "p", dir: -1 },
  { key: "ctx", head: "Ctx", tip: "Số lần đổi loại công việc sát nhau (≤ 30 phút)", unit: "", dir: -1 },
  { key: "sjl_min", head: "SJL", tip: "Lệch pha ngủ giữa ngày đi học và ngày nghỉ (phút)", unit: "p", dir: -1 },
  { key: "std_min", head: "Std", tip: "Độ lệch chuẩn tổng tải giữa các ngày (phút)", unit: "p", dir: -1 },
  { key: "exec_ms", head: "ms", tip: "Thời gian giải (mili-giây) — không phải tiêu chí chất lượng", unit: "", dir: 0 },
];

function bestWorst(rows, col) {
  if (!col.dir) return { best: null, worst: null };
  const vals = rows.map((r) => r[col.key]).filter((v) => v !== null && v !== undefined);
  if (vals.length < 2) return { best: null, worst: null };
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  if (lo === hi) return { best: null, worst: null };
  return col.dir > 0 ? { best: hi, worst: lo } : { best: lo, worst: hi };
}

function fmtCell(v, unit) {
  if (v === null || v === undefined) return "—";
  return `${v}${unit}`;
}

async function ensureShowcaseLoaded(rerender) {
  const sc = state.showcase;
  if (sc.loading) return;
  sc.loading = true;
  try {
    if (!sc.list) {
      sc.list = await api.getShowcaseList();
      rerender();
    }
    for (const c of sc.list.cases) {
      if (sc.cases[c.index] || sc.errors[c.index] || sc.rerunning[c.index]) continue;
      try {
        sc.cases[c.index] = await api.getShowcaseCase(c.index);
      } catch (err) {
        sc.errors[c.index] = err.message;
      }
      rerender();
    }
  } catch (err) {
    sc.listError = err.message;
    rerender();
  } finally {
    sc.loading = false;
  }
}

function renderCaseTable(data) {
  const rows = data.rows || [];
  const marks = Object.fromEntries(COLUMNS.map((c) => [c.key, bestWorst(rows, c)]));
  const body = rows
    .map((r) => {
      const vb = getVerdictBadge(r.verdict);
      const cells = COLUMNS.map((c) => {
        const v = r[c.key];
        const m = marks[c.key];
        const cls = v !== null && v !== undefined && m.best !== null ? (v === m.best ? "sc-best" : v === m.worst ? "sc-worst" : "") : "";
        return `<td class="mono ${cls}">${fmtCell(v, c.unit)}</td>`;
      }).join("");
      const cards = `${r.crit ? `<span class="badge badge-danger mono" title="${esc((r.critical_breaches || []).join("\n"))}">${r.crit}🟥</span>` : ""}${
        r.warn ? `<span class="badge badge-warn mono">${r.warn}🟨</span>` : ""
      }${!r.crit && !r.warn ? `<span class="badge badge-ok">Sạch</span>` : ""}`;
      return `
        <tr>
          <td class="mono" style="font-weight:700;">#${r.rank}</td>
          <td class="mono" style="font-weight:600;">${esc(r.solver_key)}</td>
          <td><span class="badge ${vb.cls}" title="${esc(vb.label)}">${vb.short}</span></td>
          ${cells}
          <td><div class="sc-cards">${cards}</div></td>
        </tr>`;
    })
    .join("");
  return `
    <div class="table-wrap">
      <table class="data-table sc-table">
        <thead>
          <tr>
            <th>Hạng</th><th>Thuật toán</th><th>Verdict</th>
            ${COLUMNS.map((c) => `<th title="${esc(c.tip)}">${esc(c.head)}</th>`).join("")}
            <th title="Số thẻ đỏ (CRITICAL) / thẻ vàng (WARNING)">Thẻ</th>
          </tr>
        </thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}

function renderExplanation(data) {
  const pairs = (data.pairs || []).map((p) => `<li>${esc(p.text)}</li>`).join("");
  const spread = (data.spread || []).map((s) => `<li>${esc(s)}</li>`).join("");
  const levels = (data.decisive_levels || [])
    .map((code) => {
      const lv = (state.showcase.list?.levels || []).find((l) => l.code === code);
      return `<span class="badge badge-dark mono" title="${esc(lv?.name || code)}">${esc(lv?.name || code)}</span>`;
    })
    .join("");
  return `
    <div class="sc-explain">
      <h4>Giải thích bảng</h4>
      <p class="sc-summary">${esc(data.summary)}</p>
      <div class="sc-explain-grid">
        <div>
          <div class="sc-explain-title">Kết luận (Verdict) từng thuật toán</div>
          <p>${esc(data.verdict_line)}</p>
          <div class="sc-explain-title" style="margin-top:10px;">Cấp quyết định thứ hạng trong đề này</div>
          <div class="sc-levels">${levels || `<span class="badge badge-neutral">Hòa toàn bộ</span>`}</div>
        </div>
        <div>
          <div class="sc-explain-title">Vì sao xếp hạng như vậy (so từng cặp liền kề)</div>
          <ul>${pairs}</ul>
        </div>
      </div>
      ${
        spread
          ? `<div class="sc-explain-title" style="margin-top:10px;">Các tiêu chí có khác biệt rõ nhất</div><ul>${spread}</ul>`
          : `<p style="margin-top:8px;">Các thuật toán cho số liệu giống nhau ở mọi tiêu chí chính.</p>`
      }
    </div>`;
}

function renderCaseCard(spec, data, error) {
  const head = `
    <div class="sc-case-head">
      <div style="min-width:0;">
        <div class="sc-case-kicker">Bộ test ${spec.index + 1} · ${esc(spec.source === "fuzz" ? "FuzzGenerator v2" : "InputGenerator Regime")}</div>
        <h3>${esc(spec.focus)}</h3>
        <div class="sc-case-meta mono">${esc(data?.title || `${spec.id} seed=${spec.seed}`)}${
          data
            ? ` · ρ=${Number(data.metadata.tightness_rho).toFixed(2)} · ${data.metadata.task_count} việc · ${data.metadata.habit_count} thói quen${
                data.metadata.pinned_count ? ` · ${data.metadata.pinned_count} ghim` : ""
              }`
            : ""
        }</div>
      </div>
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        <button type="button" class="btn btn-sm" data-sc-rerun="${spec.index}" title="Giải & chấm lại đề này">↻ Chạy lại</button>
        <button type="button" class="btn btn-sm" data-sc-load="${spec.index}" title="Nạp đúng đề này vào lịch để xem chi tiết từng thuật toán">Nạp đề vào lịch</button>
      </div>
    </div>
    <p class="sc-why">${esc(spec.why)}</p>`;

  if (error) {
    return `<section class="card sc-case">${head}<div class="sc-loading" style="color:var(--st-danger);">Lỗi chạy đề: ${esc(error)}</div></section>`;
  }
  if (!data) {
    return `<section class="card sc-case">${head}<div class="sc-loading">⏳ Đang giải bằng 6 thuật toán & chấm điểm bằng Testing_System...</div></section>`;
  }
  return `<section class="card sc-case">${head}${renderCaseTable(data)}${renderExplanation(data)}</section>`;
}

function renderLegend() {
  return `
    <details class="card sc-legend">
      <summary>Chú thích cột & cách đọc bảng</summary>
      <ul>
        ${COLUMNS.map((c) => `<li><strong class="mono">${esc(c.head)}</strong> — ${esc(c.tip)}${c.dir > 0 ? " (càng cao càng tốt)" : c.dir < 0 ? " (càng thấp càng tốt)" : ""}.</li>`).join("")}
        <li><strong>Thẻ</strong> — số thẻ đỏ (CRITICAL) / thẻ vàng (WARNING) của Testing_System v2.1.</li>
        <li><span class="sc-best mono">Xanh</span> = giá trị tốt nhất của cột, <span class="sc-worst mono">đỏ nhạt</span> = kém nhất (chỉ tô khi các thuật toán khác nhau).</li>
        <li><strong>Lưu ý độ ổn định:</strong> SCORED_GREEDY, BACKTRACK và HYBRID_ALNS có bước tối ưu chạy theo giới hạn thời gian thực, nên khi máy đang bận (nhiều tab/request cùng lúc) số liệu của chúng có thể kém hơn bình thường. Bấm “↻ Chạy lại” khi máy rảnh để có kết quả đại diện. EDF, WSPT, LST không bị ảnh hưởng theo cách này.</li>
        <li>Thứ hạng <strong>không</strong> cộng điểm: so theo Cổng #0 rồi 10 cấp từ điển (Verdict → P1.1 → Shk25 → Nghỉ → Nhịp sinh học → &lt;10h → Trần ngày → Ctx → Thói quen → Đều tải). Hai thuật toán chỉ được so ở cấp sau khi hòa ở mọi cấp trước (sau khi làm tròn bậc dung sai).</li>
      </ul>
    </details>`;
}

export function renderShowcaseView(container, callbacks) {
  const sc = state.showcase;
  const rerender = () => {
    if (state.activeView === "showcase") renderShowcaseView(container, callbacks);
  };

  const list = sc.list?.cases || [];
  const done = list.filter((c) => sc.cases[c.index]).length;
  container.innerHTML = `
    <div class="section-head">
      <div>
        <h2>Bảng So Sánh Thuật Toán Trên Các Bộ Test Nổi Bật</h2>
        <p>${list.length || 7} đề sinh từ <code>Testing_System</code> (InputGenerator & FuzzGenerator v2) mà 6 thuật toán cho kết quả khác nhau rõ. Mỗi bảng được giải và chấm trực tiếp; phần giải thích bên dưới sinh tự động từ chính số liệu.${
          list.length && done < list.length ? ` <strong>Đang chạy ${done}/${list.length}...</strong>` : ""
        }</p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <button type="button" class="btn btn-sm" id="btnScBack">← Quay lại lịch</button>
      </div>
    </div>
    ${sc.listError ? `<div class="card sc-case" style="color:var(--st-danger);">Không tải được danh sách: ${esc(sc.listError)}</div>` : ""}
    <div class="sc-cases">
      ${list.map((spec) => renderCaseCard(spec, sc.cases[spec.index], sc.errors[spec.index])).join("")}
    </div>
    ${renderLegend()}
  `;

  container.querySelector("#btnScBack")?.addEventListener("click", () => callbacks.onBackToCalendar?.());
  container.querySelectorAll("[data-sc-rerun]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const idx = Number(btn.getAttribute("data-sc-rerun"));
      if (sc.rerunning[idx]) return;
      sc.rerunning[idx] = true;
      delete sc.cases[idx];
      delete sc.errors[idx];
      rerender();
      try {
        sc.cases[idx] = await api.getShowcaseCase(idx, true);
      } catch (err) {
        sc.errors[idx] = err.message;
      }
      delete sc.rerunning[idx];
      rerender();
    });
  });
  container.querySelectorAll("[data-sc-load]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const spec = list[Number(btn.getAttribute("data-sc-load"))];
      if (spec) callbacks.onLoadSuite?.(spec.source, spec.id, spec.seed, spec.horizon_days ?? null);
    });
  });

  ensureShowcaseLoaded(rerender);
}
