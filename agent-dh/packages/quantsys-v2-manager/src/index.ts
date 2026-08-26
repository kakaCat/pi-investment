/**
 * quantsys-v2 service manager
 * Manages the lifecycle of the quantsys-v2 backend service
 */
import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';

export interface Config {
  projectRoot: string;
  port: number;
  healthCheckUrl: string;
  startupScript: string;
  activateScript: string;
  logFile: string;
}

export const name = 'quantsys-v2-manager';

export const Config = z.object({
  projectRoot: z.string().required(),
  port: z.number().default(5001),
  healthCheckUrl: z.string().default('http://localhost:5001/api/health'),
  startupScript: z.string().required(),
  activateScript: z.string().required(),
  logFile: z.string().required(),
});

export class QuantsysV2Manager extends Service {
  constructor(public ctx: Context, public config: Config) {
    super(ctx, name);

    ctx.on('ready', async () => {
      this.ctx.logger('quantsys-v2-manager').info('Service manager initialized', {
        projectRoot: config.projectRoot,
        port: config.port,
      });

      // TODO: Implement health check and auto-restart logic if needed
    });
  }
}

export default QuantsysV2Manager;
