import { Kafka } from 'kafkajs';
import { NextRequest } from 'next/server';

// Kafka client is module-level so the connection can be reused across requests
// in a long-running Node.js process (not re-created on every SSE connection).
const kafka = new Kafka({
  clientId: 'dashboard',
  brokers: [(process.env.KAFKA_BROKER ?? 'kafka:29092')],
});

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const consumer = kafka.consumer({
        // Unique groupId per connection so multiple browser tabs each get all messages.
        groupId: `dashboard-sse-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      });

      await consumer.connect();
      await consumer.subscribe({ topic: 'anomalies.detected', fromBeginning: false });

      await consumer.run({
        eachMessage: async ({ message }) => {
          const value = message.value?.toString();
          if (value) {
            // SSE format: "data: <payload>\n\n"
            controller.enqueue(encoder.encode(`data: ${value}\n\n`));
          }
        },
      });

      // Disconnect and close the stream when the client navigates away.
      request.signal.addEventListener('abort', async () => {
        try {
          await consumer.disconnect();
        } finally {
          controller.close();
        }
      });
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      // Prevents proxies from buffering the stream
      'X-Accel-Buffering': 'no',
    },
  });
}
