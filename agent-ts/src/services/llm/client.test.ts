import { describe, it, expect } from '@jest/globals';
import { complete } from './client.js';
import { LLMError, type LLMModelConfig } from './types.js';

const baseConfig: LLMModelConfig = {
  provider: 'deepseek',
  modelId: 'deepseek-v4-flash',
  displayName: 'DeepSeek Chat',
  baseUrl: 'https://api.deepseek.com/v1',
  apiKey: 'test-key',
  contextWindow: 128000,
  maxTokens: 8000,
  reasoning: true,
  timeoutMs: 120000,
  maxRetries: 2,
};

const noSleep = () => Promise.resolve();
const req = { messages: [{ role: 'user' as const, content: 'hi' }] };

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('complete', () => {
  it('成功：映射 text/usage/model，请求体符合 OpenAI 格式', async () => {
    let captured: { url: string; init: RequestInit } | null = null;
    const fetchImpl = async (url: any, init: any) => {
      captured = { url: String(url), init };
      return jsonResponse(200, {
        model: 'deepseek-v4-flash',
        choices: [{ message: { role: 'assistant', content: '你好' } }],
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      });
    };
    const r = await complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep });
    expect(r.text).toBe('你好');
    expect(r.usage).toEqual({ input: 10, output: 5, totalTokens: 15 });
    expect(r.model).toBe('deepseek-v4-flash');
    expect(captured!.url).toBe('https://api.deepseek.com/v1/chat/completions');
    const body = JSON.parse(String(captured!.init.body));
    expect(body.model).toBe('deepseek-v4-flash');
    expect(body.messages).toEqual([{ role: 'user', content: 'hi' }]);
    expect((captured!.init.headers as any).Authorization).toBe('Bearer test-key');
  });

  it('401 → LLMError auth 不可重试（fetch 只调一次）', async () => {
    let calls = 0;
    const fetchImpl = async () => { calls++; return jsonResponse(401, { error: 'bad key' }); };
    await expect(complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep }))
      .rejects.toMatchObject({ kind: 'auth', retryable: false });
    expect(calls).toBe(1);
  });

  it('429 overloaded → kind=overloaded，重试后成功', async () => {
    let calls = 0;
    const fetchImpl = async () => {
      calls++;
      if (calls === 1) return new Response('429 The engine is currently overloaded', { status: 429 });
      return jsonResponse(200, { choices: [{ message: { content: 'ok' } }], usage: {} });
    };
    const r = await complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep });
    expect(r.text).toBe('ok');
    expect(calls).toBe(2);
  });

  it('500 持续失败 → 重试 5 次后抛 overloaded', async () => {
    let calls = 0;
    const fetchImpl = async () => { calls++; return jsonResponse(500, 'server error'); };
    await expect(complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep }))
      .rejects.toMatchObject({ kind: 'overloaded', retryable: true });
    expect(calls).toBe(6); // 1 + 5 retries
  });

  it('fetch 抛 AbortError → kind=timeout 可重试', async () => {
    const fetchImpl = async () => { throw new DOMException('aborted', 'AbortError'); };
    await expect(complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep }))
      .rejects.toMatchObject({ kind: 'timeout', retryable: true });
  });

  it('400 → invalid_request 不重试', async () => {
    let calls = 0;
    const fetchImpl = async () => { calls++; return jsonResponse(400, 'bad request'); };
    await expect(complete(baseConfig, req, { fetchImpl: fetchImpl as any, sleep: noSleep }))
      .rejects.toBeInstanceOf(LLMError);
    expect(calls).toBe(1);
  });
});
