import test from "node:test";
import assert from "node:assert/strict";

import { describeUpstreamFailure, parseUpstreamPayload } from "./_proxy.js";

function createResponse({ status = 200, headers = {} } = {}) {
  const normalizedHeaders = Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [key.toLowerCase(), value]),
  );

  return {
    status,
    headers: {
      get(name) {
        return normalizedHeaders[name.toLowerCase()] || null;
      },
    },
  };
}

test("parses JSON payloads from upstream", () => {
  const response = createResponse({
    status: 200,
    headers: { "content-type": "application/json; charset=utf-8" },
  });

  assert.deepEqual(parseUpstreamPayload(response, '{"weeks":[{"weekId":"WK22"}]}'), {
    weeks: [{ weekId: "WK22" }],
  });
});

test("maps ngrok offline HTML to a readable error", () => {
  const response = createResponse({
    status: 404,
    headers: {
      "content-type": "text/html",
      "ngrok-error-code": "ERR_NGROK_3200",
    },
  });

  assert.equal(
    describeUpstreamFailure(response, "<!DOCTYPE html><html><body>offline</body></html>"),
    "本机写回服务未连接，请先启动本机 API 和 ngrok",
  );

  assert.throws(
    () => parseUpstreamPayload(response, "<!DOCTYPE html><html><body>offline</body></html>"),
    /本机写回服务未连接，请先启动本机 API 和 ngrok/,
  );
});
