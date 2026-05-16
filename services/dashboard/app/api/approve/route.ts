import { NextRequest, NextResponse } from 'next/server';

const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL ?? 'http://orchestrator:8089';

export async function POST(request: NextRequest) {
  const { anomaly_id, approved_by = 'dashboard' } = await request.json() as {
    anomaly_id: string;
    approved_by?: string;
  };

  if (!anomaly_id) {
    return NextResponse.json({ error: 'anomaly_id required' }, { status: 400 });
  }

  const resp = await fetch(
    `${ORCHESTRATOR_URL}/approve/${anomaly_id}?approved_by=${encodeURIComponent(approved_by)}`,
    { method: 'POST' },
  );

  const body = await resp.json();
  return NextResponse.json(body, { status: resp.status });
}
