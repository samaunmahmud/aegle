-- Aegle core schema (PostgreSQL 16)
--
-- Tenancy: every tenant-scoped table has org_id and row-level security (RLS).
-- The application sets `SET LOCAL app.current_org_id = '<uuid>'` per transaction.
-- The app must connect as `aegle_app` (not the owner/superuser), because
-- superusers bypass RLS.
--
-- PHI: patient identifiers are stored encrypted by the application (bytea),
-- in one table. Everything else references patients.id only.

-- ---------------------------------------------------------------- tenancy
CREATE TABLE organizations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id),
    idp_subject   text NOT NULL UNIQUE,          -- Keycloak 'sub' claim
    email         text NOT NULL,
    full_name     text NOT NULL,
    role          text NOT NULL CHECK (role IN ('ADMIN', 'RADIOLOGIST', 'PHYSICIAN', 'AUDITOR')),
    active        boolean NOT NULL DEFAULT true,
    last_login_at timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, email)
);

-- --------------------------------------------------------------- patients
CREATE TABLE patients (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         uuid NOT NULL REFERENCES organizations(id),
    mrn_encrypted  bytea NOT NULL,               -- medical record number
    mrn_hash       bytea NOT NULL,               -- keyed hash for lookup without decrypting
    name_encrypted bytea,
    dob_encrypted  bytea,
    sex            text CHECK (sex IN ('F', 'M', 'O', 'U')),
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, mrn_hash)
);

-- ------------------------------------------------------------ model registry
-- Global (not tenant-scoped): the platform's catalogue of models.
CREATE TABLE ai_models (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name         text NOT NULL UNIQUE,
    modality     text NOT NULL,                  -- XR, CT, MR, US, DOC ...
    body_part    text,
    task         text NOT NULL,                  -- classification, segmentation, extraction
    intended_use text NOT NULL,                  -- regulatory-relevant statement
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE model_versions (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id                 uuid NOT NULL REFERENCES ai_models(id),
    version                  text NOT NULL,
    artifact_uri             text NOT NULL,
    input_spec               jsonb NOT NULL DEFAULT '{}',
    validation_metrics       jsonb NOT NULL DEFAULT '{}',
    approved_by              uuid REFERENCES users(id),
    approved_at              timestamptz,
    active                   boolean NOT NULL DEFAULT false,
    created_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (model_id, version)
);
-- At most one active version per model.
CREATE UNIQUE INDEX model_versions_one_active
    ON model_versions (model_id) WHERE active;

-- ---------------------------------------------------------- clinical data
CREATE TABLE studies (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES organizations(id),
    patient_id    uuid NOT NULL REFERENCES patients(id),
    modality      text NOT NULL,
    body_part     text,
    accession_no  text,
    source        text NOT NULL CHECK (source IN ('UPLOAD', 'DICOM', 'DICOMWEB')),
    study_date    date,
    status        text NOT NULL DEFAULT 'RECEIVED'
                  CHECK (status IN ('RECEIVED', 'QUEUED', 'ANALYZING', 'READY', 'REVIEWED', 'FAILED')),
    uploaded_by   uuid NOT NULL REFERENCES users(id),
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX studies_org_patient ON studies (org_id, patient_id);

CREATE TABLE instances (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid NOT NULL REFERENCES organizations(id),
    study_id        uuid NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    storage_key     text NOT NULL,               -- object-store key, never a file path
    sha256          text NOT NULL,
    mime_type       text NOT NULL,
    size_bytes      bigint NOT NULL,
    dicom_sop_uid   text,
    dicom_meta      jsonb NOT NULL DEFAULT '{}', -- de-identified header subset
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX instances_study ON instances (study_id);

CREATE TABLE documents (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id              uuid NOT NULL REFERENCES organizations(id),
    study_id            uuid REFERENCES studies(id) ON DELETE SET NULL,
    patient_id          uuid NOT NULL REFERENCES patients(id),
    doc_type            text NOT NULL,           -- LAB_REPORT, DISCHARGE_SUMMARY, ...
    storage_key         text NOT NULL,
    extracted_text_key  text,
    extraction_status   text NOT NULL DEFAULT 'PENDING'
                        CHECK (extraction_status IN ('PENDING', 'DONE', 'FAILED')),
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- -------------------------------------------------------------- inference
CREATE TABLE inference_jobs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            uuid NOT NULL REFERENCES organizations(id),
    study_id          uuid NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    model_version_id  uuid NOT NULL REFERENCES model_versions(id),
    status            text NOT NULL DEFAULT 'QUEUED'
                      CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')),
    attempts          int NOT NULL DEFAULT 0,
    error             text,
    queued_at         timestamptz NOT NULL DEFAULT now(),
    started_at        timestamptz,
    finished_at       timestamptz
);
-- Workers poll with FOR UPDATE SKIP LOCKED over this index.
CREATE INDEX inference_jobs_queue ON inference_jobs (queued_at) WHERE status = 'QUEUED';

CREATE TABLE predictions (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id                  uuid NOT NULL REFERENCES organizations(id),
    job_id                  uuid NOT NULL REFERENCES inference_jobs(id) ON DELETE CASCADE,
    label                   text NOT NULL,
    probability             real NOT NULL CHECK (probability BETWEEN 0 AND 1),
    calibrated_probability  real CHECK (calibrated_probability BETWEEN 0 AND 1),
    urgency_class           text NOT NULL DEFAULT 'ROUTINE'
                            CHECK (urgency_class IN ('CRITICAL', 'URGENT', 'ROUTINE')),
    raw_output              jsonb NOT NULL DEFAULT '{}',
    created_at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX predictions_job ON predictions (job_id);

CREATE TABLE heatmaps (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         uuid NOT NULL REFERENCES organizations(id),
    prediction_id  uuid NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    instance_id    uuid NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
    storage_key    text NOT NULL,
    method         text NOT NULL DEFAULT 'grad-cam'
);

CREATE TABLE document_findings (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       uuid NOT NULL REFERENCES organizations(id),
    document_id  uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    entity_type  text NOT NULL,                  -- MEDICATION, DIAGNOSIS, LAB_VALUE ...
    value        text NOT NULL,
    source_span  jsonb NOT NULL,                 -- where in the source text (citation)
    confidence   real CHECK (confidence BETWEEN 0 AND 1)
);

-- ------------------------------------------------------- triage and review
CREATE TABLE worklist_items (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            uuid NOT NULL REFERENCES organizations(id),
    study_id          uuid NOT NULL UNIQUE REFERENCES studies(id) ON DELETE CASCADE,
    priority_score    real NOT NULL,
    priority_reason   jsonb NOT NULL DEFAULT '{}',  -- explains the score to the clinician
    assigned_to       uuid REFERENCES users(id),
    state             text NOT NULL DEFAULT 'OPEN'
                      CHECK (state IN ('OPEN', 'IN_REVIEW', 'DONE')),
    sla_due_at        timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX worklist_queue ON worklist_items (org_id, state, priority_score DESC);

CREATE TABLE clinician_reviews (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         uuid NOT NULL REFERENCES organizations(id),
    prediction_id  uuid NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    reviewer_id    uuid NOT NULL REFERENCES users(id),
    decision       text NOT NULL CHECK (decision IN ('ACCEPT', 'REJECT', 'MODIFY')),
    final_label    text,
    comment        text,
    reviewed_at    timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------- compliance
CREATE TABLE audit_log (
    id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id       uuid NOT NULL,
    actor_id     uuid,
    action       text NOT NULL,                  -- e.g. STUDY_VIEWED, PREDICTION_REVIEWED
    entity_type  text NOT NULL,
    entity_id    text NOT NULL,
    ip           inet,
    user_agent   text,
    details      jsonb NOT NULL DEFAULT '{}',
    at           timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_entity ON audit_log (org_id, entity_type, entity_id);
CREATE INDEX audit_log_actor  ON audit_log (org_id, actor_id, at DESC);

-- Append-only: block UPDATE, DELETE and TRUNCATE for everyone, including the owner.
CREATE FUNCTION audit_log_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END $$;
CREATE TRIGGER audit_log_no_change
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
CREATE TRIGGER audit_log_no_truncate
    BEFORE TRUNCATE ON audit_log
    FOR EACH STATEMENT EXECUTE FUNCTION audit_log_immutable();

-- ------------------------------------------------ row-level security (RLS)
-- current_setting(..., true) returns NULL when unset, so a missing tenant
-- context matches no rows instead of erroring or leaking.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users', 'patients', 'studies', 'instances', 'documents',
        'inference_jobs', 'predictions', 'heatmaps', 'document_findings',
        'worklist_items', 'clinician_reviews', 'audit_log'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I
                 USING (org_id = NULLIF(current_setting(''app.current_org_id'', true), '''')::uuid)
                 WITH CHECK (org_id = NULLIF(current_setting(''app.current_org_id'', true), '''')::uuid)',
            t);
    END LOOP;
END $$;

-- ---------------------------------------------------- application DB role
-- Created NOLOGIN here so no password lives in source control; the deployment
-- sets `ALTER ROLE aegle_app LOGIN PASSWORD '...'`. Not a superuser and does
-- not own the tables, so RLS applies to it.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aegle_app') THEN
        CREATE ROLE aegle_app NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO aegle_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aegle_app;
-- audit_log: the app may only read/insert, never alter history.
REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM aegle_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO aegle_app;
