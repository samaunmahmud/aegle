import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { WorklistItem } from "../api/types";
import { StateBadge, UrgencyBadge } from "../components/Badges";

export function WorklistPage() {
  const [items, setItems] = useState<WorklistItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [claiming, setClaiming] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .worklist()
      .then((page) => setItems(page.items))
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load worklist"));
  }, []);

  useEffect(() => {
    load();
    // Cases keep moving (new uploads, SLA aging), so refresh periodically
    // rather than requiring a manual reload.
    const interval = setInterval(load, 15_000);
    return () => clearInterval(interval);
  }, [load]);

  async function claim(studyId: string) {
    setClaiming(studyId);
    try {
      await api.claim(studyId);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to claim case");
    } finally {
      setClaiming(null);
    }
  }

  if (error) return <p className="error-text">{error}</p>;
  if (!items) return <p>Loading worklist&hellip;</p>;
  if (items.length === 0) return <p className="muted">No open cases. New uploads will appear here.</p>;

  return (
    <div>
      <h1>Worklist</h1>
      <p className="muted">Ranked by priority: findings' urgency plus how long a case has waited.</p>
      <table className="data-table">
        <thead>
          <tr>
            <th>Priority</th>
            <th>Patient MRN</th>
            <th>Modality / body part</th>
            <th>Finding</th>
            <th>SLA</th>
            <th>State</th>
            <th>Assigned to</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => (
            <tr key={it.studyId} className={it.slaBreached ? "row-breached" : ""}>
              <td className="numeric">{it.effectivePriority.toFixed(1)}</td>
              <td>{it.patientMrn}</td>
              <td>
                {it.modality} / {it.bodyPart}
              </td>
              <td>
                <UrgencyBadge urgency={it.urgencyClass} />{" "}
                {it.topLabel && (
                  <span className="finding">
                    {it.topLabel}
                    {it.topProbability != null ? ` (${(it.topProbability * 100).toFixed(0)}%)` : ""}
                  </span>
                )}
              </td>
              <td>
                {it.slaDueAt ? (
                  <span className={it.slaBreached ? "sla-breached" : "sla-ok"}>
                    {new Date(it.slaDueAt).toLocaleString()}
                  </span>
                ) : (
                  "—"
                )}
              </td>
              <td>
                <StateBadge state={it.state} />
              </td>
              <td>{it.assignedTo ?? "—"}</td>
              <td>
                {it.state === "OPEN" ? (
                  <button disabled={claiming === it.studyId} onClick={() => claim(it.studyId)}>
                    {claiming === it.studyId ? "Claiming…" : "Claim"}
                  </button>
                ) : (
                  <Link to={`/studies/${it.studyId}`}>Open</Link>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
