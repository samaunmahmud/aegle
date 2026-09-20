package com.aegle.support;

import com.aegle.storage.ObjectStore;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public class InMemoryObjectStore implements ObjectStore {

    public final Map<String, byte[]> objects = new ConcurrentHashMap<>();

    @Override
    public void put(String key, byte[] data, String contentType) {
        objects.put(key, data);
    }

    @Override
    public byte[] get(String key) {
        byte[] data = objects.get(key);
        if (data == null) {
            throw new IllegalStateException("missing object " + key);
        }
        return data;
    }
}
