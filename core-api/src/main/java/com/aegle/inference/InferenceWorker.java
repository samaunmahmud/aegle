package com.aegle.inference;

import com.aegle.audit.AuditService;
import com.aegle.config.AegleProperties;
import com.aegle.storage.ObjectStore;
import com.aegle.tenant.TenantTx;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Drains the inference job queue.
 *
 * The queue lives in Postgres and is claimed with FOR UPDATE SKIP LOCKED, so several API
 * instances can run workers without picking the same job. Row-level security applies to
 * the worker like everything else, so it visits one organisation at a time and claims
 * inside that organisation's tenant context.
 */
@Component
public class InferenceWorker {

    private static final Logger log = LoggerFactory.getLogger(InferenceWorker.class);

    record Job(UUID id, UUID studyId, UUID modelVersionId, int attempts) {}

    private record ModelRef(String name, String weightsSha256) {}

    private record InstanceRef(UUID id, String storageKey) {}

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final InferenceClient inference;
    private final ObjectStore store;
    private final TriagePolicy triage;
    private final AuditService audit;
    private final ObjectMapper json;
    private final AegleProperties.Worker cfg;

    public InferenceWorker(JdbcClient jdbc, TenantTx tenantTx, InferenceClient inference, ObjectStore store,
                           TriagePolicy triage, AuditService audit, ObjectMapper json, AegleProperties props) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.inference = inference;
        this.store = store;
        this.triage = triage;
        this.audit = audit;
        this.json = json;
        this.cfg = props.worker();
    }

    @Scheduled(fixedDelayString = "${aegle.worker.poll-interval-ms}")
    void scheduledTick() {
        if (cfg.enabled()) {
            runOnce();
        }
    }

    /** Processes every job that is ready right now, in every organisation. Returns how many it handled. */
    public int runOnce() {
        int handled = 0;
        for (UUID orgId : jdbc.sql("SELECT id FROM organizations").query(UUID.class).list()) {
            try {
                handled += runOnce(orgId);
            } catch (Exception e) {
                log.error("Worker failed for one organisation; continuing with the others", e);
            }
        }
        return handled;
    }

    /** Processes every ready job of one organisation. */
    public int runOnce(UUID orgId) {
        int handled = 0;
        requeueStale(orgId);
        Job job;
        while ((job = claim(orgId)) != null) {
            process(orgId, job);
            handled++;
        }
        return handled;
    }

    /** A worker that died mid-job leaves it RUNNING forever; put such jobs back. */
    private void requeueStale(UUID orgId) {
        tenantTx.runAs(orgId, () -> jdbc.sql("""
                UPDATE inference_jobs SET status = 'QUEUED'
                WHERE status = 'RUNNING' AND started_at < now() - make_interval(secs => :secs)""")
                .param("secs", (double) cfg.staleAfter().toSeconds()).update());
    }

    private Job claim(UUID orgId) {
        return tenantTx.executeAs(orgId, () -> {
            Optional<Job> job = jdbc.sql("""
                    UPDATE inference_jobs SET status = 'RUNNING', attempts = attempts + 1, started_at = now()
                    WHERE id = (SELECT id FROM inference_jobs
                                WHERE status = 'QUEUED' AND queued_at <= now()
                                ORDER BY queued_at FOR UPDATE SKIP LOCKED LIMIT 1)
                    RETURNING id, study_id, model_version_id, attempts""")
                    .query((rs, i) -> new Job(rs.getObject("id", UUID.class), rs.getObject("study_id", UUID.class),
                            rs.getObject("model_version_id", UUID.class), rs.getInt("attempts")))
                    .optional();
            job.ifPresent(j -> refreshStudyStatus(j.studyId()));
            return job.orElse(null);
        });
    }

    private void process(UUID orgId, Job job) {
        try {
            ModelRef model = jdbc.sql("""
                    SELECT m.name, mv.weights_sha256 FROM model_versions mv JOIN ai_models m ON m.id = mv.model_id
                    WHERE mv.id = :id""").param("id", job.modelVersionId())
                    .query((rs, i) -> new ModelRef(rs.getString("name"), rs.getString("weights_sha256"))).single();

            InstanceRef instance = tenantTx.executeAs(orgId, () -> jdbc.sql("""
                    SELECT id, storage_key FROM instances WHERE study_id = :s ORDER BY created_at LIMIT 1""")
                    .param("s", job.studyId())
                    .query((rs, i) -> new InstanceRef(rs.getObject("id", UUID.class), rs.getString("storage_key")))
                    .single());

            InferenceClient.Result result = inference.predict(model.name(), store.get(instance.storageKey()));

            // The queued job was approved for specific weights. If the service now serves
            // different ones, storing the result under that version would be a lie.
            if (model.weightsSha256() != null && !model.weightsSha256().equals(result.model().weightsSha256())) {
                throw new InferenceClient.NonRetryableInferenceException(
                        "Inference service is serving different weights than the approved model version");
            }

            String heatmapKey = null;
            if (result.heatmap() != null) {
                heatmapKey = orgId + "/studies/" + job.studyId() + "/heatmaps/" + UUID.randomUUID() + ".png";
                store.put(heatmapKey, result.heatmap().png(), "image/png");
            }
            complete(orgId, job, instance, result, heatmapKey);
        } catch (Exception e) {
            fail(orgId, job, e);
        }
    }

    private void complete(UUID orgId, Job job, InstanceRef instance, InferenceClient.Result result, String heatmapKey) {
        TriagePolicy.Score score = triage.score(result.predictions());
        String rawOutput = toJson(Map.of("modelVersion", result.model().version(),
                "weightsSha256", result.model().weightsSha256()));

        tenantTx.runAs(orgId, () -> {
            UUID topPredictionId = null;
            for (InferenceClient.Label p : result.predictions()) {
                UUID id = UUID.randomUUID();
                if (topPredictionId == null) {
                    topPredictionId = id;   // predictions arrive sorted, highest probability first
                }
                jdbc.sql("""
                        INSERT INTO predictions (id, org_id, job_id, label, probability, urgency_class, raw_output)
                        VALUES (:id, :org, :job, :label, :p, :urgency, CAST(:raw AS jsonb))""")
                        .param("id", id).param("org", orgId).param("job", job.id()).param("label", p.label())
                        .param("p", p.probability()).param("urgency", triage.urgencyOf(p.label()).name())
                        .param("raw", rawOutput).update();
            }
            if (heatmapKey != null) {
                jdbc.sql("""
                        INSERT INTO heatmaps (org_id, prediction_id, instance_id, storage_key, method)
                        VALUES (:org, :pred, :inst, :key, :method)""")
                        .param("org", orgId).param("pred", topPredictionId).param("inst", instance.id())
                        .param("key", heatmapKey).param("method", result.heatmap().method()).update();
            }
            jdbc.sql("""
                    INSERT INTO worklist_items (org_id, study_id, priority_score, priority_reason, sla_due_at)
                    VALUES (:org, :study, :score, CAST(:reason AS jsonb),
                            (SELECT created_at FROM studies WHERE id = :study) + make_interval(secs => :sla))
                    ON CONFLICT (study_id) DO UPDATE SET
                        priority_score = GREATEST(worklist_items.priority_score, EXCLUDED.priority_score),
                        priority_reason = CASE WHEN EXCLUDED.priority_score > worklist_items.priority_score
                                               THEN EXCLUDED.priority_reason ELSE worklist_items.priority_reason END,
                        sla_due_at = LEAST(worklist_items.sla_due_at, EXCLUDED.sla_due_at)""")
                    .param("org", orgId).param("study", job.studyId()).param("score", score.priority())
                    .param("reason", toJson(score.reason())).param("sla", (double) score.sla().toSeconds()).update();
            jdbc.sql("UPDATE inference_jobs SET status = 'SUCCEEDED', error = NULL, finished_at = now() WHERE id = :id")
                    .param("id", job.id()).update();
            refreshStudyStatus(job.studyId());
            audit.record(orgId, null, "INFERENCE_COMPLETED", "study", job.studyId().toString(),
                    Map.of("jobId", job.id().toString(), "topLabel", result.predictions().get(0).label()));
        });
    }

    private void fail(UUID orgId, Job job, Exception e) {
        boolean retryable = !(e instanceof InferenceClient.NonRetryableInferenceException);
        boolean giveUp = !retryable || job.attempts() >= cfg.maxAttempts();
        String message = truncate(e.getClass().getSimpleName() + ": " + e.getMessage(), 500);
        log.warn("Inference job {} attempt {} failed ({}){}", job.id(), job.attempts(), e.getClass().getSimpleName(),
                giveUp ? ", giving up" : ", will retry");

        tenantTx.runAs(orgId, () -> {
            jdbc.sql("""
                    UPDATE inference_jobs SET status = :status, error = :err,
                           finished_at = CASE WHEN :giveUp THEN now() END,
                           queued_at = CASE WHEN :giveUp THEN queued_at
                                            ELSE now() + make_interval(secs => :backoff) END
                    WHERE id = :id""")
                    .param("status", giveUp ? "FAILED" : "QUEUED").param("err", message).param("giveUp", giveUp)
                    .param("backoff", (double) cfg.retryBackoff().toSeconds() * job.attempts())
                    .param("id", job.id()).update();
            refreshStudyStatus(job.studyId());
            if (giveUp) {
                audit.record(orgId, null, "INFERENCE_FAILED", "study", job.studyId().toString(),
                        Map.of("jobId", job.id().toString(), "attempts", job.attempts()));
            }
        });
    }

    /** Derives the study's status from its jobs. A reviewed study is never moved back. */
    private void refreshStudyStatus(UUID studyId) {
        jdbc.sql("""
                UPDATE studies s SET status = CASE
                    WHEN EXISTS (SELECT 1 FROM inference_jobs j WHERE j.study_id = s.id
                                 AND j.status IN ('QUEUED', 'RUNNING')) THEN 'ANALYZING'
                    WHEN EXISTS (SELECT 1 FROM inference_jobs j WHERE j.study_id = s.id
                                 AND j.status = 'SUCCEEDED') THEN 'READY'
                    ELSE 'FAILED' END
                WHERE s.id = :id AND s.status <> 'REVIEWED'""")
                .param("id", studyId).update();
    }

    private String toJson(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Unserialisable value", e);
        }
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max);
    }
}
