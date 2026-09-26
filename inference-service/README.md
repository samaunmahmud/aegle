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

### Model #1 results and known limitations (v0.1.0)

Held-out Kaggle test set (624 images, threshold 0.5):

| AUC | Sensitivity | Specificity | Accuracy | False positives |
|---|---|---|---|---|
| 0.968 | 0.990 | 0.667 | 0.869 | 78 of 234 normals |

Treat this as a research prototype, not a usable clinical model:

- **Validation is not trustworthy.** Patient-level validation AUC was 0.999
  with 100% specificity, far above test performance. The train and validation
  images come from the same source, and normal and pneumonia images in this
  dataset differ in ways unrelated to disease (scanner, positioning, markers).
- **Grad-CAM shows shortcut learning.** On one confidently-predicted pneumonia
  case the strongest activation was in the image corner, outside the body.
  Heatmaps must be shown to clinicians as an aid, never as proof of the finding.
- **Low specificity.** It over-calls pneumonia (a third of normal test images
  flagged), which would flood a triage worklist.
- **Pediatric, single-centre data.** No adult or external validation.

Next steps for this model: adult multi-centre data (CheXpert, NIH ChestX-ray14,
MIMIC-CXR), lung segmentation or cropping before classification to remove
border and marker cues, probability calibration, and external validation.

## Run

```bash
export AEGLE_INFERENCE_TOKEN=...   # same value the Core API uses, at least 32 chars
.venv/bin/uvicorn app.main:app --port 8000
```

`/v1/*` requires `Authorization: Bearer $AEGLE_INFERENCE_TOKEN`; without a token
configured the service refuses to start. `/health` stays open for probes.

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
