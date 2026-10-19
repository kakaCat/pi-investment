/**
 * Agent OS CLI Executor
 *
 * 执行 Agent OS CLI 命令的底层封装
 */

import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';
import { fileURLToPath } from 'url';

const execAsync = promisify(exec);

// ES module __dirname equivalent
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface CLIResult<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

/**
 * 获取 Agent OS CLI 路径（延迟计算，确保环境变量已加载）
 */
function getAgentOSCLIPath(): string {
  return process.env.AGENT_OS_CLI_PATH ||
    path.join(__dirname, '../../../agent-os/agent-os');
}

/**
 * 执行 Agent OS CLI 命令
 */
async function execAgentOS(args: string[]): Promise<CLIResult> {
  try {
    const AGENT_OS_CLI_PATH = getAgentOSCLIPath();

    // 对参数进行 shell 转义
    const escapedArgs = args.map(arg => {
      // 如果参数包含空格、特殊字符或 JSON，用单引号包裹并转义内部单引号
      if (arg.includes(' ') || arg.includes('{') || arg.includes('"') || arg.includes('$')) {
        return `'${arg.replace(/'/g, "'\\''")}'`;
      }
      return arg;
    });

    const command = `${AGENT_OS_CLI_PATH} ${escapedArgs.join(' ')}`;

    // Agent OS 需要在其根目录下执行才能找到 config.yaml
    const agentOSDir = path.dirname(AGENT_OS_CLI_PATH);

    const { stdout, stderr } = await execAsync(command, {
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer
      timeout: 30000, // 30s timeout
      cwd: agentOSDir, // 在 Agent OS 根目录下执行
      env: {
        ...process.env,
        PGDATABASE: 'agent_os', // Agent OS 优先使用 PostgreSQL 环境变量
      },
    });

    if (stderr && !stderr.includes('INFO')) {
      console.error(`[Agent OS CLI] stderr: ${stderr}`);
    }

    // 尝试解析 JSON 输出
    try {
      const data = JSON.parse(stdout);
      return { success: true, data };
    } catch {
      // 非 JSON 输出，返回原始文本
      return { success: true, data: stdout.trim() };
    }
  } catch (error: any) {
    const errorMessage = error.stderr || error.message;
    console.error(`[Agent OS CLI] Error executing: ${args.join(' ')}`, errorMessage);
    return {
      success: false,
      error: errorMessage
    };
  }
}

// ============================================================================
// Memory Operations
// ============================================================================

export interface AgentOSMemoryWriteOptions {
  namespace: string;
  content: string;
  metadata?: Record<string, any>;
  tags?: string[];
}

export interface AgentOSMemorySearchOptions {
  namespace: string;
  query: string;
  limit?: number;
  minScore?: number;
}

export interface AgentOSMemorySearchResult {
  id: string;
  content: string;
  score: number;
  metadata?: Record<string, any>;
  tags?: string[];
  createdAt: string;
}

export interface AgentOSMemoryRecallAuditEntry {
  id: string;
  namespace: string;
  query: string;
  resultsCount: number;
  timestamp: string;
}

/**
 * 写入记忆
 */
export async function agentOSMemoryWrite(
  options: AgentOSMemoryWriteOptions
): Promise<CLIResult<{ id: string }>> {
  const args = [
    'memory', 'write',
    '--namespace', options.namespace,
    '--content', options.content,
  ];

  if (options.metadata) {
    args.push('--metadata', JSON.stringify(options.metadata));
  }

  if (options.tags && options.tags.length > 0) {
    args.push('--tags', options.tags.join(','));
  }

  // Agent OS CLI 使用 --category 而不是独立的分类系统
  const category = options.metadata?.kind || 'project';
  args.push('--category', category);

  return execAgentOS(args);
}

/**
 * 搜索记忆
 */
export async function agentOSMemorySearch(
  options: AgentOSMemorySearchOptions
): Promise<CLIResult<AgentOSMemorySearchResult[]>> {
  const args = [
    'memory', 'search',
    '--namespace', options.namespace,
    '--query', options.query,
    '--json',
  ];

  if (options.limit) {
    args.push('--limit', options.limit.toString());
  }

  // Agent OS CLI 使用 --min-importance 而不是 --min-score
  if (options.minScore) {
    args.push('--min-importance', options.minScore.toString());
  }

  return execAgentOS(args);
}

/**
 * 获取 Recall Audit 日志
 */
export async function agentOSMemoryRecallAudit(
  namespace: string,
  limit?: number
): Promise<CLIResult<AgentOSMemoryRecallAuditEntry[]>> {
  const args = [
    'memory', 'recall-audit',
    '--namespace', namespace,
  ];

  if (limit) {
    args.push('--limit', limit.toString());
  }

  return execAgentOS(args);
}

// ============================================================================
// Decision Operations
// ============================================================================

export interface AgentOSDecisionRecordOptions {
  namespace: string;
  type: string;
  reasoning: string;
  result?: string;
  metadata?: Record<string, any>;
}

/**
 * 记录决策
 *
 * 2026-10-20 契约对齐：agent-os CLI（bin/agent-os，decision record）真实支持的
 * 只有 --agent/--action(watch|buy|sell|hold)/--reason/--confidence/--context/
 * --targets。本函数此前传 --namespace/--type/--reasoning/--result/--metadata，
 * 全是 CLI 不认识的 flag → 每条决策日志上传必失败（生产启动日志实测）。
 * 映射口径（原字段零丢失，全部留痕）：
 *   namespace  → --agent（agent-ts/<namespace>）
 *   type       → --action 的枚举映射（买/卖/持有按词，其余一律 watch=观察），
 *                原始 type 写进 --context 保留
 *   reasoning  → --reason
 *   result+metadata → 并入 --context JSON
 */
export async function agentOSDecisionRecord(
  options: AgentOSDecisionRecordOptions
): Promise<CLIResult<{ id: string }>> {
  const t = (options.type || '').toLowerCase();
  const action = t.includes('buy') ? 'buy'
    : t.includes('sell') ? 'sell'
    : t.includes('hold') ? 'hold'
    : 'watch';

  const context = {
    ...(options.metadata || {}),
    originalType: options.type,
    ...(options.result !== undefined ? { result: options.result } : {}),
  };

  const args = [
    'decision', 'record',
    '--agent', `agent-ts/${options.namespace || 'general'}`,
    '--action', action,
    '--reason', String(options.reasoning ?? ''),
    '--context', JSON.stringify(context),
  ];

  return execAgentOS(args);
}

// ============================================================================
// Notification Operations
// ============================================================================

export interface AgentOSNotificationSendOptions {
  channel: string;
  title: string;
  content: string;
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  metadata?: Record<string, any>;
}

/**
 * 发送通知
 */
export async function agentOSNotificationSend(
  options: AgentOSNotificationSendOptions
): Promise<CLIResult<{ id: string }>> {
  const args = [
    'notify', 'send',
    '--channel', options.channel,
    '--title', options.title,
    '--content', options.content,
  ];

  // Agent OS CLI 使用 --urgency 而不是 --priority
  if (options.priority) {
    const urgencyMap: Record<string, string> = {
      'low': 'low',
      'medium': 'normal',
      'high': 'high',
      'urgent': 'critical',
    };
    const urgency = urgencyMap[options.priority] || 'normal';
    args.push('--urgency', urgency);
  }

  if (options.metadata) {
    // Agent OS notify 可能不支持 metadata，跳过
    console.log('[Agent OS Notification] Metadata not supported, skipping');
  }

  return execAgentOS(args);
}

// ============================================================================
// Resource Operations (支持未来扩展)
// ============================================================================

export interface AgentOSResourceQueryOptions {
  namespace?: string;
  type?: string;
  limit?: number;
}

/**
 * 查询资源
 */
export async function agentOSResourceQuery(
  options: AgentOSResourceQueryOptions = {}
): Promise<CLIResult<any[]>> {
  const args = ['resource', 'list'];

  if (options.namespace) {
    args.push('--namespace', options.namespace);
  }

  if (options.type) {
    args.push('--type', options.type);
  }

  if (options.limit) {
    args.push('--limit', options.limit.toString());
  }

  return execAgentOS(args);
}

// ============================================================================
// Scheduler Operations (支持未来扩展)
// ============================================================================

export interface AgentOSSchedulerTask {
  id: string;
  name: string;
  schedule: string;
  enabled: boolean;
  lastRun?: string;
  nextRun?: string;
}

/**
 * 列出调度任务
 */
export async function agentOSSchedulerList(): Promise<CLIResult<AgentOSSchedulerTask[]>> {
  return execAgentOS(['scheduler', 'list']);
}

/**
 * 触发调度任务
 */
export async function agentOSSchedulerTrigger(taskName: string): Promise<CLIResult> {
  return execAgentOS(['scheduler', 'trigger', '--task', taskName]);
}
