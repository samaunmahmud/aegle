package com.aegle.review;

import com.aegle.audit.AuditService;
import com.aegle.security.Actor;
import com.aegle.security.ClinicianOnly;
import com.aegle.security.CurrentUserService;
import com.aegle.tenant.TenantTx;
import com.aegle.web.BadRequestException;
import com.aegle.web.NotFoundException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** The clinician's verdict on an AI finding. The AI suggests; this is what counts. */
@RestController
@RequestMapping("/api/predictions")
@ClinicianOnly
public class ReviewController {

    public enum Decision { ACCEPT, REJECT, MODIFY }

    public record ReviewRequest(@NotNull Decision decision, @Size(max = 64) String finalLabel,
                                @Size(max = 2000) String comment) {}

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final CurrentUserService users;
    private final AuditService audit;

    public ReviewController(JdbcClient jdbc, TenantTx tenantTx, CurrentUserService users, AuditService audit) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.users = users;
        this.audit = audit;
    }

    @PostMapping("/{predictionId}/review")
    public Map<String, Object> review(@PathVariable UUID predictionId, @Valid @RequestBody ReviewRequest req) {
        if (req.decision() == Decision.MODIFY && (req.finalLabel() == null || req.finalLabel().isBlank())) {
            throw new BadRequestException("finalLabel is required when the decision is MODIFY");
        }
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            UUID studyId = jdbc.sql("""
                    SELECT j.study_id FROM predictions pr JOIN inference_jobs j ON j.id = pr.job_id
                    WHERE pr.id = :id""")
                    .param("id", predictionId).query(UUID.class).optional()
                    .orElseThrow(() -> new NotFoundException("prediction"));

            UUID reviewId = jdbc.sql("""
                    INSERT INTO clinician_reviews (org_id, prediction_id, reviewer_id, decision, final_label, comment)
                    VALUES (:org, :pred, :me, :decision, :label, :comment) RETURNING id""")
                    .param("org", actor.orgId()).param("pred", predictionId).param("me", actor.userId())
                    .param("decision", req.decision().name()).param("label", req.finalLabel())
                    .param("comment", req.comment()).query(UUID.class).single();

            jdbc.sql("""
                    UPDATE worklist_items SET state = 'DONE', assigned_to = COALESCE(assigned_to, :me)
                    WHERE study_id = :study""")
                    .param("me", actor.userId()).param("study", studyId).update();
            jdbc.sql("UPDATE studies SET status = 'REVIEWED' WHERE id = :study").param("study", studyId).update();

            audit.record(actor.orgId(), actor.userId(), "PREDICTION_REVIEWED", "prediction", predictionId.toString(),
                    Map.of("decision", req.decision().name(), "studyId", studyId.toString()));
            return Map.of("reviewId", reviewId, "studyId", studyId, "decision", req.decision().name());
        });
    }
}
