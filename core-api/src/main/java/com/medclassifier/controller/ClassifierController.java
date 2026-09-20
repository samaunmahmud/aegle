package com.medclassifier.controller;

import com.medclassifier.model.PredictionResult;
import com.medclassifier.service.ModelTrainer;
import com.medclassifier.service.PredictionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.util.Map;

/**
 * REST API surface:
 *
 *   POST /api/predict   — upload an X-ray image, get back a JSON prediction
 *   POST /api/train     — kick off model training (blocks until done)
 *   GET  /api/status    — check whether the model is loaded
 */
@RestController
@RequestMapping("/api")
public class ClassifierController {

    private static final Logger log = LoggerFactory.getLogger(ClassifierController.class);

    private final PredictionService predictionService;
    private final ModelTrainer modelTrainer;

    public ClassifierController(PredictionService predictionService, ModelTrainer modelTrainer) {
        this.predictionService = predictionService;
        this.modelTrainer = modelTrainer;
    }

    // ------------------------------------------------------------------
    // POST /api/predict
    // ------------------------------------------------------------------

    /**
     * Accepts a single chest X-ray image (JPEG / PNG) and returns JSON:
     * {
     *   "label": "PNEUMONIA",
     *   "confidence": 0.93,
     *   "normalProbability": 0.07,
     *   "pneumoniaProbability": 0.93,
     *   "modelLoaded": true
     * }
     */
    @PostMapping("/predict")
    public ResponseEntity<?> predict(@RequestParam("image") MultipartFile image) {

        if (image.isEmpty()) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "No image file received."));
        }

        String contentType = image.getContentType();
        if (contentType == null ||
            (!contentType.startsWith("image/jpeg") && !contentType.startsWith("image/png"))) {
            return ResponseEntity.badRequest()
                    .body(Map.of("error", "Only JPEG and PNG images are supported."));
        }

        try {
            PredictionResult result = predictionService.predict(image);
            return ResponseEntity.ok(result);
        } catch (IllegalStateException e) {
            // Model not trained yet
            return ResponseEntity.status(503)
                    .body(Map.of("error", e.getMessage()));
        } catch (Exception e) {
            log.error("Prediction failed", e);
            return ResponseEntity.internalServerError()
                    .body(Map.of("error", "Prediction failed: " + e.getMessage()));
        }
    }

    // ------------------------------------------------------------------
    // POST /api/train
    // ------------------------------------------------------------------

    /**
     * Triggers training synchronously. In production you'd offload this
     * to an async task — for a portfolio project, blocking is fine.
     *
     * Call: curl -X POST http://localhost:8080/api/train
     */
    @PostMapping("/train")
    public ResponseEntity<?> train() {
        log.info("Training requested via REST API");
        try {
            modelTrainer.trainAndSave();
            // Reload model after training
            predictionService.loadModel();
            return ResponseEntity.ok(Map.of(
                "message", "Training complete. Model is ready for predictions."
            ));
        } catch (Exception e) {
            log.error("Training failed", e);
            return ResponseEntity.internalServerError()
                    .body(Map.of("error", "Training failed: " + e.getMessage()));
        }
    }

    // ------------------------------------------------------------------
    // GET /api/status
    // ------------------------------------------------------------------

    @GetMapping("/status")
    public ResponseEntity<?> status() {
        return ResponseEntity.ok(Map.of(
            "modelLoaded", predictionService.isModelLoaded(),
            "message", predictionService.isModelLoaded()
                ? "Model is loaded and ready."
                : "Model not loaded. Run POST /api/train first."
        ));
    }
}
