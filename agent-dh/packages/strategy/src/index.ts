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
 * Strategy Plugin for Agent-DH
 *
 * Strategy execution, backtest, screening, sector rotation.
 */
export default class StrategyPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'strategy');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 策略执行
    ctx.tools.register(defineTool({
      name: 'strategy_execute',
      description: '执行策略回测或生成交易信号。用于：验证策略历史表现、获取当前买卖信号',
      parameters: {
        strategy_id: {
          type: 'integer',
          description: '策略ID',
          required: true,
        },
        symbols: {
          type: 'array',
          description: '股票代码列表，如：["600519", "000001"]',
          items: { type: 'string' },
        },
        mode: {
          type: 'string',
          description: '执行模式：backtest（回测，验证历史表现）、signal（生成当前信号，默认）',
          enum: ['backtest', 'signal'],
          default: 'signal',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            strategy_id: { type: 'integer', description: '策略ID' },
            mode: { type: 'string', description: '执行模式' },
            signals: { type: 'array', description: '交易信号列表' },
            backtest_result: { type: 'object', description: '回测结果（mode=backtest时）', additionalProperties: true },
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
        if (args.mode === 'backtest') {
          return qv2.backtestStrategy({
            strategy_id: args.strategy_id,
            symbols: args.symbols,
            start_date: '',
            end_date: '',
          }) as any;
        }
        return qv2.generateSignals({
          strategy_id: args.strategy_id,
          symbols: args.symbols,
        }) as any;
      },
    } as any));

    // 机会扫描
    ctx.tools.register(defineTool({
      name: 'opportunity_scan',
      description: '扫描市场机会，基于多因子综合评分筛选优质标的。用于：发现被低估的股票、寻找技术形态突破、识别资金流入标的',
      parameters: {
        conditions: {
          type: 'array',
          description: '筛选条件列表，支持：roe_gt_15（ROE>15%）、pe_lt_30（PE<30）、rsi_oversold（RSI超卖）、volume_spike（成交量突增）、breakout（突破形态）',
          items: { type: 'string' },
        },
        limit: {
          type: 'integer',
          description: '返回数量上限，默认5个',
          default: 5,
        },
      },
      output: {
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              symbol: { type: 'string', description: '股票代码' },
              name: { type: 'string', description: '股票名称' },
              score: { type: 'number', description: '综合评分（0-100）' },
              reasons: { type: 'array', description: '入选理由' },
              price: { type: 'number', description: '当前价格' },
              change_pct: { type: 'number', description: '涨跌幅（%）' },
            },
            additionalProperties: true,
          },
        },
        render: (_args, value) => [{
          type: 'text',
          text: `扫描到 ${(value as any[]).length} 个机会:\n${JSON.stringify(value, null, 2)}`,
        }],
      },
      timeoutMs: 20000,
      execute: async (args: any) => {
        return qv2.scanOpportunities({
          conditions: args.conditions,
          limit: args.limit || 5,
        }) as any;
      },
    } as any));

    // 股票筛选
    ctx.tools.register(defineTool({
      name: 'screening',
      description: '按条件筛选股票，支持财务指标、技术指标、估值等多维度。用于：构建股票池、寻找符合特定条件的标的',
      parameters: {
        filters: {
          type: 'object',
          description: '筛选条件对象，如：{roe_min: 15, pe_max: 30, market_cap_min: 100}',
          additionalProperties: true,
        },
        limit: {
          type: 'integer',
          description: '返回数量上限，默认20个',
          default: 20,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            total: { type: 'integer', description: '符合条件的总数' },
            stocks: { type: 'array', description: '股票列表' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 20000,
      execute: async (args: any) => {
        return qv2.screenStocks({
          filters: args.filters,
          limit: args.limit || 20,
        }) as any;
      },
    } as any));

    // 轮动策略提案
    ctx.tools.register(defineTool({
      name: 'rotation_proposal',
      description: '分析行业轮动趋势，生成调仓提案。用于：判断当前应增持哪些行业、减持哪些行业，从弱势行业切换到强势行业',
      parameters: {
        portfolio_id: {
          type: 'string',
          description: '组合ID，不传则基于默认组合分析',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            proposal_id: { type: 'string', description: '提案ID' },
            current_allocation: { type: 'array', description: '当前行业配置' },
            proposed_allocation: { type: 'array', description: '建议行业配置' },
            sell_list: { type: 'array', description: '建议卖出列表' },
            buy_list: { type: 'array', description: '建议买入列表' },
            reasoning: { type: 'string', description: '调仓理由' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 20000,
      execute: async (args: any) => {
        return qv2.generateRotationProposal({
          portfolio_id: args.portfolio_id,
        }) as any;
      },
    } as any));

    // 轮动模拟
    ctx.tools.register(defineTool({
      name: 'rotation_simulate',
      description: '模拟轮动调仓效果，对比调仓前后的预期收益。用于：验证调仓提案是否合理、评估调仓风险',
      parameters: {
        proposal_id: {
          type: 'string',
          description: '提案ID（由 rotation_proposal 生成）',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            proposal_id: { type: 'string', description: '提案ID' },
            current_return: { type: 'number', description: '当前配置预期收益（%）' },
            proposed_return: { type: 'number', description: '调仓后预期收益（%）' },
            improvement: { type: 'number', description: '收益提升（%）' },
            risk_change: { type: 'number', description: '风险变化' },
            simulation_details: { type: 'object', description: '模拟详情', additionalProperties: true },
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
        return qv2.simulateRotation({
          proposal_id: args.proposal_id,
        }) as any;
      },
    } as any));

    // 轮动执行
    ctx.tools.register(defineTool({
      name: 'rotation_execute',
      description: '执行轮动调仓（卖出弱势行业，买入强势行业）。用于：确认调仓方案后执行实际交易',
      parameters: {
        proposal_id: {
          type: 'string',
          description: '提案ID',
          required: true,
        },
        dry_run: {
          type: 'boolean',
          description: '是否试运行：true（只计算不执行，默认）、false（实际执行交易）',
          default: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            proposal_id: { type: 'string', description: '提案ID' },
            dry_run: { type: 'boolean', description: '是否试运行' },
            executed: { type: 'boolean', description: '是否已执行' },
            orders: { type: 'array', description: '生成的订单列表' },
            summary: { type: 'string', description: '执行摘要' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 20000,
      execute: async (args: any) => {
        return qv2.executeRotation({
          proposal_id: args.proposal_id,
          dry_run: args.dry_run !== false,
        }) as any;
      },
    } as any));
  }
}
