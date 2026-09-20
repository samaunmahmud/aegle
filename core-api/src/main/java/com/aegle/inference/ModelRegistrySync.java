package com.aegle.inference;

import com.aegle.config.AegleProperties;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Keeps the model registry in step with what the inference service serves.
 *
 * A new version is registered inactive: nothing runs on patient data until a version is
 * approved (auto-approved only when `aegle.models.auto-activate` is on, i.e. local dev).
 * If the weights behind an existing version label change, the change is refused, so a
 * stored prediction can always be traced to the exact weights that produced it.
 */
@Component
public class ModelRegistrySync {

    private static final Logger log = LoggerFactory.getLogger(ModelRegistrySync.class);

    private final InferenceClient inference;
    private final JdbcClient jdbc;
    private final TransactionTemplate tx;
    private final ObjectMapper json;
    private final boolean autoActivate;

    public ModelRegistrySync(InferenceClient inference, JdbcClient jdbc, TransactionTemplate tx,
                             ObjectMapper json, AegleProperties props) {
        this.inference = inference;
        this.jdbc = jdbc;
        this.tx = tx;
        this.json = json;
        this.autoActivate = props.models().autoActivate();
    }

    @Scheduled(initialDelayString = "${aegle.models.sync-initial-delay-ms}", fixedDelayString = "${aegle.models.sync-interval-ms}")
    public void scheduledSync() {
        try {
            sync();
        } catch (Exception e) {
            log.warn("Model registry sync skipped: inference service unavailable ({})", e.getClass().getSimpleName());
        }
    }

    public void sync() {
        for (InferenceClient.ModelInfo m : inference.models()) {
            tx.executeWithoutResult(s -> register(m));
        }
    }

    private void register(InferenceClient.ModelInfo m) {
        UUID modelId = jdbc.sql("""
                INSERT INTO ai_models (name, modality, body_part, task, intended_use)
                VALUES (:name, :modality, :bodyPart, :task, :use)
                ON CONFLICT (name) DO UPDATE SET modality = EXCLUDED.modality, body_part = EXCLUDED.body_part,
                    task = EXCLUDED.task, intended_use = EXCLUDED.intended_use
                RETURNING id""")
                .param("name", m.id()).param("modality", m.modality()).param("bodyPart", m.bodyPart())
                .param("task", m.task()).param("use", m.intendedUse())
                .query(UUID.class).single();

        Optional<String> knownHash = jdbc.sql(
                "SELECT COALESCE(weights_sha256, '') FROM model_versions WHERE model_id = :m AND version = :v")
                .param("m", modelId).param("v", m.version()).query(String.class).optional();

        UUID versionId;
        if (knownHash.isPresent()) {
            if (!knownHash.get().isEmpty() && !knownHash.get().equals(m.weightsSha256())) {
                log.error("Model {} version {} is being served with different weights than registered. "
                        + "Bump the version to register it. Refusing.", m.id(), m.version());
                return;
            }
            versionId = jdbc.sql("""
                    UPDATE model_versions SET weights_sha256 = :h
                    WHERE model_id = :m AND version = :v RETURNING id""")
                    .param("h", m.weightsSha256()).param("m", modelId).param("v", m.version())
                    .query(UUID.class).single();
        } else {
            versionId = jdbc.sql("""
                    INSERT INTO model_versions (model_id, version, artifact_uri, weights_sha256, validation_metrics)
                    VALUES (:m, :v, :uri, :h, CAST(:metrics AS jsonb)) RETURNING id""")
                    .param("m", modelId).param("v", m.version())
                    .param("uri", "inference-service://" + m.id() + "@" + m.version())
                    .param("h", m.weightsSha256()).param("metrics", toJson(m))
                    .query(UUID.class).single();
            log.info("Registered model {} version {} (inactive until approved)", m.id(), m.version());
        }

        if (autoActivate) {
            jdbc.sql("UPDATE model_versions SET active = false WHERE model_id = :m AND id <> :v AND active")
                    .param("m", modelId).param("v", versionId).update();
            jdbc.sql("UPDATE model_versions SET active = true, approved_at = COALESCE(approved_at, now()) WHERE id = :v")
                    .param("v", versionId).update();
        }
    }

    private String toJson(InferenceClient.ModelInfo m) {
        try {
            return json.writeValueAsString(m.metrics() == null ? java.util.Map.of() : m.metrics());
        } catch (JsonProcessingException e) {
            return "{}";
        }
    }
}
