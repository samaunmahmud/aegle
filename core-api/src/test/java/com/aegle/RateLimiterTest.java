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
        for (int i = 0; i < 60; i++) {
            limiter.tryAcquire("b", key, 60);
        }
        assertThat(limiter.tryAcquire("b", key, 60)).isPositive();
        Thread.sleep(1_100);                                      // one token per second
        assertThat(limiter.tryAcquire("b", key, 60)).isZero();
        assertThat(limiter.tryAcquire("b", key, 60)).isPositive();
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
