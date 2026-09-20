package com.medclassifier;

import org.datavec.api.io.labels.ParentPathLabelGenerator;
import org.datavec.api.split.FileSplit;
import org.datavec.image.loader.NativeImageLoader;
import org.datavec.image.recordreader.ImageRecordReader;
import org.deeplearning4j.datasets.datavec.RecordReaderDataSetIterator;
import org.deeplearning4j.nn.conf.*;
import org.deeplearning4j.nn.conf.inputs.InputType;
import org.deeplearning4j.nn.conf.layers.*;
import org.deeplearning4j.nn.multilayer.MultiLayerNetwork;
import org.deeplearning4j.nn.weights.WeightInit;
import org.deeplearning4j.optimize.listeners.ScoreIterationListener;
import org.deeplearning4j.util.ModelSerializer;
import org.nd4j.evaluation.classification.Evaluation;
import org.nd4j.linalg.activations.Activation;
import org.nd4j.linalg.dataset.api.iterator.DataSetIterator;
import org.nd4j.linalg.dataset.api.preprocessor.ImagePreProcessingScaler;
import org.nd4j.linalg.learning.config.Adam;
import org.nd4j.linalg.lossfunctions.LossFunctions;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.File;
import java.util.Random;

/**
 * Builds, trains, and saves a CNN for chest X-ray classification.
 *
 * Architecture:
 * Input (1 x 64 x 64)
 * → Conv(32, 3x3, ReLU) → MaxPool(2x2)
 * → Conv(64, 3x3, ReLU) → MaxPool(2x2)
 * → Conv(128, 3x3, ReLU) → MaxPool(2x2)
 * → Flatten → Dense(256, ReLU) → Dropout(0.5)
 * → Dense(2, Softmax)  [NORMAL=0, PNEUMONIA=1]
 *
 * Expected dataset layout (Kaggle chest-xray-pneumonia):
 * dataset/chest_xray/
 * train/NORMAL/   train/PNEUMONIA/
 * test/NORMAL/    test/PNEUMONIA/
 */
@Service
public class ModelTrainer {

    private static final Logger log = LoggerFactory.getLogger(ModelTrainer.class);

    // ---- configurable via application.properties ----
    @Value("${app.dataset.path}")
    private String datasetPath;

    @Value("${app.model.path}")
    private String modelPath;

    @Value("${app.image.height}")
    private int imageHeight;

    @Value("${app.image.width}")
    private int imageWidth;

    @Value("${app.image.channels}")
    private int channels;

    @Value("${app.training.epochs}")
    private int epochs;

    @Value("${app.training.batch-size}")
    private int batchSize;

    @Value("${app.training.learning-rate}")
    private double learningRate;

    @Value("${app.training.seed}")
    private int seed;

    /** Number of output classes (NORMAL, PNEUMONIA). */
    private static final int NUM_CLASSES = 2;

    // -------------------------------------------------

    /**
     * Trains the CNN from scratch and saves it to disk.
     * Call this once; the web app loads the saved model at startup.
     */
    public void trainAndSave() throws Exception {

        log.info("=== Starting training ===");
        log.info("Dataset path : {}", datasetPath);
        log.info("Model output : {}", modelPath);

        // ---- 1. Load training data ----
        DataSetIterator trainIter = buildIterator(datasetPath + "/train", true);

        // ---- 2. Load test data ----
        DataSetIterator testIter = buildIterator(datasetPath + "/test", false);

        // ---- 3. Build model ----
        MultiLayerNetwork model = buildCNN();
        model.init();
        model.setListeners(new ScoreIterationListener(10));
        log.info("Model summary:\n{}", model.summary());

        // ---- 4. Train ----
        for (int epoch = 1; epoch <= epochs; epoch++) {
            log.info("--- Epoch {}/{} ---", epoch, epochs);
            model.fit(trainIter);
            trainIter.reset();

            // Evaluate on test set after every epoch
            Evaluation eval = model.evaluate(testIter);
            
            // FIXED: Using Java's String.format to correctly process decimal placement placeholders
            log.info(String.format("Epoch %d | Accuracy: %.4f | F1: %.4f", epoch, eval.accuracy(), eval.f1()));
            
            testIter.reset();
        }

        // ---- 5. Final evaluation ----
        // FIXED: Explicitly resetting test iterator before the final evaluation pass
        testIter.reset();
        Evaluation finalEval = model.evaluate(testIter);
        log.info("=== Final Test Results ===");
        log.info(finalEval.stats());

        // ---- 6. Save model ----
        File modelFile = new File(modelPath);
        modelFile.getParentFile().mkdirs();
        ModelSerializer.writeModel(model, modelFile, true);
        log.info("Model saved to {}", modelPath);
    }

    // ---------------------------------------------------------------
    //  Private helpers
    // ---------------------------------------------------------------

    /**
     * Creates a DataSetIterator that loads images from subfolders.
     * Each subfolder name becomes a class label (NORMAL / PNEUMONIA).
     */
    private DataSetIterator buildIterator(String folderPath, boolean shuffle) throws Exception {
        File parentDir = new File(folderPath);
        if (!parentDir.exists()) {
            throw new IllegalArgumentException(
                "Dataset folder not found: " + parentDir.getAbsolutePath() +
                "\nDownload from https://www.kaggle.com/datasets/paultimothymooney/chest-xray-pneumonia");
        }

        FileSplit split = new FileSplit(
                parentDir,
                NativeImageLoader.ALLOWED_FORMATS,
                shuffle ? new Random(seed) : null
        );

        // Label images by their parent folder name (NORMAL or PNEUMONIA)
        ParentPathLabelGenerator labelMaker = new ParentPathLabelGenerator();
        ImageRecordReader recordReader = new ImageRecordReader(imageHeight, imageWidth, channels, labelMaker);
        recordReader.initialize(split);

        DataSetIterator iterator = new RecordReaderDataSetIterator(
                recordReader, batchSize, 1, NUM_CLASSES);

        // Normalize pixel values from [0, 255] to [0, 1]
        ImagePreProcessingScaler scaler = new ImagePreProcessingScaler(0, 1);
        scaler.fit(iterator);
        iterator.setPreProcessor(scaler);

        return iterator;
    }

    /**
     * Defines the CNN architecture using DL4J's MultiLayerConfiguration.
     */
    private MultiLayerNetwork buildCNN() {
        MultiLayerConfiguration conf = new NeuralNetConfiguration.Builder()
                .seed(seed)
                .weightInit(WeightInit.RELU)
                .updater(new Adam(learningRate))
                .list()

                // --- Block 1: Conv + Pool ---
                .layer(new ConvolutionLayer.Builder(3, 3)
                        .nIn(channels)
                        .nOut(32)
                        .stride(1, 1)
                        .padding(1, 1)
                        .activation(Activation.RELU)
                        .build())
                .layer(new SubsamplingLayer.Builder(SubsamplingLayer.PoolingType.MAX)
                        .kernelSize(2, 2)
                        .stride(2, 2)
                        .build())

                // --- Block 2: Conv + Pool ---
                .layer(new ConvolutionLayer.Builder(3, 3)
                        .nOut(64)
                        .stride(1, 1)
                        .padding(1, 1)
                        .activation(Activation.RELU)
                        .build())
                .layer(new SubsamplingLayer.Builder(SubsamplingLayer.PoolingType.MAX)
                        .kernelSize(2, 2)
                        .stride(2, 2)
                        .build())

                // --- Block 3: Conv + Pool ---
                .layer(new ConvolutionLayer.Builder(3, 3)
                        .nOut(128)
                        .stride(1, 1)
                        .padding(1, 1)
                        .activation(Activation.RELU)
                        .build())
                .layer(new SubsamplingLayer.Builder(SubsamplingLayer.PoolingType.MAX)
                        .kernelSize(2, 2)
                        .stride(2, 2)
                        .build())

                // --- Flatten → Dense ---
                .layer(new DenseLayer.Builder()
                        .nOut(256)
                        .activation(Activation.RELU)
                        .build())
                .layer(new DropoutLayer.Builder(0.5).build())

                // --- Output (Softmax) ---
                .layer(new OutputLayer.Builder(LossFunctions.LossFunction.NEGATIVELOGLIKELIHOOD)
                        .nOut(NUM_CLASSES)
                        .activation(Activation.SOFTMAX)
                        .build())

                // Tell DL4J what the input shape is (channels x height x width)
                .setInputType(InputType.convolutional(imageHeight, imageWidth, channels))
                .build();

        return new MultiLayerNetwork(conf);
    }
}