import { ApiClientError, getApiHealth, getApiReadiness } from "@/lib/api-client";
import type { ReadinessResponse } from "@/lib/api-client";
import { Card } from "@/components/Card";
import { StatusBadge } from "@/components/StatusBadge";

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

export default async function HomePage() {
  const readiness = await loadReadiness();

  return (
    <main>
      <h1>EvalForge</h1>
      <p>Milestone 2 engineering foundation — application shell only.</p>

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
    </main>
  );
}
