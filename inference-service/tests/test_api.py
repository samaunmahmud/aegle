"""API and imaging tests. Run with: pytest

Uses a tiny randomly-initialised model written to a temp dir, so the tests need
neither the dataset nor trained weights and run in seconds.
"""
import base64
import io
import json

import numpy as np
import pytest
import torch
from fastapi.testclient import TestClient
from PIL import Image

from app import imaging
from app.models import brain_mri_tumor as bmt
from app.models import chest_xray_pneumonia as cxp
from app.models.resnet import IMAGENET_MEAN, IMAGENET_STD, build_resnet18

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(scope="module")
def client(tmp_path_factory, monkeypatch_module):
    model_dir = tmp_path_factory.mktemp("models")
    torch.manual_seed(0)
    torch.save(build_resnet18(2).state_dict(), model_dir / cxp.WEIGHTS_FILE)
    (model_dir / cxp.META_FILE).write_text(json.dumps({
        "version": "test", "labels": ["NORMAL", "PNEUMONIA"], "input_size": 64,
        "mean": IMAGENET_MEAN, "std": IMAGENET_STD,
    }))
    torch.save(build_resnet18(3).state_dict(), model_dir / bmt.WEIGHTS_FILE)
    (model_dir / bmt.META_FILE).write_text(json.dumps({
        "version": "test", "labels": ["MENINGIOMA", "GLIOMA", "PITUITARY"], "input_size": 64,
        "mean": IMAGENET_MEAN, "std": IMAGENET_STD,
    }))
    monkeypatch_module.setenv("AEGLE_MODEL_DIR", str(model_dir))
    monkeypatch_module.setenv("AEGLE_INFERENCE_TOKEN", TOKEN)
    from app.main import app
    with TestClient(app, headers=AUTH) as c:
        yield c


@pytest.fixture(scope="module")
def monkeypatch_module():
    with pytest.MonkeyPatch.context() as mp:
        yield mp


def png_bytes(size=(120, 90)) -> bytes:
    arr = (np.random.RandomState(1).rand(size[1], size[0]) * 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def test_health_reports_loaded_model(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert sorted(body["models_loaded"]) == ["brain-mri-tumor-type", "chest-xray-pneumonia"]


def test_list_models_exposes_intended_use_and_hash(client):
    models = {m["id"]: m for m in client.get("/v1/models").json()["models"]}
    assert (models["chest-xray-pneumonia"]["modality"], models["chest-xray-pneumonia"]["body_part"]) == ("XR", "CHEST")
    assert (models["brain-mri-tumor-type"]["modality"], models["brain-mri-tumor-type"]["body_part"]) == ("MR", "BRAIN")
    for m in models.values():
        assert m["intended_use"] and len(m["weights_sha256"]) == 64
    # The tumour model must say plainly that it cannot detect whether a tumour is present.
    assert "cannot tell whether a tumour is present" in models["brain-mri-tumor-type"]["intended_use"]


def test_brain_model_returns_the_three_tumour_types(client):
    r = client.post("/v1/models/brain-mri-tumor-type/predict",
                    files={"file": ("x.png", png_bytes((96, 96)), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert {p["label"] for p in body["predictions"]} == {"MENINGIOMA", "GLIOMA", "PITUITARY"}
    assert abs(sum(p["probability"] for p in body["predictions"]) - 1) < 1e-3
    assert body["heatmap"]["target_label"] == body["top_label"]


def test_predict_returns_sorted_probabilities_and_heatmap(client):
    r = client.post("/v1/models/chest-xray-pneumonia/predict",
                    files={"file": ("x.png", png_bytes(), "image/png")})
    assert r.status_code == 200
    body = r.json()
    probs = [p["probability"] for p in body["predictions"]]
    assert probs == sorted(probs, reverse=True)
    assert abs(sum(probs) - 1) < 1e-3
    assert body["top_label"] == body["predictions"][0]["label"]
    heat = Image.open(io.BytesIO(base64.b64decode(body["heatmap"]["image_base64"])))
    assert heat.size == (120, 90)          # overlay matches the original image size


def test_heatmap_can_be_disabled(client):
    r = client.post("/v1/models/chest-xray-pneumonia/predict?heatmap=false",
                    files={"file": ("x.png", png_bytes(), "image/png")})
    assert r.status_code == 200 and r.json()["heatmap"] is None


@pytest.mark.parametrize("auth", [None, "Bearer wrong-token", f"Basic {TOKEN}", TOKEN])
def test_model_endpoints_require_the_service_token(client, auth):
    headers = {"Authorization": auth} if auth else {"Authorization": ""}
    assert client.get("/v1/models", headers=headers).status_code == 401
    r = client.post("/v1/models/chest-xray-pneumonia/predict", headers=headers,
                    files={"file": ("x.png", png_bytes(), "image/png")})
    assert r.status_code == 401


@pytest.mark.parametrize("token", [None, "too-short"])
def test_service_refuses_to_start_without_a_strong_token(monkeypatch, token):
    if token is None:
        monkeypatch.delenv("AEGLE_INFERENCE_TOKEN", raising=False)
    else:
        monkeypatch.setenv("AEGLE_INFERENCE_TOKEN", token)
    from app.main import app
    with pytest.raises(RuntimeError, match="AEGLE_INFERENCE_TOKEN"):
        with TestClient(app):
            pass


def test_render_turns_dicom_into_a_png(client):
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.Rows, ds.Columns = 20, 30
    ds.SamplesPerPixel, ds.BitsAllocated, ds.BitsStored, ds.HighBit = 1, 16, 12, 11
    ds.PixelRepresentation = 0
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelData = np.tile(np.arange(30, dtype=np.uint16) * 100, (20, 1)).tobytes()
    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds)

    r = client.post("/v1/render", files={"file": ("x.dcm", buf.getvalue())})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    png = Image.open(io.BytesIO(r.content))
    assert png.size == (30, 20) and png.mode == "L"


def test_render_rejects_non_images_and_needs_the_token(client):
    assert client.post("/v1/render", files={"file": ("x.bin", b"nope")}).status_code == 422
    r = client.post("/v1/render", headers={"Authorization": ""}, files={"file": ("x.png", png_bytes())})
    assert r.status_code == 401


def test_unknown_model_is_404(client):
    r = client.post("/v1/models/nope/predict", files={"file": ("x.png", png_bytes(), "image/png")})
    assert r.status_code == 404


@pytest.mark.parametrize("payload", [b"", b"not an image at all"])
def test_bad_upload_is_422(client, payload):
    r = client.post("/v1/models/chest-xray-pneumonia/predict", files={"file": ("x.bin", payload)})
    assert r.status_code == 422


def test_missing_weights_gives_503(tmp_path, monkeypatch):
    monkeypatch.setenv("AEGLE_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("AEGLE_INFERENCE_TOKEN", TOKEN)
    from app.main import app
    with TestClient(app, headers=AUTH) as c:
        assert c.get("/health").json()["status"] == "degraded"
        r = c.post("/v1/models/chest-xray-pneumonia/predict",
                   files={"file": ("x.png", png_bytes(), "image/png")})
        assert r.status_code == 503


def test_dicom_monochrome1_is_inverted_and_decoded():
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, generate_uid

    def make(photometric):
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.1"
        meta.MediaStorageSOPInstanceUID = generate_uid()
        ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
        ds.Rows, ds.Columns = 32, 32
        ds.SamplesPerPixel, ds.BitsAllocated, ds.BitsStored, ds.HighBit = 1, 16, 16, 15
        ds.PixelRepresentation = 0
        ds.PhotometricInterpretation = photometric
        ds.PixelData = np.tile(np.arange(32, dtype=np.uint16) * 100, (32, 1)).tobytes()
        buf = io.BytesIO()
        pydicom.dcmwrite(buf, ds)
        return buf.getvalue()

    mono2 = np.asarray(imaging.decode_image(make("MONOCHROME2")))[..., 0].astype(int)
    mono1 = np.asarray(imaging.decode_image(make("MONOCHROME1")))[..., 0].astype(int)
    assert mono2.shape == (32, 32)
    assert mono2[0, 0] < mono2[0, -1]          # MONOCHROME2: brighter to the right
    assert mono1[0, 0] > mono1[0, -1]          # MONOCHROME1: inverted


def test_decode_rejects_oversized_upload():
    with pytest.raises(imaging.UnsupportedImage):
        imaging.decode_image(b"\0" * (imaging.MAX_UPLOAD_BYTES + 1))


def test_colour_is_preserved_for_colour_images_and_grayscale_stays_gray():
    rgb = np.zeros((10, 12, 3), np.uint8); rgb[..., 0] = 200; rgb[..., 2] = 40
    buf = io.BytesIO(); Image.fromarray(rgb).save(buf, format="PNG")
    out = np.asarray(imaging.decode_image(buf.getvalue()))
    assert out.shape == (10, 12, 3) and out[0, 0].tolist() == [200, 0, 40]
    assert not imaging.is_grayscale(imaging.decode_image(buf.getvalue()))
    assert imaging.is_grayscale(imaging.decode_image(png_bytes()))


def test_render_keeps_colour(client):
    rgb = np.zeros((8, 8, 3), np.uint8); rgb[..., 1] = 180
    buf = io.BytesIO(); Image.fromarray(rgb).save(buf, format="PNG")
    r = client.post("/v1/render", files={"file": ("x.png", buf.getvalue())})
    assert Image.open(io.BytesIO(r.content)).mode == "RGB"
