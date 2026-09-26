-- DICOM ingestion from Orthanc, and browser-viewable previews of DICOM images.

-- Studies received over DICOM have no uploading user.
ALTER TABLE studies ALTER COLUMN uploaded_by DROP NOT NULL;
ALTER TABLE studies
    ADD COLUMN dicom_study_uid  text,
    ADD COLUMN orthanc_study_id text;
-- Ingest each Orthanc study at most once (checked across tenants: unique indexes ignore RLS).
CREATE UNIQUE INDEX studies_orthanc_study ON studies (orthanc_study_id) WHERE orthanc_study_id IS NOT NULL;

-- PNG rendering of a DICOM instance, made on first view (object-store key).
ALTER TABLE instances ADD COLUMN preview_key text;

-- Which organisation a DICOM sender belongs to, by its calling AE title. Global, not
-- tenant-scoped: ingestion must look it up before it knows the tenant. Admins manage
-- their own organisation's rows through the API, which filters by org_id itself.
CREATE TABLE dicom_sources (
    ae_title    text PRIMARY KEY CHECK (ae_title ~ '^[!-~]([ -~]{0,14}[!-~])?$'),   -- DICOM AE: 1-16 printable
    org_id      uuid NOT NULL REFERENCES organizations(id),
    description text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX dicom_sources_org ON dicom_sources (org_id);

-- Position in Orthanc's change log up to which studies have been ingested.
CREATE TABLE dicom_ingest_cursor (
    id          int PRIMARY KEY CHECK (id = 1),
    last_change bigint NOT NULL
);
INSERT INTO dicom_ingest_cursor (id, last_change) VALUES (1, 0);
