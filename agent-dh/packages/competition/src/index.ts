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
 * Competition Intelligence Plugin for Agent-DH
 *
 * Market competition analysis: opponent behavior, battlefield assessment, manipulation detection.
 */
export default class CompetitionPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'competition');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 1. 对手行为分析
    ctx.tools.register(defineTool({
      name: 'opponent_behavior',
      description: '分析市场参与者（散户/机构/游资）的行为与情绪，识别对手错误和博弈机会。适用于：判断当前谁在主导市场、散户是否恐慌（错杀机会）、机构是否出货（撤退信号）、游资是否撤退（炒作结束）。返回机会信号与风险警告列表，是博弈决策的核心输入。',
      parameters: {
        symbol: {
          type: 'string',
          description: '股票代码，如 600519。传入则分析该股的参与者结构；不传则分析全市场总体格局',
        },
        focus: {
          type: 'string',
          description: '分析重点。retail：散户情绪（panic 恐慌=潜在买点，fomo 狂热=潜在卖点）；institution：机构动向（建仓/出货）；hot_money：游资活跃度（拉高/撤退）；all（默认）：三方综合分析',
          enum: ['retail', 'institution', 'hot_money', 'all'],
          default: 'all',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码或 market' },
            retail_sentiment: { type: 'string', description: '散户情绪：panic/fear/neutral/greed/fomo' },
            institution_flow: { type: 'string', description: '机构资金流向：heavy_inflow/inflow/neutral/outflow/heavy_outflow' },
            hot_money_activity: { type: 'string', description: '游资活跃度：high/medium/low' },
            opportunity_signals: { type: 'array', description: '博弈机会信号列表' },
            risk_warnings: { type: 'array', description: '风险警告列表' },
            analysis_summary: { type: 'string', description: '综合分析摘要' },
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
        return qv2.getOpponentBehavior({
          symbol: args.symbol,
          focus: args.focus || 'all',
        }) as any;
      },
    } as any));

    // 2. 池子战场评估
    ctx.tools.register(defineTool({
      name: 'pool_battlefield',
      description: '评估指定股票池的博弈竞争优势：综合评分、对手分析、风险评估、操作建议及其在所有池中的排名。适用于：定期评估各池子优劣、决定把资金和注意力投向哪个战场。先用 pool_list 获取池子ID；池内个股的参与者细节用 opponent_behavior。',
      parameters: {
        pool_id: {
          type: 'integer',
          description: '股票池ID，通过 pool_list 获取',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            pool_id: { type: 'integer', description: '股票池ID' },
            pool_name: { type: 'string', description: '股票池名称' },
            competitive_score: { type: 'number', description: '竞争优势评分（0-100，越高越好）' },
            opponent_analysis: { type: 'object', description: '对手分析详情', additionalProperties: true },
            risk_assessment: { type: 'object', description: '风险评估详情', additionalProperties: true },
            recommendations: { type: 'array', description: '操作建议列表' },
            ranking: { type: 'integer', description: '在所有池子中的排名' },
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
        return qv2.getPoolBattlefield({ pool_id: args.pool_id }) as any;
      },
    } as any));

    // 3. 操纵检测
    ctx.tools.register(defineTool({
      name: 'manipulation_detect',
      description: '检测个股操纵嫌疑（拉高出货、对倒交易、诱多诱空等），给出嫌疑评分、检测到的模式、证据列表和操作建议。适用于：买入陌生标的前排雷、识别操纵崩盘后的抄底机会。评分高（如>70）时应回避，或等待崩盘后的机会窗口。',
      parameters: {
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
        days: {
          type: 'integer',
          description: '分析最近 N 天的数据，默认 30。操纵周期较长时可加大到 60-90',
          default: 30,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            manipulation_score: { type: 'number', description: '操纵嫌疑评分（0-100，越高嫌疑越大）' },
            detected_patterns: { type: 'array', description: '检测到的操纵模式列表' },
            risk_level: { type: 'string', description: '风险等级：low（低风险）/medium（中风险）/high（高风险）' },
            recommendation: { type: 'string', description: '建议：avoid（回避）/watch（观望）/opportunity（操纵后机会）' },
            evidence: { type: 'array', description: '证据列表' },
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
        return qv2.detectManipulation({
          symbol: args.symbol,
          days: args.days || 30,
        }) as any;
      },
    } as any));
  }
}
