"""Non-contrast head CT slice → haemorrhage / ischaemic stroke / no stroke (see training/)."""
from __future__ import annotations

from .resnet_classifier import ResNetClassifier

MODEL_ID = "head-ct-stroke"
WEIGHTS_FILE = "head-ct-stroke-resnet18.pt"
META_FILE = "head-ct-stroke-resnet18.json"


class HeadCtStroke(ResNetClassifier):
    MODEL_ID = MODEL_ID
    WEIGHTS_FILE = WEIGHTS_FILE
    META_FILE = META_FILE
    MODALITY = "CT"
    BODY_PART = "BRAIN"
    GRAYSCALE = True
    TRAIN_COMMAND = "python -m training.train_stroke"
    INTENDED_USE = (
        "Research prototype. Flags axial non-contrast head CT slices that look like intracranial "
        "haemorrhage or an established ischaemic infarct, to push suspected strokes up the reading "
        "list; for a series it reports the most suspicious slice. Early ischaemia is often invisible "
        "on CT, so a negative result never excludes stroke, and it must not be used to decide on "
        "thrombolysis or thrombectomy. Trained on 99 patients from one Spanish hospital. A radiologist "
        "reads the scan."
    )
