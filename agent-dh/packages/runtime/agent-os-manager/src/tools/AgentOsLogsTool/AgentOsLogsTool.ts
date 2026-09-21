import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import { execSync } from 'child_process';
import { existsSync } from 'fs';
import { agentOsLogsPrompt, type AgentOsLogsParams, type AgentOsLogsResult } from './prompt';

export interface AgentOsConfig {
  projectRoot: string;
  logDir: string;
}

export class AgentOsLogsTool extends BaseTool<AgentOsLogsParams, AgentOsLogsResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'agent_os_logs',
    category: 'agent-os-manager',
    version: '1.0.0',
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
    // 2026-08-30 修复：agent-os 实际日志文件是 agent-os.log（launchd 托管），
    // 不存在 main.log/scheduler.log。按优先级回退查找真实文件。
    const candidates = source === 'scheduler'
      ? ['scheduler.log', 'agent-os.log']
      : ['main.log', 'agent-os.log', 'launchd-stdout.log'];
    const logPath = candidates
      .map(f => `${projectRoot}/${logDir}/${f}`)
      .find(p => existsSync(p));

    if (!logPath) {
      throw new Error(`Log file not found under ${projectRoot}/${logDir} (tried: ${candidates.join(', ')})`);
    }

    let cmd = `tail -${lines} "${logPath}"`;
    if (params.grep) {
      cmd += ` | grep -i "${params.grep}"`;
    }

    const output = execSync(cmd, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });
    const logLines = output.split('\n').filter(l => l.trim());

    return {
      lines: logLines,
      total: logLines.length,
      source: logPath,
    };
  }

  protected wrap(data: AgentOsLogsResult, _context: ToolContext): ToolResponse<AgentOsLogsResult> {
    return {
      success: true,
      data,
    };
  }
}
