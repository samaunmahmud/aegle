package com.aegle.dicom;

import java.util.List;
import java.util.Map;
import java.util.Optional;

/** Reads studies that modalities have sent to the Orthanc DICOM server. */
public interface OrthancClient {

    record Change(long seq, String type, String orthancId) {}

    /** {@code done}: nothing newer than {@code last} exists yet. */
    record ChangePage(List<Change> changes, long last, boolean done) {}

    /** Patient and study fields come straight from the DICOM header, so they hold PHI. */
    record StudyInfo(String orthancId, String studyInstanceUid, String accessionNo, String studyDate,
                     String patientId, String patientName, String patientBirthDate, String patientSex,
                     List<InstanceInfo> instances) {}

    /** {@code meta} is the de-identified header subset kept with the image. */
    record InstanceInfo(String orthancId, String sopInstanceUid, String remoteAet, String modality,
                        String bodyPart, Map<String, Object> meta) {}

    ChangePage changes(long since, int limit);

    /** Empty when Orthanc no longer has the study. */
    Optional<StudyInfo> study(String orthancStudyId);

    byte[] instanceFile(String orthancInstanceId);
}
