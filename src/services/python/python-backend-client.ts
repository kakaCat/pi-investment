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
    const url = this.buildURL(path, params);
    return this.request(url, { method: "GET" });
  }

  public async post(path: string, body: any): Promise<any> {
    const url = this.buildURL(path);
    return this.request(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  public async put(path: string, body: any): Promise<any> {
    const url = this.buildURL(path);
    return this.request(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  public async delete(path: string): Promise<any> {
    const url = this.buildURL(path);
    return this.request(url, { method: "DELETE" });
  }

  public async healthCheck(): Promise<boolean> {
    try {
      await this.get("/health");
      return true;
    } catch (error) {
      return false;
    }
  }

  private buildURL(path: string, params?: Record<string, any>): string {
    let url = `${this.baseURL}${path}`;
    if (params && Object.keys(params).length > 0) {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
        searchParams.append(key, String(value));
      }
      url = `${url}?${searchParams.toString()}`;
    }
    return url;
  }

  private async request(url: string, options: RequestInit): Promise<any> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url, {
        ...options,
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
}

