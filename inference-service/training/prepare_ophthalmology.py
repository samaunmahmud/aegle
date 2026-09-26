"""Prepare the two ophthalmology datasets.

    cd inference-service
    python -m training.prepare_ophthalmology

Diabetic retinopathy: RetinaMNIST at 224 px (MedMNIST+, CC BY 4.0), derived from
DeepDRiD (Liu et al. 2022): 1,600 colour fundus photos graded 0-4 on the international
DR scale, with the source's own train/val/test split. Put retinamnist_224.npz from
zenodo.org/records/10519652 in <repo>/dataset/retina_dr/.

Glaucoma: ACRIMA (Diaz-Pinto et al. 2019, CC BY 4.0): 705 optic-disc-centred crops,
396 glaucomatous and 309 normal, from FISABIO, Valencia. Unzip Database.zip from
figshare article 7613135 into <repo>/dataset/glaucoma_acrima/. No patient ids are
published, so near-duplicate images are grouped (training/dedupe.py) before splitting.
"""
from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from PIL import Image

from .dedupe import near_duplicate_groups

REPO_ROOT = Path(__file__).resolve().parents[2]
DR_LABELS = ["DR_NONE", "DR_MILD", "DR_MODERATE", "DR_SEVERE", "DR_PROLIFERATIVE"]


def write_index(path: Path, rows: list[dict], fields: list[str]):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def retinopathy():
    data = REPO_ROOT / "dataset" / "retina_dr"
    npz = np.load(data / "retinamnist_224.npz")
    (data / "images").mkdir(exist_ok=True)
    rows = []
    for split in ("train", "val", "test"):
        for i, (img, label) in enumerate(zip(npz[f"{split}_images"], npz[f"{split}_labels"])):
            name = f"images/{split}_{i:04d}.png"
            Image.fromarray(img).save(data / name)
            rows.append({"file": name, "label": DR_LABELS[int(np.ravel(label)[0])],
                         "group": f"{split}_{i}", "split": split})
    write_index(data / "index.csv", rows, ["file", "label", "group", "split"])
    by = {l: sum(r["label"] == l for r in rows) for l in DR_LABELS}
    print(f"retinopathy: {len(rows)} images {by}")


def glaucoma():
    data = REPO_ROOT / "dataset" / "glaucoma_acrima"
    paths = sorted(p for p in (data / "Database" / "Images").iterdir() if p.suffix.lower() == ".jpg")
    groups = near_duplicate_groups(paths)
    rows = [{"file": str(p.relative_to(data)),
             "label": "GLAUCOMA_SUSPECT" if "_g_" in p.name else "NORMAL_DISC",
             "group": f"g{g}"} for p, g in zip(paths, groups)]
    write_index(data / "index.csv", rows, ["file", "label", "group"])
    sizes = np.bincount(np.unique(groups, return_inverse=True)[1])
    mixed = sum(len({r["label"] for r in rows if r["group"] == g}) > 1 for g in {r["group"] for r in rows})
    print(f"glaucoma: {len(rows)} images, {len(sizes)} near-duplicate groups "
          f"(largest {sizes.max()}), {mixed} groups mixing labels")


if __name__ == "__main__":
    retinopathy()
    glaucoma()
