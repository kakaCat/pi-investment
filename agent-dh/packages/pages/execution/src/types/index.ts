// Type definitions for dashboard-execution plugin (P1)

export type CheckpointStatus = 'off_day' | 'confirmed' | 'failed' | 'late' | 'pending' | 'unknown';

export type CheckpointLine = 'engine' | 'autonomy';

export interface Checkpoint {
  id: string;
  line: CheckpointLine;
  module: string;
  name: string;
  verify: Verify;
  expectDays: string;   // cron dow 语义："1-5" 工作日 / "0" 周日 / "0-6" 每日
  expectTime: string;   // "HH:mm" 本地时区
  graceMinutes: number; // 默认 30
  blocksFlow?: string[]; // failed/late 时阻断的下游模块 id
}

export type Verify =
  | { type: 'scheduler_task'; taskName: string; statusField?: 'lastRun' | 'todaySuccess' }
  | { type: 'v2_regime' }                    // market/perception/regime 最新 trade_date
  | { type: 'v2_themes' }                    // market/perception/themes 最新 trade_date
  | { type: 'v2_memory_kind'; kind: string } // memory/search 当日新增计数
  | { type: 'genome_file'; file: 'genome.json' | 'candidates.json' }
  // REQ-9bcd0a WP6②：今日 morning_analysis 决策的 context.attribution_read（M6↔L2 回流边消费证据）
  | { type: 'decision_reflux_read' }
  | { type: 'log_marker'; file: string; pattern: string };

export interface CheckpointResult {
  id: string;
  line: CheckpointLine;
  module: string;
  name: string;
  status: CheckpointStatus;
  message?: string;
  blocksFlow?: string[];
  /** 计划执行时间 HH:mm（registry expectTime） */
  expectTime?: string;
}

export type HealthRowStatus = 'ok' | 'degraded' | 'failed';

export interface HealthStatus {
  name: string;            // quantsys-v2 | agent-os | postgres | agent-dh
  status: HealthRowStatus;
  port?: number;
  metrics?: Record<string, unknown>;
  responseTimeMs?: number;
  error?: string;
}

/** scheduler/tasks 真实字段：id 为字符串（"258"），enabled/todaySuccess 等序列化为字符串 */
export interface SchedulerTask {
  id: string;
  name: string;
  enabled: boolean | string;
  scheduleKind?: string;
  scheduleExpr?: string | null;
  payload?: { command?: string } | null;
  lastRun?: Record<string, unknown> | string | null; // dict | None（repr）
  nextRunAt?: string | null;
  createdAt?: string;
  updatedAt?: string | null;
  todaySuccess?: number | string;
  todayTriggered?: number | string;
  /** 任务自带业务线字段（OS=agent_line：profit_engine/autonomy）——接口暴露后分类以其为准 */
  agentLine?: string | null;
  /** v2 领域模型六域（data/signal/trading/analysis/report/monitor）——与业务线正交，仅作打标对账信号 */
  domain?: string | null;
  /** 调度来源：v2=quantsys-v2 引擎任务 / os=Agent OS 定时（webhook 触发 agent） */
  src?: 'v2' | 'os';
  /** 是否调用 agent 及运行时：dh=agent-dh / ts=agent-ts / none=纯引擎无 agent */
  agentCall?: 'dh' | 'ts' | 'none';
}

export interface SchedulerRun {
  id: number | string;
  taskId: string | number;
  taskName: string;
  status: string;             // success | failed
  triggeredAt: string;        // "2026-09-03 20:26:29.986688+08:00"（空格分隔本地）
  finishedAt?: string;
  durationMs?: number;
  error?: string | null;      // 顶层 error（失败样例存在）
  payload?: { error?: string; status?: string; details?: unknown } | null;
}

export type ErrorEventStatus = 'open' | 'processing' | 'resolved' | 'ignored';

/** 错误事件：2026-09-09 起数据源=Agent OS error_events 表（采集入库、按指纹去重计数）。
 *  solve-kit 兼容字段（source/timestamp/line/file）保持填充：投递消息读 source/line/file/timestamp。 */
export interface ErrorEvent {
  source: 'v2' | 'os' | 'dsh' | 'pg';
  /** 兼容/展示用：最近一次出现时间（last_seen_at ISO，fmtClock 可解析） */
  timestamp?: string;
  /** 兼容/展示用：单行错误摘要（msg 或 msg+err 提炼） */
  line: string;
  /** 兼容/展示用：来源文件或任务（metadata.log_path basename 或 task_name） */
  file: string;
  // —— Agent OS error_events DB 字段 ——
  id: string;
  status: ErrorEventStatus;
  occurrenceCount: number;      // 指纹去重后的出现次数
  firstSeenAt?: string;         // ISO
  lastSeenAt?: string;          // ISO
  level?: string;
  msg?: string;
  detail?: string | null;
  taskName?: string | null;
  taskId?: string | null;
  assignee?: string | null;           // claim 认领窗口（如 w-xxxx）
  dispatchedSession?: string | null;
  resolvedAt?: string | null;
  resolutionNote?: string | null;
  metadata?: Record<string, unknown> | null;
}

export interface TimelineEntry {
  taskId: string;
  taskName: string;
  expectedTime: string; // cron 换算 HH:mm
  status: 'success' | 'failed' | 'pending' | 'unknown' | 'off_day';
  runId?: number | string;
  error?: string;
  /** 频率分桶：daily=日执行 / weekly=周执行 */
  freq: 'daily' | 'weekly';
  /** 透传调度来源与 agent 调用标记（供徽标渲染） */
  src?: 'v2' | 'os';
  agentCall?: 'dh' | 'ts' | 'none';
  /** 透传任务自带业务线字段（分类以其为准，缺省回退名单） */
  agentLine?: string | null;
}

export interface BlockedFlowEntry {
  checkpointId: string;
  checkpointName: string;
  status: CheckpointStatus;
  blocks: string[];
}

export interface BoardData {
  health: HealthStatus[];
  checkpoints: CheckpointResult[];
  tasks: SchedulerTask[];
  /** 分类对账（2026-09-12 新增）：分类字段是否打通 / 有无未归类任务 / OS 并入对账 */
  taskCoverage?: {
    total: number;
    byLine: Record<string, number>;
    fieldTagged: number;
    fieldMissing: number;
    unclassified: string[];
    os?: { apiTotal: number; included: number; excluded: number; byReason: Record<string, number>; lineTagged?: number };
    v2?: { total: number; domainTagged: number; domainMissing: number; domainByValue: Record<string, number>; missingNames: string[] };
  };
  errors: ErrorEvent[];
  timeline: TimelineEntry[];
  blockedFlows: BlockedFlowEntry[];
  degraded: Array<{ source: string; error: string }>;
  v2Available: boolean;
  fetchedAt: string;
  orphanedTasks?: OrphanedTask[]; // 本地 ISO
}

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  degraded?: Array<{ source: string; error: string }>;
}

export interface AggregatorOptions {
  v2BaseURL: string;
  osBaseURL: string;
  genomeDir: string;                 // genome 目录（candidates.json/genome.json）
  profileStateDir: string;           // ~/.dsh/profiles/investment/state
  requestTimeoutMs?: number;
}
export interface OrphanedTask {
  id: string;
  name: string;
  scheduleExpr: string;
  lastRunAt?: string | null;
  createdAt: string;
  inScheduler: boolean;
  inDatabase: boolean;
  daysSinceLastRun: number;
  enabled: boolean;
  reason: string;
  webhookUrl?: string;
}
