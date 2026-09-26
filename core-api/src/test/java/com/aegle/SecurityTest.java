package com.aegle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.support.IntegrationTestBase;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessException;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.mock.web.MockMultipartFile;

class SecurityTest extends IntegrationTestBase {

    private JdbcTemplate appRole() {
        return new JdbcTemplate(new DriverManagerDataSource(PG.getJdbcUrl(), "aegle_app", "test-app"));
    }

    // ---- authentication

    @Test
    void requestsWithoutATokenAreRejected() throws Exception {
        mvc.perform(get("/api/worklist")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/me")).andExpect(status().isUnauthorized());
    }

    @Test
    void healthIsPublicButNothingElseIs() throws Exception {
        mvc.perform(get("/actuator/health")).andExpect(status().isOk());
        mvc.perform(get("/actuator/env")).andExpect(status().isUnauthorized());
    }

    @Test
    void responsesForbidScriptsFramingAndCaching() throws Exception {
        mvc.perform(get("/api/me").with(radiologist()))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"))
                .andExpect(header().string("X-Content-Type-Options", "nosniff"))
                .andExpect(header().string("X-Frame-Options", "DENY"))
                .andExpect(header().string("Referrer-Policy", "no-referrer"))
                .andExpect(header().exists("Permissions-Policy"))
                .andExpect(header().string("Cache-Control", containsString("no-store")));
        mvc.perform(get("/api/me").secure(true).with(radiologist()))
                .andExpect(header().string("Strict-Transport-Security", "max-age=31536000 ; includeSubDomains"));
    }

    @Test
    void tokensWithoutAValidTenantOrRoleAreRefused() throws Exception {
        var noOrg = jwt().jwt(j -> j.subject("u1").claim("realm_access", Map.of("roles", List.of("RADIOLOGIST"))));
        mvc.perform(get("/api/me").with(noOrg)).andExpect(status().isForbidden());

        mvc.perform(get("/api/me").with(as("u2", UUID.randomUUID(), "RADIOLOGIST")))
                .andExpect(status().isForbidden());                       // organisation does not exist

        mvc.perform(get("/api/me").with(as("u3", org))).andExpect(status().isForbidden());   // no role

        var badOrg = jwt().jwt(j -> j.subject("u4").claim("org_id", "not-a-uuid")
                .claim("realm_access", Map.of("roles", List.of("RADIOLOGIST"))));
        mvc.perform(get("/api/me").with(badOrg)).andExpect(status().isForbidden());
    }

    @Test
    void aValidTokenIsMappedToAUserInItsOwnTenant() throws Exception {
        mvc.perform(get("/api/me").with(as("carol", org, "RADIOLOGIST")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.organisationId").value(org.toString()))
                .andExpect(jsonPath("$.roles[0]").value("RADIOLOGIST"));
        assertThat(owner.queryForObject("SELECT org_id FROM users WHERE idp_subject = 'carol'", UUID.class))
                .isEqualTo(org);
    }

    @Test
    void deactivatedUsersAreRefusedEvenWithAValidToken() throws Exception {
        owner.update("""
                INSERT INTO users (org_id, idp_subject, email, full_name, role, active)
                VALUES (?, 'dave', 'dave@test.local', 'dave', 'RADIOLOGIST', false)""", org);
        var dave = as("dave", org, "RADIOLOGIST");
        mvc.perform(get("/api/me").with(dave)).andExpect(status().isForbidden());
        mvc.perform(get("/api/worklist").with(dave)).andExpect(status().isForbidden());
    }

    // ---- roles

    @Test
    void auditorsAndAdminsCannotSeePatientData() throws Exception {
        for (String role : List.of("AUDITOR", "ADMIN")) {
            var user = as("nonclinical-" + role, org, role);
            mvc.perform(get("/api/worklist").with(user)).andExpect(status().isForbidden());
            mvc.perform(get("/api/studies").with(user)).andExpect(status().isForbidden());
            mvc.perform(multipart("/api/studies")
                            .file(new MockMultipartFile("file", "x.png", "image/png", image(50)))
                            .param("patientMrn", "X").with(user))
                    .andExpect(status().isForbidden());
        }
    }

    @Test
    void cliniciansCannotReadTheAuditLog() throws Exception {
        mvc.perform(get("/api/audit").with(radiologist())).andExpect(status().isForbidden());
        mvc.perform(get("/api/audit").with(as("p", org, "PHYSICIAN"))).andExpect(status().isForbidden());
    }

    // ---- tenant isolation

    @Test
    void anotherOrganisationCannotSeeOrTouchAStudy() throws Exception {
        var mine = radiologist();
        UUID study = upload(mine, "SHARED-MRN", 90);
        worker.runOnce(org);
        String prediction = json.readTree(mvc.perform(get("/api/studies/{id}", study).with(mine))
                .andReturn().getResponse().getContentAsString()).at("/predictions/0/id").asText();

        UUID otherOrg = newOrg();
        var theirs = as("intruder-" + otherOrg, otherOrg, "RADIOLOGIST");

        mvc.perform(get("/api/studies/{id}", study).with(theirs)).andExpect(status().isNotFound());
        mvc.perform(get("/api/studies/{id}/heatmap", study).with(theirs)).andExpect(status().isNotFound());
        mvc.perform(get("/api/studies/{id}/image", study).with(theirs)).andExpect(status().isNotFound());
        mvc.perform(post("/api/worklist/{id}/claim", study).with(theirs)).andExpect(status().isNotFound());
        mvc.perform(post("/api/predictions/{id}/review", prediction).with(theirs)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"decision\":\"ACCEPT\"}"))
                .andExpect(status().isNotFound());
        mvc.perform(get("/api/worklist").with(theirs)).andExpect(jsonPath("$.total").value(0));
        mvc.perform(get("/api/studies").with(theirs)).andExpect(jsonPath("$.length()").value(0));

        // ...and their attempts changed nothing for the real owner.
        mvc.perform(get("/api/studies/{id}", study).with(mine))
                .andExpect(status().isOk()).andExpect(jsonPath("$.study.status").value("READY"));
    }

    @Test
    void theSameMrnInTwoOrganisationsIsTwoUnlinkedPatients() throws Exception {
        UUID other = newOrg();
        upload(radiologist(), "SAME-MRN", 50);
        upload(as("other-rad", other, "RADIOLOGIST"), "SAME-MRN", 50);

        List<Map<String, Object>> rows = owner.queryForList(
                "SELECT org_id, mrn_hash FROM patients WHERE org_id IN (?, ?)", org, other);
        assertThat(rows).hasSize(2);
        assertThat((byte[]) rows.get(0).get("mrn_hash")).isNotEqualTo((byte[]) rows.get(1).get("mrn_hash"));
    }

    @Test
    void theDatabaseRefusesToServeTenantRowsWithoutATenantContext() throws Exception {
        upload(radiologist(), "RLS-1", 50);
        assertThat(owner.queryForObject("SELECT count(*) FROM studies", Long.class)).isPositive();
        // The application role, with no `app.current_org_id` set, sees nothing at all.
        assertThat(appRole().queryForObject("SELECT count(*) FROM studies", Long.class)).isZero();
        assertThat(appRole().queryForObject("SELECT count(*) FROM patients", Long.class)).isZero();
    }

    // ---- PHI and audit

    @Test
    void patientIdentifiersAreEncryptedAtRest() throws Exception {
        upload(radiologist(), "SECRET-MRN-4471", 50);
        Map<String, Object> row = owner.queryForMap(
                "SELECT mrn_encrypted, name_encrypted FROM patients WHERE org_id = ?", org);
        assertThat(new String((byte[]) row.get("mrn_encrypted"))).doesNotContain("SECRET-MRN");
        assertThat(new String((byte[]) row.get("name_encrypted"))).doesNotContain("Test Patient");
        // Object keys and stored instance rows must not carry identifiers either.
        assertThat(store.objects.keySet()).noneMatch(k -> k.contains("SECRET") || k.contains("scan.png"));
    }

    @Test
    void everyAccessIsAuditedWithoutLeakingPatientData() throws Exception {
        var user = radiologist();
        UUID study = upload(user, "AUDIT-MRN-9931", 60);
        worker.runOnce(org);
        mvc.perform(get("/api/studies/{id}", study).with(user)).andExpect(status().isOk());
        mvc.perform(get("/api/studies/{id}/heatmap", study).with(user)).andExpect(status().isOk());

        String body = mvc.perform(get("/api/audit").with(as("aud-" + org, org, "AUDITOR")))
                .andExpect(status().isOk()).andReturn().getResponse().getContentAsString();
        JsonNode entries = json.readTree(body);
        assertThat(entries).extracting(n -> n.get("action").asText())
                .contains("STUDY_UPLOADED", "INFERENCE_COMPLETED", "STUDY_VIEWED", "HEATMAP_VIEWED");
        assertThat(entries).filteredOn(n -> n.get("action").asText().equals("INFERENCE_COMPLETED"))
                .allMatch(n -> n.get("actor").asText().equals("system"));
        assertThat(body).doesNotContain("AUDIT-MRN-9931").doesNotContain("Test Patient");

        // Reading the audit log is itself recorded.
        mvc.perform(get("/api/audit?action=AUDIT_VIEWED").with(as("aud-" + org, org, "AUDITOR")))
                .andExpect(jsonPath("$.length()").value(1));
    }

    @Test
    void theAuditLogCannotBeAlteredByAnyone() throws Exception {
        upload(radiologist(), "AUD-IMM", 50);
        assertThatThrownBy(() -> owner.update("UPDATE audit_log SET action = 'TAMPERED'"))
                .isInstanceOf(DataAccessException.class).hasMessageContaining("append-only");
        assertThatThrownBy(() -> owner.update("DELETE FROM audit_log"))
                .isInstanceOf(DataAccessException.class).hasMessageContaining("append-only");
        assertThatThrownBy(() -> appRole().update("DELETE FROM audit_log"))
                .isInstanceOf(DataAccessException.class).rootCause().hasMessageContaining("permission denied");
        assertThatThrownBy(() -> appRole().update("UPDATE audit_log SET action = 'x'"))
                .isInstanceOf(DataAccessException.class).rootCause().hasMessageContaining("permission denied");
    }
}
