"""Index the Kather colorectal H&E tile datasets for the tissue classifier.

    cd inference-service
    python -m training.prepare_tissue

NCT-CRC-HE-100K (training) and CRC-VAL-HE-7K (test), Kather et al. 2019, CC BY 4.0,
zenodo.org/records/1214456: 224x224 px tiles at 0.5 um/px, Macenko-normalised, from
86 and 50 patients respectively (NCT Biobank / UMM pathology archive, Germany). Unzip
both into <repo>/dataset/crc_tissue/.

The 100K set has no slide ids, so its train/validation split is by tile and only used
to pick a checkpoint. The reported test is CRC-VAL-HE-7K: different patients.
Training uses up to 2,500 tiles per class to keep training time reasonable.
"""
from __future__ import annotations

import csv
import random
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "crc_tissue"
CLASSES = {
    "TUM": "TUMOUR_EPITHELIUM",
    "STR": "CANCER_STROMA",
    "NORM": "NORMAL_COLON_MUCOSA",
    "LYM": "LYMPHOCYTES",
    "MUC": "MUCUS",
    "MUS": "SMOOTH_MUSCLE",
    "DEB": "DEBRIS_NECROSIS",
    "ADI": "ADIPOSE",
    "BACK": "BACKGROUND",
}
LABELS = list(CLASSES.values())
PER_CLASS = 2500


def main():
    rng = random.Random(42)
    rows = []
    for code, label in CLASSES.items():
        tiles = sorted((DATA / "NCT-CRC-HE-100K" / code).glob("*.tif"))
        rng.shuffle(tiles)
        for i, p in enumerate(tiles[:PER_CLASS]):
            rows.append({"file": str(p.relative_to(DATA)), "label": label, "group": p.stem,
                         "split": "val" if i % 10 == 0 else "train"})
        for p in sorted((DATA / "CRC-VAL-HE-7K" / code).glob("*.tif")):
            rows.append({"file": str(p.relative_to(DATA)), "label": label, "group": f"val7k-{p.stem}",
                         "split": "test"})
    with open(DATA / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "label", "group", "split"])
        w.writeheader()
        w.writerows(rows)
    print({s: sum(1 for r in rows if r["split"] == s) for s in ("train", "val", "test")},
          dict(Counter(r["label"] for r in rows if r["split"] == "test")))


if __name__ == "__main__":
    main()
