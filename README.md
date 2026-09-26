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
6. Every service call is authenticated: browsers present Keycloak tokens whose audience
   must be `aegle-api`; the Core API presents a shared secret (`AEGLE_INFERENCE_TOKEN`)
   to the inference service, which refuses to start without one. Deactivated users
   (`users.active = false`) are refused within a minute, whatever their token says.
7. The audit log is append-only and tamper-evident: each organisation's entries form a
   SHA-256 hash chain. `GET /api/audit/verify` (auditors and admins; "Verify integrity"
   on the audit page) recomputes it and returns the head hash to record elsewhere.
8. Per-user rate limits (300 requests and 30 uploads per minute by default), kept in
   Postgres so they hold across any number of API instances, and strict security
   headers (deny-all CSP, no framing, HSTS) on every API response.

## Local development

```bash
cp .env.example .env          # then change the values
infra/tls/generate.sh         # local dev CA + certificates (once)
set -a; source .env; set +a   # in every shell that starts a service below
docker compose up -d          # Postgres :5433, MinIO :9000/:9001, Orthanc :8042, Keycloak :8443
cd core-api && SPRING_PROFILES_ACTIVE=dev mvn spring-boot:run   # https://localhost:8090
cd inference-service && .venv/bin/uvicorn app.main:app --port 8000 \
    --ssl-keyfile ../infra/tls/certs/server.key --ssl-certfile ../infra/tls/certs/server.crt
cd frontend && npm install && npm run dev                       # https://localhost:5173
```

### TLS

Every connection is encrypted, including the internal ones: browser to frontend and
Keycloak, core-api to Postgres (`sslmode=verify-full`; the server's `pg_hba.conf`
refuses non-TLS connections), MinIO, Keycloak and the inference service, and Orthanc's
HTTP/DICOMweb API. No service answers plain HTTP.

DICOM on port 4242 is mutual TLS: a sending modality must present a certificate issued
by the CA, or Orthanc drops the association. `generate.sh` issues a sample one
(`certs/modality.crt` and `.key`); issue one per real modality the same way.

`infra/tls/generate.sh` creates a private development CA and one certificate for
`localhost` and the compose service names, in the git-ignored `infra/tls/certs/`.
`mvn spring-boot:run` makes core-api trust it through `certs/truststore.p12`. To let
your browser trust it (macOS; Firefox keeps its own store):

```bash
security add-trusted-cert -r trustRoot -k ~/Library/Keychains/login.keychain-db infra/tls/certs/ca.crt
```

Production uses real certificates from a secret store instead; the dev CA key sits on
disk next to the certificates and must never be trusted outside development.

### DICOM from modalities

Modalities and PACS send to Orthanc (C-STORE, port 4242, mutual TLS). core-api follows
Orthanc's change log and, once a study is complete (`StableStudy`, after Orthanc's
`STABLE_AGE`, 10 s in dev), imports it into the organisation that registered the
sender's calling AE title: patient identifiers are encrypted as for uploads, images go to
object storage with a de-identified header subset, matching models are queued, and the
study appears in the worklist. Admins register AE titles on the "DICOM senders" page
(`/api/admin/dicom-sources`); the dev seed registers `AEGLE_DEV_CR` for the demo clinic.

- Studies from unregistered AE titles, or without a PatientID, are left in Orthanc and
  logged; registering the title later does not import them retroactively (re-send them).
- Each Orthanc study is imported once. Instances that arrive after the import are not
  added; configure modalities to send a study in one association.
- An AE title is claimed by the sender itself. The TLS certificate proves the sender is
  one of yours, not which AE title it may use, so issue certificates only to devices you
  would trust with any of your organisation's titles.
- Browsers cannot display DICOM: the image endpoint returns a PNG rendered by the
  inference service on first view and kept in object storage next to the original.

### Production-style frontend

```bash
docker compose --profile web up -d --build web   # https://localhost:5443
```

nginx serves the built app with the full header set (including the CSP, generated from
`frontend/security-headers.ts`, the same source the Vite servers use) and proxies `/api`
to core-api over verified TLS (`AEGLE_API_UPSTREAM`, default
`https://host.docker.internal:8090`). It replaces any client-sent `X-Forwarded-For`;
core-api only believes that header from `AEGLE_TRUSTED_PROXIES` (a regex, loopback by
default), so audit entries record the real client address and nobody else can forge it.

If a port is taken by something else, override it: `AEGLE_API_PORT` for core-api,
`AEGLE_API_URL` for where the frontend proxies to, and a full `AEGLE_DB_URL` (keep the
`sslmode` and `sslrootcert` parameters) for the database.

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
