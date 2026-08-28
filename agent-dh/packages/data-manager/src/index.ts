import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

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
    ctx.tools.register(defineTool({
      name: 'data_quality_report',
      description: '生成数据质量报告：整体评分、缺失数据、延迟数据、异常值列表及质量摘要。适用于：定期（如每日盘前）检查数据健康度——所有分析和交易决策都依赖数据质量，评分偏低时应先用 data_manager 修复数据再做决策。',
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
            data_type: { type: 'string', description: '数据类型' },
            check_date: { type: 'string', description: '检查日期' },
            overall_score: { type: 'number', description: '整体质量评分（0-100）' },
            missing_data: { type: 'array', description: '缺失数据列表' },
            delayed_data: { type: 'array', description: '延迟数据列表' },
            anomalies: { type: 'array', description: '异常值列表' },
            summary: { type: 'string', description: '质量摘要' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        return qv2.getDataQualityReport({
          data_type: args.data_type || 'all',
          days: args.days || 7,
        }) as any;
      },
    } as any));

    // 数据管理
    ctx.tools.register(defineTool({
      name: 'data_manager',
      description: '数据管理操作：查看数据源状态、触发数据补录刷新、清理缓存、备份数据。适用于：data_quality_report 发现缺失后手动补录、数据异常时排查数据源。注意：refresh/cleanup/backup 是写操作，会改变数据或缓存状态；status 为只读。',
      parameters: {
        command: {
          type: 'string',
          description: '命令。status：查看各数据源连接与同步状态（只读）；refresh：触发数据补录/刷新（可配合 data_type、symbol 缩小范围）；cleanup：清理过期缓存；backup：备份数据',
          enum: ['status', 'refresh', 'cleanup', 'backup'],
          required: true,
        },
        data_type: {
          type: 'string',
          description: '限定数据类型：quote（行情）、kline（K线）、financial（财务）、dividend（分红）、macro（宏观）。不传则作用于全部类型',
        },
        symbol: {
          type: 'string',
          description: '股票代码，仅 refresh 时有效：指定只补录某一只股票，如 600519',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            command: { type: 'string', description: '执行的命令' },
            status: { type: 'string', description: '执行状态' },
            details: { type: 'object', description: '详细信息', additionalProperties: true },
            message: { type: 'string', description: '结果消息' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        return qv2.dataManager({
          command: args.command,
          data_type: args.data_type,
          symbol: args.symbol,
        }) as any;
      },
    } as any));

    // K线每日同步（调用 quantsys-v2 HTTP API）
    ctx.tools.register(defineTool({
      name: 'kline_daily_sync',
      description: '执行每日K线同步：调用 quantsys-v2 业务逻辑同步指定日期所有活跃股票的K线数据。适用于：每日定时任务（盘后同步）、手动补录缺失日期数据。返回同步结果：成功数、失败数、数据量、耗时。',
      parameters: {
        date: {
          type: 'string',
          description: '同步日期 YYYY-MM-DD（默认昨日，因当日数据通常收盘后才可用）',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean', description: '是否成功' },
            sync_date: { type: 'string', description: '同步日期' },
            success_count: { type: 'number', description: '成功股票数' },
            failed_count: { type: 'number', description: '失败股票数' },
            total_stocks: { type: 'number', description: '总股票数' },
            total_rows: { type: 'number', description: '同步数据条数' },
            elapsed_time: { type: 'number', description: '耗时（秒）' },
            message: { type: 'string', description: '结果消息' },
            failed_symbols: { type: 'array', description: '失败股票列表（前20只）' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 300000, // 5分钟超时（5532只股票需要时间）
      execute: async (args: any) => {
        try {
          const result = await qv2.syncDailyKlines({
            date: args.date,
          });
          return result as any;
        } catch (error: any) {
          return {
            success: false,
            sync_date: args.date || new Date(Date.now() - 86400000).toISOString().split('T')[0],
            success_count: 0,
            failed_count: 0,
            total_stocks: 0,
            total_rows: 0,
            elapsed_time: 0,
            message: `❌ K线同步失败: ${error.message}`,
            failed_symbols: [],
          } as any;
        }
      },
    } as any));
  }
}
