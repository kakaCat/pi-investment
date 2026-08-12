import { FileBasedSchedulerStore } from "./persistent-store.js";
import { createSchedulerExecutor, type SchedulerExecutorOptions } from "./scheduler-executor.js";
import { SchedulerService, type SchedulerServiceOptions } from "./scheduler-service.js";

let runtime: {
  store: FileBasedSchedulerStore;
  service: SchedulerService;
} | null = null;

export async function getSchedulerRuntime(
  options: Partial<SchedulerServiceOptions> & SchedulerExecutorOptions = {},
) {
  if (runtime) {
    return runtime;
  }

  const store = options.store instanceof FileBasedSchedulerStore
    ? options.store
    : new FileBasedSchedulerStore();

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
