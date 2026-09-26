"""H&E tile of colorectal tissue → 9 tissue classes (see training/train_tissue.py)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "colorectal-tissue-he"
WEIGHTS_FILE = "colorectal-tissue-resnet18.pt"
META_FILE = "colorectal-tissue-resnet18.json"


class ColorectalTissue(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "SM"
    BODY_PART = "TISSUE"
    TRAIN_COMMAND = "python -m training.train_tissue"
    INTENDED_USE = (
        "Research prototype. Classifies one 224x224 px tile (0.5 um/px, H&E) of colorectal tissue as "
        "tumour epithelium, cancer-associated stroma, normal mucosa, lymphocytes, mucus, muscle, "
        "debris/necrosis, fat or background. It does not read whole slides, grade tumours, stage, or "
        "assess other organs; stain differences from its training labs degrade it. A pathologist "
        "makes the diagnosis."
    )
