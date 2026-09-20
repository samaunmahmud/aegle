package com.aegle.security;

import com.aegle.tenant.TenantTx;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;
import org.springframework.dao.DataAccessException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

/**
 * Turns the verified login token into an {@link Actor}.
 *
 * The tenant comes only from the signed `org_id` claim, never from request parameters.
 * Users are created in our database on first sight, inside their own tenant.
 */
@Service
public class CurrentUserService {

    /** Highest privilege first: decides the single role stored on the users row. */
    private static final List<String> ROLE_PRECEDENCE = List.of("ADMIN", "RADIOLOGIST", "PHYSICIAN", "AUDITOR");

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final Map<String, Actor> cache = new ConcurrentHashMap<>();

    public CurrentUserService(JdbcClient jdbc, TenantTx tenantTx) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
    }

    public Actor require() {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        if (!(auth instanceof JwtAuthenticationToken token)) {
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED);
        }
        Jwt jwt = token.getToken();

        UUID orgId = parseOrg(jwt.getClaimAsString("org_id"));
        Set<String> roles = roles(jwt);
        String role = ROLE_PRECEDENCE.stream().filter(roles::contains).findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "No Aegle role"));

        String cacheKey = jwt.getSubject() + "|" + orgId;
        Actor cached = cache.get(cacheKey);
        if (cached != null) {
            return new Actor(cached.userId(), orgId, jwt.getSubject(), roles);
        }

        boolean orgExists = jdbc.sql("SELECT count(*) FROM organizations WHERE id = :id")
                .param("id", orgId).query(Long.class).single() > 0;
        if (!orgExists) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Unknown organisation");
        }

        String email = orNull(jwt.getClaimAsString("email"), jwt.getSubject());
        String name = orNull(jwt.getClaimAsString("name"), email);
        UUID userId;
        try {
            userId = tenantTx.executeAs(orgId, () -> jdbc.sql("""
                    INSERT INTO users (org_id, idp_subject, email, full_name, role, last_login_at)
                    VALUES (:org, :sub, :email, :name, :role, now())
                    ON CONFLICT (idp_subject) DO UPDATE
                       SET email = EXCLUDED.email, full_name = EXCLUDED.full_name,
                           role = EXCLUDED.role, last_login_at = now()
                    RETURNING id""")
                    .param("org", orgId).param("sub", jwt.getSubject())
                    .param("email", email).param("name", name).param("role", role)
                    .query(UUID.class).single());
        } catch (DataAccessException e) {
            // e.g. the same login now claims a different organisation: refuse rather than guess.
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Account cannot be provisioned");
        }
        cache.put(cacheKey, new Actor(userId, orgId, jwt.getSubject(), roles));
        return new Actor(userId, orgId, jwt.getSubject(), roles);
    }

    private static UUID parseOrg(String claim) {
        if (claim == null || claim.isBlank()) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Token has no organisation");
        }
        try {
            return UUID.fromString(claim);
        } catch (IllegalArgumentException e) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Invalid organisation");
        }
    }

    @SuppressWarnings("unchecked")
    private static Set<String> roles(Jwt jwt) {
        Map<String, Object> realm = jwt.getClaimAsMap("realm_access");
        if (realm == null || !(realm.get("roles") instanceof List<?> list)) {
            return Set.of();
        }
        return ((List<Object>) list).stream().map(String::valueOf).collect(Collectors.toSet());
    }

    private static String orNull(String v, String fallback) {
        return v == null || v.isBlank() ? fallback : v;
    }
}
