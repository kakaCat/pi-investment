import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { createDataQualityReportTool } from './tools/DataQualityReportTool';
import { createDataManagerTool } from './tools/DataManagerTool';
import { createKlineDailySyncTool } from './tools/KlineDailySyncTool';

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

/**
 * Data Manager Plugin for Agent-DH
 *
 * Data quality monitoring and management.
 */
export default class DataManagerPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'data-manager');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 数据质量报告
    ctx.tools.register(createDataQualityReportTool(qv2));

    // 数据管理
    ctx.tools.register(createDataManagerTool(qv2));

    // K线每日同步
    ctx.tools.register(createKlineDailySyncTool(qv2));
  }
}

// Re-export tools for testing
export {
  DataQualityReportTool,
  dataQualityReportPrompt,
} from './tools/DataQualityReportTool';
export {
  DataManagerTool,
  dataManagerPrompt,
} from './tools/DataManagerTool';
export {
  KlineDailySyncTool,
  klineDailySyncPrompt,
} from './tools/KlineDailySyncTool';
export type {
  DataQualityReportParams,
  DataQualityReportResult,
} from './tools/DataQualityReportTool';
export type {
  DataManagerParams,
  DataManagerResult,
} from './tools/DataManagerTool';
export type {
  KlineDailySyncParams,
  KlineDailySyncResult,
} from './tools/KlineDailySyncTool';
