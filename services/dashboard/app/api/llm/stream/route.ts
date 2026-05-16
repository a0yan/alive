import { Kafka } from 'kafkajs';
import { NextRequest } from 'next/server';

const kafka = new Kafka({
  clientId: 'dashboard-llm',
  brokers: [(process.env.KAFKA_BROKER ?? 'kafka:29092')],
});

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const consumer = kafka.consumer({
        groupId: `dashboard-llm-sse-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      });

      await consumer.connect();
      await consumer.subscribe({ topic: 'llm.responses', fromBeginning: false });

      await consumer.run({
        eachMessage: async ({ message }) => {
          const value = message.value?.toString();
          if (value) {
            controller.enqueue(encoder.encode(`data: ${value}\n\n`));
          }
        },
      });

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
      'X-Accel-Buffering': 'no',
    },
  });
}
