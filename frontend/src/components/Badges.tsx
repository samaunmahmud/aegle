import type { StudyStatus, Urgency, WorklistState } from "../api/types";

export function UrgencyBadge({ urgency }: { urgency: Urgency | null }) {
  if (!urgency) return <span className="badge badge-neutral">Pending</span>;
  const cls = { CRITICAL: "badge-critical", URGENT: "badge-urgent", ROUTINE: "badge-routine" }[urgency];
  return <span className={`badge ${cls}`}>{urgency}</span>;
}

export function StateBadge({ state }: { state: WorklistState }) {
  const cls = { OPEN: "badge-neutral", IN_REVIEW: "badge-progress", DONE: "badge-done" }[state];
  const label = { OPEN: "Open", IN_REVIEW: "In review", DONE: "Done" }[state];
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function StatusBadge({ status }: { status: StudyStatus }) {
  const cls: Record<StudyStatus, string> = {
    RECEIVED: "badge-neutral",
    QUEUED: "badge-neutral",
    ANALYZING: "badge-progress",
    READY: "badge-routine",
    REVIEWED: "badge-done",
    FAILED: "badge-critical",
  };
  return <span className={`badge ${cls[status]}`}>{status}</span>;
}
