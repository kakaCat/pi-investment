import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import {
  DataQualityReportTool,
  dataQualityReportPrompt,
} from './tools/DataQualityReportTool';
import {
  DataManagerTool,
  dataManagerPrompt,
} from './tools/DataManagerTool';
import {
  KlineDailySyncTool,
  klineDailySyncPrompt,
} from './tools/KlineDailySyncTool';

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
    const dataQualityReportTool = new DataQualityReportTool(qv2);
    ctx.tools.register(defineTool({
      name: 'data_quality_report',
      description: dataQualityReportPrompt.description,
      parameters: {
        data_type: {
          type: 'string',
          description: '检查范围。all（默认）：全部；quote：行情；kline：K线；financial：财务',
          enum: ['quote', 'kline', 'financial', 'all'],
          default: 'all',
        },
        days: {
          type: 'integer',
          description: '检查最近 N 天的数据，默认 7',
          default: 7,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            data_type: { type: 'string' },
            check_date: { type: 'string' },
            overall_score: { type: 'number' },
            missing_data: { type: 'array' },
            delayed_data: { type: 'array' },
            anomalies: { type: 'array' },
            summary: { type: 'string' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 20000,
      execute: async (args: any) => {
        const result = await dataQualityReportTool.run(args, {});
        if (!result.success) {
          throw new Error(result.message);
        }
        return result.data as any;
      },
    } as any));

    // 数据管理
    const dataManagerTool = new DataManagerTool(qv2);
    ctx.tools.register(defineTool({
      name: 'data_manager',
      description: dataManagerPrompt.description,
      parameters: {
        operation: {
          type: 'string',
          description: '操作类型：status（查询状态）/ refresh（刷新数据）/ cleanup（清理缓存）/ backup（备份数据）',
          enum: ['status', 'refresh', 'cleanup', 'backup'],
          required: true,
        },
        data_type: {
          type: 'string',
          description: '数据类型：quote / kline / financial / all（默认）',
          enum: ['quote', 'kline', 'financial', 'all'],
        },
        symbol: {
          type: 'string',
          description: '股票代码（6位数字），仅 refresh 时有效',
        },
        start_date: {
          type: 'string',
          description: '开始日期 YYYY-MM-DD',
        },
        end_date: {
          type: 'string',
          description: '结束日期 YYYY-MM-DD',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            operation: { type: 'string' },
            data_type: { type: 'string' },
            status: { type: 'string' },
            message: { type: 'string' },
            details: { type: 'object', additionalProperties: true },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        const result = await dataManagerTool.run(args, {});
        if (!result.success) {
          throw new Error(result.message);
        }
        return result.data as any;
      },
    } as any));

    // K线每日同步
    const klineDailySyncTool = new KlineDailySyncTool(qv2);
    ctx.tools.register(defineTool({
      name: 'kline_daily_sync',
      description: klineDailySyncPrompt.description,
      parameters: {
        date: {
          type: 'string',
          description: '同步日期 YYYY-MM-DD（默认今日）',
        },
        symbols: {
          type: 'array',
          description: '股票代码数组（6位数字）。不传则同步全市场',
          items: { type: 'string' },
        },
        force: {
          type: 'boolean',
          description: '是否强制重新同步已存在的数据',
          default: false,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            sync_date: { type: 'string' },
            total_symbols: { type: 'number' },
            success_count: { type: 'number' },
            failed_count: { type: 'number' },
            skipped_count: { type: 'number' },
            failed_symbols: { type: 'array', items: { type: 'string' } },
            duration_seconds: { type: 'number' },
            message: { type: 'string' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 300000,
      execute: async (args: any) => {
        const result = await klineDailySyncTool.run(args, {});
        if (!result.success) {
          throw new Error(result.message);
        }
        return result.data as any;
      },
    } as any));
  }
}

// Re-export tools for testing
export {
  DataQualityReportTool,
  DataManagerTool,
  KlineDailySyncTool,
  dataQualityReportPrompt,
  dataManagerPrompt,
  klineDailySyncPrompt,
};
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
