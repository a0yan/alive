import { AnomalyFeed } from './components/AnomalyFeed';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-xl font-semibold text-gray-900">
          AIRA — Anomaly Feed
        </h1>
        <p className="mt-0.5 text-sm text-gray-500">
          Live stream from <code className="font-mono text-xs">anomalies.detected</code>
        </p>
      </header>
      <main className="mx-auto max-w-2xl px-6 py-8">
        <AnomalyFeed />
      </main>
    </div>
  );
}
