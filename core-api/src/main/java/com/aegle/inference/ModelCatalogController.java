package com.aegle.inference;

import com.aegle.audit.AuditService;
import com.aegle.security.Actor;
import com.aegle.security.CurrentUserService;
import com.aegle.tenant.TenantTx;
import com.aegle.web.NotFoundException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.constraints.NotNull;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The AI models the platform offers, with what they are for, how they were validated and
 * whether they run for this organisation. Everyone signed in can read it (clinicians should
 * be able to see what produced a finding); only admins switch models on or off.
 */
@RestController
@RequestMapping("/api/models")
public class ModelCatalogController {

    public record ModelEntry(UUID id, String name, String specialty, String modality, String bodyPart, String task,
                             String intendedUse, String activeVersion, String weightsSha256,
                             OffsetDateTime approvedAt, JsonNode metrics, boolean enabledForOrganisation) {}

    public record Toggle(@NotNull Boolean enabled) {}

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final CurrentUserService users;
    private final AuditService audit;
    private final ObjectMapper json;

    public ModelCatalogController(JdbcClient jdbc, TenantTx tenantTx, CurrentUserService users, AuditService audit,
                                  ObjectMapper json) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.users = users;
        this.audit = audit;
        this.json = json;
    }

    @GetMapping
    public List<ModelEntry> list() {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> jdbc.sql("""
                        SELECT m.id, m.name, aegle_specialty(m.modality, m.body_part) AS specialty, m.modality,
                               m.body_part, m.task, m.intended_use, mv.version, mv.weights_sha256, mv.approved_at,
                               mv.validation_metrics, COALESCE(o.enabled, true) AS enabled
                        FROM ai_models m
                        LEFT JOIN model_versions mv ON mv.model_id = m.id AND mv.active
                        LEFT JOIN org_model_settings o ON o.model_id = m.id
                        ORDER BY specialty, m.name""")
                .query((rs, i) -> new ModelEntry(rs.getObject("id", UUID.class), rs.getString("name"),
                        rs.getString("specialty"), rs.getString("modality"), rs.getString("body_part"),
                        rs.getString("task"), rs.getString("intended_use"), rs.getString("version"),
                        rs.getString("weights_sha256"), rs.getObject("approved_at", OffsetDateTime.class),
                        parse(rs.getString("validation_metrics")), rs.getBoolean("enabled")))
                .list());
    }

    /** Switches a model on or off for the admin's organisation only. Studies already queued are unaffected. */
    @PutMapping("/{modelId}/enabled")
    @PreAuthorize("hasRole('ADMIN')")
    public Map<String, Object> setEnabled(@PathVariable UUID modelId, @RequestBody @jakarta.validation.Valid Toggle body) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            boolean exists = jdbc.sql("SELECT count(*) FROM ai_models WHERE id = :id").param("id", modelId)
                    .query(Long.class).single() > 0;
            if (!exists) {
                throw new NotFoundException("model");
            }
            jdbc.sql("""
                    INSERT INTO org_model_settings (org_id, model_id, enabled, changed_by)
                    VALUES (:org, :model, :enabled, :by)
                    ON CONFLICT (org_id, model_id) DO UPDATE
                       SET enabled = EXCLUDED.enabled, changed_by = EXCLUDED.changed_by, changed_at = now()""")
                    .param("org", actor.orgId()).param("model", modelId).param("enabled", body.enabled())
                    .param("by", actor.userId()).update();
            audit.record(actor.orgId(), actor.userId(), body.enabled() ? "MODEL_ENABLED" : "MODEL_DISABLED",
                    "ai_model", modelId.toString(), Map.of());
            return Map.of("modelId", modelId, "enabled", body.enabled());
        });
    }

    private JsonNode parse(String s) {
        try {
            return s == null ? null : json.readTree(s);
        } catch (Exception e) {
            return null;
        }
    }
}
