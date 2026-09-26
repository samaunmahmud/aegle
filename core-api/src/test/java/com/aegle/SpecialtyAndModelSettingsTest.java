package com.aegle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.support.IntegrationTestBase;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;

class SpecialtyAndModelSettingsTest extends IntegrationTestBase {

    private String specialty(String modality, String bodyPart) {
        return owner.queryForObject("SELECT aegle_specialty(?, ?)", String.class, modality, bodyPart);
    }

    @Test
    void modalityAndBodyPartDecideTheSpecialty() {
        assertThat(specialty("XR", "CHEST")).isEqualTo("RADIOLOGY");
        assertThat(specialty("ECG", null)).isEqualTo("CARDIOLOGY");
        assertThat(specialty("US", "HEART")).isEqualTo("CARDIOLOGY");
        assertThat(specialty("US", "ABDOMEN")).isEqualTo("RADIOLOGY");
        assertThat(specialty("XC", "SKIN")).isEqualTo("DERMATOLOGY");
        assertThat(specialty("OP", "EYE")).isEqualTo("OPHTHALMOLOGY");
        assertThat(specialty("SM", "BLOOD")).isEqualTo("PATHOLOGY");
        assertThat(specialty("ES", "COLON")).isEqualTo("GASTROENTEROLOGY");
        assertThat(specialty("MR", "BRAIN")).isEqualTo("NEUROLOGY");
        assertThat(specialty("ct", "head")).isEqualTo("NEUROLOGY");
        assertThat(specialty("EEG", null)).isEqualTo("NEUROLOGY");
    }

    private void uploadAs(String mrn, String modality, String bodyPart) throws Exception {
        mvc.perform(multipart("/api/studies")
                        .file(new MockMultipartFile("file", "x.png", "image/png", image(60)))
                        .param("patientMrn", mrn).param("modality", modality).param("bodyPart", bodyPart)
                        .with(radiologist()))
                .andExpect(status().isCreated());
    }

    @Test
    void studiesAndTheWorklistFilterBySpecialty() throws Exception {
        uploadAs("SP-1", "XR", "CHEST");
        uploadAs("SP-2", "MR", "BRAIN");
        worker.runOnce(org);

        mvc.perform(get("/api/studies?specialty=NEUROLOGY").with(radiologist()))
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].patientMrn").value("SP-2"))
                .andExpect(jsonPath("$[0].specialty").value("NEUROLOGY"));
        mvc.perform(get("/api/worklist?specialty=RADIOLOGY").with(radiologist()))
                .andExpect(jsonPath("$.total").value(1))
                .andExpect(jsonPath("$.items[0].specialty").value("RADIOLOGY"));
        mvc.perform(get("/api/worklist?specialty=CARDIOLOGY").with(radiologist()))
                .andExpect(jsonPath("$.total").value(0));
        mvc.perform(get("/api/studies?specialty=ASTROLOGY").with(radiologist())).andExpect(status().isBadRequest());
    }

    private UUID modelId() throws Exception {
        JsonNode models = body(mvc.perform(get("/api/models").with(radiologist())).andExpect(status().isOk()).andReturn());
        assertThat(models.get(0).get("specialty").asText()).isEqualTo("RADIOLOGY");
        assertThat(models.get(0).get("enabledForOrganisation").asBoolean()).isTrue();
        return UUID.fromString(models.get(0).get("id").asText());
    }

    @Test
    void anOrganisationCanSwitchAModelOffForItselfOnly() throws Exception {
        UUID model = modelId();
        var admin = as("admin-" + org, org, "ADMIN");
        mvc.perform(put("/api/models/" + model + "/enabled").with(radiologist())
                        .contentType(MediaType.APPLICATION_JSON).content("{\"enabled\":false}"))
                .andExpect(status().isForbidden());
        mvc.perform(put("/api/models/" + model + "/enabled").with(admin)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"enabled\":false}"))
                .andExpect(status().isOk());

        uploadAs("OFF-1", "XR", "CHEST");
        mvc.perform(get("/api/studies").with(radiologist())).andExpect(jsonPath("$[0].status").value("RECEIVED"));
        mvc.perform(get("/api/models").with(radiologist()))
                .andExpect(jsonPath("$[0].enabledForOrganisation").value(false));

        UUID other = newOrg();
        mvc.perform(multipart("/api/studies")
                        .file(new MockMultipartFile("file", "x.png", "image/png", image(60)))
                        .param("patientMrn", "ON-1").with(as("rad-" + other, other, "RADIOLOGIST")))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("QUEUED"));      // other hospitals unaffected

        mvc.perform(put("/api/models/" + model + "/enabled").with(admin)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"enabled\":true}"))
                .andExpect(status().isOk());
        uploadAs("ON-2", "XR", "CHEST");
        assertThat(owner.queryForObject(
                "SELECT count(*) FROM audit_log WHERE org_id = ? AND action IN ('MODEL_ENABLED', 'MODEL_DISABLED')",
                Long.class, org)).isEqualTo(2);
        mvc.perform(put("/api/models/" + UUID.randomUUID() + "/enabled").with(admin)
                        .contentType(MediaType.APPLICATION_JSON).content("{\"enabled\":true}"))
                .andExpect(status().isNotFound());
    }

    @Test
    void meIncludesTheOrganisationName() throws Exception {
        mvc.perform(get("/api/me").with(radiologist()))
                .andExpect(jsonPath("$.organisationName").value("Test org " + org));
    }
}
