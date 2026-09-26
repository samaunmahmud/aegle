"""Model registry. To add a model: write an adapter, add it to ADAPTERS."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from .base import ModelAdapter, ModelUnavailable
from .models import brain_mri_tumor, chest_xray_pneumonia

log = logging.getLogger("aegle.registry")

# model id -> adapter class (constructed with the model directory)
ADAPTERS: dict[str, type[ModelAdapter]] = {
    chest_xray_pneumonia.MODEL_ID: chest_xray_pneumonia.ChestXrayPneumonia,
    brain_mri_tumor.MODEL_ID: brain_mri_tumor.BrainMriTumorType,
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
