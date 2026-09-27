"""Train the head CT stroke classifier (split by patient).

    cd inference-service
    python -m training.prepare_stroke
    python -m training.train_stroke
"""
from app.models.head_ct_stroke import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run
from .prepare_stroke import LABELS

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=LABELS,
    data_dir=REPO_ROOT / "dataset" / "stroke_ncct",
    dataset="Baseline non-contrast head CT for stroke triage (Teruelo Diaz et al., 2026; CC BY 4.0): 7,965 "
            "axial slices, 99 patients, Complejo Asistencial Universitario de Leon, Spain; image-level labels",
    caveat="Small (99 patients, about 15 in test); label codes interpreted by visual review; slice-level "
           "labels; early ischaemia is often invisible on CT; do not use for clinical decisions.",
    epochs=12,
    grayscale=True,
    rotation=10,
)

if __name__ == "__main__":
    run(TASK)
