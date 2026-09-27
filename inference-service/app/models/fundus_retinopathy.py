"""Colour fundus photograph → diabetic retinopathy grade 0-4 (see training/train_retinopathy.py)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "fundus-diabetic-retinopathy"
WEIGHTS_FILE = "retinopathy-resnet18.pt"
META_FILE = "retinopathy-resnet18.json"


class FundusRetinopathy(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "OP"
    BODY_PART = "EYE"
    TRAIN_COMMAND = "python -m training.train_retinopathy"
    INTENDED_USE = (
        "Research prototype. Suggests a diabetic retinopathy grade (none, mild, moderate, severe, "
        "proliferative; international scale) for one colour fundus photograph of a person with "
        "diabetes, to help order screening review. It does not assess diabetic macular oedema or "
        "any other eye disease, and was trained on 1,600 photos of 400 patients from one Chinese "
        "screening programme. A trained grader or ophthalmologist decides the grade and referral."
    )
