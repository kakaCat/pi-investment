import { beforeEach, describe, expect, jest, test } from "@jest/globals";

const createSessionMock = jest.fn(async (opts: any) => ({ session: {}, options: opts }));
const createAppResourceLoaderMock = jest.fn(
  async (cwd: string, systemPrompt?: string) => ({ __loader: true, cwd, systemPrompt }),
);

jest.unstable_mockModule("../../session-facade.js", () => ({
  createSession: createSessionMock,
}));
jest.unstable_mockModule("../../api/extensions/model-command.js", () => ({
  createAppResourceLoader: createAppResourceLoaderMock,
}));

const { createSchedulerSession } = await import("./scheduler-session.js");

describe("createSchedulerSession（A2-T2）", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("fin 保持现状裸会话（无 customTools / 无 model）", async () => {
    await createSchedulerSession("fin");

    expect(createSessionMock).toHaveBeenCalledTimes(1);
    const opts = createSessionMock.mock.calls[0][0] as any;
    expect(opts.customTools).toBeUndefined();
    expect(opts.model).toBeUndefined();
    expect(opts.resourceLoader).toBeDefined();
    // fin 不注入系统提示词（走 SDK 默认发现）
    expect(createAppResourceLoaderMock.mock.calls[0][1]).toBeUndefined();
  });

  test("evolution 装配进化工具 + pro 模型 + 身份系统提示词", async () => {
    await createSchedulerSession("evolution");

    const opts = createSessionMock.mock.calls[0][0] as any;
    const toolNames = opts.customTools.map((t: any) => t.name);
    expect(toolNames).toContain("evolution_run");
    expect(toolNames).toContain("evolution_leaderboard");
    // 结构隔离：进化 Agent 无交易写工具
    expect(toolNames.filter((n: string) => n.startsWith("portfolio_"))).toEqual([]);
    expect(toolNames.filter((n: string) => n.startsWith("pool_"))).toEqual([]);

    expect(opts.model).toBeTruthy();
    // 系统提示词经 resourceLoader 注入（非空）
    const systemPrompt = createAppResourceLoaderMock.mock.calls[0][1] as string;
    expect(typeof systemPrompt).toBe("string");
    expect(systemPrompt.length).toBeGreaterThan(50);
  });

  test("默认 agentKind 为 fin（零变化）", async () => {
    await createSchedulerSession();
    const opts = createSessionMock.mock.calls[0][0] as any;
    expect(opts.customTools).toBeUndefined();
  });
});
