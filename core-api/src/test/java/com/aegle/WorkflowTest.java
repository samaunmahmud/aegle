package com.aegle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.inference.InferenceClient;
import com.aegle.support.IntegrationTestBase;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;

class WorkflowTest extends IntegrationTestBase {

    @Test
    void uploadIsAnalysedByTheWorkerAndAppearsOnTheWorklist() throws Exception {
        var user = radiologist();
        UUID study = upload(user, "MRN-1", 90);

        mvc.perform(get("/api/studies/{id}", study).with(user))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.study.status").value("QUEUED"))
                .andExpect(jsonPath("$.jobs[0].status").value("QUEUED"));

        assertThat(worker.runOnce(org)).isEqualTo(1);

        mvc.perform(get("/api/studies/{id}", study).with(user))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.study.status").value("READY"))
                .andExpect(jsonPath("$.patient.mrn").value("MRN-1"))
                .andExpect(jsonPath("$.patient.name").value("Test Patient MRN-1"))
                .andExpect(jsonPath("$.predictions[0].label").value("PNEUMONIA"))
                .andExpect(jsonPath("$.predictions[0].probability").value(0.9))
                .andExpect(jsonPath("$.predictions[0].modelVersion").value("test-1"))
                .andExpect(jsonPath("$.predictions[0].weightsSha256").value("sha-test-1"))
                .andExpect(jsonPath("$.hasHeatmap").value(true));

        // 0.9 x 60 (URGENT) + 0.1 x 10 (ROUTINE) = 55, and the reasoning is exposed in full.
        mvc.perform(get("/api/worklist").with(user))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.items[0].studyId").value(study.toString()))
                .andExpect(jsonPath("$.items[0].urgencyClass").value("URGENT"))
                .andExpect(jsonPath("$.items[0].topLabel").value("PNEUMONIA"))
                .andExpect(jsonPath("$.items[0].priorityScore").value(55.0))
                .andExpect(jsonPath("$.items[0].priorityReason.terms.length()").value(2))
                .andExpect(jsonPath("$.items[0].priorityReason.formula").exists());

        mvc.perform(get("/api/studies/{id}/heatmap", study).with(user))
                .andExpect(status().isOk())
                .andExpect(content().contentType(MediaType.IMAGE_PNG))
                .andExpect(content().bytes(new byte[]{1, 2, 3}));
    }

    @Test
    void worklistIsOrderedByRisk() throws Exception {
        var user = radiologist();
        UUID low = upload(user, "LOW", 5);
        UUID high = upload(user, "HIGH", 95);
        UUID mid = upload(user, "MID", 50);
        assertThat(worker.runOnce(org)).isEqualTo(3);

        String body = mvc.perform(get("/api/worklist").with(user)).andReturn().getResponse().getContentAsString();
        JsonNode items = json.readTree(body).get("items");
        assertThat(items).extracting(n -> n.get("studyId").asText())
                .containsExactly(high.toString(), mid.toString(), low.toString());
    }

    @Test
    void waitingTimeLetsAnOldLowRiskCaseOvertakeANewerModerateOne() throws Exception {
        var user = radiologist();
        UUID old = upload(user, "OLD", 10);      // priority 15
        UUID fresh = upload(user, "FRESH", 30);  // priority 25
        worker.runOnce(org);
        owner.update("UPDATE studies SET created_at = now() - interval '30 hours' WHERE id = ?", old);

        // 30h x 0.5/h = 15 bonus points: 15 + 15 = 30 > 25
        String body = mvc.perform(get("/api/worklist").with(user)).andReturn().getResponse().getContentAsString();
        JsonNode items = json.readTree(body).get("items");
        assertThat(items.get(0).get("studyId").asText()).isEqualTo(old.toString());
        assertThat(items.get(0).get("waitBonus").asDouble()).isBetween(14.9, 15.2);
        assertThat(items.get(1).get("studyId").asText()).isEqualTo(fresh.toString());
    }

    @Test
    void aStudyWithNoMatchingModelIsStoredButNotAnalysed() throws Exception {
        var user = radiologist();
        mvc.perform(multipart("/api/studies")
                        .file(new MockMultipartFile("file", "ct.png", "image/png", image(50)))
                        .param("patientMrn", "CT-1").param("modality", "CT").param("bodyPart", "HEAD").with(user))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("RECEIVED"))
                .andExpect(jsonPath("$.jobsQueued").value(0));
        assertThat(worker.runOnce(org)).isZero();
    }

    @Test
    void transientFailuresAreRetriedThenGiveUp() throws Exception {
        var user = radiologist();
        inference.failure = new IllegalStateException("inference service down");
        UUID study = upload(user, "RETRY", 80);

        assertThat(worker.runOnce(org)).isEqualTo(2);       // max-attempts = 2 in tests
        assertThat(inference.calls.get()).isEqualTo(2);

        mvc.perform(get("/api/studies/{id}", study).with(user))
                .andExpect(jsonPath("$.study.status").value("FAILED"))
                .andExpect(jsonPath("$.jobs[0].status").value("FAILED"))
                .andExpect(jsonPath("$.jobs[0].attempts").value(2));
        mvc.perform(get("/api/worklist").with(user)).andExpect(jsonPath("$.total").value(0));
    }

    @Test
    void inputTheServiceRejectsIsNotRetried() throws Exception {
        var user = radiologist();
        inference.failure = new InferenceClient.NonRetryableInferenceException("HTTP 422");
        UUID study = upload(user, "BADIMG", 80);

        assertThat(worker.runOnce(org)).isEqualTo(1);
        assertThat(inference.calls.get()).isEqualTo(1);
        mvc.perform(get("/api/studies/{id}", study).with(user))
                .andExpect(jsonPath("$.jobs[0].status").value("FAILED"))
                .andExpect(jsonPath("$.jobs[0].attempts").value(1));
    }

    @Test
    void resultsFromDifferentWeightsThanApprovedAreRejected() throws Exception {
        var user = radiologist();
        UUID study = upload(user, "SWAP", 80);
        inference.weightsSha = "sha-someone-swapped-the-model";

        worker.runOnce(org);
        mvc.perform(get("/api/studies/{id}", study).with(user))
                .andExpect(jsonPath("$.jobs[0].status").value("FAILED"))
                .andExpect(jsonPath("$.jobs[0].error").value(containsString("different weights")))
                .andExpect(jsonPath("$.predictions.length()").value(0));

        // The registry must not silently adopt the new weights under the same version label.
        registry.sync();
        assertThat(owner.queryForObject("""
                SELECT weights_sha256 FROM model_versions mv JOIN ai_models m ON m.id = mv.model_id
                WHERE m.name = 'chest-xray-pneumonia' AND mv.version = 'test-1'""", String.class))
                .isEqualTo("sha-test-1");
    }

    @Test
    void reviewingAPredictionCompletesTheCase() throws Exception {
        var user = radiologist();
        UUID study = upload(user, "REVIEW", 85);
        worker.runOnce(org);
        String prediction = json.readTree(mvc.perform(get("/api/studies/{id}", study).with(user))
                .andReturn().getResponse().getContentAsString()).at("/predictions/0/id").asText();

        mvc.perform(post("/api/predictions/{id}/review", prediction).with(user)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"decision\":\"MODIFY\"}"))
                .andExpect(status().isBadRequest());     // MODIFY needs a final label

        mvc.perform(post("/api/predictions/{id}/review", prediction).with(user)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"REJECT\",\"comment\":\"Looks like atelectasis\"}"))
                .andExpect(status().isOk());

        mvc.perform(get("/api/studies/{id}", study).with(user))
                .andExpect(jsonPath("$.study.status").value("REVIEWED"))
                .andExpect(jsonPath("$.reviews[0].decision").value("REJECT"))
                .andExpect(jsonPath("$.reviews[0].reviewer").value("rad-" + org));
        mvc.perform(get("/api/worklist").with(user)).andExpect(jsonPath("$.total").value(0));
        mvc.perform(get("/api/worklist?state=DONE").with(user)).andExpect(jsonPath("$.total").value(1));
    }

    @Test
    void aCaseCanOnlyBeClaimedByOneClinician() throws Exception {
        var alice = as("alice-" + org, org, "RADIOLOGIST");
        var bob = as("bob-" + org, org, "PHYSICIAN");
        UUID study = upload(alice, "CLAIM", 70);
        worker.runOnce(org);

        mvc.perform(post("/api/worklist/{id}/claim", study).with(alice)).andExpect(status().isOk());
        mvc.perform(post("/api/worklist/{id}/claim", study).with(alice)).andExpect(status().isOk());   // idempotent
        mvc.perform(post("/api/worklist/{id}/claim", study).with(bob)).andExpect(status().isConflict());
        mvc.perform(get("/api/worklist").with(bob))
                .andExpect(jsonPath("$.items[0].state").value("IN_REVIEW"))
                .andExpect(jsonPath("$.items[0].assignedTo").value("alice-" + org));
    }

    @Test
    void uploadsThatAreNotImagesAreRejected() throws Exception {
        mvc.perform(multipart("/api/studies")
                        .file(new MockMultipartFile("file", "notes.png", "image/png", "just text".getBytes()))
                        .param("patientMrn", "X").with(radiologist()))
                .andExpect(status().isBadRequest());
    }

    @Test
    void thereIsNoHeatmapBeforeAnalysis() throws Exception {
        var user = radiologist();
        UUID study = upload(user, "EARLY", 50);
        mvc.perform(get("/api/studies/{id}/heatmap", study).with(user)).andExpect(status().isNotFound());
    }
}
