/**
 * Hook 系统 —— 统一导出入口
 */
export {
  hookRegistry,
  type HookDefinition,
  type HookHandler,
  type HookResult,
  type HookAction,
  type HookTrigger,
  type BeforeToolCallContext,
} from "./registry.js";

export {
  executeBeforeToolCallHooks,
  initHookLog,
} from "./executor.js";
