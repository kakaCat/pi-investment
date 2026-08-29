import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { createAgentOsStatusTool } from './tools/AgentOsStatusTool';
import { createAgentOsRestartTool } from './tools/AgentOsRestartTool';
import { createAgentOsLogsTool } from './tools/AgentOsLogsTool';

export interface Config {
  projectRoot?: string;
  port?: number;
  healthCheckUrl?: string;
  startCommand?: string;
  logDir?: string;
  launchdLabel?: string;
}

/**
 * AgentOsManager Plugin for Agent-DH
 *
 * Manage agent-os backend service: status check, restart, logs.
 */
export default class AgentOsManager extends Service {
  static inject = ['tools'];
  static Config = z.object({
    projectRoot: z.string().default('/Users/yunpeng/pi-investment/agent-os'),
    port: z.number().default(8080),
    healthCheckUrl: z.string().default('http://localhost:8080/health'),
    startCommand: z.string().default('./bin/agent-os serve'),
    logDir: z.string().default('logs'),
    launchdLabel: z.string().default('com.pi-investment.agent-os'),
  }).default({} as any);

  private config: any;

  constructor(ctx: Context, config: any) {
    super(ctx, 'agent-os-manager');
    this.config = { ...AgentOsManager.Config.default({} as any), ...config };
    this.registerTools();
  }

  private registerTools() {
    const { ctx } = this;
    const config = {
      projectRoot: this.config.projectRoot,
      port: this.config.port,
      healthCheckUrl: this.config.healthCheckUrl,
      startCommand: this.config.startCommand,
      logDir: this.config.logDir,
      launchdLabel: this.config.launchdLabel,
    };

    // 注册 agent-os 状态检查工具
    ctx.tools.register(createAgentOsStatusTool(config));

    // 注册 agent-os 重启工具
    ctx.tools.register(createAgentOsRestartTool(config));

    // 注册 agent-os 日志查询工具
    ctx.tools.register(createAgentOsLogsTool({
      projectRoot: config.projectRoot,
      logDir: config.logDir,
    }));
  }
}

// Re-export tools for testing
export {
  AgentOsStatusTool,
  createAgentOsStatusTool,
} from './tools/AgentOsStatusTool';
export {
  AgentOsRestartTool,
  createAgentOsRestartTool,
} from './tools/AgentOsRestartTool';
export {
  AgentOsLogsTool,
  createAgentOsLogsTool,
} from './tools/AgentOsLogsTool';
export type {
  AgentOsStatusParams,
  AgentOsStatusResult,
} from './tools/AgentOsStatusTool';
export type {
  AgentOsRestartParams,
  AgentOsRestartResult,
} from './tools/AgentOsRestartTool';
export type {
  AgentOsLogsParams,
  AgentOsLogsResult,
} from './tools/AgentOsLogsTool';
