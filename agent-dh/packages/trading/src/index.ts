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
 * Trading Plugin for Agent-DH
 *
 * Portfolio management, trade execution, and monitoring tools.
 */
export default class TradingPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    quantsysV2: z.object({
      baseURL: z.string().default('http://localhost:5001'),
      timeout: z.number().default(30000),
    }).default({} as any),
  }).default({} as any)

  private qv2: QuantsysV2Client;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'trading');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 1. 账户信息
    ctx.tools.register(defineTool({
      name: 'account_info',
      description: '获取虚拟账户资产总览：总资产、持仓市值、可用资金、总盈亏、当日涨跌、盈利/亏损持仓数。适用于：交易前确认可用资金、盘后复盘账户整体表现。只读操作，可随时调用。查看逐只持仓明细用 position_list。',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual（Agent 虚拟交易账户）。除非配置了多账户，否则无需传入',
          default: 'agent_virtual',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            accountName: { type: 'string', description: '账户名称' },
            totalValue: { type: 'number', description: '总资产（元）' },
            totalCost: { type: 'number', description: '总成本（元）' },
            totalMarketValue: { type: 'number', description: '持仓市值（元）' },
            totalPnl: { type: 'number', description: '总盈亏（元）' },
            totalPnlPct: { type: 'number', description: '总盈亏比例（%）' },
            dailyChange: { type: 'number', description: '当日涨跌（元）' },
            positions: { type: 'integer', description: '持仓数量（只）' },
            cash: { type: 'number', description: '可用资金（元）' },
            liquidAssets: { type: 'number', description: '流动资产（元）' },
            profitCount: { type: 'integer', description: '盈利持仓数' },
            lossCount: { type: 'integer', description: '亏损持仓数' },
            lastUpdated: { type: 'string', description: '更新时间' },
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
        const accountName = args.account_name || 'agent_virtual';
        return qv2.getPortfolioSummary(accountName) as any;
      },
    } as any));

    // 2. 持仓列表
    ctx.tools.register(defineTool({
      name: 'position_list',
      description: '获取当前持仓明细：每只股票的持仓数量、可卖数量（受T+1限制）、成本价、现价、市值、盈亏。适用于：调仓前核对持仓、止损检查时确认盈亏。卖出前必须确认 shares_available——当日买入的股份次日才可卖。',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual。除非配置了多账户，否则无需传入',
          default: 'agent_virtual',
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
              quantity: { type: 'integer', description: '持仓数量（股）' },
              shares_available: { type: 'integer', description: '可卖数量（股），受T+1限制' },
              cost_price: { type: 'number', description: '成本价（元）' },
              current_price: { type: 'number', description: '当前价（元）' },
              market_value: { type: 'number', description: '市值（元）' },
              pnl: { type: 'number', description: '盈亏（元）' },
              pnl_pct: { type: 'number', description: '盈亏比例（%）' },
            },
            additionalProperties: true,
          },
        },
        render: (_args, value) => [{
          type: 'text',
          text: `持仓 ${(value as any[]).length} 只股票:\n${JSON.stringify(value, null, 2)}`,
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        const accountName = args.account_name || 'agent_virtual';
        return qv2.getPositions(accountName) as any;
      },
    } as any));

    // 3. 交易执行（虚拟仓）
    ctx.tools.register(defineTool({
      name: 'portfolio_trade',
      description: '执行虚拟仓买卖委托（写操作，立即成交并改变持仓）。执行前应先确认：用 account_info 查可用资金、用 position_list 查可卖数量、用 risk_controller 计算建议仓位。约束：买入数量必须是100的整数倍（A股一手100股）；卖出数量不得超过可卖数量（T+1限制）。成交后建议用 trade_monitor 确认订单状态。大额订单考虑用 algo_execute 拆单以降低冲击。',
      parameters: {
        action: {
          type: 'string',
          description: 'BUY：买入；SELL：卖出',
          enum: ['BUY', 'SELL'],
          required: true,
        },
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
        quantity: {
          type: 'integer',
          description: '交易数量（股）。买入必须是100的整数倍；卖出不得超过可卖数量（position_list 的 shares_available）',
          required: true,
        },
        price: {
          type: 'number',
          description: '委托价格（元）。不传则按市价成交；限价委托可控制成交成本，但存在不成交风险',
        },
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            order_id: { type: 'string', description: '订单ID' },
            action: { type: 'string', description: '操作方向' },
            symbol: { type: 'string', description: '股票代码' },
            quantity: { type: 'integer', description: '成交数量' },
            price: { type: 'number', description: '成交价格' },
            amount: { type: 'number', description: '成交金额' },
            status: { type: 'string', description: '状态：filled/partial/rejected' },
            timestamp: { type: 'string', description: '成交时间' },
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
        return qv2.executeTrade({
          action: args.action,
          symbol: args.symbol,
          quantity: args.quantity,
          price: args.price,
          account_name: args.account_name || 'agent_virtual',
        }) as any;
      },
    } as any));

    // 4. 交易监控
    ctx.tools.register(defineTool({
      name: 'trade_monitor',
      description: '查询订单执行状态与成交明细。适用于：portfolio_trade 或 algo_execute 之后确认成交结果、检查未成交订单。只读操作。每日收盘后核对全部成交用 trade_verify。',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
        order_id: {
          type: 'string',
          description: '订单ID。传入则只查该订单；不传则返回近期全部订单',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            orders: { type: 'array', description: '订单列表' },
            pending_count: { type: 'integer', description: '未成交订单数' },
            filled_count: { type: 'integer', description: '已成交订单数' },
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
        return qv2.getTradeHistory({
          account_name: args.account_name || 'agent_virtual',
          order_id: args.order_id,
        }) as any;
      },
    } as any));

    // 5. 算法执行
    ctx.tools.register(defineTool({
      name: 'algo_execute',
      description: '以算法单拆分执行大额交易（写操作），降低市场冲击和滑点。适用于：单笔金额较大（如超过该股日均成交额的1%）时；小额交易直接用 portfolio_trade 更简单。返回算法订单ID和拆分子单列表，执行进度用 trade_monitor 跟踪。',
      parameters: {
        action: {
          type: 'string',
          description: 'BUY：买入；SELL：卖出',
          enum: ['BUY', 'SELL'],
          required: true,
        },
        symbol: {
          type: 'string',
          description: 'A股6位数字股票代码，如 600519',
          required: true,
        },
        quantity: {
          type: 'integer',
          description: '总交易数量（股），将按算法拆成多笔子单逐步执行',
          required: true,
        },
        algo: {
          type: 'string',
          description: '算法类型。TWAP：按时间均匀拆分，适合成交量平稳的股票；VWAP：按市场成交量分布拆分，更贴近真实流动性，适合大多数场景',
          enum: ['TWAP', 'VWAP'],
          required: true,
        },
        duration: {
          type: 'integer',
          description: '执行时长（分钟），默认 30。时长越长市场冲击越小，但价格漂移风险越大',
          default: 30,
        },
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            algo_order_id: { type: 'string', description: '算法订单ID' },
            algo: { type: 'string', description: '算法类型' },
            symbol: { type: 'string', description: '股票代码' },
            total_quantity: { type: 'integer', description: '总数量' },
            filled_quantity: { type: 'integer', description: '已成交数量' },
            avg_price: { type: 'number', description: '成交均价' },
            slices: { type: 'array', description: '拆分的子单列表' },
            status: { type: 'string', description: '状态' },
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
        return qv2.executeAlgo({
          action: args.action,
          symbol: args.symbol,
          quantity: args.quantity,
          algo: args.algo,
          duration: args.duration || 30,
          account_name: args.account_name || 'agent_virtual',
        }) as any;
      },
    } as any));

    // 6. 交易对账
    ctx.tools.register(defineTool({
      name: 'trade_verify',
      description: '交易对账：核对当日成交记录与预期，输出异常列表。适用于：每日收盘后例行核对，发现漏单、错单、重复成交等问题；发现交易异常后排查。只读操作。',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
        date: {
          type: 'string',
          description: '对账日期，格式 YYYY-MM-DD。不传则对账当日',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            date: { type: 'string', description: '对账日期' },
            total_orders: { type: 'integer', description: '总订单数' },
            matched: { type: 'integer', description: '匹配数' },
            mismatched: { type: 'integer', description: '异常数' },
            anomalies: { type: 'array', description: '异常列表' },
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
        return qv2.verifyTrades({
          account_name: args.account_name || 'agent_virtual',
          date: args.date,
        }) as any;
      },
    } as any));
  }
}
