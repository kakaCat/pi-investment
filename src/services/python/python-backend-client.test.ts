import { describe, test, expect, beforeEach, afterEach, jest } from "@jest/globals";
import { PythonBackendClient } from "./python-backend-client.js";

describe("PythonBackendClient", () => {
  let originalEnv: NodeJS.ProcessEnv;

  beforeEach(() => {
    originalEnv = { ...process.env };
    (PythonBackendClient as any).instance = undefined;
  });

  afterEach(() => {
    process.env = originalEnv;
    jest.restoreAllMocks();
  });

  test("getInstance returns same instance", () => {
    const instance1 = PythonBackendClient.getInstance();
    const instance2 = PythonBackendClient.getInstance();
    expect(instance1).toBe(instance2);
  });

  test("uses default baseURL when env var not set", () => {
    delete process.env.PYTHON_BACKEND_URL;
    const client = PythonBackendClient.getInstance();
    expect((client as any).baseURL).toBe("http://localhost:5000");
  });

  test("uses env var for baseURL when set", () => {
    process.env.PYTHON_BACKEND_URL = "http://custom:8080";
    const client = PythonBackendClient.getInstance();
    expect((client as any).baseURL).toBe("http://custom:8080");
  });

  test("uses default timeout when env var not set", () => {
    delete process.env.PYTHON_BACKEND_TIMEOUT;
    const client = PythonBackendClient.getInstance();
    expect((client as any).timeout).toBe(30000);
  });

  test("uses env var for timeout when set", () => {
    process.env.PYTHON_BACKEND_TIMEOUT = "5000";
    const client = PythonBackendClient.getInstance();
    expect((client as any).timeout).toBe(5000);
  });

  test("makes GET request with query params", async () => {
    const client = PythonBackendClient.getInstance();
    const mockResponse = { data: "test" };

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      })
    ) as any;

    const result = await client.get("/api/test", { param1: "value1", param2: "value2" });

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:5000/api/test?param1=value1&param2=value2",
      expect.objectContaining({
        method: "GET",
        signal: expect.any(AbortSignal),
      })
    );
    expect(result).toEqual(mockResponse);
  });

  test("makes POST request with body", async () => {
    const client = PythonBackendClient.getInstance();
    const mockResponse = { id: 1, created: true };
    const requestBody = { name: "test", value: 123 };

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 201,
        json: async () => mockResponse,
      })
    ) as any;

    const result = await client.post("/api/create", requestBody);

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:5000/api/create",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
        signal: expect.any(AbortSignal),
      })
    );
    expect(result).toEqual(mockResponse);
  });

  test("throws 503 on ECONNREFUSED", async () => {
    const client = PythonBackendClient.getInstance();

    const connRefusedError: any = new Error("fetch failed");
    connRefusedError.cause = { code: "ECONNREFUSED" };

    global.fetch = jest.fn(() => Promise.reject(connRefusedError)) as any;

    await expect(client.get("/api/test")).rejects.toMatchObject({
      status: 503,
      message: "Python backend service unavailable",
    });
  });

  test("throws 504 on timeout", async () => {
    const client = PythonBackendClient.getInstance();

    const timeoutError: any = new Error("The operation was aborted");
    timeoutError.name = "AbortError";

    global.fetch = jest.fn(() => Promise.reject(timeoutError)) as any;

    await expect(client.get("/api/test")).rejects.toMatchObject({
      status: 504,
      message: "Gateway timeout",
    });
  });

  test("healthCheck returns true when backend is healthy", async () => {
    const client = PythonBackendClient.getInstance();

    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ status: "ok" }),
      })
    ) as any;

    const result = await client.healthCheck();

    expect(fetch).toHaveBeenCalledWith(
      "http://localhost:5000/health",
      expect.objectContaining({
        method: "GET",
        signal: expect.any(AbortSignal),
      })
    );
    expect(result).toBe(true);
  });

  test("healthCheck returns false when backend is unavailable", async () => {
    const client = PythonBackendClient.getInstance();

    const connRefusedError: any = new Error("fetch failed");
    connRefusedError.cause = { code: "ECONNREFUSED" };

    global.fetch = jest.fn(() => Promise.reject(connRefusedError)) as any;

    const result = await client.healthCheck();
    expect(result).toBe(false);
  });
});

