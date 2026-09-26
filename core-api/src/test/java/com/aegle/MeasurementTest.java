package com.aegle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.support.IntegrationTestBase;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

class MeasurementTest extends IntegrationTestBase {

    private UUID visit(String mrn, int area, String date) throws Exception {
        byte[] img = image(40);
        img[9] = (byte) area;                          // the stub reports area = this byte x 100 px
        String body = mvc.perform(multipart("/api/studies")
                        .file(new MockMultipartFile("file", "w.png", "image/png", img))
                        .param("patientMrn", mrn).param("studyDate", date).with(radiologist()))
                .andExpect(status().isCreated()).andReturn().getResponse().getContentAsString();
        worker.runOnce(org);
        return UUID.fromString(json.readTree(body).get("studyId").asText());
    }

    @Test
    void measurementsAreKeptPerStudyAndFollowedAcrossThePatientsVisits() throws Exception {
        inference.measure = true;
        visit("WOUND-1", 90, "2026-09-01");
        visit("WOUND-1", 60, "2026-09-15");
        UUID latest = visit("WOUND-1", 30, "2026-09-29");
        visit("OTHER-PATIENT", 10, "2026-09-20");

        JsonNode d = body(mvc.perform(get("/api/studies/" + latest).with(radiologist())).andReturn());
        assertThat(d.at("/measurements/0/name").asText()).isEqualTo("wound_area");
        assertThat(d.at("/measurements/0/value").asDouble()).isEqualTo(3000.0);
        JsonNode history = d.get("measurementHistory");
        assertThat(history).hasSize(3);                                        // not the other patient
        assertThat(history.get(0).get("value").asDouble()).isEqualTo(9000.0);   // oldest first
        assertThat(history.get(2).get("studyId").asText()).isEqualTo(latest.toString());
    }

    @Test
    void studiesWithoutMeasurementsHaveNoHistory() throws Exception {
        UUID study = visit("PLAIN-1", 10, "2026-09-01");
        JsonNode d = body(mvc.perform(get("/api/studies/" + study).with(radiologist())).andReturn());
        assertThat(d.get("measurements")).isEmpty();
        assertThat(d.get("measurementHistory")).isEmpty();
    }
}
