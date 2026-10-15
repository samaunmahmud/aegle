import { useState } from "react";
import type { Urgency } from "../api/types";
import { titleCase } from "../format";
import { Icon } from "./Icons";

type Term = { label: string; weight: number; probability: number; contribution: number; urgencyClass: Urgency };
type Reason = { terms?: Term[]; formula?: string };

function asReason(r: unknown): Reason | null {
  return r && typeof r === "object" && Array.isArray((r as Reason).terms) ? (r as Reason) : null;
}

/**
 * How a triage score was built, from the reason core-api stores with it: each label's
 * probability times its urgency weight, plus a bonus for time waiting. Shown so that a
 * clinician can see why a case sits where it does, and disagree with it.
 */
export function PriorityBreakdown({ reason, waitBonus }: { reason: unknown; waitBonus?: number }) {
  const r = asReason(reason);
  if (!r) return <p className="pane-sub">No breakdown recorded for this study.</p>;
  const terms = (r.terms ?? []).filter((t) => t.contribution >= 0.05).sort((a, b) => b.contribution - a.contribution);
  const total = terms.reduce((n, t) => n + t.contribution, 0) + (waitBonus ?? 0);
  const scale = Math.max(total, 1);
  return (
    <div className="pbreak">
      <div className="pbreak-bar" aria-hidden="true">
        {terms.map((t) => (
          <span key={t.label} className={`seg seg-${t.urgencyClass}`} style={{ width: `${(t.contribution / scale) * 100}%` }} />
        ))}
        {waitBonus ? <span className="seg seg-wait" style={{ width: `${(waitBonus / scale) * 100}%` }} /> : null}
      </div>
      {/* A grid, not a table: it sits inside worklist rows, whose table styles would leak in. */}
      <div className="pbreak-rows" role="list">
        {terms.map((t) => (
          <div key={t.label} className="pbreak-row" role="listitem">
            <span>
              <span className={`swatch seg-${t.urgencyClass}`} /> {titleCase(t.label)}
            </span>
            <span className="numeric">
              {(t.probability * 100).toFixed(1)}% × {t.weight}
            </span>
            <span className="numeric">{t.contribution.toFixed(1)}</span>
          </div>
        ))}
        {waitBonus != null && (
          <div className="pbreak-row" role="listitem">
            <span>
              <span className="swatch seg-wait" /> Time waiting
            </span>
            <span className="numeric">0.5 / hour, max 20</span>
            <span className="numeric">{waitBonus.toFixed(1)}</span>
          </div>
        )}
        <div className="pbreak-row pbreak-total" role="listitem">
          <span>Priority score</span>
          <span />
          <span className="numeric">{total.toFixed(1)}</span>
        </div>
      </div>
    </div>
  );
}

/** Info button that opens the breakdown on hover or keyboard focus (worklist rows). */
export function PriorityExplain({ reason, waitBonus }: { reason: unknown; waitBonus: number }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="pexplain"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onClick={(e) => e.stopPropagation()}
    >
      <button
        type="button"
        className="pexplain-button"
        aria-label="Why this priority?"
        aria-expanded={open}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        <Icon.Info />
      </button>
      {open && (
        <span className="pexplain-pop" role="tooltip">
          <strong>Why this priority?</strong>
          <PriorityBreakdown reason={reason} waitBonus={waitBonus} />
        </span>
      )}
    </span>
  );
}
