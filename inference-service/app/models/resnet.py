"""ResNet-18 classifier shared by training and serving, so they cannot drift."""
from __future__ import annotations

from PIL import Image
from torch import nn
from torchvision import models

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def blank_regions(img: Image.Image, regions) -> Image.Image:
    """Paints each (x0, y0, x1, y1) region, given as fractions of the frame, black.

    Used where scanners burn overlays into the image (text, position guides) whose presence
    differs by class for reasons unrelated to disease, so the model must never see them.
    """
    if not regions:
        return img
    img = img.copy()
    w, h = img.size
    for x0, y0, x1, y1 in regions:
        img.paste((0,) * len(img.getbands()), (round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h)))
    return img


def build_resnet18(num_classes: int, pretrained: bool = False) -> nn.Module:
    weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
    net = models.resnet18(weights=weights)
    net.fc = nn.Linear(net.fc.in_features, num_classes)
    return net
