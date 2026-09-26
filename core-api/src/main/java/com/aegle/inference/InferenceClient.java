package com.aegle.inference;

import java.util.List;
import java.util.Map;

/** Talks to the Python inference service. */
public interface InferenceClient {

    List<ModelInfo> models();

    /** @throws NonRetryableInferenceException when retrying the same input cannot succeed */
    Result predict(String modelId, byte[] image);

    /** A PNG rendering of any supported image, DICOM included, for display in browsers. */
    byte[] render(byte[] image);

    record ModelInfo(String id, String version, String modality, String bodyPart, String task,
                     String intendedUse, String weightsSha256, Map<String, Object> metrics) {}

    record Label(String label, double probability) {}

    record Heatmap(String method, String targetLabel, byte[] png) {}

    /** A quantity the model measured, e.g. wound area. */
    record Measurement(String name, double value, String unit) {}

    /** {@code predictions} is sorted by probability, highest first. */
    record Result(ModelInfo model, List<Label> predictions, Heatmap heatmap, List<Measurement> measurements) {
        public Result(ModelInfo model, List<Label> predictions, Heatmap heatmap) {
            this(model, predictions, heatmap, List.of());
        }
    }

    class NonRetryableInferenceException extends RuntimeException {
        public NonRetryableInferenceException(String message) {
            super(message);
        }
    }
}
