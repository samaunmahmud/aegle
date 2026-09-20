package com.aegle.inference;

import com.aegle.config.AegleProperties;
import java.time.Duration;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

/**
 * Turns model output into a worklist priority a clinician can inspect.
 *
 * priority = sum over labels of (probability x weight of that label's urgency class).
 * Every term is recorded in {@code reason}, and waiting time is added at query time, so
 * "why is this case ranked here" always has a complete answer. The score is a
 * prioritisation aid, not a diagnosis, and probabilities are uncalibrated for now.
 */
@Component
public class TriagePolicy {

    public record Score(double priority, Urgency urgency, Duration sla, Map<String, Object> reason) {}

    private final AegleProperties.Triage cfg;

    public TriagePolicy(AegleProperties props) {
        this.cfg = props.triage();
    }

    public Urgency urgencyOf(String label) {
        return cfg.labelUrgency().getOrDefault(label, Urgency.ROUTINE);
    }

    public Score score(List<InferenceClient.Label> predictions) {
        InferenceClient.Label top = predictions.get(0);
        double total = 0;
        List<Map<String, Object>> terms = new ArrayList<>();
        for (InferenceClient.Label p : predictions) {
            Urgency u = urgencyOf(p.label());
            double weight = cfg.weights().get(u);
            double contribution = p.probability() * weight;
            total += contribution;
            Map<String, Object> term = new LinkedHashMap<>();
            term.put("label", p.label());
            term.put("probability", round(p.probability()));
            term.put("urgencyClass", u.name());
            term.put("weight", weight);
            term.put("contribution", round(contribution));
            terms.add(term);
        }
        Urgency topUrgency = urgencyOf(top.label());
        Map<String, Object> reason = new LinkedHashMap<>();
        reason.put("topLabel", top.label());
        reason.put("topProbability", round(top.probability()));
        reason.put("urgencyClass", topUrgency.name());
        reason.put("terms", terms);
        reason.put("formula", "priority = sum(probability x urgency weight); waiting time adds up to "
                + cfg.waitBonusCap() + " points at " + cfg.waitBonusPerHour() + " per hour");
        return new Score(round(total), topUrgency, cfg.sla().get(topUrgency), reason);
    }

    private static double round(double v) {
        return Math.round(v * 10_000d) / 10_000d;
    }
}
