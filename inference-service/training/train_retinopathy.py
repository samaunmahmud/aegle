"""Train the diabetic retinopathy grader (5 grades) on full-resolution DeepDRiD.

    cd inference-service
    python -m training.prepare_ophthalmology
    python -m training.train_retinopathy

v0.2 over v0.1 (RetinaMNIST, 224 px): the original photos cropped to the retina at
512 px, so microaneurysms and small haemorrhages (a few pixels at 224) stay visible;
patient ids, so validation is patient-level; and the challenge's evaluation patients,
never used before, as the test set.
"""
from app.models.fundus_retinopathy import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run
from .prepare_ophthalmology import DR_LABELS

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=DR_LABELS,
    data_dir=REPO_ROOT / "dataset" / "retina_dr_full",
    dataset="DeepDRiD regular fundus images (Liu et al., 2022; CC BY-SA 4.0): 2,000 colour fundus "
            "photographs of 500 patients (two views per eye), Shanghai diabetic screening, international "
            "0-4 DR grades; trained on 340 patients, validated on 60, tested on the challenge's 100 "
            "evaluation patients",
    caveat="Small, single-programme dataset from Chinese screening clinics; grades of neighbouring "
           "levels (mild vs moderate) are hard even for graders; not validated elsewhere; do not use "
           "for clinical decisions.",
    version="0.2.0",
    input_size=512,
    batch_size=16,
    epochs=25,
    rotation=30,
    crop_fundus=True,
    ordinal=True,
    refer_from=DR_LABELS.index("DR_MODERATE"),
)

if __name__ == "__main__":
    run(TASK)
