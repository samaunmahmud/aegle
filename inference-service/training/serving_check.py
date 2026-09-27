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
    if model_id == "chest-xray-pneumonia":
        from . import train_pneumonia as tp
        return [(p, tp.LABELS[y]) for p, y, _ in tp.scan(DS / "chest_xray" / "test")]
    if model_id == "brain-mri-tumor-type":
        from . import train_brain_tumor as tb
        d = DS / "brain_tumor_figshare"
        _, _, test = tb.split_by_patient(tb.load_index(d), 0.15, 0.15, 42)
        return [(d / r["file"], r["label"]) for r in test]
    from .common import load_index, split
    trainers = {"blood-smear-malaria": "train_malaria", "fundus-diabetic-retinopathy": "train_retinopathy",
                "skin-lesion-dermoscopy": "train_dermatology", "colonoscopy-findings": "train_gastro",
                "colorectal-tissue-he": "train_tissue", "head-ct-stroke": "train_stroke",
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="*")
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()
    token = os.environ["AEGLE_INFERENCE_TOKEN"]
    skip = {"eeg-seizure", "wound-segmentation"}      # whole recordings / masks: checked by their own tests
    models = args.models or [m for m in ADAPTERS if m not in skip]
    for model_id in models:
        module = __import__(ADAPTERS[model_id].__module__, fromlist=["META_FILE"])
        if not (default_model_dir() / module.META_FILE).exists():
            print(f"{model_id:28} not trained here, skipped")
            continue
        result = check_ecg(args.n, token) if model_id == "ecg-rhythm" else check_images(model_id, args.n, token)
        print(f"{model_id:28} {json.dumps(result)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
