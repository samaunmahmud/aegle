"""Train the colonoscopy frame classifier on HyperKvasir.

    cd inference-service
    python -m training.prepare_gastro
    python -m training.train_gastro
"""
import json

import numpy as np
import torch
from PIL import Image

from app.models.colonoscopy import META_FILE, MODEL_ID, WEIGHTS_FILE
from app.models.resnet import build_resnet18

from .common import REPO_ROOT, Task, blank_regions, default_model_dir, load_index, metrics, run, split, transforms
from .prepare_gastro import LABELS

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=LABELS,
    data_dir=REPO_ROOT / "dataset" / "hyperkvasir",
    dataset="HyperKvasir labelled images (Borgli et al., 2020; CC BY 4.0), lower-GI subset: polyps, "
            "ulcerative colitis (all grades), normal landmarks and well-prepared views, and poorly "
            "prepared views; Baerum Hospital, Norway",
    caveat="No patient ids: near-duplicate frames were grouped before splitting, but frames of one "
           "procedure may still fall on both sides, which would flatter the test result. One hospital; "
           "not validated elsewhere; do not use for clinical decisions.",
    version="0.2.0",
    # The ScopeGuide position box (lower left) and the text strip (left) are burnt into most normal
    # and poorly prepared frames but few polyp or colitis frames. v0.1.0 learnt them: pasting the box
    # onto a polyp frame turned 12% of polyps into "normal". Both areas are blacked out everywhere.
    mask_regions=[(0.0, 0.65, 0.36, 1.0), (0.0, 0.12, 0.14, 0.72)],
    epochs=10,
    vflip=True,          # endoscope orientation is arbitrary
    rotation=180,
)

SCOPEGUIDE = (0.0, 0.70, 0.30, 1.0)


def has_scopeguide(path) -> bool:
    """The ScopeGuide box is a solid teal-green block; its presence marks the capture setup."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    a = np.asarray(im.crop((round(SCOPEGUIDE[0] * w), round(SCOPEGUIDE[1] * h),
                            round(SCOPEGUIDE[2] * w), round(SCOPEGUIDE[3] * h))), dtype=np.int16)
    return float(((a[..., 1] > a[..., 0] + 30) & (a[..., 1] > 80)).mean()) > 0.3


@torch.no_grad()
def by_capture_setup(seed: int = 42) -> dict:
    """Test metrics within frames recorded with and without ScopeGuide. A model that tells classes
    apart by capture setup rather than mucosa falls apart inside each group."""
    _, _, test_rows, _ = split(load_index(TASK), TASK.labels, 0.15, 0.15, seed)
    net = build_resnet18(len(TASK.labels))
    net.load_state_dict(torch.load(default_model_dir() / TASK.weights_file, map_location="cpu", weights_only=True))
    net.eval()
    _, tf = transforms(TASK)
    out = {}
    for name, flag in (("with_scopeguide", True), ("without_scopeguide", False)):
        rows = [r for r in test_rows if has_scopeguide(TASK.data_dir / r["file"]) == flag]
        x = torch.stack([tf(blank_regions(Image.open(TASK.data_dir / r["file"]).convert("RGB"), TASK.mask_regions))
                         for r in rows])
        p = torch.cat([torch.softmax(net(x[i:i + 64]), 1) for i in range(0, len(x), 64)]).numpy()
        m = metrics(p, np.array([r["y"] for r in rows]), TASK.labels)
        out[name] = {k: m[k] for k in ("n", "accuracy", "balanced_accuracy", "per_class")}
    return out


if __name__ == "__main__":
    run(TASK)
    meta_path = default_model_dir() / TASK.meta_file
    meta = json.loads(meta_path.read_text())
    meta["metrics"]["test"]["by_capture_setup"] = by_capture_setup()
    print("BY CAPTURE SETUP:", json.dumps(meta["metrics"]["test"]["by_capture_setup"], indent=2))
    meta_path.write_text(json.dumps(meta, indent=2))
