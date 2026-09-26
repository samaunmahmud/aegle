"""Brain MRI slice with a known tumour → MENINGIOMA / GLIOMA / PITUITARY (see training/)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "brain-mri-tumor-type"
WEIGHTS_FILE = "brain-tumor-resnet18.pt"
META_FILE = "brain-tumor-resnet18.json"


class BrainMriTumorType(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "MR"
    BODY_PART = "BRAIN"
    TRAIN_COMMAND = "python -m training.train_brain_tumor"
    INTENDED_USE = (
        "Research prototype. Suggests the most likely type (meningioma, glioma or pituitary "
        "tumour) for a single contrast-enhanced T1 MRI slice that is already known to show a "
        "tumour. It cannot tell whether a tumour is present, and its output on scans without "
        "one is meaningless. Not validated for clinical use; histopathology and a "
        "neuroradiologist decide the diagnosis."
    )
