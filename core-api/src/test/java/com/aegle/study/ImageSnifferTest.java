package com.aegle.study;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ImageSnifferTest {

    @Test
    void recognisesSupportedFormatsByContent() {
        assertThat(ImageSniffer.detect(new byte[]{(byte) 0x89, 'P', 'N', 'G', 0x0D, 0x0A, 0x1A, 0x0A, 0}))
                .contains("image/png");
        assertThat(ImageSniffer.detect(new byte[]{(byte) 0xFF, (byte) 0xD8, (byte) 0xFF, (byte) 0xE0}))
                .contains("image/jpeg");
        byte[] dicom = new byte[200];
        dicom[128] = 'D'; dicom[129] = 'I'; dicom[130] = 'C'; dicom[131] = 'M';
        assertThat(ImageSniffer.detect(dicom)).contains("application/dicom");
        assertThat(ImageSniffer.detect(new byte[]{'I', 'I', 42, 0, 8, 0})).contains("image/tiff");
        assertThat(ImageSniffer.detect(new byte[]{'M', 'M', 0, 42, 0, 8})).contains("image/tiff");
    }

    @Test
    void recognisesEcgCsvExports() {
        assertThat(ImageSniffer.detect("# fs=500\nI,II,III,aVR,aVL,aVF,V1,V2,V3,V4,V5,V6\n0.1,0.2".getBytes()))
                .contains("text/csv");
        assertThat(ImageSniffer.detect("Lead I,Lead II,Lead V1\n1,2,3".getBytes())).contains("text/csv");
        assertThat(ImageSniffer.detect("name,dob,mrn\nx,y,z".getBytes())).isEmpty();   // not an ECG
    }

    @Test
    void recognisesEdf() {
        byte[] edf = new byte[300];
        java.util.Arrays.fill(edf, (byte) ' ');
        edf[0] = '0';
        assertThat(ImageSniffer.detect(edf)).contains("application/edf");
    }

    @Test
    void rejectsEverythingElse() {
        assertThat(ImageSniffer.detect("<html>".getBytes())).isEmpty();
        assertThat(ImageSniffer.detect(new byte[0])).isEmpty();
        assertThat(ImageSniffer.detect("MZ executable".getBytes())).isEmpty();
    }
}
