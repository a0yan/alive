FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY app ./app

# Run the consumer (unbuffered output so logs show up instantly)
CMD ["python", "-u", "-m", "app.main"]