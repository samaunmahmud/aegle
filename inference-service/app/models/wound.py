"""Wound photograph → wound outline and area (see training/train_wound.py)."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from ..base import (Heatmap, Measurement, ModelAdapter, ModelInfo, ModelUnavailable, Prediction,
                    PredictionOutput)
from .resnet import IMAGENET_MEAN, IMAGENET_STD
from .unet import UNetResNet18

MODEL_ID = "wound-segmentation"
WEIGHTS_FILE = "wound-unet-resnet18.pt"
META_FILE = "wound-unet-resnet18.json"

INTENDED_USE = (
    "Research prototype. Outlines the open wound on a clinical photograph of a chronic (foot) ulcer "
    "and reports its area, to follow healing between visits. Area is in image pixels: it is only "
    "comparable between photos taken at the same distance and zoom (a ruler or calibration sticker "
    "is needed for mm2). It does not grade infection, depth or tissue type; trained on diabetic foot "
    "ulcers from one US wound centre. It assumes a wound is in the photo: on 4 of 5 wound-free test "
    "photos it still outlined a small area, so it cannot tell whether a wound is present. "
    "The clinician measures and decides."
)


class WoundSegmentation(ModelAdapter):
    def __init__(self, model_dir: Path):
        weights_path, meta_path = model_dir / WEIGHTS_FILE, model_dir / META_FILE
        if not weights_path.exists() or not meta_path.exists():
            raise ModelUnavailable(
                f"{MODEL_ID}: weights not found in {model_dir}. Train them with `python -m training.train_wound`.")
        meta = json.loads(meta_path.read_text())
        self._size = int(meta["input_size"])
        self._net = UNetResNet18()
        self._net.load_state_dict(torch.load(weights_path, map_location="cpu", weights_only=True))
        self._net.eval()
        self._mean = torch.tensor(IMAGENET_MEAN).view(1, 3, 1, 1)
        self._std = torch.tensor(IMAGENET_STD).view(1, 3, 1, 1)
        self._info = ModelInfo(
            id=MODEL_ID, version=meta["version"], modality="XC", body_part="WOUND",
            task="segmentation", intended_use=INTENDED_USE,
            weights_sha256=hashlib.sha256(weights_path.read_bytes()).hexdigest(),
            metrics=meta.get("metrics", {}),
        )

    @property
    def info(self) -> ModelInfo:
        return self._info

    def probability_map(self, image: Image.Image) -> np.ndarray:
        """Per-pixel wound probability at the image's own size."""
        img = image.convert("RGB")
        x = torch.from_numpy(np.asarray(img.resize((self._size, self._size), Image.BILINEAR),
                                        dtype=np.float32) / 255.0).permute(2, 0, 1).unsqueeze(0)
        with torch.no_grad():
            p = torch.sigmoid(self._net((x - self._mean) / self._std))[0, 0].numpy()
        return np.asarray(Image.fromarray((p * 255).astype(np.uint8)).resize(img.size, Image.BILINEAR),
                          dtype=np.float32) / 255.0

    def predict(self, image: Image.Image, explain: bool = True) -> PredictionOutput:
        p = self.probability_map(image)
        mask = p >= 0.5
        present = float(p.max())
        preds = sorted([Prediction("WOUND_DETECTED", round(present, 6)),
                        Prediction("NO_WOUND_DETECTED", round(1 - present, 6))],
                       key=lambda q: q.probability, reverse=True)
        measurements = [Measurement("wound_area", float(mask.sum()), "px"),
                        Measurement("wound_area_fraction", round(float(mask.mean()) * 100, 3), "%")]
        heatmap = None
        if explain:
            heatmap = Heatmap(method="segmentation", target_label="WOUND_DETECTED", png=_outline(image, mask))
        return PredictionOutput(predictions=preds, heatmap=heatmap, measurements=measurements)


def _outline(image: Image.Image, mask: np.ndarray) -> bytes:
    """The photo with the wound filled translucent cyan and outlined, same size as the photo."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    edge = mask & ~(np.roll(mask, 1, 0) & np.roll(mask, -1, 0) & np.roll(mask, 1, 1) & np.roll(mask, -1, 1))
    out = rgb.copy()
    out[mask] = out[mask] * 0.55 + np.array([0, 200, 220]) * 0.45
    thick = edge | np.roll(edge, 1, 0) | np.roll(edge, 1, 1)
    out[thick] = [0, 255, 255]
    buf = io.BytesIO()
    Image.fromarray(out.astype(np.uint8)).save(buf, format="PNG")
    return buf.getvalue()
