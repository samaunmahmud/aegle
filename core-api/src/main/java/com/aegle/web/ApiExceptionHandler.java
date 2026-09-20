package com.aegle.web;

import jakarta.validation.ConstraintViolationException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;
import org.springframework.web.multipart.MaxUploadSizeExceededException;
import org.springframework.web.multipart.support.MissingServletRequestPartException;
import org.springframework.web.server.ResponseStatusException;

/**
 * Maps failures to RFC 7807 problem responses. Messages are written here, never taken from
 * exceptions, so internals and patient data do not leak into error bodies.
 */
@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(NotFoundException.class)
    ProblemDetail notFound(NotFoundException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, "Not found");
    }

    @ExceptionHandler(ConflictException.class)
    ProblemDetail conflict(ConflictException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, e.getMessage());
    }

    @ExceptionHandler(BadRequestException.class)
    ProblemDetail badRequest(BadRequestException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, e.getMessage());
    }

    @ExceptionHandler({MethodArgumentNotValidException.class, ConstraintViolationException.class,
            MissingServletRequestParameterException.class, MissingServletRequestPartException.class,
            MethodArgumentTypeMismatchException.class})
    ProblemDetail invalid(Exception e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, "Invalid request");
    }

    @ExceptionHandler(MaxUploadSizeExceededException.class)
    ProblemDetail tooLarge(MaxUploadSizeExceededException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.PAYLOAD_TOO_LARGE, "File too large");
    }

    @ExceptionHandler(ResponseStatusException.class)
    ProblemDetail status(ResponseStatusException e) {
        HttpStatus status = HttpStatus.resolve(e.getStatusCode().value());
        return ProblemDetail.forStatusAndDetail(e.getStatusCode(),
                status == HttpStatus.FORBIDDEN || status == HttpStatus.UNAUTHORIZED
                        ? "Access denied" : String.valueOf(e.getReason()));
    }

    @ExceptionHandler(AccessDeniedException.class)
    ProblemDetail denied(AccessDeniedException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.FORBIDDEN, "Access denied");
    }

    @ExceptionHandler(AuthenticationException.class)
    ProblemDetail unauthenticated(AuthenticationException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.UNAUTHORIZED, "Authentication required");
    }

    @ExceptionHandler(Exception.class)
    ProblemDetail unexpected(Exception e) {
        log.error("Unhandled error", e);
        return ProblemDetail.forStatusAndDetail(HttpStatus.INTERNAL_SERVER_ERROR, "Internal error");
    }
}
