"""1D ResNet for 12-lead ECG, shared by training and serving so they cannot drift."""
from __future__ import annotations

import torch
from torch import nn


class Block(nn.Module):
    def __init__(self, cin: int, cout: int, stride: int):
        super().__init__()
        self.conv1 = nn.Conv1d(cin, cout, 9, stride=stride, padding=4, bias=False)
        self.bn1 = nn.BatchNorm1d(cout)
        self.conv2 = nn.Conv1d(cout, cout, 9, padding=4, bias=False)
        self.bn2 = nn.BatchNorm1d(cout)
        self.skip = nn.Sequential() if stride == 1 and cin == cout else nn.Sequential(
            nn.Conv1d(cin, cout, 1, stride=stride, bias=False), nn.BatchNorm1d(cout))
        self.act = nn.ReLU(inplace=True)

    def forward(self, x):
        out = self.act(self.bn1(self.conv1(x)))
        return self.act(self.bn2(self.conv2(out)) + self.skip(x))


class ResNet1d(nn.Module):
    """Input (batch, 12, samples) in mV; output one logit per label (multi-label)."""

    def __init__(self, num_labels: int, leads: int = 12):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv1d(leads, 64, 15, stride=2, padding=7, bias=False),
                                  nn.BatchNorm1d(64), nn.ReLU(inplace=True))
        self.layer1 = nn.Sequential(Block(64, 64, 1), Block(64, 64, 1))
        self.layer2 = nn.Sequential(Block(64, 128, 2), Block(128, 128, 1))
        self.layer3 = nn.Sequential(Block(128, 192, 2), Block(192, 192, 1))
        self.layer4 = nn.Sequential(Block(192, 256, 2), Block(256, 256, 1))
        self.head = nn.Linear(512, num_labels)

    def forward(self, x):
        x = self.layer4(self.layer3(self.layer2(self.layer1(self.stem(x)))))
        return self.head(torch.cat([x.mean(dim=2), x.amax(dim=2)], dim=1))
