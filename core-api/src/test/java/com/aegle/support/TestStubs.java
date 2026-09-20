package com.aegle.support;

import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;

/** Replaces the real inference client and object store in integration tests. */
@TestConfiguration
public class TestStubs {
    @Bean @Primary StubInferenceClient stubInference() { return new StubInferenceClient(); }

    @Bean @Primary InMemoryObjectStore memoryStore() { return new InMemoryObjectStore(); }
}
