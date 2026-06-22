/**
 * CronService - 定时任务调度器
 *
 * 移植自 claw0/s07_heartbeat_cron.py，适配 TypeScript/Node.js 环境。
 * 加载 .pi-invest/CRON.json，每秒 tick，到期则执行任务。
 *
 * 调度类型：
 *   at    - 一次性，指定 ISO 时间
 *   every - 固定间隔（秒）
 *   cron  - 5字段 cron 表达式（仅支持 minute/hour/dom/month/dow）
 *
 * 连续失败 5 次后自动禁用任务（同 claw0）。
 */
import { readFileSync, existsSync, mkdirSync, appendFileSync } from "fs";
import { join } from "path";

// ─── 类型 ───────────────────────────────────────────────────────────────────

export interface CronJobPayload {
  kind: "agent_turn" | "daily_review" | "system_event" | "stop_loss_alert" | "weekly_evolution";
  message?: string;
  text?: string;
  chatId?: string;
}

interface RawJob {
  id: string;
  name: string;
  enabled: boolean;
  schedule: { kind: "at" | "every" | "cron"; at?: string; every_seconds?: number; anchor?: string; expr?: string };
  payload: CronJobPayload;
  delete_after_run?: boolean;
}

interface CronJob {
  id: string;
  name: string;
  enabled: boolean;
  scheduleKind: "at" | "every" | "cron";
  scheduleConfig: RawJob["schedule"];
  payload: CronJobPayload;
  deleteAfterRun: boolean;
  consecutiveErrors: number;
  lastRunAt: number;  // unix seconds
  nextRunAt: number;  // unix seconds
}

// ─── 简单 cron 解析器（不依赖外部库）───────────────────────────────────────

/**
 * 解析 cron 表达式 "min hour dom mon dow" 并计算下次触发时间（本地时间）。
 * 不支持特殊字符（L, W, #），支持：* / - 和数字列表。
 */
function parseCronField(field: string, min: number, max: number): number[] {
  if (field === "*") {
    const result: number[] = [];
    for (let i = min; i <= max; i++) result.push(i);
    return result;
  }
  const values = new Set<number>();
  for (const part of field.split(",")) {
    if (part.includes("/")) {
      const [range, stepStr] = part.split("/");
      const step = parseInt(stepStr, 10);
      const [lo, hi] = range === "*" ? [min, max] : range.split("-").map(Number);
      for (let i = lo; i <= (hi ?? lo); i += step) values.add(i);
    } else if (part.includes("-")) {
      const [lo, hi] = part.split("-").map(Number);
      for (let i = lo; i <= hi; i++) values.add(i);
    } else {
      values.add(parseInt(part, 10));
    }
  }
  return [...values].sort((a, b) => a - b);
}

function cronNextRun(expr: string, afterSec: number): number {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return 0;
  const [minF, hourF, domF, monF, dowF] = parts;
  const mins  = parseCronField(minF,  0, 59);
  const hours = parseCronField(hourF, 0, 23);
  const doms  = parseCronField(domF,  1, 31);
  const mons  = parseCronField(monF,  1, 12);
  const dows  = parseCronField(dowF,  0, 6);

  // 从 afterSec + 60s 开始搜索（精度 1 分钟，最多搜索 1 年）
  const start = new Date((afterSec + 60) * 1000);
  start.setSeconds(0, 0);
  const limit = new Date(start.getTime() + 366 * 24 * 60 * 60 * 1000);

  let d = new Date(start);
  while (d < limit) {
    const mon = d.getMonth() + 1;
    const dom = d.getDate();
    const dow = d.getDay();
    const hr  = d.getHours();
    const mn  = d.getMinutes();
    if (mons.includes(mon) && doms.includes(dom) && dows.includes(dow) &&
        hours.includes(hr) && mins.includes(mn)) {
      return d.getTime() / 1000;
    }
    d = new Date(d.getTime() + 60 * 1000);
  }
  return 0;
}

// ─── CronService ─────────────────────────────────────────────────────────────

const AUTO_DISABLE_THRESHOLD = 5;

export class CronService {
  private jobs: CronJob[] = [];
  private ticker: ReturnType<typeof setInterval> | null = null;
  private runLog: string;
  private outputQueue: string[] = [];

  constructor(
    private cronFile: string,
    private piDir: string,
    private onJob: (job: CronJobPayload) => Promise<void>,
  ) {
    const cronDir = join(piDir, "cron");
    mkdirSync(cronDir, { recursive: true });
    this.runLog = join(cronDir, "cron-runs.jsonl");
    this.loadJobs();
  }

  // ── 加载 ──────────────────────────────────────────────────────────────────

  loadJobs(): void {
    this.jobs = [];
    if (!existsSync(this.cronFile)) return;
    try {
      const raw: { jobs: RawJob[] } = JSON.parse(readFileSync(this.cronFile, "utf-8"));
      const now = Date.now() / 1000;
      for (const j of raw.jobs ?? []) {
        const sched = j.schedule ?? {};
        const kind = sched.kind;
        if (!["at", "every", "cron"].includes(kind)) continue;
        const job: CronJob = {
          id: j.id ?? "",
          name: j.name ?? "",
          enabled: j.enabled !== false,
          scheduleKind: kind,
          scheduleConfig: sched,
          payload: j.payload ?? { kind: "system_event" },
          deleteAfterRun: j.delete_after_run === true,
          consecutiveErrors: 0,
          lastRunAt: 0,
          nextRunAt: 0,
        };
        job.nextRunAt = this.computeNext(job, now);
        this.jobs.push(job);
      }
    } catch (e) {
      console.warn(`[cron] CRON.json 加载失败: ${e}`);
    }
  }

  // ── 调度计算 ──────────────────────────────────────────────────────────────

  private computeNext(job: CronJob, now: number): number {
    const cfg = job.scheduleConfig;
    if (job.scheduleKind === "at") {
      try {
        const ts = new Date(cfg.at!).getTime() / 1000;
        return ts > now ? ts : 0;
      } catch { return 0; }
    }
    if (job.scheduleKind === "every") {
      const every = cfg.every_seconds ?? 3600;
      let anchor = now;
      if (cfg.anchor) {
        try { anchor = new Date(cfg.anchor).getTime() / 1000; } catch { /* ignore */ }
      }
      if (now < anchor) return anchor;
      const steps = Math.floor((now - anchor) / every) + 1;
      return anchor + steps * every;
    }
    if (job.scheduleKind === "cron") {
      const expr = cfg.expr ?? "";
      if (!expr) return 0;
      return cronNextRun(expr, now);
    }
    return 0;
  }

  // ── 定时 tick ─────────────────────────────────────────────────────────────

  start(): void {
    if (this.ticker) return;
    this.ticker = setInterval(() => { void this.tick(); }, 1000);
  }

  stop(): void {
    if (this.ticker) { clearInterval(this.ticker); this.ticker = null; }
  }

  private async tick(): Promise<void> {
    const now = Date.now() / 1000;
    const toRemove: string[] = [];
    for (const job of this.jobs) {
      if (!job.enabled || job.nextRunAt <= 0 || now < job.nextRunAt) continue;
      await this.runJob(job, now);
      if (job.deleteAfterRun && job.scheduleKind === "at") toRemove.push(job.id);
    }
    if (toRemove.length > 0) {
      this.jobs = this.jobs.filter(j => !toRemove.includes(j.id));
    }
  }

  private async runJob(job: CronJob, now: number): Promise<void> {
    let status = "ok";
    let error = "";
    let output = "";
    try {
      await this.onJob(job.payload);
      job.consecutiveErrors = 0;
    } catch (e) {
      status = "error";
      error = e instanceof Error ? e.message : String(e);
      output = `[cron error: ${error}]`;
      job.consecutiveErrors++;
      if (job.consecutiveErrors >= AUTO_DISABLE_THRESHOLD) {
        job.enabled = false;
        const msg = `任务「${job.name}」连续失败 ${job.consecutiveErrors} 次，已自动禁用`;
        console.warn(`[cron] ${msg}`);
        this.outputQueue.push(msg);
      }
    }
    job.lastRunAt = now;
    job.nextRunAt = this.computeNext(job, now);

    const entry = JSON.stringify({
      job_id: job.id, job_name: job.name,
      run_at: new Date(now * 1000).toISOString(),
      status, error: error || undefined,
      output_preview: output.slice(0, 200) || undefined,
    }, (_, v) => v === undefined ? undefined : v);
    try { appendFileSync(this.runLog, entry + "\n", "utf-8"); } catch { /* ignore */ }
  }

  // ── 状态与控制 ────────────────────────────────────────────────────────────

  listJobs(): Array<{ id: string; name: string; enabled: boolean; kind: string; nextIn: number | null; nextRun: string; errors: number }> {
    const now = Date.now() / 1000;
    return this.jobs.map(j => ({
      id: j.id, name: j.name, enabled: j.enabled, kind: j.scheduleKind,
      errors: j.consecutiveErrors,
      nextRun: j.nextRunAt > 0 ? new Date(j.nextRunAt * 1000).toLocaleString("zh-CN") : "n/a",
      nextIn: j.nextRunAt > 0 ? Math.max(0, Math.round(j.nextRunAt - now)) : null,
    }));
  }

  async triggerJob(jobId: string): Promise<string> {
    const job = this.jobs.find(j => j.id === jobId);
    if (!job) return `任务 '${jobId}' 不存在`;
    const now = Date.now() / 1000;
    await this.runJob(job, now);
    return `任务「${job.name}」已触发`;
  }

  drainOutput(): string[] {
    const items = [...this.outputQueue];
    this.outputQueue = [];
    return items;
  }
}
