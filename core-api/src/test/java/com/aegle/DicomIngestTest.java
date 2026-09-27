package com.aegle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.dicom.DicomIngestor;
import com.aegle.dicom.OrthancClient.InstanceInfo;
import com.aegle.dicom.OrthancClient.StudyInfo;
import com.aegle.support.IntegrationTestBase;
import com.aegle.support.StubInferenceClient;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

class DicomIngestTest extends IntegrationTestBase {

    @Autowired DicomIngestor ingestor;

    private String aet;

    @BeforeEach
    void uniqueSender() {
        aet = "MOD" + UUID.randomUUID().toString().substring(0, 8).toUpperCase();
    }

    private RequestPostProcessor admin(UUID orgId) {
        return as("admin-" + orgId, orgId, "ADMIN");
    }

    private void register(UUID orgId, String aeTitle) throws Exception {
        mvc.perform(post("/api/admin/dicom-sources").with(admin(orgId)).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"aeTitle\":\"" + aeTitle + "\",\"description\":\"Test CR room\"}"))
                .andExpect(status().isCreated());
    }

    /** A two-image chest radiograph; the stub model reads pneumonia probability from the bytes. */
    private StudyInfo sendChestXray(String fromAet, int pneumoniaPercent) {
        String sid = "orthanc-" + UUID.randomUUID();
        List<InstanceInfo> instances = List.of(
                new InstanceInfo(sid + "-i1", "1.2.3." + System.nanoTime(), fromAet, "DX", "CHEST",
                        Map.of("ViewPosition", "PA", "Rows", "2048")),
                new InstanceInfo(sid + "-i2", "1.2.4." + System.nanoTime(), fromAet, "DX", "CHEST",
                        Map.of("ViewPosition", "LL")));
        StudyInfo study = new StudyInfo(sid, "1.2.840." + System.nanoTime(), "ACC-9", "20260920",
                "MRN-" + sid, "DOE^JANE^Q", "19800102", "F", instances);
        orthanc.send(study, Map.of(sid + "-i1", image(pneumoniaPercent), sid + "-i2", image(pneumoniaPercent)));
        return study;
    }

    @Test
    void studiesFromARegisteredSenderAreIngestedAnalysedAndAudited() throws Exception {
        register(org, aet);
        StudyInfo sent = sendChestXray(aet, 80);

        assertThat(ingestor.ingestPending()).isEqualTo(1);

        JsonNode list = body(mvc.perform(get("/api/studies").with(radiologist())).andExpect(status().isOk()).andReturn());
        assertThat(list).hasSize(1);
        JsonNode study = list.get(0);
        assertThat(study.get("source").asText()).isEqualTo("DICOM");
        assertThat(study.get("modality").asText()).isEqualTo("XR");       // DX is radiography
        assertThat(study.get("status").asText()).isEqualTo("QUEUED");
        assertThat(study.get("patientMrn").asText()).isEqualTo(sent.patientId());

        UUID studyId = UUID.fromString(study.get("id").asText());
        JsonNode detail = body(mvc.perform(get("/api/studies/" + studyId).with(radiologist())).andReturn());
        assertThat(detail.at("/patient/name").asText()).isEqualTo("JANE Q DOE");
        assertThat(detail.at("/patient/dob").asText()).isEqualTo("1980-01-02");
        assertThat(detail.at("/study/studyDate").asText()).isEqualTo("2026-09-20");

        var rows = owner.queryForList(
                "SELECT dicom_sop_uid, dicom_meta::text AS meta FROM instances WHERE study_id = ? ORDER BY dicom_sop_uid",
                studyId);
        assertThat(rows).hasSize(2);
        assertThat(rows.get(0).get("meta").toString()).contains("ViewPosition").doesNotContain("DOE");
        assertThat(owner.queryForObject("SELECT uploaded_by FROM studies WHERE id = ?", UUID.class, studyId)).isNull();
        assertThat(owner.queryForObject(
                "SELECT count(*) FROM audit_log WHERE org_id = ? AND action = 'STUDY_RECEIVED' AND actor_id IS NULL",
                Long.class, org)).isEqualTo(1);

        assertThat(worker.runOnce(org)).isEqualTo(1);
        mvc.perform(get("/api/studies/" + studyId).with(radiologist()))
                .andExpect(jsonPath("$.study.status").value("READY"))
                .andExpect(jsonPath("$.predictions[0].label").value("PNEUMONIA"))
                .andExpect(jsonPath("$.predictions[0].intendedUse").value("test model"));
    }

    @Test
    void aSeriesTakesItsMostUrgentImageAndTheViewerOpensOnIt() throws Exception {
        register(org, aet);
        String sid = "orthanc-" + UUID.randomUUID();
        List<InstanceInfo> instances = List.of(
                new InstanceInfo(sid + "-a", "1.9.1", aet, "DX", "CHEST", Map.of()),
                new InstanceInfo(sid + "-b", "1.9.2", aet, "DX", "CHEST", Map.of()),
                new InstanceInfo(sid + "-c", "1.9.3", aet, "DX", "CHEST", Map.of()));
        orthanc.send(new StudyInfo(sid, "1.2.840.9", "ACC-S", "20260920", "MRN-SERIES", "SERIES^PT", null, "F",
                instances), Map.of(sid + "-a", image(10), sid + "-b", image(92), sid + "-c", image(30)));
        ingestor.ingestPending();
        worker.runOnce(org);

        UUID studyId = owner.queryForObject("SELECT id FROM studies WHERE orthanc_study_id = ?", UUID.class, sid);
        mvc.perform(get("/api/studies/" + studyId).with(radiologist()))
                .andExpect(jsonPath("$.predictions[0].label").value("PNEUMONIA"))
                .andExpect(jsonPath("$.predictions[0].probability").value(0.92));
        assertThat(inference.calls.get()).isEqualTo(3);
        assertThat(owner.queryForObject("""
                SELECT i.dicom_sop_uid FROM heatmaps h JOIN instances i ON i.id = h.instance_id
                WHERE i.study_id = ?""", String.class, studyId)).isEqualTo("1.9.2");
    }

    @Test
    void eachOrthancStudyIsIngestedOnlyOnce() throws Exception {
        register(org, aet);
        StudyInfo sent = sendChestXray(aet, 20);
        assertThat(ingestor.ingestPending()).isEqualTo(1);

        orthanc.restabilise(sent.orthancId());           // late instance, or a re-send
        assertThat(ingestor.ingestPending()).isZero();
        assertThat(ingestor.ingestPending()).isZero();    // caught up: nothing left to do
        assertThat(owner.queryForObject("SELECT count(*) FROM studies WHERE org_id = ?", Long.class, org)).isEqualTo(1);
    }

    @Test
    void studiesFromUnknownSendersAreSkippedAndGoNowhere() throws Exception {
        UUID other = newOrg();
        register(other, aet);
        sendChestXray("UNKNOWN" + aet.substring(3), 50);
        sendChestXray(null, 50);                           // uploaded to Orthanc without DICOM

        assertThat(ingestor.ingestPending()).isZero();
        assertThat(owner.queryForObject("SELECT count(*) FROM studies WHERE org_id IN (?, ?)", Long.class, org, other))
                .isZero();
    }

    @Test
    void sendersOnlyFeedTheirOwnOrganisation() throws Exception {
        UUID other = newOrg();
        register(other, aet);
        sendChestXray(aet, 50);
        assertThat(ingestor.ingestPending()).isEqualTo(1);

        assertThat(body(mvc.perform(get("/api/studies").with(radiologist())).andReturn())).isEmpty();
        assertThat(body(mvc.perform(get("/api/studies").with(as("rad-" + other, other, "RADIOLOGIST"))).andReturn()))
                .hasSize(1);
    }

    @Test
    void dicomImagesAreServedAsARenderedPngThatIsKept() throws Exception {
        register(org, aet);
        sendChestXray(aet, 50);
        ingestor.ingestPending();
        String id = body(mvc.perform(get("/api/studies").with(radiologist())).andReturn()).get(0).get("id").asText();

        for (int i = 0; i < 2; i++) {
            mvc.perform(get("/api/studies/" + id + "/image").with(radiologist()))
                    .andExpect(status().isOk())
                    .andExpect(content().contentType(MediaType.IMAGE_PNG))
                    .andExpect(content().bytes(StubInferenceClient.RENDERED_PNG));
        }
        assertThat(inference.renders.get()).isEqualTo(1);
    }

    @Test
    void ecgCsvUploadsAreAcceptedAndShownAsARenderedTracing() throws Exception {
        StringBuilder csv = new StringBuilder("# fs=500 units=mV\nI,II,III,aVR,aVL,aVF,V1,V2,V3,V4,V5,V6\n");
        for (int i = 0; i < 1500; i++) {
            csv.append("0.1,0.2,0.1,-0.1,0.0,0.1,0.3,0.5,0.6,0.7,0.6,0.5\n");
        }
        String body = mvc.perform(multipart("/api/studies")
                        .file(new MockMultipartFile("file", "ecg.csv", "text/csv",
                                csv.toString().getBytes()))
                        .param("patientMrn", "ECG-1").param("modality", "ECG").param("bodyPart", "HEART")
                        .with(radiologist()))
                .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        String id = json.readTree(body).get("studyId").asText();
        assertThat(owner.queryForObject("SELECT mime_type FROM instances WHERE study_id = ?::uuid", String.class, id))
                .isEqualTo("text/csv");
        mvc.perform(get("/api/studies/" + id).with(radiologist()))
                .andExpect(jsonPath("$.study.specialty").value("CARDIOLOGY"));
        mvc.perform(get("/api/studies/" + id + "/image").with(radiologist()))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.IMAGE_PNG));
    }

    // ---- admin API

    @Test
    void onlyAdminsManageSendersAndOnlyTheirOwn() throws Exception {
        mvc.perform(get("/api/admin/dicom-sources").with(radiologist())).andExpect(status().isForbidden());
        mvc.perform(post("/api/admin/dicom-sources").with(as("aud-" + org, org, "AUDITOR"))
                        .contentType(MediaType.APPLICATION_JSON).content("{\"aeTitle\":\"" + aet + "\"}"))
                .andExpect(status().isForbidden());

        register(org, aet);
        mvc.perform(get("/api/admin/dicom-sources").with(admin(org)))
                .andExpect(jsonPath("$[0].aeTitle").value(aet))
                .andExpect(jsonPath("$[0].description").value("Test CR room"));

        UUID other = newOrg();
        mvc.perform(get("/api/admin/dicom-sources").with(admin(other))).andExpect(jsonPath("$").isEmpty());
        mvc.perform(post("/api/admin/dicom-sources").with(admin(other)).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"aeTitle\":\"" + aet + "\"}"))
                .andExpect(status().isConflict());
        mvc.perform(delete("/api/admin/dicom-sources/" + aet).with(admin(other))).andExpect(status().isNotFound());

        mvc.perform(delete("/api/admin/dicom-sources/" + aet).with(admin(org))).andExpect(status().isNoContent());
        mvc.perform(get("/api/admin/dicom-sources").with(admin(org))).andExpect(jsonPath("$").isEmpty());
    }

    @Test
    void invalidAeTitlesAreRejected() throws Exception {
        for (String bad : List.of("", " LEADING", "TOO-LONG-AE-TITLE-X", "TAB\\tIN")) {
            mvc.perform(post("/api/admin/dicom-sources").with(admin(org)).contentType(MediaType.APPLICATION_JSON)
                            .content("{\"aeTitle\":\"" + bad + "\"}"))
                    .andExpect(status().isBadRequest());
        }
        mvc.perform(post("/api/admin/dicom-sources").with(admin(org)).contentType(MediaType.APPLICATION_JSON)
                        .content("{}"))
                .andExpect(status().isBadRequest());
    }
}
