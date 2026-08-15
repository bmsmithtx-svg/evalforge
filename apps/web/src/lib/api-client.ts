import { env } from "@/lib/env";

/**
 * Typed boundary for calls to the EvalForge API.
 *
 * Milestone 2 scope: foundation-level health and readiness only. No
 * product-domain client methods exist yet.
 */

export interface HealthResponse {
  status: string;
}

export interface ReadinessDependency {
  name: string;
  ok: boolean;
  detail: string | null;
}

export interface ReadinessResponse {
  status: string;
  dependencies: ReadinessDependency[];
}

export class ApiClientError extends Error {
  constructor(
    public readonly path: string,
    public readonly status: number,
  ) {
    super(`EvalForge API request to ${path} failed with status ${status}`);
    this.name = "ApiClientError";
  }
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  accessToken?: string;
}

export async function requestJson<T>(
  path: string,
  baseUrl: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (options.accessToken) {
    headers["Authorization"] = `Bearer ${options.accessToken}`;
  }

  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });
  if (!response.ok) {
    throw new ApiClientError(path, response.status);
  }
  return (await response.json()) as T;
}

export function getApiHealth(baseUrl: string = env.API_BASE_URL): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/healthz", baseUrl);
}

export function getApiReadiness(baseUrl: string = env.API_BASE_URL): Promise<ReadinessResponse> {
  return requestJson<ReadinessResponse>("/readyz", baseUrl);
}
