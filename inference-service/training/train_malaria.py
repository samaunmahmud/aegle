"""Train the malaria cell classifier.

    cd inference-service
    python -m training.prepare_malaria
    python -m training.train_malaria            # add --limit 50 --epochs 1 for a smoke test

Split by patient: 15% of infected and 15% of healthy patients are held out for testing.
"""
from app.models.blood_smear_malaria import META_FILE, MODEL_ID, WEIGHTS_FILE

from .common import REPO_ROOT, Task, run

TASK = Task(
    model_id=MODEL_ID,
    weights_file=WEIGHTS_FILE,
    meta_file=META_FILE,
    labels=["PARASITIZED", "UNINFECTED"],
    data_dir=REPO_ROOT / "dataset" / "malaria_nih",
    dataset="NIH/NLM malaria cell images (Rajaraman et al., 2018; public domain): 27,558 segmented cells "
            "from Giemsa-stained thin smears of 150 P. falciparum patients and 50 healthy people, "
            "Chittagong Medical College Hospital, Bangladesh",
    caveat="Single-cell classification only; one site, one stain protocol, one smartphone-microscope "
           "setup; not validated elsewhere; do not use for clinical decisions.",
    input_size=128,
    epochs=8,
    vflip=True,          # a cell has no up or down
    rotation=180,
)

if __name__ == "__main__":
    run(TASK)
