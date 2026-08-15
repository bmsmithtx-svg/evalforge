import { requestJson } from "@/lib/api-client";
import { env } from "@/lib/env";

/**
 * Typed boundary for the authentication and tenant-membership API.
 *
 * This module only calls the API; it never decides authorization
 * itself. Every 401/403 the API returns propagates as an
 * ApiClientError for the caller to handle explicitly.
 */

export interface UserPublic {
  id: string;
  email: string;
  status: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface TenantMembership {
  tenant_id: string;
  tenant_slug: string;
  tenant_name: string;
  role: string;
  membership_status: string;
}

export interface TenantContext {
  tenant_id: string;
  tenant_slug: string;
  role: string;
  membership_status: string;
}

export function registerUser(
  email: string,
  password: string,
  baseUrl: string = env.API_BASE_URL,
): Promise<UserPublic> {
  return requestJson<UserPublic>("/auth/register", baseUrl, {
    method: "POST",
    body: { email, password },
  });
}

export function loginUser(
  email: string,
  password: string,
  baseUrl: string = env.API_BASE_URL,
): Promise<TokenResponse> {
  return requestJson<TokenResponse>("/auth/login", baseUrl, {
    method: "POST",
    body: { email, password },
  });
}

export function getCurrentUser(
  accessToken: string,
  baseUrl: string = env.API_BASE_URL,
): Promise<UserPublic> {
  return requestJson<UserPublic>("/auth/me", baseUrl, { accessToken });
}

export function listMyTenants(
  accessToken: string,
  baseUrl: string = env.API_BASE_URL,
): Promise<TenantMembership[]> {
  return requestJson<TenantMembership[]>("/tenants", baseUrl, { accessToken });
}

export function getTenantContext(
  tenantId: string,
  accessToken: string,
  baseUrl: string = env.API_BASE_URL,
): Promise<TenantContext> {
  return requestJson<TenantContext>(`/tenants/${tenantId}/context`, baseUrl, { accessToken });
}
