import { fetchUpstream, sendJson } from "../_proxy.js";

export default async function handler(request, response) {
  if (request.method !== "POST") {
    sendJson(response, 405, { error: "Method Not Allowed" });
    return;
  }

  try {
    const upstream = await fetchUpstream("/api/weeks/create-next", {
      method: "POST",
      body: request.body || {},
    });
    sendJson(response, upstream.status, upstream.payload);
  } catch (error) {
    sendJson(response, 500, { error: error.message || "Proxy failed" });
  }
}
