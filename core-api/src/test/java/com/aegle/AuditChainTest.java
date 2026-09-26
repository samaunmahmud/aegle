package com.aegle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.audit.AuditService;
import com.aegle.support.IntegrationTestBase;
import com.aegle.tenant.TenantTx;
import com.fasterxml.jackson.databind.JsonNode;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.ConnectionCallback;

class AuditChainTest extends IntegrationTestBase {

    @Autowired AuditService audit;
    @Autowired TenantTx tenantTx;

    private JsonNode verify() throws Exception {
        return body(mvc.perform(get("/api/audit/verify").with(as("auditor-" + org, org, "AUDITOR")))
                .andExpect(status().isOk()).andReturn());
    }

    @Test
    void entriesFormAnIntactChainPerTenant() throws Exception {
        upload(radiologist(), "CHAIN-1", 40);
        JsonNode v = verify();
        assertThat(v.get("intact").asBoolean()).isTrue();
        assertThat(v.get("entries").asLong()).isPositive();
        assertThat(v.get("headHash").asText()).hasSize(64);

        List<Long> seqs = owner.queryForList("SELECT seq FROM audit_log WHERE org_id = ? ORDER BY seq", Long.class, org);
        for (int i = 0; i < seqs.size(); i++) {
            assertThat(seqs.get(i)).isEqualTo(i + 1L);
        }
    }

    @Test
    void concurrentWritersNeverForkTheChain() throws Exception {
        ExecutorService pool = Executors.newFixedThreadPool(8);
        try {
            List<Future<?>> done = new ArrayList<>();
            for (int t = 0; t < 8; t++) {
                done.add(pool.submit(() -> {
                    for (int i = 0; i < 10; i++) {
                        tenantTx.runAs(org, () -> audit.record(org, null, "TEST", "test", "x", Map.of()));
                    }
                }));
            }
            for (Future<?> f : done) {
                f.get();
            }
        } finally {
            pool.shutdown();
        }
        JsonNode v = verify();
        assertThat(v.get("intact").asBoolean()).isTrue();
        assertThat(v.get("entries").asLong()).isGreaterThanOrEqualTo(80);
    }

    @Test
    void editingHistoryBehindTheAppsBackIsDetected() throws Exception {
        upload(radiologist(), "CHAIN-2", 40);
        // A superuser can bypass the append-only triggers; the chain still exposes the edit.
        owner.execute((ConnectionCallback<Void>) c -> {
            try (Statement s = c.createStatement()) {
                s.execute("SET session_replication_role = replica");
                s.executeUpdate("UPDATE audit_log SET entity_id = 'forged' WHERE org_id = '" + org + "' AND seq = 1");
                s.execute("SET session_replication_role = origin");
            }
            return null;
        });
        JsonNode v = verify();
        assertThat(v.get("intact").asBoolean()).isFalse();
        assertThat(v.get("firstBrokenSeq").asLong()).isEqualTo(1);
    }

    @Test
    void cliniciansCannotRunTheCheck() throws Exception {
        mvc.perform(get("/api/audit/verify").with(radiologist())).andExpect(status().isForbidden());
    }
}
