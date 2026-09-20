"""Grad-CAM heatmaps (Selvaraju et al., 2017) for convolutional classifiers."""
from __future__ import annotations

import io

import numpy as np
import torch
from PIL import Image
from torch import nn


def grad_cam(model: nn.Module, target_layer: nn.Module, x: torch.Tensor, class_idx: int) -> np.ndarray:
    """Return a (h, w) map in [0, 1] showing which regions drove `class_idx`.

    `x` is a single preprocessed image, shape (1, C, H, W). The map has the
    spatial size of `target_layer`'s output and must be resized by the caller.
    """
    activations: list[torch.Tensor] = []
    gradients: list[torch.Tensor] = []

    def forward_hook(_module, _inputs, output):
        activations.append(output)
        output.register_hook(lambda grad: gradients.append(grad))

    handle = target_layer.register_forward_hook(forward_hook)
    try:
        with torch.enable_grad():
            model.zero_grad(set_to_none=True)
            logits = model(x)
            logits[0, class_idx].backward()
    finally:
        handle.remove()

    weights = gradients[0].mean(dim=(2, 3), keepdim=True)            # (1, C, 1, 1)
    cam = torch.relu((weights * activations[0]).sum(dim=1))[0]       # (h, w)
    cam = cam.detach().cpu().numpy()
    peak = cam.max()
    return cam / peak if peak > 0 else np.zeros_like(cam)


def _colormap(v: np.ndarray) -> np.ndarray:
    """Blue→cyan→yellow→red ('jet'-like) for v in [0, 1]; returns uint8 RGB."""
    r = np.clip(1.5 - np.abs(4 * v - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * v - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * v - 1), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def overlay_png(image: Image.Image, cam: np.ndarray, alpha: float = 0.4) -> bytes:
    """Blend the heatmap over `image` (RGB) and return PNG bytes."""
    cam_img = Image.fromarray((cam * 255).astype(np.uint8)).resize(image.size, Image.BILINEAR)
    heat = _colormap(np.asarray(cam_img, dtype=np.float32) / 255.0)
    base = np.asarray(image.convert("RGB"), dtype=np.float32)
    # Blend proportionally to activation so low-signal regions stay untouched.
    mask = (np.asarray(cam_img, dtype=np.float32) / 255.0)[..., None] * alpha * 2
    blended = base * (1 - np.clip(mask, 0, alpha * 2)) + heat * np.clip(mask, 0, alpha * 2)
    out = io.BytesIO()
    Image.fromarray(blended.clip(0, 255).astype(np.uint8)).save(out, format="PNG")
    return out.getvalue()
