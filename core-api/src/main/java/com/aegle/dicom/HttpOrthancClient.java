package com.aegle.dicom;

import com.aegle.config.AegleProperties;
import com.fasterxml.jackson.databind.JsonNode;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.springframework.http.HttpHeaders;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;

@Component
public class HttpOrthancClient implements OrthancClient {

    /** Header fields kept with each image: technical only, nothing that identifies a patient. */
    static final Set<String> META_FIELDS = Set.of("Modality", "BodyPartExamined", "ViewPosition", "Laterality",
            "Rows", "Columns", "PhotometricInterpretation", "BitsStored", "PixelSpacing", "ImagerPixelSpacing",
            "Manufacturer", "ManufacturerModelName", "SOPClassUID", "TransferSyntaxUID");

    private final RestClient http;

    public HttpOrthancClient(AegleProperties props) {
        var cfg = props.dicom();
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout((int) Duration.ofSeconds(5).toMillis());
        factory.setReadTimeout((int) Duration.ofSeconds(60).toMillis());
        RestClient.Builder b = RestClient.builder().baseUrl(cfg.orthancUrl()).requestFactory(factory);
        if (cfg.username() != null && !cfg.username().isBlank()) {
            String basic = Base64.getEncoder().encodeToString(
                    (cfg.username() + ":" + cfg.password()).getBytes(StandardCharsets.UTF_8));
            b.defaultHeader(HttpHeaders.AUTHORIZATION, "Basic " + basic);
        }
        this.http = b.build();
    }

    @Override
    public ChangePage changes(long since, int limit) {
        JsonNode root = http.get().uri("/changes?since={s}&limit={l}", since, limit).retrieve().body(JsonNode.class);
        List<Change> out = new ArrayList<>();
        for (JsonNode c : root.path("Changes")) {
            out.add(new Change(c.path("Seq").asLong(), c.path("ChangeType").asText(), c.path("ID").asText()));
        }
        return new ChangePage(out, root.path("Last").asLong(), root.path("Done").asBoolean());
    }

    @Override
    public Optional<StudyInfo> study(String orthancStudyId) {
        JsonNode study;
        try {
            study = http.get().uri("/studies/{id}", orthancStudyId).retrieve().body(JsonNode.class);
        } catch (HttpClientErrorException.NotFound e) {
            return Optional.empty();
        }
        JsonNode tags = study.path("MainDicomTags");
        JsonNode patient = study.path("PatientMainDicomTags");

        List<InstanceInfo> instances = new ArrayList<>();
        for (JsonNode seriesId : study.path("Series")) {
            JsonNode series = http.get().uri("/series/{id}", seriesId.asText()).retrieve().body(JsonNode.class);
            String modality = text(series.path("MainDicomTags"), "Modality");
            String bodyPart = text(series.path("MainDicomTags"), "BodyPartExamined");
            for (JsonNode instanceId : series.path("Instances")) {
                String id = instanceId.asText();
                JsonNode all = http.get().uri("/instances/{id}/simplified-tags", id).retrieve().body(JsonNode.class);
                Map<String, Object> meta = new LinkedHashMap<>();
                all.fields().forEachRemaining(f -> {
                    if (META_FIELDS.contains(f.getKey()) && f.getValue().isValueNode()) {
                        meta.put(f.getKey(), f.getValue().asText());
                    }
                });
                instances.add(new InstanceInfo(id, text(all, "SOPInstanceUID"), remoteAet(id), modality,
                        bodyPart, meta));
            }
        }
        return Optional.of(new StudyInfo(orthancStudyId, text(tags, "StudyInstanceUID"),
                text(tags, "AccessionNumber"), text(tags, "StudyDate"), text(patient, "PatientID"),
                text(patient, "PatientName"), text(patient, "PatientBirthDate"), text(patient, "PatientSex"),
                instances));
    }

    @Override
    public byte[] instanceFile(String orthancInstanceId) {
        return http.get().uri("/instances/{id}/file", orthancInstanceId).retrieve().body(byte[].class);
    }

    /** The calling AE title the modality used when it sent this instance. */
    private String remoteAet(String instanceId) {
        try {
            String aet = http.get().uri("/instances/{id}/metadata/RemoteAET", instanceId).retrieve().body(String.class);
            return aet == null ? null : aet.trim();
        } catch (HttpClientErrorException.NotFound e) {
            return null;   // not received over DICOM (e.g. uploaded through Orthanc's REST API)
        }
    }

    private static String text(JsonNode node, String field) {
        JsonNode v = node.path(field);
        return v.isMissingNode() || v.isNull() || v.asText().isBlank() ? null : v.asText().trim();
    }
}
