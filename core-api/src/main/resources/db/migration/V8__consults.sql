-- Clinician-to-clinician consults: a question about a case, put to a named colleague or to
-- any clinician in the organisation, answered in a thread.
--
-- A consult may link a study, but never copies patient identifiers: colleagues open the
-- study itself, which is access-controlled and audited like any other read.

CREATE TABLE consult_threads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          uuid NOT NULL REFERENCES organizations(id),
    subject         text NOT NULL CHECK (length(subject) BETWEEN 1 AND 140),
    specialty       text CHECK (specialty IN ('RADIOLOGY', 'CARDIOLOGY', 'DERMATOLOGY', 'OPHTHALMOLOGY',
                                              'PATHOLOGY', 'GASTROENTEROLOGY', 'NEUROLOGY')),
    study_id        uuid REFERENCES studies(id) ON DELETE SET NULL,
    created_by      uuid NOT NULL REFERENCES users(id),
    asked_of        uuid REFERENCES users(id),     -- null: open to any clinician
    urgency         text NOT NULL DEFAULT 'ROUTINE' CHECK (urgency IN ('ROUTINE', 'URGENT')),
    status          text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_message_at timestamptz NOT NULL DEFAULT now(),
    resolved_at     timestamptz,
    resolved_by     uuid REFERENCES users(id)
);
CREATE INDEX consult_threads_recent ON consult_threads (org_id, status, last_message_at DESC);

CREATE TABLE consult_messages (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     uuid NOT NULL REFERENCES organizations(id),
    thread_id  uuid NOT NULL REFERENCES consult_threads(id) ON DELETE CASCADE,
    author_id  uuid NOT NULL REFERENCES users(id),
    body       text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX consult_messages_thread ON consult_messages (thread_id, created_at);

-- How far each clinician has read each thread, for unread counts.
CREATE TABLE consult_reads (
    org_id       uuid NOT NULL REFERENCES organizations(id),
    thread_id    uuid NOT NULL REFERENCES consult_threads(id) ON DELETE CASCADE,
    user_id      uuid NOT NULL REFERENCES users(id),
    last_read_at timestamptz NOT NULL,
    PRIMARY KEY (thread_id, user_id)
);

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['consult_threads', 'consult_messages', 'consult_reads'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I
                 USING (org_id = NULLIF(current_setting(''app.current_org_id'', true), '''')::uuid)
                 WITH CHECK (org_id = NULLIF(current_setting(''app.current_org_id'', true), '''')::uuid)',
            t);
    END LOOP;
END $$;

-- Clinician profile, shown beside consults so a colleague can see who is answering and how
-- senior they are. Kept out of the login token: provisioning never overwrites these.
ALTER TABLE users ADD COLUMN job_title text;
ALTER TABLE users ADD COLUMN grade text CHECK (grade IN ('CONSULTANT', 'REGISTRAR', 'FOUNDATION'));
ALTER TABLE users ADD COLUMN specialty text CHECK (specialty IN ('RADIOLOGY', 'CARDIOLOGY', 'DERMATOLOGY',
    'OPHTHALMOLOGY', 'PATHOLOGY', 'GASTROENTEROLOGY', 'NEUROLOGY'));
ALTER TABLE users ADD COLUMN avatar text CHECK (avatar ~ '^[a-z0-9-]{1,64}$');  -- a bundled image name
