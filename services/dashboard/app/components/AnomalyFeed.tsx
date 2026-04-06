'use client';

import { useState, useEffect } from 'react';
import { AnomalyCard, Anomaly } from './AnomalyCard';

const MAX_ANOMALIES = 50;

export function AnomalyFeed() {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const es = new EventSource('/api/events/stream');

    es.onopen = () => setConnected(true);

    es.onmessage = (event: MessageEvent) => {
      try {
        const anomaly: Anomaly = JSON.parse(event.data as string);
        // Prepend so newest is at the top; cap at MAX_ANOMALIES to prevent unbounded growth.
        setAnomalies(prev => [anomaly, ...prev].slice(0, MAX_ANOMALIES));
      } catch {
        console.error('Failed to parse SSE message', event.data);
      }
    };

    es.onerror = () => setConnected(false);

    return () => es.close();
  }, []);

  return (
    <div>
      {/* Connection status indicator */}
      <div className="mb-4 flex items-center gap-2">
        <span
          className={`inline-block h-2 w-2 rounded-full ${
            connected ? 'bg-green-500' : 'bg-red-400'
          }`}
        />
        <span className="text-sm text-gray-500">
          {connected ? 'Live' : 'Connecting…'}
        </span>
        {anomalies.length > 0 && (
          <span className="ml-auto text-xs text-gray-400">
            {anomalies.length} anomal{anomalies.length === 1 ? 'y' : 'ies'}
          </span>
        )}
      </div>

      {anomalies.length === 0 ? (
        <p className="text-sm text-gray-400">Waiting for anomalies…</p>
      ) : (
        <div className="flex flex-col gap-3">
          {anomalies.map(a => (
            <AnomalyCard key={a.anomaly_id} anomaly={a} />
          ))}
        </div>
      )}
    </div>
  );
}
