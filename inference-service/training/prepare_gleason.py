"""Index SICAPv2 prostate biopsy patches for the Gleason pattern classifier.

    cd inference-service
    python -m training.prepare_gleason

SICAPv2 (Silva-Rodriguez et al. 2020; CC BY 4.0; Mendeley Data 9xxm58dvs3): 512x512 px
patches at 10x from 155 H&E prostate biopsies of 95 patients, Hospital Clinico de
Valencia, each labelled non-cancerous or Gleason pattern 3, 4 (incl. cribriform) or 5.
Unzip SICAPv2.zip into <repo>/dataset/sicapv2/.

Uses the dataset's own patient-level test partition (partition/Test) as the test set;
the rest is split by patient into train and validation here.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "sicapv2"
ROOT = DATA / "SICAPv2"
LABELS = ["GLEASON_5", "GLEASON_4", "GLEASON_3", "BENIGN_PROSTATE"]   # most severe first (strata)


def read_sheet(path: Path) -> list[dict]:
    rows = list(openpyxl.load_workbook(path, read_only=True).worksheets[0].iter_rows(values_only=True))
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:] if r and r[0]]


def label(r: dict) -> str:
    if r.get("G5"):
        return "GLEASON_5"
    if r.get("G4") or r.get("G4C"):
        return "GLEASON_4"
    if r.get("G3"):
        return "GLEASON_3"
    return "BENIGN_PROSTATE"


def main():
    patients = {str(r["slide_id"]).strip(): str(r["patient_id"]).strip()
                for r in read_sheet(ROOT / "wsi_labels.xlsx")}

    def slide(image_name: str) -> str:
        return image_name.split("_Block")[0]

    rows = []
    for split, sheet in (("", "Train.xlsx"), ("test", "Test.xlsx")):
        for r in read_sheet(ROOT / "partition" / "Test" / sheet):
            name = str(r["image_name"]).strip()
            s = slide(name)
            rows.append({"file": f"SICAPv2/images/{name}", "label": label(r),
                         "group": patients.get(s, s), "split": split})
    missing = [r["file"] for r in rows if not (DATA / r["file"]).exists()]
    assert not missing, missing[:3]
    # Validation comes from the training patients; mark train rows for the group splitter.
    train_patients = sorted({r["group"] for r in rows if not r["split"]})
    test_patients = {r["group"] for r in rows if r["split"] == "test"}
    assert not set(train_patients) & test_patients, "patient in both official partitions"
    # Stratify the validation draw by whether a patient has benign patches, so validation
    # (used to pick the checkpoint) sees every class.
    import random
    rng = random.Random(42)
    has_benign = {r["group"] for r in rows if not r["split"] and r["label"] == "BENIGN_PROSTATE"}
    val = set()
    for stratum in (sorted(set(train_patients) & has_benign), sorted(set(train_patients) - has_benign)):
        rng.shuffle(stratum)
        val.update(stratum[: max(1, round(len(stratum) / 7))])
    for r in rows:
        if not r["split"]:
            r["split"] = "val" if r["group"] in val else "train"
    with open(DATA / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "label", "group", "split"])
        w.writeheader()
        w.writerows(rows)
    for s in ("train", "val", "test"):
        part = [r for r in rows if r["split"] == s]
        print(f"{s}: {len({r['group'] for r in part})} patients, {len(part)} patches, "
              f"{dict(Counter(r['label'] for r in part))}")


if __name__ == "__main__":
    main()
