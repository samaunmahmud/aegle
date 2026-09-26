"""Group near-duplicate images, for datasets without patient ids.

Images whose 16x16 difference hashes are within `max_distance` bits are put in the same
group (union-find), so a split cannot put near-identical shots (same eye photographed
twice, consecutive video frames) on both sides. This reduces, but cannot rule out,
patient leakage: two different-looking images of one patient are still separable.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def dhash(path: Path, size: int = 16) -> np.ndarray:
    img = Image.open(path).convert("L").resize((size + 1, size), Image.BILINEAR)
    a = np.asarray(img, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def near_duplicate_groups(paths: list[Path], max_distance: int = 20) -> list[int]:
    hashes = np.stack([dhash(p) for p in paths])
    parent = list(range(len(paths)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(paths)):
        dist = (hashes[i + 1:] != hashes[i]).sum(axis=1)
        for j in np.nonzero(dist <= max_distance)[0] + i + 1:
            parent[find(int(j))] = find(i)
    return [find(i) for i in range(len(paths))]
