"""Train the brain MRI tumour-type classifier (ResNet-18, ImageNet-pretrained).

    cd inference-service
    python -m training.prepare_brain_tumor          # once: .mat -> PNG + masks + index.csv
    python -m training.train_brain_tumor            # full run
    python -m training.train_brain_tumor --limit 20 --epochs 1   # smoke test

Data: Figshare brain tumour dataset (Cheng et al., CC BY 4.0), 3064 contrast-enhanced
T1 slices from 233 patients, each showing a meningioma, glioma or pituitary tumour.

Train, validation and test are split BY PATIENT (patients have up to 38 slices, so an
image-level split would put the same tumour on both sides). Besides accuracy, the test
report measures calibration (ECE) and whether Grad-CAM falls on the expert tumour outline,
because this dataset mixes imaging planes in a way that correlates with tumour type and a
model can score well by recognising the plane instead of the tumour.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageFilter
from sklearn.metrics import confusion_matrix, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T

from app.gradcam import grad_cam
from app.models.brain_mri_tumor import META_FILE, MODEL_ID, WEIGHTS_FILE
from app.models.resnet import IMAGENET_MEAN, IMAGENET_STD, build_resnet18
from app.registry import default_model_dir

LABELS = ["MENINGIOMA", "GLIOMA", "PITUITARY"]
INPUT_SIZE = 224
VERSION = "0.1.0"
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_index(data: Path) -> list[dict]:
    with open(data / "index.csv") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["y"] = LABELS.index(r["label"])
    return rows


def split_by_patient(rows, val_fraction: float, test_fraction: float, seed: int):
    """Per tumour type, hold out that fraction of its patients for validation and for test."""
    rng = random.Random(seed)
    parts = {"train": [], "val": [], "test": []}
    for y in range(len(LABELS)):
        patients = sorted({r["patient"] for r in rows if r["y"] == y})
        rng.shuffle(patients)
        n_test = max(1, round(len(patients) * test_fraction))
        n_val = max(1, round(len(patients) * val_fraction))
        side = {p: "test" for p in patients[:n_test]}
        side.update({p: "val" for p in patients[n_test:n_test + n_val]})
        for r in rows:
            if r["y"] == y:
                parts[side.get(r["patient"], "train")].append(r)
    return parts["train"], parts["val"], parts["test"]


class SliceDataset(Dataset):
    def __init__(self, data: Path, rows, transform):
        self.data, self.rows, self.transform = data, rows, transform

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        return self.transform(Image.open(self.data / r["file"]).convert("RGB")), r["y"]


def transforms():
    norm = T.Normalize(IMAGENET_MEAN, IMAGENET_STD)
    train = T.Compose([
        T.Resize((INPUT_SIZE, INPUT_SIZE)),
        T.RandomHorizontalFlip(),                  # tumour type does not depend on side
        T.RandomAffine(degrees=10, translate=(0.05, 0.05), scale=(0.9, 1.1)),
        T.ColorJitter(brightness=0.2, contrast=0.2),
        T.ToTensor(), norm,
    ])
    evaluate = T.Compose([T.Resize((INPUT_SIZE, INPUT_SIZE)), T.ToTensor(), norm])
    return train, evaluate


@torch.no_grad()
def predict_all(model, loader, device):
    model.eval()
    probs, labels = [], []
    for x, y in loader:
        probs.append(torch.softmax(model(x.to(device)), dim=1).cpu().numpy())
        labels.append(y.numpy())
    return np.concatenate(probs), np.concatenate(labels)


def expected_calibration_error(p: np.ndarray, y: np.ndarray, bins: int = 15) -> float:
    """Average gap between stated confidence and actual accuracy of the top label."""
    conf, correct = p.max(axis=1), (p.argmax(axis=1) == y)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def metrics(p: np.ndarray, y: np.ndarray) -> dict:
    pred = p.argmax(axis=1)
    cm = confusion_matrix(y, pred, labels=list(range(len(LABELS))))
    per_class = {}
    for i, name in enumerate(LABELS):
        tp = cm[i, i]
        per_class[name] = {
            "n": int(cm[i].sum()),
            "sensitivity": round(float(tp / max(1, cm[i].sum())), 4),
            "precision": round(float(tp / max(1, cm[:, i].sum())), 4),
        }
    return {
        "n": int(len(y)),
        "accuracy": round(float((pred == y).mean()), 4),
        "balanced_accuracy": round(float(np.mean([v["sensitivity"] for v in per_class.values()])), 4),
        "macro_auc_ovr": round(float(roc_auc_score(y, p, multi_class="ovr", average="macro")), 4),
        "ece": round(expected_calibration_error(p, y), 4),
        "per_class": per_class,
        "confusion": {"labels": LABELS, "rows_true_cols_predicted": cm.tolist()},
    }


def attention_on_tumour(model, data: Path, rows, tf_eval, device) -> dict:
    """How much Grad-CAM (for the predicted type) falls on the expert tumour outline.

    energy_inside: share of heatmap mass inside the mask; compare with mask_area, what
    a heatmap spread evenly over the slice would score. pointing: the heatmap's peak lies
    within about 7 mm (15 px) of the tumour.
    """
    model.eval()
    inside, area, hits = {l: [] for l in LABELS}, {l: [] for l in LABELS}, {l: [] for l in LABELS}
    for r in rows:
        img = Image.open(data / r["file"]).convert("RGB")
        mask_img = Image.open(data / r["mask"]).convert("L")
        x = tf_eval(img).unsqueeze(0).to(device)
        with torch.no_grad():
            pred = int(model(x).argmax(dim=1).item())
        cam = grad_cam(model, model.layer4, x, pred)
        cam = np.asarray(Image.fromarray((cam * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR),
                         dtype=np.float32) / 255
        mask = np.asarray(mask_img) > 0
        near = np.asarray(mask_img.filter(ImageFilter.MaxFilter(31))) > 0
        total = cam.sum()
        label = r["label"]
        inside[label].append(float(cam[mask].sum() / total) if total > 0 else 0.0)
        area[label].append(float(mask.mean()))
        hits[label].append(bool(near.flat[int(cam.argmax())]))

    def summary(names):
        e = [v for n in names for v in inside[n]]
        a = [v for n in names for v in area[n]]
        h = [v for n in names for v in hits[n]]
        return {"n": len(e), "energy_inside": round(float(np.mean(e)), 4),
                "mask_area": round(float(np.mean(a)), 4), "pointing": round(float(np.mean(h)), 4)}

    return {"all": summary(LABELS), **{n: summary([n]) for n in LABELS}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=REPO_ROOT / "dataset" / "brain_tumor_figshare")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--val-fraction", type=float, default=0.15)
    ap.add_argument("--test-fraction", type=float, default=0.15)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="use only N images per class per split (smoke test)")
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    out_dir = args.out or default_model_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    train_rows, val_rows, test_rows = split_by_patient(
        load_index(args.data), args.val_fraction, args.test_fraction, args.seed)
    if args.limit:
        def cap(rows):
            return [r for y in range(len(LABELS)) for r in [r for r in rows if r["y"] == y][: args.limit]]
        train_rows, val_rows, test_rows = cap(train_rows), cap(val_rows), cap(test_rows)

    sides = [{r["patient"] for r in rows} for rows in (train_rows, val_rows, test_rows)]
    assert not (sides[0] & sides[1] or sides[0] & sides[2] or sides[1] & sides[2]), "patient on two sides"
    counts = [sum(r["y"] == y for r in train_rows) for y in range(len(LABELS))]
    print(f"device={device} patients train/val/test={[len(s) for s in sides]} "
          f"slices train={len(train_rows)} {counts} val={len(val_rows)} test={len(test_rows)}")

    tf_train, tf_eval = transforms()
    dl = lambda rows, tf, shuffle: DataLoader(  # noqa: E731
        SliceDataset(args.data, rows, tf), batch_size=args.batch_size, shuffle=shuffle,
        num_workers=args.workers, persistent_workers=args.workers > 0)
    train_dl, val_dl, test_dl = dl(train_rows, tf_train, True), dl(val_rows, tf_eval, False), dl(test_rows, tf_eval, False)

    model = build_resnet18(len(LABELS), pretrained=True).to(device)
    class_weights = torch.tensor([sum(counts) / (len(LABELS) * c) for c in counts], dtype=torch.float32, device=device)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)      # glioma has twice the slices of meningioma
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

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
            total += loss.item() * len(y)
        sched.step()
        val = metrics(*predict_all(model, val_dl, device))
        print(f"epoch {epoch}/{args.epochs} loss={total / len(train_rows):.4f} val_bal_acc={val['balanced_accuracy']} "
              f"val_auc={val['macro_auc_ovr']} ({time.time() - t0:.0f}s)", flush=True)
        if val["balanced_accuracy"] > best:
            best, best_val = val["balanced_accuracy"], val
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    test = metrics(*predict_all(model, test_dl, device))
    test["attention_on_tumour"] = attention_on_tumour(model, args.data, test_rows, tf_eval, device)
    print("TEST (best-val checkpoint):", json.dumps(test, indent=2))

    torch.save(best_state, out_dir / WEIGHTS_FILE)
    (out_dir / META_FILE).write_text(json.dumps({
        "model_id": MODEL_ID,
        "version": VERSION,
        "architecture": "resnet18",
        "labels": LABELS,
        "input_size": INPUT_SIZE,
        "mean": IMAGENET_MEAN,
        "std": IMAGENET_STD,
        "metrics": {
            "validation_patient_split": best_val,
            "test_patient_split": test,
            "split": {"seed": args.seed, "patients_train_val_test": [len(s) for s in sides]},
            "dataset": "Figshare brain tumor dataset (Cheng et al., CC BY 4.0): T1 contrast MRI slices "
                       "from two hospitals in China, 2005-2010; every slice contains a tumour",
            "caveat": "Tumour-type classification only; not externally validated; do not use for clinical decisions.",
        },
    }, indent=2))
    print(f"saved to {out_dir}")


if __name__ == "__main__":
    main()
