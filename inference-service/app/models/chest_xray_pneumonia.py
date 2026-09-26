"""Chest X-ray → NORMAL / PNEUMONIA (ResNet-18 fine-tuned; see training/)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "chest-xray-pneumonia"
WEIGHTS_FILE = "pneumonia-resnet18.pt"
META_FILE = "pneumonia-resnet18.json"


class ChestXrayPneumonia(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "XR"
    BODY_PART = "CHEST"
    GRAYSCALE = True
    TRAIN_COMMAND = "python -m training.train_pneumonia"
    INTENDED_USE = (
        "Research prototype. Flags chest radiographs that may show pneumonia so a "
        "clinician can prioritise review. Not validated for clinical use; does not "
        "replace clinician interpretation."
    )
