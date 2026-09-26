import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { PredictionView, ReviewDecision, StudyDetail } from "../api/types";
import { StatusBadge, UrgencyBadge } from "../components/Badges";

export function StudyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<StudyDetail | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [heatmapUrl, setHeatmapUrl] = useState<string | null>(null);
  const [showHeatmap, setShowHeatmap] = useState(true);
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
  if (!detail || !id) return <p>Loading study&hellip;</p>;

  const reviewedIds = new Set(detail.reviews.map((r) => r.predictionId));

  return (
    <div>
      <h1>
        {detail.study.modality} / {detail.study.bodyPart} <StatusBadge status={detail.study.status} />
      </h1>
      <div className="study-meta">
        <span>MRN: {detail.patient.mrn}</span>
        {detail.patient.name && <span>Name: {detail.patient.name}</span>}
        {detail.patient.dob && <span>DOB: {detail.patient.dob}</span>}
        {detail.study.accessionNo && <span>Accession: {detail.study.accessionNo}</span>}
        <span>
          Received: {new Date(detail.study.createdAt).toLocaleString()}
          {detail.study.source === "DICOM" ? " from a DICOM modality" : " by upload"}
        </span>
      </div>

      <div className="study-layout">
        <div className="image-pane">
          {imageUrl ? (
            <div className="image-stack">
              <img src={imageUrl} alt="Study" />
              {heatmapUrl && showHeatmap && (
                <img src={heatmapUrl} alt="Grad-CAM heatmap" className="heatmap-overlay" />
              )}
            </div>
          ) : (
            <p>Loading image&hellip;</p>
          )}
          {heatmapUrl && (
            <label className="heatmap-toggle">
              <input type="checkbox" checked={showHeatmap} onChange={(e) => setShowHeatmap(e.target.checked)} />
              Show Grad-CAM heatmap
            </label>
          )}
        </div>

        <div className="side-pane">
          <h2>AI findings</h2>
          {detail.predictions.length === 0 && <p className="muted">No predictions yet.</p>}
          {detail.predictions.map((p) => (
            <PredictionCard
              key={p.id}
              prediction={p}
              alreadyReviewed={reviewedIds.has(p.id)}
              onReviewed={() => api.study(id).then(setDetail)}
            />
          ))}

          {detail.reviews.length > 0 && (
            <>
              <h2>Clinician reviews</h2>
              {detail.reviews.map((r) => (
                <div key={r.id} className="review-record">
                  <strong>{r.decision}</strong> by {r.reviewer} on {new Date(r.reviewedAt).toLocaleString()}
                  {r.finalLabel && <div>Final label: {r.finalLabel}</div>}
                  {r.comment && <div className="muted">"{r.comment}"</div>}
                </div>
              ))}
            </>
          )}

          {detail.jobs.some((j) => j.status === "FAILED") && (
            <>
              <h2>Inference issues</h2>
              {detail.jobs
                .filter((j) => j.status === "FAILED")
                .map((j) => (
                  <p key={j.id} className="error-text">
                    Attempt {j.attempts}: {j.error ?? "Unknown error"}
                  </p>
                ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function PredictionCard({
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

  return (
    <div className="prediction-card">
      <div className="prediction-headline">
        <UrgencyBadge urgency={prediction.urgencyClass} />
        <strong>{prediction.label}</strong>
        <span className="numeric">{(prediction.probability * 100).toFixed(1)}%</span>
      </div>
      <div className="muted small">
        {prediction.modelName} v{prediction.modelVersion} &middot;{" "}
        {new Date(prediction.analysedAt).toLocaleString()}
      </div>

      {alreadyReviewed && !open ? (
        <button className="link-button" onClick={() => setOpen(true)}>
          Reviewed — change?
        </button>
      ) : open ? (
        <div className="review-form">
          <div className="decision-buttons">
            {(["ACCEPT", "MODIFY", "REJECT"] as ReviewDecision[]).map((d) => (
              <button
                key={d}
                className={decision === d ? "decision-selected" : ""}
                type="button"
                onClick={() => setDecision(d)}
              >
                {d}
              </button>
            ))}
          </div>
          {decision === "MODIFY" && (
            <input
              placeholder="Final label"
              value={finalLabel}
              onChange={(e) => setFinalLabel(e.target.value)}
              maxLength={64}
            />
          )}
          <textarea
            placeholder="Comment (optional)"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            maxLength={2000}
          />
          {error && <p className="error-text">{error}</p>}
          <button onClick={submitReview} disabled={submitting}>
            {submitting ? "Submitting…" : "Submit review"}
          </button>
        </div>
      ) : null}
    </div>
  );
}
