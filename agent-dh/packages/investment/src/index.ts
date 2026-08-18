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
      description: '获取股票实时行情快照：最新价、开高低、昨收、涨跌额/涨跌幅、成交量、成交额。适用于：盘中查看个股即时表现、下单前确认当前价格。非交易时段返回最近一个交易日的收盘数据。需要历史走势用 data_fetch_kline；需要估值与基本面用 data_fetch_financial。',
      parameters: {
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，不带交易所前缀。如 600519（贵州茅台）、000001（平安银行）、300750（宁德时代）',
          required: true,
        },
        source: {
          type: 'string',
          description: '数据源。auto（默认）：优先实时行情，不可用时回退数据库缓存；realtime：强制实时，获取失败即报错，下单前建议用；db：只读数据库缓存，速度快但可能不是最新，批量查询或复盘时建议用',
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
        render: (_args: any, value: any) => [{
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
      description: '获取股票历史K线数据：每日开高低收、成交量、成交额，按日期升序返回。适用于：技术分析、趋势研判、计算 MA/RSI/MACD 等技术指标、回测取数。时间段越长返回数据越多，应按需限定日期范围；只要最新价格时用 data_fetch_quote 更轻量。',
      parameters: {
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
        start_date: {
          type: 'string',
          description: '开始日期，格式 YYYY-MM-DD，如 2024-01-01。与 end_date 配合限定区间',
          required: true,
        },
        end_date: {
          type: 'string',
          description: '结束日期，格式 YYYY-MM-DD，如 2024-12-31',
          required: true,
        },
        period: {
          type: 'string',
          description: 'K线周期。daily（默认）：日线，适合短中线分析；weekly：周线，适合中线趋势；monthly：月线，适合长期趋势判断',
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
        render: (_args: any, value: any) => [{
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
      description: '获取股票最新一期财务数据：营收、净利润、总资产、ROE、EPS、PE-TTM、PB、资产负债率、毛利率等核心指标。适用于：基本面分析、价值投资筛选、评估公司盈利能力与财务健康度。数据随财报季更新（季报/年报），非实时；判断短期价格走势应结合 data_fetch_quote 与 data_fetch_kline。',
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
        render: (_args: any, value: any) => [{
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
      description: '获取宏观经济指标的时间序列及趋势判断。适用于：判断经济周期位置、评估市场大环境、指导大类资产配置方向。宏观指标按月/季发布，适合中长期决策，不适合短线择时。注意：后端接口尚未就绪，当前返回占位结果，暂勿用于实际决策。',
      parameters: {
        indicator: {
          type: 'string',
          description: '指标名称。pmi：制造业景气度（50为荣枯线）；cpi：通胀水平；ppi：工业品价格（领先于CPI）；gdp：经济增速；m2：货币供应量增速（反映流动性）；interest_rate：基准利率',
          enum: ['pmi', 'cpi', 'ppi', 'gdp', 'm2', 'interest_rate'],
          required: true,
        },
        start_date: {
          type: 'string',
          description: '开始日期，格式 YYYY-MM-DD，如 2024-01-01。不传则由后端返回默认区间',
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
            indicator: { type: 'string', description: '指标名称' },
            data: { type: 'array', description: '时间序列数据' },
            latest_value: { type: 'number', description: '最新值' },
            trend: { type: 'string', description: '趋势：up/down/stable' },
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
        return { indicator: args.indicator, note: 'data_fetch_macro API endpoint needed in quantsys-v2' } as any;
      },
    } as any));

    // 5. 北向资金流向
    ctx.tools.register(defineTool({
      name: 'data_fetch_north_flow',
      description: '获取北向资金（沪股通+深股通）流向：每日净流入、累计净流入、买入/卖出最多的个股。适用于：判断外资对A股的态度，持续净流入通常视为利好信号。注意：后端接口尚未就绪，当前返回占位结果，暂勿用于实际决策。',
      parameters: {
        days: {
          type: 'integer',
          description: '查询最近 N 个交易日的数据，默认 5。看趋势建议取 20 以上',
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
        render: (_args: any, value: any) => [{
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
      description: '获取市场整体情绪指标：涨跌家数比、涨停/跌停家数、总成交额、恐慌贪婪指数（0-100）。适用于：判断市场恐慌/贪婪程度、评估短期系统性风险。注意：后端接口尚未就绪，当前返回占位结果，暂勿用于实际决策。',
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
        render: (_args: any, value: any) => [{
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
      description: '获取全部股票池列表：名称、筛选逻辑描述、成员数量、更新时间。股票池是预定义筛选条件的集合（如高ROE池、低估值池），是博弈中的"战场"。适用于：盘前查看可用池子、选择分析对象。评估某个池子的博弈竞争力用 pool_battlefield；查池内个股行情用 data_fetch_quote。',
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
        render: (_args: any, value: any) => [{
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
      description: '获取交易策略列表：名称、类型、状态、参数配置。策略是具体的交易规则（如均线突破、MACD金叉）。适用于：查看可用策略、执行策略前确认 strategy_id。执行策略或生成信号用 strategy_execute；比较策略表现用 evolution_leaderboard。',
      parameters: {
        source: {
          type: 'string',
          description: '按来源过滤。builtin：系统内置策略；user：用户自定义策略。不传则返回全部',
          enum: ['builtin', 'user'],
        },
        code_type: {
          type: 'string',
          description: '按策略类型过滤：indicator（技术指标类）、trend_following（趋势跟踪）、mean_reversion（均值回归）、breakout（突破）。不传则不过滤',
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
        render: (_args: any, value: any) => {
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
