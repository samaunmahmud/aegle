package com.aegle.study;

import com.aegle.audit.AuditService;
import com.aegle.inference.InferenceClient;
import com.aegle.phi.PhiCipher;
import com.aegle.security.Actor;
import com.aegle.storage.ObjectStore;
import com.aegle.tenant.TenantTx;
import com.aegle.web.BadRequestException;
import com.aegle.web.NotFoundException;
import com.fasterxml.jackson.core.JsonProcessingException;
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
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClientException;
import org.springframework.web.server.ResponseStatusException;

@Service
public class StudyService {

    public record UploadRequest(String patientMrn, String patientName, LocalDate patientDob, String patientSex,
                                String modality, String bodyPart, String accessionNo, LocalDate studyDate) {}

    public record Patient(String mrn, String name, LocalDate dob, String sex) {}

    public record StudySummary(UUID id, String status, String source, String specialty, String modality,
                               String bodyPart, String accessionNo, LocalDate studyDate, OffsetDateTime createdAt,
                               String patientMrn) {}

    public record PredictionView(UUID id, String label, double probability, String urgencyClass,
                                 String modelName, String modelVersion, String weightsSha256,
                                 String intendedUse, OffsetDateTime analysedAt) {}

    public record ReviewView(UUID id, UUID predictionId, String decision, String finalLabel, String comment,
                             OffsetDateTime reviewedAt, String reviewer) {}

    public record JobView(UUID id, String status, int attempts, String error) {}

    public record MeasurementView(String name, double value, String unit) {}

    /** One visit's value of a measurement, for the same patient and study type. */
    public record MeasurementPoint(UUID studyId, LocalDate studyDate, OffsetDateTime receivedAt, String name,
                                   double value, String unit) {}

    public record StudyDetail(StudySummary study, Patient patient, List<PredictionView> predictions,
                              boolean hasHeatmap, List<ReviewView> reviews, List<JobView> jobs,
                              JsonNode priority, List<MeasurementView> measurements,
                              List<MeasurementPoint> measurementHistory) {}

    public record UploadResult(UUID studyId, String status, int jobsQueued) {}

    public record ImageBytes(byte[] data, String contentType) {}

    /** {@code dicomMeta}: a de-identified subset of the DICOM header, never patient data. */
    public record NewInstance(byte[] data, String mime, String sopInstanceUid, Map<String, Object> dicomMeta) {}

    /** {@code source} is UPLOAD or DICOM; the DICOM ids are null for uploads. */
    public record NewStudy(String source, UploadRequest meta, String dicomStudyUid, String orthancStudyId,
                           List<NewInstance> instances) {}

    static final java.util.Set<String> BROWSER_IMAGES = java.util.Set.of("image/png", "image/jpeg");

    private final JdbcClient jdbc;
    private final TenantTx tenantTx;
    private final PhiCipher phi;
    private final ObjectStore store;
    private final AuditService audit;
    private final ObjectMapper json;
    private final InferenceClient inference;

    public StudyService(JdbcClient jdbc, TenantTx tenantTx, PhiCipher phi, ObjectStore store,
                        AuditService audit, ObjectMapper json, InferenceClient inference) {
        this.inference = inference;
        this.jdbc = jdbc;
        this.tenantTx = tenantTx;
        this.phi = phi;
        this.store = store;
        this.audit = audit;
        this.json = json;
    }

    public UploadResult upload(Actor actor, byte[] data, UploadRequest req) {
        String mime = ImageSniffer.detect(data)
                .orElseThrow(() -> new BadRequestException("Unsupported file: expected PNG, JPEG, DICOM, EDF (EEG) or an ECG CSV"));
        NewStudy study = new NewStudy("UPLOAD", req, null, null, List.of(new NewInstance(data, mime, null, Map.of())));
        return tenantTx.executeAs(actor.orgId(), () -> create(actor.orgId(), actor.userId(), study));
    }

    /**
     * Stores a study's images, records it, and queues every active model that fits its
     * modality and body part. Must run inside {@code TenantTx} for {@code orgId}.
     * {@code userId} is null when no person uploaded it (DICOM from a modality).
     */
    public UploadResult create(UUID orgId, UUID userId, NewStudy study) {
        UploadRequest req = study.meta();
        UUID studyId = UUID.randomUUID();
        String modality = req.modality().toUpperCase();
        String bodyPart = req.bodyPart() == null ? null : req.bodyPart().toUpperCase();

        UUID patientId = jdbc.sql("""
                INSERT INTO patients (org_id, mrn_encrypted, mrn_hash, name_encrypted, dob_encrypted, sex)
                VALUES (:org, :mrn, :hash, :name, :dob, :sex)
                ON CONFLICT (org_id, mrn_hash) DO UPDATE SET
                    name_encrypted = COALESCE(EXCLUDED.name_encrypted, patients.name_encrypted),
                    dob_encrypted = COALESCE(EXCLUDED.dob_encrypted, patients.dob_encrypted),
                    sex = COALESCE(EXCLUDED.sex, patients.sex)
                RETURNING id""")
                .param("org", orgId)
                .param("mrn", phi.encrypt(req.patientMrn().trim(), "patients.mrn"))
                .param("hash", phi.mrnHash(orgId, req.patientMrn()))
                .param("name", req.patientName() == null ? null : phi.encrypt(req.patientName(), "patients.name"))
                .param("dob", req.patientDob() == null ? null : phi.encrypt(req.patientDob().toString(), "patients.dob"))
                .param("sex", req.patientSex())
                .query(UUID.class).single();

        List<UUID> models = jdbc.sql("""
                SELECT mv.id FROM model_versions mv JOIN ai_models m ON m.id = mv.model_id
                WHERE mv.active AND m.modality = :modality AND (m.body_part IS NULL OR m.body_part = :bodyPart)
                  AND NOT EXISTS (SELECT 1 FROM org_model_settings o
                                  WHERE o.model_id = m.id AND NOT o.enabled)""")
                .param("modality", modality).param("bodyPart", bodyPart)
                .query(UUID.class).list();
        String status = models.isEmpty() ? "RECEIVED" : "QUEUED";

        jdbc.sql("""
                INSERT INTO studies (id, org_id, patient_id, modality, body_part, accession_no, source,
                                     study_date, status, uploaded_by, dicom_study_uid, orthanc_study_id)
                VALUES (:id, :org, :patient, :modality, :bodyPart, :accession, :source, :date, :status, :by,
                        :studyUid, :orthancId)""")
                .param("id", studyId).param("org", orgId).param("patient", patientId)
                .param("modality", modality).param("bodyPart", bodyPart).param("accession", req.accessionNo())
                .param("source", study.source()).param("date", req.studyDate()).param("status", status)
                .param("by", userId).param("studyUid", study.dicomStudyUid())
                .param("orthancId", study.orthancStudyId()).update();

        for (NewInstance inst : study.instances()) {
            UUID instanceId = UUID.randomUUID();
            // Keys carry ids only: never filenames, which often contain patient names.
            String key = orgId + "/studies/" + studyId + "/instances/" + instanceId;
            store.put(key, inst.data(), inst.mime());
            jdbc.sql("""
                    INSERT INTO instances (id, org_id, study_id, storage_key, sha256, mime_type, size_bytes,
                                           dicom_sop_uid, dicom_meta)
                    VALUES (:id, :org, :study, :key, :sha, :mime, :size, :sop, CAST(:meta AS jsonb))""")
                    .param("id", instanceId).param("org", orgId).param("study", studyId).param("key", key)
                    .param("sha", sha256(inst.data())).param("mime", inst.mime())
                    .param("size", (long) inst.data().length).param("sop", inst.sopInstanceUid())
                    .param("meta", toJson(inst.dicomMeta())).update();
        }

        for (UUID mv : models) {
            jdbc.sql("INSERT INTO inference_jobs (org_id, study_id, model_version_id) VALUES (:org, :study, :mv)")
                    .param("org", orgId).param("study", studyId).param("mv", mv).update();
        }
        audit.record(orgId, userId, "UPLOAD".equals(study.source()) ? "STUDY_UPLOADED" : "STUDY_RECEIVED",
                "study", studyId.toString(),
                Map.of("source", study.source(), "modality", modality, "instances", study.instances().size(),
                        "sizeBytes", study.instances().stream().mapToLong(i -> i.data().length).sum(),
                        "jobsQueued", models.size()));
        return new UploadResult(studyId, status, models.size());
    }

    public List<StudySummary> list(Actor actor, String status, String specialty, int limit, int offset) {
        return tenantTx.executeAs(actor.orgId(), () -> {
            List<StudySummary> rows = jdbc.sql("""
                    SELECT s.id, s.status, s.source, aegle_specialty(s.modality, s.body_part) AS specialty,
                           s.modality, s.body_part, s.accession_no, s.study_date, s.created_at,
                           p.mrn_encrypted
                    FROM studies s JOIN patients p ON p.id = s.patient_id
                    WHERE (CAST(:status AS text) IS NULL OR s.status = :status)
                      AND (CAST(:specialty AS text) IS NULL OR aegle_specialty(s.modality, s.body_part) = :specialty)
                    ORDER BY s.created_at DESC LIMIT :limit OFFSET :offset""")
                    .param("status", status).param("specialty", specialty).param("limit", limit).param("offset", offset)
                    .query((rs, i) -> summary(rs)).list();
            audit.record(actor.orgId(), actor.userId(), "STUDIES_LISTED", "study", "*", Map.of("count", rows.size()));
            return rows;
        });
    }

    public StudyDetail detail(Actor actor, UUID studyId) {
        return tenantTx.executeAs(actor.orgId(), () -> {
            var row = jdbc.sql("""
                    SELECT s.id, s.status, s.source, aegle_specialty(s.modality, s.body_part) AS specialty,
                           s.modality, s.body_part, s.accession_no, s.study_date, s.created_at,
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
                           m.intended_use, j.finished_at
                    FROM predictions pr JOIN inference_jobs j ON j.id = pr.job_id
                    JOIN model_versions mv ON mv.id = j.model_version_id JOIN ai_models m ON m.id = mv.model_id
                    WHERE j.study_id = :id ORDER BY j.finished_at DESC, pr.probability DESC""")
                    .param("id", studyId)
                    .query((rs, i) -> new PredictionView(rs.getObject("id", UUID.class), rs.getString("label"),
                            Math.round(rs.getFloat("probability") * 10_000d) / 10_000d, rs.getString("urgency_class"), rs.getString("name"),
                            rs.getString("version"), rs.getString("weights_sha256"), rs.getString("intended_use"),
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

            List<MeasurementView> measurements = jdbc.sql("""
                    SELECT name, value, unit FROM measurements WHERE study_id = :id ORDER BY created_at, name""")
                    .param("id", studyId)
                    .query((rs, i) -> new MeasurementView(rs.getString("name"), rs.getDouble("value"),
                            rs.getString("unit"))).list();

            // The same measurements from this patient's other studies of the same type: healing over visits.
            List<MeasurementPoint> history = measurements.isEmpty() ? List.of() : jdbc.sql("""
                    SELECT s.id, s.study_date, s.created_at, m.name, m.value, m.unit
                    FROM measurements m JOIN studies s ON s.id = m.study_id
                    JOIN studies me ON me.id = :id
                    WHERE s.patient_id = me.patient_id AND s.modality = me.modality
                      AND s.body_part IS NOT DISTINCT FROM me.body_part
                    ORDER BY COALESCE(s.study_date, s.created_at::date), s.created_at""")
                    .param("id", studyId)
                    .query((rs, i) -> new MeasurementPoint(rs.getObject("id", UUID.class),
                            rs.getObject("study_date", LocalDate.class), rs.getObject("created_at", OffsetDateTime.class),
                            rs.getString("name"), rs.getDouble("value"), rs.getString("unit"))).list();

            audit.record(actor.orgId(), actor.userId(), "STUDY_VIEWED", "study", studyId.toString(), Map.of());
            return new StudyDetail(row.getKey(), row.getValue(), predictions, hasHeatmap, reviews, jobs, priority,
                    measurements, history);
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

    /**
     * The study's first image. Anything a browser cannot show (DICOM images and ECGs, ECG
     * CSVs) is returned as a PNG rendering made by the inference service on first view and
     * kept next to the original.
     */
    public ImageBytes image(Actor actor, UUID studyId) {
        record Ref(UUID id, String key, String mime, String previewKey) {}
        Ref ref = tenantTx.executeAs(actor.orgId(), () -> {
            Ref r = jdbc.sql("""
                    SELECT id, storage_key, mime_type, preview_key FROM instances
                    WHERE study_id = :id ORDER BY created_at LIMIT 1""")
                    .param("id", studyId)
                    .query((rs, i) -> new Ref(rs.getObject("id", UUID.class), rs.getString("storage_key"),
                            rs.getString("mime_type"), rs.getString("preview_key")))
                    .optional().orElseThrow(() -> new NotFoundException("image"));
            audit.record(actor.orgId(), actor.userId(), "IMAGE_VIEWED", "study", studyId.toString(), Map.of());
            return r;
        });
        if (BROWSER_IMAGES.contains(ref.mime())) {
            return new ImageBytes(store.get(ref.key()), ref.mime());
        }
        if (ref.previewKey() != null) {
            return new ImageBytes(store.get(ref.previewKey()), "image/png");
        }
        byte[] png;
        try {
            png = inference.render(store.get(ref.key()));
        } catch (RestClientException e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "Image preview unavailable");
        }
        String previewKey = ref.key() + "/preview.png";
        store.put(previewKey, png, "image/png");
        tenantTx.runAs(actor.orgId(), () -> jdbc.sql("UPDATE instances SET preview_key = :k WHERE id = :id")
                .param("k", previewKey).param("id", ref.id()).update());
        return new ImageBytes(png, "image/png");
    }

    private StudySummary summary(java.sql.ResultSet rs) throws java.sql.SQLException {
        return new StudySummary(rs.getObject("id", UUID.class), rs.getString("status"), rs.getString("source"),
                rs.getString("specialty"), rs.getString("modality"),
                rs.getString("body_part"), rs.getString("accession_no"), rs.getObject("study_date", LocalDate.class),
                rs.getObject("created_at", OffsetDateTime.class),
                phi.decrypt(rs.getBytes("mrn_encrypted"), "patients.mrn"));
    }

    private String toJson(Map<String, Object> value) {
        try {
            return json.writeValueAsString(value == null ? Map.of() : value);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Unserialisable DICOM metadata", e);
        }
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
