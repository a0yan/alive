package com.alive.ingestion.controller;

import com.alive.ingestion.model.Event;
import com.alive.ingestion.service.ProducerService;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/v1/events")
public class EventController {

    private final ProducerService producerService;

    public EventController(ProducerService producerService) {
        this.producerService = producerService;
    }

    @PostMapping
    public ResponseEntity<Map<String, String>> ingestEvent(@Valid @RequestBody Event event) {
        // Fire and forget — ProducerService callbacks handle success/error logging
        producerService.sendEvent(event);

        // 202 Accepted: event is buffered for Kafka, not yet guaranteed delivered
        return ResponseEntity.accepted().body(Map.of(
            "status", "accepted",
            "event_id", event.getEventId()
        ));
    }
}
