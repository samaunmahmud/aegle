package com.aegle.worklist;

import com.aegle.audit.AuditService;
import com.aegle.config.AegleProperties;
import com.aegle.phi.PhiCipher;
import com.aegle.security.Actor;
import com.aegle.security.ClinicianOnly;
import com.aegle.security.CurrentUserService;
import com.aegle.tenant.TenantTx;
import com.aegle.web.ConflictException;
import com.aegle.web.NotFoundException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** The risk-prioritised worklist: highest effective priority first, ties broken by age. */
@RestController
@RequestMapping("/api/worklist")
@Validated
@ClinicianOnly
public class WorklistController {

    public record Item(UUID studyId, String patientMrn, String modality, String bodyPart, String studyStatus,
                       String state, double priorityScore, double waitBonus, double effectivePriority,
                       String urgencyClass, String topLabel, Double topProbability, OffsetDateTime slaDueAt,
                       boolean slaBreached, OffsetDateTime studyCreatedAt, String assignedTo, JsonNode priorityReason) {}

    public record Page(List<Item> items, long total) {}

    private static final List<String> STATES = List.of("OPEN", "IN_REVIEW", "DONE");

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final CurrentUserService users;
    private final PhiCipher phi;
    private final AuditService audit;
    private final ObjectMapper json;
    private final AegleProperties.Triage triage;

    public WorklistController(JdbcClient jdbc, TenantTx tenantTx, CurrentUserService users, PhiCipher phi,
                              AuditService audit, ObjectMapper json, AegleProperties props) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.users = users;
        this.phi = phi;
        this.audit = audit;
        this.json = json;
        this.triage = props.triage();
    }

    @GetMapping
    public Page list(@RequestParam(defaultValue = "OPEN,IN_REVIEW") List<String> state,
                     @RequestParam(defaultValue = "50") @Min(1) @Max(200) int limit,
                     @RequestParam(defaultValue = "0") @Min(0) int offset) {
        if (!STATES.containsAll(state)) {
            throw new com.aegle.web.BadRequestException("state must be one of " + STATES);
        }
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            // Waiting time is applied here, not stored, so the ranking keeps moving as cases age.
            List<Item> items = jdbc.sql("""
                    SELECT w.study_id, w.state, w.priority_score, w.priority_reason, w.sla_due_at,
                           s.modality, s.body_part, s.status, s.created_at, p.mrn_encrypted, u.full_name AS assignee,
                           LEAST(:cap, EXTRACT(EPOCH FROM (now() - s.created_at)) / 3600.0 * :perHour) AS wait_bonus
                    FROM worklist_items w
                    JOIN studies s ON s.id = w.study_id
                    JOIN patients p ON p.id = s.patient_id
                    LEFT JOIN users u ON u.id = w.assigned_to
                    WHERE w.state IN (:states)
                    ORDER BY w.priority_score
                             + LEAST(:cap, EXTRACT(EPOCH FROM (now() - s.created_at)) / 3600.0 * :perHour) DESC,
                             s.created_at ASC
                    LIMIT :limit OFFSET :offset""")
                    .param("cap", triage.waitBonusCap()).param("perHour", triage.waitBonusPerHour())
                    .param("states", state).param("limit", limit).param("offset", offset)
                    .query((rs, i) -> item(rs)).list();
            long total = jdbc.sql("SELECT count(*) FROM worklist_items WHERE state IN (:states)")
                    .param("states", state).query(Long.class).single();
            audit.record(actor.orgId(), actor.userId(), "WORKLIST_VIEWED", "worklist", "*",
                    Map.of("count", items.size()));
            return new Page(items, total);
        });
    }

    /** Take a case. Idempotent for the same clinician; 409 if someone else has it. */
    @PostMapping("/{studyId}/claim")
    public Map<String, Object> claim(@PathVariable UUID studyId) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            int updated = jdbc.sql("""
                    UPDATE worklist_items SET assigned_to = :me, state = 'IN_REVIEW'
                    WHERE study_id = :study AND state = 'OPEN'""")
                    .param("me", actor.userId()).param("study", studyId).update();
            if (updated == 0) {
                var current = jdbc.sql("SELECT state, assigned_to FROM worklist_items WHERE study_id = :study")
                        .param("study", studyId)
                        .query((rs, i) -> Map.entry(rs.getString("state"),
                                String.valueOf(rs.getObject("assigned_to", UUID.class))))
                        .optional().orElseThrow(() -> new NotFoundException("worklist item"));
                boolean mine = "IN_REVIEW".equals(current.getKey()) && current.getValue().equals(actor.userId().toString());
                if (!mine) {
                    throw new ConflictException("Case is already " + current.getKey().toLowerCase().replace('_', ' '));
                }
            } else {
                audit.record(actor.orgId(), actor.userId(), "WORKLIST_CLAIMED", "study", studyId.toString(), Map.of());
            }
            return Map.of("studyId", studyId, "state", "IN_REVIEW");
        });
    }

    private Item item(java.sql.ResultSet rs) throws java.sql.SQLException {
        JsonNode reason = parse(rs.getString("priority_reason"));
        double base = round(rs.getFloat("priority_score"));
        double bonus = rs.getDouble("wait_bonus");
        OffsetDateTime sla = rs.getObject("sla_due_at", OffsetDateTime.class);
        return new Item(rs.getObject("study_id", UUID.class),
                phi.decrypt(rs.getBytes("mrn_encrypted"), "patients.mrn"), rs.getString("modality"),
                rs.getString("body_part"), rs.getString("status"), rs.getString("state"), base, round(bonus),
                round(base + bonus), text(reason, "urgencyClass"), text(reason, "topLabel"),
                reason != null && reason.has("topProbability") ? reason.get("topProbability").asDouble() : null,
                sla, sla != null && sla.isBefore(OffsetDateTime.now()),
                rs.getObject("created_at", OffsetDateTime.class), rs.getString("assignee"), reason);
    }

    private static String text(JsonNode n, String field) {
        return n != null && n.hasNonNull(field) ? n.get(field).asText() : null;
    }

    private JsonNode parse(String s) {
        try {
            return s == null ? null : json.readTree(s);
        } catch (Exception e) {
            return null;
        }
    }

    private static double round(double v) {
        return Math.round(v * 100d) / 100d;
    }
}
