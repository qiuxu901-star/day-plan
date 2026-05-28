import { emptyDayStatus, isDayEmpty } from "./day-state.js";

const state = {
  weeks: [],
  weekPath: "",
  day: "",
};

const elements = {
  connectBtn: document.getElementById("connect-btn"),
  refreshBtn: document.getElementById("refresh-btn"),
  createNextWeekBtn: document.getElementById("create-next-week-btn"),
  weekTabs: document.getElementById("week-tabs"),
  dayTabs: document.getElementById("day-tabs"),
  previousSummary: document.getElementById("previous-summary"),
  status: document.getElementById("global-status"),
  carryNextUp: document.getElementById("carry-next-up"),
  carryMigrated: document.getElementById("carry-migrated"),
  clearPriorities: document.getElementById("clear-priorities"),
  saveWeeklyBtn: document.getElementById("save-weekly-btn"),
  saveDailyBtn: document.getElementById("save-daily-btn"),
  weeklyFocus: document.getElementById("weekly-focus"),
  mustDo: document.getElementById("must-do"),
  shouldProgress: document.getElementById("should-progress"),
  backlog: document.getElementById("backlog"),
  priorities: document.getElementById("priorities"),
  inbox: document.getElementById("inbox"),
  completed: document.getElementById("completed"),
  migrated: document.getElementById("migrated"),
  dropped: document.getElementById("dropped"),
  interruptions: document.getElementById("interruptions"),
  nextUp: document.getElementById("next-up"),
};

bootstrap();

function bootstrap() {
  elements.connectBtn.addEventListener("click", connectAndLoad);
  elements.refreshBtn.addEventListener("click", () => loadPlan(""));
  elements.createNextWeekBtn.addEventListener("click", createNextWeek);
  elements.weekTabs.addEventListener("click", handleWeekTabClick);
  elements.dayTabs.addEventListener("click", handleDayTabClick);
  elements.carryNextUp.addEventListener("click", () => loadPlan("next_up"));
  elements.carryMigrated.addEventListener("click", () => loadPlan("migrated"));
  elements.clearPriorities.addEventListener("click", () => {
    elements.priorities.value = "";
    setStatus("今日重点已清空，别忘了保存", "warn");
  });
  elements.saveWeeklyBtn.addEventListener("click", saveWeekly);
  elements.saveDailyBtn.addEventListener("click", saveDaily);
  connectAndLoad();
}

async function connectAndLoad() {
  setStatus("连接中…", "pending");

  try {
    const payload = await apiFetch("/api/weeks");
    state.weeks = payload.weeks || [];
    state.weekPath = state.weekPath || state.weeks[0]?.path || "";
    renderWeekTabs();
    await loadPlan("");
  } catch (error) {
    setStatus(`连接失败：${error.message}`, "error");
  }
}

async function loadPlan(carry) {
  if (!state.weekPath) {
    state.weekPath = state.weeks[0]?.path || "";
  }

  if (!state.weekPath) {
    setStatus("没有可用的 WK 文件", "error");
    return;
  }

  const query = new URLSearchParams({
    wk: state.weekPath,
    day: state.day || "",
  });
  if (carry) {
    query.set("carry", carry);
  }

  setStatus("读取中…", "pending");

  try {
    const payload = await apiFetch(`/api/plan?${query.toString()}`);
    state.weekPath = payload.week.weekPath;
    state.day = payload.day.activeDay;
    renderWeek(payload.week);
    renderDay(payload.day);
    setStatus("已同步当前周内容", "ok");
  } catch (error) {
    setStatus(`读取失败：${error.message}`, "error");
  }
}

async function saveWeekly() {
  if (!state.weekPath) {
    setStatus("先选择周文件", "error");
    return;
  }

  setStatus("保存周计划中…", "pending");

  try {
    await apiFetch("/api/save/weekly", {
      method: "POST",
      body: {
        wk: state.weekPath,
        weeklyFocus: splitEntries(elements.weeklyFocus.value),
        mustDo: splitEntries(elements.mustDo.value),
        shouldProgress: splitEntries(elements.shouldProgress.value),
        backlog: splitEntries(elements.backlog.value),
      },
    });
    setStatus("周计划已写回 Obsidian", "ok");
  } catch (error) {
    setStatus(`周计划保存失败：${error.message}`, "error");
  }
}

async function saveDaily() {
  if (!state.weekPath || !state.day) {
    setStatus("先选择周文件和日期", "error");
    return;
  }

  setStatus("保存日计划中…", "pending");

  try {
    await apiFetch("/api/save/daily", {
      method: "POST",
      body: {
        wk: state.weekPath,
        day: state.day,
        priorities: splitEntries(elements.priorities.value),
        inbox: splitEntries(elements.inbox.value),
        completed: splitEntries(elements.completed.value),
        migrated: splitEntries(elements.migrated.value),
        dropped: splitEntries(elements.dropped.value),
        interruptions: splitEntries(elements.interruptions.value),
        nextUp: splitEntries(elements.nextUp.value),
      },
    });
    setStatus("日计划已写回 Obsidian", "ok");
  } catch (error) {
    setStatus(`日计划保存失败：${error.message}`, "error");
  }
}

async function createNextWeek() {
  if (!state.weekPath) {
    setStatus("先选择一个来源 WK 文件", "error");
    return;
  }

  setStatus("正在新建下一周 WK，并承接上周遗留…", "pending");

  try {
    const payload = await apiFetch("/api/weeks/create-next", {
      method: "POST",
      body: { wk: state.weekPath },
    });
    state.weeks = payload.weeks || [];
    state.weekPath = "";
    state.day = "";
    renderWeekTabs();
    clearDayFields();
    await loadPlan("");
    setStatus(`已新建 ${payload.weekId}，当前仍停留在本周`, "ok");
  } catch (error) {
    setStatus(`新建下一周失败：${error.message}`, "error");
  }
}

function renderWeekTabs() {
  elements.weekTabs.innerHTML = "";
  state.weeks.forEach((week, index) => {
    if (!state.weekPath && index === 0) {
      state.weekPath = week.path;
    }
    elements.weekTabs.appendChild(
      createChoiceButton({
        active: week.path === state.weekPath,
        label: week.label,
        name: "week",
        value: week.path,
      }),
    );
  });
}

function renderWeek(week) {
  elements.weeklyFocus.value = joinEntries(week.weeklyFocus);
  elements.mustDo.value = joinEntries(week.mustDo);
  elements.shouldProgress.value = joinEntries(week.shouldProgress);
  elements.backlog.value = joinEntries(week.backlog);
}

function renderDay(day) {
  state.day = day.activeDay;
  renderDayTabs(day.availableDays, day.activeDay);
  elements.previousSummary.textContent = `昨日参考（不会自动算作今天内容）：${day.previousSummary}`;
  elements.priorities.value = joinEntries(day.priorities);
  elements.inbox.value = joinEntries(day.inbox);
  elements.completed.value = joinEntries(day.completed);
  elements.migrated.value = joinEntries(day.migrated);
  elements.dropped.value = joinEntries(day.dropped);
  elements.interruptions.value = joinEntries(day.interruptions);
  elements.nextUp.value = joinEntries(day.nextUp);
  setStatus(emptyDayStatus(day), isDayEmpty(day) ? "warn" : "ok");
}

function renderDayTabs(days, activeDay) {
  elements.dayTabs.innerHTML = "";
  days.forEach((day) => {
    elements.dayTabs.appendChild(
      createChoiceButton({
        active: day === activeDay,
        label: day,
        name: "day",
        value: day,
      }),
    );
  });
}

async function apiFetch(path, options = {}) {
  const url = path;
  const requestOptions = {
    method: options.method || "GET",
    headers: {},
  };

  if (options.body) {
    requestOptions.headers["Content-Type"] = "application/json";
    requestOptions.body = JSON.stringify(options.body);
  }

  const response = await fetch(url, requestOptions);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }

  return response.json();
}

function splitEntries(raw) {
  return raw
    .split(/\n\s*\n/g)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinEntries(items) {
  return (items || []).join("\n\n");
}

function createChoiceButton({ active, label, name, value }) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `choice-chip${active ? " active" : ""}`;
  button.dataset.name = name;
  button.dataset.value = value;
  button.setAttribute("aria-pressed", active ? "true" : "false");
  button.textContent = label;
  return button;
}

function handleWeekTabClick(event) {
  const button = event.target.closest("[data-name='week']");
  if (!button || button.dataset.value === state.weekPath) {
    return;
  }
  state.weekPath = button.dataset.value;
  state.day = "";
  renderWeekTabs();
  clearDayFields();
  setStatus("正在切换周文件…", "pending");
  loadPlan("");
}

function handleDayTabClick(event) {
  const button = event.target.closest("[data-name='day']");
  if (!button || button.dataset.value === state.day) {
    return;
  }
  state.day = button.dataset.value;
  renderDayTabs(
    Array.from(elements.dayTabs.querySelectorAll("[data-name='day']")).map((item) => item.dataset.value),
    state.day,
  );
  clearDayFields();
  setStatus(`正在切换到 ${state.day}…`, "pending");
  loadPlan("");
}

function clearDayFields() {
  elements.priorities.value = "";
  elements.inbox.value = "";
  elements.completed.value = "";
  elements.migrated.value = "";
  elements.dropped.value = "";
  elements.interruptions.value = "";
  elements.nextUp.value = "";
  elements.previousSummary.textContent = "昨日参考（不会自动算作今天内容）：加载中…";
}

function setStatus(message, tone) {
  elements.status.textContent = message;
  elements.status.dataset.tone = tone;
}
