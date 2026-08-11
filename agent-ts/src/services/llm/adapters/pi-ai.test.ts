import { describe, it, expect, afterEach } from '@jest/globals';
import type { LLMModelConfig } from '../types.js';
import { toSDKModel } from './pi-ai.js';

const kimiConfig: LLMModelConfig = {
  provider: 'kimi',
  modelId: 'kimi-k3',
  displayName: 'Kimi (Moonshot)',
  baseUrl: 'https://api.kimi.com/coding/v1',
  apiKey: 'kimi-key',
  contextWindow: 256000,
  maxTokens: 8000,
  reasoning: true,
  compat: { supportsDeveloperRole: false, supportsStore: false, maxTokensField: 'max_tokens' },
  timeoutMs: 120000,
  maxRetries: 2,
};

const dsConfig: LLMModelConfig = {
  provider: 'deepseek',
  modelId: 'deepseek-v4-flash',
  displayName: 'DeepSeek Chat',
  baseUrl: 'https://api.deepseek.com/v1',
  apiKey: 'ds-key',
  contextWindow: 128000,
  maxTokens: 8000,
  reasoning: true,
  timeoutMs: 120000,
  maxRetries: 2,
};

const savedOpenAIKey = process.env.OPENAI_API_KEY;
afterEach(() => {
  if (savedOpenAIKey === undefined) delete process.env.OPENAI_API_KEY;
  else process.env.OPENAI_API_KEY = savedOpenAIKey;
});

describe('toSDKModel', () => {
  it('kimi compat 透传锁死（两次 tokenization failed 事故回归）', () => {
    const m = toSDKModel(kimiConfig) as any;
    expect(m.id).toBe('kimi-k3');
    expect(m.baseUrl).toBe('https://api.kimi.com/coding/v1');
    expect(m.compat).toEqual({ supportsDeveloperRole: false, supportsStore: false, maxTokensField: 'max_tokens' });
  });

  it('deepseek 无 compat 覆盖（依赖 SDK 自动检测）', () => {
    const m = toSDKModel(dsConfig) as any;
    expect(m.compat).toBeUndefined();
    expect(m.provider).toBe('openai');
    expect(m.api).toBe('openai-completions');
  });

  it('副作用：同步 OPENAI_API_KEY 为当前 provider 的 key（SDK 只认该变量）', () => {
    toSDKModel(kimiConfig);
    expect(process.env.OPENAI_API_KEY).toBe('kimi-key');
    toSDKModel(dsConfig);
    expect(process.env.OPENAI_API_KEY).toBe('ds-key');
  });
});
