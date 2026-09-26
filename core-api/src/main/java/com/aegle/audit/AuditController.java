package com.aegle.audit;

import com.aegle.security.Actor;
import com.aegle.security.AuditReader;
import com.aegle.security.CurrentUserService;
import com.aegle.tenant.TenantTx;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Read-only view of the organisation's audit trail, for auditors and admins. */
@RestController
@RequestMapping("/api/audit")
@Validated
@AuditReader
public class AuditController {

    public record Entry(long id, OffsetDateTime at, String actor, String action, String entityType,
                        String entityId, String ip, JsonNode details) {}

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final CurrentUserService users;
    private final AuditService audit;
    private final ObjectMapper json;

    public AuditController(JdbcClient jdbc, TenantTx tenantTx, CurrentUserService users, AuditService audit,
                           ObjectMapper json) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.users = users;
        this.audit = audit;
        this.json = json;
    }

    /** Newest first. Pass the last id seen as `before` to page backwards. */
    @GetMapping
    public List<Entry> list(@RequestParam(defaultValue = "100") @Min(1) @Max(500) int limit,
                            @RequestParam(required = false) Long before,
                            @RequestParam(required = false) String action) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            List<Entry> rows = jdbc.sql("""
                    SELECT a.id, a.at, u.full_name, a.action, a.entity_type, a.entity_id, host(a.ip) AS ip, a.details
                    FROM audit_log a LEFT JOIN users u ON u.id = a.actor_id
                    WHERE (CAST(:before AS bigint) IS NULL OR a.id < :before)
                      AND (CAST(:action AS text) IS NULL OR a.action = :action)
                    ORDER BY a.id DESC LIMIT :limit""")
                    .param("before", before).param("action", action).param("limit", limit)
                    .query((rs, i) -> new Entry(rs.getLong("id"), rs.getObject("at", OffsetDateTime.class),
                            rs.getString("full_name") == null ? "system" : rs.getString("full_name"),
                            rs.getString("action"), rs.getString("entity_type"), rs.getString("entity_id"),
                            rs.getString("ip"), parse(rs.getString("details")))).list();
            audit.record(actor.orgId(), actor.userId(), "AUDIT_VIEWED", "audit", "*", Map.of("count", rows.size()));
            return rows;
        });
    }

    public record Verification(long entries, boolean intact, Long firstBrokenSeq, String headHash) {}

    /**
     * Recomputes the organisation's audit hash chain. {@code headHash} identifies the chain's
     * current state; recording it elsewhere lets a later check detect a rewritten history.
     */
    @GetMapping("/verify")
    public Verification verify() {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            Verification v = jdbc.sql("SELECT entries, first_broken_seq, encode(head_hash, 'hex') AS head FROM audit_log_verify()")
                    .query((rs, i) -> new Verification(rs.getLong("entries"), rs.getObject("first_broken_seq") == null,
                            rs.getObject("first_broken_seq", Long.class), rs.getString("head"))).single();
            audit.record(actor.orgId(), actor.userId(), "AUDIT_VERIFIED", "audit", "*",
                    Map.of("entries", v.entries(), "intact", v.intact()));
            return v;
        });
    }

    private JsonNode parse(String s) {
        try {
            return json.readTree(s);
        } catch (Exception e) {
            return null;
        }
    }
}
