/**
 * HTTP client for communicating with Python Flask backend
 * Singleton pattern ensures single instance across application
 */
export class PythonBackendClient {
  private static instance: PythonBackendClient;
  private baseURL: string;
  private timeout: number;

  private constructor() {
    this.baseURL = process.env.PYTHON_BACKEND_URL || "http://localhost:5000";
    this.timeout = parseInt(process.env.PYTHON_BACKEND_TIMEOUT || "30000", 10);
  }

  /**
   * Get singleton instance
   */
  public static getInstance(): PythonBackendClient {
    if (!PythonBackendClient.instance) {
      PythonBackendClient.instance = new PythonBackendClient();
    }
    return PythonBackendClient.instance;
  }

  /**
   * Make GET request with optional query parameters
   */
  public async get<T = any>(path: string, params?: Record<string, any>): Promise<T> {
    const url = this.buildURL(path, params);
    return this.request<T>(url, { method: "GET" });
  }

  /**
   * Make POST request with body
   */
  public async post<T = any>(path: string, body: any): Promise<T> {
    const url = this.buildURL(path);
    return this.request<T>(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  /**
   * Make PUT request with body
   */
  public async put<T = any>(path: string, body: any): Promise<T> {
    const url = this.buildURL(path);
    return this.request<T>(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  /**
   * Make DELETE request
   */
  public async delete<T = any>(path: string): Promise<T> {
    const url = this.buildURL(path);
    return this.request<T>(url, { method: "DELETE" });
  }

  /**
   * Check if Python backend is healthy
   * Returns true if healthy, false otherwise (does not throw)
   */
  public async healthCheck(): Promise<boolean> {
    try {
      await this.get("/health");
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Build full URL with query parameters
   */
  private buildURL(path: string, params?: Record<string, any>): string {
    const url = `${this.baseURL}${path}`;
    if (!params || Object.keys(params).length === 0) {
      return url;
    }

    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      searchParams.append(key, String(value));
    }

    return `${url}?${searchParams.toString()}`;
  }

  /**
   * Make HTTP request with timeout and error handling
   */
  private async request<T>(url: string, options: RequestInit): Promise<T> {
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

      return (await response.json()) as T;
    } catch (error: any) {
      clearTimeout(timeoutId);

      // Handle timeout
      if (error.name === "AbortError") {
        const timeoutError: any = new Error("Gateway timeout");
        timeoutError.status = 504;
        throw timeoutError;
      }

      // Handle connection refused
      if (error.cause?.code === "ECONNREFUSED") {
        const connError: any = new Error("Python backend service unavailable");
        connError.status = 503;
        throw connError;
      }

      // Re-throw HTTP errors with status
      throw error;
    }
  }
}
