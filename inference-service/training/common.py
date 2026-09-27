"""Shared training for Aegle's image classifiers (ResNet-18, ImageNet-pretrained).

Each model has a prepare script that writes <data>/index.csv with columns:

    file   image path relative to <data>
    label  one of the task's labels
    group  patient (or slide, lesion, procedure) id: all rows of a group stay on one side;
           groups are stratified by the first-listed label they contain
    mask   optional: expert lesion mask, enables the Grad-CAM localisation check
    split  optional: train/val/test fixed by the dataset, or "external" for an independent
           test set reported separately; rows without it are split by group

and a train script that describes the Task and calls run(). Every model is reported
the same way on its held-out test set: accuracy, balanced accuracy, macro AUC,
per-class sensitivity and precision, confusion matrix, calibration error, (with masks)
how much of the Grad-CAM heatmap lands on the lesion, and a shortcut baseline: a trivial
model on image size, colour statistics and file size. If that baseline scores close to
the real model, the classes probably differ in how images were acquired and the real
score is not evidence the model sees disease. Colour can be genuine signal (stained
parasites, for example), so read the baseline per dataset.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from sklearn.metrics import confusion_matrix, roc_auc_score
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T

from app.gradcam import grad_cam
from app.models.resnet import IMAGENET_MEAN, IMAGENET_STD, build_resnet18
from app.registry import default_model_dir

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Task:
    model_id: str
    weights_file: str
    meta_file: str
    labels: list[str]
    data_dir: Path
    dataset: str                     # provenance and licence, stored with the model
    caveat: str
    version: str = "0.1.0"
    input_size: int = 224
    epochs: int = 12
    batch_size: int = 32
    lr: float = 1e-4
    hflip: bool = True
    vflip: bool = False              # true only where orientation carries no meaning (cells, tissue)
    rotation: float = 10
    jitter: float = 0.2
    grayscale: bool = False          # radiology: single channel replicated; colour imaging keeps RGB
    extra_meta: dict = field(default_factory=dict)


def load_index(task: Task) -> list[dict]:
    with open(task.data_dir / "index.csv") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["y"] = task.labels.index(r["label"])
    return rows


def split(rows, labels, val_fraction: float, test_fraction: float, seed: int):
    """Returns train, val, test, external. Uses the dataset's own split column where given,
    else holds out groups per stratum."""
    external = [r for r in rows if r.get("split") == "external"]
    rows = [r for r in rows if r.get("split") != "external"]
    if rows and rows[0].get("split"):
        parts = {"train": [], "val": [], "test": []}
        for r in rows:
            parts[r["split"]].append(r)
        return parts["train"], parts["val"], parts["test"], external
    # Each group belongs to one stratum: the first-listed label among its rows (list the
    # finding before normal, so e.g. an infected patient's normal cells stay with them).
    stratum: dict[str, int] = {}
    for r in rows:
        stratum[r["group"]] = min(stratum.get(r["group"], r["y"]), r["y"])
    rng = random.Random(seed)
    side: dict[str, str] = {}
    for y in range(len(labels)):
        groups = sorted(g for g, s in stratum.items() if s == y)
        rng.shuffle(groups)
        n_test = max(1, round(len(groups) * test_fraction))
        n_val = max(1, round(len(groups) * val_fraction))
        side.update({g: "test" for g in groups[:n_test]})
        side.update({g: "val" for g in groups[n_test:n_test + n_val]})
    parts = {"train": [], "val": [], "test": []}
    for r in rows:
        parts[side.get(r["group"], "train")].append(r)
    return parts["train"], parts["val"], parts["test"], external


class ImageRows(Dataset):
    def __init__(self, task: Task, rows, transform):
        self.task, self.rows, self.transform = task, rows, transform

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = Image.open(self.task.data_dir / r["file"])
        img = img.convert("L").convert("RGB") if self.task.grayscale else img.convert("RGB")
        return self.transform(img), r["y"]


def transforms(task: Task):
    norm = T.Normalize(IMAGENET_MEAN, IMAGENET_STD)
    size = (task.input_size, task.input_size)
    aug = [T.Resize(size)]
    if task.hflip:
        aug.append(T.RandomHorizontalFlip())
    if task.vflip:
        aug.append(T.RandomVerticalFlip())
    aug += [T.RandomAffine(degrees=task.rotation, translate=(0.05, 0.05), scale=(0.9, 1.1)),
            T.ColorJitter(brightness=task.jitter, contrast=task.jitter), T.ToTensor(), norm]
    return T.Compose(aug), T.Compose([T.Resize(size), T.ToTensor(), norm])


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


def metrics(p: np.ndarray, y: np.ndarray, labels: list[str]) -> dict:
    pred = p.argmax(axis=1)
    cm = confusion_matrix(y, pred, labels=list(range(len(labels))))
    per_class = {}
    for i, name in enumerate(labels):
        per_class[name] = {
            "n": int(cm[i].sum()),
            "sensitivity": round(float(cm[i, i] / max(1, cm[i].sum())), 4),
            "precision": round(float(cm[i, i] / max(1, cm[:, i].sum())), 4),
        }
    present = sorted(set(y.tolist()))
    if len(labels) == 2:
        auc = roc_auc_score(y, p[:, 1]) if len(present) == 2 else float("nan")
    else:
        auc = roc_auc_score(y, p, multi_class="ovr", average="macro", labels=list(range(len(labels)))) \
            if len(present) == len(labels) else float("nan")
    return {
        "n": int(len(y)),
        "accuracy": round(float((pred == y).mean()), 4),
        "balanced_accuracy": round(float(np.mean([per_class[labels[i]]["sensitivity"] for i in present])), 4),
        ("auc" if len(labels) == 2 else "macro_auc_ovr"): round(float(auc), 4),
        "ece": round(expected_calibration_error(p, y), 4),
        "per_class": per_class,
        "confusion": {"labels": labels, "rows_true_cols_predicted": cm.tolist()},
    }


def image_stats(path: Path) -> list[float]:
    """Features that say nothing about disease: size, colour mean/spread, file size."""
    im = Image.open(path)
    a = np.asarray(im.convert("RGB").resize((64, 64)), dtype=np.float32)
    return [im.size[0], im.size[1], *a.mean((0, 1)), *a.std((0, 1)), path.stat().st_size / 1e3]


def shortcut_baseline(task: Task, train_rows, test_rows) -> dict:
    """How well a trivial model on non-disease image statistics does on the same test set.

    If it comes close to the real model, the classes differ in how images were acquired
    (camera, crop, compression), and the real model's score is not evidence it sees disease.
    """
    from sklearn.linear_model import LogisticRegression

    def xy(rows):
        return (np.array([image_stats(task.data_dir / r["file"]) for r in rows]),
                np.array([r["y"] for r in rows]))

    x_tr, y_tr = xy(train_rows)
    x_te, y_te = xy(test_rows)
    mu, sd = x_tr.mean(0), x_tr.std(0) + 1e-9
    clf = LogisticRegression(max_iter=5000).fit((x_tr - mu) / sd, y_tr)
    p = np.zeros((len(y_te), len(task.labels)))
    p[:, clf.classes_] = clf.predict_proba((x_te - mu) / sd)
    m = metrics(p, y_te, task.labels)
    return {k: m[k] for k in ("accuracy", "balanced_accuracy", "auc", "macro_auc_ovr") if k in m}


def attention_on_lesion(model, task: Task, rows, tf_eval, device) -> dict:
    """Share of Grad-CAM mass on the expert lesion mask (vs. the mask's share of the image),
    and how often the heatmap's peak lies within 15 px of the lesion."""
    model.eval()
    inside, area, hits = {l: [] for l in task.labels}, {l: [] for l in task.labels}, {l: [] for l in task.labels}
    for r in rows:
        img = Image.open(task.data_dir / r["file"]).convert("RGB")
        mask_img = Image.open(task.data_dir / r["mask"]).convert("L").resize(img.size)
        x = tf_eval(img.convert("L").convert("RGB") if task.grayscale else img).unsqueeze(0).to(device)
        with torch.no_grad():
            pred = int(model(x).argmax(dim=1).item())
        cam = grad_cam(model, model.layer4, x, pred)
        cam = np.asarray(Image.fromarray((cam * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR),
                         dtype=np.float32) / 255
        mask = np.asarray(mask_img) > 0
        # Dilate the lesion by 15 px (a 31x31 max filter), via max-pooling: same result, far faster.
        near = F.max_pool2d(torch.from_numpy(mask.astype(np.float32))[None, None], 31, stride=1,
                            padding=15)[0, 0].numpy() > 0
        total = cam.sum()
        inside[r["label"]].append(float(cam[mask].sum() / total) if total > 0 else 0.0)
        area[r["label"]].append(float(mask.mean()))
        hits[r["label"]].append(bool(near.flat[int(cam.argmax())]))

    def summary(names):
        e = [v for n in names for v in inside[n]]
        if not e:
            return {"n": 0}
        return {"n": len(e), "energy_inside": round(float(np.mean(e)), 4),
                "mask_area": round(float(np.mean([v for n in names for v in area[n]])), 4),
                "pointing": round(float(np.mean([v for n in names for v in hits[n]])), 4)}

    return {"all": summary(task.labels), **{n: summary([n]) for n in task.labels}}


def run(task: Task, argv=None) -> dict:
    ap = argparse.ArgumentParser(description=f"Train {task.model_id}")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=task.epochs)
    ap.add_argument("--val-fraction", type=float, default=0.15)
    ap.add_argument("--test-fraction", type=float, default=0.15)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0, help="use only N images per class per split (smoke test)")
    args = ap.parse_args(argv)

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    out_dir = args.out or default_model_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    train_rows, val_rows, test_rows, external_rows = split(load_index(task), task.labels, args.val_fraction,
                                                           args.test_fraction, args.seed)
    if args.limit:
        def cap(rows):
            return [r for y in range(len(task.labels)) for r in [r for r in rows if r["y"] == y][: args.limit]]
        train_rows, val_rows, test_rows, external_rows = map(cap, (train_rows, val_rows, test_rows, external_rows))

    sides = [{r["group"] for r in rows} for rows in (train_rows, val_rows, test_rows)]
    assert not (sides[0] & sides[1] or sides[0] & sides[2] or sides[1] & sides[2]), "a group is on two sides"
    counts = [sum(r["y"] == y for r in train_rows) for y in range(len(task.labels))]
    print(f"{task.model_id}: device={device} groups train/val/test={[len(s) for s in sides]} "
          f"images train={len(train_rows)} {counts} val={len(val_rows)} test={len(test_rows)}", flush=True)

    tf_train, tf_eval = transforms(task)
    dl = lambda rows, tf, shuffle: DataLoader(  # noqa: E731
        ImageRows(task, rows, tf), batch_size=task.batch_size, shuffle=shuffle,
        num_workers=args.workers, persistent_workers=args.workers > 0)
    train_dl, val_dl, test_dl = dl(train_rows, tf_train, True), dl(val_rows, tf_eval, False), dl(test_rows, tf_eval, False)

    model = build_resnet18(len(task.labels), pretrained=True).to(device)
    weights = torch.tensor([sum(counts) / (len(task.labels) * max(1, c)) for c in counts],
                           dtype=torch.float32, device=device)
    loss_fn = nn.CrossEntropyLoss(weight=weights)             # classes are rarely balanced
    opt = torch.optim.AdamW(model.parameters(), lr=task.lr, weight_decay=1e-4)
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
        val = metrics(*predict_all(model, val_dl, device), task.labels)
        print(f"epoch {epoch}/{args.epochs} loss={total / len(train_rows):.4f} "
              f"val_bal_acc={val['balanced_accuracy']} ({time.time() - t0:.0f}s)", flush=True)
        if val["balanced_accuracy"] > best:
            best, best_val = val["balanced_accuracy"], val
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    test = metrics(*predict_all(model, test_dl, device), task.labels)
    if test_rows and test_rows[0].get("mask"):
        test["attention_on_lesion"] = attention_on_lesion(model, task, test_rows, tf_eval, device)
    test["shortcut_baseline"] = shortcut_baseline(task, train_rows, test_rows)
    print("TEST (best-val checkpoint):", json.dumps(test, indent=2), flush=True)
    external = None
    if external_rows:
        external = metrics(*predict_all(model, dl(external_rows, tf_eval, False), device), task.labels)
        print("EXTERNAL TEST:", json.dumps(external, indent=2), flush=True)

    torch.save(best_state, out_dir / task.weights_file)
    (out_dir / task.meta_file).write_text(json.dumps({
        "model_id": task.model_id,
        "version": task.version,
        "architecture": "resnet18",
        "labels": task.labels,
        "input_size": task.input_size,
        "mean": IMAGENET_MEAN,
        "std": IMAGENET_STD,
        "metrics": {
            "validation": best_val,
            "test": test,
            **({"external_test": external} if external else {}),
            "split": {"seed": args.seed, "groups_train_val_test": [len(s) for s in sides],
                      "images_train_val_test": [len(train_rows), len(val_rows), len(test_rows)],
                      **({"images_external": len(external_rows)} if external_rows else {})},
            "dataset": task.dataset,
            "caveat": task.caveat,
            **task.extra_meta,
        },
    }, indent=2))
    print(f"saved to {out_dir}", flush=True)
    return test
