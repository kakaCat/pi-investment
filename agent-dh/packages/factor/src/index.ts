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
 * Factor Plugin for Agent-DH
 *
 * Factor calculation and effectiveness analysis.
 */
export default class FactorPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'factor');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 因子计算
    ctx.tools.register(defineTool({
      name: 'factor_calculate',
      description: '计算个股的技术因子和财务因子当前值。适用于：量化选股前获取因子数据、验证个股当前因子状态、为 model_train 挑选特征。评估因子本身的预测能力（是否有效）用 factor_analyze。',
      parameters: {
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
        factors: {
          type: 'array',
          description: '指定因子列表，如 ["rsi", "macd", "roe"]。可选：rsi（相对强弱）、macd、pe（市盈率）、pb（市净率）、roe（净资产收益率）、turnover（换手率）、volatility（波动率）。不传则计算全部因子（更全但更慢）',
          items: { type: 'string' },
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            date: { type: 'string', description: '计算日期' },
            factors: { type: 'object', description: '因子值字典', additionalProperties: true },
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
        return qv2.calculateFactors({
          symbol: args.symbol,
          factors: args.factors,
        }) as any;
      },
    } as any));

    // 因子分析
    ctx.tools.register(defineTool({
      name: 'factor_analyze',
      description: '分析因子的历史有效性：IC（信息系数）、IR（信息比率）、覆盖率、单调性、换手率，并给出有效性结论。适用于：构建策略前筛选有效因子、定期检查因子是否失效。解读参考：IR>0.5 通常认为因子有效；覆盖率低的因子结论可信度差。',
      parameters: {
        factor_name: {
          type: 'string',
          description: '因子名称，如 roe、pe、rsi、macd',
          required: true,
        },
        start_date: {
          type: 'string',
          description: '开始日期，格式 YYYY-MM-DD，如 2023-01-01。样本建议覆盖至少 1 年并跨越不同市场环境，结论才可靠',
        },
        end_date: {
          type: 'string',
          description: '结束日期，格式 YYYY-MM-DD，如 2024-12-31',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            factor_name: { type: 'string', description: '因子名称' },
            ic_mean: { type: 'number', description: 'IC均值（信息系数，越高越好）' },
            ic_std: { type: 'number', description: 'IC标准差' },
            ir: { type: 'number', description: 'IR信息比率（IC均值/标准差，>0.5较好）' },
            coverage: { type: 'number', description: '覆盖率（%）' },
            monotonicity: { type: 'number', description: '单调性评分（0-1）' },
            turnover: { type: 'number', description: '因子换手率（%）' },
            conclusion: { type: 'string', description: '有效性结论' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        return qv2.analyzeFactor({
          factor_name: args.factor_name,
          start_date: args.start_date,
          end_date: args.end_date,
        }) as any;
      },
    } as any));
  }
}
