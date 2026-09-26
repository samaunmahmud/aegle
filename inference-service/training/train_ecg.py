"""Train the 12-lead ECG rhythm model on PTB-XL (multi-label).

    cd inference-service
    python -m training.train_ecg            # add --limit 400 --epochs 1 for a smoke test

Data: PTB-XL 1.0.3 (Wagner et al. 2020, CC BY 4.0), 21,799 10-second 12-lead ECGs from
18,869 patients, Physikalisch-Technische Bundesanstalt, Germany. Put ptbxl_database.csv,
scp_statements.csv and records100/ (the 100 Hz records) in <repo>/dataset/ptbxl/.

Split: the dataset's recommended stratified folds, which keep each patient in one fold:
1-8 train, 9 validation, 10 test (folds 9 and 10 only contain labels a cardiologist
validated). Rhythm statements with at least 150 recordings are modelled, independently.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, Dataset

from app.models.ecg_rhythm import META_FILE, MODEL_ID, WEIGHTS_FILE
from app.models.resnet1d import ResNet1d
from app.registry import default_model_dir
from app.waveform import LEADS

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "ptbxl"
FS, SECONDS, CLIP_MV = 100, 10, 5.0
VERSION = "0.1.0"
# PTB-XL rhythm code -> Aegle label. Rarer rhythms (<150 recordings) are left out.
RHYTHMS = {
    "SR": "SINUS_RHYTHM",
    "AFIB": "ATRIAL_FIBRILLATION",
    "STACH": "SINUS_TACHYCARDIA",
    "SBRAD": "SINUS_BRADYCARDIA",
    "SARRH": "SINUS_ARRHYTHMIA",
    "PACE": "PACED_RHYTHM",
    "SVARR": "SUPRAVENTRICULAR_ARRHYTHMIA",
}
LABELS = list(RHYTHMS.values())


def read_record(base: Path) -> np.ndarray:
    """A WFDB format-16 record as (12, samples) in mV, rows in Aegle's lead order."""
    header = base.with_suffix(".hea").read_text().splitlines()
    n_sig = int(header[0].split()[1])
    gains, names = [], []
    for line in header[1:1 + n_sig]:
        parts = line.split()
        gains.append(float(parts[2].split("/")[0].split("(")[0]))
        names.append(parts[-1])
    raw = np.fromfile(base.with_suffix(".dat"), dtype="<i2").reshape(-1, n_sig).T
    mv = raw.astype(np.float32) / np.array(gains, dtype=np.float32)[:, None]
    order = [names.index(l if l in names else l.upper()) for l in LEADS]
    return mv[order]


def load(limit: int = 0):
    rows = list(csv.DictReader(open(DATA / "ptbxl_database.csv")))
    records = {"train": [], "val": [], "test": []}
    for r in rows:
        codes = ast.literal_eval(r["scp_codes"])
        y = np.array([1.0 if code in codes else 0.0 for code in RHYTHMS], dtype=np.float32)
        fold = int(r["strat_fold"])
        split = "test" if fold == 10 else "val" if fold == 9 else "train"
        records[split].append((DATA / r["filename_lr"], y, r["patient_id"]))
    if limit:
        records = {k: v[:limit] for k, v in records.items()}
    return records


class EcgDataset(Dataset):
    def __init__(self, items, augment: bool):
        self.x = np.stack([np.clip(read_record(p), -CLIP_MV, CLIP_MV) for p, _, _ in items])
        self.y = np.stack([y for _, y, _ in items])
        self.augment = augment

    def __len__(self):
        return len(self.y)

    def __getitem__(self, i):
        x = self.x[i].copy()
        if self.augment:
            x *= np.random.uniform(0.8, 1.2)                          # amplitude/gain differences
            x = np.roll(x, np.random.randint(-50, 50), axis=1)        # where the strip starts
            x += np.random.normal(0, 0.02, x.shape).astype(np.float32)
        return torch.from_numpy(x), torch.from_numpy(self.y[i])


@torch.no_grad()
def predict_all(model, loader, device):
    model.eval()
    ps, ys = [], []
    for x, y in loader:
        ps.append(torch.sigmoid(model(x.to(device))).cpu().numpy())
        ys.append(y.numpy())
    return np.concatenate(ps), np.concatenate(ys)


def metrics(p: np.ndarray, y: np.ndarray) -> dict:
    per_label, aucs = {}, []
    for i, name in enumerate(LABELS):
        pos, pred = y[:, i] == 1, p[:, i] >= 0.5
        auc = float(roc_auc_score(y[:, i], p[:, i])) if 0 < pos.sum() < len(pos) else float("nan")
        if not np.isnan(auc):
            aucs.append(auc)
        per_label[name] = {
            "n_positive": int(pos.sum()),
            "auc": round(auc, 4),
            "sensitivity": round(float((pred & pos).sum() / max(1, pos.sum())), 4),
            "specificity": round(float((~pred & ~pos).sum() / max(1, (~pos).sum())), 4),
            "precision": round(float((pred & pos).sum() / max(1, pred.sum())), 4),
            "brier": round(float(np.mean((p[:, i] - y[:, i]) ** 2)), 4),
        }
    return {"n": int(len(y)), "macro_auc": round(float(np.mean(aucs)), 4), "per_label": per_label}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    out_dir = args.out or default_model_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    recs = load(args.limit)
    patients = {k: {pid for _, _, pid in v} for k, v in recs.items()}
    assert not (patients["train"] & patients["test"] or patients["train"] & patients["val"]), "patient overlap"
    train, val, test = EcgDataset(recs["train"], True), EcgDataset(recs["val"], False), EcgDataset(recs["test"], False)
    prevalence = train.y.mean(axis=0)
    print(f"{MODEL_ID}: device={device} records train/val/test={len(train)}/{len(val)}/{len(test)} "
          f"positives in train={dict(zip(LABELS, train.y.sum(0).astype(int).tolist()))}", flush=True)

    dl = lambda ds, shuffle: DataLoader(ds, batch_size=args.batch_size, shuffle=shuffle)  # noqa: E731
    train_dl, val_dl, test_dl = dl(train, True), dl(val, False), dl(test, False)

    model = ResNet1d(len(LABELS)).to(device)
    # Rare rhythms would otherwise be ignored; cap the weight so they are not over-called.
    pos_weight = torch.tensor(np.clip((1 - prevalence) / np.maximum(prevalence, 1e-3), 1, 20),
                              dtype=torch.float32, device=device)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-3)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * len(train_dl))

    best, best_state, best_val = -1.0, None, None
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, total = time.time(), 0.0
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss = loss_fn(model(x), y)
            loss.backward()
            opt.step()
            sched.step()
            total += loss.item() * len(y)
        val_m = metrics(*predict_all(model, val_dl, device))
        print(f"epoch {epoch}/{args.epochs} loss={total / len(train):.4f} val_macro_auc={val_m['macro_auc']} "
              f"({time.time() - t0:.0f}s)", flush=True)
        if val_m["macro_auc"] > best:
            best, best_val = val_m["macro_auc"], val_m
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    test_m = metrics(*predict_all(model, test_dl, device))
    print("TEST (best-val checkpoint):", json.dumps(test_m, indent=2), flush=True)

    torch.save(best_state, out_dir / WEIGHTS_FILE)
    (out_dir / META_FILE).write_text(json.dumps({
        "model_id": MODEL_ID, "version": VERSION, "architecture": "resnet1d",
        "labels": LABELS, "fs": FS, "seconds": SECONDS, "clip_mv": CLIP_MV,
        "metrics": {
            "validation": best_val,
            "test": test_m,
            "split": "PTB-XL recommended folds: 1-8 train, 9 validation, 10 test (patient-disjoint)",
            "dataset": "PTB-XL 1.0.3 (Wagner et al., 2020; CC BY 4.0): 21,799 resting 12-lead ECGs, "
                       "10 s, from 18,869 patients, Germany, 1989-1996",
            "caveat": "Multi-label rhythm statements only; decades-old recordings from one country; "
                      "not validated elsewhere; do not use for clinical decisions.",
        },
    }, indent=2))
    print(f"saved to {out_dir}", flush=True)


if __name__ == "__main__":
    main()
