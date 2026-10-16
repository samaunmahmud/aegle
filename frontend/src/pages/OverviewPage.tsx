import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { ModelEntry } from "../api/types";
import { useDepartmentSummary } from "../components/DepartmentSummary";
import { useAuth } from "../auth/AuthContext";
import { Icon, SpecialtyIcon } from "../components/Icons";
import { MedicalArt } from "../components/MedicalArt";
import { CountUp } from "../components/CountUp";
import { WorkloadChart } from "../components/WorkloadChart";
import { clinicalDay, clock, waited } from "../format";
import { SPECIALTIES } from "../specialties";

function greeting(d: Date) {
  const h = d.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function OverviewPage() {
  const { name } = useAuth();
  const { summary, updatedAt } = useDepartmentSummary();
  const [models, setModels] = useState<ModelEntry[]>([]);
  const now = updatedAt || Date.now();

  useEffect(() => {
    api.models().then(setModels).catch(() => setModels([]));
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
  const first = name.split(/\s+/)[0];

  return (
    <div>
      <div className="dept-hero">
        <div>
          <div className="hero-kicker">
            {clinicalDay(new Date(now))} · {clock(new Date(now))}
          </div>
          <h1>
            {greeting(new Date(now))}, {first}
          </h1>
          <p className="page-subtitle">
            Seven departments, {live.length} AI models screening incoming studies. Critical findings rise to the top
            of every worklist.
          </p>
        </div>
        <div className="hero-stats" aria-label="Department totals">
          <Link to="/worklist" className="hero-stat">
            <span className="hero-n">{summary ? <CountUp value={totals.open} /> : "–"}</span>
            <span>open studies</span>
          </Link>
          <Link to="/worklist" className="hero-stat hero-critical">
            <span className="hero-n">{summary ? <CountUp value={totals.critical} /> : "–"}</span>
            <span>critical</span>
          </Link>
          <Link to="/worklist" className="hero-stat hero-urgent">
            <span className="hero-n">{summary ? <CountUp value={totals.urgent} /> : "–"}</span>
            <span>urgent</span>
          </Link>
          <Link to="/worklist" className="hero-stat hero-breached">
            <span className="hero-n">{summary ? <CountUp value={totals.breached} /> : "–"}</span>
            <span>past report deadline</span>
          </Link>
        </div>
      </div>

      {summary && <WorkloadChart summary={summary} />}

      <div className="dept-grid">
        {SPECIALTIES.map((sp) => {
          const s = bySpecialty.get(sp.id);
          const spModels = live.filter((m) => m.specialty === sp.id);
          const openCount = s ? s.open + s.inReview : 0;
          return (
            <Link key={sp.id} to={`/worklist/${sp.slug}`} className="dept-card">
              <div className="dept-art">
                <MedicalArt specialty={sp.id} />
                <span className="art-caption">{sp.imaging}</span>
                {s && s.critical > 0 && <span className="art-alert">{s.critical} critical</span>}
              </div>
              <div className="dept-body">
                <div className="dept-title">
                  <span className="dept-icon">
                    <SpecialtyIcon specialty={sp.id} />
                  </span>
                  <div>
                    <h2>{sp.name}</h2>
                    <div className="cell-secondary">{sp.summary}</div>
                  </div>
                </div>
                <div className="dept-counts">
                  <div>
                    <b>{openCount}</b>
                    <span>open</span>
                  </div>
                  <div className={s?.critical ? "is-critical" : ""}>
                    <b>{s?.critical ?? 0}</b>
                    <span>critical</span>
                  </div>
                  <div className={s?.urgent ? "is-urgent" : ""}>
                    <b>{s?.urgent ?? 0}</b>
                    <span>urgent</span>
                  </div>
                  <div className={s?.slaBreached ? "is-critical" : ""}>
                    <b>{s?.slaBreached ?? 0}</b>
                    <span>overdue</span>
                  </div>
                </div>
                <div className="dept-foot">
                  <span className="cell-secondary">
                    {spModels.length === 0 ? (
                      "No AI model live"
                    ) : (
                      <>
                        <Icon.Sparkle /> {spModels.length} AI model{spModels.length === 1 ? "" : "s"} live
                      </>
                    )}
                    {s?.oldestWaitingSince ? ` · oldest ${waited(s.oldestWaitingSince, now)}` : ""}
                  </span>
                  <span className="dept-go">
                    Worklist <Icon.Chevron />
                  </span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
