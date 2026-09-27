"""H&E prostate biopsy patch → Gleason pattern 3/4/5 or benign (see training/train_gleason.py)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "prostate-gleason-pattern"
WEIGHTS_FILE = "prostate-gleason-resnet18.pt"
META_FILE = "prostate-gleason-resnet18.json"


class ProstateGleason(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "SM"
    BODY_PART = "PROSTATE"
    TRAIN_COMMAND = "python -m training.train_gleason"
    INTENDED_USE = (
        "Research prototype. Suggests the Gleason pattern (benign, 3, 4 or 5) of one 512x512 px patch "
        "of an H&E prostate core biopsy at 10x, to help a pathologist find and grade tumour areas. It "
        "does not read whole slides, compute a Gleason score or ISUP grade group, or measure tumour "
        "extent; trained on 95 patients from one Spanish hospital, and Gleason grading varies between "
        "pathologists. The pathologist grades the biopsy."
    )
