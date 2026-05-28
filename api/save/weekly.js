import { fetchUpstream, sendJson } from "../_proxy.js";

export default async function handler(request, response) {
  try {
    const upstream = await fetchUpstream("/api/save/weekly", {
      method: "POST",
      body: request.body || {},
    });
    sendJson(response, upstream.status, upstream.payload);
  } catch (error) {
    sendJson(response, 500, { error: error.message || "Proxy failed" });
  }
}
