package com.alive.ingestion.service;

import com.alive.ingestion.model.Event;
import io.micrometer.core.instrument.MeterRegistry;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
public class ProducerService {

    private static final Logger log = LoggerFactory.getLogger(ProducerService.class);

    @Value("${kafka.topic.ingestion:ingestion.events}")
    private String topic;

    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final MeterRegistry meterRegistry;

    public ProducerService(KafkaTemplate<String, Object> kafkaTemplate, MeterRegistry meterRegistry) {
        this.kafkaTemplate = kafkaTemplate;
        this.meterRegistry = meterRegistry;
    }

    public void sendEvent(Event event) {
        kafkaTemplate.send(topic, event.getSource(), event)
            .whenComplete((result, ex) -> {
                if (ex == null) {
                    // Increment per-source, per-type counter — enables Grafana queries like
                    // "events/sec broken down by service" without extra log parsing
                    meterRegistry.counter("events_ingested_total",
                            "source", event.getSource(),
                            "type", event.getType())
                        .increment();
                    log.info("Sent event_id={} source={} type={} to topic={}",
                            event.getEventId(), event.getSource(), event.getType(), topic);
                } else {
                    meterRegistry.counter("events_ingested_errors_total",
                            "source", event.getSource())
                        .increment();
                    log.error("Failed to send event_id={} source={}: {}",
                            event.getEventId(), event.getSource(), ex.getMessage());
                }
            });
    }
}
