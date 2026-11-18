/**
 * v2 → dh 唤醒桥：鉴权、有界读取、持久幂等、快速入队。
 *
 * 同一 event_id 重试只入队一次；投递失败会释放 pending，允许真正重试。
 * completed 默认保留 24h，pending 崩溃后 60s 可恢复，避免重启把旧事件再次当新事件。
 */
import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { Context } from '@deepseek-ai/cordis';

const DEFAULT_MAX_BODY_BYTES = 256 * 1024;
const DEFAULT_DEDUP_TTL_MS = 24 * 60 * 60 * 1000;
const DEFAULT_PENDING_TTL_MS = 60 * 1000;
const DEFAULT_DEDUP_CAPACITY = 4096;

interface WakeBody {
  event?: unknown;
  event_id?: unknown;
  data?: unknown;
  timestamp?: unknown;
}

export type WakeDeliver = (event: string, data: unknown, timestamp?: string) => Promise<void>;

export interface RegisterWakeWebhookOptions {
  token?: string;
  maxBodyBytes?: number;
  deliver: WakeDeliver;
  /** 持久化幂等台账；不传仅进程内去重（单测/嵌入场景）。 */
  dedupPath?: string;
  dedupTtlMs?: number;
  pendingTtlMs?: number;
  dedupCapacity?: number;
}

class WakeHttpError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

type DedupEntry = { state: 'pending' | 'completed'; updatedAt: number };

/** 小型原子 JSON 台账。损坏/写入失败必须显式 503，不能静默退化成无幂等。 */
export class WakeDedupStore {
  private entries = new Map<string, DedupEntry>();
  private readonly loadError?: Error;

  constructor(
    private readonly filePath = '',
    private readonly completedTtlMs = DEFAULT_DEDUP_TTL_MS,
    private readonly pendingTtlMs = DEFAULT_PENDING_TTL_MS,
    private readonly capacity = DEFAULT_DEDUP_CAPACITY,
  ) {
    if (!filePath || !existsSync(filePath)) return;
    try {
      const raw = JSON.parse(readFileSync(filePath, 'utf-8'));
      const values = raw?.entries;
      if (values && typeof values === 'object' && !Array.isArray(values)) {
        for (const [id, value] of Object.entries(values) as Array<[string, any]>) {
          if ((value?.state === 'pending' || value?.state === 'completed')
              && Number.isFinite(value?.updatedAt)) {
            this.entries.set(id, { state: value.state, updatedAt: Number(value.updatedAt) });
          }
        }
      }
    } catch (error) {
      this.loadError = error as Error;
    }
  }

  reserve(id: string, now = Date.now()): boolean {
    this.assertHealthy();
    this.prune(now);
    const old = this.entries.get(id);
    if (old) {
      const ttl = old.state === 'completed' ? this.completedTtlMs : this.pendingTtlMs;
      if (now - old.updatedAt < ttl) return false;
    }
    this.entries.set(id, { state: 'pending', updatedAt: now });
    this.persist();
    return true;
  }

  complete(id: string, now = Date.now()): void {
    this.assertHealthy();
    this.entries.set(id, { state: 'completed', updatedAt: now });
    this.prune(now);
    this.persist();
  }

  release(id: string): void {
    this.assertHealthy();
    if (this.entries.get(id)?.state === 'pending') {
      this.entries.delete(id);
      this.persist();
    }
  }

  private assertHealthy(): void {
    if (this.loadError) throw new WakeHttpError(503, `wake dedup store is unavailable: ${this.loadError.message}`);
  }

  private prune(now: number): void {
    for (const [id, entry] of this.entries) {
      const ttl = entry.state === 'completed' ? this.completedTtlMs : this.pendingTtlMs;
      if (now - entry.updatedAt >= ttl) this.entries.delete(id);
    }
    while (this.entries.size >= this.capacity) {
      const oldest = [...this.entries.entries()]
        .sort((a, b) => a[1].updatedAt - b[1].updatedAt)[0]?.[0];
      if (!oldest) break;
      this.entries.delete(oldest);
    }
  }

  private persist(): void {
    if (!this.filePath) return;
    try {
      mkdirSync(dirname(this.filePath), { recursive: true });
      const temp = `${this.filePath}.${process.pid}.tmp`;
      const body = JSON.stringify({ version: 1, entries: Object.fromEntries(this.entries) });
      writeFileSync(temp, body, { encoding: 'utf-8', mode: 0o600 });
      renameSync(temp, this.filePath);
    } catch (error) {
      throw new WakeHttpError(503, `wake dedup store write failed: ${(error as Error).message}`);
    }
  }
}

function respondJson(response: any, status: number, body: Record<string, unknown>): void {
  response.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(body));
}

function isJsonContentType(value: string | undefined): boolean {
  if (value === undefined) return false;
  const [mediaType, parameter, ...extra] = value.split(';').map((p) => p.trim());
  if (mediaType?.toLowerCase() !== 'application/json') return false;
  if (parameter === undefined) return true;
  return extra.length === 0 && /^charset=(?:utf-8|"utf-8")$/i.test(parameter);
}

async function readBoundedBody(request: any, maxBytes: number): Promise<string> {
  const declared = Number(request.headers['content-length']);
  if (Number.isFinite(declared) && declared > maxBytes) {
    request.resume();
    throw new WakeHttpError(413, 'request body is too large');
  }
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const raw of request) {
    const chunk = Buffer.isBuffer(raw) ? raw : Buffer.from(raw);
    size += chunk.byteLength;
    if (size > maxBytes) {
      request.resume();
      throw new WakeHttpError(413, 'request body is too large');
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf-8');
}

function assertToken(request: any, expected: string | undefined): void {
  if (!expected) return;
  const given = request.headers['x-wake-token'];
  if (typeof given !== 'string' || given.length !== expected.length) {
    throw new WakeHttpError(401, 'invalid wake token');
  }
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= given.charCodeAt(i) ^ expected.charCodeAt(i);
  if (diff !== 0) throw new WakeHttpError(401, 'invalid wake token');
}

function parseWakeBody(body: string): WakeBody {
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    throw new WakeHttpError(400, 'request body is not valid JSON');
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new WakeHttpError(400, 'wake body must be a JSON object');
  }
  const wake = parsed as WakeBody;
  if (typeof wake.event !== 'string' || wake.event.trim() === '') {
    throw new WakeHttpError(400, 'wake body requires a non-empty string field "event"');
  }
  return wake;
}

function resolveEventId(request: any, wake: WakeBody): string {
  const header = request.headers['idempotency-key'] ?? request.headers['x-wake-event-id'];
  let value = wake.event_id ?? header;
  if (value === undefined) {
    const data = (wake.data && typeof wake.data === 'object' && !Array.isArray(wake.data))
      ? wake.data as Record<string, any> : {};
    const triggerIds = Array.isArray(data.trigger_ids) ? data.trigger_ids : [];
    if (data.trigger_id !== undefined) triggerIds.push(data.trigger_id);
    if (triggerIds.length > 0) {
      value = `${wake.event}:${[...new Set(triggerIds.map(String))].sort().join(',')}`;
    } else if (String(wake.event).startsWith('watch_')) {
      throw new WakeHttpError(400, 'watch wake requires event_id or stable trigger_ids');
    } else {
      value = `sha256:${createHash('sha256')
        .update(`${String(wake.event)}:${JSON.stringify(data)}`).digest('hex')}`;
    }
  }
  if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9:_.=-]{0,255}$/.test(value)) {
    throw new WakeHttpError(400, 'event_id must be 1-256 safe ASCII characters');
  }
  // 把可读但不固定长度的业务身份收敛成固定键，避免长 trigger_ids 占用台账。
  if (value.length > 80) return `sha256:${createHash('sha256').update(value).digest('hex')}`;
  return value;
}

function createWakeHandler(deliver: WakeDeliver, token: string | undefined,
                           maxBodyBytes: number, dedup: WakeDedupStore) {
  return async (request: any, response: any): Promise<void> => {
    let reservedId = '';
    try {
      if (request.method !== 'POST') {
        response.setHeader('allow', 'POST');
        throw new WakeHttpError(405, 'method not allowed');
      }
      if (!isJsonContentType(request.headers['content-type'])) {
        throw new WakeHttpError(415, 'content type must be application/json');
      }
      const body = await readBoundedBody(request, maxBodyBytes);
      assertToken(request, token);
      const wake = parseWakeBody(body);
      const eventId = resolveEventId(request, wake);
      if (!dedup.reserve(eventId)) {
        respondJson(response, 200, { success: true, deduplicated: true, event_id: eventId });
        return;
      }
      reservedId = eventId;
      try {
        await deliver(wake.event as string, wake.data,
          typeof wake.timestamp === 'string' ? wake.timestamp : undefined);
        dedup.complete(eventId);
        respondJson(response, 200, { success: true, event_id: eventId });
      } catch (err: any) {
        dedup.release(eventId);
        reservedId = '';
        console.warn(`[wake] deliver failed for event ${wake.event}: ${err?.message ?? err}`);
        respondJson(response, 200, { success: false, error: 'deliver failed', event_id: eventId });
      }
    } catch (error) {
      if (reservedId) {
        try { dedup.release(reservedId); } catch { /* 原始错误优先，绝不吞掉响应 */ }
      }
      if (error instanceof WakeHttpError) {
        respondJson(response, error.status, { success: false, error: error.message });
        return;
      }
      console.warn('[wake] request failed:', error);
      respondJson(response, 503, { success: false, error: 'wake ingress is unavailable' });
    }
  };
}

export function registerWakeWebhook(ctx: Context, options: RegisterWakeWebhookOptions): void {
  const token = options.token;
  const maxBodyBytes = options.maxBodyBytes ?? DEFAULT_MAX_BODY_BYTES;
  const deliver = options.deliver;
  const dedup = new WakeDedupStore(
    options.dedupPath ?? '', options.dedupTtlMs, options.pendingTtlMs, options.dedupCapacity,
  );
  (ctx as any).inject?.(['webServer'], (webCtx: any) => {
    const route = {
      kind: 'exact',
      path: '/wake',
      handler: createWakeHandler(deliver, token, maxBodyBytes, dedup),
    };
    webCtx.effect(() => webCtx.webServer.register(route), 'lifecycle: /wake');
  });
}
