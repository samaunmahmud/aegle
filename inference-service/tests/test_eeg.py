"""EEG (EDF) reading, montage, rendering and the seizure model path."""
import io
import json

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image

from app import eeg
from app.models import eeg_seizure
from app.models.resnet1d import ResNet1d
from training.edf import write_edf

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ELECTRODES = ["FP1", "F7", "T7", "P7", "O1", "F3", "C3", "P3", "FP2", "F4", "C4", "P4", "F8", "T8", "P8",
              "O2", "FZ", "CZ", "PZ"]


def signals(n_channels, fs=256, seconds=30):
    t = np.arange(fs * seconds) / fs
    return np.stack([30 * np.sin(2 * np.pi * (5 + i) * t) for i in range(n_channels)])


def bipolar_edf(fs=256, seconds=30):
    return write_edf(signals(len(eeg.MONTAGE), fs, seconds), eeg.MONTAGE, fs)


def test_bipolar_edf_is_read_in_montage_order_and_resampled():
    e = eeg.read_edf(bipolar_edf())
    assert e.signals.shape == (18, 30 * 128) and e.fs == 128
    expected = signals(18)[0].reshape(-1, 2).mean(axis=1)         # 256 -> 128 Hz by averaging
    assert np.abs(e.signals[0] - expected).max() < 0.2           # within EDF quantisation


def test_referential_edf_is_converted_to_the_bipolar_montage():
    ref = signals(len(ELECTRODES))
    labels = [f"EEG {n.title()}-REF" for n in ELECTRODES]
    labels[ELECTRODES.index("T7")] = "EEG T3-REF"                 # old 10-20 name
    e = eeg.read_edf(write_edf(ref, labels, 256))
    fp1, f7 = ref[ELECTRODES.index("FP1")], ref[ELECTRODES.index("F7")]
    assert np.abs(e.signals[0] - (fp1 - f7).reshape(-1, 2).mean(axis=1)).max() < 0.3


def test_bad_eegs_are_refused():
    with pytest.raises(eeg.UnsupportedEeg, match="lacks channel"):
        eeg.read_edf(write_edf(signals(5), eeg.MONTAGE[:5], 256))
    with pytest.raises(eeg.UnsupportedEeg, match="at least 10 seconds"):
        eeg.read_edf(bipolar_edf(seconds=5))
    assert not eeg.is_edf(b"not an edf")


def test_windows_and_render():
    e = eeg.read_edf(bipolar_edf())
    x, starts = eeg.windows(e, 8, 4)
    assert x.shape == (6, 18, 1024) and starts.tolist() == [0, 4, 8, 12, 16, 20]
    png = Image.open(io.BytesIO(eeg.render(e, probabilities=np.linspace(0, 1, 6), window_starts=starts)))
    assert png.size[0] > 1000


@pytest.fixture()
def client(tmp_path, monkeypatch):
    torch.manual_seed(0)
    torch.save(ResNet1d(1, leads=18).state_dict(), tmp_path / eeg_seizure.WEIGHTS_FILE)
    (tmp_path / eeg_seizure.META_FILE).write_text(json.dumps(
        {"version": "test", "window_seconds": 8, "stride_seconds": 4}))
    monkeypatch.setenv("AEGLE_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("AEGLE_INFERENCE_TOKEN", TOKEN)
    from app.main import app
    with TestClient(app, headers=AUTH) as c:
        yield c


def test_seizure_model_reports_a_recording_probability_and_timeline(client):
    r = client.post("/v1/models/eeg-seizure/predict", files={"file": ("x.edf", bipolar_edf())})
    assert r.status_code == 200, r.text
    body = r.json()
    assert {p["label"] for p in body["predictions"]} == {"SEIZURE_ACTIVITY", "NO_SEIZURE_ACTIVITY"}
    assert abs(sum(p["probability"] for p in body["predictions"]) - 1) < 1e-3
    assert body["model"]["modality"] == "EEG" and body["heatmap"]["method"] == "window-probability"


def test_render_draws_edf(client):
    r = client.post("/v1/render", files={"file": ("x.edf", bipolar_edf())})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
