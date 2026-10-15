import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { PredictionView, ReviewDecision, StudyDetail } from "../api/types";
import { AiTag, PriorityTag, StatusBadge } from "../components/Badges";
import { Icon, SpecialtyIcon } from "../components/Icons";
import { ImageViewer } from "../components/ImageViewer";
import { formatValue, MEASUREMENTS, MeasurementTrend, measurementTitle } from "../components/MeasurementTrend";
import { age, clinicalDate, clinicalDateTime, patientName, probability, titleCase } from "../format";
import { specialtyById } from "../specialties";

const GENDER: Record<string, string> = { F: "Female", M: "Male", O: "Other" };

export function StudyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<StudyDetail | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [heatmapUrl, setHeatmapUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const revoke: string[] = [];

    api
      .study(id)
      .then(async (d) => {
        setDetail(d);
        const img = await api.studyImage(id);
        const url = URL.createObjectURL(img);
        revoke.push(url);
        setImageUrl(url);
        if (d.hasHeatmap) {
          const hm = await api.studyHeatmap(id);
          const hmUrl = URL.createObjectURL(hm);
          revoke.push(hmUrl);
          setHeatmapUrl(hmUrl);
        }
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load study"));

    return () => revoke.forEach((u) => URL.revokeObjectURL(u));
  }, [id]);

  if (error) return <p className="error-text">{error}</p>;
  if (!detail || !id) return <div className="panel empty-state">Loading study…</div>;

  const { study, patient } = detail;
  const reviewedIds = new Set(detail.reviews.map((r) => r.predictionId));
  const specialty = specialtyById(study.specialty);
  const years = age(patient.dob);
  const failed = detail.jobs.filter((j) => j.status === "FAILED");
  const recording = ["ECG", "EEG"].includes(study.modality);
  // Group each model's outputs: its top label is the finding, the rest give context.
  const byModel = [...new Set(detail.predictions.map((p) => `${p.modelName}@${p.modelVersion}`))].map((key) =>
    detail.predictions.filter((p) => `${p.modelName}@${p.modelVersion}` === key).sort((a, b) => b.probability - a.probability),
  );
  const examDate = study.studyDate ? clinicalDate(study.studyDate) : clinicalDateTime(study.createdAt);

  return (
    <div className="study-page">
      <div className="crumbs">
        <Link to={specialty ? `/worklist/${specialty.slug}` : "/worklist"}>
          ← {specialty ? `${specialty.name} worklist` : "Worklist"}
        </Link>
      </div>

      {/* Patient banner, after the NHS CUI layout: identity first and always visible. */}
      <section className="patient-banner" aria-label="Patient">
        <div className="pb-identity">
          <div className="patient-name">{patientName(patient.name) ?? "Name not recorded"}</div>
          <dl className="pb-fields">
            <div>
              <dt>Born</dt>
              <dd>{patient.dob ? `${clinicalDate(patient.dob)}${years != null ? ` (${years}y)` : ""}` : "Not recorded"}</dd>
            </div>
            <div>
              <dt>Gender</dt>
              <dd>{GENDER[patient.sex ?? ""] ?? "Unknown"}</dd>
            </div>
            <div>
              <dt>MRN</dt>
              <dd className="mrn">{patient.mrn}</dd>
            </div>
          </dl>
        </div>
        <dl className="pb-fields pb-study">
          <div>
            <dt>Examination</dt>
            <dd>
              {specialty && <SpecialtyIcon specialty={specialty.id} />} {study.modality} {titleCase(study.bodyPart)}
            </dd>
          </div>
          <div>
            <dt>Accession</dt>
            <dd className="mrn">{study.accessionNo ?? "—"}</dd>
          </div>
          <div>
            <dt>Received</dt>
            <dd>
              {clinicalDateTime(study.createdAt)} · {study.source === "DICOM" ? "PACS (DICOM)" : "Upload"}
            </dd>
          </div>
        </dl>
        <StatusBadge status={study.status} />
      </section>

      <div className="reading-room">
        <ImageViewer
          imageUrl={imageUrl}
          heatmapUrl={heatmapUrl}
          recording={recording}
          aiViewLabel={recording ? (study.modality === "EEG" ? "AI timeline" : "AI view") : "AI overlay"}
          corners={{
            topLeft: [patientName(patient.name) ?? patient.mrn, `MRN ${patient.mrn}`, patient.dob ? `DOB ${clinicalDate(patient.dob)}` : ""].filter(Boolean),
            topRight: [`${study.modality} ${study.bodyPart}`, examDate, study.accessionNo ? `ACC ${study.accessionNo}` : ""].filter(Boolean),
          }}
        />

        <aside className="findings-pane" aria-label="AI findings and review">
          <div className="pane-head">
            <h2>
              <AiTag /> AI findings
            </h2>
            <span className="pane-sub">Suggestions until signed</span>
          </div>

          {byModel.length === 0 ? (
            <div className="pane-empty">
              {study.status === "RECEIVED" ? "No AI model is deployed for this examination." : "AI analysis in progress…"}
            </div>
          ) : (
            byModel.map((outputs) => (
              <ModelFinding
                key={outputs[0].id}
                outputs={outputs}
                alreadyReviewed={reviewedIds.has(outputs[0].id)}
                onReviewed={() => api.study(id).then(setDetail)}
              />
            ))
          )}

          {detail.measurements.length > 0 && (
            <section className="pane-section" aria-label="Measurements">
              <h3>
                Measurements <span className="pane-sub">AI-derived · verify clinically</span>
              </h3>
              {detail.measurements
                .filter((m) => MEASUREMENTS[m.name]?.trend)
                .map((m) => (
                  <MeasurementTrend
                    key={m.name}
                    title={measurementTitle(m.name)}
                    note={MEASUREMENTS[m.name].note}
                    points={detail.measurementHistory.filter((h) => h.name === m.name)}
                    currentStudyId={study.id}
                  />
                ))}
              {detail.measurements.some((m) => !MEASUREMENTS[m.name]?.trend) && (
                <table className="kv-table">
                  <tbody>
                    {detail.measurements
                      .filter((m) => !MEASUREMENTS[m.name]?.trend)
                      .map((m) => (
                        <tr key={m.name}>
                          <th scope="row">{measurementTitle(m.name)}</th>
                          <td className="numeric">{formatValue(m.value, m.unit)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              )}
            </section>
          )}

          {failed.length > 0 && (
            <section className="pane-section">
              <h3>Analysis problems</h3>
              {failed.map((j) => (
                <p key={j.id} className="error-text">
                  Attempt {j.attempts}: {j.error ?? "Unknown error"}
                </p>
              ))}
            </section>
          )}

          <section className="pane-section" aria-label="Review history">
            <h3>Review history</h3>
            {detail.reviews.length === 0 ? (
              <div className="pane-empty">Not reviewed yet.</div>
            ) : (
              <ol className="timeline">
                {detail.reviews.map((r) => (
                  <li key={r.id} className={`tl-${r.decision}`}>
                    <div>
                      <strong>{titleCase(r.decision)}</strong> · {r.reviewer}
                    </div>
                    <div className="pane-sub">{clinicalDateTime(r.reviewedAt)}</div>
                    {r.finalLabel && <div>Final: {titleCase(r.finalLabel)}</div>}
                    {r.comment && <div className="tl-comment">“{r.comment}”</div>}
                  </li>
                ))}
              </ol>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}

function ModelFinding({
  outputs,
  alreadyReviewed,
  onReviewed,
}: {
  outputs: PredictionView[];
  alreadyReviewed: boolean;
  onReviewed: () => void;
}) {
  const top = outputs[0];
  const [decision, setDecision] = useState<ReviewDecision>("ACCEPT");
  const [finalLabel, setFinalLabel] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Unreviewed findings show the decision straight away: reviewing is the point of the page.
  const [open, setOpen] = useState(!alreadyReviewed);
  const pct = top.probability * 100;

  async function submitReview() {
    setSubmitting(true);
    setError(null);
    try {
      await api.review(top.id, {
        decision,
        finalLabel: decision === "MODIFY" ? finalLabel : undefined,
        comment: comment || undefined,
      });
      setOpen(false);
      onReviewed();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className={`finding-card finding-${top.urgencyClass}`}>
      <div className="finding-model">
        <Icon.Sparkle /> {top.modelName} <span className="pane-sub">v{top.modelVersion}</span>
      </div>
      <div className="finding-main">
        <div>
          <div className="finding-label">{titleCase(top.label)}</div>
          <PriorityTag urgency={top.urgencyClass} />
        </div>
        <div className="finding-prob">
          <span className="numeric">{probability(top.probability)}</span>
          <span className="pane-sub">model probability</span>
        </div>
      </div>
      <div className="prob-bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} aria-label={`${top.label} probability`}>
        <div className={`prob-fill ${top.urgencyClass}`} style={{ width: `${pct}%` }} />
      </div>
      {outputs.length > 1 && (
        <ul className="alt-labels">
          {outputs.slice(1).map((p) => (
            <li key={p.id}>
              <span>{titleCase(p.label)}</span>
              <span className="alt-bar">
                <span style={{ width: `${p.probability * 100}%` }} />
              </span>
              <span className="numeric">{probability(p.probability)}</span>
            </li>
          ))}
        </ul>
      )}
      <details className="intended-use">
        <summary>What this model can and cannot do</summary>
        <p>{top.intendedUse}</p>
        <p className="pane-sub">
          Analysed {clinicalDateTime(top.analysedAt)} · weights {top.weightsSha256?.slice(0, 12)}…
        </p>
      </details>

      {!open ? (
        <button className="link-button small" onClick={() => setOpen(true)}>
          {alreadyReviewed ? "Reviewed · amend review" : "Review this finding"}
        </button>
      ) : (
        <div className="review-form">
          <div className="decision-buttons" role="radiogroup" aria-label="Decision">
            {(
              [
                ["ACCEPT", "Agree"],
                ["MODIFY", "Amend"],
                ["REJECT", "Disagree"],
              ] as [ReviewDecision, string][]
            ).map(([d, label]) => (
              <button
                key={d}
                type="button"
                role="radio"
                aria-checked={decision === d}
                className={`decision-${d}${decision === d ? " decision-selected" : ""}`}
                onClick={() => setDecision(d)}
              >
                {label}
              </button>
            ))}
          </div>
          {decision === "MODIFY" && (
            <input placeholder="Correct finding" value={finalLabel} onChange={(e) => setFinalLabel(e.target.value)} maxLength={64} aria-label="Correct finding" />
          )}
          <textarea placeholder="Comment for the report (optional)" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} aria-label="Comment" />
          {error && <p className="error-text">{error}</p>}
          <div className="toolbar">
            <button onClick={submitReview} disabled={submitting || (decision === "MODIFY" && !finalLabel)}>
              {submitting ? "Signing…" : "Sign review"}
            </button>
            <button className="secondary" type="button" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
          <p className="pane-sub">Signed reviews are attributed to you and recorded in the audit log.</p>
        </div>
      )}
    </section>
  );
}
