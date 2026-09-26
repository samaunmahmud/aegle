"""Train the EEG seizure detector on CHB-MIT.

    cd inference-service
    python -m training.train_eeg            # add --limit-files 3 --epochs 1 for a smoke test

Data: CHB-MIT Scalp EEG Database 1.0.0 (Shoeb 2009; ODC-BY 1.0), children with
intractable seizures at Boston Children's Hospital, 256 Hz bipolar 10-20 EEG with expert
seizure onset/offset times. Put chbNN/chbNN-summary.txt and the recordings listed in
RECORDS-WITH-SEIZURES under <repo>/dataset/chbmit/.

Split by patient (chb21 is chb01 recorded later, so they are one patient). Training
windows: every seizure window at 1 s stride plus random background windows. Test: the
model runs continuously over whole recordings of unseen patients; reported as window AUC,
seizures detected, detection delay and false alarms per hour.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from app.eeg import MONTAGE, UnsupportedEeg, read_edf, windows
from app.models.eeg_seizure import META_FILE, MODEL_ID, WEIGHTS_FILE
from app.models.resnet1d import ResNet1d
from app.registry import default_model_dir

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "chbmit"
WINDOW, STRIDE, VERSION = 8.0, 4.0, "0.1.0"
BACKGROUND_PER_FILE = 80
THRESHOLD = 0.5


def seizures() -> dict[Path, list[tuple[float, float]]]:
    """Recording path -> seizure (start, end) seconds, from the summary files."""
    out = {}
    for summary in sorted(DATA.glob("chb*/chb*-summary.txt")):
        current = None
        starts: list[float] = []
        for line in summary.read_text(errors="replace").splitlines():
            if m := re.match(r"File Name:\s*(\S+)", line):
                current = summary.parent / m.group(1)
                out[current] = []
                starts = []
            elif m := re.match(r"Seizure(?:\s+\d+)?\s+Start Time:\s*(\d+)", line):
                starts.append(float(m.group(1)))
            elif (m := re.match(r"Seizure(?:\s+\d+)?\s+End Time:\s*(\d+)", line)) and current:
                out[current].append((starts[-1], float(m.group(1))))
    return {p: s for p, s in out.items() if p.exists()}


def patient(path: Path) -> str:
    case = path.parent.name
    return "chb01" if case == "chb21" else case


def overlap(a0, a1, spans) -> float:
    return sum(max(0.0, min(a1, b1) - max(a0, b0)) for b0, b1 in spans)


def sample(files, rng, seizure_stride: float):
    xs, ys = [], []
    for path, spans in files:
        try:
            eeg = read_edf(path.read_bytes())
        except UnsupportedEeg:
            continue                                   # some CHB-MIT files use a different montage
        n = int(WINDOW * eeg.fs)
        total = eeg.signals.shape[1]
        starts = [s for b0, b1 in spans for s in np.arange(b0, b1 - WINDOW / 2, seizure_stride)]
        pos = [int(s * eeg.fs) for s in starts if overlap(s, s + WINDOW, spans) >= WINDOW / 2]
        neg = []
        while len(neg) < BACKGROUND_PER_FILE:
            a = rng.randrange(0, total - n)
            if overlap(a / eeg.fs, a / eeg.fs + WINDOW, spans) == 0:
                neg.append(a)
        for a, y in [(a, 1.0) for a in pos if a + n <= total] + [(a, 0.0) for a in neg]:
            xs.append(np.clip(eeg.signals[:, a:a + n] / 100.0, -10, 10).astype(np.float16))
            ys.append(y)
    return torch.from_numpy(np.stack(xs)), torch.tensor(ys, dtype=torch.float32)


@torch.no_grad()
def probabilities(model, x, device):
    model.eval()
    out = []
    for i in range(0, len(x), 512):
        out.append(torch.sigmoid(model(x[i:i + 512].float().to(device)))[:, 0].cpu().numpy())
    return np.concatenate(out)


def continuous_evaluation(model, files, device) -> dict:
    """Run over whole recordings as in use, with the served smoothing and threshold."""
    ys, ps = [], []
    detected, delays, false_alarms, hours, total_seizures = 0, [], 0, 0.0, 0
    for path, spans in files:
        try:
            eeg = read_edf(path.read_bytes())
        except UnsupportedEeg:
            continue
        x, starts = windows(eeg, WINDOW, STRIDE)
        p = probabilities(model, torch.from_numpy(x), device)
        p = np.convolve(np.pad(p, 1, mode="edge"), np.ones(3) / 3, mode="valid")
        y = np.array([overlap(s, s + WINDOW, spans) >= WINDOW / 2 for s in starts], dtype=float)
        ys.append(y); ps.append(p)
        hours += eeg.seconds / 3600
        alarms = p >= THRESHOLD
        # Alarm events: runs of consecutive positive windows.
        events, run = [], None
        for i, a in enumerate(alarms):
            if a and run is None:
                run = i
            if (not a or i == len(alarms) - 1) and run is not None:
                end = i if a else i - 1
                events.append((starts[run], starts[end] + WINDOW))
                run = None
        for b0, b1 in spans:
            total_seizures += 1
            hits = [e0 for e0, e1 in events if e0 < b1 and e1 > b0]
            if hits:
                detected += 1
                delays.append(max(0.0, min(hits) + WINDOW - b0))    # alarm known at window end
        false_alarms += sum(1 for e0, e1 in events if overlap(e0, e1, spans) == 0)
    y, p = np.concatenate(ys), np.concatenate(ps)
    pred = p >= THRESHOLD
    return {
        "recordings": len(ys), "hours": round(hours, 1), "windows": int(len(y)), "seizures": total_seizures,
        "window_auc": round(float(roc_auc_score(y, p)), 4) if 0 < y.sum() < len(y) else None,
        "window_sensitivity": round(float((pred & (y == 1)).sum() / max(1, (y == 1).sum())), 4),
        "window_specificity": round(float((~pred & (y == 0)).sum() / max(1, (y == 0).sum())), 4),
        "seizures_detected": round(detected / max(1, total_seizures), 4),
        "median_detection_delay_s": round(float(np.median(delays)), 1) if delays else None,
        "false_alarms_per_hour": round(false_alarms / max(hours, 1e-6), 3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit-files", type=int, default=0, help="per patient (smoke test)")
    args = ap.parse_args()

    rng = random.Random(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    out_dir = args.out or default_model_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    by_patient: dict[str, list] = {}
    for path, spans in seizures().items():
        by_patient.setdefault(patient(path), []).append((path, spans))
    if args.limit_files:
        by_patient = {k: v[: args.limit_files] for k, v in by_patient.items()}
    patients = sorted(by_patient)
    rng.shuffle(patients)
    n_test = max(1, round(len(patients) * 0.2))
    test_p, val_p, train_p = patients[:n_test], patients[n_test:n_test + 3], patients[n_test + 3:]
    files = lambda ps: [f for p in ps for f in by_patient[p]]  # noqa: E731
    print(f"{MODEL_ID}: device={device} patients train={train_p} val={val_p} test={test_p}", flush=True)

    x_train, y_train = sample(files(train_p), rng, seizure_stride=1.0)
    x_val, y_val = sample(files(val_p), rng, seizure_stride=4.0)
    print(f"windows train={len(y_train)} ({int(y_train.sum())} seizure) val={len(y_val)} "
          f"({int(y_val.sum())} seizure)", flush=True)

    model = ResNet1d(1, leads=len(MONTAGE)).to(device)
    pos_weight = torch.tensor([float((y_train == 0).sum() / max(1, (y_train == 1).sum()))], device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-3)
    loader = DataLoader(TensorDataset(x_train, y_train), batch_size=128, shuffle=True)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=args.epochs * len(loader))

    best, best_state = -1.0, None
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, total = time.time(), 0.0
        for x, y in loader:
            x = x.float() * torch.empty(len(x), 1, 1).uniform_(0.8, 1.2)     # amplitude variation
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = loss_fn(model(x)[:, 0], y)
            loss.backward()
            opt.step()
            sched.step()
            total += loss.item() * len(y)
        val_auc = roc_auc_score(y_val.numpy(), probabilities(model, x_val, device))
        print(f"epoch {epoch}/{args.epochs} loss={total / len(y_train):.4f} val_window_auc={val_auc:.4f} "
              f"({time.time() - t0:.0f}s)", flush=True)
        if val_auc > best:
            best = val_auc
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    test = continuous_evaluation(model, files(test_p), device)
    print("TEST (continuous, unseen patients):", json.dumps(test, indent=2), flush=True)

    torch.save(best_state, out_dir / WEIGHTS_FILE)
    (out_dir / META_FILE).write_text(json.dumps({
        "model_id": MODEL_ID, "version": VERSION, "architecture": "resnet1d",
        "window_seconds": WINDOW, "stride_seconds": STRIDE, "threshold": THRESHOLD,
        "metrics": {
            "validation_window_auc": round(float(best), 4),
            "test": {"n": test["windows"], **test},
            "split": {"test_patients": test_p, "validation_patients": val_p, "train_patients": len(train_p)},
            "dataset": "CHB-MIT Scalp EEG (Shoeb, 2009; ODC-BY 1.0): recordings with seizures from 23 "
                       "children with intractable epilepsy, Boston Children's Hospital",
            "caveat": "Paediatric, one centre, patients with intractable epilepsy; evaluated on recordings "
                      "that contain seizures only; do not use for clinical decisions.",
        },
    }, indent=2))
    print(f"saved to {out_dir}", flush=True)


if __name__ == "__main__":
    main()
