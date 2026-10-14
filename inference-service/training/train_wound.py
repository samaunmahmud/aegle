"""Train the wound segmentation model on the Foot Ulcer Segmentation Challenge data.

    cd inference-service
    python -m training.train_wound            # add --limit 40 --epochs 1 for a smoke test

Data: FUSeg 2021 (Wang et al., MICCAI challenge; published for research, no explicit
licence), about 1,000 de-identified photos of diabetic foot ulcers with expert wound masks,
AZH Wound and Vascular Center, Milwaukee. Put the repository's
"data/Foot Ulcer Segmentation Challenge" folder at <repo>/dataset/fuseg/challenge/.

The challenge's own validation set (200 images) is the held-out test here; its test masks
are not public. Training images are split into train/validation after grouping near-duplicate
photos (patients were photographed at several visits and no patient ids are given).
Seven validation photos are pixel-identical to training photos (annotated twice); those
training copies are dropped so the test set is unseen.
Reported: Dice and IoU against the expert outline, and the error of the measured area,
which is what a clinician would follow over visits.

v0.2 over v0.1: the photos at their full 512 px instead of shrunk to 256, so the thin edges
of small ulcers stay visible; and no test photos in training.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.nn import functional as F
from torch.utils.data import DataLoader, Dataset

from app.models.resnet import IMAGENET_MEAN, IMAGENET_STD
from app.models.unet import UNetResNet18
from app.models.wound import META_FILE, MODEL_ID, WEIGHTS_FILE
from app.registry import default_model_dir

from .dedupe import dhash, near_duplicate_groups

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "fuseg" / "challenge"
SIZE, VERSION = 512, "0.2.0"
MEAN = np.array(IMAGENET_MEAN, dtype=np.float32)
STD = np.array(IMAGENET_STD, dtype=np.float32)


def pairs(split: str) -> list[tuple[Path, Path]]:
    images = sorted((DATA / split / "images").glob("*.png"))
    return [(p, DATA / split / "labels" / p.name) for p in images if (DATA / split / "labels" / p.name).exists()]


class WoundDataset(Dataset):
    def __init__(self, items, augment: bool):
        self.items, self.augment = items, augment

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        img_path, mask_path = self.items[i]
        img = Image.open(img_path).convert("RGB").resize((SIZE, SIZE), Image.BILINEAR)
        mask = Image.open(mask_path).convert("L").resize((SIZE, SIZE), Image.NEAREST)
        x = np.asarray(img, dtype=np.float32) / 255.0
        m = (np.asarray(mask) > 127).astype(np.float32)
        if self.augment:
            if random.random() < 0.5:
                x, m = x[:, ::-1], m[:, ::-1]
            if random.random() < 0.5:
                x, m = x[::-1], m[::-1]
            k = random.randint(0, 3)
            x, m = np.rot90(x, k), np.rot90(m, k)
            x = np.clip(x * random.uniform(0.8, 1.2) + random.uniform(-0.08, 0.08), 0, 1)
        x = (x - MEAN) / STD
        return torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1))), torch.from_numpy(np.ascontiguousarray(m))[None]


def dice_loss(logits, target):
    p = torch.sigmoid(logits)
    inter = (p * target).sum(dim=(1, 2, 3))
    return 1 - ((2 * inter + 1) / (p.sum(dim=(1, 2, 3)) + target.sum(dim=(1, 2, 3)) + 1)).mean()


@torch.no_grad()
def evaluate(model, items, device) -> dict:
    """Per image at full resolution, as served: Dice, IoU and area error."""
    model.eval()
    dice, iou, area_err, empty_ok = [], [], [], []
    for img_path, mask_path in items:
        img = Image.open(img_path).convert("RGB")
        truth = np.asarray(Image.open(mask_path).convert("L")) > 127
        x = (np.asarray(img.resize((SIZE, SIZE), Image.BILINEAR), dtype=np.float32) / 255.0 - MEAN) / STD
        p = torch.sigmoid(model(torch.from_numpy(x.transpose(2, 0, 1)).unsqueeze(0).to(device)))[0, 0].cpu().numpy()
        pred = np.asarray(Image.fromarray((p * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR)) >= 128
        if truth.sum() == 0:
            empty_ok.append(pred.sum() == 0)
            continue
        inter = (pred & truth).sum()
        dice.append(2 * inter / (pred.sum() + truth.sum()))
        iou.append(inter / (pred | truth).sum())
        area_err.append(abs(int(pred.sum()) - int(truth.sum())) / truth.sum())
    return {
        "n": len(items),
        "dice": round(float(np.mean(dice)), 4),
        "iou": round(float(np.mean(iou)), 4),
        "median_area_error": round(float(np.median(area_err)), 4),
        "area_within_20pct": round(float(np.mean(np.array(area_err) <= 0.2)), 4),
        **({"empty_images_correct": round(float(np.mean(empty_ok)), 4)} if empty_ok else {}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    out_dir = args.out or default_model_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    train_all, test = pairs("train"), pairs("validation")
    test_hashes = np.stack([dhash(p) for p, _ in test])
    in_test = [bool(((test_hashes != dhash(p)).sum(axis=1) <= 20).any()) for p, _ in train_all]
    train_all = [it for it, dup in zip(train_all, in_test) if not dup]
    groups = near_duplicate_groups([p for p, _ in train_all])
    distinct = sorted(set(groups))
    random.Random(args.seed).shuffle(distinct)
    val_groups = set(distinct[: max(1, len(distinct) // 10)])
    train = [it for it, g in zip(train_all, groups) if g not in val_groups]
    val = [it for it, g in zip(train_all, groups) if g in val_groups]
    if args.limit:
        train, val, test = train[: args.limit], val[: args.limit // 4 + 1], test[: args.limit // 4 + 1]
    print(f"{MODEL_ID}: device={device} images train={len(train)} val={len(val)} test={len(test)} "
          f"({len(distinct)} near-duplicate groups in training data; {sum(in_test)} training photos "
          f"dropped as duplicates of test photos)", flush=True)

    loader = DataLoader(WoundDataset(train, True), batch_size=8, shuffle=True, num_workers=4, persistent_workers=True)
    model = UNetResNet18(pretrained=True).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)

    best, best_state, best_val = -1.0, None, None
    for epoch in range(1, args.epochs + 1):
        model.train()
        t0, total = time.time(), 0.0
        for x, m in loader:
            x, m = x.to(device), m.to(device)
            opt.zero_grad()
            logits = model(x)
            loss = F.binary_cross_entropy_with_logits(logits, m) + dice_loss(logits, m)
            loss.backward()
            opt.step()
            total += loss.item() * len(x)
        sched.step()
        if epoch % 2 == 0 or epoch == args.epochs:
            val_m = evaluate(model, val, device)
            print(f"epoch {epoch}/{args.epochs} loss={total / len(train):.4f} val_dice={val_m['dice']} "
                  f"({time.time() - t0:.0f}s)", flush=True)
            if val_m["dice"] > best:
                best, best_val = val_m["dice"], val_m
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    model.load_state_dict(best_state)
    test_m = evaluate(model, test, device)
    print("TEST (FUSeg validation set, held out):", json.dumps(test_m, indent=2), flush=True)

    torch.save(best_state, out_dir / WEIGHTS_FILE)
    (out_dir / META_FILE).write_text(json.dumps({
        "model_id": MODEL_ID, "version": VERSION, "architecture": "unet-resnet18", "input_size": SIZE,
        "metrics": {
            "validation": best_val,
            "test": test_m,
            "split": {"seed": args.seed, "images_train_val_test": [len(train), len(val), len(test)],
                      "train_dropped_as_test_duplicates": sum(in_test)},
            "dataset": "Foot Ulcer Segmentation Challenge 2021 (Wang et al.; published for research, no explicit "
                       "licence): diabetic foot ulcer photos with expert masks, AZH Wound and Vascular Center, USA",
            "caveat": "Research use only (licence unclear). Area is in pixels and depends on camera distance; "
                      "no patient ids are given, so other visits of test patients may be in training; assumes a wound is present (outlines a "
                      "small false area on most wound-free photos); do not use for clinical decisions.",
        },
    }, indent=2))
    print(f"saved to {out_dir}", flush=True)


if __name__ == "__main__":
    main()
