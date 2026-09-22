import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { AuditEntry } from "../api/types";

export function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    api
      .audit()
      .then(setEntries)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load audit log"));
  }, []);

  async function loadMore() {
    const last = entries?.[entries.length - 1];
    if (!last) return;
    setLoadingMore(true);
    try {
      const more = await api.audit(last.id);
      setEntries((prev) => [...(prev ?? []), ...more]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load more");
    } finally {
      setLoadingMore(false);
    }
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!entries) return <p>Loading audit log&hellip;</p>;

  return (
    <div>
      <h1>Audit log</h1>
      <p className="muted">Every read and write to patient data in this organisation, newest first.</p>
      <table className="data-table">
        <thead>
          <tr>
            <th>When</th>
            <th>Actor</th>
            <th>Action</th>
            <th>Entity</th>
            <th>IP</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.id}>
              <td>{new Date(e.at).toLocaleString()}</td>
              <td>{e.actor}</td>
              <td>{e.action}</td>
              <td>
                {e.entityType}:{e.entityId}
              </td>
              <td>{e.ip ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button onClick={loadMore} disabled={loadingMore}>
        {loadingMore ? "Loading…" : "Load more"}
      </button>
    </div>
  );
}
