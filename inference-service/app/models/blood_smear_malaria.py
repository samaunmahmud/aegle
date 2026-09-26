"""Single red blood cell image → PARASITIZED / UNINFECTED (see training/train_malaria.py)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "blood-smear-malaria"
WEIGHTS_FILE = "malaria-resnet18.pt"
META_FILE = "malaria-resnet18.json"


class BloodSmearMalaria(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "SM"
    BODY_PART = "BLOOD"
    TRAIN_COMMAND = "python -m training.train_malaria"
    INTENDED_USE = (
        "Research prototype. Classifies one segmented red blood cell from a Giemsa-stained thin "
        "blood smear as parasitised by Plasmodium or uninfected. It does not find cells in a "
        "microscope field or whole slide, does not identify the species or estimate parasitaemia, "
        "and was trained on P. falciparum smears from one hospital in Bangladesh. Microscopy by a "
        "trained reader remains the diagnosis."
    )
