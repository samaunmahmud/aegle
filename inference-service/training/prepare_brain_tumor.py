"""Convert the Figshare brain tumour dataset (Cheng et al., CC BY 4.0) into PNGs.

    cd inference-service
    python -m training.prepare_brain_tumor

Reads <repo>/dataset/brain_tumor_figshare/raw/mat/*.mat (unzip the four
brainTumorDataPublic_*.zip files there) and writes images/<n>.png, the expert tumour
outline as masks/<n>.png (used to check where the model looks), and index.csv
(file, mask, label, patient) next to raw/. Intensities are scaled exactly as the service
scales a DICOM without window settings (app.imaging._to_uint8), so the model sees
the same kind of input in training and in use.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import h5py
import numpy as np
from PIL import Image

from app.imaging import _to_uint8

LABELS = {1: "MENINGIOMA", 2: "GLIOMA", 3: "PITUITARY"}
REPO_ROOT = Path(__file__).resolve().parents[2]


def read_mat(path: Path) -> tuple[np.ndarray, np.ndarray, str, str]:
    with h5py.File(path, "r") as f:
        cj = f["cjdata"]
        image = np.array(cj["image"]).T            # MATLAB is column-major
        mask = np.array(cj["tumorMask"]).T.astype(bool)
        label = LABELS[int(np.array(cj["label"]).item())]
        pid = "".join(chr(c) for c in np.array(cj["PID"]).flatten())   # stored as char codes
    return image, mask, label, pid.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=REPO_ROOT / "dataset" / "brain_tumor_figshare")
    args = ap.parse_args()

    mats = sorted((args.data / "raw" / "mat").glob("*.mat"), key=lambda p: int(p.stem))
    (args.data / "images").mkdir(parents=True, exist_ok=True)
    (args.data / "masks").mkdir(parents=True, exist_ok=True)
    rows = []
    for p in mats:
        image, mask, label, pid = read_mat(p)
        Image.fromarray(_to_uint8(image, None, None)).save(args.data / "images" / f"{p.stem}.png")
        Image.fromarray(mask.astype(np.uint8) * 255).save(args.data / "masks" / f"{p.stem}.png")
        rows.append({"file": f"images/{p.stem}.png", "mask": f"masks/{p.stem}.png", "label": label, "patient": pid})
    with open(args.data / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "mask", "label", "patient"])
        w.writeheader()
        w.writerows(rows)
    by_label = {l: sum(r["label"] == l for r in rows) for l in LABELS.values()}
    print(f"{len(rows)} images, {len({r['patient'] for r in rows})} patients, {by_label}")


if __name__ == "__main__":
    main()
