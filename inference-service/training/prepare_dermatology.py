"""Index HAM10000 and the ISIC 2018 test set for the skin lesion classifier.

    cd inference-service
    python -m training.prepare_dermatology

HAM10000 (Tschandl et al. 2018; CC BY-NC 4.0, non-commercial use only): 10,015
dermoscopy images of 7,470 lesions from Vienna and Queensland, with lesion outlines.
Download from Harvard Dataverse doi:10.7910/DVN/DBW86T into <repo>/dataset/ham10000/:
the two image zips (unzipped in place), HAM10000_metadata.tab as metadata.tab, the
Tschandl segmentations, and the ISIC 2018 Task 3 test images and ground truth.

Groups are lesions: several photos of one lesion stay together. The ISIC 2018 test
set (1,512 images, different lesions) is marked "external".
"""
from __future__ import annotations

import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "ham10000"
DX = {
    "mel": "MELANOMA",
    "bcc": "BASAL_CELL_CARCINOMA",
    "akiec": "ACTINIC_KERATOSIS",           # includes intraepithelial carcinoma (Bowen's)
    "bkl": "BENIGN_KERATOSIS",
    "df": "DERMATOFIBROMA",
    "nv": "MELANOCYTIC_NEVUS",
    "vasc": "VASCULAR_LESION",
}
LABELS = list(DX.values())


def read_tab(path: Path) -> list[dict]:
    with open(path) as f:
        return [{k: v.strip('"') for k, v in r.items()} for r in csv.DictReader(f, delimiter="\t")]


def main():
    rows = []
    for r in read_tab(DATA / "metadata.tab"):
        rows.append({"file": f"{r['image_id']}.jpg",
                     "mask": f"HAM10000_segmentations_lesion_tschandl/{r['image_id']}_segmentation.png",
                     "label": DX[r["dx"]], "group": r["lesion_id"], "split": ""})
    for r in read_tab(DATA / "isic2018_test_gt.tab"):
        rows.append({"file": f"ISIC2018_Task3_Test_Images/{r['image_id']}.jpg", "mask": "",
                     "label": DX[r["dx"]], "group": r["lesion_id"], "split": "external"})
    missing = [r for r in rows if not (DATA / r["file"]).exists()]
    assert not [r for r in missing if r["split"] != "external"], "HAM10000 images missing"
    if missing:   # the published ISIC 2018 test archive lacks ISIC_0035068
        print(f"skipping {len(missing)} external image(s) absent from the archive: {[r['file'] for r in missing]}")
        rows = [r for r in rows if r not in missing]
    with open(DATA / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "mask", "label", "group", "split"])
        w.writeheader()
        w.writerows(rows)
    internal = [r for r in rows if not r["split"]]
    print(f"{len(internal)} HAM10000 images ({len({r['group'] for r in internal})} lesions), "
          f"{len(rows) - len(internal)} external ISIC 2018 test images")


if __name__ == "__main__":
    main()
