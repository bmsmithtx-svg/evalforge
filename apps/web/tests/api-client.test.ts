import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiClientError, getApiHealth, getApiReadiness } from "@/lib/api-client";

const originalFetch = globalThis.fetch;

describe("api-client", () => {
  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("getApiHealth resolves with the parsed health payload", async () => {
    globalThis.fetch = vi.fn(
      async () => new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );

    const result = await getApiHealth("http://api.internal");

    expect(result).toEqual({ status: "ok" });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://api.internal/healthz",
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("getApiReadiness resolves with the parsed readiness payload", async () => {
    const payload = {
      status: "ready",
      dependencies: [{ name: "postgres", ok: true, detail: null }],
    };
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }));

    const result = await getApiReadiness("http://api.internal");

    expect(result).toEqual(payload);
  });

  it("throws ApiClientError on a non-2xx response", async () => {
    globalThis.fetch = vi.fn(async () => new Response("", { status: 503 }));

    await expect(getApiReadiness("http://api.internal")).rejects.toBeInstanceOf(ApiClientError);
  });
});
