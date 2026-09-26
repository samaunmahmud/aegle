package com.aegle.security;

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

    public MeController(CurrentUserService users, JdbcClient jdbc) {
        this.users = users;
        this.jdbc = jdbc;
    }

    @GetMapping
    public Map<String, Object> me() {
        Actor a = users.require();
        String organisation = jdbc.sql("SELECT name FROM organizations WHERE id = :id").param("id", a.orgId())
                .query(String.class).single();
        return Map.of("userId", a.userId(), "organisationId", a.orgId(), "organisationName", organisation,
                "roles", a.roles());
    }
}
