const DEFAULT_UPSTREAM_BASE = "https://commotion-serving-finicky.ngrok-free.dev";
const DEFAULT_UPSTREAM_TOKEN = "jMDgJZ7Xsc07Gk2QKFmtqvIASRywPVi6l6m66hY4yyE";

function getConfig() {
  const upstreamBase = (process.env.LOCAL_API_BASE_URL || DEFAULT_UPSTREAM_BASE).replace(/\/+$/, "");
  const upstreamToken = process.env.LOCAL_API_TOKEN || DEFAULT_UPSTREAM_TOKEN;

  if (!upstreamBase || !upstreamToken) {
    throw new Error("Missing upstream configuration");
  }

  return { upstreamBase, upstreamToken };
}

async function fetchUpstream(path, options = {}) {
  const { upstreamBase, upstreamToken } = getConfig();
  const response = await fetch(`${upstreamBase}${path}`, {
    method: options.method || "GET",
    headers: {
      Authorization: `Bearer ${upstreamToken}`,
      "Content-Type": "application/json",
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  const text = await response.text();

  return {
    ok: response.ok,
    status: response.status,
    payload: text ? JSON.parse(text) : {},
  };
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

export { buildQueryString, fetchUpstream, sendJson };
