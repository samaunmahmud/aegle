import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { WorklistItem, WorklistState } from "../api/types";
import { useDepartmentSummary } from "../components/DepartmentSummary";
import { AiTag, PriorityTag, StateBadge } from "../components/Badges";
import { PriorityExplain } from "../components/PriorityExplain";
import { Icon, SpecialtyIcon } from "../components/Icons";
import { clock, probability, slaStatus, titleCase, waited } from "../format";
import { SPECIALTIES, specialtyById, specialtyBySlug } from "../specialties";

const VIEWS: { id: string; label: string; states: WorklistState[] }[] = [
  { id: "active", label: "Active", states: ["OPEN", "IN_REVIEW"] },
  { id: "open", label: "Unclaimed", states: ["OPEN"] },
  { id: "done", label: "Reported", states: ["DONE"] },
];

type Filter = "all" | "critical" | "urgent" | "breached";
type SortKey = "priority" | "waiting" | "sla" | "mrn";

const SORTS: Record<SortKey, (a: WorklistItem, b: WorklistItem) => number> = {
  priority: (a, b) => b.effectivePriority - a.effectivePriority,
  waiting: (a, b) => Date.parse(a.studyCreatedAt) - Date.parse(b.studyCreatedAt),
  sla: (a, b) => (a.slaDueAt ? Date.parse(a.slaDueAt) : Infinity) - (b.slaDueAt ? Date.parse(b.slaDueAt) : Infinity),
  mrn: (a, b) => a.patientMrn.localeCompare(b.patientMrn),
};

export function WorklistPage() {
  const { specialty: slug } = useParams<{ specialty?: string }>();
  const [params, setParams] = useSearchParams();
  const specialty = specialtyBySlug(slug);
  const [view, setView] = useState(VIEWS[0]);
  const [items, setItems] = useState<WorklistItem[] | null>(null);
  const summary = useDepartmentSummary().summary ?? [];
  const [error, setError] = useState<string | null>(null);
  const [claiming, setClaiming] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<SortKey>("priority");
  const [cursor, setCursor] = useState(0);
  const mrn = params.get("mrn") ?? "";
  const navigate = useNavigate();
  const tableRef = useRef<HTMLTableSectionElement>(null);

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



  const counts = useMemo(() => {
    const list = (items ?? []).filter((i) => !mrn || i.patientMrn.toLowerCase().includes(mrn.toLowerCase()));
    return {
      list,
      all: list.length,
      critical: list.filter((i) => i.urgencyClass === "CRITICAL").length,
      urgent: list.filter((i) => i.urgencyClass === "URGENT").length,
      breached: list.filter((i) => i.slaBreached).length,
    };
  }, [items, mrn]);

  const rows = useMemo(() => {
    const keep: Record<Filter, (i: WorklistItem) => boolean> = {
      all: () => true,
      critical: (i) => i.urgencyClass === "CRITICAL",
      urgent: (i) => i.urgencyClass === "URGENT",
      breached: (i) => i.slaBreached,
    };
    return counts.list.filter(keep[filter]).sort(SORTS[sort]);
  }, [counts.list, filter, sort]);

  useEffect(() => setCursor(0), [filter, sort, mrn, slug, view]);

  async function claim(studyId: string) {
    setClaiming(studyId);
    try {
      await api.claim(studyId);
      navigate(`/studies/${studyId}`); // claiming a case means reading it now
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to claim case");
    } finally {
      setClaiming(null);
    }
  }

  // Keyboard reading: up/down moves through the list, Enter opens. Ignored while typing.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT", "BUTTON", "A"].includes(t.tagName) || rows.length === 0) return;
      if (e.key === "ArrowDown" || e.key === "j") {
        e.preventDefault();
        setCursor((c) => Math.min(rows.length - 1, c + 1));
      } else if (e.key === "ArrowUp" || e.key === "k") {
        e.preventDefault();
        setCursor((c) => Math.max(0, c - 1));
      } else if (e.key === "Enter") {
        navigate(`/studies/${rows[cursor].studyId}`);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, cursor, navigate]);

  useEffect(() => {
    tableRef.current?.children[cursor]?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  const bySpecialty = new Map(summary.map((s) => [s.specialty, s]));
  const totalOpen = summary.reduce((n, s) => n + s.open + s.inReview, 0);

  function SortHeader({ k, children }: { k: SortKey; children: string }) {
    return (
      <th aria-sort={sort === k ? "descending" : "none"}>
        <button type="button" className={`sort-button${sort === k ? " active" : ""}`} onClick={() => setSort(k)}>
          {children}
          <span aria-hidden="true">{sort === k ? "▾" : "↕"}</span>
        </button>
      </th>
    );
  }

  return (
    <div className="worklist-layout">
      <aside className="dept-rail" aria-label="Departments">
        <div className="rail-heading">Departments</div>
        <Link to="/worklist" className={`dept-link${!specialty ? " active" : ""}`}>
          <Icon.Worklist />
          <span>All departments</span>
          <span className="dept-count">{totalOpen}</span>
        </Link>
        {SPECIALTIES.map((sp) => {
          const s = bySpecialty.get(sp.id);
          const open = s ? s.open + s.inReview : 0;
          return (
            <Link key={sp.id} to={`/worklist/${sp.slug}`} className={`dept-link${specialty?.id === sp.id ? " active" : ""}`}>
              <SpecialtyIcon specialty={sp.id} />
              <span>{sp.name}</span>
              {s && s.critical > 0 && (
                <span className="dept-critical" title={`${s.critical} critical`}>
                  {s.critical}
                </span>
              )}
              <span className="dept-count">{open}</span>
            </Link>
          );
        })}
        <div className="rail-help">
          <Icon.Keyboard />
          <span>
            <kbd>↑</kbd> <kbd>↓</kbd> move · <kbd>Enter</kbd> open · <kbd>/</kbd> find patient
          </span>
        </div>
      </aside>

      <section className="worklist-main">
        <div className="worklist-head">
          <div>
            <h1>{specialty ? `${specialty.name}` : "Reporting worklist"}</h1>
            <div className="page-subtitle">
              {specialty ? specialty.summary : "All departments"} · ranked by AI-assessed urgency and time waiting
            </div>
          </div>
          <div className="live-indicator" title="Refreshes every 15 seconds">
            <span className="live-dot" /> Live · updated {clock(new Date(now))}
          </div>
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
        </div>

        <div className="filter-strip">
          {(
            [
              ["all", "All", counts.all],
              ["critical", "Critical", counts.critical],
              ["urgent", "Urgent", counts.urgent],
              ["breached", "Past SLA", counts.breached],
            ] as [Filter, string, number][]
          ).map(([f, label, n]) => (
            <button
              key={f}
              type="button"
              className={`filter-chip filter-${f}${filter === f ? " on" : ""}`}
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
            >
              {label} <span className="filter-n">{items ? n : "–"}</span>
            </button>
          ))}
          <div className="appbar-spacer" />
          <label className="mrn-filter">
            <Icon.Search />
            <input
              value={mrn}
              placeholder="Filter by MRN"
              aria-label="Filter by MRN"
              onChange={(e) => {
                const v = e.target.value;
                setParams(v ? { mrn: v } : {}, { replace: true });
              }}
            />
          </label>
        </div>

        {error && <p className="error-text">{error}</p>}

        {!items ? (
          <div className="panel empty-state">Loading worklist…</div>
        ) : rows.length === 0 ? (
          <div className="panel empty-state">
            <h2>{mrn ? `No studies for MRN “${mrn}”` : "Nothing waiting"}</h2>
            <p>
              {mrn
                ? "Check the number, or look under Reported."
                : `New ${specialty ? specialty.name.toLowerCase() + " " : ""}studies appear here as soon as AI analysis finishes.`}
            </p>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table worklist-table">
              <thead>
                <tr>
                  <SortHeader k="priority">Priority</SortHeader>
                  <SortHeader k="mrn">Patient</SortHeader>
                  <th>Examination</th>
                  <th>AI finding</th>
                  <SortHeader k="waiting">Waiting</SortHeader>
                  <SortHeader k="sla">Report due</SortHeader>
                  <th>Status</th>
                  <th>Reader</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody ref={tableRef}>
                {rows.map((it, i) => {
                  const sla = slaStatus(it.slaDueAt, now);
                  const sp = specialtyById(it.specialty);
                  return (
                    <tr
                      key={it.studyId}
                      className={`${it.urgencyClass ? `urgency-${it.urgencyClass}` : ""}${i === cursor ? " cursor" : ""}`}
                      onClick={() => navigate(`/studies/${it.studyId}`)}
                      onMouseEnter={() => setCursor(i)}
                    >
                      <td>
                        <PriorityTag urgency={it.urgencyClass} />
                        <span className="priority-score">{it.effectivePriority.toFixed(0)}</span>
                        <PriorityExplain reason={it.priorityReason} waitBonus={it.waitBonus} />
                      </td>
                      <td>
                        <span className="mrn">{it.patientMrn}</span>
                      </td>
                      <td>
                        <div className="exam">
                          {sp && (
                            <span className="exam-icon" title={sp.name}>
                              <SpecialtyIcon specialty={sp.id} />
                            </span>
                          )}
                          <div>
                            <div className="cell-primary">
                              {it.modality} {titleCase(it.bodyPart)}
                            </div>
                            <div className="cell-secondary">{sp?.name}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        {it.topLabel ? (
                          <div className="ai-finding">
                            <AiTag />
                            <div>
                              <div className="cell-primary">{titleCase(it.topLabel)}</div>
                              {it.topProbability != null && (
                                <div className="confidence">
                                  <span className="confidence-bar">
                                    <span style={{ width: `${it.topProbability * 100}%` }} />
                                  </span>
                                  <span className="numeric">{probability(it.topProbability)}</span>
                                </div>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="muted">Awaiting AI</span>
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
                      <td onClick={(e) => e.stopPropagation()}>
                        {it.state === "OPEN" ? (
                          <button
                            className="small-button"
                            disabled={claiming === it.studyId}
                            onClick={() => claim(it.studyId)}
                          >
                            {claiming === it.studyId ? "Claiming…" : "Claim & read"}
                          </button>
                        ) : (
                          <Link className="button button-quiet" to={`/studies/${it.studyId}`}>
                            Open
                          </Link>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
