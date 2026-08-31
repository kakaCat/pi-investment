import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import { existsSync, readFileSync, statSync } from 'fs';
import { agentOsLogsPrompt, type AgentOsLogsParams, type AgentOsLogsResult } from './prompt';

export interface AgentOsConfig {
  projectRoot: string;
  logDir: string;
}

export class AgentOsLogsTool extends BaseTool<AgentOsLogsParams, AgentOsLogsResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'agent_os_logs',
    category: 'agent-os-manager',
    version: '1.1.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = agentOsLogsPrompt;

  constructor(private config: AgentOsConfig) {
    super();
  }

  protected validate(params: AgentOsLogsParams): ValidationResult {
    const errors: string[] = [];

    if (params.lines !== undefined) {
      if (!Number.isInteger(params.lines) || params.lines < 1 || params.lines > 1000) {
        errors.push('lines 必须是 1-1000 之间的整数');
      }
    }

    if (params.source) {
      const validSources = ['main', 'scheduler'];
      if (!validSources.includes(params.source)) {
        errors.push(`source 必须是 ${validSources.join(', ')} 之一`);
      }
    }

    if (errors.length > 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: errors.join('; '),
      };
    }

    return { success: true };
  }

  protected async execute(
    params: AgentOsLogsParams,
    context: ToolContext
  ): Promise<AgentOsLogsResult> {
    const { projectRoot, logDir } = this.config;
    const lines = params.lines || 50;
    const source = params.source || 'main';

    // 2026-08-31 修复：候选文件按 mtime 最新优先（launchd 托管时 stdout/stderr 才是活跃日志，
    // agent-os.log 可能是旧进程遗留）；读取改用 node fs 尾部切片，不依赖系统 tail/grep 命令。
    const candidates = source === 'scheduler'
      ? ['launchd-stderr.log', 'agent-os.log', 'scheduler.log', 'launchd-stdout.log']
      : ['launchd-stdout.log', 'agent-os.log', 'main.log', 'launchd-stderr.log'];

    const existing = candidates
      .map(f => `${projectRoot}/${logDir}/${f}`)
      .filter(p => {
        try { return existsSync(p) && statSync(p).isFile() && statSync(p).size > 0; } catch { return false; }
      })
      .sort((a, b) => statSync(b).mtimeMs - statSync(a).mtimeMs);

    const logPath = existing[0];
    if (!logPath) {
      // plan 兜底：不 throw，返回建议命令让调用方用 bash 排查
      return {
        lines: [],
        total: 0,
        source: `${projectRoot}/${logDir}`,
        error: `未找到可用日志文件（候选：${candidates.join(', ')}）。建议用 bash 执行：ls -la ${projectRoot}/${logDir}/`,
      };
    }

    try {
      const content = readFileSync(logPath, 'utf-8');
      let rawLines = content.split(/\r?\n/).filter(l => l.trim());
      if (params.grep) {
        const g = params.grep.toLowerCase();
        rawLines = rawLines.filter(l => l.toLowerCase().includes(g));
      }
      const logLines = rawLines.slice(-lines);
      return {
        lines: logLines,
        total: logLines.length,
        source: logPath,
      };
    } catch (e) {
      // plan 兜底：读取失败时给出可直接执行的 bash 命令
      return {
        lines: [],
        total: 0,
        source: logPath,
        error: `读取失败：${(e as Error).message}。建议用 bash 执行：tail -${lines} "${logPath}"${params.grep ? ` | grep -i "${params.grep}"` : ''}`,
      };
    }
  }

  protected wrap(data: AgentOsLogsResult, _context: ToolContext): ToolResponse<AgentOsLogsResult> {
    return {
      success: true,
      data,
    };
  }
}
