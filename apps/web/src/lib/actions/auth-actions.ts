"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ApiClientError } from "@/lib/api-client";
import { loginUser } from "@/lib/auth-client";
import { SESSION_COOKIE_NAME } from "@/lib/session";

export interface LoginActionState {
  error: string | null;
}

export async function loginAction(
  _prevState: LoginActionState,
  formData: FormData,
): Promise<LoginActionState> {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  let token;
  try {
    token = await loginUser(email, password);
  } catch (error) {
    // The API returns the same generic message for every rejection
    // reason (unknown email, wrong password, inactive account) so the
    // UI cannot narrow it further either — narrowing here would leak
    // exactly what the API deliberately avoids leaking.
    if (error instanceof ApiClientError && error.status === 401) {
      return { error: "Invalid email or password." };
    }
    return { error: "Unable to sign in right now. Please try again." };
  }

  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE_NAME, token.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: token.expires_in,
  });

  redirect("/");
}

export async function logoutAction(): Promise<void> {
  const cookieStore = await cookies();
  cookieStore.delete(SESSION_COOKIE_NAME);
  redirect("/");
}
