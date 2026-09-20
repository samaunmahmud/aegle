package com.aegle.security;

import java.util.Set;
import java.util.UUID;

/** The authenticated clinician making a request, resolved from their login token. */
public record Actor(UUID userId, UUID orgId, String subject, Set<String> roles) {}
