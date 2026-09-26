import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { AuditEntry, AuditVerification } from "../api/types";
import { Icon } from "../components/Icons";
import { PageHeader } from "../components/PageHeader";
import { dateTime, titleCase } from "../format";

export function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [verification, setVerification] = useState<AuditVerification | null>(null);
  const [verifying, setVerifying] = useState(false);

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

  async function verify() {
    setVerifying(true);
    try {
      setVerification(await api.verifyAudit());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Integrity check failed to run");
    } finally {
      setVerifying(false);
    }
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!entries) return <p>Loading audit log&hellip;</p>;

  return (
    <div>
      <PageHeader
        icon={<Icon.Audit />}
        title="Audit log"
        subtitle="Every read and write of patient data in this organisation, newest first. Append-only and hash-chained."
      />
      <div className="audit-verify">
        <button onClick={verify} disabled={verifying}>
          {verifying ? "Checking…" : "Verify integrity"}
        </button>
        {verification &&
          (verification.intact ? (
            <p className="verify-ok">
              Chain intact: {verification.entries} entries. Head hash{" "}
              <code>{verification.headHash}</code>. Record it elsewhere to detect a rewritten history later.
            </p>
          ) : (
            <p className="error-text">
              Tampering detected: the chain breaks at entry #{verification.firstBrokenSeq} of{" "}
              {verification.entries}. Treat the log from that point on as untrustworthy.
            </p>
          ))}
      </div>
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
              <td className="numeric">{dateTime(e.at)}</td>
              <td>{e.actor}</td>
              <td>{titleCase(e.action)}</td>
              <td>
                {e.entityType}:{e.entityId}
              </td>
              <td>{e.ip ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="secondary" onClick={loadMore} disabled={loadingMore} style={{ marginTop: "0.75rem" }}>
        {loadingMore ? "Loading…" : "Load more"}
      </button>
    </div>
  );
}
