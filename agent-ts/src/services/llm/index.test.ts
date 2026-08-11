import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { getLLM, initLLM, resetLLMForTests } from './index.js';

const ENV_KEYS = ['LLM_PROVIDER', 'LLM_API_KEY', 'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY', 'MODEL_ID', 'DEEPSEEK_MODEL_ID', 'KIMI_MODEL_ID'];
let dir: string;
let saved: Record<string, string | undefined>;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'llm-port-'));
  saved = {};
  for (const k of ENV_KEYS) { saved[k] = process.env[k]; delete process.env[k]; }
  resetLLMForTests();
});
afterEach(() => {
  for (const k of ENV_KEYS) {
    if (saved[k] === undefined) delete process.env[k]; else process.env[k] = saved[k];
  }
  resetLLMForTests();
  rmSync(dir, { recursive: true, force: true });
});

describe('LLMPort', () => {
  it('initLLM 后 current() 返回默认选择，source=default', () => {
    initLLM(dir);
    const llm = getLLM();
    expect(llm.current()).toMatchObject({ provider: 'deepseek', modelId: 'deepseek-v4-flash' });
    expect(llm.source()).toBe('default');
  });

  it('switch 成功 → current/getSessionModel/status 全部反映新选择，onChange 触发', () => {
    process.env.KIMI_API_KEY = 'k';
    const llm = initLLM(dir);
    const seen: string[] = [];
    llm.onChange((s) => seen.push(s.modelId));
    const r = llm.switch('kimi', 'human');
    expect(r.ok).toBe(true);
    expect(llm.current().provider).toBe('kimi');
    expect((llm.getSessionModel() as any).id).toBe('kimi-k3');
    const st = llm.status();
    expect(st.source).toBe('state');
    expect(st.providers.find((p) => p.name === 'kimi')).toMatchObject({ configured: true, active: true });
    expect(st.providers.find((p) => p.name === 'deepseek')).toMatchObject({ active: false });
    expect(seen).toEqual(['kimi-k3']);
  });

  it('switch 失败（key 未配置）→ 选择不变', () => {
    const llm = initLLM(dir);
    const r = llm.switch('kimi', 'agent');
    expect(r.ok).toBe(false);
    expect(llm.current().provider).toBe('deepseek');
  });

  it('getModelConfig 返回自有类型（含 kimi compat）', () => {
    process.env.LLM_PROVIDER = 'kimi';
    process.env.KIMI_API_KEY = 'k';
    const llm = initLLM(dir);
    const c = llm.getModelConfig();
    expect(c.provider).toBe('kimi');
    expect(c.compat?.supportsDeveloperRole).toBe(false);
  });

  it('未 initLLM 时 getLLM() 惰性可用（env/default 回退，兼容旧调用方）', () => {
    process.env.LLM_PROVIDER = 'kimi';
    process.env.KIMI_API_KEY = 'k';
    process.env.DEEPSEEK_API_KEY = 'k'; // 让 validate 通过，走到 setSelection 才暴露未初始化
    const llm = getLLM();
    expect(llm.current().provider).toBe('kimi');
    expect(() => llm.switch('deepseek', 'human')).toThrow(/initSelection/);
  });
});
