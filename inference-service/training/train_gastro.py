"""Train the colonoscopy frame classifier on HyperKvasir.

    cd inference-service
    python -m training.prepare_gastro
    python -m training.train_gastro
"""
from app.models.colonoscopy import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run
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
    epochs=10,
    vflip=True,          # endoscope orientation is arbitrary
    rotation=180,
)

if __name__ == "__main__":
    run(TASK)
