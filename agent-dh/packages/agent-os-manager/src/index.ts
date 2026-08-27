import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { execSync, spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';

export default class AgentOsManager extends Service {
  static inject = ['tools'];
  static Config = z.object({
    projectRoot: z.string().default('/Users/yunpeng/pi-investment/agent-os'),
    port: z.number().default(8080),
    healthCheckUrl: z.string().default('http://localhost:8080/health'),
    startCommand: z.string().default('./bin/agent-os serve'),
    logDir: z.string().default('logs'),
  }).default({} as any);

  private config: any;

  constructor(ctx: Context, config: any) {
    super(ctx, 'agent-os-manager');
    this.config = { ...AgentOsManager.Config.default(), ...config };
    this.registerTools();
  }

  private registerTools() {
    // 1. agent_os_status
    this.ctx.tools.register(defineTool({
      name: 'agent_os_status',
      description: '检查 Agent OS 服务状态：进程/端口/健康检查/最近日志错误。用于：重启前后验证、故障诊断',
      parameters: {},
      output: {
        schema: { 
          type: 'object', 
          additionalProperties: true,
          properties: {
            running: { type: 'boolean' },
            pid: { type: 'number', description: '进程 PID，0 表示服务未运行' },
            port_listening: { type: 'boolean' },
            health_ok: { type: 'boolean' },
            recent_errors: { type: 'array', items: { type: 'string' } },
          }
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async () => {
        return this.checkStatus() as any;
      },
    } as any));

    // 2. agent_os_restart
    this.ctx.tools.register(defineTool({
      name: 'agent_os_restart',
      description: '重启 Agent OS 服务（智能流程：停止→验证→启动→健康检查→失败诊断）。用于：服务挂死/升级/配置变更后恢复',
      parameters: {
        force: { 
          type: 'boolean', 
          description: '是否强制杀死（SIGKILL）',
        },
        wait_startup_sec: {
          type: 'number',
          description: '启动后等待多少秒进行健康检查（默认30）',
        },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 120000,
      execute: async (args: any) => {
        return this.restart(args.force ?? false, args.wait_startup_sec ?? 30) as any;
      },
    } as any));

    // 3. agent_os_logs
    this.ctx.tools.register(defineTool({
      name: 'agent_os_logs',
      description: '查看 Agent OS 最近日志（默认最后50行），可按关键词过滤',
      parameters: {
        lines: { type: 'number', description: '显示最后N行（默认50）' },
        grep: { type: 'string', description: '过滤关键词' },
        source: { 
          type: 'string', 
          description: '日志源：main（主服务）/scheduler（调度器）/all（默认main）', 
        },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return this.getLogs(args.lines ?? 50, args.grep, args.source ?? 'main') as any;
      },
    } as any));
  }

  private checkStatus() {
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
    let healthError = null;
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

  private restart(force: boolean, waitSec: number) {
    const { port, projectRoot, startCommand, healthCheckUrl } = this.config;
    const steps: any[] = [];

    try {
      // 2026-08-28 根本性修复：Agent OS 由 launchd 守护（KeepAlive + serve-guard.sh 幂等清场）。
      // 重启的唯一权威入口是 launchctl kickstart -k（原子 kill+重拉，经守护脚本清场），
      // 避免"插件杀进程 vs launchd 重拉"的双实例竞争（8-27 18:17 端口冲突的根因）。
      const uid = execSync('id -u', { encoding: 'utf-8', timeout: 3000 }).trim();
      const launchdLabel = (this.config as any).launchdLabel || 'com.pi-investment.agent-os';
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
      return { success: false, steps, diagnosis };

    } catch (e: any) {
      steps.push({ step: 'fatal_error', error: e.message });
      return { success: false, steps, error: e.message };
    }
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

  private getLogs(lines: number, grep?: string, source?: string) {
    const { projectRoot, logDir } = this.config;
    const logFile = source === 'scheduler' ? 'scheduler.log' : 'main.log';
    const logPath = `${projectRoot}/${logDir}/${logFile}`;
    
    if (!existsSync(logPath)) {
      return { error: `Log file not found: ${logPath}` };
    }

    try {
      let cmd = `tail -${lines} "${logPath}"`;
      if (grep) {
        cmd += ` | grep -i "${grep}"`;
      }
      const output = execSync(cmd, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });
      return { lines: output.split('\n'), total: output.split('\n').length, source: logFile };
    } catch (e: any) {
      return { error: e.message };
    }
  }
}
