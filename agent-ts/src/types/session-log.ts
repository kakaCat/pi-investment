/**
 * Session 日志解析相关类型定义
 */

// ── 事件类型 ──────────────────────────────────────────────────────────────

export interface SessionEvent {
  ts: number;
  event: string;
  run_id: string;
  [key: string]: any;
}

export interface ToolCallEvent extends SessionEvent {
  event: 'tool.call';
  turn_index: number;
  tool_name: string;
  tool_id: string;
  params: any;
  params_length: number;
  start_time: number;
}

export interface ToolResultEvent extends SessionEvent {
  event: 'tool.result';
  turn_index: number;
  tool_name: string;
  tool_id: string;
  success: boolean;
  error: string | null;
  result: any;
  result_length: number;
  duration_ms: number;
}

// ── 元数据 ────────────────────────────────────────────────────────────────

export interface SessionMetadata {
  session_key: string;
  run_id: string;
  start_time: string;
  model: string;
  cwd: string;
  workspace: string;
  total_turns: number;
  total_messages: number;
  total_tokens: number;
  total_cost: number;
  llm_calls: number;
  tool_calls: number;
}

// ── 工具统计 ──────────────────────────────────────────────────────────────

export interface ToolStats {
  name: string;
  callCount: number;
  successCount: number;
  failureCount: number;
  totalDuration: number;
  avgDuration: number;
  errorRate: number;
}

// ── Session 分析结果 ──────────────────────────────────────────────────────

export interface SessionAnalysis {
  metadata: SessionMetadata;
  toolStats: ToolStats[];
  totalToolCalls: number;
  totalToolFailures: number;
  overallErrorRate: number;
  avgToolDuration: number;
  topTools: ToolStats[]; // 按调用次数排序的前5个工具
  slowestTools: ToolStats[]; // 按平均耗时排序的前5个工具
  mostFailedTools: ToolStats[]; // 按失败次数排序的前5个工具
}
