"""Train the brain MRI tumour-type classifier (ResNet-18, ImageNet-pretrained).

    cd inference-service
    python -m training.prepare_brain_tumor          # once: .mat -> PNG + masks + index.csv
    python -m training.train_brain_tumor            # full run
    python -m training.train_brain_tumor --limit 20 --epochs 1   # smoke test

Data: Figshare brain tumour dataset (Cheng et al., CC BY 4.0), 3064 contrast-enhanced
T1 slices from 233 patients, each showing a meningioma, glioma or pituitary tumour.

Train, validation and test are split BY PATIENT (patients have up to 38 slices, so an
image-level split would put the same tumour on both sides). Besides accuracy, the test
report measures calibration (ECE) and whether Grad-CAM falls on the expert tumour outline,
because this dataset mixes imaging planes in a way that correlates with tumour type and a
model can score well by recognising the plane instead of the tumour.

v0.2 over v0.1: the shared training (calibration, shortcut baseline, same patient split),
and slices at their full 512 px instead of shrunk to 224, so small tumours (pituitary
ones cover a few hundred pixels) stay visible.
"""
from app.models.brain_mri_tumor import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run

LABELS = ["MENINGIOMA", "GLIOMA", "PITUITARY"]

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=LABELS,
    data_dir=REPO_ROOT / "dataset" / "brain_tumor_figshare",
    dataset="Figshare brain tumor dataset (Cheng et al., CC BY 4.0): T1 contrast MRI slices "
            "from two hospitals in China, 2005-2010; every slice contains a tumour",
    caveat="Tumour-type classification only; every slice shows a tumour, so it cannot tell whether one "
           "is present; not externally validated; do not use for clinical decisions.",
    version="0.2.0",
    input_size=512,
    batch_size=16,
    grayscale=True,
)

if __name__ == "__main__":
    run(TASK)
