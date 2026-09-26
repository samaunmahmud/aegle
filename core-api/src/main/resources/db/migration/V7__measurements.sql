-- Quantities a model measures (e.g. wound area), kept per study so a patient's values can
-- be followed across visits.
CREATE TABLE measurements (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     uuid NOT NULL REFERENCES organizations(id),
    study_id   uuid NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
    job_id     uuid NOT NULL REFERENCES inference_jobs(id) ON DELETE CASCADE,
    name       text NOT NULL,
    value      double precision NOT NULL,
    unit       text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX measurements_study ON measurements (study_id);

ALTER TABLE measurements ENABLE ROW LEVEL SECURITY;
ALTER TABLE measurements FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON measurements
    USING (org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid);
