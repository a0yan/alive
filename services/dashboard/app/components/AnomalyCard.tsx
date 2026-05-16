'use client';

import { useState } from 'react';

export interface Anomaly {
  anomaly_id: string;
  type: string;
  source_event_id: string;
  timestamp: string;
  description: string;
  raw_data?: { source?: string };
}

export interface LLMResult {
  anomaly_id: string;
  confidence: number;
  summary: string;
  actions: { action: string; target: { kind: string; name: string } }[];
  root_causes: { label: string; reason: string }[];
  source?: string;
}

const TYPE_STYLES: Record<string, string> = {
  HighLatency: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  ErrorLog:    'bg-red-100 text-red-800 border-red-200',
  MLAnomaly:   'bg-purple-100 text-purple-800 border-purple-200',
};

const CONFIDENCE_THRESHOLD = 0.8;

function ApproveButton({ anomalyId }: { anomalyId: string }) {
  const [state, setState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');

  async function handleApprove() {
    setState('loading');
    try {
      const resp = await fetch('/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anomaly_id: anomalyId }),
      });
      setState(resp.ok ? 'done' : 'error');
    } catch {
      setState('error');
    }
  }

  if (state === 'done') {
    return <span className="text-xs text-green-600 font-medium">Approved</span>;
  }
  if (state === 'error') {
    return <span className="text-xs text-red-500">Approval failed</span>;
  }

  return (
    <button
      onClick={handleApprove}
      disabled={state === 'loading'}
      className="rounded border border-orange-300 bg-orange-50 px-3 py-1 text-xs font-medium text-orange-700 hover:bg-orange-100 disabled:opacity-50"
    >
      {state === 'loading' ? 'Approving…' : 'Approve action'}
    </button>
  );
}

export function AnomalyCard({
  anomaly,
  llm,
}: {
  anomaly: Anomaly;
  llm?: LLMResult;
}) {
  const badge = TYPE_STYLES[anomaly.type] ?? 'bg-blue-100 text-blue-800 border-blue-200';
  const source = anomaly.raw_data?.source ?? anomaly.source_event_id;
  const time = new Date(anomaly.timestamp).toLocaleTimeString();
  const needsApproval = llm && llm.confidence < CONFIDENCE_THRESHOLD;

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

      {llm && (
        <div className="mt-3 rounded border border-gray-100 bg-gray-50 p-3 text-xs space-y-1">
          <div className="flex items-center justify-between">
            <span className="font-medium text-gray-600">LLM Analysis</span>
            <span
              className={`font-mono font-semibold ${
                llm.confidence >= CONFIDENCE_THRESHOLD
                  ? 'text-green-600'
                  : 'text-orange-500'
              }`}
            >
              {(llm.confidence * 100).toFixed(0)}% confidence
            </span>
          </div>
          <p className="text-gray-600">{llm.summary}</p>
          {llm.actions.length > 0 && (
            <p className="text-gray-500">
              Action:{' '}
              <span className="font-mono">{llm.actions[0].action}</span>{' '}
              {llm.actions[0].target.name}
            </p>
          )}
          {needsApproval && (
            <div className="pt-1">
              <ApproveButton anomalyId={anomaly.anomaly_id} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
