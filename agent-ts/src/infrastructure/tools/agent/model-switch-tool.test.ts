/**
 * model_switch 工具测试
 */
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { modelSwitchTool, resetSwitchHistoryForTests } from './model-switch-tool.js';
import {
  resetRuntimeProviderForTests,
  getRuntimeOverride,
} from '../../../config/model-switcher.js';

const ENV_KEYS = ['LLM_API_KEY', 'DEEPSEEK_API_KEY', 'KIMI_API_KEY', 'MOONSHOT_API_KEY'];
let savedEnv: Record<string, string | undefined>;

beforeEach(() => {
  savedEnv = {};
  for (const k of ENV_KEYS) { savedEnv[k] = process.env[k]; delete process.env[k]; }
  resetRuntimeProviderForTests();
  resetSwitchHistoryForTests();
});

afterEach(() => {
  for (const k of ENV_KEYS) {
    if (savedEnv[k] === undefined) delete process.env[k];
    else process.env[k] = savedEnv[k];
  }
  resetRuntimeProviderForTests();
});

async function run(provider: string): Promise<string> {
  const result = await modelSwitchTool.execute('test-call', { provider });
  return result.content[0].type === 'text' ? result.content[0].text : '';
}

describe('model_switch 工具', () => {
  it('正常切换：设置 override 并返回决策上下文', async () => {
    process.env.DEEPSEEK_API_KEY = 'sk-a';
    process.env.KIMI_API_KEY = 'sk-b';
    const text = await run('kimi');
    expect(getRuntimeOverride()).toBe('kimi');
    expect(text).toContain('kimi');
    expect(text).toContain('新会话');
  });

  it('幂等：目标 = 当前 provider 时不重复切换', async () => {
    process.env.DEEPSEEK_API_KEY = 'sk-a';
    const text = await run('deepseek'); // 当前默认就是 deepseek
    expect(text).toContain('已是');
    expect(getRuntimeOverride()).toBeNull(); // 未设置 override
  });

  it('缺 key 拒绝切换', async () => {
    process.env.DEEPSEEK_API_KEY = 'sk-a';
    const text = await run('kimi'); // kimi 无 key
    expect(text).toContain('未配置');
    expect(getRuntimeOverride()).toBeNull();
  });

  it('防抖动：滚动窗口内最多 3 次，第 4 次拒绝', async () => {
    process.env.DEEPSEEK_API_KEY = 'sk-a';
    process.env.KIMI_API_KEY = 'sk-b';
    expect(await run('kimi')).toContain('kimi');
    expect(await run('deepseek')).toContain('deepseek');
    expect(await run('kimi')).toContain('kimi');
    const fourth = await run('deepseek');
    expect(fourth).toContain('过于频繁');
  });
});
