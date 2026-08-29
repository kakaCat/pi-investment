import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse } from '@pi-investment/core-tool';
import { execSync } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { agentOsStatusPrompt, type AgentOsStatusParams, type AgentOsStatusResult } from './prompt';

export interface AgentOsConfig {
  projectRoot: string;
  port: number;
  healthCheckUrl: string;
  logDir: string;
}

export class AgentOsStatusTool extends BaseTool<AgentOsStatusParams, AgentOsStatusResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'agent_os_status',
    category: 'agent-os-manager',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = agentOsStatusPrompt;

  constructor(private config: AgentOsConfig) {
    super();
  }

  protected validate(params: AgentOsStatusParams): ValidationResult {
    // 无参数，直接通过
    return { success: true };
  }

  protected async execute(
    params: AgentOsStatusParams,
    context: ToolContext
  ): Promise<AgentOsStatusResult> {
    const { port, healthCheckUrl, projectRoot, logDir } = this.config;

    // 检查进程
    let pid: number | null = null;
    let portListening = false;
    try {
      const pidStr = execSync(`lsof -ti:${port} -sTCP:LISTEN`, { encoding: 'utf-8', timeout: 5000 }).trim();
      if (pidStr) {
        pid = parseInt(pidStr);
        portListening = true;
      }
    } catch {}

    // 健康检查
    let healthOk = false;
    let healthError: string | null = null;
    if (portListening) {
      try {
        execSync(`curl -sf --max-time 5 "${healthCheckUrl}" > /dev/null`, { timeout: 6000 });
        healthOk = true;
      } catch (e: any) {
        healthError = e.message;
      }
    }

    // 读取最近错误
    const recentErrors: string[] = [];
    const logPath = `${projectRoot}/${logDir}/main.log`;
    if (existsSync(logPath)) {
      try {
        const logs = readFileSync(logPath, 'utf-8').split('\n').slice(-100);
        const errors = logs.filter(l => l.toLowerCase().includes('error') || l.toLowerCase().includes('exception'));
        recentErrors.push(...errors.slice(-5));
      } catch {}
    }

    return {
      running: !!pid,
      pid: pid ?? 0,
      port,
      port_listening: portListening,
      health_ok: healthOk,
      health_error: healthError,
      recent_errors: recentErrors,
      timestamp: new Date().toISOString(),
    };
  }

  protected wrap(data: AgentOsStatusResult, _context: ToolContext): ToolResponse<AgentOsStatusResult> {
    return {
      success: true,
      data,
    };
  }
}
