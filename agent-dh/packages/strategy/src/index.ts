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
    ctx.tools.register(defineTool({
      name: 'signal_track',
      description: '信号质量追踪：record 记录买入信号（标的/级别/入场价/理由）落库；update 对已记录信号回填 5/10/20 日前瞻收益（K线计算，supersede 更新原记录）；report 统计各来源信号的胜率。供：信号分级制（A/B/C）的效果验证、策略优胜劣汰、每日盘后例程。',
      parameters: {
        action: { type: 'string', description: 'record / update / report', enum: ['record', 'update', 'report'], required: true },
        symbol: { type: 'string', description: 'record 时必填：股票代码' },
        grade: { type: 'string', description: 'record 时必填：信号级别 A/B/C（docs/architecture/signal-grading.md）' },
        price: { type: 'number', description: 'record 时必填：信号产生时的价格' },
        source: { type: 'string', description: '信号来源：strategy_execute / opportunity_scan / mainline_stocks / watch_rule 等，record 时必填' },
        reason: { type: 'string', description: '信号理由（维度共振说明）' },
        signal_date: { type: 'string', description: '信号日期 YYYY-MM-DD，默认今天（补录历史信号时显式传）' },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            action: { type: 'string' },
            recorded: { type: 'object', additionalProperties: true },
            updated: { type: 'array', items: { type: 'object', additionalProperties: true } },
            report: { type: 'object', additionalProperties: true },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      timeoutMs: 60000,
      execute: async (args: any) => {
        const today = new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });

        if (args.action === 'record') {
          if (!args.symbol || !args.grade || !(args.price > 0) || !args.source) {
            throw new Error('record 需要 symbol/grade/price/source');
          }
          const sigDate = args.signal_date || today;
          const entry = {
            symbol: args.symbol,
            grade: String(args.grade).toUpperCase(),
            price: args.price,
            source: args.source,
            reason: args.reason ?? null,
            signal_date: sigDate,
            forward: {},  // {d5: pct, d10: pct, d20: pct} 由 update 回填
          };
          await qv2.createMemory({
            kind: 'episode',
            scope: 'signal:tracking',
            title: `signal ${sigDate} ${args.symbol} ${String(args.grade).toUpperCase()}级 @${args.price} (${args.source})`,
            content: `信号：${args.symbol} ${String(args.grade).toUpperCase()}级 @${args.price}，来源 ${args.source}。理由：${args.reason ?? '未填'}。前瞻收益待 update 回填。`,
            payload: entry,
            status: 'testing',
            confidence: 0.6,
            source: 'signal_track',
            provenance: { channel: 'dsh', session_kind: 'agent' },
          });
          return { action: 'record', recorded: entry } as any;
        }

        if (args.action === 'update') {
          // 找所有追踪中的信号，回填到期的前瞻收益
          const res = await qv2.searchMemory({ q: 'signal', scope: 'signal:tracking', limit: 100 });
          const items = (res?.items || []).filter((it: any) => it.status !== 'deprecated' && it.payload?.signal_date);
          const updated: any[] = [];

          for (const it of items) {
            const p = it.payload;
            const need5 = p.forward?.d5 === undefined;
            const need10 = p.forward?.d10 === undefined;
            const need20 = p.forward?.d20 === undefined;
            if (!need5 && !need10 && !need20) continue;

            // 取信号日之后的 K 线
            const klines: any[] = await qv2.getKlines(p.symbol, p.signal_date, today, 'daily');
            if (!klines || klines.length < 2) continue;
            const after = klines.filter((k: any) => k.trade_date > p.signal_date);
            const forward = { ...(p.forward || {}) };
            const closeAt = (n: number) => after.length >= n ? after[n - 1].close : null;
            const c5 = closeAt(5), c10 = closeAt(10), c20 = closeAt(20);
            if (need5 && c5 != null) forward.d5 = +(((c5 - p.price) / p.price) * 100).toFixed(2);
            if (need10 && c10 != null) forward.d10 = +(((c10 - p.price) / p.price) * 100).toFixed(2);
            if (need20 && c20 != null) forward.d20 = +(((c20 - p.price) / p.price) * 100).toFixed(2);

            if (JSON.stringify(forward) !== JSON.stringify(p.forward || {})) {
              const newPayload = { ...p, forward, last_updated: today };
              // supersede 原记录（历史只增不改，新版本带最新 forward）
              const created = await qv2.createMemory({
                kind: 'episode',
                scope: 'signal:tracking',
                title: it.title,
                content: `信号：${p.symbol} ${p.grade}级 @${p.price}，来源 ${p.source}。前瞻收益：5日 ${forward.d5 ?? '未满'}% / 10日 ${forward.d10 ?? '未满'}% / 20日 ${forward.d20 ?? '未满'}%。`,
                payload: newPayload,
                status: 'testing',
                confidence: 0.6,
                source: 'signal_track',
                provenance: { channel: 'dsh', session_kind: 'agent' },
              });
              // 2026-08-23 验收修复：supersede 路由要求 new_id（旧记录标 deprecated），
              // 原实现只传 reason 导致 400 静默失败、新旧双活重复计数
              const newId = created?.id;
              if (newId) {
                try {
                  await (qv2 as any).client.post(`/api/memory/${it.id}/supersede`, { new_id: newId });
                } catch { /* supersede 失败不阻塞 */ }
              }
              updated.push({ id: it.id, symbol: p.symbol, forward });
            }
          }
          return { action: 'update', updated, scanned: items.length } as any;
        }

        // report：各来源/级别的信号胜率
        const res = await qv2.searchMemory({ q: 'signal', scope: 'signal:tracking', limit: 100 });
        const items = (res?.items || []).filter((it: any) => it.status !== 'deprecated' && it.payload?.signal_date);
        const groups: Record<string, { total: number; evaluated: number; wins5: number; avg5: number | null; avg10: number | null; avg20: number | null }> = {};
        for (const it of items) {
          const p = it.payload;
          const key = `${p.source}/${p.grade}级`;
          if (!groups[key]) groups[key] = { total: 0, evaluated: 0, wins5: 0, avg5: null, avg10: null, avg20: null };
          const g = groups[key];
          g.total++;
          const f5 = p.forward?.d5, f10 = p.forward?.d10, f20 = p.forward?.d20;
          if (f5 !== undefined) { g.evaluated++; if (f5 > 0) g.wins5++; g.avg5 = +(((g.avg5 ?? 0) * (g.evaluated - 1) + f5) / g.evaluated).toFixed(2); }
          if (f10 !== undefined) g.avg10 = f10;  // MVP：均值留待样本增多后完善
          if (f20 !== undefined) g.avg20 = f20;
        }
        const report = {
          total_signals: items.length,
          by_source_grade: Object.entries(groups).map(([k, g]) => ({
            group: k, total: g.total, evaluated_5d: g.evaluated,
            win_rate_5d: g.evaluated > 0 ? +(g.wins5 / g.evaluated).toFixed(3) : null,
            avg_return_5d: g.avg5,
          })),
        };
        return { action: 'report', report } as any;
      },
    } as any));
  }
}
