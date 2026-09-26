package com.aegle.unit;

import static org.assertj.core.api.Assertions.assertThat;

import com.aegle.config.AegleProperties;
import com.aegle.inference.InferenceClient.Label;
import com.aegle.inference.TriagePolicy;
import com.aegle.inference.Urgency;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class TriagePolicyTest {

    private final TriagePolicy policy = new TriagePolicy(new AegleProperties(null, null, null, null, null, null, null,
            new AegleProperties.Triage(
                    Map.of(Urgency.CRITICAL, 100.0, Urgency.URGENT, 60.0, Urgency.ROUTINE, 10.0),
                    Map.of(Urgency.CRITICAL, Duration.ofHours(1), Urgency.URGENT, Duration.ofHours(4),
                            Urgency.ROUTINE, Duration.ofHours(24)),
                    Map.of("PNEUMONIA", Urgency.URGENT, "NORMAL", Urgency.ROUTINE), 0.5, 20)));

    @Test
    void scoreIsTheProbabilityWeightedUrgency() {
        var score = policy.score(List.of(new Label("PNEUMONIA", 0.9), new Label("NORMAL", 0.1)));
        assertThat(score.priority()).isEqualTo(55.0);                 // 0.9x60 + 0.1x10
        assertThat(score.urgency()).isEqualTo(Urgency.URGENT);
        assertThat(score.sla()).isEqualTo(Duration.ofHours(4));
    }

    @Test
    void aConfidentNormalRanksBelowAnUncertainPneumonia() {
        var normal = policy.score(List.of(new Label("NORMAL", 0.99), new Label("PNEUMONIA", 0.01)));
        var unsure = policy.score(List.of(new Label("PNEUMONIA", 0.55), new Label("NORMAL", 0.45)));
        assertThat(normal.urgency()).isEqualTo(Urgency.ROUTINE);
        assertThat(unsure.priority()).isGreaterThan(normal.priority());
    }

    @Test
    void unmappedLabelsDefaultToRoutineNotToSilence() {
        var score = policy.score(List.of(new Label("SOMETHING_NEW", 1.0)));
        assertThat(score.urgency()).isEqualTo(Urgency.ROUTINE);
        assertThat(score.priority()).isEqualTo(10.0);
    }

    @Test
    void theReasonListsEveryTerm() {
        var score = policy.score(List.of(new Label("PNEUMONIA", 0.7), new Label("NORMAL", 0.3)));
        assertThat(score.reason()).containsKeys("topLabel", "topProbability", "urgencyClass", "terms", "formula");
        assertThat((List<?>) score.reason().get("terms")).hasSize(2);
    }
}
