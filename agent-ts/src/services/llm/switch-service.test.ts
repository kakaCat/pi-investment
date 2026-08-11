import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, readFileSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { initSelection, resetSelectionForTests } from './selection.js';
import { resolveSwitchTarget, switchLLM } from './switch-service.js';

const ENV_KEYS = ['LLM_PROVIDER', 'LLM_API_KEY', 'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'DEEPSEEK_MODEL_ID', 'KIMI_MODEL_ID', 'MODEL_ID'];
let dir: string;
let saved: Record<string, string | undefined>;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'llm-sw-'));
  saved = {};
  for (const k of ENV_KEYS) { saved[k] = process.env[k]; delete process.env[k]; }
  resetSelectionForTests();
  initSelection(dir);
});
afterEach(() => {
  for (const k of ENV_KEYS) {
    if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k];
  }
  resetSelectionForTests();
  rmSync(dir, { recursive: true, force: true });
});

describe('resolveSwitchTarget', () => {
  it('模型别名 / provider 名（provider 用 env 链解析模型）', () => {
    expect(resolveSwitchTarget('pro')).toEqual({ provider: 'deepseek', modelId: 'deepseek-v4-pro' });
    expect(resolveSwitchTarget('kimi')).toEqual({ provider: 'kimi', modelId: 'kimi-k3' });
    process.env.KIMI_MODEL_ID = 'kimi-k3-0905';
    expect(resolveSwitchTarget('kimi')).toEqual({ provider: 'kimi', modelId: 'kimi-k3-0905' });
    expect(resolveSwitchTarget('gpt-5')).toBeNull();
  });
});

describe('switchLLM', () => {
  it('未知目标 → ok:false，报可选值', () => {
    const r = switchLLM('gpt-5', 'human', { piDir: dir });
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/未知目标/);
  });

  it('相同目标 → ok:true changed:false', () => {
    const r = switchLLM('deepseek', 'human', { piDir: dir });
    expect(r).toMatchObject({ ok: true, changed: false });
  });

  it('目标 key 未配置 → 拒绝并指出缺哪个变量', () => {
    const r = switchLLM('kimi', 'human', { piDir: dir });
    expect(r.ok).toBe(false);
    expect(r.error).toMatch(/KIMI_API_KEY/);
  });

  it('成功切换：持久化 state 文件 + 审计日志追加', () => {
    process.env.KIMI_API_KEY = 'k';
    const r = switchLLM('kimi', 'human', { piDir: dir });
    expect(r).toMatchObject({ ok: true, changed: true, from: 'deepseek:deepseek-v4-flash', to: 'kimi:kimi-k3' });
    const state = JSON.parse(readFileSync(join(dir, 'llm-state.json'), 'utf8'));
    expect(state.provider).toBe('kimi');
    const log = readFileSync(join(dir, 'model-switch.log'), 'utf8').trim().split('\n').map((l) => JSON.parse(l));
    expect(log).toHaveLength(1);
    expect(log[0]).toMatchObject({ from: 'deepseek:deepseek-v4-flash', to: 'kimi:kimi-k3', trigger: 'human' });
    expect(typeof log[0].ts).toBe('string');
  });

  it('模型档位切换（pro）也走同一入口', () => {
    process.env.DEEPSEEK_API_KEY = 'k';
    const r = switchLLM('pro', 'agent', { piDir: dir });
    expect(r).toMatchObject({ ok: true, changed: true, to: 'deepseek:deepseek-v4-pro' });
  });
});
