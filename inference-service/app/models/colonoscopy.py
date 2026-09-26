"""Colonoscopy frame → polyp / ulcerative colitis / normal / inadequate view (see training/)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "colonoscopy-findings"
WEIGHTS_FILE = "colonoscopy-resnet18.pt"
META_FILE = "colonoscopy-resnet18.json"


class Colonoscopy(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "ES"
    BODY_PART = "COLON"
    TRAIN_COMMAND = "python -m training.train_gastro"
    INTENDED_USE = (
        "Research prototype. Sorts one white-light colonoscopy still into polyp, ulcerative colitis, "
        "normal mucosa or inadequate view (poor bowel preparation), to help review recorded frames. "
        "It does not localise or size polyps, predict histology, grade colitis activity, or work on "
        "live video or the upper GI tract; trained at one Norwegian hospital. The endoscopist decides."
    )
