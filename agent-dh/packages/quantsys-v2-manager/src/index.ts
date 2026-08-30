import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { createQuantsysV2StatusTool } from './tools/QuantsysV2StatusTool';
import { createQuantsysV2RestartTool } from './tools/QuantsysV2RestartTool';
import { createQuantsysV2LogsTool } from './tools/QuantsysV2LogsTool';

export interface Config {
  projectRoot?: string;
  port?: number;
  healthCheckUrl?: string;
  startupScript?: string;
  activateScript?: string;
  logFile?: string;
  baseURL?: string;
}

/**
 * QuantsysV2Manager Plugin for Agent-DH
 *
 * Manage quantsys-v2 backend service: status check, restart, logs.
 */
export default class QuantsysV2Manager extends Service {
  static inject = ['tools'];
  static Config = z.object({
    projectRoot: z.string().default('/Users/yunpeng/pi-investment/quantsys-v2'),
    port: z.number().default(5001),
    healthCheckUrl: z.string().default('http://localhost:5001/api/health'),
    startupScript: z.string().default('adapters/inbound/fastapi_app/main.py'),
    activateScript: z.string().default('activate-py313.sh'),
    logFile: z.string().default('logs/launchd-stdout.log'),
    baseURL: z.string().default('http://localhost:5001'),
  }).default({} as any);

  private config: any;
  private qv2Client: QuantsysV2Client;

  constructor(ctx: Context, config: any) {
    super(ctx, 'quantsys-v2-manager');
    this.config = { ...QuantsysV2Manager.Config.default({} as any), ...config };

    // 创建 QuantsysV2Client 实例
    this.qv2Client = new QuantsysV2Client({
      baseURL: this.config.baseURL,
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx } = this;

    const config = {
      projectRoot: this.config.projectRoot,
      port: this.config.port,
      healthCheckUrl: this.config.healthCheckUrl,
      startupScript: this.config.startupScript,
      activateScript: this.config.activateScript,
      logFile: this.config.logFile,
    };

    // 注册 quantsys-v2 状态检查工具（使用 API）
    ctx.tools.register(createQuantsysV2StatusTool(this.qv2Client));

    // 注册 quantsys-v2 重启工具（本地命令）
    ctx.tools.register(createQuantsysV2RestartTool(config));

    // 注册 quantsys-v2 日志查询工具（本地文件读取）
    ctx.tools.register(createQuantsysV2LogsTool({
      projectRoot: config.projectRoot,
      logFile: config.logFile,
    }));
  }
}

// Re-export tools for testing
export {
  QuantsysV2StatusTool,
  createQuantsysV2StatusTool,
} from './tools/QuantsysV2StatusTool';
export {
  QuantsysV2RestartTool,
  createQuantsysV2RestartTool,
} from './tools/QuantsysV2RestartTool';
export {
  QuantsysV2LogsTool,
  createQuantsysV2LogsTool,
} from './tools/QuantsysV2LogsTool';
export type {
  QuantsysV2StatusParams,
  QuantsysV2StatusResult,
} from './tools/QuantsysV2StatusTool';
export type {
  QuantsysV2RestartParams,
  QuantsysV2RestartResult,
} from './tools/QuantsysV2RestartTool';
export type {
  QuantsysV2LogsParams,
  QuantsysV2LogsResult,
} from './tools/QuantsysV2LogsTool';
