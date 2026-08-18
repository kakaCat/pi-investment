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
 * Market Analysis Plugin for Agent-DH
 *
 * Market style detection, sector analysis, chip distribution analysis.
 */
export default class MarketPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'market');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 市场风格检测
    ctx.tools.register(defineTool({
      name: 'market_style_detect',
      description: '检测当前市场主导风格（价值/成长/大盘/小盘/周期/防御）及置信度，返回领涨领跌板块和配置建议。适用于：定期（如每周）判断市场偏好、指导配置方向——风格偏价值时增配低估值蓝筹，偏成长时关注科技成长。行业层面的细节分析用 sector_analysis。',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            primary_style: { type: 'string', description: '主风格：value（价值）/growth（成长）/large_cap（大盘）/small_cap（小盘）/cyclical（周期）/defensive（防御）' },
            secondary_style: { type: 'string', description: '次要风格' },
            confidence: { type: 'number', description: '置信度（0-1）' },
            description: { type: 'string', description: '风格描述和配置建议' },
            leading_sectors: { type: 'array', description: '领涨板块' },
            lagging_sectors: { type: 'array', description: '领跌板块' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async () => {
        return qv2.getMarketStyle() as any;
      },
    } as any));

    // 行业分析
    ctx.tools.register(defineTool({
      name: 'sector_analysis',
      description: '分析行业板块表现、资金流向与轮动信号。适用于：发现强势板块、判断行业轮动节奏、选择配置方向。与 market_style_detect 的分工：后者看市场整体风格，本工具看行业细节。确认轮动方向后可用 rotation_proposal 生成调仓提案。',
      parameters: {
        sector: {
          type: 'string',
          description: '行业名称或代码，如 白酒、半导体、银行。传入则返回该行业详情；不传则返回全部行业排名',
        },
        days: {
          type: 'integer',
          description: '分析周期（交易日），默认 5。短线轮动看 5-10 天，中线趋势看 20-60 天',
          default: 5,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            sectors: { type: 'array', description: '行业列表，按涨幅排序' },
            top_performers: { type: 'array', description: '表现最好的行业' },
            worst_performers: { type: 'array', description: '表现最差的行业' },
            rotation_signal: { type: 'string', description: '轮动信号' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return qv2.getSectorAnalysis({
          sector: args.sector,
          days: args.days || 5,
        }) as any;
      },
    } as any));

    // 筹码分析
    ctx.tools.register(defineTool({
      name: 'chip_analysis',
      description: '分析个股筹码分布与成本结构：平均成本、获利盘比例、筹码集中度、支撑/压力位。适用于：判断支撑压力位、识别主力成本区、评估突破有效性。解读参考：获利盘比例过高（如>90%）说明浮盈兑现压力大，过低说明套牢盘沉重、反弹阻力大。',
      parameters: {
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            avg_cost: { type: 'number', description: '平均成本（元）' },
            profit_ratio: { type: 'number', description: '获利盘比例（%）' },
            concentration: { type: 'number', description: '筹码集中度（%）' },
            support_levels: { type: 'array', description: '支撑位列表' },
            resistance_levels: { type: 'array', description: '压力位列表' },
            chip_distribution: { type: 'array', description: '筹码分布数据' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return qv2.getChipDistribution(args.symbol) as any;
      },
    } as any));
  }
}
