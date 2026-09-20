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
    }

    @Test
    void rejectsEverythingElse() {
        assertThat(ImageSniffer.detect("<html>".getBytes())).isEmpty();
        assertThat(ImageSniffer.detect(new byte[0])).isEmpty();
        assertThat(ImageSniffer.detect("MZ executable".getBytes())).isEmpty();
    }
}
