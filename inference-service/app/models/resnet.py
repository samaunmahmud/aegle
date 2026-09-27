"""ResNet-18 classifier shared by training and serving, so they cannot drift."""
from __future__ import annotations

import numpy as np
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


def crop_fundus(img: Image.Image, threshold: int = 12) -> Image.Image:
    """Crops a fundus photo to the retina and pads it square with black.

    Cameras put the round retina in a black frame whose width varies by camera and
    patient; without cropping, the retina fills a varying share of the input and small
    lesions lose pixels to background. Idempotent, so it is safe on already-cropped images.
    """
    small = img.convert("L").resize((256, round(256 * img.height / img.width)))
    ys, xs = np.nonzero(np.asarray(small) > threshold)
    if len(xs) == 0:
        return img
    sx, sy = img.width / small.width, img.height / small.height
    box = (int(xs.min() * sx), int(ys.min() * sy), int((xs.max() + 1) * sx), int((ys.max() + 1) * sy))
    retina = img.crop(box)
    side = max(retina.size)
    square = Image.new(retina.mode, (side, side))
    square.paste(retina, ((side - retina.width) // 2, (side - retina.height) // 2))
    return square


def build_resnet18(num_classes: int, pretrained: bool = False) -> nn.Module:
    weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
    net = models.resnet18(weights=weights)
    net.fc = nn.Linear(net.fc.in_features, num_classes)
    return net
