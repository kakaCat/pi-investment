/**
 * Hook 执行器 —— 按优先级串行执行 hooks，支持超时保护
 */
import { writeFileSync, appendFileSync, existsSync, mkdirSync } from "fs";
import { join } from "path";
import type { HookDefinition, HookResult, BeforeToolCallContext, HookTrigger } from "./registry.js";
import { hookRegistry } from "./registry.js";
import { paths } from "../../config/config.js";

const HOOK_LOG_PATH = join(paths.piDir, "hooks.log");

/**
 * 带超时的 Promise.race 包装
 */
async function withTimeout<T>(
  promise: Promise<T>,
  timeoutMs: number,
  defaultValue: T
): Promise<T> {
  const timeoutPromise = new Promise<T>((resolve) => {
    setTimeout(() => resolve(defaultValue), timeoutMs);
  });
  return Promise.race([promise, timeoutPromise]);
}

/**
 * 记录 hook 拦截日志
 */
function logHookAction(
  hookName: string,
  action: string,
  reason: string,
  context: BeforeToolCallContext
): void {
  const timestamp = new Date().toISOString();
  const logLine = `${timestamp} [${hookName}] action=${action} reason="${reason}" tool=${context.toolName} turn=${context.turnCount}\n`;

  try {
    appendFileSync(HOOK_LOG_PATH, logLine, "utf-8");
  } catch (err) {
    console.warn(`[HookExecutor] Failed to write hook log:`, err);
  }
}

/**
 * 执行 before_tool_call 的所有 hooks
 * @returns 第一个 block/modify 的结果，或最后一个 allow
 */
export async function executeBeforeToolCallHooks(
  context: BeforeToolCallContext
): Promise<HookResult> {
  const hooks = hookRegistry.getHooksForTrigger("before_tool_call");

  let lastResult: HookResult = { action: "allow" };

  for (const hook of hooks) {
    try {
      const result = await withTimeout(
        Promise.resolve(hook.handler(context)),
        hook.timeoutMs,
        { action: "allow" as const, reason: `timeout after ${hook.timeoutMs}ms` }
      );

      // 记录非 allow 的结果
      if (result.action !== "allow") {
        logHookAction(hook.name, result.action, result.reason || "", context);
      }

      lastResult = result;

      // block 或 modify 立即返回，不再执行后续 hooks
      if (result.action === "block" || result.action === "modify") {
        return result;
      }
    } catch (err) {
      console.warn(`[HookExecutor] Hook "${hook.name}" threw error:`, err);
      // 错误不阻断后续 hooks
    }
  }

  return lastResult;
}

/**
 * 初始化 hook 日志文件（确保目录存在）
 */
export function initHookLog(): void {
  try {
    if (!existsSync(paths.piDir)) {
      mkdirSync(paths.piDir, { recursive: true });
    }
    // 创建空文件（如果不存在）
    if (!existsSync(HOOK_LOG_PATH)) {
      writeFileSync(HOOK_LOG_PATH, "", "utf-8");
    }
  } catch (err) {
    console.warn(`[HookExecutor] Failed to init hook log:`, err);
  }
}
