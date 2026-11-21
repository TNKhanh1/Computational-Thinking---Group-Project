/**
 * Pure formatting, temporal math, and label utilities for SmartSchedule UI v3.
 */

export const WEEKDAYS_EN = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

export const WEEKDAYS_VI_SHORT = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
export const WEEKDAYS_VI_FULL = [
  "Thứ Hai",
  "Thứ Ba",
  "Thứ Tư",
  "Thứ Năm",
  "Thứ Sáu",
  "Thứ Bảy",
  "Chủ Nhật",
];

export const CATEGORY_LABELS = {
  EXAM: "Thi cử",
  PROJECT: "Đồ án",
  ASSIGNMENT: "Bài tập",
  LAB: "Thực hành",
  READING: "Đọc tài liệu",
  HABIT: "Thói quen",
  DEADLINE: "Công việc",
  ACADEMIC_CLASS: "Lớp học",
  MEAL: "Bữa ăn",
  WORK: "Làm thêm",
  MEETING: "Họp / CLB",
  OTHER: "Khác",
};

export const PRIORITY_LABELS = {
  5: "5 · Khẩn cấp nhất",
  4: "4 · Cao",
  3: "3 · Trung bình",
  2: "2 · Thấp",
  1: "1 · Rất thấp",
};

export const LOAD_LABELS = {
  3: "L3 · Tập trung sâu",
  2: "L2 · Trung bình",
  1: "L1 · Nhẹ",
};

export const WINDOW_LABELS = {
  ANYTIME: "Bất kỳ",
  MORNING: "Sáng (06–12h)",
  AFTERNOON: "Chiều (12–18h)",
  EVENING: "Tối (18–23h)",
};

export const FOCUS_PROFILES = {
  MORNING: { label: "Sáng (Early Bird)", peak: "Peak 06:00–12:00", curve: [3, 2, 1, 1] },
  AFTERNOON: { label: "Chiều", peak: "Peak 12:00–18:00", curve: [2, 3, 1, 1] },
  EVENING: { label: "Tối (Night Owl)", peak: "Peak 18:00–24:00", curve: [1, 2, 3, 2] },
  BALANCED: { label: "Cân bằng", peak: "Peak 06:00–12:00, ổn định chiều/tối", curve: [3, 2, 2, 1] },
};

export function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function parseWeekStartDate(isoStr) {
  const m = String(isoStr || "2026-11-02").match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return new Date(2026, 10, 2);
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

export function addDays(baseDate, days) {
  const d = new Date(baseDate.getTime());
  d.setDate(d.getDate() + days);
  return d;
}

export function fmtDDMM(dateObj) {
  const dd = String(dateObj.getDate()).padStart(2, "0");
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}`;
}

export function fmtDDMMYYYY(dateObj) {
  return `${fmtDDMM(dateObj)}/${dateObj.getFullYear()}`;
}

export function fmtISODate(dateObj) {
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function parseHHMMToMin(hhmm) {
  const parts = String(hhmm || "00:00").split(":");
  const h = Math.max(0, Math.min(24, Number(parts[0]) || 0));
  const m = Math.max(0, Math.min(59, Number(parts[1]) || 0));
  return h * 60 + m;
}

export function minToHHMM(totalMin) {
  const clamped = Math.max(0, Math.min(1440, Math.round(totalMin)));
  const h = Math.floor(clamped / 60);
  const m = clamped % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function slotToDayIndex(slot) {
  return Math.floor(Number(slot || 0) / 96);
}

export function slotToMinuteInDay(slot) {
  return (Number(slot || 0) % 96) * 15;
}

export function resolveNowSlot(commitments) {
  const nowStr = commitments?.now;
  if (!nowStr) return 0;
  const ws = parseWeekStartDate(commitments?.planning_week_start);

  // Try ISO string YYYY-MM-DDTHH:MM
  const isoMatch = String(nowStr).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
  if (isoMatch) {
    const dt = new Date(
      Number(isoMatch[1]),
      Number(isoMatch[2]) - 1,
      Number(isoMatch[3]),
      Number(isoMatch[4]),
      Number(isoMatch[5])
    );
    const diffMin = Math.floor((dt.getTime() - ws.getTime()) / 60000);
    return Math.max(0, Math.floor(diffMin / 15));
  }

  // Try "Monday 09:00"
  const dayMatch = String(nowStr).match(/^(Next\s+)?([A-Za-z]+)\s+(\d{1,2}):(\d{2})/i);
  if (dayMatch) {
    const isNext = Boolean(dayMatch[1]);
    const dayIdx = WEEKDAYS_EN.findIndex((w) => w.toLowerCase() === dayMatch[2].toLowerCase());
    if (dayIdx >= 0) {
      const totalDay = dayIdx + (isNext ? 7 : 0);
      const mins = Number(dayMatch[3]) * 60 + Number(dayMatch[4]);
      return totalDay * 96 + Math.floor(mins / 15);
    }
  }
  return 0;
}

export function getEnergyForHour(focusPref, hour) {
  const key = String(focusPref || "BALANCED").toUpperCase();
  const profile = FOCUS_PROFILES[key] || FOCUS_PROFILES.BALANCED;
  const [m, a, e, n] = profile.curve;
  if (hour >= 6 && hour < 12) return m;
  if (hour >= 12 && hour < 18) return a;
  if (hour >= 18 && hour < 24) return e;
  return n;
}

export function getVerdictBadge(verdict) {
  switch (verdict) {
    case "HIGH_PRODUCTIVITY":
      return { short: "HIGH", label: "HIGH_PRODUCTIVITY", cls: "badge-ok", dot: "ok" };
    case "FEASIBLE_BUT_LOW_PRODUCTIVITY":
      return { short: "LOW", label: "LOW_PRODUCTIVITY", cls: "badge-warn", dot: "warn" };
    case "OVERLOAD_TRIAGE":
      return { short: "OVLD", label: "OVERLOAD_TRIAGE", cls: "badge-info", dot: "info" };
    case "SUBOPTIMAL_ALGORITHM_FAILURE":
      return { short: "SUBOPT", label: "SUBOPTIMAL", cls: "badge-danger", dot: "danger" };
    case "INVALID":
      return { short: "INV", label: "INVALID", cls: "badge-danger", dot: "danger" };
    default:
      return { short: "—", label: verdict || "Chưa chấm", cls: "badge-neutral", dot: "" };
  }
}

export function expandFixedEventsForDay(fixedEvents, dayIdx) {
  const weekdayEn = WEEKDAYS_EN[dayIdx % 7];
  const out = [];
  for (const ev of fixedEvents || []) {
    const rawDays = ev.day_of_week;
    let matches = false;
    if (Array.isArray(rawDays)) {
      matches = rawDays.some((d) => String(d).toLowerCase() === weekdayEn.toLowerCase() || String(d).toUpperCase() === "ALL");
    } else {
      const s = String(rawDays || "").trim();
      matches = s.toUpperCase() === "ALL" || s.toLowerCase() === weekdayEn.toLowerCase();
    }
    if (!matches) continue;
    const startMin = parseHHMMToMin(ev.start_time);
    const endMin = parseHHMMToMin(ev.end_time);
    if (endMin > startMin) {
      out.push({
        ...ev,
        startMin,
        endMin,
        durationMin: endMin - startMin,
      });
    }
  }
  out.sort((a, b) => a.startMin - b.startMin);
  return out;
}

export function getSleepSegmentsForDay(sleepSchedule) {
  const startMin = parseHHMMToMin(sleepSchedule?.daily_start_time || "23:30");
  const endMin = parseHHMMToMin(sleepSchedule?.daily_end_time || "06:30");
  if (startMin > endMin) {
    // Overnight sleep: 00:00..endMin and startMin..24:00
    return [
      { startMin: 0, endMin, label: `Ngủ (00:00–${minToHHMM(endMin)})` },
      { startMin, endMin: 1440, label: `Ngủ (${minToHHMM(startMin)}–24:00)` },
    ];
  }
  if (endMin > startMin) {
    return [{ startMin, endMin, label: `Ngủ (${minToHHMM(startMin)}–${minToHHMM(endMin)})` }];
  }
  return [];
}

export function computeSleepHours(startHHMM, endHHMM) {
  const s = parseHHMMToMin(startHHMM);
  const e = parseHHMMToMin(endHHMM);
  const mins = s > e ? 1440 - s + e : Math.max(0, e - s);
  return +(mins / 60).toFixed(2);
}

export function formatDeadlineCountdown(deadlineSlot, nowSlot) {
  if (deadlineSlot == null) return "Linh hoạt";
  const diffMin = (deadlineSlot - nowSlot) * 15;
  if (diffMin <= 0) return "Đã tới hạn";
  const days = Math.floor(diffMin / 1440);
  const hours = Math.floor((diffMin % 1440) / 60);
  if (days > 0) return `Còn ${days}d ${hours}h`;
  return `Còn ${hours}h ${diffMin % 60}p`;
}

export function formatMinutesLabel(min) {
  const m = Math.round(Number(min || 0));
  if (m < 60) return `${m}p`;
  const h = Math.floor(m / 60);
  const rem = m % 60;
  return rem ? `${h}h${rem}p` : `${h}h`;
}

export function computeBufferPreview(durationMin, cognitiveLoad, profile) {
  const raw = Math.max(15, Number(durationMin) || 60);
  const mode = String(profile?.buffer_mode || "HABIT").toUpperCase();
  let mult = 1.0;
  if (mode === "COGNITIVE_LOAD") {
    mult = Number(cognitiveLoad) === 3 ? Number(profile?.alpha_heavy || 1.35) : Number(profile?.alpha_light || 1.2);
  } else if (profile?.estimate_habit === "OFTEN") {
    mult = 1.3;
  } else if (profile?.estimate_habit === "SOMETIMES") {
    mult = 1.15;
  }
  const planned = Math.ceil((raw * mult) / 15) * 15;
  return { raw, mult, planned };
}

export function dateAndTimeToDeadlineDay(dateStr, weekStartIso) {
  if (!dateStr) return null;
  const ws = parseWeekStartDate(weekStartIso);
  const target = parseWeekStartDate(dateStr);
  const diffDays = Math.round((target.getTime() - ws.getTime()) / 86400000);
  if (diffDays >= 0 && diffDays < 7) {
    return WEEKDAYS_EN[diffDays];
  }
  if (diffDays >= 7 && diffDays < 14) {
    return `Next ${WEEKDAYS_EN[diffDays - 7]}`;
  }
  return WEEKDAYS_EN[((diffDays % 7) + 7) % 7];
}
