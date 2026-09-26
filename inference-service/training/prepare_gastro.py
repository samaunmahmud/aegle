"""Index HyperKvasir lower-GI frames for the colonoscopy classifier.

    cd inference-service
    python -m training.prepare_gastro

HyperKvasir (Borgli et al. 2020; CC BY 4.0), labelled images, from Baerum Hospital,
Norway. Unzip hyper-kvasir-labeled-images.zip into <repo>/dataset/hyperkvasir/.

No patient or procedure ids are published and frames from one procedure look alike,
so near-duplicate frames are grouped (training/dedupe.py) before splitting.
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from .dedupe import near_duplicate_groups

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "dataset" / "hyperkvasir"
LOWER = "labeled-images/lower-gi-tract"
CLASSES = {
    "POLYP": ["pathological-findings/polyps"],
    "ULCERATIVE_COLITIS": [f"pathological-findings/ulcerative-colitis-grade-{g}"
                           for g in ("0-1", "1", "1-2", "2", "2-3", "3")],
    "NORMAL_MUCOSA": ["anatomical-landmarks/cecum", "anatomical-landmarks/ileum",
                      "anatomical-landmarks/retroflex-rectum", "quality-of-mucosal-views/bbps-2-3"],
    "INADEQUATE_VIEW": ["quality-of-mucosal-views/bbps-0-1", "quality-of-mucosal-views/impacted-stool"],
}
LABELS = list(CLASSES)


def main():
    files, labels = [], []
    for label, folders in CLASSES.items():
        for folder in folders:
            for p in sorted((DATA / LOWER / folder).glob("*.jpg")):
                files.append(p)
                labels.append(label)
    groups = near_duplicate_groups(files)
    rows = [{"file": str(p.relative_to(DATA)), "label": l, "group": f"g{g}"}
            for p, l, g in zip(files, labels, groups)]
    with open(DATA / "index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "label", "group"])
        w.writeheader()
        w.writerows(rows)
    sizes = Counter(groups)
    print(f"{len(rows)} frames {dict(Counter(labels))}; {len(sizes)} near-duplicate groups, "
          f"{sum(1 for s in sizes.values() if s > 1)} with more than one frame (largest {max(sizes.values())})")


if __name__ == "__main__":
    main()
