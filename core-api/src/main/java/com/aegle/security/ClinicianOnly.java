package com.aegle.security;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import org.springframework.security.access.prepost.PreAuthorize;

/** Clinical endpoints (patient data, worklist, review). Admins and auditors are excluded. */
@Target({ElementType.METHOD, ElementType.TYPE})
@Retention(RetentionPolicy.RUNTIME)
@Documented
@PreAuthorize("hasAnyRole('RADIOLOGIST','PHYSICIAN')")
public @interface ClinicianOnly {}
