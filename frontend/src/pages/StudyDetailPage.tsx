import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { PredictionView, ReviewDecision, StudyDetail } from "../api/types";
import { StatusBadge, UrgencyBadge } from "../components/Badges";
import { SpecialtyIcon } from "../components/Icons";
import { MeasurementTrend } from "../components/MeasurementTrend";
import { age, dateTime, probability, titleCase } from "../format";
import { specialtyById } from "../specialties";

export function StudyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<StudyDetail | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [heatmapUrl, setHeatmapUrl] = useState<string | null>(null);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [opacity, setOpacity] = useState(0.45);
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
  const models = [...new Map(detail.predictions.map((p) => [`${p.modelName} v${p.modelVersion}`, p])).values()];
  const failed = detail.jobs.filter((j) => j.status === "FAILED");
  // For recordings the AI view is a separate drawing (EEG: the most suspicious page), so it
  // replaces the tracing instead of being blended over it.
  const recording = ["ECG", "EEG"].includes(study.modality);

  return (
    <div>
      <div className="toolbar" style={{ marginBottom: "0.75rem" }}>
        <Link to={specialty ? `/worklist/${specialty.slug}` : "/worklist"}>
          ← {specialty ? `${specialty.name} worklist` : "Worklist"}
        </Link>
      </div>

      <section className="patient-banner" aria-label="Patient">
        <div>
          <div className="patient-name">{patient.name ?? "Name not recorded"}</div>
          <div className="cell-secondary">Patient</div>
        </div>
        <div className="banner-field">
          <span className="banner-label">MRN</span>
          <span className="banner-value">{patient.mrn}</span>
        </div>
        <div className="banner-field">
          <span className="banner-label">DOB</span>
          <span className="banner-value">
            {patient.dob ? `${patient.dob}${years != null ? ` (${years}y)` : ""}` : "—"}
          </span>
        </div>
        <div className="banner-field">
          <span className="banner-label">Sex</span>
          <span className="banner-value">{{ F: "Female", M: "Male", O: "Other" }[patient.sex ?? ""] ?? "Unknown"}</span>
        </div>
        <div className="banner-spacer" />
        <div className="banner-field">
          <span className="banner-label">Study</span>
          <span className="banner-value">
            {study.modality} · {study.bodyPart}
          </span>
        </div>
        <div className="banner-field">
          <span className="banner-label">Accession</span>
          <span className="banner-value">{study.accessionNo ?? "—"}</span>
        </div>
        <div className="banner-field">
          <span className="banner-label">Received</span>
          <span className="banner-value">
            {dateTime(study.createdAt)} · {study.source === "DICOM" ? "DICOM" : "Upload"}
          </span>
        </div>
        <StatusBadge status={study.status} />
      </section>

      <div className="study-layout">
        <section className="viewer" aria-label="Image viewer">
          <div className="viewer-toolbar">
            {specialty && (
              <span className="specialty-chip" style={{ color: "#c8d3de" }}>
                <SpecialtyIcon specialty={specialty.id} /> {specialty.name}
              </span>
            )}
            {heatmapUrl && recording ? (
              <label>
                <input type="checkbox" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} />
                AI view ({study.modality === "EEG" ? "probability timeline, most suspicious page" : "model attention"})
              </label>
            ) : heatmapUrl ? (
              <>
                <label>
                  <input type="checkbox" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} />
                  Grad-CAM overlay
                </label>
                <label>
                  Opacity
                  <input
                    type="range"
                    min={0.1}
                    max={1}
                    step={0.05}
                    value={opacity}
                    disabled={!showHeatmap}
                    onChange={(e) => setOpacity(Number(e.target.value))}
                    aria-label="Heatmap opacity"
                  />
                </label>
                <span className="heat-legend" aria-label="Colour scale: blue is low, red is high model attention">
                  low <span className="heat-legend-bar" /> high attention
                </span>
              </>
            ) : (
              <span>No heatmap for this study</span>
            )}
          </div>
          <div className="viewer-canvas">
            <div className="viewer-overlay-text">
              {study.modality} {study.bodyPart}
              <br />
              {study.studyDate ?? `received ${new Date(study.createdAt).toLocaleDateString()}`}
              <br />
              {patient.mrn}
            </div>
            {imageUrl && recording ? (
              <div className="image-stack">
                <img
                  src={heatmapUrl && showHeatmap ? heatmapUrl : imageUrl}
                  alt={heatmapUrl && showHeatmap ? `${study.modality} with AI annotations` : `${study.modality} tracing`}
                />
              </div>
            ) : imageUrl ? (
              <div className="image-stack">
                <img src={imageUrl} alt={`${study.modality} ${study.bodyPart} image`} />
                {heatmapUrl && showHeatmap && (
                  <img
                    src={heatmapUrl}
                    alt="Grad-CAM heatmap overlay"
                    className="heatmap-overlay"
                    style={{ opacity }}
                  />
                )}
              </div>
            ) : (
              <p style={{ color: "#9fb1c3" }}>Loading image…</p>
            )}
          </div>
        </section>

        <div className="side-pane">
          <section className="panel" aria-label="AI findings">
            <div className="panel-header">
              <h2>AI findings</h2>
              <span className="cell-secondary">{detail.predictions.length} outputs</span>
            </div>
            {models.map((m) => (
              <details key={m.modelName + m.modelVersion} className="intended-use" style={{ margin: "0.75rem 1rem 0" }} open>
                <summary>
                  {m.modelName} v{m.modelVersion}: what it can and cannot do
                </summary>
                <p>{m.intendedUse}</p>
              </details>
            ))}
            {detail.predictions.length === 0 ? (
              <div className="panel-body muted">
                {study.status === "RECEIVED"
                  ? "No AI model is deployed for this study type."
                  : "Analysis pending."}
              </div>
            ) : (
              detail.predictions.map((p, i) => {
                // The top output per model is the finding; the rest are shown quietly for context.
                const isTop = detail.predictions.findIndex((q) => q.modelName === p.modelName) === i;
                return isTop ? (
                  <Finding
                    key={p.id}
                    prediction={p}
                    alreadyReviewed={reviewedIds.has(p.id)}
                    onReviewed={() => api.study(id).then(setDetail)}
                  />
                ) : (
                  <div key={p.id} className="finding-minor">
                    <div className="finding-headline">
                      <span style={{ minWidth: "7rem" }}>{p.label}</span>
                      <div className="prob-bar" aria-hidden="true">
                        <div className="prob-fill" style={{ width: `${p.probability * 100}%` }} />
                      </div>
                      <span className="numeric">{probability(p.probability)}</span>
                    </div>
                  </div>
                );
              })
            )}
          </section>

          {detail.measurements.length > 0 && (
            <section className="panel" aria-label="Measurements">
              <div className="panel-header">
                <h2>Measurements</h2>
                <span className="cell-secondary">AI-derived · verify clinically</span>
              </div>
              <div className="panel-body">
                <MeasurementTrend
                  title="Wound area"
                  points={detail.measurementHistory.filter((m) => m.name === detail.measurements[0].name)}
                  currentStudyId={study.id}
                />
              </div>
            </section>
          )}

          {failed.length > 0 && (
            <section className="panel">
              <div className="panel-header">
                <h2>Analysis problems</h2>
              </div>
              <div className="panel-body">
                {failed.map((j) => (
                  <p key={j.id} className="error-text">
                    Attempt {j.attempts}: {j.error ?? "Unknown error"}
                  </p>
                ))}
              </div>
            </section>
          )}

          <section className="panel" aria-label="Review history">
            <div className="panel-header">
              <h2>Review history</h2>
            </div>
            {detail.reviews.length === 0 ? (
              <div className="panel-body muted">Not reviewed yet.</div>
            ) : (
              <ul className="timeline">
                {detail.reviews.map((r) => (
                  <li key={r.id}>
                    <strong>{titleCase(r.decision)}</strong> by {r.reviewer}
                    <div className="cell-secondary">{dateTime(r.reviewedAt)}</div>
                    {r.finalLabel && <div>Final label: {r.finalLabel}</div>}
                    {r.comment && <div className="muted">“{r.comment}”</div>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function Finding({
  prediction,
  alreadyReviewed,
  onReviewed,
}: {
  prediction: PredictionView;
  alreadyReviewed: boolean;
  onReviewed: () => void;
}) {
  const [decision, setDecision] = useState<ReviewDecision>("ACCEPT");
  const [finalLabel, setFinalLabel] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Unreviewed findings show the decision straight away: reviewing is the point of the page.
  const [open, setOpen] = useState(!alreadyReviewed);

  async function submitReview() {
    setSubmitting(true);
    setError(null);
    try {
      await api.review(prediction.id, {
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

  const pct = prediction.probability * 100;

  return (
    <div className="finding">
      <div className="finding-headline">
        <span className="finding-label">{prediction.label}</span>
        <UrgencyBadge urgency={prediction.urgencyClass} />
        <span className="numeric cell-primary">{probability(prediction.probability)}</span>
      </div>
      <div
        className="prob-bar"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={`${prediction.label} probability`}
      >
        <div className={`prob-fill ${prediction.urgencyClass}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="cell-secondary">
        {prediction.modelName} v{prediction.modelVersion} · {dateTime(prediction.analysedAt)}
      </div>

      {!open ? (
        <button className="link-button small" onClick={() => setOpen(true)} style={{ marginTop: "0.4rem" }}>
          {alreadyReviewed ? "Reviewed · change review" : "Review this finding"}
        </button>
      ) : (
        <div className="review-form">
          <div className="decision-buttons" role="radiogroup" aria-label="Decision">
            {(["ACCEPT", "MODIFY", "REJECT"] as ReviewDecision[]).map((d) => (
              <button
                key={d}
                type="button"
                role="radio"
                aria-checked={decision === d}
                className={decision === d ? "decision-selected" : ""}
                onClick={() => setDecision(d)}
              >
                {titleCase(d)}
              </button>
            ))}
          </div>
          {decision === "MODIFY" && (
            <input
              placeholder="Correct label"
              value={finalLabel}
              onChange={(e) => setFinalLabel(e.target.value)}
              maxLength={64}
              aria-label="Correct label"
            />
          )}
          <textarea
            placeholder="Comment (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
            aria-label="Comment"
          />
          {error && <p className="error-text">{error}</p>}
          <div className="toolbar">
            <button onClick={submitReview} disabled={submitting || (decision === "MODIFY" && !finalLabel)}>
              {submitting ? "Submitting…" : "Sign review"}
            </button>
            <button className="secondary" type="button" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
