/**
 * AIRA k6 load test — ramp 10 → 500 events/sec
 *
 * Run:
 *   k6 run --env INGESTION_URL=http://localhost:8080 tooling/k6/load_test.js
 *
 * After the test finishes, assert consumer lag:
 *   python tooling/k6/check_consumer_lag.py
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const eventsAccepted  = new Counter('events_accepted_total');
const eventsRejected  = new Rate('events_rejected_rate');
const ingestionP99    = new Trend('ingestion_latency_p99_ms', true);

const BASE_URL  = (__ENV.INGESTION_URL || 'http://localhost:8080').replace(/\/$/, '');
const ENDPOINT  = `${BASE_URL}/v1/events`;

const SERVICES = [
  'payment-service',
  'order-service',
  'user-service',
  'inventory-service',
  'notification-service',
];

export const options = {
  scenarios: {
    load_ramp: {
      executor: 'ramping-arrival-rate',
      // Start slow to let the JVM warm up
      startRate: 10,
      timeUnit: '1s',
      // Pre-allocate enough VUs to handle peak rate; k6 scales up to maxVUs as needed
      preAllocatedVUs: 60,
      maxVUs: 700,
      stages: [
        { duration: '30s',  target: 10  },  // warm-up: 10 rps
        { duration: '90s',  target: 500 },  // ramp:    10 → 500 rps
        { duration: '60s',  target: 500 },  // hold:    500 rps
        { duration: '30s',  target: 50  },  // cooldown: 500 → 50 rps
      ],
    },
  },

  thresholds: {
    // Primary SLOs — failing these fails the test
    http_req_failed:   ['rate<0.01'],   // < 1% HTTP errors (non-2xx or network failure)
    http_req_duration: ['p(95)<200'],   // 95th percentile response < 200ms

    // Secondary signals — informational, don't fail the run
    events_rejected_rate:    ['rate<0.01'],
    ingestion_latency_p99_ms: ['p(99)<500'],
  },
};

function randomService() {
  return SERVICES[Math.floor(Math.random() * SERVICES.length)];
}

function makeMetricEvent(source) {
  // 5% chance of anomaly-triggering latency spike
  const isAnomaly = Math.random() < 0.05;
  return {
    source,
    type: 'metric',
    payload: {
      name: 'latency',
      value: isAnomaly
        ? parseFloat((2.0 + Math.random() * 3.0).toFixed(3))
        : parseFloat((0.05 + Math.random() * 0.45).toFixed(3)),
      metadata: { region: 'us-east-1', env: 'load-test' },
    },
  };
}

function makeLogEvent(source) {
  // 3% chance of error log
  const isError = Math.random() < 0.03;
  return {
    source,
    type: 'log',
    payload: {
      level: isError ? 'ERROR' : 'INFO',
      message: isError
        ? 'Connection timeout to upstream dependency'
        : 'Request processed successfully',
      metadata: { region: 'us-east-1', env: 'load-test' },
    },
  };
}

export default function () {
  const source = randomService();
  // Alternate metric and log events — mirrors realistic traffic mix
  const body = JSON.stringify(
    Math.random() < 0.6 ? makeMetricEvent(source) : makeLogEvent(source),
  );

  const res = http.post(ENDPOINT, body, {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'ingest' },
  });

  const ok = check(res, {
    'status 202': (r) => r.status === 202,
    'body has event_id': (r) => {
      try { return Boolean(JSON.parse(r.body).event_id); } catch { return false; }
    },
  });

  ingestionP99.add(res.timings.duration);

  if (ok) {
    eventsAccepted.add(1);
  } else {
    eventsRejected.add(true);
  }
}

export function handleSummary(data) {
  const rps = data.metrics.http_reqs?.values?.rate?.toFixed(1) ?? 'n/a';
  const p95 = data.metrics.http_req_duration?.values?.['p(95)']?.toFixed(1) ?? 'n/a';
  const p99 = data.metrics.http_req_duration?.values?.['p(99)']?.toFixed(1) ?? 'n/a';
  const errRate = ((data.metrics.http_req_failed?.values?.rate ?? 0) * 100).toFixed(2);
  const accepted = data.metrics.events_accepted_total?.values?.count ?? 0;

  console.log(`
╔═══════════════════════════════════════╗
║         AIRA Load Test Summary        ║
╠═══════════════════════════════════════╣
║  Peak rate targeted   : 500 rps       ║
║  Actual avg rate      : ${rps.padEnd(9)} rps  ║
║  Events accepted      : ${String(accepted).padEnd(14)} ║
║  Error rate           : ${errRate.padEnd(8)} %    ║
║  Latency p95          : ${p95.padEnd(8)} ms   ║
║  Latency p99          : ${p99.padEnd(8)} ms   ║
╚═══════════════════════════════════════╝

Next step: python tooling/k6/check_consumer_lag.py
`);

  return {
    'tooling/k6/results/load_test_summary.json': JSON.stringify(data, null, 2),
  };
}
