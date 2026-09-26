package com.aegle.support;

import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.inference.InferenceClient;
import com.aegle.inference.InferenceWorker;
import com.aegle.inference.ModelRegistrySync;
import com.aegle.storage.ObjectStore;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.RequestPostProcessor;
import org.testcontainers.containers.PostgreSQLContainer;

/**
 * Real Postgres (with the production migrations and the restricted application role),
 * stubbed inference and in-memory object storage. Each test gets its own organisation,
 * so tests never see each other's data.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Import(TestStubs.class)
public abstract class IntegrationTestBase {

    protected static final PostgreSQLContainer<?> PG =
            new PostgreSQLContainer<>("postgres:16").withInitScript("test-init.sql");

    static {
        PG.start();
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry r) {
        r.add("server.ssl.enabled", () -> "false");
        r.add("spring.datasource.url", PG::getJdbcUrl);
        r.add("spring.datasource.password", () -> "test-app");
        r.add("spring.flyway.url", PG::getJdbcUrl);
        r.add("spring.flyway.user", PG::getUsername);
        r.add("spring.flyway.password", PG::getPassword);
        r.add("spring.flyway.locations", () -> "classpath:db/migration");
        r.add("aegle.storage.access-key", () -> "test");
        r.add("aegle.storage.secret-key", () -> "test-secret");
        r.add("aegle.inference.token", () -> "test-inference-token");
        r.add("aegle.phi.enc-key", () -> key());
        r.add("aegle.phi.hash-key", () -> key());
        r.add("aegle.worker.enabled", () -> "false");          // tests drive the worker by hand
        r.add("aegle.worker.max-attempts", () -> "2");
        r.add("aegle.worker.retry-backoff", () -> "0s");
        r.add("aegle.models.auto-activate", () -> "true");
        r.add("aegle.models.sync-initial-delay-ms", () -> "3600000");
        r.add("aegle.models.sync-interval-ms", () -> "3600000");
    }

    private static String key() {
        byte[] k = new byte[32];
        new java.security.SecureRandom().nextBytes(k);
        return Base64.getEncoder().encodeToString(k);
    }

    @Autowired protected MockMvc mvc;
    @Autowired protected ObjectMapper json;
    @Autowired protected StubInferenceClient inference;
    @Autowired protected InMemoryObjectStore store;
    @Autowired protected InferenceWorker worker;
    @Autowired protected ModelRegistrySync registry;

    /** Connects as the schema owner (a superuser here), so it sees every tenant: for assertions only. */
    protected final JdbcTemplate owner = new JdbcTemplate(
            new DriverManagerDataSource(PG.getJdbcUrl(), PG.getUsername(), PG.getPassword()));

    protected UUID org;

    @BeforeEach
    void freshTenant() {
        inference.reset();
        registry.sync();
        org = newOrg();
    }

    protected UUID newOrg() {
        UUID id = UUID.randomUUID();
        owner.update("INSERT INTO organizations (id, name) VALUES (?, ?)", id, "Test org " + id);
        return id;
    }

    /** A signed-in user of `orgId` holding the given roles. */
    protected RequestPostProcessor as(String subject, UUID orgId, String... roles) {
        return jwt().jwt(j -> j.subject(subject).claim("org_id", orgId.toString())
                        .claim("email", subject + "@test.local").claim("name", subject)
                        .claim("realm_access", Map.of("roles", List.of(roles))))
                .authorities(java.util.Arrays.stream(roles)
                        .map(r -> (GrantedAuthority) new SimpleGrantedAuthority("ROLE_" + r))
                        .toArray(GrantedAuthority[]::new));
    }

    protected RequestPostProcessor radiologist() {
        return as("rad-" + org, org, "RADIOLOGIST");
    }

    /** A fake image whose 9th byte is the stub's pneumonia probability in percent. */
    protected static byte[] image(int pneumoniaPercent) {
        return new byte[]{(byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, (byte) pneumoniaPercent, 0, 0, 0};
    }

    protected UUID upload(RequestPostProcessor user, String mrn, int pneumoniaPercent) throws Exception {
        String body = mvc.perform(multipart("/api/studies")
                        .file(new MockMultipartFile("file", "scan.png", "image/png", image(pneumoniaPercent)))
                        .param("patientMrn", mrn).param("patientName", "Test Patient " + mrn)
                        .with(user))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString();
        return UUID.fromString(json.readTree(body).get("studyId").asText());
    }

    protected JsonNode body(MvcResult r) throws Exception {
        return json.readTree(r.getResponse().getContentAsString());
    }

    protected InferenceClient inferenceClient() {
        return inference;
    }

    protected ObjectStore objectStore() {
        return store;
    }
}
