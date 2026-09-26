package com.aegle.security;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * Token buckets kept in Postgres ({@code rate_limit_acquire}, migration V4), so every API
 * instance draws from the same budget. One round trip per check.
 */
@Component
public class RateLimiter {

    private static final Logger log = LoggerFactory.getLogger(RateLimiter.class);

    private final JdbcClient jdbc;

    public RateLimiter(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /**
     * Takes one call from {@code key}'s bucket in {@code bucket}, which allows bursts of up
     * to {@code perMinute} and refills at that rate. Returns 0 if the call is allowed,
     * otherwise the whole seconds to wait.
     */
    public long tryAcquire(String bucket, String key, int perMinute) {
        try {
            double wait = jdbc.sql("SELECT rate_limit_acquire(:key, :capacity, :perSecond)")
                    .param("key", bucket + "|" + key)
                    .param("capacity", (double) perMinute)
                    .param("perSecond", perMinute / 60.0)
                    .query(Double.class).single();
            return wait <= 0 ? 0 : Math.max(1, (long) Math.ceil(wait));
        } catch (DataAccessException e) {
            // Without the database the request cannot succeed anyway; let it fail on its own terms.
            log.warn("Rate limit check unavailable ({}), allowing request", e.getClass().getSimpleName());
            return 0;
        }
    }

    /** A bucket idle for a minute is full again, so its row can go. */
    @Scheduled(fixedDelay = 300_000, initialDelay = 300_000)
    void purgeIdle() {
        jdbc.sql("DELETE FROM rate_limit_buckets WHERE updated_at < now() - interval '5 minutes'").update();
    }
}
