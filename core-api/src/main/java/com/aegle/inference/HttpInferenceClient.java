package com.aegle.inference;

import com.aegle.config.AegleProperties;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.ArrayList;
import java.util.Base64;
import java.util.List;
import java.util.Map;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

@Component
public class HttpInferenceClient implements InferenceClient {

    private final RestClient http;
    private final ObjectMapper json;

    public HttpInferenceClient(AegleProperties props, ObjectMapper json) {
        var cfg = props.inference();
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout((int) cfg.connectTimeout().toMillis());
        factory.setReadTimeout((int) cfg.readTimeout().toMillis());
        this.http = RestClient.builder().baseUrl(cfg.baseUrl()).requestFactory(factory)
                .defaultHeader(HttpHeaders.AUTHORIZATION, "Bearer " + cfg.token())
                .build();
        this.json = json;
    }

    @Override
    public List<ModelInfo> models() {
        JsonNode root = http.get().uri("/v1/models").retrieve().body(JsonNode.class);
        List<ModelInfo> out = new ArrayList<>();
        for (JsonNode m : root.path("models")) {
            out.add(modelInfo(m));
        }
        return out;
    }

    @Override
    public Result predict(String modelId, byte[] image) {
        MultiValueMap<String, Object> body = fileBody(image);
        JsonNode root;
        try {
            root = http.post().uri("/v1/models/{id}/predict", modelId)
                    .contentType(MediaType.MULTIPART_FORM_DATA).body(body)
                    .retrieve().body(JsonNode.class);
        } catch (HttpClientErrorException e) {
            if (e.getStatusCode().value() == 408 || e.getStatusCode().value() == 429) {
                throw e;   // transient: worth retrying
            }
            throw new NonRetryableInferenceException("Inference rejected the input (HTTP " + e.getStatusCode().value() + ")");
        }

        List<Label> labels = new ArrayList<>();
        for (JsonNode p : root.path("predictions")) {
            labels.add(new Label(p.path("label").asText(), p.path("probability").asDouble()));
        }
        Heatmap heatmap = null;
        JsonNode h = root.path("heatmap");
        if (h.isObject()) {
            heatmap = new Heatmap(h.path("method").asText(), h.path("target_label").asText(),
                    Base64.getDecoder().decode(h.path("image_base64").asText()));
        }
        List<Measurement> measurements = new ArrayList<>();
        for (JsonNode m : root.path("measurements")) {
            measurements.add(new Measurement(m.path("name").asText(), m.path("value").asDouble(), m.path("unit").asText()));
        }
        return new Result(modelInfo(root.path("model")), labels, heatmap, measurements);
    }

    @Override
    public byte[] render(byte[] image) {
        return http.post().uri("/v1/render")
                .contentType(MediaType.MULTIPART_FORM_DATA).body(fileBody(image))
                .retrieve().body(byte[].class);
    }

    private static MultiValueMap<String, Object> fileBody(byte[] image) {
        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        body.add("file", new ByteArrayResource(image) {
            @Override
            public String getFilename() {
                return "upload";   // fixed name: never forward client-supplied filenames (may hold PHI)
            }
        });
        return body;
    }

    private ModelInfo modelInfo(JsonNode m) {
        Map<String, Object> metrics = json.convertValue(m.path("metrics"), new TypeReference<>() {});
        return new ModelInfo(m.path("id").asText(), m.path("version").asText(), m.path("modality").asText(),
                m.path("body_part").isNull() ? null : m.path("body_part").asText(), m.path("task").asText(),
                m.path("intended_use").asText(), m.path("weights_sha256").asText(), metrics);
    }
}
