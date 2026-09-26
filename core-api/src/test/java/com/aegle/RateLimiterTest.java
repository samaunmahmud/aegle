package com.aegle;

import static org.assertj.core.api.Assertions.assertThat;

import com.aegle.security.RateLimiter;
import com.aegle.support.IntegrationTestBase;
import java.util.UUID;
import javax.sql.DataSource;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.simple.JdbcClient;

class RateLimiterTest extends IntegrationTestBase {

    @Autowired RateLimiter limiter;
    @Autowired DataSource dataSource;

    private final String key = "test:" + UUID.randomUUID();

    @Test
    void allowsABurstUpToCapacityThenAsksToWait() {
        for (int i = 0; i < 10; i++) {
            assertThat(limiter.tryAcquire("b", key, 10)).isZero();
        }
        assertThat(limiter.tryAcquire("b", key, 10)).isBetween(1L, 6L);
    }

    @Test
    void refillsOverTime() throws Exception {
        // 30 per minute = one token every 2 s. Drain it; on a busy machine a token may come
        // back while draining, so keep taking until the bucket is actually empty.
        for (int i = 0; i < 30; i++) {
            limiter.tryAcquire("b", key, 30);
        }
        int extra = 0;
        while (limiter.tryAcquire("b", key, 30) == 0) {
            assertThat(++extra).as("bucket never runs dry").isLessThan(5);
        }
        Thread.sleep(2_200);
        assertThat(limiter.tryAcquire("b", key, 30)).isZero();    // a token has refilled
    }

    @Test
    void bucketsAndKeysAreIndependent() {
        for (int i = 0; i < 3; i++) {
            limiter.tryAcquire("b", key, 3);
        }
        assertThat(limiter.tryAcquire("b", key, 3)).isPositive();
        assertThat(limiter.tryAcquire("other", key, 3)).isZero();
        assertThat(limiter.tryAcquire("b", key + "-2", 3)).isZero();
    }

    @Test
    void separateApiInstancesShareOneBudget() {
        RateLimiter secondInstance = new RateLimiter(JdbcClient.create(dataSource));
        for (int i = 0; i < 4; i++) {
            assertThat((i % 2 == 0 ? limiter : secondInstance).tryAcquire("b", key, 4)).isZero();
        }
        assertThat(limiter.tryAcquire("b", key, 4)).isPositive();
        assertThat(secondInstance.tryAcquire("b", key, 4)).isPositive();
    }
}
