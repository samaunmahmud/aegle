package com.aegle.phi;

import com.aegle.config.AegleProperties;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;
import java.util.UUID;
import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.stereotype.Component;

/**
 * Application-level encryption for patient identifiers (AES-256-GCM) and a keyed hash
 * for looking a patient up by MRN without decrypting every row.
 *
 * Ciphertext layout: 12-byte random IV || ciphertext+tag. The column name is bound in as
 * authenticated data, so a value copied into a different column fails to decrypt.
 */
@Component
public class PhiCipher {

    private static final int IV_BYTES = 12;
    private static final int TAG_BITS = 128;

    private final SecretKeySpec encKey;
    private final SecretKeySpec hashKey;
    private final SecureRandom random = new SecureRandom();

    public PhiCipher(AegleProperties props) {
        this.encKey = new SecretKeySpec(decode(props.phi().encKey(), "AEGLE_PHI_ENC_KEY"), "AES");
        this.hashKey = new SecretKeySpec(decode(props.phi().hashKey(), "AEGLE_PHI_HASH_KEY"), "HmacSHA256");
    }

    private static byte[] decode(String base64, String name) {
        byte[] key;
        try {
            key = Base64.getDecoder().decode(base64.trim());
        } catch (IllegalArgumentException e) {
            throw new IllegalStateException(name + " is not valid base64");
        }
        if (key.length != 32) {
            throw new IllegalStateException(name + " must be 32 bytes (generate with: openssl rand -base64 32)");
        }
        return key;
    }

    public byte[] encrypt(String plaintext, String column) {
        try {
            byte[] iv = new byte[IV_BYTES];
            random.nextBytes(iv);
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, encKey, new GCMParameterSpec(TAG_BITS, iv));
            cipher.updateAAD(column.getBytes(StandardCharsets.UTF_8));
            byte[] ct = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
            byte[] out = new byte[IV_BYTES + ct.length];
            System.arraycopy(iv, 0, out, 0, IV_BYTES);
            System.arraycopy(ct, 0, out, IV_BYTES, ct.length);
            return out;
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Encryption failed", e);
        }
    }

    public String decrypt(byte[] stored, String column) {
        if (stored == null) {
            return null;
        }
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, encKey,
                    new GCMParameterSpec(TAG_BITS, Arrays.copyOfRange(stored, 0, IV_BYTES)));
            cipher.updateAAD(column.getBytes(StandardCharsets.UTF_8));
            return new String(cipher.doFinal(stored, IV_BYTES, stored.length - IV_BYTES), StandardCharsets.UTF_8);
        } catch (GeneralSecurityException | IllegalArgumentException e) {
            throw new IllegalStateException("Could not decrypt " + column, e);
        }
    }

    /** Stable per organisation, so the same MRN in two organisations never matches. */
    public byte[] mrnHash(UUID orgId, String mrn) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(hashKey);
            return mac.doFinal((orgId + ":" + mrn.trim().toUpperCase()).getBytes(StandardCharsets.UTF_8));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Hashing failed", e);
        }
    }
}
