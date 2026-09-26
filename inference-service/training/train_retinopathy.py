"""Train the diabetic retinopathy grader (5 grades) on RetinaMNIST-224 / DeepDRiD.

    cd inference-service
    python -m training.prepare_ophthalmology
    python -m training.train_retinopathy
"""
from app.models.fundus_retinopathy import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run
from .prepare_ophthalmology import DR_LABELS

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=DR_LABELS,
    data_dir=REPO_ROOT / "dataset" / "retina_dr",
    dataset="RetinaMNIST-224 (MedMNIST+, CC BY 4.0) from DeepDRiD (Liu et al., 2022): 1,600 colour "
            "fundus photographs, Shanghai diabetic screening, international 0-4 DR grades; the "
            "source's own train/val/test split (1,080/120/400)",
    caveat="Small, single-programme dataset; published results on it are modest (about 0.5 accuracy); "
           "not validated elsewhere; do not use for clinical decisions.",
    epochs=20,
    rotation=15,
)

if __name__ == "__main__":
    run(TASK)
