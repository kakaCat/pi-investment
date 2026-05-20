import { describe, expect, jest, test } from "@jest/globals";
import express from "express";
import http from "node:http";
import type { AddressInfo } from "node:net";
import type { Socket } from "node:net";

await jest.unstable_mockModule("../../../services/quant/quant-service.js", () => ({
  QuantService: class {
    async listStrategies(): Promise<unknown[]> {
      return [];
    }

    async getStrategy(): Promise<null> {
      return null;
    }

    async createStrategy(): Promise<never> {
      throw new Error("createStrategy should be blocked by ops auth");
    }
  },
}));

await jest.unstable_mockModule("child_process", () => ({
  spawn(): never {
    throw new Error("training spawn should be blocked by ops auth");
  },
}));

const { strategiesRouter } = await import("./strategies.js");
const { backtestRouter } = await import("./backtest.js");
const { signalsRouter } = await import("./signals.js");
const { trainingRouter } = await import("./training.js");

type JsonResponse<T> = {
  status: number;
  body: T;
  rawBody: string;
};

async function withServer<T>(app: express.Express, run: (baseUrl: string) => Promise<T>): Promise<T> {
  const server = app.listen(0);
  const sockets = new Set<Socket>();
  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.once("close", () => sockets.delete(socket));
  });

  try {
    await new Promise<void>((resolve) => server.once("listening", resolve));
    const address = server.address() as AddressInfo;
    return await run(`http://127.0.0.1:${address.port}`);
  } finally {
    server.closeAllConnections();
    for (const socket of sockets) {
      socket.destroy();
    }
    await new Promise<void>((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
}

async function requestJson<T>(
  url: string,
  options: { method?: string; headers?: Record<string, string>; body?: string } = {},
): Promise<JsonResponse<T>> {
  return new Promise((resolve, reject) => {
    const request = http.request(url, {
      method: options.method ?? "GET",
      headers: options.headers,
      agent: false,
    }, (response) => {
      let rawBody = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        rawBody += chunk;
      });
      response.on("end", () => {
        const body = rawBody.trim().startsWith("{")
          ? JSON.parse(rawBody) as T
          : rawBody as T;
        resolve({
          status: response.statusCode ?? 0,
          body,
          rawBody,
        });
      });
    });

    request.on("error", reject);
    if (options.body) {
      request.write(options.body);
    }
    request.end();
  });
}

describe("operations auth on mutating quant-web routes", () => {
  test("rejects state-changing routes when OPS_API_TOKEN is configured", async () => {
    const previousToken = process.env.OPS_API_TOKEN;
    process.env.OPS_API_TOKEN = "secret-token";
    const app = express();
    app.use(express.json());
    app.use("/api/strategies", strategiesRouter);
    app.use("/api/backtest", backtestRouter);
    app.use("/api/signals", signalsRouter);
    app.use("/api/training", trainingRouter);

    try {
      await withServer(app, async (baseUrl) => {
        const requests = [
          ["POST /api/strategies", requestJson(`${baseUrl}/api/strategies`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ name: "test" }),
          })],
          ["PUT /api/strategies/s1", requestJson(`${baseUrl}/api/strategies/s1`, {
            method: "PUT",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ name: "test" }),
          })],
          ["DELETE /api/strategies/s1", requestJson(`${baseUrl}/api/strategies/s1`, { method: "DELETE" })],
          ["POST /api/strategies/s1/enable", requestJson(`${baseUrl}/api/strategies/s1/enable`, { method: "POST" })],
          ["POST /api/strategies/s1/disable", requestJson(`${baseUrl}/api/strategies/s1/disable`, { method: "POST" })],
          ["POST /api/backtest/run", requestJson(`${baseUrl}/api/backtest/run`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ strategy_id: "s1", symbol: "000001", start_date: "2026-01-01", end_date: "2026-05-19" }),
          })],
          ["POST /api/signals/generate", requestJson(`${baseUrl}/api/signals/generate`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ strategy_id: "s1", symbol: "000001", name: "平安银行" }),
          })],
          ["POST /api/signals/scan", requestJson(`${baseUrl}/api/signals/scan`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ strategy_id: "s1", stocks: [{ symbol: "000001", name: "平安银行" }] }),
          })],
          ["POST /api/training/start", requestJson(`${baseUrl}/api/training/start`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ days: 90 }),
          })],
        ] as const;

        const responses = await Promise.all(requests.map(async ([name, request]) => [name, await request] as const));
        for (const [name, response] of responses) {
          try {
            expect(response.status).toBe(401);
            expect(response.body).toEqual({
              success: false,
              error: "Missing or invalid operations token",
            });
          } catch (error) {
            throw new Error(`${name} was not guarded: ${response.status} ${response.rawBody}`, { cause: error });
          }
        }
      });
    } finally {
      if (previousToken === undefined) {
        delete process.env.OPS_API_TOKEN;
      } else {
        process.env.OPS_API_TOKEN = previousToken;
      }
    }
  });

  test("keeps read-only routes accessible when OPS_API_TOKEN is configured", async () => {
    const previousToken = process.env.OPS_API_TOKEN;
    process.env.OPS_API_TOKEN = "secret-token";
    const app = express();
    app.use("/api/strategies", strategiesRouter);
    app.use("/api/backtest", backtestRouter);
    app.use("/api/training", trainingRouter);

    try {
      await withServer(app, async (baseUrl) => {
        const strategies = await requestJson<{ success?: boolean; data?: unknown }>(`${baseUrl}/api/strategies`);
        const backtests = await requestJson<{ count?: unknown; summary?: unknown }>(`${baseUrl}/api/backtest/results`);
        const history = await requestJson<{ count?: unknown; history?: unknown }>(`${baseUrl}/api/training/history`);

        expect(strategies.status).toBe(200);
        expect(strategies.body).toEqual({ success: true, data: [] });
        expect(backtests.status).toBe(200);
        expect(Array.isArray(backtests.body.summary)).toBe(true);
        expect(history.status).toBe(200);
        expect(Array.isArray(history.body.history)).toBe(true);
      });
    } finally {
      if (previousToken === undefined) {
        delete process.env.OPS_API_TOKEN;
      } else {
        process.env.OPS_API_TOKEN = previousToken;
      }
    }
  });
});
