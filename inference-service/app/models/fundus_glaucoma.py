"""Optic-disc crop of a fundus photograph → GLAUCOMA_SUSPECT / NORMAL_DISC (see training/)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "fundus-glaucoma"
WEIGHTS_FILE = "glaucoma-resnet18.pt"
META_FILE = "glaucoma-resnet18.json"


class FundusGlaucoma(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "OP"
    BODY_PART = "EYE"
    TRAIN_COMMAND = "python -m training.train_glaucoma"
    INTENDED_USE = (
        "Research prototype. Flags glaucomatous optic disc appearance on a fundus photograph "
        "cropped around the optic disc. It needs that crop (a full fundus photo is out of "
        "distribution), sees only disc morphology, and cannot replace intraocular pressure, "
        "visual fields or OCT. Trained on 705 images from one clinic in Spain."
    )
