# Developer tools (local only)

Helpers used to train, verify and demo Aegle on a developer machine. Not part of any
deployed service; demo logins and paths are for the local dev stack.

| Script | Use |
|---|---|
| `login.py USER PASSWORD CA` | Signs in through Keycloak's browser flow (auth code + PKCE) and prints an access token |
| `shots.py OUTDIR [page ...]` | Screenshots every page as each role via Playwright (`pip install playwright && playwright install chromium`) |
| `seed_demo.py API TOKENFILE CA` | Uploads one held-out case per specialty to a running stack |
| `seed_clinic.py` | Fills the dev clinic: ~40 fictional patients, ~60 held-out studies through the real pipeline, signed reports, and consult threads between the demo doctors (run from `inference-service/` with its venv) |
| `send_cxr.py CERTS JPEG AET MRN` | Acts as a CR modality: sends a chest X-ray as DICOM over mutual TLS |
| `send_ct_series.py CERTS DATADIR PATIENT AET MRN` | Sends a held-out head CT patient as one DICOM CT series (series import only: the stroke model is withdrawn) |
| `train_queue*.sh` | Train the models one after another; logs in `$AEGLE_LOG_DIR` (default /tmp/aegle-training) |

The DICOM senders need `pip install pynetdicom pydicom pillow numpy` and the modality
certificate from `infra/tls/generate.sh`.
