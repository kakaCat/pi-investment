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
  | { type: 'log_marker'; file: string; pattern: string };

export interface CheckpointResult {
  id: string;
  line: CheckpointLine;
  module: string;
  name: string;
  status: CheckpointStatus;
  message?: string;
  blocksFlow?: string[];
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

export interface ErrorEvent {
  source: 'v2' | 'os' | 'dsh' | 'pg';
  timestamp?: string;   // 解析自行首，失败为 undefined
  line: string;         // 截断 500 字符
  file: string;         // 日志文件名（basename）
}

export interface TimelineEntry {
  taskId: string;
  taskName: string;
  expectedTime: string; // cron 换算 HH:mm
  status: 'success' | 'failed' | 'pending' | 'unknown';
  runId?: number | string;
  error?: string;
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
  errors: ErrorEvent[];
  timeline: TimelineEntry[];
  blockedFlows: BlockedFlowEntry[];
  degraded: Array<{ source: string; error: string }>;
  v2Available: boolean;
  fetchedAt: string; // 本地 ISO
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
  logFiles: Array<{ source: 'v2' | 'os' | 'dsh' | 'pg'; file: string }>;
  requestTimeoutMs?: number;
}
