package com.aegle.storage;

import com.aegle.config.AegleProperties;
import io.minio.BucketExistsArgs;
import io.minio.GetObjectArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import java.io.ByteArrayInputStream;
import java.io.InputStream;
import org.springframework.stereotype.Component;

/** S3-compatible storage (MinIO locally, S3 in production). */
@Component
public class MinioObjectStore implements ObjectStore {

    private final MinioClient client;
    private final String bucket;
    private volatile boolean bucketReady;

    public MinioObjectStore(AegleProperties props) {
        var s = props.storage();
        this.client = MinioClient.builder().endpoint(s.endpoint()).credentials(s.accessKey(), s.secretKey()).build();
        this.bucket = s.bucket();
    }

    @Override
    public void put(String key, byte[] data, String contentType) {
        try {
            ensureBucket();
            client.putObject(PutObjectArgs.builder().bucket(bucket).object(key)
                    .stream(new ByteArrayInputStream(data), data.length, -1)
                    .contentType(contentType).build());
        } catch (Exception e) {
            throw new IllegalStateException("Object store write failed", e);
        }
    }

    @Override
    public byte[] get(String key) {
        try (InputStream in = client.getObject(GetObjectArgs.builder().bucket(bucket).object(key).build())) {
            return in.readAllBytes();
        } catch (Exception e) {
            throw new IllegalStateException("Object store read failed", e);
        }
    }

    /** Created lazily so the API can start before MinIO is reachable. */
    private void ensureBucket() throws Exception {
        if (bucketReady) {
            return;
        }
        if (!client.bucketExists(BucketExistsArgs.builder().bucket(bucket).build())) {
            client.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
        }
        bucketReady = true;
    }
}
