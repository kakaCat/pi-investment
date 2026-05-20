import { describe, expect, test } from "@jest/globals";
import express from "express";
import type { AddressInfo } from "node:net";
import { requireOpsAuth } from "./ops-auth.js";

async function withServer<T>(app: express.Express, run: (baseUrl: string) => Promise<T>): Promise<T> {
  const server = app.listen(0);
  try {
    await new Promise<void>((resolve) => server.once("listening", resolve));
    const address = server.address() as AddressInfo;
    return await run(`http://127.0.0.1:${address.port}`);
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close((error) => error ? reject(error) : resolve());
    });
  }
}

describe("requireOpsAuth", () => {
  test("allows requests when no token is configured", async () => {
    const app = express();
    app.post("/mutate", requireOpsAuth(undefined), (_req, res) => res.json({ ok: true }));

    await withServer(app, async (baseUrl) => {
      const response = await fetch(`${baseUrl}/mutate`, { method: "POST" });
      expect(response.status).toBe(200);
    });
  });

  test("rejects mutating requests when configured token is missing", async () => {
    const app = express();
    app.post("/mutate", requireOpsAuth("secret-token"), (_req, res) => res.json({ ok: true }));

    await withServer(app, async (baseUrl) => {
      const response = await fetch(`${baseUrl}/mutate`, { method: "POST" });
      const body = await response.json() as { success?: boolean; error?: string };

      expect(response.status).toBe(401);
      expect(body).toEqual({ success: false, error: "Missing or invalid operations token" });
    });
  });

  test("allows bearer and x-pi-ops-token tokens", async () => {
    const app = express();
    app.post("/mutate", requireOpsAuth("secret-token"), (_req, res) => res.json({ ok: true }));

    await withServer(app, async (baseUrl) => {
      const bearer = await fetch(`${baseUrl}/mutate`, {
        method: "POST",
        headers: { authorization: "Bearer secret-token" },
      });
      const header = await fetch(`${baseUrl}/mutate`, {
        method: "POST",
        headers: { "x-pi-ops-token": "secret-token" },
      });

      expect(bearer.status).toBe(200);
      expect(header.status).toBe(200);
    });
  });
});
