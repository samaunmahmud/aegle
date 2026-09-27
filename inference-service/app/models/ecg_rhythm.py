"""12-lead ECG → rhythm statements, multi-label (see training/train_ecg.py)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from ..base import Heatmap, ModelAdapter, ModelInfo, ModelUnavailable, Prediction, PredictionOutput
from ..gradcam import grad_cam
from ..waveform import Waveform, render, resample
from .resnet1d import ResNet1d

MODEL_ID = "ecg-rhythm"
WEIGHTS_FILE = "ecg-rhythm-resnet1d.pt"
META_FILE = "ecg-rhythm-resnet1d.json"

INTENDED_USE = (
    "Research prototype. Estimates, independently for each, how likely a resting 12-lead ECG "
    "shows sinus rhythm, atrial fibrillation, sinus tachycardia, sinus bradycardia, sinus "
    "arrhythmia, a paced rhythm or supraventricular ectopy, using the first 10 seconds. "
    "Probabilities do not sum to one. It does not measure intervals, detect ischaemia or read "
    "ambulatory or single-lead recordings; trained on German hospital ECGs (PTB-XL). "
    "Probabilities are calibrated on held-out PTB-XL patients. A "
    "clinician reads the ECG."
)


class EcgRhythm(ModelAdapter):
    INPUT_KIND = "waveform"

    def __init__(self, model_dir: Path):
        weights_path, meta_path = model_dir / WEIGHTS_FILE, model_dir / META_FILE
        if not weights_path.exists() or not meta_path.exists():
            raise ModelUnavailable(
                f"{MODEL_ID}: weights not found in {model_dir}. Train them with `python -m training.train_ecg`.")
        meta = json.loads(meta_path.read_text())
        self._labels: list[str] = meta["labels"]
        self._fs: float = meta["fs"]
        self._seconds: float = meta["seconds"]
        self._clip: float = meta["clip_mv"]
        cal = meta.get("calibration")
        self._platt = (torch.tensor(cal["a"]), torch.tensor(cal["b"])) if cal else None
        self._net = ResNet1d(len(self._labels))
        self._net.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
        self._net.eval()
        self._info = ModelInfo(
            id=MODEL_ID, version=meta["version"], modality="ECG", body_part=None,
            task="classification", intended_use=INTENDED_USE,
            weights_sha256=hashlib.sha256(weights_path.read_bytes()).hexdigest(),
            metrics=meta.get("metrics", {}),
        )

    @property
    def info(self) -> ModelInfo:
        return self._info

    def _tensor(self, w: Waveform) -> torch.Tensor:
        x = np.clip(resample(w, self._fs, self._seconds), -self._clip, self._clip)
        return torch.from_numpy(x).unsqueeze(0)

    def predict(self, image: Waveform, explain: bool = True) -> PredictionOutput:
        x = self._tensor(image)
        with torch.no_grad():
            logits = self._net(x)[0]
            if self._platt:
                logits = logits * self._platt[0] + self._platt[1]
            probs = torch.sigmoid(logits).tolist()
        preds = sorted((Prediction(label=l, probability=round(p, 6)) for l, p in zip(self._labels, probs)),
                       key=lambda p: p.probability, reverse=True)
        heatmap = None
        if explain:
            top = preds[0].label
            cam = grad_cam(self._net, self._net.layer4, x, self._labels.index(top))
            heatmap = Heatmap(method="grad-cam-1d", target_label=top,
                              png=render(image, seconds=self._seconds, saliency=cam))
        return PredictionOutput(predictions=preds, heatmap=heatmap)
