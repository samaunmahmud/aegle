package com.aegle.support;

import com.aegle.dicom.OrthancClient;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicLong;

/** An in-memory Orthanc: tests "send" studies, which appear in the change log as stable. */
public class StubOrthancClient implements OrthancClient {

    private final List<Change> log = new ArrayList<>();
    private final Map<String, StudyInfo> studies = new HashMap<>();
    private final Map<String, byte[]> files = new HashMap<>();
    private final AtomicLong seq = new AtomicLong(1_000_000);

    public synchronized void reset() {
        log.clear();
        studies.clear();
        files.clear();
    }

    /** Stores the study and logs it as stable. Instance files are keyed by instance id. */
    public synchronized void send(StudyInfo study, Map<String, byte[]> instanceFiles) {
        studies.put(study.orthancId(), study);
        files.putAll(instanceFiles);
        log.add(new Change(seq.incrementAndGet(), "NewStudy", study.orthancId()));
        log.add(new Change(seq.incrementAndGet(), "StableStudy", study.orthancId()));
    }

    /** Logs the study as stable again, as Orthanc does when late instances arrive. */
    public synchronized void restabilise(String orthancId) {
        log.add(new Change(seq.incrementAndGet(), "StableStudy", orthancId));
    }

    @Override
    public synchronized ChangePage changes(long since, int limit) {
        List<Change> page = log.stream().filter(c -> c.seq() > since).limit(limit).toList();
        long last = page.isEmpty() ? Math.max(since, seq.get()) : page.get(page.size() - 1).seq();
        boolean done = log.stream().noneMatch(c -> c.seq() > last);
        return new ChangePage(page, last, done);
    }

    @Override
    public synchronized Optional<StudyInfo> study(String orthancStudyId) {
        return Optional.ofNullable(studies.get(orthancStudyId));
    }

    @Override
    public synchronized byte[] instanceFile(String orthancInstanceId) {
        return files.get(orthancInstanceId);
    }
}
