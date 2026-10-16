package com.aegle.security;

import com.aegle.tenant.TenantTx;
import java.util.HashMap;
import java.util.Map;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/me")
public class MeController {

    private final CurrentUserService users;
    private final JdbcClient jdbc;
    private final TenantTx tenantTx;

    public MeController(CurrentUserService users, JdbcClient jdbc, TenantTx tenantTx) {
        this.users = users;
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
    }

    @GetMapping
    public Map<String, Object> me() {
        Actor a = users.require();
        String organisation = jdbc.sql("SELECT name FROM organizations WHERE id = :id").param("id", a.orgId())
                .query(String.class).single();
        Map<String, Object> profile = tenantTx.executeAs(a.orgId(), () -> jdbc.sql(
                        "SELECT job_title, grade, specialty, avatar FROM users WHERE id = :id")
                .param("id", a.userId())
                .query((rs, n) -> {
                    Map<String, Object> m = new HashMap<>();
                    m.put("jobTitle", rs.getString("job_title"));
                    m.put("grade", rs.getString("grade"));
                    m.put("specialty", rs.getString("specialty"));
                    m.put("avatar", rs.getString("avatar"));
                    return m;
                }).single());
        Map<String, Object> me = new HashMap<>(profile);
        me.putAll(Map.of("userId", a.userId(), "organisationId", a.orgId(), "organisationName", organisation,
                "roles", a.roles()));
        return me;
    }
}
