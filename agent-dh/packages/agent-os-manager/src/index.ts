/**
 * agent-os service manager
 * Manages the lifecycle of the agent-os backend service
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';

export interface Config {
  projectRoot: string;
  port: number;
  healthCheckUrl: string;
  startCommand: string;
  logDir: string;
}

export const name = 'agent-os-manager';

export const Config = z.object({
  projectRoot: z.string().required(),
  port: z.number().default(8080),
  healthCheckUrl: z.string().default('http://localhost:8080/api/v1/health'),
  startCommand: z.string().required(),
  logDir: z.string().required(),
});

export class AgentOSManager extends Service {
  constructor(public ctx: Context, public config: Config) {
    super(ctx, name);

    ctx.on('ready', async () => {
      this.ctx.logger('agent-os-manager').info('Service manager initialized', {
        projectRoot: config.projectRoot,
        port: config.port,
      });

      // TODO: Implement health check and auto-restart logic if needed
    });
  }
}

export default AgentOSManager;
