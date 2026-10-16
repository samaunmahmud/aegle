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

-- Demo clinicians (Keycloak users in infra/keycloak/aegle-realm.json, same ids), with the
-- profile shown beside consults. Avatars are illustrations of fictional people, made for
-- this demo with Figma AI (frontend/public/avatars).
SELECT set_config('app.current_org_id', '00000000-0000-0000-0000-00000000a001', false);
INSERT INTO users (idp_subject, org_id, email, full_name, role, job_title, grade, specialty, avatar)
SELECT v.sub, '00000000-0000-0000-0000-00000000a001'::uuid, v.email, v.name, v.role, v.title, v.grade, v.spec, v.avatar
FROM (VALUES
    ('5b76715e-c18a-4c0c-a855-1c23249ef8c0', 'rita.radiologist@aegle.local', 'Rita Radiologist', 'RADIOLOGIST', 'Consultant Radiologist', 'CONSULTANT', 'RADIOLOGY', 'rita-radiologist'),
    ('e9e6459a-83cd-4926-82b4-03122aec3663', 'paul.physician@aegle.local', 'Paul Physician', 'PHYSICIAN', 'Specialty Registrar (ST4), Acute Medicine', 'REGISTRAR', NULL, 'paul-physician'),
    ('8df1319b-b40c-5664-92e4-0a2491687afd', 'amara.okafor@aegle.local', 'Amara Okafor', 'RADIOLOGIST', 'Consultant Neuroradiologist', 'CONSULTANT', 'NEUROLOGY', 'amara-okafor'),
    ('602eea36-d4b5-5354-8ba3-c1ff1c79d6da', 'kwame.asante@aegle.local', 'Kwame Asante', 'RADIOLOGIST', 'Consultant Thoracic Radiologist', 'CONSULTANT', 'RADIOLOGY', 'kwame-asante'),
    ('b1f6c661-cb60-5b40-98ff-43f125f5f3c3', 'tomasz.nowak@aegle.local', 'Tomasz Nowak', 'RADIOLOGIST', 'Specialty Registrar (ST3), Radiology', 'REGISTRAR', 'RADIOLOGY', 'tomasz-nowak'),
    ('5500228a-33b5-5fd9-b7ed-499fce3bffce', 'james.whitfield@aegle.local', 'James Whitfield', 'PHYSICIAN', 'Consultant Cardiologist', 'CONSULTANT', 'CARDIOLOGY', 'james-whitfield'),
    ('47062f75-aae5-58e2-8f36-c3040bfcef99', 'priya.raman@aegle.local', 'Priya Raman', 'PHYSICIAN', 'Consultant Dermatologist', 'CONSULTANT', 'DERMATOLOGY', 'priya-raman'),
    ('d3710671-3e50-59d5-a1a9-1092a495efec', 'wei.chen@aegle.local', 'Wei Chen', 'PHYSICIAN', 'Consultant Ophthalmologist', 'CONSULTANT', 'OPHTHALMOLOGY', 'wei-chen'),
    ('3107feec-4338-59f5-8e09-ffb12b33907d', 'hannah.clarke@aegle.local', 'Hannah Clarke', 'PHYSICIAN', 'Consultant Histopathologist', 'CONSULTANT', 'PATHOLOGY', 'hannah-clarke'),
    ('f60447f9-6b20-5e87-ace5-251018acfe91', 'fatima.alsayed@aegle.local', 'Fatima Al-Sayed', 'PHYSICIAN', 'Consultant Gastroenterologist', 'CONSULTANT', 'GASTROENTEROLOGY', 'fatima-al-sayed'),
    ('2bdd7af8-e8b4-5283-9631-f33b619a569e', 'daniel.mensah@aegle.local', 'Daniel Mensah', 'PHYSICIAN', 'Consultant Neurologist', 'CONSULTANT', 'NEUROLOGY', 'daniel-mensah'),
    ('cd7f4cf6-a827-5607-a617-0f1c9060ed16', 'sofia.rossi@aegle.local', 'Sofia Rossi', 'PHYSICIAN', 'Foundation Doctor (FY2)', 'FOUNDATION', NULL, 'sofia-rossi')
) AS v(sub, email, name, role, title, grade, spec, avatar)
ON CONFLICT (idp_subject) DO UPDATE
   SET job_title = EXCLUDED.job_title, grade = EXCLUDED.grade,
       specialty = EXCLUDED.specialty, avatar = EXCLUDED.avatar;
SELECT set_config('app.current_org_id', '', false);
