import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse } from '@pi-investment/core-tool';
import { execSync } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { quantsysV2StatusPrompt, type QuantsysV2StatusParams, type QuantsysV2StatusResult } from './prompt';

export interface QuantsysV2Config {
  projectRoot: string;
  port: number;
  healthCheckUrl: string;
  logFile: string;
}

export class QuantsysV2StatusTool extends BaseTool<QuantsysV2StatusParams, QuantsysV2StatusResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'quantsys_v2_status',
    category: 'quantsys-v2-manager',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = quantsysV2StatusPrompt;

  constructor(private config: QuantsysV2Config) {
    super();
  }

  protected validate(params: QuantsysV2StatusParams): ValidationResult {
    // 无参数，直接通过
    return { success: true };
  }

  protected async execute(
    params: QuantsysV2StatusParams,
    context: ToolContext
  ): Promise<QuantsysV2StatusResult> {
    const { port, healthCheckUrl, projectRoot, logFile } = this.config;

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
    const logPath = `${projectRoot}/${logFile}`;
    if (existsSync(logPath)) {
      try {
        const logs = readFileSync(logPath, 'utf-8').split('\n').slice(-100);
        const errors = logs.filter(l => l.includes('ERROR') || l.includes('Exception') || l.includes('error'));
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

  protected wrap(data: QuantsysV2StatusResult, _context: ToolContext): ToolResponse<QuantsysV2StatusResult> {
    return {
      success: true,
      data,
    };
  }
}
