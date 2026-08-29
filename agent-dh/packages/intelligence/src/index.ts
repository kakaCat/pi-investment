import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { createWatchListTool } from './tools/WatchListTool';
import { createWatchManageTool } from './tools/WatchManageTool';
import { createMarketAlertTool } from './tools/MarketAlertTool';
import { createSignalTrackTool } from './tools/SignalTrackTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Intelligence Plugin for Agent-DH
 *
 * Market intelligence, watchlist, signal tracking.
 */
export default class IntelligencePlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'intelligence');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 盯盘规则列表
    ctx.tools.register(createWatchListTool(qv2));

    // 盯盘规则管理
    ctx.tools.register(createWatchManageTool(qv2));

    // 市场异动提醒
    ctx.tools.register(createMarketAlertTool(qv2));

    // M3-1 信号质量追踪
    ctx.tools.register(createSignalTrackTool(qv2));
  }
}
