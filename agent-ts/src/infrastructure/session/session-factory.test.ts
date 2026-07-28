/**
 * Session Factory - Unit Tests
 *
 * 目标：gateway 渠道会话（agentType: 'main'）必须走主 agent 日志路径：
 * - prompt() 记录 user.input（conversation.messages 有 user 消息）
 * - 不再产生 subagent.start 误标事件
 *
 * 注意：ts-jest ESM 模式下 jest.mock 不提升，必须使用
 * jest.unstable_mockModule + 动态 import（ESM 标准做法）。
 * 仓库 jest 配置不支持顶层 await，动态 import 放在 beforeAll。
 */
import { describe, it, expect, beforeAll, beforeEach, jest } from '@jest/globals';

const mockCreateAgentSession = jest.fn();
const mockSubscribe = jest.fn();
const mockInnerPrompt = jest.fn<(msg: string, opts?: unknown) => Promise<unknown>>();

jest.unstable_mockModule('../../sdk-facade.js', () => ({
  createAgentSession: mockCreateAgentSession,
}));

jest.unstable_mockModule('../../services/intelligence/skill-router.js', () => ({
  rewritePromptWithSkill: jest.fn((p: string) => ({ prompt: p, forcedSkill: null })),
}));

jest.unstable_mockModule('../tools/skill-guard.js', () => ({
  getExplicitSkillFromPrompt: jest.fn(() => null),
  withForcedSkillScope: jest.fn((_skill: unknown, fn: () => unknown) => fn()),
}));

let createTrackedSession: typeof import('./session-factory.js').createTrackedSession;
let logger: typeof import('../logging/observable-logger.js');

beforeAll(async () => {
  ({ createTrackedSession } = await import('./session-factory.js'));
  logger = await import('../logging/observable-logger.js');
});

describe('createTrackedSession', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockInnerPrompt.mockResolvedValue({ ok: true });
    mockCreateAgentSession.mockResolvedValue({
      session: { prompt: mockInnerPrompt, subscribe: mockSubscribe },
    } as never);
  });

  it("agentType='main' 时 prompt() 记录 user 消息到 conversation（gateway 修复）", async () => {
    const before = logger.getConversationMessages().length;

    const session = await createTrackedSession({
      agentType: 'main',
      createOptions: { cwd: '/tmp' },
    });
    await session.prompt('渠道消息：分析一下茅台');

    const messages = logger.getConversationMessages();
    const newMessages = messages.slice(before);
    expect(newMessages.some((m) => m.role === 'user' && m.content === '渠道消息：分析一下茅台')).toBe(true);
    expect(mockInnerPrompt).toHaveBeenCalledWith('渠道消息：分析一下茅台', undefined);
  });

  it("agentType='subagent' 时 prompt() 不写 conversation（保持原语义）", async () => {
    const before = logger.getConversationMessages().length;

    const session = await createTrackedSession({
      agentType: 'subagent',
      createOptions: { cwd: '/tmp' },
    });
    await session.prompt('子代理任务');

    const messages = logger.getConversationMessages();
    expect(messages.length).toBe(before);
    expect(mockInnerPrompt).toHaveBeenCalledWith('子代理任务', undefined);
  });
});
