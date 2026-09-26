"""Scalp EEG (EDF) → probability of seizure activity, with a timeline (see training/train_eeg.py)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from ..base import Heatmap, ModelAdapter, ModelInfo, ModelUnavailable, Prediction, PredictionOutput
from ..eeg import MONTAGE, Eeg, render, windows
from .resnet1d import ResNet1d

MODEL_ID = "eeg-seizure"
WEIGHTS_FILE = "eeg-seizure-resnet1d.pt"
META_FILE = "eeg-seizure-resnet1d.json"

INTENDED_USE = (
    "Research prototype. Screens a routine or long-term scalp EEG (EDF, 10-20 electrodes) for "
    "stretches that look like electrographic seizures and shows where they are over the recording. "
    "It gives one probability per recording (the most seizure-like stretch), cannot characterise "
    "seizure type, and was trained on children with intractable epilepsy (CHB-MIT, Boston). It "
    "misses some seizures and raises false alarms; a neurophysiologist reads the EEG."
)


class EegSeizure(ModelAdapter):
    INPUT_KIND = "eeg"

    def __init__(self, model_dir: Path):
        weights_path, meta_path = model_dir / WEIGHTS_FILE, model_dir / META_FILE
        if not weights_path.exists() or not meta_path.exists():
            raise ModelUnavailable(
                f"{MODEL_ID}: weights not found in {model_dir}. Train them with `python -m training.train_eeg`.")
        meta = json.loads(meta_path.read_text())
        self._window = float(meta["window_seconds"])
        self._stride = float(meta["stride_seconds"])
        self._net = ResNet1d(1, leads=len(MONTAGE))
        self._net.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
        self._net.eval()
        self._info = ModelInfo(
            id=MODEL_ID, version=meta["version"], modality="EEG", body_part=None,
            task="detection", intended_use=INTENDED_USE,
            weights_sha256=hashlib.sha256(weights_path.read_bytes()).hexdigest(),
            metrics=meta.get("metrics", {}),
        )

    @property
    def info(self) -> ModelInfo:
        return self._info

    def window_probabilities(self, eeg: Eeg) -> tuple[np.ndarray, np.ndarray]:
        """Per-window seizure probability, smoothed over neighbouring windows, and window starts."""
        x, starts = windows(eeg, self._window, self._stride)
        probs = []
        with torch.no_grad():
            for i in range(0, len(x), 256):
                probs.append(torch.sigmoid(self._net(torch.from_numpy(x[i:i + 256])))[:, 0].numpy())
        p = np.concatenate(probs)
        return np.convolve(np.pad(p, 1, mode="edge"), np.ones(3) / 3, mode="valid"), starts

    def predict(self, image: Eeg, explain: bool = True) -> PredictionOutput:
        p, starts = self.window_probabilities(image)
        peak = float(p.max())
        preds = sorted([Prediction("SEIZURE_ACTIVITY", round(peak, 6)),
                        Prediction("NO_SEIZURE_ACTIVITY", round(1 - peak, 6))],
                       key=lambda q: q.probability, reverse=True)
        heatmap = None
        if explain:
            centre = float(starts[int(p.argmax())]) + self._window / 2
            heatmap = Heatmap(method="window-probability", target_label="SEIZURE_ACTIVITY",
                              png=render(image, page_start=centre - 5, probabilities=p,
                                         window_starts=starts, window_seconds=self._window))
        return PredictionOutput(predictions=preds, heatmap=heatmap)
