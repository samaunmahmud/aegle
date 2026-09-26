"""Serving for any ResNet-18 image classifier trained by a script in training/.

A concrete model sets the class attributes below; weights and a metadata JSON
(labels, input size, normalisation, metrics) are read from the model directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from ..base import (Heatmap, ModelAdapter, ModelInfo, ModelUnavailable, Prediction,
                    PredictionOutput)
from ..gradcam import grad_cam, overlay_png
from .resnet import build_resnet18


class ResNetClassifier(ModelAdapter):
    MODEL_ID: str
    WEIGHTS_FILE: str
    META_FILE: str
    MODALITY: str
    BODY_PART: str | None
    INTENDED_USE: str
    TRAIN_COMMAND: str
    # Radiology models were trained on grayscale; colour modalities keep RGB.
    GRAYSCALE: bool = False

    def __init__(self, model_dir: Path):
        weights_path = model_dir / self.WEIGHTS_FILE
        meta_path = model_dir / self.META_FILE
        if not weights_path.exists() or not meta_path.exists():
            raise ModelUnavailable(
                f"{self.MODEL_ID}: weights not found in {model_dir}. Train them with `{self.TRAIN_COMMAND}`."
            )
        meta = json.loads(meta_path.read_text())
        self._labels: list[str] = meta["labels"]
        self._size: int = meta["input_size"]
        self._mean = torch.tensor(meta["mean"]).view(1, 3, 1, 1)
        self._std = torch.tensor(meta["std"]).view(1, 3, 1, 1)

        self._net = build_resnet18(len(self._labels), pretrained=False)
        # weights_only=True: never unpickle arbitrary objects from a weights file.
        state = torch.load(weights_path, map_location="cpu", weights_only=True)
        self._net.load_state_dict(state)
        self._net.eval()

        self._info = ModelInfo(
            id=self.MODEL_ID,
            version=meta["version"],
            modality=self.MODALITY,
            body_part=self.BODY_PART,
            task="classification",
            intended_use=self.INTENDED_USE,
            weights_sha256=hashlib.sha256(weights_path.read_bytes()).hexdigest(),
            metrics=meta.get("metrics", {}),
        )

    @property
    def info(self) -> ModelInfo:
        return self._info

    def _preprocess(self, image: Image.Image) -> torch.Tensor:
        img = image.convert("L").convert("RGB") if self.GRAYSCALE else image.convert("RGB")
        img = img.resize((self._size, self._size), Image.BILINEAR)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        x = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
        return (x - self._mean) / self._std

    def predict(self, image: Image.Image, explain: bool = True) -> PredictionOutput:
        x = self._preprocess(image)
        with torch.no_grad():
            probs = torch.softmax(self._net(x), dim=1)[0].tolist()
        preds = sorted(
            (Prediction(label=l, probability=round(p, 6)) for l, p in zip(self._labels, probs)),
            key=lambda p: p.probability,
            reverse=True,
        )

        heatmap = None
        if explain:
            top = preds[0].label
            cam = grad_cam(self._net, self._net.layer4, x, self._labels.index(top))
            heatmap = Heatmap(method="grad-cam", target_label=top, png=overlay_png(image, cam))
        return PredictionOutput(predictions=preds, heatmap=heatmap)
