// 看板数据聚合器（P1）· 2026-09-03 全量重写
// 数据链路契约基于真实 curl 打样（设计文档 §4.2）：
//   tasks/runs/themes 无 data 键、regime/platform 有 data 键、health/memory 均无 → 每端点独立 pluck
// 状态语义（§5.4）：off_day 灰 / confirmed 绿 / failed 红 / late 黄 / pending 灰白 / unknown 紫灰
// 关键修正：
//   - regime/themes 在预期快照窗口（22:10 + 30min 宽限）内展示上一交易日属 pending，绝不 late/failed
//   - memory 用真实 created_at 当日计数验证 m6（非占位）
//   - genome 目录默认 ~/.dsh-agent-dh/genome（非 agent-dh/evolution 假路径）
//   - DSH 日志取 state/launchd.{out,err}.log（非过期 profile-13080.log）
//   - task/run 匹配用 String()（task id "258" 为字符串），run 错误主载为 payload.error（兼容顶层 error）

import { promises as fsp } from 'node:fs';
import { readdirSync } from 'node:fs';
import * as path from 'node:path';
import { CHECKPOINTS } from './checkpoint-registry.js';
import { computeTaskCoverage } from '../shared/line-classify.js';
import { fetchJson, HttpError } from './http.js';
import type {
  AggregatorOptions, BlockedFlowEntry, BoardData, Checkpoint, CheckpointResult,
  ErrorEvent, HealthStatus, OrphanedTask, SchedulerRun, SchedulerTask, TimelineEntry, Verify,
} from '../types/index.js';

interface TaskRunsResult {
  tasks: SchedulerTask[];
  fetchError?: string;
  /** OS 端对账（2026-09-12）：接口返回总数与被排除原因计数，供分类对账披露 */
  osCoverage?: { apiTotal: number; byReason: Record<string, number> };
}
interface GenomeState { date?: string; missing?: boolean; statErr?: string }
/** Agent OS /api/v1/scheduler/tasks 行（6 段 cron，payload 含 executor） */
interface OsSchedulerTask {
  id?: string; name?: string; enabled?: boolean | string; schedule?: string | null;
  command?: string | null; payload?: Record<string, unknown> | null;
}
/** Agent OS /api/v1/scheduler/tasks/stats 行（today 计数缺 → 由 last_run_at 推导） */
interface OsSchedulerStat {
  name?: string; enabled?: boolean | string; total_runs?: number;
  last_run_at?: string | null; last_run_status?: string | null;
}
type GenomeMap = Record<string, GenomeState>;

function pad2(n: number): string { return String(n).padStart(2, '0'); }
function toLocalDate(d: Date): string {
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
}
function parseTs(ts: string | null | undefined): Date | null {
  if (!ts) return null;
  const t = ts.includes(' ') ? ts.replace(' ', 'T') : ts;
  const d = new Date(t);
  return Number.isNaN(d.getTime()) ? null : d;
}
function tsMs(ts: string | null | undefined): number | null {
  const d = parseTs(ts);
  return d ? d.getTime() : null;
}
function hhmmOf(d: Date | null): string {
  if (!d) return '';
  return pad2(d.getHours()) + ':' + pad2(d.getMinutes());
}
function hhmm(ts: string | null | undefined): string {
  return hhmmOf(parseTs(ts));
}
function errMsg(e: unknown): string {
  if (e instanceof HttpError) return e.message;
  if (e instanceof Error) return e.message;
  return String(e);
}
function trunc(s: string | null | undefined, n = 200): string {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : '';
}
/** v2 /api/health/db 序列化为 Python repr（单引号 + True/None），非法 JSON → 容错解析 */
function looseJson(text: string): Record<string, unknown> | null {
  try { return JSON.parse(text); } catch { /* fall through */ }
  try {
    const fixed = text
      .replace(/True/g, 'true')
      .replace(/False/g, 'false')
      .replace(/None/g, 'null')
      .replace(/'/g, '"');
    return JSON.parse(fixed);
  } catch { return null; }
}
/** cron dow 语义：expectDays "1-5" / "0" / "6" / "0-6"，dayOfWeek 0=周日 */
function matchesDayPattern(dayOfWeek: number, pattern: string): boolean {
  if (pattern === '0-6') return true;
  const parts = pattern.split('-');
  if (parts.length === 2) {
    const a = parseInt(parts[0], 10);
    const b = parseInt(parts[1], 10);
    return dayOfWeek >= a && dayOfWeek <= b;
  }
  return dayOfWeek === parseInt(pattern, 10);
}
/** cron 前两位 minute hour → "HH:mm"（无法解析返回 undefined） */
function parseCronTime(cronExpr: string | null | undefined): string | undefined {
  if (!cronExpr) return undefined;
  const parts = cronExpr.trim().split(/\s+/);
  if (parts.length < 2) return undefined;
  const minute = parts[0];
  const hour = parts[1];
  if (!/^\d+$/.test(minute) || !/^\d+$/.test(hour)) return undefined;
  return pad2(parseInt(hour, 10)) + ':' + pad2(parseInt(minute, 10));
}
/** timeline 频率分桶：日执行（* 或每周 >=4 天） vs 周执行（每周固定 <=3 天） */
function cronFreq(cronExpr: string | null | undefined): 'daily' | 'weekly' {
  if (!cronExpr) return 'daily';
  const parts = cronExpr.trim().split(/\s+/);
  if (parts.length < 5) return 'daily';
  const dow = parts[4];
  if (dow === '*' || dow === '?') return 'daily';
  const days = new Set<number>();
  for (const seg of dow.split(',')) {
    const m = /^(\d+)(?:-(\d+))?$/.exec(seg);
    if (!m) return 'daily';
    const a = Number(m[1]);
    if (m[2]) { const b = Number(m[2]); for (let d = a; d <= b; d++) days.add(d % 7); }
    else days.add(a % 7);
  }
  return days.size >= 4 ? 'daily' : 'weekly';
}
/** cron dow 今日是否命中（与 checkpoint matchesDayPattern 同口径，0=周日）。
 *  返回 undefined 表示 '*','?' 或无法解析（视为每日命中，不判非执行日）。 */
function cronDowMatchToday(cronExpr: string | null | undefined, weekday: number): boolean | undefined {
  if (!cronExpr) return undefined;
  const parts = cronExpr.trim().split(/\s+/);
  if (parts.length < 5) return undefined;
  const dow = parts[4];
  if (dow === '*' || dow === '?') return undefined;
  for (const seg of dow.split(',')) {
    const m = /^(\d+)(?:-(\d+))?$/.exec(seg);
    if (!m) return undefined;
    const a = Number(m[1]) % 7;
    const b = m[2] ? Number(m[2]) % 7 : a;
    if (b < a) return undefined;
    for (let d = a; d <= b; d++) if (d % 7 === weekday) return true;
  }
  return false;
}
/** Agent OS cron 为 6 段（前导秒 "0"）→ 归一到 5 段 v2 式；无法归一返回 undefined */
function osCron5(expr: string | null | undefined): string | undefined {
  if (!expr) return undefined;
  const parts = expr.trim().split(/\s+/);
  if (parts.length === 6 && parts[0] === '0') parts.shift(); // 去掉前导秒
  return parts.length === 5 ? parts.join(' ') : undefined;
}
/** expectTime + graceMinutes 后的绝对 deadline（今日） */
function deadlineDate(now: Date, expectTime: string, graceMinutes: number): Date {
  const seg = expectTime.split(':');
  const h = Number(seg[0]) || 0;
  const m = Number(seg[1]) || 0;
  const d = new Date(now);
  d.setHours(h, m, 0, 0);
  return new Date(d.getTime() + graceMinutes * 60 * 1000);
}
// ================= 错误事件映射（Agent OS error_events 行 → ErrorEvent） =================
/** os 采集行 msg 常为通用文案（如 "Scheduled task execution failed"），真实错误在 detail.error —— 提炼合并 */
function errorLine(row: Record<string, unknown>): string {
  const msg = String(row.msg ?? '').trim();
  const det = typeof row.detail === 'string' ? row.detail.trim() : '';
  if (msg && msg.length < 60 && det.length > 0) {
    try {
      const o: any = JSON.parse(det);
      const e = o && typeof o === 'object' ? (o.error ?? o.err ?? o.message ?? o.msg) : null;
      if (typeof e === 'string' && e.length > 0) return msg + ' · ' + e.slice(0, 200);
    } catch { /* detail 非 JSON，忽略 */ }
  }
  if (msg) return msg;
  return det ? det.slice(0, 300) : String(row.id ?? '未知错误');
}
function errorFile(row: Record<string, unknown>): string {
  const md: any = row.metadata;
  const lp = md && typeof md === 'object' ? md.log_path : null;
  if (typeof lp === 'string' && lp) {
    const i = lp.lastIndexOf('/');
    return i >= 0 ? lp.slice(i + 1) : lp;
  }
  return row.task_name ? String(row.task_name) : String(row.source ?? 'log');
}
export function errorEventRowToView(row: Record<string, any>): ErrorEvent {
  const status = (['open', 'processing', 'resolved', 'ignored'] as const).includes(row.status) ? row.status : 'open';
  const source = (['v2', 'os', 'dsh', 'pg'] as const).includes(row.source) ? row.source : 'os';
  const seenAt: string = row.last_seen_at ?? row.first_seen_at ?? '';
  return {
    id: String(row.id),
    source,
    status,
    occurrenceCount: Number(row.occurrence_count ?? 1),
    firstSeenAt: row.first_seen_at ?? undefined,
    lastSeenAt: row.last_seen_at ?? undefined,
    level: row.level ?? undefined,
    msg: row.msg ?? undefined,
    detail: row.detail ?? null,
    taskName: row.task_name ?? null,
    taskId: row.task_id ?? null,
    assignee: row.assignee ?? null,
    dispatchedSession: row.dispatched_session ?? null,
    resolvedAt: row.resolved_at ?? null,
    resolutionNote: row.resolution_note ?? null,
    metadata: row.metadata ?? null,
    timestamp: seenAt || undefined,          // solve-kit 兼容：最近出现时间
    line: errorLine(row),                    // solve-kit 兼容：错误摘要（一行）
    file: errorFile(row),                    // solve-kit 兼容：来源文件/任务名
  };
}

/**
 * OS 任务是否应并入看板（= 是否真的唤醒 agent）。纯函数，便于回归。
 *
 * 判据（2026-09-12 修正，w-c8cae280）——**以 webhook_url 指向 DSH（/agent-os-trigger）为准**：
 * 该地址就是"投递到 DSH 唤醒 agent"的直接证据，而 `payload.executor` 只是**部分任务才写的字段**。
 * 修正前的判据只看 executor → 把 pre-market-routine / post-market-routine-live /
 * intraday-surge-scan-am/pm 这类"靠 webhook_url 投递、payload 里没有 executor"的任务
 * **静默过滤掉**，于是「今日时间轴」少了当天最该出现的例程（用户报"展示不对"的根因）。
 *
 * 仍排除：①disabled ②无任何 webhook 的任务（如 equity-snapshot-daily，纯脚本不唤醒 agent）
 * ③指向 v2 内部 webhook（:5001/…）的任务 —— 它们由 v2 侧展示，并入会与 v2 scheduler 双计。
 */
export type OsExclusionReason = 'disabled' | 'v2_internal' | 'no_webhook';

/** 不并入的原因（null=应并入）。与 shouldIncludeOsTask 同源，供"对账"显式披露被排除者 */
export function osTaskExclusionReason(t: {
  enabled?: unknown; payload?: unknown; webhook_url?: unknown;
}): OsExclusionReason | null {
  const enabled = t.enabled === true || t.enabled === 'true' || t.enabled === 1 || t.enabled === '1';
  if (!enabled) return 'disabled';
  const webhookUrl = String(t.webhook_url ?? '');
  if (webhookUrl.includes(':5001/')) return 'v2_internal';       // v2 内部：避免双计
  const executor = String((t.payload as Record<string, unknown> | null | undefined)?.executor ?? '');
  if (executor === 'dsh-webhook') return null;
  return webhookUrl.includes('/agent-os-trigger') ? null : 'no_webhook';
}

export function shouldIncludeOsTask(t: {
  enabled?: unknown; payload?: unknown; webhook_url?: unknown;
}): boolean {
  return osTaskExclusionReason(t) === null;
}

export class DataAggregationService {
  private readonly opts: AggregatorOptions;
  private readonly now: Date;
  private readonly today: string;
  private readonly weekday: number;
  private readonly v2Base: string;
  private readonly osBase: string;

  constructor(opts: AggregatorOptions) {
    this.opts = { requestTimeoutMs: 4000, ...opts };
    this.now = new Date();
    this.today = toLocalDate(this.now);
    this.weekday = this.now.getDay();
    this.v2Base = opts.v2BaseURL.replace(/\/$/, '');
    this.osBase = opts.osBaseURL.replace(/\/$/, '');
  }

  async fetchBoardData(): Promise<BoardData> {
    const degraded: Array<{ source: string; error: string }> = [];

    // 各数据路全部并行；单路失败只进 degraded，绝不整体 500
    const [healthR, tasksR, runsR, regimeR, themesR, memoryR, genomeR, orphanedR, refluxR] = await Promise.all([
      this.fetchHealthRows(degraded),
      this.fetchTasks(),
      this.fetchRuns(),
      this.fetchRegime(),
      this.fetchThemes(),
      this.fetchMemoryToday(),
      this.fetchGenomeState(),
      this.fetchOrphanedTasks(),
      this.fetchRefluxRead(),
    ]);

    const v2Available = healthR.v2Available;
    for (const [key, val] of Object.entries({
      'scheduler-runs': runsR.error, regime: regimeR.error, themes: themesR.error,
      memory: memoryR.error, genome: genomeR.error, orphaned: orphanedR.error,
      reflux: refluxR.error,
    })) {
      if (val) degraded.push({ source: key, error: val });
    }

    const checkpoints = this.verifyAllCheckpoints(v2Available, tasksR, runsR.runs, {
      regimeLatest: regimeR.latest, themesLatest: themesR.latest, memoryToday: memoryR.count,
      refluxRead: refluxR.read, refluxHasRecord: refluxR.hasRecord, refluxLessonCoverage: refluxR.lessonCoverage,
    }, genomeR.state);
    const timeline = this.buildTimeline(tasksR.tasks, runsR.runs);
    const blockedFlows = this.buildBlockedFlows(checkpoints);
    // 错误事件已解耦为独立分页子端点（/dashboard/api/board/error-events），主 board 不再内嵌
    const tasks = this.enrichTasks(tasksR.tasks, runsR.runs);
    // 分类对账（2026-09-12）：分类字段是否已打通 / 有无未归类 / OS 端并入是否完整
    const osCov = tasksR.osCoverage;
    const osIncluded = tasks.filter(t => t.src === 'os').length;
    const taskCoverage = computeTaskCoverage(tasks, osCov ? {
      apiTotal: osCov.apiTotal,
      included: osIncluded,
      excluded: osCov.apiTotal - osIncluded,
      byReason: osCov.byReason,
    } : undefined);

    return {
      health: healthR.rows,
      checkpoints,
      tasks,
      taskCoverage,
      timeline,
      blockedFlows,
      degraded,
      v2Available,
      fetchedAt: new Date().toISOString(),
      orphanedTasks: orphanedR.tasks ?? [],
    };
  }

  // ================= Health（4 行，并行探测） =================
  private async fetchHealthRows(degraded: Array<{ source: string; error: string }>): Promise<{ rows: HealthStatus[]; v2Available: boolean }> {
    const t = this.opts.requestTimeoutMs ?? 4000;
    const v2 = this.v2Base;
    const os = this.osBase;
    const started = Date.now();

    const probe = async <T>(fn: () => Promise<T>) => {
      const s = Date.now();
      try {
        return { ok: true as const, value: await fn(), ms: Date.now() - s };
      } catch (e) {
        return { ok: false as const, error: errMsg(e), ms: Date.now() - s };
      }
    };

    const [v2H, dbH, platH, osH] = await Promise.all([
      probe(() => fetchJson<{ status?: string }>(v2 + '/api/health', { timeoutMs: t })),
      probe(() => fetchJson<{ status?: string }>(v2 + '/api/health/db', { timeoutMs: t }).catch(async () => {
        const res = await fetch(v2 + '/api/health/db', { signal: AbortSignal.timeout(t) });
        const txt = await res.text();
        return looseJson(txt) as { status?: string };
      })),
      probe(() => fetchJson<{ success?: boolean; data?: any }>(v2 + '/api/health/platform/status', { timeoutMs: t }).then(j => j?.data)),
      probe(() => fetchJson<{ status?: string }>(os + '/health', { timeoutMs: t })),
    ]);

    const rows: HealthStatus[] = [];
    let v2Available = false;
    const totalMs = Date.now() - started;

    if (v2H.ok && v2H.value?.status === 'ok') {
      v2Available = true;
      const dbOk = dbH.ok && dbH.value?.status === 'healthy';
      const p = platH.ok ? (platH.value as any) : undefined;
      const platDb = p?.db_connected;
      const dbKnownBad = (platH.ok && platDb === false) || (!platH.ok && !dbH.ok);
      const dbMetric = dbH.ok ? dbH.value.status : (platH.ok ? String(platDb) : 'unreachable');
      rows.push({
        name: 'quantsys-v2',
        status: dbKnownBad ? 'degraded' : 'ok',
        port: 5001,
        metrics: {
          api: v2H.value.status,
          db: dbMetric,
          db_connected: p?.db_connected,
          holdings_count: p?.holdings_count,
          model_loaded: p?.model_loaded,
          balance_date: p?.balance?.balance_date,
          total_assets: p?.balance?.total_assets,
        },
        responseTimeMs: v2H.ms,
        error: dbKnownBad ? (platH.ok && platDb === false ? 'db_connected=false' : 'db health 不可用') : undefined,
      });
    } else {
      rows.push({ name: 'quantsys-v2', status: 'failed', port: 5001, responseTimeMs: v2H.ms, error: v2H.error });
      degraded.push({ source: 'v2', error: v2H.error });
    }

    // agent-os（v1 遗留，:8080）
    if (osH.ok && osH.value?.status === 'ok') {
      rows.push({ name: 'agent-os', status: 'ok', port: 8080, metrics: { status: osH.value.status }, responseTimeMs: osH.ms });
    } else {
      rows.push({ name: 'agent-os', status: 'failed', port: 8080, responseTimeMs: osH.ms, error: osH.error });
    }

    // postgres：由 v2 platform/status.db_connected 代理（不直连 PG，设计文档 §6.1）
    if (!v2Available) {
      rows.push({ name: 'postgres', status: 'failed', metrics: { via: 'v2 platform/status' }, error: 'v2 不可达，无法取 db_connected' });
    } else if (platH.ok) {
      const p = platH.value as any;
      rows.push({
        name: 'postgres',
        status: p?.db_connected === true ? 'ok' : 'failed',
        metrics: { db_connected: p?.db_connected, via: 'v2 platform/status' },
        responseTimeMs: platH.ms,
        error: p?.db_connected === false ? 'db_connected=false → 查 v2 /api/health/db' : undefined,
      });
    } else {
      rows.push({ name: 'postgres', status: 'degraded', metrics: { via: 'v2 platform/status' }, responseTimeMs: platH.ms, error: platH.error });
    }

    // agent-dh：同进程（uptime / 内存 / 重启计数）
    const mem = process.memoryUsage();
    let restarts = 0;
    try {
      const names = readdirSync(this.opts.profileStateDir);
      restarts = names.filter(n => /^restart-.*\.log$/.test(n)).length;
    } catch { /* state 目录缺失/无权限时按 0 处理 */ }
    rows.push({
      name: 'agent-dh',
      status: 'ok',
      port: 13080,
      metrics: {
        uptime_s: Math.floor(process.uptime()),
        rss_mb: Math.round(mem.rss / 1024 / 1024),
        heap_mb: Math.round(mem.heapUsed / 1024 / 1024),
        probe_ms: totalMs,
        restarts,
      },
      responseTimeMs: totalMs,
    });

    return { rows, v2Available };
  }
  // ================= Scheduler 取数 =================
  private async fetchTasks(): Promise<TaskRunsResult> {
    // 双路并行：v2 引擎任务 + Agent OS 调 agent 的任务；任一失败只降级不整体 500
    let v2Tasks: SchedulerTask[] = [];
    let v2Error: string | undefined;
    try {
      const json = await fetchJson<{ success?: boolean; tasks?: SchedulerTask[] }>(this.v2Base + '/api/scheduler/tasks?pageSize=200');
      const tasks = Array.isArray(json?.tasks) ? json.tasks : [];
      v2Tasks = tasks.map(t => this.normalizeTask(t, 'v2'));
    } catch (e) {
      v2Error = errMsg(e);
    }
    const os = await this.fetchOsAgentTasks();
    if (v2Error && os.tasks.length === 0) return { tasks: [], fetchError: v2Error, osCoverage: os.coverage };
    if (v2Error) return { tasks: os.tasks, fetchError: v2Error, osCoverage: os.coverage };
    return { tasks: [...v2Tasks, ...os.tasks], osCoverage: os.coverage };
  }

  private normalizeTask(t: SchedulerTask, src: 'v2' | 'os' = 'v2'): SchedulerTask {
    const enabled = t.enabled === true || t.enabled === 'true' || t.enabled === 1 || t.enabled === '1';
    const num = (v: unknown): number | undefined => {
      if (v === undefined || v === null) return undefined;
      const n = Number(v);
      return Number.isNaN(n) ? undefined : n;
    };
    return {
      ...t, id: String(t.id), enabled, src, agentCall: src === 'os' ? undefined : 'none',
      // 分类字段透传（2026-09-12）：接口暴露后即成为分类首选依据；未暴露时保持 undefined
      agentLine: (t as { agentLine?: string | null }).agentLine ?? null,
      domain: (t as { domain?: string | null }).domain ?? null,
      todaySuccess: num(t.todaySuccess), todayTriggered: num(t.todayTriggered),
    };
  }

  /**
   * Agent OS 中"真正调用 agent"的定时任务并入看板：src=os / agentCall=dh。
   * 入选判据见上方 shouldIncludeOsTask（2026-09-12 修正：以 webhook 指向 DSH 为准）。
   * 无 v2 run：今日状态由 /tasks/stats 的 last_run_at / last_run_status 推导（Agent OS 无 today 计数）。
   * 注：间隔型 cron（例如每 30 分钟一次）经 osCron5 拿不到单一时刻 → 不进时间轴（无法定位在时间轴上）。
   */
  private async fetchOsAgentTasks(): Promise<{
    tasks: SchedulerTask[];
    coverage?: { apiTotal: number; byReason: Record<string, number> };
    error?: string;
  }> {
    try {
      const [listJ, statJ] = await Promise.all([
        fetchJson<{ success?: boolean; tasks?: OsSchedulerTask[] }>(this.osBase + '/api/v1/scheduler/tasks'),
        fetchJson<{ success?: boolean; tasks?: OsSchedulerStat[] }>(this.osBase + '/api/v1/scheduler/tasks/stats'),
      ]);
      const stats = new Map<string, OsSchedulerStat>(
        (Array.isArray(statJ?.tasks) ? statJ.tasks : []).map(s => [String(s.name), s]),
      );
      const out: SchedulerTask[] = [];
      // 对账（2026-09-12）：把"被排除的对象与原因"计数，供页面显式披露——静默 continue 会让
      // "少了东西"永远只能靠人眼发现（本次时间轴缺例程即因此长期无人知）。
      const all = Array.isArray(listJ?.tasks) ? listJ.tasks : [];
      const byReason: Record<string, number> = {};
      const bump = (k: string) => { byReason[k] = (byReason[k] ?? 0) + 1; };
      for (const t of all) {
        const name = String(t.name ?? '');
        if (!name) { bump('no_name'); continue; }
        const why = osTaskExclusionReason(t);
        if (why) { bump(why); continue; }   // 判据见 osTaskExclusionReason 注释
        const expr5 = osCron5(String(t.schedule ?? ''));
        if (!expr5) { bump('unparsable_time'); continue; } // 区间型 cron 无单一时刻 → 不进时间轴
        const st = stats.get(name);
        const lastAt = st?.last_run_at ? String(st.last_run_at) : null;
        const lastStatus = String(st?.last_run_status ?? '');
        const ranToday = lastAt ? toLocalDate(parseTs(lastAt)) === this.today : false;
        out.push({
          id: 'os:' + name,
          name,
          enabled: true,
          scheduleExpr: expr5,
          payload: { command: String(t.command ?? '') || name },
          lastRun: lastStatus ? { status: lastStatus, triggeredAt: lastAt ?? undefined } : null,
          nextRunAt: null,
          src: 'os',
          agentCall: 'dh', // executor=dsh-webhook 当前只唤醒 agent-dh（agent-ts 已并入 v2 引擎）
          // 任务自带业务线字段（DB public.tasks.agent_line）；接口未暴露时为 null → 分类回退名单
          agentLine: (t as { agent_line?: string | null }).agent_line
            ?? (t as { agentLine?: string | null }).agentLine ?? null,
          todayTriggered: ranToday ? 1 : 0,
          todaySuccess: ranToday && lastStatus === 'success' ? 1 : 0,
        });
      }
      out.sort((a, b) => String(a.name).localeCompare(String(b.name)));
      return { tasks: out, coverage: { apiTotal: all.length, byReason } };
    } catch (e) {
      return { tasks: [], error: errMsg(e) };
    }
  }

  private async fetchRuns(): Promise<{ runs: SchedulerRun[]; error?: string }> {
    try {
      const json = await fetchJson<{ success?: boolean; runs?: SchedulerRun[] }>(this.v2Base + '/api/scheduler/runs?pageSize=300');
      const runs = Array.isArray(json?.runs) ? json.runs : [];
      runs.sort((a, b) => (tsMs(b.triggeredAt) ?? 0) - (tsMs(a.triggeredAt) ?? 0));
      return { runs };
    } catch (e) {
      return { runs: [], error: errMsg(e) };
    }
  }

  // 当日该任务的运行（按时间倒序）；run 无 taskId 时回退按 taskName 匹配
  private todayRunsFor(task: SchedulerTask, runs: SchedulerRun[]): SchedulerRun[] {
    const all = runs.filter(r => {
      const byId = String(r.taskId) === String(task.id);
      const byName = (r.taskId === undefined || r.taskId === null || String(r.taskId) === '') && r.taskName === task.name;
      if (!(byId || byName)) return false;
      const d = parseTs(r.triggeredAt);
      return d ? toLocalDate(d) === this.today : String(r.triggeredAt).startsWith(this.today);
    });
    all.sort((a, b) => (tsMs(b.triggeredAt) ?? 0) - (tsMs(a.triggeredAt) ?? 0));
    return all;
  }

  private latestRunFor(task: SchedulerTask, runs: SchedulerRun[]): SchedulerRun | undefined {
    const all = runs
      .filter(r => String(r.taskId) === String(task.id) || r.taskName === task.name)
      .sort((a, b) => (tsMs(b.triggeredAt) ?? 0) - (tsMs(a.triggeredAt) ?? 0));
    return all[0];
  }

  private runError(r: SchedulerRun | undefined): string | undefined {
    if (!r) return undefined;
    return trunc((r.error || r.payload?.error) as string | undefined, 200);
  }

  private enrichTasks(tasks: SchedulerTask[], runs: SchedulerRun[]): SchedulerTask[] {
    return tasks.map(t => {
      const latest = this.latestRunFor(t, runs);
      return { ...t, lastRun: latest ? { status: latest.status, triggeredAt: latest.triggeredAt, error: this.runError(latest) } : (t.lastRun ?? null) };
    });
  }

  // ================= Checkpoints（registry × 状态机；数量以 checkpoint-registry.ts 为准） =================
  private verifyAllCheckpoints(
    v2Available: boolean,
    tasksResult: TaskRunsResult,
    runs: SchedulerRun[],
    vs: { regimeLatest?: string; themesLatest?: string; memoryToday?: number; refluxRead?: boolean | null; refluxHasRecord?: boolean; refluxLessonCoverage?: number | null },
    genome: GenomeMap,
  ): CheckpointResult[] {
    return CHECKPOINTS.map(cp => {
      try {
        return this.verifyOne(cp, v2Available, tasksResult, runs, vs, genome);
      } catch (e) {
        return { id: cp.id, line: cp.line, module: cp.module, name: cp.name, status: 'unknown', message: errMsg(e), blocksFlow: cp.blocksFlow, expectTime: cp.expectTime };
      }
    });
  }

  private verifyOne(
    cp: Checkpoint,
    v2Available: boolean,
    tasksResult: TaskRunsResult,
    runs: SchedulerRun[],
    vs: { regimeLatest?: string; themesLatest?: string; memoryToday?: number; refluxRead?: boolean | null; refluxHasRecord?: boolean; refluxLessonCoverage?: number | null },
    genome: GenomeMap,
  ): CheckpointResult {
    const base = { id: cp.id, line: cp.line, module: cp.module, name: cp.name, blocksFlow: cp.blocksFlow, expectTime: cp.expectTime };

    // 今日不在预期执行日 → off_day（灰，非异常）
    if (!matchesDayPattern(this.weekday, cp.expectDays)) {
      return { ...base, status: 'off_day', message: '今日非执行日' };
    }
    const deadline = deadlineDate(this.now, cp.expectTime, cp.graceMinutes);
    const deadlinePassed = this.now.getTime() > deadline.getTime();

    // v2 依赖且 v2 不可达 → unknown（紫灰降级保护，防误报"业务没跑"）
    const vt = cp.verify.type;
    if (!v2Available && (vt === 'scheduler_task' || vt === 'v2_regime' || vt === 'v2_themes' || vt === 'v2_memory_kind' || vt === 'decision_reflux_read')) {
      return { ...base, status: 'unknown', message: 'v2 不可达（降级保护）' };
    }

    if (vt === 'scheduler_task') {
      const v = cp.verify as Extract<Verify, { type: 'scheduler_task' }>;
      if (tasksResult.fetchError) {
        return { ...base, status: 'unknown', message: '任务列表获取失败' };
      }
      const task = tasksResult.tasks.find(t => t.name === v.taskName);
      if (!task) {
        return { ...base, status: 'unknown', message: '任务不存在: ' + v.taskName };
      }
      const todayRuns = this.todayRunsFor(task, runs);
      if (todayRuns.length > 0) {
        const latest = todayRuns[0];
        if (latest.status === 'failed') {
          return { ...base, status: 'failed', message: trunc(this.runError(latest) || '执行失败', 200) };
        }
        if (latest.status === 'success') {
          const hm = hhmm(latest.triggeredAt);
          return {
            ...base,
            status: 'confirmed',
            message: '今日已完成' + (hm ? ' ' + hm : '') + (latest.durationMs ? ' (' + latest.durationMs + 'ms)' : ''),
          };
        }
      }
      // 今日尚无 run → 窗口判定
      if (deadlinePassed) {
        const latest = this.latestRunFor(task, runs);
        const lastTxt = latest ? '（最近 ' + trunc(String(latest.triggeredAt), 30) + ' ' + latest.status + '）' : '';
        return { ...base, status: 'late', message: '超时未执行' + lastTxt };
      }
      return { ...base, status: 'pending', message: '等待 ' + cp.expectTime + ' 执行' };
    }

    if (vt === 'v2_regime' || vt === 'v2_themes') {
      const latest = vt === 'v2_regime' ? vs.regimeLatest : vs.themesLatest;
      if (latest === this.today) {
        return { ...base, status: 'confirmed', message: '已落库 trade_date=' + latest };
      }
      if (!this.isPastExpectTime(cp.expectTime)) {
        return { ...base, status: 'pending', message: '等待今日 ' + cp.expectTime + ' 快照' + (latest ? '（当前最近 ' + latest + '）' : '') };
      }
      if (deadlinePassed) {
        return { ...base, status: 'late', message: '今日未落库（最近 ' + (latest || '无数据') + '）' };
      }
      return { ...base, status: 'pending', message: '等待快照落库（当前最近 ' + (latest || '无数据') + '）' };
    }

    if (vt === 'v2_memory_kind') {
      const n = vs.memoryToday ?? 0;
      if (n > 0) return { ...base, status: 'confirmed', message: '今日新增 ' + n + ' 条 experience' };
      if (deadlinePassed) return { ...base, status: 'late', message: '今日无新增 experience 经验' };
      return { ...base, status: 'pending', message: '等待 ' + cp.expectTime + ' 蒸馏' };
    }

    if (vt === 'genome_file') {
      const v = cp.verify as Extract<Verify, { type: 'genome_file' }>;
      const gs = genome[v.file];
      if (!gs) return { ...base, status: 'unknown', message: 'genome 状态缺失' };
      if (gs.statErr) {
        if (deadlinePassed) return { ...base, status: 'late', message: gs.statErr };
        return { ...base, status: 'pending', message: '等待 ' + cp.expectTime + '（' + gs.statErr + '）' };
      }
      if (gs.date === this.today) {
        return { ...base, status: 'confirmed', message: '今日已更新（mtime 当日）' };
      }
      if (deadlinePassed) {
        return { ...base, status: 'late', message: '今日未更新' + (gs.date ? '（最近 ' + gs.date + '）' : '') };
      }
      return { ...base, status: 'pending', message: '等待 ' + cp.expectTime + (gs.date ? '（最近 ' + gs.date + '）' : '') };
    }

    if (vt === 'decision_reflux_read') {
      const read = vs.refluxRead;
      if (read === null || read === undefined) {
        if (!this.isPastExpectTime(cp.expectTime)) return { ...base, status: 'pending', message: '等待今日盘前分析（' + cp.expectTime + '）' };
        if (!deadlinePassed) return { ...base, status: 'pending', message: '等待盘前分析落库' };
        if (vs.refluxHasRecord) {
          // 落库了却没写 attribution_read —— 纪律未生效，是断链而非"没跑"
          return { ...base, status: 'failed', message: '盘前分析已落库但未写 attribution_read 字段（回流纪律未生效，需检查例程指令是否含第⑧步）' };
        }
        return { ...base, status: 'late', message: '今日无盘前分析决策记录 → 无法确认回流边是否被消费' };
      }
      if (read === true) {
        const lc = vs.refluxLessonCoverage;
        return { ...base, status: 'confirmed', message: '今日分析已读回流产出（attribution_read=true）' + (typeof lc === 'number' ? '，教训覆盖率 ' + lc : '') };
      }
      return { ...base, status: 'failed', message: '回流边断链：今日分析 attribution_read=false（未读昨日归因/决策评分）' };
    }

    return { ...base, status: 'unknown', message: '未实现的验证类型: ' + vt };
  }

  private isPastExpectTime(expectTime: string): boolean {
    const seg = expectTime.split(':');
    const d = new Date(this.now);
    d.setHours(Number(seg[0]) || 0, Number(seg[1]) || 0, 0, 0);
    return this.now.getTime() >= d.getTime();
  }
  // ================= v2 数据日期 / memory / genome =================
  private async fetchRegime(): Promise<{ ok: boolean; latest?: string; error?: string }> {
    try {
      const json = await fetchJson<{ success?: boolean; data?: Array<{ trade_date?: string }> }>(this.v2Base + '/api/market/perception/regime');
      const arr = Array.isArray(json?.data) ? json.data : [];
      return { ok: true, latest: arr.find(x => x && x.trade_date)?.trade_date };
    } catch (e) {
      return { ok: false, error: errMsg(e) };
    }
  }

  private async fetchThemes(): Promise<{ ok: boolean; latest?: string; error?: string }> {
    try {
      const json = await fetchJson<{ success?: boolean; trade_date?: string }>(this.v2Base + '/api/market/perception/themes');
      return { ok: true, latest: json?.trade_date };
    } catch (e) {
      return { ok: false, error: errMsg(e) };
    }
  }

  private async fetchMemoryToday(): Promise<{ ok: boolean; count?: number; error?: string }> {
    try {
      const json = await fetchJson<{ items?: Array<{ created_at?: string }> }>(
        this.v2Base + '/api/memory/search?namespace=experience&limit=100'
      );
      const items = Array.isArray(json?.items) ? json.items : [];
      const count = items.filter(it => {
        if (!it?.created_at) return false;
        const d = parseTs(it.created_at);
        return d ? toLocalDate(d) === this.today : it.created_at.startsWith(this.today);
      }).length;
      return { ok: true, count };
    } catch (e) {
      return { ok: false, error: errMsg(e) };
    }
  }

  /**
   * REQ-9bcd0a WP3/WP6②：今日盘前分析是否消费了回流产出。
   * 读 decision_audit 中 decision_type=morning_analysis 的当日记录，取 context.attribution_read。
   * 三态：true=已读 / false=断链 / null=今日尚未落库（区分"没做"与"做了但没读"）。
   */
  private async fetchRefluxRead(): Promise<{ ok: boolean; read?: boolean | null; hasRecord?: boolean; lessonCoverage?: number | null; error?: string }> {
    try {
      const json = await fetchJson<{ success?: boolean; data?: Array<{ created_at?: string; context?: Record<string, unknown> }> }>(
        this.v2Base + '/api/decisions/history?decision_type=morning_analysis&limit=20'
      );
      const rows = Array.isArray(json?.data) ? json.data : [];
      const todayRow = rows.find(r => {
        if (!r?.created_at) return false;
        const d = parseTs(r.created_at);
        return d ? toLocalDate(d) === this.today : r.created_at.startsWith(this.today);
      });
      if (!todayRow) return { ok: true, read: null, hasRecord: false };
      const ctx = (todayRow.context ?? {}) as Record<string, unknown>;
      const raw = ctx['attribution_read'];
      const read = raw === true || raw === 'true' ? true : raw === false || raw === 'false' ? false : null;
      const lc = ctx['scores_lesson_coverage'];
      // hasRecord 用于区分两种都表现为 read=null 的情况：
      //   false = 盘前分析根本没落库（流程没跑）
      //   true  = 落库了但没写 attribution_read（纪律未生效 —— 是断链，不是没跑）
      // 二者排查方向完全不同，不可合并（2026-09-12 review 修正）。
      return { ok: true, read, hasRecord: true, lessonCoverage: typeof lc === 'number' ? lc : null };
    } catch (e) {
      return { ok: false, error: errMsg(e) };
    }
  }

  private async fetchGenomeState(): Promise<{ state: GenomeMap; error?: string }> {
    const files = ['candidates.json', 'genome.json'];
    const state: GenomeMap = {};
    let error: string | undefined;
    for (const file of files) {
      const fp = path.join(this.opts.genomeDir, file);
      try {
        const st = await fsp.stat(fp);
        const d = st.mtime;
        state[file] = { date: toLocalDate(d) };
      } catch {
        state[file] = { missing: true, statErr: file + ' 文件缺失（' + this.opts.genomeDir + '）' };
      }
    }
    if (!state['candidates.json']?.date && !state['genome.json']?.date) {
      error = 'genome 目录不可读: ' + this.opts.genomeDir;
    }
    return { state, error };
  }

  // ================= Timeline（当日 cron 底本 + 当日 run 状态） =================
  // ⏱ 时间口径（用户 2026-09-05 确认 · 全看板统一）：展示时间 = cron 计划时刻，几点就几点。
  //    expectedTime 恒取 scheduleExpr 前两位（分:时 → "HH:mm"），run 状态只标注"当日是否真的跑过/结果如何"，
  //    绝不用实际触发时刻 lastRun.triggeredAt 覆盖展示；实际触发时刻仅供任务表「上次运行」列补充参考。
  private buildTimeline(tasks: SchedulerTask[], runs: SchedulerRun[]): TimelineEntry[] {
    const list: TimelineEntry[] = [];
    for (const task of tasks) {
      const expectedTime = parseCronTime(task.scheduleExpr);
      if (!expectedTime) continue;
      const todayRuns = this.todayRunsFor(task, runs);
      let status: TimelineEntry['status'] = 'pending';
      let runId: number | string | undefined;
      let error: string | undefined;
      if (todayRuns.length > 0) {
        const latest = todayRuns[0];
        runId = latest.id;
        if (latest.status === 'success') status = 'success';
        else if (latest.status === 'failed') {
          status = 'failed';
          error = this.runError(latest);
        } else status = 'unknown';
      } else if (task.src === 'os') {
        // Agent OS 任务无 v2 run：用 OS stats 最近运行推导今日状态
        const lr = task.lastRun;
        const lrs = lr && typeof lr === 'object' ? String((lr as { status?: unknown }).status ?? '') : '';
        const lra = lr && typeof lr === 'object' ? String((lr as { triggeredAt?: unknown }).triggeredAt ?? '') : '';
        const d = lra ? parseTs(lra) : null;
        if (d && toLocalDate(d) === this.today) {
          if (lrs === 'success') status = 'success';
          else if (lrs === 'failed') status = 'failed';
          else status = 'unknown';
        }
      }
      // 今日无真实 run 且 cron 星期几不含今天 → 非执行日（灰，与 checkpoint off_day 同语义，§5.4）
      if (status === 'pending' && cronDowMatchToday(task.scheduleExpr, this.weekday) === false) {
        status = 'off_day';
      }
      list.push({
        taskId: task.id, taskName: task.name, expectedTime, status, runId, error,
        freq: cronFreq(task.scheduleExpr), src: task.src, agentCall: task.agentCall,
        agentLine: task.agentLine ?? null,
      });
    }
    list.sort((a, b) => a.expectedTime.localeCompare(b.expectedTime) || a.taskName.localeCompare(b.taskName));
    return list;
  }

  // ================= Blocked flows（failed/late 且声明阻断下游） =================
  private buildBlockedFlows(checkpoints: CheckpointResult[]): BlockedFlowEntry[] {
    return checkpoints
      .filter(cp => (cp.status === 'failed' || cp.status === 'late') && cp.blocksFlow && cp.blocksFlow.length > 0)
      .map(cp => ({ checkpointId: cp.id, checkpointName: cp.name, status: cp.status, blocks: cp.blocksFlow ?? [] }));
  }

  // ================= 僵尸任务（数据库存在但调度器未加载） =================
  private async fetchOrphanedTasks(): Promise<{ tasks: OrphanedTask[]; error?: string }> {
    try {
      const res = await fetch(`${this.opts.osBaseURL}/api/v1/scheduler/orphaned-tasks`, { signal: AbortSignal.timeout(3000) });
      if (!res.ok) return { tasks: [], error: `HTTP ${res.status}` };
      const json: any = await res.json();
      return { tasks: json.orphanedTasks ?? [] };
    } catch (err) {
      return { tasks: [], error: err instanceof Error ? err.message : String(err) };
    }
  }

}