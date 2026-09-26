package com.aegle.config;

import com.aegle.inference.Urgency;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties("aegle")
public record AegleProperties(
        @Valid @NotNull Cors cors,
        @Valid @NotNull Storage storage,
        @Valid @NotNull Inference inference,
        @Valid @NotNull Phi phi,
        @Valid @NotNull Worker worker,
        @Valid @NotNull Models models,
        @Valid @NotNull RateLimit rateLimit,
        @Valid @NotNull Triage triage) {

    public record Cors(List<String> allowedOrigins) {}

    public record Storage(@NotBlank String endpoint, @NotBlank String accessKey,
                          @NotBlank String secretKey, @NotBlank String bucket) {}

    /** {@code token} is the shared secret the inference service requires on every model call. */
    public record Inference(@NotBlank String baseUrl, @NotBlank String token,
                            @NotNull Duration connectTimeout, @NotNull Duration readTimeout) {}

    /** Base64 keys, 32 bytes each. Missing or blank keys stop the application from starting. */
    public record Phi(@NotBlank String encKey, @NotBlank String hashKey) {}

    public record Worker(boolean enabled, long pollIntervalMs, int maxAttempts,
                         @NotNull Duration retryBackoff, @NotNull Duration staleAfter) {}

    public record Models(boolean autoActivate, long syncIntervalMs, long syncInitialDelayMs) {}

    public record RateLimit(@Positive int requestsPerMinute, @Positive int uploadsPerMinute) {}

    public record Triage(@NotNull Map<Urgency, Double> weights,
                         @NotNull Map<Urgency, Duration> sla,
                         @NotNull Map<String, Urgency> labelUrgency,
                         double waitBonusPerHour, double waitBonusCap) {}
}
