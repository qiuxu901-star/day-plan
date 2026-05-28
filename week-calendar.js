function normalizeDayLabel(dayTitle) {
  const match = String(dayTitle || "").match(/周[一二三四五六日]/);
  return match ? match[0] : String(dayTitle || "");
}

function buildWeekDateMap(weekId, currentDate = new Date()) {
  const weekNumber = extractWeekNumber(weekId);
  if (!weekNumber) {
    return {};
  }

  const year = inferWeekYear(weekNumber, currentDate);
  const monday = isoWeekStart(year, weekNumber);
  const weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  const map = {};

  weekdays.forEach((weekday, index) => {
    const date = new Date(monday);
    date.setUTCDate(monday.getUTCDate() + index);
    map[weekday] = formatShortDate(date);
  });

  return map;
}

function formatWeekRange(weekId, currentDate = new Date()) {
  const weekNumber = extractWeekNumber(weekId);
  if (!weekNumber) {
    return "";
  }

  const year = inferWeekYear(weekNumber, currentDate);
  const monday = isoWeekStart(year, weekNumber);
  const sunday = new Date(monday);
  sunday.setUTCDate(monday.getUTCDate() + 6);
  return `${formatShortDate(monday)} - ${formatShortDate(sunday)}`;
}

function extractWeekNumber(weekId) {
  const match = String(weekId || "").match(/WK(\d+)/i);
  return match ? Number(match[1]) : 0;
}

function inferWeekYear(weekNumber, currentDate) {
  const currentYear = currentDate.getFullYear();
  const currentWeek = isoWeekNumber(currentDate);
  if (weekNumber >= 52 && currentWeek <= 2) {
    return currentYear - 1;
  }
  if (weekNumber <= 2 && currentWeek >= 52) {
    return currentYear + 1;
  }
  return currentYear;
}

function isoWeekStart(year, weekNumber) {
  const januaryFourth = new Date(Date.UTC(year, 0, 4));
  const dayOfWeek = januaryFourth.getUTCDay() || 7;
  const monday = new Date(januaryFourth);
  monday.setUTCDate(januaryFourth.getUTCDate() - dayOfWeek + 1 + (weekNumber - 1) * 7);
  return monday;
}

function isoWeekNumber(currentDate) {
  const date = new Date(Date.UTC(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate()));
  const dayNumber = date.getUTCDay() || 7;
  date.setUTCDate(date.getUTCDate() + 4 - dayNumber);
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
}

function formatShortDate(date) {
  return `${String(date.getUTCMonth() + 1).padStart(2, "0")}/${String(date.getUTCDate()).padStart(2, "0")}`;
}

export { buildWeekDateMap, formatWeekRange, normalizeDayLabel };
