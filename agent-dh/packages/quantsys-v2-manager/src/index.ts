import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { execSync, spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';

export default class QuantsysV2Manager extends Service {
  static inject = ['tools'];
  static Config = z.object({
    projectRoot: z.string().default('/Users/yunpeng/pi-investment/quantsys-v2'),
    port: z.number().default(5001),
    healthCheckUrl: z.string().default('http://localhost:5001/api/health'),
    startupScript: z.string().default('adapters/inbound/fastapi_app/main.py'),
    activateScript: z.string().default('activate-py313.sh'),
    logFile: z.string().default('logs/fastapi_5001.log'),
  }).default({} as any);

  private config: any;

  constructor(ctx: Context, config: any) {
    super(ctx, 'quantsys-v2-manager');
    this.config = { ...QuantsysV2Manager.Config.default(), ...config };
    this.registerTools();
  }

  private registerTools() {
    // 1. quantsys_v2_status - 检查服务状态
    this.ctx.tools.register(defineTool({
      name: 'quantsys_v2_status',
      description: '检查 quantsys-v2 后端服务状态：进程/端口/健康检查/最近日志错误。用于：重启前后验证、故障诊断',
      parameters: {},
      output: {
        schema: { 
          type: 'object', 
          additionalProperties: true,
          properties: {
            running: { type: 'boolean', description: '进程是否运行' },
            pid: { type: 'number', description: '进程 PID' },
            port_listening: { type: 'boolean', description: '端口是否监听' },
            health_ok: { type: 'boolean', description: '健康检查是否通过' },
            recent_errors: { type: 'array', items: { type: 'string' }, description: '最近5条错误日志' },
          }
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async () => {
        return this.checkStatus() as any;
      },
    } as any));

    // 2. quantsys_v2_restart - 智能重启
    this.ctx.tools.register(defineTool({
      name: 'quantsys_v2_restart',
      description: '重启 quantsys-v2 后端服务（智能流程：停止→验证→启动→健康检查→失败诊断）。用于：服务挂死/升级/配置变更后恢复',
      parameters: {
        force: { 
          type: 'boolean', 
          description: '是否强制杀死（SIGKILL）。false=优雅停止（SIGTERM）然后等待，true=立即SIGKILL',
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

    // 3. quantsys_v2_logs - 查看日志
    this.ctx.tools.register(defineTool({
      name: 'quantsys_v2_logs',
      description: '查看 quantsys-v2 最近日志（默认最后50行），可按关键词过滤（如 ERROR/exception）',
      parameters: {
        lines: { type: 'number', description: '显示最后N行（默认50）' },
        grep: { type: 'string', description: '过滤关键词（如 ERROR），不传则显示全部' },
      },
      output: {
        schema: { type: 'object', additionalProperties: true },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return this.getLogs(args.lines ?? 50, args.grep) as any;
      },
    } as any));
  }

  private checkStatus() {
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
      pid,
      port,
      port_listening: portListening,
      health_ok: healthOk,
      health_error: healthError,
      recent_errors: recentErrors,
      timestamp: new Date().toISOString(),
    };
  }

  private restart(force: boolean, waitSec: number) {
    const { port, projectRoot, startupScript, activateScript, healthCheckUrl } = this.config;
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

    return { issues, recommendation: issues.length > 0 ? 'Check logs with quantsys_v2_logs, verify PG/port' : 'Unknown issue' };
  }

  private getLogs(lines: number, grep?: string) {
    const { projectRoot, logFile } = this.config;
    const logPath = `${projectRoot}/${logFile}`;
    
    if (!existsSync(logPath)) {
      return { error: `Log file not found: ${logPath}` };
    }

    try {
      let cmd = `tail -${lines} "${logPath}"`;
      if (grep) {
        cmd += ` | grep -i "${grep}"`;
      }
      const output = execSync(cmd, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });
      return { lines: output.split('\n'), total: output.split('\n').length };
    } catch (e: any) {
      return { error: e.message };
    }
  }
}
