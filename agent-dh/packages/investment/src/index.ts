import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';

// ========== Plugin Config Schema ==========

export interface Config {
  quantsysV2?: {
    baseURL?: string;
    timeout?: number;
  };
}

// ========== Investment Plugin (Cordis Service) ==========

/**
 * Investment Plugin for Agent-DH
 *
 * Provides market data tools: real-time quotes, kline, financial reports,
 * macro data, north-bound flow, market sentiment, stock pool and strategy lists.
 */
export default class InvestmentPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'investment');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 1. 实时行情
    ctx.tools.register(defineTool({
      name: 'data_fetch_quote',
      description: '获取股票实时行情。用于：分析个股当前价格、涨跌幅、成交量等即时数据。示例：查询贵州茅台(600519)最新行情',
      parameters: {
        symbol: {
          type: 'string',
          description: '股票代码，A股格式为6位数字，如：600519（贵州茅台）、000001（平安银行）、300750（宁德时代）',
          required: true,
        },
        source: {
          type: 'string',
          description: '数据源选择：auto（自动，优先实时）、realtime（强制实时）、db（数据库缓存，更快但可能非最新）',
          enum: ['auto', 'realtime', 'db'],
          default: 'auto',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            name: { type: 'string', description: '股票名称' },
            price: { type: 'number', description: '当前价格（元）' },
            open: { type: 'number', description: '开盘价（元）' },
            high: { type: 'number', description: '最高价（元）' },
            low: { type: 'number', description: '最低价（元）' },
            prevClose: { type: 'number', description: '昨收价（元）' },
            change: { type: 'number', description: '涨跌额（元）' },
            changePct: { type: 'number', description: '涨跌幅（%）' },
            volume: { type: 'number', description: '成交量（股）' },
            amount: { type: 'number', description: '成交额（元）' },
            source: { type: 'string', description: '数据来源' },
            timestamp: { type: 'string', description: '行情时间戳' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        const source = args.source || 'auto';
        return qv2.getQuote(args.symbol, source) as any;
      },
    } as any));

    // 2. K线数据
    ctx.tools.register(defineTool({
      name: 'data_fetch_kline',
      description: '获取股票历史K线数据。用于：技术分析、趋势研判、计算技术指标（MA、RSI、MACD等）。支持日线、周线、月线',
      parameters: {
        symbol: {
          type: 'string',
          description: '股票代码，如：600519',
          required: true,
        },
        start_date: {
          type: 'string',
          description: '开始日期，格式：YYYY-MM-DD，如：2024-01-01',
          required: true,
        },
        end_date: {
          type: 'string',
          description: '结束日期，格式：YYYY-MM-DD，如：2024-12-31',
          required: true,
        },
        period: {
          type: 'string',
          description: 'K线周期：daily（日线，默认）、weekly（周线）、monthly（月线）',
          enum: ['daily', 'weekly', 'monthly'],
          default: 'daily',
        },
      },
      output: {
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              date: { type: 'string', description: '日期' },
              open: { type: 'number', description: '开盘价' },
              high: { type: 'number', description: '最高价' },
              low: { type: 'number', description: '最低价' },
              close: { type: 'number', description: '收盘价' },
              volume: { type: 'number', description: '成交量（股）' },
              amount: { type: 'number', description: '成交额（元）' },
            },
            additionalProperties: true,
          },
        },
        render: (_args, value) => [{
          type: 'text',
          text: `获取到 ${(value as any[]).length} 条K线数据:\n${JSON.stringify(value, null, 2)}`,
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        const period = args.period || 'daily';
        return qv2.getKlines(
          args.symbol,
          args.start_date,
          args.end_date,
          period
        ) as any;
      },
    } as any));

    // 3. 财务数据
    ctx.tools.register(defineTool({
      name: 'data_fetch_financial',
      description: '获取股票最新财务数据。用于：基本面分析、价值投资筛选、评估公司盈利能力。返回利润表、资产负债表、现金流量表核心指标',
      parameters: {
        symbol: {
          type: 'string',
          description: '股票代码，如：600519',
          required: true,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            symbol: { type: 'string', description: '股票代码' },
            name: { type: 'string', description: '公司名称' },
            report_date: { type: 'string', description: '报告期，如：2024-09-30' },
            revenue: { type: 'number', description: '营业收入（亿元）' },
            net_profit: { type: 'number', description: '净利润（亿元）' },
            total_assets: { type: 'number', description: '总资产（亿元）' },
            total_liabilities: { type: 'number', description: '总负债（亿元）' },
            roe: { type: 'number', description: '净资产收益率 ROE（%）' },
            eps: { type: 'number', description: '每股收益 EPS（元）' },
            pe_ttm: { type: 'number', description: '市盈率 PE-TTM' },
            pb: { type: 'number', description: '市净率 PB' },
            debt_ratio: { type: 'number', description: '资产负债率（%）' },
            gross_margin: { type: 'number', description: '毛利率（%）' },
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
        return qv2.getFinancialData(args.symbol) as any;
      },
    } as any));

    // 4. 宏观经济数据
    ctx.tools.register(defineTool({
      name: 'data_fetch_macro',
      description: '获取宏观经济指标。用于：判断经济周期、评估市场环境、指导资产配置方向。指标包括PMI（制造业景气度）、CPI（通胀）、PPI（工业品价格）、GDP增速、M2（货币供应量）、利率',
      parameters: {
        indicator: {
          type: 'string',
          description: '指标名称：pmi（制造业采购经理指数）、cpi（居民消费价格指数）、ppi（工业生产者出厂价格指数）、gdp（国内生产总值增速）、m2（广义货币供应量增速）、interest_rate（基准利率）',
          enum: ['pmi', 'cpi', 'ppi', 'gdp', 'm2', 'interest_rate'],
          required: true,
        },
        start_date: {
          type: 'string',
          description: '开始日期，格式：YYYY-MM-DD，如：2024-01-01',
        },
        end_date: {
          type: 'string',
          description: '结束日期，格式：YYYY-MM-DD，如：2024-12-31',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            indicator: { type: 'string', description: '指标名称' },
            data: { type: 'array', description: '时间序列数据' },
            latest_value: { type: 'number', description: '最新值' },
            trend: { type: 'string', description: '趋势：up/down/stable' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return { indicator: args.indicator, note: 'data_fetch_macro API endpoint needed in quantsys-v2' } as any;
      },
    } as any));

    // 5. 北向资金流向
    ctx.tools.register(defineTool({
      name: 'data_fetch_north_flow',
      description: '获取北向资金（沪股通+深股通）流向数据。用于：判断外资对A股的态度，外资持续流入通常被视为利好信号',
      parameters: {
        days: {
          type: 'integer',
          description: '查询最近多少天的数据，默认5天',
          default: 5,
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            dates: { type: 'array', description: '日期列表' },
            net_inflows: { type: 'array', description: '每日净流入（亿元）' },
            cumulative: { type: 'number', description: '累计净流入（亿元）' },
            top_buy: { type: 'array', description: '买入最多的股票' },
            top_sell: { type: 'array', description: '卖出最多的股票' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return { days: args.days || 5, note: 'data_fetch_north_flow API endpoint needed in quantsys-v2' } as any;
      },
    } as any));

    // 6. 市场情绪
    ctx.tools.register(defineTool({
      name: 'data_fetch_market_sentiment',
      description: '获取市场整体情绪指标。用于：判断市场恐慌/贪婪程度、评估短期风险。包括涨跌家数比、涨停跌停数、成交额变化、恐慌指数等',
      parameters: {},
      output: {
        schema: {
          type: 'object',
          properties: {
            advance_decline_ratio: { type: 'number', description: '涨跌家数比' },
            limit_up_count: { type: 'integer', description: '涨停家数' },
            limit_down_count: { type: 'integer', description: '跌停家数' },
            total_turnover: { type: 'number', description: '总成交额（亿元）' },
            fear_greed_index: { type: 'number', description: '恐慌贪婪指数（0-100，越高越贪婪）' },
            sentiment: { type: 'string', description: '情绪判断：extreme_fear/fear/neutral/greed/extreme_greed' },
          },
          additionalProperties: true,
        },
        render: (_args, value) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async () => {
        return { note: 'data_fetch_market_sentiment API endpoint needed in quantsys-v2' } as any;
      },
    } as any));

    // 7. 股票池列表
    ctx.tools.register(defineTool({
      name: 'pool_list',
      description: '获取所有股票池列表。用于：查看已有的筛选池、了解各池子的成员数量和更新状态。股票池是预定义的筛选条件集合（如高ROE池、低估值池等）',
      parameters: {},
      output: {
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'integer', description: '股票池ID' },
              name: { type: 'string', description: '股票池名称' },
              description: { type: 'string', description: '股票池描述' },
              created_at: { type: 'string', description: '创建时间' },
              updated_at: { type: 'string', description: '更新时间' },
              member_count: { type: 'integer', description: '成员数量' },
            },
            additionalProperties: true,
          },
        },
        render: (_args, value) => [{
          type: 'text',
          text: `共找到 ${(value as any[]).length} 个股票池:\n${JSON.stringify(value, null, 2)}`,
        }],
      },
      timeoutMs: 10000,
      execute: async () => {
        return qv2.listPools() as any;
      },
    } as any));

    // 8. 策略列表
    ctx.tools.register(defineTool({
      name: 'strategy_list',
      description: '获取交易策略列表。用于：查看可用的交易策略、了解策略类型和状态。策略是具体的交易规则（如均线突破、MACD金叉等）',
      parameters: {
        source: {
          type: 'string',
          description: '策略来源：builtin（系统内置策略）、user（用户自定义策略）',
          enum: ['builtin', 'user'],
        },
        code_type: {
          type: 'string',
          description: '策略类型过滤：indicator（技术指标）、trend_following（趋势跟踪）、mean_reversion（均值回归）、breakout（突破）',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            total: { type: 'integer', description: '策略总数' },
            page: { type: 'integer', description: '当前页码' },
            pageSize: { type: 'integer', description: '每页数量' },
            items: {
              type: 'array',
              items: {
                type: 'object',
                properties: {
                  id: { type: 'string', description: '策略ID' },
                  name: { type: 'string', description: '策略名称' },
                  strategyType: { type: 'string', description: '策略类型' },
                  type: { type: 'string', description: '类别' },
                  status: { type: 'string', description: '状态' },
                  description: { type: 'string', description: '策略描述' },
                  code: { type: 'string', description: '策略代码' },
                  params: { type: 'array', description: '参数列表' },
                },
                additionalProperties: true,
              },
            },
          },
          additionalProperties: true,
        },
        render: (_args, value) => {
          const v = value as any;
          return [{
            type: 'text',
            text: `共找到 ${v.total} 个策略（当前页 ${v.page}，每页 ${v.pageSize}，本页 ${v.items?.length || 0} 个）:\n${JSON.stringify(v.items?.slice(0, 5), null, 2)}${v.items?.length > 5 ? '\n...(仅显示前5个)' : ''}`,
          }];
        },
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        const params: { source?: 'builtin' | 'user'; code_type?: string } = {};
        if (args.source) params.source = args.source;
        if (args.code_type) params.code_type = args.code_type;
        return qv2.listStrategies(params) as any;
      },
    } as any));
  }
}
