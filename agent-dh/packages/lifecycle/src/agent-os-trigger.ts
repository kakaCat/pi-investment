/**
 * Agent OS → dh 定时任务 webhook 驱动（2026-09-04 僵尸 cron 修复）
 *
 * 背景：Agent OS（Go, :8080）的 14 个 dsh-native 定时任务配置了 command=/bin/true
 * （Linux 占位），macOS 无 /bin/true → 每次 Go cron 触发都 fork/exec 失败
 * （僵尸执行）。与此同时 DH lifecycle 的 NativeReminderScheduler 轮询采纳
 * payload.executor='dsh-native' 的任务自行 cron 直投 → 同一批任务"Agent OS 层
 * 全失败 + DH 层自投"的双轨僵尸。
 *
 * 修复方案（用户决策：webhook 驱动 agent 工作）：Agent OS 本身支持 WebhookURL
 * 执行模式（executeWebhook：POST JSON，仅 Content-Type + User-Agent 两个 header，
 * 2xx=成功）。把 14 个任务的 webhook_url 指向本路由，executor 摘除 'dsh-native'：
 *   Agent OS cron → POST /agent-os-trigger（WP-15 契约）→ deliverReminder 直投
 *   investor 窗口 → 任务完成。
 *
 * 协议契约（与 agent-os internal/kernel/scheduler/executor.go buildWebhookPayload 对齐）：
 *   POST /agent-os-trigger
 *   Content-Type: application/json
 *   body: {
 *     "job_id":       task.ID.String(),
 *     "job_name":     task.Name,
 *     "trigger_time": time.Now().UTC().Format(time.RFC3339),
 *     "metadata":     { ...task.Payload, "run_id", "owner", "triggered_by" }
 *   }
 *   期望响应: 200 {"success": true}   ← Agent OS 只看 2xx
 *     - 非 2xx → Agent OS 记 TaskRun 失败并重试（至 MaxRetries）
 *
 * 鉴权：无 token 校验——Agent OS 无法携带自定义 header（executeWebhook 只设
 * Content-Type/User-Agent），且 :8080→:13080 均为本机回环服务。若未来需要，
 * 可升级为 URL 签名/共享 secret query 参数。
 *
 * 实现参照 lifecycle wake-webhook.ts（exact 路由 + fire-and-forget）：
 * deliver 只做消息入队（followup 立即返回），不等 LLM 处理。
 */

import { Context } from '@deepseek-ai/cordis';

const DEFAULT_MAX_BODY_BYTES = 256 * 1024;

/** WP-15 webhook payload 的结构（只取本侧需要的字段） */
interface AgentOsTriggerBody {
  job_id?: unknown;
  job_name?: unknown;
  trigger_time?: unknown;
  metadata?: Record<string, unknown>;
}

/** 投递回调：把 Agent OS 定时任务交给 lifecycle 处理（找 investor 窗口投递） */
export type AgentOsDeliver = (job: {
  jobName: string;
  jobId: string | undefined;
  triggerTime: string | undefined;
  prompt: string | undefined;
  window: string | undefined;
}) => Promise<void>;

export interface RegisterAgentOsTriggerOptions {
  /** body 大小上限，默认 256KiB */
  maxBodyBytes?: number;
  /** 任务投递回调（由 lifecycle 注入） */
  deliver: AgentOsDeliver;
}

/** HTTP 错误：status + message，映射为 JSON 响应 */
class AgentOsHttpError extends Error {
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
    throw new AgentOsHttpError(413, 'request body is too large');
  }
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const raw of request) {
    const chunk = Buffer.isBuffer(raw) ? raw : Buffer.from(raw);
    size += chunk.byteLength;
    if (size > maxBytes) {
      request.resume();
      throw new AgentOsHttpError(413, 'request body is too large');
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf-8');
}

/** 解析并校验 WP-15 webhook body */
function parseAgentOsBody(body: string): AgentOsTriggerBody {
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    throw new AgentOsHttpError(400, 'request body is not valid JSON');
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new AgentOsHttpError(400, 'webhook body must be a JSON object');
  }
  const hook = parsed as AgentOsTriggerBody;
  // job_name 必须有（任务可溯）；job_id/metadata 允许缺省（宽松解析，防旧版调用 400）
  if (typeof hook.job_name !== 'string' || hook.job_name.trim() === '') {
    throw new AgentOsHttpError(400, 'webhook body requires a non-empty string field "job_name"');
  }
  if (hook.metadata !== undefined && (hook.metadata === null || typeof hook.metadata !== 'object' || Array.isArray(hook.metadata))) {
    throw new AgentOsHttpError(400, 'webhook body field "metadata" must be an object when present');
  }
  return hook;
}

/** 创建 /agent-os-trigger exact 路由的 HTTP handler */
function createAgentOsTriggerHandler(deliver: AgentOsDeliver, maxBodyBytes: number) {
  return async (request: any, response: any): Promise<void> => {
    try {
      if (request.method !== 'POST') {
        response.setHeader('allow', 'POST');
        throw new AgentOsHttpError(405, 'method not allowed');
      }
      if (!isJsonContentType(request.headers['content-type'])) {
        throw new AgentOsHttpError(415, 'content type must be application/json');
      }
      const body = await readBoundedBody(request, maxBodyBytes);
      const hook = parseAgentOsBody(body);
      const metadata = hook.metadata ?? {};
      const job = {
        jobName: hook.job_name as string,
        jobId: typeof hook.job_id === 'string' ? hook.job_id : undefined,
        triggerTime: typeof hook.trigger_time === 'string' ? hook.trigger_time : undefined,
        prompt: typeof metadata['prompt'] === 'string' ? metadata['prompt'] : undefined,
        window: typeof metadata['window'] === 'string' ? metadata['window'] : undefined,
      };
      // deliver 只做消息入队（followup 立即返回），不等 LLM 处理 → Agent OS 超时内必响应。
      // 投递失败 → success:false（body 标记），但仍 200（Agent OS 只看状态码，避免无谓重试轰炸）。
      try {
        await deliver(job);
        respondJson(response, 200, { success: true });
      } catch (err: any) {
        console.warn(`[agent-os-trigger] deliver failed for job ${job.jobName}: ${err?.message ?? err}`);
        respondJson(response, 200, { success: false, error: 'deliver failed' });
      }
    } catch (error) {
      if (error instanceof AgentOsHttpError) {
        respondJson(response, error.status, { success: false, error: error.message });
        return;
      }
      console.warn('[agent-os-trigger] request failed:', error);
      respondJson(response, 503, { success: false, error: 'agent-os-trigger ingress is unavailable' });
    }
  };
}

/**
 * 在 webServer 上注册 exact /agent-os-trigger 路由。
 * 用 ctx.inject(['webServer'], ...) 惰性注入（与 wake-webhook 同款）——
 * webServer 服务就绪前不阻塞 lifecycle 启动。
 */
export function registerAgentOsTrigger(ctx: Context, options: RegisterAgentOsTriggerOptions): void {
  const maxBodyBytes = options.maxBodyBytes ?? DEFAULT_MAX_BODY_BYTES;
  const deliver = options.deliver;
  (ctx as any).inject?.(['webServer'], (webCtx: any) => {
    const route = {
      kind: 'exact',
      path: '/agent-os-trigger',
      handler: createAgentOsTriggerHandler(deliver, maxBodyBytes),
    };
    webCtx.effect(() => webCtx.webServer.register(route), 'lifecycle: /agent-os-trigger');
  });
}
