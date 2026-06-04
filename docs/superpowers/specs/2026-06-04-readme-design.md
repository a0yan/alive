---
name: readme-design
description: Design spec for AIRA Day 28 README — hybrid structure targeting both recruiters and engineers
metadata:
  type: project
---

# AIRA README Design Spec

**Date:** 2026-06-04
**Audience:** Recruiters/hiring managers + engineers
**Goal:** Single README.md at repo root that earns a second look from both audiences

---

## Structure (top to bottom)

### Section 1 — Header
- `# AIRA — AI-driven Incident Response & Anomaly Detection`
- 2-sentence hook: what the system does + what the tech stack demonstrates
- Badge row: CI status (`github.com/a0yan/alive` workflow `ci.yml`) + Python 3.10 + Java 17 + license

### Section 2 — Architecture
- `## Architecture`
- Mermaid `flowchart TD` diagram covering full pipeline:
  - Simulator → `POST /v1/events` → Ingestion (`:8080`)
  - Ingestion → Kafka `ingestion.events` → Anomaly Detector (`:8001`)
  - Anomaly Detector → Kafka `anomalies.detected` → LLM Reasoner (`:8082`) + Orchestrator
  - Orchestrator (Temporal) → Executor Agent (`:8090`)
  - Side nodes: PostgreSQL audit_log, Grafana (`:3000`), Prometheus (`:9090`), Jaeger (`:16686`)
  - Dashboard (`:3001`) reading from Kafka + PostgreSQL via SSE
- Kafka topic labels on arrows

### Section 3 — Run in 60 Seconds
- `## Run in 60 Seconds`
- Prerequisite: Docker + Docker Compose
- 4 steps:
  1. `cp .env.example .env`
  2. `docker-compose up` (note: waits for Kafka health automatically)
  3. `python tooling/simulation/generator.py` (sends ~5% anomaly rate events)
  4. Open links table: Dashboard `:3001`, Grafana `:3000`, Temporal UI `:8088`, Jaeger `:16686`, Prometheus `:9090`

### Section 4 — Key Engineering Decisions
- `## Key Engineering Decisions`
- 5 entries, each: **bold title** — one sentence what + one sentence why (the interview-ready version)
  1. **Kafka for event transport** — async decoupling so LLM latency (~2s) never blocks anomaly detection; Kafka also enables replay for reprocessing historical events with a new model
  2. **Temporal for orchestration** — workflow state survives crashes (durable timers + event sourcing); heartbeat pattern makes the LLM call safe to retry without double-executing
  3. **SSE not WebSockets for dashboard** — works over plain HTTP/1.1, no upgrade handshake, no extra infra; sufficient for one-directional live feed
  4. **dry_run="All" on K8s executor** — demonstrates real kubectl capability (reads cluster state, produces a full diff) without risk; safe for a portfolio demo without a prod cluster
  5. **Isolation Forest for anomaly ML** — interpretable (contamination parameter maps directly to expected anomaly rate ~5%), trains on 1800 samples without labels, handles multivariate payloads

### Section 5 — Observability
- `## Observability`
- Intro line: "All services emit Prometheus metrics; traces propagate via W3C TraceContext."
- Port/tool table: Grafana `:3000`, Prometheus `:9090`, Jaeger `:16686`, Temporal UI `:8088`
- 3 Grafana dashboards bullet list:
  - **System Health** — Kafka consumer lag, events/sec, anomalies/sec by type, ingestion p95 latency
  - **LLM Reasoning** — LLM latency p50/p95/p99, confidence score distribution, auto-execute vs. manual ratio
  - **Audit/Business** — anomalies by source service, MTTR, pending approvals count (queries PostgreSQL directly)

### Section 6 — Configuration
- `## Configuration`
- Intro: "All tuneable values live in `.env` (never committed). Copy `.env.example` to get started."
- Full env var table:

| Variable | Default | Purpose |
|---|---|---|
| `KAFKA_BROKER` | `kafka:29092` | Kafka bootstrap server |
| `LATENCY_THRESHOLD` | `2.0` | Seconds above which a metric triggers HighLatency anomaly |
| `DETECTION_MODE` | `rule-only` | `rule-only` \| `ml-only` \| `hybrid` |
| `ANOMALY_CONFIDENCE_THRESHOLD` | `0.8` | LLM confidence above which actions auto-execute |
| `LLM_PROVIDER` | `openai` | `openai` \| `anthropic` |
| `LLM_MODEL` | — | Model name for chosen provider |
| `OPENAI_API_KEY` | — | Required if `LLM_PROVIDER=openai` |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `POSTGRES_USER` | — | PostgreSQL credentials |
| `POSTGRES_PASSWORD` | — | PostgreSQL credentials |
| `POSTGRES_DB` | — | Database name |

---

## Constraints

- No screenshots (demo-day decision — Grafana panels need live data to look good)
- No contribution/license sections (portfolio project, not OSS)
- README.md at repo root (`C:/Projects/alive/README.md`)
- Mermaid diagram must render on GitHub (use `flowchart TD` not `graph TD` for best compat)
- CI badge URL: `https://github.com/a0yan/alive/actions/workflows/ci.yml/badge.svg`

---

## Files Changed

| File | Action |
|---|---|
| `README.md` | Create at repo root |
