"""Train the chest X-ray pneumonia classifier on the Kaggle paediatric dataset.

    cd inference-service
    python -m training.prepare_pneumonia
    python -m training.train_pneumonia

v0.2 over v0.1: the shared training (calibration, balanced accuracy, per-class results,
cosine learning rate); no horizontal flips, since the heart is on the left and a
mirrored film is not a real one; and the 170 children Kaggle put in both train and test
are no longer trained on (see prepare_pneumonia.py).
"""
from app.models.chest_xray_pneumonia import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run
from .prepare_pneumonia import LABELS

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=LABELS,
    data_dir=REPO_ROOT / "dataset" / "chest_xray",
    dataset="Kaggle Chest X-Ray Images (Pneumonia) (Kermany et al., 2018; CC BY 4.0): anterior-posterior "
            "films of children aged 1-5, Guangzhou Women and Children's Medical Center; Kaggle's test "
            "set of 624 films kept as the test set, children who also appear in it removed from training",
    caveat="Paediatric, single centre; Kaggle's test set was drawn separately from its training set and "
           "differs from it, which is why validation scores run higher than test: about one normal film "
           "in four is flagged as pneumonia, and probabilities are overconfident on such films (the "
           "temperature fitted on validation is ~1 and cannot correct this); not externally validated; "
           "do not use for clinical decisions.",
    version="0.2.0",
    grayscale=True,
    hflip=False,
    rotation=8,
)

if __name__ == "__main__":
    run(TASK)
