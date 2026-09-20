package com.aegle.web;

public class NotFoundException extends RuntimeException {
    public NotFoundException(String what) {
        super(what);
    }
}
