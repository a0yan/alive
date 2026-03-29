package com.alive.ingestion.controller;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

    /**
     * Bean validation failures (@NotNull, @Size, etc.) → 400 with field-level errors.
     * Callers get a machine-readable list of exactly which fields failed.
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException ex) {
        List<String> errors = ex.getBindingResult().getFieldErrors()
                .stream()
                .map(e -> e.getField() + ": " + e.getDefaultMessage())
                .collect(Collectors.toList());

        log.warn("Rejected event — validation failed: {}", errors);

        return ResponseEntity.badRequest().body(Map.of(
                "status", "invalid",
                "errors", errors
        ));
    }

    /**
     * Catch-all — prevents stack traces leaking to callers and ensures a consistent error shape.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, String>> handleUnexpected(Exception ex) {
        log.error("Unhandled exception in request: {}", ex.getMessage(), ex);
        return ResponseEntity.internalServerError().body(Map.of(
                "status", "error",
                "message", "An internal error occurred"
        ));
    }
}
