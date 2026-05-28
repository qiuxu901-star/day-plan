function hasEntries(items) {
  return (items || []).some((item) => String(item || "").trim());
}

function isDayEmpty(day) {
  return ![
    day?.priorities,
    day?.inbox,
    day?.completed,
    day?.migrated,
    day?.dropped,
    day?.interruptions,
    day?.nextUp,
  ].some(hasEntries);
}

function emptyDayStatus(day) {
  if (isDayEmpty(day)) {
    return `当前日期 ${day?.activeDay || ""} 还没有已填内容`;
  }
  return `已同步 ${day?.activeDay || ""} 的计划内容`;
}

export { emptyDayStatus, isDayEmpty };
