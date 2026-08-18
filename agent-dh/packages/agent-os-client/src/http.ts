import axios, { AxiosInstance } from 'axios';
import axiosRetry from 'axios-retry';
import type { RegistryClientConfig } from './types.js';

/**
 * Shared HTTP client factory: axios + exponential-backoff retry,
 * identical behavior to RegistryClient so every sub-client fails
 * the same way (network errors and 5xx are retried up to 3 times).
 */
export function createHttpClient(config: RegistryClientConfig): AxiosInstance {
  const client = axios.create({
    baseURL: config.baseURL,
    timeout: config.timeout || 30000,
    headers: {
      'Content-Type': 'application/json',
      ...config.headers,
    },
  });

  axiosRetry(client, {
    retries: 3,
    retryDelay: axiosRetry.exponentialDelay,
    retryCondition: (error) => {
      return (
        axiosRetry.isNetworkOrIdempotentRequestError(error) ||
        (error.response?.status ? error.response.status >= 500 : false)
      );
    },
    onRetry: (retryCount, error, requestConfig) => {
      console.log(
        `[AgentOSClient] Retrying request (${retryCount}/3): ${requestConfig.method?.toUpperCase()} ${requestConfig.url}`
      );
    },
  });

  return client;
}
