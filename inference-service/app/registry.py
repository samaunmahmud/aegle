"""Model registry. To add a model: write an adapter, add it to ADAPTERS."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from .base import ModelAdapter, ModelUnavailable
from .models import (blood_smear_malaria, brain_mri_tumor, chest_xray_pneumonia, colonoscopy,
                     prostate_gleason,
                     colorectal_tissue, ecg_rhythm, eeg_seizure, fundus_retinopathy,
                     skin_lesion, wound)

log = logging.getLogger("aegle.registry")

# model id -> adapter class (constructed with the model directory)
ADAPTERS: dict[str, type[ModelAdapter]] = {
    chest_xray_pneumonia.MODEL_ID: chest_xray_pneumonia.ChestXrayPneumonia,
    brain_mri_tumor.MODEL_ID: brain_mri_tumor.BrainMriTumorType,
    blood_smear_malaria.MODEL_ID: blood_smear_malaria.BloodSmearMalaria,
    fundus_retinopathy.MODEL_ID: fundus_retinopathy.FundusRetinopathy,
    # fundus-glaucoma is withdrawn: on ACRIMA a trivial model using only image size and
    # colour statistics reaches AUC 0.99, so its perfect test score reflects how the two
    # classes were photographed, not glaucoma. Re-enable only after training on data
    # without that confound (see training/train_glaucoma.py).
    ecg_rhythm.MODEL_ID: ecg_rhythm.EcgRhythm,
    skin_lesion.MODEL_ID: skin_lesion.SkinLesion,
    colonoscopy.MODEL_ID: colonoscopy.Colonoscopy,
    colorectal_tissue.MODEL_ID: colorectal_tissue.ColorectalTissue,
    eeg_seizure.MODEL_ID: eeg_seizure.EegSeizure,
    wound.MODEL_ID: wound.WoundSegmentation,
    # head-ct-stroke is withdrawn: on its 99-patient dataset it overfits after two epochs and
    # finds 15% of ischaemic-stroke slices; see training/train_stroke.py.
    prostate_gleason.MODEL_ID: prostate_gleason.ProstateGleason,
}


def default_model_dir() -> Path:
    env = os.environ.get("AEGLE_MODEL_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[2] / "saved-model"


class Registry:
    def __init__(self, model_dir: Path | None = None):
        self._dir = model_dir or default_model_dir()
        self._loaded: dict[str, ModelAdapter] = {}
        self._unavailable: dict[str, str] = {}
        for model_id, cls in ADAPTERS.items():
            try:
                self._loaded[model_id] = cls(self._dir)
                log.info("loaded model %s", model_id)
            except ModelUnavailable as exc:
                self._unavailable[model_id] = str(exc)
                log.warning("model %s unavailable: %s", model_id, exc)

    def get(self, model_id: str) -> ModelAdapter:
        if model_id in self._loaded:
            return self._loaded[model_id]
        if model_id in self._unavailable:
            raise ModelUnavailable(self._unavailable[model_id])
        raise KeyError(model_id)

    def loaded(self) -> list[ModelAdapter]:
        return list(self._loaded.values())

    def unavailable(self) -> dict[str, str]:
        return dict(self._unavailable)
