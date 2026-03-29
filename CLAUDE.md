# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: AIRA

**AIRA** (AI-driven Incident Response & Anomaly detection) is a portfolio project built on a 30-day plan. The goal is a functioning end-to-end prototype that:
- Ingests simulated events via REST API
- Detects anomalies (rule-based + ML Isolation Forest)
- Uses LLM-assisted reasoning for root-cause analysis
- Runs Temporal workflows for safe, human-approved remediation
- Has full observability (Prometheus, Grafana, OpenTelemetry tracing) and CI/CD

**Current status (~Day 11):** Ingestion service, anomaly consumer (rules + metrics), Isolation Forest ML model, simulation tooling, and all infrastructure fixes are complete. Services not yet built: `dashboard`, `llm-reasoner`, `orchestrator`, `executor-agent`.

---

## Running the System

```bash
# Copy env file and fill in any API keys before first run
cp .env.example .env

# Start all services (waits for Kafka health before starting app services)
docker-compose up

# Stop everything
docker-compose down
```

## Services

### Ingestion Service (Java/Spring Boot) — `services/ingestion/`
- REST API on port 8080; accepts `POST /v1/events`
- Produces to Kafka topic `ingestion.events` (fire-and-forget, returns 202 Accepted)
- Kafka topic is configurable via `kafka.topic.ingestion` property
- Prometheus metrics at `/actuator/prometheus`

```bash
cd services/ingestion
mvn clean package -DskipTests   # Build JAR
mvn clean package               # Build with tests
```

### Anomaly Detection Service (Python) — `services/anomaly/`
- Consumes `ingestion.events`, produces to `anomalies.detected`
- Supports `DETECTION_MODE`: `rule-only` | `ml-only` | `hybrid` (env var)
- `LATENCY_THRESHOLD` is configurable via env var (default 2.0s)
- Prometheus metrics on port 8001

```bash
cd services/anomaly
pip install -r requirements.txt
python -m app.main
```

## Tooling — `tooling/`

```bash
# Train the Isolation Forest model (reads training_data.csv, writes isolation_forest.pkl)
cd tooling
python train_model.py

# Run the event simulator (~5% anomaly rate, POSTs to Ingestion API, saves CSV for ML training)
cd tooling/simulation
python generator.py
```

---

## Architecture

### Current (Implemented)
```
Simulator → POST /v1/events
              ↓
     Ingestion Service (Spring Boot :8080)
              ↓ Kafka: ingestion.events
     Anomaly Detector (Python :8001)    ← rules + Isolation Forest (DETECTION_MODE toggle)
              ↓ Kafka: anomalies.detected
     Prometheus (:9090) → Grafana (:3000)
```

### Full Planned Architecture
```
Simulator → POST /v1/events
              ↓
     Ingestion Service (Spring Boot :8080)
              ↓ Kafka: ingestion.events
     Anomaly Detector (Python :8001)
              ↓ Kafka: anomalies.detected
     LLM Reasoner (Python :8082)         ← Kafka consumer, produces to llm.responses
              ↓ Kafka: llm.responses
     Orchestrator (Temporal worker)      ← enrich → ask_llm → decide → execute
              ↓
     Executor Agent (K8s dry-run)        ← dry_run="All" always in dev
              ↓
     Dashboard (Next.js + SSE)           ← live feed + LLM panel + approval UI
              ↓
     PostgreSQL audit_log table
```

**Infrastructure (Docker Compose):**
- Kafka on 9092, Zookeeper on 2181
- PostgreSQL on 5432 (credentials from `.env`) — used by Temporal + audit log
- Temporal on 7233 (gRPC), web UI on 8088

---

## Event Schema — AIRA Schema v1

**Wire format: `snake_case` throughout** (all Kafka messages use snake_case field names).

### Ingestion event (produced by ingestion service, consumed by anomaly detector)
```json
{
  "event_id": "UUID",
  "source": "orders-service",
  "timestamp": "2024-01-01T00:00:00Z",
  "type": "metric",
  "payload": {
    "name": "latency",
    "value": 2.5,
    "level": "ERROR",
    "metadata": {}
  }
}
```

### Anomaly event (produced by anomaly detector)
```json
{
  "anomaly_id": "anom-<event_id>",
  "source_event_id": "<event_id>",
  "timestamp": "ISO-8601",
  "type": "HighLatency | ErrorLog",
  "description": "string",
  "raw_data": { /* original event */ }
}
```

### LLM response schema (to be produced by llm-reasoner)
```json
{
  "root_causes": [{"label": "string", "reason": "string"}],
  "actions": [{"action": "string", "target": {"kind": "string", "name": "string"}}],
  "confidence": 0.0,
  "summary": "string"
}
```

---

## Configuration

All tuneable values live in `.env` (never committed — see `.env.example`).

| Variable | Default | Purpose |
|---|---|---|
| `KAFKA_BROKER` | `kafka:29092` | Kafka bootstrap server |
| `LATENCY_THRESHOLD` | `2.0` | Seconds above which a metric triggers HighLatency anomaly |
| `DETECTION_MODE` | `rule-only` | `rule-only` \| `ml-only` \| `hybrid` |
| `ANOMALY_CONFIDENCE_THRESHOLD` | `0.8` | LLM confidence above which actions auto-execute |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | LLM service credentials |

Key config files:

| File | Purpose |
|---|---|
| `services/ingestion/src/main/resources/application.properties` | Spring Boot: Kafka bootstrap, producer batching (10ms linger, 16KB batch) |
| `charts/prometheus/prometheus.yml` | Scrapes ingestion (`/actuator/prometheus`) and anomaly (`:8001/metrics`) every 5s |

---

## Services Not Yet Built

| Service | Path | Tech | Key Design Decision |
|---|---|---|---|
| LLM Reasoner | `services/llm-reasoner/` | Python | **Kafka consumer** (not HTTP) — decouples LLM latency from pipeline; reads `anomalies.detected`, produces to `llm.responses` |
| Orchestrator | `services/orchestrator/` | Temporal Python SDK | Ask LLM via **Kafka + heartbeat** (durable across crashes); `confidence > 0.8` auto-executes, else human approval via Temporal signal |
| Executor Agent | `services/executor-agent/` | Python + k8s client | Always `dry_run="All"` in dev; logs full diff of what *would* change to `audit_log` |
| Dashboard | `services/dashboard/` | Next.js | **SSE** not WebSockets — works over plain HTTP, no extra infra |

---

## Testing Strategy

Tests in priority order (write these before adding new features):

1. **Schema contract test** — `services/anomaly/tests/test_schema.py`: Ensures `event_id` (snake_case) is correctly read; prevents the `eventId`/`event_id` class of bugs from recurring
2. **Rule engine unit tests** — `services/anomaly/tests/test_consumer.py`: Test `process_event` with latency below/above threshold, ERROR log, malformed JSON — pure functions, no Kafka needed
3. **Ingestion controller test** — `services/ingestion/src/test/java/.../EventControllerTest.java`: `@SpringBootTest` + `@MockBean ProducerService`; assert 202 on valid POST, 400 on missing `source`
4. **Temporal workflow test** (Week 3) — `services/orchestrator/tests/test_workflow.py`: Use `temporalio.testing.WorkflowEnvironment` with mocked activities; assert routing by confidence score

Run Python tests:
```bash
pytest services/anomaly/tests/
```

---

## Upcoming Build Roadmap

```
Day 12:   LLM Reasoner skeleton (Kafka consumer, schema validation, .env API key)
          + schema contract test
Day 13:   ML hybrid mode in consumer.py + rule engine unit tests
Day 14:   Dashboard skeleton (Next.js, SSE endpoint, basic anomaly feed)
          + OpenTelemetry on ingestion (Java agent, zero code changes)
Day 15:   Temporal orchestrator — workflow definition + activity stubs
          + PostgreSQL audit_log schema (services/orchestrator/db/schema.sql)
Day 16:   Enrich + Ask LLM activities (heartbeat pattern for durability)
Day 17:   Decide + Execute activities + approval signal + dashboard approval button
Day 18:   Executor agent (dry-run K8s + audit log writes) + Temporal workflow test
Day 19:   k6 load test (ramp 10→500 events/sec, assert consumer lag < 1000)
Day 20-21: Integration pass-through + buffer
Day 22:   GitHub Actions Stage 1+2 (lint, test, Trivy security scan)
Day 23:   GitHub Actions Stage 3 (docker-compose smoke test)
Day 24-25: Helm charts — one per service + umbrella chart
Day 26-27: Grafana dashboards as JSON (auto-provisioned via volume mount)
          3 dashboards: System Health, LLM Reasoning, Audit/Business
Day 28:   README — architecture SVG, "Run in 60 seconds", "Key Engineering Decisions"
Day 29:   Demo video + docs/runbooks/
Day 30:   Buffer / polish
```

### Audit Log Schema (for Day 15)
```sql
CREATE TABLE audit_log (
  id            SERIAL PRIMARY KEY,
  workflow_id   TEXT NOT NULL,
  anomaly_id    TEXT NOT NULL,
  source        TEXT NOT NULL,
  anomaly_type  TEXT NOT NULL,
  llm_summary   TEXT,
  confidence    FLOAT,
  action_taken  TEXT,
  action_status TEXT,  -- auto_executed | pending_approval | approved | rejected | skipped
  approved_by   TEXT,  -- null for auto-executed
  created_at    TIMESTAMPTZ DEFAULT now(),
  resolved_at   TIMESTAMPTZ
);
```

### Grafana Dashboards (for Day 26-27)
Three dashboards targeting specific questions:
1. **System Health** — Kafka consumer lag (most important operational metric), events/sec, anomalies/sec by type
2. **LLM Reasoning** — latency p50/p95/p99 histogram, confidence distribution, auto-execute vs. manual ratio
3. **Audit/Business** — anomalies by source service, MTTR, pending approvals count
