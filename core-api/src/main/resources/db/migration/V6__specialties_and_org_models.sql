-- Clinical specialties, and per-organisation control over which AI models run.

-- The specialty a study or model belongs to, from its DICOM modality and body part.
-- One definition, used by the worklist filter, the study list and the model registry.
--   ECG waveforms, cardiac ultrasound (echo)           -> CARDIOLOGY
--   XC external photography, skin and wounds           -> DERMATOLOGY
--   OP/OPT ophthalmic photography and OCT               -> OPHTHALMOLOGY
--   SM slide microscopy, GM general microscopy          -> PATHOLOGY
--   ES endoscopy                                        -> GASTROENTEROLOGY
--   EEG, and CT/MR of the brain                         -> NEUROLOGY
--   everything else (XR, CT, MR, US ...)                -> RADIOLOGY
CREATE FUNCTION aegle_specialty(modality text, body_part text) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE
        WHEN upper(modality) = 'ECG' OR (upper(modality) = 'US' AND upper(body_part) = 'HEART') THEN 'CARDIOLOGY'
        WHEN upper(modality) = 'XC' OR upper(body_part) IN ('SKIN', 'WOUND') THEN 'DERMATOLOGY'
        WHEN upper(modality) IN ('OP', 'OPT') OR upper(body_part) IN ('EYE', 'RETINA') THEN 'OPHTHALMOLOGY'
        WHEN upper(modality) IN ('SM', 'GM') THEN 'PATHOLOGY'
        WHEN upper(modality) = 'ES' THEN 'GASTROENTEROLOGY'
        WHEN upper(modality) = 'EEG'
             OR (upper(modality) IN ('CT', 'MR') AND upper(body_part) IN ('BRAIN', 'HEAD')) THEN 'NEUROLOGY'
        ELSE 'RADIOLOGY'
    END
$$;

-- A hospital can switch off a model the platform offers (its own clinical governance
-- may not have signed it off). No row means the model runs for that organisation.
CREATE TABLE org_model_settings (
    org_id     uuid NOT NULL REFERENCES organizations(id),
    model_id   uuid NOT NULL REFERENCES ai_models(id),
    enabled    boolean NOT NULL,
    changed_by uuid REFERENCES users(id),
    changed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (org_id, model_id)
);
ALTER TABLE org_model_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_model_settings FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON org_model_settings
    USING (org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.current_org_id', true), '')::uuid);
