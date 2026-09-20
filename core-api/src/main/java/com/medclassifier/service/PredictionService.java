package com.medclassifier.service;

import com.medclassifier.model.PredictionResult;
import jakarta.annotation.PostConstruct;
import org.datavec.image.loader.NativeImageLoader;
import org.deeplearning4j.nn.multilayer.MultiLayerNetwork;
import org.deeplearning4j.util.ModelSerializer;
import org.nd4j.linalg.api.ndarray.INDArray;
import org.nd4j.linalg.dataset.api.preprocessor.ImagePreProcessingScaler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.File;
import java.io.InputStream;

/**
 * Loads the saved CNN model at startup and runs inference on uploaded images.
 *
 * Label mapping:
 *   index 0 → NORMAL
 *   index 1 → PNEUMONIA
 */
@Service
public class PredictionService {

    private static final Logger log = LoggerFactory.getLogger(PredictionService.class);

    private static final String[] LABELS = {"NORMAL", "PNEUMONIA"};

    @Value("${app.model.path}")
    private String modelPath;

    @Value("${app.image.height}")
    private int imageHeight;

    @Value("${app.image.width}")
    private int imageWidth;

    @Value("${app.image.channels}")
    private int channels;

    private MultiLayerNetwork model;
    private boolean modelLoaded = false;
    private final ImagePreProcessingScaler scaler = new ImagePreProcessingScaler(0, 1);

    /**
     * Tries to load the saved model when the Spring context starts.
     * If the model file doesn't exist yet (not trained), the app still
     * starts but predictions will return a "model not loaded" error.
     */
    @PostConstruct
    public void loadModel() {
        File modelFile = new File(modelPath);
        if (modelFile.exists()) {
            try {
                model = ModelSerializer.restoreMultiLayerNetwork(modelFile);
                modelLoaded = true;
                log.info("Model loaded from {}", modelPath);
            } catch (Exception e) {
                log.error("Failed to load model: {}", e.getMessage());
            }
        } else {
            log.warn("Model file not found at {}. Train the model first via POST /api/train", modelPath);
        }
    }

    /**
     * Classifies an uploaded chest X-ray image.
     *
     * @param file the multipart image upload (JPEG / PNG)
     * @return PredictionResult with label, confidence, and per-class probabilities
     */
    public PredictionResult predict(MultipartFile file) throws Exception {
        if (!modelLoaded) {
            throw new IllegalStateException(
                "Model is not loaded. Please train first via POST /api/train");
        }

        // ---- 1. Load and resize image to model input dimensions ----
        NativeImageLoader loader = new NativeImageLoader(imageHeight, imageWidth, channels);
        INDArray imageArray;
        try (InputStream inputStream = file.getInputStream()) {
            imageArray = loader.asMatrix(inputStream);
        }

        // ---- 2. Normalize pixels [0, 255] → [0, 1] ----
        scaler.transform(imageArray);

        // ---- 3. Run forward pass ----
        INDArray output = model.output(imageArray);

        // ---- 4. Extract per-class probabilities ----
        double normalProb     = output.getDouble(0, 0); // index 0 = NORMAL
        double pneumoniaProb  = output.getDouble(0, 1); // index 1 = PNEUMONIA

        // ---- 5. Pick winner ----
        int predictedIndex = pneumoniaProb >= normalProb ? 1 : 0;
        String predictedLabel = LABELS[predictedIndex];
        double confidence = Math.max(normalProb, pneumoniaProb);

        log.debug("Prediction: {} (confidence {:.3f}), NORMAL={:.3f}, PNEUMONIA={:.3f}",
                predictedLabel, confidence, normalProb, pneumoniaProb);

        return new PredictionResult(
                predictedLabel,
                confidence,
                normalProb,
                pneumoniaProb,
                true
        );
    }

    public boolean isModelLoaded() {
        return modelLoaded;
    }
}
