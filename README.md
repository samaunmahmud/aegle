# Aegle

Clinical decision support for doctors and radiologists: AI-assisted triage and
second opinions across medical images and reports. Aegle is a tool for
clinicians only. It suggests, the clinician decides.

> Status: early development. Not a medical device and not for clinical use.

## Architecture

```
 Clinician (React SPA, OIDC login)
        │ HTTPS
        ▼
 Core API (Spring Boot) ──── PostgreSQL (metadata, worklist, audit; row-level security)
        │ enqueue job          │ signed URLs
        ▼                      ▼
   Job queue              Object storage (MinIO / S3, encrypted)
        │
        ▼
 Inference workers (Python / FastAPI): one adapter per registered model
   → probabilities + Grad-CAM heatmap + model version

 Orthanc  – DICOM server (C-STORE / DICOMweb)
 Keycloak – identity provider (OIDC, MFA)
```

Aegle is a platform of pluggable models. Each model is registered with a
modality, body part, task and intended use. The chest X-ray pneumonia
classifier is model #1; its original Java/DL4J prototype is documented in
[docs/pneumonia-prototype.md](docs/pneumonia-prototype.md).

Design rules:

1. Multi-tenant from day one: every tenant table has `org_id` and Postgres RLS.
2. Patient identifiers are encrypted and isolated in one table; the AI pipeline sees internal IDs only.
3. AI output is a suggestion; every prediction has a clinician review state.
4. Every prediction records the exact model version.
5. The triage score is explainable (`worklist_items.priority_reason`).

## Local development

```bash
cp .env.example .env          # then change the values
docker compose up -d          # Postgres :5433, MinIO :9000/:9001, Orthanc :8042, Keycloak :8080
cd core-api && SPRING_PROFILES_ACTIVE=dev mvn spring-boot:run   # :8090
cd inference-service && uvicorn app.main:app --port 8000
cd frontend && npm install && npm run dev                       # :5173
```

The schema lives in `core-api/src/main/resources/db/migration/`. The application must
connect as the `aegle_app` role (created by the migration, `NOLOGIN` until you
give it a password) because superusers bypass row-level security:

```sql
ALTER ROLE aegle_app LOGIN PASSWORD '...';
```

Per transaction, the API sets the tenant with
`SET LOCAL app.current_org_id = '<uuid>'`. With no tenant set, queries return
no rows.

See `frontend/README.md` for demo logins and a gotcha around Keycloak's
dev-mode storage not surviving container restarts.

## Data policy

Never commit patient or imaging data, datasets, or model weights.
`.gitignore` excludes `dataset/`, `saved-model/`, `*.dcm` and model files.

## Roadmap

1. Architecture and database design — done
2. Backend API and inference pipeline — done
3. Frontend dashboard and triage worklist — done (worklist, upload, study
   detail with Grad-CAM overlay, clinician review, audit log)
4. Security and compliance — ongoing
5. Additional disease models beyond chest X-ray pneumonia (the platform
   supports this via the inference service's adapter registry, but each
   model needs its own dataset, training and validation work)
