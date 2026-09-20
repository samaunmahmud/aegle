package com.aegle.study;

import java.util.Optional;

/** Identifies supported uploads by content, not by the client-supplied name or type. */
final class ImageSniffer {

    private ImageSniffer() {}

    static Optional<String> detect(byte[] b) {
        if (b.length >= 8 && (b[0] & 0xFF) == 0x89 && b[1] == 'P' && b[2] == 'N' && b[3] == 'G'
                && b[4] == 0x0D && b[5] == 0x0A && b[6] == 0x1A && b[7] == 0x0A) {
            return Optional.of("image/png");
        }
        if (b.length >= 3 && (b[0] & 0xFF) == 0xFF && (b[1] & 0xFF) == 0xD8 && (b[2] & 0xFF) == 0xFF) {
            return Optional.of("image/jpeg");
        }
        if (b.length > 132 && b[128] == 'D' && b[129] == 'I' && b[130] == 'C' && b[131] == 'M') {
            return Optional.of("application/dicom");
        }
        return Optional.empty();
    }
}
