import json

import numpy as np
import torch
from PIL import Image

from app.models.resnet import blank_regions, build_resnet18
from app.models.resnet_classifier import ResNetClassifier


def test_blank_regions_paints_fractions_black():
    img = Image.new("RGB", (100, 50), (200, 150, 100))
    out = np.asarray(blank_regions(img, [(0.0, 0.5, 0.3, 1.0)]))
    assert (out[25:, :30] == 0).all()
    assert (out[:25] == (200, 150, 100)).all() and (out[25:, 30:] == (200, 150, 100)).all()
    assert np.asarray(img).min() == 100          # the input is not modified


class _Tiny(ResNetClassifier):
    MODEL_ID, WEIGHTS_FILE, META_FILE = "tiny", "tiny.pt", "tiny.json"
    MODALITY, BODY_PART, INTENDED_USE, TRAIN_COMMAND = "XC", None, "test", "none"


def test_serving_applies_mask_regions_from_metadata(tmp_path):
    torch.save(build_resnet18(2).state_dict(), tmp_path / "tiny.pt")
    meta = {"version": "0", "labels": ["A", "B"], "input_size": 32, "mean": [0, 0, 0], "std": [1, 1, 1],
            "mask_regions": [[0.0, 0.5, 0.5, 1.0]]}
    (tmp_path / "tiny.json").write_text(json.dumps(meta))
    x = _Tiny(tmp_path)._preprocess(Image.new("RGB", (64, 64), (255, 255, 255)))
    assert torch.all(x[0, :, 18:, :14] == 0)     # lower-left quarter blacked out (bilinear blurs its edge)
    assert torch.all(x[0, :, :14] == 1)
