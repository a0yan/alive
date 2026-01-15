import time
import requests
import json
import random
import uuid
import csv  # <--- NEW
import os

API_URL = "http://localhost:8080/v1/events"
SERVICES = ["payment-service", "order-service", "user-service"]

# File to save training data
CSV_FILE = "../training_data.csv"

def run_simulation():
    # Setup CSV Writer
    file_exists = os.path.isfile(CSV_FILE)
    
    with open(CSV_FILE, 'a', newline='') as csvfile:
        fieldnames = ['latency', 'metadata_size', 'source_id']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # Only write header if file is new
        if not file_exists:
            writer.writeheader()

        print(f" Generator Started. Saving data to {CSV_FILE}...")
        
        while True:
            # 1. Generate Random Data
            source = random.choice(SERVICES)
            
            # Normal behavior: Latency between 0.1 and 0.5
            # Anomaly behavior: Random spikes
            if random.random() < 0.05: # 5% chance of anomaly
                latency = random.uniform(2.0, 5.0) 
            else:
                latency = random.uniform(0.1, 0.5)

            metadata = {"region": "us-east-1", "user": "test"}
            metadata_size = len(json.dumps(metadata))
            
            # Map source string to a number (ML models like numbers)
            source_mapping = {"payment-service": 1, "order-service": 2, "user-service": 3}
            source_id = source_mapping.get(source, 0)

            # 2. Save to CSV (The "Memory" for ML)
            writer.writerow({
                'latency': latency,
                'metadata_size': metadata_size,
                'source_id': source_id
            })
            csvfile.flush() # Ensure it writes immediately

            # 3. Send to API (Keep the dashboard alive)
            event = {
                "event_id": str(uuid.uuid4()),
                "source": source,
                "payload": {"value": latency, "metadata": metadata}
            }
            
            try:
                requests.post(API_URL, json=event)
                print(f"Recorded: {latency:.2f}s")
            except:
                print("API unreachable, but CSV saved.")

            time.sleep(0.1)

if __name__ == "__main__":
    run_simulation()