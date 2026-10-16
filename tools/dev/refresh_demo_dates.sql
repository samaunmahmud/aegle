-- Re-age the dev clinic so it looks like a working day, not a backlog from weeks ago.
--
--   docker compose exec -T postgres psql -U aegle -d aegle -v ON_ERROR_STOP=1 < tools/dev/refresh_demo_dates.sql
--
-- Each open study gets a waiting time that is a fixed fraction (5% to 130%) of its own report
-- window (1 h critical, 4 h urgent, 24 h routine), so most are within time and about one in
-- five is overdue. Signed studies move to the last one to three days. Everything that belongs
-- to a study (images, AI jobs, predictions, measurements, reviews, worklist deadline) moves by
-- the same amount, so each study's own timeline stays intact. Consult threads move together so
-- the newest message is a few minutes old. The fraction comes from the study id, so re-running
-- the script gives the same picture relative to the time it is run.
--
-- The audit log is never touched: it is a true record, and its hash chain covers timestamps.
-- Dev only: runs as the database owner (bypasses row-level security) across all organisations.

BEGIN;

CREATE TEMP TABLE shift ON COMMIT DROP AS
SELECT s.id AS study_id,
       now() - CASE
           WHEN s.status = 'REVIEWED' THEN interval '24 hours' + interval '48 hours' * f
           ELSE coalesce(w.sla_due_at - s.created_at, interval '4 hours') * (0.05 + 1.25 * f)
       END - s.created_at AS delta
FROM studies s
LEFT JOIN worklist_items w ON w.study_id = s.id
CROSS JOIN LATERAL (SELECT (abs(hashtext(s.id::text)) % 1000) / 1000.0 AS f) r;

UPDATE studies s SET created_at = s.created_at + x.delta,
                     study_date = (s.created_at + x.delta)::date
FROM shift x WHERE x.study_id = s.id;

UPDATE worklist_items w SET created_at = w.created_at + x.delta,
                            sla_due_at = w.sla_due_at + x.delta
FROM shift x WHERE x.study_id = w.study_id;

UPDATE instances i SET created_at = i.created_at + x.delta FROM shift x WHERE x.study_id = i.study_id;
UPDATE documents d SET created_at = d.created_at + x.delta FROM shift x WHERE x.study_id = d.study_id;
UPDATE measurements m SET created_at = m.created_at + x.delta FROM shift x WHERE x.study_id = m.study_id;

UPDATE inference_jobs j SET queued_at = j.queued_at + x.delta,
                            started_at = j.started_at + x.delta,
                            finished_at = j.finished_at + x.delta
FROM shift x WHERE x.study_id = j.study_id;

UPDATE predictions p SET created_at = p.created_at + x.delta
FROM inference_jobs j JOIN shift x ON x.study_id = j.study_id
WHERE p.job_id = j.id;

UPDATE clinician_reviews r SET reviewed_at = r.reviewed_at + x.delta
FROM predictions p JOIN inference_jobs j ON j.id = p.job_id JOIN shift x ON x.study_id = j.study_id
WHERE r.prediction_id = p.id;

-- Consults: one shift for every thread, keeping their order and who has read what.
CREATE TEMP TABLE consult_shift ON COMMIT DROP AS
SELECT now() - interval '7 minutes' - max(created_at) AS delta FROM consult_messages;

UPDATE consult_messages SET created_at = created_at + (SELECT delta FROM consult_shift);
UPDATE consult_threads SET created_at = created_at + (SELECT delta FROM consult_shift),
                           last_message_at = last_message_at + (SELECT delta FROM consult_shift),
                           resolved_at = resolved_at + (SELECT delta FROM consult_shift);
UPDATE consult_reads SET last_read_at = last_read_at + (SELECT delta FROM consult_shift);

COMMIT;

SELECT CASE WHEN s.status = 'REVIEWED' THEN 'signed'
            WHEN w.sla_due_at < now() THEN 'open, overdue'
            ELSE 'open, in time' END AS state,
       count(*) AS studies,
       min(now() - s.created_at)::interval(0) AS newest,
       max(now() - s.created_at)::interval(0) AS oldest
FROM studies s LEFT JOIN worklist_items w ON w.study_id = s.id
GROUP BY 1 ORDER BY 1;
