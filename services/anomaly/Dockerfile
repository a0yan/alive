FROM python:3.10-slim

WORKDIR /app

# Install dependencies first — cached layer, only rebuilds when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Mount point for the trained ML model (injected at runtime via volume or build arg)
# Path must match MODEL_PATH env var in consumer.py
RUN mkdir -p /app/models

# Unbuffered output ensures log lines appear immediately in docker-compose logs
CMD ["python", "-u", "-m", "app.main"]

# Prometheus metrics endpoint — consumer is healthy when it can serve metrics
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/')" || exit 1
