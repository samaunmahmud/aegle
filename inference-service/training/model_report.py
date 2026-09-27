"""Write docs/models.md from the trained models' metadata, so documentation cannot drift.

    cd inference-service
    python -m training.model_report            # writes ../docs/models.md

Every number comes from the metadata JSON written at training time (held-out test sets).
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

from app.registry import ADAPTERS, default_model_dir

REPO_ROOT = Path(__file__).resolve().parents[2]

SPECIALTY = {"XR": "Radiology", "ECG": "Cardiology", "XC": "Dermatology", "OP": "Ophthalmology",
             "SM": "Pathology", "ES": "Gastroenterology", "EEG": "Neurology"}
WITHDRAWN = {  # model id -> (metadata file, specialty, why, short reason, data)
    "fundus-glaucoma": ("glaucoma-resnet18.json", "Ophthalmology",
                        "Withdrawn. On ACRIMA a logistic regression on image size and colour statistics reaches "
                        "AUC 0.99, so the model's perfect test score reflects how the classes were photographed.",
                        "shortcut", "ACRIMA"),
    "head-ct-stroke": ("head-ct-stroke-resnet18.json", "Neurology",
                       "Withdrawn. With 99 patients it overfits after two epochs and finds 15% of ischaemic-stroke "
                       "slices; haemorrhage triage needs a far larger dataset (e.g. RSNA Intracranial Haemorrhage).",
                       "too little data", "León NCCT"),
}


def specialty(modality: str, body_part: str | None) -> str:
    if modality in ("CT", "MR") and body_part in ("BRAIN", "HEAD"):
        return "Neurology"
    return SPECIALTY.get(modality, "Radiology")


def pct(v) -> str:
    return f"{v * 100:.1f}%" if isinstance(v, (int, float)) else "–"


def num(v, digits=3) -> str:
    return f"{v:.{digits}f}" if isinstance(v, (int, float)) else "–"


def headline(test: dict) -> str:
    """The one-line result, chosen by task type."""
    if "seizures_detected" in test:
        return (f"window AUC {num(test.get('window_auc'))}; {pct(test['seizures_detected'])} of "
                f"{test['seizures']} seizures detected, median delay {test.get('median_detection_delay_s')} s, "
                f"{num(test['false_alarms_per_hour'], 2)} false alarms/hour over {test['hours']} h")
    if "dice" in test:
        return (f"Dice {num(test['dice'])}, IoU {num(test['iou'])}; median area error "
                f"{pct(test['median_area_error'])}, area within 20% in {pct(test['area_within_20pct'])}")
    if "per_label" in test:
        return f"macro AUC {num(test['macro_auc'])} over {len(test['per_label'])} rhythm labels"
    auc = test.get("auc", test.get("macro_auc_ovr"))
    return (f"accuracy {pct(test.get('accuracy'))}, balanced accuracy {pct(test.get('balanced_accuracy'))}, "
            f"AUC {num(auc)}, calibration error {num(test.get('ece'))}")


def section(model_id: str, meta: dict) -> list[str]:
    m = meta["metrics"]
    test = m.get("test") or m.get("test_patient_split") or {}
    lines = [f"### `{model_id}` v{meta['version']}", ""]
    lines.append(f"**Held-out test ({test.get('n', '?')} cases):** {headline(test)}.")
    if "external_test" in m:
        lines.append(f"**External test ({m['external_test']['n']} cases):** {headline(m['external_test'])}.")
    base = test.get("shortcut_baseline")
    if base:
        bal = test.get("balanced_accuracy", (test.get("sensitivity", 0) + test.get("specificity", 0)) / 2)
        lines.append(f"**Shortcut check:** image size/colour alone reaches balanced accuracy "
                     f"{pct(base['balanced_accuracy'])}, AUC {num(base.get('auc', base.get('macro_auc_ovr')))} "
                     f"(model: {pct(bal)}, {num(test.get('auc', test.get('macro_auc_ovr')))}).")
    setups = test.get("by_capture_setup")
    if setups:
        lines.append("**Within one capture setup:** " + "; ".join(
            f"{name.replace('_', ' ')} ({s['n']} frames) balanced accuracy {pct(s['balanced_accuracy'])}"
            for name, s in setups.items()) + ".")
    if meta.get("mask_regions"):
        lines.append(f"**Blacked out before the model sees the image:** {len(meta['mask_regions'])} burnt-in "
                     f"overlay region(s) that differed by class.")
    att = test.get("attention_on_lesion") or test.get("attention_on_tumour")
    if att:
        a = att["all"]
        lines.append(f"**Where it looks:** {pct(a['energy_inside'])} of Grad-CAM on the expert lesion outline "
                     f"(lesion covers {pct(a['mask_area'])} of the image); peak within 15 px of the lesion in "
                     f"{pct(a['pointing'])} of cases.")
    cm = test.get("confusion", {})
    if cm.get("labels", [None])[0] == "DR_NONE":
        # Screening is judged on referable disease: moderate or worse vs none/mild.
        c = cm["rows_true_cols_predicted"]
        found = sum(c[i][j] for i in range(2, 5) for j in range(2, 5))
        cleared = sum(c[i][j] for i in range(2) for j in range(2))
        lines.append(f"**Referable DR (moderate or worse):** sensitivity {pct(found / sum(map(sum, c[2:])))}, "
                     f"specificity {pct(cleared / sum(map(sum, c[:2])))}.")
    if cm.get("labels", [None])[-1] == "BENIGN_PROSTATE":
        # The first question for a biopsy patch: any cancer (pattern 3, 4 or 5) vs benign.
        c = cm["rows_true_cols_predicted"]
        found = sum(c[i][j] for i in range(3) for j in range(3))
        lines.append(f"**Cancer (any pattern) vs benign:** sensitivity {pct(found / sum(map(sum, c[:3])))}, "
                     f"specificity {pct(c[3][3] / sum(c[3]))}.")
    if "per_class" in test:
        lines += ["", "| Class | n | Sensitivity | Precision |", "|---|---|---|---|"]
        lines += [f"| {k} | {v['n']} | {pct(v['sensitivity'])} | {pct(v['precision'])} |"
                  for k, v in test["per_class"].items()]
    if "per_label" in test:
        lines += ["", "| Rhythm | Positives | AUC | Sensitivity | Specificity |", "|---|---|---|---|---|"]
        lines += [f"| {k} | {v['n_positive']} | {num(v['auc'])} | {pct(v['sensitivity'])} | {pct(v['specificity'])} |"
                  for k, v in test["per_label"].items()]
    lines += ["", f"*Data:* {m.get('dataset', '–')}", "", f"*Caveat:* {m.get('caveat', '–')}", ""]
    return lines


def main():
    out = ["# Aegle AI models", "",
           "Generated by `inference-service/training/model_report.py` from each model's training metadata. "
           "Every result is on data the model never trained on. All models are research prototypes: "
           "none is validated for clinical use.", ""]
    rows, sections = [], []
    for model_id, cls in ADAPTERS.items():
        module = importlib.import_module(cls.__module__)
        meta_path = default_model_dir() / module.META_FILE
        if not meta_path.exists():
            rows.append(f"| – | `{model_id}` | not trained on this machine | – |")
            continue
        meta = json.loads(meta_path.read_text())
        modality = getattr(cls, "MODALITY", None) or {"ecg-rhythm": "ECG", "eeg-seizure": "EEG",
                                                      "wound-segmentation": "XC"}[model_id]
        m = meta["metrics"]
        test = m.get("test") or m.get("test_patient_split") or {}
        rows.append(f"| {specialty(modality, getattr(cls, 'BODY_PART', None))} | `{model_id}` | {headline(test)} | "
                    f"{m.get('dataset', '–').split(':')[0]} |")
        sections += section(model_id, meta)
    for model_id, (meta_file, spec, reason, short, data) in WITHDRAWN.items():
        p = default_model_dir() / meta_file
        if p.exists():
            rows.append(f"| {spec} | ~~`{model_id}`~~ | **withdrawn**: {short} | {data} |")
            sections += section(model_id, json.loads(p.read_text())) + [f"**{reason}**", ""]
    out += ["| Specialty | Model | Held-out result | Data |", "|---|---|---|---|", *rows, "", *sections]
    target = REPO_ROOT / "docs" / "models.md"
    target.write_text("\n".join(out))
    print(f"wrote {target} ({len(rows)} models)")


if __name__ == "__main__":
    main()
