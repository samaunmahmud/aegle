"""U-Net with an ImageNet ResNet-18 encoder, shared by training and serving."""
from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F
from torchvision import models


class Up(nn.Module):
    def __init__(self, cin: int, cskip: int, cout: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(cin + cskip, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True),
            nn.Conv2d(cout, cout, 3, padding=1, bias=False), nn.BatchNorm2d(cout), nn.ReLU(inplace=True))

    def forward(self, x, skip):
        x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
        return self.conv(torch.cat([x, skip], dim=1))


class UNetResNet18(nn.Module):
    """Input (batch, 3, H, W) normalised like ImageNet; output (batch, 1, H, W) logits."""

    def __init__(self, pretrained: bool = False):
        super().__init__()
        r = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1 if pretrained else None)
        self.stem = nn.Sequential(r.conv1, r.bn1, r.relu)          # 1/2, 64
        self.pool = r.maxpool
        self.enc1, self.enc2, self.enc3, self.enc4 = r.layer1, r.layer2, r.layer3, r.layer4
        self.up4 = Up(512, 256, 256)
        self.up3 = Up(256, 128, 128)
        self.up2 = Up(128, 64, 64)
        self.up1 = Up(64, 64, 32)
        self.head = nn.Conv2d(32, 1, 1)

    def forward(self, x):
        s0 = self.stem(x)
        e1 = self.enc1(self.pool(s0))
        e2 = self.enc2(e1)
        e3 = self.enc3(e2)
        e4 = self.enc4(e3)
        d = self.up1(self.up2(self.up3(self.up4(e4, e3), e2), e1), s0)
        return F.interpolate(self.head(d), size=x.shape[-2:], mode="bilinear", align_corners=False)
