/**
 * Hook 注册表 —— 声明式扩展点，供 LoopGuardian 等模块注册拦截逻辑
 * 设计：docs/superpowers/plans/2026-08-12-execution-tickets.md T6
 */

export type HookTrigger = "before_tool_call" | "after_tool_call" | "turn_end" | "agent_end";

export type HookAction = "allow" | "block" | "modify";

export interface HookResult {
  action: HookAction;
  reason?: string;
  modifiedArgs?: unknown;
}

export interface BeforeToolCallContext {
  toolName: string;
  args: unknown;
  turnCount: number;
  toolCallCount: number;
}

export type HookHandler = (context: BeforeToolCallContext) => HookResult | Promise<HookResult>;

export interface HookDefinition {
  name: string;
  priority: number;  // 数字越小越优先执行
  timeoutMs: number;
  triggers: HookTrigger[];
  handler: HookHandler;
}

class HookRegistry {
  private hooks: Map<string, HookDefinition> = new Map();

  /**
   * 注册一个 hook
   * @param hook Hook 定义
   * @throws 如果同名 hook 已存在
   */
  register(hook: HookDefinition): void {
    if (this.hooks.has(hook.name)) {
      throw new Error(`Hook "${hook.name}" already registered`);
    }
    this.hooks.set(hook.name, hook);
  }

  /**
   * 注销一个 hook（主要用于测试清理）
   */
  unregister(name: string): void {
    this.hooks.delete(name);
  }

  /**
   * 获取指定 trigger 的所有 hook，按 priority 升序排序
   */
  getHooksForTrigger(trigger: HookTrigger): HookDefinition[] {
    return Array.from(this.hooks.values())
      .filter(h => h.triggers.includes(trigger))
      .sort((a, b) => a.priority - b.priority);
  }

  /**
   * 清空所有 hook（仅测试用）
   */
  clear(): void {
    this.hooks.clear();
  }

  /**
   * 获取所有已注册 hook 名称
   */
  getRegisteredHooks(): string[] {
    return Array.from(this.hooks.keys());
  }
}

export const hookRegistry = new HookRegistry();
