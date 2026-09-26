package com.aegle.support;

import com.aegle.inference.InferenceClient;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Deterministic stand-in for the Python service. The "image" carries the pneumonia
 * probability in percent in its 9th byte, so tests choose the model output per upload.
 */
public class StubInferenceClient implements InferenceClient {

    public volatile String weightsSha = "sha-test-1";
    public volatile RuntimeException failure;
    public final AtomicInteger calls = new AtomicInteger();
    public final AtomicInteger renders = new AtomicInteger();

    /** What {@link #render} returns: a PNG signature is all the tests look at. */
    public static final byte[] RENDERED_PNG = {(byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 42};

    public void reset() {
        weightsSha = "sha-test-1";
        failure = null;
        calls.set(0);
        renders.set(0);
    }

    public ModelInfo info() {
        return new ModelInfo("chest-xray-pneumonia", "test-1", "XR", "CHEST", "classification",
                "test model", weightsSha, Map.of("note", "stub"));
    }

    @Override
    public List<ModelInfo> models() {
        return List.of(info());
    }

    @Override
    public Result predict(String modelId, byte[] image) {
        calls.incrementAndGet();
        if (failure != null) {
            throw failure;
        }
        double pneumonia = (image[8] & 0xFF) / 100.0;
        List<Label> labels = pneumonia >= 0.5
                ? List.of(new Label("PNEUMONIA", pneumonia), new Label("NORMAL", 1 - pneumonia))
                : List.of(new Label("NORMAL", 1 - pneumonia), new Label("PNEUMONIA", pneumonia));
        return new Result(info(), labels, new Heatmap("grad-cam", labels.get(0).label(), new byte[]{1, 2, 3}));
    }

    @Override
    public byte[] render(byte[] image) {
        renders.incrementAndGet();
        return RENDERED_PNG.clone();
    }
}
