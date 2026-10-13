"""Train the prostate Gleason pattern classifier on SICAPv2 (patient-level official test split).

    cd inference-service
    python -m training.prepare_gleason
    python -m training.train_gleason

v0.2 over v0.1: patches at their full 512 px instead of shrunk to 224, so the gland
shapes that separate patterns 3, 4 and 5 stay visible; and calibrated probabilities.
"""
from app.models.prostate_gleason import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run
from .prepare_gleason import LABELS

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=LABELS,
    data_dir=REPO_ROOT / "dataset" / "sicapv2",
    dataset="SICAPv2 (Silva-Rodriguez et al., 2020; CC BY 4.0): H&E prostate biopsy patches, 95 patients, "
            "Hospital Clinico de Valencia, Spain; the dataset's own patient-level test partition",
    caveat="Patch-level Gleason pattern, not a biopsy Gleason score or grade group; one hospital and scanner; "
           "pathologists themselves disagree on patterns 3 vs 4; do not use for clinical decisions.",
    version="0.2.0",
    input_size=512,
    batch_size=16,
    epochs=10,
    vflip=True,
    rotation=180,
    jitter=0.1,
)

if __name__ == "__main__":
    run(TASK)
