"""ResNet-18 classifier shared by training and serving, so they cannot drift."""
from __future__ import annotations

from torch import nn
from torchvision import models

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_resnet18(num_classes: int, pretrained: bool = False) -> nn.Module:
    weights = models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None
    net = models.resnet18(weights=weights)
    net.fc = nn.Linear(net.fc.in_features, num_classes)
    return net
