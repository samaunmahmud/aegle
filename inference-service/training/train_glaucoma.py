"""Train the glaucoma disc classifier on ACRIMA.

    cd inference-service
    python -m training.prepare_ophthalmology
    python -m training.train_glaucoma
"""
from app.models.fundus_glaucoma import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=["GLAUCOMA_SUSPECT", "NORMAL_DISC"],
    data_dir=REPO_ROOT / "dataset" / "glaucoma_acrima",
    dataset="ACRIMA (Diaz-Pinto et al., 2019; CC BY 4.0): 705 optic-disc crops (396 glaucomatous, "
            "309 normal) from FISABIO Oftalmologia Medica, Valencia, Spain",
    caveat="No patient ids are published: images were grouped by near-duplicate hashing before "
           "splitting (none found), but both eyes of one patient may still be split apart. "
           "One clinic, one camera; not validated elsewhere; do not use for clinical decisions.",
    epochs=20,
    rotation=15,
)

if __name__ == "__main__":
    run(TASK)
