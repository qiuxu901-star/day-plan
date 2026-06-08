import { buildQueryString, fetchUpstream, sendJson } from "./_proxy.js";

export default async function handler(request, response) {
  try {
    const query = buildQueryString(request.query);
    const upstream = await fetchUpstream(`/api/plan${query}`);
    sendJson(response, upstream.status, upstream.payload);
  } catch (error) {
    sendJson(response, 500, { error: error.message || "Proxy failed" });
  }
}
