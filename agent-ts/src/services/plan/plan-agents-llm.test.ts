import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { mkdtempSync, rmSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { getLLM, initLLM, resetLLMForTests } from '../llm/index.js';
import type { ChatRequest, ChatResponse } from '../llm/types.js';
import { createPlanAgent } from './plan-agent.js';
import { createClarifyAgent } from './clarify-agent.js';
import { createReflectAgent } from './reflect-agent.js';

let dir: string;
let savedKey: string | undefined;
let completeCalls: ChatRequest[];

const fakeResponse: ChatResponse = {
  text: '1. 第一步\n2. 第二步',
  usage: { input: 1, output: 1, totalTokens: 2 },
  model: 'deepseek-v4-flash',
};

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'llm-plan-'));
  savedKey = process.env.DEEPSEEK_API_KEY;
  process.env.DEEPSEEK_API_KEY = 'test';
  resetLLMForTests();
  initLLM(dir);
  completeCalls = [];
  // port 是 Plain Object，直接替换 complete 为捕获 mock（避免 ESM namespace spy 的坑）
  getLLM().complete = async (req: ChatRequest) => {
    completeCalls.push(req);
    return fakeResponse;
  };
});
afterEach(() => {
  if (savedKey === undefined) delete process.env.DEEPSEEK_API_KEY;
  else process.env.DEEPSEEK_API_KEY = savedKey;
  resetLLMForTests();
  rmSync(dir, { recursive: true, force: true });
});

describe('plan 三杰走 LLMPort.complete', () => {
  it('createPlanAgent：system+user 两条消息，返回文本', async () => {
    const plan = await createPlanAgent('测试任务');
    expect(plan).toContain('第一步');
    expect(completeCalls).toHaveLength(1);
    const req = completeCalls[0];
    expect(req.messages[0].role).toBe('system');
    expect(req.messages[1].role).toBe('user');
    expect(req.messages[1].content).toContain('测试任务');
  });

  it('createClarifyAgent：system+user 结构，返回文本', async () => {
    const out = await createClarifyAgent('买个股票');
    expect(out).toContain('第一步');
    expect(completeCalls).toHaveLength(1);
    expect(completeCalls[0].messages[0].role).toBe('system');
    expect(completeCalls[0].messages[1].content).toContain('买个股票');
  });

  it('createReflectAgent：system+user 结构，返回文本', async () => {
    const out = await createReflectAgent('目标X', '完成了Y');
    expect(out).toContain('第一步');
    expect(completeCalls).toHaveLength(1);
    expect(completeCalls[0].messages[0].role).toBe('system');
    expect(completeCalls[0].messages[1].content).toContain('目标X');
  });
});
