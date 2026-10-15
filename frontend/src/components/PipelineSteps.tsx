import { useEffect, useState } from "react";
import type { StudyStatus } from "../api/types";

const STEPS: { status: StudyStatus[]; label: string; detail: string }[] = [
  { status: ["RECEIVED"], label: "Received", detail: "Identifiers encrypted, image stored" },
  { status: ["QUEUED"], label: "Queued", detail: "Matched to AI models for this exam" },
  { status: ["ANALYZING"], label: "AI analysing", detail: "Model inference and explanation" },
  { status: ["READY"], label: "Ready to report", detail: "On the worklist, ranked by priority" },
  { status: ["REVIEWED"], label: "Reviewed", detail: "Signed by a clinician" },
];

const ORDER: StudyStatus[] = ["RECEIVED", "QUEUED", "ANALYZING", "READY", "REVIEWED"];

/** Where a study is in the pipeline, with a running clock while the AI works. */
export function PipelineSteps({ status, since, noModel }: { status: StudyStatus; since: string; noModel: boolean }) {
  const [now, setNow] = useState(Date.now());
  const active = status === "QUEUED" || status === "ANALYZING";
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [active]);

  if (status === "FAILED") {
    return <div className="pipeline pipeline-failed">AI analysis failed: the study stays on the worklist for clinician review.</div>;
  }
  const at = ORDER.indexOf(status);
  const elapsed = Math.max(0, (now - Date.parse(since)) / 1000);

  return (
    <ol className="pipeline" aria-label="Study progress">
      {STEPS.map((s, i) => {
        const state = i < at ? "done" : i === at ? (active ? "running" : "current") : "todo";
        const skipped = noModel && i >= 1 && i <= 2;
        return (
          <li key={s.label} className={`step step-${skipped ? "skipped" : state}`}>
            <span className="step-dot" aria-hidden="true" />
            <span className="step-label">{s.label}</span>
            <span className="step-detail">
              {skipped ? "No AI model for this exam" : state === "running" ? `${elapsed.toFixed(1)} s` : s.detail}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
