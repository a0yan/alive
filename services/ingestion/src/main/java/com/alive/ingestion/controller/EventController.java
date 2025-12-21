package com.alive.ingestion.controller;

import com.alive.ingestion.model.Event;
import com.alive.ingestion.service.ProducerService;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
@RequestMapping("/v1/events")
public class EventController {

    @Autowired
    private ProducerService producerService;

    @PostMapping
    public ResponseEntity<Map<String, String>> ingestEvent(@Valid @RequestBody Event event) {
        // Fire and Forget (Async)
        producerService.sendEvent(event);
        
        // Return 202 Accepted immediately
        return ResponseEntity.accepted().body(Map.of(
            "status", "accepted",
            "event_id", event.getEventId()
        ));
    }
}