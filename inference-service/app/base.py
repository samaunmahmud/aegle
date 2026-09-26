"""Contract every Aegle model adapter implements.

A model is one (modality, body part, task) tuple with a declared intended use.
Adding a model means adding one adapter and registering it in registry.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from PIL import Image


@dataclass(frozen=True)
class ModelInfo:
    id: str
    version: str
    modality: str            # DICOM modality code, e.g. "XR"
    body_part: str | None
    task: str                # classification | segmentation | extraction
    intended_use: str
    weights_sha256: str
    metrics: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Prediction:
    label: str
    probability: float


@dataclass(frozen=True)
class Heatmap:
    method: str              # e.g. "grad-cam"
    target_label: str
    png: bytes               # heatmap blended over the input image


@dataclass(frozen=True)
class Measurement:
    name: str                # e.g. "wound_area"
    value: float
    unit: str                # e.g. "px", "%", "mm2"


@dataclass(frozen=True)
class PredictionOutput:
    predictions: list[Prediction]   # sorted by probability, descending
    heatmap: Heatmap | None
    measurements: list[Measurement] = field(default_factory=list)


class ModelUnavailable(RuntimeError):
    """Raised when a registered model has no usable weights on this host."""


class ModelAdapter(ABC):
    #: "image" adapters receive a PIL image, "waveform" a waveform.Waveform (ECG),
    #: "eeg" an eeg.Eeg.
    INPUT_KIND = "image"

    @property
    @abstractmethod
    def info(self) -> ModelInfo: ...

    @abstractmethod
    def predict(self, image: Image.Image, explain: bool = True) -> PredictionOutput:
        """`image` is a waveform.Waveform for adapters whose INPUT_KIND is "waveform"."""
