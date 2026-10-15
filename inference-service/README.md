# Aegle inference service

Python (FastAPI + PyTorch) service that runs the registered models. The Core
API calls it over HTTPS; browsers never talk to it directly. Uploads are decoded
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
.venv/bin/python -m training.prepare_pneumonia   # index.csv: patient ids and splits
.venv/bin/python -m training.train_pneumonia
```

Writes `../saved-model/pneumonia-resnet18.pt` and `.json` (weights plus
metadata including test metrics). Kaggle's test folder is the test set.
Validation is split **by patient** from the training folder, because many
patients have several images and an image-level split would leak. Kaggle's own
split is not by patient: 170 children have films in both train and test, and
are left out of training.

### Model #1 results and known limitations (v0.2.0)

Held-out Kaggle test set (624 images, 427 children; most likely label):

| Version | AUC | Sensitivity | Specificity | Balanced accuracy | False positives |
|---|---|---|---|---|---|
| v0.1.0 | 0.968 | 0.990 | 0.667 | 0.828 | 78 of 234 normals |
| v0.2.0 | 0.974 | 0.997 | 0.727 | 0.862 | 64 of 234 normals |

v0.2.0 uses the shared training (`training/common.py`), drops horizontal flips
(a mirrored chest film puts the heart on the right) and no longer trains on
children who are in the test set. A trivial model on image size and colour
scores AUC 0.52 on the same test set, so the result does not rest on how the
films were taken.

Treat this as a research prototype, not a usable clinical model:

- **Validation is not trustworthy.** Patient-level validation balanced accuracy
  is 99.8%, far above test. Kaggle's test films were drawn separately and
  differ from its training films; validation cannot see that shift.
- **Low specificity.** It over-calls pneumonia (a quarter of normal test images
  flagged), which would flood a triage worklist.
- **Calibration does not transfer.** The temperature fitted on validation is
  about 1, so probabilities stay overconfident on the test films (calibration
  error 0.084).
- **Grad-CAM showed shortcut learning in v0.1.** On one confidently-predicted
  pneumonia case the strongest activation was in the image corner, outside the
  body. Heatmaps must be shown to clinicians as an aid, never as proof.
- **Pediatric, single-centre data.** No adult or external validation.

Next steps for this model: adult multi-centre data (CheXpert, NIH ChestX-ray14,
MIMIC-CXR), lung segmentation or cropping before classification to remove
border and marker cues, and external validation.

## Train model #2 (brain MRI tumour type)

Data: the Figshare brain tumour dataset (Cheng et al., CC BY 4.0): 3,064 contrast T1
slices from 233 patients at two Chinese hospitals, each showing a meningioma, glioma
or pituitary tumour, with an expert tumour outline. Download the four
`brainTumorDataPublic_*.zip` files and `cvind.mat` from figshare article 1512427 and
unzip them into `../dataset/brain_tumor_figshare/raw/mat/`, then:

```bash
.venv/bin/python -m training.prepare_brain_tumor   # .mat -> PNG, masks, index.csv
.venv/bin/python -m training.train_brain_tumor
```

Train, validation and test are split by patient (165/34/34).

### Model #2 results and known limitations (v0.2.0)

Held-out test patients (34 patients, 457 slices; the same patients as v0.1):

| Accuracy | Balanced accuracy | Macro AUC | Calibration error (ECE) |
|---|---|---|---|
| 0.928 | 0.934 | 0.992 | 0.019 |

| True type | Slices | Sensitivity | Precision |
|---|---|---|---|
| Meningioma | 104 | 0.962 | 0.794 |
| Glioma | 227 | 0.912 | 0.981 |
| Pituitary | 126 | 0.929 | 0.975 |

v0.2 trains on the slices at their full 512 px (v0.1 shrank them to 224) and fits a
temperature on validation, which cut the calibration error from 0.068 to 0.019; balanced
accuracy is unchanged (0.936 in v0.1).

- **It does not detect tumours.** Every training slice contains one, so on a scan
  without a tumour it still names a type, confidently. Only use it on slices a
  radiologist has already identified as showing a tumour.
- **It mostly looks at context, not the tumour.** Using the expert outlines, only
  8% of Grad-CAM attention falls on the tumour (which covers 2% of the slice; v0.1: 5%),
  and the heatmap's peak is within 7 mm of the tumour in 51% of slices (89% for
  meningioma, 29% for pituitary). The dataset mixes axial, coronal and sagittal slices, and plane and
  anatomy correlate with tumour type; the model appears to use them. Expect it to
  fail on other hospitals' protocols.
- **The costly error is glioma called meningioma** (20 of 227 glioma slices; v0.1: 29).
- **Two hospitals, 2005-2010, one sequence.** No external validation.

Next steps: tumour-centred crops or segmentation-guided training so the classifier
has to look at the lesion, a "no tumour" class from another source, 3D volumes
instead of single slices, and validation on another centre.

## Run

```bash
export AEGLE_INFERENCE_TOKEN=...   # same value the Core API uses, at least 32 chars
.venv/bin/uvicorn app.main:app --port 8000 \
    --ssl-keyfile ../infra/tls/certs/server.key --ssl-certfile ../infra/tls/certs/server.crt
```

TLS certificates come from `../infra/tls/generate.sh`; the Core API calls
`https://localhost:8000` by default.

`/v1/*` requires `Authorization: Bearer $AEGLE_INFERENCE_TOKEN`; without a token
configured the service refuses to start. `/health` stays open for probes.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Loaded and unavailable models |
| `GET /v1/models` | Model info: modality, intended use, version, weights hash, metrics |
| `POST /v1/render` | Multipart `file` → PNG for display (DICOM windowing and MONOCHROME1 handled) |
| `POST /v1/models/{id}/predict` | Multipart `file` (PNG, JPEG, TIFF or DICOM). `?heatmap=false` skips Grad-CAM |

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
