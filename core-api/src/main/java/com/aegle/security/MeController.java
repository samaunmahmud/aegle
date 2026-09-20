package com.aegle.security;

import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/me")
public class MeController {

    private final CurrentUserService users;

    public MeController(CurrentUserService users) {
        this.users = users;
    }

    @GetMapping
    public Map<String, Object> me() {
        Actor a = users.require();
        return Map.of("userId", a.userId(), "organisationId", a.orgId(), "roles", a.roles());
    }
}
