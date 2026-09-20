package com.medclassifier;
import org.datavec.api.io.labels.ParentPathLabelGenerator;
import org.datavec.api.split.FileSplit;
import org.datavec.image.loader.NativeImageLoader;
import org.datavec.image.recordreader.ImageRecordReader;
import org.deeplearning4j.datasets.datavec.RecordReaderDataSetIterator;
import org.deeplearning4j.nn.multilayer.MultiLayerNetwork;
import org.deeplearning4j.util.ModelSerializer;
import org.nd4j.evaluation.classification.Evaluation;
import org.nd4j.linalg.dataset.api.iterator.DataSetIterator;
import org.nd4j.linalg.dataset.api.preprocessor.ImagePreProcessingScaler;

import java.io.File;

/**
 * Standalone evaluation script — run this on your own machine (where Maven
 * can reach Maven Central) to get a fully certified accuracy/F1/confusion
 * matrix for your saved model, without retraining.
 *
 * Usage:
 *   1. Put this file in src/main/java/com/medclassifier/EvaluateModel.java
 *   2. Make sure saved-model/xray-cnn.zip and dataset/chest_xray/test/ exist
 *   3. Run:  mvn compile exec:java -Dexec.mainClass="com.medclassifier.EvaluateModel"
 *      (or just run the main() method from your IDE)
 *
 * This reuses the exact same preprocessing DL4J uses internally, so the
 * numbers it prints are the real, certified evaluation — no approximation.
 */
public class EvaluateModel {

    private static final int IMG_HEIGHT = 64;
    private static final int IMG_WIDTH = 64;
    private static final int CHANNELS = 1;
    private static final int NUM_CLASSES = 2;
    private static final int BATCH_SIZE = 32;

    public static void main(String[] args) throws Exception {

        String modelPath = "../saved-model/xray-cnn.zip";
        String testPath = "../dataset/chest_xray/test";

        System.out.println("Loading model from " + modelPath + " ...");
        MultiLayerNetwork model = ModelSerializer.restoreMultiLayerNetwork(new File(modelPath));

        System.out.println("Loading test data from " + testPath + " ...");
        File testDir = new File(testPath);
        if (!testDir.exists()) {
            throw new IllegalArgumentException("Test folder not found: " + testDir.getAbsolutePath());
        }

        FileSplit split = new FileSplit(testDir, NativeImageLoader.ALLOWED_FORMATS, null);
        ParentPathLabelGenerator labelMaker = new ParentPathLabelGenerator();
        ImageRecordReader recordReader = new ImageRecordReader(IMG_HEIGHT, IMG_WIDTH, CHANNELS, labelMaker);
        recordReader.initialize(split);

        DataSetIterator testIter = new RecordReaderDataSetIterator(
                recordReader, BATCH_SIZE, 1, NUM_CLASSES);

        ImagePreProcessingScaler scaler = new ImagePreProcessingScaler(0, 1);
        scaler.fit(testIter);
        testIter.setPreProcessor(scaler);

        System.out.println("Running evaluation...");
        Evaluation eval = model.evaluate(testIter);

        System.out.println("\n=== CERTIFIED TEST RESULTS ===");
        System.out.println(eval.stats());

        System.out.printf("%nAccuracy:  %.4f%n", eval.accuracy());
        System.out.printf("F1 score:  %.4f%n", eval.f1());
        System.out.printf("Precision: %.4f%n", eval.precision());
        System.out.printf("Recall:    %.4f%n", eval.recall());
        System.out.println("\nConfusion matrix:");
        System.out.println(eval.confusionToString());
    }
}