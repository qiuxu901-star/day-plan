const DEFAULT_UPSTREAM_BASE = "https://commotion-serving-finicky.ngrok-free.dev";
const DEFAULT_UPSTREAM_TOKEN = "jMDgJZ7Xsc07Gk2QKFmtqvIASRywPVi6l6m66hY4yyE";
const REQUEST_TIMEOUT_MS = 10000;
const NGROK_OFFLINE_CODE = "ERR_NGROK_3200";

function getConfig() {
  const upstreamBase = (process.env.LOCAL_API_BASE_URL || DEFAULT_UPSTREAM_BASE).replace(/\/+$/, "");
  const upstreamToken = process.env.LOCAL_API_TOKEN || DEFAULT_UPSTREAM_TOKEN;

  if (!upstreamBase || !upstreamToken) {
    throw new Error("Missing upstream configuration");
  }

  return { upstreamBase, upstreamToken };
}

function parseJsonSafely(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function isHtmlResponse(contentType, text) {
  const normalized = (text || "").trim().toLowerCase();
  return contentType.includes("text/html") || normalized.startsWith("<!doctype html") || normalized.startsWith("<html");
}

function describeUpstreamFailure(response, text) {
  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  const ngrokErrorCode = response.headers.get("ngrok-error-code") || "";

  if (ngrokErrorCode === NGROK_OFFLINE_CODE || text.includes(NGROK_OFFLINE_CODE)) {
    return "本机写回服务未连接，请先启动本机 API 和 ngrok";
  }

  if (response.status === 401) {
    return "本机写回服务鉴权失败，请检查连接 token";
  }

  if (isHtmlResponse(contentType, text)) {
    return `上游服务返回了页面而不是数据（HTTP ${response.status}），请检查本机 API 和 ngrok`;
  }

  return `上游服务返回了无法解析的数据（HTTP ${response.status}）`;
}

function parseUpstreamPayload(response, text) {
  if (!text) {
    return {};
  }

  const parsed = parseJsonSafely(text);
  if (parsed !== null) {
    return parsed;
  }

  throw new Error(describeUpstreamFailure(response, text));
}

async function fetchUpstream(path, options = {}) {
  const { upstreamBase, upstreamToken } = getConfig();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${upstreamBase}${path}`, {
      method: options.method || "GET",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${upstreamToken}`,
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    });

    const text = await response.text();

    return {
      ok: response.ok,
      status: response.status,
      payload: parseUpstreamPayload(response, text),
    };
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("本机写回服务连接超时，请确认本机 API 和 ngrok 正在运行");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

function sendJson(response, statusCode, payload) {
  response.status(statusCode).setHeader("Content-Type", "application/json; charset=utf-8");
  response.send(JSON.stringify(payload));
}

function buildQueryString(query) {
  const params = new URLSearchParams();

  for (const [key, value] of Object.entries(query || {})) {
    if (value === undefined || value === null) {
      continue;
    }
    if (Array.isArray(value)) {
      value.forEach((item) => params.append(key, String(item)));
      continue;
    }
    params.set(key, String(value));
  }

  const rendered = params.toString();
  return rendered ? `?${rendered}` : "";
}

export { buildQueryString, describeUpstreamFailure, fetchUpstream, parseUpstreamPayload, sendJson };
