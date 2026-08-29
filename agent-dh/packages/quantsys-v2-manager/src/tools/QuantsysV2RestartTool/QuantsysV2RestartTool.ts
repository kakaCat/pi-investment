import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import { execSync, spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { quantsysV2RestartPrompt, type QuantsysV2RestartParams, type QuantsysV2RestartResult } from './prompt';

export interface QuantsysV2Config {
  projectRoot: string;
  port: number;
  healthCheckUrl: string;
  startupScript: string;
  activateScript: string;
  logFile: string;
}

export class QuantsysV2RestartTool extends BaseTool<QuantsysV2RestartParams, QuantsysV2RestartResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'quantsys_v2_restart',
    category: 'quantsys-v2-manager',
    version: '1.0.0',
    timeoutMs: 120000,
  };

  protected readonly prompt = quantsysV2RestartPrompt;

  constructor(private config: QuantsysV2Config) {
    super();
  }

  protected validate(params: QuantsysV2RestartParams): ValidationResult {
    const errors: string[] = [];

    if (params.force !== undefined && typeof params.force !== 'boolean') {
      errors.push('force 必须是布尔值');
    }

    if (params.wait_startup_sec !== undefined) {
      if (!Number.isInteger(params.wait_startup_sec) || params.wait_startup_sec < 5 || params.wait_startup_sec > 300) {
        errors.push('wait_startup_sec 必须是 5-300 之间的整数');
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
    params: QuantsysV2RestartParams,
    context: ToolContext
  ): Promise<QuantsysV2RestartResult> {
    const force = params.force ?? false;
    const waitSec = params.wait_startup_sec ?? 30;
    const { port, projectRoot, startupScript, activateScript, healthCheckUrl, logFile } = this.config;
    const steps: any[] = [];

    try {
      // Step 1: 停止旧进程
      steps.push({ step: 'stop', status: 'started' });
      let oldPid: number | null = null;
      try {
        const pidStr = execSync(`lsof -ti:${port} -sTCP:LISTEN`, { encoding: 'utf-8', timeout: 5000 }).trim();
        if (pidStr) {
          oldPid = parseInt(pidStr);
          if (force) {
            execSync(`kill -9 ${oldPid}`, { timeout: 3000 });
            steps.push({ step: 'stop', status: 'killed', pid: oldPid, signal: 'SIGKILL' });
          } else {
            execSync(`kill ${oldPid}`, { timeout: 3000 });
            // 等待优雅退出
            for (let i = 0; i < 10; i++) {
              execSync('sleep 1');
              try {
                execSync(`lsof -ti:${port} -sTCP:LISTEN`, { timeout: 2000 });
              } catch {
                steps.push({ step: 'stop', status: 'graceful_exit', pid: oldPid, waited_sec: i + 1 });
                break;
              }
              if (i === 9) {
                execSync(`kill -9 ${oldPid}`, { timeout: 2000 });
                steps.push({ step: 'stop', status: 'force_killed_after_timeout', pid: oldPid });
              }
            }
          }
        } else {
          steps.push({ step: 'stop', status: 'no_process' });
        }
      } catch (e: any) {
        steps.push({ step: 'stop', status: 'error', error: e.message });
      }

      // Step 2: 验证端口释放
      execSync('sleep 2');
      try {
        execSync(`lsof -ti:${port} -sTCP:LISTEN`, { timeout: 2000 });
        return { success: false, steps, error: `Port ${port} still occupied after stop` };
      } catch {
        steps.push({ step: 'verify_port', status: 'free' });
      }

      // Step 3: 启动新进程（后台）
      steps.push({ step: 'start', status: 'launching' });
      const startCmd = `cd ${projectRoot} && source ${activateScript} && python ${startupScript}`;
      const child = spawn('bash', ['-c', startCmd], {
        detached: true,
        stdio: 'ignore',
      });
      child.unref();
      steps.push({ step: 'start', status: 'spawned', pid: child.pid });

      // Step 4: 等待启动
      steps.push({ step: 'wait', status: 'started', wait_sec: waitSec });
      for (let i = 0; i < waitSec; i++) {
        execSync('sleep 1');
        try {
          execSync(`curl -sf --max-time 2 "${healthCheckUrl}" > /dev/null`, { timeout: 3000 });
          steps.push({ step: 'health_check', status: 'ready', after_sec: i + 1 });
          const newStatus = this.checkStatus();
          return { success: true, steps, final_status: newStatus };
        } catch {}
      }

      // Step 5: 启动超时，诊断
      steps.push({ step: 'health_check', status: 'timeout' });
      const diagnosis = this.diagnose();
      return { success: false, steps, diagnosis };

    } catch (e: any) {
      steps.push({ step: 'fatal_error', error: e.message });
      return { success: false, steps, error: e.message };
    }
  }

  private checkStatus() {
    const { port, healthCheckUrl, projectRoot, logFile } = this.config;

    let pid: number | null = null;
    let portListening = false;
    try {
      const pidStr = execSync(`lsof -ti:${port} -sTCP:LISTEN`, { encoding: 'utf-8', timeout: 5000 }).trim();
      if (pidStr) {
        pid = parseInt(pidStr);
        portListening = true;
      }
    } catch {}

    let healthOk = false;
    if (portListening) {
      try {
        execSync(`curl -sf --max-time 5 "${healthCheckUrl}" > /dev/null`, { timeout: 6000 });
        healthOk = true;
      } catch {}
    }

    return {
      running: !!pid,
      pid: pid ?? 0,
      port_listening: portListening,
      health_ok: healthOk,
    };
  }

  private diagnose() {
    const { port, projectRoot, logFile } = this.config;
    const issues: string[] = [];

    // 检查端口
    try {
      const pidStr = execSync(`lsof -ti:${port} -sTCP:LISTEN`, { encoding: 'utf-8', timeout: 3000 }).trim();
      if (!pidStr) {
        issues.push(`Port ${port} not listening - process failed to bind`);
      }
    } catch {
      issues.push(`Port ${port} not listening`);
    }

    // 检查 PostgreSQL
    try {
      execSync('pg_isready', { timeout: 3000 });
    } catch {
      issues.push('PostgreSQL not ready');
    }

    // 读最近错误
    const logPath = `${projectRoot}/${logFile}`;
    if (existsSync(logPath)) {
      const logs = readFileSync(logPath, 'utf-8').split('\n').slice(-50);
      const errors = logs.filter(l => l.includes('ERROR') || l.includes('Exception'));
      if (errors.length > 0) {
        issues.push(`Recent errors in log: ${errors.slice(-3).join(' | ')}`);
      }
    }

    return {
      issues,
      recommendation: issues.length > 0 ? 'Check logs with quantsys_v2_logs, verify PG/port' : 'Unknown issue',
    };
  }

  protected wrap(data: QuantsysV2RestartResult, _context: ToolContext): ToolResponse<QuantsysV2RestartResult> {
    return {
      success: data.success,
      data,
    };
  }
}
