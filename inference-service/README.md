# Aegle inference service

Python (FastAPI + PyTorch) service that runs the registered models. The Core
API calls it over HTTP; browsers never talk to it directly. Uploads are decoded
in memory and are not written to disk or logged.

## Setup

```bash
cd inference-service
python3.11 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

## Train model #1 (chest X-ray pneumonia)

Needs the Kaggle dataset under `../dataset/chest_xray/`.

```bash
.venv/bin/python -m training.train_pneumonia
```

Writes `../saved-model/pneumonia-resnet18.pt` and `.json` (weights plus
metadata including test metrics). Validation is split **by patient**, because
many patients have several images and an image-level split would leak.

## Run

```bash
.venv/bin/uvicorn app.main:app --port 8000
```

| Endpoint | Purpose |
|---|---|
| `GET /health` | Loaded and unavailable models |
| `GET /v1/models` | Model info: modality, intended use, version, weights hash, metrics |
| `POST /v1/models/{id}/predict` | Multipart `file` (PNG, JPEG or DICOM). `?heatmap=false` skips Grad-CAM |

Response fields map onto the database: `predictions[]` → `predictions`,
`heatmap` → `heatmaps`, `model.version` + `weights_sha256` → `model_versions`.
Urgency and triage priority are decided by the Core API, not by the model.

If a model has no weights, it is listed under `models_unavailable` in
`/health` and `predict` returns 503.

## Add a model

1. Write an adapter implementing `ModelAdapter` in `app/models/`.
2. Add it to `ADAPTERS` in `app/registry.py`.
3. Give it an honest `intended_use`.

## Tests

```bash
.venv/bin/python -m pytest
```

Tests use a tiny random model, so they need neither the dataset nor weights.
