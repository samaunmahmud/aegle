import json

import numpy as np
import torch
from PIL import Image, ImageDraw

from app.models.resnet import build_resnet18, crop_fundus
from app.models.resnet_classifier import ResNetClassifier


def fundus(w=300, h=200, r=80, colour=(180, 90, 40)):
    """A round 'retina' off-centre in a black frame, like a fundus camera image."""
    img = Image.new("RGB", (w, h))
    ImageDraw.Draw(img).ellipse((120 - r, 100 - r, 120 + r, 100 + r), fill=colour)
    return img


def test_crop_fundus_trims_the_black_frame_to_a_square():
    out = crop_fundus(fundus())
    assert out.size[0] == out.size[1]
    assert abs(out.size[0] - 160) <= 4                # the retina's diameter
    a = np.asarray(out)
    assert (a[out.size[1] // 2, out.size[0] // 2] == (180, 90, 40)).all()


def test_crop_fundus_is_idempotent_and_leaves_blank_images_alone():
    once = crop_fundus(fundus())
    assert abs(crop_fundus(once).size[0] - once.size[0]) <= 2
    blank = Image.new("RGB", (50, 40))
    assert crop_fundus(blank) is blank


class _Tiny(ResNetClassifier):
    MODEL_ID, WEIGHTS_FILE, META_FILE = "tiny", "tiny.pt", "tiny.json"
    MODALITY, BODY_PART, INTENDED_USE, TRAIN_COMMAND = "OP", "EYE", "test", "none"


def test_serving_crops_when_the_metadata_says_so(tmp_path):
    torch.save(build_resnet18(2).state_dict(), tmp_path / "tiny.pt")
    meta = {"version": "0", "labels": ["A", "B"], "input_size": 32, "mean": [0, 0, 0], "std": [1, 1, 1],
            "crop_fundus": True}
    (tmp_path / "tiny.json").write_text(json.dumps(meta))
    x = _Tiny(tmp_path)._preprocess(fundus(colour=(255, 255, 255)))
    assert x[0, :, 16, :].min() > 0.5                  # the middle row is all retina: no black frame
    assert _Tiny(tmp_path).predict(fundus(), explain=True).heatmap is not None
