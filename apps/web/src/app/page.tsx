import Link from "next/link";

import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";
import { logoutAction } from "@/lib/actions/auth-actions";
import { ApiClientError, getApiHealth, getApiReadiness } from "@/lib/api-client";
import type { ReadinessResponse } from "@/lib/api-client";
import { listMyTenants } from "@/lib/auth-client";
import type { TenantMembership } from "@/lib/auth-client";
import { getSession } from "@/lib/session";

async function loadReadiness(): Promise<
  { ok: true; data: ReadinessResponse } | { ok: false; message: string }
> {
  try {
    const [, readiness] = await Promise.all([getApiHealth(), getApiReadiness()]);
    return { ok: true, data: readiness };
  } catch (error) {
    const message = error instanceof ApiClientError ? error.message : "API is unreachable.";
    return { ok: false, message };
  }
}

async function TenantMemberships({ accessToken }: { accessToken: string }) {
  let tenants: TenantMembership[] | null = null;
  let errorMessage: string | null = null;

  try {
    tenants = await listMyTenants(accessToken);
  } catch (error) {
    errorMessage =
      error instanceof ApiClientError && error.status === 401
        ? "Your session expired. Please sign in again."
        : "Unable to load tenant memberships right now.";
  }

  if (errorMessage !== null) {
    return <p>{errorMessage}</p>;
  }
  if (tenants === null || tenants.length === 0) {
    return <p>No tenant memberships yet.</p>;
  }
  return (
    <ul>
      {tenants.map((tenant) => (
        <li key={tenant.tenant_id}>
          {tenant.tenant_name} — {tenant.role} ({tenant.membership_status})
        </li>
      ))}
    </ul>
  );
}

export default async function HomePage() {
  const readiness = await loadReadiness();
  const session = await getSession();

  return (
    <main>
      <h1>EvalForge</h1>
      <p>Application shell with authentication and tenant-scoped access control.</p>

      <Card title="API connectivity">
        {readiness.ok ? (
          <ul>
            {readiness.data.dependencies.map((dependency) => (
              <li key={dependency.name}>
                {dependency.name}:{" "}
                <StatusBadge ok={dependency.ok} label={dependency.ok ? "ok" : "down"} />
              </li>
            ))}
          </ul>
        ) : (
          <p>
            <StatusBadge ok={false} label="unreachable" /> {readiness.message}
          </p>
        )}
      </Card>

      <Card title="Account">
        {session ? (
          <>
            <p>
              Signed in as {session.user.email} <StatusBadge ok label="active" />
            </p>
            <form action={logoutAction}>
              <button type="submit">Sign out</button>
            </form>
            <h3>Your tenants</h3>
            <TenantMemberships accessToken={session.accessToken} />
          </>
        ) : (
          <p>
            <Link href="/login">Sign in</Link> to view your tenant memberships.
          </p>
        )}
      </Card>
    </main>
  );
}
