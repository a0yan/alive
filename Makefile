.PHONY: up down test-integration load-test check-lag test-all

# ── Stack ─────────────────────────────────────────────────────────────────────
up:
	docker-compose up -d

down:
	docker-compose down

# ── Unit / contract tests ─────────────────────────────────────────────────────
test-anomaly:
	pytest services/anomaly/tests/ -v

test-orchestrator:
	cd services/orchestrator && pip install -q -r requirements.txt && \
	pytest tests/ -v

# ── Integration smoke test ────────────────────────────────────────────────────
test-integration:
	python tooling/integration_test.py \
	  --api http://localhost:8080 \
	  --broker localhost:9092

# ── Load test (requires k6: https://k6.io/docs/get-started/installation/) ────
load-test:
	k6 run \
	  --env INGESTION_URL=http://localhost:8080 \
	  tooling/k6/load_test.js

check-lag:
	python tooling/k6/check_consumer_lag.py \
	  --broker localhost:9092 \
	  --max-lag 1000 \
	  --wait 10

# ── Full test pipeline: load → wait → assert lag ──────────────────────────────
test-load: load-test check-lag

# ── Run everything ────────────────────────────────────────────────────────────
test-all: test-anomaly test-orchestrator test-integration
