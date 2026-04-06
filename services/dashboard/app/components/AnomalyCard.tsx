'use client';

export interface Anomaly {
  anomaly_id: string;
  type: string;
  source_event_id: string;
  timestamp: string;
  description: string;
  raw_data?: { source?: string };
}

const TYPE_STYLES: Record<string, string> = {
  HighLatency: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  ErrorLog:    'bg-red-100 text-red-800 border-red-200',
  MLAnomaly:   'bg-purple-100 text-purple-800 border-purple-200',
};

export function AnomalyCard({ anomaly }: { anomaly: Anomaly }) {
  const badge = TYPE_STYLES[anomaly.type] ?? 'bg-blue-100 text-blue-800 border-blue-200';
  const source = anomaly.raw_data?.source ?? anomaly.source_event_id;
  const time = new Date(anomaly.timestamp).toLocaleTimeString();

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <span className={`rounded border px-2 py-0.5 text-xs font-medium ${badge}`}>
          {anomaly.type}
        </span>
        <span className="text-xs text-gray-400">{time}</span>
      </div>
      <p className="text-sm font-medium text-gray-800">{source}</p>
      <p className="mt-1 text-sm text-gray-500">{anomaly.description}</p>
      <p className="mt-1 text-xs text-gray-300 font-mono">{anomaly.anomaly_id}</p>
    </div>
  );
}
