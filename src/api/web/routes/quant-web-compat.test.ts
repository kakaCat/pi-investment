import { describe, expect, jest, test } from "@jest/globals";
import express from "express";
import http from "node:http";
import type { Socket } from "node:net";
import type { AddressInfo } from "net";
import { stocksRouter } from "./stocks.js";
import { trainingRouter } from "./training.js";

await jest.unstable_mockModule("../../../services/quant/backtest-engine.js", () => ({
  BacktestEngine: class {
    async runBacktest(): Promise<never> {
      throw new Error("BacktestEngine should not run in compatibility route tests");
    }
  },
}));

await jest.unstable_mockModule("../../../services/quant/quant-service.js", () => ({
  QuantService: class {
    async getStrategy(): Promise<null> {
      return null;
    }
  },
}));

const { backtestRouter } = await import("./backtest.js");
const { signalsRouter } = await import("./signals.js");

type JsonResponse<T> = {
  status: number;
  body: T;
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

async function requestJson<T>(url: string, options: {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
} = {}): Promise<JsonResponse<T>> {
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
        try {
          resolve({
            status: response.statusCode ?? 0,
            body: JSON.parse(rawBody) as T,
          });
        } catch (error) {
          reject(error);
        }
      });
    });

    request.on("error", reject);
    if (options.body) {
      request.write(options.body);
    }
    request.end();
  });
}

describe("quant-web compatibility routes", () => {
  test("GET /api/signals returns a top-level signals array", async () => {
    const fetchMock = jest.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({
      signals: [{ symbol: "000001", signal: "BUY", confidence: 0.8 }],
      count: 1,
      date: "2026-05-19",
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    const app = express();
    app.use("/api/signals", signalsRouter);

    await withServer(app, async (baseUrl) => {
      const response = await requestJson<{ signals?: unknown }>(`${baseUrl}/api/signals`);

      expect(response.status).toBe(200);
      expect(Array.isArray(response.body.signals)).toBe(true);
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:5001/api/signals",
        expect.any(Object)
      );
    });

    fetchMock.mockRestore();
  });

  test("POST /api/stocks/compare returns a top-level comparisons array", async () => {
    const fetchMock = jest.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({
      comparisons: [{ symbol: "000001", price: 10 }],
      count: 1,
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    const app = express();
    app.use(express.json());
    app.use("/api/stocks", stocksRouter);

    await withServer(app, async (baseUrl) => {
      const response = await requestJson<{ comparisons?: unknown }>(`${baseUrl}/api/stocks/compare`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ symbols: ["000001", "600036"] }),
      });

      expect(response.status).toBe(200);
      expect(Array.isArray(response.body.comparisons)).toBe(true);
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:5001/api/stocks/compare",
        expect.objectContaining({ method: "POST" })
      );
    });

    fetchMock.mockRestore();
  });

  test("GET /api/stocks/data-status proxies Python API data status", async () => {
    const fetchMock = jest.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({
      total_stocks: 2,
      complete_stocks: 1,
      incomplete_stocks: 1,
      stocks: [],
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    const app = express();
    app.use("/api/stocks", stocksRouter);

    await withServer(app, async (baseUrl) => {
      const response = await requestJson<{ total_stocks?: unknown }>(`${baseUrl}/api/stocks/data-status`);

      expect(response.status).toBe(200);
      expect(response.body.total_stocks).toBe(2);
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:5001/api/stocks/data-status",
        expect.any(Object)
      );
    });

    fetchMock.mockRestore();
  });

  test("GET /api/training/history returns count and history", async () => {
    const app = express();
    app.use("/api/training", trainingRouter);

    await withServer(app, async (baseUrl) => {
      const response = await requestJson<{ count?: unknown; history?: unknown }>(`${baseUrl}/api/training/history`);

      expect(response.status).toBe(200);
      expect(typeof response.body.count).toBe("number");
      expect(Array.isArray(response.body.history)).toBe(true);
      expect(response.body.count).toBe((response.body.history as unknown[]).length);
    });
  });

  test("GET /api/backtest/results returns count and summary", async () => {
    const app = express();
    app.use("/api/backtest", backtestRouter);

    await withServer(app, async (baseUrl) => {
      const response = await requestJson<{ count?: unknown; summary?: unknown }>(`${baseUrl}/api/backtest/results`);

      expect(response.status).toBe(200);
      expect(typeof response.body.count).toBe("number");
      expect(Array.isArray(response.body.summary)).toBe(true);
      expect(response.body.count).toBe((response.body.summary as unknown[]).length);
    });
  });
});
