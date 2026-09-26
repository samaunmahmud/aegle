// Display helpers shared by pages.

/** "2h 15m", "45m", "3d 4h" for a positive number of minutes. */
export function duration(minutes: number): string {
  const m = Math.max(0, Math.round(minutes));
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 48) return `${h}h ${m % 60}m`;
  return `${Math.floor(h / 24)}d ${h % 24}h`;
}

/** Time until (or since) an SLA deadline, with a state for colouring. */
export function slaStatus(due: string | null, now = Date.now()): { text: string; state: "ok" | "soon" | "breached" } | null {
  if (!due) return null;
  const minutes = (new Date(due).getTime() - now) / 60_000;
  if (minutes < 0) return { text: `${duration(-minutes)} overdue`, state: "breached" };
  return { text: `${duration(minutes)} left`, state: minutes < 60 ? "soon" : "ok" };
}

export function waited(since: string, now = Date.now()): string {
  return duration((now - new Date(since).getTime()) / 60_000);
}

/** Whole years between a date of birth and today. */
export function age(dob: string | null): number | null {
  if (!dob) return null;
  const d = new Date(dob);
  const t = new Date();
  let a = t.getFullYear() - d.getFullYear();
  if (t.getMonth() < d.getMonth() || (t.getMonth() === d.getMonth() && t.getDate() < d.getDate())) a--;
  return a;
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function titleCase(s: string): string {
  return s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, " ");
}

/**
 * A model probability for display. Never rounds up to a certain-looking 100% or down to 0%:
 * the model is never that sure, and clinicians read "100%" as "definitely".
 */
export function probability(p: number): string {
  if (p > 0.999) return ">99.9%";
  if (p < 0.001) return "<0.1%";
  return `${(p * 100).toFixed(1)}%`;
}
