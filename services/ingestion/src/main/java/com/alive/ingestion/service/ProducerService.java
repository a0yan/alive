package com.alive.ingestion.service;

import com.alive.ingestion.model.Event;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
public class ProducerService {

    private static final String TOPIC = "ingestion.events";

    @Autowired
    private KafkaTemplate<String, Object> kafkaTemplate;

    public void sendEvent(Event event) {
        // Asynchronous send
        //TODO add loggers
        kafkaTemplate.send(TOPIC, event.getSource(), event)
            .whenComplete((result, ex) -> {
                if (ex == null) {
                    // Success logging (optional in high-load prod)
                    // System.out.println("Sent event=[" + event.getEventId() + "]");
                } else {
                    // Error logging - Critical
                    System.err.println("Unable to send event=[" + event.getEventId() + "] due to : " + ex.getMessage());
                }
            });
    }
}