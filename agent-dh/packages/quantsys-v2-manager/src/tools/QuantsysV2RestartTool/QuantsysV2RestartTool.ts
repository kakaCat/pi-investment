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
  /** launchd 服务标签；默认 com.pi-investment.v2-api（2026-08-30 新增） */
  launchdLabel?: string;
}

export class QuantsysV2RestartTool extends BaseTool<QuantsysV2RestartParams, QuantsysV2RestartResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'quantsys_v2_restart',
    category: 'quantsys-v2-manager',
    version: '2.1.0',
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
      // Step 1: 重启服务。2026-08-30 修复：v2-api 由 launchd 托管（KeepAlive 自动拉起），
      // 旧 kill+spawn 流程在 kill 后被 launchd 抢先拉起，端口"永不释放"，误报失败。
      // 权威入口：launchctl kickstart -k（原子 kill+重拉）；launchd 不可用时回退旧流程。
      steps.push({ step: 'restart', status: 'started' });
      const uid = execSync('id -u', { encoding: 'utf-8', timeout: 3000 }).trim();
      const launchdLabel = this.config.launchdLabel || 'com.pi-investment.v2-api';
      let launchdKicked = false;
      try {
        execSync(`launchctl kickstart -k gui/${uid}/${launchdLabel}`, { timeout: 10000 });
        steps.push({ step: 'restart', status: 'launchd_kickstart', label: launchdLabel });
        launchdKicked = true;
      } catch (e: any) {
        steps.push({ step: 'restart', status: 'launchd_unavailable_fallback', note: e.message?.slice(0, 120) });
      }

      if (!launchdKicked) {
        // 回退：kill（graceful/force）→ 端口释放验证 → spawn
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

        execSync('sleep 2');
        try {
          execSync(`lsof -ti:${port} -sTCP:LISTEN`, { timeout: 2000 });
          return { success: false, steps, error: `Port ${port} still occupied after stop` };
        } catch {
          steps.push({ step: 'verify_port', status: 'free' });
        }

        steps.push({ step: 'start', status: 'launching' });
        const startCmd = `cd ${projectRoot} && source ${activateScript} && python ${startupScript}`;
        const child = spawn('bash', ['-c', startCmd], {
          detached: true,
          stdio: 'ignore',
        });
        child.unref();
        steps.push({ step: 'start', status: 'spawned', pid: child.pid });
      }

      // Step 2: 等待启动
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

      // Step 3: 启动超时，诊断
      steps.push({ step: 'health_check', status: 'timeout' });
      const diagnosis = this.diagnose();
      return {
        success: false,
        steps,
        diagnosis,
        error: '重启失败（健康检查超时）：' + (diagnosis?.issues ?? []).join('；'),
      };

    } catch (e: any) {
      steps.push({ step: 'fatal_error', error: e.message });
      return { success: false, steps, error: e.message };
    }
  }

  private checkStatus() {
    const { port, healthCheckUrl } = this.config;

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

    try {
      const pidStr = execSync(`lsof -ti:${port} -sTCP:LISTEN`, { encoding: 'utf-8', timeout: 3000 }).trim();
      if (!pidStr) {
        issues.push(`Port ${port} not listening - process failed to bind`);
      }
    } catch {
      issues.push(`Port ${port} not listening`);
    }

    try {
      execSync('pg_isready', { timeout: 3000 });
    } catch {
      issues.push('PostgreSQL not ready');
    }

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
