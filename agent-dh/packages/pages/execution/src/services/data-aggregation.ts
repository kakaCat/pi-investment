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
import { fetchJson, HttpError } from './http.js';
import type {
  AggregatorOptions, BlockedFlowEntry, BoardData, Checkpoint, CheckpointResult,
  ErrorEvent, HealthStatus, SchedulerRun, SchedulerTask, TimelineEntry, Verify,
} from '../types/index.js';

interface TaskRunsResult { tasks: SchedulerTask[]; fetchError?: string }
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

const ERROR_RE = /ERROR|CRITICAL|Traceback|panic|FATAL/i;
const TS_RE = /\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})/;

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
/** 读取日志尾部（>1MB 只 seek 末 512KB，绝不整读 78MB 文件）；日志被轮转/不存在时返回空 */
async function tailFile(file: string, tailLines = 300, maxBytes = 512 * 1024): Promise<string[]> {
  let st;
  try {
    st = await fsp.stat(file);
  } catch {
    return [];
  }
  let content: string;
  if (st.size > maxBytes) {
    const fh = await fsp.open(file, 'r');
    try {
      const len = Math.min(st.size, maxBytes);
      const buf = Buffer.alloc(len);
      await fh.read(buf, 0, len, st.size - len);
      content = buf.toString('utf-8');
    } finally {
      await fh.close();
    }
    const nl = content.indexOf('\n');
    content = nl >= 0 ? content.slice(nl + 1) : content; // 丢弃被截断的半行
  } else {
    content = await fsp.readFile(file, 'utf-8');
  }
  const lines = content.split('\n');
  return lines.slice(-tailLines);
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
    const [healthR, tasksR, runsR, regimeR, themesR, memoryR, genomeR] = await Promise.all([
      this.fetchHealthRows(degraded),
      this.fetchTasks(),
      this.fetchRuns(),
      this.fetchRegime(),
      this.fetchThemes(),
      this.fetchMemoryToday(),
      this.fetchGenomeState(),
    ]);

    const v2Available = healthR.v2Available;
    for (const [key, val] of Object.entries({
      'scheduler-runs': runsR.error, regime: regimeR.error, themes: themesR.error,
      memory: memoryR.error, genome: genomeR.error,
    })) {
      if (val) degraded.push({ source: key, error: val });
    }

    const checkpoints = this.verifyAllCheckpoints(v2Available, tasksR, runsR.runs, {
      regimeLatest: regimeR.latest, themesLatest: themesR.latest, memoryToday: memoryR.count,
    }, genomeR.state);
    const timeline = this.buildTimeline(tasksR.tasks, runsR.runs);
    const blockedFlows = this.buildBlockedFlows(checkpoints);
    const errors = await this.fetchErrorEvents();
    const tasks = this.enrichTasks(tasksR.tasks, runsR.runs);

    return {
      health: healthR.rows,
      checkpoints,
      tasks,
      errors,
      timeline,
      blockedFlows,
      degraded,
      v2Available,
      fetchedAt: new Date().toISOString(),
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
    if (v2Error && os.tasks.length === 0) return { tasks: [], fetchError: v2Error };
    if (v2Error) return { tasks: os.tasks, fetchError: v2Error };
    return { tasks: [...v2Tasks, ...os.tasks] };
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
      todaySuccess: num(t.todaySuccess), todayTriggered: num(t.todayTriggered),
    };
  }

  /**
   * Agent OS 中"真正调用 agent"的定时任务（payload.executor=dsh-webhook，经 webhook
   * 唤醒 DSH 侧 agent-dh/agent-ts）并入看板：src=os / agentCall=dh|ts。
   * 其余（纯引擎占位的 quantsys-v2 任务、disabled、非 dsh-webhook）不并入 —— 引擎任务
   * 以 v2 为准，避免与 v2 scheduler 双计。无 v2 run：今日状态由 /tasks/stats 的
   * last_run_at / last_run_status 推导（Agent OS 无 today 计数）。
   */
  private async fetchOsAgentTasks(): Promise<{ tasks: SchedulerTask[]; error?: string }> {
    try {
      const [listJ, statJ] = await Promise.all([
        fetchJson<{ success?: boolean; tasks?: OsSchedulerTask[] }>(this.osBase + '/api/v1/scheduler/tasks'),
        fetchJson<{ success?: boolean; tasks?: OsSchedulerStat[] }>(this.osBase + '/api/v1/scheduler/tasks/stats'),
      ]);
      const stats = new Map<string, OsSchedulerStat>(
        (Array.isArray(statJ?.tasks) ? statJ.tasks : []).map(s => [String(s.name), s]),
      );
      const out: SchedulerTask[] = [];
      for (const t of Array.isArray(listJ?.tasks) ? listJ.tasks : []) {
        const name = String(t.name ?? '');
        const enabled = t.enabled === true || t.enabled === 'true' || t.enabled === 1 || t.enabled === '1';
        if (!name || !enabled) continue;
        const executor = String((t.payload as Record<string, unknown> | null | undefined)?.executor ?? '');
        if (executor !== 'dsh-webhook') continue; // 只并入真正调用 agent 的任务
        const expr5 = osCron5(String(t.schedule ?? ''));
        if (!expr5) continue; // 时刻不可解析 → 不进时间轴（避免无依据展示）
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
          todayTriggered: ranToday ? 1 : 0,
          todaySuccess: ranToday && lastStatus === 'success' ? 1 : 0,
        });
      }
      out.sort((a, b) => String(a.name).localeCompare(String(b.name)));
      return { tasks: out };
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

  // ================= Checkpoints（16 行 registry × 状态机） =================
  private verifyAllCheckpoints(
    v2Available: boolean,
    tasksResult: TaskRunsResult,
    runs: SchedulerRun[],
    vs: { regimeLatest?: string; themesLatest?: string; memoryToday?: number },
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
    vs: { regimeLatest?: string; themesLatest?: string; memoryToday?: number },
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
    if (!v2Available && (vt === 'scheduler_task' || vt === 'v2_regime' || vt === 'v2_themes' || vt === 'v2_memory_kind')) {
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
      list.push({ taskId: task.id, taskName: task.name, expectedTime, status, runId, error, freq: cronFreq(task.scheduleExpr), src: task.src, agentCall: task.agentCall });
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

  // ================= 错误事件流（v2/os/dsh 三端 tail） =================
  private async fetchErrorEvents(): Promise<ErrorEvent[]> {
    const all: Array<{ source: ErrorEvent['source']; ts: number | null; tsText: string | null; line: string; file: string }> = [];
    for (const { source, file } of this.opts.logFiles) {
      try {
        const lines = await tailFile(file);
        for (const raw of lines) {
          if (!ERROR_RE.test(raw)) continue;
          const m = raw.match(TS_RE);
          const tsText = m ? m[1] : null;
          all.push({ source, ts: tsMs(tsText), tsText, line: raw.substring(0, 500), file: path.basename(file) });
        }
      } catch {
        // 单文件读失败忽略（可能被轮转/删除）
      }
    }
    all.sort((a, b) => (b.ts ?? 0) - (a.ts ?? 0));
    return all.slice(0, 10).map(e => ({ source: e.source, timestamp: e.tsText ?? undefined, line: e.line, file: e.file }));
  }
}
