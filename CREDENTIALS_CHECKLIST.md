# Credentials & API Keys Checklist

**Purpose:** Track all external credentials, API keys, and configuration needed to run AIRA demo and CI/CD. Use this checklist before deployment and demo day.

**Status:** Pre-demo setup required. Update this document as credentials are obtained.

---

## 🔴 Critical Path (Demo Blockers)

These must be configured before running a live demo.

### LLM Service Credentials

- [ ] **OPENAI_API_KEY**
  - **Purpose:** GPT-4o (or model specified in `LLM_MODEL`)
  - **Scope:** LLM Reasoner service (root-cause analysis)
  - **Where to get:** https://platform.openai.com/account/api-keys
  - **How to provide:** Add to `.env` file:
    ```
    OPENAI_API_KEY=sk-...
    LLM_PROVIDER=openai
    LLM_MODEL=gpt-4o-mini
    ```
  - **Status:** ☐ Not obtained
  - **Notes:** Requires paid OpenAI account. gpt-4o-mini is cheap for demo (~$0.01 per event reasoned)

- [ ] **ANTHROPIC_API_KEY** (Alternative to OpenAI)
  - **Purpose:** Claude API for LLM reasoning (if using Anthropic instead)
  - **Scope:** LLM Reasoner service (optional, mutually exclusive with OpenAI)
  - **Where to get:** https://console.anthropic.com/account/keys
  - **How to provide:** Add to `.env` file:
    ```
    ANTHROPIC_API_KEY=sk-ant-...
    LLM_PROVIDER=anthropic
    LLM_MODEL=claude-3-5-sonnet-20241022
    ```
  - **Status:** ☐ Not obtained
  - **Notes:** Use either OpenAI OR Anthropic, not both. Set `LLM_PROVIDER` accordingly.

---

## 🟡 Infrastructure Setup (CI/CD & Deployment)

Required for GitHub Actions CI/CD pipeline and image deployment.

### GitHub Container Registry (ghcr.io)

- [ ] **GitHub Personal Access Token (PAT)**
  - **Purpose:** GitHub Actions CI/CD authentication to push images to ghcr.io
  - **Scope:** Image registry, Packages API
  - **Where to get:** GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
  - **Permissions needed:**
    - `packages:read` (pull images)
    - `packages:write` (push images)
  - **How to provide:** GitHub Actions uses `GITHUB_TOKEN` automatically (no manual setup)
  - **Status:** ✅ Automatic (GITHUB_TOKEN provided by GitHub Actions)
  - **Notes:** No manual action needed; GitHub provides this automatically in CI/CD

### Docker Registry Authentication

- [ ] **ghcr.io credentials (local development)**
  - **Purpose:** Pull images from ghcr.io during local smoke tests
  - **How to provide:** After images pushed, authenticate locally:
    ```bash
    echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
    ```
  - **Status:** ☐ Configure after first CI/CD run
  - **Notes:** Only needed if pulling images locally. CI/CD handles this automatically.

---

## 🟢 Database & Infrastructure (Already Configured)

These have defaults in `.env.example` and don't require external credentials.

### PostgreSQL

- [ ] **POSTGRES_USER**
  - **Default:** `alive`
  - **Status:** ✅ Uses default
  - **Purpose:** Temporal + audit log database
  - **Notes:** Docker-compose creates this automatically

- [ ] **POSTGRES_PASSWORD**
  - **Default:** `alive`
  - **Status:** ✅ Uses default
  - **Purpose:** DB access
  - **Notes:** Change for production. Safe for demo.

- [ ] **POSTGRES_DB**
  - **Default:** `alive`
  - **Status:** ✅ Uses default
  - **Purpose:** Database name
  - **Notes:** Auto-created by docker-compose

### Message Queue (Kafka)

- [ ] **KAFKA_BROKER**
  - **Default:** `kafka:29092`
  - **Status:** ✅ Docker-compose hostname
  - **Purpose:** Service-to-service communication
  - **Notes:** No credentials needed; internal network only

### Monitoring (Grafana)

- [ ] **GRAFANA_PASSWORD**
  - **Default:** `admin`
  - **Status:** ✅ Uses default
  - **Purpose:** Access Grafana UI (http://localhost:3000)
  - **Notes:** Change for production. Safe for demo.

---

## 🟠 Optional Enhancements (Post-Demo)

These are nice-to-have but not required for a basic demo.

### Observability

- [ ] **OpenTelemetry Collector credentials** (if using external backend)
  - **Purpose:** Distributed tracing export to Jaeger/Datadog/etc.
  - **Status:** ☐ Not used (local Prometheus only)
  - **Notes:** Currently traces go to console. Can add external backend later.

- [ ] **Datadog API Key** (if using Datadog for metrics)
  - **Purpose:** Export metrics to Datadog dashboard
  - **Status:** ☐ Not integrated
  - **Notes:** Future enhancement. Prometheus/Grafana sufficient for demo.

### Kubernetes (Executor Agent)

- [ ] **KUBECONFIG** or **K8S_CONTEXT**
  - **Purpose:** Executor agent connects to K8s for dry-run actions
  - **Status:** ☐ Uses local cluster (minikube) or skips if unavailable
  - **Notes:** Executor agent gracefully skips if K8s unavailable. Not demo-critical.

---

## Demo Day Checklist (1 Hour Before)

Use this immediately before demo to verify everything is ready.

- [ ] `.env` file created from `.env.example`
- [ ] `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` set and valid
- [ ] `LLM_PROVIDER` and `LLM_MODEL` correct
- [ ] Database credentials match docker-compose (or using defaults)
- [ ] Docker images built or pulled from ghcr.io:
  ```bash
  docker-compose pull
  ```
- [ ] Stack starts cleanly:
  ```bash
  docker-compose up
  ```
- [ ] Services healthy (wait ~30s):
  ```bash
  curl http://localhost:8080/actuator/health  # Ingestion
  curl http://localhost:3001/health            # Dashboard
  curl http://localhost:9090                   # Prometheus
  curl http://localhost:3000                   # Grafana
  ```
- [ ] Run smoke test (if not using CI/CD):
  ```bash
  curl -X POST http://localhost:8080/v1/events \
    -H 'Content-Type: application/json' \
    -d '{"source":"demo","timestamp":"2026-05-23T00:00:00Z","type":"metric","payload":{"name":"latency","value":2.5}}'
  ```
- [ ] Verify anomaly detected (check Kafka):
  ```bash
  docker exec kafka kafka-console-consumer.sh \
    --bootstrap-server localhost:9092 \
    --topic anomalies.detected \
    --from-beginning \
    --max-messages 1
  ```
- [ ] Grafana dashboard loads (http://localhost:3000, admin/admin)

---

## Credential Rotation & Security

### For Production Deployment

- [ ] Rotate all default passwords (Grafana, Postgres, Grafana)
- [ ] Secure `.env` file (not committed to git, restricted permissions)
- [ ] Use secrets manager for K8s deployment (e.g., Sealed Secrets, HashiCorp Vault)
- [ ] Rotate API keys quarterly
- [ ] Monitor API usage and set spending limits (OpenAI, Anthropic)

### For CI/CD

- [ ] GitHub Actions secrets configured in repo settings:
  - `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
  - (GITHUB_TOKEN is automatic)
- [ ] No credentials in `.github/workflows/ci.yml` (use `${{ secrets.* }}` references)
- [ ] Review GitHub Actions logs for any accidental secret exposure

---

## Troubleshooting

### "Unauthorized: authentication required" (ghcr.io push fails)

**Cause:** GitHub Actions doesn't have permission to push images.

**Fix:** Ensure GitHub Actions workflow has:
```yaml
- name: Log in to ghcr.io
  run: |
    echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u ${{ github.actor }} --password-stdin
```

### "Invalid API key" (LLM requests fail)

**Cause:** OpenAI/Anthropic API key incorrect or invalid.

**Fix:** 
1. Verify key in `.env`:
   ```bash
   grep OPENAI_API_KEY .env
   ```
2. Test key directly:
   ```bash
   curl https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
   ```
3. Check API key hasn't been revoked in provider dashboard

### "Connection refused" (LLM Reasoner can't reach API)

**Cause:** Network or firewall blocking API calls.

**Fix:**
1. Check internet connectivity:
   ```bash
   curl https://api.openai.com
   ```
2. If behind proxy, set `http_proxy` / `https_proxy` env vars
3. Check firewall rules (corporate networks may block API calls)

---

## Reference

**Last Updated:** 2026-05-23  
**AIRA Version:** Day 22+ (CI/CD complete, demo-ready)

For more info, see [CLAUDE.md - Configuration](../CLAUDE.md#configuration)
