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
      description: '生成数据质量报告，检查缺失数据、延迟、异常值。用于：定期审查数据质量、发现数据问题',
      parameters: {
        data_type: {
          type: 'string',
          description: '数据类型：quote（行情）、kline（K线）、financial（财务）、all（全部，默认）',
          enum: ['quote', 'kline', 'financial', 'all'],
          default: 'all',
        },
        days: {
          type: 'integer',
          description: '检查最近多少天的数据，默认7天',
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
        render: (_args, value) => [{
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
      description: '数据管理工具：查看数据源状态、触发数据补录、清理缓存。用于：手动触发数据更新、解决数据缺失问题',
      parameters: {
        command: {
          type: 'string',
          description: '命令：status（查看状态）、refresh（触发刷新）、cleanup（清理缓存）、backup（备份数据）',
          enum: ['status', 'refresh', 'cleanup', 'backup'],
          required: true,
        },
        data_type: {
          type: 'string',
          description: '数据类型：quote（行情）、kline（K线）、financial（财务）、dividend（分红）、macro（宏观）',
        },
        symbol: {
          type: 'string',
          description: '股票代码（refresh 时可选，指定补录某只股票）',
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
        render: (_args, value) => [{
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
  }
}
