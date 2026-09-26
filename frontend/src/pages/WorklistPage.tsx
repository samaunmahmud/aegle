import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { WorklistItem, WorklistState } from "../api/types";
import { StateBadge, UrgencyBadge } from "../components/Badges";
import { Icon, SpecialtyIcon } from "../components/Icons";
import { PageHeader } from "../components/PageHeader";
import { probability, slaStatus, waited } from "../format";
import { specialtyById, specialtyBySlug } from "../specialties";

const VIEWS: { id: string; label: string; states: WorklistState[] }[] = [
  { id: "active", label: "Active", states: ["OPEN", "IN_REVIEW"] },
  { id: "open", label: "Unclaimed", states: ["OPEN"] },
  { id: "done", label: "Completed", states: ["DONE"] },
];

export function WorklistPage() {
  const { specialty: slug } = useParams<{ specialty?: string }>();
  const specialty = specialtyBySlug(slug);
  const [view, setView] = useState(VIEWS[0]);
  const [items, setItems] = useState<WorklistItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [claiming, setClaiming] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const navigate = useNavigate();

  const load = useCallback(() => {
    api
      .worklist(view.states, specialty?.id)
      .then((page) => {
        setItems(page.items);
        setNow(Date.now());
        setError(null);
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load worklist"));
  }, [view, specialty?.id]);

  useEffect(() => {
    setItems(null);
    load();
    // Cases keep moving (new studies, SLA ageing): refresh rather than make people reload.
    const interval = setInterval(load, 15_000);
    return () => clearInterval(interval);
  }, [load]);

  const stats = useMemo(() => {
    const list = items ?? [];
    return {
      total: list.length,
      critical: list.filter((i) => i.urgencyClass === "CRITICAL").length,
      urgent: list.filter((i) => i.urgencyClass === "URGENT").length,
      breached: list.filter((i) => i.slaBreached).length,
    };
  }, [items]);

  async function claim(studyId: string) {
    setClaiming(studyId);
    try {
      await api.claim(studyId);
      navigate(`/studies/${studyId}`);   // claiming a case means reading it now
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to claim case");
    } finally {
      setClaiming(null);
    }
  }

  return (
    <div>
      <PageHeader
        icon={specialty ? <SpecialtyIcon specialty={specialty.id} /> : <Icon.Worklist />}
        title={specialty ? `${specialty.name} worklist` : "All worklists"}
        subtitle={
          specialty
            ? specialty.summary
            : "Every specialty, ranked by AI-assessed urgency plus time waiting. Refreshes every 15 seconds."
        }
        actions={
          <div className="segmented" role="tablist" aria-label="Worklist view">
            {VIEWS.map((v) => (
              <button
                key={v.id}
                role="tab"
                aria-selected={view.id === v.id}
                className={view.id === v.id ? "selected" : ""}
                onClick={() => setView(v)}
              >
                {v.label}
              </button>
            ))}
          </div>
        }
      />

      <div className="stat-row">
        <div className="panel stat">
          <div className="stat-label">Cases</div>
          <div className="stat-value">{items ? stats.total : "–"}</div>
        </div>
        <div className="panel stat stat-critical">
          <div className="stat-label">Critical</div>
          <div className="stat-value">{items ? stats.critical : "–"}</div>
        </div>
        <div className="panel stat stat-urgent">
          <div className="stat-label">Urgent</div>
          <div className="stat-value">{items ? stats.urgent : "–"}</div>
        </div>
        <div className="panel stat stat-critical">
          <div className="stat-label">Past SLA</div>
          <div className="stat-value">{items ? stats.breached : "–"}</div>
        </div>
      </div>

      {error && <p className="error-text">{error}</p>}

      {!items ? (
        <div className="panel empty-state">Loading worklist…</div>
      ) : items.length === 0 ? (
        <div className="panel empty-state">
          <h2>No cases here</h2>
          <p>
            {specialty
              ? `New ${specialty.name.toLowerCase()} studies appear here once AI analysis finishes.`
              : "New studies appear here once AI analysis finishes."}
          </p>
          <Link to="/models">See which AI models are deployed</Link>
        </div>
      ) : (
        <table className="data-table worklist-table">
          <thead>
            <tr>
              <th>Priority</th>
              <th>Patient</th>
              <th>Study</th>
              <th>AI finding</th>
              <th>Waiting</th>
              <th>SLA</th>
              <th>State</th>
              <th>Reader</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {items.map((it) => {
              const sla = slaStatus(it.slaDueAt, now);
              const sp = specialtyById(it.specialty);
              return (
                <tr key={it.studyId} className={it.urgencyClass ? `urgency-${it.urgencyClass}` : ""}>
                  <td>
                    <div className="priority-score">{it.effectivePriority.toFixed(1)}</div>
                    <UrgencyBadge urgency={it.urgencyClass} />
                  </td>
                  <td>
                    <div className="cell-primary numeric">{it.patientMrn}</div>
                    <div className="cell-secondary">MRN</div>
                  </td>
                  <td>
                    <div className="cell-primary">
                      {it.modality} · {it.bodyPart}
                    </div>
                    {sp && (
                      <span className="specialty-chip">
                        <SpecialtyIcon specialty={sp.id} /> {sp.name}
                      </span>
                    )}
                  </td>
                  <td>
                    {it.topLabel ? (
                      <>
                        <div className="cell-primary">{it.topLabel}</div>
                        {it.topProbability != null && (
                          <div className="cell-secondary numeric">{probability(it.topProbability)} model probability</div>
                        )}
                      </>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                  <td className="numeric">{waited(it.studyCreatedAt, now)}</td>
                  <td>
                    {sla ? (
                      <span className={`sla sla-${sla.state}`}>
                        <Icon.Clock /> {sla.text}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    <StateBadge state={it.state} />
                  </td>
                  <td>{it.assignedTo ?? <span className="muted">Unassigned</span>}</td>
                  <td>
                    {it.state === "OPEN" ? (
                      <button
                        className="small-button"
                        disabled={claiming === it.studyId}
                        onClick={() => claim(it.studyId)}
                      >
                        {claiming === it.studyId ? "Claiming…" : "Claim"}
                      </button>
                    ) : (
                      <Link className="button" to={`/studies/${it.studyId}`}>
                        Open
                      </Link>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
