import { useState } from "react";
import { Link } from "react-router-dom";
import type { SpecialtySummary } from "../api/types";
import { SPECIALTIES } from "../specialties";
import { SpecialtyIcon } from "./Icons";

type Row = { slug: string; name: string; id: SpecialtySummary["specialty"]; critical: number; urgent: number; other: number; total: number; overdue: number };

/**
 * Open studies by department, split by AI priority, from the summary the app already polls:
 * no patient-level reads. Status colours mean status here (critical, urgent), so the rest
 * of the queue is a neutral grey.
 */
export function WorkloadChart({ summary }: { summary: SpecialtySummary[] }) {
  const [hover, setHover] = useState<string | null>(null);
  const by = new Map(summary.map((s) => [s.specialty, s]));
  const rows: Row[] = SPECIALTIES.map((sp) => {
    const s = by.get(sp.id);
    const total = s ? s.open + s.inReview : 0;
    const critical = s?.critical ?? 0;
    const urgent = s?.urgent ?? 0;
    return { slug: sp.slug, name: sp.name, id: sp.id, critical, urgent, other: Math.max(0, total - critical - urgent), total, overdue: s?.slaBreached ?? 0 };
  }).sort((a, b) => b.critical - a.critical || b.total - a.total);
  const max = Math.max(1, ...rows.map((r) => r.total));
  const h = rows.find((r) => r.slug === hover);

  return (
    <section className="panel workload" aria-labelledby="workload-title">
      <div className="workload-head">
        <h2 id="workload-title">Workload by department</h2>
        <span className="viz-legend">
          <span className="lg lg-critical" /> Critical <span className="lg lg-urgent" /> Urgent <span className="lg lg-other" /> Other open
        </span>
      </div>
      <div className="workload-rows" onMouseLeave={() => setHover(null)}>
        {rows.map((r) => (
          <Link
            key={r.slug}
            to={`/worklist/${r.slug}`}
            className={`workload-row${hover === r.slug ? " on" : ""}`}
            onMouseEnter={() => setHover(r.slug)}
            onFocus={() => setHover(r.slug)}
            aria-label={`${r.name}: ${r.total} open, ${r.critical} critical, ${r.urgent} urgent, ${r.overdue} overdue`}
          >
            <span className="workload-name">
              <SpecialtyIcon specialty={r.id} /> {r.name}
            </span>
            <span className="workload-track" aria-hidden="true">
              {r.critical > 0 && <span className="wseg wseg-critical" style={{ width: `${(r.critical / max) * 100}%` }} />}
              {r.urgent > 0 && <span className="wseg wseg-urgent" style={{ width: `${(r.urgent / max) * 100}%` }} />}
              {r.other > 0 && <span className="wseg wseg-other" style={{ width: `${(r.other / max) * 100}%` }} />}
            </span>
            <span className="workload-total numeric">{r.total}</span>
            <span className={`workload-overdue numeric${r.overdue ? " is-overdue" : ""}`}>{r.overdue ? `${r.overdue} overdue` : "on time"}</span>
          </Link>
        ))}
      </div>
      <div className="viz-readout" aria-live="polite">
        {h
          ? `${h.name}: ${h.total} open — ${h.critical} critical, ${h.urgent} urgent, ${h.other} other; ${h.overdue} past the report deadline.`
          : "Bars share one scale. Departments with critical findings come first. Select a row to open its worklist."}
      </div>
    </section>
  );
}
