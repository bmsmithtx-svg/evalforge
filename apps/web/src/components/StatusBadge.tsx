export function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`status-badge ${ok ? "status-badge--ok" : "status-badge--fail"}`}>
      {label}
    </span>
  );
}
