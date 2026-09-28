import json

import numpy as np
import torch
from PIL import Image

from app.models.resnet import build_resnet18
from app.models.resnet_classifier import ResNetClassifier
from training.common import expected_calibration_error, fit_temperature, softmax


def test_fit_temperature_recovers_overconfidence():
    rng = np.random.RandomState(0)
    true = rng.randn(4000, 3) * 1.5
    y = np.array([rng.choice(3, p=p) for p in softmax(true)])
    z = true * 3.0                                  # a model three times too confident
    t = fit_temperature(z, y)
    assert 2.6 < t < 3.4
    assert expected_calibration_error(softmax(z, t), y) < expected_calibration_error(softmax(z), y) / 2


def test_fit_temperature_leaves_calibrated_logits_alone():
    rng = np.random.RandomState(1)
    z = rng.randn(4000, 2) * 2.0
    y = np.array([rng.choice(2, p=p) for p in softmax(z)])
    assert 0.9 < fit_temperature(z, y) < 1.1


class _Tiny(ResNetClassifier):
    MODEL_ID, WEIGHTS_FILE, META_FILE = "tiny", "tiny.pt", "tiny.json"
    MODALITY, BODY_PART, INTENDED_USE, TRAIN_COMMAND = "XC", None, "test", "none"


def test_serving_applies_temperature_from_metadata(tmp_path):
    torch.manual_seed(0)
    torch.save(build_resnet18(2).state_dict(), tmp_path / "tiny.pt")
    meta = {"version": "0", "labels": ["A", "B"], "input_size": 32, "mean": [0, 0, 0], "std": [1, 1, 1]}
    img = Image.fromarray((np.random.RandomState(2).rand(32, 32, 3) * 255).astype(np.uint8))

    def top_probability(**extra):
        (tmp_path / "tiny.json").write_text(json.dumps({**meta, **extra}))
        return _Tiny(tmp_path).predict(img, explain=False).predictions[0].probability

    plain, soft = top_probability(), top_probability(temperature=1000.0)
    assert plain > 0.5 and abs(soft - 0.5) < 0.01          # a huge temperature flattens to 50/50
    assert top_probability(temperature=1.0) == plain        # 1.0 is the pre-calibration behaviour
