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
      description: '获取虚拟账户资产信息。用于：查看总资产、持仓市值、盈亏情况、可用资金。执行交易前应先调用此工具了解账户状态',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual（虚拟交易账户）',
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
      description: '获取当前持仓列表。用于：查看每只持仓股票的盈亏、市值、成本、可卖数量。调仓前必须调用',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
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
      description: '执行虚拟仓交易（买入或卖出）。用于：根据策略信号执行买卖操作。注意：卖出数量不能超过可卖数量（T+1限制）',
      parameters: {
        action: {
          type: 'string',
          description: '操作方向：BUY（买入）、SELL（卖出）',
          enum: ['BUY', 'SELL'],
          required: true,
        },
        symbol: {
          type: 'string',
          description: '股票代码，如：600519',
          required: true,
        },
        quantity: {
          type: 'integer',
          description: '交易数量（股），买入时必须是100的整数倍',
          required: true,
        },
        price: {
          type: 'number',
          description: '委托价格（元），不传则按市价成交',
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
      description: '监控交易执行情况。用于：查看订单状态、成交明细、未成交订单。交易执行后应调用确认',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
        order_id: {
          type: 'string',
          description: '订单ID，不传则查询所有近期订单',
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
      description: '使用算法执行大额订单（TWAP/VWAP），减少市场冲击。用于：单笔交易金额较大时，拆分成多笔小单逐步执行，降低滑点',
      parameters: {
        action: {
          type: 'string',
          description: '操作方向：BUY（买入）、SELL（卖出）',
          enum: ['BUY', 'SELL'],
          required: true,
        },
        symbol: {
          type: 'string',
          description: '股票代码',
          required: true,
        },
        quantity: {
          type: 'integer',
          description: '总交易数量（股）',
          required: true,
        },
        algo: {
          type: 'string',
          description: '算法类型：TWAP（时间加权平均价格，均匀拆分）、VWAP（成交量加权平均价格，按市场成交量拆分）',
          enum: ['TWAP', 'VWAP'],
          required: true,
        },
        duration: {
          type: 'integer',
          description: '执行时长（分钟），默认30分钟',
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
      description: '交易对账：核对成交记录与预期，检查异常。用于：每日收盘后核对交易记录，发现漏单、错单、重复成交等问题',
      parameters: {
        account_name: {
          type: 'string',
          description: '账户名称，默认 agent_virtual',
          default: 'agent_virtual',
        },
        date: {
          type: 'string',
          description: '对账日期，格式：YYYY-MM-DD，不传则今天',
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
