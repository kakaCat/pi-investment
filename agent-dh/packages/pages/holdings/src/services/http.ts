// 轻量自包含 HTTP 客户端（页面聚合层只读、端点固定，约 10 个）
// 设计文档 §3：不依赖 @pi-investment/quantsys-v2-client（axios 重试放大延迟 + 语义不同）
// §4.2 信封实测（2026-09-03）：
//   - /api/health, /api/health/db, os /health, /api/memory/search → 裸对象（无 success/data）
//   - /api/health/platform/status, /api/market/perception/regime → {success,data:...}
//   - /api/scheduler/tasks, /api/scheduler/runs, /api/market/perception/themes → {success, tasks|runs|themes...}（无 data 键）
// 因此本模块只做 raw fetchJson（校验 HTTP 状态 + success===false 显式抛错），pluck 由调用点按端点契约做。

export class HttpError extends Error {
  constructor(message: string, readonly status?: number, readonly causeInfo?: unknown) {
    super(message);
    this.name = 'HttpError';
  }
}

export interface FetchJsonOptions {
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT = 4000;

/**
 * GET 请求并解析 JSON。
 * - 非 2xx → HttpError（含状态码；ECONNREFUSED 包装为"连接被拒绝"中文文案）
 * - 超时 → HttpError（AbortController，默认 4s）
 * - body 含 {success:false,error} → HttpError（信封显式失败）
 * 其余原样返回整个 JSON 对象，由调用点按端点契约 pluck（绝不做统一 unwrap）。
 */
export async function fetchJson<T = Record<string, unknown>>(
  url: string,
  options: FetchJsonOptions = {}
): Promise<T> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(url, { signal: controller.signal, headers: { accept: 'application/json' } });
  } catch (err: unknown) {
    const e = err as { name?: string; message?: string; cause?: { code?: string } };
    if (e?.name === 'AbortError') {
      throw new HttpError(`请求超时(>${timeoutMs}ms): ${url}`);
    }
    const code = (e as { cause?: { code?: string } })?.cause?.code ?? (e as { code?: string })?.code;
    if (code === 'ECONNREFUSED') throw new HttpError(`连接被拒绝(ECONNREFUSED): ${url}`);
    throw new HttpError(`请求失败: ${e?.message ?? String(err)}`);
  } finally {
    clearTimeout(timer);
  }

  const text = await res.text();
  let json: unknown = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    throw new HttpError(`响应非 JSON(status=${res.status}): ${url} (body 前 200 字: ${text.slice(0, 200)})`, res.status);
  }

  if (!res.ok) {
    throw new HttpError(`HTTP ${res.status}: ${url}`, res.status, json);
  }
  const record = json as Record<string, unknown>;
  if (record && typeof record === 'object' && record.success === false) {
    const msg = typeof record.error === 'string' ? record.error : '未知错误';
    throw new HttpError(`接口返回失败: ${msg} (${url})`, res.status, json);
  }
  return json as T;
}

/** 便捷：请求 {success,data} 信封端点，取 data；非信封端点请直接用 fetchJson */
export async function fetchData<T>(url: string, options?: FetchJsonOptions): Promise<T> {
  const json = await fetchJson<{ success?: boolean; data?: T }>(url, options);
  return json?.data as T;
}

/** 便捷：请求裸对象端点（health 等） */
export async function fetchBare<T>(url: string, options?: FetchJsonOptions): Promise<T> {
  return fetchJson<T>(url, options);
}
