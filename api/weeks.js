import { fetchUpstream, sendJson } from "./_proxy.js";

export default async function handler(_request, response) {
  try {
    const upstream = await fetchUpstream("/api/weeks");
    sendJson(response, upstream.status, upstream.payload);
  } catch (error) {
    sendJson(response, 500, { error: error.message || "Proxy failed" });
  }
}
