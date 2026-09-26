"""Index the NIH malaria cell images (Rajaraman et al. 2018; NLM, public domain).

    cd inference-service
    python -m training.prepare_malaria

Expects <repo>/dataset/malaria_nih/cell_images/{Parasitized,Uninfected}/*.png (unzip
cell_images.zip from https://data.lhncbc.nlm.nih.gov/public/Malaria/). Each file name
starts with the patient code (e.g. C100P61, C51AP12), used to keep patients on one
side of the split. 150 infected patients contribute both labels; 50 healthy patients
contribute only uninfected cells.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "malaria_nih"
LABELS = {"Parasitized": "PARASITIZED", "Uninfected": "UNINFECTED"}
PATIENT = re.compile(r"(C\d+[A-Z]?P\d+|C\d+)")


def main():
    rows = []
    for folder, label in LABELS.items():
        for p in sorted((DATA / "cell_images" / folder).glob("*.png")):
            rows.append({"file": f"cell_images/{folder}/{p.name}", "label": label,
                         "group": PATIENT.match(p.name).group(1)})
    with open(DATA / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "label", "group"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} cells, {len({r['group'] for r in rows})} patients")


if __name__ == "__main__":
    main()
