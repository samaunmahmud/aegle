"""Train the chest X-ray pneumonia classifier (ResNet-18, ImageNet-pretrained).

    cd inference-service
    python -m training.train_pneumonia            # full run
    python -m training.train_pneumonia --limit 64 --epochs 1   # smoke test

Expects the Kaggle "Chest X-Ray Images (Pneumonia)" layout under
<repo>/dataset/chest_xray/{train,test}/{NORMAL,PNEUMONIA}. Writes weights and a
metadata JSON (including test metrics) to <repo>/saved-model/.

Validation is split BY PATIENT. Many patients have several images (one has 30),
so a random image-level split would leak patients into validation and inflate it.
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
from PIL import Image
from sklearn.metrics import confusion_matrix, roc_auc_score
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T

from app.models.chest_xray_pneumonia import META_FILE, WEIGHTS_FILE
from app.models.resnet import IMAGENET_MEAN, IMAGENET_STD, build_resnet18
from app.registry import default_model_dir

LABELS = ["NORMAL", "PNEUMONIA"]
INPUT_SIZE = 224
VERSION = "0.1.0"
REPO_ROOT = Path(__file__).resolve().parents[2]


def patient_key(path: Path) -> str:
    """Group id so all images of one patient stay on the same side of a split."""
    m = re.match(r"person(\d+)_", path.name)          # PNEUMONIA: person23_bacteria_...
    if m:
        return f"P{m.group(1)}"
    m = re.search(r"IM-(\d+)", path.name)              # NORMAL: IM-0115-0001, NORMAL2-IM-0385-0001
    if m:
        return f"N{m.group(1)}"
    return path.stem                                   # unknown pattern: treat as its own patient


def scan(split_dir: Path) -> list[tuple[Path, int, str]]:
    items = []
    for label_idx, label in enumerate(LABELS):
        for p in sorted((split_dir / label).glob("*.jp*g")):
            items.append((p, label_idx, patient_key(p)))
    return items


def split_by_patient(items, val_fraction: float, seed: int):
    """Hold out `val_fraction` of the patients of each class."""
    rng = random.Random(seed)
    train, val = [], []
    for label_idx in range(len(LABELS)):
        cls = [it for it in items if it[1] == label_idx]
        groups = sorted({it[2] for it in cls})
        rng.shuffle(groups)
        held = set(groups[: max(1, int(len(groups) * val_fraction))])
        for it in cls:
            (val if it[2] in held else train).append(it)
    return train, val


class XrayDataset(Dataset):
    def __init__(self, items, transform):
        self.items, self.transform = items, transform

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        path, label, _ = self.items[i]
        img = Image.open(path)
        img.draft("L", (INPUT_SIZE * 2, INPUT_SIZE * 2))   # fast JPEG downscale on decode
        return self.transform(img.convert("L").convert("RGB")), label


def transforms():
    norm = T.Normalize(IMAGENET_MEAN, IMAGENET_STD)
    train = T.Compose([
        T.Resize((INPUT_SIZE, INPUT_SIZE)),
        T.RandomAffine(degrees=8, translate=(0.05, 0.05), scale=(0.92, 1.08)),
        T.ColorJitter(brightness=0.2, contrast=0.2),
        T.ToTensor(), norm,
    ])
    evaluate = T.Compose([T.Resize((INPUT_SIZE, INPUT_SIZE)), T.ToTensor(), norm])
    return train, evaluate


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    probs, labels = [], []
    for x, y in loader:
        p = torch.softmax(model(x.to(device)), dim=1)[:, 1].cpu().numpy()
        probs.append(p)
        labels.append(y.numpy())
    p, y = np.concatenate(probs), np.concatenate(labels)
    pred = (p >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "n": int(len(y)),
        "auc": round(float(roc_auc_score(y, p)), 4),
        "accuracy": round(float((tp + tn) / len(y)), 4),
        "sensitivity": round(float(tp / (tp + fn)), 4),      # pneumonia correctly flagged
        "specificity": round(float(tn / (tn + fp)), 4),      # normal correctly cleared
        "confusion": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=REPO_ROOT / "dataset" / "chest_xray")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--val-fraction", type=float, default=0.15)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="use only N train images per class (smoke test)")
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    out_dir = args.out or default_model_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    train_items, val_items = split_by_patient(scan(args.data / "train"), args.val_fraction, args.seed)
    test_items = scan(args.data / "test")
    if args.limit:
        def cap(items):
            return [it for c in range(2) for it in [x for x in items if x[1] == c][: args.limit]]
        train_items, val_items, test_items = cap(train_items), cap(val_items), cap(test_items)

    train_patients = {it[2] for it in train_items}
    assert not train_patients & {it[2] for it in val_items}, "patient leaked into validation"
    counts = [sum(1 for it in train_items if it[1] == c) for c in range(2)]
    print(f"device={device} train={len(train_items)} {counts} val={len(val_items)} test={len(test_items)}")

    tf_train, tf_eval = transforms()
    dl = lambda items, tf, shuffle: DataLoader(  # noqa: E731
        XrayDataset(items, tf), batch_size=args.batch_size, shuffle=shuffle,
        num_workers=args.workers, persistent_workers=args.workers > 0)
    train_dl, val_dl, test_dl = dl(train_items, tf_train, True), dl(val_items, tf_eval, False), dl(test_items, tf_eval, False)

    model = build_resnet18(len(LABELS), pretrained=True).to(device)
    class_weights = torch.tensor([sum(counts) / (2 * c) for c in counts], dtype=torch.float32, device=device)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)     # compensates NORMAL:PNEUMONIA imbalance
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)

    best_auc, best_state, best_val = -1.0, None, None
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
        val = evaluate(model, val_dl, device)
        print(f"epoch {epoch}/{args.epochs} loss={total / len(train_items):.4f} "
              f"val_auc={val['auc']} val_sens={val['sensitivity']} val_spec={val['specificity']} "
              f"({time.time() - t0:.0f}s)", flush=True)
        if val["auc"] > best_auc:
            best_auc, best_val = val["auc"], val
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    test = evaluate(model, test_dl, device)
    print("TEST (best-val checkpoint):", json.dumps(test))

    torch.save(best_state, out_dir / WEIGHTS_FILE)
    (out_dir / META_FILE).write_text(json.dumps({
        "model_id": "chest-xray-pneumonia",
        "version": VERSION,
        "architecture": "resnet18",
        "labels": LABELS,
        "input_size": INPUT_SIZE,
        "mean": IMAGENET_MEAN,
        "std": IMAGENET_STD,
        "metrics": {
            "validation_patient_split": best_val,
            "test": test,
            "dataset": "Kaggle Chest X-Ray Images (Pneumonia): pediatric, single centre",
            "caveat": "Not externally validated; do not use for clinical decisions.",
        },
    }, indent=2))
    print(f"saved to {out_dir}")


if __name__ == "__main__":
    main()
