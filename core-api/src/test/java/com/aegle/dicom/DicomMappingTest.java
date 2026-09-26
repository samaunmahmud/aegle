package com.aegle.dicom;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.LocalDate;
import org.junit.jupiter.api.Test;

class DicomMappingTest {

    @Test
    void personNamesReadGivenNamesFirst() {
        assertThat(DicomIngestor.personName("DOE^JANE")).isEqualTo("JANE DOE");
        assertThat(DicomIngestor.personName("DOE^JANE^Q^DR^JR")).isEqualTo("JANE Q DOE");
        assertThat(DicomIngestor.personName("DOE")).isEqualTo("DOE");
        assertThat(DicomIngestor.personName("DOE^JANE=ideographic")).isEqualTo("JANE DOE");
        assertThat(DicomIngestor.personName("^^")).isNull();
        assertThat(DicomIngestor.personName(null)).isNull();
    }

    @Test
    void datesAndSexAreParsedDefensively() {
        assertThat(DicomIngestor.date("19800102")).isEqualTo(LocalDate.of(1980, 1, 2));
        assertThat(DicomIngestor.date("1980")).isNull();
        assertThat(DicomIngestor.date("19801399")).isNull();
        assertThat(DicomIngestor.sex("f")).isEqualTo("F");
        assertThat(DicomIngestor.sex("X")).isEqualTo("U");
        assertThat(DicomIngestor.sex(null)).isEqualTo("U");
    }

    @Test
    void radiographyModalitiesMapToXr() {
        assertThat(DicomIngestor.modality("CR")).isEqualTo("XR");
        assertThat(DicomIngestor.modality("dx")).isEqualTo("XR");
        assertThat(DicomIngestor.modality("CT")).isEqualTo("CT");
        assertThat(DicomIngestor.modality(null)).isEqualTo("OT");
    }
}
