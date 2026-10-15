package com.aegle.study;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * Identifies supported uploads by content, not by the client-supplied name or type: PNG,
 * JPEG, TIFF (pathology tiles), DICOM (images and ECG waveforms), EDF (EEG), and ECG CSV
 * exports (a header row of lead names).
 */
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
        // TIFF, little- ("II*\0") or big-endian ("MM\0*"): browsers cannot show it, so the
        // image endpoint serves a PNG rendering (see StudyService.image).
        if (b.length >= 4 && ((b[0] == 'I' && b[1] == 'I' && b[2] == 42 && b[3] == 0)
                || (b[0] == 'M' && b[1] == 'M' && b[2] == 0 && b[3] == 42))) {
            return Optional.of("image/tiff");
        }
        if (b.length > 132 && b[128] == 'D' && b[129] == 'I' && b[130] == 'C' && b[131] == 'M') {
            return Optional.of("application/dicom");
        }
        // EDF: an 8-byte version field that is "0" padded with spaces, then the header length.
        if (b.length >= 256 && new String(b, 0, 8, StandardCharsets.US_ASCII).equals("0       ")) {
            return Optional.of("application/edf");
        }
        if (isEcgCsv(b)) {
            return Optional.of("text/csv");
        }
        return Optional.empty();
    }

    /** The first non-comment line names at least leads I, II and V1. */
    private static boolean isEcgCsv(byte[] b) {
        String head = new String(b, 0, Math.min(b.length, 2048), StandardCharsets.UTF_8);
        if (head.chars().anyMatch(c -> c == 0 || (c < 0x20 && c != '\n' && c != '\r' && c != '\t'))) {
            return false;
        }
        String first = head.lines().map(String::strip).filter(l -> !l.isEmpty() && !l.startsWith("#"))
                .findFirst().orElse("");
        Set<String> cells = Arrays.stream(first.split(","))
                .map(c -> c.strip().toUpperCase().replace("LEAD", "").replaceAll("[ _-]", ""))
                .collect(Collectors.toSet());
        return cells.containsAll(Set.of("I", "II", "V1"));
    }
}
