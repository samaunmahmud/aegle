-- Tamper-evident audit log.
--
-- Each tenant's entries form a SHA-256 hash chain: an entry's hash covers its own
-- content and the previous entry's hash, and `seq` numbers the tenant's entries
-- 1, 2, 3 ... with no gaps. Editing, deleting or reordering any entry (for example by
-- someone with superuser access, who can bypass the append-only triggers) breaks the
-- chain from that point on, which audit_log_verify() reports.
--
-- Rewriting the entire chain consistently is still possible for a superuser, so the
-- head hash returned by audit_log_verify() should be recorded outside this database
-- from time to time: a later verification that does not extend it is evidence of tampering.

ALTER TABLE audit_log
    ADD COLUMN seq       bigint,
    ADD COLUMN prev_hash bytea,
    ADD COLUMN hash      bytea;

-- What an entry's hash covers. Timestamps are hashed as epoch microseconds so the
-- result does not depend on the session's time zone; jsonb's text form is canonical.
CREATE FUNCTION audit_log_digest(e audit_log) RETURNS bytea
LANGUAGE sql STABLE AS $$
    SELECT sha256(coalesce(e.prev_hash, ''::bytea) || convert_to(jsonb_build_array(
        e.id, e.seq, e.org_id, e.actor_id, e.action, e.entity_type, e.entity_id,
        host(e.ip), e.user_agent, e.details,
        (extract(epoch FROM e.at) * 1000000)::bigint)::text, 'UTF8'))
$$;

-- Chain the existing entries, oldest first per tenant. The append-only trigger is
-- lifted for this one-off backfill only.
ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_change;
DO $$
DECLARE
    r        record;
    prev     bytea;
    prev_org uuid;
    n        bigint;
BEGIN
    FOR r IN SELECT id, org_id FROM audit_log ORDER BY org_id, id LOOP
        IF prev_org IS DISTINCT FROM r.org_id THEN
            prev := NULL;
            n := 0;
            prev_org := r.org_id;
        END IF;
        n := n + 1;
        UPDATE audit_log SET seq = n, prev_hash = prev WHERE id = r.id;
        UPDATE audit_log a SET hash = audit_log_digest(a) WHERE id = r.id RETURNING hash INTO prev;
    END LOOP;
END $$;
ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_change;

ALTER TABLE audit_log ALTER COLUMN seq SET NOT NULL, ALTER COLUMN hash SET NOT NULL;
CREATE UNIQUE INDEX audit_log_chain_seq ON audit_log (org_id, seq);

-- New entries are chained on insert. The advisory lock serialises writers per tenant
-- until commit, so two transactions can never both extend the same entry. This relies
-- on READ COMMITTED (the default): each statement here sees the previous writer's row.
CREATE FUNCTION audit_log_chain() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_advisory_xact_lock(hashtextextended('aegle.audit_log:' || NEW.org_id, 0));
    SELECT seq, hash INTO NEW.seq, NEW.prev_hash
    FROM audit_log WHERE org_id = NEW.org_id ORDER BY seq DESC LIMIT 1;
    NEW.seq := coalesce(NEW.seq, 0) + 1;
    NEW.hash := audit_log_digest(NEW);
    RETURN NEW;
END $$;
CREATE TRIGGER audit_log_chain
    BEFORE INSERT ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_chain();

-- Walks the current tenant's chain (app.current_org_id). first_broken_seq is NULL when
-- the chain is intact; head_hash is the hash of the newest entry.
CREATE FUNCTION audit_log_verify(OUT entries bigint, OUT first_broken_seq bigint, OUT head_hash bytea)
LANGUAGE plpgsql STABLE AS $$
DECLARE
    org      uuid := NULLIF(current_setting('app.current_org_id', true), '')::uuid;
    e        audit_log;
    expected bigint := 1;
    prev     bytea;
BEGIN
    IF org IS NULL THEN
        RAISE EXCEPTION 'no tenant set';
    END IF;
    FOR e IN SELECT * FROM audit_log WHERE org_id = org ORDER BY seq LOOP
        IF e.seq <> expected OR e.prev_hash IS DISTINCT FROM prev OR e.hash <> audit_log_digest(e) THEN
            first_broken_seq := expected;
            EXIT;
        END IF;
        prev := e.hash;
        expected := expected + 1;
    END LOOP;
    SELECT count(*) INTO entries FROM audit_log WHERE org_id = org;
    SELECT hash INTO head_hash FROM audit_log WHERE org_id = org ORDER BY seq DESC LIMIT 1;
END $$;
