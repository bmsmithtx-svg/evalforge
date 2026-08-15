import { cookies } from "next/headers";

import { getCurrentUser, type UserPublic } from "@/lib/auth-client";

/**
 * Server-only session lookup.
 *
 * The access token lives only in an httpOnly cookie the browser never
 * exposes to page JavaScript; every server render revalidates it
 * against the API rather than trusting the cookie's mere presence, so
 * an expired or revoked token immediately falls back to signed-out.
 */

export const SESSION_COOKIE_NAME = "evalforge_session";

export interface Session {
  accessToken: string;
  user: UserPublic;
}

export async function getSession(): Promise<Session | null> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get(SESSION_COOKIE_NAME)?.value;
  if (!accessToken) {
    return null;
  }

  try {
    const user = await getCurrentUser(accessToken);
    return { accessToken, user };
  } catch {
    return null;
  }
}
