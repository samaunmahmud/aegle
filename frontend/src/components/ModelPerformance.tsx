import { useState } from "react";
import { titleCase } from "../format";
import { useTheme } from "../theme";

type Metrics = Record<string, unknown>;
type PerClass = Record<string, { n: number; sensitivity: number; precision: number }>;
type Confusion = { labels: string[]; rows_true_cols_predicted: number[][] };

// Sequential blue ramp (one hue, light -> dark) for the confusion matrix; the lightest step
// means "none" and recedes toward the surface.
const RAMP = ["#fbf3f6", "#f6dde5", "#f0c8d4", "#e9b2c3", "#e19bb1", "#d8849f", "#cd6c8c", "#c05479", "#b03f67", "#9c2f57", "#88234b", "#741a40", "#601436", "#4a0f2a"];
const INK_FLIP = 8; // from this step on, cell text is white
// Dark theme: its own steps, dark -> light, so more cases still reads as "stands out more"
// against the dark surface; text flips to dark ink on the bright end.
const RAMP_DARK = ["#141e28", "#16293b", "#17344d", "#1a3f60", "#1e4b73", "#235786", "#296399", "#3170ab", "#3e7fbd", "#5590cc", "#6da1d9", "#87b3e4", "#a2c6ee", "#c0dbf8"];

const pct = (v: number) => `${(v * 100).toFixed(v === 1 || v === 0 ? 0 : 1)}%`;
/** Column headers for wide matrices: initials for multi-word classes (BCC), else 4 letters. */
const short = (label: string) => {
  const words = titleCase(label).split(" ");
  return words.length > 1 ? words.map((w) => w[0].toUpperCase()).join("") : words[0].slice(0, 4);
};

function cellInk(step: number, n: number, dark: boolean) {
  if (n === 0) return dark ? "#5f7182" : "#8a97a5";
  if (dark) return step >= INK_FLIP + 2 ? "#0b1218" : "#dbe4ec";
  return step >= INK_FLIP ? "#fff" : "#16212c";
}

function ConfusionMatrix({ c, unit }: { c: Confusion; unit: string }) {
  const [hover, setHover] = useState<[number, number] | null>(null);
  const dark = useTheme() === "dark";
  const ramp = dark ? RAMP_DARK : RAMP;
  const rows = c.rows_true_cols_predicted;
  const totals = rows.map((r) => r.reduce((a, b) => a + b, 0));
  const readout = hover
    ? (() => {
        const [i, j] = hover;
        const n = rows[i][j];
        const of = `${n} of ${totals[i]} ${titleCase(c.labels[i]).toLowerCase()} ${unit}`;
        return i === j ? `${of} correctly identified (${pct(n / Math.max(1, totals[i]))} sensitivity)` : `${of} called ${titleCase(c.labels[j]).toLowerCase()} (${pct(n / Math.max(1, totals[i]))})`;
      })()
    : "Rows: true class. Columns: model's answer. Shade: share of the row. Hover a cell.";
  return (
    <figure className="viz">
      <figcaption>Confusion matrix</figcaption>
      <table className="cm" onMouseLeave={() => setHover(null)}>
        <thead>
          <tr>
            <th className="cm-corner">True ↓ · Predicted →</th>
            {c.labels.map((l) => (
              <th key={l} scope="col" title={titleCase(l)}>
                {c.labels.length > 4 ? short(l) : titleCase(l)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={c.labels[i]}>
              <th scope="row">{titleCase(c.labels[i])}</th>
              {r.map((n, j) => {
                const f = n / Math.max(1, totals[i]);
                const step = Math.round(f * (ramp.length - 1));
                const on = hover && hover[0] === i && hover[1] === j;
                return (
                  <td
                    key={j}
                    tabIndex={0}
                    className={`${i === j ? "cm-diag" : ""}${on ? " cm-on" : ""}`}
                    style={{ background: ramp[step], color: cellInk(step, n, dark) }}
                    onMouseEnter={() => setHover([i, j])}
                    onFocus={() => setHover([i, j])}
                    aria-label={`True ${titleCase(c.labels[i])}, predicted ${titleCase(c.labels[j])}: ${n}`}
                  >
                    {n}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="viz-readout" aria-live="polite">
        {readout}
      </div>
    </figure>
  );
}

function ClassDots({ perClass }: { perClass: PerClass }) {
  const [hover, setHover] = useState<string | null>(null);
  const entries = Object.entries(perClass);
  return (
    <figure className="viz">
      <figcaption>
        By class
        <span className="viz-legend">
          <span className="lg lg-sens" /> Sensitivity <span className="lg lg-prec" /> Precision
        </span>
      </figcaption>
      <div className="dots">
        {entries.map(([label, v]) => (
          <div
            key={label}
            className={`dot-row${hover === label ? " on" : ""}`}
            onMouseEnter={() => setHover(label)}
            onMouseLeave={() => setHover(null)}
          >
            <span className="dot-label" title={`${v.n} test cases`}>
              {titleCase(label)}
            </span>
            <span className="dot-track">
              <span className="dot-grid" style={{ left: "50%" }} />
              <span className="dot dot-sens" style={{ left: `${v.sensitivity * 100}%` }} />
              <span className="dot dot-prec" style={{ left: `${v.precision * 100}%` }} />
            </span>
            <span className="dot-values numeric">
              {pct(v.sensitivity)} · {pct(v.precision)}
            </span>
          </div>
        ))}
        <div className="dot-axis" aria-hidden="true">
          <span />
          <span className="dot-axis-scale">
            <span>0%</span>
            <span>50%</span>
            <span>100%</span>
          </span>
          <span />
        </div>
      </div>
      <div className="viz-readout" aria-live="polite">
        {hover
          ? `${titleCase(hover)}: finds ${pct(perClass[hover].sensitivity)} of ${perClass[hover].n} true cases; ${pct(perClass[hover].precision)} of its "${titleCase(hover).toLowerCase()}" calls are right.`
          : "Sensitivity: share of true cases found. Precision: share of the model's calls that are right."}
      </div>
    </figure>
  );
}

function ShortcutBars({ model, baseline }: { model: number; baseline: number }) {
  // AUC 0.5 is chance, so the axis starts there: the gap above chance is what matters.
  const x = (v: number) => `${Math.max(0, Math.min(1, (v - 0.5) / 0.5)) * 100}%`;
  const gap = model - baseline;
  return (
    <figure className="viz">
      <figcaption>AI vs shortcut baseline (AUC)</figcaption>
      <div className="sc">
        <div className="sc-row">
          <span>AI model</span>
          <span className="sc-track">
            <span className="sc-bar sc-model" style={{ width: x(model) }} />
          </span>
          <span className="numeric">{model.toFixed(3)}</span>
        </div>
        <div className="sc-row">
          <span>Image size and colour only</span>
          <span className="sc-track">
            <span className="sc-bar sc-base" style={{ width: x(baseline) }} />
          </span>
          <span className="numeric">{baseline.toFixed(3)}</span>
        </div>
        <div className="sc-axis" aria-hidden="true">
          <span />
          <span className="dot-axis-scale">
            <span>0.5 chance</span>
            <span>0.75</span>
            <span>1.0</span>
          </span>
          <span />
        </div>
      </div>
      <div className={`viz-readout${gap < 0.05 ? " viz-warn" : ""}`}>
        {gap < 0.05
          ? `Only ${gap.toFixed(2)} above a model that never looks at anatomy: the result may reflect how images were acquired.`
          : `${gap.toFixed(2)} AUC above a trivial model that sees only image size and colour: the model is using more than acquisition shortcuts.`}
      </div>
    </figure>
  );
}

/** Held-out performance as charts, for models that recorded a confusion matrix. */
export function ModelPerformance({ test, unit = "cases" }: { test: Metrics; unit?: string }) {
  const confusion = test["confusion"] as Confusion | undefined;
  const perClass = test["per_class"] as PerClass | undefined;
  const baseline = test["shortcut_baseline"] as Metrics | undefined;
  const baselineAuc = (baseline?.["auc"] ?? baseline?.["macro_auc_ovr"]) as number | undefined;
  const modelAuc = (test["auc"] ?? test["macro_auc_ovr"]) as number | undefined;
  if (!confusion && !perClass) return null;
  return (
    <div className="perf-grid">
      {confusion && <ConfusionMatrix c={confusion} unit={unit} />}
      {perClass && <ClassDots perClass={perClass} />}
      {baselineAuc != null && modelAuc != null && <ShortcutBars model={modelAuc} baseline={baselineAuc} />}
    </div>
  );
}
