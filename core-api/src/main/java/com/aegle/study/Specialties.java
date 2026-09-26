package com.aegle.study;

import java.util.List;

/** The clinical specialties studies and models are grouped by (see SQL aegle_specialty, migration V6). */
public final class Specialties {

    public static final List<String> ALL = List.of("RADIOLOGY", "CARDIOLOGY", "DERMATOLOGY", "OPHTHALMOLOGY",
            "PATHOLOGY", "GASTROENTEROLOGY", "NEUROLOGY");

    /** For request validation. */
    public static final String PATTERN =
            "RADIOLOGY|CARDIOLOGY|DERMATOLOGY|OPHTHALMOLOGY|PATHOLOGY|GASTROENTEROLOGY|NEUROLOGY";

    private Specialties() {}
}
