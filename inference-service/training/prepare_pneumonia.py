"""Index the Kaggle "Chest X-Ray Images (Pneumonia)" dataset for training/common.py.

    cd inference-service
    python -m training.prepare_pneumonia

Reads <repo>/dataset/chest_xray/{train,val,test}/{NORMAL,PNEUMONIA} and writes index.csv
there (file, label, group, split). Kaggle's test folder stays the test set, so results
compare with v0.1 and with published work; train and Kaggle's 16-image val folder are
pooled and split by patient into train and validation.

Kaggle's split is not by patient. Pneumonia files share one numbering across bacterial
and viral images (person1_bacteria_1, person1_virus_11), and 170 of those children
appear in both train and test. Every such child is dropped from training, so the test
set holds only children the model never saw. Normal files come from two series
(IM-0117, NORMAL2-IM-0117) whose numbers collide but whose images are no more alike
than random pairs: the series prefix is part of the id.
"""
from __future__ import annotations

import argparse
import csv
import random
import re
from pathlib import Path

LABELS = ["NORMAL", "PNEUMONIA"]
REPO_ROOT = Path(__file__).resolve().parents[2]


def patient_key(path: Path) -> str:
    m = re.match(r"person(\d+)_", path.name)               # PNEUMONIA: person23_bacteria_...
    if m:
        return f"P{m.group(1)}"
    m = re.match(r"(NORMAL2-)?IM-(\d+)", path.name)         # NORMAL: IM-0115-0001, NORMAL2-IM-0385-0001
    if m:
        return f"N{'2' if m.group(1) else '1'}-{m.group(2)}"
    return path.stem                                        # unknown pattern: its own patient


def scan(data: Path, folders: list[str]) -> list[dict]:
    return [{"file": str(p.relative_to(data)), "label": label, "group": patient_key(p)}
            for folder in folders for label in LABELS
            for p in sorted((data / folder / label).glob("*.jp*g"))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=REPO_ROOT / "dataset" / "chest_xray")
    ap.add_argument("--val-fraction", type=float, default=0.15)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    test = [{**r, "split": "test"} for r in scan(args.data, ["test"])]
    test_groups = {r["group"] for r in test}
    pool = scan(args.data, ["train", "val"])
    dropped = [r for r in pool if r["group"] in test_groups]
    pool = [r for r in pool if r["group"] not in test_groups]

    rng = random.Random(args.seed)
    val_groups = set()
    for label in LABELS:
        groups = sorted({r["group"] for r in pool if r["label"] == label})
        rng.shuffle(groups)
        val_groups |= set(groups[: max(1, round(len(groups) * args.val_fraction))])
    rows = [{**r, "split": "val" if r["group"] in val_groups else "train"} for r in pool] + test

    with open(args.data / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "label", "group", "split"])
        w.writeheader()
        w.writerows(rows)
    for s in ("train", "val", "test"):
        part = [r for r in rows if r["split"] == s]
        print(f"{s}: {len(part)} images, {len({r['group'] for r in part})} patients, "
              f"{ {l: sum(r['label'] == l for r in part) for l in LABELS} }")
    print(f"dropped from training: {len(dropped)} images of {len({r['group'] for r in dropped})} "
          f"children who are also in the test set")


if __name__ == "__main__":
    main()
