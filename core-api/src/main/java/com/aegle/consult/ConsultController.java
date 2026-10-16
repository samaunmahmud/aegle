package com.aegle.consult;

import com.aegle.audit.AuditService;
import com.aegle.security.Actor;
import com.aegle.security.ClinicianOnly;
import com.aegle.security.CurrentUserService;
import com.aegle.study.Specialties;
import com.aegle.tenant.TenantTx;
import com.aegle.web.BadRequestException;
import com.aegle.web.ConflictException;
import com.aegle.web.NotFoundException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

/**
 * Consults: a clinician asks a named colleague, or any clinician in the organisation, for a
 * second opinion, and the conversation is kept with the case.
 *
 * Opening a thread and every message posted are audited. Polling for new messages and the
 * unread count are not, so a panel left open does not flood the audit log; the full thread
 * read that precedes them is recorded.
 */
@RestController
@RequestMapping("/api/consults")
@ClinicianOnly
@Validated
public class ConsultController {

    public record Person(UUID id, String name, String jobTitle, String grade, String specialty, String avatar) {}

    public record LastMessage(String authorName, String preview, OffsetDateTime at) {}

    public record Thread(UUID id, String subject, String specialty, UUID studyId, String studyLabel, String urgency,
                         String status, OffsetDateTime createdAt, OffsetDateTime lastMessageAt, Person createdBy,
                         Person askedOf, int messageCount, int unread, LastMessage lastMessage) {}

    public record Message(UUID id, Person author, String body, OffsetDateTime at, boolean mine) {}

    public record Detail(Thread thread, List<Message> messages) {}

    public record NewConsult(@NotBlank @Size(max = 140) String subject, @NotBlank @Size(max = 4000) String body,
                             @Pattern(regexp = Specialties.PATTERN) String specialty, UUID studyId, UUID askedOf,
                             @Pattern(regexp = "ROUTINE|URGENT") String urgency) {}

    public record NewMessage(@NotBlank @Size(max = 4000) String body) {}

    private static final String PERSON_COLS = "%1$s.id AS %1$s_id, %1$s.full_name AS %1$s_name, "
            + "%1$s.job_title AS %1$s_title, %1$s.grade AS %1$s_grade, %1$s.specialty AS %1$s_spec, "
            + "%1$s.avatar AS %1$s_avatar";

    private static final String THREAD_SELECT = """
            SELECT t.*, s.modality, s.body_part, %s, %s,
                   (SELECT count(*) FROM consult_messages m WHERE m.thread_id = t.id) AS n,
                   (SELECT count(*) FROM consult_messages m
                     WHERE m.thread_id = t.id AND m.author_id <> :me
                       AND m.created_at > COALESCE((SELECT r.last_read_at FROM consult_reads r
                                                     WHERE r.thread_id = t.id AND r.user_id = :me),
                                                   '-infinity'::timestamptz)) AS unread,
                   lm.body AS lm_body, lm.created_at AS lm_at, la.full_name AS lm_author
            FROM consult_threads t
            JOIN users c ON c.id = t.created_by
            LEFT JOIN users a ON a.id = t.asked_of
            LEFT JOIN studies s ON s.id = t.study_id
            LEFT JOIN LATERAL (SELECT body, created_at, author_id FROM consult_messages m
                               WHERE m.thread_id = t.id ORDER BY created_at DESC LIMIT 1) lm ON true
            LEFT JOIN users la ON la.id = lm.author_id
            """.formatted(PERSON_COLS.formatted("c"), PERSON_COLS.formatted("a"));

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final CurrentUserService users;
    private final AuditService audit;

    public ConsultController(JdbcClient jdbc, TenantTx tenantTx, CurrentUserService users, AuditService audit) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.users = users;
        this.audit = audit;
    }

    /** Clinicians who can be asked, most senior first. */
    @GetMapping("/colleagues")
    public List<Person> colleagues() {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> jdbc.sql("""
                SELECT %s FROM users u
                WHERE u.active AND u.role IN ('RADIOLOGIST', 'PHYSICIAN') AND u.id <> :me
                ORDER BY CASE u.grade WHEN 'CONSULTANT' THEN 0 WHEN 'REGISTRAR' THEN 1 WHEN 'FOUNDATION' THEN 2 ELSE 3 END,
                         u.full_name""".formatted(PERSON_COLS.formatted("u")))
                .param("me", actor.userId())
                .query((rs, n) -> person(rs, "u")).list());
    }

    /**
     * {@code box}: "for-me" (asked of me), "mine" (I asked), "open" (every open consult) or
     * "resolved".
     */
    @GetMapping
    public List<Thread> list(@RequestParam(defaultValue = "open") @Pattern(regexp = "for-me|mine|open|resolved") String box) {
        Actor actor = users.require();
        String where = switch (box) {
            case "for-me" -> "t.asked_of = :me AND t.status = 'OPEN'";
            case "mine" -> "t.created_by = :me";
            case "resolved" -> "t.status = 'RESOLVED'";
            default -> "t.status = 'OPEN'";
        };
        return tenantTx.executeAs(actor.orgId(), () -> jdbc.sql(THREAD_SELECT + " WHERE " + where
                        + " ORDER BY (t.status = 'OPEN' AND t.urgency = 'URGENT') DESC, t.last_message_at DESC LIMIT 100")
                .param("me", actor.userId())
                .query((rs, n) -> thread(rs)).list());
    }

    /** Badge counts for the consult panel. Not audited: counts, no case content. */
    @GetMapping("/unread")
    public Map<String, Object> unread() {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> jdbc.sql("""
                SELECT count(*) FILTER (WHERE x.unread > 0) AS threads,
                       count(*) FILTER (WHERE t.asked_of = :me AND t.status = 'OPEN') AS for_me,
                       count(*) FILTER (WHERE t.asked_of = :me AND t.status = 'OPEN' AND x.unread > 0) AS for_me_unread
                FROM consult_threads t
                CROSS JOIN LATERAL (
                    SELECT count(*) AS unread FROM consult_messages m
                    WHERE m.thread_id = t.id AND m.author_id <> :me
                      AND m.created_at > COALESCE((SELECT r.last_read_at FROM consult_reads r
                                                    WHERE r.thread_id = t.id AND r.user_id = :me),
                                                  '-infinity'::timestamptz)) x
                WHERE t.status = 'OPEN' AND (t.asked_of = :me OR t.created_by = :me OR t.asked_of IS NULL
                      OR EXISTS (SELECT 1 FROM consult_messages p WHERE p.thread_id = t.id AND p.author_id = :me))""")
                .param("me", actor.userId())
                .query((rs, n) -> Map.<String, Object>of("unreadThreads", rs.getLong("threads"),
                        "askedOfMe", rs.getLong("for_me"), "askedOfMeUnread", rs.getLong("for_me_unread")))
                .single());
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Detail create(@Valid @RequestBody NewConsult req) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            if (req.askedOf() != null) {
                if (req.askedOf().equals(actor.userId())) {
                    throw new BadRequestException("You cannot ask yourself");
                }
                boolean clinician = jdbc.sql("""
                        SELECT count(*) FROM users WHERE id = :id AND active AND role IN ('RADIOLOGIST', 'PHYSICIAN')""")
                        .param("id", req.askedOf()).query(Long.class).single() > 0;
                if (!clinician) {
                    throw new BadRequestException("askedOf is not a clinician in this organisation");
                }
            }
            String specialty = req.specialty();
            if (req.studyId() != null) {
                // RLS: a study from another organisation is simply not found.
                String studySpecialty = jdbc.sql("SELECT aegle_specialty(modality, body_part) FROM studies WHERE id = :id")
                        .param("id", req.studyId()).query(String.class).optional()
                        .orElseThrow(() -> new NotFoundException("study"));
                if (specialty == null) {
                    specialty = studySpecialty;
                }
            }
            UUID id = jdbc.sql("""
                    INSERT INTO consult_threads (org_id, subject, specialty, study_id, created_by, asked_of, urgency)
                    VALUES (:org, :subject, :spec, :study, :me, :asked, :urgency) RETURNING id""")
                    .param("org", actor.orgId()).param("subject", req.subject().strip()).param("spec", specialty)
                    .param("study", req.studyId()).param("me", actor.userId()).param("asked", req.askedOf())
                    .param("urgency", req.urgency() == null ? "ROUTINE" : req.urgency())
                    .query(UUID.class).single();
            post(actor, id, req.body());
            Map<String, Object> details = new HashMap<>();
            details.put("urgency", req.urgency() == null ? "ROUTINE" : req.urgency());
            if (req.studyId() != null) {
                details.put("studyId", req.studyId().toString());
            }
            if (req.askedOf() != null) {
                details.put("askedOf", req.askedOf().toString());
            }
            audit.record(actor.orgId(), actor.userId(), "CONSULT_OPENED", "consult", id.toString(), details);
            return detail(actor, id);
        });
    }

    /** The whole thread; marks it read. Audited as a view of the consult. */
    @GetMapping("/{id}")
    public Detail get(@PathVariable UUID id) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            Detail d = detail(actor, id);
            audit.record(actor.orgId(), actor.userId(), "CONSULT_VIEWED", "consult", id.toString(), Map.of());
            return d;
        });
    }

    /** Messages after {@code after}, for polling an open thread. Marks them read. */
    @GetMapping("/{id}/messages")
    public List<Message> since(@PathVariable UUID id,
                               @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime after) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            requireThread(id);
            List<Message> messages = messages(actor, id, after);
            markRead(actor, id);
            return messages;
        });
    }

    @PostMapping("/{id}/messages")
    @ResponseStatus(HttpStatus.CREATED)
    public Message reply(@PathVariable UUID id, @Valid @RequestBody NewMessage req) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            if (!"OPEN".equals(requireThread(id))) {
                throw new ConflictException("This consult is resolved");
            }
            UUID messageId = post(actor, id, req.body());
            audit.record(actor.orgId(), actor.userId(), "CONSULT_REPLIED", "consult", id.toString(),
                    Map.of("messageId", messageId.toString()));
            return messages(actor, id, null).stream().filter(m -> m.id().equals(messageId)).findFirst().orElseThrow();
        });
    }

    /** Closed by the clinician who asked, or the one who was asked. */
    @PostMapping("/{id}/resolve")
    public Detail resolve(@PathVariable UUID id) {
        Actor actor = users.require();
        return tenantTx.executeAs(actor.orgId(), () -> {
            requireThread(id);
            int n = jdbc.sql("""
                    UPDATE consult_threads SET status = 'RESOLVED', resolved_at = now(), resolved_by = :me
                    WHERE id = :id AND status = 'OPEN' AND (created_by = :me OR asked_of = :me)""")
                    .param("id", id).param("me", actor.userId()).update();
            if (n == 0) {
                throw new ResponseStatusException(HttpStatus.FORBIDDEN,
                        "Only the clinician who asked, or was asked, can resolve an open consult");
            }
            audit.record(actor.orgId(), actor.userId(), "CONSULT_RESOLVED", "consult", id.toString(), Map.of());
            return detail(actor, id);
        });
    }

    // ------------------------------------------------------------------ helpers

    private String requireThread(UUID id) {
        return jdbc.sql("SELECT status FROM consult_threads WHERE id = :id").param("id", id)
                .query(String.class).optional().orElseThrow(() -> new NotFoundException("consult"));
    }

    private UUID post(Actor actor, UUID threadId, String body) {
        UUID id = jdbc.sql("""
                INSERT INTO consult_messages (org_id, thread_id, author_id, body)
                VALUES (:org, :thread, :me, :body) RETURNING id""")
                .param("org", actor.orgId()).param("thread", threadId).param("me", actor.userId())
                .param("body", body.strip()).query(UUID.class).single();
        jdbc.sql("UPDATE consult_threads SET last_message_at = now() WHERE id = :id").param("id", threadId).update();
        markRead(actor, threadId);
        return id;
    }

    private void markRead(Actor actor, UUID threadId) {
        jdbc.sql("""
                INSERT INTO consult_reads (org_id, thread_id, user_id, last_read_at)
                SELECT :org, :thread, :me, COALESCE(max(created_at), now()) FROM consult_messages WHERE thread_id = :thread
                ON CONFLICT (thread_id, user_id) DO UPDATE
                   SET last_read_at = GREATEST(consult_reads.last_read_at, EXCLUDED.last_read_at)""")
                .param("org", actor.orgId()).param("thread", threadId).param("me", actor.userId()).update();
    }

    private Detail detail(Actor actor, UUID id) {
        Thread t = jdbc.sql(THREAD_SELECT + " WHERE t.id = :id").param("id", id).param("me", actor.userId())
                .query((rs, n) -> thread(rs)).optional().orElseThrow(() -> new NotFoundException("consult"));
        List<Message> messages = messages(actor, id, null);
        markRead(actor, id);
        return new Detail(t, messages);
    }

    private List<Message> messages(Actor actor, UUID threadId, OffsetDateTime after) {
        return jdbc.sql("""
                SELECT m.id, m.body, m.created_at, %s FROM consult_messages m JOIN users u ON u.id = m.author_id
                WHERE m.thread_id = :thread AND (CAST(:after AS timestamptz) IS NULL OR m.created_at > CAST(:after AS timestamptz))
                ORDER BY m.created_at""".formatted(PERSON_COLS.formatted("u")))
                .param("thread", threadId).param("after", after)
                .query((rs, n) -> {
                    Person author = person(rs, "u");
                    return new Message(rs.getObject("id", UUID.class), author, rs.getString("body"),
                            rs.getObject("created_at", OffsetDateTime.class), author.id().equals(actor.userId()));
                }).list();
    }

    private static Thread thread(ResultSet rs) throws SQLException {
        String modality = rs.getString("modality");
        String bodyPart = rs.getString("body_part");
        String studyLabel = modality == null ? null : bodyPart == null ? modality : modality + " " + bodyPart;
        String lmBody = rs.getString("lm_body");
        LastMessage last = lmBody == null ? null : new LastMessage(rs.getString("lm_author"),
                lmBody.length() > 140 ? lmBody.substring(0, 139) + "…" : lmBody,
                rs.getObject("lm_at", OffsetDateTime.class));
        return new Thread(rs.getObject("id", UUID.class), rs.getString("subject"), rs.getString("specialty"),
                rs.getObject("study_id", UUID.class), studyLabel, rs.getString("urgency"), rs.getString("status"),
                rs.getObject("created_at", OffsetDateTime.class), rs.getObject("last_message_at", OffsetDateTime.class),
                person(rs, "c"), rs.getObject("a_id", UUID.class) == null ? null : person(rs, "a"),
                rs.getInt("n"), rs.getInt("unread"), last);
    }

    private static Person person(ResultSet rs, String p) throws SQLException {
        return new Person(rs.getObject(p + "_id", UUID.class), rs.getString(p + "_name"), rs.getString(p + "_title"),
                rs.getString(p + "_grade"), rs.getString(p + "_spec"), rs.getString(p + "_avatar"));
    }
}
