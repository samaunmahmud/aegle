package com.aegle.study;

import com.aegle.audit.AuditService;
import com.aegle.phi.PhiCipher;
import com.aegle.security.Actor;
import com.aegle.storage.ObjectStore;
import com.aegle.tenant.TenantTx;
import com.aegle.web.BadRequestException;
import com.aegle.web.NotFoundException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;

@Service
public class StudyService {

    public record UploadRequest(String patientMrn, String patientName, LocalDate patientDob, String patientSex,
                                String modality, String bodyPart, String accessionNo, LocalDate studyDate) {}

    public record Patient(String mrn, String name, LocalDate dob, String sex) {}

    public record StudySummary(UUID id, String status, String modality, String bodyPart, String accessionNo,
                               LocalDate studyDate, OffsetDateTime createdAt, String patientMrn) {}

    public record PredictionView(UUID id, String label, double probability, String urgencyClass,
                                 String modelName, String modelVersion, String weightsSha256,
                                 OffsetDateTime analysedAt) {}

    public record ReviewView(UUID id, UUID predictionId, String decision, String finalLabel, String comment,
                             OffsetDateTime reviewedAt, String reviewer) {}

    public record JobView(UUID id, String status, int attempts, String error) {}

    public record StudyDetail(StudySummary study, Patient patient, List<PredictionView> predictions,
                              boolean hasHeatmap, List<ReviewView> reviews, List<JobView> jobs,
                              JsonNode priority) {}

    public record UploadResult(UUID studyId, String status, int jobsQueued) {}

    public record ImageBytes(byte[] data, String contentType) {}

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final PhiCipher phi;
    private final ObjectStore store;
    private final AuditService audit;
    private final ObjectMapper json;

    public StudyService(JdbcClient jdbc, TenantTx tenantTx, PhiCipher phi, ObjectStore store,
                        AuditService audit, ObjectMapper json) {
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.phi = phi;
        this.store = store;
        this.audit = audit;
        this.json = json;
    }

    public UploadResult upload(Actor actor, byte[] data, UploadRequest req) {
        String mime = ImageSniffer.detect(data)
                .orElseThrow(() -> new BadRequestException("Unsupported file: expected PNG, JPEG or DICOM"));
        UUID studyId = UUID.randomUUID();
        UUID instanceId = UUID.randomUUID();
        // Keys carry ids only: never filenames, which often contain patient names.
        String key = actor.orgId() + "/studies/" + studyId + "/instances/" + instanceId;
        store.put(key, data, mime);

        String modality = req.modality().toUpperCase();
        String bodyPart = req.bodyPart() == null ? null : req.bodyPart().toUpperCase();

        return tenantTx.executeAs(actor.orgId(), () -> {
            UUID patientId = jdbc.sql("""
                    INSERT INTO patients (org_id, mrn_encrypted, mrn_hash, name_encrypted, dob_encrypted, sex)
                    VALUES (:org, :mrn, :hash, :name, :dob, :sex)
                    ON CONFLICT (org_id, mrn_hash) DO UPDATE SET
                        name_encrypted = COALESCE(EXCLUDED.name_encrypted, patients.name_encrypted),
                        dob_encrypted = COALESCE(EXCLUDED.dob_encrypted, patients.dob_encrypted),
                        sex = COALESCE(EXCLUDED.sex, patients.sex)
                    RETURNING id""")
                    .param("org", actor.orgId())
                    .param("mrn", phi.encrypt(req.patientMrn().trim(), "patients.mrn"))
                    .param("hash", phi.mrnHash(actor.orgId(), req.patientMrn()))
                    .param("name", req.patientName() == null ? null : phi.encrypt(req.patientName(), "patients.name"))
                    .param("dob", req.patientDob() == null ? null : phi.encrypt(req.patientDob().toString(), "patients.dob"))
                    .param("sex", req.patientSex())
                    .query(UUID.class).single();

            List<UUID> models = jdbc.sql("""
                    SELECT mv.id FROM model_versions mv JOIN ai_models m ON m.id = mv.model_id
                    WHERE mv.active AND m.modality = :modality AND (m.body_part IS NULL OR m.body_part = :bodyPart)""")
                    .param("modality", modality).param("bodyPart", bodyPart)
                    .query(UUID.class).list();
            String status = models.isEmpty() ? "RECEIVED" : "QUEUED";

            jdbc.sql("""
                    INSERT INTO studies (id, org_id, patient_id, modality, body_part, accession_no, source,
                                         study_date, status, uploaded_by)
                    VALUES (:id, :org, :patient, :modality, :bodyPart, :accession, 'UPLOAD', :date, :status, :by)""")
                    .param("id", studyId).param("org", actor.orgId()).param("patient", patientId)
                    .param("modality", modality).param("bodyPart", bodyPart).param("accession", req.accessionNo())
                    .param("date", req.studyDate()).param("status", status).param("by", actor.userId()).update();

            jdbc.sql("""
                    INSERT INTO instances (id, org_id, study_id, storage_key, sha256, mime_type, size_bytes)
                    VALUES (:id, :org, :study, :key, :sha, :mime, :size)""")
                    .param("id", instanceId).param("org", actor.orgId()).param("study", studyId).param("key", key)
                    .param("sha", sha256(data)).param("mime", mime).param("size", (long) data.length).update();

            for (UUID mv : models) {
                jdbc.sql("INSERT INTO inference_jobs (org_id, study_id, model_version_id) VALUES (:org, :study, :mv)")
                        .param("org", actor.orgId()).param("study", studyId).param("mv", mv).update();
            }
            audit.record(actor.orgId(), actor.userId(), "STUDY_UPLOADED", "study", studyId.toString(),
                    Map.of("modality", modality, "mimeType", mime, "sizeBytes", data.length,
                            "jobsQueued", models.size()));
            return new UploadResult(studyId, status, models.size());
        });
    }

    public List<StudySummary> list(Actor actor, String status, int limit, int offset) {
        return tenantTx.executeAs(actor.orgId(), () -> {
            List<StudySummary> rows = jdbc.sql("""
                    SELECT s.id, s.status, s.modality, s.body_part, s.accession_no, s.study_date, s.created_at,
                           p.mrn_encrypted
                    FROM studies s JOIN patients p ON p.id = s.patient_id
                    WHERE (CAST(:status AS text) IS NULL OR s.status = :status)
                    ORDER BY s.created_at DESC LIMIT :limit OFFSET :offset""")
                    .param("status", status).param("limit", limit).param("offset", offset)
                    .query((rs, i) -> summary(rs)).list();
            audit.record(actor.orgId(), actor.userId(), "STUDIES_LISTED", "study", "*", Map.of("count", rows.size()));
            return rows;
        });
    }

    public StudyDetail detail(Actor actor, UUID studyId) {
        return tenantTx.executeAs(actor.orgId(), () -> {
            var row = jdbc.sql("""
                    SELECT s.id, s.status, s.modality, s.body_part, s.accession_no, s.study_date, s.created_at,
                           p.mrn_encrypted, p.name_encrypted, p.dob_encrypted, p.sex
                    FROM studies s JOIN patients p ON p.id = s.patient_id WHERE s.id = :id""")
                    .param("id", studyId)
                    .query((rs, i) -> Map.entry(summary(rs), new Patient(
                            phi.decrypt(rs.getBytes("mrn_encrypted"), "patients.mrn"),
                            phi.decrypt(rs.getBytes("name_encrypted"), "patients.name"),
                            Optional.ofNullable(phi.decrypt(rs.getBytes("dob_encrypted"), "patients.dob"))
                                    .map(LocalDate::parse).orElse(null),
                            rs.getString("sex"))))
                    .optional().orElseThrow(() -> new NotFoundException("study"));

            List<PredictionView> predictions = jdbc.sql("""
                    SELECT pr.id, pr.label, pr.probability, pr.urgency_class, m.name, mv.version, mv.weights_sha256,
                           j.finished_at
                    FROM predictions pr JOIN inference_jobs j ON j.id = pr.job_id
                    JOIN model_versions mv ON mv.id = j.model_version_id JOIN ai_models m ON m.id = mv.model_id
                    WHERE j.study_id = :id ORDER BY j.finished_at DESC, pr.probability DESC""")
                    .param("id", studyId)
                    .query((rs, i) -> new PredictionView(rs.getObject("id", UUID.class), rs.getString("label"),
                            Math.round(rs.getFloat("probability") * 10_000d) / 10_000d, rs.getString("urgency_class"), rs.getString("name"),
                            rs.getString("version"), rs.getString("weights_sha256"),
                            rs.getObject("finished_at", OffsetDateTime.class))).list();

            boolean hasHeatmap = jdbc.sql("""
                    SELECT count(*) FROM heatmaps h JOIN predictions pr ON pr.id = h.prediction_id
                    JOIN inference_jobs j ON j.id = pr.job_id WHERE j.study_id = :id""")
                    .param("id", studyId).query(Long.class).single() > 0;

            List<ReviewView> reviews = jdbc.sql("""
                    SELECT cr.id, cr.prediction_id, cr.decision, cr.final_label, cr.comment, cr.reviewed_at, u.full_name
                    FROM clinician_reviews cr JOIN users u ON u.id = cr.reviewer_id
                    JOIN predictions pr ON pr.id = cr.prediction_id JOIN inference_jobs j ON j.id = pr.job_id
                    WHERE j.study_id = :id ORDER BY cr.reviewed_at""")
                    .param("id", studyId)
                    .query((rs, i) -> new ReviewView(rs.getObject("id", UUID.class),
                            rs.getObject("prediction_id", UUID.class), rs.getString("decision"),
                            rs.getString("final_label"), rs.getString("comment"),
                            rs.getObject("reviewed_at", OffsetDateTime.class), rs.getString("full_name"))).list();

            List<JobView> jobs = jdbc.sql("""
                    SELECT id, status, attempts, error FROM inference_jobs WHERE study_id = :id ORDER BY queued_at""")
                    .param("id", studyId)
                    .query((rs, i) -> new JobView(rs.getObject("id", UUID.class), rs.getString("status"),
                            rs.getInt("attempts"), rs.getString("error"))).list();

            JsonNode priority = jdbc.sql("SELECT priority_reason FROM worklist_items WHERE study_id = :id")
                    .param("id", studyId).query(String.class).optional().map(this::parse).orElse(null);

            audit.record(actor.orgId(), actor.userId(), "STUDY_VIEWED", "study", studyId.toString(), Map.of());
            return new StudyDetail(row.getKey(), row.getValue(), predictions, hasHeatmap, reviews, jobs, priority);
        });
    }

    public ImageBytes heatmap(Actor actor, UUID studyId) {
        String key = tenantTx.executeAs(actor.orgId(), () -> {
            String k = jdbc.sql("""
                    SELECT h.storage_key FROM heatmaps h JOIN predictions pr ON pr.id = h.prediction_id
                    JOIN inference_jobs j ON j.id = pr.job_id WHERE j.study_id = :id
                    ORDER BY j.finished_at DESC LIMIT 1""")
                    .param("id", studyId).query(String.class).optional()
                    .orElseThrow(() -> new NotFoundException("heatmap"));
            audit.record(actor.orgId(), actor.userId(), "HEATMAP_VIEWED", "study", studyId.toString(), Map.of());
            return k;
        });
        return new ImageBytes(store.get(key), "image/png");
    }

    public ImageBytes image(Actor actor, UUID studyId) {
        record Ref(String key, String mime) {}
        Ref ref = tenantTx.executeAs(actor.orgId(), () -> {
            Ref r = jdbc.sql("SELECT storage_key, mime_type FROM instances WHERE study_id = :id ORDER BY created_at LIMIT 1")
                    .param("id", studyId)
                    .query((rs, i) -> new Ref(rs.getString("storage_key"), rs.getString("mime_type")))
                    .optional().orElseThrow(() -> new NotFoundException("image"));
            audit.record(actor.orgId(), actor.userId(), "IMAGE_VIEWED", "study", studyId.toString(), Map.of());
            return r;
        });
        return new ImageBytes(store.get(ref.key()), ref.mime());
    }

    private StudySummary summary(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new StudySummary(rs.getObject("id", UUID.class), rs.getString("status"), rs.getString("modality"),
                rs.getString("body_part"), rs.getString("accession_no"), rs.getObject("study_date", LocalDate.class),
                rs.getObject("created_at", OffsetDateTime.class),
                phi.decrypt(rs.getBytes("mrn_encrypted"), "patients.mrn"));
    }

    private JsonNode parse(String s) {
        try {
            return json.readTree(s);
        } catch (Exception e) {
            return null;
        }
    }

    private static String sha256(byte[] data) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(data));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
