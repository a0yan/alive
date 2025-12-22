import requests
import time
import random
import uuid
from datetime import datetime, timezone

# API Configuration
API_URL = "http://localhost:8080/v1/events"
HEADERS = {"Content-Type": "application/json"}

# Simulation Settings
TOTAL_EVENTS = 50
DELAY_SECONDS = 0.5  # Speed of simulation

def generate_payload():
    """Generates a realistic event payload"""
    # 10% chance of an anomaly (High Latency)
    is_anomaly = random.random() < 0.10
    
    if is_anomaly:
        latency = random.uniform(2.5, 5.0) # > 2.0s triggers the rule
        print(f" Generating ANOMALY: Latency {latency:.2f}s")
    else:
        latency = random.uniform(0.1, 1.5) # Normal traffic

    return {
        "event_id": str(uuid.uuid4()),
        "source": "payment-service",
        "type": "metric",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "payload": {
            "name": "latency",
            "value": latency,
            "unit": "seconds",
            "host": "pod-payment-01"
        }
    }

def run_simulation():
    print(f" Starting Simulation: Targeting {API_URL}")
    print("------------------------------------------------")

    for i in range(1, TOTAL_EVENTS + 1):
        event = generate_payload()
        
        try:
            # Send to Spring Boot Ingestion API
            response = requests.post(API_URL, json=event, headers=HEADERS)
            
            if response.status_code == 202:
                print(f"[{i}/{TOTAL_EVENTS}]  Sent: {event['payload']['value']:.2f}s latency")
            else:
                print(f"[{i}/{TOTAL_EVENTS}]  Failed: {response.status_code} - {response.text}")
        
        except requests.exceptions.ConnectionError:
            print(f"[{i}/{TOTAL_EVENTS}]  Connection Refused! Is Ingestion Service (localhost:8080) running?")
            break

        time.sleep(DELAY_SECONDS)

    print("------------------------------------------------")
    print(" Simulation Complete.")

if __name__ == "__main__":
    run_simulation()