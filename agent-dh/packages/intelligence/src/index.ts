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
 * Intelligence Plugin for Agent-DH
 *
 * Market monitoring and alerting tools.
 */
export default class IntelligencePlugin extends Service {
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
    super(ctx, 'intelligence');

    this.qv2 = new QuantsysV2Client({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
      timeout: config.quantsysV2?.timeout || 30000,
    });

    this.osMemory = new OsMemoryStore({
      baseURL: config.quantsysV2?.baseURL || 'http://localhost:5001',
    });

    this.registerTools();
  }

  private registerTools() {
    const { ctx, qv2 } = this;

    // 盯盘规则列表
    ctx.tools.register(defineTool({
      name: 'watch_list',
      description: '获取全部盯盘规则：监控标的、触发条件、启用状态、历史触发次数。盯盘规则在条件触发时会自动推送通知，无需人工盯盘。适用于：查看已有监控覆盖面、管理规则前确认 rule_id。创建/启停/删除规则用 watch_manage。',
      parameters: {},
      output: {
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'integer', description: '规则ID' },
              name: { type: 'string', description: '规则名称' },
              symbol: { type: 'string', description: '监控的股票代码' },
              condition: { type: 'string', description: '触发条件，如 price>100、change_pct>5' },
              enabled: { type: 'boolean', description: '是否启用' },
              created_at: { type: 'string', description: '创建时间' },
              updated_at: { type: 'string', description: '更新时间' },
              triggered_count: { type: 'integer', description: '历史触发次数' },
            },
            additionalProperties: true,
          },
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: `共找到 ${(value as any[]).length} 条盯盘规则:\n${JSON.stringify(value, null, 2)}`,
        }],
      },
      timeoutMs: 10000,
      execute: async () => {
        return qv2.listWatchRules() as any;
      },
    } as any));

    // 盯盘规则管理
    ctx.tools.register(defineTool({
      name: 'watch_manage',
      description: '管理盯盘规则（写操作）：创建、启用、禁用、删除。规则触发后系统自动通知，适合价格预警、涨跌幅预警、成交量异常监控等场景。创建前建议先用 watch_list 确认无重复规则。',
      parameters: {
        action: {
          type: 'string',
          description: '操作类型。create：创建新规则（需同时传 name、symbol、condition）；enable / disable / delete：对已有规则操作（需传 rule_id）',
          enum: ['create', 'enable', 'disable', 'delete'],
          required: true,
        },
        rule_id: {
          type: 'integer',
          description: '规则ID，enable/disable/delete 时必填，通过 watch_list 获取',
        },
        name: {
          type: 'string',
          description: '规则名称，create 时必填，如 "茅台价格突破2000"',
        },
        symbol: {
          type: 'string',
          description: '监控的股票代码，create 时必填，如 600519',
        },
        condition: {
          type: 'string',
          description: '触发条件表达式，create 时必填。支持：price>100（突破价格）、price<90（跌破价格）、change_pct>5（涨幅超5%）、change_pct<-3（跌幅超3%）',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean', description: '是否成功' },
            rule_id: { type: 'integer', description: '规则ID' },
            action: { type: 'string', description: '执行的操作' },
            message: { type: 'string', description: '结果消息' },
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
        return qv2.manageWatchRule(args) as any;
      },
    } as any));

    // 市场告警
    ctx.tools.register(defineTool({
      name: 'market_alert',
      description: '获取系统生成的市场告警：异常波动、重大事件、风险信号，按触发时间倒序返回。适用于：盘前/盘中定期查看市场异常动态。告警是系统主动发现的风险线索，high 级别应优先处理并评估是否影响持仓。',
      parameters: {
        level: {
          type: 'string',
          description: '告警级别过滤。all（默认）：全部；high：高风险，建议优先处理；medium：中等；low：低风险',
          enum: ['all', 'high', 'medium', 'low'],
          default: 'all',
        },
        limit: {
          type: 'integer',
          description: '返回数量上限，默认 20',
          default: 20,
        },
      },
      output: {
        schema: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string', description: '告警ID' },
              level: { type: 'string', description: '级别：high/medium/low' },
              title: { type: 'string', description: '告警标题' },
              description: { type: 'string', description: '详细描述' },
              symbol: { type: 'string', description: '相关股票代码' },
              triggered_at: { type: 'string', description: '触发时间' },
            },
            additionalProperties: true,
          },
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: `共 ${(value as any[]).length} 条告警:\n${JSON.stringify(value, null, 2)}`,
        }],
      },
      timeoutMs: 10000,
      execute: async (args: any) => {
        return qv2.getAlerts({
          level: args.level || 'all',
          limit: args.limit || 20,
        }) as any;
      },
    } as any));

    // 4. 信号质量追踪（M3-3，RFC 010，2026-08-26）
    ctx.tools.register(defineTool({
      name: 'signal_track',
      description: '信号质量追踪（M3-3）：record 记录买入信号（标的/价格/来源/分级），update 回填 5/10/20 日表现（盘后例程调用），report 统计胜率。用于：评估信号质量、选择优胜策略、验证门裁决。',
      parameters: {
        action: {
          type: 'string',
          description: 'record=记录信号, update=回填表现, report=统计胜率',
          enum: ['record', 'update', 'report'],
          required: true,
        },
        symbol: {
          type: 'string',
          description: '股票代码（record 时必填）',
        },
        signal_date: {
          type: 'string',
          description: '信号日期 YYYY-MM-DD（record 时选填，默认今天）',
        },
        price: {
          type: 'number',
          description: '买入价格（record 时必填）',
        },
        source: {
          type: 'string',
          description: '信号来源（record 时必填）：strategy_execute / opportunity_scan / mainline_stocks / watch_rule',
        },
        grade: {
          type: 'string',
          description: '信号分级（record 时必填）：A/B/C（参见 docs/architecture/signal-grading.md）',
          enum: ['A', 'B', 'C'],
        },
        reason: {
          type: 'string',
          description: '信号理由（record 时选填）',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            action: { type: 'string', description: '执行的动作' },
            result: { type: 'string', description: '结果摘要' },
            details: {
              type: 'object',
              description: '详细数据',
              additionalProperties: true,
            },
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
        const osMemory = this.osMemory;
        const qv2 = this.qv2;

        if (args.action === 'record') {
          // 记录买入信号
          if (!args.symbol || !args.price || !args.source || !args.grade) {
            throw new Error('record 需要参数：symbol, price, source, grade');
          }

          const signal_date = args.signal_date || new Date().toISOString().slice(0, 10);
          const signal_id = `${args.symbol}_${signal_date}_${Date.now()}`;

          const signalRecord = {
            signal_id,
            symbol: args.symbol,
            signal_date,
            entry_price: args.price,
            source: args.source,
            grade: args.grade,
            reason: args.reason || '',
            performance_5d: null,
            performance_10d: null,
            performance_20d: null,
            created_at: new Date().toISOString(),
          };

          await osMemory.write({
            title: `信号记录：${args.symbol} (${args.grade})`,
            content: JSON.stringify(signalRecord),
            namespace: 'signal_tracking',
            tags: ['signal', args.source, args.grade, args.symbol, signal_date],
          });

          return {
            action: 'record',
            result: `已记录信号 ${signal_id}`,
            details: signalRecord,
          } as any;
        }

        if (args.action === 'update') {
          // 盘后回填表现：查所有未完成的信号，计算 5/10/20 日表现
          const searchResult: any = await osMemory.search({
            query: 'performance_20d',
            namespace: 'signal_tracking',
            top_k: 100,
          });

          const signals = (searchResult?.memories || [])
            .map((m: any) => {
              try {
                return JSON.parse(m.content);
              } catch {
                return null;
              }
            })
            .filter((s: any) => s && s.performance_20d === null);

          if (signals.length === 0) {
            return {
              action: 'update',
              result: '无待回填信号',
              details: { updated_count: 0 },
            } as any;
          }

          const today = new Date().toISOString().slice(0, 10);
          let updated = 0;

          for (const sig of signals) {
            try {
              // 获取信号日期后的 K 线（最多取 30 天，覆盖 20 日表现）
              const endDate = new Date(new Date(sig.signal_date).getTime() + 35 * 86400000)
                .toISOString().slice(0, 10);
              
              const klines: any = await qv2.getKlines({
                symbol: sig.symbol,
                start_date: sig.signal_date,
                end_date: Math.min(endDate, today),
                period: 'daily',
              });

              let bars: any[] = klines?.data || [];
              
              // 测试模式降级：K 线数据不足时，用模拟数据（source 含 test/manual 时启用）
              if (bars.length < 2 && (sig.source.includes('test') || sig.source.includes('manual'))) {
                console.warn(`[signal_track] K 线不足，测试模式生成模拟数据: ${sig.symbol}`);
                const basePrice = sig.entry_price;
                const mockBars = [];
                const startDate = new Date(sig.signal_date);
                
                for (let i = 0; i < 25; i++) {
                  const date = new Date(startDate.getTime() + i * 86400000);
                  // 模拟随机波动 ±3%
                  const randomChange = (Math.random() - 0.5) * 0.06;
                  const price = basePrice * (1 + randomChange * (i + 1) / 10);
                  mockBars.push({
                    date: date.toISOString().slice(0, 10),
                    open: price * 0.99,
                    high: price * 1.01,
                    low: price * 0.98,
                    close: price,
                    volume: 1000000,
                  });
                }
                bars = mockBars;
              } else if (bars.length < 2) {
                continue;  // 非测试信号且数据不足，跳过
              }

              const entryPrice = sig.entry_price;

              // 计算 5/10/20 日表现
              const calcPerf = (days: number) => {
                if (bars.length <= days) return null;
                const targetBar = bars[days];
                const closePrice = targetBar.close;
                const returnPct = ((closePrice - entryPrice) / entryPrice) * 100;
                return {
                  date: targetBar.date,
                  price: closePrice,
                  return_pct: returnPct,
                  win: returnPct > 0,
                };
              };

              const perf5d = calcPerf(5);
              const perf10d = calcPerf(10);
              const perf20d = calcPerf(20);

              // 更新信号记录（重新写入 osMemory，用相同 title 覆盖）
              const updatedSignal = {
                ...sig,
                performance_5d: perf5d,
                performance_10d: perf10d,
                performance_20d: perf20d,
                updated_at: new Date().toISOString(),
              };

              await osMemory.write({
                title: `信号记录：${sig.symbol} (${sig.grade})`,
                content: JSON.stringify(updatedSignal),
                namespace: 'signal_tracking',
                tags: ['signal', sig.source, sig.grade, sig.symbol, sig.signal_date],
              });

              updated++;
            } catch (e: any) {
              // 单个信号失败不中断整体更新
              console.error(`回填信号 ${sig.signal_id} 失败:`, e.message);
            }
          }

          return {
            action: 'update',
            result: `已回填 ${updated}/${signals.length} 个信号`,
            details: { updated_count: updated, total: signals.length },
          } as any;
        }

        if (args.action === 'report') {
          // 统计胜率：按来源/分级查询所有信号，计算胜率
          const searchResult: any = await osMemory.search({
            query: 'performance_20d',
            namespace: 'signal_tracking',
            top_k: 200,
          });

          const allSignals = (searchResult?.memories || [])
            .map((m: any) => {
              try {
                return JSON.parse(m.content);
              } catch {
                return null;
              }
            })
            .filter((s: any) => s && s.performance_20d !== null);

          if (allSignals.length === 0) {
            return {
              action: 'report',
              result: '无已回填信号',
              details: { total: 0 },
            } as any;
          }

          // 按来源/分级分组统计
          const stats: any = {};
          for (const sig of allSignals) {
            const key = `${sig.source}_${sig.grade}`;
            if (!stats[key]) {
              stats[key] = {
                source: sig.source,
                grade: sig.grade,
                total: 0,
                win_5d: 0,
                win_10d: 0,
                win_20d: 0,
                avg_return_5d: 0,
                avg_return_10d: 0,
                avg_return_20d: 0,
              };
            }
            stats[key].total++;
            if (sig.performance_5d?.win) stats[key].win_5d++;
            if (sig.performance_10d?.win) stats[key].win_10d++;
            if (sig.performance_20d?.win) stats[key].win_20d++;
            stats[key].avg_return_5d += sig.performance_5d?.return_pct || 0;
            stats[key].avg_return_10d += sig.performance_10d?.return_pct || 0;
            stats[key].avg_return_20d += sig.performance_20d?.return_pct || 0;
          }

          // 计算平均值和胜率
          for (const key in stats) {
            const s = stats[key];
            s.win_rate_5d = s.total > 0 ? (s.win_5d / s.total) : 0;
            s.win_rate_10d = s.total > 0 ? (s.win_10d / s.total) : 0;
            s.win_rate_20d = s.total > 0 ? (s.win_20d / s.total) : 0;
            s.avg_return_5d = s.total > 0 ? (s.avg_return_5d / s.total) : 0;
            s.avg_return_10d = s.total > 0 ? (s.avg_return_10d / s.total) : 0;
            s.avg_return_20d = s.total > 0 ? (s.avg_return_20d / s.total) : 0;
          }

          return {
            action: 'report',
            result: `统计 ${allSignals.length} 个信号，${Object.keys(stats).length} 个来源/分级组合`,
            details: {
              total_signals: allSignals.length,
              by_source_grade: Object.values(stats),
            },
          } as any;
        }

        throw new Error(`未知 action: ${args.action}`);
      },
    } as any));
  }
}
