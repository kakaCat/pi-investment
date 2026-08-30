import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import { execSync, spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { agentOsRestartPrompt, type AgentOsRestartParams, type AgentOsRestartResult } from './prompt';

export interface AgentOsConfig {
  projectRoot: string;
  port: number;
  healthCheckUrl: string;
  startCommand: string;
  logDir: string;
  launchdLabel?: string;
}

export class AgentOsRestartTool extends BaseTool<AgentOsRestartParams, AgentOsRestartResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'agent_os_restart',
    category: 'agent-os-manager',
    version: '1.0.0',
    timeoutMs: 120000,
  };

  protected readonly prompt = agentOsRestartPrompt;

  constructor(private config: AgentOsConfig) {
    super();
  }

  protected validate(params: AgentOsRestartParams): ValidationResult {
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
    params: AgentOsRestartParams,
    context: ToolContext
  ): Promise<AgentOsRestartResult> {
    const waitSec = params.wait_startup_sec ?? 30;
    const { port, projectRoot, startCommand, healthCheckUrl } = this.config;
    const steps: any[] = [];

    try {
      // 2026-08-28 根本性修复：Agent OS 由 launchd 守护（KeepAlive + serve-guard.sh 幂等清场）。
      // 重启的唯一权威入口是 launchctl kickstart -k（原子 kill+重拉，经守护脚本清场）
      const uid = execSync('id -u', { encoding: 'utf-8', timeout: 3000 }).trim();
      const launchdLabel = this.config.launchdLabel || 'com.pi-investment.agent-os';
      try {
        execSync(`launchctl kickstart -k gui/${uid}/${launchdLabel}`, { timeout: 10000 });
        steps.push({ step: 'restart', status: 'launchd_kickstart', label: launchdLabel });
      } catch (e: any) {
        // launchd 不可用则回退到手动 spawn（兼容未装 plist 的环境）
        steps.push({ step: 'restart', status: 'launchd_unavailable_fallback_spawn', note: e.message?.slice(0, 120) });
        const child = spawn('bash', ['-c', `cd ${projectRoot} && ${startCommand}`], {
          detached: true,
          stdio: 'ignore',
        });
        child.unref();
        steps.push({ step: 'start', status: 'spawned', pid: child.pid });
      }

      // 健康检查
      for (let i = 0; i < waitSec; i++) {
        execSync('sleep 1');
        try {
          execSync(`curl -sf --max-time 2 "${healthCheckUrl}" > /dev/null`, { timeout: 3000 });
          steps.push({ step: 'health_check', status: 'ready', after_sec: i + 1 });
          const newStatus = this.checkStatus();
          return { success: true, steps, final_status: newStatus };
        } catch {}
      }

      // 超时诊断
      steps.push({ step: 'health_check', status: 'timeout' });
      const diagnosis = this.diagnose();
      // 2026-08-30 修复：失败必须带 error 摘要，否则 DSH 层把诊断吞成笼统「工具执行失败」
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
    const { port, projectRoot, logDir } = this.config;
    const issues: string[] = [];

    try {
      const pidStr = execSync(`lsof -ti:${port} -sTCP:LISTEN`, { encoding: 'utf-8', timeout: 3000 }).trim();
      if (!pidStr) {
        issues.push(`Port ${port} not listening`);
      }
    } catch {
      issues.push(`Port ${port} not listening`);
    }

    const logPath = `${projectRoot}/${logDir}/main.log`;
    if (existsSync(logPath)) {
      const logs = readFileSync(logPath, 'utf-8').split('\n').slice(-50);
      const errors = logs.filter(l => l.toLowerCase().includes('error'));
      if (errors.length > 0) {
        issues.push(`Recent errors: ${errors.slice(-3).join(' | ')}`);
      }
    }

    return { issues, recommendation: 'Check logs with agent_os_logs' };
  }

  protected wrap(data: AgentOsRestartResult, _context: ToolContext): ToolResponse<AgentOsRestartResult> {
    return {
      success: data.success,
      data,
    };
  }
}
