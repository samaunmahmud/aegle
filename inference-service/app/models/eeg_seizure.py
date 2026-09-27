"""Scalp EEG (EDF) → probability of seizure activity, with a timeline (see training/train_eeg.py)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from ..base import Heatmap, Measurement, ModelAdapter, ModelInfo, ModelUnavailable, Prediction, PredictionOutput
from ..eeg import MONTAGE, Eeg, render, windows
from .resnet1d import ResNet1d

MODEL_ID = "eeg-seizure"
WEIGHTS_FILE = "eeg-seizure-resnet1d.pt"
META_FILE = "eeg-seizure-resnet1d.json"

INTENDED_USE = (
    "Research prototype. Screens a routine or long-term scalp EEG (EDF, 10-20 electrodes) for "
    "stretches that look like electrographic seizures and shows where they are over the recording. "
    "It gives one alarm score per recording (0.5 or more means at least one alarm), cannot characterise "
    "seizure type, and was trained on children with intractable epilepsy (CHB-MIT, Boston). It "
    "misses some seizures and raises false alarms; a neurophysiologist reads the EEG."
)


def sustained(p: np.ndarray, k: int) -> np.ndarray:
    """Per window: the highest probability held for k consecutive windows that include it."""
    if k <= 1:
        return p
    if len(p) < k:
        return np.full_like(p, p.min())
    lows = np.lib.stride_tricks.sliding_window_view(p, k).min(axis=1)   # run starting at each window
    out = np.full(len(p), -np.inf)
    for o in range(k):
        out[o:o + len(lows)] = np.maximum(out[o:o + len(lows)], lows)
    return out


def alarm_score(p: np.ndarray, threshold: float, k: int) -> np.ndarray:
    """Maps sustained probability so that 0.5 is the alarm point (tuned on validation patients):
    a window scores 0.5 or more exactly when it lies in k consecutive windows at or above threshold."""
    s = sustained(p, k)
    return np.where(s < threshold, 0.5 * s / threshold, 0.5 + 0.5 * (s - threshold) / (1 - threshold))


def alarm_events(score: np.ndarray, starts: np.ndarray, window_seconds: float) -> list[tuple[float, float]]:
    """(start, end) seconds of each run of alarm windows."""
    events, run = [], None
    for i, on in enumerate(score >= 0.5):
        if on and run is None:
            run = i
        if (not on or i == len(score) - 1) and run is not None:
            end = i if on else i - 1
            events.append((float(starts[run]), float(starts[end]) + window_seconds))
            run = None
    return events


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
        self._threshold = float(meta.get("threshold", 0.5))
        self._min_windows = int(meta.get("min_windows", 1))
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
        with torch.inference_mode():
            # Small batches: on CPU, 16+ windows per batch run ~15x slower per window (measured on
            # Apple silicon), which pushed a one-hour recording past core-api's 120 s timeout.
            for i in range(0, len(x), 8):
                probs.append(torch.sigmoid(self._net(torch.from_numpy(x[i:i + 8])))[:, 0].numpy())
        p = np.concatenate(probs)
        return np.convolve(np.pad(p, 1, mode="edge"), np.ones(3) / 3, mode="valid"), starts

    def predict(self, image: Eeg, explain: bool = True) -> PredictionOutput:
        p, starts = self.window_probabilities(image)
        p = alarm_score(p, self._threshold, self._min_windows)
        events = alarm_events(p, starts, self._window)
        peak = float(p.max())
        preds = sorted([Prediction("SEIZURE_ACTIVITY", round(peak, 6)),
                        Prediction("NO_SEIZURE_ACTIVITY", round(1 - peak, 6))],
                       key=lambda q: q.probability, reverse=True)
        measurements = [Measurement("seizure_alarms", float(len(events)), "count"),
                        Measurement("alarm_duration", round(sum(b - a for a, b in events), 1), "s")]
        heatmap = None
        if explain:
            centre = float(starts[int(p.argmax())]) + self._window / 2
            heatmap = Heatmap(method="window-probability", target_label="SEIZURE_ACTIVITY",
                              png=render(image, page_start=centre - 5, probabilities=p,
                                         window_starts=starts, window_seconds=self._window,
                                         label="Seizure alarm score (0.5 or more = alarm)"))
        return PredictionOutput(predictions=preds, heatmap=heatmap, measurements=measurements)
