/**
 * v2 → dh 唤醒桥（路 2：自写 webhook 路由，2026-09-02 死链修复）
 *
 * 断链背景：quantsys-v2 的 AgentNotificationService 把事件 POST 到
 * AGENT_API_URL/wake（v2 .env 曾指向 gateway 3002）。2026-09-01 起 AGENT_API_URL
 * 改指 dh 13080，但 dh 侧此前无 /wake 路由 → 404 断链（watch 触发/定时提醒
 * 全部静默丢失）。本模块在 webServer 注册 exact /wake 路由补上这一环。
 *
 * 协议契约（与 v2 application/services/agent_notification_service.py 对齐，Python 零改动）：
 *   POST /wake
 *   Content-Type: application/json
 *   body: { "event": string, "data": object, "timestamp": ISO string }
 *   header: X-Wake-Token（可选；本侧配置了 token 才校验）
 *   期望响应: 200 {"success": true}
 *     - success=false 或非 200 → v2 记为 error 并重试
 *     - 请求超时 → v2 视为"已送达不重试"（因此本 handler 立即响应，不等 LLM）
 *
 * 实现参照官方 @deepseek-ai/dsh-webhook-github（exact 路由 + fire-and-forget），
 * 但投递不走 webhookRuntime，而是由 lifecycle 的 deliver 回调直投 investor 窗口。
 */

import { Context } from '@deepseek-ai/cordis';

const DEFAULT_MAX_BODY_BYTES = 256 * 1024;

/** v2 事件 payload 的结构（只取本侧需要的字段） */
interface WakeBody {
  event?: unknown;
  data?: unknown;
  timestamp?: unknown;
}

/** 投递回调：把 v2 事件交给 lifecycle 处理（找 investor 窗口投递） */
export type WakeDeliver = (event: string, data: unknown, timestamp?: string) => Promise<void>;

export interface RegisterWakeWebhookOptions {
  /** 可选：配置后校验 X-Wake-Token 必须匹配（与 v2 AGENT_API_TOKEN 同值） */
  token?: string;
  /** body 大小上限，默认 256KiB */
  maxBodyBytes?: number;
  /** 事件投递回调（由 lifecycle 注入） */
  deliver: WakeDeliver;
}

/** HTTP 错误：status + message，映射为 JSON 响应 */
class WakeHttpError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
  }
}

/** 发送 JSON 响应（成功：{success:true}；失败：{success:false,error}） */
function respondJson(response: any, status: number, body: Record<string, unknown>): void {
  response.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
  response.end(JSON.stringify(body));
}

/** 校验 Content-Type 为 application/json（至多一个 utf-8 charset 参数） */
function isJsonContentType(value: string | undefined): boolean {
  if (value === undefined) return false;
  const [mediaType, parameter, ...extra] = value.split(';').map((p) => p.trim());
  if (mediaType?.toLowerCase() !== 'application/json') return false;
  if (parameter === undefined) return true;
  return extra.length === 0 && /^charset=(?:utf-8|"utf-8")$/i.test(parameter);
}

/** 有界读取请求体（原生 Node req 无内置 body 解析，须手动 collect chunks） */
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

/** 校验 X-Wake-Token：本侧配置了 token 时，header 必须匹配（constant-time 比较） */
function assertToken(request: any, expected: string | undefined): void {
  if (!expected) return; // 未配置 → 不校验（与 v2 未配 AGENT_API_TOKEN 时的行为对齐）
  const given = request.headers['x-wake-token'];
  if (typeof given !== 'string' || given.length !== expected.length) {
    throw new WakeHttpError(401, 'invalid wake token');
  }
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= given.charCodeAt(i) ^ expected.charCodeAt(i);
  if (diff !== 0) throw new WakeHttpError(401, 'invalid wake token');
}

/** 解析并校验 v2 事件 body */
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

/** 创建 /wake exact 路由的 HTTP handler */
function createWakeHandler(deliver: WakeDeliver, token: string | undefined, maxBodyBytes: number) {
  return async (request: any, response: any): Promise<void> => {
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
      // deliver 只做消息入队（followup 立即返回），不等 LLM 处理 → v2 30s 超时内必响应。
      // 投递失败 → success:false，v2 记 error 并重试（与 notifier 重试语义一致）。
      try {
        await deliver(wake.event as string, wake.data, typeof wake.timestamp === 'string' ? wake.timestamp : undefined);
        respondJson(response, 200, { success: true });
      } catch (err: any) {
        console.warn(`[wake] deliver failed for event ${wake.event}: ${err?.message ?? err}`);
        respondJson(response, 200, { success: false, error: 'deliver failed' });
      }
    } catch (error) {
      if (error instanceof WakeHttpError) {
        respondJson(response, error.status, { success: false, error: error.message });
        return;
      }
      console.warn('[wake] request failed:', error);
      respondJson(response, 503, { success: false, error: 'wake ingress is unavailable' });
    }
  };
}

/**
 * 在 webServer 上注册 exact /wake 路由。
 * 用 ctx.inject(['webServer'], ...) 惰性注入（参照官方 dsh-api-gateway）——
 * webServer 服务就绪前不阻塞 lifecycle 启动。
 */
export function registerWakeWebhook(ctx: Context, options: RegisterWakeWebhookOptions): void {
  const token = options.token;
  const maxBodyBytes = options.maxBodyBytes ?? DEFAULT_MAX_BODY_BYTES;
  const deliver = options.deliver;
  (ctx as any).inject?.(['webServer'], (webCtx: any) => {
    const route = {
      kind: 'exact',
      path: '/wake',
      handler: createWakeHandler(deliver, token, maxBodyBytes),
    };
    webCtx.effect(() => webCtx.webServer.register(route), 'lifecycle: /wake');
  });
}
