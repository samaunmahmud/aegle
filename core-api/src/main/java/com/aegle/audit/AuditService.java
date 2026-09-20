package com.aegle.audit;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import java.util.Map;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.web.context.request.RequestAttributes;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

/**
 * Appends to the audit log. Must be called inside a {@code TenantTx}, so the entry is
 * committed atomically with the action it records and lands in the right tenant.
 *
 * `details` must never contain patient identifiers: the log records who did what to which
 * record id, not the patient's data.
 */
@Service
public class AuditService {

    private final JdbcClient jdbc;
    private final ObjectMapper json;

    public AuditService(JdbcClient jdbc, ObjectMapper json) {
        this.jdbc = jdbc;
        this.json = json;
    }

    /** {@code actorId} is null for system actions such as the inference worker. */
    public void record(UUID orgId, UUID actorId, String action, String entityType,
                       String entityId, Map<String, Object> details) {
        String ip = null;
        String userAgent = null;
        RequestAttributes attrs = RequestContextHolder.getRequestAttributes();
        if (attrs instanceof ServletRequestAttributes sra) {
            HttpServletRequest req = sra.getRequest();
            ip = stripZone(req.getRemoteAddr());
            userAgent = truncate(req.getHeader("User-Agent"), 300);
        }
        jdbc.sql("""
                INSERT INTO audit_log (org_id, actor_id, action, entity_type, entity_id, ip, user_agent, details)
                VALUES (:org, :actor, :action, :etype, :eid, CAST(:ip AS inet), :ua, CAST(:details AS jsonb))""")
                .param("org", orgId).param("actor", actorId).param("action", action)
                .param("etype", entityType).param("eid", entityId)
                .param("ip", ip).param("ua", userAgent).param("details", toJson(details))
                .update();
    }

    private String toJson(Map<String, Object> details) {
        try {
            return json.writeValueAsString(details == null ? Map.of() : details);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Unserialisable audit details", e);
        }
    }

    private static String stripZone(String ip) {
        if (ip == null) {
            return null;
        }
        int i = ip.indexOf('%');
        return i >= 0 ? ip.substring(0, i) : ip;
    }

    private static String truncate(String s, int max) {
        return s == null || s.length() <= max ? s : s.substring(0, max);
    }
}
