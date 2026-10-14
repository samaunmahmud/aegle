"""Train the skin lesion classifier on HAM10000; test on held-out lesions and on ISIC 2018.

    cd inference-service
    python -m training.prepare_dermatology
    python -m training.train_dermatology

v0.2 over v0.1: images at 448 px instead of shrunk to 224 (the photos are 600x450), so
the fine network and dot patterns that separate melanoma and keratoses stay visible;
and calibrated probabilities.
"""
from app.models.skin_lesion import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run
from .prepare_dermatology import LABELS

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=LABELS,
    data_dir=REPO_ROOT / "dataset" / "ham10000",
    dataset="HAM10000 (Tschandl et al., 2018; CC BY-NC 4.0, NON-COMMERCIAL): 10,015 dermoscopy images "
            "of 7,470 lesions, Vienna and Queensland, 53% histopathology-confirmed; external test on "
            "the ISIC 2018 Task 3 test set (1,512 images)",
    caveat="Licence forbids commercial use. Mostly fair-skinned European and Australian patients; "
           "dermoscopy only; not validated prospectively; do not use for clinical decisions.",
    version="0.2.0",
    input_size=448,
    batch_size=16,
    epochs=15,
    vflip=True,          # dermoscopy has no fixed orientation
    rotation=180,
)

if __name__ == "__main__":
    run(TASK)
