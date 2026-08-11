import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import {
  effectiveSelection,
  getSelection,
  initSelection,
  onSelectionChange,
  resetSelectionForTests,
  selectionSource,
  setSelection,
} from './selection.js';

let dir: string;
let savedProvider: string | undefined;

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'llm-sel-'));
  savedProvider = process.env.LLM_PROVIDER;
  delete process.env.LLM_PROVIDER;
  resetSelectionForTests();
});
afterEach(() => {
  if (savedProvider === undefined) delete process.env.LLM_PROVIDER;
  else process.env.LLM_PROVIDER = savedProvider;
  resetSelectionForTests();
  rmSync(dir, { recursive: true, force: true });
});

describe('initSelection 优先级链', () => {
  it('无 state 文件无 env → 默认 deepseek-v4-flash，source=default', () => {
    const sel = initSelection(dir);
    expect(sel.provider).toBe('deepseek');
    expect(sel.modelId).toBe('deepseek-v4-flash');
    expect(selectionSource()).toBe('default');
  });

  it('无 state 文件有 LLM_PROVIDER=kimi → env 生效，source=env', () => {
    process.env.LLM_PROVIDER = 'kimi';
    const sel = initSelection(dir);
    expect(sel.provider).toBe('kimi');
    expect(sel.modelId).toBe('kimi-k3');
    expect(selectionSource()).toBe('env');
  });

  it('state 文件存在 → 压过 env，source=state', () => {
    process.env.LLM_PROVIDER = 'kimi';
    writeFileSync(join(dir, 'llm-state.json'), JSON.stringify({
      provider: 'deepseek', modelId: 'deepseek-v4-pro',
      updatedBy: 'human', updatedAt: '2026-08-11T00:00:00.000Z', version: 7,
    }));
    const sel = initSelection(dir);
    expect(sel.provider).toBe('deepseek');
    expect(sel.modelId).toBe('deepseek-v4-pro');
    expect(sel.version).toBe(7);
    expect(selectionSource()).toBe('state');
  });

  it('state 文件损坏 → 警告并回退 env/default，不抛错', () => {
    writeFileSync(join(dir, 'llm-state.json'), '{broken json');
    const sel = initSelection(dir);
    expect(sel.provider).toBe('deepseek');
    expect(selectionSource()).toBe('default');
  });

  it('state 文件 provider 非法 → 回退 env/default', () => {
    writeFileSync(join(dir, 'llm-state.json'), JSON.stringify({ provider: 'gpt5', modelId: 'x' }));
    const sel = initSelection(dir);
    expect(sel.provider).toBe('deepseek');
  });
});

describe('setSelection 持久化', () => {
  it('写 state 文件、版本+1、触发监听、updatedBy 记录', () => {
    initSelection(dir);
    const seen: string[] = [];
    onSelectionChange((s) => seen.push(`${s.provider}:${s.modelId}@${s.version}`));
    const next = setSelection('kimi', 'kimi-k3', 'human');
    expect(next.version).toBe(1);
    expect(selectionSource()).toBe('state');
    const onDisk = JSON.parse(readFileSync(join(dir, 'llm-state.json'), 'utf8'));
    expect(onDisk.provider).toBe('kimi');
    expect(onDisk.updatedBy).toBe('human');
    expect(seen).toEqual(['kimi:kimi-k3@1']);
    const again = setSelection('deepseek', 'deepseek-v4-pro', 'agent');
    expect(again.version).toBe(2);
  });

  it('未初始化时 setSelection 抛错（防止隐式写错位置）', () => {
    expect(() => setSelection('kimi', 'kimi-k3', 'human')).toThrow(/initSelection/);
  });
});

describe('未初始化回退', () => {
  it('effectiveSelection 未初始化时走 env/default（既有单测安全网）', () => {
    expect(getSelection()).toBeNull();
    expect(effectiveSelection().provider).toBe('deepseek');
    process.env.LLM_PROVIDER = 'kimi';
    expect(effectiveSelection().provider).toBe('kimi');
  });
});
