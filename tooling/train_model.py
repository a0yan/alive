import pandas as pd
from sklearn.ensemble import IsolationForest
import matplotlib.pyplot as plt
import joblib  # Helper to save the model to a file

# 1. Load the Data
print("Loading data...")
df = pd.read_csv('training_data.csv')


X = df[['latency', 'metadata_size']]


model = IsolationForest(contamination=0.05, random_state=42)


print("Training Isolation Forest...")
model.fit(X)


df['anomaly_score'] = model.predict(X)
# The model returns:
#  1  = Normal
# -1  = Anomaly

# 5. Visualize the Results
print("Generating plot...")
plt.figure(figsize=(10, 6))

# Plot Normal points in Blue
normal = df[df['anomaly_score'] == 1]
plt.scatter(normal['latency'], normal['metadata_size'], c='blue', label='Normal')

# Plot Anomalies in Red
anomalies = df[df['anomaly_score'] == -1]
plt.scatter(anomalies['latency'], anomalies['metadata_size'], c='red', label='Anomaly')

plt.xlabel('Latency (seconds)')
plt.ylabel('Metadata Size (bytes)')
plt.title('Isolation Forest Detection Results')
plt.legend()

# Save the plot
plt.savefig('model_visualization.png')
print("Visualization saved to 'model_visualization.png'")

# 6. Save the Trained Model
joblib.dump(model, 'isolation_forest.pkl')
print(" Model saved to 'isolation_forest.pkl'")