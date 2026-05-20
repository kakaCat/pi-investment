export class PythonBackendClient {
  private static instance: PythonBackendClient;
  private baseURL: string;
  private timeout: number;

  private constructor() {
    this.baseURL = process.env.PYTHON_BACKEND_URL || "http://localhost:5000";
    this.timeout = parseInt(process.env.PYTHON_BACKEND_TIMEOUT || "30000", 10);
  }

  public static getInstance(): PythonBackendClient {
    if (!PythonBackendClient.instance) {
      PythonBackendClient.instance = new PythonBackendClient();
    }
    return PythonBackendClient.instance;
  }

  public async get(path: string, params?: Record<string, any>): Promise<any> {
    let url = `${this.baseURL}${path}`;
    if (params && Object.keys(params).length > 0) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        searchParams.append(key, String(value));
      }
      url = `${url}?${searchParams.toString()}`;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: "GET",
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData: any = await response.json().catch(() => ({}));
        const error: any = new Error(errorData.error || response.statusText);
        error.status = response.status;
        throw error;
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);

      if (error.name === "AbortError") {
        const timeoutError: any = new Error("Gateway timeout");
        timeoutError.status = 504;
        throw timeoutError;
      }

      if (error.cause?.code === "ECONNREFUSED") {
        const connError: any = new Error("Python backend service unavailable");
        connError.status = 503;
        throw connError;
      }

      throw error;
    }
  }

  public async post(path: string, body: any): Promise<any> {
    const url = `${this.baseURL}${path}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData: any = await response.json().catch(() => ({}));
        const error: any = new Error(errorData.error || response.statusText);
        error.status = response.status;
        throw error;
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);

      if (error.name === "AbortError") {
        const timeoutError: any = new Error("Gateway timeout");
        timeoutError.status = 504;
        throw timeoutError;
      }

      if (error.cause?.code === "ECONNREFUSED") {
        const connError: any = new Error("Python backend service unavailable");
        connError.status = 503;
        throw connError;
      }

      throw error;
    }
  }

  public async put(path: string, body: any): Promise<any> {
    const url = `${this.baseURL}${path}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData: any = await response.json().catch(() => ({}));
        const error: any = new Error(errorData.error || response.statusText);
        error.status = response.status;
        throw error;
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);

      if (error.name === "AbortError") {
        const timeoutError: any = new Error("Gateway timeout");
        timeoutError.status = 504;
        throw timeoutError;
      }

      if (error.cause?.code === "ECONNREFUSED") {
        const connError: any = new Error("Python backend service unavailable");
        connError.status = 503;
        throw connError;
      }

      throw error;
    }
  }

  public async delete(path: string): Promise<any> {
    const url = `${this.baseURL}${path}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        method: "DELETE",
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorData: any = await response.json().catch(() => ({}));
        const error: any = new Error(errorData.error || response.statusText);
        error.status = response.status;
        throw error;
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);

      if (error.name === "AbortError") {
        const timeoutError: any = new Error("Gateway timeout");
        timeoutError.status = 504;
        throw timeoutError;
      }

      if (error.cause?.code === "ECONNREFUSED") {
        const connError: any = new Error("Python backend service unavailable");
        connError.status = 503;
        throw connError;
      }

      throw error;
    }
  }

  public async healthCheck(): Promise<boolean> {
    try {
      await this.get("/health");
      return true;
    } catch (error) {
      return false;
    }
  }
}
