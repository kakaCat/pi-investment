import { afterEach, describe, expect, jest, test } from "@jest/globals";
import express from "express";
import http from "node:http";
import type { Socket } from "node:net";
import type { AddressInfo } from "net";

const { stocksRouter } = await import("./stocks.js");

afterEach(() => {
  jest.restoreAllMocks();
});

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

async function requestJson<T>(url: string, body: unknown): Promise<JsonResponse<T>> {
  return new Promise((resolve, reject) => {
    const request = http.request(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
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
    request.write(JSON.stringify(body));
    request.end();
  });
}

describe("POST /api/stocks/resolve", () => {
  test("proxies symbol resolution to the Python quant API", async () => {
    const fetchMock = jest.spyOn(globalThis, "fetch").mockResolvedValueOnce(new Response(JSON.stringify({
      success: true,
      data: {
        valid: [{ symbol: "600036", source: "external_added" }],
        invalid: [],
        stocks: [{ symbol: "600036", source: "external_added" }],
      },
    }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }));
    const app = express();
    app.use(express.json());
    app.use("/api/stocks", stocksRouter);

    await withServer(app, async (baseUrl) => {
      const response = await requestJson<{
        success: boolean;
        data: {
          valid: Array<{ symbol: string; source: string }>;
          invalid: unknown[];
        };
      }>(`${baseUrl}/api/stocks/resolve`, {
        symbols: ["000001", "600036"],
        requiredDays: 180,
      });

      expect(response.status).toBe(200);
      expect(response.body.success).toBe(true);
      expect(response.body.data.valid).toEqual([
        expect.objectContaining({ symbol: "600036", source: "external_added" }),
      ]);
      expect(response.body.data.invalid).toEqual([]);
      expect(fetchMock).toHaveBeenCalledWith(
        "http://127.0.0.1:5001/api/stocks/resolve",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });
});
