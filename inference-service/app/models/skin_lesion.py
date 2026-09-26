"""Dermoscopy image of a skin lesion → 7 diagnostic categories (see training/train_dermatology.py)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "skin-lesion-dermoscopy"
WEIGHTS_FILE = "skin-lesion-resnet18.pt"
META_FILE = "skin-lesion-resnet18.json"


class SkinLesion(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "XC"
    BODY_PART = "SKIN"
    TRAIN_COMMAND = "python -m training.train_dermatology"
    INTENDED_USE = (
        "Research prototype, non-commercial licence. Suggests the likely category (melanoma, basal "
        "cell carcinoma, actinic keratosis/Bowen's, benign keratosis, dermatofibroma, naevus, "
        "vascular) of one pigmented lesion on a dermoscopy image. Not for clinical (non-dermoscopic) "
        "photos, non-pigmented or mucosal lesions, or darker skin types, which are under-represented "
        "in its training data. A dermatologist, and histopathology where indicated, decides."
    )
