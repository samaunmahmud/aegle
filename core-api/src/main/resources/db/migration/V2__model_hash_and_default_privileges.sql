-- Record the exact weights that produced predictions, not just a version label.
ALTER TABLE model_versions ADD COLUMN weights_sha256 text;

CREATE INDEX inference_jobs_study ON inference_jobs (study_id);

-- Tables created by later migrations are usable by the application role.
-- (audit_log's restrictions are set explicitly in V1 and are not affected.)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aegle_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO aegle_app;
