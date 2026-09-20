package com.medclassifier.model;

/**
 * JSON response returned by the /api/predict endpoint.
 */
public class PredictionResult {

    /** "NORMAL" or "PNEUMONIA" */
    private String label;

    /** Confidence of the predicted class, 0.0 – 1.0 */
    private double confidence;

    /** Probability of NORMAL class */
    private double normalProbability;

    /** Probability of PNEUMONIA class */
    private double pneumoniaProbability;

    /** True when a saved model was available; false = demo fallback */
    private boolean modelLoaded;

    public PredictionResult() {}

    public PredictionResult(String label, double confidence,
                            double normalProbability, double pneumoniaProbability,
                            boolean modelLoaded) {
        this.label = label;
        this.confidence = confidence;
        this.normalProbability = normalProbability;
        this.pneumoniaProbability = pneumoniaProbability;
        this.modelLoaded = modelLoaded;
    }

    // ----- getters & setters -----

    public String getLabel() { return label; }
    public void setLabel(String label) { this.label = label; }

    public double getConfidence() { return confidence; }
    public void setConfidence(double confidence) { this.confidence = confidence; }

    public double getNormalProbability() { return normalProbability; }
    public void setNormalProbability(double normalProbability) {
        this.normalProbability = normalProbability;
    }

    public double getPneumoniaProbability() { return pneumoniaProbability; }
    public void setPneumoniaProbability(double pneumoniaProbability) {
        this.pneumoniaProbability = pneumoniaProbability;
    }

    public boolean isModelLoaded() { return modelLoaded; }
    public void setModelLoaded(boolean modelLoaded) { this.modelLoaded = modelLoaded; }
}
