package com.alive.ingestion.model;

import jakarta.validation.constraints.NotNull;
import lombok.Data;
import java.util.Map;
import java.util.UUID;

@Data
public class Event {
    
    private String eventId;
    
    @NotNull(message = "Source is mandatory")
    private String source; // e.g., "orders-service"
    
    private String timestamp;
    
    @NotNull(message = "Type is mandatory")
    private String type;   // e.g., "metric", "log"
    
    private Map<String, Object> payload;

    // Constructor to auto-generate ID if missing
    public Event() {
        this.eventId = UUID.randomUUID().toString();
        this.timestamp = java.time.Instant.now().toString();
    }
}