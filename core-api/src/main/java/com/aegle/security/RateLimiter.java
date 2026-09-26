package com.aegle.security;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongSupplier;

/**
 * In-memory token buckets, one per key. Each bucket holds up to {@code perMinute} tokens and
 * refills continuously, so short bursts are allowed but the sustained rate is capped.
 *
 * Per-instance only: with several API replicas the effective limit is multiplied, which is
 * acceptable for abuse protection but not for quotas.
 */
public class RateLimiter {

    private static final long IDLE_EVICT_NANOS = 10L * 60 * 1_000_000_000;
    private static final int EVICT_THRESHOLD = 10_000;

    private final double capacity;
    private final double tokensPerNano;
    private final LongSupplier clock;
    private final Map<String, Bucket> buckets = new ConcurrentHashMap<>();

    private static final class Bucket {
        double tokens;
        long updated;

        Bucket(double tokens, long updated) {
            this.tokens = tokens;
            this.updated = updated;
        }
    }

    public RateLimiter(int perMinute, LongSupplier clock) {
        if (perMinute <= 0) {
            throw new IllegalArgumentException("perMinute must be positive");
        }
        this.capacity = perMinute;
        this.tokensPerNano = perMinute / 60e9;
        this.clock = clock;
    }

    /** Returns 0 if the call is allowed, otherwise the seconds to wait before retrying. */
    public long tryAcquire(String key) {
        long now = clock.getAsLong();
        if (buckets.size() > EVICT_THRESHOLD) {
            buckets.values().removeIf(b -> now - b.updated > IDLE_EVICT_NANOS);
        }
        Bucket b = buckets.computeIfAbsent(key, k -> new Bucket(capacity, now));
        synchronized (b) {
            b.tokens = Math.min(capacity, b.tokens + (now - b.updated) * tokensPerNano);
            b.updated = now;
            if (b.tokens >= 1) {
                b.tokens -= 1;
                return 0;
            }
            return Math.max(1, (long) Math.ceil((1 - b.tokens) / tokensPerNano / 1e9));
        }
    }
}
