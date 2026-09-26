"""ECG decoding, rendering and the waveform model path."""
import io
import json

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image

from app import waveform
from app.models import ecg_rhythm
from app.models.resnet1d import ResNet1d
from training.ecg_dicom import ecg_dicom

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}
LABELS = ["SINUS_RHYTHM", "ATRIAL_FIBRILLATION"]


def synthetic(fs=500, seconds=10):
    t = np.arange(int(fs * seconds)) / fs
    beat = np.exp(-((t % 0.8) - 0.3) ** 2 / 0.0005)            # a spike every 0.8 s
    return np.stack([beat * (1 + i / 12) for i in range(12)]).astype(np.float32)


def csv_bytes(sig, fs=500, units="mV", leads=waveform.LEADS):
    lines = [f"# fs={fs} units={units}", ",".join(leads)]
    lines += [",".join(f"{v:.4f}" for v in row) for row in sig.T]
    return "\n".join(lines).encode()


def test_csv_and_dicom_decode_to_the_same_millivolts():
    sig = synthetic()
    from_csv = waveform.decode_waveform(csv_bytes(sig))
    from_dcm = waveform.decode_waveform(ecg_dicom(sig, 500))
    assert from_csv.signals.shape == from_dcm.signals.shape == (12, 5000)
    assert from_csv.fs == from_dcm.fs == 500
    assert np.abs(from_csv.signals - from_dcm.signals).max() < 0.002      # uV rounding only


def test_microvolt_csv_is_scaled_and_lead_names_are_normalised():
    sig = synthetic()
    names = ["Lead I", "lead_ii", "III", "AVR", "aVL", "avf"] + [f"V{i}" for i in range(1, 7)]
    w = waveform.decode_waveform(csv_bytes(sig * 1000, units="uV", leads=names))
    assert np.allclose(w.signals, sig, atol=1e-3)


def test_incomplete_or_bad_ecgs_are_refused():
    sig = synthetic()
    with pytest.raises(waveform.UnsupportedWaveform, match="missing leads: V6"):
        waveform.decode_waveform(csv_bytes(sig[:11], leads=waveform.LEADS[:11]))
    with pytest.raises(waveform.UnsupportedWaveform, match="between 2 seconds"):
        waveform.decode_waveform(csv_bytes(sig[:, :500]))
    with pytest.raises(waveform.UnsupportedWaveform):
        waveform.decode_waveform(b"")


def test_detection_tells_ecgs_from_images():
    assert waveform.is_waveform(csv_bytes(synthetic()))
    assert waveform.is_waveform(ecg_dicom(synthetic(), 500))
    buf = io.BytesIO(); Image.new("L", (8, 8)).save(buf, format="PNG")
    assert not waveform.is_waveform(buf.getvalue())
    assert not waveform.is_waveform(b"a,b,c\n1,2,3")


def test_render_is_the_same_size_with_and_without_saliency():
    w = waveform.decode_waveform(csv_bytes(synthetic()))
    plain = Image.open(io.BytesIO(waveform.render(w)))
    shaded = Image.open(io.BytesIO(waveform.render(w, saliency=np.linspace(0, 1, 50))))
    assert plain.size == shaded.size and plain.size[0] > 1000


@pytest.fixture()
def client(tmp_path, monkeypatch):
    torch.manual_seed(0)
    torch.save(ResNet1d(len(LABELS)).state_dict(), tmp_path / ecg_rhythm.WEIGHTS_FILE)
    (tmp_path / ecg_rhythm.META_FILE).write_text(json.dumps(
        {"version": "test", "labels": LABELS, "fs": 100, "seconds": 10, "clip_mv": 5}))
    monkeypatch.setenv("AEGLE_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("AEGLE_INFERENCE_TOKEN", TOKEN)
    from app.main import app
    with TestClient(app, headers=AUTH) as c:
        yield c


def test_ecg_model_predicts_independent_probabilities_with_a_saliency_trace(client):
    r = client.post("/v1/models/ecg-rhythm/predict", files={"file": ("x.dcm", ecg_dicom(synthetic(), 500))})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["model"]["modality"] == "ECG" and body["model"]["body_part"] is None
    assert {p["label"] for p in body["predictions"]} == set(LABELS)
    assert body["heatmap"]["method"] == "grad-cam-1d"


def test_ecg_model_rejects_images_and_render_draws_ecgs(client):
    buf = io.BytesIO(); Image.new("L", (64, 64)).save(buf, format="PNG")
    assert client.post("/v1/models/ecg-rhythm/predict", files={"file": ("x.png", buf.getvalue())}).status_code == 422
    r = client.post("/v1/render", files={"file": ("x.csv", csv_bytes(synthetic()))})
    assert r.status_code == 200 and Image.open(io.BytesIO(r.content)).mode == "RGB"
