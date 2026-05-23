# AIRA Helm Charts

Complete Kubernetes deployment for the AIRA (AI-driven Incident Response & Anomaly detection) system using Helm.

## Quick Start

```bash
# Deploy with default values
helm install aira charts/aira

# Deploy to specific namespace
helm install aira charts/aira --namespace aira --create-namespace

# Deploy with custom values
helm install aira charts/aira -f custom-values.yaml
```

## Chart Structure

- **aira** (umbrella chart) — Orchestrates deployment of all microservices
  - **ingestion** — REST API service (Spring Boot) with HPA
  - **anomaly** — Anomaly detection consumer (Python)
  - **llm-reasoner** — LLM-assisted reasoning (Python)
  - **orchestrator** — Temporal workflow orchestrator (Python)
  - **executor-agent** — K8s action executor with RBAC
  - **dashboard** — SSE-based frontend (Next.js)

## Configuration

### Global Values
All services inherit these from `values.yaml`:

```yaml
global:
  imageRegistry: docker.io
  imagePullPolicy: IfNotPresent
  kafkaBootstrapServers: kafka:29092
  postgresqlUser: alive
  postgresqlPassword: alive
  postgresqlDatabase: alive
  postgresqlHost: postgres
  postgresqlPort: 5432
  temporalHost: temporal
  temporalPort: 7233
```

### Service-Specific Configuration

#### Ingestion Service
- **HPA**: Enabled by default, scales 2-10 replicas based on CPU (70% threshold)
- **Resources**: 256Mi/0.25 requests, 1Gi/1 limits
- **Port**: 8080

Example override:
```yaml
ingestion:
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 20
    targetCPUUtilizationPercentage: 60
  resources:
    requests:
      memory: 512Mi
      cpu: 500m
```

#### Anomaly Detector
- **Replicas**: 2 (no HPA)
- **Detection Mode**: `rule-only` | `ml-only` | `hybrid`
- **Latency Threshold**: 2.0 seconds
- **Port**: 8001 (metrics)

#### LLM Reasoner
- **Replicas**: 1
- **LLM Provider**: `openai` | `anthropic` | `ollama`
- **API Keys**: Set via `secrets.openaiApiKey` and `secrets.anthropicApiKey`
- **Port**: 8082 (metrics)

#### Orchestrator
- **Replicas**: 1
- **Depends on**: Temporal, PostgreSQL, Kafka
- **Port**: 8089 (HTTP API)

#### Executor Agent
- **Replicas**: 1
- **RBAC**: Configured to access K8s API (Deployments, Pods, Services)
- **Dry Run**: Enabled by default (`config.dryRun: "true"`)
- **Port**: 8090 (HTTP API)

#### Dashboard
- **Replicas**: 1
- **Orchestrator URL**: http://orchestrator:8089
- **Port**: 3001

## Customization

### Create Custom Values File

```yaml
# custom-values.yaml
global:
  postgresqlPassword: mysecurepassword

ingestion:
  autoscaling:
    maxReplicas: 15

llm-reasoner:
  config:
    llmProvider: anthropic
  secrets:
    anthropicApiKey: sk-ant-xxx

dashboard:
  replicaCount: 2
```

Deploy with custom values:
```bash
helm install aira charts/aira -f custom-values.yaml
```

### Resource Limits

Update resource requests/limits per service:

```yaml
orchestrator:
  resources:
    requests:
      memory: 1Gi
      cpu: 1000m
    limits:
      memory: 2Gi
      cpu: 2000m
```

## Upgrade Deployment

```bash
helm upgrade aira charts/aira --values custom-values.yaml
```

## Uninstall

```bash
helm uninstall aira
```

## Validation

Validate chart syntax:
```bash
helm lint charts/aira
```

Render templates without deploying:
```bash
helm template aira charts/aira --values custom-values.yaml
```

## Troubleshooting

### Check Deployment Status
```bash
kubectl get deployments -l app.kubernetes.io/instance=aira
kubectl describe pod <pod-name>
kubectl logs <pod-name>
```

### Verify HPA Status
```bash
kubectl get hpa -l app.kubernetes.io/instance=aira
kubectl describe hpa aira-ingestion
```

### Check Service Connectivity
```bash
kubectl get svc -l app.kubernetes.io/instance=aira
kubectl port-forward svc/aira-ingestion 8080:8080
curl http://localhost:8080/actuator/health
```

## Notes

- All services use health probes (`livenessProbe`, `readinessProbe`)
- Executor Agent requires RBAC permissions for K8s API access
- LLM Reasoner secrets are base64-encoded; store actual API keys securely (e.g., external secret management)
- Kafka and Temporal must be available in the cluster before deploying
