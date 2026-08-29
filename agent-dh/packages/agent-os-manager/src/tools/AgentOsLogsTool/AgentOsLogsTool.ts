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
    const logFile = source === 'scheduler' ? 'scheduler.log' : 'main.log';
    const logPath = `${projectRoot}/${logDir}/${logFile}`;

    if (!existsSync(logPath)) {
      throw new Error(`Log file not found: ${logPath}`);
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
      source: logFile,
    };
  }

  protected wrap(data: AgentOsLogsResult, _context: ToolContext): ToolResponse<AgentOsLogsResult> {
    return {
      success: true,
      data,
    };
  }
}
