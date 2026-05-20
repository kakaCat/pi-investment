export class QuantPythonApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly details?: unknown
  ) {
    super(message);
    this.name = 'QuantPythonApiError';
  }
}

export function getQuantPythonApiBaseUrl(): string {
  return (process.env.QUANT_PY_API_BASE_URL ?? 'http://127.0.0.1:5001').replace(/\/+$/, '');
}

export async function requestQuantPythonApi<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const url = `${getQuantPythonApiBaseUrl()}${path.startsWith('/') ? path : `/${path}`}`;
  const response = await fetch(url, init);
  const contentType = response.headers.get('content-type') ?? '';
  const payload = contentType.includes('application/json')
    ? await response.json() as unknown
    : await response.text();

  if (!response.ok) {
    const message = typeof payload === 'object' && payload !== null && 'error' in payload
      ? String((payload as { error: unknown }).error)
      : `Python quant API request failed with status ${response.status}`;
    throw new QuantPythonApiError(message, response.status, payload);
  }

  return payload as T;
}
