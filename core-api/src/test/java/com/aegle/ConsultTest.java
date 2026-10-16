package com.aegle;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.aegle.support.IntegrationTestBase;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

class ConsultTest extends IntegrationTestBase {

    private UUID userId(RequestPostProcessor user) throws Exception {
        return UUID.fromString(body(mvc.perform(get("/api/me").with(user)).andReturn()).get("userId").asText());
    }

    private JsonNode ask(RequestPostProcessor user, Map<String, Object> req) throws Exception {
        return body(mvc.perform(post("/api/consults").with(user).contentType(MediaType.APPLICATION_JSON)
                        .content(json.writeValueAsString(req)))
                .andExpect(status().isCreated()).andReturn());
    }

    @Test
    void aClinicianAsksAColleagueWhoSeesItRepliesAndTheAskerResolvesIt() throws Exception {
        RequestPostProcessor junior = as("junior-" + org, org, "PHYSICIAN");
        RequestPostProcessor senior = as("senior-" + org, org, "RADIOLOGIST");
        RequestPostProcessor bystander = as("other-" + org, org, "RADIOLOGIST");
        userId(junior);
        UUID seniorId = userId(senior);
        userId(bystander);
        UUID study = upload(junior, "CONSULT-1", 80);

        JsonNode created = ask(junior, Map.of("subject", "Consolidation or atelectasis?", "body",
                "Right lower zone opacity, AI says pneumonia. Would you agree?", "studyId", study.toString(),
                "askedOf", seniorId.toString(), "urgency", "URGENT"));
        String id = created.at("/thread/id").asText();
        assertThat(created.at("/thread/specialty").asText()).isEqualTo("RADIOLOGY");   // from the study
        assertThat(created.at("/thread/studyLabel").asText()).isEqualTo("XR CHEST");
        assertThat(created.at("/messages/0/mine").asBoolean()).isTrue();

        JsonNode unread = body(mvc.perform(get("/api/consults/unread").with(senior)).andReturn());
        assertThat(unread.get("askedOfMe").asLong()).isEqualTo(1);
        assertThat(unread.get("askedOfMeUnread").asLong()).isEqualTo(1);
        JsonNode forMe = body(mvc.perform(get("/api/consults").param("box", "for-me").with(senior)).andReturn());
        assertThat(forMe).hasSize(1);
        assertThat(forMe.at("/0/unread").asInt()).isEqualTo(1);
        assertThat(body(mvc.perform(get("/api/consults").param("box", "mine").with(junior)).andReturn())).hasSize(1);
        assertThat(body(mvc.perform(get("/api/consults").param("box", "mine").with(senior)).andReturn())).isEmpty();

        String since = body(mvc.perform(get("/api/consults/" + id).with(senior)).andReturn())
                .at("/messages/0/at").asText();
        mvc.perform(post("/api/consults/" + id + "/messages").with(senior).contentType(MediaType.APPLICATION_JSON)
                        .content("{\"body\":\"Agree: air bronchograms. Treat and repeat in 6 weeks.\"}"))
                .andExpect(status().isCreated());
        assertThat(body(mvc.perform(get("/api/consults/unread").with(senior)).andReturn())
                .get("askedOfMeUnread").asLong()).isZero();

        JsonNode fresh = body(mvc.perform(get("/api/consults/" + id + "/messages").param("after", since).with(junior))
                .andReturn());
        assertThat(fresh).hasSize(1);
        assertThat(fresh.at("/0/mine").asBoolean()).isFalse();

        mvc.perform(post("/api/consults/" + id + "/resolve").with(bystander)).andExpect(status().isForbidden());
        mvc.perform(post("/api/consults/" + id + "/resolve").with(junior)).andExpect(status().isOk());
        mvc.perform(post("/api/consults/" + id + "/messages").with(senior).contentType(MediaType.APPLICATION_JSON)
                .content("{\"body\":\"late\"}")).andExpect(status().isConflict());
        assertThat(body(mvc.perform(get("/api/consults").param("box", "resolved").with(senior)).andReturn())).hasSize(1);

        assertThat(owner.queryForList("SELECT action FROM audit_log WHERE org_id = ? AND entity_type = 'consult' ORDER BY id",
                String.class, org)).containsExactly("CONSULT_OPENED", "CONSULT_VIEWED", "CONSULT_REPLIED", "CONSULT_RESOLVED");
    }

    @Test
    void consultsStayInsideTheOrganisationAndAwayFromNonClinicians() throws Exception {
        JsonNode created = ask(radiologist(), Map.of("subject", "Second opinion", "body", "Anyone free to look?"));
        String id = created.at("/thread/id").asText();

        UUID otherOrg = newOrg();
        mvc.perform(get("/api/consults/" + id).with(as("rad-" + otherOrg, otherOrg, "RADIOLOGIST")))
                .andExpect(status().isNotFound());
        assertThat(body(mvc.perform(get("/api/consults").with(as("rad-" + otherOrg, otherOrg, "RADIOLOGIST")))
                .andReturn())).isEmpty();
        mvc.perform(get("/api/consults").with(as("aud-" + org, org, "AUDITOR"))).andExpect(status().isForbidden());

        UUID auditor = userId(as("aud2-" + org, org, "AUDITOR"));
        mvc.perform(post("/api/consults").with(radiologist()).contentType(MediaType.APPLICATION_JSON)
                .content(json.writeValueAsString(Map.of("subject", "x", "body", "y", "askedOf", auditor.toString()))))
                .andExpect(status().isBadRequest());
    }
}
