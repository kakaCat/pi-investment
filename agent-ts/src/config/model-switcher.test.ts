/**
 * model-switcher 运行时 provider 状态测试
 */
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  getRuntimeOverride,
  setRuntimeProvider,
  resetRuntimeProviderForTests,
  isProviderConfigured,
  listProviders,
} from './model-switcher.js';

const ENV_KEYS = [
  'LLM_PROVIDER', 'LLM_API_KEY',
  'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY',
  'KIMI_BASE_URL', 'KIMI_MODEL_ID',
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

describe('运行时 provider 状态', () => {
  it('默认无 override', () => {
    expect(getRuntimeOverride()).toBeNull();
  });

  it('setRuntimeProvider 后 getRuntimeOverride 返回新值', () => {
    setRuntimeProvider('kimi');
    expect(getRuntimeOverride()).toBe('kimi');
  });

  it('resetRuntimeProviderForTests 清除 override', () => {
    setRuntimeProvider('kimi');
    resetRuntimeProviderForTests();
    expect(getRuntimeOverride()).toBeNull();
  });
});

describe('isProviderConfigured', () => {
  it('DEEPSEEK_API_KEY 存在时 deepseek 已配置', () => {
    process.env.DEEPSEEK_API_KEY = 'sk-test';
    expect(isProviderConfigured('deepseek')).toBe(true);
  });

  it('KIMI_API_KEY / MOONSHOT_API_KEY 任一存在时 kimi 已配置', () => {
    process.env.MOONSHOT_API_KEY = 'sk-test';
    expect(isProviderConfigured('kimi')).toBe(true);
  });

  it('LLM_API_KEY 通用覆盖视为已配置', () => {
    process.env.LLM_API_KEY = 'sk-test';
    expect(isProviderConfigured('kimi')).toBe(true);
  });

  it('OPENAI_API_KEY 不算作任何 provider 的 key（createModel 会同步它，防假阳性）', () => {
    process.env.OPENAI_API_KEY = 'sk-deepseek-synced';
    expect(isProviderConfigured('kimi')).toBe(false);
    expect(isProviderConfigured('deepseek')).toBe(false);
  });

  it('无任何 key 时未配置', () => {
    expect(isProviderConfigured('deepseek')).toBe(false);
  });
});

describe('listProviders', () => {
  it('返回两个 provider 及配置状态', () => {
    process.env.DEEPSEEK_API_KEY = 'sk-test';
    const list = listProviders();
    expect(list).toEqual([
      { name: 'deepseek', configured: true },
      { name: 'kimi', configured: false },
    ]);
  });
});

describe('config 集成：getActiveProvider / createModel', () => {
  it('未切换时 getActiveProvider 读 LLM_PROVIDER 环境变量', async () => {
    const { getActiveProvider } = await import('./config.js');
    expect(getActiveProvider()).toBe('deepseek'); // env 缺省
    process.env.LLM_PROVIDER = 'kimi';
    expect(getActiveProvider()).toBe('kimi');
  });

  it('切换后 getActiveProvider 优先返回运行时 override', async () => {
    process.env.LLM_PROVIDER = 'deepseek';
    setRuntimeProvider('kimi');
    const { getActiveProvider } = await import('./config.js');
    expect(getActiveProvider()).toBe('kimi');
  });

  it('切换后 createModel 返回新 provider 的模型并同步 OPENAI_API_KEY', async () => {
    process.env.KIMI_API_KEY = 'sk-kimi-test';
    process.env.KIMI_BASE_URL = 'https://api.kimi.com/coding/v1';
    process.env.KIMI_MODEL_ID = 'k3';
    setRuntimeProvider('kimi');
    const { createModel } = await import('./config.js');
    const model = createModel();
    expect(model.id).toBe('k3');
    expect(model.baseUrl).toBe('https://api.kimi.com/coding/v1');
    expect(process.env.OPENAI_API_KEY).toBe('sk-kimi-test');
  });
});
