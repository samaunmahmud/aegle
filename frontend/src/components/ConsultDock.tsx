/* eslint-disable react-refresh/only-export-components -- the dock and its open-event helper belong together */
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { ApiError, api } from "../api/client";
import type { ConsultBox, ConsultDetail, ConsultMessage, ConsultThread, Grade, Me, Person } from "../api/types";
import { SPECIALTIES, specialtyById, type Specialty } from "../specialties";
import { Avatar } from "./Avatar";
import { Icon } from "./Icons";

type Size = "min" | "open" | "max";
type View = { kind: "list" } | { kind: "thread"; id: string } | { kind: "new"; studyId?: string; specialty?: Specialty; subject?: string };
type Prefill = { studyId?: string; specialty?: Specialty; subject?: string };

const SIZE_KEY = "aegle.consults.size";
const EVENT = "aegle:consult";

/** Open the consult dock on a new question, e.g. from a study ("Ask a colleague"). */
export function askColleague(prefill: Prefill) {
  window.dispatchEvent(new CustomEvent<Prefill>(EVENT, { detail: prefill }));
}

export const GRADE_LABEL: Record<Grade, string> = { CONSULTANT: "Consultant", REGISTRAR: "Registrar", FOUNDATION: "Foundation" };

function storedSize(): Size {
  try {
    const v = localStorage.getItem(SIZE_KEY);
    return v === "open" || v === "max" ? v : "min";
  } catch {
    return "min";
  }
}

function ago(iso: string, now: number) {
  const m = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60_000));
  if (m < 1) return "now";
  if (m < 60) return `${m}m`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.round(h / 24)}d`;
}

function time(iso: string) {
  return new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
}

function GradeTag({ grade }: { grade: Grade | null }) {
  if (!grade) return null;
  return <span className={`grade grade-${grade}`}>{GRADE_LABEL[grade]}</span>;
}

/**
 * Consults: ask a colleague about a case without leaving it. Docked on the right of every
 * clinical page; minimised to a rail that still shows what is waiting for you.
 */
export function ConsultDock({ me }: { me: Me | null }) {
  const [size, setSizeState] = useState<Size>(storedSize);
  const [view, setView] = useState<View>({ kind: "list" });
  const [unread, setUnread] = useState({ unreadThreads: 0, askedOfMe: 0, askedOfMeUnread: 0 });
  const location = useLocation();

  const setSize = (s: Size) => {
    setSizeState(s);
    try {
      localStorage.setItem(SIZE_KEY, s);
    } catch {
      // storage refused (private window): the size still applies until reload
    }
  };

  // Counts only, so cheap to poll and not audited server-side.
  const refreshUnread = useCallback(() => {
    api.consultUnread().then(setUnread).catch(() => undefined);
  }, []);
  useEffect(() => {
    refreshUnread();
    const t = setInterval(refreshUnread, 20_000);
    return () => clearInterval(t);
  }, [refreshUnread]);

  useEffect(() => {
    const open = (e: Event) => {
      const p = (e as CustomEvent<Prefill>).detail ?? {};
      setView({ kind: "new", ...p });
      setSizeState((s) => (s === "min" ? "open" : s));
    };
    window.addEventListener(EVENT, open);
    return () => window.removeEventListener(EVENT, open);
  }, []);

  const studyOnScreen = location.pathname.match(/^\/studies\/([0-9a-f-]{36})/)?.[1];
  const badge = unread.askedOfMeUnread || unread.unreadThreads;

  if (size === "min") {
    return (
      <aside className="consult-rail" aria-label="Consults">
        <button type="button" className="rail-button" onClick={() => setSize("open")} title="Open consults" aria-label={`Open consults, ${badge} unread`}>
          <Icon.Chat />
          {badge > 0 && <span className="rail-badge">{badge}</span>}
        </button>
        <span className="rail-label">Consults</span>
        {unread.askedOfMe > 0 && (
          <button
            type="button"
            className="rail-pill"
            onClick={() => setSize("open")}
            title={`${unread.askedOfMe} consult${unread.askedOfMe === 1 ? "" : "s"} asked of you`}
          >
            {unread.askedOfMe}
            <small>for you</small>
          </button>
        )}
        <button
          type="button"
          className="rail-button rail-ask"
          onClick={() => {
            setView({ kind: "new", studyId: studyOnScreen });
            setSize("open");
          }}
          title="Ask a colleague"
          aria-label="Ask a colleague"
        >
          <Icon.Plus />
        </button>
      </aside>
    );
  }

  return (
    <aside className={`consult-dock consult-${size}`} aria-label="Consults">
      <header className="dock-head">
        <div className="dock-title">
          <Icon.Chat />
          <div>
            <strong>Consults</strong>
            <span>Ask a colleague · kept with the case</span>
          </div>
        </div>
        <div className="dock-actions">
          {view.kind !== "new" && (
            <button type="button" className="dock-icon" onClick={() => setView({ kind: "new", studyId: studyOnScreen })} title="New consult" aria-label="New consult">
              <Icon.Plus />
            </button>
          )}
          <button
            type="button"
            className="dock-icon"
            onClick={() => setSize(size === "max" ? "open" : "max")}
            title={size === "max" ? "Restore" : "Maximise"}
            aria-label={size === "max" ? "Restore consults panel" : "Maximise consults panel"}
          >
            {size === "max" ? <Icon.Restore /> : <Icon.Expand />}
          </button>
          <button type="button" className="dock-icon" onClick={() => setSize("min")} title="Minimise" aria-label="Minimise consults panel">
            <Icon.Minimise />
          </button>
        </div>
      </header>
      {view.kind === "list" && <ThreadList unread={unread} onOpen={(id) => setView({ kind: "thread", id })} />}
      {view.kind === "thread" && (
        <ThreadView key={view.id} id={view.id} me={me} onBack={() => setView({ kind: "list" })} onChange={refreshUnread} />
      )}
      {view.kind === "new" && (
        <NewConsultForm
          prefill={view}
          me={me}
          studyOnScreen={studyOnScreen}
          onCancel={() => setView({ kind: "list" })}
          onCreated={(d) => {
            setView({ kind: "thread", id: d.thread.id });
            refreshUnread();
          }}
        />
      )}
    </aside>
  );
}

// ---------------------------------------------------------------- thread list

const BOXES: { id: ConsultBox; label: string }[] = [
  { id: "for-me", label: "For me" },
  { id: "mine", label: "I asked" },
  { id: "open", label: "All open" },
  { id: "resolved", label: "Resolved" },
];

function ThreadList({ unread, onOpen }: { unread: { askedOfMe: number }; onOpen: (id: string) => void }) {
  const [box, setBox] = useState<ConsultBox>(unread.askedOfMe > 0 ? "for-me" : "open");
  const [threads, setThreads] = useState<ConsultThread[] | null>(null);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      api
        .consults(box)
        .then((t) => {
          if (!cancelled) {
            setThreads(t);
            setNow(Date.now());
          }
        })
        .catch(() => !cancelled && setThreads([]));
    setThreads(null);
    load();
    const t = setInterval(load, 15_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [box]);

  return (
    <div className="dock-body">
      <div className="dock-tabs" role="tablist">
        {BOXES.map((b) => (
          <button key={b.id} role="tab" aria-selected={box === b.id} className={box === b.id ? "on" : ""} onClick={() => setBox(b.id)}>
            {b.label}
            {b.id === "for-me" && unread.askedOfMe > 0 && <span className="tab-n">{unread.askedOfMe}</span>}
          </button>
        ))}
      </div>
      <div className="thread-list">
        {threads === null &&
          Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton-light thread-skeleton" />)}
        {threads?.length === 0 && (
          <div className="dock-empty">
            <Icon.Chat />
            <p>{box === "for-me" ? "Nobody is waiting on you." : "No consults here yet."}</p>
            <span>Unsure about a case? Ask a senior colleague. The thread stays linked to the study.</span>
          </div>
        )}
        {threads?.map((t) => {
          const sp = t.specialty ? specialtyById(t.specialty) : null;
          return (
            <button key={t.id} type="button" className={`thread-item${t.unread ? " is-unread" : ""}`} onClick={() => onOpen(t.id)}>
              <span className="thread-avatars">
                <Avatar name={t.createdBy.name} avatar={t.createdBy.avatar} size={34} />
                {t.askedOf && (
                  <span className="thread-avatar-2">
                    <Avatar name={t.askedOf.name} avatar={t.askedOf.avatar} size={20} ring />
                  </span>
                )}
              </span>
              <span className="thread-main">
                <span className="thread-top">
                  <span className="thread-subject">{t.subject}</span>
                  <span className="thread-time">{ago(t.lastMessageAt, now)}</span>
                </span>
                <span className="thread-meta">
                  {t.urgency === "URGENT" && t.status === "OPEN" && <span className="consult-urgent">Urgent</span>}
                  {t.status === "RESOLVED" && <span className="consult-resolved">Resolved</span>}
                  {sp && <span className="consult-chip">{sp.name}</span>}
                  {t.studyLabel && <span className="consult-chip consult-study">{t.studyLabel}</span>}
                  <span className="thread-who">
                    {t.createdBy.name.split(" ")[0]} → {t.askedOf ? t.askedOf.name : "anyone"}
                  </span>
                </span>
                {t.lastMessage && (
                  <span className="thread-preview">
                    <b>{t.lastMessage.authorName.split(" ")[0]}:</b> {t.lastMessage.preview}
                  </span>
                )}
              </span>
              {t.unread > 0 && <span className="thread-unread">{t.unread}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- one thread

/** Appends messages not already shown: a poll and a send can both return the same reply. */
function withMessages(d: ConsultDetail | null, add: ConsultMessage[]): ConsultDetail | null {
  if (!d) return d;
  const seen = new Set(d.messages.map((m) => m.id));
  const fresh = add.filter((m) => !seen.has(m.id));
  return fresh.length ? { ...d, messages: [...d.messages, ...fresh] } : d;
}

function ThreadView({ id, me, onBack, onChange }: { id: string; me: Me | null; onBack: () => void; onChange: () => void }) {
  const [detail, setDetail] = useState<ConsultDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .consult(id)
      .then((d) => {
        setDetail(d);
        onChange();
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load the consult"));
  }, [id, onChange]);

  // Poll for replies while the thread is open: only messages after the last one seen.
  const last = detail?.messages[detail.messages.length - 1]?.at ?? detail?.thread.createdAt;
  useEffect(() => {
    if (!last) return;
    const t = setInterval(() => {
      api
        .consultSince(id, last)
        .then((m) => {
          if (m.length) setDetail((d) => withMessages(d, m));
        })
        .catch(() => undefined);
    }, 5_000);
    return () => clearInterval(t);
  }, [id, last]);

  const count = detail?.messages.length ?? 0;
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [count]);

  async function send(e?: FormEvent) {
    e?.preventDefault();
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      const m = await api.replyConsult(id, body);
      setDetail((d) => withMessages(d, [m]));
      setDraft("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Message not sent");
    } finally {
      setSending(false);
    }
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  async function resolve() {
    try {
      setDetail(await api.resolveConsult(id));
      onChange();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not resolve");
    }
  }

  if (!detail) {
    return (
      <div className="dock-body">
        <button type="button" className="dock-back" onClick={onBack}>
          ← All consults
        </button>
        {error ? <p className="dock-error">{error}</p> : <div className="skeleton-light thread-skeleton" />}
      </div>
    );
  }

  const t = detail.thread;
  const sp = t.specialty ? specialtyById(t.specialty) : null;
  const canResolve = t.status === "OPEN" && me && (t.createdBy.id === me.userId || t.askedOf?.id === me.userId);

  return (
    <div className="dock-body">
      <div className="thread-head">
        <button type="button" className="dock-back" onClick={onBack}>
          ← All consults
        </button>
        <h3>{t.subject}</h3>
        <div className="thread-meta">
          {t.urgency === "URGENT" && t.status === "OPEN" && <span className="consult-urgent">Urgent</span>}
          {t.status === "RESOLVED" && <span className="consult-resolved">Resolved</span>}
          {sp && <span className="consult-chip">{sp.name}</span>}
          {t.studyId && (
            <Link to={`/studies/${t.studyId}`} className="consult-chip consult-study">
              Open {t.studyLabel ?? "study"} →
            </Link>
          )}
        </div>
        <div className="thread-people">
          <Avatar name={t.createdBy.name} avatar={t.createdBy.avatar} size={22} />
          <span>
            <b>{t.createdBy.name}</b> asked {t.askedOf ? <b>{t.askedOf.name}</b> : "any clinician"}
            {t.askedOf?.jobTitle ? <span className="muted"> · {t.askedOf.jobTitle}</span> : null}
          </span>
        </div>
      </div>

      <div className="messages" aria-live="polite">
        {detail.messages.map((m, i) => {
          const prev = detail.messages[i - 1];
          const grouped = prev && prev.author.id === m.author.id && new Date(m.at).getTime() - new Date(prev.at).getTime() < 5 * 60_000;
          return (
            <div key={m.id} className={`msg${m.mine ? " mine" : ""}${grouped ? " grouped" : ""}`}>
              {!m.mine && <span className="msg-avatar">{!grouped && <Avatar name={m.author.name} avatar={m.author.avatar} size={30} />}</span>}
              <div className="msg-col">
                {!grouped && (
                  <div className="msg-who">
                    {!m.mine && <b>{m.author.name}</b>}
                    {!m.mine && <GradeTag grade={m.author.grade} />}
                    <span>{time(m.at)}</span>
                  </div>
                )}
                <div className="msg-bubble">{m.body}</div>
              </div>
            </div>
          );
        })}
        {t.status === "RESOLVED" && <div className="msg-system">Consult resolved. The thread is kept for the record.</div>}
        <div ref={end} />
      </div>

      {error && <p className="dock-error">{error}</p>}
      {t.status === "OPEN" ? (
        <form className="composer" onSubmit={send}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            placeholder="Reply… (Enter to send, Shift+Enter for a new line)"
            aria-label="Reply"
            rows={2}
            maxLength={4000}
          />
          <div className="composer-row">
            {canResolve ? (
              <button type="button" className="link-button" onClick={resolve}>
                <Icon.Check /> Mark resolved
              </button>
            ) : (
              <span className="composer-hint">Messages are part of the audit trail.</span>
            )}
            <button type="submit" className="send-button" disabled={!draft.trim() || sending} aria-label="Send">
              <Icon.Send />
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- new consult

function NewConsultForm({
  prefill,
  me,
  studyOnScreen,
  onCancel,
  onCreated,
}: {
  prefill: Prefill;
  me: Me | null;
  studyOnScreen?: string;
  onCancel: () => void;
  onCreated: (d: ConsultDetail) => void;
}) {
  const [colleagues, setColleagues] = useState<Person[] | null>(null);
  const [askedOf, setAskedOf] = useState<string>("");
  const [filter, setFilter] = useState("");
  const [seniorOnly, setSeniorOnly] = useState(false);
  const [subject, setSubject] = useState(prefill.subject ?? "");
  const [body, setBody] = useState("");
  const [specialty, setSpecialty] = useState<Specialty | "">(prefill.specialty ?? me?.specialty ?? "");
  const [urgent, setUrgent] = useState(false);
  const studyId = prefill.studyId ?? studyOnScreen;
  const [attach, setAttach] = useState(Boolean(studyId));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.colleagues().then(setColleagues).catch(() => setColleagues([]));
  }, []);

  const shown = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return (colleagues ?? []).filter(
      (c) =>
        (!seniorOnly || c.grade === "CONSULTANT") &&
        (!specialty || !c.specialty || c.specialty === specialty || q) &&
        (!q || `${c.name} ${c.jobTitle ?? ""}`.toLowerCase().includes(q)),
    );
  }, [colleagues, filter, seniorOnly, specialty]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const d = await api.openConsult({
        subject: subject.trim(),
        body: body.trim(),
        specialty: specialty || undefined,
        studyId: attach && studyId ? studyId : undefined,
        askedOf: askedOf || undefined,
        urgency: urgent ? "URGENT" : "ROUTINE",
      });
      onCreated(d);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send the consult");
      setBusy(false);
    }
  }

  return (
    <form className="dock-body new-consult" onSubmit={submit}>
      <button type="button" className="dock-back" onClick={onCancel}>
        ← All consults
      </button>
      <h3>Ask a colleague</h3>

      <fieldset className="nc-field">
        <legend>Who should answer?</legend>
        <div className="nc-filters">
          <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search name or role" aria-label="Search colleagues" />
          <label className="nc-check">
            <input type="checkbox" checked={seniorOnly} onChange={(e) => setSeniorOnly(e.target.checked)} /> Consultants only
          </label>
        </div>
        <div className="people-pick" role="radiogroup" aria-label="Colleague">
          <label className={`person${askedOf === "" ? " on" : ""}`}>
            <input type="radio" name="askedOf" checked={askedOf === ""} onChange={() => setAskedOf("")} />
            <span className="person-any">
              <Icon.Chat />
            </span>
            <span className="person-text">
              <b>Any clinician</b>
              <span>Open to everyone {specialty ? `in ${specialtyById(specialty)?.name}` : "on duty"}</span>
            </span>
          </label>
          {colleagues === null && <div className="skeleton-light thread-skeleton" />}
          {shown.map((c) => (
            <label key={c.id} className={`person${askedOf === c.id ? " on" : ""}`}>
              <input type="radio" name="askedOf" checked={askedOf === c.id} onChange={() => setAskedOf(c.id)} />
              <Avatar name={c.name} avatar={c.avatar} size={34} />
              <span className="person-text">
                <b>{c.name}</b>
                <span>{c.jobTitle ?? "Clinician"}</span>
              </span>
              <GradeTag grade={c.grade} />
            </label>
          ))}
        </div>
      </fieldset>

      <div className="nc-row">
        <label className="nc-field">
          <span>Department</span>
          <select value={specialty} onChange={(e) => setSpecialty(e.target.value as Specialty | "")}>
            <option value="">Any</option>
            {SPECIALTIES.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label className={`nc-urgent${urgent ? " on" : ""}`}>
          <input type="checkbox" checked={urgent} onChange={(e) => setUrgent(e.target.checked)} />
          <Icon.Alert /> Urgent
        </label>
      </div>

      <label className="nc-field">
        <span>Subject</span>
        <input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={140} required placeholder="e.g. Ring-enhancing lesion: abscess or metastasis?" />
      </label>
      <label className="nc-field">
        <span>Your question</span>
        <textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={4000} required rows={4} placeholder="What you see, what the AI suggests, and what you are unsure about." />
      </label>
      {studyId && (
        <label className="nc-check nc-attach">
          <input type="checkbox" checked={attach} onChange={(e) => setAttach(e.target.checked)} /> Link the study on screen
          <span>Colleagues open it from the thread; patient details are not copied into the chat.</span>
        </label>
      )}
      {error && <p className="dock-error">{error}</p>}
      <div className="nc-actions">
        <button type="button" className="secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="submit" disabled={busy || !subject.trim() || !body.trim()}>
          <Icon.Send /> Send consult
        </button>
      </div>
    </form>
  );
}
