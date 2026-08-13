import { FileBasedSchedulerStore } from "./persistent-store.js";
import { createSchedulerExecutor, type SchedulerExecutorOptions } from "./scheduler-executor.js";
import { SchedulerService, type SchedulerServiceOptions } from "./scheduler-service.js";
import { paths } from "../../config/config.js";

let runtime: {
  store: FileBasedSchedulerStore;
  service: SchedulerService;
} | null = null;

export async function getSchedulerRuntime(
  options: Partial<SchedulerServiceOptions> & SchedulerExecutorOptions = {},
) {
  if (runtime) {
    // 单例已建时带参调用是静默丢配置（2026-08-13 headless 事故：
    // initAgentDecisionTasks 先建无 promptAgent 的单例，后到的 promptAgent 被吞，
    // agent_turn 任务到点静默失败）。显式 warn 让配置竞争可见。
    if (options.promptAgent || options.executor) {
      console.warn(
        "⚠️ [SchedulerRuntime] 运行时已初始化，本次传入的 promptAgent/executor 被忽略" +
          "（调用顺序竞争——先建者生效）",
      );
    }
    return runtime;
  }

  // 默认落到项目约定的 agent-ts/.pi-invest（与记忆/会话数据同目录），
  // 不用包内默认的 ~/.pi-invest——2026-08-12 审查修正
  const store = options.store instanceof FileBasedSchedulerStore
    ? options.store
    : new FileBasedSchedulerStore({ dataDir: paths.piDir });

  const service = new SchedulerService({
    store,
    executor: options.executor ?? createSchedulerExecutor(options),
    now: options.now,
    idGenerator: options.idGenerator,
    misfireGracePeriodMs: options.misfireGracePeriodMs,
    taskTimeoutMs: options.taskTimeoutMs,
  });
  await service.reloadTasks();

  runtime = { store, service };
  return runtime;
}

export async function startSchedulerRuntime(options: SchedulerExecutorOptions = {}) {
  const current = await getSchedulerRuntime(options);
  current.service.start();
  return current;
}

export function resetSchedulerRuntimeForTests(): void {
  runtime = null;
}
