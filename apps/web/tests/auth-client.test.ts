import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiClientError } from "@/lib/api-client";
import {
  getCurrentUser,
  getTenantContext,
  listMyTenants,
  loginUser,
  registerUser,
} from "@/lib/auth-client";

const originalFetch = globalThis.fetch;
const TEST_PASSPHRASE = "Str0ng-Passphrase-1";

describe("auth-client", () => {
  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("registerUser posts email and password as JSON", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ id: "u1", email: "a@example.com", status: "active" }), {
          status: 201,
        }),
    );
    globalThis.fetch = fetchMock;

    const result = await registerUser("a@example.com", TEST_PASSPHRASE, "http://api.internal");

    expect(result.email).toBe("a@example.com");
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://api.internal/auth/register");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      email: "a@example.com",
      password: TEST_PASSPHRASE,
    });
  });

  it("loginUser returns the token payload on success", async () => {
    globalThis.fetch = vi.fn(
      async () =>
        new Response(
          JSON.stringify({ access_token: "token-value", token_type: "bearer", expires_in: 900 }),
          { status: 200 },
        ),
    );

    const result = await loginUser("a@example.com", TEST_PASSPHRASE, "http://api.internal");

    expect(result.access_token).toBe("token-value");
  });

  it("loginUser throws ApiClientError with status 401 on invalid credentials", async () => {
    globalThis.fetch = vi.fn(async () => new Response("", { status: 401 }));

    await expect(loginUser("a@example.com", "wrong", "http://api.internal")).rejects.toMatchObject({
      status: 401,
    });
  });

  it("getCurrentUser sends the access token as a bearer header", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ id: "u1", email: "a@example.com", status: "active" }), {
          status: 200,
        }),
    );
    globalThis.fetch = fetchMock;

    await getCurrentUser("token-value", "http://api.internal");

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer token-value");
  });

  it("getCurrentUser rejects with ApiClientError when unauthenticated", async () => {
    globalThis.fetch = vi.fn(async () => new Response("", { status: 401 }));

    await expect(getCurrentUser("bad-token", "http://api.internal")).rejects.toBeInstanceOf(
      ApiClientError,
    );
  });

  it("listMyTenants parses the tenant membership list", async () => {
    const payload = [
      {
        tenant_id: "t1",
        tenant_slug: "acme",
        tenant_name: "Acme",
        role: "tenant_admin",
        membership_status: "active",
      },
    ];
    globalThis.fetch = vi.fn(async () => new Response(JSON.stringify(payload), { status: 200 }));

    const result = await listMyTenants("token-value", "http://api.internal");

    expect(result).toEqual(payload);
  });

  it("getTenantContext rejects with ApiClientError status 403 for an unauthorized tenant", async () => {
    globalThis.fetch = vi.fn(async () => new Response("", { status: 403 }));

    await expect(
      getTenantContext("tenant-b", "token-value", "http://api.internal"),
    ).rejects.toMatchObject({ status: 403 });
  });
});
