import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { ModelEntry, SpecialtySummary } from "../api/types";
import { Icon, SpecialtyIcon } from "../components/Icons";
import { PageHeader } from "../components/PageHeader";
import { waited } from "../format";
import { SPECIALTIES } from "../specialties";

export function OverviewPage() {
  const [summary, setSummary] = useState<SpecialtySummary[] | null>(null);
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const load = () =>
      api
        .worklistSummary()
        .then((s) => {
          setSummary(s);
          setNow(Date.now());
        })
        .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load the overview"));
    load();
    api.models().then(setModels).catch(() => setModels([]));
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  const bySpecialty = new Map((summary ?? []).map((s) => [s.specialty, s]));
  const totals = (summary ?? []).reduce(
    (t, s) => ({
      open: t.open + s.open + s.inReview,
      critical: t.critical + s.critical,
      urgent: t.urgent + s.urgent,
      breached: t.breached + s.slaBreached,
    }),
    { open: 0, critical: 0, urgent: 0, breached: 0 },
  );
  const live = models.filter((m) => m.activeVersion && m.enabledForOrganisation);

  return (
    <div>
      <PageHeader
        icon={<Icon.Overview />}
        title="Department overview"
        subtitle="Open AI-triaged work across every specialty. Refreshes every 30 seconds."
      />
      {error && <p className="error-text">{error}</p>}

      <div className="stat-row">
        <div className="panel stat">
          <div className="stat-label">Open cases</div>
          <div className="stat-value">{summary ? totals.open : "–"}</div>
        </div>
        <div className="panel stat stat-critical">
          <div className="stat-label">Critical</div>
          <div className="stat-value">{summary ? totals.critical : "–"}</div>
        </div>
        <div className="panel stat stat-urgent">
          <div className="stat-label">Urgent</div>
          <div className="stat-value">{summary ? totals.urgent : "–"}</div>
        </div>
        <div className="panel stat stat-critical">
          <div className="stat-label">Past SLA</div>
          <div className="stat-value">{summary ? totals.breached : "–"}</div>
        </div>
        <div className="panel stat">
          <div className="stat-label">AI models live</div>
          <div className="stat-value">{live.length}</div>
        </div>
      </div>

      <div className="specialty-grid">
        {SPECIALTIES.map((sp) => {
          const s = bySpecialty.get(sp.id);
          const spModels = live.filter((m) => m.specialty === sp.id);
          const openCount = s ? s.open + s.inReview : 0;
          return (
            <Link
              key={sp.id}
              to={`/worklist/${sp.slug}`}
              className={`panel specialty-tile${openCount === 0 && spModels.length === 0 ? " specialty-tile-idle" : ""}`}
            >
              <div className="specialty-tile-head">
                <span className="page-title-icon">
                  <SpecialtyIcon specialty={sp.id} />
                </span>
                <div>
                  <h2>{sp.name}</h2>
                  <div className="cell-secondary">
                    {spModels.length === 0
                      ? "No AI model live"
                      : `${spModels.length} AI model${spModels.length === 1 ? "" : "s"} live`}
                  </div>
                </div>
              </div>
              <div className="specialty-tile-count">
                <span className="stat-value">{openCount}</span>
                <span className="cell-secondary">open {openCount === 1 ? "case" : "cases"}</span>
              </div>
              <div className="toolbar">
                {s && s.critical > 0 && <span className="badge badge-critical">{s.critical} critical</span>}
                {s && s.urgent > 0 && <span className="badge badge-urgent">{s.urgent} urgent</span>}
                {s && s.slaBreached > 0 && <span className="badge badge-critical">{s.slaBreached} past SLA</span>}
                {s && s.inReview > 0 && <span className="badge badge-progress">{s.inReview} in review</span>}
                {!s && <span className="cell-secondary">Nothing waiting</span>}
              </div>
              {s?.oldestWaitingSince && (
                <div className="cell-secondary">Oldest waiting {waited(s.oldestWaitingSince, now)}</div>
              )}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
