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
 * 宪法第 1 条工具层硬校验（P0-1b，2026-08-20）：A股交易时段
 * 9:30-11:30 / 13:00-15:00（工作日）之外禁止下单。
 * 提示词层约束是软约束，这里是硬拒单——双保险。
 * 已知限制：未接交易日历，法定节假日仅按周一至周五判断；时区按进程本地时间。
 * @param now 可注入时间（测试用），默认当前时间
 */
export function assertTradingHours(now: Date = new Date()): void {
  const day = now.getDay();
  const hh = now.getHours();
  const mm = String(now.getMinutes()).padStart(2, '0');
  if (day === 0 || day === 6) {
    throw new Error(`非交易日（周末）禁止下单。宪法：仅 A股交易日 9:30-11:30、13:00-15:00 可执行买卖委托。`);
  }
  const hhmm = now.getHours() * 100 + now.getMinutes();
  const inSession = (hhmm >= 930 && hhmm <= 1130) || (hhmm >= 1300 && hhmm <= 1500);
  if (!inSession) {
    throw new Error(`当前 ${hh}:${mm} 非交易时段，禁止下单（交易宪法第 1 条）。盘前/盘后/夜间禁止买卖委托；分析与复盘不受限。`);
  }
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
        render: (_args: any, value: any) => [{
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
        render: (_args: any, value: any) => [{
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
        reason: {
          type: 'string',
          description: '决策依据（强烈建议填写）：引用的规则 ID（如 R-001）+ 一句话理由。learning 插件会从中提取规则 ID 做归因统计，填写后才能回答"哪条规则在赚钱"',
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
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        assertTradingHours();  // 宪法第 1 条硬校验：非交易时段拒单

        // M5 滑点追踪（2026-08-25）：下单前抓决策时价
        let decisionPrice: number | undefined;
        let decisionTime: string | undefined;
        try {
          const q: any = await qv2.getQuote(args.symbol);
          if (Number(q?.price) > 0) {
            decisionPrice = Number(q.price);
            decisionTime = q?.timestamp ?? new Date().toISOString();
          }
        } catch { /* 行情获取失败不阻塞下单 */ }

        const result: any = await qv2.executeTrade({
          action: args.action,
          symbol: args.symbol,
          quantity: args.quantity,
          price: args.price,
          account_name: args.account_name || 'agent_virtual',
          // 2026-08-25 后端契约变更：order_type 必填（市价/限价，按是否给价推断）
          order_type: args.price ? 'limit' : 'market',
          // R-005：交易理由透传（simulation 端点要求 ≥10 字）
          reason: args.reason,
        });

        // 滑点计算与落库（失败不影响交易结果）
        const fillPrice = Number(result?.price);
        if (decisionPrice && fillPrice > 0) {
          // 方向归一：滑点为正 = 比决策时价更差（买贵/卖便宜）
          const dirSign = String(args.action).toUpperCase() === 'SELL' ? -1 : 1;
          const slipPct = +(((fillPrice - decisionPrice) / decisionPrice * 100) * dirSign).toFixed(3);
          try {
            await qv2.createMemory({
              kind: 'episode',
              scope: 'trade:slippage',
              title: `slippage ${args.symbol} ${args.action} ${slipPct}%`,
              content: `滑点记录：${args.symbol} ${args.action} ${args.quantity}股，决策时价 ${decisionPrice}（${decisionTime}）→ 成交 ${fillPrice}，滑点 ${slipPct}%。理由：${args.reason ?? '未填'}`,
              payload: {
                symbol: args.symbol, action: args.action, quantity: args.quantity,
                decision_price: decisionPrice, fill_price: fillPrice, slippage_pct: slipPct,
                decision_time: decisionTime, order_id: result?.order_id ?? null,
                ts: new Date().toISOString(),
              },
              status: 'testing', confidence: 0.8, source: 'trade_slippage',
              provenance: { channel: 'dsh', session_kind: 'agent' },
            });
          } catch { /* 落库失败不影响交易 */ }
          return { ...result, slippage: { decision_price: decisionPrice, fill_price: fillPrice, slippage_pct: slipPct, decision_time: decisionTime } };
        }
        return result;
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
        render: (_args: any, value: any) => [{
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
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        assertTradingHours();  // 宪法第 1 条硬校验：非交易时段拒单
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
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        // 2026-08-23 重写：后端 /api/risk/trade-verify 路由在重构中丢失（404），
        // 改为本地对账（拉成交记录自查异常），不再依赖后端路由
        return localTradeVerify(qv2, args.account_name || 'agent_virtual', args.date);
      },
    } as any));

    // 7. 滑点报告（M5，2026-08-25）
    ctx.tools.register(defineTool({
      name: 'slippage_report',
      description: '滑点追踪报告：汇总 trade:slippage 落库记录——成交笔数、平均滑点、最大滑点、按标的分布。滑点=成交价 vs 决策时价（方向归一：正值=买贵/卖便宜）。供：评估模拟盘与真实成交的差距（P6 接真金前必看）、执行质量复盘。',
      parameters: {
        symbol: { type: 'string', description: '可选：只看某只标的' },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            total_fills: { type: 'number' },
            avg_slippage_pct: { type: 'number' },
            max_slippage_pct: { type: 'number' },
            by_symbol: { type: 'array', items: { type: 'object', additionalProperties: true } },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 15000,
      execute: async (args: any) => {
        const res = await qv2.searchMemory({ q: args.symbol ? `slippage ${args.symbol}` : 'slippage', scope: 'trade:slippage', limit: 100 });
        const items = (res?.items || []).filter((it: any) => it.status !== 'deprecated' && typeof it.payload?.slippage_pct === 'number');
        const records = items.map((it: any) => it.payload);
        const slips = records.map((r: any) => r.slippage_pct);
        const avg = slips.length ? +(slips.reduce((a: number, b: number) => a + b, 0) / slips.length).toFixed(3) : 0;
        const maxSlip = slips.length ? Math.max(...slips.map(Math.abs)) : 0;

        const bySymbol: Record<string, { count: number; avg: number }> = {};
        for (const r of records) {
          const k = r.symbol ?? 'unknown';
          if (!bySymbol[k]) bySymbol[k] = { count: 0, avg: 0 };
          bySymbol[k].avg = +(((bySymbol[k].avg * bySymbol[k].count) + r.slippage_pct) / (bySymbol[k].count + 1)).toFixed(3);
          bySymbol[k].count++;
        }

        return {
          total_fills: slips.length,
          avg_slippage_pct: avg,
          max_slippage_pct: maxSlip,
          by_symbol: Object.entries(bySymbol).map(([symbol, v]) => ({ symbol, ...v })),
          note: slips.length === 0 ? '暂无滑点记录（首笔真实成交后自动开始积累）' : '滑点为方向归一值：正=比决策时价差',
        } as any;
      },
    } as any));
  }
}

/**
 * 本地交易对账（2026-08-23，替代丢失的后端 /api/risk/trade-verify）
 * 检查项：重复成交（同标的+同价+同量+同秒）、关键字段缺失、
 * 持仓勾稽（持仓数 = 累计买-累计卖，逐标的）
 */
async function localTradeVerify(qv2: QuantsysV2Client, accountName: string, date?: string): Promise<any> {
  const targetDate = date || new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
  const anomalies: any[] = [];

  // 1. 拉取成交记录（全量：pageSize 500，避免分页截断导致勾稽误报）
  const th: any = await qv2.getTradeHistory({ account_name: accountName, pageSize: 500 });
  // orders/items 双兼容（后端实际返回 items）
  const allTrades: any[] = th?.orders || th?.items || [];
  const dayTrades = allTrades.filter((t: any) => String(t.tradeDate ?? t.trade_date ?? '') === targetDate);

  // 2. 重复成交检测（同标的+同方向+同价+同量+同分钟）
  const seen = new Map<string, number>();
  for (const t of dayTrades) {
    const key = [t.symbol, t.action, t.price, t.quantity, String(t.createdAt ?? '').slice(0, 16)].join('|');
    const cnt = (seen.get(key) ?? 0) + 1;
    seen.set(key, cnt);
    if (cnt > 1) {
      anomalies.push({ type: 'duplicate_trade', detail: `疑似重复成交: ${t.symbol} ${t.action} ${t.quantity}股@${t.price}（第${cnt}次）`, trade_id: t.id ?? null });
    }
  }

  // 3. 关键字段缺失
  for (const t of dayTrades) {
    const missing = ['symbol', 'action', 'price', 'quantity'].filter(f => t[f] === undefined || t[f] === null);
    if (missing.length > 0) {
      anomalies.push({ type: 'missing_fields', detail: `成交记录缺字段 ${missing.join('/')}: id=${t.id ?? '?'}` , trade_id: t.id ?? null });
    }
    if (!(Number(t.price) > 0) || !(Number(t.quantity) > 0)) {
      anomalies.push({ type: 'invalid_value', detail: `成交价格/数量非法: ${t.symbol} @${t.price} x${t.quantity}`, trade_id: t.id ?? null });
    }
  }

  // 4. 持仓勾稽（全量历史：逐标的 买入-卖出 = 当前持仓）
  // 2026-08-23 验收修正：历史迁移缺买入腿的记录不算异常——
  // 只有"当前有持仓但与成交净额不符"才算真异常；net<0 或 held=0 的不符降级为 history_gap 提示
  const positions: any[] = await qv2.getPositions(accountName).catch(() => [] as any[]);
  const posMap = new Map<string, number>();
  for (const p of positions) {
    const sym = String(p.symbol ?? '').replace(/\.\w+$/, '');
    posMap.set(sym, Number(p.quantity ?? p.shares ?? 0));
  }
  const netMap = new Map<string, number>();
  for (const t of allTrades) {
    const sym = String(t.symbol ?? '').replace(/\.\w+$/, '');
    const q = Number(t.quantity ?? 0);
    const dir = String(t.action).toLowerCase() === 'buy' ? q : -q;
    netMap.set(sym, (netMap.get(sym) ?? 0) + dir);
  }
  const historyGaps: any[] = [];
  // 2026-08-25 修正：可见历史无买入记录的标的（迁移持仓缺买入腿），净额为负也降级为缺腿提示，
  // 否则熔断减仓日会把"只有卖出记录"误判为勾稽异常
  const hasBuy = new Set<string>();
  for (const t of allTrades) {
    if (String(t.action).toLowerCase() === 'buy') {
      hasBuy.add(String(t.symbol ?? '').replace(/\.\w+$/, ''));
    }
  }
  for (const [sym, net] of netMap) {
    const held = posMap.get(sym) ?? 0;
    if (held > 0 && held !== net && Math.abs(held - net) >= 100) {
      if (!hasBuy.has(sym)) {
        historyGaps.push({ symbol: sym, net_trades: net, note: '迁移持仓（可见历史无买入腿），不参与勾稽' });
      } else {
        anomalies.push({ type: 'position_mismatch', detail: `持仓勾稽不符 ${sym}: 账面 ${held} vs 成交净额 ${net}`, symbol: sym });
      }
    } else if (held === 0 && net !== 0) {
      historyGaps.push({ symbol: sym, net_trades: net, note: '历史迁移缺腿（买入/卖出记录不全），不参与勾稽' });
    }
  }

  const result: any = {
    date: targetDate,
    total_orders: dayTrades.length,
    matched: dayTrades.length - anomalies.filter(a => a.type === 'duplicate_trade' || a.type === 'missing_fields' || a.type === 'invalid_value').length,
    mismatched: anomalies.length,
    anomalies,
    note: '本地对账（后端 trade-verify 路由 404 丢失后的替代实现，2026-08-23）',
  };
  if (historyGaps.length > 0) result.history_gaps = historyGaps;  // undefined 字段会触发 not lossless JSON，按需拼装
  return result;
}
