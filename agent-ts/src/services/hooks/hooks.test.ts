/**
 * Hook 系统测试 —— 优先级、超时、trigger 门控、拦截生效
 */
import { hookRegistry, executeBeforeToolCallHooks, initHookLog, type HookDefinition } from "./index.js";
import type { BeforeToolCallContext } from "./registry.js";
import { readFileSync, existsSync, unlinkSync } from "fs";
import { join } from "path";
import { paths } from "../../config/config.js";

const HOOK_LOG_PATH = join(paths.piDir, "hooks.log");

describe("Hook Registry", () => {
  beforeEach(() => {
    hookRegistry.clear();
  });

  test("注册和获取 hook", () => {
    const hook: HookDefinition = {
      name: "test-hook",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow" }),
    };

    hookRegistry.register(hook);
    expect(hookRegistry.getRegisteredHooks()).toContain("test-hook");

    const hooks = hookRegistry.getHooksForTrigger("before_tool_call");
    expect(hooks).toHaveLength(1);
    expect(hooks[0].name).toBe("test-hook");
  });

  test("重复注册同名 hook 抛错", () => {
    const hook: HookDefinition = {
      name: "duplicate",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow" }),
    };

    hookRegistry.register(hook);
    expect(() => hookRegistry.register(hook)).toThrow('Hook "duplicate" already registered');
  });

  test("按 priority 升序排序", () => {
    hookRegistry.register({
      name: "hook-30",
      priority: 30,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow" }),
    });

    hookRegistry.register({
      name: "hook-10",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow" }),
    });

    hookRegistry.register({
      name: "hook-20",
      priority: 20,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow" }),
    });

    const hooks = hookRegistry.getHooksForTrigger("before_tool_call");
    expect(hooks.map(h => h.name)).toEqual(["hook-10", "hook-20", "hook-30"]);
  });

  test("trigger 门控过滤", () => {
    hookRegistry.register({
      name: "only-turn-end",
      priority: 10,
      timeoutMs: 100,
      triggers: ["turn_end"],
      handler: async () => ({ action: "allow" }),
    });

    hookRegistry.register({
      name: "only-tool-call",
      priority: 20,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow" }),
    });

    const beforeToolCall = hookRegistry.getHooksForTrigger("before_tool_call");
    expect(beforeToolCall).toHaveLength(1);
    expect(beforeToolCall[0].name).toBe("only-tool-call");

    const turnEnd = hookRegistry.getHooksForTrigger("turn_end");
    expect(turnEnd).toHaveLength(1);
    expect(turnEnd[0].name).toBe("only-turn-end");
  });
});

describe("Hook Executor", () => {
  beforeEach(() => {
    hookRegistry.clear();
    initHookLog();
  });

  const mockContext: BeforeToolCallContext = {
    toolName: "test_tool",
    args: { param: "value" },
    turnCount: 5,
    toolCallCount: 10,
  };

  test("无 hook 时返回 allow", async () => {
    const result = await executeBeforeToolCallHooks(mockContext);
    expect(result.action).toBe("allow");
  });

  test("所有 hook 返回 allow 时，返回最后一个 allow", async () => {
    hookRegistry.register({
      name: "hook-1",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow", reason: "hook-1 allow" }),
    });

    hookRegistry.register({
      name: "hook-2",
      priority: 20,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow", reason: "hook-2 allow" }),
    });

    const result = await executeBeforeToolCallHooks(mockContext);
    expect(result.action).toBe("allow");
  });

  test("第一个 block 立即返回，不执行后续 hooks", async () => {
    let hook2Called = false;

    hookRegistry.register({
      name: "blocker",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "block", reason: "blocked by policy" }),
    });

    hookRegistry.register({
      name: "hook-2",
      priority: 20,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => {
        hook2Called = true;
        return { action: "allow" };
      },
    });

    const result = await executeBeforeToolCallHooks(mockContext);
    expect(result.action).toBe("block");
    expect(result.reason).toBe("blocked by policy");
    expect(hook2Called).toBe(false);
  });

  test("modify 立即返回修改后的参数", async () => {
    hookRegistry.register({
      name: "modifier",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({
        action: "modify",
        reason: "modified args",
        modifiedArgs: { param: "modified_value" },
      }),
    });

    const result = await executeBeforeToolCallHooks(mockContext);
    expect(result.action).toBe("modify");
    expect(result.modifiedArgs).toEqual({ param: "modified_value" });
  });

  test("超时后返回 allow（不阻塞后续流程）", async () => {
    hookRegistry.register({
      name: "slow-hook",
      priority: 10,
      timeoutMs: 50,
      triggers: ["before_tool_call"],
      handler: async () => {
        await new Promise(resolve => setTimeout(resolve, 200));
        return { action: "block", reason: "should timeout" };
      },
    });

    const result = await executeBeforeToolCallHooks(mockContext);
    expect(result.action).toBe("allow");
    expect(result.reason).toContain("timeout");
  });

  test("hook 抛错不阻断后续 hooks", async () => {
    hookRegistry.register({
      name: "failing-hook",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => {
        throw new Error("unexpected error");
      },
    });

    hookRegistry.register({
      name: "working-hook",
      priority: 20,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "block", reason: "blocked" }),
    });

    const result = await executeBeforeToolCallHooks(mockContext);
    expect(result.action).toBe("block");
    expect(result.reason).toBe("blocked");
  });

  test("拦截动作写入 hooks.log", async () => {
    // 清空日志文件
    if (existsSync(HOOK_LOG_PATH)) {
      unlinkSync(HOOK_LOG_PATH);
    }
    initHookLog();

    hookRegistry.register({
      name: "test-block-hook",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "block", reason: "test block" }),
    });

    await executeBeforeToolCallHooks(mockContext);

    const logContent = readFileSync(HOOK_LOG_PATH, "utf-8");
    expect(logContent).toContain("[test-block-hook]");
    expect(logContent).toContain("action=block");
    expect(logContent).toContain('reason="test block"');
    expect(logContent).toContain("tool=test_tool");
    expect(logContent).toContain("turn=5");
  });

  test("allow 动作不写日志", async () => {
    // 清空日志文件
    if (existsSync(HOOK_LOG_PATH)) {
      unlinkSync(HOOK_LOG_PATH);
    }
    initHookLog();

    hookRegistry.register({
      name: "test-allow-hook",
      priority: 10,
      timeoutMs: 100,
      triggers: ["before_tool_call"],
      handler: async () => ({ action: "allow" }),
    });

    await executeBeforeToolCallHooks(mockContext);

    const logContent = readFileSync(HOOK_LOG_PATH, "utf-8");
    expect(logContent).not.toContain("[test-allow-hook]");
  });
});
