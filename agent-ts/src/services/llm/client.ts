/**
 * 自有 LLM 客户端：complete() 直走 OpenAI 兼容 HTTP。
 * 错误归一化为 LLMError，调用方不感知 provider/SDK 特有错误。
 * 重试策略沿用 .pi/settings.json：最多 5 次重试，间隔 3s（仅 retryable 错误）。
 */
import { LLMError, type ChatRequest, type ChatResponse, type LLMModelConfig } from './types.js';

const MAX_RETRIES = 5;
const RETRY_DELAY_MS = 3000;

export interface ClientDeps {
  fetchImpl?: typeof fetch;
  sleep?: (ms: number) => Promise<void>;
}

export async function complete(
  config: LLMModelConfig,
  req: ChatRequest,
  deps: ClientDeps = {},
): Promise<ChatResponse> {
  const sleep = deps.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  let lastErr: LLMError | null = null;
  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    try {
      return await completeOnce(config, req, deps.fetchImpl ?? fetch);
    } catch (e) {
      const err = e instanceof LLMError ? e : new LLMError(String(e), 'unknown', false);
      if (!err.retryable || attempt === MAX_RETRIES) throw err;
      lastErr = err;
      await sleep(RETRY_DELAY_MS);
    }
  }
  throw lastErr ?? new LLMError('unreachable', 'unknown', false);
}

async function completeOnce(
  config: LLMModelConfig,
  req: ChatRequest,
  fetchImpl: typeof fetch,
): Promise<ChatResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), config.timeoutMs);
  try {
    const res = await fetchImpl(`${config.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${config.apiKey}`,
      },
      body: JSON.stringify({
        model: config.modelId,
        messages: req.messages,
        max_tokens: req.maxTokens ?? config.maxTokens,
        ...(req.temperature !== undefined ? { temperature: req.temperature } : {}),
        stream: false,
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw await toLLMError(res);
    const data = (await res.json()) as any;
    const message = data.choices?.[0]?.message ?? {};
    const usage = data.usage ?? {};
    return {
      text: typeof message.content === 'string' ? message.content : '',
      model: data.model ?? config.modelId,
      usage: {
        input: usage.prompt_tokens ?? 0,
        output: usage.completion_tokens ?? 0,
        totalTokens: usage.total_tokens ?? 0,
      },
    };
  } catch (e) {
    if (e instanceof LLMError) throw e;
    if ((e as Error).name === 'AbortError') {
      throw new LLMError(`请求超时（${config.timeoutMs}ms）`, 'timeout', true);
    }
    throw new LLMError(`网络错误: ${(e as Error).message}`, 'unknown', true);
  } finally {
    clearTimeout(timer);
  }
}

async function toLLMError(res: Response): Promise<LLMError> {
  const body = await res.text().catch(() => '');
  if (res.status === 401 || res.status === 403) {
    return new LLMError(`认证失败 (${res.status}): ${body}`, 'auth', false);
  }
  if (res.status === 429) {
    const overloaded = /overloaded/i.test(body);
    return new LLMError(
      `限流/过载 (429): ${body}`,
      overloaded ? 'overloaded' : 'rate_limit',
      true,
    );
  }
  if (res.status === 400) return new LLMError(`请求无效 (400): ${body}`, 'invalid_request', false);
  if (res.status >= 500) return new LLMError(`服务端错误 (${res.status}): ${body}`, 'overloaded', true);
  return new LLMError(`HTTP ${res.status}: ${body}`, 'unknown', false);
}
