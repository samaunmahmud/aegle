package com.aegle.dicom;

import com.aegle.config.AegleProperties;
import com.aegle.dicom.OrthancClient.Change;
import com.aegle.dicom.OrthancClient.ChangePage;
import com.aegle.dicom.OrthancClient.InstanceInfo;
import com.aegle.dicom.OrthancClient.StudyInfo;
import com.aegle.study.StudyService;
import com.aegle.study.StudyService.NewInstance;
import com.aegle.study.StudyService.NewStudy;
import com.aegle.study.StudyService.UploadRequest;
import com.aegle.tenant.TenantTx;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Pulls studies that modalities sent to Orthanc into Aegle.
 *
 * Follows Orthanc's change log and acts on StableStudy events (no new instance for
 * Orthanc's StableAge). The sender's calling AE title decides the organisation, via
 * {@code dicom_sources}; studies from unregistered senders are left in Orthanc and logged.
 * Each change is handled in one transaction together with the cursor, which is locked so
 * several API instances never ingest the same study, and the unique Orthanc study id makes
 * a repeat impossible anyway. Instances that arrive after a study was ingested are not added.
 *
 * Logs carry Orthanc ids and AE titles only, never patient data.
 */
@Component
public class DicomIngestor {

    private static final Logger log = LoggerFactory.getLogger(DicomIngestor.class);
    private static final DateTimeFormatter DICOM_DATE = DateTimeFormatter.BASIC_ISO_DATE;
    /** DICOM projection radiography modalities, which Aegle calls XR. */
    private static final Set<String> RADIOGRAPHY = Set.of("CR", "DX", "DR", "RG", "PX");

    private final OrthancClient orthanc;
    private final StudyService studies;
    private final TenantTx tenantTx;
    private final TransactionTemplate tx;
    private final JdbcClient jdbc;
    private final AegleProperties.Dicom cfg;

    public DicomIngestor(OrthancClient orthanc, StudyService studies, TenantTx tenantTx, TransactionTemplate tx,
                         JdbcClient jdbc, AegleProperties props) {
        this.orthanc = orthanc;
        this.studies = studies;
        this.tenantTx = tenantTx;
        this.tx = tx;
        this.jdbc = jdbc;
        this.cfg = props.dicom();
    }

    @Scheduled(fixedDelayString = "${aegle.dicom.poll-interval-ms}", initialDelayString = "${aegle.dicom.poll-interval-ms}")
    void poll() {
        if (!cfg.enabled()) {
            return;
        }
        try {
            ingestPending();
        } catch (RuntimeException e) {
            log.warn("DICOM ingest paused: {}", e.getClass().getSimpleName());
        }
    }

    /** Works through Orthanc's change log until caught up. Returns the number of studies ingested. */
    public int ingestPending() {
        int ingested = 0;
        while (true) {
            long cursor = jdbc.sql("SELECT last_change FROM dicom_ingest_cursor WHERE id = 1").query(Long.class).single();
            ChangePage page = orthanc.changes(cursor, 100);
            long expected = cursor;
            for (Change change : page.changes()) {
                long previous = expected;
                Boolean result = tx.execute(status -> {
                    Optional<Long> locked = jdbc.sql(
                                    "SELECT last_change FROM dicom_ingest_cursor WHERE id = 1 FOR UPDATE SKIP LOCKED")
                            .query(Long.class).optional();
                    if (locked.isEmpty() || locked.get() != previous) {
                        return null;   // another instance is on it
                    }
                    boolean did = "StableStudy".equals(change.type()) && handle(change.orthancId());
                    jdbc.sql("UPDATE dicom_ingest_cursor SET last_change = :seq WHERE id = 1")
                            .param("seq", change.seq()).update();
                    return did;
                });
                if (result == null) {
                    return ingested;
                }
                if (result) {
                    ingested++;
                }
                expected = change.seq();
            }
            if (page.done() || page.changes().isEmpty()) {
                return ingested;
            }
        }
    }

    /** True if the study was ingested; false if it was skipped (and never will be ingested). */
    private boolean handle(String orthancStudyId) {
        Optional<StudyInfo> found = orthanc.study(orthancStudyId);
        if (found.isEmpty() || found.get().instances().isEmpty()) {
            log.info("Orthanc study {} is gone or empty, skipping", orthancStudyId);
            return false;
        }
        StudyInfo study = found.get();
        String aet = study.instances().get(0).remoteAet();
        Optional<UUID> org = aet == null ? Optional.empty()
                : jdbc.sql("SELECT org_id FROM dicom_sources WHERE ae_title = :aet").param("aet", aet)
                        .query(UUID.class).optional();
        if (org.isEmpty()) {
            log.warn("Orthanc study {} came from unregistered AE title '{}', left in Orthanc", orthancStudyId, aet);
            return false;
        }
        if (study.patientId() == null) {
            log.warn("Orthanc study {} has no PatientID, cannot be attributed to a patient; skipping", orthancStudyId);
            return false;
        }
        return tenantTx.executeAs(org.get(), () -> {
            boolean seen = jdbc.sql("SELECT count(*) FROM studies WHERE orthanc_study_id = :id")
                    .param("id", orthancStudyId).query(Long.class).single() > 0;
            if (seen) {
                log.info("Orthanc study {} already ingested; later instances are not added", orthancStudyId);
                return false;
            }
            List<NewInstance> instances = new ArrayList<>();
            for (InstanceInfo inst : study.instances()) {
                instances.add(new NewInstance(orthanc.instanceFile(inst.orthancId()), "application/dicom",
                        inst.sopInstanceUid(), inst.meta()));
            }
            InstanceInfo first = study.instances().get(0);
            UploadRequest meta = new UploadRequest(truncate(study.patientId(), 64), personName(study.patientName()),
                    date(study.patientBirthDate()), sex(study.patientSex()), modality(first.modality()),
                    first.bodyPart(), truncate(study.accessionNo(), 64), date(study.studyDate()));
            var result = studies.create(org.get(), null,
                    new NewStudy("DICOM", meta, study.studyInstanceUid(), orthancStudyId, instances));
            log.info("Ingested Orthanc study {} from '{}' as study {} ({} instances, {} jobs)",
                    orthancStudyId, aet, result.studyId(), instances.size(), result.jobsQueued());
            return true;
        });
    }

    static String modality(String dicomModality) {
        if (dicomModality == null) {
            return "OT";
        }
        String m = dicomModality.toUpperCase();
        return RADIOGRAPHY.contains(m) ? "XR" : m;
    }

    /** DICOM PN "Family^Given^Middle^Prefix^Suffix" to "Given Middle Family". */
    static String personName(String pn) {
        if (pn == null) {
            return null;
        }
        String[] p = pn.split("=")[0].split("\\^", -1);
        List<String> ordered = new ArrayList<>(Arrays.asList(p).subList(1, Math.min(p.length, 3)));
        ordered.add(p[0]);
        String name = ordered.stream().map(String::trim).filter(s -> !s.isEmpty()).collect(Collectors.joining(" "));
        return name.isEmpty() ? null : truncate(name, 200);
    }

    static LocalDate date(String dicomDate) {
        if (dicomDate == null || dicomDate.length() < 8) {
            return null;
        }
        try {
            return LocalDate.parse(dicomDate.substring(0, 8), DICOM_DATE);
        } catch (DateTimeParseException e) {
            return null;
        }
    }

    static String sex(String dicomSex) {
        return dicomSex != null && Set.of("F", "M", "O").contains(dicomSex.toUpperCase()) ? dicomSex.toUpperCase() : "U";
    }

    private static String truncate(String s, int max) {
        return s == null || s.length() <= max ? s : s.substring(0, max);
    }
}
