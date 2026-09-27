"""Prepare the two ophthalmology datasets.

    cd inference-service
    python -m training.prepare_ophthalmology

Diabetic retinopathy: DeepDRiD regular fundus images (Liu et al. 2022, CC BY-SA 4.0):
2,000 full-resolution colour fundus photos of 500 patients (two views per eye), graded
0-4 on the international DR scale. Clone github.com/deepdrdoc/DeepDRiD into
<repo>/dataset/deepdrid/ (only regular_fundus_images/ is needed). Each photo is cropped
to the retina and stored at 768 px; the challenge's evaluation patients are the test set.

Glaucoma: ACRIMA (Diaz-Pinto et al. 2019, CC BY 4.0): 705 optic-disc-centred crops,
396 glaucomatous and 309 normal, from FISABIO, Valencia. Unzip Database.zip from
figshare article 7613135 into <repo>/dataset/glaucoma_acrima/. No patient ids are
published, so near-duplicate images are grouped (training/dedupe.py) before splitting.
"""
from __future__ import annotations

import csv
import random
import re
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from app.models.resnet import crop_fundus

from .dedupe import near_duplicate_groups

REPO_ROOT = Path(__file__).resolve().parents[2]
DR_LABELS = ["DR_NONE", "DR_MILD", "DR_MODERATE", "DR_SEVERE", "DR_PROLIFERATIVE"]


def write_index(path: Path, rows: list[dict], fields: list[str]):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def xlsx_rows(path: Path) -> list[list[str]]:
    """First sheet of a simple .xlsx as rows of strings (no spreadsheet library needed)."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        shared = [re.sub("<[^>]+>", "", m) for m in re.findall(r"<si>(.*?)</si>", z.read("xl/sharedStrings.xml").decode())]
    rows = []
    for row in re.findall(r"<row[^>]*>(.*?)</row>", z.read("xl/worksheets/sheet1.xml").decode()):
        rows.append([shared[int(v)] if 't="s"' in attrs else v
                     for attrs, v in re.findall(r"<c([^>]*)>(?:<f>.*?</f>)?<v>(.*?)</v></c>", row)])
    return rows


def retinopathy(val_fraction: float = 0.15, seed: int = 42, size: int = 768):
    src = REPO_ROOT / "dataset" / "deepdrid" / "regular_fundus_images"
    data = REPO_ROOT / "dataset" / "retina_dr_full"
    (data / "images").mkdir(parents=True, exist_ok=True)
    images = []                                   # (image id, patient id, grade, source split)
    for split in ("training", "validation"):
        for r in csv.DictReader(open(src / f"regular-fundus-{split}" / f"regular-fundus-{split}.csv")):
            grade = r["left_eye_DR_Level"] or r["right_eye_DR_Level"]
            images.append((r["image_id"], r["patient_id"], int(grade), f"regular-fundus-{split}"))
    for image_id, grade in xlsx_rows(src / "Online-Challenge1&2-Evaluation" / "Challenge1_labels.xlsx")[1:]:
        images.append((image_id, image_id.split("_")[0], int(float(grade)), "Online-Challenge1&2-Evaluation"))

    # Test: the challenge's own evaluation patients. Validation: patients of the training
    # pool, stratified by their worst eye, so no patient is on two sides.
    test_patients = {pid for _, pid, _, folder in images if folder.startswith("Online")}
    worst: dict[str, int] = {}
    for _, pid, grade, _ in images:
        if pid not in test_patients:
            worst[pid] = max(worst.get(pid, 0), grade)
    rng = random.Random(seed)
    val_patients = set()
    for g in range(len(DR_LABELS)):
        pids = sorted(p for p, w in worst.items() if w == g)
        rng.shuffle(pids)
        val_patients.update(pids[:round(len(pids) * val_fraction)])

    rows = []
    for image_id, pid, grade, folder in images:
        name = f"images/{image_id}.jpg"
        if not (data / name).exists():
            img = crop_fundus(Image.open(src / folder / "Images" / pid / f"{image_id}.jpg").convert("RGB"))
            img.resize((size, size), Image.LANCZOS).save(data / name, quality=95)
        split = "test" if pid in test_patients else "val" if pid in val_patients else "train"
        rows.append({"file": name, "label": DR_LABELS[grade], "group": f"patient_{pid}", "split": split})
    write_index(data / "index.csv", rows, ["file", "label", "group", "split"])
    for split in ("train", "val", "test"):
        part = [r for r in rows if r["split"] == split]
        by = {l: sum(r["label"] == l for r in part) for l in DR_LABELS}
        print(f"retinopathy {split}: {len(part)} images, {len({r['group'] for r in part})} patients {by}")


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
