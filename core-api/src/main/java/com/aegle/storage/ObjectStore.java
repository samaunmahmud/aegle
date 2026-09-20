package com.aegle.storage;

/** Where image bytes live. The database only ever holds the key. */
public interface ObjectStore {
    void put(String key, byte[] data, String contentType);

    byte[] get(String key);
}
