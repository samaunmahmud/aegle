import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import type { ModelEntry } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Icon, SpecialtyIcon } from "../components/Icons";
import { PageHeader } from "../components/PageHeader";
import { dateTime } from "../format";
import { SPECIALTIES } from "../specialties";

// Metrics worth showing on a card, in order, with how to display them.
const KEY_METRICS: { key: string; label: string; percent: boolean; plain?: boolean }[] = [
  { key: "accuracy", label: "Accuracy", percent: true },
  { key: "balanced_accuracy", label: "Balanced acc.", percent: true },
  { key: "auc", label: "AUC", percent: false },
  { key: "macro_auc_ovr", label: "Macro AUC", percent: false },
  { key: "macro_auc", label: "Macro AUC", percent: false },
  { key: "window_auc", label: "Window AUC", percent: false },
  { key: "seizures_detected", label: "Seizures found", percent: true },
  { key: "false_alarms_per_hour", label: "False alarms/h", percent: false, plain: true },
  { key: "sensitivity", label: "Sensitivity", percent: true },
  { key: "specificity", label: "Specificity", percent: true },
  { key: "ece", label: "Calib. error", percent: false },
];

type Metrics = Record<string, unknown>;

/** The held-out test results, whichever key the training script used. */
function testMetrics(m: Metrics | null): Metrics | null {
  if (!m) return null;
  const t = (m["test_patient_split"] ?? m["test"]) as Metrics | undefined;
  return t && typeof t === "object" ? t : null;
}

function ModelCard({ model, onToggle, canToggle }: { model: ModelEntry; onToggle: (m: ModelEntry) => void; canToggle: boolean }) {
  const test = testMetrics(model.metrics);
  const shown = KEY_METRICS.filter((k) => typeof test?.[k.key] === "number").slice(0, 4);
  const dataset = model.metrics?.["dataset"];
  const baseline = test?.["shortcut_baseline"] as Metrics | undefined;
  const baselineAuc = (baseline?.["auc"] ?? baseline?.["macro_auc_ovr"]) as number | undefined;
  const modelAuc = (test?.["auc"] ?? test?.["macro_auc_ovr"]) as number | undefined;
  const caveat = model.metrics?.["caveat"];

  return (
    <article className="panel model-card">
      <div className="panel-header">
        <div>
          <h3>{model.name}</h3>
          <div className="cell-secondary">
            {model.modality}
            {model.bodyPart ? ` · ${model.bodyPart}` : ""} · {model.task}
            {model.activeVersion ? ` · v${model.activeVersion}` : ""}
          </div>
        </div>
        <div className="toolbar">
          {canToggle && model.activeVersion && (
            <label className="switch">
              <input
                type="checkbox"
                checked={model.enabledForOrganisation}
                onChange={() => onToggle(model)}
                aria-label={`Run ${model.name} for this organisation`}
              />
              Run here
            </label>
          )}
          {!model.activeVersion ? (
            <span className="badge badge-neutral">Not deployed</span>
          ) : model.enabledForOrganisation ? (
            <span className="badge badge-routine">Active</span>
          ) : (
            <span className="badge badge-done">Off here</span>
          )}
        </div>
      </div>
      <div className="model-card-body">
        <div className="model-card-results">
          {shown.length > 0 ? (
            <>
              <div className="stat-label">Held-out test · {String(test?.["n"] ?? "?")} cases the model never saw</div>
              <div className="metric-row">
                {shown.map((k) => {
                  const v = test![k.key] as number;
                  return (
                    <div key={k.key} className="metric">
                      <div className="metric-value">
                        {k.percent ? `${(v * 100).toFixed(1)}%` : k.plain ? v.toFixed(2) : v.toFixed(3)}
                      </div>
                      <div className="metric-label">{k.label}</div>
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div className="muted small">No held-out results recorded.</div>
          )}
          {baselineAuc != null && modelAuc != null && (
            <div
              className={`shortcut ${modelAuc - baselineAuc < 0.05 ? "shortcut-bad" : "shortcut-ok"}`}
              title="A trivial model using only image size, colour statistics and file size. If it scores close to the real model, the result may reflect how images were acquired rather than disease."
            >
              <strong>Shortcut check</strong> · image size and colour alone reach AUC {baselineAuc.toFixed(2)}{" "}
              (model {modelAuc.toFixed(2)})
              {modelAuc - baselineAuc < 0.05 ? ": too close, treat the result as unproven." : ""}
            </div>
          )}
          <div className="cell-secondary">
            {model.approvedAt ? `Approved ${dateTime(model.approvedAt)}` : "Awaiting platform approval"}
            {model.weightsSha256 && (
              <>
                {" · weights "}
                <code title={model.weightsSha256}>{model.weightsSha256.slice(0, 12)}</code>
              </>
            )}
          </div>
        </div>
        <div className="model-card-context">
          <div className="callout">
            <Icon.Alert />
            <div>{model.intendedUse}</div>
          </div>
          {typeof dataset === "string" && (
            <div className="small">
              <strong>Training data:</strong> {dataset}
            </div>
          )}
          {typeof caveat === "string" && <div className="small muted">{caveat}</div>}
        </div>
      </div>
    </article>
  );
}

export function ModelsPage() {
  const { roles } = useAuth();
  const isAdmin = roles.includes("ADMIN");
  const [models, setModels] = useState<ModelEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .models()
      .then(setModels)
      .catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load models"));
  }, []);

  async function toggle(m: ModelEntry) {
    const enabled = !m.enabledForOrganisation;
    const verb = enabled ? "Switch on" : "Switch off";
    if (!window.confirm(`${verb} ${m.name} for your organisation? New studies are affected; queued ones are not.`)) return;
    try {
      await api.setModelEnabled(m.id, enabled);
      setModels((prev) => (prev ?? []).map((x) => (x.id === m.id ? { ...x, enabledForOrganisation: enabled } : x)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not change the model");
    }
  }

  const deployed = models?.filter((m) => m.activeVersion && m.enabledForOrganisation).length ?? 0;

  return (
    <div>
      <PageHeader
        icon={<Icon.Models />}
        title="AI model registry"
        subtitle={
          models
            ? `${deployed} model${deployed === 1 ? "" : "s"} running for your organisation. Every result is validated on patients the model never saw.`
            : "Loading…"
        }
      />
      {error && <p className="error-text">{error}</p>}

      {SPECIALTIES.map((sp) => {
        const own = (models ?? []).filter((m) => m.specialty === sp.id);
        return (
          <section key={sp.id} style={{ marginBottom: "1.5rem" }} aria-label={sp.name}>
            <h2 className="specialty-chip" style={{ fontSize: "0.95rem", color: "var(--text)", marginBottom: "0.6rem" }}>
              <SpecialtyIcon specialty={sp.id} /> {sp.name}
            </h2>
            {own.length === 0 && (
              <div className="panel panel-body small muted">No AI model is deployed for {sp.name.toLowerCase()} yet.</div>
            )}
            {own.length > 0 && (
              <div className="model-grid">
                {own.map((m) => (
                  <ModelCard key={m.id} model={m} onToggle={toggle} canToggle={isAdmin} />
                ))}
              </div>
            )}
            {sp.planned.length > 0 && (
              <div className="panel panel-body small" style={{ marginTop: own.length ? "0.6rem" : 0 }}>
                <strong>In development</strong>
                <ul className="planned-list">
                  {sp.planned.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
