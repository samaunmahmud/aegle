/* eslint-disable react-refresh/only-export-components -- provider and hook belong together */
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { SpecialtySummary } from "../api/types";
import { SPECIALTIES, specialtyById } from "../specialties";
import { Icon, SpecialtyIcon } from "./Icons";

type Alert = { id: number; specialty: SpecialtySummary["specialty"]; added: number };

type State = { summary: SpecialtySummary[] | null; updatedAt: number };

const Ctx = createContext<State>({ summary: null, updatedAt: 0 });

export function useDepartmentSummary() {
  return useContext(Ctx);
}

const POLL_MS = 30_000;

/**
 * One poll of the department summary for the whole app (every read is audited, so pages
 * share it instead of each polling). A rise in a department's critical count raises an
 * alert that stays until someone acknowledges it, as critical results must be.
 */
export function DepartmentSummaryProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const [state, setState] = useState<State>({ summary: null, updatedAt: 0 });
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const previous = useRef<Map<string, number> | null>(null);
  const nextId = useRef(1);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const load = () =>
      api
        .worklistSummary()
        .then((s) => {
          if (cancelled) return;
          const before = previous.current;
          if (before) {
            const raised = s
              .filter((d) => d.critical > (before.get(d.specialty) ?? 0))
              .map((d) => ({ id: nextId.current++, specialty: d.specialty, added: d.critical - (before.get(d.specialty) ?? 0) }));
            if (raised.length) setAlerts((a) => [...a, ...raised]);
          }
          previous.current = new Map(s.map((d) => [d.specialty, d.critical]));
          setState({ summary: s, updatedAt: Date.now() });
        })
        .catch(() => undefined);
    load();
    const t = setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [enabled]);

  // The tab title carries the critical count, so it is visible from other tabs.
  const critical = (state.summary ?? []).reduce((n, s) => n + s.critical, 0);
  useEffect(() => {
    document.title = critical > 0 ? `(${critical}) Aegle · Clinical Imaging` : "Aegle · Clinical Imaging";
  }, [critical]);

  return (
    <Ctx.Provider value={state}>
      {children}
      {alerts.length > 0 && (
        <div className="toast-stack" role="alert" aria-live="assertive">
          {alerts.map((a) => {
            const sp = specialtyById(a.specialty);
            return (
              <div key={a.id} className="toast toast-critical">
                <div className="toast-icon">
                  <Icon.Alert />
                </div>
                <div className="toast-body">
                  <strong>New critical finding · {sp?.name}</strong>
                  <span>
                    {a.added} new P1 case{a.added === 1 ? "" : "s"} flagged by AI, awaiting a report.
                  </span>
                  <div className="toast-actions">
                    <Link to={`/worklist/${sp?.slug ?? ""}`} onClick={() => setAlerts((x) => x.filter((y) => y.id !== a.id))}>
                      Open worklist
                    </Link>
                    <button type="button" className="link-button" onClick={() => setAlerts((x) => x.filter((y) => y.id !== a.id))}>
                      Acknowledge
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Ctx.Provider>
  );
}

/** App-bar bell: open critical findings by department. */
export function CriticalBell() {
  const { summary } = useDepartmentSummary();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const critical = (summary ?? []).filter((s) => s.critical > 0);
  const total = critical.reduce((n, s) => n + s.critical, 0);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div className="bell" ref={ref}>
      <button
        className="icon-button bell-button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={`${total} critical findings awaiting report`}
        title="Critical findings"
      >
        <Icon.Bell />
        {total > 0 && <span className="bell-count">{total}</span>}
      </button>
      {open && (
        <div className="bell-panel" role="dialog" aria-label="Critical findings">
          <div className="bell-head">
            <strong>Critical findings</strong>
            <span>P1 AI findings awaiting a report</span>
          </div>
          {critical.length === 0 ? (
            <p className="bell-empty">None waiting. New ones raise an alert here.</p>
          ) : (
            SPECIALTIES.filter((sp) => critical.some((c) => c.specialty === sp.id)).map((sp) => {
              const s = critical.find((c) => c.specialty === sp.id)!;
              return (
                <Link key={sp.id} to={`/worklist/${sp.slug}`} className="bell-row" onClick={() => setOpen(false)}>
                  <SpecialtyIcon specialty={sp.id} />
                  <span>{sp.name}</span>
                  <span className="dept-critical">{s.critical}</span>
                </Link>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
