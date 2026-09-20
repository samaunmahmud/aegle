package com.aegle.tenant;

import java.util.UUID;
import java.util.function.Supplier;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Runs database work inside a transaction scoped to one tenant.
 *
 * Sets `app.current_org_id` for the transaction only (set_config(..., true)), which
 * Postgres row-level security policies read. Every query touching tenant data must go
 * through here: with no tenant set, RLS returns no rows instead of leaking another
 * organisation's data.
 */
@Component
public class TenantTx {

    private final TransactionTemplate tx;
    private final JdbcClient jdbc;

    public TenantTx(TransactionTemplate tx, JdbcClient jdbc) {
        this.tx = tx;
        this.jdbc = jdbc;
    }

    public <T> T executeAs(UUID orgId, Supplier<T> work) {
        return tx.execute(status -> {
            jdbc.sql("SELECT set_config('app.current_org_id', :org, true)")
                    .param("org", orgId.toString())
                    .query().singleValue();
            return work.get();
        });
    }

    public void runAs(UUID orgId, Runnable work) {
        executeAs(orgId, () -> {
            work.run();
            return null;
        });
    }
}
