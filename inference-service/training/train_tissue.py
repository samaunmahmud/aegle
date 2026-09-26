"""Train the colorectal tissue tile classifier (train NCT-CRC-HE-100K, test CRC-VAL-HE-7K).

    cd inference-service
    python -m training.prepare_tissue
    python -m training.train_tissue
"""
from app.models.colorectal_tissue import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run
from .prepare_tissue import LABELS

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=LABELS,
    data_dir=REPO_ROOT / "dataset" / "crc_tissue",
    dataset="Kather et al. 2019 (CC BY 4.0): trained on 22,500 tiles of NCT-CRC-HE-100K (86 patients), "
            "tested on CRC-VAL-HE-7K (7,180 tiles, 50 different patients); H&E, 0.5 um/px, Germany",
    caveat="Tile classification, not diagnosis or grading; test patients differ from training patients "
           "but come from the same institutions and stain normalisation; do not use for clinical decisions.",
    epochs=6,
    vflip=True,           # histology tiles have no orientation
    rotation=180,
    jitter=0.1,
)

if __name__ == "__main__":
    run(TASK)
