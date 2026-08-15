import axios, { AxiosInstance, AxiosError } from 'axios';

/**
 * Agent OS Client Configuration
 */
export interface AgentOSConfig {
  /** Base URL of Agent OS API (e.g., http://localhost:8080) */
  baseURL: string;
  /** Agent ID for authentication */
  agentId?: string;
  /** API Key for authentication */
  apiKey?: string;
  /** Request timeout in milliseconds (default: 30000) */
  timeout?: number;
}

/**
 * Standard API Response Envelope
 */
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  metadata?: {
    timestamp: string;
    latency_ms?: number;
  };
}

/**
 * Agent OS Error
 */
export class AgentOSError extends Error {
  constructor(
    public code: string,
    message: string,
    public details?: any,
    public statusCode?: number
  ) {
    super(message);
    this.name = 'AgentOSError';
  }
}

/**
 * Base HTTP Client for Agent OS API
 */
export class BaseHTTPClient {
  private axios: AxiosInstance;
  private config: AgentOSConfig;

  constructor(config: AgentOSConfig) {
    this.config = config;
    this.axios = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        ...(config.agentId && { 'X-Agent-ID': config.agentId }),
        ...(config.apiKey && { Authorization: `Bearer ${config.apiKey}` }),
      },
    });

    // Response interceptor for error handling
    this.axios.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response) {
          const data = error.response.data as any;
          const apiError = data?.error || {
            code: 'HTTP_ERROR',
            message: error.message,
          };
          throw new AgentOSError(
            apiError.code,
            apiError.message,
            apiError.details,
            error.response.status
          );
        } else if (error.request) {
          throw new AgentOSError(
            'NETWORK_ERROR',
            `Failed to connect to Agent OS at ${this.config.baseURL}`,
            { originalError: error.message }
          );
        } else {
          throw new AgentOSError('UNKNOWN_ERROR', error.message);
        }
      }
    );
  }

  /**
   * GET request
   */
  async get<T>(path: string, params?: any): Promise<T> {
    const response = await this.axios.get<T>(path, { params });
    return response.data;
  }

  /**
   * POST request
   */
  async post<T>(path: string, data?: any): Promise<T> {
    const response = await this.axios.post<T>(path, data);
    return response.data;
  }

  /**
   * PUT request
   */
  async put<T>(path: string, data?: any): Promise<T> {
    const response = await this.axios.put<T>(path, data);
    return response.data;
  }

  /**
   * DELETE request
   */
  async delete<T>(path: string): Promise<T> {
    const response = await this.axios.delete<T>(path);
    return response.data;
  }

  /**
   * Get base URL
   */
  getBaseURL(): string {
    return this.config.baseURL;
  }

  /**
   * Get agent ID
   */
  getAgentId(): string | undefined {
    return this.config.agentId;
  }
}
