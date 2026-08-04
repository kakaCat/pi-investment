/**
 * config compat 回归测试
 *
 * 背景（2026-07-28 两次事故）：
 * pi-ai SDK 的 detectCompat 只认 api.moonshot.* 为 Moonshot；
 * api.kimi.com / 本地代理 URL 会被当作标准 OpenAI，reasoning=true 时
 * system prompt 以 role:"developer" 发送，Kimi 端点报
 * "400 Invalid request: tokenization failed"。
 * 修复：kimi preset 显式声明 compat.supportsDeveloperRole=false，
 * createModel() 必须把 preset.compat 透传到 SDK Model 对象。
 * 此测试防止该修复被后续改动意外移除。
 */
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { createModel } from './config.js';
import { resetRuntimeProviderForTests } from './model-switcher.js';

const ENV_KEYS = [
  'LLM_PROVIDER', 'LLM_API_KEY', 'LLM_BASE_URL', 'LLM_REASONING',
  'LLM_CONTEXT_WINDOW', 'LLM_MAX_TOKENS', 'MODEL_ID',
  'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY',
  'KIMI_BASE_URL', 'KIMI_MODEL_ID', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_MODEL_ID',
];
let savedEnv: Record<string, string | undefined>;

beforeEach(() => {
  savedEnv = {};
  for (const k of ENV_KEYS) { savedEnv[k] = process.env[k]; delete process.env[k]; }
  resetRuntimeProviderForTests();
});

afterEach(() => {
  for (const k of ENV_KEYS) {
    if (savedEnv[k] === undefined) delete process.env[k];
    else process.env[k] = savedEnv[k];
  }
  resetRuntimeProviderForTests();
});

describe('createModel compat 透传', () => {
  it('kimi preset 必须关闭 developer role（否则 400 tokenization failed）', () => {
    process.env.LLM_PROVIDER = 'kimi';
    process.env.KIMI_API_KEY = 'test-key';
    const model = createModel() as any;
    expect(model.compat).toBeDefined();
    expect(model.compat.supportsDeveloperRole).toBe(false);
    expect(model.compat.supportsStore).toBe(false);
    expect(model.compat.maxTokensField).toBe('max_tokens');
  });

  it('kimi 走自定义/代理 baseUrl 时 compat 依然生效', () => {
    process.env.LLM_PROVIDER = 'kimi';
    process.env.KIMI_API_KEY = 'test-key';
    process.env.KIMI_BASE_URL = 'https://api.kimi.com/coding/v1';
    const model = createModel() as any;
    expect(model.baseUrl).toBe('https://api.kimi.com/coding/v1');
    expect(model.compat?.supportsDeveloperRole).toBe(false);
  });

  it('deepseek preset 不携带 compat 覆盖（依赖 SDK 自动检测）', () => {
    process.env.LLM_PROVIDER = 'deepseek';
    process.env.DEEPSEEK_API_KEY = 'test-key';
    const model = createModel() as any;
    expect(model.compat).toBeUndefined();
  });
});

describe('deepseek v4 默认模型', () => {
  it('默认模型为 deepseek-v4-flash（deepseek-chat 已不在官方模型列表）', () => {
    process.env.LLM_PROVIDER = 'deepseek';
    process.env.DEEPSEEK_API_KEY = 'test-key';
    const model = createModel() as any;
    expect(model.id).toBe('deepseek-v4-flash');
  });

  it('DEEPSEEK_MODEL_ID 可切换为 deepseek-v4-pro', () => {
    process.env.LLM_PROVIDER = 'deepseek';
    process.env.DEEPSEEK_API_KEY = 'test-key';
    process.env.DEEPSEEK_MODEL_ID = 'deepseek-v4-pro';
    const model = createModel() as any;
    expect(model.id).toBe('deepseek-v4-pro');
  });

  it('deepseek 工作上下文窗口默认 128K（v4 实际 1M，可用 LLM_CONTEXT_WINDOW 上调）', () => {
    process.env.LLM_PROVIDER = 'deepseek';
    process.env.DEEPSEEK_API_KEY = 'test-key';
    const model = createModel() as any;
    expect(model.contextWindow).toBe(128000);
    process.env.LLM_CONTEXT_WINDOW = '1000000';
    expect((createModel() as any).contextWindow).toBe(1000000);
  });
});
