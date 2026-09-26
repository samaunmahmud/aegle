-- DEV ONLY: loaded when the `dev` Spring profile is active (see application-dev.yml).
-- Two demo clinics so tenant isolation can be tried by hand. The ids match the
-- org_id attribute of the demo users in infra/keycloak/aegle-realm.json.
INSERT INTO organizations (id, name) VALUES
    ('00000000-0000-0000-0000-00000000a001', 'Aegle Demo Clinic'),
    ('00000000-0000-0000-0000-00000000b001', 'Other Demo Clinic')
ON CONFLICT (id) DO NOTHING;

-- A DICOM sender for the demo clinic: studies sent with calling AE title AEGLE_DEV_CR
-- (and the modality certificate from infra/tls/generate.sh) land in its worklist.
INSERT INTO dicom_sources (ae_title, org_id, description) VALUES
    ('AEGLE_DEV_CR', '00000000-0000-0000-0000-00000000a001', 'Demo CR room (dev)')
ON CONFLICT (ae_title) DO NOTHING;
