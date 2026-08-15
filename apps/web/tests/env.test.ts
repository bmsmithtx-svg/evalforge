import { afterEach, describe, expect, it, vi } from "vitest";

describe("env module (fail-closed configuration)", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
  });

  it("exposes a validated env when API_BASE_URL is a valid URL", async () => {
    vi.stubEnv("API_BASE_URL", "http://localhost:8000");
    const { env } = await import("@/lib/env");
    expect(env).toEqual({ API_BASE_URL: "http://localhost:8000" });
  });

  it("fails module load when API_BASE_URL is missing", async () => {
    vi.stubEnv("API_BASE_URL", "");
    await expect(import("@/lib/env")).rejects.toThrow(/Invalid frontend environment configuration/);
  });

  it("fails module load when API_BASE_URL is not a valid URL", async () => {
    vi.stubEnv("API_BASE_URL", "not-a-url");
    await expect(import("@/lib/env")).rejects.toThrow(/Invalid frontend environment configuration/);
  });
});
