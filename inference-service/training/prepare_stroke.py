"""Index the León baseline NCCT stroke-triage images.

    cd inference-service
    python -m training.prepare_stroke

Data: "A multi-class, image-level labeled dataset of baseline non-contrast head CT for
stroke triage" (Teruelo Diaz et al., Complejo Asistencial Universitario de León; Zenodo
21162781; CC BY 4.0): 7,965 axial slices from 99 patients. Unzip "NCCT Images.zip" into
<repo>/dataset/stroke_ncct/. Files are named <patient>_<slice>.jpg.

The spreadsheet's numeric codes are not documented. By visual review, 3 is no stroke
(every patient has such slices), 4 is haemorrhage (bright bleeds throughout), and 1 and 2
are ischaemic infarcts (1 mostly posterior-fossa, 2 hemispheric). Only the unambiguous
grouping is used: HAEMORRHAGE / ISCHAEMIC_STROKE / NO_STROKE. Slices coded with both a
haemorrhage and an infarct count as haemorrhage, which is what decides treatment.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import openpyxl

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "stroke_ncct"
LABELS = ["HAEMORRHAGE", "ISCHAEMIC_STROKE", "NO_STROKE"]


def label(code) -> str:
    parts = {p for p in str(code).split(".")}
    if "4" in parts:
        return "HAEMORRHAGE"
    if parts & {"1", "2"}:
        return "ISCHAEMIC_STROKE"
    if parts == {"3"}:
        return "NO_STROKE"
    raise ValueError(f"unexpected code {code!r}")


def main():
    sheet = openpyxl.load_workbook(DATA / "NCCT Images" / "CAULE-ANOM.xlsx", read_only=True).worksheets[0]
    rows = []
    for name, code in list(sheet.iter_rows(values_only=True))[1:]:
        if not name:
            continue
        rows.append({"file": f"NCCT Images/{name}.jpg", "label": label(code), "group": str(name).split("_")[0]})
    # The spreadsheet lists 000036_28..35 but the files are named 000037_28..35: which patient
    # they belong to is ambiguous, so those 8 slices are left out rather than risk a patient
    # appearing on both sides of the split. Anything else missing is an error.
    missing = [r for r in rows if not (DATA / r["file"]).exists()]
    assert all(r["file"].startswith("NCCT Images/000036_") for r in missing), [r["file"] for r in missing][:3]
    rows = [r for r in rows if r not in missing]
    print(f"left out {len(missing)} slices with an ambiguous patient")
    with open(DATA / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "label", "group"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} slices, {len({r['group'] for r in rows})} patients, {dict(Counter(r['label'] for r in rows))}")


if __name__ == "__main__":
    main()
