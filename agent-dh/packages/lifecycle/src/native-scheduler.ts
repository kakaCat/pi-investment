/**
 * DSH 原生提醒调度器（2026-09-01，替代 os-remind-bridge.sh 链路）
 *
 * 旧链路：Agent OS cron → os-remind-bridge.sh（shell）→ OS memory 信箱 → lifecycle 60s 轮询 → followup
 * 新链路：Agent OS 注册表（payload.executor='dsh-native'）→ 本调度器按 cron 直投 followup
 *
 * 职责：
 * - 每 30s tick：拉任务注册表（60s 缓存），到点任务调用 deliver 回调投递
 * - misfire 补偿：启动时若 lastFired 之后有错过的触发，补投最近一次
 * - 状态持久化：state/native-scheduler.json 记录每任务 lastFired（重启不重投）
 *
 * 不变式：
 * - 同一任务同一分钟只投递一次（lastFired 判重）
 * - Agent OS 宕机时用缓存任务表继续运行；无缓存则静默等下轮
 * - deliver 异常不阻断其他任务（单任务失败隔离）
 */
import { parseCron, matchesCron, nextRunAfter, type ParsedCron } from './cron.js';
import type { StateStore } from './state.js';

export interface NativeTask {
  id: string;
  name: string;
  cron: string;
  prompt: string;
  window?: string;
  enabled: boolean;
  timeout?: number;
}

export interface NativeSchedulerDeps {
  /** Agent OS baseURL（注册表来源） */
  baseURL: string;
  /** 状态持久化（lastFired） */
  state: StateStore;
  /** 投递回调（由 lifecycle 注入：在线窗口 followup / 不在线创建窗口代执行） */
  deliver: (task: NativeTask, firedAt: Date) => Promise<void>;
  /** tick 间隔（默认 30s） */
  tickMs?: number;
  /** 注册表缓存时长（默认 60s） */
  cacheMs?: number;
  /** misfire 补偿窗口（默认 24h：超过一天前的漏投不补） */
  misfireWindowMs?: number;
}

interface SchedulerState {
  lastFired: Record<string, string>; // taskId → ISO 时间
}

const STATE_FILE = 'native-scheduler.json';

export class NativeReminderScheduler {
  private timer: ReturnType<typeof setInterval> | null = null;
  private cache: { tasks: NativeTask[]; fetchedAt: number } | null = null;
  private parsed = new Map<string, ParsedCron>(); // taskId+cron → 解析结果
  private state: SchedulerState;
  private running = false;

  constructor(private deps: NativeSchedulerDeps) {
    this.state = deps.state.readNamed<SchedulerState>(STATE_FILE) ?? { lastFired: {} };
  }

  start(): void {
    if (this.timer) return;
    // 启动即跑一轮（含 misfire 补偿），之后按 tickMs 周期
    this.tick(true).catch(() => {});
    this.timer = setInterval(() => {
      this.tick(false).catch(() => {});
    }, this.deps.tickMs ?? 30_000);
  }

  stop(): void {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
  }

  /** 供测试/诊断：当前缓存的任务数 */
  get cachedTaskCount(): number { return this.cache?.tasks.length ?? 0; }

  private saveState(): void {
    this.deps.state.writeNamed(STATE_FILE, this.state);
  }

  /** 从 Agent OS 拉取 dsh-native 任务（60s 缓存；失败用旧缓存） */
  private async fetchTasks(): Promise<NativeTask[]> {
    const now = Date.now();
    if (this.cache && now - this.cache.fetchedAt < (this.deps.cacheMs ?? 60_000)) {
      return this.cache.tasks;
    }
    try {
      const res = await fetch(`${this.deps.baseURL}/api/v1/scheduler/tasks?limit=200`, {
        signal: AbortSignal.timeout(10_000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: any = await res.json();
      const raw: any[] = data?.tasks ?? data?.items ?? [];
      const tasks: NativeTask[] = [];
      for (const t of raw) {
        const payload = t.payload ?? {};
        // 只接管显式标记 dsh-native 的任务；其余（webhook/脚本）不碰
        if (payload.executor !== 'dsh-native') continue;
        if (!t.cron || !payload.prompt) continue;
        tasks.push({
          id: String(t.id),
          name: String(t.name ?? t.id),
          cron: String(t.cron),
          prompt: String(payload.prompt),
          window: payload.window ? String(payload.window) : undefined,
          enabled: t.enabled !== false,
          timeout: typeof t.timeout === 'number' ? t.timeout : undefined,
        });
      }
      this.cache = { tasks, fetchedAt: now };
      return tasks;
    } catch {
      // Agent OS 宕机：用旧缓存继续；无缓存则空表等下轮
      return this.cache?.tasks ?? [];
    }
  }

  private parsedFor(task: NativeTask): ParsedCron | null {
    const key = `${task.id}:${task.cron}`;
    let p = this.parsed.get(key);
    if (!p) {
      try {
        p = parseCron(task.cron);
        this.parsed.set(key, p);
      } catch {
        return null; // 非法 cron 跳过（不阻断其他任务）
      }
    }
    return p;
  }

  private minuteKey(d: Date): string {
    // 分钟级判重键
    return new Date(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes()).toISOString();
  }

  private async tick(isStartup: boolean): Promise<void> {
    if (this.running) return; // 防重入（deliver 可能耗时）
    this.running = true;
    try {
      const tasks = await this.fetchTasks();
      const now = new Date();

      for (const task of tasks) {
        if (!task.enabled) continue;
        const cron = this.parsedFor(task);
        if (!cron) continue;

        const lastFired = this.state.lastFired[task.id]
          ? new Date(this.state.lastFired[task.id])
          : null;

        if (isStartup) {
          // misfire 补偿：lastFired（或启动前 24h）之后最近一次错过的触发 → 补投
          await this.compensate(task, cron, lastFired, now);
          continue;
        }

        // 正常路径：当前分钟匹配且未投过
        if (!matchesCron(cron, now)) continue;
        const key = this.minuteKey(now);
        if (this.state.lastFired[task.id] === key) continue;

        await this.fire(task, now, key);
      }
    } finally {
      this.running = false;
    }
  }

  private async compensate(task: NativeTask, cron: ParsedCron, lastFired: Date | null, now: Date): Promise<void> {
    // 首次运行（无 lastFired 记录）：不补投历史——历史触发已由旧链路（os-remind-bridge）
    // 执行过，补投会造成重复执行。以 now 为基线，只补偿"投过之后进程宕机错过"的场景。
    if (!lastFired) {
      this.state.lastFired[task.id] = this.minuteKey(now);
      this.saveState();
      return;
    }

    const windowMs = this.deps.misfireWindowMs ?? 24 * 3600 * 1000;
    if (now.getTime() - lastFired.getTime() >= windowMs) {
      // 超出补偿窗口：重置基线，不补投远古触发
      this.state.lastFired[task.id] = this.minuteKey(now);
      this.saveState();
      return;
    }

    // 找 lastFired 之后最近一次触发；若已过且未投 → 补投
    const next = nextRunAfter(cron, lastFired);
    if (!next || next > now) return;
    // 当前分钟的触发留给正常路径（下一轮 tick 会接住）
    if (this.minuteKey(next) === this.minuteKey(now)) return;

    const key = this.minuteKey(next);
    if (this.state.lastFired[task.id] === key) return;
    await this.fire(task, next, key);
  }

  private async fire(task: NativeTask, firedAt: Date, key: string): Promise<void> {
    try {
      await this.deps.deliver(task, firedAt);
      this.state.lastFired[task.id] = key;
    } catch {
      // 投递失败不写 lastFired——下轮 tick 会重试同一分钟键（at-least-once）
    }
    this.saveState();
  }
}
