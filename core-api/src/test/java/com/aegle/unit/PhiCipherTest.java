package com.aegle.unit;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.aegle.config.AegleProperties;
import com.aegle.phi.PhiCipher;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class PhiCipherTest {

    private static String key() {
        byte[] k = new byte[32];
        new SecureRandom().nextBytes(k);
        return Base64.getEncoder().encodeToString(k);
    }

    private static PhiCipher cipher(String enc, String hash) {
        return new PhiCipher(new AegleProperties(null, null, null, new AegleProperties.Phi(enc, hash),
                null, null, null, null));
    }

    @Test
    void roundTripsAndNeverRepeatsCiphertext() {
        PhiCipher c = cipher(key(), key());
        byte[] a = c.encrypt("Jane Doe", "patients.name");
        byte[] b = c.encrypt("Jane Doe", "patients.name");
        assertThat(c.decrypt(a, "patients.name")).isEqualTo("Jane Doe");
        assertThat(a).isNotEqualTo(b);                                // fresh random IV each time
        assertThat(new String(a)).doesNotContain("Jane");
    }

    @Test
    void aValueMovedToAnotherColumnDoesNotDecrypt() {
        PhiCipher c = cipher(key(), key());
        byte[] mrn = c.encrypt("12345", "patients.mrn");
        assertThatThrownBy(() -> c.decrypt(mrn, "patients.name")).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void tamperedOrForeignCiphertextIsRejected() {
        byte[] data = cipher(key(), key()).encrypt("x", "patients.mrn");
        assertThatThrownBy(() -> cipher(key(), key()).decrypt(data, "patients.mrn"))   // different key
                .isInstanceOf(IllegalStateException.class);
        PhiCipher c = cipher(key(), key());
        byte[] mine = c.encrypt("x", "patients.mrn");
        mine[mine.length - 1] ^= 1;
        assertThatThrownBy(() -> c.decrypt(mine, "patients.mrn")).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void nullStaysNull() {
        assertThat(cipher(key(), key()).decrypt(null, "patients.dob")).isNull();
    }

    @Test
    void mrnHashIsStableCaseInsensitiveAndPerOrganisation() {
        PhiCipher c = cipher(key(), key());
        UUID a = UUID.randomUUID(), b = UUID.randomUUID();
        assertThat(c.mrnHash(a, " ab-12 ")).isEqualTo(c.mrnHash(a, "AB-12"));
        assertThat(c.mrnHash(a, "AB-12")).isNotEqualTo(c.mrnHash(b, "AB-12"));
    }

    @Test
    void badKeysStopTheApplicationFromStarting() {
        assertThatThrownBy(() -> cipher("not base64!!", key())).hasMessageContaining("AEGLE_PHI_ENC_KEY");
        assertThatThrownBy(() -> cipher(Base64.getEncoder().encodeToString(new byte[16]), key()))
                .hasMessageContaining("32 bytes");
    }
}
