package com.aegle.unit;

import static org.assertj.core.api.Assertions.assertThat;

import com.aegle.security.RateLimiter;
import java.util.concurrent.atomic.AtomicLong;
import org.junit.jupiter.api.Test;

class RateLimiterTest {

    private final AtomicLong now = new AtomicLong();
    private final RateLimiter limiter = new RateLimiter(60, now::get);   // one per second sustained

    @Test
    void allowsABurstUpToCapacityThenAsksToWait() {
        for (int i = 0; i < 60; i++) {
            assertThat(limiter.tryAcquire("a")).isZero();
        }
        assertThat(limiter.tryAcquire("a")).isEqualTo(1);
    }

    @Test
    void refillsOverTime() {
        for (int i = 0; i < 60; i++) {
            limiter.tryAcquire("a");
        }
        now.addAndGet(3_000_000_000L);
        assertThat(limiter.tryAcquire("a")).isZero();
        assertThat(limiter.tryAcquire("a")).isZero();
        assertThat(limiter.tryAcquire("a")).isZero();
        assertThat(limiter.tryAcquire("a")).isPositive();
    }

    @Test
    void keysAreIndependent() {
        for (int i = 0; i < 60; i++) {
            limiter.tryAcquire("a");
        }
        assertThat(limiter.tryAcquire("a")).isPositive();
        assertThat(limiter.tryAcquire("b")).isZero();
    }
}
