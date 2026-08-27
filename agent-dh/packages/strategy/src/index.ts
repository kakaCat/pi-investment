import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { OsMemoryStore } from '@pi-investment/os-memory';

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
  private osMemory: OsMemoryStore;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'strategy');
    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });
    this.osMemory = new OsMemoryStore({ baseURL: (config as any).agentOS?.baseURL || 'http://localhost:8080', agentId: (config as any).agentOS?.agentId || 'agent-dh' });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 策略执行
    ctx.tools.register(defineTool({
      name: 'strategy_execute',
      description: '执行策略：基于最新数据生成买卖信号，或在历史数据上回测验证。适用于：盘前获取交易信号（signal 模式）、验证策略历史表现（backtest 模式）。先用 strategy_list 确认策略ID；优化策略参数用 evolution_run。',
      parameters: {
        strategy_id: {
          type: 'integer',
          description: '策略ID，通过 strategy_list 获取',
          required: true,
        },
        symbols: {
          type: 'array',
          description: '股票代码列表，如 ["600519", "000001"]。不传则由后端按策略默认范围执行',
          items: { type: 'string' },
        },
        mode: {
          type: 'string',
          description: '执行模式。signal（默认）：基于最新数据生成当前买卖信号，用于实盘决策；backtest：在历史数据上回测，返回收益、回撤等指标，用于验证策略有效性',
          enum: ['backtest', 'signal'],
          default: 'signal',
        },
        start_date: {
          type: 'string',
          description: '回测开始日期（mode=backtest时必填），格式 YYYY-MM-DD，如 2025-01-02',
        },
        end_date: {
          type: 'string',
          description: '回测结束日期（mode=backtest时必填），格式 YYYY-MM-DD，如 2026-08-21',
        },
        initial_capital: {
          type: 'number',
          description: '回测初始资金（mode=backtest时可选），默认 100000',
          default: 100000,
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
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 30000,
      execute: async (args: any) => {
        if (args.mode === 'backtest') {
          // 2026-08-25 修复：回测模式透传日期参数（原硬编码空串导致验证门回测腿无法指定窗口）
          return qv2.backtestStrategy({
            strategy_id: args.strategy_id,
            symbol: args.symbols?.[0] || '',  // 当前后端 API 单标的，取第一个
            symbols: args.symbols,
            start_date: args.start_date || '',
            end_date: args.end_date || '',
            initial_capital: args.initial_capital || 100000,
          }) as any;
        }
        return qv2.generateSignals({
          strategy_id: args.strategy_id,
          symbols: args.symbols,
        }) as any;
      },
    } as any));

    // 策略参数优化（回测矩阵）
    ctx.tools.register(defineTool({
      name: 'strategy_optimize',
      description: '批量回测策略参数组合（网格搜索），找到最优参数配置。适用于：策略开发后调优参数、定期重新校准策略。返回按夏普比率排序的所有回测结果。',
      parameters: {
        strategy_id: {
          type: 'integer',
          description: '策略ID，通过 strategy_list 获取',
          required: true,
        },
        symbol: {
          type: 'string',
          description: '股票代码，如 600519',
          required: true,
        },
        start_date: {
          type: 'string',
          description: '回测开始日期，格式 YYYY-MM-DD',
          required: true,
        },
        end_date: {
          type: 'string',
          description: '回测结束日期，格式 YYYY-MM-DD',
          required: true,
        },
        param_ranges: {
          type: 'object',
          description: '参数网格定义，如 {"ma_short": [5, 10, 20], "ma_long": [30, 60]}。每个参数给出候选值列表，系统会自动生成所有组合',
          additionalProperties: true,
          required: true,
        },
        initial_cash: {
          type: 'number',
          description: '初始资金，默认 1000000',
          default: 1000000,
        },
        sort_by: {
          type: 'string',
          description: '排序指标：sharpe_ratio（夏普比率，默认）、total_return（总收益）、max_drawdown（最大回撤）、win_rate（胜率）',
          enum: ['sharpe_ratio', 'total_return', 'max_drawdown', 'win_rate'],
          default: 'sharpe_ratio',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean' },
            results: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  params: { type: 'object', description: '参数组合', additionalProperties: true },
                  sharpeRatio: { type: 'number', description: '夏普比率' },
                  totalReturn: { type: 'number', description: '总收益率（%）' },
                  maxDrawdown: { type: 'number', description: '最大回撤（%）' },
                  winRate: { type: 'number', description: '胜率（%）' },
                  totalTrades: { type: 'integer', description: '总交易次数' },
                },
                additionalProperties: true,
              },
            },
            totalCombinations: { type: 'integer', description: '总参数组合数' },
            successfulCombinations: { type: 'integer', description: '成功回测数' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => {
          if (!value.success) return [{ type: 'text', text: `❌ 优化失败` }];
          const top3 = value.results?.slice(0, 3) || [];
          let text = `✅ 参数优化完成: ${value.successfulCombinations}/${value.totalCombinations} 组成功\n\n`;
          text += `Top 3 参数组合:\n`;
          top3.forEach((r: any, i: number) => {
            text += `\n${i + 1}. 参数: ${JSON.stringify(r.params)}\n`;
            text += `   夏普: ${r.sharpeRatio?.toFixed(2)}, 收益: ${r.totalReturn?.toFixed(2)}%, 回撤: ${r.maxDrawdown?.toFixed(2)}%, 胜率: ${r.winRate?.toFixed(2)}%\n`;
          });
          return [{ type: 'text', text }];
        },
      },
      timeoutMs: 300000,  // 5分钟（批量回测可能较慢）
      execute: async (args: any) => {
        return qv2.optimizeStrategy({
          strategyId: args.strategy_id,
          symbol: args.symbol,
          startDate: args.start_date,
          endDate: args.end_date,
          paramRanges: args.param_ranges,
          initialCash: args.initial_cash || 1000000,
          sortBy: args.sort_by || 'sharpe_ratio',
        }) as any;
      },
    } as any));

    // 机会扫描
    ctx.tools.register(defineTool({
      name: 'opportunity_scan',
      description: '按预设条件扫描全市场机会，基于多因子综合评分返回排序后的优质标的及入选理由。适用于：盘前选股、发现被低估/超卖/资金流入的标的。与 screening 的区别：本工具用内置多因子评分模型给出排序，screening 按你指定的指标阈值精确过滤。',
      parameters: {
        conditions: {
          type: 'array',
          description: '筛选条件列表，可多选组合：roe_gt_15（ROE>15%，盈利能力强）、pe_lt_30（PE<30，估值合理）、rsi_oversold（RSI超卖，可能反弹）、volume_spike（成交量突增，资金关注）、breakout（突破形态）。不传则使用默认条件组合',
          items: { type: 'string' },
        },
        limit: {
          type: 'integer',
          description: '返回标的数量上限，默认 5，按综合评分从高到低取',
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
        render: (_args: any, value: any) => [{
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
      description: '按自定义指标阈值精确筛选股票（财务、估值、技术多维度），返回符合条件的股票列表和总数。适用于：构建股票池、验证筛选条件的覆盖面。需要综合评分排序用 opportunity_scan。',
      parameters: {
        filters: {
          type: 'object',
          description: '筛选条件键值对，如 {"roe_min": 15, "pe_max": 30, "market_cap_min": 100}。常用键：roe_min（ROE下限%）、pe_max（PE上限）、market_cap_min（市值下限，亿元）。多个条件之间为 AND 关系',
          additionalProperties: true,
        },
        limit: {
          type: 'integer',
          description: '返回数量上限，默认 20',
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
        render: (_args: any, value: any) => [{
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
      description: '分析行业轮动趋势，基于当前组合生成调仓提案：建议增持/减持的行业、具体买卖清单及调仓理由。适用于：定期（如每周）评估行业配置、从弱势行业切换到强势行业。这是轮动三步流程的第一步：提案生成后用 rotation_simulate 验证效果，确认后再用 rotation_execute 执行。只读操作，不改变持仓。',
      parameters: {
        portfolio_id: {
          type: 'string',
          description: '组合ID。不传则基于默认组合分析',
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
        render: (_args: any, value: any) => [{
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
      description: '对 rotation_proposal 生成的调仓提案做模拟，对比调仓前后的预期收益与风险变化。适用于：执行调仓前验证提案是否合理。只读操作，不改变持仓。验证通过后用 rotation_execute 执行。',
      parameters: {
        proposal_id: {
          type: 'string',
          description: '调仓提案ID，由 rotation_proposal 返回',
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
        render: (_args: any, value: any) => [{
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
      description: '执行轮动调仓提案：卖出弱势行业、买入强势行业。默认 dry_run 试运行——只生成订单预览，不产生真实交易；确认无误后显式传 dry_run=false 才实际执行。执行前建议先用 rotation_simulate 评估效果。',
      parameters: {
        proposal_id: {
          type: 'string',
          description: '调仓提案ID，由 rotation_proposal 返回',
          required: true,
        },
        dry_run: {
          type: 'boolean',
          description: 'true（默认）：试运行，只输出将生成的订单，不产生实际交易；false：真实执行，生成实际委托',
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
        render: (_args: any, value: any) => [{
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

    // M3-3: 信号质量追踪（RFC 004/005，2026-08-23）
    // 注意：signal_track 工具已在 @pi-investment/intelligence 插件中注册，此处不重复注册
    // 参见：agent-dh/packages/intelligence/src/index.ts
  }
}
