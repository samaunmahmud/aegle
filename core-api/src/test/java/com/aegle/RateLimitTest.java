package com.aegle;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.support.IntegrationTestBase;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.TestPropertySource;

@TestPropertySource(properties = {"aegle.rate-limit.requests-per-minute=5", "aegle.rate-limit.uploads-per-minute=2"})
class RateLimitTest extends IntegrationTestBase {

    @Test
    void uploadsHaveTheirOwnTighterLimit() throws Exception {
        var user = as("uploader-" + org, org, "RADIOLOGIST");
        upload(user, "RL-1", 10);
        upload(user, "RL-2", 10);
        mvc.perform(multipart("/api/studies")
                        .file(new MockMultipartFile("file", "scan.png", "image/png", image(10)))
                        .param("patientMrn", "RL-3").with(user))
                .andExpect(status().isTooManyRequests())
                .andExpect(header().exists("Retry-After"))
                .andExpect(jsonPath("$.status").value(429));
    }

    @Test
    void eachUserHasTheirOwnRequestBudget() throws Exception {
        var busy = as("busy-" + org, org, "RADIOLOGIST");
        for (int i = 0; i < 5; i++) {
            mvc.perform(get("/api/me").with(busy)).andExpect(status().isOk());
        }
        mvc.perform(get("/api/me").with(busy)).andExpect(status().isTooManyRequests());
        mvc.perform(get("/api/me").with(as("calm-" + org, org, "RADIOLOGIST"))).andExpect(status().isOk());
    }
}
