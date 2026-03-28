/**
 * HTTP client with GBK support for Sina/Eastmoney APIs
 */
import { chinaDate, chinaDateTime } from "../../utils/china-time.js";

const HEADERS = {
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
  "Accept": "*/*",
  "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
  "Referer": "https://finance.sina.com.cn/",
  "Cache-Control": "no-cache",
};

export async function fetchGbk(url: string, timeoutMs = 10000): Promise<string> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { headers: HEADERS, signal: ctrl.signal });
    const buf = await resp.arrayBuffer();
    // Node.js 22 supports GBK via full ICU; falls back gracefully on systems without it
    try {
      return new TextDecoder("gbk").decode(buf);
    } catch {
      // Fallback: latin1 → works for ASCII content, numbers will still parse
      return new TextDecoder("latin1").decode(buf);
    }
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchJson<T = unknown>(
  url: string,
  params?: Record<string, string>,
  timeoutMs = 10000,
): Promise<T> {
  const urlObj = new URL(url);
  if (params) {
    for (const [k, v] of Object.entries(params)) urlObj.searchParams.set(k, v);
  }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const resp = await fetch(urlObj.toString(), { headers: HEADERS, signal: ctrl.signal });
    return (await resp.json()) as T;
  } finally {
    clearTimeout(timer);
  }
}

export async function withRetry<T>(fn: () => Promise<T>, retries = 3, delayMs = 1000): Promise<T> {
  let lastErr: unknown;
  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      if (i < retries - 1) await new Promise(r => setTimeout(r, delayMs));
    }
  }
  throw lastErr;
}

export function safeFloat(v: unknown, decimals = 2): number {
  const n = parseFloat(String(v ?? 0));
  if (!isFinite(n)) return 0;
  const factor = Math.pow(10, decimals);
  return Math.round(n * factor) / factor;
}

export function today(): string {
  return chinaDate();
}

export function nowStr(): string {
  return chinaDateTime();
}
