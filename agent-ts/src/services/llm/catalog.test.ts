import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  buildModelConfig,
  envModelId,
  isProviderConfigured,
  resolveModelTarget,
  resolveProvider,
} from './catalog.js';

const ENV_KEYS = [
  'LLM_PROVIDER', 'LLM_API_KEY', 'LLM_BASE_URL', 'LLM_REASONING',
  'LLM_CONTEXT_WINDOW', 'LLM_MAX_TOKENS', 'MODEL_ID',
  'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY',
  'KIMI_BASE_URL', 'KIMI_MODEL_ID', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL_ID',
];
let saved: Record<string, string | undefined>;
beforeEach(() => {
  saved = {};
  for (const k of ENV_KEYS) { saved[k] = process.env[k]; delete process.env[k]; }
});
afterEach(() => {
  for (const k of ENV_KEYS) {
    if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k];
  }
});

describe('resolveProvider 别名', () => {
  it('k3/moonshot 归一为 kimi；deepseek-chat 归一为 deepseek', () => {
    expect(resolveProvider('k3')).toBe('kimi');
    expect(resolveProvider('Moonshot')).toBe('kimi');
    expect(resolveProvider('deepseek-chat')).toBe('deepseek');
    expect(resolveProvider('gpt-5')).toBeNull();
  });
});

describe('resolveModelTarget', () => {
  it('flash/pro 短别名与完整模型 ID', () => {
    expect(resolveModelTarget('flash')).toEqual({ provider: 'deepseek', modelId: 'deepseek-v4-flash' });
    expect(resolveModelTarget('PRO')).toEqual({ provider: 'deepseek', modelId: 'deepseek-v4-pro' });
    expect(resolveModelTarget('kimi-k3')).toEqual({ provider: 'kimi', modelId: 'kimi-k3' });
    expect(resolveModelTarget('deepseek')).toBeNull();
  });
});

describe('buildModelConfig', () => {
  it('kimi compat 锁死：supportsDeveloperRole=false（两次事故回归）', () => {
    process.env.KIMI_API_KEY = 'k';
    const c = buildModelConfig('kimi', 'kimi-k3');
    expect(c.compat?.supportsDeveloperRole).toBe(false);
    expect(c.compat?.supportsStore).toBe(false);
    expect(c.compat?.maxTokensField).toBe('max_tokens');
  });

  it('deepseek 默认 flash，128K 工作窗口，DEEPSEEK_MODEL_ID 可覆盖', () => {
    process.env.DEEPSEEK_API_KEY = 'k';
    expect(buildModelConfig('deepseek', envModelId('deepseek')).modelId).toBe('deepseek-v4-flash');
    expect(buildModelConfig('deepseek', envModelId('deepseek')).contextWindow).toBe(128000);
    process.env.DEEPSEEK_MODEL_ID = 'deepseek-v4-pro';
    expect(envModelId('deepseek')).toBe('deepseek-v4-pro');
  });

  it('通用覆盖：LLM_BASE_URL / LLM_CONTEXT_WINDOW / LLM_REASONING=false', () => {
    process.env.DEEPSEEK_API_KEY = 'k';
    process.env.LLM_BASE_URL = 'http://proxy.local/v1';
    process.env.LLM_CONTEXT_WINDOW = '1000000';
    process.env.LLM_REASONING = 'false';
    const c = buildModelConfig('deepseek', 'deepseek-v4-flash');
    expect(c.baseUrl).toBe('http://proxy.local/v1');
    expect(c.contextWindow).toBe(1000000);
    expect(c.reasoning).toBe(false);
  });

  it('key 解析：LLM_API_KEY 通用覆盖优先', () => {
    process.env.DEEPSEEK_API_KEY = 'ds';
    process.env.LLM_API_KEY = 'override';
    expect(buildModelConfig('deepseek', 'deepseek-v4-flash').apiKey).toBe('override');
  });
});

describe('isProviderConfigured', () => {
  it('专用 key 或 LLM_API_KEY 存在即已配置；OPENAI_API_KEY 不算（防假已配置）', () => {
    expect(isProviderConfigured('kimi')).toBe(false);
    process.env.OPENAI_API_KEY = 'x';
    expect(isProviderConfigured('kimi')).toBe(false);
    process.env.KIMI_API_KEY = 'x';
    expect(isProviderConfigured('kimi')).toBe(true);
    delete process.env.KIMI_API_KEY;
    process.env.LLM_API_KEY = 'x';
    expect(isProviderConfigured('kimi')).toBe(true);
  });
});
