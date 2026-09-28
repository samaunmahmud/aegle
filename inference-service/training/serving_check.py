"""Check that the running inference service reproduces each model's held-out results.

    cd inference-service
    AEGLE_INFERENCE_TOKEN=... python -m training.serving_check [model-id ...] [--n 200]

Sends a random sample of each model's held-out test cases through the live HTTP API,
exactly as core-api does (raw file bytes; DICOM for ECG), and compares accuracy with
the value recorded at training time. A clear gap means serving decodes or preprocesses
differently from training, which would make every result in the app wrong.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import os
import random
import ssl
import sys
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

from app.registry import ADAPTERS, default_model_dir

REPO = Path(__file__).resolve().parents[2]
DS = REPO / "dataset"
URL = os.environ.get("AEGLE_INFERENCE_URL", "https://localhost:8000")
CA = os.environ.get("AEGLE_CA", str(REPO / "infra/tls/certs/ca.crt"))


def post(model_id: str, data: bytes, token: str) -> dict:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"upload\"\r\n"
            f"Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{URL}/v1/models/{model_id}/predict?heatmap=false", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, context=ssl.create_default_context(cafile=CA), timeout=120) as r:
        return json.load(r)


def image_cases(model_id: str) -> list[tuple[Path, str]]:
    """Held-out (file, true label) pairs, from the same split the training script used."""
    if model_id == "brain-mri-tumor-type":
        from . import train_brain_tumor as tb
        d = DS / "brain_tumor_figshare"
        _, _, test = tb.split_by_patient(tb.load_index(d), 0.15, 0.15, 42)
        return [(d / r["file"], r["label"]) for r in test]
    from .common import load_index, split
    trainers = {"chest-xray-pneumonia": "train_pneumonia", "blood-smear-malaria": "train_malaria", "fundus-diabetic-retinopathy": "train_retinopathy",
                "skin-lesion-dermoscopy": "train_dermatology", "colonoscopy-findings": "train_gastro",
                "colorectal-tissue-he": "train_tissue",
                "prostate-gleason-pattern": "train_gleason"}
    task = __import__(f"training.{trainers[model_id]}", fromlist=["TASK"]).TASK
    _, _, test, _ = split(load_index(task), task.labels, 0.15, 0.15, 42)
    return [(task.data_dir / r["file"], r["label"]) for r in test]


def recorded(model_id: str) -> dict:
    module = __import__(ADAPTERS[model_id].__module__, fromlist=["META_FILE"])
    m = json.loads((default_model_dir() / module.META_FILE).read_text())["metrics"]
    return m.get("test") or m.get("test_patient_split") or {}


def check_images(model_id: str, n: int, token: str) -> dict:
    cases = image_cases(model_id)
    random.Random(0).shuffle(cases)
    cases = cases[:n]
    truth, pred = [], []
    for path, label in cases:
        out = post(model_id, path.read_bytes(), token)
        truth.append(label)
        pred.append(out["top_label"])
    labels = sorted(set(truth))
    bal = np.mean([np.mean([p == l for t, p in zip(truth, pred) if t == l]) for l in labels])
    rec = recorded(model_id)
    return {"n": len(cases), "served_accuracy": round(float(np.mean(np.array(truth) == np.array(pred))), 4),
            "recorded_accuracy": rec.get("accuracy"), "served_balanced_accuracy": round(float(bal), 4),
            "recorded_balanced_accuracy": rec.get("balanced_accuracy")}


def check_ecg(n: int, token: str) -> dict:
    from .ecg_dicom import ecg_dicom
    from .train_ecg import LABELS, RHYTHMS, read_record
    rows = [r for r in csv.DictReader(open(DS / "ptbxl/ptbxl_database.csv")) if r["strat_fold"] == "10"]
    random.Random(0).shuffle(rows)
    y, p = [], []
    for r in rows[:n]:
        out = post("ecg-rhythm", ecg_dicom(read_record(DS / "ptbxl" / r["filename_lr"]), 100.0), token)
        probs = {q["label"]: q["probability"] for q in out["predictions"]}
        codes = ast.literal_eval(r["scp_codes"])
        y.append([1 if code in codes else 0 for code in RHYTHMS])
        p.append([probs[l] for l in LABELS])
    y, p = np.array(y), np.array(p)
    aucs = [roc_auc_score(y[:, i], p[:, i]) for i in range(len(LABELS)) if 0 < y[:, i].sum() < len(y)]
    return {"n": len(y), "served_macro_auc": round(float(np.mean(aucs)), 4),
            "recorded_macro_auc": recorded("ecg-rhythm").get("macro_auc"),
            "note": "sample macro AUC over labels present in the sample"}


def check_wound(n: int, token: str) -> dict:
    """Served wound area vs the expert mask, as recorded at training time."""
    from PIL import Image
    from .train_wound import pairs
    cases = [(i, m) for i, m in pairs("validation") if (np.asarray(Image.open(m).convert("L")) > 127).any()]
    random.Random(0).shuffle(cases)
    errs = []
    for img, mask in cases[:n]:
        out = post("wound-segmentation", img.read_bytes(), token)
        area = {q["name"]: q["value"] for q in out["measurements"]}["wound_area"]
        truth = int((np.asarray(Image.open(mask).convert("L")) > 127).sum())
        errs.append(abs(area - truth) / truth)
    rec = recorded("wound-segmentation")
    return {"n": len(errs), "served_median_area_error": round(float(np.median(errs)), 4),
            "recorded_median_area_error": rec.get("median_area_error"),
            "served_area_within_20pct": round(float(np.mean(np.array(errs) <= 0.2)), 4),
            "recorded_area_within_20pct": rec.get("area_within_20pct")}


def check_eeg(n: int, token: str) -> dict:
    """Whole test-patient recordings through the API vs the training code's alarm computation."""
    import torch
    from app.models.eeg_seizure import alarm_events, alarm_score
    from app.models.resnet1d import ResNet1d
    from . import train_eeg as te
    _, files, _, _, test_p = te.split_patients(42)
    meta = json.loads((default_model_dir() / te.META_FILE).read_text())
    net = ResNet1d(1, leads=len(te.MONTAGE))
    net.load_state_dict(torch.load(default_model_dir() / te.WEIGHTS_FILE, map_location="cpu", weights_only=True))
    recs = files(test_p)
    random.Random(0).shuffle(recs)
    peak_diff, same_count = [], 0
    for path, spans in recs[:n]:
        out = post("eeg-seizure", path.read_bytes(), token)
        served_peak = {q["label"]: q["probability"] for q in out["predictions"]}["SEIZURE_ACTIVITY"]
        served_alarms = {q["name"]: q["value"] for q in out["measurements"]}["seizure_alarms"]
        r = te.recording_probabilities(net, [(path, spans)], torch.device("cpu"))[0]
        score = alarm_score(r["p"], meta["threshold"], meta["min_windows"])
        peak_diff.append(abs(served_peak - float(score.max())))
        same_count += int(served_alarms == len(alarm_events(score, r["starts"], te.WINDOW)))
    return {"recordings": len(peak_diff), "max_peak_score_difference": round(max(peak_diff), 6),
            "same_alarm_count": f"{same_count}/{len(peak_diff)}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*")
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()
    token = os.environ["AEGLE_INFERENCE_TOKEN"]
    models = args.models or list(ADAPTERS)
    for model_id in models:
        module = __import__(ADAPTERS[model_id].__module__, fromlist=["META_FILE"])
        if not (default_model_dir() / module.META_FILE).exists():
            print(f"{model_id:28} not trained here, skipped")
            continue
        special = {"ecg-rhythm": check_ecg, "wound-segmentation": check_wound,
                   "eeg-seizure": lambda n, t: check_eeg(min(n, 6), t)}          # EEG: whole recordings, slow
        result = special[model_id](args.n, token) if model_id in special else check_images(model_id, args.n, token)
        print(f"{model_id:28} {json.dumps(result)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
